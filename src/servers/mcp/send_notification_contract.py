#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
# SPDX-License-Identifier: Apache-2.0

"""Shared MCP contract helpers for the send_notification tool."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

SEND_NOTIFICATION_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "destinations": {
            "type": "array",
            "description": "List of destinations (channel and address)",
            "items": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "Channel name"},
                    "address": {"type": "string", "description": "Destination address"},
                    "destination": {"type": "string", "description": "Alias for address"},
                    "recipient": {"type": "string", "description": "Alias for address"},
                    "url": {"type": "string", "description": "Alias for address"},
                    "type": {"type": "string", "description": "Alias for channel"},
                    "preferences": {"type": "object", "description": "Per-destination delivery preferences"},
                    "user_email": {"type": "string", "description": "Optional user email for channel destinations"},
                },
                "required": ["channel", "address"],
            },
        },
        "content": {
            "type": "array",
            "description": "Message content blocks",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "description": "Content type"},
                    "body": {"type": "string", "description": "Content body"},
                    "html": {"type": "string", "description": "Alias for an HTML body"},
                    "text": {"type": "string", "description": "Alias for a text body"},
                    "markdown": {"type": "string", "description": "Alias for a markdown body"},
                    "subject": {"type": "string", "description": "Optional message subject"},
                    "metadata": {"type": "object", "description": "Optional content metadata"},
                },
                "required": ["type", "body"],
            },
        },
        "audience_type": {"type": "string", "description": "Audience mode, usually personalised"},
        "subject": {"type": "string", "description": "Optional message subject"},
        "options": {"type": "object", "description": "Additional API message options"},
        "idempotency_key": {
            "type": "string",
            "description": "Optional idempotency key to prevent duplicates",
        },
        "async_mode": {
            "type": "boolean",
            "default": False,
            "description": (
                "XC-010: when true, submit the notification as a background job through "
                "cloud_dog_jobs and return {job_id, queued: true} immediately instead of "
                "waiting for delivery completion. When false (default) the call runs inline "
                "and returns the delivery result. Queued and inline paths share the same "
                "message-post handler logic; poll /admin/jobs/<job_id> (or /messages/<id>) "
                "for terminal status."
            ),
        },
    },
    "required": ["destinations", "content"],
}

SEND_NOTIFICATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "job_id": {"type": ["string", "integer", "null"]},
        "queued": {"type": "boolean"},
        "message_id": {"type": ["integer", "null"]},
        "delivery_ids": {"type": "array", "items": {"type": "integer"}},
        "status": {"type": "string", "enum": ["completed", "partial", "failed"]},
        "deduped": {"type": "boolean"},
        "error": {"type": "string"},
        "diagnostics": {"type": ["object", "array", "null"]},
    },
    "required": ["ok", "message_id", "delivery_ids", "status", "deduped"],
    "additionalProperties": True,
}

PostMessage = Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]
GetDeliveries = Callable[[int], Awaitable[Any] | Any]
ResolveDuplicate = Callable[[str], Awaitable[dict[str, Any] | None] | dict[str, Any] | None]


def _coerce_content_block(block: Any) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {"type": "text", "body": str(block)}

    result = dict(block)
    body = result.get("body")
    if body in (None, ""):
        for alias, content_type in (("html", "html"), ("markdown", "markdown"), ("md", "markdown"), ("text", "text"), ("content", None)):
            value = result.get(alias)
            if value not in (None, ""):
                result["body"] = str(value)
                if content_type and not result.get("type"):
                    result["type"] = content_type
                break

    if not result.get("type"):
        result["type"] = "text"
    if result.get("body") in (None, ""):
        result["body"] = ""
    else:
        result["body"] = str(result["body"])
    return result


def _coerce_destination(dest: Any) -> dict[str, Any]:
    if not isinstance(dest, dict):
        return {"channel": "", "address": str(dest)}

    result = dict(dest)
    channel = result.get("channel") or result.get("type") or result.get("channel_name")
    address = result.get("address") or result.get("destination") or result.get("recipient") or result.get("url") or result.get("webhook")

    if channel is not None:
        result["channel"] = str(channel)
    if address is not None:
        address = str(address).strip()
        channel_norm = str(result.get("channel") or "").strip().lower()
        # LLMs often drop the group: prefix from named email-group destinations.
        # Preserve direct email addresses and URLs, but normalise bare display
        # names for the API group resolver.
        if (
            address
            and not address.startswith("group:")
            and "@" not in address
            and "://" not in address
            and channel_norm in {"email", "smtp", "email_default"}
        ):
            address = f"group:{address}"
        result["address"] = address
    return result


def build_send_notification_api_payload(arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalise MCP arguments into the REST API message-create payload."""
    content = arguments.get("content")
    if isinstance(content, list):
        content_blocks = [_coerce_content_block(block) for block in content]
    elif isinstance(content, dict):
        content_blocks = [_coerce_content_block(content)]
    else:
        content_blocks = [_coerce_content_block({"type": "text", "body": str(content)})]

    destinations = arguments.get("destinations") or []
    if not isinstance(destinations, list):
        destinations = [destinations]

    payload: dict[str, Any] = {
        "destinations": [_coerce_destination(dest) for dest in destinations],
        "content": content_blocks,
    }
    if arguments.get("audience_type"):
        payload["audience_type"] = arguments["audience_type"]
    if isinstance(arguments.get("options"), dict):
        payload["options"] = dict(arguments["options"])
    subject = arguments.get("subject") or next((block.get("subject") for block in content_blocks if isinstance(block, dict) and block.get("subject")), None)
    if subject:
        options = dict(payload.get("options") or {})
        options.setdefault("subject", subject)
        payload["options"] = options
    if arguments.get("idempotency_key"):
        payload["idempotency_key"] = arguments["idempotency_key"]
    return payload


