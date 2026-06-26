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

"""Notification-agent MCP HTTP transport glue built on cloud_dog_api_kit."""

from __future__ import annotations

from datetime import datetime
import inspect
from typing import Any, Optional

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from cloud_dog_api_kit import create_app as platform_create_app
from cloud_dog_api_kit.clients import ClientTimeout, create_http_client
from cloud_dog_api_kit.mcp import InMemoryAsyncJobStore, LegacySSEConfig, register_mcp_routes, register_tool_router
from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

from ...config import get_config
from ...utils.logger import PlatformContextMiddleware, setup_logger
from .send_notification_contract import (
    SEND_NOTIFICATION_INPUT_SCHEMA,
    SEND_NOTIFICATION_OUTPUT_SCHEMA,
    execute_send_notification,
    resolve_duplicate_notification_from_db,
)

_fs = _PlatformLocalStorage(root_path="/")


def _require_config(value: Any, key: str) -> Any:
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _normalise_path(raw_path: Any, *, default: str) -> str:
    value = str(raw_path or "").strip() or default
    if not value.startswith("/"):
        value = f"/{value}"
    if value != "/":
        value = value.rstrip("/")
    return value or "/"


def _create_platform_app(**kwargs: Any) -> FastAPI:
    try:
        signature = inspect.signature(platform_create_app)
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return platform_create_app(**kwargs)
        return platform_create_app(
            **{key: value for key, value in kwargs.items() if key in signature.parameters}
        )
    except (TypeError, ValueError):
        return platform_create_app(**kwargs)


