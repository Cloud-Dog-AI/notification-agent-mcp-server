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
Description: Web UI Server for Notification Agent MCP Server - Provides a web-based dashboard for monitoring and managing notifications

Related Requirements: FR1.5, UC1.1
Covers: FR1.27, FR1.28, FR1.29, FR1.30, FR1.31, FR1.32, FR1.33
Related Tasks: T10
Related Architecture: CC1.2
Related Tests: IT1.3, IT1.4, IT1.5, IT1.6

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import json
import asyncio
import inspect
import re
import time
from functools import wraps
from pathlib import Path
import secrets
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode, urlparse
from fastapi import Request, Form, HTTPException, Depends, status, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from httpx import (
    AsyncClient as SharedAsyncHTTPClient,
    HTTPError,
    HTTPStatusError,
    RequestError as HTTPRequestError,
    Timeout as HTTPTimeout,
)
from cloud_dog_api_kit.clients import ClientTimeout, create_http_client
from cloud_dog_api_kit.web.proxy import WebApiProxy
try:
    import psutil
except ImportError:
    psutil = None  # psutil is optional for process monitoring

from ...config import get_config
from ...utils.logger import PlatformContextMiddleware, setup_logger, get_logger, setup_sidecar_logger
from ...core.idam.runtime import get_idam_runtime
from ...core.rbac.permissions import (
    ADMIN, CONFIG_READ, CONFIG_WRITE, DELETE_ITEM, LIST, READ_ITEM, SEND,
    get_checker_for_user, list_role_permissions,
)
from .web_flat_roles import (
    ADMIN_ROLE,
    READ_ONLY_ROLE,
    READ_WRITE_ROLE,
    normalise_flat_role,
    permissions_for_role,
)
from cloud_dog_logging.middleware.fastapi import LoggingMiddleware
from cloud_dog_logging import get_audit_logger
from cloud_dog_logging.audit_schema import Actor, Target
from cloud_dog_api_kit import create_app as platform_create_app, create_health_router
from cloud_dog_api_kit.lifecycle.hooks import LifecycleHooks
from ...database.db_manager import get_db_manager
from ...database.repositories import UserRepository, GroupMemberRepository

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

_fs = _PlatformLocalStorage(root_path="/")

# Global configuration
config = None
logger = None
web_access_logger = None
api_base_url = None
api_key = None
_web_proxy: WebApiProxy | None = None
_shared_http_client: Any = None
# Shared long-lived clients for internal service calls (W28A-93b, AGENT-LESSONS §2.3)
_keycloak_http_client: SharedAsyncHTTPClient | None = None
_internal_http_client: SharedAsyncHTTPClient | None = None


def _get_keycloak_client() -> SharedAsyncHTTPClient:
    """Return shared client for Keycloak OAuth calls (verify=False for self-signed)."""
    global _keycloak_http_client
    if _keycloak_http_client is None or _keycloak_http_client.is_closed:
        _keycloak_http_client = SharedAsyncHTTPClient(verify=False, timeout=10.0)
    return _keycloak_http_client


def _get_internal_client() -> SharedAsyncHTTPClient:
    """Return shared client for internal service-to-service calls."""
    global _internal_http_client
    if _internal_http_client is None or _internal_http_client.is_closed:
        _internal_http_client = SharedAsyncHTTPClient(
            timeout=HTTPTimeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
        )
    return _internal_http_client
idam_runtime = get_idam_runtime()
_ui_dist_root = Path(__file__).resolve().parents[3] / "ui" / "dist"
_ui_assets_root = _ui_dist_root / "assets"
_ui_passthrough_exact_paths = (
    "/openapi.json",
)
_ui_passthrough_prefixes = (
    "/api",
    "/webapi",
    "/web/api",
    "/health",
    "/redoc",
    "/auth",
    "/logout",
    "/static",
)

_public_webui_alias_redirects = {
    "/ui/login": "/login",
    "/auth/login": "/login",
}

