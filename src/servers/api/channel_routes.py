#!/usr/bin/env python3
"""APIRouter routes extracted from api_server.py: channel routes."""

from fastapi import APIRouter
from . import api_server as _api

globals().update({name: value for name, value in vars(_api).items() if not name.startswith("__")})
router = APIRouter()

class ChannelConfig(BaseModel):
    """Channel configuration"""
    name: str = Field(..., description="Channel name")
    type: str = Field(..., description="Channel type (smtp, sms, whatsapp, chat_rest)")
    enabled: Optional[bool] = Field(default=True, description="Whether channel is enabled")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Channel-specific config")
    limits: Optional[Dict[str, Any]] = Field(default=None, description="Rate limits")


class TestChannelRequest(BaseModel):
    """Request to test a channel"""
    destination: str = Field(..., description="Test destination")
    test_message: Optional[str] = Field(default="Test notification", description="Test message")


@router.get("/channels", dependencies=[Depends(verify_api_key)])
async def list_channels(request: Request):
    """List all channels (W28A-744: scoped to the caller's RBAC bindings — IDAM-B2 §2.3)."""
    # Run blocking database operation in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    channels = await loop.run_in_executor(None, channel_repo.list_all)
    # IDAM-B2 cascade list-filter: a GROUPUSER sees ONLY channels bound to their group.
    channels = _scope_channels_for_caller(request, channels)

    # Mask sensitive config
    for channel in channels:
        stats = db.fetchone(
            """
            SELECT COUNT(DISTINCT message_id) AS message_count, MAX(created_at) AS last_used
            FROM deliveries
            WHERE channel_id = ?
            """,
            (channel["id"],),
        )
        channel["message_count"] = int((stats or {}).get("message_count") or 0)
        channel["last_used"] = (stats or {}).get("last_used")
        if channel["config_json"]:
            config_data = json.loads(channel["config_json"])
            channel["config"] = config.mask_secrets(config_data)
            del channel["config_json"]

    return channels


@router.get("/channels/{channel_id}", dependencies=[Depends(verify_api_key)])
async def get_channel(channel_id: int, request: Request):
    """Get channel by ID (W28A-744: cascade point-check — IDAM-B2 §2.3)."""
    if not _authorise_channel_read(request, channel_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised for this channel",
        )
    loop = asyncio.get_event_loop()
    channel = await loop.run_in_executor(None, channel_repo.get_by_id, channel_id)

    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Parse and mask config
    if channel["config_json"]:
        config_data = json.loads(channel["config_json"])
        channel["config"] = config.mask_secrets(config_data)
    del channel["config_json"]

    if channel["limits_json"]:
        channel["limits"] = json.loads(channel["limits_json"])
    del channel["limits_json"]

    return channel


@router.post("/channels", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def create_channel(channel_config: ChannelConfig, request: Request):
    """Create a new channel (W28A-744: requires channel.write — IDAM-B2 §3.1 graded)"""
    if not _authorise_channel_write(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised to write channels")
    # Check if name already exists
    existing = channel_repo.get_by_name(channel_config.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel name already exists",
        )

    # Create channel
    channel_id = channel_repo.create(
        name=channel_config.name,
        channel_type=channel_config.type,
        enabled=channel_config.enabled,
        config_json=json.dumps(channel_config.config) if channel_config.config else None,
        limits_json=json.dumps(channel_config.limits) if channel_config.limits else None,
    )

    # Register adapter
    if channel_config.enabled:
        adapter_registry.register_channel(
            channel_id=channel_id,
            channel_type=channel_config.type,
            config=channel_config.config or {},
        )
    created_payload = {
        "id": channel_id,
        "name": channel_config.name,
        "type": channel_config.type,
        "enabled": channel_config.enabled,
        "config": channel_config.config or {},
        "limits": channel_config.limits or {},
    }
    await _broadcast_config_event("channel", "created", created_payload)
    return {"id": channel_id, "name": channel_config.name}


@router.post("/channels/{channel_id}/test", dependencies=[Depends(verify_api_key)])
async def test_channel(channel_id: int, test_request: TestChannelRequest):
    """Test a channel with a sample send"""

    channel = channel_repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Get adapter
    adapter = adapter_registry.get_adapter(channel_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Channel adapter not initialized",
        )

    # Validate destination
    if not adapter.validate_destination(test_request.destination):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid destination format",
        )

    # Keep channel test endpoint responsive even when external providers are slow.
    channel_test_timeout = float(config.get("api_server.channel_test_timeout") or 8.0)

    # Send test
    message_guid = uuid4().hex
    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            adapter.send({
                "destination": test_request.destination,
                "message_guid": message_guid,
                "personalised_payload": test_request.test_message,
            }),
            timeout=channel_test_timeout,
        )
    except TimeoutError:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": f"Channel test timed out after {channel_test_timeout:.1f}s",
            "error_class": "transient",
            "latency_ms": latency_ms,
        }
    latency_ms = int((time.time() - start_time) * 1000)

    if result.success:
        return {
            "success": True,
            "tracking_id": result.tracking_id,
            "latency_ms": latency_ms,
        }
    else:
        return {
            "success": False,
            "error": result.error,
            "error_class": result.error_class.value if result.error_class else None,
        }


