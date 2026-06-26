#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Unified HTTP process for notification-agent.

The delivery worker intentionally remains a separate process.  This module
only consolidates the HTTP surfaces that previously ran as API, Web, MCP, and
A2A processes.
"""

from __future__ import annotations

import inspect
import asyncio
import json
import uuid
from importlib import import_module
from typing import Any

import httpx
from fastapi import Request
from fastapi.routing import APIRoute
from starlette.responses import JSONResponse, RedirectResponse, StreamingResponse
from starlette.responses import Response
from starlette.routing import Route

from ..config import get_config
from .api.api_server import app
from .a2a import a2a_server as _a2a_server
from .mcp.mcp_server_http import MCPServerJSONRPC
from .web import web_server as _web_server

_web_auth_routes = import_module("src.servers.web.auth_routes")
_web_proxy_routes = import_module("src.servers.web.proxy_routes")
_web_static_handler = import_module("src.servers.web.static_handler")


_cfg = get_config(
    defaults_yaml="defaults.yaml",
    config_yaml="config.yaml",
    force_reload=False,
    unresolved_policy="empty",
)
_mcp_server = MCPServerJSONRPC(
    config=_cfg,
    transport_mode=str(_cfg.get("mcp_server.transport") or "streamable_http").lower(),
)
_mcp_app = _mcp_server.app
_mcp_health_endpoint = None
_legacy_sse_sessions: dict[str, asyncio.Queue[dict[str, Any]]] = {}
_legacy_sse_lock = asyncio.Lock()
_surface_startup_lock = asyncio.Lock()


def _sync_mounted_surface_config(runtime_config: Any | None = None) -> None:
    """Share the env-loaded runtime config with mounted standalone modules."""
    cfg = runtime_config or _cfg or get_config()
    _web_server.config = cfg
    _web_auth_routes.config = cfg
    _web_proxy_routes.config = cfg
    _web_static_handler.config = cfg
    _a2a_server.config = cfg


_sync_mounted_surface_config(_cfg)


def _sync_web_route_state() -> None:
    sync = getattr(_web_server, "_sync_extracted_route_state", None)
    if callable(sync):
        sync()


def _path_starts(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _resolved_runtime_secret(value: Any) -> str:
    text = str(value or "").strip()
    if not text or "${" in text or "$${" in text:
        return ""
    return text


def _bootstrap_api_key() -> str:
    return _resolved_runtime_secret(
        _cfg.get("api_server.api_key")
        or _cfg.get("runtime.a2a_test_api_key")
        or "st-local-secret"
    )


def _needs_unified_auth_bridge(path: str) -> bool:
    if path in {
        "/mcp/health",
        "/a2a/health",
        "/a2a/ready",
        "/a2a/live",
        "/a2a/.well-known/agent.json",
        "/.well-known/agent.json",
    }:
        return True
    if path == "/groups/add":
        return True
    if path.startswith("/groups/") and (path.endswith("/edit") or path.endswith("/assign-owner")):
        return True
    if path in {"/channels/add", "/users/add", "/admin/api-keys"}:
        return True
    if path.startswith("/users/") and path.endswith("/edit"):
        return True
    if path.startswith("/messages/") and path.endswith("/cancel"):
        return True
    if _path_starts(path, ("/api/proxy", "/webapi/proxy")):
        return True
    # MCP, A2A, SSE, and message transport paths require their own auth.
    # Health/discovery endpoints (e.g. /mcp/health, /a2a/health) are handled
    # above and still receive the bridge key.  Execution paths must carry a
    # real caller-supplied API key so AuthContextMiddleware enforces PS-70 UM1.
    if _path_starts(path, ("/mcp", "/a2a", "/sse", "/message")):
        return False
    if _path_starts(path, ("/jobs",)):
        return True
    if path == "/status":
        return False
    if _path_starts(path, ("/api", "/api/v1", "/messages", "/channels", "/deliveries", "/llm")):
        return False
    if _path_starts(path, ("/users", "/groups", "/admin", "/callbacks", "/storage/files")):
        return False
    return True


def _is_legacy_web_page_request(request: Request) -> bool:
    path = request.url.path or ""
    if request.method not in {"GET", "HEAD"}:
        return False
    if request.headers.get("x-api-key"):
        return False
    if path == "/":
        return True
    if path.startswith("/admin/"):
        return True
    if path in {
        "/channels/add",
        "/users/add",
        "/admin/api-keys",
        "/about",
        "/api-docs",
        "/dashboard",
        "/deliveries",
        "/channels",
        "/users",
        "/groups",
        "/messages",
        "/jobs",
        "/settings",
        "/monitoring",
        "/mcp-console",
        "/a2a-console",
        "/storage",
        "/logs",
        "/mcp-logs",
        "/web-api-docs",
        "/db/config",
        "/web-mcp-test",
        "/llm-test",
        "/services",
        "/prompts",
    }:
        return True
    if path.startswith("/db/"):
        return True
    if path.startswith("/deliveries/"):
        return True
    if path.startswith("/users/") and path.endswith("/edit"):
        return True
    if path.startswith("/groups/") and (path.endswith("/edit") or path.endswith("/assign-owner")):
        return True
    return False


def _redirect_with_query(request: Request, target_path: str, *, status_code: int = 308) -> RedirectResponse:
    query = str(request.url.query or "")
    target = f"{target_path}?{query}" if query else target_path
    return RedirectResponse(url=target, status_code=status_code)


def _has_web_session(request: Request) -> bool:
    try:
        if request.session.get("user"):
            return True
    except AssertionError:
        pass
    cookies = request.cookies
    return bool(cookies.get("session") or cookies.get("notification_role") or cookies.get("notification_api_key"))


async def _ensure_unified_surfaces_started() -> None:
    if (
        getattr(_web_server.app.state, "unified_started", False)
        and getattr(_a2a_server.app.state, "unified_started", False)
    ):
        return
    async with _surface_startup_lock:
        if not getattr(_web_server.app.state, "unified_started", False):
            await _web_server._startup(_web_server.app)
            _web_server.app.state.unified_started = True
        if not getattr(_a2a_server.app.state, "unified_started", False):
            await _a2a_server._startup(_a2a_server.app)
            _a2a_server.app.state.unified_started = True
        _sync_mounted_surface_config(get_config())
        _sync_web_route_state()


@app.middleware("http")
async def _unified_auth_bridge(request: Request, call_next):
    """Let mounted Web/A2A public routes pass the API auth middleware."""
    await _ensure_unified_surfaces_started()
    path = request.url.path or ""
    if request.method in {"GET", "HEAD"}:
        public_aliases = getattr(_web_server, "_public_webui_alias_redirects", {})
        protected_aliases = getattr(_web_server, "_protected_webui_alias_redirects", {})
        if path in public_aliases:
            return _redirect_with_query(request, public_aliases[path])
        if path in protected_aliases:
            if not _has_web_session(request):
                return RedirectResponse(url="/login", status_code=307)
            return _redirect_with_query(request, protected_aliases[path])
    if _is_legacy_web_page_request(request):
        return _web_server._ui_index_response()
    if not request.headers.get("x-api-key") and _needs_unified_auth_bridge(path):
        api_key = _bootstrap_api_key()
        if api_key:
            headers = list(request.scope.get("headers", []))
            headers.append((b"x-api-key", api_key.encode("utf-8")))
            request.scope["headers"] = headers
    return await call_next(request)


# Thread-a (PROGRAM-IDAM-RECOVERY-2) flat read-only enforcement across EVERY
# surface. The web-app write-gate only sees /webapi/* (the SPA proxy); /api, /mcp
# and /a2a are served by the API app directly and bypass it. This unified gate
# denies a flat read-only session's writes on ALL of them. Registered AFTER the
# auth bridge above so Starlette runs it FIRST (outermost) — a read-only request
# is rejected BEFORE the bridge can inject a write-capable bootstrap api-key.
_RO_WRITE_EXEMPT_PATHS = {"/auth/login", "/auth/logout", "/auth/refresh", "/login", "/logout"}
_RO_WRITE_SURFACES = (
    "/api", "/webapi", "/web/api", "/messages", "/channels", "/deliveries", "/llm",
    "/users", "/groups", "/admin", "/jobs", "/prompts", "/mcp", "/a2a", "/sse", "/message",
    "/storage/files",
)


def _request_role_is_read_only(request: Request) -> bool:
    role = str(request.cookies.get("notification_role") or "").strip().lower().replace("_", "-")
    return role in {"read-only", "readonly", "read"}


def _request_is_anonymous(request: Request) -> bool:
    """True when the caller carries NO credential of any kind.

    A write to a gated surface from an anonymous caller must be denied with 401
    here, at the outer write seam, BEFORE _unified_auth_bridge can inject the
    bootstrap (service-admin) api-key for SPA page paths — otherwise an anon
    ``POST /prompts`` is silently elevated to bootstrap-admin and succeeds
    (PS-82 §3.1/§8.3: anon must resolve to DENY, never admin).
    """
    if request.headers.get("x-api-key") or request.headers.get("authorization"):
        return False
    cookies = request.cookies
    if cookies.get("session") or cookies.get("notification_role") or cookies.get("notification_api_key"):
        return False
    return True


@app.middleware("http")
async def _flat_read_only_write_gate(request: Request, call_next):
    if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        path = request.url.path or ""
        if path not in _RO_WRITE_EXEMPT_PATHS and _path_starts(path, _RO_WRITE_SURFACES):
            if _request_role_is_read_only(request):
                return JSONResponse(
                    {
                        "detail": "read-only role: write operations are not permitted",
                        "role": "read-only",
                    },
                    status_code=403,
                )
            if _request_is_anonymous(request):
                return JSONResponse(
                    {"detail": "Authentication required"},
                    status_code=401,
                )
    return await call_next(request)


def _add_mcp_health_alias() -> None:
    global _mcp_health_endpoint
    for route in _mcp_app.router.routes:
        if getattr(route, "path", None) == "/health":
            _mcp_health_endpoint = getattr(route, "endpoint", None)
            break

    async def _mcp_health(request: Request) -> Response:
        del request
        if _mcp_health_endpoint is None:
            return Response(status_code=503)
        result = _mcp_health_endpoint()
        if inspect.isawaitable(result):
            result = await result
        return result

    app.add_api_route("/mcp/health", _mcp_health, methods=["GET"], include_in_schema=False)


async def _legacy_sse_queue(session_id: str) -> asyncio.Queue[dict[str, Any]]:
    async with _legacy_sse_lock:
        queue = _legacy_sse_sessions.get(session_id)
        if queue is None:
            queue = asyncio.Queue()
            _legacy_sse_sessions[session_id] = queue
        return queue


async def _drop_legacy_sse_queue(session_id: str) -> None:
    async with _legacy_sse_lock:
        _legacy_sse_sessions.pop(session_id, None)


def _legacy_mcp_base_url() -> str:
    api_base = str(_cfg.get("api_server.base_url") or "").strip()
    if api_base:
        return api_base.rstrip("/")
    port = str(_cfg.get("api_server.port") or "8020")
    return f"http://127.0.0.1:{port}"


async def _legacy_sse_stream(request: Request) -> StreamingResponse:
    session_id = request.headers.get("Mcp-Session-Id") or uuid.uuid4().hex
    queue = await _legacy_sse_queue(session_id)
    endpoint = f"/message?session_id={session_id}&sessionId={session_id}"

    async def _events():
        yield f"event: endpoint\ndata: {endpoint}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    continue
                yield f"event: message\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"
        finally:
            await _drop_legacy_sse_queue(session_id)

    return StreamingResponse(_events(), media_type="text/event-stream")


async def _legacy_sse_message(request: Request) -> JSONResponse:
    session_id = (
        request.query_params.get("session_id")
        or request.query_params.get("sessionId")
        or request.headers.get("Mcp-Session-Id")
    )
    if not session_id:
        return JSONResponse(status_code=400, content={"error": "missing session_id"})

    queue = await _legacy_sse_queue(session_id)
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Propagate the caller's credentials to the internal MCP endpoint. The
    # legacy SSE transport authenticates on the /sse and /message requests, but
    # /mcp/messages enforces its own auth, so the forward must carry the same
    # api-key / bearer token (and session id) or it 401s.
    forward_headers: dict[str, str] = {}
    for _hdr in ("x-api-key", "authorization", "mcp-session-id"):
        _val = request.headers.get(_hdr)
        if _val:
            forward_headers[_hdr] = _val

    endpoint = f"{_legacy_mcp_base_url()}/mcp/messages"
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(endpoint, json=payload, headers=forward_headers)
    try:
        response_payload = response.json()
    except Exception:
        response_payload = None

    # The SSE client parses every queued frame as a JSON-RPC envelope; a bare
    # error body (e.g. {"detail": "..."} from an auth failure) is unparseable
    # and would hang the client until its timeout. Always queue a well-formed
    # JSON-RPC response, synthesising an error envelope (carrying the request
    # id) when the upstream returned a non-JSON-RPC body.
    request_id = payload.get("id") if isinstance(payload, dict) else None
    if isinstance(response_payload, dict) and "jsonrpc" in response_payload:
        await queue.put(response_payload)
    elif request_id is not None:
        # A request (has an id) must get a response; the upstream body was not a
        # JSON-RPC envelope, so synthesise an error carrying the request id.
        detail = ""
        if isinstance(response_payload, dict):
            detail = str(response_payload.get("detail") or response_payload.get("error") or "")
        await queue.put(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": detail or f"upstream error (status {response.status_code})",
                },
            }
        )
    # else: a notification (no id) expects no response — queue nothing.
    return JSONResponse(status_code=200, content={"accepted": True, "session_id": session_id})


app.add_api_route("/sse", _legacy_sse_stream, methods=["GET"], include_in_schema=False)
app.add_api_route("/message", _legacy_sse_message, methods=["POST"], include_in_schema=False)


def _copy_mcp_routes() -> None:
    for route in list(_mcp_app.router.routes):
        path = getattr(route, "path", "")
        if path in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/health"}:
            continue
        if path == "/messages":
            if isinstance(route, APIRoute):
                app.add_api_route(
                    "/mcp/messages",
                    route.endpoint,
                    methods=list(route.methods or []),
                    include_in_schema=False,
                )
            continue
        if isinstance(route, (APIRoute, Route)):
            app.router.routes.append(route)


_add_mcp_health_alias()
_copy_mcp_routes()


@app.get("/.well-known/agent.json")
async def root_agent_card():
    """Serve the A2A agent card at the top-level well-known path."""
    a2a_base = str(_cfg.get("a2a_server.base_url") or "http://127.0.0.1:8020/a2a").rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{a2a_base}/.well-known/agent.json")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


app.mount("/a2a", _a2a_server.app, name="a2a")
app.mount("/", _web_server.app, name="web")


def create_unified_app(*, env_files: list[str] | None = None):
    """Return the unified app, optionally preloading tier env files."""
    if env_files:
        env_file = env_files[0] if len(env_files) == 1 else ",".join(env_files)
        runtime_config = get_config(
            defaults_yaml="defaults.yaml",
            config_yaml="config.yaml",
            env_file=env_file,
            load_env_file=True,
            force_reload=True,
            unresolved_policy="empty",
        )
        _sync_mounted_surface_config(runtime_config)
        _sync_web_route_state()
    return app


@app.on_event("startup")
async def _startup_unified_surfaces() -> None:
    if not getattr(_web_server.app.state, "unified_started", False):
        await _web_server._startup(_web_server.app)
        _web_server.app.state.unified_started = True
    if not getattr(_a2a_server.app.state, "unified_started", False):
        await _a2a_server._startup(_a2a_server.app)
        _a2a_server.app.state.unified_started = True
    _sync_mounted_surface_config(get_config())
    _sync_web_route_state()


@app.on_event("shutdown")
async def _shutdown_unified_surfaces() -> None:
    if getattr(_web_server.app.state, "unified_started", False):
        await _web_server._shutdown(_web_server.app)
        _web_server.app.state.unified_started = False
    if getattr(_a2a_server.app.state, "unified_started", False):
        await _a2a_server._shutdown(_a2a_server.app)
        _a2a_server.app.state.unified_started = False
    await _mcp_server.close()