_protected_webui_alias_redirects = {
    "/audit": "/audit-log",
    "/diagnostics-audit": "/audit-log",
    "/monitoring": "/audit-log",
    "/observability": "/audit-log",
    "/logs": "/audit-log",
    "/mcp-logs": "/audit-log",
    "/services": "/audit-log",
    "/status": "/audit-log",
    "/idam/users": "/admin/users",
    "/idam/groups": "/admin/groups",
    "/idam/api-keys": "/admin/api-keys",
    "/idam/roles": "/admin/roles",
    "/idam/rbac": "/admin/rbac",
    "/apikeys": "/admin/api-keys",
    "/api-keys": "/admin/api-keys",
    "/rbac": "/admin/rbac",
    "/api-docs": "/developer/api-docs",
    "/docs": "/developer/api-docs",
    "/openapi": "/developer/api-docs",
    "/mcp-console": "/developer/mcp-console",
    "/a2a-console": "/developer/a2a-console",
    "/web-api-docs": "/developer/api-docs",
    "/web-mcp-test": "/developer/mcp-console",
    "/jobs": "/system/jobs",
    "/settings": "/system/settings",
    "/about": "/system/about",
    "/storage": "/system/settings",
    "/db/config": "/system/settings",
    "/llm-test": "/system/settings",
    "/db/users": "/admin/users",
    "/db/groups": "/admin/groups",
    "/db/channels": "/channels",
    "/db/messages": "/messages",
    "/db/deliveries": "/deliveries",
    "/db/prompts": "/prompts",
}

_known_webui_exact_paths = {
    "/",
    "/login",
    "/dashboard",
    "/audit-log",
    "/admin/users",
    "/admin/groups",
    "/admin/api-keys",
    "/admin/roles",
    "/admin/rbac",
    "/developer/api-docs",
    "/developer/mcp-console",
    "/developer/a2a-console",
    "/system/jobs",
    "/system/settings",
    "/system/about",
    "/channels",
    "/messages",
    "/deliveries",
    "/prompts",
}

_known_webui_prefixes = (
    "/admin/users/",
    "/admin/groups/",
    "/channels/",
    "/messages/",
    "/deliveries/",
    "/prompts/",
)


def _normalise_base_path(value: Any, *, default: str = "") -> str:
    """Return a normalised leading-slash base path."""
    text = str(value if value not in (None, "") else default).strip()
    if not text:
        return ""
    if not text.startswith("/"):
        text = f"/{text}"
    if text != "/":
        text = text.rstrip("/")
    return "" if text == "/" else text


def _configured_base_path(config_key: str, *, default: str = "") -> str:
    cfg = config or _temp_config
    return _normalise_base_path(cfg.get(config_key), default=default)


def _join_path(base_path: str, suffix: str = "") -> str:
    suffix_text = str(suffix or "").strip()
    if suffix_text and not suffix_text.startswith("/"):
        suffix_text = f"/{suffix_text}"
    if not base_path:
        return suffix_text or ""
    return f"{base_path.rstrip('/')}{suffix_text}"


def _api_target_path(suffix: str = "") -> str:
    return _join_path(_configured_base_path("api_server.base_path", default="/api/v1"), suffix)


def _is_ui_passthrough_path(path: str) -> bool:
    if path in _ui_passthrough_exact_paths:
        return True
    if any(path == prefix or path.startswith(f"{prefix}/") for prefix in _ui_passthrough_prefixes):
        return True
    for base_path in (
        _configured_base_path("mcp_server.base_path", default="/mcp"),
        _configured_base_path("a2a_server.base_path", default="/a2a"),
    ):
        if base_path and (path == base_path or path.startswith(f"{base_path}/")):
            return True
    return False


def _is_known_webui_path(path: str) -> bool:
    return path in _known_webui_exact_paths or any(path.startswith(prefix) for prefix in _known_webui_prefixes)


def _redirect_with_query(request: Request, target_path: str, *, status_code: int = 308) -> RedirectResponse:
    query = str(request.url.query or "")
    location = f"{target_path}?{query}" if query else target_path
    return RedirectResponse(url=location, status_code=status_code)



def _require_config(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _resolve_server_id() -> str:
    cfg = config or get_config()
    return str(cfg.get("app.server_id") or "notification-agent").strip() or "notification-agent"


def _request_client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    forwarded = request.headers.get("x-forwarded-for") if getattr(request, "headers", None) else None
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "unknown") or "unknown")


def _request_user_agent(request: Request | None) -> str:
    if request is None or not getattr(request, "headers", None):
        return ""
    return str(request.headers.get("user-agent") or "")