class _PlatformMCPServer:
    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        logger: Optional[Any] = None,
        transport_mode: Optional[str] = None,
    ) -> None:
        self.config = config or get_config()
        self.logger = logger or setup_logger(
            name="mcp_server_http",
            log_file=_require_config(self.config.get("log.mcp_server_log"), "log.mcp_server_log"),
            log_level=_require_config(self.config.get("log.level"), "log.level"),
            log_format=_require_config(self.config.get("log.format"), "log.format"),
            console=_require_config(self.config.get("log.console"), "log.console"),
        )

        self.transport_mode = (
            transport_mode
            or _require_config(self.config.get("mcp_server.transport"), "mcp_server.transport")
        ).lower()
        self.host = _require_config(self.config.get("mcp_server.host"), "mcp_server.host")
        self.port = _require_config(self.config.get("mcp_server.port"), "mcp_server.port")
        self.tls_enabled = _require_config(self.config.get("mcp_server.tls"), "mcp_server.tls")
        if self.tls_enabled:
            self.ssl_certfile = _require_config(self.config.get("app.certificate"), "app.certificate")
            self.ssl_keyfile = _require_config(self.config.get("app.key"), "app.key")
        else:
            self.ssl_certfile = None
            self.ssl_keyfile = None

        self.api_base_url = _require_config(self.config.get("mcp_server.api_base_url"), "mcp_server.api_base_url")
        self.api_key = _require_config(self.config.get("mcp_server.api_key"), "mcp_server.api_key")
        self.api_timeout = _require_config(self.config.get("mcp_server.request_timeout"), "mcp_server.request_timeout")
        self.protocol_version = self.config.get("mcp_server.protocol_version") or "2024-11-05"
        self.client_api_key = str(self.config.get("mcp_server.client_api_key") or "")
        self.streamable_http_path = _normalise_path(
            self.config.get("mcp_server.streamable_http_path"),
            default="/mcp",
        )
        self.jsonrpc_path = _normalise_path(
            self.config.get("mcp_server.jsonrpc_path"),
            default="/messages",
        )
        self.legacy_sse_path = _normalise_path(
            self.config.get("mcp_server.legacy_sse_path"),
            default="/sse",
        )
        self.legacy_sse_message_path = _normalise_path(
            self.config.get("mcp_server.legacy_sse_message_path"),
            default="/message",
        )
        self.async_jobs_enabled = bool(self.config.get("mcp_server.async_jobs_enabled")) or (
            self.transport_mode == "http_jsonrpc_async"
        )
        self.async_jobs_status_path = _normalise_path(
            self.config.get("mcp_server.async_jobs_status_path"),
            default="/jobs/{job_id}",
        )
        self.base_path = str(self.config.get("mcp_server.base_path") or "")

        timeout_value = float(self.api_timeout)
        self.http_client = create_http_client(
            base_url=self.api_base_url,
            timeout=ClientTimeout(connect=min(5.0, timeout_value), read=timeout_value, total=timeout_value),
            api_key=self.api_key or None,
        )
        self.app = self._build_app()

    def _tool_registry(self) -> dict[str, dict[str, Any]]:
        return {
            "send_notification": {
                "handler": self._tool_send_notification,
                "description": "Send a notification to one or more destinations",
                "input_schema": SEND_NOTIFICATION_INPUT_SCHEMA,
                "output_schema": SEND_NOTIFICATION_OUTPUT_SCHEMA,
            },
            "get_message_status": {
                "handler": self._tool_get_message_status,
                "description": "Get the status of a notification message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "integer", "description": "Message ID to query"},
                    },
                    "required": ["message_id"],
                },
            },
            "list_channels": {
                "handler": self._tool_list_channels,
                "description": "List all available notification channels",
                "input_schema": {"type": "object", "properties": {}},
            },
            "cancel_message": {
                "handler": self._tool_cancel_message,
                "description": "Cancel a pending notification message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "integer", "description": "Message ID to cancel"},
                    },
                    "required": ["message_id"],
                },
            },
            "send_notification_natural": {
                "handler": self._tool_send_notification_natural,
                "description": "Send a notification using natural language",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Natural language command"},
                        "channels": {
                            "type": "array",
                            "description": "Optional explicit channels",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["command"],
                },
            },
            "list_messages": {
                "handler": self._tool_list_messages,
                "description": "List recent messages with optional filtering",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "offset": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 100},
                        "status": {"type": "string"},
                    },
                },
            },
            "get_message": {
                "handler": self._tool_get_message,
                "description": "Get detailed information about a specific message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": ["integer", "string"],
                            "description": "Message ID (numeric) or GUID",
                        },
                    },
                    "required": ["message_id"],
                },
            },
            "list_deliveries": {
                "handler": self._tool_list_deliveries,
                "description": "List deliveries for a specific message",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": ["integer", "string"],
                            "description": "Message ID (numeric) or GUID",
                        },
                        "offset": {"type": "integer", "default": 0},
                        "limit": {"type": "integer", "default": 50},
                    },
                    "required": ["message_id"],
                },
            },
            "resend_delivery": {
                "handler": self._tool_resend_delivery,
                "description": "Resend a failed or cancelled delivery",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "delivery_id": {"type": "integer", "description": "Delivery ID to resend"},
                    },
                    "required": ["delivery_id"],
                },
            },
            "abort_delivery": {
                "handler": self._tool_abort_delivery,
                "description": "Abort a pending delivery immediately",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "delivery_id": {"type": "integer", "description": "Delivery ID to abort"},
                    },
                    "required": ["delivery_id"],
                },
            },
            "get_status": {
                "handler": self._tool_get_status,
                "description": "Get system status and metrics",
                "input_schema": {"type": "object", "properties": {}},
            },
            # W28D-440A: Admin group/channel/user tools for DEMO-027
            **self._admin_tool_entries(),
        }

    def _admin_tool_entries(self) -> dict[str, dict[str, Any]]:
        """Generate admin tool registry entries with name-injecting handlers."""
        defs: dict[str, tuple[str, dict[str, Any]]] = {
            "admin_list_channels": ("List channel definitions", {"type": "object", "properties": {}}),
            "admin_create_channel": ("Create a channel definition", {"type": "object", "properties": {"name": {"type": "string"}, "type": {"type": "string"}, "enabled": {"type": "boolean"}}, "required": ["name", "type"]}),
            "admin_update_channel": ("Update an existing channel", {"type": "object", "properties": {"channel_id": {"type": "integer"}, "updates": {"type": "object"}}, "required": ["channel_id"]}),
            "admin_delete_channel": ("Delete a channel", {"type": "object", "properties": {"channel_id": {"type": "integer"}}, "required": ["channel_id"]}),
            "admin_list_users": ("List users", {"type": "object", "properties": {"q": {"type": "string"}, "limit": {"type": "integer"}}}),
            "admin_create_user": ("Create a user", {"type": "object", "properties": {"username": {"type": "string"}, "email": {"type": "string"}, "role": {"type": "string"}}, "required": ["email"]}),
            "admin_list_groups": ("List groups", {"type": "object", "properties": {}}),
            "admin_create_group": ("Create a group", {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}}, "required": ["name"]}),
            "admin_update_group": ("Update a group", {"type": "object", "properties": {"group_id": {"type": "integer"}, "description": {"type": "string"}, "enabled": {"type": "boolean"}}, "required": ["group_id"]}),
            "admin_add_group_member": ("Add a user to a group", {"type": "object", "properties": {"group_id": {"type": "integer"}, "user_id": {"type": "integer"}, "role": {"type": "string"}}, "required": ["group_id", "user_id"]}),
            "admin_list_group_members": ("List group members", {"type": "object", "properties": {"group_id": {"type": "integer"}}, "required": ["group_id"]}),
            "admin_remove_group_member": ("Remove a user from a group", {"type": "object", "properties": {"group_id": {"type": "integer"}, "user_id": {"type": "integer"}}, "required": ["group_id", "user_id"]}),
        }
        entries: dict[str, dict[str, Any]] = {}
        for name, (desc, schema) in defs.items():
            # Bind name into a closure so the handler knows which tool was called
            def _make_handler(tool_name: str):
                async def _handler(payload: dict[str, Any], _request: Any = None, _context: Any = None) -> dict[str, Any]:
                    payload["__tool_name__"] = tool_name
                    return await self._tool_admin_api(payload, _request=_request, _context=_context)
                return _handler
            entries[name] = {"handler": _make_handler(name), "description": desc, "input_schema": schema}
        return entries

    def _platform_transport_modes(self) -> set[str]:
        modes = {"http_jsonrpc"}
        if self.transport_mode == "streamable_http":
            modes.add("streamable_http")
            modes.add("legacy_sse")
        elif self.transport_mode in ("legacy_sse", "http", "sse"):
            modes.add("legacy_sse")
        return modes

    def _legacy_sse_config(self) -> LegacySSEConfig | None:
        if self.transport_mode not in ("streamable_http", "legacy_sse", "http", "sse"):
            return None
        return LegacySSEConfig(
            sse_path=self.legacy_sse_path,
            message_path=self.legacy_sse_message_path,
            session_header="Mcp-Session-Id",
        )

    def _async_job_store(self) -> InMemoryAsyncJobStore | None:
        if not self.async_jobs_enabled:
            return None
        return InMemoryAsyncJobStore()

    def _requires_auth(self, path: str) -> bool:
        if path == "/health":
            return False
        if path in {
            self.streamable_http_path,
            self.jsonrpc_path,
            self.legacy_sse_path,
            self.legacy_sse_message_path,
            f"{self.streamable_http_path}/tools",
        }:
            return True
        if path.startswith(f"{self.streamable_http_path}/tools/"):
            return True
        if self.async_jobs_enabled:
            async_prefix = self.async_jobs_status_path.split("{job_id}", 1)[0]
            if async_prefix and path.startswith(async_prefix):
                return True
        return False

    def _authorised(self, request: Request) -> bool:
        if not self.client_api_key:
            return True
        header_key = request.headers.get("X-API-Key")
        bearer = request.headers.get("Authorization", "")
        if header_key == self.client_api_key:
            return True
        if bearer.startswith("Bearer ") and bearer.split(" ", 1)[1] == self.client_api_key:
            return True
        return False

    def _build_app(self) -> FastAPI:
        app = _create_platform_app(
            title=str(self.config.get("mcp_server.name") or "notification-agent-mcp"),
            version=str(self.config.get("app.version") or "1.0"),
            enable_health=False,
            enable_docs=True,
            register_signal_handlers_on_startup=False,
        )
        app.add_middleware(PlatformContextMiddleware, logger_name="mcp_server")

        @app.middleware("http")
        async def _mcp_auth_middleware(request: Request, call_next):
            if self._requires_auth(request.url.path) and not self._authorised(request):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return await call_next(request)

        @app.get("/health")
        async def _health_check() -> JSONResponse:
            api_healthy = False
            try:
                response = await self.http_client.get("/health", timeout=5)
                api_healthy = response.status_code == 200
            except Exception as exc:
                self.logger.warning(f"API server health check failed: {exc}")
            app_name = self.config.get("app.title") or self.config.get("app.server_name")
            env_file = self.config.get("app.env_file")
            return JSONResponse(
                {
                    "app": app_name or "notification-agent-mcp-server",
                    "server": "mcp",
                    "env_file": env_file or "",
                    "status": "healthy" if api_healthy else "degraded",
                    "transport": self.transport_mode,
                    "port": self.port,
                    "api_server": self.api_base_url,
                    "api_server_healthy": api_healthy,
                    "endpoints": {
                        "streamable_http": self.streamable_http_path,
                        "jsonrpc": self.jsonrpc_path,
                        "legacy_sse": self.legacy_sse_path if self._legacy_sse_config() else None,
                        "legacy_sse_message": self.legacy_sse_message_path if self._legacy_sse_config() else None,
                        "async_jobs": self.async_jobs_status_path if self.async_jobs_enabled else None,
                        "tools": f"{self.streamable_http_path}/tools",
                        "health": "/health",
                    },
                    "timestamp": datetime.now().isoformat(),
                }
            )

        tools = self._tool_registry()
        register_tool_router(app, tools, base_path=f"{self.streamable_http_path}/tools")
        register_mcp_routes(
            app,
            tools,
            transport_modes=self._platform_transport_modes(),
            async_job_store=self._async_job_store(),
            async_job_status_path=self.async_jobs_status_path if self.async_jobs_enabled else None,
            legacy_sse=self._legacy_sse_config(),
            error_response_mode="jsonrpc_200",
            transport_base_path=self.streamable_http_path,
            transport_messages_path=self.jsonrpc_path,
            capabilities_override={"tools": {}},
        )
        app.add_event_handler("shutdown", self.close)
        return app

    async def _tool_send_notification(self, payload: dict[str, Any]) -> dict[str, Any]:
        async def _post_message(api_payload: dict[str, Any]) -> dict[str, Any]:
            response = await self.http_client.post("/messages", json=api_payload, timeout=self.api_timeout)
            if response.status_code >= 400:
                raise RuntimeError(f"POST /messages failed {response.status_code}: {response.text[:1000]}")
            return response.json()

        async def _get_deliveries(message_id: int) -> Any:
            response = await self.http_client.get(
                f"/messages/{message_id}/deliveries",
                params={"offset": 0, "limit": 1000},
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return response.json()

        def _resolve_duplicate(idempotency_key: str) -> dict[str, Any] | None:
            return resolve_duplicate_notification_from_db(self.config, idempotency_key)

        return await execute_send_notification(
            payload,
            post_message=_post_message,
            get_deliveries=_get_deliveries,
            resolve_duplicate=_resolve_duplicate,
        )

    async def _tool_send_notification_natural(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from ...database import get_db_manager
            from ...core.resolvers.natural_language_parser import NaturalLanguageParser

            command = str(payload.get("command") or payload.get("instruction") or "").strip()
            channels = payload.get("channels") or []
            db_uri = _require_config(self.config.get("db.uri"), "db.uri")
            db = get_db_manager(db_uri)
            db.connect()
            parser = NaturalLanguageParser(db)
            parsed = parser.parse(command)

            default_channel = _require_config(self.config.get("default_channel"), "default_channel")
            destinations: list[dict[str, str]] = []
            for recipient in parsed.get("recipients", []):
                if channels:
                    for channel in channels:
                        destinations.append({"channel": channel, "address": recipient})
                else:
                    destinations.append({"channel": default_channel, "address": recipient})

            for group_name in parsed.get("groups", []):
                if channels:
                    for channel in channels:
                        destinations.append({"channel": channel, "address": f"group:{group_name}"})
                else:
                    destinations.append({"channel": default_channel, "address": f"group:{group_name}"})

            api_payload: dict[str, Any] = {
                "destinations": destinations,
                "content": parsed.get("content", [{"type": "text", "body": command}]),
                "options": {},
            }
            if parsed.get("subject"):
                api_payload["options"]["subject"] = parsed["subject"]

            response = await self.http_client.post("/messages", json=api_payload, timeout=self.api_timeout)
            response.raise_for_status()
            result = response.json()
            return {
                "success": True,
                "message_id": result.get("message_id"),
                "parsed": parsed,
                "result": result,
                "status": result.get("status", "queued"),
            }
        except Exception as exc:
            self.logger.error(f"Error in send_notification_natural tool: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    async def _tool_get_message_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            message_id = payload.get("message_id")
            response = await self.http_client.get(
                f"/messages/{message_id}",
                params={"format": "json"},
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            result = response.json()
            return {
                "message_id": message_id,
                "status": result.get("status", "unknown"),
                "created_at": result.get("created_at"),
                "deliveries": result.get("deliveries", []),
            }
        except Exception as exc:
            self.logger.error(f"Error in get_message_status tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_list_channels(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        del payload
        try:
            response = await self.http_client.get("/channels", timeout=self.api_timeout)
            response.raise_for_status()
            channels = response.json()
            return channels if isinstance(channels, list) else []
        except Exception as exc:
            self.logger.error(f"Error in list_channels tool: {exc}", exc_info=True)
            return []

    async def _tool_cancel_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            message_id = payload.get("message_id")
            response = await self.http_client.post(
                f"/messages/{message_id}/cancel",
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            result = response.json()
            return {"success": True, "message_id": message_id, "status": result.get("status", "cancelled")}
        except Exception as exc:
            self.logger.error(f"Error in cancel_message tool: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    async def _tool_list_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            params = {
                "offset": payload.get("offset", 0),
                "limit": payload.get("limit", 100),
            }
            if payload.get("status"):
                params["status"] = payload["status"]
            response = await self.http_client.get("/messages", params=params, timeout=self.api_timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in list_messages tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_get_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            message_id = payload.get("message_id")
            response = await self.http_client.get(
                f"/messages/{message_id}",
                params={"format": "json"},
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in get_message tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_list_deliveries(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            message_id = payload.get("message_id")
            response = await self.http_client.get(
                f"/messages/{message_id}/deliveries",
                params={"offset": payload.get("offset", 0), "limit": payload.get("limit", 50)},
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in list_deliveries tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_resend_delivery(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            delivery_id = payload.get("delivery_id")
            response = await self.http_client.post(
                f"/deliveries/{delivery_id}/resend",
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in resend_delivery tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_abort_delivery(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            delivery_id = payload.get("delivery_id")
            response = await self.http_client.post(
                f"/deliveries/{delivery_id}/abort",
                timeout=self.api_timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in abort_delivery tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def _tool_get_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        del payload
        try:
            response = await self.http_client.get("/status", timeout=self.api_timeout)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in get_status tool: {exc}", exc_info=True)
            return {"error": str(exc)}

    # W28D-440A: Generic admin tool dispatcher — routes to REST based on tool name
    _ADMIN_TOOL_ROUTES: dict[str, tuple[str, str]] = {
        "admin_list_channels": ("GET", "/channels"),
        "admin_create_channel": ("POST", "/channels"),
        "admin_update_channel": ("PATCH", "/channels/{channel_id}"),
        "admin_delete_channel": ("DELETE", "/channels/{channel_id}"),
        "admin_list_users": ("GET", "/users"),
        "admin_create_user": ("POST", "/users"),
        "admin_list_groups": ("GET", "/groups"),
        "admin_create_group": ("POST", "/groups"),
        "admin_update_group": ("PATCH", "/groups/{group_id}"),
        "admin_add_group_member": ("POST", "/groups/{group_id}/members"),
        "admin_list_group_members": ("GET", "/groups/{group_id}/members"),
        "admin_remove_group_member": ("DELETE", "/groups/{group_id}/members/{user_id}"),
    }

    async def _tool_admin_api(self, payload: dict[str, Any], _request: Any = None, _context: Any = None) -> dict[str, Any]:
        """Generic admin tool handler — dispatches to REST by tool name."""
        import inspect
        # PS-70 UM3 RBAC: verify caller has admin permission for admin tools
        if _request is not None:
            user = getattr(getattr(_request, "state", None), "user", None)
            if user is not None:
                uid = str(getattr(user, "user_id", ""))
                if uid and uid not in {"notification-api", "bootstrap-admin", "api-runtime"}:
                    from ...core.idam.runtime import get_idam_runtime
                    rt = get_idam_runtime()
                    if not rt.rbac_engine.has_permission(uid, "*"):
                        return {"error": "Admin access required", "status": 403}
        # Determine which tool called us by inspecting the caller context
        tool_name = payload.pop("__tool_name__", None)
        if not tool_name:
            # Fallback: tool_name should be injected by the dispatch layer
            return {"error": "Admin tool dispatch requires __tool_name__"}

        route = self._ADMIN_TOOL_ROUTES.get(tool_name)
        if not route:
            return {"error": f"Unknown admin tool: {tool_name}"}

        method, path_template = route
        # Substitute path parameters from payload
        path = path_template
        for key in ("channel_id", "group_id", "user_id"):
            if f"{{{key}}}" in path:
                val = payload.pop(key, None)
                if val is None:
                    return {"error": f"Missing required parameter: {key}"}
                path = path.replace(f"{{{key}}}", str(val))

        # Remaining payload is the body for POST/PATCH or params for GET
        try:
            if method == "GET":
                response = await self.http_client.get(path, params=payload or None, timeout=self.api_timeout)
            elif method == "POST":
                response = await self.http_client.post(path, json=payload or None, timeout=self.api_timeout)
            elif method == "PATCH":
                body = payload.pop("updates", payload) if "updates" in payload else payload
                response = await self.http_client.patch(path, json=body or None, timeout=self.api_timeout)
            elif method == "DELETE":
                response = await self.http_client.delete(path, timeout=self.api_timeout)
            else:
                return {"error": f"Unsupported method: {method}"}
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.error(f"Error in admin tool {tool_name}: {exc}", exc_info=True)
            return {"error": str(exc)}

    async def close(self) -> None:
        if getattr(self, "http_client", None) is not None:
            await self.http_client.aclose()

    def run(self) -> None:
        protocol = "https" if self.tls_enabled else "http"
        self.logger.info("=" * 80)
        self.logger.info(f"Starting MCP Server with transport: {self.transport_mode}")
        self.logger.info(f"Host: {self.host}")
        self.logger.info(f"Port: {self.port}")
        self.logger.info(f"TLS/SSL: {'enabled' if self.tls_enabled else 'disabled'}")
        self.logger.info(f"API Server: {self.api_base_url}")
        self.logger.info(f"Streamable HTTP endpoint: {protocol}://{self.host}:{self.port}{self.streamable_http_path}")
        self.logger.info(f"JSON-RPC endpoint: {protocol}://{self.host}:{self.port}{self.jsonrpc_path}")
        if self._legacy_sse_config():
            self.logger.info(f"Legacy SSE endpoint: {protocol}://{self.host}:{self.port}{self.legacy_sse_path}")
            self.logger.info(
                f"Legacy message endpoint: {protocol}://{self.host}:{self.port}{self.legacy_sse_message_path}"
            )
        if self.async_jobs_enabled:
            self.logger.info(f"Async jobs endpoint: {protocol}://{self.host}:{self.port}{self.async_jobs_status_path}")
        self.logger.info(f"Tools endpoint: {protocol}://{self.host}:{self.port}{self.streamable_http_path}/tools")
        self.logger.info(f"Health endpoint: {protocol}://{self.host}:{self.port}/health")
        self.logger.info("=" * 80)

        try:
            if self.tls_enabled:
                if _fs.stat(self.ssl_certfile) is None:
                    raise FileNotFoundError(f"SSL certificate not found: {self.ssl_certfile}")
                if _fs.stat(self.ssl_keyfile) is None:
                    raise FileNotFoundError(f"SSL key not found: {self.ssl_keyfile}")
            import uvicorn

            kwargs = {
                "app": self.app,
                "host": self.host,
                "port": self.port,
                "root_path": self.base_path,
                "log_level": str(self.config.get("log.level", "info")).lower(),
            }
            if self.tls_enabled:
                kwargs["ssl_keyfile"] = self.ssl_keyfile
                kwargs["ssl_certfile"] = self.ssl_certfile
            getattr(uvicorn, "run")(**kwargs)
        except Exception as exc:
            self.logger.error(f"MCP HTTP server error: {exc}", exc_info=True)
            raise

    def start(self) -> None:
        self.run()


class MCPServerHTTP(_PlatformMCPServer):
    def __init__(self, config: Optional[dict[str, Any]] = None, logger: Optional[Any] = None) -> None:
        super().__init__(config=config, logger=logger, transport_mode="legacy_sse")


class MCPServerJSONRPC(_PlatformMCPServer):
    pass