def extract_delivery_ids(deliveries_payload: Any) -> list[int]:
    """Extract delivery IDs from the API deliveries response shapes used by this service."""
    if isinstance(deliveries_payload, dict):
        if isinstance(deliveries_payload.get("items"), list):
            deliveries = deliveries_payload["items"]
        elif isinstance(deliveries_payload.get("deliveries"), list):
            deliveries = deliveries_payload["deliveries"]
        elif isinstance(deliveries_payload.get("data"), list):
            deliveries = deliveries_payload["data"]
        else:
            deliveries = []
    elif isinstance(deliveries_payload, list):
        deliveries = deliveries_payload
    else:
        deliveries = []

    delivery_ids: list[int] = []
    for delivery in deliveries:
        if not isinstance(delivery, dict):
            continue
        raw_id = delivery.get("id", delivery.get("delivery_id"))
        try:
            delivery_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    return delivery_ids


def build_success_tool_payload(
    *,
    message_id: int,
    delivery_ids: list[int],
    deduped: bool,
    status: str = "completed",
    diagnostics: Any | None = None,
) -> dict[str, Any]:
    structured: dict[str, Any] = {
        "ok": True,
        "message_id": int(message_id),
        "delivery_ids": [int(delivery_id) for delivery_id in delivery_ids],
        "status": status,
        "deduped": bool(deduped),
    }
    if diagnostics is not None:
        structured["diagnostics"] = diagnostics

    delivery_text = ",".join(str(delivery_id) for delivery_id in structured["delivery_ids"])
    return {
        "content": [
            {
                "type": "text",
                "text": f"Notification sent: message {structured['message_id']}, deliveries {delivery_text}",
            }
        ],
        "structuredContent": structured,
        "isError": False,
    }


