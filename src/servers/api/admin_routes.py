#!/usr/bin/env python3
"""APIRouter routes extracted from api_server.py: admin routes."""

from fastapi import APIRouter
from . import api_server as _api

globals().update({name: value for name, value in vars(_api).items() if not name.startswith("__")})
router = APIRouter()

class APIKeyCreateRequest(BaseModel):
    """Request model for creating an admin API key."""

    owner_user_id: str = Field(..., description="Owner identifier for the generated API key")
    ttl_days: Optional[int] = Field(default=None, ge=1, description="Optional TTL in days")
    ttl_seconds: Optional[int] = Field(default=None, ge=1, description="Optional TTL in seconds (lifecycle testing)")
    key_prefix: Optional[str] = Field(default=None, description="Optional key prefix")


class ConfigQueryRequest(BaseModel):
    """Request model for querying configuration settings"""
    keys: List[str] = Field(..., description="List of configuration keys to retrieve (e.g., 'app.default_language', 'llm.model')")


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration settings"""
    updates: Dict[str, Any] = Field(..., description="Map of configuration keys to new values")
    persist: bool = Field(default=False, description="Persist updates to env file when enabled")


@router.post("/config/query", dependencies=[Depends(verify_api_key)])
async def query_config(query: ConfigQueryRequest):
    """
    Query system configuration settings

    Accepts an array of configuration keys and returns their current values.
    Uses dot notation for nested keys (e.g., 'app.default_language', 'llm.model')

    Example:
        POST /config/query
        {"keys": ["app.default_language", "llm.model", "llm.temperature"]}

        Returns:
        {
            "app.default_language": "en",
            "llm.model": "<model-name>",
            "llm.temperature": 0.3
        }
    """
    result = {}
    for key in query.keys:
        value = config.get(key, None)
        result[key] = value

    return result


@router.post("/config/update", dependencies=[Depends(verify_admin)])
async def update_config(update: ConfigUpdateRequest):
    """Update configuration values (optionally persist to env file)."""
    if not config:
        raise HTTPException(status_code=500, detail="Configuration not loaded")

    updates = update.updates or {}
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    for key, value in updates.items():
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise HTTPException(status_code=400, detail=f"Unsupported value type for {key}")
        config.set(key, value)

    persisted = False
    if update.persist:
        if not config.get("app.env_write_enabled"):
            raise HTTPException(status_code=403, detail="Env write disabled by configuration")
        try:
            config.persist_env_updates(updates)
            persisted = True
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Env write failed: {exc}")

    init_cache_from_config(config)
    await invalidate_event("config_change")

    return {"updated": updates, "persisted": persisted}


@router.get("/jobs", dependencies=[Depends(verify_api_key)])
async def list_jobs(limit: int = 100):
    """List recorded queue jobs for WebUI operational visibility."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    jobs = list(runtime.backend.all_jobs())
    jobs.sort(
        key=lambda item: (
            getattr(item, "created_at", None).isoformat()
            if getattr(item, "created_at", None) is not None
            else ""
        ),
        reverse=True,
    )
    limited = jobs[: max(1, min(int(limit or 100), 500))]
    payload = [_encode_job(job) for job in limited]
    return {"total": len(jobs), "items": payload}


@router.get("/jobs/queue/status", dependencies=[Depends(verify_api_key)])
async def get_job_queue_status():
    """Return queue status counts for Jobs page summary metrics."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    return jsonable_encoder(runtime.queue_status())


@router.get("/jobs/{job_id}", dependencies=[Depends(verify_api_key)])
async def get_job(job_id: str):
    """Return a single recorded queue job."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    job = runtime.backend.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _encode_job(job)


@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_job(job_id: str):
    """Cancel a queued/running job."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    job = runtime.backend.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status_name = _job_status_name(job)
    if status_name in _terminal_job_statuses():
        return {"cancelled": False, "status": status_name}
    return {"cancelled": _set_job_status(job, JobStatus.CANCELLED.value, action="job.cancel")}


@router.post("/jobs/{job_id}/retry", dependencies=[Depends(verify_api_key)])
async def retry_job(job_id: str):
    """Retry a terminal job by returning it to queued state."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    job = runtime.backend.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status_name = _job_status_name(job)
    if status_name not in {
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.TIMEOUT.value,
        JobStatus.DEAD_LETTERED.value,
    }:
        return {"retried": False, "status": status_name}
    return {"retried": _set_job_status(job, JobStatus.QUEUED.value, action="job.retry")}


@router.delete("/jobs/{job_id}", dependencies=[Depends(verify_admin)])
async def delete_job(job_id: str):
    """Archive a terminal job for Jobs page cleanup."""
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    job = runtime.backend.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    status_name = _job_status_name(job)
    if status_name not in _terminal_job_statuses():
        raise HTTPException(status_code=409, detail=f"Job {job_id} is not in a terminal state")
    return {"deleted": _set_job_status(job, JobStatus.ARCHIVED.value, action="job.archive")}