def _request_path(request: Request | None) -> str:
    request_url = getattr(request, "url", None)
    return str(getattr(request_url, "path", "") or "")


def _auth_actor(request: Request | None, principal: str | None) -> Actor:
    principal_id = str(principal or "anonymous")
    actor_type = "user" if principal and principal.strip() else "anonymous"
    return Actor(
        type=actor_type,
        id=principal_id,
        ip=_request_client_ip(request),
        user_agent=_request_user_agent(request),
    )


def _emit_login_audit(
    request: Request | None,
    username: str | None,
    *,
    outcome: str,
    auth_method: str,
    reason: str | None = None,
    provider: str | None = None,
) -> None:
    details = {
        "server_id": _resolve_server_id(),
        "request_path": _request_path(request),
        "auth_method": auth_method,
    }
    if reason:
        details["reason"] = reason
    if provider:
        details["provider"] = provider
    try:
        get_audit_logger().log_login(
            actor=_auth_actor(request, username),
            outcome=outcome,
            target=Target(type="auth_flow", id=_request_path(request) or "/login", name=auth_method),
            **details,
        )
    except Exception:
        if logger:
            logger.debug("Failed to emit structured login audit event", exc_info=True)


def _emit_oauth_audit(
    request: Request | None,
    *,
    action: str,
    outcome: str,
    reason: str,
    provider: str = "keycloak",
    flow_target: str | None = None,
    **extra_details,
) -> None:
    details = {
        "server_id": _resolve_server_id(),
        "request_path": _request_path(request),
        "provider": provider,
        "reason": reason,
        **extra_details,
    }
    try:
        get_audit_logger().log_security(
            actor=_auth_actor(request, str(getattr(request, "session", {}).get("user") or "anonymous")),
            action=action,
            target=Target(
                type="auth_flow",
                id=flow_target or _request_path(request) or "oauth",
                name=provider,
            ),
            outcome=outcome,
            **details,
        )
    except Exception:
        if logger:
            logger.debug("Failed to emit structured OAuth audit event", exc_info=True)


def _users_table_available(db) -> bool:
    try:
        db.fetchone("SELECT 1 FROM users LIMIT 1")
        return True
    except Exception as exc:
        if "no such table" in str(exc).lower():
            return False
        raise


async def _startup(app):
    """Platform lifecycle startup hook."""
    global config, logger, web_access_logger, api_base_url, api_key

    config = get_config(
        defaults_yaml="defaults.yaml",
        config_yaml="config.yaml",
        force_reload=True,
        unresolved_policy="empty",
    )

    logger = setup_logger(
        name="web_server",
        log_file=_require_config(config.get("log.web_server_log"), "log.web_server_log"),
        log_level=_require_config(config.get("log.level"), "log.level"),
        log_format=_require_config(config.get("log.format"), "log.format"),
        console=_require_config(config.get("log.console"), "log.console"),
    )
    logger.info("Starting Web UI server...")

    if bool(config.get("log.enable_access_log", False)):
        web_access_logger = setup_sidecar_logger(
            name="web_access",
            log_file=_require_config(config.get("log.web_access_log"), "log.web_access_log"),
            log_level=_require_config(config.get("log.level"), "log.level"),
            log_format=_require_config(config.get("log.format"), "log.format"),
        )
    else:
        web_access_logger = None

    db_uri = _require_config(config.get("db.uri"), "db.uri")
    db = get_db_manager(db_uri)
    if not _users_table_available(db):
        try:
            db.initialize_schema()
        except Exception as exc:
            logger.warning(f"Web schema bootstrap encountered non-fatal error: {exc}")
        if not _users_table_available(db):
            raise RuntimeError("users table is unavailable after schema bootstrap")

    global _web_proxy
    api_base_url = config.get("web_server.api_base_url") or config.get("api_server.base_url")
    api_base_url = _require_config(api_base_url, "web_server.api_base_url/api_server.base_url")
    env_file = str(config.get("app.env_file") or "")
    proxy_api_key = _resolved_runtime_secret(config.get("api_server.api_key"))
    if "/tests/" in env_file:
        # Local test envs seed the API runtime with the dedicated E2E key.
        # The sourced env file can still carry unresolved placeholders for api_server.api_key,
        # so the shared proxy needs this explicit runtime-safe override.
        proxy_api_key = str(config.get("runtime.a2a_test_api_key") or "st-local-secret")
    api_key = _require_config(proxy_api_key, "api_server.api_key/runtime.a2a_test_api_key")
    _web_proxy = WebApiProxy.from_config(config)

    global _shared_http_client
    proxy_timeout = float(config.get("web_server.proxy_timeout") or 60.0)
    _shared_http_client = create_http_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=ClientTimeout(connect=min(5.0, proxy_timeout), read=proxy_timeout, total=proxy_timeout),
    )

    _sync_extracted_route_state()

    logger.info(f"Web UI will proxy to API server at {api_base_url}")
    logger.info("Web UI server started successfully")


