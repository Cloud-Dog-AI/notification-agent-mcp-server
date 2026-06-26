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
Description: REST API Server for Notification Agent MCP Server - Provides REST endpoints for message submission, channel management, and monitoring

Related Requirements: FR1.4, FR1.5, UC1.1
Related Tasks: T9
Related Architecture: CC1.1, AI1.1
Related Tests: IT1.1, ST1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import json
import asyncio
import re
import time
import inspect
import psutil  # W28A-569: unconditional — psutil is a hard requirement for resource metrics
from dataclasses import asdict, is_dataclass
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from httpx import AsyncClient as SharedAsyncHTTPClient, Timeout as HTTPTimeout
from fastapi import HTTPException, Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi import Request
from pydantic import BaseModel, Field
from cloud_dog_cache import create_cache_router, init_cache_from_config, invalidate_event

from ...config import get_config
from ...database import get_db_manager, ChannelRepository
from ...core import JobManager
from ...core.idam.runtime import get_idam_runtime, require_authenticated_request
from ...adapters import get_adapter_registry
from ...utils.logger import PlatformContextMiddleware, setup_logger, get_logger, get_context_logger
from .routes.callbacks import router as callback_router
from .routes.users import router as users_router
from .routes.groups import router as groups_router
from cloud_dog_logging.middleware.fastapi import LoggingMiddleware
from cloud_dog_api_kit import create_app as platform_create_app, create_health_router
from cloud_dog_api_kit.lifecycle.hooks import LifecycleHooks
from cloud_dog_api_kit.middleware.timeout import TimeoutMiddleware
from cloud_dog_jobs.domain.enums import JobStatus


# Global instances
_temp_cfg = get_config(unresolved_policy="empty")
_API_KEY_RUNTIME_STARTED_AT = datetime.now(timezone.utc).isoformat()
_API_KEY_FIRST_SEEN_AT: dict[str, str] = {}


def _normalise_base_path(value: Any, *, default: str) -> str:
    """Return a normalised leading-slash base path."""
    text = str(value if value not in (None, "") else default).strip()
    if not text:
        return ""
    if not text.startswith("/"):
        text = f"/{text}"
    if text != "/":
        text = text.rstrip("/")
    return "" if text == "/" else text


_api_base_path = _normalise_base_path(
    _temp_cfg.get("api_server.base_path"),
    default="/api/v1",
)
_cors_origins = _temp_cfg.get("api_server.cors_origins", ["http://localhost", "http://127.0.0.1"])
_lifecycle_hooks = LifecycleHooks()
_app_kwargs = {
    "title": "Notification Agent MCP Server API",
    "version": "0.1.0",
    "description": "Multi-channel notification platform REST API",
    "base_path": _api_base_path,
    "enable_cors": True,
    "cors_origins": _cors_origins if isinstance(_cors_origins, list) else ["http://localhost", "http://127.0.0.1"],
    "enable_health": False,
    "enable_docs": True,
    "register_signal_handlers_on_startup": False,
    "lifecycle_hooks": _lifecycle_hooks,
}
try:
    _create_app_sig = inspect.signature(platform_create_app)
    if any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in _create_app_sig.parameters.values()
    ):
        app = platform_create_app(**_app_kwargs)
    else:
        _supported_kwargs = {
            key: value
            for key, value in _app_kwargs.items()
            if key in _create_app_sig.parameters
        }
        app = platform_create_app(**_supported_kwargs)
except (TypeError, ValueError):
    app = platform_create_app(**_app_kwargs)

# Replace default health routes with platform create_health_router() carrying
# project-specific probes for database and channel health.
_probe_paths = {"/health", "/ready", "/live"}  # W28A-569: /status excluded — custom handler has psutil metrics
app.router.routes = [
    route for route in app.router.routes
    if getattr(route, "path", None) not in _probe_paths
]


# Bootstrap globals used during module import and replaced during startup().
config = _temp_cfg
api_http_timeout = float(config.get("api_server.http_client_timeout", 10) or 10)
api_db_timeout = float(config.get("api_server.db_query_timeout", 5) or 5)
api_db_timeout_short = float(config.get("api_server.db_query_timeout_short", 3) or 3)
api_subprocess_timeout = int(config.get("api_server.subprocess_timeout", 600) or 600)
db = None
llm_formatter = None
job_manager = None
adapter_registry = None
channel_repo = None
logger = None
# Shared long-lived HTTP client for API-to-worker/A2A calls (W28A-93b, AGENT-LESSONS §2.3)
_api_http_client: SharedAsyncHTTPClient | None = None


def _config_truthy(value: Any, default: bool = True) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _runtime_config(*, force_reload: bool = False):
    """Return the active runtime config without relying on removed env bootstrap globals."""
    global config
    if config is not None and not force_reload:
        return config
    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        force_reload=force_reload,
        unresolved_policy="empty",
    )
    return config


async def _db_health_check() -> dict:
    db_healthy = db.health_check() if db else False
    result: dict = {"status": "ok" if db_healthy else "error"}
    if db_healthy and db:
        try:
            result["dialect"] = db.get_dialect() or ""
        except Exception:
            pass
    return result