@router.post("/channels/{channel_id}/enable", dependencies=[Depends(verify_api_key)])
async def enable_channel(channel_id: int, request: Request):
    """Enable a channel (W28A-744: cascade write point-check)"""
    if not _authorise_channel_write(request, channel_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this channel")
    channel_repo.update(channel_id, {"enabled": True})
    updated_channel = channel_repo.get_by_id(channel_id)
    if updated_channel:
        channel_config = json.loads(updated_channel.get("config_json") or "{}")
        adapter_registry.register_channel(
            channel_id=channel_id,
            channel_type=updated_channel["type"],
            config=channel_config,
        )
        await _broadcast_config_event("channel", "enabled", updated_channel)
    return {"enabled": True}


@router.post("/channels/{channel_id}/disable", dependencies=[Depends(verify_api_key)])
async def disable_channel(channel_id: int, request: Request):
    """Disable a channel (W28A-744: cascade write point-check)"""
    if not _authorise_channel_write(request, channel_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this channel")
    channel_repo.update(channel_id, {"enabled": False})
    if adapter_registry:
        adapter_registry.unregister_channel(channel_id)
    updated_channel = channel_repo.get_by_id(channel_id)
    if updated_channel:
        await _broadcast_config_event("channel", "disabled", updated_channel)
    return {"enabled": False}


@router.patch("/channels/{channel_id}", dependencies=[Depends(verify_api_key)])
async def update_channel(channel_id: int, updates: dict, request: Request):
    """
    Update channel configuration (W28A-744: cascade write point-check)

    Accepts partial updates to channel fields:
    - name, type, enabled
    - config_json (endpoint, auth, format)
    - limits_json (rate limits)
    - restrictions_json (max_length, allowed_formats, link_strategy)
    - preferences_json (default language, content_style)
    """
    if not _authorise_channel_write(request, channel_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this channel")
    # Convert JSON strings if provided as dicts
    for json_field in ['config_json', 'limits_json', 'restrictions_json', 'preferences_json']:
        if json_field in updates and isinstance(updates[json_field], dict):
            updates[json_field] = json.dumps(updates[json_field])

    channel_repo.update(channel_id, updates)
    updated_channel = channel_repo.get_by_id(channel_id)
    if not updated_channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if adapter_registry:
        adapter_registry.unregister_channel(channel_id)
        if int(updated_channel.get("enabled") or 0):
            channel_config = json.loads(updated_channel.get("config_json") or "{}")
            adapter_registry.register_channel(
                channel_id=channel_id,
                channel_type=updated_channel["type"],
                config=channel_config,
            )
    await _broadcast_config_event("channel", "updated", updated_channel)
    return updated_channel


@router.delete("/channels/{channel_id}", dependencies=[Depends(verify_api_key)])
async def delete_channel(channel_id: int, request: Request):
    """Delete a channel by ID (W28A-744: cascade write point-check)"""
    if not _authorise_channel_write(request, channel_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorised for this channel")
    channel = channel_repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    delivery_count = channel_repo.count_deliveries(channel_id)
    if delivery_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "channel_in_use",
                "message": "Channel has associated deliveries; disable it instead of deleting it.",
                "channel_id": channel_id,
                "delivery_count": delivery_count,
            },
        )

    try:
        if adapter_registry:
            adapter_registry.unregister_channel(channel_id)
        channel_repo.delete(channel_id)
        await _broadcast_config_event("channel", "deleted", channel)
        return {"deleted": True}
    except Exception as e:
        logger.error(f"Failed to delete channel {channel_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "channel_delete_failed",
                "message": "Channel could not be deleted. Disable it instead and retry after dependent records are archived.",
                "channel_id": channel_id,
            },
        )


# ============================================================================
# LLM Prompts endpoints
# ============================================================================