async def _shutdown(app):
    """Platform lifecycle shutdown hook."""
    global _shared_http_client, _keycloak_http_client, _internal_http_client
    for client_ref in (_shared_http_client, _keycloak_http_client, _internal_http_client):
        if client_ref is not None and not client_ref.is_closed:
            await client_ref.aclose()
    _shared_http_client = None
    _keycloak_http_client = None
    _internal_http_client = None
    logger.info("Web UI server shutting down")


def _runtime_environment() -> str:
    cfg = config or _temp_config
    value = str(cfg.get("app.environment") or "dev").strip().lower()
    if value in {"dev", "staging", "production"}:
        return value
    return "dev"


def _looks_unresolved_secret(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or "${" in text or "$${" in text


def _resolved_runtime_secret(value: Any) -> str:
    text = str(value or "").strip()
    if text and not _looks_unresolved_secret(text):
        return text
    return ""


def _runtime_config_payload(request: Request) -> dict[str, object]:
    cfg = config or _temp_config
    runtime = {
        "ENV": _runtime_environment(),
        "AUTH_MODE": "cookie",
        "SESSION_TIMEOUT_MINUTES": float(cfg.get("web_server.session_timeout_minutes") or 30),
        "MCP_JSONRPC_PATH": str(cfg.get("mcp_server.jsonrpc_path") or "/messages"),
    }

    if (
        str(cfg.get("web_server.auth_mode") or "").strip().lower() == "oidc"
        and cfg.get("idp.enabled", False)
        and cfg.get("idp.keycloak.enabled", False)
    ):
        base_url = str(cfg.get("idp.keycloak.base_url") or "").rstrip("/")
        realm = str(cfg.get("idp.keycloak.realm") or "").strip()
        client_id = str(cfg.get("idp.keycloak.client_id") or "").strip()
        redirect_uri = str(cfg.get("idp.keycloak.redirect_uri") or "").strip()
        scopes = str(cfg.get("idp.keycloak.scopes") or "openid email profile").strip()
        if base_url and realm and client_id and redirect_uri:
            runtime["OIDC_ISSUER"] = f"{base_url}/realms/{realm}"
            runtime["OIDC_CLIENT_ID"] = client_id
            runtime["OIDC_REDIRECT_URI"] = redirect_uri
            runtime["OIDC_SCOPE"] = scopes
            runtime["AUTH_MODE"] = "oidc"

    return runtime


def _ui_index_response() -> HTMLResponse | FileResponse:
    index_path = _ui_dist_root / "index.html"
    if _fs.stat(str(index_path)) is None:
        return HTMLResponse("<h1>Notification UI bundle is not available.</h1>", status_code=503)
    return FileResponse(index_path)


def _ui_file_response(path: str) -> FileResponse | None:
    if not _fs.exists(str(_ui_dist_root)):
        return None

    candidate = (_ui_dist_root / path.lstrip("/")).resolve()
    try:
        candidate.relative_to(_ui_dist_root.resolve())
    except ValueError:
        return None
    _candidate_stat = _fs.stat(str(candidate))
    if _candidate_stat is not None and not _candidate_stat.is_dir:
        return FileResponse(candidate)
    return None


# Load config for middleware setup (expects preloaded config via --env)
_temp_config = get_config(unresolved_policy="empty")
_session_secret = _require_config(
    _temp_config.get("auth.jwt_secret"),
    "auth.jwt_secret",
)
_session_max_age = _require_config(_temp_config.get("web_server.session_max_age"), "web_server.session_max_age")
_web_cors_origins = _temp_config.get("web_server.cors_origins") or []
if not isinstance(_web_cors_origins, list):
    _web_cors_origins = []

_lifecycle_hooks = LifecycleHooks(on_post_router=_startup, on_shutdown=_shutdown)
_request_timeout = float(_temp_config.get("api_server.request_timeout") or 300)
_app_kwargs = {
    "title": "Notification Agent Web UI",
    "version": "0.1.0",
    "description": "Browser-authenticated dashboard and proxy for notification-agent",
    "base_path": _configured_base_path("web_server.base_path", default=""),
    "enable_cors": False,
    "enable_docs": False,
    "enable_health": False,
    "register_signal_handlers_on_startup": False,
    "lifecycle_hooks": _lifecycle_hooks,
    "timeout_seconds": _request_timeout,
}
try:
    _create_app_sig = inspect.signature(platform_create_app)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in _create_app_sig.parameters.values()):
        app = platform_create_app(**_app_kwargs)
    else:
        app = platform_create_app(**{k: v for k, v in _app_kwargs.items() if k in _create_app_sig.parameters})
