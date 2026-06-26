#!/usr/bin/env python3
"""APIRouter routes extracted from web_server.py: backend proxy and test routes."""

import hashlib

from fastapi import APIRouter, Request, Depends
from . import web_server as _web

globals().update({name: value for name, value in vars(_web).items() if not name.startswith("__")})
router = APIRouter()

@router.get("/webapi/proxy/status")
async def proxy_status(user: str = Depends(get_current_user)):
    """Proxy status endpoint"""
    return await api_request("GET", "/status")

@router.get("/webapi/proxy/health")
async def proxy_health(user: str = Depends(get_current_user)):
    """Proxy health endpoint"""
    return await api_request("GET", "/health")

def _log_file_map() -> dict[str, Path]:
    cfg = config or _temp_config
    def _absolute_log_path(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (Path.cwd() / path).resolve()

    return {
        "api": _absolute_log_path(str(cfg.get("log.api_server_log") or "./logs/api_server.log")),
        "worker": _absolute_log_path(str(cfg.get("log.delivery_worker_log") or "./logs/delivery_worker.log")),
        "web": _absolute_log_path(str(cfg.get("log.web_server_log") or "./logs/web_server.log")),
        "mcp": _absolute_log_path(str(cfg.get("log.mcp_server_log") or "./logs/mcp_server.log")),
        "a2a": _absolute_log_path(str(cfg.get("log.a2a_server_log") or "./logs/a2a_server.log")),
        "audit": _absolute_log_path(str(cfg.get("log.audit_log") or "./logs/audit.log")),
    }

def _log_entries(log_type: str, lines: int) -> list[dict[str, str]]:
    log_path = _log_file_map().get(log_type, _log_file_map()["api"])
    log_path_str = str(log_path)
    if not _fs.exists(log_path_str):
        return []

    try:
        raw_lines = _fs.read_bytes(log_path_str).decode("utf-8", errors="ignore").splitlines(True)
    except Exception as exc:
        return [{
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "message": f"Could not read {log_path}: {exc}",
            "source": log_type,
        }]

    entries: list[dict[str, str]] = []
    for line in raw_lines[-max(1, min(lines, 1000)):]:
        stripped = line.rstrip()
        upper = stripped.upper()
        level = "INFO"
        for candidate in ("ERROR", "WARN", "INFO", "DEBUG"):
            if candidate in upper:
                level = candidate
                break
        timestamp = ""
        if stripped[:4].isdigit():
            timestamp = stripped.split(" ", 1)[0]
        entries.append({
            "timestamp": timestamp,
            "level": level,
            "message": stripped,
            "source": log_type,
        })
    return entries

@router.get("/api/proxy/logs")
@router.get("/webapi/proxy/logs")
async def proxy_logs(
    user: str = Depends(get_current_user),
    log_type: str = Query("api"),
    lines: int = Query(200, ge=1, le=1000),
):
    """Return structured log lines for the SPA monitoring view."""
    return {
        "items": _log_entries(log_type, lines),
    }


# ---------------------------------------------------------------------------
# PS-40 NIST AU-3 structured log reader — W28A-644
# ---------------------------------------------------------------------------

_LOG_SURFACES: dict[str, dict[str, str]] = {
    "audit": {
        "label": "Audit",
        "config_key": "audit_log",
        "default_path": "logs/audit.log.jsonl",
    },
    "api": {
        "label": "API",
        "config_key": "api_server_log",
        "default_path": "logs/api_server.log",
    },
    "worker": {
        "label": "Worker",
        "config_key": "delivery_worker_log",
        "default_path": "logs/delivery_worker.log",
    },
    "web": {
        "label": "Web",
        "config_key": "web_server_log",
        "default_path": "logs/web_server.log",
    },
    "mcp": {
        "label": "MCP",
        "config_key": "mcp_server_log",
        "default_path": "logs/mcp_server.log",
    },
    "a2a": {
        "label": "A2A",
        "config_key": "a2a_server_log",
        "default_path": "logs/a2a_server.log",
    },
}

_HTTP_ACCESS_LOG_PATTERN = re.compile(
    r'^(?P<level>[A-Z]+):\s+(?P<client_ip>[^:]+):\d+\s+-\s+"'
    r'(?P<method>[A-Z]+)\s+(?P<path>\S+)\s+HTTP/\d\.\d"\s+'
    r"(?P<status_code>\d{3})\s+(?P<status_text>.+)$"
)
_STRUCTURED_TEXT_PATTERN = re.compile(
    r"^(?P<level>[A-Z]+)\s+\[(?P<logger>[^\]]+)\]\s+(?P<message>.+)$"
)

def _surface_meta(surface: str) -> dict[str, str]:
    return _LOG_SURFACES.get(surface, _LOG_SURFACES["audit"])

def _resolve_log_path(surface: str) -> Path:
    cfg = config or _temp_config
    meta = _surface_meta(surface)
    raw = str(cfg.get(f"log.{meta['config_key']}") or meta["default_path"])
    path = Path(raw)
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()

def _normalise_runtime_env() -> str:
    cfg = config or _temp_config
    return str(cfg.get("app.environment") or cfg.get("environment") or "dev")

def _service_name() -> str:
    cfg = config or _temp_config
    return str(cfg.get("app.service_name") or cfg.get("app.name") or "notification-agent")

def _normalise_actor(value) -> dict:
    if isinstance(value, dict):
        return {
            "type": value.get("type") or "unknown",
            "id": value.get("id") or "N/A",
            "roles": value.get("roles"),
            "ip": value.get("ip"),
            "user_agent": value.get("user_agent"),
        }
    return {"type": "unknown", "id": "N/A", "roles": None, "ip": None, "user_agent": None}

def _normalise_target(value) -> dict:
    if isinstance(value, dict):
        return {
            "type": value.get("type") or "unknown",
            "id": value.get("id") or "N/A",
            "name": value.get("name"),
        }
    return {"type": "unknown", "id": "N/A", "name": None}

def _http_action(method: str) -> str:
    return {"GET": "read", "POST": "create", "PUT": "update", "PATCH": "update", "DELETE": "delete", "HEAD": "read", "OPTIONS": "read"}.get(method.upper(), "access")

def _status_outcome(code) -> str:
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "unknown"
    if 200 <= code < 300:
        return "success"
    if code == 401 or code == 403:
        return "denied"
    if 400 <= code < 500:
        return "failure"
    if code >= 500:
        return "error"
    return "unknown"

def _normalise_json_log_entry(*, surface: str, line_number: int, source_path: Path, raw_line: str, payload: dict) -> dict:
    meta = _surface_meta(surface)
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    actor = _normalise_actor(payload.get("actor"))
    target = _normalise_target(payload.get("target"))
    details = payload.get("details") if isinstance(payload.get("details"), dict) else None
    method = str(extra.get("method") or "").upper() or None
    path = str(extra.get("path") or "").strip() or None
    request_id = payload.get("request_id") or extra.get("request_id")
    trace_id = (
        payload.get("trace_id")
        or payload.get("correlation_id")
        or extra.get("correlation_id")
        or request_id
    )
    severity = str(payload.get("severity") or payload.get("level") or "INFO").upper()
    outcome = payload.get("outcome")
    status_code = extra.get("status_code")

    if method and path and not any(target.values()):
        target = {"type": "endpoint", "id": path, "name": f"{method} {path}"}
    if method and path and not payload.get("event_type"):
        payload["event_type"] = f"http.{_http_action(method)}"
    if method and not payload.get("action"):
        payload["action"] = _http_action(method)
    if method and path and not any(actor.values()):
        actor = {
            "type": "user" if extra.get("user") else "system",
            "id": extra.get("user") or "anonymous",
            "ip": extra.get("client_ip"),
            "roles": None,
            "user_agent": extra.get("user_agent"),
        }
    if not outcome and status_code is not None:
        outcome = _status_outcome(status_code)
    if details is None and extra:
        details = dict(extra)
    if details is not None and payload.get("logger") and "logger" not in details:
        details["logger"] = payload.get("logger")
    if details is not None and payload.get("message") and "message" not in details:
        details["message"] = payload.get("message")

    return {
        "id": f"{surface}:{line_number}",
        "surface": surface,
        "surface_label": meta["label"],
        "source_path": str(source_path),
        "line_number": line_number,
        "timestamp": payload.get("timestamp"),
        "message": payload.get("message") or raw_line,
        "logger": payload.get("logger"),
        "level": payload.get("level"),
        "actor": actor,
        "event_type": payload.get("event_type") or "application.log",
        "action": payload.get("action") or "log",
        "target": target,
        "outcome": outcome,
        "severity": severity,
        "trace_id": trace_id,
        "request_id": request_id,
        "service": payload.get("service") or _service_name(),
        "service_instance": payload.get("service_instance") or _resolve_server_id(),
        "environment": payload.get("environment") or _normalise_runtime_env(),
        "details": details,
        "raw": payload,
    }

def _normalise_text_log_entry(*, surface: str, line_number: int, source_path: Path, raw_line: str) -> dict:
    meta = _surface_meta(surface)
    base_entry = {
        "id": f"{surface}:{line_number}",
        "surface": surface,
        "surface_label": meta["label"],
        "source_path": str(source_path),
        "line_number": line_number,
        "timestamp": None,
        "message": raw_line,
        "logger": None,
        "level": None,
        "actor": _normalise_actor(None),
        "event_type": "application.log",
        "action": "log",
        "target": _normalise_target(None),
        "outcome": None,
        "severity": "INFO",
        "trace_id": None,
        "request_id": None,
        "service": _service_name(),
        "service_instance": _resolve_server_id(),
        "environment": _normalise_runtime_env(),
        "details": {"raw_line": raw_line},
        "raw": {"raw_line": raw_line},
    }

    access_match = _HTTP_ACCESS_LOG_PATTERN.match(raw_line)
    if access_match:
        method = access_match.group("method")
        access_path = access_match.group("path")
        status_code_val = int(access_match.group("status_code"))
        level = access_match.group("level")
        base_entry.update({
            "message": f"{method} {access_path} -> {status_code_val}",
            "level": level,
            "event_type": f"http.{_http_action(method)}",
            "action": _http_action(method),
            "target": {"type": "endpoint", "id": access_path, "name": f"{method} {access_path}"},
            "outcome": _status_outcome(status_code_val),
            "severity": level.upper(),
            "actor": {
                "type": "system",
                "id": "anonymous",
                "ip": access_match.group("client_ip"),
                "roles": None,
                "user_agent": None,
            },
            "details": {
                "status_code": status_code_val,
                "status_text": access_match.group("status_text"),
                "raw_line": raw_line,
            },
            "raw": {
                "status_code": status_code_val,
                "status_text": access_match.group("status_text"),
                "raw_line": raw_line,
            },
        })
        return base_entry

    structured_match = _STRUCTURED_TEXT_PATTERN.match(raw_line)
    if structured_match:
        level = structured_match.group("level")
        logger_name = structured_match.group("logger")
        message = structured_match.group("message")
        base_entry.update({
            "message": message,
            "logger": logger_name,
            "level": level,
            "target": {"type": "logger", "id": logger_name, "name": logger_name},
            "severity": level.upper(),
            "details": {"logger": logger_name, "raw_line": raw_line},
            "raw": {"logger": logger_name, "message": message, "raw_line": raw_line},
        })
    return base_entry

def _read_structured_log_entries(surface: str, limit: int, query: str | None = None) -> dict:
    source_path = _resolve_log_path(surface)
    source_path_str = str(source_path)
    meta = _surface_meta(surface)
    if not _fs.exists(source_path_str):
        return {
            "entries": [],
            "count": 0,
            "surface": surface,
            "surface_label": meta["label"],
            "source_path": source_path_str,
        }

    try:
        raw_bytes = _fs.read_bytes(source_path_str)
        all_lines = raw_bytes.decode("utf-8", errors="replace").splitlines(True)
    except Exception:
        return {
            "entries": [],
            "count": 0,
            "surface": surface,
            "surface_label": meta["label"],
            "source_path": str(source_path),
        }

    entries: list[dict] = []
    needle = str(query or "").strip().lower()
    if needle:
        indexed_lines = list(enumerate(all_lines, start=1))
        candidate_lines = [
            (ln, raw)
            for ln, raw in reversed(indexed_lines)
            if needle in raw.lower()
        ][:limit]
        candidate_lines.reverse()
    else:
        start = max(0, len(all_lines) - limit)
        candidate_lines = list(enumerate(all_lines[start:], start=start + 1))

    for offset, raw_line in candidate_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            entries.append(_normalise_json_log_entry(
                surface=surface, line_number=offset, source_path=source_path, raw_line=line, payload=payload,
            ))
        else:
            entries.append(_normalise_text_log_entry(
                surface=surface, line_number=offset, source_path=source_path, raw_line=line,
            ))

    entries.reverse()
    return {
        "entries": entries,
        "count": len(entries),
        "surface": surface,
        "surface_label": meta["label"],
        "source_path": str(source_path),
    }

@router.get("/web/api/logs")
@router.get("/webapi/proxy/structured-logs")
async def structured_logs(
    request: Request,
    user: str = Depends(get_current_user),
    surface: str = Query("audit"),
    limit: int = Query(100, ge=1, le=500),
    query: str | None = Query(None),
):
    """PS-40 NIST AU-3 compliant structured log entries for the DataTable log viewer."""
    normalised_surface = str(surface or "audit").strip().lower()
    if normalised_surface not in _LOG_SURFACES:
        raise HTTPException(status_code=400, detail=f"Unsupported log surface: {surface}")
    safe_limit = max(1, min(int(limit), 500))
    payload = _read_structured_log_entries(normalised_surface, safe_limit, query)
    payload["available_surfaces"] = [
        {"id": key, "label": val["label"]}
        for key, val in _LOG_SURFACES.items()
    ]
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# PS-74 v2 docs WebUI source-backed document proxy — W28A-811
# ---------------------------------------------------------------------------

_DOCS_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOCS_CONTRACT: tuple[dict[str, str], ...] = (
    {
        "id": "readme",
        "title": "README",
        "source_path": "README.md",
        "widget": "markdown",
        "required": "YES",
        "download_filename": "notification-agent-README.md",
        "content_type": "text/markdown; charset=utf-8",
    },
    {
        "id": "api-openapi-swagger",
        "title": "OpenAPI Swagger",
        "source_path": "docs/openapi.json",
        "widget": "swagger",
        "required": "YES",
        "download_filename": "notification-agent-openapi.json",
        "content_type": "application/json; charset=utf-8",
    },
    {
        "id": "mcp-tool-reference",
        "title": "MCP Tool Reference",
        "source_path": "docs/MCP_SERVER.md",
        "widget": "markdown",
        "required": "YES",
        "download_filename": "notification-agent-MCP_SERVER.md",
        "content_type": "text/markdown; charset=utf-8",
    },
    {
        "id": "a2a-card",
        "title": "A2A Agent Card",
        "source_path": "docs/A2A_SERVER.md (live /.well-known/agent.json)",
        "widget": "json",
        "required": "YES",
        "download_filename": "notification-agent-a2a-agent-card.json",
        "content_type": "application/json; charset=utf-8",
    },
    {
        "id": "configuration-summary",
        "title": "Configuration Summary",
        "source_path": "defaults.yaml",
        "widget": "markdown",
        "required": "YES",
        "download_filename": "notification-agent-defaults.yaml",
        "content_type": "text/yaml; charset=utf-8",
    },
    {
        "id": "docker-reference",
        "title": "Docker Reference",
        "source_path": "docs/DOCKER.md",
        "widget": "markdown",
        "required": "YES",
        "download_filename": "notification-agent-DOCKER.md",
        "content_type": "text/markdown; charset=utf-8",
    },
    {
        "id": "channel-adapter-reference",
        "title": "Channel Adapter Reference",
        "source_path": "docs/ARCHITECTURE.md",
        "widget": "markdown",
        "required": "YES-PROJECT-SPECIFIC",
        "download_filename": "notification-agent-ARCHITECTURE.md",
        "content_type": "text/markdown; charset=utf-8",
    },
    {
        "id": "notification-template-catalogue",
        "title": "Notification Template Catalogue",
        "source_path": "docs/PROMPTS.md",
        "widget": "markdown",
        "required": "YES-PROJECT-SPECIFIC",
        "download_filename": "notification-agent-PROMPTS.md",
        "content_type": "text/markdown; charset=utf-8",
    },
)
_DOCS_BY_ID = {item["id"]: item for item in _DOCS_CONTRACT}


def _docs_file_path(meta: dict[str, str]) -> Path:
    source_path = meta["source_path"].split(" ", 1)[0]
    return (_DOCS_PROJECT_ROOT / source_path).resolve()


def _docs_read_source_file(meta: dict[str, str]) -> bytes:
    source = _docs_file_path(meta)
    root = _DOCS_PROJECT_ROOT.resolve()
    if root not in source.parents and source != root:
        raise HTTPException(status_code=400, detail="Document source path escapes project root")
    source_text = str(source)
    if not _fs.exists(source_text):
        raise HTTPException(status_code=404, detail=f"Document source not found: {meta['source_path']}")
    return _fs.read_bytes(source_text)


async def _docs_live_a2a_card() -> tuple[bytes, str]:
    cfg = config or _temp_config
    try:
        a2a_base_url = _require_config(cfg.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")
        response = await _get_internal_client().get(f"{a2a_base_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.content, f"{a2a_base_url}/.well-known/agent.json"
    except Exception as exc:
        logger.warning("Docs A2A card live probe failed; using local registry fallback: %s", exc)
        card = _fallback_a2a_agent_card()
        card["source"] = "local_registry_fallback_for_docs"
        return json.dumps(card, indent=2, sort_keys=True).encode("utf-8"), "local_registry_fallback"


async def _docs_raw_bytes(doc_id: str) -> tuple[dict[str, str], bytes, str]:
    meta = _DOCS_BY_ID.get(doc_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown documentation id: {doc_id}")
    if doc_id == "a2a-card":
        raw, observed_source = await _docs_live_a2a_card()
        return meta, raw, observed_source
    raw = _docs_read_source_file(meta)
    return meta, raw, str(_docs_file_path(meta))


def _docs_text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _docs_render_content(doc_id: str, raw: bytes) -> tuple[str, Any | None]:
    text = _docs_text(raw)
    if doc_id == "configuration-summary":
        return (
            "# Configuration Summary\n\n"
            "Source: `defaults.yaml`\n\n"
            "```yaml\n"
            f"{text.rstrip()}\n"
            "```\n",
            None,
        )
    if doc_id in {"api-openapi-swagger", "a2a-card"}:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        pretty = json.dumps(parsed, indent=2, sort_keys=True) if parsed is not None else text
        return pretty, parsed
    return text, None


def _docs_payload_meta(meta: dict[str, str], observed_source: str, raw: bytes) -> dict[str, Any]:
    return {
        "id": meta["id"],
        "title": meta["title"],
        "source_path": meta["source_path"],
        "observed_source": observed_source,
        "widget": meta["widget"],
        "required": meta["required"],
        "download_filename": meta["download_filename"],
        "content_type": meta["content_type"],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _emit_docs_audit(
    request: Request,
    user: str,
    *,
    action: str,
    doc_id: str,
    outcome: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    try:
        payload = {
            "server_id": _resolve_server_id(),
            "request_path": _request_path(request),
            "doc_id": doc_id,
            "details": details or {},
        }
        get_audit_logger().log_crud(
            actor=_auth_actor(request, user),
            action=action,
            target=Target(type="docs", id=doc_id, name=f"notification-agent docs {doc_id}"),
            outcome=outcome,
            details=payload,
        )
    except Exception as exc:
        logger.warning("Failed to emit docs audit event %s for %s: %s", action, doc_id, exc)


@router.get("/api/proxy/docs/index")
@router.get("/webapi/proxy/docs/index")
async def proxy_docs_index(request: Request, user: str = Depends(get_current_user)):
    """Return the locked PS-74 document bank for the notification-agent docs WebUI."""
    docs = []
    for meta in _DOCS_CONTRACT:
        source_exists = meta["id"] == "a2a-card" or _fs.exists(str(_docs_file_path(meta)))
        docs.append({
            "id": meta["id"],
            "title": meta["title"],
            "source_path": meta["source_path"],
            "widget": meta["widget"],
            "required": meta["required"],
            "download_filename": meta["download_filename"],
            "content_type": meta["content_type"],
            "source_exists": source_exists,
        })
    _emit_docs_audit(request, user, action="docs.index", doc_id="all", details={"count": len(docs)})
    return {"documents": docs, "count": len(docs), "source": "source_backed_locked_bank"}


@router.get("/api/proxy/docs/raw/{doc_id}")
@router.get("/webapi/proxy/docs/raw/{doc_id}")
async def proxy_docs_raw(request: Request, doc_id: str, user: str = Depends(get_current_user)):
    """Download a source-backed documentation artifact with original bytes where applicable."""
    try:
        meta, raw, observed_source = await _docs_raw_bytes(doc_id)
        _emit_docs_audit(
            request,
            user,
            action="docs.download",
            doc_id=doc_id,
            details={"observed_source": observed_source, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        )
        headers = {"Content-Disposition": f"attachment; filename={meta['download_filename']}"}
        return Response(content=raw, media_type=meta["content_type"], headers=headers)
    except HTTPException:
        _emit_docs_audit(request, user, action="docs.download", doc_id=doc_id, outcome="failure")
        raise


@router.get("/api/proxy/docs/{doc_id}")
@router.get("/webapi/proxy/docs/{doc_id}")
async def proxy_docs_document(request: Request, doc_id: str, user: str = Depends(get_current_user)):
    """Return one locked documentation artifact with rendering metadata and source attribution."""
    try:
        meta, raw, observed_source = await _docs_raw_bytes(doc_id)
        content, json_value = _docs_render_content(doc_id, raw)
        payload = {
            "document": _docs_payload_meta(meta, observed_source, raw),
            "content": content,
            "json": json_value,
        }
        _emit_docs_audit(
            request,
            user,
            action="docs.view",
            doc_id=doc_id,
            details={"observed_source": observed_source, "sha256": payload["document"]["sha256"]},
        )
        return payload
    except HTTPException:
        _emit_docs_audit(request, user, action="docs.view", doc_id=doc_id, outcome="failure")
        raise


@router.post("/api/proxy/docs/audit")
@router.post("/webapi/proxy/docs/audit")
async def proxy_docs_audit(request: Request, user: str = Depends(get_current_user)):
    """Record a docs WebUI action such as copy, print, search, or source inspection."""
    payload = await request.json()
    doc_id = str(payload.get("doc_id") or "unknown").strip() or "unknown"
    action = str(payload.get("action") or "").strip()
    allowed = {"docs.copy", "docs.print", "docs.search", "docs.source", "docs.download", "docs.view"}
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported docs audit action: {action}")
    outcome = str(payload.get("outcome") or "success").strip() or "success"
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    _emit_docs_audit(request, user, action=action, doc_id=doc_id, outcome=outcome, details=details)
    return {"ok": True, "action": action, "doc_id": doc_id, "outcome": outcome}


def _request_metadata_headers(request: Request, override_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    request_id = str(request.headers.get("x-request-id") or "").strip()
    correlation_id = str(request.headers.get("x-correlation-id") or "").strip()
    if request_id:
        headers["X-Request-Id"] = request_id
    if correlation_id:
        headers["X-Correlation-Id"] = correlation_id
    if override_key:
        headers["X-API-Key"] = override_key
        # W28A-889-B-R2 / W28A-890: the web proxy authenticates to the API with the
        # notification-api service key (a _SERVICE_ADMINS member). Forward the real
        # authenticated web user so the API authorizes per-user RBAC instead of
        # collapsing every web session to the service admin.
        try:
            session = request.session
        except Exception:
            session = {}
        web_user = str((session or {}).get("user") or "").strip()
        if web_user:
            headers["X-Request-Source"] = "webui"
            headers["X-Request-User"] = web_user
            headers["X-Request-Role"] = str((session or {}).get("role") or "viewer").strip().lower() or "viewer"
    return headers

def _a2a_proxy_headers(request: Request, override_key: str | None = None) -> dict[str, str]:
    cfg = config or _temp_config
    headers = _request_metadata_headers(request, override_key)
    if "X-API-Key" not in headers:
        a2a_api_key = cfg.get("a2a_server.api_key") or cfg.get("api_server.api_key")
        if a2a_api_key:
            headers["X-API-Key"] = str(a2a_api_key)
    return headers

async def _mcp_jsonrpc(method: str, params: Optional[dict] = None, extra_headers: Optional[dict[str, str]] = None) -> dict:
    cfg = config or _temp_config
    mcp_base_url = _require_config(cfg.get("mcp_server.base_url"), "mcp_server.base_url").rstrip("/")
    jsonrpc_path = str(cfg.get("mcp_server.jsonrpc_path") or "/messages")
    protocol_version = str(cfg.get("mcp_server.protocol_version") or "2025-11-25")
    endpoint = f"{mcp_base_url}{jsonrpc_path}"
    headers: dict[str, str] = dict(extra_headers or {})
    mcp_api_key = cfg.get("mcp_server.api_key")
    if mcp_api_key and "X-API-Key" not in headers:
        headers["X-API-Key"] = str(mcp_api_key)

    client = _get_internal_client()
    init_response = await client.post(
        endpoint,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "notification-agent-webui", "version": "1.0"},
            },
        },
    )
    init_response.raise_for_status()

    await client.post(
        endpoint,
        headers=headers,
        json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
    )

    request_id = 2 if method == "tools/list" else 3
    response = await client.post(
        endpoint,
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        },
    )
    response.raise_for_status()
    return response.json()

@router.get("/api/proxy/mcp/tools")
@router.get("/webapi/proxy/mcp/tools")
async def proxy_mcp_tools(user: str = Depends(get_current_user)):
    """Return MCP tool metadata for the shared console."""
    try:
        payload = await _mcp_jsonrpc("tools/list")
        tools = payload.get("result", {}).get("tools", [])
        if tools:
            return {"items": tools}
    except Exception as exc:
        logger.warning("MCP tools JSON-RPC probe failed; using local registry fallback: %s", exc)

    from ..mcp.tool_registry import build_tool_contracts

    items = []
    for contract in build_tool_contracts().values():
        schema = getattr(contract, "input_schema", None) or getattr(contract, "inputSchema", None) or {}
        items.append({
            "name": contract.name,
            "description": getattr(contract, "description", "") or "",
            "inputSchema": schema,
        })
    return {"items": items, "total": len(items), "source": "local_registry"}

@router.post("/api/proxy/mcp/tools/call")
@router.post("/webapi/proxy/mcp/tools/call")
async def proxy_mcp_tool_call(request: Request, user: str = Depends(get_current_user)):
    """Execute an MCP tool through the web proxy."""
    payload = await request.json()
    tool_name = str(payload.get("name") or "").strip()
    if not tool_name:
        raise HTTPException(status_code=400, detail="Tool name is required")
    arguments = payload.get("arguments") or {}
    override_key = str(
        request.headers.get("x-admin-override-key") or payload.get("admin_override_key") or ""
    ).strip()
    metadata_headers = _request_metadata_headers(request, override_key or None)
    try:
        return await _mcp_jsonrpc("tools/call", {"name": tool_name, "arguments": arguments}, metadata_headers)
    except Exception as exc:
        logger.warning("MCP tool JSON-RPC call failed; using read-only API fallback for %s: %s", tool_name, exc)

    if tool_name == "get_status":
        return {"result": await api_request("GET", "/status"), "source": "api_fallback"}
    if tool_name in {"list_channels", "admin_list_channels"}:
        return {"result": await api_request("GET", "/channels"), "source": "api_fallback"}
    if tool_name == "list_messages":
        params = {
            key: value
            for key, value in {
                "limit": arguments.get("limit"),
                "status": arguments.get("status"),
            }.items()
            if value not in (None, "")
        }
        return {"result": await api_request("GET", "/messages", params=params or None), "source": "api_fallback"}
    if tool_name == "get_message":
        message_id = arguments.get("message_id") or arguments.get("id")
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        return {"result": await api_request("GET", f"/messages/{message_id}", params={"format": "json"}), "source": "api_fallback"}
    if tool_name == "list_deliveries":
        params = {
            key: value
            for key, value in {
                "message_id": arguments.get("message_id"),
                "limit": arguments.get("limit"),
            }.items()
            if value not in (None, "")
        }
        return {"result": await api_request("GET", "/deliveries", params=params or None), "source": "api_fallback"}
    raise HTTPException(status_code=502, detail=f"MCP JSON-RPC unavailable and no safe fallback exists for {tool_name}")

@router.post("/api/proxy/a2a/send")
@router.post("/webapi/proxy/a2a/send")
async def proxy_a2a_send(request: Request, user: str = Depends(get_current_user)):
    """Send an A2A request through the web proxy."""
    cfg = config or _temp_config
    payload = await request.json()
    topic = str(payload.get("topic") or "").strip()
    message_payload = payload.get("payload") or {}
    override_key = str(
        request.headers.get("x-admin-override-key") or payload.get("admin_override_key") or ""
    ).strip()
    a2a_base_url = _require_config(cfg.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")
    client = _get_internal_client()
    headers = _a2a_proxy_headers(request, override_key or None)
    if topic in {"list_channels", "get_status"}:
        command = "List available notification channels." if topic == "list_channels" else "Get notification delivery status."
        if isinstance(message_payload, dict):
            command = str(message_payload.get("command") or message_payload.get("text") or command)
        response = await client.post(
            f"{a2a_base_url}/a2a/tasks",
            json={"skill_id": topic, "input": {"text": command}},
            headers=headers,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()

    if topic in {"send_notification", "notify/natural"}:
        topic = "notify/natural"
        if isinstance(message_payload, dict) and "command" not in message_payload:
            message_payload = {
                "command": "Send notification to user@example.com that the local PS-72 notification-agent A2A test completed.",
                "channels": ["loopback_test"],
            }
    else:
        raise HTTPException(status_code=400, detail="Unsupported A2A topic")

    response = await client.post(
        f"{a2a_base_url}/notify/natural",
        json=message_payload,
        headers=headers,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()

def _fallback_a2a_agent_card() -> dict[str, Any]:
    cfg = config or _temp_config
    return {
        "name": "notification-agent",
        "description": "Notification agent A2A server for real-time notification streaming and dispatch",
        "url": str(cfg.get("a2a_server.base_url") or "/a2a"),
        "version": str(cfg.get("a2a_server.version") or cfg.get("app.version") or "notification-webui-2026.05.28"),
        "capabilities": {
            "streaming": True,
            "pushNotifications": True,
        },
        "skills": [
            {
                "id": "send_notification",
                "name": "Send Notification",
                "description": "Send a notification via configured channels",
            },
            {
                "id": "list_channels",
                "name": "List Channels",
                "description": "List available notification channels",
            },
            {
                "id": "get_status",
                "name": "Get Status",
                "description": "Get notification delivery status",
            },
        ],
        "source": "local_registry",
    }

@router.get("/api/proxy/a2a/agent-card")
@router.get("/webapi/proxy/a2a/agent-card")
async def proxy_a2a_agent_card(user: str = Depends(get_current_user)):
    """Return the A2A agent card through the authenticated web proxy."""
    cfg = config or _temp_config
    a2a_base_url = _require_config(cfg.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")
    client = _get_internal_client()
    try:
        response = await client.get(f"{a2a_base_url}/.well-known/agent.json")
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.warning("A2A agent card probe failed; using local registry fallback: %s", exc)
        return _fallback_a2a_agent_card()


# ============================================================================
# TEST API ENDPOINTS - For automated testing
# ============================================================================

@router.post("/webapi/tests/login")
async def test_login(request: Request):
    """Test endpoint for login - returns session info"""
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")

        # Try database-based authentication first
        try:
            db_uri = _require_config(config.get("db.uri"), "db.uri")
            db_manager = get_db_manager(db_uri)
            user_repo = UserRepository(db_manager)
            user = user_repo.get_by_username(username)

            if user:
                # Verify via cloud_dog_idam password provider.
                password_hash = user.get("password_hash", "")
                verified = False
                if password_hash:
                    verified = idam_runtime.verify_password(password, password_hash)

                if verified:
                    # Create session
                    request.session["user"] = username
                    request.session["user_id"] = user["id"]
                    request.session["role"] = user.get("role", "viewer")

                    return {
                        "success": True,
                        "username": username,
                        "user_id": user["id"],
                        "role": user.get("role", "viewer"),
                        "message": "Login successful (database)"
                    }
        except Exception as db_error:
            logger.debug(f"Database auth failed, trying config-based: {db_error}")

        # Fall back to config-based authentication (same as regular login)
        expected_username = config.get("web_server.username", "admin")
        expected_password = _require_config(config.get("web_server.password"), "web_server.password")

        if username == expected_username and password == expected_password:
            # Create session
            request.session["user"] = username
            request.session["user_id"] = 1  # Default admin user ID
            request.session["role"] = "admin"

            logger.info(f"User {username} logged in via test endpoint")
            return {
                "success": True,
                "username": username,
                "user_id": 1,
                "role": "admin",
                "message": "Login successful (config-based)"
            }
        else:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webapi/tests/logout")
async def test_logout(request: Request):
    """Test endpoint for logout"""
    request.session.clear()
    return {"success": True, "message": "Logged out"}

@router.get("/webapi/tests/session")
async def test_session(request: Request):
    """Test endpoint to check session"""
    user = request.session.get("user")
    if user:
        return {
            "authenticated": True,
            "username": user,
            "user_id": request.session.get("user_id"),
            "role": request.session.get("role")
        }
    else:
        return {"authenticated": False}

@router.get("/webapi/tests/endpoints")
async def test_endpoints(user: str = Depends(get_current_user)):
    """Test endpoint to list all available test endpoints"""
    return {
        "endpoints": {
            "login": "POST /webapi/tests/login - Login with username/password",
            "logout": "POST /webapi/tests/logout - Logout current session",
            "session": "GET /webapi/tests/session - Check current session",
            "endpoints": "GET /webapi/tests/endpoints - List all test endpoints",
            "api_health": "GET /webapi/proxy/health - API server health",
            "web_health": "GET /health - Web UI health",
            "keycloak_login": "GET /auth/keycloak/login - Initiate Keycloak OAuth2",
            "mcp_test": "GET /web-mcp-test - MCP/A2A test page",
            "dashboard": "GET /dashboard - Dashboard page"
        },
        "authenticated": True,
        "username": user
    }

@router.get("/webapi/tests/api-connection")
async def test_api_connection(user: str = Depends(get_current_user)):
    """Test endpoint to verify API server connection"""
    try:
        result = await api_request("GET", "/health")
        return {
            "success": True,
            "api_connected": True,
            "api_url": api_base_url,
            "api_response": result
        }
    except Exception as e:
        return {
            "success": False,
            "api_connected": False,
            "api_url": api_base_url,
            "error": str(e)
        }

@router.post("/webapi/tests/mcp-test")
async def test_mcp_test(request: Request, user: str = Depends(get_current_user)):
    """Test endpoint for MCP/A2A natural language command"""
    try:
        data = await request.json()
        command = data.get("command")
        channels = data.get("channels", [])

        if not command:
            raise HTTPException(status_code=400, detail="Command required")

        # Proxy to A2A endpoint
        a2a_base_url = _require_config(config.get("a2a_server.base_url"), "a2a_server.base_url")
        a2a_base_url = a2a_base_url.rstrip('/')

        client = _get_internal_client()
        response = await client.post(
            f"{a2a_base_url}/notify/natural",
            json={"command": command, "channels": channels},
        )
        response.raise_for_status()
        return response.json()
    except HTTPError as e:
        logger.error(f"A2A connection error: {e}")
        raise HTTPException(status_code=503, detail=f"A2A server error: {str(e)}")
    except Exception as e:
        logger.error(f"Test MCP error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/proxy/channels")
@router.get("/webapi/proxy/channels")
async def proxy_channels(user: str = Depends(get_current_user)):
    """Proxy channels endpoint"""
    return await api_request("GET", "/channels")

@router.post("/api/proxy/channels")
@router.post("/webapi/proxy/channels")
@require_permission(CONFIG_WRITE)
async def proxy_create_channel(request: Request):
    """Proxy POST to create channel"""
    data = await request.json()
    return await api_request("POST", "/channels", data=data)

@router.get("/api/proxy/channels/{channel_id}")
@router.get("/webapi/proxy/channels/{channel_id}")
async def proxy_get_channel(channel_id: int, user: str = Depends(get_current_user)):
    """Proxy GET channel"""
    return await api_request("GET", f"/channels/{channel_id}")

@router.put("/api/proxy/channels/{channel_id}")
@router.put("/webapi/proxy/channels/{channel_id}")
@router.patch("/api/proxy/channels/{channel_id}")
@router.patch("/webapi/proxy/channels/{channel_id}")
@require_permission(CONFIG_WRITE)
async def proxy_update_channel(request: Request, channel_id: int):
    """Proxy PATCH to update channel"""
    try:
        data = await request.json()
        result = await api_request("PATCH", f"/channels/{channel_id}", data=data)
        return result
    except Exception as e:
        logger.error(f"Error updating channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/proxy/channels/{channel_id}")
@router.delete("/webapi/proxy/channels/{channel_id}")
@require_permission(CONFIG_WRITE)
async def proxy_delete_channel(request: Request, channel_id: int):
    """Proxy DELETE channel"""
    try:
        result = await api_request("DELETE", f"/channels/{channel_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting channel: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/proxy/channels/{channel_id}/test")
@router.post("/webapi/proxy/channels/{channel_id}/test")
@require_permission(CONFIG_WRITE)
async def proxy_test_channel(request: Request, channel_id: int):
    """Proxy POST to test channel"""
    data = await request.json()
    return await api_request("POST", f"/channels/{channel_id}/test", data=data)

@router.post("/api/proxy/channels/{channel_id}/enable")
@router.post("/webapi/proxy/channels/{channel_id}/enable")
@require_permission(CONFIG_WRITE)
async def proxy_enable_channel(request: Request, channel_id: int):
    """Proxy POST to enable channel"""
    return await api_request("POST", f"/channels/{channel_id}/enable")

@router.post("/api/proxy/channels/{channel_id}/disable")
@router.post("/webapi/proxy/channels/{channel_id}/disable")
@require_permission(CONFIG_WRITE)
async def proxy_disable_channel(request: Request, channel_id: int):
    """Proxy POST to disable channel"""
    return await api_request("POST", f"/channels/{channel_id}/disable")

@router.get("/api/proxy/messages")
@router.get("/webapi/proxy/messages")
async def proxy_messages(offset: int = 0, limit: int = 100, status: str = None, user: str = Depends(get_current_user)):
    """Proxy messages endpoint"""
    params = {"offset": offset, "limit": limit}
    if status:
        params["status"] = status
    return await api_request("GET", "/messages", params=params)

@router.post("/api/proxy/messages")
@router.post("/webapi/proxy/messages")
async def proxy_create_message(request: Request, user: str = Depends(get_current_user)):
    """Proxy message creation for the monorepo UI."""
    data = await request.json()
    if not data.get("created_by"):
        data["created_by"] = user
    return await api_request("POST", "/messages", data=data)


# Dashboard with left menu layout

async def dashboard(request: Request, user: str = Depends(get_current_user)):
    """Display dashboard with left menu"""
    return _ui_index_response()
    content = """
    <style>
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: var(--bg-secondary);
            padding: 25px;
            border-radius: 10px;
            border: 1px solid var(--border);
        }
        .stat-label {
            color: var(--text-secondary);
            font-size: 14px;
            margin-bottom: 8px;
        }
        .stat-value {
            color: var(--primary);
            font-size: 32px;
            font-weight: 600;
        }
        .section {
            margin-bottom: 20px;
        }
        .section h2 {
            color: var(--text-primary);
            margin-bottom: 20px;
            font-size: 20px;
        }
        .status {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }
        .status-queued { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
        .status-sent { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .status-failed { background: rgba(239, 68, 68, 0.2); color: #f87171; }
        .loading {
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
        }
        .grid-links {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
    </style>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Messages</div>
            <div class="stat-value" id="total-messages">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Queue Depth</div>
            <div class="stat-value" id="queue-depth">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Active Channels</div>
            <div class="stat-value" id="active-channels">-</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">System Status</div>
            <div class="stat-value" id="system-status" style="font-size: 24px;">⏳</div>
        </div>
    </div>

    <div class="card section">
        <h2>Recent Messages</h2>
        <div id="messages-table">
            <div class="loading">Loading messages...</div>
        </div>
    </div>

    <div class="card section">
        <h2>Active Channels</h2>
        <div id="channels-table">
            <div class="loading">Loading channels...</div>
        </div>
    </div>

    <script>
        async function fetchWithAuth(url) {
            const response = await fetch(url);
            if (!response.ok) throw new Error('API request failed');
            return response.json();
        }

        async function loadDashboard() {
            try {
                const status = await fetch('/webapi/proxy/status');
                const statusData = await status.json();
                document.getElementById('queue-depth').textContent = statusData.queue_depth || 0;
                document.getElementById('active-channels').textContent = Object.keys(statusData.channels || {}).length;
                document.getElementById('system-status').textContent = '✅';

                const health = await fetch('/webapi/proxy/health');

                try {
                    const messages = await fetch('/webapi/proxy/messages?limit=1');
                    const messagesData = await messages.json();
                    document.getElementById('total-messages').textContent = messagesData.total || 0;
                } catch (e) {
                    document.getElementById('total-messages').textContent = '-';
                }

                const channels = await fetch('/webapi/proxy/channels');
                const channelsData = await channels.json();
                renderChannels(channelsData);

            } catch (error) {
                console.error('Failed to load dashboard:', error);
                document.getElementById('system-status').textContent = '❌';
            }
        }

        function renderChannels(channels) {
            const html = `
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>Circuit State</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${channels.map(ch => `
                            <tr>
                                <td>${ch.name}</td>
                                <td>${ch.type}</td>
                                <td>
                                    <span class="status ${ch.enabled ? 'status-sent' : 'status-failed'}">
                                        ${ch.enabled ? 'Enabled' : 'Disabled'}
                                    </span>
                                </td>
                                <td>${ch.circuit_state}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
            document.getElementById('channels-table').innerHTML = html;
        }

        loadDashboard();
        setInterval(loadDashboard, 10000);
    </script>
"""
    html = get_base_layout("Dashboard", "dashboard", content, user)
    return HTMLResponse(content=html)


# API docs redirect
# Status page - Comprehensive server status

async def view_users(request: Request, user: str = Depends(get_current_user), limit: int = 50, offset: int = 0):
    """View users page with statistics, select/delete, disable functionality, pagination"""
    return _ui_index_response()
    try:
        # Get user permissions
        user_data, checker = await get_user_with_permissions(request)

        # Get users from API server (API max limit is 1000)
        result = await api_request("GET", _api_target_path("/users"), params={"limit": 1000})  # Get all for filtering (max 1000)
        all_users = result.get("items", [])

        # Filter out system users (user_type='system')
        all_users_filtered = [u for u in all_users if u.get("user_type", "real") != "system"]

        # Apply pagination
        total_users = len(all_users_filtered)
        users = all_users_filtered[offset:offset + limit]

        # Get statistics for each user
        user_stats = {}
        for u in users:
            stats = await get_user_stats(u.get("id"), u.get("username", ""))
            user_stats[u.get("id")] = stats

        # Build table rows with statistics
        table_rows = []
        for u in users:
            stats = user_stats.get(u.get("id"), {})
            msg_count = stats.get("message_count", 0)
            last_msg_id = stats.get("last_message_id")
            last_msg_date = stats.get("last_message_date", "")
            groups = stats.get("groups", [])
            ", ".join(groups[:3]) + ("..." if len(groups) > 3 else "")

            enabled_status = "✅" if u.get("enabled", True) else "❌"
            enabled_class = "status-sent" if u.get("enabled", True) else "status-failed"

            last_msg_link = f'<a href="/messages/{last_msg_id}" class="btn btn-small btn-secondary">View</a>' if last_msg_id else "None"
            groups_link = f'<a href="/groups?user={u.get("id")}" class="btn btn-small btn-secondary">{len(groups)} groups</a>' if groups else "None"

            table_rows.append(f'''
            <tr data-user-id="{u.get("id")}">
                <td><input type="checkbox" class="user-checkbox" value="{u.get("id")}"></td>
                <td>{u.get("id", "")}</td>
                <td>{u.get("username", "")}</td>
                <td>{u.get("email", "")}</td>
                <td>{u.get("display_name", "")}</td>
                <td><span class="status {enabled_class}">{enabled_status}</span></td>
                <td>{msg_count}</td>
                <td>{last_msg_date[:19] if last_msg_date else "Never"}</td>
                <td>{last_msg_link}</td>
                <td>{groups_link}</td>
                <td>{u.get("language", "en")}</td>
                <td>{u.get("preferred_channel", "")}</td>
                <td>
                    <a href="/users/{u.get("id", "")}/edit" class="btn btn-small btn-primary">Edit</a>
                    <a href="/users/{u.get("id", "")}/view" class="btn btn-small btn-secondary">View</a>
                    <button onclick="toggleUserEnabled({u.get("id")}, {str(u.get("enabled", True)).lower()})" class="btn btn-small {'btn-danger' if u.get('enabled') else 'btn-success'}">{'Disable' if u.get('enabled') else 'Enable'}</button>
                </td>
            </tr>
            ''')

        content = f"""
    <style>
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .action-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .search-box {{
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .select-all {{
            margin-right: 10px;
        }}
        .status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-sent {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .status-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        .pagination-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .pagination-info {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .limit-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .limit-selector select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .pagination-buttons {{
            display: flex;
            gap: 10px;
        }}
    </style>

    <div class="page-header">
        <h2>Users ({total_users} total, showing {len(users)} on this page)</h2>
        <div style="display: flex; gap: 10px;">
            <a href="/admin/api-keys" class="btn btn-secondary">🔑 Manage API Keys</a>
            <a href="/users/add" class="btn btn-primary">➕ Create User</a>
        </div>
    </div>

    <div class="action-bar">
        <input type="checkbox" class="select-all" onchange="selectAllUsers(this)">
        <input type="text" class="search-box" placeholder="Search users..." onkeyup="filterUsers(this.value)">
        <button onclick="deleteSelectedUsers()" class="btn btn-danger">Delete Selected</button>
        <button onclick="enableSelectedUsers()" class="btn btn-success">Enable Selected</button>
        <button onclick="disableSelectedUsers()" class="btn btn-secondary">Disable Selected</button>
    </div>

    <div class="card">
        <div class="table-container">
            <table id="users-table">
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" class="select-all-header" onchange="selectAllUsers(this)"></th>
                        <th>ID</th>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Display Name</th>
                        <th>Enabled</th>
                        <th># Messages</th>
                        <th>Last Message</th>
                        <th>View Message</th>
                        <th>Groups</th>
                        <th>Language</th>
                        <th>Channel</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <div class="pagination-info">
                Showing {offset + 1} to {min(offset + limit, total_users)} of {total_users} users
            </div>
            <div class="limit-selector">
                <label>Items per page:</label>
                <select id="limit-select" onchange="changeLimit()">
                    <option value="25" {'selected' if limit == 25 else ''}>25</option>
                    <option value="50" {'selected' if limit == 50 else ''}>50</option>
                    <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    <option value="200" {'selected' if limit == 200 else ''}>200</option>
                </select>
            </div>
            <div class="pagination-buttons">
                <button onclick="changePage({max(0, offset - limit)})" class="btn btn-secondary" {'disabled' if offset == 0 else ''}>Previous</button>
                <button onclick="changePage({offset + limit})" class="btn btn-secondary" {'disabled' if offset + limit >= total_users else ''}>Next</button>
            </div>
        </div>
    </div>

    <script>
        function changePage(newOffset) {{
            const limit = document.getElementById('limit-select').value;
            window.location.href = `/users?limit=${{limit}}&offset=${{newOffset}}`;
        }}

        function changeLimit() {{
            const limit = document.getElementById('limit-select').value;
            window.location.href = `/users?limit=${{limit}}&offset=0`;
        }}

        function selectAllUsers(checkbox) {{
            const checkboxes = document.querySelectorAll('.user-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }}

        function filterUsers(query) {{
            const rows = document.querySelectorAll('#users-table tbody tr');
            const lowerQuery = query.toLowerCase();
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(lowerQuery) ? '' : 'none';
            }});
        }}

        function getSelectedUserIds() {{
            const checkboxes = document.querySelectorAll('.user-checkbox:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        }}

        async function deleteSelectedUsers() {{
            const ids = getSelectedUserIds();
            if (ids.length === 0) {{
                alert('Please select users to delete');
                return;
            }}
            if (!confirm(`Delete ${{ids.length}} user(s)?`)) return;

            for (const id of ids) {{
                try {{
                    await fetch(`/webapi/proxy/users/${{id}}`, {{ method: 'DELETE' }});
                }} catch (e) {{
                    console.error('Failed to delete user:', e);
                }}
            }}
            location.reload();
        }}

        async function toggleUserEnabled(userId, currentlyEnabled) {{
            const newStatus = !currentlyEnabled;
            try {{
                await fetch(`/webapi/proxy/users/${{userId}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: newStatus }})
                }});
                location.reload();
            }} catch (e) {{
                alert('Failed to update user: ' + e.message);
            }}
        }}

        async function enableSelectedUsers() {{
            const ids = getSelectedUserIds();
            for (const id of ids) {{
                await fetch(`/webapi/proxy/users/${{id}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: true }})
                }});
            }}
            location.reload();
        }}

        async function disableSelectedUsers() {{
            const ids = getSelectedUserIds();
            for (const id of ids) {{
                await fetch(`/webapi/proxy/users/${{id}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: false }})
                }});
            }}
            location.reload();
        }}
    </script>
"""
        html = get_base_layout("Users", "users", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@require_permission(CONFIG_WRITE)
async def view_api_keys(request: Request, user: str = Depends(get_current_user)):
    """API key management page."""
    return _ui_index_response()
    keys_result = await api_request("GET", "/admin/api-keys")
    items = keys_result.get("items", []) if isinstance(keys_result, dict) else []
    empty_rows = "<tr><td colspan='6'>No API keys found</td></tr>"
    rows = "".join(
        f"""
        <tr>
            <td>{item.get('api_key_id', '')}</td>
            <td>{item.get('owner_user_id', '')}</td>
            <td>{item.get('key_prefix', '')}</td>
            <td>{item.get('status', '')}</td>
            <td>{item.get('expires_at', '') or 'Never'}</td>
            <td><button class="btn btn-danger btn-small" onclick="revokeKey('{item.get('api_key_id', '')}')">Revoke</button></td>
        </tr>
        """
        for item in items
    )
    content = f"""
    <div class="page-header">
        <h2>API Keys ({len(items)} total)</h2>
    </div>
    <div class="card" style="margin-bottom: 20px;">
        <h3>Create API Key</h3>
        <form onsubmit="createKey(event)" style="display: grid; gap: 12px; max-width: 520px;">
            <input id="owner_user_id" placeholder="Owner user id" required />
            <input id="key_prefix" placeholder="Key prefix (optional)" />
            <input id="ttl_days" type="number" min="1" placeholder="TTL days (optional)" />
            <button class="btn btn-primary" type="submit">Create API Key</button>
        </form>
        <div id="api-key-create-result" style="margin-top: 15px;"></div>
    </div>
    <div class="card">
        <h3>Existing API Keys</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Owner</th>
                    <th>Prefix</th>
                    <th>Status</th>
                    <th>Expires</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>{rows or empty_rows}</tbody>
        </table>
    </div>
    <script>
        async function createKey(event) {{
            event.preventDefault();
            const payload = {{
                owner_user_id: document.getElementById('owner_user_id').value.trim(),
                key_prefix: document.getElementById('key_prefix').value.trim() || null,
                ttl_days: document.getElementById('ttl_days').value ? Number(document.getElementById('ttl_days').value) : null,
            }};
            const response = await fetch('/webapi/proxy/admin/api-keys', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(payload),
            }});
            const result = await response.json();
            const resultDiv = document.getElementById('api-key-create-result');
            if (response.ok) {{
                resultDiv.innerHTML = `<div class="success">Created API key: <code>${{result.api_key}}</code></div>`;
                setTimeout(() => window.location.reload(), 1000);
            }} else {{
                resultDiv.innerHTML = `<div class="error">${{result.detail || 'Failed to create API key'}}</div>`;
            }}
        }}

        async function revokeKey(keyId) {{
            const response = await fetch(`/webapi/proxy/admin/api-keys/${{keyId}}`, {{ method: 'DELETE' }});
            if (response.ok) {{
                window.location.reload();
                return;
            }}
            const result = await response.json();
            alert(result.detail || 'Failed to revoke API key');
        }}
    </script>
    """
    html = get_base_layout("API Keys", "api-keys", content, user)
    return HTMLResponse(content=html)


# Helper function to get group statistics

async def view_groups(request: Request, user: str = Depends(get_current_user), limit: int = 50, offset: int = 0):
    """View groups page with statistics, select/delete, enable/disable functionality, pagination"""
    return _ui_index_response()
    try:
        # Get groups from API server
        result = await api_request("GET", _api_target_path("/groups"), params={"enabled_only": False})
        all_groups = result.get("items", [])

        # Apply pagination
        total_groups = len(all_groups)
        groups = all_groups[offset:offset + limit]

        # Get statistics for each group
        group_stats = {}
        for g in groups:
            stats = await get_group_stats(g.get("id"), g.get("name", ""))
            group_stats[g.get("id")] = stats

        # Build table rows with statistics
        table_rows = []
        for g in groups:
            stats = group_stats.get(g.get("id"), {})
            member_count = stats.get("member_count", 0)
            msg_count = stats.get("message_count", 0)
            last_msg_id = stats.get("last_message_id")
            last_msg_date = stats.get("last_message_date", "")

            enabled_status = "✅" if g.get("enabled", True) else "❌"
            enabled_class = "status-sent" if g.get("enabled", True) else "status-failed"

            last_msg_link = f'<a href="/messages/{last_msg_id}" class="btn btn-small btn-secondary">View</a>' if last_msg_id else "None"
            f'<a href="/groups/{g.get("id")}/edit" class="btn btn-small btn-secondary">{member_count} members</a>'

            table_rows.append(f'''
            <tr data-group-id="{g.get("id")}">
                <td><input type="checkbox" class="group-checkbox" value="{g.get("id")}"></td>
                <td>{g.get("id", "")}</td>
                <td><a href="/groups/{g.get("id")}/edit" style="color: var(--primary); text-decoration: none;">{g.get("name", "")}</a></td>
                <td>{g.get("description", "")}</td>
                <td><span class="status {enabled_class}">{enabled_status}</span></td>
                <td>{member_count}</td>
                <td>{msg_count}</td>
                <td>{last_msg_date[:19] if last_msg_date else "Never"}</td>
                <td>{last_msg_link}</td>
                <td>{g.get("language", "")}</td>
                <td>
                    <a href="/groups/{g.get("id")}/edit" class="btn btn-small btn-primary">Edit</a>
                    <button onclick="toggleGroupEnabled({g.get("id")}, {str(g.get("enabled", True)).lower()})" class="btn btn-small {'btn-danger' if g.get('enabled') else 'btn-success'}">{'Disable' if g.get('enabled') else 'Enable'}</button>
                </td>
            </tr>
            ''')

        content = f"""
    <style>
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .action-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .search-box {{
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-sent {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .status-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        .pagination-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .pagination-info {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .limit-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .limit-selector select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .pagination-buttons {{
            display: flex;
            gap: 10px;
        }}
    </style>

    <div class="page-header">
        <h2>Groups ({total_groups} total, showing {len(groups)} on this page)</h2>
        <a href="/groups/add" class="btn btn-primary">➕ Create Group</a>
    </div>

    <div class="action-bar">
        <input type="checkbox" class="select-all" onchange="selectAllGroups(this)">
        <input type="text" class="search-box" placeholder="Search groups..." onkeyup="filterGroups(this.value)">
        <button onclick="deleteSelectedGroups()" class="btn btn-danger">Delete Selected</button>
        <button onclick="enableSelectedGroups()" class="btn btn-success">Enable Selected</button>
        <button onclick="disableSelectedGroups()" class="btn btn-secondary">Disable Selected</button>
    </div>

    <div class="card">
        <div class="table-container">
            <table id="groups-table">
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" class="select-all-header" onchange="selectAllGroups(this)"></th>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Description</th>
                        <th>Enabled</th>
                        <th>Members</th>
                        <th># Messages</th>
                        <th>Last Message</th>
                        <th>View Message</th>
                        <th>Language</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <div class="pagination-info">
                Showing {offset + 1} to {min(offset + limit, total_groups)} of {total_groups} groups
            </div>
            <div class="limit-selector">
                <label>Items per page:</label>
                <select id="limit-select" onchange="changeLimit()">
                    <option value="25" {'selected' if limit == 25 else ''}>25</option>
                    <option value="50" {'selected' if limit == 50 else ''}>50</option>
                    <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    <option value="200" {'selected' if limit == 200 else ''}>200</option>
                </select>
            </div>
            <div class="pagination-buttons">
                <button onclick="changePage({max(0, offset - limit)})" class="btn btn-secondary" {'disabled' if offset == 0 else ''}>Previous</button>
                <button onclick="changePage({offset + limit})" class="btn btn-secondary" {'disabled' if offset + limit >= total_groups else ''}>Next</button>
            </div>
        </div>
    </div>

    <script>
        function changePage(newOffset) {{
            const limit = document.getElementById('limit-select').value;
            window.location.href = `/groups?limit=${{limit}}&offset=${{newOffset}}`;
        }}

        function changeLimit() {{
            const limit = document.getElementById('limit-select').value;
            window.location.href = `/groups?limit=${{limit}}&offset=0`;
        }}

        function selectAllGroups(checkbox) {{
            const checkboxes = document.querySelectorAll('.group-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }}

        function filterGroups(query) {{
            const rows = document.querySelectorAll('#groups-table tbody tr');
            const lowerQuery = query.toLowerCase();
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(lowerQuery) ? '' : 'none';
            }});
        }}

        function getSelectedGroupIds() {{
            const checkboxes = document.querySelectorAll('.group-checkbox:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        }}

        async function deleteSelectedGroups() {{
            const ids = getSelectedGroupIds();
            if (ids.length === 0) {{
                alert('Please select groups to delete');
                return;
            }}
            if (!confirm(`Delete ${{ids.length}} group(s)?`)) return;

            for (const id of ids) {{
                try {{
                    await fetch(`/webapi/proxy/groups/${{id}}`, {{ method: 'DELETE' }});
                }} catch (e) {{
                    console.error('Failed to delete group:', e);
                }}
            }}
            location.reload();
        }}

        async function toggleGroupEnabled(groupId, currentlyEnabled) {{
            const newStatus = !currentlyEnabled;
            try {{
                await fetch(`/webapi/proxy/groups/${{groupId}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: newStatus }})
                }});
                location.reload();
            }} catch (e) {{
                alert('Failed to update group: ' + e.message);
            }}
        }}

        async function enableSelectedGroups() {{
            const ids = getSelectedGroupIds();
            for (const id of ids) {{
                await fetch(`/webapi/proxy/groups/${{id}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: true }})
                }});
            }}
            location.reload();
        }}

        async function disableSelectedGroups() {{
            const ids = getSelectedGroupIds();
            for (const id of ids) {{
                await fetch(`/webapi/proxy/groups/${{id}}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ enabled: false }})
                }});
            }}
            location.reload();
        }}
    </script>
"""
        html = get_base_layout("Groups", "groups", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading groups: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# Channels page with left menu, definition screen, select/delete

async def view_channels(request: Request, user: str = Depends(get_current_user), limit: int = 50, offset: int = 0):
    """View channels page with definition screen, select/delete functionality, pagination and scrolling"""
    return _ui_index_response()
    try:
        def _format_datetime(value):
            if value is None or value == "":
                return ""
            if isinstance(value, datetime):
                return value.isoformat(sep=" ", timespec="seconds")
            return str(value)

        # Get channels from API server
        all_channels = await api_request("GET", "/channels")

        # Apply pagination
        total_channels = len(all_channels)
        channels = all_channels[offset:offset + limit]

        # Get config-defined channels (from config.yaml/defaults.yaml)
        config_channels = set()
        try:
            config_data = config.get("channels", {})
            for channel_type, channels_dict in config_data.items():
                for channel_name in channels_dict.keys():
                    config_channels.add(f"{channel_type}__{channel_name}")
        except Exception:
            pass

        # Get channel statistics (message count, last used) for all channels
        from ...database.db_manager import get_db_manager
        db_uri = _require_config(config.get("db.uri"), "db.uri")
        db = get_db_manager(db_uri)
        channel_stats = {}
        for c in channels:
            channel_id = c.get("id")
            # Get message count and last used for this channel
            stats = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda cid=channel_id: db.fetchone(
                    """
                    SELECT
                        COUNT(DISTINCT message_id) as message_count,
                        MAX(created_at) as last_used
                    FROM deliveries
                    WHERE channel_id = ?
                    """,
                    (cid,)
                )
            )
            channel_stats[channel_id] = {
                "message_count": stats.get("message_count", 0) if stats and stats.get("message_count") is not None else 0,
                "last_used": stats.get("last_used", "") if stats and stats.get("last_used") else "Never"
            }

        # Build table rows
        table_rows = []
        for c in channels:
            channel_key = f"{c.get('type', '')}__{c.get('name', '')}"
            is_config_defined = channel_key in config_channels
            channel_id = c.get("id")
            stats = channel_stats.get(channel_id, {"message_count": 0, "last_used": "Never"})
            last_used_value = stats.get("last_used")
            if last_used_value in (None, "", "Never"):
                last_used_display = "Never"
            else:
                last_used_display = _format_datetime(last_used_value)[:19]
            created_at_display = _format_datetime(c.get("created_at"))[:19] if c.get("created_at") else ""

            enabled_status = "✅" if c.get("enabled") else "❌"
            enabled_class = "status-sent" if c.get("enabled") else "status-failed"

            table_rows.append(f'''
            <tr data-channel-id="{channel_id}" data-config-defined="{str(is_config_defined).lower()}">
                <td><input type="checkbox" class="channel-checkbox" value="{channel_id}" {'disabled' if is_config_defined else ''}></td>
                <td>{channel_id}</td>
                <td><a href="/channels/{channel_id}" style="color: var(--primary); text-decoration: none;">{c.get("name", "")}</a></td>
                <td>{c.get("type", "")}</td>
                <td><span class="status {enabled_class}">{enabled_status}</span></td>
                <td>{c.get("circuit_state", "closed")}</td>
                <td>{c.get("error_count", 0)}</td>
                <td><strong>{stats["message_count"]}</strong></td>
                <td>{last_used_display}</td>
                <td>{created_at_display}</td>
                <td>
                    <a href="/channels/{channel_id}" class="btn btn-small btn-primary">View</a>
                    {'<span style="color: var(--text-secondary); font-size: 12px;">Config</span>' if is_config_defined else ''}
                </td>
            </tr>
            ''')

        content = f"""
    <style>
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .action-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .search-box {{
            flex: 1;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-sent {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .status-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .pagination-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .pagination-info {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .limit-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .limit-selector select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .pagination-buttons {{
            display: flex;
            gap: 10px;
        }}
    </style>

    <div class="page-header">
        <h2>Channels ({total_channels} total, showing {len(channels)} on this page)</h2>
    </div>

    <div class="action-bar">
        <input type="checkbox" class="select-all" onchange="selectAllChannels(this)">
        <input type="text" class="search-box" placeholder="Search channels..." onkeyup="filterChannels(this.value)">
        <a href="/channels/add" class="btn btn-primary">Add Channel</a>
        <button onclick="deleteSelectedChannels()" class="btn btn-danger">Delete Selected</button>
    </div>

    <div class="card">
        <div class="table-container">
            <table id="channels-table">
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" class="select-all-header" onchange="selectAllChannels(this)"></th>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Enabled</th>
                        <th>Circuit State</th>
                        <th>Error Count</th>
                        <th>Message Count</th>
                        <th>Last Used</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <div class="pagination-info">
                Showing {offset + 1} to {min(offset + limit, total_channels)} of {total_channels} channels
            </div>
            <div class="limit-selector">
                <label>Items per page:</label>
                <select id="limit-select" onchange="changeLimit(this.value)">
                    <option value="25" {'selected' if limit == 25 else ''}>25</option>
                    <option value="50" {'selected' if limit == 50 else ''}>50</option>
                    <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    <option value="200" {'selected' if limit == 200 else ''}>200</option>
                </select>
            </div>
            <div class="pagination-buttons">
                <button onclick="changePage({max(0, offset - limit)})" class="btn btn-secondary" {'disabled' if offset == 0 else ''}>Previous</button>
                <button onclick="changePage({offset + limit})" class="btn btn-secondary" {'disabled' if offset + limit >= total_channels else ''}>Next</button>
            </div>
        </div>
    </div>

    <script>
        function selectAllChannels(checkbox) {{
            const checkboxes = document.querySelectorAll('.channel-checkbox:not(:disabled)');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }}

        function filterChannels(query) {{
            const rows = document.querySelectorAll('#channels-table tbody tr');
            const lowerQuery = query.toLowerCase();
            rows.forEach(row => {{
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(lowerQuery) ? '' : 'none';
            }});
        }}

        function getSelectedChannelIds() {{
            const checkboxes = document.querySelectorAll('.channel-checkbox:checked:not(:disabled)');
            return Array.from(checkboxes).map(cb => cb.value);
        }}

        async function deleteSelectedChannels() {{
            const ids = getSelectedChannelIds();
            if (ids.length === 0) {{
                alert('Please select channels to delete (config-defined channels cannot be deleted)');
                return;
            }}
            if (!confirm(`Delete ${{ids.length}} channel(s)?`)) return;

            for (const id of ids) {{
                try {{
                    await fetch(`/webapi/proxy/channels/${{id}}`, {{ method: 'DELETE' }});
                }} catch (e) {{
                    console.error('Failed to delete channel:', e);
                }}
            }}
            location.reload();
        }}

        function changeLimit(newLimit) {{
            const url = new URL(window.location);
            url.searchParams.set('limit', newLimit);
            url.searchParams.set('offset', '0');
            window.location = url;
        }}

        function changePage(newOffset) {{
            const url = new URL(window.location);
            url.searchParams.set('offset', newOffset);
            window.location = url;
        }}
    </script>
"""
        html = get_base_layout("Channels", "channels", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading channels: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# Channel creation page

async def add_channel_page(request: Request, user: str = Depends(get_current_user)):
    """Add new channel page"""
    return _ui_index_response()
    content = """
    <style>
        .form-container {
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 10px;
            max-width: 800px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
        }
        .form-group input,
        .form-group select,
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 14px;
            font-family: inherit;
        }
        .btn-submit {
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }
        .btn-submit:hover {
            background: var(--primary-hover);
        }
        .error {
            color: #e53e3e;
            margin-top: 10px;
            padding: 10px;
            background: rgba(229, 62, 62, 0.1);
            border-radius: 6px;
        }
        .success {
            color: #48bb78;
            margin-top: 10px;
            padding: 10px;
            background: rgba(72, 187, 120, 0.1);
            border-radius: 6px;
        }
    </style>

    <div class="card">
        <h2>Create Channel</h2>
        <div class="form-container">
            <form id="channel-form" onsubmit="createChannel(event)">
                <div class="form-group">
                    <label>Name *</label>
                    <input type="text" name="name" required />
                </div>
                <div class="form-group">
                    <label>Type *</label>
                    <select name="type" required>
                        <option value="loopback">loopback</option>
                        <option value="smtp">smtp</option>
                        <option value="sms">sms</option>
                        <option value="whatsapp">whatsapp</option>
                        <option value="chat_rest">chat_rest</option>
                        <option value="file">file</option>
                    </select>
                </div>
                <div class="form-group">
                    <label><input type="checkbox" name="enabled" checked /> Enabled</label>
                </div>
                <div class="form-group">
                    <label>Config JSON (optional)</label>
                    <textarea name="config_json" rows="6" placeholder='{"base_url": "http://localhost:8004"}'></textarea>
                </div>
                <div class="form-group">
                    <label>Limits JSON (optional)</label>
                    <textarea name="limits_json" rows="4" placeholder='{"rate_per_minute": 60}'></textarea>
                </div>
                <button type="submit" class="btn-submit">Create Channel</button>
                <div id="result" style="margin-top: 15px;"></div>
            </form>
        </div>
    </div>

    <script>
        function parseJsonField(value, fieldName) {
            if (!value) return null;
            try {
                return JSON.parse(value);
            } catch (e) {
                throw new Error(`Invalid JSON for ${fieldName}`);
            }
        }

        async function createChannel(event) {
            event.preventDefault();
            const form = event.target;
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '';

            try {
                const payload = {
                    name: form.name.value.trim(),
                    type: form.type.value,
                    enabled: form.enabled.checked
                };

                const configVal = parseJsonField(form.config_json.value.trim(), "config_json");
                const limitsVal = parseJsonField(form.limits_json.value.trim(), "limits_json");
                if (configVal) payload.config = configVal;
                if (limitsVal) payload.limits = limitsVal;

                const response = await fetch("/webapi/proxy/channels", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();
                if (response.ok) {
                    resultDiv.innerHTML = `<div class="success">✅ Channel created! <a href="/db/channels">Back to Channels</a></div>`;
                    form.reset();
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${data.detail || 'Unknown error'}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Request failed: ${error.message}</div>`;
            }
        }
    </script>
    """

    html = get_base_layout("Add Channel", "channels", content, user)
    return HTMLResponse(content=html)


# Channel definition screen

async def view_channel_definition(request: Request, channel_id: int, user: str = Depends(get_current_user)):
    """Channel definition screen - shows full channel configuration"""
    return _ui_index_response()
    try:
        channel = await api_request("GET", f"/channels/{channel_id}")

        # Parse config_json if present
        config_json = channel.get("config_json", "{}")
        try:
            import json
            config_data = json.loads(config_json) if config_json else {}
        except Exception:
            config_data = {}

        def _pretty_json(value):
            if value is None:
                return ""
            if isinstance(value, str):
                if value.strip() == "":
                    return ""
                try:
                    value = json.loads(value)
                except Exception:
                    return value
            try:
                return json.dumps(value, indent=2)
            except Exception:
                return str(value)

        config_json_value = _pretty_json(config_data)
        limits_json_value = _pretty_json(channel.get("limits_json"))
        restrictions_json_value = _pretty_json(channel.get("restrictions_json"))
        preferences_json_value = _pretty_json(channel.get("preferences_json"))

        # Get channel statistics (message count, last used)
        from ...database.db_manager import get_db_manager
        from ...database.repositories import DeliveryRepository
        db_uri = _require_config(config.get("db.uri"), "db.uri")
        db = get_db_manager(db_uri)
        DeliveryRepository(db)

        # Get deliveries for this channel to count messages and find last used
        deliveries = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: db.fetchall(
                """
                SELECT DISTINCT message_id, MAX(created_at) as last_used
                FROM deliveries
                WHERE channel_id = ?
                GROUP BY message_id
                ORDER BY last_used DESC
                LIMIT 100
                """,
                (channel_id,)
            )
        )

        message_count = len(deliveries) if deliveries else 0
        last_used = deliveries[0].get("last_used", "") if deliveries else "Never"

        # Get recent messages for this channel
        recent_messages = []
        if deliveries:
            message_ids = [d.get("message_id") for d in deliveries[:10]]
            if message_ids:
                from ...database.repositories import MessageRepository
                message_repo = MessageRepository(db)
                for msg_id in message_ids:
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, message_repo.get_by_id, msg_id
                    )
                    if msg:
                        recent_messages.append(msg)

        # Build recent messages links
        messages_html = ""
        if recent_messages:
            msg_rows = []
            for msg in recent_messages[:10]:
                msg_rows.append(f'''
                <tr>
                    <td><a href="/messages/{msg.get('id')}" style="color: var(--primary);">{msg.get('id')}</a></td>
                    <td>{msg.get('status', '')}</td>
                    <td>{msg.get('created_at', '')[:19] if msg.get('created_at') else ''}</td>
                    <td><a href="/messages/{msg.get('id')}" class="btn btn-small btn-primary">View</a></td>
                </tr>
                ''')
            messages_html = f"""
        <h3 style="margin-top: 30px;">Recent Messages ({message_count} total)</h3>
        <div class="card">
            <table>
                <thead>
                    <tr>
                        <th>Message ID</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(msg_rows)}
                </tbody>
            </table>
            <div style="margin-top: 15px;">
                <a href="/messages?channel_id={channel_id}" class="btn btn-primary">View All Messages for This Channel</a>
            </div>
        </div>
        """
        else:
            messages_html = """
        <h3 style="margin-top: 30px;">Messages</h3>
        <div class="card">
            <p style="color: var(--text-secondary);">No messages sent through this channel yet.</p>
        </div>
        """

        script = """
    <script>
        function parseJsonField(value, fieldName) {
            if (!value) return null;
            try {
                return JSON.parse(value);
            } catch (e) {
                throw new Error("Invalid JSON for " + fieldName);
            }
        }

        async function updateChannel(event) {
            event.preventDefault();
            const form = event.target;
            const resultDiv = document.getElementById('update-result');
            resultDiv.innerHTML = '';

            try {
                const payload = {
                    enabled: form.enabled.checked
                };
                const configVal = parseJsonField(form.config_json.value.trim(), "config_json");
                const limitsVal = parseJsonField(form.limits_json.value.trim(), "limits_json");
                const restrictionsVal = parseJsonField(form.restrictions_json.value.trim(), "restrictions_json");
                const preferencesVal = parseJsonField(form.preferences_json.value.trim(), "preferences_json");

                if (configVal !== null) payload.config_json = configVal;
                if (limitsVal !== null) payload.limits_json = limitsVal;
                if (restrictionsVal !== null) payload.restrictions_json = restrictionsVal;
                if (preferencesVal !== null) payload.preferences_json = preferencesVal;

                const response = await fetch(`/webapi/proxy/channels/__CHANNEL_ID__`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await response.json();
                if (response.ok) {
                    resultDiv.innerHTML = '<div class="success">✅ Channel updated</div>';
                } else {
                    resultDiv.innerHTML = '<div class="error">❌ Error: ' + (data.detail || "Unknown error") + '</div>';
                }
            } catch (error) {
                resultDiv.innerHTML = '<div class="error">❌ Request failed: ' + error.message + '</div>';
            }
        }

        async function enableChannel() {
            const resultDiv = document.getElementById('action-result');
            resultDiv.innerHTML = '';
            const response = await fetch(`/webapi/proxy/channels/__CHANNEL_ID__/enable`, { method: 'POST' });
            resultDiv.innerHTML = response.ok ? "✅ Enabled" : "❌ Enable failed";
        }

        async function disableChannel() {
            const resultDiv = document.getElementById('action-result');
            resultDiv.innerHTML = '';
            const response = await fetch(`/webapi/proxy/channels/__CHANNEL_ID__/disable`, { method: 'POST' });
            resultDiv.innerHTML = response.ok ? "✅ Disabled" : "❌ Disable failed";
        }

        async function testChannel() {
            const destination = prompt("Destination for test send:");
            if (!destination) return;
            const resultDiv = document.getElementById('action-result');
            resultDiv.innerHTML = 'Testing...';
            const response = await fetch(`/webapi/proxy/channels/__CHANNEL_ID__/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ destination })
            });
            const data = await response.json().catch(() => ({}));
            resultDiv.innerHTML = response.ok ? "✅ Test sent" : ("❌ Test failed: " + (data.detail || "Unknown error"));
        }
    </script>
"""
        script = script.replace("__CHANNEL_ID__", str(channel_id))

        content = f"""
    <div class="card">
        <h2>Channel Definition: {channel.get("name")}</h2>
        <table>
            <tr><th>ID</th><td>{channel.get("id")}</td></tr>
            <tr><th>Name</th><td>{channel.get("name")}</td></tr>
            <tr><th>Type</th><td>{channel.get("type")}</td></tr>
            <tr><th>Enabled</th><td>{'✅ Yes' if channel.get("enabled") else '❌ No'}</td></tr>
            <tr><th>Circuit State</th><td>{channel.get("circuit_state", "closed")}</td></tr>
            <tr><th>Error Count</th><td>{channel.get("error_count", 0)}</td></tr>
            <tr><th>Message Count</th><td><strong>{message_count}</strong></td></tr>
            <tr><th>Last Used</th><td>{last_used[:19] if last_used != "Never" else "Never"}</td></tr>
            <tr><th>Created</th><td>{channel.get("created_at", "")}</td></tr>
            <tr><th>Updated</th><td>{channel.get("updated_at", "")}</td></tr>
        </table>

        <h3 style="margin-top: 30px;">Configuration</h3>
        <div class="card" style="background: var(--bg-tertiary);">
            <pre style="white-space: pre-wrap; font-family: monospace; font-size: 12px;">{config_json_value or "{}"}</pre>
        </div>

        <h3 style="margin-top: 30px;">Admin Actions</h3>
        <div class="card">
            <button class="btn btn-primary" onclick="enableChannel()">Enable</button>
            <button class="btn btn-secondary" onclick="disableChannel()">Disable</button>
            <button class="btn btn-secondary" onclick="testChannel()">Test Send</button>
            <div id="action-result" style="margin-top: 10px;"></div>
        </div>

        <h3 style="margin-top: 30px;">Update Channel</h3>
        <div class="card">
            <form id="channel-update-form" onsubmit="updateChannel(event)">
                <div class="form-group">
                    <label><input type="checkbox" name="enabled" {'checked' if channel.get("enabled") else ''} /> Enabled</label>
                </div>
                <div class="form-group">
                    <label>Config JSON</label>
                    <textarea name="config_json" rows="6">{config_json_value}</textarea>
                </div>
                <div class="form-group">
                    <label>Limits JSON</label>
                    <textarea name="limits_json" rows="4">{limits_json_value}</textarea>
                </div>
                <div class="form-group">
                    <label>Restrictions JSON</label>
                    <textarea name="restrictions_json" rows="4">{restrictions_json_value}</textarea>
                </div>
                <div class="form-group">
                    <label>Preferences JSON</label>
                    <textarea name="preferences_json" rows="4">{preferences_json_value}</textarea>
                </div>
                <button type="submit" class="btn btn-primary">Update Channel</button>
                <div id="update-result" style="margin-top: 10px;"></div>
            </form>
        </div>

        {messages_html}

        <div style="margin-top: 20px;">
            <a href="/channels" class="btn btn-secondary">Back to Channels</a>
        </div>
    </div>
    {script}
"""
        html = get_base_layout(f"Channel: {channel.get('name')}", "channels", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error viewing channel: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# View individual message page

async def view_messages(request: Request, user: str = Depends(get_current_user),
                        sort_by: str = "created_at", sort_order: str = "desc",
                        search: str = "", limit: int = 50, offset: int = 0):
    """View messages page with comprehensive functionality and pagination"""
    return _ui_index_response()
    try:
        # Get messages from API server - use API max limit of 1000
        params = {"limit": 1000, "offset": 0}
        result = await api_request("GET", "/messages", params=params, timeout=30.0)
        all_messages = result.get("items", []) if result else []
        if not isinstance(all_messages, list):
            all_messages = []
        result.get("total", len(all_messages)) if result else len(all_messages)

        # Filter by search term
        if search:
            search_lower = search.lower()
            all_messages = [m for m in all_messages if
                          search_lower in str(m.get("id", "")).lower() or
                          search_lower in str(m.get("guid", "")).lower() or
                          search_lower in str(m.get("created_by", "")).lower() or
                          search_lower in str(m.get("status", "")).lower() or
                          search_lower in str(m.get("audience_type", "")).lower()]

        # Sort messages
        reverse_order = (sort_order == "desc")
        if sort_by == "id":
            all_messages.sort(key=lambda x: x.get("id", 0), reverse=reverse_order)
        elif sort_by == "created_at":
            all_messages.sort(key=lambda x: x.get("created_at", ""), reverse=reverse_order)
        elif sort_by == "status":
            all_messages.sort(key=lambda x: x.get("status", ""), reverse=reverse_order)
        elif sort_by == "created_by":
            all_messages.sort(key=lambda x: x.get("created_by", ""), reverse=reverse_order)

        # Apply pagination after filtering and sorting
        total = len(all_messages)
        messages = all_messages[offset:offset + limit]

        # Get delivery counts for each message (only for paginated messages) - batch with timeout
        message_delivery_counts = {}
        for m in messages:
            try:
                deliveries_result = await api_request("GET", f"/messages/{m.get('id')}/deliveries", timeout=5.0)
                deliveries = deliveries_result.get("items", []) if isinstance(deliveries_result, dict) else []
                message_delivery_counts[m.get("id")] = len(deliveries)
            except Exception as e:
                logger.warning(f"Failed to get delivery count for message {m.get('id')}: {e}")
                message_delivery_counts[m.get("id")] = 0

        # Build table rows
        table_rows = []
        for m in messages:
            delivery_count = message_delivery_counts.get(m.get("id"), 0)
            ttl_at = m.get("ttl_at", "")
            ttl_display = ttl_at[:19] if ttl_at else "Never"
            ttl_hours = m.get("ttl_hours", 24)

            status_class = m.get("status", "").lower().replace("_", "-")

            # Get recipients count from message data if available, otherwise default to 0
            # Don't make individual API calls - too slow
            recipients_count = len(m.get("destinations", [])) if isinstance(m.get("destinations"), list) else 0

            table_rows.append(f'''
            <tr data-message-id="{m.get("id")}">
                <td><input type="checkbox" class="message-checkbox" value="{m.get("id")}"></td>
                <td>{m.get("id", "")}</td>
                <td><code style="font-size: 11px;">{m.get("guid", "")[:8] if m.get("guid") else "N/A"}</code></td>
                <td><span class="status status-{status_class}">{m.get("status", "")}</span></td>
                <td>{m.get("created_by", "")}</td>
                <td>{recipients_count}</td>
                <td>{m.get("audience_type", "")}</td>
                <td>{ttl_hours}h</td>
                <td>{ttl_display}</td>
                <td>{m.get("created_at", "")[:19] if m.get("created_at") else ""}</td>
                <td>{delivery_count}</td>
                <td>
                    <a href="/messages/{m.get("id", "")}" class="btn btn-small btn-primary">View</a>
                    <a href="/deliveries?message_id={m.get("id", "")}" class="btn btn-small btn-secondary">Deliveries</a>
                    {f'<a href="/messages/{m.get("id", "")}/cancel" class="btn btn-small btn-danger">Cancel</a>' if m.get("status") in ["queued", "processing"] else ''}
                </td>
            </tr>
            ''')

        content = f"""
    <style>
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .action-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            flex-wrap: wrap;
        }}
        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .sort-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-queued {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
        .status-processing {{ background: rgba(251, 191, 36, 0.2); color: #fbbf24; }}
        .status-completed {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .status-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        th.sortable {{
            cursor: pointer;
            user-select: none;
        }}
        th.sortable:hover {{
            background: var(--bg-tertiary);
        }}
        .pagination-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .pagination-info {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .limit-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .limit-selector select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .pagination-buttons {{
            display: flex;
            gap: 10px;
        }}
    </style>

    <div class="page-header">
        <h2>Messages ({total} total, showing {len(messages)} on this page)</h2>
        <a href="/messages/create" class="btn btn-primary">➕ Create Message</a>
    </div>

    <div class="action-bar">
        <input type="checkbox" class="select-all" onchange="selectAllMessages(this)">
        <input type="text" class="search-box" placeholder="Search messages..." value="{search}" onkeyup="searchMessages(this.value)">
        <div class="sort-controls">
            <label>Sort by:</label>
            <select id="sort-by" onchange="applySort()" style="padding: 6px; border-radius: 4px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border);">
                <option value="created_at" {'selected' if sort_by == 'created_at' else ''}>Created Date</option>
                <option value="id" {'selected' if sort_by == 'id' else ''}>ID</option>
                <option value="status" {'selected' if sort_by == 'status' else ''}>Status</option>
                <option value="created_by" {'selected' if sort_by == 'created_by' else ''}>Sender</option>
            </select>
            <select id="sort-order" onchange="applySort()" style="padding: 6px; border-radius: 4px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border);">
                <option value="desc" {'selected' if sort_order == 'desc' else ''}>Descending</option>
                <option value="asc" {'selected' if sort_order == 'asc' else ''}>Ascending</option>
            </select>
        </div>
        <button onclick="deleteSelectedMessages()" class="btn btn-danger">Delete Selected</button>
    </div>

    <div class="card">
        <div class="table-container">
            <table id="messages-table">
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" class="select-all-header" onchange="selectAllMessages(this)"></th>
                        <th class="sortable" onclick="sortBy('id')">ID ↕</th>
                        <th>GUID</th>
                        <th class="sortable" onclick="sortBy('status')">Status ↕</th>
                        <th class="sortable" onclick="sortBy('created_by')">Sender ↕</th>
                        <th>Recipients</th>
                        <th>Audience</th>
                        <th>TTL (hours)</th>
                        <th>TTL At</th>
                        <th class="sortable" onclick="sortBy('created_at')">Created ↕</th>
                        <th>Deliveries</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <div class="pagination-info">
                Showing {offset + 1} to {min(offset + limit, total)} of {total} messages
            </div>
            <div class="limit-selector">
                <label>Items per page:</label>
                <select id="limit-select" onchange="changeLimit()">
                    <option value="25" {'selected' if limit == 25 else ''}>25</option>
                    <option value="50" {'selected' if limit == 50 else ''}>50</option>
                    <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    <option value="200" {'selected' if limit == 200 else ''}>200</option>
                </select>
            </div>
            <div class="pagination-buttons">
                <button onclick="changePage({max(0, offset - limit)})" class="btn btn-secondary" {'disabled' if offset == 0 else ''}>Previous</button>
                <button onclick="changePage({offset + limit})" class="btn btn-secondary" {'disabled' if offset + limit >= total else ''}>Next</button>
            </div>
        </div>
    </div>

    <script>
        let currentSortBy = '{sort_by}';
        let currentSortOrder = '{sort_order}';
        let currentSearch = '{search}';
        let currentLimit = {limit};
        let currentOffset = {offset};

        function changePage(newOffset) {{
            const limit = document.getElementById('limit-select').value;
            const url = new URL(window.location);
            url.searchParams.set('limit', limit);
            url.searchParams.set('offset', newOffset);
            url.searchParams.set('sort_by', currentSortBy);
            url.searchParams.set('sort_order', currentSortOrder);
            if (currentSearch) url.searchParams.set('search', currentSearch);
            window.location.href = url.toString();
        }}

        function changeLimit() {{
            const limit = document.getElementById('limit-select').value;
            const url = new URL(window.location);
            url.searchParams.set('limit', limit);
            url.searchParams.set('offset', '0');
            url.searchParams.set('sort_by', currentSortBy);
            url.searchParams.set('sort_order', currentSortOrder);
            if (currentSearch) url.searchParams.set('search', currentSearch);
            window.location.href = url.toString();
        }}

        function selectAllMessages(checkbox) {{
            const checkboxes = document.querySelectorAll('.message-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }}

        function searchMessages(query) {{
            currentSearch = query;
            applySort();
        }}

        function sortBy(field) {{
            if (currentSortBy === field) {{
                currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
            }} else {{
                currentSortBy = field;
                currentSortOrder = 'desc';
            }}
            applySort();
        }}

        function applySort() {{
            const sortBy = document.getElementById('sort-by').value;
            const sortOrder = document.getElementById('sort-order').value;
            const search = currentSearch;
            const limit = document.getElementById('limit-select') ? document.getElementById('limit-select').value : currentLimit;
            const url = `/messages?sort_by=${{sortBy}}&sort_order=${{sortOrder}}&search=${{encodeURIComponent(search)}}&limit=${{limit}}&offset=0`;
            window.location.href = url;
        }}

        function getSelectedMessageIds() {{
            const checkboxes = document.querySelectorAll('.message-checkbox:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        }}

        async function deleteSelectedMessages() {{
            const ids = getSelectedMessageIds();
            if (ids.length === 0) {{
                alert('Please select messages to delete');
                return;
            }}
            if (!confirm(`Delete ${{ids.length}} message(s)?`)) return;

            for (const id of ids) {{
                try {{
                    await fetch(`/webapi/proxy/messages/${{id}}`, {{ method: 'DELETE' }});
                }} catch (e) {{
                    console.error('Failed to delete message:', e);
                }}
            }}
            location.reload();
        }}
    </script>
"""
        html = get_base_layout("Messages", "messages", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading messages: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)


# Deliveries page with left menu, features, links to messages

async def view_deliveries(request: Request, user: str = Depends(get_current_user),
                          message_id: int = None, sort_by: str = "created_at",
                          sort_order: str = "desc", search: str = "", limit: int = 50, offset: int = 0):
    """View deliveries page with comprehensive functionality, links to messages, and pagination"""
    return _ui_index_response()
    try:
        # Get deliveries from API server - use API max limit of 1000
        params = {"limit": 1000, "offset": 0}
        if message_id:
            params["message_id"] = message_id
        result = await api_request("GET", "/deliveries", params=params, timeout=30.0)
        all_deliveries = result.get("items", []) if result else []
        if not isinstance(all_deliveries, list):
            all_deliveries = []
        total_all = result.get("total", len(all_deliveries)) if result else len(all_deliveries)
        if not isinstance(total_all, (int, float)):
            total_all = len(all_deliveries)

        # Filter by search term
        if search:
            search_lower = search.lower()
            all_deliveries = [d for d in all_deliveries if
                            search_lower in str(d.get("id", "")).lower() or
                            search_lower in str(d.get("message_id", "")).lower() or
                            search_lower in str(d.get("destination", "")).lower() or
                            search_lower in str(d.get("state", "")).lower() or
                            search_lower in str(d.get("channel_name", "")).lower()]

        # Sort deliveries
        reverse_order = (sort_order == "desc")
        if sort_by == "id":
            all_deliveries.sort(key=lambda x: x.get("id", 0), reverse=reverse_order)
        elif sort_by == "created_at":
            all_deliveries.sort(key=lambda x: x.get("created_at", ""), reverse=reverse_order)
        elif sort_by == "state":
            all_deliveries.sort(key=lambda x: x.get("state", ""), reverse=reverse_order)
        elif sort_by == "message_id":
            all_deliveries.sort(key=lambda x: x.get("message_id", 0), reverse=reverse_order)

        # Apply pagination after filtering and sorting
        total = len(all_deliveries)
        deliveries = all_deliveries[offset:offset + limit]

        # Build table rows with links to messages
        resendable_states = {
            "failed",
            "cancelled",
            "soft_failed",
            "permanent_failed",
            "retry_exhausted",
            "ttl_expired",
        }
        abortable_states = {"queued", "processing"}
        table_rows = []
        for d in deliveries:
            state_class = d.get("state", "").lower().replace("_", "-")
            state_value = str(d.get("state", "")).lower()
            resend_button = ""
            abort_button = ""
            if state_value in resendable_states:
                resend_button = f'<button class="btn btn-small btn-secondary" onclick="resendDelivery({d.get("id")})">Resend</button>'
            if state_value in abortable_states:
                abort_button = f'<button class="btn btn-small btn-danger" onclick="abortDelivery({d.get("id")})">Abort</button>'

            table_rows.append(f'''
            <tr data-delivery-id="{d.get("id")}">
                <td><input type="checkbox" class="delivery-checkbox" value="{d.get("id")}"></td>
                <td>{d.get("id", "")}</td>
                <td><a href="/messages/{d.get("message_id", "")}" style="color: var(--primary); text-decoration: none;">{d.get("message_id", "")}</a></td>
                <td>{d.get("channel_id", "")}</td>
                <td>{d.get("destination", "")[:50] if d.get("destination") else ""}</td>
                <td><span class="status status-{state_class}">{d.get("state", "")}</span></td>
                <td>{d.get("attempt_no", 0)}</td>
                <td>{d.get("created_at", "")[:19] if d.get("created_at") else ""}</td>
                <td>
                    <a href="/messages/{d.get("message_id", "")}" class="btn btn-small btn-primary">Message</a>
                    <a href="/deliveries/{d.get("id", "")}" class="btn btn-small btn-secondary">View</a>
                    {resend_button}
                    {abort_button}
                </td>
            </tr>
            ''')

        content = f"""
    <style>
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .action-bar {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            flex-wrap: wrap;
        }}
        .search-box {{
            flex: 1;
            min-width: 200px;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .sort-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .status {{
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }}
        .status-queued {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; }}
        .status-sent {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
        .status-failed {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        th.sortable {{
            cursor: pointer;
            user-select: none;
        }}
        .pagination-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 15px;
            padding: 10px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }}
        .pagination-info {{
            color: var(--text-secondary);
            font-size: 14px;
        }}
        .limit-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .limit-selector select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-secondary);
            color: var(--text-primary);
        }}
        .pagination-buttons {{
            display: flex;
            gap: 10px;
        }}
    </style>

    <div class="page-header">
        <h2>Deliveries ({total} total, showing {len(deliveries)} on this page)</h2>
        {f'<a href="/messages/{message_id}" class="btn btn-secondary">← Back to Message</a>' if message_id else ''}
    </div>

    <div class="action-bar">
        <input type="checkbox" class="select-all" onchange="selectAllDeliveries(this)">
        <input type="text" class="search-box" placeholder="Search deliveries..." value="{search}" onkeyup="searchDeliveries(this.value)">
        <div class="sort-controls">
            <label>Sort by:</label>
            <select id="sort-by" onchange="applySort()" style="padding: 6px; border-radius: 4px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border);">
                <option value="created_at" {'selected' if sort_by == 'created_at' else ''}>Created Date</option>
                <option value="id" {'selected' if sort_by == 'id' else ''}>ID</option>
                <option value="state" {'selected' if sort_by == 'state' else ''}>State</option>
                <option value="message_id" {'selected' if sort_by == 'message_id' else ''}>Message ID</option>
            </select>
            <select id="sort-order" onchange="applySort()" style="padding: 6px; border-radius: 4px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border);">
                <option value="desc" {'selected' if sort_order == 'desc' else ''}>Descending</option>
                <option value="asc" {'selected' if sort_order == 'asc' else ''}>Ascending</option>
            </select>
        </div>
        <button onclick="deleteSelectedDeliveries()" class="btn btn-danger">Delete Selected</button>
    </div>

    <div class="card">
        <div class="table-container">
            <table id="deliveries-table">
                <thead>
                    <tr>
                        <th style="width: 40px;"><input type="checkbox" class="select-all-header" onchange="selectAllDeliveries(this)"></th>
                        <th class="sortable" onclick="sortBy('id')">ID ↕</th>
                        <th class="sortable" onclick="sortBy('message_id')">Message ID ↕</th>
                        <th>Channel</th>
                        <th>Destination</th>
                        <th class="sortable" onclick="sortBy('state')">State ↕</th>
                        <th>Attempts</th>
                        <th class="sortable" onclick="sortBy('created_at')">Created ↕</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <div class="pagination-info">
                Showing {offset + 1} to {min(offset + limit, total)} of {total} deliveries
            </div>
            <div class="limit-selector">
                <label>Items per page:</label>
                <select id="limit-select" onchange="changeLimit()">
                    <option value="25" {'selected' if limit == 25 else ''}>25</option>
                    <option value="50" {'selected' if limit == 50 else ''}>50</option>
                    <option value="100" {'selected' if limit == 100 else ''}>100</option>
                    <option value="200" {'selected' if limit == 200 else ''}>200</option>
                </select>
            </div>
            <div class="pagination-buttons">
                <button onclick="changePage({max(0, offset - limit)})" class="btn btn-secondary" {'disabled' if offset == 0 else ''}>Previous</button>
                <button onclick="changePage({offset + limit})" class="btn btn-secondary" {'disabled' if offset + limit >= total else ''}>Next</button>
            </div>
        </div>
    </div>

    <script>
        let currentSortBy = '{sort_by}';
        let currentSortOrder = '{sort_order}';
        let currentSearch = '{search}';
        let currentLimit = {limit};
        let currentOffset = {offset};
        {f"let currentMessageId = {message_id};" if message_id is not None else "let currentMessageId = null;"}

        function changePage(newOffset) {{
            const limit = document.getElementById('limit-select').value;
            const url = new URL(window.location);
            url.searchParams.set('limit', limit);
            url.searchParams.set('offset', newOffset);
            url.searchParams.set('sort_by', currentSortBy);
            url.searchParams.set('sort_order', currentSortOrder);
            if (currentSearch) url.searchParams.set('search', currentSearch);
            if (currentMessageId) url.searchParams.set('message_id', currentMessageId);
            window.location.href = url.toString();
        }}

        function changeLimit() {{
            const limit = document.getElementById('limit-select').value;
            const url = new URL(window.location);
            url.searchParams.set('limit', limit);
            url.searchParams.set('offset', '0');
            url.searchParams.set('sort_by', currentSortBy);
            url.searchParams.set('sort_order', currentSortOrder);
            if (currentSearch) url.searchParams.set('search', currentSearch);
            if (currentMessageId) url.searchParams.set('message_id', currentMessageId);
            window.location.href = url.toString();
        }}

        function selectAllDeliveries(checkbox) {{
            const checkboxes = document.querySelectorAll('.delivery-checkbox');
            checkboxes.forEach(cb => cb.checked = checkbox.checked);
        }}

        function searchDeliveries(query) {{
            currentSearch = query;
            applySort();
        }}

        function sortBy(field) {{
            if (currentSortBy === field) {{
                currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
            }} else {{
                currentSortBy = field;
                currentSortOrder = 'desc';
            }}
            applySort();
        }}

        function applySort() {{
            const sortBy = document.getElementById('sort-by').value;
            const sortOrder = document.getElementById('sort-order').value;
            const search = currentSearch;
            const limit = document.getElementById('limit-select') ? document.getElementById('limit-select').value : currentLimit;
            const url = new URL(window.location);
            url.searchParams.set('sort_by', sortBy);
            url.searchParams.set('sort_order', sortOrder);
            url.searchParams.set('search', search);
            url.searchParams.set('limit', limit);
            url.searchParams.set('offset', '0');
            if (currentMessageId) url.searchParams.set('message_id', currentMessageId);
            window.location.href = url.toString();
        }}

        function getSelectedDeliveryIds() {{
            const checkboxes = document.querySelectorAll('.delivery-checkbox:checked');
            return Array.from(checkboxes).map(cb => cb.value);
        }}

        async function deleteSelectedDeliveries() {{
            const ids = getSelectedDeliveryIds();
            if (ids.length === 0) {{
                alert('Please select deliveries to delete');
                return;
            }}
            if (!confirm(`Delete ${{ids.length}} delivery(s)?`)) return;

            for (const id of ids) {{
                try {{
                    await fetch(`/webapi/proxy/deliveries/${{id}}`, {{ method: 'DELETE' }});
                }} catch (e) {{
                    console.error('Failed to delete delivery:', e);
                }}
            }}
            location.reload();
        }}

        async function resendDelivery(deliveryId) {{
            if (!confirm('Resend this delivery?')) return;
            try {{
                const response = await fetch(`/webapi/proxy/deliveries/${{deliveryId}}/resend`, {{ method: 'POST' }});
                if (!response.ok) {{
                    const data = await response.json();
                    alert('Resend failed: ' + (data.detail || response.status));
                    return;
                }}
                location.reload();
            }} catch (e) {{
                alert('Resend failed: ' + e.message);
            }}
        }}

        async function abortDelivery(deliveryId) {{
            if (!confirm('Abort this delivery?')) return;
            try {{
                const response = await fetch(`/webapi/proxy/deliveries/${{deliveryId}}/abort`, {{ method: 'POST' }});
                if (!response.ok) {{
                    const data = await response.json();
                    alert('Abort failed: ' + (data.detail || response.status));
                    return;
                }}
                location.reload();
            }} catch (e) {{
                alert('Abort failed: ' + e.message);
            }}
        }}
    </script>
"""
        html = get_base_layout("Deliveries", "deliveries", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading deliveries: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

async def view_config(request: Request, user: str = Depends(get_current_user)):
    """View configuration (with secrets masked) - via API proxy"""
    return _ui_index_response()
    try:
        # Get config from API server
        config_data = await api_request("GET", "/config")

        # Flatten config for display
        def flatten_dict(d, parent_key='', sep='.'):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key, sep=sep).items())
                else:
                    items.append((new_key, v))
            return dict(items)

        config_flat = flatten_dict(config_data)

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Configuration - Notification Agent</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #f5f7fa; }}
        .header {{ background: white; padding: 20px 40px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ color: #2d3748; font-size: 24px; }}
        .nav-menu {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; }}
        .nav-item {{ padding: 8px 16px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; }}
        .nav-item:hover {{ background: #5568d3; }}
        .nav-item.active {{ background: #4c51bf; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 30px 40px; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f7fafc; color: #4a5568; font-weight: 600; }}
        .user-info {{ display: flex; align-items: center; gap: 15px; }}
        .logout-btn {{ padding: 8px 16px; background: #e53e3e; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; }}
        .config-value {{ font-family: monospace; background: #f7fafc; padding: 4px 8px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔔 Notification Agent - Configuration</h1>
        <div class="user-info">
            <span>👤 {user}</span>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
    </div>
    <div class="container">
        {get_nav_menu("config")}
        <div class="section">
            <h2>Configuration ({len(config_flat)} settings)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'''
                    <tr>
                        <td>{k}</td>
                        <td><span class="config-value">{json.dumps(v) if isinstance(v, (dict, list)) else str(v)}</span></td>
                    </tr>
                    ''' for k, v in sorted(config_flat.items())])}
                </tbody>
            </table>
        </div>
        <div class="section">
            <h2>Update Configuration (Admin)</h2>
            <form id="config-update-form" onsubmit="updateConfig(event)">
                <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px;">
                    <input type="text" name="key" placeholder="config key (e.g., app.title)" required />
                    <input type="text" name="value" placeholder="value" required />
                    <label style="display:flex; align-items:center; gap:6px;">
                        <input type="checkbox" name="persist" />
                        Persist to env file
                    </label>
                </div>
                <button type="submit" class="nav-item">Update</button>
            </form>
            <div id="config-update-result" style="margin-top:10px;"></div>
        </div>
    </div>
    <script>
        function parseValue(value) {{
            if (value === "true") return true;
            if (value === "false") return false;
            if (!isNaN(value) && value.trim() !== "") return Number(value);
            return value;
        }}

        async function updateConfig(event) {{
            event.preventDefault();
            const form = event.target;
            const key = form.key.value.trim();
            const value = parseValue(form.value.value.trim());
            const persist = form.persist.checked;
            const result = document.getElementById("config-update-result");
            result.innerHTML = "Updating...";

            const response = await fetch("/webapi/proxy/config/update", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ updates: {{ [key]: value }}, persist }})
            }});

            if (response.ok) {{
                result.innerHTML = "✅ Updated (reload to see changes)";
            }} else {{
                const data = await response.json().catch(() => ({{}}));
                result.innerHTML = `❌ Update failed: ${{data.detail || response.status}}`;
            }}
        }}
    </script>
</body>
</html>
"""
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

async def mcp_test_page(request: Request, user: str = Depends(get_current_user)):
    """MCP/A2A Natural Language Testing Interface"""
    return _ui_index_response()
    content = """
    <style>
        .mcp-test-container {
            max-width: 1200px;
        }
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid var(--border);
        }
        .tab {
            padding: 10px 20px;
            background: none;
            border: none;
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 14px;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
        }
        .tab.active {
            color: var(--primary);
            border-bottom-color: var(--primary);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
        }
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 14px;
            font-family: inherit;
        }
        textarea {
            min-height: 120px;
            resize: vertical;
        }
        .test-btn {
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s;
        }
        .test-btn:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
        }
        .test-btn:disabled {
            background: var(--bg-tertiary);
            cursor: not-allowed;
            transform: none;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            border-left: 4px solid var(--primary);
        }
        .result pre {
            background: #1a1a2e;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
            margin-top: 10px;
        }
        .result.error {
            border-left-color: var(--danger);
            background: rgba(244, 67, 54, 0.1);
        }
        .result.success {
            border-left-color: var(--success);
            background: rgba(76, 175, 80, 0.1);
        }
        .examples {
            margin-top: 20px;
        }
        .example {
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 6px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.3s;
            border: 1px solid var(--border);
        }
        .example:hover {
            background: var(--bg-primary);
            border-color: var(--primary);
        }
        .example code {
            color: var(--primary);
            font-family: 'Courier New', monospace;
        }
        .mcp-info {
            background: var(--bg-tertiary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        .mcp-info pre {
            background: #1a1a2e;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>

    <div class="mcp-test-container">
        <div class="card">
            <h2 class="card-title">Natural Language Command Testing</h2>
            <div class="tabs">
                <button class="tab active" onclick="switchTab('a2a')">A2A Endpoint</button>
                <button class="tab" onclick="switchTab('mcp')">MCP Tool (Info)</button>
            </div>

            <div id="a2a-tab" class="tab-content active">
                <div class="form-group">
                    <label>Natural Language Command</label>
                    <textarea id="command" placeholder="e.g., Send notification to Fred that JOB XXXX has finished"></textarea>
                </div>
                <div class="form-group">
                    <label>Channels (Optional - comma separated)</label>
                    <input type="text" id="channels" placeholder="<DEFAULT_CHANNEL_NAME>, <SECONDARY_CHANNEL_NAME>">
                </div>
                <button onclick="testA2A()" id="test-btn" class="test-btn">Send via A2A</button>

                <div class="examples">
                    <h3 style="margin-top: 20px; margin-bottom: 10px;">Example Commands:</h3>
                    <div class="example" onclick="setExample('Send notification to Fred that JOB XXXX has finished')">
                        <code>Send notification to Fred that JOB XXXX has finished</code>
                    </div>
                    <div class="example" onclick="setExample('Send all the results to the Admin Users')">
                        <code>Send all the results to the Admin Users</code>
                    </div>
                    <div class="example" onclick="setExample('Notify user@example.com about the system update')">
                        <code>Notify user@example.com about the system update</code>
                    </div>
                </div>

                <div id="result"></div>
            </div>

            <div id="mcp-tab" class="tab-content">
                <div class="mcp-info">
                    <h3>MCP Tool: send_notification_natural</h3>
                    <p>To use the MCP tool, connect via an MCP client and call:</p>
                    <pre>{
  "name": "send_notification_natural",
  "arguments": {
    "command": "Send notification to Fred that JOB XXXX has finished",
    "channels": ["<DEFAULT_CHANNEL_NAME>"]
  }
}</pre>
                    <p><strong>Note:</strong> MCP tools are accessed via stdio protocol, not HTTP. Use an MCP client to test.</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            if (tab === 'a2a') {
                document.querySelector('.tab:first-child').classList.add('active');
                document.getElementById('a2a-tab').classList.add('active');
            } else {
                document.querySelector('.tab:last-child').classList.add('active');
                document.getElementById('mcp-tab').classList.add('active');
            }
        }

        function setExample(cmd) {
            document.getElementById('command').value = cmd;
        }

        async function testA2A() {
            const command = document.getElementById('command').value.trim();
            const channelsInput = document.getElementById('channels').value.trim();
            const resultDiv = document.getElementById('result');
            const testBtn = document.getElementById('test-btn');

            if (!command) {
                resultDiv.innerHTML = '<div class="result error"><strong>Error:</strong> Command is required</div>';
                return;
            }

            testBtn.disabled = true;
            testBtn.textContent = 'Sending...';
            resultDiv.innerHTML = '<div class="result">Sending request...</div>';

            const payload = {
                command: command
            };

            if (channelsInput) {
                payload.channels = channelsInput.split(',').map(c => c.trim()).filter(c => c);
            }

            try {
                // Call A2A endpoint via API proxy
                const response = await fetch('/webapi/proxy/a2a/notify/natural', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (data.success || response.ok) {
                    resultDiv.innerHTML = `
                        <div class="result success">
                            <strong>✅ Success!</strong>
                            <p>Message ID: ${data.message_id || 'N/A'}</p>
                            <details>
                                <summary>Response Details</summary>
                                <pre>${JSON.stringify(data, null, 2)}</pre>
                            </details>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `
                        <div class="result error">
                            <strong>❌ Error:</strong> ${data.error || data.detail || 'Unknown error'}
                            <details>
                                <summary>Response Details</summary>
                                <pre>${JSON.stringify(data, null, 2)}</pre>
                            </details>
                        </div>
                    `;
                }
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="result error">
                        <strong>❌ Request Failed:</strong> ${error.message}
                    </div>
                `;
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = 'Send via A2A';
            }
        }
    </script>
"""
    html = get_base_layout("MCP/A2A Testing", "mcp-test", content, user)
    return HTMLResponse(content=html)

async def llm_test_page(request: Request, user: str = Depends(get_current_user)):
    """LLM Functionality Testing Interface"""
    return _ui_index_response()
    content = """
    <style>
        .llm-test-container {
            max-width: 1200px;
        }
        .test-card {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid var(--border);
        }
        .test-card h3 {
            margin-top: 0;
            color: var(--primary);
        }
        .test-controls {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .test-result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 6px;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            display: none;
        }
        .test-result.show {
            display: block;
        }
        .test-result.success {
            border-color: #4ade80;
            background: rgba(34, 197, 94, 0.1);
        }
        .test-result.error {
            border-color: #f87171;
            background: rgba(239, 68, 68, 0.1);
        }
        .test-result pre {
            margin: 10px 0;
            padding: 10px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow-x: auto;
            font-size: 12px;
        }
        .btn-test {
            padding: 10px 20px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 500;
        }
        .btn-test:hover {
            opacity: 0.9;
        }
        .btn-test:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .config-info {
            background: var(--bg-secondary);
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .config-info code {
            background: var(--bg-primary);
            padding: 2px 6px;
            border-radius: 3px;
        }
    </style>

    <div class="llm-test-container">
        <div class="card">
            <h2>🤖 LLM Functionality Tests</h2>
            <p>Test LLM capabilities: translation, formatting, summarization, and combined operations.</p>

            <div class="config-info" id="config-info">
                <strong>Configuration:</strong> Loading...
            </div>

            <div class="test-card">
                <h3>1. Connection Test</h3>
                <p>Verify LLM connection and basic response capability.</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('connection')">Run Connection Test</button>
                </div>
                <div class="test-result" id="result-connection"></div>
            </div>

            <div class="test-card">
                <h3>2. Translation Test</h3>
                <p>Test LLM's ability to translate content to French.</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('translation')">Run Translation Test</button>
                </div>
                <div class="test-result" id="result-translation"></div>
            </div>

            <div class="test-card">
                <h3>3. Formatting Test</h3>
                <p>Test LLM's ability to format content as Markdown.</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('formatting')">Run Formatting Test</button>
                </div>
                <div class="test-result" id="result-formatting"></div>
            </div>

            <div class="test-card">
                <h3>4. Summarization Test</h3>
                <p>Test LLM's ability to summarize content.</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('summarization')">Run Summarization Test</button>
                </div>
                <div class="test-result" id="result-summarization"></div>
            </div>

            <div class="test-card">
                <h3>5. Combined Instructions Test</h3>
                <p>Test LLM's ability to handle multiple instructions (translate + format).</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('combined')">Run Combined Test</button>
                </div>
                <div class="test-result" id="result-combined"></div>
            </div>

            <div class="test-card">
                <h3>6. Run All Tests</h3>
                <p>Run all LLM functionality tests in sequence.</p>
                <div class="test-controls">
                    <button class="btn-test" onclick="runTest('all')">Run All Tests</button>
                </div>
                <div class="test-result" id="result-all"></div>
            </div>
        </div>
    </div>

    <script>
        // Load config on page load
        async function loadConfig() {
            try {
                const response = await fetch('/webapi/proxy/tests/llm/status');
                const data = await response.json();
                const configDiv = document.getElementById('config-info');
                configDiv.innerHTML = `
                    <strong>Configuration:</strong><br>
                    Provider: <code>${data.config.llm_provider}</code><br>
                    Model: <code>${data.config.llm_model}</code><br>
                    Temperature: <code>${data.config.llm_temperature}</code><br>
                    Base URL: <code>${data.config.llm_base_url}</code>
                `;
            } catch (e) {
                console.error('Failed to load config:', e);
            }
        }

        async function runTest(testType) {
            const resultDiv = document.getElementById(`result-${testType}`);
            const btn = event.target;

            // Show loading state
            resultDiv.className = 'test-result show';
            resultDiv.innerHTML = '<p>⏳ Running test... This may take a minute.</p>';
            btn.disabled = true;
            btn.textContent = 'Running...';

            try {
                const response = await fetch('/webapi/proxy/tests/llm/run', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ test_type: testType })
                });

                const data = await response.json();

                if (data.success) {
                    resultDiv.className = 'test-result show success';
                    resultDiv.innerHTML = `
                        <h4>✅ Test Passed</h4>
                        <p><strong>Summary:</strong> ${data.summary.passed}/${data.summary.total} tests passed</p>
                        <pre>${JSON.stringify(data.test_results, null, 2)}</pre>
                        <details>
                            <summary>Full Output</summary>
                            <pre>${data.stdout}</pre>
                        </details>
                    `;
                } else {
                    resultDiv.className = 'test-result show error';
                    resultDiv.innerHTML = `
                        <h4>❌ Test Failed</h4>
                        <p><strong>Error:</strong> ${data.error || 'Test execution failed'}</p>
                        <pre>${data.stderr || data.stdout || 'No output'}</pre>
                    `;
                }
            } catch (e) {
                resultDiv.className = 'test-result show error';
                resultDiv.innerHTML = `<h4>❌ Error</h4><p>${e.message}</p>`;
            } finally {
                btn.disabled = false;
                btn.textContent = btn.textContent.replace('Running...', 'Run ' + testType.charAt(0).toUpperCase() + testType.slice(1) + ' Test');
            }
        }

        // Load config on page load
        loadConfig();
    </script>
"""
    html = get_base_layout("LLM Testing", "llm-test", content, user)
    return HTMLResponse(content=html)

@router.get("/webapi/proxy/tests/llm/status")
async def proxy_llm_test_status(user: str = Depends(get_current_user)):
    """Proxy LLM test status endpoint"""
    return await api_request("GET", "/tests/llm/status")

@router.post("/webapi/proxy/tests/llm/run")
async def proxy_llm_test_run(request: Request, user: str = Depends(get_current_user)):
    """Proxy LLM test run endpoint"""
    data = await request.json()
    return await api_request("POST", "/tests/llm/run", json=data)

@router.get("/webapi/proxy/a2a/notify/natural")
async def proxy_a2a_natural_get():
    """Proxy GET to A2A natural endpoint (not supported, redirect to POST)"""
    raise HTTPException(status_code=405, detail="Method not allowed. Use POST.")

@router.post("/webapi/proxy/a2a/notify/natural")
async def proxy_a2a_natural(request: Request):
    """Proxy POST to A2A /notify/natural endpoint"""
    try:
        data = await request.json()
        a2a_base_url = _require_config(config.get("a2a_server.base_url"), "a2a_server.base_url")
        a2a_base_url = a2a_base_url.rstrip('/')

        client = _get_internal_client()
        response = await client.post(
            f"{a2a_base_url}/notify/natural",
            json=data,
            headers=_a2a_proxy_headers(request),
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail)
        return response.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying A2A request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Logs page with left menu, follow, wrap, refresh (like sql-agent-mcp-server)

async def add_user_page(request: Request, user: str = Depends(get_current_user)):
    """Add new user page"""
    return _ui_index_response()
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Add User - Notification Agent</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; background: #f5f7fa; }}
        .header {{ background: white; padding: 20px 40px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }}
        .header h1 {{ color: #2d3748; font-size: 24px; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 30px 40px; }}
        .section {{ background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #4a5568; font-weight: 500; }}
        input, select, textarea {{
            width: 100%;
            padding: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 14px;
            font-family: inherit;
        }}
        button {{ padding: 12px 24px; background: #667eea; color: white; border: none; border-radius: 5px; font-size: 16px; font-weight: 500; cursor: pointer; }}
        button:hover {{ background: #5568d3; }}
        .btn {{ padding: 8px 16px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; display: inline-block; }}
        .btn-secondary {{ background: #718096; }}
        .error {{ color: #e53e3e; margin-top: 10px; }}
        .success {{ color: #48bb78; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>👥 Add User</h1>
        <div>
            <a href="/db/users" class="btn btn-secondary">← Back to Users</a>
            <span style="margin: 0 15px;">👤 {user}</span>
            <a href="/logout" class="btn" style="background: #e53e3e;">Logout</a>
        </div>
    </div>
    <div class="container">
        <div class="section">
            <h2>Create New User</h2>
            <form id="user-form" onsubmit="submitUser(event)">
                <div class="form-group">
                    <label>Username *</label>
                    <input type="text" name="username" required />
                </div>
                <div class="form-group">
                    <label>Email *</label>
                    <input type="email" name="email" required />
                </div>
                <div class="form-group">
                    <label>Display Name</label>
                    <input type="text" name="display_name" />
                </div>
                <div class="form-group">
                    <label>Password *</label>
                    <input type="password" name="password" required />
                </div>
                <div class="form-group">
                    <label>Role</label>
                    <select name="role">
                        <option value="viewer">Viewer</option>
                        <option value="editor">Editor</option>
                        <option value="admin">Admin</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Language</label>
                    <select name="language">
                        <option value="en">English</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                        <option value="es">Spanish</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Preferred Channel</label>
                    <select name="preferred_channel">
                        <option value="email">Email</option>
                        <option value="sms">SMS</option>
                        <option value="whatsapp">WhatsApp</option>
                        <option value="slack">Slack</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Content Style</label>
                    <select name="content_style">
                        <option value="html">HTML</option>
                        <option value="plain">Plain Text</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>User Type</label>
                    <select name="user_type">
                        <option value="real">Real</option>
                        <option value="system">System</option>
                    </select>
                </div>
                <button type="submit">Create User</button>
                <div id="result"></div>
            </form>
        </div>
    </div>
    <script>
        async function submitUser(event) {{
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('result');

            // Convert form data to JSON
            const data = {{
                username: formData.get('username'),
                email: formData.get('email'),
                display_name: formData.get('display_name') || null,
                password: formData.get('password'),
                role: formData.get('role') || 'viewer',
                language: formData.get('language') || null,
                preferred_channel: formData.get('preferred_channel') || null,
                content_style: formData.get('content_style') || null,
                user_type: formData.get('user_type') || 'real',
            }};

            try {{
                const response = await fetch('/webapi/proxy/users', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                const result = await response.json();

                if (response.ok) {{
                    resultDiv.innerHTML = `<div class="success">✅ User created successfully! <a href="/db/users">View Users</a></div>`;
                    form.reset();
                }} else {{
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${{result.detail || 'Unknown error'}}</div>`;
                }}
            }} catch (error) {{
                resultDiv.innerHTML = `<div class="error">❌ Request failed: ${{error.message}}</div>`;
            }}
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

@router.get("/api/proxy/users")
@router.get("/webapi/proxy/users")
async def proxy_list_users(
    request: Request,
    q: str = None,
    email: str = None,
    limit: int = 100,
    user: str = Depends(get_current_user),
):
    """Proxy GET to list users for the monorepo UI."""
    params = {"limit": limit}
    if q:
        params["q"] = q
    if email:
        params["email"] = email
    return await api_request("GET", "/users", params=params)

@router.post("/api/proxy/users")
@router.post("/webapi/proxy/users")
async def proxy_create_user(request: Request):
    """Proxy POST to create user"""
    try:
        data = await request.json()
        result = await api_request("POST", "/users", data=data)
        return result
    except HTTPException as e:
        # Re-raise HTTP exceptions (422, 400, 409, etc.) as-is
        raise e
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _normalise_preference_payload(data: dict) -> dict:
    payload = dict(data)
    language = payload.get("language")
    if language not in (None, ""):
        language = str(language).strip().lower()
        if len(language) != 2 or not language.isalpha():
            raise HTTPException(status_code=422, detail="language must be an ISO 639-1 two-letter code")
        payload["language"] = language
    content_style = payload.get("content_style")
    if content_style not in (None, ""):
        # req: FR-014 — accept the WebUI-offered content_style values (html, plain,
        # summary+link) so a preference selectable in the rendered form is not
        # rejected by the proxy validator (W28E-1807B contract alignment).
        content_style = str(content_style).strip().lower()
        if content_style.split(":", 1)[0] not in {"short", "detailed", "summary+link", "rich", "plain", "html"}:
            raise HTTPException(status_code=422, detail="content_style must be one of short, detailed, summary+link, rich, plain, html")
        payload["content_style"] = content_style
    if "keywords" in payload:
        keywords = payload.get("keywords") or []
        if not isinstance(keywords, list):
            raise HTTPException(status_code=422, detail="keywords must be a list")
        payload["keywords"] = sorted({str(item).strip() for item in keywords if str(item).strip()})
    return payload


def _preference_manager():
    from ...core.users.user_manager import UserManager
    from ...database.db_manager import get_db_manager

    return UserManager(get_db_manager())


def _current_profile_user(request: Request):
    manager = _preference_manager()
    username = str(request.session.get("user") or "").strip()
    user_id = request.session.get("user_id")
    if user_id:
        user = manager.user_repo.get_by_id(int(user_id))
        if user:
            return manager, user
    user = manager.user_repo.get_by_username(username)
    if user:
        return manager, user
    raise HTTPException(status_code=404, detail="Current user profile not found")


@router.get("/api/proxy/users/me/preferences")
@router.get("/webapi/proxy/users/me/preferences")
async def proxy_get_my_preferences(request: Request, user: str = Depends(get_current_user)):
    """Read the logged-in user's self-service preference profile."""
    manager, current_user = _current_profile_user(request)
    return manager.get_user_with_destinations(int(current_user["id"]))


@router.put("/api/proxy/users/me/preferences")
@router.put("/webapi/proxy/users/me/preferences")
async def proxy_update_my_preferences(request: Request, user: str = Depends(get_current_user)):
    """Update the logged-in user's self-service preference profile."""
    manager, current_user = _current_profile_user(request)
    data = _normalise_preference_payload(await request.json())
    user_id = int(current_user["id"])
    manager.update_preferences(
        user_id=user_id,
        language=data.get("language"),
        preferred_channel=data.get("preferred_channel"),
        content_style=data.get("content_style"),
        timezone=data.get("timezone"),
    )
    if "keywords" in data:
        for existing in manager.keyword_repo.get_by_user_id(user_id):
            manager.keyword_repo.remove(user_id, existing["keyword"])
        for keyword in data["keywords"]:
            manager.keyword_repo.add(user_id, keyword)
    return manager.get_user_with_destinations(user_id)


@router.delete("/api/proxy/users/me/preferences")
@router.delete("/webapi/proxy/users/me/preferences")
async def proxy_delete_my_preferences(request: Request, user: str = Depends(get_current_user)):
    """Clear the logged-in user's self-service preference profile."""
    manager, current_user = _current_profile_user(request)
    user_id = int(current_user["id"])
    manager.user_repo.clear_preferences(user_id)
    for existing in manager.keyword_repo.get_by_user_id(user_id):
        manager.keyword_repo.remove(user_id, existing["keyword"])
    return {"success": True, "user_id": user_id}

@router.get("/api/proxy/admin/api-keys")
@router.get("/webapi/proxy/admin/api-keys")
@require_permission(CONFIG_WRITE)
async def proxy_list_api_keys(request: Request):
    """Proxy GET to list admin API keys."""
    owner_user_id = request.query_params.get("owner_user_id")
    params = {"owner_user_id": owner_user_id} if owner_user_id else None
    return await api_request("GET", "/admin/api-keys", params=params)

@router.post("/api/proxy/admin/api-keys")
@router.post("/webapi/proxy/admin/api-keys")
@require_permission(CONFIG_WRITE)
async def proxy_create_api_key(request: Request):
    """Proxy POST to create an admin API key."""
    data = await request.json()
    return await api_request("POST", "/admin/api-keys", data=data)

@router.delete("/api/proxy/admin/api-keys/{key_id}")
@router.delete("/webapi/proxy/admin/api-keys/{key_id}")
@require_permission(CONFIG_WRITE)
async def proxy_revoke_api_key(request: Request, key_id: str):
    """Proxy DELETE to revoke an admin API key."""
    return await api_request("DELETE", f"/admin/api-keys/{key_id}")


_RBAC_ROLE_DESCRIPTIONS = {
    "admin": "Full access to Notification-Agent administration",
    "owner": "Operational owner access for notification resources",
    "user": "Standard sender and reader access",
    "viewer": "Read-only access",
}


def _rbac_role_permissions() -> dict[str, set[str]]:
    permissions = getattr(idam_runtime.rbac_engine, "_role_permissions", None)
    if not isinstance(permissions, dict):
        permissions = {}
        setattr(idam_runtime.rbac_engine, "_role_permissions", permissions)
    return permissions


def _serialise_rbac_role(name: str, permissions: set[str] | list[str] | tuple[str, ...]) -> dict[str, Any]:
    sorted_permissions = sorted(str(item) for item in permissions)
    return {
        "name": name,
        "description": _RBAC_ROLE_DESCRIPTIONS.get(name, ""),
        "permissions": sorted_permissions,
        "channels": sorted(
            permission.removeprefix("channel:")
            for permission in sorted_permissions
            if permission.startswith("channel:")
        ),
        "functions": [
            permission
            for permission in sorted_permissions
            if not permission.startswith("channel:")
        ],
    }


@router.get("/api/proxy/rbac/roles")
@router.get("/webapi/proxy/rbac/roles")
@require_permission(CONFIG_READ)
async def proxy_list_rbac_roles(request: Request):
    """List mutable RBAC role definitions for the SPA."""
    roles = [
        _serialise_rbac_role(name, permissions)
        for name, permissions in sorted(_rbac_role_permissions().items())
    ]
    return {"items": roles, "total": len(roles)}


@router.get("/api/proxy/admin/policies")
@router.get("/webapi/proxy/admin/policies")
@require_permission(CONFIG_READ)
async def proxy_admin_policies(request: Request):
    """CX-110 (W28E-615): permission catalogue + role policies for the Roles page.

    ``permissions`` feeds the RolesPage MultiSelect (not a CSV input);
    ``role_policies`` maps each role to its concrete permission strings sourced
    from the runtime RBAC engine. The static catalogue guarantees the canonical
    notification permission set is always selectable even before any custom role
    has been defined.
    """
    from src.core.rbac import permissions as _perms

    role_permissions = _rbac_role_permissions()
    role_policies = {
        name: sorted(str(item) for item in perms)
        for name, perms in sorted(role_permissions.items())
    }
    catalogue: set[str] = {
        _perms.SEND,
        _perms.LIST,
        _perms.READ_ITEM,
        _perms.DELETE_ITEM,
        _perms.CONFIG_WRITE,
        _perms.CONFIG_READ,
        _perms.ADMIN,
        "*",
    }
    for perms in role_policies.values():
        catalogue.update(perms)
    return {
        "permissions": sorted(catalogue),
        "roles": sorted(role_policies.keys()),
        "role_policies": role_policies,
    }


@router.post("/api/proxy/rbac/roles")
@router.post("/webapi/proxy/rbac/roles")
@require_permission(ADMIN)
async def proxy_create_rbac_role(request: Request):
    """Create an RBAC role definition in the runtime RBAC engine."""
    data = await request.json()
    name = str(data.get("name") or "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Role name is required")
    role_permissions = _rbac_role_permissions()
    if name in role_permissions:
        raise HTTPException(status_code=409, detail="Role already exists")
    permissions = {str(item).strip() for item in data.get("permissions", []) if str(item).strip()}
    role_permissions[name] = permissions
    _RBAC_ROLE_DESCRIPTIONS[name] = str(data.get("description") or "")
    getattr(idam_runtime.rbac_engine, "_cache", None).clear() if hasattr(getattr(idam_runtime.rbac_engine, "_cache", None), "clear") else None
    return _serialise_rbac_role(name, permissions)


@router.put("/api/proxy/rbac/roles/{role_name}")
@router.put("/webapi/proxy/rbac/roles/{role_name}")
@require_permission(ADMIN)
async def proxy_update_rbac_role(request: Request, role_name: str):
    """Update RBAC role permissions."""
    data = await request.json()
    name = str(role_name or "").strip().lower()
    role_permissions = _rbac_role_permissions()
    if name not in role_permissions:
        raise HTTPException(status_code=404, detail="Role not found")
    permissions = {str(item).strip() for item in data.get("permissions", []) if str(item).strip()}
    role_permissions[name] = permissions
    _RBAC_ROLE_DESCRIPTIONS[name] = str(data.get("description") or _RBAC_ROLE_DESCRIPTIONS.get(name, ""))
    getattr(idam_runtime.rbac_engine, "_cache", None).clear() if hasattr(getattr(idam_runtime.rbac_engine, "_cache", None), "clear") else None
    return _serialise_rbac_role(name, permissions)


@router.delete("/api/proxy/rbac/roles/{role_name}")
@router.delete("/webapi/proxy/rbac/roles/{role_name}")
@require_permission(ADMIN)
async def proxy_delete_rbac_role(request: Request, role_name: str):
    """Revoke an RBAC role definition."""
    name = str(role_name or "").strip().lower()
    if name == "admin":
        raise HTTPException(status_code=409, detail="The admin role cannot be revoked")
    role_permissions = _rbac_role_permissions()
    if name not in role_permissions:
        raise HTTPException(status_code=404, detail="Role not found")
    role_permissions.pop(name, None)
    _RBAC_ROLE_DESCRIPTIONS.pop(name, None)
    getattr(idam_runtime.rbac_engine, "_cache", None).clear() if hasattr(getattr(idam_runtime.rbac_engine, "_cache", None), "clear") else None
    return {"deleted": True, "name": name}

async def edit_user_page(request: Request, user_id: int, user: str = Depends(get_current_user)):
    """Edit user page with base layout"""
    return _ui_index_response()
    try:
        user_data = await api_request("GET", _api_target_path(f"/users/{user_id}"))

        content = f"""
    <style>
        .form-container {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 10px;
            max-width: 600px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
        }}
        .form-group input,
        .form-group select {{
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 14px;
        }}
        .btn-submit {{
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }}
        .btn-submit:hover {{
            background: var(--primary-hover);
        }}
        .error {{
            color: #e53e3e;
            margin-top: 10px;
            padding: 10px;
            background: rgba(229, 62, 62, 0.1);
            border-radius: 6px;
        }}
        .success {{
            color: #48bb78;
            margin-top: 10px;
            padding: 10px;
            background: rgba(72, 187, 120, 0.1);
            border-radius: 6px;
        }}
    </style>

    <div class="card">
        <h2>Edit User: {user_data.get('display_name', user_data.get('username', ''))}</h2>
        <div class="form-container">
            <form id="user-form" onsubmit="updateUser(event)">
                <div class="form-group">
                    <label>Language</label>
                    <select name="language" id="language">
                        <option value="en" {'selected' if user_data.get('language') == 'en' else ''}>English</option>
                        <option value="fr" {'selected' if user_data.get('language') == 'fr' else ''}>French</option>
                        <option value="de" {'selected' if user_data.get('language') == 'de' else ''}>German</option>
                        <option value="es" {'selected' if user_data.get('language') == 'es' else ''}>Spanish</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Preferred Channel</label>
                    <select name="preferred_channel" id="preferred_channel">
                        <option value="email" {'selected' if user_data.get('preferred_channel') == 'email' else ''}>Email</option>
                        <option value="sms" {'selected' if user_data.get('preferred_channel') == 'sms' else ''}>SMS</option>
                        <option value="whatsapp" {'selected' if user_data.get('preferred_channel') == 'whatsapp' else ''}>WhatsApp</option>
                        <option value="slack" {'selected' if user_data.get('preferred_channel') == 'slack' else ''}>Slack</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Content Style</label>
                    <select name="content_style" id="content_style">
                        <option value="html" {'selected' if user_data.get('content_style') == 'html' else ''}>HTML</option>
                        <option value="plain" {'selected' if user_data.get('content_style') == 'plain' else ''}>Plain Text</option>
                    </select>
                </div>
                <button type="submit" class="btn-submit">Update Preferences</button>
                <div id="result"></div>
            </form>
        </div>
        <div style="margin-top: 20px;">
            <a href="/users" class="btn btn-secondary">← Back to Users</a>
        </div>
    </div>

    <script>
        async function updateUser(event) {{
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('result');

            const data = {{
                language: formData.get('language') || null,
                preferred_channel: formData.get('preferred_channel') || null,
                content_style: formData.get('content_style') || null,
            }};

            try {{
                const response = await fetch(`/webapi/proxy/users/{user_id}/preferences`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                const result = await response.json();

                if (response.ok) {{
                    resultDiv.innerHTML = `<div class="success">✅ Preferences updated successfully!</div>`;
                }} else {{
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${{result.detail || 'Unknown error'}}</div>`;
                }}
            }} catch (error) {{
                resultDiv.innerHTML = `<div class="error">❌ Request failed: ${{error.message}}</div>`;
            }}
        }}
    </script>
"""
        html = get_base_layout(f"Edit User: {user_data.get('display_name', user_data.get('username', ''))}", "users", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading user: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@router.put("/api/proxy/users/{user_id}/preferences")
@router.put("/webapi/proxy/users/{user_id}/preferences")
async def proxy_update_user_preferences(user_id: int, request: Request):
    """Proxy PUT to update user preferences"""
    try:
        data = _normalise_preference_payload(await request.json())
        # The API runtime updates user preferences via the user patch contract.
        result = await api_request("PATCH", _api_target_path(f"/users/{user_id}"), data=data)
        return result
    except Exception as e:
        logger.error(f"Error updating user preferences: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/proxy/users/{user_id}")
@router.get("/webapi/proxy/users/{user_id}")
async def proxy_get_user(user_id: int):
    """Proxy GET to get user details"""
    try:
        result = await api_request("GET", f"/users/{user_id}")
        return result
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _patch_user_record(user_id: int, data: dict):
    """Update user fields for the SPA without round-tripping through the web proxy client."""
    from ...database.repositories import UserRepository

    db = get_db_manager()
    user_repo = UserRepository(db)
    loop = asyncio.get_event_loop()
    current = await loop.run_in_executor(None, user_repo.get_by_id, user_id)
    if not current:
        raise HTTPException(status_code=404, detail="User not found")

    assignments = []
    values = []
    field_map = {
        "email": "email",
        "display_name": "display_name",
        "role": "role",
        "language": "language",
        "preferred_channel": "preferred_channel",
        "content_style": "content_style",
        "timezone": "timezone",
    }
    for payload_key, column_name in field_map.items():
        if payload_key in data:
            assignments.append(f"{column_name} = ?")
            values.append(data[payload_key])

    if assignments:
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)
        await loop.run_in_executor(
            None,
            db.execute,
            f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )
        await loop.run_in_executor(None, db.commit)

    return await loop.run_in_executor(None, user_repo.get_by_id, user_id)

@router.patch("/api/proxy/users/{user_id}")
@router.patch("/webapi/proxy/users/{user_id}")
async def proxy_patch_user(user_id: int, request: Request, user: str = Depends(get_current_user)):
    """Proxy PATCH to update user fields for the monorepo UI."""
    try:
        data = await request.json()
        return await _patch_user_record(user_id, data)
    except Exception as e:
        logger.error(f"Error patching user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/proxy/users/{user_id}")
@router.put("/webapi/proxy/users/{user_id}")
async def proxy_update_user(user_id: int, request: Request, user: str = Depends(get_current_user)):
    """Proxy PUT to update user"""
    try:
        data = await request.json()
        return await _patch_user_record(user_id, data)
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/proxy/users/{user_id}")
@router.delete("/webapi/proxy/users/{user_id}")
async def proxy_delete_user(user_id: int, user: str = Depends(get_current_user)):
    """Proxy DELETE user"""
    try:
        result = await api_request("DELETE", f"/users/{user_id}")
        return result
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/proxy/messages/{message_id}/deliveries")
@router.get("/webapi/proxy/messages/{message_id}/deliveries")
async def proxy_get_message_deliveries(message_id: int):
    """Proxy GET to get message deliveries"""
    try:
        result = await api_request("GET", f"/messages/{message_id}/deliveries")
        return result
    except Exception as e:
        logger.error(f"Error getting message deliveries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/proxy/deliveries")
@router.get("/webapi/proxy/deliveries")
async def proxy_deliveries(user: str = Depends(get_current_user), message_id: int = None, limit: int = 100):
    """Proxy GET deliveries"""
    if message_id:
        return await api_request("GET", f"/messages/{message_id}/deliveries")
    params = {"limit": limit}
    return await api_request("GET", "/deliveries", params=params)

@router.get("/api/proxy/deliveries/{delivery_id}")
@router.get("/webapi/proxy/deliveries/{delivery_id}")
async def proxy_get_delivery(delivery_id: int, user: str = Depends(get_current_user)):
    """Proxy GET delivery"""
    return await api_request("GET", f"/deliveries/{delivery_id}")

@router.delete("/api/proxy/deliveries/{delivery_id}")
@router.delete("/webapi/proxy/deliveries/{delivery_id}")
async def proxy_delete_delivery(delivery_id: int, user: str = Depends(get_current_user)):
    """Proxy DELETE delivery"""
    try:
        result = await api_request("DELETE", f"/deliveries/{delivery_id}")
        return result
    except Exception as e:
        logger.error(f"Error deleting delivery: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/proxy/deliveries/{delivery_id}/resend")
@router.post("/webapi/proxy/deliveries/{delivery_id}/resend")
@require_permission(ADMIN)
async def proxy_resend_delivery(request: Request, delivery_id: int):
    """Proxy POST to resend delivery"""
    return await api_request("POST", f"/deliveries/{delivery_id}/resend")

@router.post("/api/proxy/deliveries/{delivery_id}/abort")
@router.post("/webapi/proxy/deliveries/{delivery_id}/abort")
@require_permission(ADMIN)
async def proxy_abort_delivery(request: Request, delivery_id: int):
    """Proxy POST to abort delivery"""
    return await api_request("POST", f"/deliveries/{delivery_id}/abort")

@router.get("/api/proxy/messages/{message_id}")
@router.get("/webapi/proxy/messages/{message_id}")
async def proxy_get_message(message_id: int, user: str = Depends(get_current_user)):
    """Proxy GET message"""
    return await api_request("GET", f"/messages/{message_id}", params={"format": "json"})

@router.delete("/api/proxy/messages/{message_id}")
@router.delete("/webapi/proxy/messages/{message_id}")
async def proxy_delete_message(message_id: int, user: str = Depends(get_current_user)):
    """Proxy DELETE message"""
    try:
        result = await api_request("DELETE", f"/messages/{message_id}")
        return result
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/proxy/messages/{message_id}/cancel")
@router.post("/webapi/proxy/messages/{message_id}/cancel")
async def proxy_cancel_message(message_id: int, user: str = Depends(get_current_user)):
    """Proxy POST to cancel a message"""
    try:
        result = await api_request("POST", f"/messages/{message_id}/cancel")
        return result
    except Exception as e:
        logger.error(f"Error cancelling message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def view_prompts(request: Request, user: str = Depends(get_current_user)):
    """View and manage LLM prompts via API proxy"""
    return _ui_index_response()
    try:
        prompts = await api_request("GET", "/prompts")
        if not isinstance(prompts, list):
            prompts = []

        rows = []
        for prompt in prompts:
            rows.append(
                f"""
                <tr>
                    <td>{prompt.get("id")}</td>
                    <td>{prompt.get("name")}</td>
                    <td>{prompt.get("channel_type") or ""}</td>
                    <td>{prompt.get("group_id") or ""}</td>
                    <td>{prompt.get("language") or ""}</td>
                    <td>{prompt.get("keyword") or ""}</td>
                    <td>{prompt.get("priority")}</td>
                    <td>{'Yes' if prompt.get("enabled") else 'No'}</td>
                    <td>
                        <button onclick="deletePrompt({prompt.get('id')})" class="btn btn-danger">Delete</button>
                    </td>
                </tr>
                """
            )

        rows_html = "\n".join(rows) if rows else "<tr><td colspan='9'>No prompts found</td></tr>"

        content = f"""
        <div class="section">
            <h2>LLM Prompts</h2>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Channel</th>
                        <th>Group</th>
                        <th>Language</th>
                        <th>Keyword</th>
                        <th>Priority</th>
                        <th>Enabled</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Create Prompt</h2>
            <form id="create-prompt-form" onsubmit="createPrompt(event)">
                <div class="form-row">
                    <input type="text" name="name" placeholder="Name" required />
                    <input type="text" name="channel_type" placeholder="Channel type (email/sms/whatsapp/slack/teams)" />
                    <input type="text" name="group_id" placeholder="Group ID (optional)" />
                    <input type="text" name="language" placeholder="Language (optional)" />
                    <input type="text" name="keyword" placeholder="Keyword (optional)" />
                    <input type="number" name="priority" placeholder="Priority" value="0" />
                </div>
                <div class="form-row">
                    <textarea name="prompt_text" placeholder="Prompt text" required></textarea>
                </div>
                <div class="form-row">
                    <label><input type="checkbox" name="enabled" checked /> Enabled</label>
                </div>
                <button class="btn btn-primary" type="submit">Create</button>
            </form>
        </div>

        <div class="section">
            <h2>Update Prompt</h2>
            <form id="update-prompt-form" onsubmit="updatePrompt(event)">
                <div class="form-row">
                    <input type="number" name="prompt_id" placeholder="Prompt ID" required />
                    <input type="text" name="name" placeholder="Name (optional)" />
                    <input type="number" name="priority" placeholder="Priority (optional)" />
                </div>
                <div class="form-row">
                    <textarea name="prompt_text" placeholder="Prompt text (optional)"></textarea>
                </div>
                <div class="form-row">
                    <label><input type="checkbox" name="enabled" onchange="this.dataset.touched='1'" /> Enabled</label>
                </div>
                <button class="btn btn-secondary" type="submit">Update</button>
            </form>
        </div>

        <script>
            async function createPrompt(event) {{
                event.preventDefault();
                const form = event.target;
                const data = Object.fromEntries(new FormData(form).entries());
                data.enabled = form.enabled.checked;
                if (data.group_id === "") {{
                    delete data.group_id;
                }} else {{
                    data.group_id = parseInt(data.group_id, 10);
                }}
                data.priority = parseInt(data.priority || "0", 10);
                const response = await fetch("/webapi/proxy/prompts", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(data),
                }});
                if (response.ok) {{
                    window.location.reload();
                }} else {{
                    alert("Prompt creation failed");
                }}
            }}

            async function updatePrompt(event) {{
                event.preventDefault();
                const form = event.target;
                const data = Object.fromEntries(new FormData(form).entries());
                const promptId = data.prompt_id;
                delete data.prompt_id;
                if (data.name === "") delete data.name;
                if (data.prompt_text === "") delete data.prompt_text;
                if (data.priority === "") delete data.priority;
                const enabledTouched = form.enabled.dataset.touched === "1";
                if (enabledTouched) {{
                    data.enabled = form.enabled.checked;
                }}
                if (Object.keys(data).length === 0) {{
                    alert("No update fields provided");
                    return;
                }}
                const response = await fetch(`/webapi/proxy/prompts/${{promptId}}`, {{
                    method: "PATCH",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify(data),
                }});
                if (response.ok) {{
                    window.location.reload();
                }} else {{
                    alert("Prompt update failed");
                }}
            }}

            async function deletePrompt(promptId) {{
                if (!confirm("Delete this prompt?")) return;
                const response = await fetch(`/webapi/proxy/prompts/${{promptId}}`, {{
                    method: "DELETE"
                }});
                if (response.ok) {{
                    window.location.reload();
                }} else {{
                    alert("Prompt delete failed");
                }}
            }}
        </script>
        """

        html = get_base_layout("Prompts", "prompts", content, user)
        return HTMLResponse(content=html)
    except Exception as e:
        logger.error(f"Error loading prompts: {e}")
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

@router.get("/groups/add")
async def add_group_page(request: Request, user: str = Depends(get_current_user)):
    """Add new group page"""
    return _ui_index_response()
    nav = get_nav_menu("groups")

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Create Group - Notification Agent</title>
    <style>
        {get_common_styles()}
        .form-container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 600px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: #4a5568;
            font-weight: 500;
        }}
        .form-group input,
        .form-group textarea,
        .form-group select {{
            width: 100%;
            padding: 10px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 14px;
        }}
        .btn-submit {{
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }}
        .btn-submit:hover {{
            background: #5568d3;
        }}
    </style>
</head>
<body>
    {nav}
    <div class="container">
        <h1>➕ Create New Group</h1>
        <div class="form-container">
            <form id="group-form" onsubmit="createGroup(event)">
                <div class="form-group">
                    <label>Group Name *</label>
                    <input type="text" name="name" required />
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <textarea name="description" rows="3"></textarea>
                </div>
                <div class="form-group">
                    <label>Default Language</label>
                    <select name="language">
                        <option value="">Default</option>
                        <option value="en">English</option>
                        <option value="fr">French</option>
                        <option value="de">German</option>
                        <option value="es">Spanish</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Preferred Channel</label>
                    <select name="preferred_channel">
                        <option value="">Default</option>
                        <option value="email">Email</option>
                        <option value="sms">SMS</option>
                        <option value="whatsapp">WhatsApp</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Content Style</label>
                    <select name="content_style">
                        <option value="">Default</option>
                        <option value="html">HTML</option>
                        <option value="plain">Plain Text</option>
                        <option value="summary+link">Summary + Link</option>
                    </select>
                </div>
                <button type="submit" class="btn-submit">Create Group</button>
                <div id="result" style="margin-top: 15px;"></div>
            </form>
        </div>
    </div>
    <script>
        async function createGroup(event) {{
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('result');

            const data = {{
                name: formData.get('name'),
                description: formData.get('description') || null,
                language: formData.get('language') || null,
                preferred_channel: formData.get('preferred_channel') || null,
                content_style: formData.get('content_style') || null,
            }};

            try {{
                const response = await fetch('/webapi/proxy/groups', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                const result = await response.json();

                if (response.ok) {{
                    resultDiv.innerHTML = `<div style="color: green;">✅ Group created successfully! <a href="/groups">View Groups</a></div>`;
                    form.reset();
                }} else {{
                    resultDiv.innerHTML = `<div style="color: red;">❌ Error: ${{result.detail || 'Unknown error'}}</div>`;
                }}
            }} catch (error) {{
                resultDiv.innerHTML = `<div style="color: red;">❌ Request failed: ${{error.message}}</div>`;
            }}
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)

@router.get("/groups/{group_id}/edit")
async def edit_group_page(request: Request, group_id: int, user: str = Depends(get_current_user)):
    """Edit group page with base layout"""
    return _ui_index_response()
    user_data, checker = await get_user_with_permissions(request)

    # Check permission - admin or owner of this group
    if not checker.has_permission(ADMIN) and not checker.can_manage_group(str(group_id)):
        raise HTTPException(status_code=403, detail="Permission denied")

    try:
        group_data = await api_request("GET", _api_target_path(f"/groups/{group_id}"))
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

    content = f"""
    <style>
        .form-container {{
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 10px;
            max-width: 600px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-weight: 500;
        }}
        .form-group input,
        .form-group textarea,
        .form-group select {{
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-size: 14px;
        }}
        .btn-submit {{
            padding: 12px 24px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }}
        .btn-submit:hover {{
            background: var(--primary-hover);
        }}
        .members-section {{
            margin-top: 30px;
            background: var(--bg-secondary);
            padding: 30px;
            border-radius: 10px;
        }}
    </style>

    <div class="card">
        <h2>Edit Group: {group_data.get('name', 'Unknown')}</h2>
        <div class="form-container">
            <form id="group-form" onsubmit="updateGroup(event)">
                <div class="form-group">
                    <label>Group Name</label>
                    <input type="text" name="name" value="{group_data.get('name', '')}" readonly />
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <textarea name="description" rows="3">{group_data.get('description', '')}</textarea>
                </div>
                <div class="form-group">
                    <label>Default Language</label>
                    <select name="language">
                        <option value="" {'selected' if not group_data.get('language') else ''}>Default</option>
                        <option value="en" {'selected' if group_data.get('language') == 'en' else ''}>English</option>
                        <option value="fr" {'selected' if group_data.get('language') == 'fr' else ''}>French</option>
                        <option value="de" {'selected' if group_data.get('language') == 'de' else ''}>German</option>
                        <option value="es" {'selected' if group_data.get('language') == 'es' else ''}>Spanish</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Preferred Channel</label>
                    <select name="preferred_channel">
                        <option value="" {'selected' if not group_data.get('preferred_channel') else ''}>Default</option>
                        <option value="email" {'selected' if group_data.get('preferred_channel') == 'email' else ''}>Email</option>
                        <option value="sms" {'selected' if group_data.get('preferred_channel') == 'sms' else ''}>SMS</option>
                        <option value="whatsapp" {'selected' if group_data.get('preferred_channel') == 'whatsapp' else ''}>WhatsApp</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Content Style</label>
                    <select name="content_style">
                        <option value="" {'selected' if not group_data.get('content_style') else ''}>Default</option>
                        <option value="html" {'selected' if group_data.get('content_style') == 'html' else ''}>HTML</option>
                        <option value="plain" {'selected' if group_data.get('content_style') == 'plain' else ''}>Plain Text</option>
                        <option value="summary+link" {'selected' if group_data.get('content_style') == 'summary+link' else ''}>Summary + Link</option>
                    </select>
                </div>
                <button type="submit" class="btn-submit">Update Group</button>
                <div id="result" style="margin-top: 15px;"></div>
            </form>
        </div>

        <div class="members-section">
            <h2>Group Members</h2>
            <div id="members-list">
                <table>
                    <thead>
                        <tr>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Role</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'<tr><td>{m.get("username", m.get("user_id", "-"))}</td><td>{m.get("email", "-")}</td><td>{m.get("role", "member")}</td></tr>' for m in group_data.get('members', [])]) if group_data.get('members') else '<tr><td colspan="3">No members in this group.</td></tr>'}
                    </tbody>
                </table>
            </div>
            {f'<a href="/groups/{group_id}/assign-owner" class="btn">Assign Owner</a>' if checker.has_permission(ADMIN) or checker.can_manage_group(str(group_id)) else ''}
        </div>
        <div style="margin-top: 20px;">
            <a href="/groups" class="btn btn-secondary">← Back to Groups</a>
        </div>
    </div>

    <script>
        async function updateGroup(event) {{
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('result');

            const data = {{
                description: formData.get('description') || null,
                language: formData.get('language') || null,
                preferred_channel: formData.get('preferred_channel') || null,
                content_style: formData.get('content_style') || null,
            }};

            try {{
                const response = await fetch(`/webapi/proxy/groups/{group_id}`, {{
                    method: 'PUT',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(data)
                }});

                const result = await response.json();

                if (response.ok) {{
                    resultDiv.innerHTML = `<div style="color: green; padding: 10px; background: rgba(72, 187, 120, 0.1); border-radius: 6px;">✅ Group updated successfully!</div>`;
                }} else {{
                    resultDiv.innerHTML = `<div style="color: red; padding: 10px; background: rgba(229, 62, 62, 0.1); border-radius: 6px;">❌ Error: ${{result.detail || 'Unknown error'}}</div>`;
                }}
            }} catch (error) {{
                resultDiv.innerHTML = `<div style="color: red; padding: 10px; background: rgba(229, 62, 62, 0.1); border-radius: 6px;">❌ Request failed: ${{error.message}}</div>`;
            }}
        }}
    </script>
"""
    html = get_base_layout(f"Edit Group: {group_data.get('name', 'Unknown')}", "groups", content, user)
    return HTMLResponse(content=html)

@router.get("/groups/{group_id}/assign-owner")
@require_permission(ADMIN)
async def assign_owner_page(request: Request, group_id: int):
    """Assign owner to group page"""
    return _ui_index_response()
    nav = get_nav_menu("groups")

    try:
        group_data = await api_request("GET", _api_target_path(f"/groups/{group_id}"))
        users_data = await api_request("GET", _api_target_path("/users"))
    except Exception as e:
        return HTMLResponse(content=f"<h1>Error: {str(e)}</h1>", status_code=500)

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Assign Owner - Notification Agent</title>
    <style>
        {get_common_styles()}
        .form-container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 600px;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        .form-group label {{
            display: block;
            margin-bottom: 8px;
            color: #4a5568;
            font-weight: 500;
        }}
        .form-group select {{
            width: 100%;
            padding: 10px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 14px;
        }}
        .btn-submit {{
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    {nav}
    <div class="container">
        <h1>👤 Assign Owner to Group: {group_data.get('name', 'Unknown')}</h1>
        <div class="form-container">
            <form id="owner-form" onsubmit="assignOwner(event)">
                <div class="form-group">
                    <label>Select User</label>
                    <select name="user_id" required>
                        <option value="">-- Select User --</option>
                        {' '.join([f'<option value="{u.get("id")}">{u.get("username")} ({u.get("email", "")})</option>' for u in users_data.get('items', [])])}
                    </select>
                </div>
                <button type="submit" class="btn-submit">Assign as Owner</button>
                <div id="result" style="margin-top: 15px;"></div>
            </form>
        </div>
    </div>
    <script>
        async function assignOwner(event) {{
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const resultDiv = document.getElementById('result');

            const userId = formData.get('user_id');

            try {{
                // First add user to group as member, then update role to owner
                const addResponse = await fetch(`/webapi/proxy/groups/{group_id}/members`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ user_id: parseInt(userId), role: 'owner' }})
                }});

                if (addResponse.ok) {{
                    resultDiv.innerHTML = `<div style="color: green;">✅ Owner assigned successfully! <a href="/groups/{group_id}/edit">Back to Group</a></div>`;
                }} else {{
                    const result = await addResponse.json();
                    resultDiv.innerHTML = `<div style="color: red;">❌ Error: ${{result.detail || 'Unknown error'}}</div>`;
                }}
            }} catch (error) {{
                resultDiv.innerHTML = `<div style="color: red;">❌ Request failed: ${{error.message}}</div>`;
            }}
        }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


# Proxy endpoint for config updates

@router.get("/api/proxy/config")
@router.get("/webapi/proxy/config")
@require_permission(CONFIG_READ)
async def proxy_config_dump(request: Request):
    """Proxy GET to fetch the masked configuration dump for the monorepo UI."""
    return await api_request("GET", "/config")

@router.post("/api/proxy/config/query")
@router.post("/webapi/proxy/config/query")
@require_permission(CONFIG_READ)
async def proxy_config_query(request: Request):
    """Proxy POST to query configuration values."""
    data = await request.json()
    return await api_request("POST", "/config/query", data=data)

@router.post("/api/proxy/config/update")
@router.post("/webapi/proxy/config/update")
@require_permission(CONFIG_WRITE)
async def proxy_config_update(request: Request):
    """Proxy POST to update configuration"""
    data = await request.json()
    if data.get("persist") and not config.get("app.env_write_enabled"):
        data["persist"] = False
    return await api_request("POST", "/config/update", data=data)

def _job_identity_values(job: Any) -> set[str]:
    """Return stable lowercase owner identifiers from a job payload."""
    if not isinstance(job, dict):
        return set()
    values = {
        job.get("request_auth_identity"),
        job.get("user_id"),
    }
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def _user_identity_values(user_data: dict[str, Any]) -> set[str]:
    """Return stable lowercase identifiers for the current web user."""
    values = {
        user_data.get("id"),
        user_data.get("username"),
        user_data.get("email"),
        user_data.get("display_name"),
        user_data.get("displayName"),
    }
    return {str(value).strip().lower() for value in values if str(value or "").strip()}


def _job_owned_by_user(job: Any, user_data: dict[str, Any]) -> bool:
    """Apply PS-76 JW6 own-job visibility semantics."""
    job_values = _job_identity_values(job)
    if not job_values:
        return False
    return bool(job_values & _user_identity_values(user_data))


async def _require_admin_or_owned_job(request: Request, job_id: str) -> None:
    """Permit admin users or the owner of a job to run non-delete lifecycle actions."""
    user_data, checker = await get_user_with_permissions(request)
    if checker.has_permission(ADMIN):
        return
    job = await api_request("GET", f"/jobs/{job_id}")
    if _job_owned_by_user(job, user_data):
        return
    raise HTTPException(status_code=403, detail="Permission denied: job is not owned by current user")


@router.get("/api/proxy/jobs")
@router.get("/webapi/proxy/jobs")
@require_permission(LIST)
async def proxy_list_jobs(request: Request):
    """Proxy GET to list jobs for the monorepo UI."""
    payload = await api_request("GET", "/jobs", params=dict(request.query_params))
    user_data, checker = await get_user_with_permissions(request)
    if checker.has_permission(ADMIN):
        return payload
    if not isinstance(payload, dict):
        return payload
    items = payload.get("items")
    if not isinstance(items, list):
        return payload
    visible = [item for item in items if _job_owned_by_user(item, user_data)]
    next_payload = dict(payload)
    next_payload["items"] = visible
    next_payload["total"] = len(visible)
    return next_payload

@router.get("/api/proxy/jobs/queue/status")
@router.get("/webapi/proxy/jobs/queue/status")
@require_permission(LIST)
async def proxy_job_queue_status(request: Request):
    """Proxy GET to job queue status for metrics."""
    return await api_request("GET", "/jobs/queue/status")

@router.get("/api/proxy/jobs/{job_id}")
@router.get("/webapi/proxy/jobs/{job_id}")
@require_permission(LIST)
async def proxy_get_job(request: Request, job_id: str):
    """Proxy GET to a single job record."""
    job = await api_request("GET", f"/jobs/{job_id}")
    user_data, checker = await get_user_with_permissions(request)
    if checker.has_permission(ADMIN) or _job_owned_by_user(job, user_data):
        return job
    raise HTTPException(status_code=403, detail="Permission denied: job is not owned by current user")

@router.post("/api/proxy/jobs/{job_id}/cancel")
@router.post("/webapi/proxy/jobs/{job_id}/cancel")
@require_permission(LIST)
async def proxy_cancel_job(request: Request, job_id: str):
    """Proxy POST to cancel a job."""
    await _require_admin_or_owned_job(request, job_id)
    return await api_request("POST", f"/jobs/{job_id}/cancel")

@router.post("/api/proxy/jobs/{job_id}/retry")
@router.post("/webapi/proxy/jobs/{job_id}/retry")
@require_permission(LIST)
async def proxy_retry_job(request: Request, job_id: str):
    """Proxy POST to retry a job."""
    await _require_admin_or_owned_job(request, job_id)
    return await api_request("POST", f"/jobs/{job_id}/retry")

@router.delete("/api/proxy/jobs/{job_id}")
@router.delete("/webapi/proxy/jobs/{job_id}")
async def proxy_delete_job(request: Request, job_id: str):
    """Proxy DELETE to archive a terminal job; admin-only."""
    user_data, checker = await get_user_with_permissions(request)
    if not checker.has_permission(ADMIN):
        raise HTTPException(status_code=403, detail="Permission denied: notification:admin:*")
    return await api_request("DELETE", f"/jobs/{job_id}")


# Proxy endpoints for prompts

@router.get("/api/proxy/prompts")
@router.get("/webapi/proxy/prompts")
async def proxy_list_prompts(user: str = Depends(get_current_user)):
    """Proxy GET to list prompts"""
    return await api_request("GET", "/prompts")

@router.post("/api/proxy/prompts")
@router.post("/webapi/proxy/prompts")
@require_permission(CONFIG_WRITE)
async def proxy_create_prompt(request: Request):
    """Proxy POST to create prompt"""
    data = await request.json()
    return await api_request("POST", "/prompts", data=data)

@router.patch("/api/proxy/prompts/{prompt_id}")
@router.patch("/webapi/proxy/prompts/{prompt_id}")
@require_permission(CONFIG_WRITE)
async def proxy_update_prompt(request: Request, prompt_id: int):
    """Proxy PATCH to update prompt"""
    data = await request.json()
    return await api_request("PATCH", f"/prompts/{prompt_id}", data=data)

@router.delete("/api/proxy/prompts/{prompt_id}")
@router.delete("/webapi/proxy/prompts/{prompt_id}")
@require_permission(CONFIG_WRITE)
async def proxy_delete_prompt(request: Request, prompt_id: int):
    """Proxy DELETE to remove prompt"""
    return await api_request("DELETE", f"/prompts/{prompt_id}")


# Add proxy endpoints for groups

@router.get("/api/proxy/groups")
@router.get("/webapi/proxy/groups")
async def proxy_list_groups(user: str = Depends(get_current_user)):
    """Proxy GET to list groups for the monorepo UI."""
    return await api_request("GET", "/groups")

@router.get("/api/proxy/groups/{group_id}")
@router.get("/webapi/proxy/groups/{group_id}")
async def proxy_get_group(group_id: int, user: str = Depends(get_current_user)):
    """Proxy GET to fetch a group for the monorepo UI."""
    return await api_request("GET", f"/groups/{group_id}")

@router.post("/api/proxy/groups")
@router.post("/webapi/proxy/groups")
@require_permission(ADMIN)
async def proxy_create_group(request: Request):
    """Proxy POST to create group"""
    data = await request.json()
    return await api_request("POST", _api_target_path("/groups"), data=data)

@router.put("/api/proxy/groups/{group_id}")
@router.put("/webapi/proxy/groups/{group_id}")
@require_permission(ADMIN)
async def proxy_update_group(request: Request, group_id: int):
    """Proxy PUT to update group"""
    data = await request.json()
    return await api_request("PATCH", _api_target_path(f"/groups/{group_id}"), data=data)

@router.delete("/api/proxy/groups/{group_id}")
@router.delete("/webapi/proxy/groups/{group_id}")
@require_permission(ADMIN)
async def proxy_delete_group(request: Request, group_id: int):
    """Proxy DELETE to remove group"""
    return await api_request("DELETE", _api_target_path(f"/groups/{group_id}"))

@router.get("/api/proxy/groups/{group_id}/members")
@router.get("/webapi/proxy/groups/{group_id}/members")
async def proxy_get_group_members(group_id: int, user: str = Depends(get_current_user)):
    """Proxy GET to get group members"""
    from ...database.repositories import GroupMemberRepository

    db = get_db_manager()
    member_repo = GroupMemberRepository(db)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, member_repo.get_group_members, group_id)

@router.post("/api/proxy/groups/{group_id}/members")
@router.post("/webapi/proxy/groups/{group_id}/members")
@require_permission(ADMIN)
async def proxy_add_group_member(request: Request, group_id: int):
    """Proxy POST to add group member"""
    data = await request.json()
    return await api_request("POST", _api_target_path(f"/groups/{group_id}/members"), data=data)

@router.delete("/api/proxy/groups/{group_id}/members/{user_id}")
@router.delete("/webapi/proxy/groups/{group_id}/members/{user_id}")
@require_permission(ADMIN)
async def proxy_remove_group_member(request: Request, group_id: int, user_id: int):
    """Proxy DELETE to remove group member"""
    return await api_request("DELETE", _api_target_path(f"/groups/{group_id}/members/{user_id}"))

@router.put("/api/proxy/groups/{group_id}/members/{user_id}/role")
@router.put("/webapi/proxy/groups/{group_id}/members/{user_id}/role")
@require_permission(ADMIN)
async def proxy_update_group_member_role(request: Request, group_id: int, user_id: int):
    """Proxy PUT to update group member role"""
    data = await request.json()
    role = data.get("role")
    if not role:
        raise HTTPException(status_code=400, detail="role is required")
    return await api_request(
        "PUT",
        _api_target_path(f"/groups/{group_id}/members/{user_id}/role"),
        params={"role": role},
    )


# W28A-876: cookie-auth bridge for the shared @cloud-dog/idam pages. They call
# /v1/admin/<entity> (apiBaseUrl="/webapi"); this forwards to the API server's
# canonical /api/v1/admin/<entity> (SqlAlchemyRoleStore-backed) with the
# session-validated api-key injected by api_request.
@router.api_route("/webapi/v1/admin/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_idam_admin(request: Request, path: str, user: str = Depends(get_current_user)):
    method = request.method.upper()
    data = None
    if method in ("POST", "PUT", "PATCH"):
        try:
            data = await request.json()
        except Exception:
            data = None
    return await api_request(method, f"/api/v1/admin/{path}", data=data, params=dict(request.query_params))


# W28A-876: forward the canonical /idam/v1/* surface (resource-registry + rbac-bindings)
# to the api server's mounted shared cloud_dog_idam idam_v1_router, so the RBAC page resolves.
@router.api_route("/webapi/v1/idam/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_idam_v1(request: Request, path: str, user: str = Depends(get_current_user)):
    method = request.method.upper()
    data = None
    if method in ("POST", "PUT", "PATCH"):
        try:
            data = await request.json()
        except Exception:
            data = None
    return await api_request(method, f"/api/v1/idam/v1/{path}", data=data, params=dict(request.query_params))
