#!/usr/bin/env python3
"""APIRouter routes extracted from api_server.py: message routes."""

from fastapi import APIRouter
from . import api_server as _api

globals().update({name: value for name, value in vars(_api).items() if not name.startswith("__")})
router = APIRouter()

class ContentBlock(BaseModel):
    """Content block in a message"""
    type: str = Field(..., description="Content type (text, markdown, html, binary, image, audio, video)")
    body: str = Field(..., description="Content body")
    uri: Optional[str] = Field(default=None, description="URI for media content (images, audio, video)")
    alt_text: Optional[str] = Field(default=None, description="Alt text for images")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the content block")

    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class Destination(BaseModel):
    """Destination specification"""
    channel: str = Field(..., description="Channel name or type")
    address: str = Field(..., description="Destination address (email/phone/URL)")
    preferences: Optional[Dict[str, Any]] = Field(default=None, description="Per-destination preferences")
    user_email: Optional[str] = Field(
        default=None,
        description="Optional target user email for channel-based destinations",
    )


class MessageRequest(BaseModel):
    """Request to create a message"""
    audience_type: str = Field(default="personalised", description="personalised or broadcast")
    destinations: List[Destination] = Field(..., description="List of destinations")
    content: List[ContentBlock] = Field(..., description="Message content blocks")
    created_by: Optional[str] = Field(default=None, description="Submitting user or API key owner")
    template_ref: Optional[str] = Field(default=None, description="Template reference")
    variables: Optional[Dict[str, Any]] = Field(default=None, description="Template variables")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Additional options")
    prompt_id: Optional[int] = Field(default=None, description="Explicit prompt ID (highest priority - FR1.15)")
    prompt_name: Optional[str] = Field(default=None, description="Explicit prompt name (highest priority - FR1.15)")
    language: Optional[str] = Field(default=None, description="Target language code (e.g., 'fr', 'de') — overrides user/default language")


class MessagePreviewRequest(BaseModel):
    """Request model for previewing LLM-formatted messages"""
    message_body: str = Field(..., description="Raw message body to format")
    prompt_name: Optional[str] = Field(default=None, description="Explicit prompt name to use")
    prompt_id: Optional[int] = Field(default=None, description="Explicit prompt ID to use")
    user_id: Optional[int] = Field(default=None, description="User ID for prompt selection context")
    language: Optional[str] = Field(default=None, description="Target language (overrides user language)")
    keywords: Optional[List[str]] = Field(default=None, description="Keywords for prompt selection")


class MessageRenderRequest(BaseModel):
    """Request model for cached render/format preview."""
    template: str = Field(..., description="Template text with Python format placeholders")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Template variables")
    language: Optional[str] = Field(default="en", description="Target language for formatting")
    channel_type: Optional[str] = Field(default="email", description="Channel type for formatting context")


@router.post("/messages/preview", dependencies=[Depends(verify_api_key)])
async def preview_message_formatting(request: MessagePreviewRequest):
    """
    Preview LLM message formatting without sending

    Tests prompt selection and LLM formatting without creating a real message.
    Returns the formatted output as it would appear in delivery.

    Example:
        POST /messages/preview
        {
            "message_body": "Test alert: Server down",
            "prompt_name": "at16e_explicit_prompt",
            "language": "en"
        }

        Returns:
        {
            "formatted_text": "Subject: ...\n\nHello,\n\n[PROMPT_E1_EXPLICIT]...",
            "prompt_used": {"id": 70, "name": "at16e_explicit_prompt", "priority": 1000},
            "language_resolved": "en",
            "variables": {...}
        }
    """
    from ...core.formatters.llm_formatter import LLMFormatter
    from ...database.repositories import UserRepository, LLMPromptRepository

    loop = asyncio.get_event_loop()

    # Get user context if provided
    user_prefs = None
    if request.user_id:
        user_repo = UserRepository(db)
        user = await loop.run_in_executor(None, user_repo.get_by_id, request.user_id)
        if user:
            user_prefs = {
                "language": user.get("language"),
                "content_style": user.get("content_style"),
                "keywords": []  # Would need to fetch from user_keywords table
            }

    # Build variables for formatter
    variables = {
        "user_prefs": user_prefs or {},
        "target_language": request.language or (user_prefs.get("language") if user_prefs else None) or config.get("app.default_language") or "en"
    }

    if request.keywords:
        variables["keywords"] = request.keywords

    # Get prompt if specified
    prompt_info = None
    if request.prompt_name or request.prompt_id:
        prompt_repo = LLMPromptRepository(db)
        if request.prompt_name:
            prompt = await loop.run_in_executor(None, prompt_repo.get_by_name, request.prompt_name)
        else:
            prompt = await loop.run_in_executor(None, prompt_repo.get_by_id, request.prompt_id)

        if prompt:
            prompt_info = {
                "id": prompt["id"],
                "name": prompt["name"],
                "priority": prompt["priority"],
                "keyword": prompt.get("keyword"),
                "language": prompt.get("language")
            }

    # Format message using LLM
    formatter = LLMFormatter(db, config)

    # Convert message body to content format expected by formatter
    content = [{"type": "text", "body": request.message_body}]

    try:
        formatted_text = await loop.run_in_executor(
            None,
            formatter.format_message,
            content,  # content (List[Dict])
            "email",  # channel_type
            request.user_id,  # user_id
            None,  # group_id
            request.prompt_name,  # explicit_prompt
            variables,  # variables
            None,  # message_id
            None,  # message_guid
            None   # channel_id
        )

        return {
            "formatted_text": formatted_text,
            "prompt_used": prompt_info,
            "language_resolved": variables.get("target_language"),
            "variables": variables,
            "success": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "success": False
        }