except (TypeError, ValueError):
    app = platform_create_app(**_app_kwargs)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in _web_cors_origins if isinstance(origin, str) and origin and origin != "*"],
    allow_origin_regex=(
        r"https?://.+"
        if any(origin == "*" for origin in _web_cors_origins)
        else r"https?://(localhost|127\.0\.0\.1)(:\d+)?$|https://([A-Za-z0-9-]+\.)*cloud-dog\.net$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Package middleware handles request correlation and request/response logging.
# Use the Web logger namespace so request-scoped middleware logs flow through
# the same configured handlers/log files as the rest of the Web server.
app.add_middleware(LoggingMiddleware, logger=get_logger("web_server"))
app.add_middleware(PlatformContextMiddleware, logger_name="web_server")

# Suppress ClientDisconnect at the outermost layer (registered last = runs first)
# so it catches disconnects before any logging middleware sees them.
from starlette.middleware.base import BaseHTTPMiddleware
class _ClientDisconnectGuard(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except BaseException as exc:
            if _is_client_disconnect(exc):
                from starlette.responses import Response
                return Response(status_code=499)
            raise
app.add_middleware(_ClientDisconnectGuard)


@app.middleware("http")
async def suppress_client_disconnect(request: Request, call_next):
    """Silently handle ClientDisconnect to avoid ERROR logs from navigating away."""
    try:
        return await call_next(request)
    except BaseException as exc:
        # Check direct exception or any nested sub-exception for ClientDisconnect
        if _is_client_disconnect(exc):
            from starlette.responses import Response
            return Response(status_code=499)
        raise


def _is_client_disconnect(exc: BaseException) -> bool:
    """Recursively check if an exception (or any sub-exception in a group) is ClientDisconnect."""
    if "ClientDisconnect" in type(exc).__name__:
        return True
    if "ClientDisconnect" in str(exc):
        return True
    # Check ExceptionGroup sub-exceptions
    for sub in getattr(exc, 'exceptions', []):
        if _is_client_disconnect(sub):
            return True
    return False


@app.middleware("http")
async def web_access_log_middleware(request: Request, call_next):
    start_time = time.monotonic()
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        if web_access_logger is not None:
            request_id = ""
            if response is not None:
                request_id = str(response.headers.get("X-Request-Id") or "")
            if not request_id:
                request_id = str(request.headers.get("x-request-id") or "")
            web_access_logger.info(
                "web_access",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_string": str(request.url.query or ""),
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - start_time) * 1000, 2),
                    "client_ip": _request_client_ip(request),
                    "user_agent": _request_user_agent(request),
                    "request_id": request_id,
                },
            )