async def _channel_health_check() -> dict:
    if not channel_repo:
        return {"status": "ok", "channels": {}}
    channels = channel_repo.list_all(enabled_only=True)
    channels_status = {}
    for channel in channels:
        channels_status[channel["name"]] = {
            "type": channel["type"],
            "circuit_state": channel["circuit_state"],
            "error_count": channel["error_count"],
        }
    return {"status": "ok", "channels": channels_status}


def _delivery_worker_base_url() -> str:
    current_cfg = config or _temp_cfg
    explicit = str(current_cfg.get("delivery_worker.base_url") or "").strip()
    if explicit:
        return explicit.rstrip("/")

    host = str(current_cfg.get("delivery_worker.host") or "127.0.0.1").strip()
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    port = current_cfg.get("delivery_worker.port")
    if port in (None, ""):
        port = 8024
    return f"http://{host}:{port}"


def _estimate_queue_wait_seconds(queue_length: int) -> int:
    current_cfg = config or _temp_cfg
    max_concurrent = max(1, int(current_cfg.get("llm.max_concurrent", 3) or 3))
    avg_request_duration = float(current_cfg.get("llm.avg_request_duration", 60.0) or 60.0)
    if queue_length <= 0:
        return 0
    return max(1, int((queue_length * avg_request_duration) / max_concurrent))


def _pending_delivery_backlog() -> int:
    if db is None:
        return 0
    try:
        from ...database.repositories import DeliveryRepository

        return DeliveryRepository(db).count_pending_backlog()
    except Exception:
        return 0


def _delivery_queue_gate(requested_deliveries: int) -> Dict[str, Any]:
    current_cfg = config or _temp_cfg
    limit_raw = current_cfg.get("delivery.max_queued", 1000)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 1000

    requested = max(0, int(requested_deliveries))
    current_backlog = _pending_delivery_backlog()
    projected_backlog = current_backlog + requested
    if limit <= 0:
        return {
            "enabled": False,
            "limit": limit,
            "current_backlog": current_backlog,
            "projected_backlog": projected_backlog,
            "warning": False,
            "saturated": False,
            "retry_after_seconds": 0,
        }

    warning_threshold = max(1, int((limit * 0.8) + 0.9999))
    retry_after_seconds = max(5, _estimate_queue_wait_seconds(projected_backlog))
    return {
        "enabled": True,
        "limit": limit,
        "current_backlog": current_backlog,
        "projected_backlog": projected_backlog,
        "warning": projected_backlog >= warning_threshold,
        "saturated": projected_backlog > limit,
        "retry_after_seconds": retry_after_seconds,
    }


def _fallback_llm_status(*, connection_status: str = "worker_unavailable") -> Dict[str, Any]:
    current_cfg = config or _temp_cfg
    queue_length = _pending_delivery_backlog()
    max_concurrent = max(1, int(current_cfg.get("llm.max_concurrent", 3) or 3))
    avg_request_duration = float(current_cfg.get("llm.avg_request_duration", 60.0) or 60.0)
    estimated_wait_seconds = _estimate_queue_wait_seconds(queue_length)
    return {
        "available": queue_length == 0,
        "active_requests": 0,
        "max_concurrent": max_concurrent,
        "queue_length": queue_length,
        "estimated_wait_seconds": estimated_wait_seconds if queue_length > 0 else 0,
        "connection_status": connection_status,
        "avg_request_duration": avg_request_duration,
    }


async def _get_effective_llm_status() -> Dict[str, Any]:
    current_cfg = config or _temp_cfg
    if not _config_truthy(current_cfg.get("delivery_worker.enabled", True), True):
        return _fallback_llm_status(connection_status="disabled")

    try:
        global _api_http_client
        if _api_http_client is None or _api_http_client.is_closed:
            _api_http_client = SharedAsyncHTTPClient(
                timeout=HTTPTimeout(timeout=2.0, connect=1.0, read=2.0),
                trust_env=False,
            )
        response = await _api_http_client.get(f"{_delivery_worker_base_url()}/worker/llm/status")
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
        if logger:
            logger.warning(
                "Delivery worker status endpoint returned non-200: %s %s",
                response.status_code,
                response.text[:200],
            )
    except Exception as exc:
        if logger:
            logger.debug(f"Delivery worker status proxy unavailable: {exc}")
    return _fallback_llm_status()


_health_env_file = ""
if config:
    _health_env_file = str(config.get("app.env_file") or "")
_health_router = create_health_router(
    application_name="notification-agent-mcp-server",
    version="0.1.0",
    env_file=_health_env_file,
    checks={"database": _db_health_check, "channels": _channel_health_check},
)
# W28A-569: Remove /status from health router — custom get_status() has psutil metrics
_health_router.routes = [r for r in _health_router.routes if getattr(r, "path", None) != "/status"]
app.include_router(_health_router)
app.include_router(_health_router, prefix=_api_base_path)

# Override platform-api-kit default 30s timeout for long-running endpoints
# (for example full-message translation/view rendering).
_request_timeout = float(_temp_cfg.get("api_server.request_timeout") or 300)
for _middleware in app.user_middleware:
    if getattr(_middleware, "cls", None) is TimeoutMiddleware:
        _middleware.kwargs["timeout_seconds"] = _request_timeout
        break