# Status endpoint

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def get_status():
    """Get system status and metrics"""
    from ...database.repositories import MessageRepository

    message_repo = MessageRepository(db)
    queue_depth = message_repo.count(status="queued") + message_repo.count(status="processing")

    channels = channel_repo.list_all()
    channel_states = {}
    for channel in channels:
        channel_states[channel["name"]] = {
            "type": channel["type"],
            "enabled": channel["enabled"],
            "circuit_state": channel["circuit_state"],
            "error_count": channel["error_count"],
        }

    delivered_row = db.fetchone("SELECT COUNT(*) AS count FROM deliveries WHERE state = 'delivered'") or {"count": 0}
    terminal_row = db.fetchone(
        """
        SELECT COUNT(*) AS count
        FROM deliveries
        WHERE state IN ('delivered', 'sent', 'accepted', 'failed', 'soft_failed', 'hard_failed', 'bounced')
        """
    ) or {"count": 0}
    messages_24h_row = db.fetchone(
        "SELECT COUNT(*) AS count FROM messages WHERE created_at >= datetime('now', '-1 day')"
    ) or {"count": 0}
    retry_queue_row = db.fetchone(
        "SELECT COUNT(*) AS count FROM deliveries WHERE state IN ('soft_failed', 'deferred')"
    ) or {"count": 0}
    oldest_queue_row = db.fetchone(
        """
        SELECT MIN(created_at) AS created_at
        FROM deliveries
        WHERE state IN ('queued', 'processing', 'formatting', 'soft_failed', 'deferred')
        """
    ) or {"created_at": None}

    delivered_count = int(delivered_row.get("count") or 0)
    terminal_count = int(terminal_row.get("count") or 0)
    retry_queue_size = int(retry_queue_row.get("count") or 0)
    messages_sent_24h = int(messages_24h_row.get("count") or 0)
    delivery_success_rate = round((delivered_count / terminal_count) * 100.0, 1) if terminal_count else None

    # W28A-569: Collect resource metrics via psutil
    _proc = psutil.Process()
    uptime_seconds = max(0, int(time.time() - _proc.create_time()))
    memory_mb = round(_proc.memory_info().rss / (1024 * 1024), 1)
    memory_percent = round(float(_proc.memory_percent()), 1)
    cpu_percent = round(float(psutil.cpu_percent(interval=0.1)), 1)
    disk_percent = round(float(psutil.disk_usage("/").percent), 1)
    active_connections = 0

    oldest_queue_item_age_seconds = None
    oldest_created_at = oldest_queue_row.get("created_at")
    if oldest_created_at:
        try:
            oldest_dt = datetime.fromisoformat(str(oldest_created_at))
            oldest_queue_item_age_seconds = max(0, int((datetime.now() - oldest_dt).total_seconds()))
        except Exception:
            oldest_queue_item_age_seconds = None

    return {
        "uptime_seconds": uptime_seconds,
        "memory_mb": memory_mb,
        "memory_percent": memory_percent,
        "cpu_percent": cpu_percent,
        "disk_percent": disk_percent,
        "active_connections": active_connections,
        "channel_count": len(channels),
        "messages_sent_24h": messages_sent_24h,
        "delivery_success_rate": delivery_success_rate,
        "queue_depth": queue_depth,
        "retry_queue_size": retry_queue_size,
        "oldest_queue_item_age_seconds": oldest_queue_item_age_seconds,
        "channels": channel_states,
        "timestamp": datetime.now().isoformat(),
    }


# Config endpoint

@router.get("/config", dependencies=[Depends(verify_api_key)])
async def get_config_dump():
    """Get configuration (with secrets masked)"""
    return config.dump(mask_secrets=True)


@router.get("/llm/status", dependencies=[Depends(verify_api_key)])
async def get_llm_status():
    """Get LLM availability and queue status"""
    return await _get_effective_llm_status()


# Messages endpoints

class PromptCreate(BaseModel):
    """Request model for creating a prompt"""
    name: str = Field(..., description="Prompt name")
    prompt_text: str = Field(..., description="Prompt template text")
    channel_type: Optional[str] = Field(default=None, description="Channel type (email, sms, whatsapp, slack, teams)")
    group_id: Optional[int] = Field(default=None, description="Group ID for group-specific prompts")
    language: Optional[str] = Field(default=None, description="Language code (en, fr, de, etc.)")
    keyword: Optional[str] = Field(default=None, description="Keyword for keyword-specific prompts")
    variables_json: Optional[str] = Field(default=None, description="JSON schema for prompt variables")
    priority: int = Field(default=0, description="Priority (higher = selected first)")
    enabled: bool = Field(default=True, description="Whether prompt is enabled")


class PromptUpdate(BaseModel):
    """Request model for updating a prompt"""
    name: Optional[str] = Field(default=None, description="Prompt name")
    prompt_text: Optional[str] = Field(default=None, description="Prompt template text")
    variables_json: Optional[str] = Field(default=None, description="JSON schema for prompt variables")
    priority: Optional[int] = Field(default=None, description="Priority (higher = selected first)")
    enabled: Optional[bool] = Field(default=None, description="Whether prompt is enabled")


@router.post("/prompts", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def create_prompt(prompt_data: PromptCreate):
    """Create a new LLM prompt"""
    from ...database.repositories import LLMPromptRepository

    # Get database connection
    db = get_db_manager()
    prompt_repo = LLMPromptRepository(db)

    # Validate channel type if provided
    if prompt_data.channel_type and prompt_data.channel_type not in ["email", "sms", "whatsapp", "slack", "teams"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel_type: {prompt_data.channel_type}. Must be one of: email, sms, whatsapp, slack, teams"
        )

    # Validate prompt text is not empty
    if not prompt_data.prompt_text or not prompt_data.prompt_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt_text cannot be empty"
        )

    # Validate group exists if group_id provided
    if prompt_data.group_id:
        from ...database.repositories import GroupRepository
        group_repo = GroupRepository(db)
        group = group_repo.get_by_id(prompt_data.group_id)
        if not group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Group {prompt_data.group_id} not found"
            )

    # Create prompt
    loop = asyncio.get_event_loop()
    prompt_id = await loop.run_in_executor(
        None,
        prompt_repo.create,
        prompt_data.name,
        prompt_data.prompt_text,
        prompt_data.channel_type,
        prompt_data.group_id,
        prompt_data.language,
        prompt_data.keyword,
        prompt_data.variables_json,
        prompt_data.priority,
        prompt_data.enabled,
    )

    # Get the created prompt to return full object
    prompt = await loop.run_in_executor(None, prompt_repo.get_by_id, prompt_id)
    await invalidate_event("prompt_change")
    return prompt


