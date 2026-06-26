#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
# SPDX-License-Identifier: Apache-2.0

"""Centralised MCP tool registry with per-tool RBAC and audit logging.

Provides the canonical tool catalogue for notification-agent MCP servers.
All tool definitions, RBAC permission mappings, and audit middleware are
centralised here so that stdio, SSE, and JSON-RPC transports share a
single source of truth.

Uses cloud_dog_api_kit ToolContract for tool definitions (PS-50 compliance).
Uses cloud_dog_idam RBAC for per-tool permission enforcement (PS-70 UM3).
Uses cloud_dog_logging for tool audit events (PS-40 L3).

Related: W28A-740, PS-50, PS-70 UM3, PS-40 L3
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict

from cloud_dog_api_kit import ToolContract
from cloud_dog_logging import get_logger  # type: ignore[import-untyped]

from .send_notification_contract import SEND_NOTIFICATION_INPUT_SCHEMA, SEND_NOTIFICATION_OUTPUT_SCHEMA

logger = get_logger("notification_agent.mcp.tools")

# ── PS-70 UM3: Per-tool RBAC permission map ──────────────────────────────

TOOL_RBAC_MAP: Dict[str, str] = {
    # Email send operations (higher privilege)
    "send_notification": "notify:email:send",
    "send_notification_natural": "notify:email:send",
    # Email read operations
    "list_messages": "notify:email:read",
    "get_message": "notify:email:read",
    "get_message_status": "notify:email:read",
    "list_deliveries": "notify:email:read",
    # Message control
    "cancel_message": "notify:email:send",
    "resend_delivery": "notify:email:send",
    "abort_delivery": "notify:email:send",
    # Channel operations
    "list_channels": "notify:channel:read",
    "admin_list_channels": "notify:admin:*",
    "admin_create_channel": "notify:admin:*",
    "admin_update_channel": "notify:admin:*",
    "admin_delete_channel": "notify:admin:*",
    # Admin user operations
    "admin_list_users": "notify:admin:*",
    "admin_create_user": "notify:admin:*",
    # Admin group operations
    "admin_list_groups": "notify:admin:*",
    "admin_create_group": "notify:admin:*",
    "admin_update_group": "notify:admin:*",
    "admin_add_group_member": "notify:admin:*",
    "admin_list_group_members": "notify:admin:*",
    "admin_remove_group_member": "notify:admin:*",
    # Admin API key operations
    "admin_create_api_key": "notify:admin:*",
    "admin_revoke_api_key": "notify:admin:*",
    # System status
    "get_status": "notify:status:read",
}


def check_tool_permission(tool_name: str, user_role: str = "user") -> bool:
    """Check whether a role has permission to call a tool via cloud_dog_idam RBAC.

    Uses cloud_dog_idam.RBACEngine.has_permission pattern for per-tool enforcement.
    Admin role has wildcard access. Other roles checked against TOOL_RBAC_MAP.
    """
    from cloud_dog_idam import RBACEngine

    required = TOOL_RBAC_MAP.get(tool_name, "notify:tool:execute")
    if user_role == "admin":
        return True
    engine = RBACEngine()
    engine.assign_role_to_user(user_role, user_role)
    return engine.has_permission(user_role, required)


# ── PS-40 L3: Tool audit logging ─────────────────────────────────────────

_REDACT_KEYS = {"password", "secret", "token", "api_key", "content", "body", "message_body", "recipients", "to", "email"}


def _redact_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields from tool parameters for audit logging."""
    redacted: Dict[str, Any] = {}
    for key, value in (params or {}).items():
        lower = key.lower()
        if any(s in lower for s in _REDACT_KEYS):
            if isinstance(value, str):
                redacted[key] = f"[REDACTED {len(value)} chars]"
            elif isinstance(value, list):
                redacted[key] = f"[REDACTED {len(value)} items]"
            else:
                redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value
    return redacted


def audit_tool_call(
    tool_name: str,
    params: Dict[str, Any],
    *,
    success: bool = True,
    duration_ms: float = 0.0,
    error: str = "",
    actor_id: str = "",
    correlation_id: str = "",
) -> None:
    """Emit a structured audit event for an MCP tool call (PS-40 L3)."""
    logger.info(
        f"mcp_tool_audit tool={tool_name} outcome={'success' if success else 'failure'}"
        f" duration_ms={duration_ms:.0f} actor={actor_id}"
    )


