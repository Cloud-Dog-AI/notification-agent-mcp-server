#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: MCP Server for Notification Agent - Provides MCP protocol tools for agent-based notification interaction

Related Requirements: FR1.5, UC1.2
Related Tasks: T11
Related Architecture: CC1.3
Related Tests: IT1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import json
import time
from typing import Any, Dict, List
from cloud_dog_api_kit.clients import ClientTimeout, create_http_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from ...config import get_config
from ...utils.logger import setup_logger
from .tool_registry import TOOL_RBAC_MAP, audit_tool_call, check_tool_permission, build_tool_contracts
from .send_notification_contract import (
    SEND_NOTIFICATION_INPUT_SCHEMA,
    SEND_NOTIFICATION_OUTPUT_SCHEMA,
    build_failure_tool_payload,
    execute_send_notification,
    resolve_duplicate_notification_from_db,
)


# Global configuration
config = None
logger = None
api_base_url = None
api_key = None
# Shared long-lived HTTP client for API requests (W28A-93b, AGENT-LESSONS §2.3)
_mcp_http_client: Any = None


def _require_config(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _truncate_params(params: Dict[str, Any]) -> str:
    try:
        rendered = json.dumps(params, default=str)
    except Exception:
        rendered = str(params)
    max_len = 1000
    if len(rendered) > max_len:
        return f"{rendered[:max_len]}...(truncated)"
    return rendered


def _get_mcp_http_client() -> Any:
    """Return module-level shared HTTP client for MCP-to-API calls."""
    global _mcp_http_client
    if _mcp_http_client is None or _mcp_http_client.is_closed:
        _mcp_http_client = create_http_client(
            timeout=ClientTimeout(connect=5.0, read=30.0, total=30.0)
        )
    return _mcp_http_client


def _to_call_tool_result(payload: Dict[str, Any]) -> types.CallToolResult:
    content = []
    for item in payload.get("content") or []:
        if isinstance(item, dict):
            content.append(
                types.TextContent(
                    type="text",
                    text=str(item.get("text") or item.get("body") or ""),
                )
            )
    if not content:
        content = [types.TextContent(type="text", text=json.dumps(payload, indent=2))]
    return types.CallToolResult(
        content=content,
        structuredContent=payload.get("structuredContent"),
        isError=bool(payload.get("isError")),
    )


async def _api_request(
    method: str,
    path: str,
    *,
    json_body: Dict[str, Any] | None = None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    client = _get_mcp_http_client()
    response = await client.request(
        method.upper(),
        f"{api_base_url}{path}",
        json=json_body,
        params=params,
        headers={"X-API-Key": api_key},
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{method.upper()} {path} failed {response.status_code}: {response.text[:1000]}")
    return response.json()


# MCP Server instance
mcp_app = Server("notification-agent-mcp")


@mcp_app.list_tools()
async def list_tools() -> List[types.Tool]:
    """List available MCP tools"""
    return [
        types.Tool(
            name="send_notification",
            description="Send a notification to one or more destinations",
            inputSchema=SEND_NOTIFICATION_INPUT_SCHEMA,
            outputSchema=SEND_NOTIFICATION_OUTPUT_SCHEMA,
        ),
        types.Tool(
            name="get_message_status",
            description="Get the status of a notification message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "integer",
                        "description": "Message ID to query",
                    },
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="list_channels",
            description="List all available notification channels",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="cancel_message",
            description="Cancel a pending notification message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "integer",
                        "description": "Message ID to cancel",
                    },
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="send_notification_natural",
            description="Send a notification using natural language (e.g., 'Send notification to Fred that JOB XXXX has finished')",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Natural language command (e.g., 'Send notification to Fred that JOB XXXX has finished', 'Send all the results to the Admin Users')",
                    },
                    "channels": {
                        "type": "array",
                        "description": "Optional: Specific channels to use (if not specified, uses user preferences)",
                        "items": {"type": "string"},
                    },
                },
                "required": ["command"],
            },
        ),
        types.Tool(
            name="list_messages",
            description="List recent messages with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return (default: 100)",
                        "default": 100,
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by message status (optional)",
                    },
                },
            },
        ),
        types.Tool(
            name="get_message",
            description="Get detailed information about a specific message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": ["integer", "string"],
                        "description": "Message ID (numeric) or GUID (UUID format)",
                    },
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="list_deliveries",
            description="List deliveries for a specific message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": ["integer", "string"],
                        "description": "Message ID (numeric) or GUID (UUID format)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset (default: 0)",
                        "default": 0,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of deliveries to return (default: 50)",
                        "default": 50,
                    },
                },
                "required": ["message_id"],
            },
        ),
        types.Tool(
            name="resend_delivery",
            description="Resend a failed or cancelled delivery",
            inputSchema={
                "type": "object",
                "properties": {
                    "delivery_id": {
                        "type": "integer",
                        "description": "Delivery ID to resend",
                    },
                },
                "required": ["delivery_id"],
            },
        ),
        types.Tool(
            name="abort_delivery",
            description="Abort a pending delivery immediately",
            inputSchema={
                "type": "object",
                "properties": {
                    "delivery_id": {
                        "type": "integer",
                        "description": "Delivery ID to abort",
                    },
                },
                "required": ["delivery_id"],
            },
        ),
        types.Tool(
            name="get_status",
            description="Get system status and metrics",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="admin_list_channels",
            description="List channel definitions for admin/configuration tasks",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="admin_create_channel",
            description="Create a channel definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "config": {"type": "object"},
                    "limits": {"type": "object"},
                },
                "required": ["name", "type"],
            },
        ),
        types.Tool(
            name="admin_update_channel",
            description="Update an existing channel definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {"type": "integer"},
                    "updates": {"type": "object"},
                },
                "required": ["channel_id", "updates"],
            },
        ),
        types.Tool(
            name="admin_delete_channel",
            description="Delete a channel definition",
            inputSchema={
                "type": "object",
                "properties": {"channel_id": {"type": "integer"}},
                "required": ["channel_id"],
            },
        ),
        types.Tool(
            name="admin_list_users",
            description="List users for admin/configuration tasks",
            inputSchema={
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "email": {"type": "string"},
                    "limit": {"type": "integer", "default": 100},
                },
            },
        ),
        types.Tool(
            name="admin_create_user",
            description="Create a user profile",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "email": {"type": "string"},
                    "display_name": {"type": "string"},
                    "role": {"type": "string"},
                    "language": {"type": "string"},
                    "preferred_channel": {"type": "string"},
                    "content_style": {"type": "string"},
                },
                "required": ["email"],
            },
        ),
        types.Tool(
            name="admin_list_groups",
            description="List groups for admin/configuration tasks",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="admin_create_group",
            description="Create a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "language": {"type": "string"},
                    "preferred_channel": {"type": "string"},
                    "content_style": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="admin_update_group",
            description="Update an existing group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "description": {"type": "string"},
                    "language": {"type": "string"},
                    "preferred_channel": {"type": "string"},
                    "content_style": {"type": "string"},
                    "enabled": {"type": "boolean"},
                },
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="admin_add_group_member",
            description="Add a user to a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "user_id": {"type": "integer"},
                    "role": {"type": "string", "default": "member"},
                },
                "required": ["group_id", "user_id"],
            },
        ),
        types.Tool(
            name="admin_list_group_members",
            description="List members of a group",
            inputSchema={
                "type": "object",
                "properties": {"group_id": {"type": "integer"}},
                "required": ["group_id"],
            },
        ),
        types.Tool(
            name="admin_remove_group_member",
            description="Remove a user from a group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_id": {"type": "integer"},
                    "user_id": {"type": "integer"},
                },
                "required": ["group_id", "user_id"],
            },
        ),
        types.Tool(
            name="admin_create_api_key",
            description="Generate an admin API key",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner_user_id": {"type": "string"},
                    "ttl_days": {"type": "integer"},
                    "key_prefix": {"type": "string"},
                },
                "required": ["owner_user_id"],
            },
        ),
        types.Tool(
            name="admin_revoke_api_key",
            description="Revoke an admin API key",
            inputSchema={
                "type": "object",
                "properties": {"key_id": {"type": "string"}},
                "required": ["key_id"],
            },
        ),
    ]