@app.middleware("http")
async def spa_asset_middleware(request: Request, call_next):
    path = request.url.path

    if request.method not in {"GET", "HEAD"}:
        return await call_next(request)

    if path in _public_webui_alias_redirects:
        return _redirect_with_query(request, _public_webui_alias_redirects[path])
    if path == "/ui" or path == "/ui/":
        if not request.session.get("user"):
            return RedirectResponse(url="/login", status_code=307)
        return _redirect_with_query(request, "/")
    if path.startswith("/ui/"):
        suffix = path[3:] or "/"
        target = suffix if suffix.startswith("/") else f"/{suffix}"
        if target != "/login" and not request.session.get("user"):
            return RedirectResponse(url="/login", status_code=307)
        return _redirect_with_query(request, _protected_webui_alias_redirects.get(target, target))

    if path in _protected_webui_alias_redirects:
        if not request.session.get("user"):
            return RedirectResponse(url="/login", status_code=307)
        return _redirect_with_query(request, _protected_webui_alias_redirects[path])

    if path == "/runtime-config.js":
        return await call_next(request)

    if _is_ui_passthrough_path(path):
        return await call_next(request)

    file_response = _ui_file_response(path)
    if file_response is not None:
        return file_response

    if path != "/login" and not request.session.get("user"):
        return RedirectResponse(url="/login", status_code=307)

    if not _is_known_webui_path(path):
        return HTMLResponse("<h1>Page not found</h1>", status_code=404)

    return _ui_index_response()


# Thread-a (PROGRAM-IDAM-RECOVERY-2) flat-role write-gate. A logged-in
# read-only visitor may VIEW every data surface but is denied mutations: any
# write method (POST/PUT/PATCH/DELETE) on a data path resolves to a 403-inline
# (never a 401, never a blank UI). admin / read-write fall through. The auth
# endpoints (/auth/login, /auth/logout, /login) are exempt so a read-only user
# can still log in and out. This is defence in depth on top of the per-route
# @require_permission(CONFIG_WRITE) checks and the API server's own shared-guard
# RBAC — the ONE shared flat-role catalog decides write capability (no fork).
_WRITE_GATE_EXEMPT_PATHS = {
    "/auth/login",
    "/auth/logout",
    "/auth/refresh",
    "/login",
    "/logout",
}


@app.middleware("http")
async def flat_role_write_gate(request: Request, call_next):
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return await call_next(request)
    path = request.url.path
    if path in _WRITE_GATE_EXEMPT_PATHS:
        return await call_next(request)
    try:
        session = request.session
    except (AssertionError, AttributeError):
        session = {}
    user = str((session or {}).get("user") or "").strip()
    # Deny ONLY the explicit flat read-only role. Unknown / viewer / service /
    # DB roles fall through to the per-route @require_permission + API RBAC — the
    # flat gate must not blanket-deny non-read-write sessions (that would break
    # legitimate non-admin write paths). The /api+/mcp surfaces are additionally
    # covered by the unified read-only write-gate in src/servers/unified_app.py.
    role = str((session or {}).get("role") or "").strip().lower().replace("_", "-")
    if user and role in {"read-only", "readonly", "read"}:
        return JSONResponse(
            {
                "detail": "read-only role: write operations are not permitted",
                "role": READ_ONLY_ROLE,
            },
            status_code=403,
        )
    return await call_next(request)


# Starlette runs the last registered middleware first. The function-style SPA
# middleware above reads request.session, so SessionMiddleware must be registered
# after it to be the outer layer and populate the scope before dispatch.
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    max_age=_session_max_age,
)