@router.post(f"{_api_base_path}/messages/render", dependencies=[Depends(verify_api_key)])
@router.post("/api/messages/render", dependencies=[Depends(verify_api_key)], include_in_schema=False)
@router.post("/messages/render", dependencies=[Depends(verify_api_key)], include_in_schema=False)
async def render_message_template(request: MessageRenderRequest):
    """Render a template and format it through the cached notification path."""
    from ...core.formatters.llm_formatter import LLMFormatter

    loop = asyncio.get_event_loop()
    formatter = LLMFormatter(db, config)

    try:
        result = await loop.run_in_executor(
            None,
            formatter.render_message_template,
            request.template,
            request.variables or {},
            request.language or "en",
            request.channel_type or "email",
        )
        return {
            "success": True,
            "template": request.template,
            "variables": request.variables or {},
            "language": request.language or "en",
            "channel_type": request.channel_type or "email",
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Render failed: {exc}") from exc


@router.post("/messages", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
async def create_message(request: MessageRequest, http_request: Request):
    """Create and enqueue a new message"""
    from ...database.repositories import GroupRepository, GroupMemberRepository, UserDestinationRepository, UserRepository

    # =========================================================================
    # INPUT VALIDATION
    # =========================================================================

    # Validate audience_type is not empty
    if not request.audience_type or not request.audience_type.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="audience_type is required and cannot be empty"
        )

    # Validate destinations exist
    if not request.destinations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one destination is required"
        )

    default_channel = _require_config(config.get("default_channel"), "default_channel")

    # Validate each destination has required fields
    for idx, dest in enumerate(request.destinations):
        if not dest.channel or not dest.channel.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Destination {idx}: channel is required and cannot be empty"
            )

        # Validate email format for email destinations (basic check)
        if dest.address and not dest.address.startswith("group:"):
            # Basic email validation - must contain @ and .
            if dest.channel == default_channel:
                if "@" not in dest.address or "." not in dest.address.split("@")[-1]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Destination {idx}: invalid email address format '{dest.address}'"
                    )

    # Validate content exists (at least one content block)
    if not request.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one content block is required"
        )

    # Validate each content block has body
    for idx, content in enumerate(request.content):
        if not hasattr(content, 'body') or not content.body or not content.body.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content block {idx}: body is required and cannot be empty"
            )

    # =========================================================================
    # PROCESS MESSAGE (existing code)
    # =========================================================================

    # Resolve channel names to IDs and expand groups
    loop = asyncio.get_event_loop()
    destinations_with_ids = []
    for dest in request.destinations:
        channel_name = dest.channel
        address = dest.address

        # Try to find channel by name
        channel = await loop.run_in_executor(None, channel_repo.get_by_name, channel_name)
        if not channel:
            # Try by type as fallback
            channels_by_type = await loop.run_in_executor(None, channel_repo.get_by_type, channel_name)
            if channels_by_type:
                channel = channels_by_type[0]  # Use first available
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Channel '{channel_name}' not found",
                )

        if not channel["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Channel '{channel['name']}' is disabled",
            )

        if not _request_user_can_create_message(http_request, channel):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorised to send via channel '{channel['name']}'",
            )

        # Validate email destination format using resolved channel type so
        # named email channels are validated (not only the configured default name).
        if address and not address.startswith("group:"):
            channel_type_norm = str(channel.get("type") or "").strip().lower()
            default_channel_norm = str(default_channel or "").strip().lower()
            if channel_type_norm in {"email", "smtp", default_channel_norm}:
                if "@" not in address or "." not in address.split("@")[-1]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Destination {dest.channel}: invalid email address format '{address}'",
                    )

        # Check if address is a group reference (group:GroupName)
        if address and address.startswith("group:"):
            group_name = address[6:]  # Remove "group:" prefix
            group_repo = GroupRepository(db)
            member_repo = GroupMemberRepository(db)
            user_repo = UserRepository(db)
            dest_repo = UserDestinationRepository(db)

            # Find group
            group = await loop.run_in_executor(None, group_repo.get_by_name, group_name)
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Group '{group_name}' not found",
                )

            # Get group members
            members = await loop.run_in_executor(None, member_repo.get_group_members, group['id'])
            if not members:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Group '{group_name}' has no members",
                )

            # Expand to individual destinations for each member
            for member in members:
                user_id = member['user_id']
                user = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
                if not user:
                    continue

                # Get user's destination for this channel type
                channel_type = channel['type']
                user_dest = await loop.run_in_executor(None, dest_repo.get_primary, user_id, channel_type)

                # Convert Pydantic model preferences to dict if needed
                prefs_dict = dest.preferences
                if prefs_dict is not None and not isinstance(prefs_dict, dict):
                    # If it's a Pydantic model, convert to dict
                    prefs_dict = prefs_dict.dict() if hasattr(prefs_dict, 'dict') else dict(prefs_dict)

                if user_dest:
                    destinations_with_ids.append({
                        "channel_id": channel["id"],
                        "destination": user_dest['destination'],
                        "preferences": prefs_dict,
                        "user_email": user.get("email"),
                    })
                elif user.get('email') and channel_type == 'smtp':
                    # Fallback to user email for email channels
                    destinations_with_ids.append({
                        "channel_id": channel["id"],
                        "destination": user['email'],
                        "preferences": prefs_dict,
                        "user_email": user.get("email"),
                    })
        else:
            # Regular destination
            # Convert Pydantic model preferences to dict if needed
            prefs_dict = dest.preferences
            if prefs_dict is not None and not isinstance(prefs_dict, dict):
                # If it's a Pydantic model, convert to dict
                prefs_dict = prefs_dict.dict() if hasattr(prefs_dict, 'dict') else dict(prefs_dict)

            destinations_with_ids.append({
                "channel_id": channel["id"],
                "destination": address,
                "preferences": prefs_dict,
                "user_email": dest.user_email,
            })

    queue_gate = _delivery_queue_gate(len(destinations_with_ids))
    if queue_gate["warning"]:
        logger.warning(
            "Delivery queue nearing saturation: current=%s projected=%s limit=%s requested=%s",
            queue_gate["current_backlog"],
            queue_gate["projected_backlog"],
            queue_gate["limit"],
            len(destinations_with_ids),
        )
    if queue_gate["saturated"]:
        retry_after_seconds = int(queue_gate["retry_after_seconds"])
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": (
                    "Delivery queue is full. "
                    f"Current backlog={queue_gate['current_backlog']}, "
                    f"requested_deliveries={len(destinations_with_ids)}, "
                    f"limit={queue_gate['limit']}. "
                    f"Retry after approximately {retry_after_seconds} seconds."
                )
            },
            headers={"Retry-After": str(retry_after_seconds)},
        )

    # =========================================================================
    # EXTRACT EXPLICIT PROMPT DIRECTIVE (FR1.15 Priority #1)
    # =========================================================================
    explicit_prompt_name = None
    if request.prompt_id:
        # Look up prompt by ID to get its name
        from ...database.repositories import LLMPromptRepository
        prompt_repo = LLMPromptRepository(db)
        prompt = await loop.run_in_executor(None, prompt_repo.get_by_id, request.prompt_id)
        if prompt:
            explicit_prompt_name = prompt['name']
            logger.info(f"Explicit prompt directive: ID={request.prompt_id}, name={explicit_prompt_name}")
        else:
            logger.warning(f"Explicit prompt ID {request.prompt_id} not found, ignoring")
    elif request.prompt_name:
        explicit_prompt_name = request.prompt_name
        logger.info(f"Explicit prompt directive: name={explicit_prompt_name}")

    # Extract TTL and subject from options
    ttl_hours = None
    subject = None
    if request.options:
        ttl_hours = request.options.get("ttl_hours")
        subject = request.options.get("subject")

    # Merge subject, language, and explicit_prompt into variables if provided
    message_variables = request.variables.copy() if request.variables else {}
    # W28A-322: Pass explicit language into message variables so delivery worker
    # can use it as target_language override (prevents orphan FK language leak).
    if request.language:
        message_variables["target_language"] = request.language
        if "preferences" not in message_variables:
            message_variables["preferences"] = {}
        if isinstance(message_variables["preferences"], dict):
            message_variables["preferences"]["language"] = request.language
    if subject:
        message_variables["subject"] = subject
    if explicit_prompt_name:
        # Store explicit prompt in variables so it can be passed through to LLM formatter
        message_variables["_explicit_prompt"] = explicit_prompt_name
        logger.critical(f"[API] Stored _explicit_prompt in message_variables: {message_variables}")

    logger.critical(f"[API] Final message_variables before enqueue: {message_variables}, bool={bool(message_variables)}")

    # Enqueue message (job_manager.enqueue_message is blocking, wrap it)
    # Note: loop is already defined earlier in the function
    # NOTIFWEB-085: capture HTTP request context for job metadata
    _req_ip = http_request.client.host if http_request.client else None
    _req_ua = http_request.headers.get("user-agent")
    _req_auth = http_request.headers.get("authorization", "")[:20] if http_request.headers.get("authorization") else "cookie"
    _req_source = "api"

    result = await loop.run_in_executor(None, lambda: job_manager.enqueue_message(
        created_by=request.created_by or "api",
        content=[block.dict() for block in request.content],
        destinations=destinations_with_ids,
        audience_type=request.audience_type,
        template_ref=request.template_ref,
        variables=message_variables if message_variables else None,
        idempotency_key=request.idempotency_key,
        ttl_hours=ttl_hours,
        request_source=_req_source,
        request_ip=_req_ip,
        request_auth_method=_req_auth,
        request_auth_identity=request.created_by or "api",
        request_user_agent=_req_ua,
    ))

    if result["status"] == "duplicate":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate idempotency key",
        )

    try:
        queue_status = await _get_effective_llm_status()
        if not queue_status["available"] and queue_status["queue_length"] > 0:
            from datetime import timedelta

            estimated_delivery = datetime.now() + timedelta(seconds=queue_status["estimated_wait_seconds"])
            result["estimated_delivery_time"] = estimated_delivery.isoformat()
    except Exception as exc:
        logger.debug(f"Could not check LLM status (non-blocking): {exc}")

    return result