@router.get("/prompts", dependencies=[Depends(verify_api_key)])
async def list_prompts(
    channel_type: Optional[str] = None,
    group_id: Optional[int] = None,
    language: Optional[str] = None,
    keyword: Optional[str] = None,
    enabled_only: bool = True,
):
    """List LLM prompts with optional filters"""
    from ...database.repositories import LLMPromptRepository

    db = get_db_manager()
    prompt_repo = LLMPromptRepository(db)

    loop = asyncio.get_event_loop()
    prompts = await loop.run_in_executor(
        None,
        prompt_repo.list_all,
        channel_type,
        group_id,
        enabled_only,
    )

    # Additional filtering for language and keyword
    if language:
        prompts = [p for p in prompts if p.get("language") == language or p.get("language") is None]
    if keyword:
        prompts = [p for p in prompts if p.get("keyword") == keyword or p.get("keyword") is None]

    return prompts


@router.get("/prompts/{prompt_id}", dependencies=[Depends(verify_api_key)])
async def get_prompt(prompt_id: int):
    """Get a specific prompt by ID"""
    from ...database.repositories import LLMPromptRepository

    db = get_db_manager()
    prompt_repo = LLMPromptRepository(db)

    loop = asyncio.get_event_loop()
    prompt = await loop.run_in_executor(None, prompt_repo.get_by_id, prompt_id)

    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    return prompt


@router.patch("/prompts/{prompt_id}", dependencies=[Depends(verify_api_key)])
async def update_prompt(prompt_id: int, updates: PromptUpdate):
    """Update a prompt"""
    from ...database.repositories import LLMPromptRepository

    db = get_db_manager()
    prompt_repo = LLMPromptRepository(db)

    # Check prompt exists
    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    # Validate prompt text if provided
    if updates.prompt_text is not None and (not updates.prompt_text or not updates.prompt_text.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="prompt_text cannot be empty"
        )

    # Update prompt
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        prompt_repo.update,
        prompt_id,
        updates.name,
        updates.prompt_text,
        updates.variables_json,
        updates.priority,
        updates.enabled,
    )

    # Return updated prompt
    updated_prompt = await loop.run_in_executor(None, prompt_repo.get_by_id, prompt_id)
    await invalidate_event("prompt_change")
    return updated_prompt


@router.delete("/prompts/{prompt_id}", dependencies=[Depends(verify_api_key)])
async def delete_prompt(prompt_id: int):
    """Delete a prompt"""
    from ...database.repositories import LLMPromptRepository

    db = get_db_manager()
    prompt_repo = LLMPromptRepository(db)

    # Check prompt exists
    prompt = prompt_repo.get_by_id(prompt_id)
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prompt not found"
        )

    # Delete prompt
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, db.execute, "DELETE FROM llm_prompts WHERE id = ?", (prompt_id,))
    await loop.run_in_executor(None, db.commit)
    await invalidate_event("prompt_change")

    return {"deleted": True, "id": prompt_id}


class GroupCreate(BaseModel):
    """Request model for creating a group"""
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(default=None, description="Group description")
    language: Optional[str] = Field(default=None, description="Group language preference")
    preferred_channel: Optional[str] = Field(default=None, description="Group preferred channel")
    content_style: Optional[str] = Field(default=None, description="Group content style")
    enabled: bool = Field(default=True, description="Whether group is enabled")


class GroupMemberCreate(BaseModel):
    """Request model for adding a group member"""
    user_id: int = Field(..., description="User ID")
    role: str = Field(default="member", description="Member role (admin, member)")


class GroupKeywordCreate(BaseModel):
    """Request model for adding a keyword to a group"""
    keyword: str = Field(..., description="Keyword to add")


class GroupUpdate(BaseModel):
    """Request model for updating a group"""
    description: Optional[str] = Field(default=None, description="Group description")
    language: Optional[str] = Field(default=None, description="Group language preference")
    preferred_channel: Optional[str] = Field(default=None, description="Group preferred channel")
    content_style: Optional[str] = Field(default=None, description="Group content style")
    enabled: Optional[bool] = Field(default=None, description="Whether group is enabled")


@router.get("/groups", dependencies=[Depends(verify_api_key)])
async def list_groups():
    """List all groups"""
    from ...database.repositories import GroupRepository

    db = get_db_manager()
    group_repo = GroupRepository(db)

    loop = asyncio.get_event_loop()
    groups = await loop.run_in_executor(None, group_repo.list_all)

    return groups


@router.get("/groups/{group_id:int}", dependencies=[Depends(verify_api_key)])
async def get_group(group_id: int):
    """Get group by ID"""
    from ...core.groups.group_manager import GroupManager

    db = get_db_manager()
    manager = GroupManager(db)

    loop = asyncio.get_event_loop()
    group = await loop.run_in_executor(None, manager.get_group, group_id)

    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    return group