# API Proxy Helper Functions — uses shared httpx client (W28A-849)
async def api_request(method: str, endpoint: str, data: Optional[dict] = None, params: Optional[dict] = None, timeout: float = 30.0):
    """Make a request to the API server via the shared httpx client."""
    if _shared_http_client is None:
        raise HTTPException(status_code=500, detail="API server not configured")
    try:
        response = await _shared_http_client.request(method, endpoint, json=data, params=params)
        if response.status_code >= 400:
            detail = response.text[:200]
            logger.error(f"API request failed: {response.status_code} - {detail}")
            raise HTTPException(status_code=response.status_code, detail=f"API error: {detail}")
        try:
            return response.json()
        except Exception:
            return response.text
    except HTTPRequestError as exc:
        logger.error(f"API request error: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))

# Session dependency
async def get_current_user(request: Request):
    """Get current user from session"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


# Optional authentication (returns None if not authenticated)
async def get_current_user_optional(request: Request):
    """Get current user from session (optional)"""
    return request.session.get("user")


def _flat_login_accounts() -> dict[str, tuple[str, str]]:
    """Return ``{username: (password, flat-role)}`` for the three flat accounts.

    Thread-a (PROGRAM-IDAM-RECOVERY-2) flat WebUI login: the three flat roles
    admin / read-write / read-only. The admin account keeps the historical
    ``web_server.username``/``web_server.password`` credentials (back-compat
    with existing demo scripts/tests); read-write and read-only are seeded so
    all three flat roles are demoable out of the box. Credentials are
    config-overridable (``web_login.*``); roles/permissions come from the ONE
    shared idam guard (see ``web_flat_roles``).
    """
    cfg = config or _temp_config
    admin_user = str(cfg.get("web_server.username") or "admin").strip() or "admin"
    admin_pw = _resolved_runtime_secret(cfg.get("web_server.password"))
    rw_user = str(cfg.get("web_login.read_write_username") or "read-write").strip() or "read-write"
    rw_pw = str(cfg.get("web_login.read_write_password") or "BlueRiverChair").strip() or "BlueRiverChair"
    ro_user = str(cfg.get("web_login.read_only_username") or "read-only").strip() or "read-only"
    ro_pw = str(cfg.get("web_login.read_only_password") or "GreenRiverDesk").strip() or "GreenRiverDesk"
    accounts: dict[str, tuple[str, str]] = {}
    # Only seed the admin account when a concrete (resolved) password exists, so
    # an unresolved placeholder never authenticates with an empty password.
    if admin_pw:
        accounts[admin_user] = (admin_pw, ADMIN_ROLE)
    accounts[rw_user] = (rw_pw, READ_WRITE_ROLE)
    accounts[ro_user] = (ro_pw, READ_ONLY_ROLE)
    return accounts


def _match_flat_account(username: str, password: str) -> str | None:
    """Constant-time flat-account match. Returns the flat role, or None.

    Compares against EVERY account with ``secrets.compare_digest`` so a wrong
    username and a wrong password are indistinguishable (no username
    enumeration). The matched account decides the flat role; permissions come
    from the shared idam guard.
    """
    matched: str | None = None
    for cand_user, (cand_pw, cand_role) in _flat_login_accounts().items():
        user_ok = secrets.compare_digest(str(username), str(cand_user))
        pw_ok = secrets.compare_digest(str(password), str(cand_pw))
        if user_ok and pw_ok:
            matched = cand_role
    return matched


def _session_user_payload(request: Request) -> dict:
    user = str(request.session.get("user") or "").strip()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    # Thread-a: the session role is one of the three flat roles; permissions are
    # derived from the ONE shared idam guard (no per-service fork). normalise so
    # a legacy/DB role string (admin/owner/user/viewer) still resolves to a flat
    # role + its shared-derived permission set.
    role = normalise_flat_role(request.session.get("role"))
    email = request.session.get("user_email")
    if not email and "@" not in user:
        email = f"{user}@cloud-dog.local"
    permissions = permissions_for_role(role)
    return {
        "id": request.session.get("user_id", 0),
        "username": user,
        "displayName": user,
        "email": email,
        "role": role,
        "roles": [role],
        "permissions": permissions,
    }


# RBAC Helper Functions
async def get_user_with_permissions(request: Request):
    """
    Get current user and permission checker

    Returns:
        Tuple of (user_dict, permission_checker)
    """
    user = await get_current_user(request)

    # Get user details from database
    config = get_config()
    db_uri = _require_config(config.get("db.uri"), "db.uri")
    db = get_db_manager(db_uri)
    db.connect()

    try:
        user_repo = UserRepository(db)
        user_data = None
        try:
            user_data = user_repo.get_by_username(user)
        except Exception as exc:
            logger.warning(f"Web RBAC user lookup failed for '{user}', falling back to session context: {exc}")

        if not user_data:
            expected_username = config.get("web_server.username", "admin")
            session_role = str(request.session.get("role") or "").strip().lower()
            if user == expected_username and get_checker_for_user({"id": 1, "role": session_role}).has_permission(ADMIN):
                user_data = {
                    "id": request.session.get("user_id", 1),
                    "username": user,
                    "email": "",
                    "role": "admin",
                    "enabled": True,
                }
                checker = get_checker_for_user(user_data, [])
                return user_data, checker

            if session_role in {"admin", "owner", "user", "viewer"}:
                user_data = {
                    "id": request.session.get("user_id", 0),
                    "username": user,
                    "email": "",
                    "role": session_role,
                    "enabled": True,
                }
                checker = get_checker_for_user(user_data, [])
                return user_data, checker
            raise HTTPException(status_code=401, detail="User not found")

        # Get groups where user is owner
        member_repo = GroupMemberRepository(db)
        user_groups = member_repo.get_user_groups(user_data['id'])
        owned_groups = [g['id'] for g in user_groups if g.get('role') == 'owner']

        # Create permission checker
        checker = get_checker_for_user(user_data, owned_groups)

        return user_data, checker
    finally:
        # DatabaseManager doesn't need explicit close
        pass


def require_permission(permission: str):
    """Decorator to require a specific permission via cloud_dog_idam RBACEngine."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                raise HTTPException(status_code=500, detail="Request not found for permission check")

            user_data, checker = await get_user_with_permissions(request)
            if not checker.has_permission(permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission}"
                )
            # Add user_data and checker only if the function accepts them
            func_params = inspect.signature(func).parameters
            if "user_data" in func_params:
                kwargs["user_data"] = user_data
            if "checker" in func_params:
                kwargs["checker"] = checker
            return await func(*args, **kwargs)
        wrapper.__signature__ = inspect.signature(func)
        return wrapper
    return decorator