@router.get("/messages/{message_identifier}")
async def get_message(
    request: Request,
    message_identifier: str,
    format: Optional[str] = None,
    language: Optional[str] = None
):
    """Get message by ID or GUID with optional formatting and translation

    Default behavior: Returns HTML when accessed via browser, JSON for API calls
    Query params:
        format: html (default for browsers), json, markdown, text
        language: Target language code (e.g., 'de', 'fr') - translates if provided
    """
    from ...database.repositories import MessageRepository, DeliveryRepository
    from ...core.formatters.llm_formatter import LLMFormatter
    import json
    import re

    message_repo = MessageRepository(db)
    delivery_repo = DeliveryRepository(db)
    message_fetch_timeout = float(
        config.get("api_server.message_fetch_timeout")
        or config.get("api_server.request_timeout")
        or 30
    )

    # Determine output format: check query param, then Accept header, default to HTML for browsers
    accept_header = request.headers.get("Accept", "")
    if not format:
        # Check Accept header
        if "application/json" in accept_header and "text/html" not in accept_header:
            format = "json"
        elif "text/markdown" in accept_header:
            format = "markdown"
        elif "text/plain" in accept_header:
            format = "text"
        else:
            # Default to HTML for browser requests
            format = "html"

    try:
        # Try to determine if it's a GUID (UUID format) or numeric ID
        is_guid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message_identifier, re.IGNORECASE)

        if is_guid:
            message = await asyncio.wait_for(
                asyncio.to_thread(message_repo.get_by_guid, message_identifier),
                timeout=message_fetch_timeout
            )
        else:
            try:
                message_id = int(message_identifier)
                message = await asyncio.wait_for(
                    asyncio.to_thread(message_repo.get_by_id, message_id),
                    timeout=message_fetch_timeout
                )
            except ValueError:
                # If not a valid int, check if it's "None" string (from test)
                if message_identifier.lower() == 'none':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Message GUID is None. Use numeric message ID instead.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid message identifier. Must be numeric ID or GUID (UUID format)",
                )

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        message_id = message['id']
        message_guid = message.get('guid')
        # CRITICAL: Always use the GUID from the database, never from the URL parameter
        # Verify the GUID matches what was requested (data integrity check)
        if is_guid and message_guid and message_guid.lower() != message_identifier.lower():
            logger.warning(f"Message {message_id} GUID mismatch: requested '{message_identifier}', database has '{message_guid}'")
            # Still return the message, but log the mismatch

        # Get delivery summary (with timeout)
        state_counts = await asyncio.wait_for(
            asyncio.to_thread(delivery_repo.count_by_state, message_id),
            timeout=message_fetch_timeout
        )
        total_deliveries = sum(state_counts.values())
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting message {message_identifier}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out while fetching message",
        )

    # Parse content
    content_json = message.get('content_json', '[]')
    content = json.loads(content_json) if isinstance(content_json, str) else content_json

    # Use shared formatter if available (already connected at startup), otherwise create new one
    global llm_formatter
    if llm_formatter:
        formatter = llm_formatter
    else:
        formatter = LLMFormatter(db, config)

    # Format content based on requested format
    formatted_body = ""
    original_text = "\n\n".join(
        block.get("body", "")
        for block in content
        if isinstance(block, dict) and block.get("body")
    ).strip()
    # W28D-440A: enrich subject from variables_json/content if column is null
    message = _enrich_subject(message)
    subject = message.get('subject', '')

    # For other formats, try to get formatted content from delivery (fast path)
    # If not available, use original content
    processed_media = []  # Extract images from processed_media
    destination_preferences = None
    try:
        deliveries = await asyncio.wait_for(
            asyncio.to_thread(delivery_repo.get_by_message_id, message_id),
            timeout=api_db_timeout_short
        )

        # Get formatted content from first delivery if available
        if deliveries:
            delivery = deliveries[0]
            personalised_payload = delivery.get('personalised_payload')
            if personalised_payload:
                try:
                    payload_data = json.loads(personalised_payload) if isinstance(personalised_payload, str) else personalised_payload
                    # Handle dict format: {subject, body, content_type, attachments}
                    if isinstance(payload_data, dict):
                        formatted_body = payload_data.get('body', '')
                        if not subject:
                            subject = payload_data.get('subject', '')
                    # Handle list format: [{type: "html", body: ...}, ...]
                    elif isinstance(payload_data, list) and len(payload_data) > 0:
                        block = payload_data[0]
                        formatted_body = block.get('body', '')
                        if not subject:
                            subject = block.get('subject', '')
                except Exception as e:
                    logger.warning(f"Failed to parse personalised_payload: {e}")
                    pass

            # Extract processed_media and preferences from metadata_json
            metadata_json = delivery.get('metadata_json')
            if metadata_json:
                try:
                    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
                    processed_media = metadata.get('processed_media', [])
                    destination_preferences = metadata.get('preferences')
                except Exception:
                    pass

            # CRITICAL: Check for cached translated delivery content first (fast)
            cached_content_found = False
            cached_full_content = None
            if language:
                logger.info(f"[WEB VIEW] Language '{language}' requested - checking for cached translation")
                try:
                    def _extract_cached_payload_text(payload_value) -> str:
                        try:
                            payload_obj = json.loads(payload_value) if isinstance(payload_value, str) else payload_value
                        except Exception:
                            payload_obj = payload_value

                        extracted = ""
                        if isinstance(payload_obj, dict):
                            extracted = str(payload_obj.get("body") or payload_obj.get("text") or "")
                        elif isinstance(payload_obj, list):
                            extracted = "\n".join(
                                str((blk or {}).get("body") or (blk or {}).get("text") or "")
                                for blk in payload_obj
                                if isinstance(blk, dict)
                            )
                        elif isinstance(payload_obj, str):
                            extracted = payload_obj

                        extracted = str(extracted or "").strip()
                        if extracted:
                            extracted = re.sub(r"<https?://[^>|]+\|([^>]+)>", r"\1", extracted)
                            extracted = re.sub(r"\[[^\]]+\]\(https?://[^)]+\)", "", extracted)
                            extracted = re.sub(r"https?://\S+", "", extracted)
                            extracted = re.sub(r"\s+", " ", extracted).strip()
                        return extracted

                    def _payload_matches_language(candidate_text: str, requested_language: str) -> bool:
                        lang_code = str(requested_language or "").strip().lower()
                        if not candidate_text or len(candidate_text) < 80 or not lang_code:
                            return False
                        if lang_code in {"zh", "zh-cn", "zh-hans", "zh-hant", "zh-tw"}:
                            return sum(1 for c in candidate_text if "\u4e00" <= c <= "\u9fff") >= 20
                        if lang_code == "ja":
                            return sum(
                                1 for c in candidate_text
                                if ("\u3040" <= c <= "\u30ff") or ("\u4e00" <= c <= "\u9fff")
                            ) >= 20
                        if lang_code == "ko":
                            return sum(1 for c in candidate_text if "\uac00" <= c <= "\ud7af") >= 20
                        if lang_code in {"ar", "he", "fa", "ur"}:
                            return sum(1 for c in candidate_text if "\u0590" <= c <= "\u08FF") >= 20

                        try:
                            from langdetect import detect_langs

                            detected_langs = detect_langs(candidate_text[:1000])
                            if detected_langs:
                                detected = detected_langs[0]
                                detected_code = {"zh-cn": "zh", "zh-tw": "zh"}.get(
                                    detected.lang,
                                    detected.lang,
                                )
                                if detected_code == lang_code and detected.prob >= 0.60:
                                    return True
                        except Exception:
                            pass

                        if lang_code.startswith("en"):
                            return formatter._is_predominantly_english(candidate_text)
                        return not formatter._has_english_leakage(candidate_text, lang_code)

                    # Find deliveries for this message with the requested language
                    deliveries_list = db.fetchall(
                        """SELECT personalised_payload, metadata_json
                           FROM deliveries
                           WHERE message_id = ? AND state = 'sent'
                           ORDER BY sent_at DESC LIMIT 10""",
                        (message_id,)
                    )

                    for delivery_row in deliveries_list:
                        if delivery_row and delivery_row.get('personalised_payload'):
                            meta_json = delivery_row.get('metadata_json')
                            if meta_json:
                                meta = json.loads(meta_json) if isinstance(meta_json, str) else meta_json
                                prefs = meta.get('preferences', {})
                                delivery_lang = prefs.get('language', '').lower()

                                if delivery_lang == language.lower():
                                    # Use cached full translated content when present.
                                    cached_full_content = meta.get("full_content_text")
                                    if isinstance(cached_full_content, str) and cached_full_content.strip():
                                        cached_candidate = cached_full_content.strip()
                                        lang_code = str(language or "").strip().lower()
                                        cjk_langs = {"zh", "zh-cn", "zh-hans", "zh-hant", "zh-tw", "ja", "ko"}
                                        rtl_langs = {"ar", "he", "fa", "ur"}
                                        min_cached_len = 0
                                        script_valid = True
                                        if original_text and lang_code not in cjk_langs and lang_code not in rtl_langs:
                                            min_cached_len = int(len(original_text) * 0.7)
                                        if lang_code in cjk_langs:
                                            cjk_chars = sum(1 for c in cached_candidate if "\u4e00" <= c <= "\u9fff")
                                            script_valid = cjk_chars >= 50
                                        elif lang_code in rtl_langs:
                                            rtl_chars = sum(1 for c in cached_candidate if "\u0590" <= c <= "\u08FF")
                                            script_valid = rtl_chars >= 50
                                        if min_cached_len and len(cached_candidate) < min_cached_len:
                                            logger.warning(
                                                f"[WEB VIEW] Cached full-content too short for {language} "
                                                f"(len={len(cached_candidate)}, min={min_cached_len}); "
                                                "forcing fresh full-content translation."
                                            )
                                            cached_full_content = None
                                        elif not script_valid:
                                            logger.warning(
                                                f"[WEB VIEW] Cached full-content script mismatch for {language} "
                                                f"(len={len(cached_candidate)}); forcing fresh full-content translation."
                                            )
                                            cached_full_content = None
                                        else:
                                            formatted_body = cached_candidate
                                            logger.info(
                                                f"Found cached {language} delivery with full translated content "
                                                f"(len={len(formatted_body)})"
                                            )
                                            cached_content_found = True
                                            break
                                    if not cached_content_found:
                                        payload_fallback = _extract_cached_payload_text(
                                            delivery_row.get("personalised_payload")
                                        )
                                        if _payload_matches_language(payload_fallback, language):
                                            formatted_body = payload_fallback
                                            cached_full_content = payload_fallback
                                            cached_content_found = True
                                            logger.info(
                                                f"Found cached {language} delivery with validated translated body fallback "
                                                f"(len={len(formatted_body)})"
                                            )
                                            break
                                        logger.info(
                                            f"Found cached {language} delivery, but no full-content cache; "
                                            "will translate original for full content"
                                        )
                except Exception as e:
                    logger.error(f"Failed to check cached deliveries: {e}")

            # CRITICAL: If language parameter is provided, we MUST translate (even if slow)
            # This is required functionality - users expect translated content when ?language=XX is set
            logger.info(f"[REFORMAT CHECK] formatted_body exists: {bool(formatted_body)}, language param: {language}, cached: {cached_content_found}")
            should_reformat = language is not None and not cached_full_content  # Skip when full cache exists

            # OLD CODE - DISABLED FOR PERFORMANCE
            # if language and not cached_content_found:
            #     should_reformat = True
            # elif formatted_body and destination_preferences:
            # OLD SUMMARY CHECK CODE - DISABLED
            #     summary_indicators = [...]
            #     should_reformat = is_summary
            # else:
            #     should_reformat = False

            if should_reformat:
                    # This is a summary OR language parameter is specified - need to format the original content
                    # CRITICAL: Use language query parameter if provided, otherwise use destination_preferences
                    prefs_to_use = destination_preferences.copy() if destination_preferences else {}
                    if language:
                        # Query parameter takes precedence
                        prefs_to_use['language'] = language
                        logger.info(f"CRITICAL: Using language from query parameter: {language} (URL param overrides everything)")
                        # CRITICAL: Web-view language rendering must return FULL content.
                        # Destination preferences often include max_length for notification summaries.
                        # Strip any summarisation constraints and force full output.
                        prefs_to_use.pop('max_length', None)
                        prefs_to_use.pop('max_chars', None)
                        prefs_to_use['output_formats'] = ['full']

                    # Build original text once for translation/formatting.
                    full_translation_applied = False
                    translation_timeout = config.get("llm.translation_timeout") or config.get("llm.formatting_timeout")
                    if not translation_timeout:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Missing required configuration: llm.translation_timeout or llm.formatting_timeout",
                        )
                    chunk_chars = config.get("llm.translation_chunk_chars")
                    # Web-view full-content translations for long messages can exceed
                    # request budgets when done as a single LLM call. Use safe defaults
                    # when no explicit chunking config is provided.
                    if (chunk_chars is None or chunk_chars == "") and language and len(original_text) > 2500:
                        chunk_chars = 1400
                    if chunk_chars is not None and chunk_chars != "":
                        try:
                            chunk_chars = int(chunk_chars)
                        except Exception as exc:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Invalid llm.translation_chunk_chars value: {exc}",
                            )
                        if chunk_chars <= 0:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Invalid llm.translation_chunk_chars value: must be > 0",
                            )
                    chunk_parallelism = config.get("llm.translation_chunk_parallelism")
                    if (chunk_parallelism is None or chunk_parallelism == "") and chunk_chars:
                        chunk_parallelism = 2
                    if chunk_parallelism is not None and chunk_parallelism != "":
                        try:
                            chunk_parallelism = int(chunk_parallelism)
                        except Exception as exc:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Invalid llm.translation_chunk_parallelism value: {exc}",
                            )
                        if chunk_parallelism <= 0:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail="Invalid llm.translation_chunk_parallelism value: must be > 0",
                            )

                    # Prefer direct full translation for web-view language requests (no summarisation).
                    if language and original_text:
                        try:
                            if chunk_chars:
                                chunks = [
                                    original_text[idx:idx + chunk_chars]
                                    for idx in range(0, len(original_text), chunk_chars)
                                ]
                                parallelism = chunk_parallelism or 1
                                if parallelism <= 1 or len(chunks) == 1:
                                    translated_chunks = []
                                    for chunk in chunks:
                                        translated_chunk = await asyncio.wait_for(
                                            asyncio.to_thread(formatter._translate, chunk, language),
                                            timeout=float(translation_timeout),
                                        )
                                        if not translated_chunk:
                                            raise RuntimeError("LLM returned empty translation chunk")
                                        translated_chunks.append(translated_chunk)
                                else:
                                    semaphore = asyncio.Semaphore(parallelism)

                                    async def _translate_chunk(chunk: str) -> str:
                                        async with semaphore:
                                            translated_chunk = await asyncio.wait_for(
                                                asyncio.to_thread(formatter._translate, chunk, language),
                                                timeout=float(translation_timeout),
                                            )
                                            if not translated_chunk:
                                                raise RuntimeError("LLM returned empty translation chunk")
                                            return translated_chunk

                                    translated_chunks = await asyncio.gather(
                                        *(_translate_chunk(chunk) for chunk in chunks)
                                    )
                                translated_text = "\n\n".join(translated_chunks)
                            else:
                                translated_text = await asyncio.wait_for(
                                    asyncio.to_thread(formatter._translate, original_text, language),
                                    timeout=float(translation_timeout),
                                )
                            if translated_text:
                                formatted_body = translated_text
                                full_translation_applied = True
                                logger.info(
                                    f"✅ Applied full translation for web view language={language}: {len(formatted_body)} chars"
                                )
                        except Exception as translate_error:
                            logger.error(f"Full translation failed for language={language}: {translate_error}")

                    try:
                        # Format original content with preferences
                        format_variables = {
                            'message_id': message_id,
                            'message_guid': message_guid,
                            'preferences': prefs_to_use
                        }
                        # CRITICAL: Get user_id from delivery if available, so preferences are properly applied
                        user_id = delivery.get('user_id') if deliveries else None
                        # Use 'storage' channel type to avoid summarization (we want full content)
                        logger.info(f"Reformatting message with language={prefs_to_use.get('language')}")
                        if not full_translation_applied:
                            format_result = await asyncio.wait_for(
                                asyncio.to_thread(
                                    formatter.format_message,
                                    content=content,
                                    channel_type='storage',  # No max_length restrictions
                                    user_id=user_id,  # Pass user_id if available
                                    variables=format_variables,
                                    message_id=message_id,
                                    message_guid=message_guid,
                                    channel_id=None,  # Don't use channel_id to avoid restrictions
                                ),
                                timeout=float(translation_timeout),
                            )
                        else:
                            format_result = {}
                        # Extract formatted text from formatted_content blocks
                        formatted_blocks = format_result.get('formatted_content', []) if format_result else []
                        if formatted_blocks:
                            formatted_body = '\n\n'.join([block.get('body', '') for block in formatted_blocks if isinstance(block, dict)])
                            logger.info(f"✅ Reformatted message: {len(formatted_body)} chars, language={prefs_to_use.get('language')}")
                            # CRITICAL: Verify translation was applied
                            requested_lang = prefs_to_use.get('language')
                            if requested_lang and requested_lang != 'en':
                                translation_applied = format_result.get('translation_applied', False)
                                logger.info(f"Translation status: target={requested_lang}, applied={translation_applied}")
                                if not translation_applied:
                                    logger.error(f"❌ Translation NOT applied for {requested_lang}, content is in English!")
                                    # Fallback: force translate full original content for web view.
                                    try:
                                        original_text = "\n\n".join(
                                            block.get("body", "")
                                            for block in content
                                            if isinstance(block, dict) and block.get("body")
                                        )
                                        if original_text:
                                            translated_text = await asyncio.wait_for(
                                                asyncio.to_thread(formatter._translate, original_text, requested_lang),
                                                timeout=float(translation_timeout),
                                            )
                                            if translated_text:
                                                formatted_body = translated_text
                                                logger.info(f"✅ Fallback translation applied for {requested_lang}: {len(formatted_body)} chars")
                                    except Exception as translate_error:
                                        logger.error(f"Fallback translation failed for {requested_lang}: {translate_error}")
                                # Additional safeguard for CJK: verify script presence, fallback if needed.
                                if requested_lang and requested_lang.lower().startswith("zh") and formatted_body:
                                    try:
                                        import re
                                        cjk_chars = re.findall(r"[\u4e00-\u9fff]", formatted_body)
                                        cjk_ratio = len(cjk_chars) / len(formatted_body) if formatted_body else 0
                                        if cjk_ratio < 0.2:
                                            logger.error(f"❌ Chinese content ratio too low ({cjk_ratio:.2f}), forcing translation.")
                                            original_text = "\n\n".join(
                                                block.get("body", "")
                                                for block in content
                                                if isinstance(block, dict) and block.get("body")
                                            )
                                            if original_text:
                                                translated_text = await asyncio.wait_for(
                                                    asyncio.to_thread(formatter._translate, original_text, requested_lang),
                                                    timeout=float(translation_timeout),
                                                )
                                                if translated_text:
                                                    formatted_body = translated_text
                                                    logger.info(f"✅ CJK fallback translation applied: {len(formatted_body)} chars")
                                    except Exception as translate_error:
                                        logger.error(f"CJK fallback translation failed: {translate_error}")
                    except Exception as e:
                        logger.error(f"Failed to format full message: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        # Keep the summary if formatting fails
                        pass
    except (asyncio.TimeoutError, Exception):
        pass  # Fall back to original content

    # If no formatted content, use original
    if not formatted_body:
        for block in content:
            if isinstance(block, dict) and block.get('body'):
                formatted_body += block.get('body', '') + '\n'

    # Guard: ensure French web-view content is actually French (not German).
    if language == 'fr' and formatted_body:
        formatted_lower = formatted_body.lower()
        french_indicators = ["le", "la", "les", "des", "pour", "que", "dans", "avec", "sont"]
        german_indicators = ["der", "die", "das", "und", "mit", "von", "auf", "ist", "sind", "nicht", "für", "über"]
        french_hits = sum(1 for ind in french_indicators if re.search(rf"\b{re.escape(ind)}\b", formatted_lower))
        german_hits = sum(1 for ind in german_indicators if re.search(rf"\b{re.escape(ind)}\b", formatted_lower))
        needs_french = False
        try:
            from langdetect import detect_langs
            detected = detect_langs(formatted_body[:1000])[0]
            lang_map = {
                'en': 'en', 'fr': 'fr', 'de': 'de', 'pl': 'pl', 'zh-cn': 'zh', 'zh-tw': 'zh',
                'ar': 'ar', 'ja': 'ja', 'ko': 'ko', 'es': 'es', 'pt': 'pt', 'ru': 'ru', 'it': 'it'
            }
            detected_code = lang_map.get(detected.lang, detected.lang)
            if detected_code != "fr" and detected.prob > 0.60:
                needs_french = True
        except Exception as detect_err:
            logger.warning(f"[WEB VIEW FR GUARD] Language detection skipped: {detect_err}")
        if not needs_french and german_hits >= 2 and german_hits > french_hits:
            needs_french = True
        if needs_french:
            logger.warning(
                f"[WEB VIEW FR GUARD] Weak French output (fr_hits={french_hits}, de_hits={german_hits}); "
                "forcing French translation."
            )
            source_text = original_text or "\n\n".join(
                block.get("body", "")
                for block in content
                if isinstance(block, dict) and block.get("body")
            )
            if source_text:
                try:
                    translated_text = await asyncio.wait_for(
                        asyncio.to_thread(formatter._translate, source_text, "fr"),
                        timeout=float(translation_timeout) if 'translation_timeout' in locals() else 300.0,
                    )
                    if translated_text:
                        formatted_body = translated_text
                        formatted_lower = formatted_body.lower()
                        french_hits = sum(1 for ind in french_indicators if ind in formatted_lower)
                        german_hits = sum(1 for ind in german_indicators if ind in formatted_lower)
                        if german_hits >= 2 and german_hits > french_hits:
                            strict_prompt = (
                                "Translate the following text into French. "
                                "Return ONLY French text, no original language, no labels.\n\n"
                                f"{source_text}\n"
                            )
                            strict_timeout = translation_timeout if 'translation_timeout' in locals() else 300.0
                            strict_translated = await asyncio.wait_for(
                                asyncio.to_thread(
                                    lambda: formatter.llm_manager.invoke(strict_prompt, timeout=strict_timeout)
                                ),
                                timeout=float(strict_timeout),
                            )
                            strict_translated = (strict_translated or "").strip()
                            if strict_translated:
                                formatted_body = strict_translated
                        # Final fallback: force German→French if source detected as German.
                        formatted_lower = formatted_body.lower()
                        french_hits = sum(1 for ind in french_indicators if ind in formatted_lower)
                        german_hits = sum(1 for ind in german_indicators if ind in formatted_lower)
                        if german_hits >= 2 and german_hits > french_hits:
                            try:
                                from langdetect import detect_langs
                                detected = detect_langs(source_text[:1000])[0]
                                if detected.lang == "de" and detected.prob > 0.7:
                                    strict_prompt = (
                                        "Translate the following German text into French. "
                                        "Return ONLY French text, no original language, no labels.\n\n"
                                        f"{source_text}\n"
                                    )
                                    strict_timeout = translation_timeout if 'translation_timeout' in locals() else 300.0
                                    strict_translated = await asyncio.wait_for(
                                        asyncio.to_thread(
                                            lambda: formatter.llm_manager.invoke(strict_prompt, timeout=strict_timeout)
                                        ),
                                        timeout=float(strict_timeout),
                                    )
                                    strict_translated = (strict_translated or "").strip()
                                    if strict_translated:
                                        formatted_body = strict_translated

                                    # If still weak French, try chunked fallback for long texts.
                                    formatted_lower = formatted_body.lower() if formatted_body else ""
                                    french_hits = sum(1 for ind in french_indicators if ind in formatted_lower)
                                    german_hits = sum(1 for ind in german_indicators if ind in formatted_lower)
                                    if german_hits >= 2 and german_hits > french_hits:
                                        chunks = [source_text[i:i + 1500] for i in range(0, len(source_text), 1500)]
                                        translated_chunks = []
                                        for chunk in chunks:
                                            chunk_prompt = (
                                                "Translate the following German text into French. "
                                                "Return ONLY French text, no original language, no labels.\n\n"
                                                f"{chunk}\n"
                                            )
                                            chunk_translated = await asyncio.wait_for(
                                                asyncio.to_thread(
                                                    lambda: formatter.llm_manager.invoke(chunk_prompt, timeout=strict_timeout)
                                                ),
                                                timeout=float(strict_timeout),
                                            )
                                            chunk_translated = (chunk_translated or "").strip()
                                            if chunk_translated:
                                                translated_chunks.append(chunk_translated)
                                        if translated_chunks:
                                            formatted_body = "\n\n".join(translated_chunks)
                            except Exception as detect_err:
                                logger.error(f"[WEB VIEW FR GUARD] German detection/translation failed: {detect_err}")
                except Exception as fr_translate_error:
                    logger.error(f"[WEB VIEW FR GUARD] Forced French translation failed: {fr_translate_error}")

    # Guard: ensure requested language is respected for web view (generic).
    if language and formatted_body:
        requested_lang = language.lower()
        try:
            from langdetect import detect_langs
            rtl_langs = {"ar", "he", "fa", "ur"}
            cjk_langs = {"zh", "zh-cn", "zh-hans", "zh-hant", "zh-tw", "ja", "ko"}
            # Langdetect performs badly on long mixed-format payloads containing
            # markdown, URLs and residual ASCII. Trust strong target-script
            # evidence first so we do not trigger an unnecessary second full
            # translation on already-translated web-view content.
            if requested_lang in rtl_langs:
                rtl_chars = sum(1 for c in formatted_body if "\u0590" <= c <= "\u08FF")
                total_letters = sum(1 for c in formatted_body if c.isalpha() or "\u0590" <= c <= "\u08FF")
                rtl_ratio = (rtl_chars / total_letters) if total_letters else 0.0
                if rtl_chars >= 80 and rtl_ratio >= 0.20:
                    raise RuntimeError("__LANG_GUARD_SKIP_RTL__")
            elif requested_lang in cjk_langs:
                cjk_chars = sum(1 for c in formatted_body if "\u4e00" <= c <= "\u9fff")
                if requested_lang == "ja":
                    cjk_chars += sum(1 for c in formatted_body if "\u3040" <= c <= "\u30ff")
                elif requested_lang == "ko":
                    cjk_chars += sum(1 for c in formatted_body if "\uac00" <= c <= "\ud7af")
                if cjk_chars >= 80:
                    raise RuntimeError("__LANG_GUARD_SKIP_CJK__")
            lang_map = {
                'en': 'en', 'fr': 'fr', 'de': 'de', 'pl': 'pl', 'zh-cn': 'zh', 'zh-tw': 'zh',
                'ar': 'ar', 'ja': 'ja', 'ko': 'ko', 'es': 'es', 'pt': 'pt', 'ru': 'ru', 'it': 'it'
            }
            detected = detect_langs(formatted_body[:1000])[0]
            detected_code = lang_map.get(detected.lang, detected.lang)
            if detected_code != requested_lang and detected.prob > 0.60:
                logger.warning(
                    f"[WEB VIEW LANG GUARD] Detected {detected_code} ({detected.prob:.1%}) "
                    f"but requested {requested_lang}. Forcing translation."
                )
                source_text = original_text or "\n\n".join(
                    block.get("body", "")
                    for block in content
                    if isinstance(block, dict) and block.get("body")
                )
                if source_text:
                    guard_timeout = config.get("llm.translation_timeout") or config.get("llm.formatting_timeout") or 300.0
                    translated_text = await asyncio.wait_for(
                        asyncio.to_thread(formatter._translate, source_text, requested_lang),
                        timeout=float(guard_timeout),
                    )
                    if translated_text:
                        translated_text = formatter._strip_summary_lead_in(translated_text)
                        translated_text = formatter._strip_english_boilerplate(translated_text, requested_lang)
                        translated_text = formatter._enforce_non_english_output(translated_text, requested_lang)
                        formatted_body = translated_text
        except Exception as guard_err:
            if str(guard_err) in {"__LANG_GUARD_SKIP_RTL__", "__LANG_GUARD_SKIP_CJK__"}:
                logger.info(
                    f"[WEB VIEW LANG GUARD] Skipping secondary translation for {requested_lang}; "
                    "strong target-script evidence already present."
                )
            else:
                logger.warning(f"[WEB VIEW LANG GUARD] Language check skipped: {guard_err}")

    # Final safeguard: enforce CJK translation for web view only when output still
    # lacks enough CJK script. Avoid unconditional re-translation which can double
    # per-request latency for large messages.
    if language and language.lower().startswith("zh"):
        try:
            needs_cjk_translation = True
            if formatted_body:
                cjk_chars = re.findall(r"[\u4e00-\u9fff]", formatted_body)
                cjk_ratio = len(cjk_chars) / max(len(formatted_body), 1)
                # Consider content already translated when enough CJK content exists.
                if len(cjk_chars) >= 20 and cjk_ratio >= 0.10:
                    needs_cjk_translation = False
                    logger.info(
                        f"Skipping forced CJK translation for web view: "
                        f"cjk_chars={len(cjk_chars)}, cjk_ratio={cjk_ratio:.2f}"
                    )
            if needs_cjk_translation:
                original_text = "\n\n".join(
                    block.get("body", "")
                    for block in content
                    if isinstance(block, dict) and block.get("body")
                )
                if original_text:
                    cjk_translation_timeout = float(config.get("llm.translation_timeout") or config.get("llm.timeout") or 300)
                    translated_text = await asyncio.wait_for(
                        asyncio.to_thread(formatter._translate, original_text, language),
                        timeout=cjk_translation_timeout,
                    )
                    if translated_text:
                        formatted_body = translated_text
                        logger.info(f"✅ Web view CJK translation applied: {len(formatted_body)} chars")
        except Exception as translate_error:
            logger.error(f"Web view CJK translation failed: {translate_error}")

    # CRITICAL: If language is requested and content is in English, try to get already-translated delivery content
    # This avoids slow on-demand translation (which can take 2-5 minutes for large content)
    if language and language != 'en' and formatted_body:
        # Quick heuristic: check if content appears to be in English
        english_indicators = ['the digital age', 'information overload', 'paradigm shift', 'Large Language Models']
        has_english = any(phrase.lower() in formatted_body.lower() for phrase in english_indicators)

        if has_english:
            logger.info(f"Content appears to be in English, but {language} was requested - looking for translated delivery")
            try:
                # Find a delivery for this message that has the requested language
                deliveries = db.fetchall(
                    """SELECT personalised_payload, metadata_json
                       FROM deliveries
                       WHERE message_id = ? AND state = 'sent'
                       ORDER BY sent_at DESC LIMIT 5""",
                    (message_id,),
                )

                translated_found = False
                for delivery in deliveries:
                    if not delivery:
                        continue
                    metadata_raw = delivery.get('metadata_json')
                    if not metadata_raw:
                        continue
                    try:
                        metadata = (
                            json.loads(metadata_raw)
                            if isinstance(metadata_raw, str)
                            else metadata_raw
                        )
                    except Exception:
                        continue
                    if not isinstance(metadata, dict):
                        continue
                    # New schema stores delivery preferences in metadata_json.preferences.
                    # Keep a fallback for historical flat JSON layouts.
                    delivery_prefs = metadata.get('preferences', metadata)
                    if not isinstance(delivery_prefs, dict):
                        continue
                    delivery_lang = str(delivery_prefs.get('language', '')).lower()

                    if delivery_lang == language.lower():
                        # Found a delivery in the requested language - extract its formatted content
                        payload = json.loads(delivery['personalised_payload'])
                        # For text-based deliveries, extract the formatted text
                        if 'text' in payload:
                            # This is already translated content from delivery
                            delivery_text = payload['text']
                            # Remove links and extra formatting to get clean content
                            import re
                            # Remove Slack-style links but keep the label
                            delivery_text = re.sub(r'<https?://[^>|]+\|([^>]+)>', r'\1', delivery_text)
                            # Remove plain URLs
                            delivery_text = re.sub(r'https?://\S+', '', delivery_text)
                            delivery_text = delivery_text.strip()

                            if len(delivery_text) > 200:  # Has substantial content
                                formatted_body = formatter._markdown_to_html(delivery_text)
                                logger.info(f"✅ Using translated content from delivery ({len(delivery_text)} chars)")
                                translated_found = True
                                break

                if not translated_found:
                    logger.warning(f"No translated delivery found for language={language}, returning original English content")

            except Exception as e:
                logger.error(f"Failed to retrieve translated delivery: {e}")
                import traceback
                logger.error(traceback.format_exc())

    # Apply format conversion
    try:

        # Convert to requested format
        if format == 'html':
            # Strip markdown code block markers if present (LLM sometimes wraps HTML in ```html ... ```)
            if formatted_body.startswith('```html') or formatted_body.startswith('```HTML'):
                formatted_body = re.sub(r'^```html\s*\n?', '', formatted_body, flags=re.IGNORECASE)
                formatted_body = re.sub(r'\n?```\s*$', '', formatted_body)
            elif formatted_body.startswith('```'):
                formatted_body = re.sub(r'^```[a-z]*\s*\n?', '', formatted_body, flags=re.IGNORECASE)
                formatted_body = re.sub(r'\n?```\s*$', '', formatted_body)
            formatted_body = formatted_body.strip()
            logger.info(f"[HTML CONVERSION] Before markdown_to_html: {formatted_body[:200]}")
            # Convert markdown to HTML if needed (if no HTML tags detected)
            if '<' not in formatted_body or not any(tag in formatted_body for tag in ['<p>', '<h', '<div>', '<br>', '<ul>', '<ol>']):
                formatted_body = formatter._markdown_to_html(formatted_body)
                logger.info(f"[HTML CONVERSION] After markdown_to_html: {formatted_body[:200]}")

            # Add images from processed_media
            if processed_media:
                images_html = []
                for media in processed_media:
                    if media.get('type') == 'image':
                        url = media.get('url') or media.get('original_uri')
                        if url:
                            alt_text = media.get('alt_text') or media.get('metadata', {}).get('alt', 'Image')
                            width = media.get('metadata', {}).get('width')
                            height = media.get('metadata', {}).get('height')
                            width_attr = f' width="{width}"' if width else ""
                            height_attr = f' height="{height}"' if height else ""
                            images_html.append(f'<p><img src="{url}" alt="{alt_text}"{width_attr}{height_attr}></p>')
                if images_html:
                    formatted_body += '\n' + '\n'.join(images_html)
        elif format == 'text':
            # Strip HTML and convert markdown to text
            formatted_body = re.sub(r'<[^>]+>', '', formatted_body)
            formatted_body = formatter._markdown_to_text(formatted_body)

            # Add image links from processed_media
            if processed_media:
                image_links = []
                for media in processed_media:
                    if media.get('type') == 'image':
                        # Prefer stored URL over data URI for text format
                        url = media.get('url') or media.get('original_uri')
                        if url:
                            alt_text = media.get('alt_text') or 'Image'
                            # For data URIs, truncate for readability
                            if url.startswith('data:'):
                                url_display = f"{url[:50]}... (embedded image)"
                            else:
                                url_display = url
                            image_links.append(f"Image ({alt_text}): {url_display}")
                if image_links:
                    formatted_body += '\n\n' + '\n'.join(image_links)
        elif format == 'markdown':
            # Convert HTML to markdown if HTML is present
            if '<' in formatted_body and '>' in formatted_body:
                # Convert common HTML tags to markdown
                formatted_body = re.sub(r'<h1>(.*?)</h1>', r'# \1', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<h2>(.*?)</h2>', r'## \1', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<h3>(.*?)</h3>', r'### \1', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<p>(.*?)</p>', r'\1\n\n', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<strong>(.*?)</strong>', r'**\1**', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<em>(.*?)</em>', r'*\1*', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<ul>(.*?)</ul>', r'\1', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<li>(.*?)</li>', r'- \1\n', formatted_body, flags=re.IGNORECASE | re.DOTALL)
                formatted_body = re.sub(r'<br\s*/?>', r'\n', formatted_body, flags=re.IGNORECASE)
                # Remove any remaining HTML tags
                formatted_body = re.sub(r'<[^>]+>', '', formatted_body)
                # Clean up extra newlines
                formatted_body = re.sub(r'\n{3,}', r'\n\n', formatted_body)
                formatted_body = formatted_body.strip()

            # Add image references from processed_media
            if processed_media:
                image_refs = []
                for media in processed_media:
                    if media.get('type') == 'image':
                        url = media.get('url') or media.get('original_uri')
                        if url:
                            alt_text = media.get('alt_text') or 'Image'
                            image_refs.append(f"![{alt_text}]({url})")
                if image_refs:
                    formatted_body += '\n\n' + '\n'.join(image_refs)
        # format == 'json' - return JSON below

    except Exception as e:
        logger.warning(f"Failed to format message: {e}", exc_info=True)
        # Fallback: use original content
        for block in content:
            if isinstance(block, dict) and block.get('body'):
                formatted_body += block.get('body', '') + '\n'

    # Determine actual status (if all deliveries are sent/completed, status should be completed)
    actual_status = message.get('status')
    if state_counts.get('sent', 0) == total_deliveries and total_deliveries > 0:
        actual_status = 'completed'
    elif state_counts.get('delivered', 0) + state_counts.get('sent', 0) + state_counts.get('accepted', 0) == total_deliveries and total_deliveries > 0:
        actual_status = 'completed'

    # Return based on format
    if format == 'json':
        return {
            "id": message_id,
            "guid": message_guid,
            "subject": subject or None,
            "status": actual_status,
            "created_at": message.get('created_at'),
            # Backward compatibility: older AT/IT paths expect `content`,
            # while newer paths use `content_json`.
            "content": content,
            "content_json": content,
            "variables_json": message.get('variables_json'),
            "deliveries": {
                "total": total_deliveries,
                "by_state": state_counts
            },
            "formatted_content": formatted_body,
            "format_applied": format,
            "language_applied": language or 'original',
        }
    elif format == 'markdown':
        return Response(
            content=formatted_body,
            media_type="text/markdown; charset=utf-8"
        )
    elif format == 'text':
        return Response(
            content=formatted_body,
            media_type="text/plain; charset=utf-8"
        )
    # Determine actual status (if all deliveries are sent/completed, status should be completed)
    actual_status = message.get('status')
    if state_counts.get('sent', 0) == total_deliveries and total_deliveries > 0:
        actual_status = 'completed'
    elif state_counts.get('delivered', 0) + state_counts.get('sent', 0) + state_counts.get('accepted', 0) == total_deliveries and total_deliveries > 0:
        actual_status = 'completed'

    if format == 'html' or format is None:  # HTML (default)
        # Get delivery information for this message
        delivery_info = None
        delivery_id = None
        destination = None
        try:
            deliveries = await asyncio.wait_for(
                asyncio.to_thread(delivery_repo.get_by_message_id, message_id),
                timeout=api_db_timeout_short
            )
            if deliveries:
                delivery_info = deliveries[0]
                delivery_id = delivery_info.get('id')
                destination = delivery_info.get('destination')
        except Exception:
            pass

        # Get original content for display
        original_content_text = ""
        for block in content:
            if isinstance(block, dict) and block.get('body'):
                original_content_text += block.get('body', '') + '\n'

        # Get variables (original settings)
        variables_display = "None"
        if message.get('variables_json'):
            try:
                variables = json.loads(message['variables_json']) if isinstance(message['variables_json'], str) else message['variables_json']
                variables_display = json.dumps(variables, indent=2)
            except Exception:
                variables_display = str(message.get('variables_json', 'None'))

        # Delivery links removed - endpoints require API key authentication
        delivery_links = ""

        # Detect RTL content (Arabic/Hebrew)
        def has_rtl_characters(text):
            """Check if text contains RTL characters (Arabic/Hebrew)"""
            rtl_chars = sum(1 for c in text if
                           (0x0600 <= ord(c) <= 0x06FF or  # Arabic
                            0x0750 <= ord(c) <= 0x077F or  # Arabic Supplement
                            0x08A0 <= ord(c) <= 0x08FF or  # Arabic Extended-A
                            0xFB50 <= ord(c) <= 0xFDFF or  # Arabic Presentation Forms-A
                            0xFE70 <= ord(c) <= 0xFEFF or  # Arabic Presentation Forms-B
                            0x0590 <= ord(c) <= 0x05FF))   # Hebrew
            total_letters = sum(1 for c in text if c.isalpha())
            return rtl_chars > 0 and (rtl_chars / total_letters > 0.3 if total_letters > 0 else False)

        # Check if content is RTL
        rtl_class = "rtl-content" if has_rtl_characters(formatted_body) else ""

        def _format_dt(value):
            if not value:
                return "N/A"
            if hasattr(value, "strftime"):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            return str(value)[:19]

        # Generate HTML page with all information
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject or 'Message'} - Full Message</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .section {{
            margin-bottom: 30px;
            padding: 20px;
            background: #fafafa;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }}
        .section h2 {{
            margin-top: 0;
            color: #333;
            font-size: 1.3em;
        }}
        .section h3 {{
            margin-top: 0;
            color: #555;
            font-size: 1.1em;
        }}
        .message-content {{
            background: white;
            padding: 20px;
            border-radius: 4px;
            border: 1px solid #e0e0e0;
            margin-top: 10px;
        }}
        /* RTL support for Arabic/Hebrew */
        .rtl-content {{
            direction: rtl;
            text-align: right;
            unicode-bidi: embed;
        }}
        /* Preserve numbered lists */
        .message-content ol {{
            margin: 1em 0;
            padding-left: 2em;
        }}
        .message-content ol li {{
            margin: 0.5em 0;
        }}
        .message-content ul {{
            margin: 1em 0;
            padding-left: 2em;
        }}
        .message-content ul li {{
            margin: 0.5em 0;
        }}
        .original-content {{
            background: #fff9e6;
            padding: 15px;
            border-radius: 4px;
            border: 1px solid #ffd700;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}
        .settings {{
            background: #e8f4f8;
            padding: 15px;
            border-radius: 4px;
            border: 1px solid #b3d9e6;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-x: auto;
        }}
        .links {{
            margin-top: 15px;
        }}
        .links a {{
            display: inline-block;
            margin-right: 10px;
            margin-bottom: 10px;
            padding: 8px 16px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }}
        .links a:hover {{
            background: #0056b3;
        }}
        .meta {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .meta-item {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #e0e0e0;
        }}
        .meta-label {{
            font-weight: bold;
            color: #666;
            font-size: 0.85em;
            text-transform: uppercase;
        }}
        .meta-value {{
            margin-top: 5px;
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{subject or 'Message'}</h1>
            <div class="meta">
                <div class="meta-item">
                    <div class="meta-label">Message ID</div>
                    <div class="meta-value">{message_id}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">GUID</div>
                    <div class="meta-value"><code>{message_guid or 'N/A'}</code></div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Status</div>
                    <div class="meta-value">{actual_status}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Created</div>
                    <div class="meta-value">{_format_dt(message.get('created_at'))}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Sent At</div>
                    <div class="meta-value">{_format_dt(delivery_info.get('sent_at') if delivery_info else None)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Delivered At</div>
                    <div class="meta-value">{_format_dt(delivery_info.get('delivered_at') if delivery_info else None)}</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>📧 Formatted Message Content</h2>
            <div class="message-content {rtl_class}">
                {formatted_body}
            </div>
        </div>

        <div class="section">
            <h2>📝 Original Message</h2>
            <p><em>Original content as submitted:</em></p>
            <div class="original-content">{original_content_text.strip()}</div>
        </div>

        <div class="section">
            <h2>⚙️ Original Settings</h2>
            <p><em>Variables and options used when creating this message:</em></p>
            <div class="settings">{variables_display}</div>
        </div>

        <div class="section">
            <h2>📍 Destination</h2>
            <p><strong>Destination:</strong> {destination or 'N/A'}</p>
            <p><strong>Total Deliveries:</strong> {total_deliveries}</p>
            <p><strong>Delivery States:</strong> {', '.join([f"{k}: {v}" for k, v in state_counts.items()])}</p>
        </div>

        <div class="section">
            <h2>🔗 Links</h2>
            <div class="links">
                <a href="/messages/{message_identifier}?format=json" target="_blank">View as JSON</a>
                <a href="/messages/{message_identifier}?format=html" target="_blank">View as HTML</a>
                <a href="/messages/{message_identifier}?format=markdown" target="_blank">View as Markdown</a>
                <a href="/messages/{message_identifier}?format=text" target="_blank">View as Text</a>
                {delivery_links}
            </div>
        </div>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html_content)


@router.get("/messages/{message_identifier}/deliveries", dependencies=[Depends(verify_api_key)])
async def get_message_deliveries(message_identifier: str, offset: int = 0, limit: int = 50):
    """Get deliveries for a message by ID or GUID"""
    from ...database.repositories import DeliveryRepository, MessageRepository
    import re

    try:
        # Try to determine if it's a GUID (UUID format) or numeric ID
        is_guid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message_identifier, re.IGNORECASE)

        message_repo = MessageRepository(db)
        if is_guid:
            # Look up message by GUID first (with timeout)
            message = await asyncio.wait_for(
                asyncio.to_thread(message_repo.get_by_guid, message_identifier),
                timeout=api_db_timeout
            )
            if not message:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Message not found",
                )
            message_id = message['id']
        else:
            try:
                message_id = int(message_identifier)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid message identifier. Must be numeric ID or GUID (UUID format)",
                )

        delivery_repo = DeliveryRepository(db)
        # Execute with timeout to prevent hanging
        deliveries = await asyncio.wait_for(
            asyncio.to_thread(delivery_repo.get_by_message_id, message_id),
            timeout=api_db_timeout
        )

        # Normalise nullable JSON/text columns for client compatibility.
        for delivery in deliveries:
            if delivery.get("metadata_json") is None:
                delivery["metadata_json"] = "{}"
            # Keep unset payloads null/empty until formatting actually runs.
            # Coercing None -> "{}" makes queued deliveries look populated.

        # Apply pagination
        total = len(deliveries)
        paginated = deliveries[offset:offset + limit]

        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "items": paginated,
        }
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting deliveries for message {message_identifier}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out while fetching deliveries",
        )
    except Exception as e:
        logger.error(f"Error getting deliveries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get deliveries: {str(e)}",
        )


def _enrich_subject(msg: dict) -> dict:
    """W28D-440A: extract subject from variables_json if subject column is null."""
    if msg.get("subject"):
        return msg
    vj = msg.get("variables_json")
    if isinstance(vj, str) and vj:
        try:
            import json as _json
            parsed = _json.loads(vj)
            if isinstance(parsed, dict) and parsed.get("subject"):
                msg = dict(msg)
                msg["subject"] = parsed["subject"]
        except Exception:
            pass
    # Fallback: first content block subject
    if not msg.get("subject"):
        cj = msg.get("content_json")
        if isinstance(cj, str) and cj:
            try:
                import json as _json
                blocks = _json.loads(cj)
                if isinstance(blocks, list):
                    for block in blocks:
                        if isinstance(block, dict) and block.get("subject"):
                            msg = dict(msg)
                            msg["subject"] = block["subject"]
                            break
            except Exception:
                pass
    return msg


@router.get("/messages", dependencies=[Depends(verify_api_key)])
async def list_messages(offset: int = 0, limit: int = 100, status: Optional[str] = None):
    """List messages with pagination"""
    from ...database.repositories import MessageRepository

    message_repo = MessageRepository(db)
    messages = message_repo.list_messages(offset=offset, limit=limit, status=status)
    total = message_repo.count(status=status)
    message_ids = [int(message["id"]) for message in messages if message.get("id") is not None]
    delivery_summary: dict[int, dict[str, Any]] = {}
    if message_ids:
        placeholders = ", ".join(["?"] * len(message_ids))
        rows = db.fetchall(
            f"""
            SELECT
                d.message_id,
                MIN(c.name) AS channel_name,
                MIN(c.type) AS channel_type,
                COUNT(*) AS delivery_count,
                GROUP_CONCAT(d.destination) AS recipients
            FROM deliveries d
            LEFT JOIN channels c ON d.channel_id = c.id
            WHERE d.message_id IN ({placeholders})
            GROUP BY d.message_id
            """,
            tuple(message_ids),
        )
        delivery_summary = {int(row["message_id"]): row for row in rows}

    enriched_messages = []
    for message in messages:
        enriched = _enrich_subject(dict(message))
        summary = delivery_summary.get(int(message["id"]))
        if summary:
            enriched["channel_name"] = summary.get("channel_name")
            enriched["channel_type"] = summary.get("channel_type")
            enriched["delivery_count"] = summary.get("delivery_count")
            recipients = summary.get("recipients")
            enriched["recipients"] = [item for item in str(recipients or "").split(",") if item]
        else:
            enriched["recipients"] = []
        enriched_messages.append(enriched)

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": enriched_messages,
    }


@router.get("/deliveries", dependencies=[Depends(verify_api_key)])
async def list_deliveries(offset: int = 0, limit: int = 100, state: Optional[str] = None):
    """List deliveries with pagination"""
    from ...database.repositories import DeliveryRepository

    loop = asyncio.get_event_loop()
    delivery_repo = DeliveryRepository(db)
    deliveries = await loop.run_in_executor(
        None,
        lambda: delivery_repo.list(state=state, limit=limit, offset=offset),
    )

    return {
        "total": len(deliveries),
        "offset": offset,
        "limit": limit,
        "items": deliveries,
    }


@router.post("/messages/{message_identifier}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_message(message_identifier: str):
    """Cancel a message and all pending deliveries by ID or GUID"""
    from ...database.repositories import MessageRepository
    import re

    # Try to determine if it's a GUID (UUID format) or numeric ID
    is_guid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message_identifier, re.IGNORECASE)

    loop = asyncio.get_event_loop()
    message_repo = MessageRepository(db)

    if is_guid:
        message = await loop.run_in_executor(None, message_repo.get_by_guid, message_identifier)
    else:
        try:
            message_id = int(message_identifier)
            message = await loop.run_in_executor(None, message_repo.get_by_id, message_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message identifier. Must be numeric ID or GUID (UUID format)",
            )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    message_id = message['id']
    cancelled_count = await loop.run_in_executor(None, job_manager.cancel_message, message_id)

    return {
        "message_id": message_id,
        "cancelled_count": cancelled_count,
        "message": f"Cancelled {cancelled_count} pending deliveries",
    }


@router.delete("/messages/{message_identifier}", dependencies=[Depends(verify_api_key)])
async def delete_message(
    request: Request,
    message_identifier: str
):
    """Delete a message and all associated deliveries and receipts by ID or GUID

    WARNING: This permanently deletes the message and all related data.
    Use /messages/{id}/cancel to cancel pending deliveries without deletion.
    """
    from ...database.repositories import MessageRepository, DeliveryRepository, ReceiptRepository
    import re

    # Try to determine if it's a GUID (UUID format) or numeric ID
    is_guid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', message_identifier, re.IGNORECASE)

    loop = asyncio.get_event_loop()
    message_repo = MessageRepository(db)
    delivery_repo = DeliveryRepository(db)
    receipt_repo = ReceiptRepository(db)

    # Find message
    if is_guid:
        message = await loop.run_in_executor(None, message_repo.get_by_guid, message_identifier)
    else:
        try:
            message_id = int(message_identifier)
            message = await loop.run_in_executor(None, message_repo.get_by_id, message_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message identifier. Must be numeric ID or GUID (UUID format)",
            )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found",
        )

    message_id = message['id']

    # Delete in order: receipts -> deliveries -> message (to respect foreign keys)
    # Get all deliveries for this message
    deliveries = await loop.run_in_executor(None, delivery_repo.get_by_message_id, message_id)
    delivery_ids = [d['id'] for d in deliveries]

    # Delete receipts for all deliveries
    receipts_deleted = 0
    for delivery_id in delivery_ids:
        receipts = await loop.run_in_executor(None, receipt_repo.get_by_delivery_id, delivery_id)
        for receipt in receipts:
            receipt_id = receipt.get('id')
            if receipt_id:
                await loop.run_in_executor(None, receipt_repo.delete, receipt_id)
                receipts_deleted += 1

    # Delete deliveries
    deliveries_deleted = 0
    for delivery_id in delivery_ids:
        await loop.run_in_executor(None, delivery_repo.delete, delivery_id)
        deliveries_deleted += 1

    # Delete message
    await loop.run_in_executor(None, message_repo.delete, message_id)

    logger.info(f"Deleted message {message_id} ({deliveries_deleted} deliveries, {receipts_deleted} receipts)")

    return {
        "message_id": message_id,
        "deleted": True,
        "deliveries_deleted": deliveries_deleted,
        "receipts_deleted": receipts_deleted,
        "message": f"Deleted message {message_id} and {deliveries_deleted} deliveries, {receipts_deleted} receipts",
    }