# Package middleware handles request correlation and request/response logging.
# Use the API logger namespace so request-scoped middleware logs flow through
# the same configured handlers/log files as the rest of the API server.
app.add_middleware(LoggingMiddleware, logger=get_logger("api_server"))
app.add_middleware(PlatformContextMiddleware, logger_name="api_server")
idam_runtime = get_idam_runtime()
_bootstrap_api_key = str(
    _temp_cfg.get("api_server.api_key")
    or ""
).strip()
if _bootstrap_api_key:
    # Seed early so middleware sees a valid key during initial request handling.
    idam_runtime.seed_api_key(str(_bootstrap_api_key), owner_user_id="notification-api")
# Seed the E2E test key so Playwright can call the API directly.
_e2e_test_key = _temp_cfg.get("runtime.a2a_test_api_key") or "st-local-secret"
idam_runtime.seed_api_key(str(_e2e_test_key), owner_user_id="notification-api")
_auth_skip_paths = {
    "/health",
    "/ready",
    "/live",
    "/docs",
    "/openapi.json",
    "/",
}
if _api_base_path:
    for suffix in ("/health", "/ready", "/live"):
        _auth_skip_paths.add(f"{_api_base_path}{suffix}")
idam_runtime.install_auth_middleware(
    app,
    auth_scheme="api_key",
    skip_paths=_auth_skip_paths,
)

# Storage and message-view links are emitted for end-users without headers.
# Inject the bootstrap API key for safe read-only link paths so auth middleware
# can resolve request.state.user while keeping CRUD routes protected.
@app.middleware("http")
async def _inject_api_key_for_public_storage_links(request: Request, call_next):
    path = request.url.path or ""
    is_public_storage_get = (
        request.method.upper() == "GET"
        and path.startswith("/storage/")
        and not path.startswith("/storage/files/")
    )
    # Public message links are only the top-level message read endpoint:
    #   /messages/{id-or-guid}
    # Do not inject for subroutes like /messages/{id}/deliveries.
    message_suffix = path[len("/messages/"):] if path.startswith("/messages/") else ""
    is_public_message_get = (
        request.method.upper() == "GET"
        and path.startswith("/messages/")
        and bool(message_suffix)
        and "/" not in message_suffix
    )
    if (
        (is_public_storage_get or is_public_message_get)
        and not request.headers.get("x-api-key")
        and _bootstrap_api_key
    ):
        headers = list(request.scope.get("headers", []))
        headers.append((b"x-api-key", str(_bootstrap_api_key).encode("utf-8")))
        request.scope["headers"] = headers
    return await call_next(request)

@app.exception_handler(HTTPException)
async def http_exception_envelope(request: Request, exc: HTTPException):
    if request.url.path == "/status" and exc.status_code in (400, 401, 403, 404):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "ok": False,
                "errors": [{"code": str(exc.status_code), "message": str(exc.detail)}],
                "meta": {"path": request.url.path},
            },
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

app.include_router(callback_router, prefix="", tags=["callbacks"])
app.include_router(users_router, prefix=_api_base_path, tags=["users"])
app.include_router(users_router, prefix="/api", tags=["users-legacy"], include_in_schema=False)
app.include_router(groups_router, prefix=_api_base_path, tags=["groups"])
app.include_router(groups_router, prefix="/api", tags=["groups-legacy-api"], include_in_schema=False)
# Backwards-compatible group routes for legacy integrations still calling /groups.
app.include_router(groups_router, prefix="", tags=["groups-legacy"], include_in_schema=False)