# Serve static files (if they exist)
try:
    static_path = Path(__file__).parent / "static"
    if _fs.exists(str(static_path)):
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
except Exception:
    pass  # Static files optional

try:
    if _fs.exists(str(_ui_assets_root)):
        app.mount("/assets", StaticFiles(directory=str(_ui_assets_root)), name="ui-assets")
except Exception:
    pass




from . import static_handler as _static_handler
from . import auth_routes as _auth_routes
from . import proxy_routes as _proxy_routes

app.include_router(_static_handler.router)
app.include_router(_auth_routes.router)
app.include_router(_proxy_routes.router)

_AUTH_ROUTE_NAMES = {
    "login_page",
    "login",
    "logout",
    "auth_login",
    "auth_me",
    "auth_logout",
    "auth_refresh",
    "is_keycloak_enabled",
    "get_keycloak_config",
    "keycloak_login",
    "keycloak_callback",
}
_AUTH_ROUTE_EXPORTS = {name: getattr(_auth_routes, name) for name in _AUTH_ROUTE_NAMES}


def _sync_module_state(module, *, skip_names=frozenset()):
    for _name, _value in globals().items():
        if (
            _name.startswith("__")
            or _name in skip_names
            or _name in {"app", "_auth_routes", "_proxy_routes", "_static_handler"}
        ):
            continue
        setattr(module, _name, _value)


def _sync_auth_route_state():
    _sync_module_state(_auth_routes, skip_names=_AUTH_ROUTE_NAMES)


def _sync_extracted_route_state():
    _sync_auth_route_state()
    _sync_module_state(_static_handler)
    _sync_module_state(_proxy_routes)


async def login_page(request: Request, message: str = None):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["login_page"](request, message=message)


async def login(username: str = Form(...), password: str = Form(...), request: Request = None):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["login"](username=username, password=password, request=request)


async def logout(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["logout"](request)


async def auth_login(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["auth_login"](request)


async def auth_me(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["auth_me"](request)


async def auth_logout(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["auth_logout"](request)


async def auth_refresh(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["auth_refresh"](request)


def is_keycloak_enabled():
    _sync_auth_route_state()
    return _AUTH_ROUTE_EXPORTS["is_keycloak_enabled"]()


def get_keycloak_config():
    _sync_auth_route_state()
    return _AUTH_ROUTE_EXPORTS["get_keycloak_config"]()


async def keycloak_login(request: Request):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["keycloak_login"](request)


async def keycloak_callback(request: Request, code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    _sync_auth_route_state()
    return await _AUTH_ROUTE_EXPORTS["keycloak_callback"](request, code=code, state=state, error=error)


if __name__ == "__main__":
    import uvicorn

    temp_config = get_config(
        env_file=_bootstrap_env_file,
        load_env_file=bool(_bootstrap_env_file),
        unresolved_policy="empty",
    )
    port = temp_config.get("web_server.port", 8080)
    host = temp_config.get("web_server.host", "0.0.0.0")

    getattr(uvicorn, "run")(app, host=host, port=port)