@router.post("/groups", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def create_group(group_data: GroupCreate):
    """Create a new group"""
    from ...database.repositories import GroupRepository

    db = get_db_manager()
    group_repo = GroupRepository(db)

    # Check if name already exists
    existing = group_repo.get_by_name(group_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Group name already exists"
        )

    # Create group
    loop = asyncio.get_event_loop()
    group_id = await loop.run_in_executor(
        None,
        group_repo.create,
        group_data.name,
        group_data.description,
        group_data.language,
        group_data.preferred_channel,
        group_data.content_style,
        group_data.enabled,
    )
    await _broadcast_config_event(
        "group",
        "created",
        {
            "id": group_id,
            "name": group_data.name,
            "description": group_data.description,
            "language": group_data.language,
            "preferred_channel": group_data.preferred_channel,
            "content_style": group_data.content_style,
            "enabled": group_data.enabled,
        },
    )
    return {"success": True, "group_id": group_id, "id": group_id, "name": group_data.name}


@router.patch("/groups/{group_id:int}", dependencies=[Depends(verify_admin)])
async def admin_update_group(group_id: int, group_data: GroupUpdate):
    """Update an existing group by numeric ID"""
    from ...core.groups.group_manager import GroupManager

    db = get_db_manager()
    manager = GroupManager(db)

    loop = asyncio.get_event_loop()
    group = await loop.run_in_executor(None, manager.group_repo.get_by_id, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    await loop.run_in_executor(
        None,
        manager.update_group,
        group_id,
        group_data.description,
        group_data.language,
        group_data.preferred_channel,
        group_data.content_style,
        group_data.enabled,
    )

    updated = await loop.run_in_executor(None, manager.group_repo.get_by_id, group_id)
    await _broadcast_config_event("group", "updated", updated or {"id": group_id})
    return {"success": True, "id": group_id, "group": updated}


@router.get("/groups/{group_id:int}/members", dependencies=[Depends(verify_api_key)])
async def list_group_members(group_id: int):
    """List members of a group"""
    from ...database.repositories import GroupMemberRepository

    db = get_db_manager()
    member_repo = GroupMemberRepository(db)

    loop = asyncio.get_event_loop()
    members = await loop.run_in_executor(None, member_repo.get_group_members, group_id)

    return members


@router.post("/groups/{group_id:int}/members", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def add_group_member(group_id: int, member_data: GroupMemberCreate):
    """Add a member to a group"""
    from ...database.repositories import GroupRepository, GroupMemberRepository

    db = get_db_manager()
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)

    # Check group exists
    loop = asyncio.get_event_loop()
    group = await loop.run_in_executor(None, group_repo.get_by_id, group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )

    # Add member (add_member returns None if already exists)
    member_id = await loop.run_in_executor(
        None,
        member_repo.add_member,
        group_id,
        member_data.user_id,
        member_data.role,
    )

    if member_id is None:
        # Already a member, just return success
        return {"id": 0, "group_id": group_id, "user_id": member_data.user_id, "note": "Already a member"}
    # Register group membership in RBAC engine for PS-70 UM3 group propagation
    uid_str = str(member_data.user_id)
    idam_runtime.rbac_engine.add_user_to_group(uid_str, f"group:{group_id}")
    # Flush prefixed cache keys (cloud_dog_idam cache uses "roles:X"/"perms:X" keys)
    idam_runtime.rbac_engine._cache.invalidate(f"roles:{uid_str}")  # noqa: SLF001
    idam_runtime.rbac_engine._cache.invalidate(f"perms:{uid_str}")  # noqa: SLF001
    await _broadcast_config_event(
        "group",
        "member_added",
        {"group_id": group_id, "member_id": member_id, "user_id": member_data.user_id, "role": member_data.role},
    )
    return {"id": member_id, "group_id": group_id, "user_id": member_data.user_id}


@router.delete("/groups/{group_id:int}/members/{member_id:int}", dependencies=[Depends(verify_admin)])
async def remove_group_member(group_id: int, member_id: int):
    """Remove a member from a group"""
    from ...database.repositories import GroupMemberRepository

    db = get_db_manager()
    member_repo = GroupMemberRepository(db)

    loop = asyncio.get_event_loop()
    members = await loop.run_in_executor(None, member_repo.get_group_members, group_id)
    member = next((item for item in members if int(item.get("id") or 0) == member_id), None)
    if member is not None:
        await loop.run_in_executor(None, member_repo.remove_member_by_id, member_id)
        payload = {"group_id": group_id, "member_id": member_id, "user_id": member.get("user_id")}
    else:
        await loop.run_in_executor(None, member_repo.remove_member, group_id, member_id)
        payload = {"group_id": group_id, "user_id": member_id}
    # Remove from RBAC engine for PS-70 UM3 group propagation
    removed_user_id = str(payload.get("user_id", member_id))
    memberships = idam_runtime.rbac_engine._group_memberships.get(removed_user_id, set())  # noqa: SLF001
    memberships.discard(f"group:{group_id}")
    idam_runtime.rbac_engine._cache.invalidate(f"roles:{removed_user_id}")  # noqa: SLF001
    idam_runtime.rbac_engine._cache.invalidate(f"perms:{removed_user_id}")  # noqa: SLF001
    await _broadcast_config_event("group", "member_removed", payload)
    return {"success": True, "message": "Member removed"}


@router.post("/groups/{group_id:int}/rbac-role", dependencies=[Depends(verify_admin)])
async def set_group_rbac_role(group_id: int, body: dict = None):
    """Assign an RBAC role to a group for PS-70 UM3 group-based permission propagation."""
    body = body or {}
    role_name = str(body.get("role", "")).strip()
    if not role_name:
        raise HTTPException(status_code=400, detail="role is required")
    idam_runtime.rbac_engine.assign_role_to_group(f"group:{group_id}", role_name)
    return {"success": True, "group_id": group_id, "rbac_role": role_name}



@router.post("/groups/{group_id:int}/keywords", dependencies=[Depends(verify_api_key)])
async def add_group_keyword(group_id: int, keyword_data: GroupKeywordCreate):
    """Add a keyword to a group on the root API surface used behind /api/v1."""
    from ...core.groups.group_manager import GroupManager

    db = get_db_manager()
    manager = GroupManager(db)

    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    added = manager.add_keyword(group_id, keyword_data.keyword)
    if not added:
        return {"success": True, "message": "Keyword already exists", "keyword": keyword_data.keyword}

    await _broadcast_config_event("group", "keyword_added", {"group_id": group_id, "keyword": keyword_data.keyword})
    return {"success": True, "message": "Keyword added", "keyword": keyword_data.keyword}


@router.delete("/groups/{group_id:int}/keywords/{keyword}", dependencies=[Depends(verify_api_key)])
async def remove_group_keyword(group_id: int, keyword: str):
    """Remove a keyword from a group on the root API surface used behind /api/v1."""
    from ...core.groups.group_manager import GroupManager

    db = get_db_manager()
    manager = GroupManager(db)

    group = manager.group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    manager.remove_keyword(group_id, keyword)
    await _broadcast_config_event("group", "keyword_removed", {"group_id": group_id, "keyword": keyword})
    return {"success": True, "message": "Keyword removed"}


@router.delete("/groups/{group_id:int}", dependencies=[Depends(verify_admin)])
async def delete_group(group_id: int):
    """Delete a group (FULL CRUD)"""
    from ...database.repositories import GroupRepository

    db = get_db_manager()
    group_repo = GroupRepository(db)

    # Check if group exists
    existing = group_repo.get_by_id(group_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group {group_id} not found"
        )

    # Delete group (cascade deletes members)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, db.execute, "DELETE FROM groups WHERE id = ?", (group_id,))
    await loop.run_in_executor(None, db.commit)
    await _broadcast_config_event("group", "deleted", existing)
    return {"deleted": True, "id": group_id}


# ============================================================================
# Users endpoints
# ============================================================================

class UserCreate(BaseModel):
    """Request model for creating a user"""
    username: Optional[str] = Field(default=None, description="Username")
    email: str = Field(..., description="Email address")
    display_name: Optional[str] = Field(default=None, description="Display name")
    name: Optional[str] = Field(default=None, description="Legacy display name field")
    password: Optional[str] = Field(default=None, description="Optional password value")
    role: str = Field(default="user", description="User role")
    user_type: str = Field(default="real", description="User type")
    language: Optional[str] = Field(default=None, description="Language preference (ISO 639-1: en, fr, de, pl, etc.)")
    preferred_channel: Optional[str] = Field(default=None, description="Preferred channel")
    content_style: Optional[str] = Field(default=None, description="Preferred content style")
    channel_preferences: Optional[Any] = Field(default=None, description="Legacy channel preferences payload")
    metadata: Optional[Any] = Field(default=None, description="Legacy metadata payload")
    is_active: Optional[bool] = Field(default=True, description="Legacy active flag")


class UserPatch(BaseModel):
    """Request model for updating a user"""
    display_name: Optional[str] = Field(default=None, description="Display name")
    name: Optional[str] = Field(default=None, description="Legacy display name field")
    language: Optional[str] = Field(default=None, description="Language preference")
    preferred_channel: Optional[str] = Field(default=None, description="Preferred channel")
    content_style: Optional[str] = Field(default=None, description="Content style")
    channel_preferences: Optional[Any] = Field(default=None, description="Legacy channel preferences payload")


class UserPreferencesUpdate(BaseModel):
    """Request model for updating user delivery preferences."""
    language: Optional[str] = Field(default=None, description="Language preference")
    preferred_channel: Optional[str] = Field(default=None, description="Preferred channel")
    content_style: Optional[str] = Field(default=None, description="Content style")
    timezone: Optional[str] = Field(default=None, description="User timezone")


class UserDestinationCreate(BaseModel):
    """Request model for adding a user destination."""
    channel_type: Optional[str] = Field(default=None, description="Channel type")
    channel: Optional[str] = Field(default=None, description="Legacy channel type field")
    destination: Optional[str] = Field(default=None, description="Destination address")
    address: Optional[str] = Field(default=None, description="Legacy destination address field")
    is_primary: bool = Field(default=False, description="Whether this is the primary destination")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional destination metadata")


def _parse_json_value(raw: Any) -> Optional[Any]:
    """Parse legacy JSON-in-string payloads if present."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return None
    return None


def _extract_channel_preferences(raw: Any) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract channel, language and style from legacy channel_preferences payload."""
    parsed = _parse_json_value(raw)
    if not isinstance(parsed, dict) or not parsed:
        return None, None, None
    channel_name = next(iter(parsed.keys()))
    pref_payload = parsed.get(channel_name)
    if not isinstance(pref_payload, dict):
        return channel_name, None, None
    language = pref_payload.get("language")
    content_style = pref_payload.get("content_style")
    return channel_name, language, content_style


def _normalise_username(username: Optional[str], email: str, display_name: Optional[str]) -> str:
    """Build a deterministic username when clients omit one."""
    candidate = (username or "").strip()
    if not candidate:
        candidate = (email.split("@", 1)[0] if "@" in email else "").strip()
    if not candidate:
        candidate = (display_name or "").strip().lower()
    candidate = re.sub(r"[^a-zA-Z0-9_.-]+", "_", candidate or "").strip("._-")
    return candidate or f"user_{uuid4().hex[:8]}"


@router.get("/users", dependencies=[Depends(verify_api_key)])
async def list_users(
    request: Request,
    q: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 1000,
):
    """List users (optionally filtered by q/email)."""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)

    loop = asyncio.get_event_loop()
    safe_limit = max(1, min(int(limit), 1000))

    if email:
        user = await loop.run_in_executor(None, user_repo.get_by_email, email)
        users = [user] if user else []
        return {"total": len(users), "items": users}

    if q:
        users = await loop.run_in_executor(None, user_repo.search, q, safe_limit)
        return {"total": len(users), "items": users}

    users = await loop.run_in_executor(None, user_repo.list_all, safe_limit)
    return {"total": len(users), "items": users}


# ── PS-71 §IW1/§IW2 canonical IDAM admin aliases (W28A-876) ──────────────────
# The shared @cloud-dog/idam WebUI fetches /v1/admin/{users,groups}. notif already
# manages users/groups (via /users, /groups); expose them at the canonical /admin/*
# path so the Users and Groups pages render (parity with file/db/git which serve
# /admin/users + /admin/groups). normalizeIdamEnvelope handles {items:[...]} / list.
@router.get("/admin/users", dependencies=[Depends(verify_api_key)])
async def list_admin_users(
    request: Request,
    q: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 1000,
):
    """Canonical Users list for the shared IDAM WebUI (alias of /users)."""
    return await list_users(request, q=q, email=email, limit=limit)


@router.get("/admin/groups", dependencies=[Depends(verify_api_key)])
async def list_admin_groups():
    """Canonical Groups list for the shared IDAM WebUI (alias of /groups)."""
    return await list_groups()


@router.get("/users/{user_id}", dependencies=[Depends(verify_api_key)])
async def get_user(user_id: int):
    """Get user by ID"""
    from ...core.users.user_manager import UserManager

    db = get_db_manager()
    manager = UserManager(db)

    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(None, manager.get_user_with_destinations, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


@router.post("/users", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def create_user(user_data: UserCreate):
    """Create a new user"""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)

    # Check if email already exists
    existing = user_repo.get_by_email(user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    display_name = user_data.display_name or user_data.name
    channel_name, cp_language, cp_style = _extract_channel_preferences(user_data.channel_preferences)
    language = user_data.language or cp_language
    preferred_channel = user_data.preferred_channel or channel_name
    content_style = user_data.content_style or cp_style
    username = _normalise_username(user_data.username, user_data.email, display_name)

    # Keep username unique for legacy clients that only send email/name.
    if not user_data.username:
        suffix = 2
        base = username
        while user_repo.get_by_username(username):
            username = f"{base}_{suffix}"
            suffix += 1
    else:
        existing_username = user_repo.get_by_username(username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

    # Create user (legacy compatibility: fall back to display_name/default when password is absent).
    password_hash = idam_runtime.hash_password(user_data.password or display_name or "default_password")
    loop = asyncio.get_event_loop()
    user_id = await loop.run_in_executor(
        None,
        user_repo.create,
        username,
        user_data.email,
        password_hash,
        user_data.role,
        display_name,
        user_data.user_type,
        language,
        preferred_channel,
        content_style,
        None,  # timezone
    )
    await _broadcast_config_event(
        "user",
        "created",
        {
            "id": user_id,
            "username": username,
            "email": user_data.email,
            "display_name": display_name,
            "role": user_data.role,
            "language": language,
            "preferred_channel": preferred_channel,
            "content_style": content_style,
        },
    )
    return {
        "success": True,
        "user_id": user_id,
        "id": user_id,
        "username": username,
        "email": user_data.email,
        "message": "User created successfully",
    }


@router.patch("/users/{user_id}", dependencies=[Depends(verify_admin)])
async def patch_user(user_id: int, update: UserPatch):
    """Patch user profile fields required by AT compatibility paths."""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    display_name = update.display_name or update.name
    channel_name, cp_language, cp_style = _extract_channel_preferences(update.channel_preferences)
    language = update.language or cp_language
    preferred_channel = update.preferred_channel or channel_name
    content_style = update.content_style or cp_style

    if any(v is not None for v in (language, preferred_channel, content_style)):
        await loop.run_in_executor(
            None,
            user_repo.update_preferences,
            user_id,
            language,
            preferred_channel,
            content_style,
            None,
        )

    if display_name is not None:
        await loop.run_in_executor(
            None,
            db.execute,
            "UPDATE users SET display_name = ? WHERE id = ?",
            (display_name, user_id),
        )
        await loop.run_in_executor(None, db.commit)

    updated = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    await _broadcast_config_event("user", "updated", updated)
    return updated


@router.put("/users/{user_id}/preferences", dependencies=[Depends(verify_api_key)])
async def update_user_preferences(user_id: int, preferences: UserPreferencesUpdate):
    """Update user preferences on the root API surface used behind /api/v1."""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await loop.run_in_executor(
        None,
        user_repo.update_preferences,
        user_id,
        preferences.language,
        preferences.preferred_channel,
        preferences.content_style,
        preferences.timezone,
    )

    updated = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    await _broadcast_config_event("user", "updated", updated)
    return {"success": True, "message": "Preferences updated"}


@router.post("/users/{user_id}/destinations", dependencies=[Depends(verify_api_key)])
async def add_user_destination(user_id: int, destination_data: UserDestinationCreate):
    """Add a destination for a user on the root API surface used behind /api/v1."""
    from ...core.users.user_manager import UserManager

    db = get_db_manager()
    manager = UserManager(db)
    loop = asyncio.get_event_loop()

    user = await loop.run_in_executor(None, manager.user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    channel_type = destination_data.channel_type or destination_data.channel
    destination = destination_data.destination or destination_data.address
    if not channel_type or not destination:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="channel_type and destination are required")

    destination_id = await loop.run_in_executor(
        None,
        manager.add_destination,
        user_id,
        channel_type,
        destination,
        destination_data.is_primary,
        destination_data.metadata,
    )

    payload = {
        "user_id": user_id,
        "destination_id": destination_id,
        "channel_type": channel_type,
        "destination": destination,
    }
    await _broadcast_config_event("user", "destination_added", payload)
    return {"success": True, **payload}


@router.delete("/users/{user_id}/destinations/{destination_id}", dependencies=[Depends(verify_api_key)])
async def remove_user_destination(user_id: int, destination_id: int):
    """Remove a destination from a user on the root API surface used behind /api/v1."""
    from ...core.users.user_manager import UserManager

    db = get_db_manager()
    manager = UserManager(db)
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(None, manager.remove_destination, destination_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    await _broadcast_config_event("user", "destination_removed", {"user_id": user_id, "destination_id": destination_id})
    return {"success": True, "message": "Destination removed"}


@router.post("/users/{user_id}/destinations/{destination_id}/primary", dependencies=[Depends(verify_api_key)])
async def set_user_primary_destination(user_id: int, destination_id: int):
    """Set a user destination as primary on the root API surface used behind /api/v1."""
    from ...core.users.user_manager import UserManager

    db = get_db_manager()
    manager = UserManager(db)
    loop = asyncio.get_event_loop()

    try:
        await loop.run_in_executor(None, manager.set_primary_destination, destination_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    await _broadcast_config_event("user", "destination_primary", {"user_id": user_id, "destination_id": destination_id})
    return {"success": True, "message": "Primary destination set"}


@router.delete("/users/{user_id}", dependencies=[Depends(verify_admin)])
async def delete_user(user_id: int):
    """Delete a user (full CRUD support)"""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)

    # Check if user exists
    user = user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Delete user (cascade will handle user_keywords via FK)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    )
    await loop.run_in_executor(None, db.commit)
    await _broadcast_config_event("user", "deleted", user)
    return {"message": f"User {user_id} deleted successfully"}


# ============================================================================
# User Keywords endpoints
# ============================================================================

class UserKeywordCreate(BaseModel):
    """Request model for adding a keyword to a user"""
    keyword: str = Field(..., description="Keyword to add (e.g., 'urgent', 'formal', 'technical')")


@router.get("/users/{user_id}/keywords", dependencies=[Depends(verify_api_key)])
async def list_user_keywords(user_id: int):
    """List all keywords for a user"""
    from ...database.repositories import UserRepository, UserKeywordRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    keyword_repo = UserKeywordRepository(db)

    # Check user exists
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get keywords
    keywords = await loop.run_in_executor(None, keyword_repo.get_by_user_id, user_id)

    return keywords


@router.post("/users/{user_id}/keywords", dependencies=[Depends(verify_api_key)])
async def add_user_keyword(user_id: int, keyword_data: UserKeywordCreate):
    """Add a keyword to a user"""
    from ...database.repositories import UserRepository, UserKeywordRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    keyword_repo = UserKeywordRepository(db)

    # Check user exists
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Add keyword (returns None if already exists)
    keyword_id = await loop.run_in_executor(
        None,
        keyword_repo.add,
        user_id,
        keyword_data.keyword,
    )

    if keyword_id is None:
        # Already exists, just return success
        return {"id": 0, "user_id": user_id, "keyword": keyword_data.keyword, "note": "Keyword already exists"}

    return {"id": keyword_id, "user_id": user_id, "keyword": keyword_data.keyword}


@router.delete("/users/{user_id}/keywords/{keyword}", dependencies=[Depends(verify_api_key)])
async def remove_user_keyword(user_id: int, keyword: str):
    """Remove a keyword from a user"""
    from ...database.repositories import UserRepository, UserKeywordRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    keyword_repo = UserKeywordRepository(db)

    # Check user exists
    loop = asyncio.get_event_loop()
    user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Remove keyword
    await loop.run_in_executor(None, keyword_repo.remove, user_id, keyword)

    return {"deleted": True, "user_id": user_id, "keyword": keyword}


# ============================================================================
# Admin API key endpoints
# ============================================================================


@router.get("/admin/api-keys", dependencies=[Depends(verify_api_key)])
async def list_admin_api_keys(owner_user_id: Optional[str] = None):
    """List provisioned API keys without exposing raw key material."""
    keys = idam_runtime.api_key_manager.list_keys(owner_id=owner_user_id)
    items = [_serialise_api_key_item(item) for item in keys]
    return {"items": items, "total": len(items)}


@router.post("/admin/api-keys", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def create_admin_api_key(request: APIKeyCreateRequest):
    """Generate a new API key for admin surfaces."""
    raw_key, metadata = idam_runtime.api_key_manager.generate(
        request.owner_user_id,
        ttl_days=request.ttl_days,
        key_prefix=request.key_prefix,
    )
    # Support seconds-based TTL for lifecycle testing (PS-70 UM4 expiry proof)
    if request.ttl_seconds is not None:
        from datetime import datetime, timedelta, timezone
        key_item = next(
            (k for k in idam_runtime.api_key_manager._keys.values()  # noqa: SLF001
             if k.api_key_id == metadata.api_key_id),
            None,
        )
        if key_item is not None:
            key_item.expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.ttl_seconds)
    payload = _serialise_api_key_item(metadata, include_raw_key=raw_key)
    await _broadcast_config_event("api_key", "created", payload)
    return payload


@router.delete("/admin/api-keys/{key_id}", dependencies=[Depends(verify_admin)])
async def revoke_admin_api_key(key_id: str):
    """Revoke an existing API key by identifier."""
    existing = next(
        (item for item in idam_runtime.api_key_manager.list_keys() if str(item.api_key_id) == str(key_id)),
        None,
    )
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    revoked = idam_runtime.api_key_manager.revoke(key_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="API key could not be revoked")

    await _broadcast_config_event("api_key", "revoked", _serialise_api_key_item(existing))
    return {"revoked": True, "id": key_id}


# ============================================================================
# Admin Roles endpoints (PS-71 IW3A) — canonical cloud_dog_idam role store
# ============================================================================


class RoleCreateRequest(BaseModel):
    """Request model for creating a role."""

    name: str = Field(..., description="Role name (unique)")
    description: Optional[str] = Field(default="", description="Role description")
    permissions: List[str] = Field(default_factory=list, description="Permission strings granted to the role")


class RoleUpdateRequest(BaseModel):
    """Request model for updating a role."""

    description: Optional[str] = Field(default=None, description="Role description")
    permissions: Optional[List[str]] = Field(default=None, description="Replacement permission set")


def _get_roles_service():
    """Build a roles admin service bound to the live DatabaseManager engine."""
    from .admin_identity_roles import RolesAdminService

    manager = get_db_manager()
    if not getattr(manager, "engine", None):
        manager.connect()
    engine = getattr(manager, "engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Database engine unavailable")
    return RolesAdminService(engine=engine)


def _roles_error_to_http(exc) -> HTTPException:
    return HTTPException(status_code=getattr(exc, "status", 400), detail=str(exc))


@router.get("/admin/roles", dependencies=[Depends(verify_api_key)])
async def list_admin_roles():
    """List role definitions backed by the canonical cloud_dog_idam role store."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        roles = await loop.run_in_executor(None, service.list_roles)
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)
    return {"items": roles, "total": len(roles)}


@router.get("/admin/roles/{role_id}", dependencies=[Depends(verify_api_key)])
async def get_admin_role(role_id: str):
    """Fetch a single role definition by identifier."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, service.get_role, role_id)
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)


@router.post("/admin/roles", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_admin)])
async def create_admin_role(request: RoleCreateRequest):
    """Create a new role definition."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        role = await loop.run_in_executor(
            None,
            lambda: service.create_role(
                name=request.name,
                description=request.description or "",
                permissions=request.permissions or [],
            ),
        )
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)
    await _broadcast_config_event("role", "created", role)
    return role


@router.put("/admin/roles/{role_id}", dependencies=[Depends(verify_admin)])
async def replace_admin_role(role_id: str, request: RoleUpdateRequest):
    """Update an existing role definition (PUT)."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        role = await loop.run_in_executor(
            None,
            lambda: service.update_role(role_id, data=request.model_dump(exclude_unset=True)),
        )
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)
    await _broadcast_config_event("role", "updated", role)
    return role