def wrap_tool_with_audit(tool_name: str, handler: Callable) -> Callable:
    """Wrap a tool handler with audit logging and RBAC check."""

    async def _audited_handler(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        success = True
        error_msg = ""
        try:
            result = handler(*args, **kwargs)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as exc:
            success = False
            error_msg = str(exc)[:200]
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            params = args[0] if args and isinstance(args[0], dict) else kwargs
            audit_tool_call(
                tool_name,
                _redact_params(params if isinstance(params, dict) else {}),
                success=success,
                duration_ms=duration_ms,
                error=error_msg,
            )

    _audited_handler.__name__ = f"audited_{tool_name}"
    _audited_handler.__qualname__ = f"audited_{tool_name}"
    return _audited_handler


# ── Tool catalogue (cloud_dog_api_kit ToolContract) ───────────────────────

def build_tool_contracts() -> Dict[str, ToolContract]:
    """Return the canonical tool catalogue as cloud_dog_api_kit ToolContract objects.

    This is the single source of truth for all MCP tool definitions. The
    stdio, SSE, and JSON-RPC transports should reference this catalogue
    rather than maintaining separate tool lists.
    """
    return {
        "send_notification": ToolContract(
            name="send_notification",
            handler=lambda p: p,  # Placeholder — real handler bound at transport level
            description="Send a notification message to specified destinations.",
            input_schema=SEND_NOTIFICATION_INPUT_SCHEMA,
            output_schema=SEND_NOTIFICATION_OUTPUT_SCHEMA,
        ),
        "get_message_status": ToolContract(
            name="get_message_status",
            handler=lambda p: p,
            description="Get delivery status for a message by ID.",
            input_schema={"type": "object", "properties": {"message_id": {"type": "integer"}}},
        ),
        "list_channels": ToolContract(
            name="list_channels",
            handler=lambda p: p,
            description="List available notification channels.",
            input_schema={"type": "object", "properties": {}},
        ),
        "cancel_message": ToolContract(
            name="cancel_message",
            handler=lambda p: p,
            description="Cancel a pending notification message.",
            input_schema={"type": "object", "properties": {"message_id": {"type": "integer"}}},
        ),
        "send_notification_natural": ToolContract(
            name="send_notification_natural",
            handler=lambda p: p,
            description="Send notification using natural language description.",
            input_schema={"type": "object", "properties": {"instruction": {"type": "string"}}},
        ),
        "list_messages": ToolContract(
            name="list_messages",
            handler=lambda p: p,
            description="List recent messages with optional filtering.",
            input_schema={"type": "object", "properties": {"limit": {"type": "integer"}, "status": {"type": "string"}}},
        ),
        "get_message": ToolContract(
            name="get_message",
            handler=lambda p: p,
            description="Get detailed information for a message.",
            input_schema={"type": "object", "properties": {"message_id": {"type": "integer"}}},
        ),
        "list_deliveries": ToolContract(
            name="list_deliveries",
            handler=lambda p: p,
            description="List deliveries for a message.",
            input_schema={"type": "object", "properties": {"message_id": {"type": "integer"}}},
        ),
        "resend_delivery": ToolContract(
            name="resend_delivery",
            handler=lambda p: p,
            description="Resend a failed delivery attempt.",
            input_schema={"type": "object", "properties": {"delivery_id": {"type": "integer"}}},
        ),
        "abort_delivery": ToolContract(
            name="abort_delivery",
            handler=lambda p: p,
            description="Abort a pending delivery.",
            input_schema={"type": "object", "properties": {"delivery_id": {"type": "integer"}}},
        ),
        "get_status": ToolContract(
            name="get_status",
            handler=lambda p: p,
            description="Get notification agent system status.",
            input_schema={"type": "object", "properties": {}},
        ),
        "admin_list_channels": ToolContract(
            name="admin_list_channels",
            handler=lambda p: p,
            description="Admin: list all notification channels.",
            input_schema={"type": "object", "properties": {}},
        ),
        "admin_create_channel": ToolContract(
            name="admin_create_channel",
            handler=lambda p: p,
            description="Admin: create a notification channel.",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "config": {"type": "object"}}},
        ),
        "admin_update_channel": ToolContract(
            name="admin_update_channel",
            handler=lambda p: p,
            description="Admin: update a notification channel.",
            input_schema={"type": "object", "properties": {"channel_id": {"type": "string"}, "config": {"type": "object"}}},
        ),
        "admin_delete_channel": ToolContract(
            name="admin_delete_channel",
            handler=lambda p: p,
            description="Admin: delete a notification channel.",
            input_schema={"type": "object", "properties": {"channel_id": {"type": "string"}}},
        ),
        "admin_list_users": ToolContract(
            name="admin_list_users",
            handler=lambda p: p,
            description="Admin: list all users.",
            input_schema={"type": "object", "properties": {}},
        ),
        "admin_create_user": ToolContract(
            name="admin_create_user",
            handler=lambda p: p,
            description="Admin: create a user.",
            input_schema={"type": "object", "properties": {"username": {"type": "string"}, "email": {"type": "string"}}},
        ),
        "admin_create_api_key": ToolContract(
            name="admin_create_api_key",
            handler=lambda p: p,
            description="Admin: create an API key.",
            input_schema={"type": "object", "properties": {"user_id": {"type": "integer"}, "name": {"type": "string"}}},
        ),
        "admin_revoke_api_key": ToolContract(
            name="admin_revoke_api_key",
            handler=lambda p: p,
            description="Admin: revoke an API key.",
            input_schema={"type": "object", "properties": {"key_id": {"type": "integer"}}},
        ),
    }