@mcp_app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Execute an MCP tool"""
    start_time = time.monotonic()
    tool_params = _truncate_params(arguments)
    success = False
    error_msg = None
    try:
        if name == "send_notification":
            result = await send_notification_tool(arguments)
        elif name == "get_message_status":
            result = await get_message_status_tool(arguments)
        elif name == "list_channels":
            result = await list_channels_tool(arguments)
        elif name == "cancel_message":
            result = await cancel_message_tool(arguments)
        elif name == "send_notification_natural":
            result = await send_notification_natural_tool(arguments)
        elif name == "list_messages":
            result = await list_messages_tool(arguments)
        elif name == "get_message":
            result = await get_message_tool(arguments)
        elif name == "list_deliveries":
            result = await list_deliveries_tool(arguments)
        elif name == "resend_delivery":
            result = await resend_delivery_tool(arguments)
        elif name == "abort_delivery":
            result = await abort_delivery_tool(arguments)
        elif name == "get_status":
            result = await get_status_tool(arguments)
        elif name == "admin_list_channels":
            result = await admin_list_channels_tool(arguments)
        elif name == "admin_create_channel":
            result = await admin_create_channel_tool(arguments)
        elif name == "admin_update_channel":
            result = await admin_update_channel_tool(arguments)
        elif name == "admin_delete_channel":
            result = await admin_delete_channel_tool(arguments)
        elif name == "admin_list_users":
            result = await admin_list_users_tool(arguments)
        elif name == "admin_create_user":
            result = await admin_create_user_tool(arguments)
        elif name == "admin_list_groups":
            result = await admin_list_groups_tool(arguments)
        elif name == "admin_create_group":
            result = await admin_create_group_tool(arguments)
        elif name == "admin_update_group":
            result = await admin_update_group_tool(arguments)
        elif name == "admin_add_group_member":
            result = await admin_add_group_member_tool(arguments)
        elif name == "admin_list_group_members":
            result = await admin_list_group_members_tool(arguments)
        elif name == "admin_remove_group_member":
            result = await admin_remove_group_member_tool(arguments)
        elif name == "admin_create_api_key":
            result = await admin_create_api_key_tool(arguments)
        elif name == "admin_revoke_api_key":
            result = await admin_revoke_api_key_tool(arguments)
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        if isinstance(result, types.CallToolResult):
            success = not result.isError
            return result

        success = True
        return [types.TextContent(
            type="text",
            text=json.dumps(result, indent=2),
        )]
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error executing tool {name}: {e}")
        if name == "send_notification":
            return _to_call_tool_result(build_failure_tool_payload(error=str(e)))
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2),
        )]
    finally:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        if logger:
            logger.info(
                "mcp_stdio_tool",
                extra={
                    "tool_name": name,
                    "tool_params": tool_params,
                    "duration_ms": duration_ms,
                    "success": success,
                    "error": error_msg,
                },
            )


async def send_notification_tool(arguments: Dict[str, Any]) -> Dict:
    """Send notification tool implementation"""
    async def _post_message(api_payload: Dict[str, Any]) -> Dict[str, Any]:
        return await _api_request("POST", "/messages", json_body=api_payload)

    async def _get_deliveries(message_id: int) -> Any:
        return await _api_request(
            "GET",
            f"/messages/{message_id}/deliveries",
            params={"offset": 0, "limit": 1000},
        )

    def _resolve_duplicate(idempotency_key: str) -> Dict[str, Any] | None:
        return resolve_duplicate_notification_from_db(config, idempotency_key)

    payload = await execute_send_notification(
        arguments,
        post_message=_post_message,
        get_deliveries=_get_deliveries,
        resolve_duplicate=_resolve_duplicate,
    )
    return _to_call_tool_result(payload)


async def get_message_status_tool(arguments: Dict[str, Any]) -> Dict:
    """Get message status tool implementation"""
    message_id = arguments.get("message_id")
    return await _api_request("GET", f"/messages/{message_id}")


async def list_channels_tool(arguments: Dict[str, Any]) -> Dict:
    """List channels tool implementation"""
    channels = await _api_request("GET", "/channels")
    return {"channels": channels, "count": len(channels)}


async def cancel_message_tool(arguments: Dict[str, Any]) -> Dict:
    """Cancel message tool implementation"""
    message_id = arguments.get("message_id")
    return await _api_request("POST", f"/messages/{message_id}/cancel")


async def send_notification_natural_tool(arguments: Dict[str, Any]) -> Dict:
    """Send notification using natural language command"""
    from ...database import get_db_manager
    from ...core.resolvers import NaturalLanguageParser
    from ...config import get_config
    
    command = arguments.get("command", "")
    specified_channels = arguments.get("channels", [])
    
    # Parse natural language command
    temp_config = get_config()
    db_uri = _require_config(temp_config.get("db.uri"), "db.uri")
    default_channel = _require_config(temp_config.get("default_channel"), "default_channel")
    db = get_db_manager(db_uri)
    db.connect()
    parser = NaturalLanguageParser(db)
    parsed = parser.parse(command)
    
    # Build destinations from parsed recipients and groups
    destinations = []
    
    # Add individual recipients
    for recipient in parsed.get("recipients", []):
        # Determine channel from user preference or use specified
        if specified_channels:
            for channel in specified_channels:
                destinations.append({
                    "channel": channel,
                    "address": recipient,
                })
        else:
            # Use default email channel if no preference
            destinations.append({
                "channel": default_channel,
                "address": recipient,
            })
    
    # Add group destinations (will be resolved by API)
    for group_name in parsed.get("groups", []):
        # For groups, we need to send to the group
        # The API will resolve group members
        if specified_channels:
            for channel in specified_channels:
                destinations.append({
                    "channel": channel,
                    "address": f"group:{group_name}",
                })
        else:
            destinations.append({
                "channel": default_channel,
                "address": f"group:{group_name}",
            })
    
    # Build message payload
    payload = {
        "destinations": destinations,
        "content": parsed.get("content", [{"type": "text", "body": command}]),
        "options": {},
    }
    
    if parsed.get("subject"):
        payload["options"]["subject"] = parsed["subject"]
    
    # Send via API
    result = await _api_request("POST", "/messages", json_body=payload)
    return {
        "success": True,
        "message_id": result.get("message_id"),
        "parsed": parsed,
        "result": result,
    }


async def list_messages_tool(arguments: Dict[str, Any]) -> Dict:
    """List messages tool implementation — W28C-430R2: returns structuredContent."""
    offset = arguments.get("offset", 0)
    limit = arguments.get("limit", 100)
    status_filter = arguments.get("status")

    params = {"offset": offset, "limit": limit}
    if status_filter:
        params["status"] = status_filter

    api_result = await _api_request("GET", "/messages", params=params)
    # W28C-430R2: Wrap with structuredContent so strict MCP clients get typed data.
    return {
        "content": [{"type": "text", "text": json.dumps(api_result, default=str)}],
        "structuredContent": api_result,
    }


async def get_message_tool(arguments: Dict[str, Any]) -> Dict:
    """Get message tool implementation"""
    message_id = arguments.get("message_id")
    
    return await _api_request("GET", f"/messages/{message_id}", params={"format": "json"})


async def list_deliveries_tool(arguments: Dict[str, Any]) -> Dict:
    """List deliveries tool implementation"""
    message_id = arguments.get("message_id")
    offset = arguments.get("offset", 0)
    limit = arguments.get("limit", 50)
    
    return await _api_request(
        "GET",
        f"/messages/{message_id}/deliveries",
        params={"offset": offset, "limit": limit},
    )


async def resend_delivery_tool(arguments: Dict[str, Any]) -> Dict:
    """Resend delivery tool implementation"""
    delivery_id = arguments.get("delivery_id")
    
    return await _api_request("POST", f"/deliveries/{delivery_id}/resend")


async def abort_delivery_tool(arguments: Dict[str, Any]) -> Dict:
    """Abort delivery tool implementation"""
    delivery_id = arguments.get("delivery_id")
    
    return await _api_request("POST", f"/deliveries/{delivery_id}/abort")


async def get_status_tool(arguments: Dict[str, Any]) -> Dict:
    """Get system status tool implementation"""
    return await _api_request("GET", "/status")


async def admin_list_channels_tool(arguments: Dict[str, Any]) -> Dict:
    """List channels for admin parity."""
    return await list_channels_tool(arguments)


async def admin_create_channel_tool(arguments: Dict[str, Any]) -> Dict:
    """Create a channel via the admin MCP surface."""
    return await _api_request("POST", "/channels", json_body=arguments)


async def admin_update_channel_tool(arguments: Dict[str, Any]) -> Dict:
    """Update a channel via the admin MCP surface."""
    channel_id = arguments.get("channel_id")
    updates = arguments.get("updates") or {}
    return await _api_request("PATCH", f"/channels/{channel_id}", json_body=updates)


async def admin_delete_channel_tool(arguments: Dict[str, Any]) -> Dict:
    """Delete a channel via the admin MCP surface."""
    channel_id = arguments.get("channel_id")
    return await _api_request("DELETE", f"/channels/{channel_id}")


async def admin_list_users_tool(arguments: Dict[str, Any]) -> Dict:
    """List users for admin parity."""
    params = {}
    for key in ("q", "email", "limit"):
        value = arguments.get(key)
        if value is not None:
            params[key] = value
    return await _api_request("GET", "/users", params=params)


async def admin_create_user_tool(arguments: Dict[str, Any]) -> Dict:
    """Create a user via the admin MCP surface."""
    return await _api_request("POST", "/users", json_body=arguments)


async def admin_list_groups_tool(arguments: Dict[str, Any]) -> Dict:
    """List groups for admin parity."""
    return await _api_request("GET", "/groups")


async def admin_create_group_tool(arguments: Dict[str, Any]) -> Dict:
    """Create a group via the admin MCP surface."""
    return await _api_request("POST", "/groups", json_body=arguments)


async def admin_update_group_tool(arguments: Dict[str, Any]) -> Dict:
    """Update a group via the admin MCP surface."""
    group_id = arguments.get("group_id")
    updates = {k: v for k, v in arguments.items() if k != "group_id"}
    return await _api_request("PATCH", f"/groups/{group_id}", json_body=updates)


async def admin_add_group_member_tool(arguments: Dict[str, Any]) -> Dict:
    """Add a member to a group via the admin MCP surface."""
    group_id = arguments.get("group_id")
    user_id = arguments.get("user_id")
    role = arguments.get("role", "member")
    return await _api_request("POST", f"/groups/{group_id}/members", json_body={"user_id": user_id, "role": role})


async def admin_list_group_members_tool(arguments: Dict[str, Any]) -> Dict:
    """List members of a group via the admin MCP surface."""
    group_id = arguments.get("group_id")
    return await _api_request("GET", f"/groups/{group_id}/members")


async def admin_remove_group_member_tool(arguments: Dict[str, Any]) -> Dict:
    """Remove a member from a group via the admin MCP surface."""
    group_id = arguments.get("group_id")
    user_id = arguments.get("user_id")
    return await _api_request("DELETE", f"/groups/{group_id}/members/{user_id}")


async def admin_create_api_key_tool(arguments: Dict[str, Any]) -> Dict:
    """Generate an API key via the admin MCP surface."""
    return await _api_request("POST", "/admin/api-keys", json_body=arguments)


async def admin_revoke_api_key_tool(arguments: Dict[str, Any]) -> Dict:
    """Revoke an API key via the admin MCP surface."""
    key_id = arguments.get("key_id")
    return await _api_request("DELETE", f"/admin/api-keys/{key_id}")


async def main():
    """Main entry point for MCP server - supports both stdio and HTTP/SSE transport"""
    global config, logger, api_base_url, api_key
    
    # Load configuration
    config = get_config()

    # Get transport type before logger setup so stdio stays a clean JSON-RPC stream.
    transport = _require_config(config.get("mcp_server.transport"), "mcp_server.transport").lower()
    console_logging = bool(_require_config(config.get("log.console"), "log.console"))
    if transport not in ("sse", "http", "legacy_sse", "streamable_http", "http_jsonrpc", "http_jsonrpc_async"):
        console_logging = False
    
    # Setup logger
    logger = setup_logger(
        name="mcp_server",
        log_file=_require_config(config.get("log.mcp_server_log"), "log.mcp_server_log"),
        log_level=_require_config(config.get("log.level"), "log.level"),
        log_format=_require_config(config.get("log.format"), "log.format"),
        console=console_logging,
    )
    
    logger.info(f"Starting MCP server with {transport} transport...")
    
    # Get API configuration
    api_base_url = _require_config(config.get("mcp_server.api_base_url"), "mcp_server.api_base_url")
    api_key = _require_config(config.get("mcp_server.api_key"), "mcp_server.api_key")
    
    logger.info(f"MCP server connected to API: {api_base_url}")
    
    if transport in ("sse", "http", "legacy_sse", "streamable_http", "http_jsonrpc", "http_jsonrpc_async"):
        # Use HTTP-based transport (blocking, so we can't use async here)
        # This will be handled by start_mcp_server.py instead
        logger.warning("HTTP-based MCP transports should be started via start_mcp_server.py, not async main()")
        raise RuntimeError("HTTP-based MCP transports must be started via start_mcp_server.py (blocking mode)")
    else:
        # Default to stdio transport
        logger.info("Using stdio transport")
        async with stdio_server() as (read_stream, write_stream):
            await mcp_app.run(
                read_stream,
                write_stream,
                mcp_app.create_initialization_options(),
            )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