@router.patch("/admin/roles/{role_id}", dependencies=[Depends(verify_admin)])
async def patch_admin_role(role_id: str, request: RoleUpdateRequest):
    """Patch an existing role definition (PATCH)."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        role = await loop.run_in_executor(
            None,
            lambda: service.update_role(role_id, data=request.model_dump(exclude_unset=True)),
        )
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)
    await _broadcast_config_event("role", "updated", role)
    return role


@router.delete("/admin/roles/{role_id}", dependencies=[Depends(verify_admin)])
async def delete_admin_role(role_id: str):
    """Delete a role definition. Baseline roles are protected (403)."""
    from .admin_identity_roles import RolesAdminError

    service = _get_roles_service()
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, service.delete_role, role_id)
    except RolesAdminError as exc:
        raise _roles_error_to_http(exc)
    await _broadcast_config_event("role", "deleted", result)
    return result


@router.post("/tests/llm/run", dependencies=[Depends(verify_api_key)])
async def run_llm_tests(
    test_type: str = "all",
    prompt_file: Optional[str] = None,
    content_file: Optional[str] = None
):
    """
    Run LLM functionality tests via API

    Args:
        test_type: Type of test to run - "connection", "translation", "formatting", "summarization", "combined", or "all"
        prompt_file: Optional path to prompt file (defaults to tests/system/ST1.18_LLMFunctionality/test_prompt.txt)
        content_file: Optional path to content file (defaults to tests/system/ST1.18_LLMFunctionality/test_content.txt)

    Returns:
        Test results with summary and detailed results
    """
    try:
        import subprocess
        from pathlib import Path

        # Get test file paths from config or use defaults
        config = _runtime_config()
        if not prompt_file:
            prompt_file = config.get("test.llm_prompt_file", "tests/system/ST1.18_LLMFunctionality/test_prompt.txt")
        if not content_file:
            content_file = config.get("test.llm_content_file", "tests/system/ST1.18_LLMFunctionality/test_content.txt")

        # Build pytest command
        test_file = "tests/system/ST1.18_LLMFunctionality/test_llm_functionality.py"
        env_file = config.get("env_file", "private/env-test")

        # Determine which test to run
        test_name = None
        if test_type == "connection":
            test_name = "test_llm_connection"
        elif test_type == "translation":
            test_name = "test_llm_translation"
        elif test_type == "formatting":
            test_name = "test_llm_formatting"
        elif test_type == "summarization":
            test_name = "test_llm_summarization"
        elif test_type == "combined":
            test_name = "test_llm_combined_instructions"
        # "all" means run all tests

        # Build command
        cmd = [
            "python3", "-m", "pytest",
            test_file,
            "--env", env_file,
            "-v",
            "--tb=short"
        ]

        if test_name:
            cmd.append(f"::{test_name}")

        # Run tests
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=api_subprocess_timeout,
            cwd=Path(__file__).parent.parent.parent.parent
        )

        # Parse results
        output_lines = result.stdout.split('\n')
        passed = "passed" in result.stdout.lower() and "failed" not in result.stdout.lower()

        # Extract test results
        test_results = []
        for line in output_lines:
            if "PASSED" in line or "FAILED" in line or "ERROR" in line:
                if "::" in line:
                    test_name_match = line.split("::")[-1].split()[0]
                    status = "PASSED" if "PASSED" in line else "FAILED" if "FAILED" in line else "ERROR"
                    test_results.append({
                        "test": test_name_match,
                        "status": status
                    })

        return {
            "success": result.returncode == 0,
            "test_type": test_type,
            "passed": passed,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "test_results": test_results,
            "summary": {
                "total": len(test_results),
                "passed": sum(1 for t in test_results if t["status"] == "PASSED"),
                "failed": sum(1 for t in test_results if t["status"] == "FAILED"),
                "errors": sum(1 for t in test_results if t["status"] == "ERROR")
            }
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Test execution timed out after 10 minutes",
            "test_type": test_type
        }
    except Exception as e:
        logger.error(f"Error running LLM tests: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tests/llm/status", dependencies=[Depends(verify_api_key)])
async def get_llm_test_status():
    """Get available LLM test types and configuration"""
    config = _runtime_config()
    return {
        "available_tests": [
            "connection",
            "translation",
            "formatting",
            "summarization",
            "combined",
            "all"
        ],
        "config": {
            "prompt_file": config.get("test.llm_prompt_file", "tests/system/ST1.18_LLMFunctionality/test_prompt.txt"),
            "content_file": config.get("test.llm_content_file", "tests/system/ST1.18_LLMFunctionality/test_content.txt"),
            "llm_provider": config.get("llm.provider"),
            "llm_model": config.get("llm.model"),
            "llm_temperature": config.get("llm.temperature"),
            "llm_base_url": config.get("llm.base_url")
        }
    }


@router.get("/debug/psutil")
async def debug_psutil():
    import time as _t
    result = {"psutil_available": psutil is not None, "psutil_version": getattr(psutil, "__version__", None)}
    if psutil is not None:
        try:
            p = psutil.Process()
            result["pid"] = p.pid
            result["uptime"] = max(0, int(_t.time() - p.create_time()))
            result["memory_mb"] = round(p.memory_info().rss / 1048576, 1)
            result["cpu"] = round(psutil.cpu_percent(interval=0.1), 1)
            result["disk"] = round(psutil.disk_usage("/").percent, 1)
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
    return result