def build_failure_tool_payload(
    *,
    error: str,
    message_id: int | None = None,
    delivery_ids: list[int] | None = None,
    diagnostics: Any | None = None,
) -> dict[str, Any]:
    structured: dict[str, Any] = {
        "ok": False,
        "message_id": int(message_id) if message_id is not None else None,
        "delivery_ids": [int(delivery_id) for delivery_id in (delivery_ids or [])],
        "status": "failed",
        "deduped": False,
        "error": str(error),
    }
    if diagnostics is not None:
        structured["diagnostics"] = diagnostics

    return {
        "content": [{"type": "text", "text": f"Notification send failed: {error}"}],
        "structuredContent": structured,
        "isError": True,
    }


def is_duplicate_idempotency_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 409:
        return True
    return "Duplicate idempotency key" in str(exc)


def resolve_duplicate_notification_from_db(config: Any, idempotency_key: str) -> dict[str, Any] | None:
    """Resolve an idempotent duplicate through the existing message/delivery repositories."""
    if not idempotency_key:
        return None

    db_uri = config.get("db.uri") if config is not None and hasattr(config, "get") else None
    if not db_uri:
        return None

    from ...database import DeliveryRepository, MessageRepository, get_db_manager

    db = get_db_manager(db_uri)
    message = MessageRepository(db).get_by_idempotency_key(idempotency_key)
    if not message:
        return None

    message_id = int(message["id"])
    deliveries = DeliveryRepository(db).get_by_message_id(message_id)
    return {
        "message_id": message_id,
        "delivery_ids": extract_delivery_ids(deliveries),
    }


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def execute_send_notification(
    arguments: dict[str, Any],
    *,
    post_message: PostMessage,
    get_deliveries: GetDeliveries,
    resolve_duplicate: ResolveDuplicate,
) -> dict[str, Any]:
    """Execute send_notification and return a complete MCP tool-call payload."""
    api_payload = build_send_notification_api_payload(arguments)
    requested_count = len(api_payload.get("destinations") or [])
    idempotency_key = str(api_payload.get("idempotency_key") or "")

    try:
        api_result = await _maybe_await(post_message(api_payload))
        raw_message_id = api_result.get("message_id") or api_result.get("id")
        message_id = int(raw_message_id)
        # XC-010: async path — the message POST has already submitted the delivery
        # JobEnvelope(s) through cloud_dog_jobs at the API layer. When async_mode is
        # requested, return the queued handle immediately and let the worker drive the
        # delivery jobs to terminal status (poll /admin/jobs/<job_id> or /messages/<id>).
        if bool(arguments.get("async_mode")):
            job_id = str(api_result.get("job_id") or api_result.get("delivery_job_id") or message_id)
            return {
                "ok": True,
                "queued": True,
                "job_id": job_id,
                "message_id": message_id,
                "status": "queued",
            }
        deliveries_payload = await _maybe_await(get_deliveries(message_id))
        delivery_ids = extract_delivery_ids(deliveries_payload)
        if not delivery_ids:
            return build_failure_tool_payload(
                error="Message was created but no deliveries were accepted",
                message_id=message_id,
                diagnostics={"api_result": api_result},
            )

        status = "partial" if requested_count > 0 and len(delivery_ids) < requested_count else "completed"
        diagnostics = None
        if status == "partial":
            diagnostics = {
                "requested_destinations": requested_count,
                "accepted_deliveries": len(delivery_ids),
            }
        return build_success_tool_payload(
            message_id=message_id,
            delivery_ids=delivery_ids,
            status=status,
            deduped=False,
            diagnostics=diagnostics,
        )
    except Exception as exc:
        if idempotency_key and is_duplicate_idempotency_error(exc):
            duplicate = await _maybe_await(resolve_duplicate(idempotency_key))
            if duplicate:
                message_id = int(duplicate["message_id"])
                delivery_ids = [int(delivery_id) for delivery_id in duplicate.get("delivery_ids") or []]
                if delivery_ids:
                    return build_success_tool_payload(
                        message_id=message_id,
                        delivery_ids=delivery_ids,
                        deduped=True,
                    )
                return build_failure_tool_payload(
                    error="Duplicate idempotency key resolved to a message with no deliveries",
                    message_id=message_id,
                )

        return build_failure_tool_payload(error=str(exc))