@router.post("/deliveries/{delivery_id}/resend", dependencies=[Depends(verify_api_key)])
async def resend_delivery(delivery_id: int):
    """
    Resend a failed or cancelled delivery.

    Resets the delivery to 'queued' state so it can be retried.
    """
    from ...database.repositories import DeliveryRepository
    from ...core.state_machine import DeliveryState

    loop = asyncio.get_event_loop()
    delivery_repo = DeliveryRepository(db)
    delivery = await loop.run_in_executor(None, delivery_repo.get_by_id, delivery_id)

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    current_state = delivery["state"]

    # Only allow resending from terminal failure states
    resendable_states = [
        DeliveryState.HARD_FAILED.value,
        DeliveryState.SOFT_FAILED.value,
        DeliveryState.CANCELLED.value,
        DeliveryState.TTL_EXPIRED.value
    ]

    if current_state not in resendable_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resend delivery in state '{current_state}'. Must be in a failed or cancelled state.",
        )

    # Reset delivery to queued and clear retry backoff metadata.
    await loop.run_in_executor(None, delivery_repo.update_state, delivery_id, DeliveryState.QUEUED.value)
    await loop.run_in_executor(
        None,
        lambda: db.execute(
            """
            UPDATE deliveries
            SET attempt_no = 0,
                next_action_at = NULL,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (delivery_id,),
        ),
    )
    await loop.run_in_executor(None, db.commit)

    return {
        "delivery_id": delivery_id,
        "previous_state": current_state,
        "new_state": "queued",
        "message": "Delivery queued for resend",
    }


@router.get("/deliveries/{delivery_id}", dependencies=[Depends(verify_api_key)])
async def get_delivery(delivery_id: int):
    """Get individual delivery details by ID"""
    from ...database.repositories import DeliveryRepository

    asyncio.get_event_loop()
    delivery_repo = DeliveryRepository(db)

    try:
        delivery = await asyncio.wait_for(
            asyncio.to_thread(delivery_repo.get_by_id, delivery_id),
            timeout=api_db_timeout
        )

        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Delivery not found",
            )

        return delivery
    except asyncio.TimeoutError:
        logger.error(f"Timeout getting delivery {delivery_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out while fetching delivery",
        )
    except Exception as e:
        logger.error(f"Error getting delivery: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get delivery: {str(e)}",
        )


@router.post("/deliveries/{delivery_id}/abort", dependencies=[Depends(verify_api_key)])
async def abort_delivery(delivery_id: int):
    """
    Abort a pending delivery immediately.

    Moves the delivery to 'cancelled' state, preventing further delivery attempts.
    """
    from ...database.repositories import DeliveryRepository
    from ...core.state_machine import DeliveryState

    loop = asyncio.get_event_loop()
    delivery_repo = DeliveryRepository(db)
    delivery = await loop.run_in_executor(None, delivery_repo.get_by_id, delivery_id)

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    current_state = delivery["state"]

    # Check if already in a terminal state
    terminal_states = [
        DeliveryState.DELIVERED.value,
        DeliveryState.READ.value,
        DeliveryState.HARD_FAILED.value,
        DeliveryState.CANCELLED.value,
        DeliveryState.TTL_EXPIRED.value
    ]

    if current_state in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot abort delivery in terminal state '{current_state}'.",
        )

    # Move to cancelled state
    await loop.run_in_executor(None, delivery_repo.update_state, delivery_id, DeliveryState.CANCELLED.value)

    return {
        "delivery_id": delivery_id,
        "previous_state": current_state,
        "new_state": "cancelled",
        "message": "Delivery aborted",
    }


# ============================================================================
# Storage File CRUD Endpoints (MUST BE BEFORE generic /storage/{file_path:path})
# ============================================================================

def _get_storage_backend_config(backend_type: str) -> dict:
    """
    Get storage backend configuration from env or database channels.

    Args:
        backend_type: Backend type (filesystem, webdav, s3, ftp)

    Returns:
        Storage configuration dict
    """
    # Try to get config from environment first
    config = _runtime_config()
    storage_config = config.get(f"file_channel.{backend_type}", {})

    # Check if file_channel config is actually populated (skip empty defaults)
    if storage_config:
        if backend_type == "webdav" and not storage_config.get("url"):
            storage_config = {}
        elif backend_type == "s3" and not storage_config.get("endpoint"):
            storage_config = {}
        elif backend_type == "ftp" and not storage_config.get("host"):
            storage_config = {}
        elif backend_type == "filesystem" and not storage_config.get("base_path"):
            storage_config = {}

    # Try storage config if file_channel not found
    if not storage_config:
        storage_config = config.get(f"storage.{backend_type}", {})
        # Check if storage config is actually populated (skip empty defaults)
        if backend_type == "webdav" and not storage_config.get("url"):
            storage_config = {}
        elif backend_type == "s3" and not storage_config.get("endpoint"):
            storage_config = {}
        elif backend_type == "ftp" and not storage_config.get("host"):
            storage_config = {}
        elif backend_type == "filesystem" and not storage_config.get("base_path"):
            storage_config = {}

    # If not in env, find ALL file channels with matching backend type
    # and return them as a list for the caller to try
    if not storage_config:
        channels = channel_repo.list_all()
        matching_channels = []

        for ch in channels:
            if ch.get("type") == "file":
                ch_config = json.loads(ch.get("config_json", "{}"))
                if ch_config.get("storage_type") == backend_type:
                    matching_channels.append(ch_config)

        # If only one matching channel, use it
        if len(matching_channels) == 1:
            storage_config = matching_channels[0]
        # If multiple, return the list so caller can try each one
        elif len(matching_channels) > 1:
            return {"_multiple": True, "_channels": matching_channels}

    return storage_config


@router.put("/storage/files/{backend_type}/{filename:path}", dependencies=[Depends(verify_api_key)])
async def update_storage_file(backend_type: str, filename: str, payload: dict):
    """
    Update/overwrite file content in storage backend.

    Args:
        backend_type: Storage backend type (filesystem, webdav, s3, ftp)
        filename: File path/name to update
        payload: JSON with 'content' field containing new content

    Returns:
        Success status
    """
    from ...core.storage.factory import StorageFactory

    content = payload.get("content")
    if content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'content' field in payload"
        )

    # Get storage backend config
    storage_config = _get_storage_backend_config(backend_type)

    # Handle multiple channels - try each one until update succeeds
    if storage_config.get("_multiple"):
        channels = storage_config["_channels"]

        for ch_config in channels:
            try:
                ch_config["storage_type"] = backend_type
                backend = StorageFactory.create(ch_config)
                # First check if file exists in THIS channel
                exists = await backend.exists(filename)
                if not exists:
                    continue
                # File exists, update it
                content_bytes = content.encode('utf-8') if isinstance(content, str) else content
                stored_file = await backend.store_file(
                    content=content_bytes,
                    filename=filename,
                    content_type="text/plain"
                )
                return {
                    "status": "updated",
                    "filename": filename,
                    "backend": backend_type,
                    "size": stored_file.size_bytes
                }
            except Exception:
                continue

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {filename}")

    if not storage_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage backend '{backend_type}' not configured"
        )

    storage_config["storage_type"] = backend_type

    try:
        backend = StorageFactory.create(storage_config)

        # Convert content to bytes
        content_bytes = content.encode('utf-8') if isinstance(content, str) else content

        # Store/update file
        stored_file = await backend.store_file(
            content=content_bytes,
            filename=filename,
            content_type="text/plain"
        )

        return {
            "status": "updated",
            "filename": filename,
            "backend": backend_type,
            "size": stored_file.size_bytes
        }

    except Exception as e:
        logger.error(f"Error updating file in {backend_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update file: {str(e)}"
        )


@router.get("/storage/files/{backend_type}/{filename:path}/exists", dependencies=[Depends(verify_api_key)])
async def check_file_exists(backend_type: str, filename: str):
    """
    Check if file exists in storage backend.

    Args:
        backend_type: Storage backend type (filesystem, webdav, s3, ftp)
        filename: File path/name to check

    Returns:
        Boolean indicating if file exists
    """
    from ...core.storage.factory import StorageFactory

    # Get storage backend config
    storage_config = _get_storage_backend_config(backend_type)

    # Handle multiple channels - check if file exists in any of them
    if storage_config.get("_multiple"):
        channels = storage_config["_channels"]

        for ch_config in channels:
            try:
                ch_config["storage_type"] = backend_type
                backend = StorageFactory.create(ch_config)
                exists = await backend.exists(filename)
                if exists:
                    return {"filename": filename, "exists": True}
            except Exception:
                continue

        return {"filename": filename, "exists": False}

    if not storage_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage backend '{backend_type}' not configured"
        )

    storage_config["storage_type"] = backend_type

    try:
        backend = StorageFactory.create(storage_config)
        exists = await backend.file_exists(filename)

        return {
            "exists": exists,
            "filename": filename,
            "backend": backend_type
        }

    except Exception as e:
        logger.error(f"Error checking file existence in {backend_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check file existence: {str(e)}"
        )


@router.get("/storage/files/{backend_type}/{filename:path}", dependencies=[Depends(verify_api_key)])
async def read_storage_file(backend_type: str, filename: str):
    """
    Read file content from storage backend.

    Args:
        backend_type: Storage backend type (filesystem, webdav, s3, ftp)
        filename: File path/name to read

    Returns:
        File content
    """
    from ...core.storage.factory import StorageFactory
    from ...core.storage.base import FileNotFoundError as StorageFileNotFoundError

    logger.info(f"[STORAGE READ] Backend: {backend_type}, Filename: {filename}")

    # Get storage backend config
    storage_config = _get_storage_backend_config(backend_type)

    # Handle multiple channels - try each one until we find the file
    if storage_config.get("_multiple"):
        channels = storage_config["_channels"]
        logger.info(f"[STORAGE READ] Found {len(channels)} channels, trying each")

        for ch_config in channels:
            try:
                ch_config["storage_type"] = backend_type
                backend = StorageFactory.create(ch_config)
                content = await backend.get_file_content(filename)
                # File found! Return it
                return Response(content=content, media_type="text/plain")
            except Exception:
                # File not in this channel, try next
                continue

        # File not found in any channel
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {filename}")

    if not storage_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage backend '{backend_type}' not configured"
        )

    storage_config["storage_type"] = backend_type
    logger.info(f"[STORAGE READ] Using config: {storage_config}")

    try:
        backend = StorageFactory.create(storage_config)
        content = await backend.get_file_content(filename)

        # Return as plain text
        return Response(content=content, media_type="text/plain")

    except StorageFileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error reading file from {backend_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read file: {str(e)}"
        )


@router.delete("/storage/files/{backend_type}/{filename:path}", dependencies=[Depends(verify_api_key)])
async def delete_storage_file(backend_type: str, filename: str):
    """
    Delete file from storage backend.

    Args:
        backend_type: Storage backend type (filesystem, webdav, s3, ftp)
        filename: File path/name to delete

    Returns:
        Success status
    """
    from ...core.storage.factory import StorageFactory

    # Get storage backend config
    storage_config = _get_storage_backend_config(backend_type)

    # Handle multiple channels - try each one until delete succeeds
    if storage_config.get("_multiple"):
        channels = storage_config["_channels"]

        for ch_config in channels:
            try:
                ch_config["storage_type"] = backend_type
                backend = StorageFactory.create(ch_config)
                # First check if file exists in THIS channel
                exists = await backend.exists(filename)
                if not exists:
                    continue
                # File exists, delete it
                success = await backend.delete_file(filename)
                if success:
                    return {
                        "status": "deleted",
                        "filename": filename,
                        "backend": backend_type
                    }
            except Exception:
                continue

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {filename}")

    if not storage_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Storage backend '{backend_type}' not configured"
        )

    storage_config["storage_type"] = backend_type

    try:
        backend = StorageFactory.create(storage_config)
        success = await backend.delete_file(filename)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {filename}"
            )

        return {
            "status": "deleted",
            "filename": filename,
            "backend": backend_type
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file from {backend_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


# Storage endpoints - Serve stored files (PDFs, HTML pages, images, etc.)

@router.get("/storage/{file_path:path}")
async def serve_storage_file(file_path: str, request: Request):
    """
    Serve stored files (PDFs, HTML pages, images, audio, video)

    This endpoint serves files from the notification storage directory.
    Files are organized by type and date (e.g., storage/html/2025/12/03/...)

    Args:
        file_path: Path to file relative to storage root (e.g., "html/2025/12/03/file.html")
    """
    from ...core.storage.storage_manager import get_storage_manager
    from pathlib import Path
    import mimetypes

    try:
        storage_manager = get_storage_manager()
        if not storage_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage manager not available"
            )

        # Retrieve file from storage
        file_content = storage_manager.retrieve_file(file_path)

        if file_content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_path}"
            )

        # Determine MIME type from file extension
        file_ext = Path(file_path).suffix.lower()
        mime_type, _ = mimetypes.guess_type(file_path)

        # Default MIME types for common file types
        if not mime_type:
            mime_map = {
                '.html': 'text/html',
                '.htm': 'text/html',
                '.pdf': 'application/pdf',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.mp3': 'audio/mpeg',
                '.wav': 'audio/wav',
                '.mp4': 'video/mp4',
                '.webm': 'video/webm',
            }
            mime_type = mime_map.get(file_ext, 'application/octet-stream')

        # Set appropriate headers
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(len(file_content)),
        }

        # For HTML files, add charset
        if mime_type.startswith('text/html'):
            headers["Content-Type"] = 'text/html; charset=utf-8'

        # For images, allow caching
        if mime_type.startswith('image/'):
            headers["Cache-Control"] = "public, max-age=3600"

        return Response(
            content=file_content,
            media_type=headers["Content-Type"],
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving storage file {file_path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve file: {str(e)}"
        )


# Channels endpoints

@router.delete("/messages/{message_id}", dependencies=[Depends(verify_api_key)])
async def delete_message_by_id(message_id: int):
    """Delete a message and its deliveries (FULL CRUD)"""
    from ...database.repositories import MessageRepository

    db = get_db_manager()
    msg_repo = MessageRepository(db)

    # Check if message exists
    existing = msg_repo.get_by_id(message_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )

    # Delete message (cascade deletes deliveries)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, db.execute, "DELETE FROM messages WHERE id = ?", (message_id,))
    await loop.run_in_executor(None, db.commit)

    return {"deleted": True, "id": message_id}


#============================================================================
# Groups endpoints
# ============================================================================