def _require_config(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _looks_unresolved_secret(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or "${" in text or "$${" in text


def _resolved_runtime_secret(value: Any) -> str:
    text = str(value or "").strip()
    if text and not _looks_unresolved_secret(text):
        return text
    return ""


def _serialise_api_key_item(item: Any, *, include_raw_key: str | None = None) -> dict[str, Any]:
    """Convert cloud_dog_idam API key dataclasses into JSON-safe payloads."""
    if is_dataclass(item):
        payload = asdict(item)
    elif isinstance(item, dict):
        payload = dict(item)
    else:
        payload = {
            key: getattr(item, key)
            for key in dir(item)
            if not key.startswith("_") and not callable(getattr(item, key))
        }

    payload.pop("key_hash", None)
    payload = jsonable_encoder(payload)
    key_id = str(payload.get("api_key_id") or "")
    if payload.get("created_at") is None and payload.get("created") is not None:
        payload["created_at"] = payload.get("created")
    if payload.get("created_at") is None:
        payload["created_at"] = _API_KEY_FIRST_SEEN_AT.setdefault(key_id, _API_KEY_RUNTIME_STARTED_AT)
    payload.setdefault("expires_at", None)
    payload.setdefault("last_used_at", None)
    payload.setdefault("last_used", None)
    # W28A-889-B-R2: alias the canonical identifiers under the keys the shared
    # IDAM API-Keys page reads (id / user_id) and guarantee a human label, so the
    # page never renders the literal "key-undefined" / owner "undefined".
    payload.setdefault("id", key_id)
    if payload.get("user_id") in (None, ""):
        payload["user_id"] = payload.get("owner_user_id")
    if not payload.get("name"):
        prefix = str(payload.get("key_prefix") or "").strip()
        owner = str(payload.get("owner_user_id") or "").strip()
        payload["name"] = "-".join(p for p in (owner, prefix) if p) or (
            f"key-{key_id[:8]}" if key_id else "api-key"
        )
    if include_raw_key is not None:
        payload["api_key"] = include_raw_key
    return payload


async def _broadcast_config_event(resource: str, action: str, payload: dict[str, Any]) -> None:
    """Broadcast config/admin CRUD events to the A2A event stream."""
    event_payload = {
        "resource": resource,
        "action": action,
        "payload": jsonable_encoder(payload),
    }
    cfg = config or get_config()
    a2a_base_url = _require_config(cfg.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")
    api_key = _require_config(
        cfg.get("a2a_server.api_key") or cfg.get("api_server.api_key"),
        "a2a_server.api_key/api_server.api_key",
    )

    topics = ["config.events"]
    if resource == "channel":
        topics.append("channels.state")

    try:
        global _api_http_client
        if _api_http_client is None or _api_http_client.is_closed:
            _api_http_client = SharedAsyncHTTPClient(
                timeout=HTTPTimeout(timeout=2.0, connect=1.0, read=2.0),
                trust_env=False,
            )
        for topic in topics:
            response = await _api_http_client.post(
                f"{a2a_base_url}/internal/events/broadcast",
                json={"topic": topic, "data": event_payload},
                headers={"X-API-Key": api_key},
            )
            response.raise_for_status()
    except Exception:
        pass  # Best-effort broadcast — CRUD must not fail if A2A is unavailable


def _channel_name_from_profile(channel_type: str, profile_name: str) -> str:
    profile = str(profile_name).strip().lower()
    channel = str(channel_type).strip().lower()
    explicit = {
        ("smtp", "default"): "email_default",
        ("sms", "default"): "sms_default",
        ("whatsapp", "default"): "whatsapp_default",
        ("chat_rest", "default"): "chat_rest_default",
    }
    if (channel, profile) in explicit:
        return explicit[(channel, profile)]
    return f"{channel}_{profile}"


def _hydrate_sms_channel_from_test_config(
    cfg: Any, *, channel_name: str, enabled: bool, payload: Dict[str, Any]
) -> tuple[bool, Dict[str, Any]]:
    """Bridge legacy test.sms/test.twilio.sms settings into channels.sms.default."""
    out = dict(payload)
    provider = out.get("provider") or cfg.get("test.sms.provider")
    sender = out.get("sender") or cfg.get("test.twilio.sms.from_number")
    api_key = out.get("api_key") or cfg.get("test.twilio.sms.auth_token")
    account_sid = out.get("account_sid") or cfg.get("test.twilio.sms.account_sid")
    base_url = out.get("base_url") or cfg.get("test.twilio.sms.base_url")
    verify_ssl = out.get("verify_ssl")
    if verify_ssl is None:
        verify_ssl = cfg.get("test.twilio.sms.verify_ssl")

    # Optional custom CA bundle for TLS verification.
    # If present, Twilio adapter will pass this path to httpx verify=...
    ca_bundle = out.get("ca_bundle")
    if ca_bundle is None:
        ca_bundle = (
            cfg.get("test.twilio.sms.ca_bundle")
            or cfg.get("test.twilio.sms.ca_cert")
            or cfg.get("test.twilio.sms.certificate")
        )

    if provider is not None:
        out["provider"] = provider
    if sender is not None:
        out["sender"] = sender
    if api_key is not None:
        out["api_key"] = api_key
    if account_sid is not None:
        out["account_sid"] = account_sid
    if base_url is not None:
        out["base_url"] = base_url
    if verify_ssl is not None:
        out["verify_ssl"] = verify_ssl
    if ca_bundle:
        out["ca_bundle"] = ca_bundle

    configured = bool(provider and sender and api_key and account_sid and base_url)
    test_sms_channel = str(cfg.get("test.sms.channel_name") or "").strip()
    if not enabled and configured and test_sms_channel == channel_name:
        enabled = True
    return enabled, out


def _reconcile_channels_from_config(cfg: Any, repo: Any, log: Any) -> None:
    """
    Ensure DB channels reflect the active runtime config loaded from --env.
    This guarantees test runtimes expose all channels required by each env profile.
    """
    channels_root = cfg.get("channels") or {}
    if not isinstance(channels_root, dict):
        return

    total_profiles = 0
    synced = 0
    for channel_type, profiles in channels_root.items():
        if not isinstance(profiles, dict):
            continue
        for profile_name, profile_cfg in profiles.items():
            if not isinstance(profile_cfg, dict):
                continue
            total_profiles += 1
            channel_name = _channel_name_from_profile(channel_type, profile_name)
            enabled = bool(profile_cfg.get("enabled", False))
            payload = {
                k: v
                for k, v in profile_cfg.items()
                if k not in {"enabled", "name"}
            }

            if str(channel_type).strip().lower() == "sms":
                enabled, payload = _hydrate_sms_channel_from_test_config(
                    cfg, channel_name=channel_name, enabled=enabled, payload=payload
                )

            # Separate limits/restrictions from connection config
            limits = payload.pop("limits", None)
            restrictions = payload.pop("restrictions", None)
            config_json = json.dumps(payload, sort_keys=True) if payload else None
            limits_json = json.dumps(limits, sort_keys=True) if limits else None
            restrictions_json = json.dumps(restrictions, sort_keys=True) if restrictions else None

            existing = repo.get_by_name(channel_name)
            enabled_int = 1 if enabled else 0

            if existing:
                updates: Dict[str, Any] = {}
                if str(existing.get("type")) != str(channel_type):
                    updates["type"] = str(channel_type)
                if int(existing.get("enabled") or 0) != enabled_int:
                    updates["enabled"] = enabled_int
                if (existing.get("config_json") or None) != config_json:
                    updates["config_json"] = config_json
                # Apply limits/restrictions from config if not already set in DB
                if limits_json and not existing.get("limits_json"):
                    updates["limits_json"] = limits_json
                if restrictions_json and not existing.get("restrictions_json"):
                    updates["restrictions_json"] = restrictions_json
                if updates:
                    repo.update(existing["id"], updates)
                    synced += 1
            else:
                repo.create(
                    name=channel_name,
                    channel_type=str(channel_type),
                    enabled=enabled,
                    config_json=config_json,
                    limits_json=limits_json,
                )
                # Apply restrictions if present in config
                if restrictions_json:
                    created = repo.get_by_name(channel_name)
                    if created:
                        repo.update(created["id"], {"restrictions_json": restrictions_json})
                synced += 1

    if total_profiles:
        log.info(
            "Channel config reconciliation complete: profiles=%s, updated_or_created=%s",
            total_profiles,
            synced,
        )


# Dependency for API key authentication
async def verify_api_key(request: Request):
    """Compatibility dependency backed by cloud_dog_idam auth context middleware."""
    require_authenticated_request(request)


async def verify_admin(request: Request):
    """Require an authenticated admin principal.

    Checks the principal's role from the IDAM auth context.  The bootstrap
    API key owner (``notification-api``) is always treated as admin.
    Non-admin users receive 403 Forbidden.
    Also checks cloud_dog_idam RBACEngine for group-inherited admin
    permissions (PS-70 UM3 group propagation).
    """
    principal = require_authenticated_request(request)
    user_id = str(getattr(principal, "user_id", "") or "").strip()
    # Bootstrap/service principals are implicitly admin
    if user_id in {"notification-api", "bootstrap-admin", "api-runtime"}:
        # W28A-889-B-R2 / W28A-890: the web proxy authenticates with the
        # notification-api service key (a service-admin) but forwards the real web
        # user (X-Request-Source=webui + X-Request-User/Role). Authorize as the
        # FORWARDED user so an authed non-admin web user does NOT collapse to admin.
        # A non-service api-key cannot reach this branch, so it cannot escalate.
        forwarded_source = str(request.headers.get("X-Request-Source") or "").strip().lower()
        forwarded_user = str(request.headers.get("X-Request-User") or "").strip()
        if forwarded_source == "webui" and forwarded_user:
            forwarded_role = str(request.headers.get("X-Request-Role") or "viewer").strip().lower() or "viewer"
            if idam_runtime.rbac_engine.has_permission(forwarded_user, "*"):
                return
            if forwarded_role in {"admin", "owner"}:
                return
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )
        return
    # Check RBAC engine for admin permission (includes group-inherited roles)
    if idam_runtime.rbac_engine.has_permission(user_id, "*"):
        return
    roles = set()
    for attr in ("roles", "role"):
        val = getattr(principal, attr, None)
        if isinstance(val, (list, tuple, set)):
            roles.update(str(r).lower() for r in val)
        elif isinstance(val, str) and val:
            roles.add(val.lower())
    if "admin" in roles or "owner" in roles:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


# ---- W28A-744 (IDAM-B2 §3/§4): resource-aware guard + cascade providers ----
_resource_guard = None
_SERVICE_PRINCIPALS = {"notification-api", "bootstrap-admin", "api-runtime"}


def get_resource_guard():
    """Lazily build the shared W28A-741 resource-aware guard (cascade authoriser)."""
    global _resource_guard
    if _resource_guard is None and db is not None:
        from ...core.rbac.binding_store import NotifBindingStore
        from ...core.rbac.rbac_seam import NotifResourceGuard
        from ...database.repositories import GroupMemberRepository
        _resource_guard = NotifResourceGuard(
            idam_runtime.rbac_engine, GroupMemberRepository(db), NotifBindingStore(db)
        )
    return _resource_guard


def get_binding_store():
    """Return a DB-backed RBAC binding store over the live database."""
    from ...core.rbac.binding_store import NotifBindingStore
    return NotifBindingStore(db)


def _resolve_user_id(raw: Any) -> str:
    """Map a forwarded username/id to the numeric notification user id (membership key)."""
    raw = str(raw or "").strip()
    if not raw or raw.isdigit() or raw in _SERVICE_PRINCIPALS:
        return raw
    try:
        from ...database.repositories import UserRepository
        user = UserRepository(db).get_by_username(raw) if db is not None else None
        if user and user.get("id") is not None:
            return str(user["id"])
    except Exception:
        pass
    return raw


def _caller_user_role(request) -> tuple[str, str]:
    """Resolve (numeric user_id, role) for the request principal (PS-82 §8.3 forwarded session)."""
    src = str(request.headers.get("X-Request-Source") or "").strip().lower()
    fwd_user = str(request.headers.get("X-Request-User") or "").strip()
    fwd_role = str(request.headers.get("X-Request-Role") or "").strip().lower()
    principal = None
    try:
        principal = require_authenticated_request(request)
    except Exception:
        principal = None
    if src == "webui" and fwd_user:
        raw_id, role = fwd_user, fwd_role
    else:
        raw_id = str(getattr(principal, "user_id", "") or "")
        role = ""
        for attr in ("role", "roles"):
            val = getattr(principal, attr, None)
            if isinstance(val, str) and val:
                role = val
                break
            if isinstance(val, (list, tuple, set)) and val:
                role = str(next(iter(val)))
                break
    if not role:
        role = str(request.cookies.get("notification_role") or "viewer")
    return _resolve_user_id(raw_id), role.strip().lower()


def _caller_is_unscoped(user_id: str, role: str, guard) -> bool:
    """admin / service / owner principals are never channel-scoped (no regression)."""
    if not user_id or user_id in _SERVICE_PRINCIPALS or role in {"admin", "owner"}:
        return True
    try:
        idam_runtime.rbac_engine.assign_role_to_user(user_id, role)
    except Exception:
        pass
    return guard.is_admin(user_id)


def _scope_channels_for_caller(request, channels):
    """Filter a channel list to the caller's allowed_resource_ids (IDAM-B2 §2.3 list-filter)."""
    guard = get_resource_guard()
    if guard is None:
        return channels
    user_id, role = _caller_user_role(request)
    if _caller_is_unscoped(user_id, role, guard):
        return channels
    allowed = guard.allowed_resource_ids(user_id, "channel", "channel.read")
    if "*" in allowed:
        return channels
    return [c for c in channels if str(c.get("id")) in allowed]


def _authorise_channel_read(request, channel_id) -> bool:
    """Point-check a single channel read against the cascade (IDAM-B2 §2.3 point check)."""
    guard = get_resource_guard()
    if guard is None:
        return True
    user_id, role = _caller_user_role(request)
    if _caller_is_unscoped(user_id, role, guard):
        return True
    return guard.authorise(
        user_id, permission="channel.read", resource_type="channel", resource_id=str(channel_id)
    )


def _authorise_channel_write(request, channel_id=None) -> bool:
    """Authorise a channel write (IDAM-B2 §3.1 graded): admin/service/read-write pass;
    a restricted GROUPUSER (read-only flat grant only) is denied. ``channel_id=None`` is
    the create surface gate; a concrete id is the point gate."""
    guard = get_resource_guard()
    if guard is None:
        return True
    user_id, role = _caller_user_role(request)
    if _caller_is_unscoped(user_id, role, guard):
        return True
    if channel_id is None:
        return guard.authorise(user_id, permission="channel.write")
    return guard.authorise(
        user_id, permission="channel.write", resource_type="channel", resource_id=str(channel_id)
    )


def _invalidate_binding_subject(subject_type, subject_id) -> None:
    """Drop resolver cache for the binding's subject (and its members) — live cascade."""
    guard = get_resource_guard()
    if guard is None:
        return
    try:
        if str(subject_type) == "group":
            from ...database.repositories import GroupMemberRepository
            members = GroupMemberRepository(db).get_group_members(int(subject_id)) or []
            guard.invalidate(*[str(m["user_id"]) for m in members])
        else:
            guard.invalidate(str(subject_id))
    except Exception:
        guard.invalidate()


def _job_status_name(job: Any) -> str:
    value = getattr(job, "status", None)
    if isinstance(value, JobStatus):
        return value.value
    return str(value or "").strip().lower()


def _job_outcome_summary(job: Any) -> str:
    last_error = getattr(job, "last_error", None)
    if isinstance(last_error, dict):
        for key in ("message", "detail", "error", "reason"):
            value = last_error.get(key)
            if value:
                return str(value)
        try:
            return json.dumps(last_error, sort_keys=True)[:160]
        except Exception:
            return str(last_error)[:160]
    if last_error:
        return str(last_error)[:160]
    result_ref = getattr(job, "result_ref", None)
    if result_ref:
        return str(result_ref)[:160]
    progress = getattr(job, "progress", None)
    if isinstance(progress, dict):
        stage = progress.get("stage")
        if stage:
            return str(stage)[:160]
    return ""


def _terminal_job_statuses() -> set[str]:
    return {
        JobStatus.SUCCEEDED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
        JobStatus.TIMEOUT.value,
        JobStatus.TTL_EXPIRED.value,
        JobStatus.DEAD_LETTERED.value,
        JobStatus.ARCHIVED.value,
    }


def _job_action_delivery_id(job: Any) -> int | None:
    payload = getattr(job, "payload", None) or {}
    delivery_id = payload.get("delivery_id")
    if delivery_id is None:
        return None
    try:
        return int(delivery_id)
    except (TypeError, ValueError):
        return None


def _resolve_channel_name(channel_id: Any) -> str | None:
    if channel_repo is None or channel_id in (None, ""):
        return None
    try:
        channel = channel_repo.get_by_id(int(channel_id))
    except Exception:
        return None
    if not channel:
        return None
    return str(channel.get("name") or channel.get("type") or "").strip() or None


def _encode_job(job: Any) -> dict[str, Any]:
    raw = asdict(job) if is_dataclass(job) else dict(job)
    payload = dict(raw.get("payload") or {})
    channel_id = payload.get("channel_id") or raw.get("channel_id")
    encoded = jsonable_encoder(raw)
    encoded["status"] = _job_status_name(job)
    encoded["message_id"] = payload.get("message_id")
    encoded["channel_name"] = _resolve_channel_name(channel_id)
    encoded["destination"] = payload.get("destination")
    encoded["request_source"] = encoded.get("request_source") or payload.get("request_source") or "legacy"
    encoded["request_auth_method"] = encoded.get("request_auth_method") or payload.get("request_auth_method") or "not_recorded"
    encoded["request_user_agent"] = encoded.get("request_user_agent") or payload.get("request_user_agent") or "not_recorded"
    progress = encoded.get("progress")
    if not isinstance(progress, dict) or not progress.get("stage"):
        status_name = encoded.get("status") or _job_status_name(job)
        encoded["progress"] = {
            "stage": status_name or "recorded",
            "percentage": 100 if str(status_name).lower() in _terminal_job_statuses() else None,
        }
    encoded["outcome_summary"] = _job_outcome_summary(job) or str(encoded.get("status") or "recorded")
    return encoded


def _set_job_status(job: Any, target_status: str, *, action: str) -> bool:
    from ...core.jobs import get_jobs_runtime

    runtime = get_jobs_runtime()
    delivery_id = _job_action_delivery_id(job)
    ok = runtime.backend.update_status(job.job_id, target_status)
    if ok:
        runtime._emit_job_audit(  # noqa: SLF001 - local service bridge for PS-40/PS-75 audit emission
            action,
            "success",
            job_id=job.job_id,
            delivery_id=delivery_id,
            details={"target_status": target_status},
        )
    return ok


def _request_user_can_create_message(request: Request, channel: Dict[str, Any]) -> bool:
    """Authorise message creation against the local user/group model."""
    principal = require_authenticated_request(request)
    principal_id = str(getattr(principal, "user_id", "") or getattr(request.state, "user_id", "") or "").strip()
    if principal_id == "notification-api":
        return True

    if not principal_id.isdigit():
        return False

    from ...database.repositories import GroupMemberRepository, UserRepository
    from ...core.rbac.permissions import SEND, get_checker_for_user

    user_repo = UserRepository(db)
    member_repo = GroupMemberRepository(db)
    user = user_repo.get_by_id(int(principal_id))
    if not user:
        return False

    memberships = member_repo.get_user_groups(int(principal_id))
    owned_groups = [
        int(group["id"])
        for group in memberships
        if str(group.get("role") or "").strip().lower() in {"owner", "admin"}
    ]
    checker = get_checker_for_user(user, owned_groups=owned_groups)
    if checker.has_permission(SEND):
        return True

    channel_config = json.loads(channel.get("config_json") or "{}") if channel.get("config_json") else {}
    linked_group_id = channel_config.get("group_id")
    if linked_group_id is None:
        return False

    try:
        linked_group_id = int(linked_group_id)
    except (TypeError, ValueError):
        return False

    return any(int(group["id"]) == linked_group_id for group in memberships)


if create_cache_router is not None:
    app.include_router(
        create_cache_router(),
        dependencies=[Depends(verify_api_key)],
    )


# Startup hook
async def startup(_: Any) -> None:
    """Initialize server at platform lifecycle startup."""
    global config, db, job_manager, adapter_registry, channel_repo, logger, llm_formatter

    # Load configuration (expects it to be preloaded via --env)
    config = _runtime_config(force_reload=True)
    init_cache_from_config(config)
    idam_runtime.seed_api_key(
        _require_config(
            _resolved_runtime_secret(config.get("api_server.api_key")),
            "api_server.api_key",
        ),
        owner_user_id="notification-api",
    )

    # Setup logger
    logger = setup_logger(
        name="api_server",
        log_file=_require_config(config.get("log.api_server_log"), "log.api_server_log"),
        log_level=_require_config(config.get("log.level"), "log.level"),
        log_format=_require_config(config.get("log.format"), "log.format"),
        console=_require_config(config.get("log.console"), "log.console"),
    )

    logger.info("Starting API server...")

    # Initialize database
    db_uri = _require_config(config.get("db.uri"), "db.uri")

    db = get_db_manager(db_uri)

    # Initialize schema if database is new
    try:
        db.initialize_schema()
        logger.info("Database schema initialized")
    except Exception as e:
        error_message = str(e).lower()
        if "duplicate column name" in error_message or "already exists" in error_message:
            logger.info(f"Schema initialization skipped: {e}")
        else:
            raise

    # W28A-876: ensure the canonical cloud_dog_idam role tables exist and the
    # baseline admin/user roles are seeded so the PS-71 IW3A Roles page
    # (/api/v1/admin/roles) is backed by the shared SqlAlchemyRoleStore.
    try:
        from .admin_identity_roles import RolesAdminService, ensure_role_tables

        if not getattr(db, "engine", None):
            db.connect()
        ensure_role_tables(db.engine)
        RolesAdminService(engine=db.engine).ensure_roles_seed()
        from ...core.rbac.binding_store import ensure_rbac_bindings_table
        ensure_rbac_bindings_table(db)
        logger.info("Admin role tables + rbac_bindings ensured and baseline roles seeded")
    except Exception as e:
        logger.warning(f"Admin role table init failed (non-blocking): {e}", exc_info=True)

    # Initialize repositories
    channel_repo = ChannelRepository(db)

    # Reconcile channels from active runtime config before adapter registration.
    # Source of truth is env/config, DB mirrors runtime state.
    _reconcile_channels_from_config(config, channel_repo, logger)

    # Initialize job manager
    job_manager = JobManager(
        db=db,
        default_ttl_hours=_require_config(config.get("queue.default_ttl_hours"), "queue.default_ttl_hours"),
        max_retries=_require_config(config.get("queue.max_retries"), "queue.max_retries"),
        backoff_base_seconds=_require_config(config.get("queue.backoff_base_seconds"), "queue.backoff_base_seconds"),
        backoff_max_seconds=_require_config(config.get("queue.backoff_max_seconds"), "queue.backoff_max_seconds"),
    )

    # Initialize adapter registry
    adapter_registry = get_adapter_registry()

    # Register channels from database
    channels = channel_repo.list_all(enabled_only=True)
    for channel in channels:
        try:
            channel_config = json.loads(channel["config_json"]) if channel["config_json"] else {}
            adapter_registry.register_channel(
                channel_id=channel["id"],
                channel_type=channel["type"],
                config=channel_config,
            )
            ctx_logger = get_context_logger(
                logger.name,
                channel_id=channel['id'],
                channel_name=channel['name'],
                channel_type=channel['type']
            )
            ctx_logger.info("Registered channel")
        except Exception as e:
            ctx_logger = get_context_logger(
                logger.name,
                channel_name=channel.get('name'),
                channel_id=channel.get('id'),
                channel_type=channel.get('type')
            )
            ctx_logger.info(f"Channel registration deferred (missing config): {e}")

    # Initialize users from configuration (if configured)
    try:
        from src.core.users.user_initializer import initialize_users_from_config
        initialize_users_from_config(db, config.dump(mask_secrets=False))
    except Exception as e:
        logger.warning(f"User initialization failed (non-blocking): {e}", exc_info=True)

    # Initialize shared LLM formatter using its built-in lazy LLM connection path.
    # Eager connect during API startup makes the server vulnerable to avoidable
    # startup kills before the first request is even handled.
    try:
        logger.info("Initializing shared LLM formatter...")
        from src.core.formatters.llm_formatter import LLMFormatter
        llm_formatter = LLMFormatter(db, config)
        logger.info("Shared LLM formatter initialized (lazy LLM connect)")
    except Exception as e:
        logger.error(f"Failed to initialize LLM formatter: {e}", exc_info=True)
        llm_formatter = None

    if _config_truthy(config.get("delivery_worker.enabled", True), True):
        logger.info(f"Delivery worker expected at {_delivery_worker_base_url()}")
    else:
        logger.info("Delivery worker disabled by configuration")

    _sync_extracted_route_state()
    logger.info("API server started successfully")


_lifecycle_hooks.on_post_router = startup


# Root endpoint
@app.get("/")
async def root():
    """API banner"""
    return {
        "name": "Notification Agent MCP Server",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/version")
@app.get("/api/v1/version")
async def api_version():
    """Version endpoint for unified API surface checks."""
    return {
        "name": "Notification Agent MCP Server",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


# Health endpoints are now provided by create_health_router() above.





def _sync_module_state(module):
    for _name, _value in globals().items():
        if _name.startswith("__") or _name in {"app", "_message_routes", "_channel_routes", "_admin_routes"}:
            continue
        setattr(module, _name, _value)


def _sync_extracted_route_state():
    _sync_module_state(_message_routes)
    _sync_module_state(_channel_routes)
    _sync_module_state(_admin_routes)

from . import message_routes as _message_routes
from . import channel_routes as _channel_routes
from . import admin_routes as _admin_routes

app.include_router(_message_routes.router)
app.include_router(_channel_routes.router)
app.include_router(_admin_routes.router)

# W28A-876: mount the canonical SHARED cloud_dog_idam idam_v1_router (resource-registry +
# rbac-bindings) at the api base so the shared @cloud-dog/idam RBAC page resolves
# /api/v1/idam/v1/* (via the web /webapi proxy). ONE estate-wide implementation.
from cloud_dog_idam.api.fastapi.router import idam_v1_router as _idam_v1_router  # noqa: E402

# W28A-744 (IDAM-B2 §2.4): cloud_dog_idam 0.5.x removed set_idam_v1_engine — the host
# app now OWNS the binding store + the resource-aware guard. Mount the notification
# DB-backed binding routes (/idam/v1/rbac/bindings) BEFORE the shared idam_v1_router so
# the persistent rbac_bindings table is the authoritative cascade source of truth; the
# shared router still serves /idam/v1/resource-registry for the WebUI RBAC page.
from . import rbac_binding_routes as _rbac_binding_routes  # noqa: E402
app.include_router(_rbac_binding_routes.router)
app.include_router(_idam_v1_router)

if __name__ == "__main__":
    import uvicorn

    # Load config to get port
    temp_config = _runtime_config()
    port = temp_config.get("api_server.port", 8080)  # Default changed to 8080 for IDP support
    host = temp_config.get("api_server.host", "0.0.0.0")

    getattr(uvicorn, "run")(app, host=host, port=port)

# W28A-569: Debug endpoint for psutil diagnostics
