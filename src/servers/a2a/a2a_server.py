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
Description: A2A (Agent-to-Agent) Server for Notification Agent - Provides WebSocket streaming for real-time notification events and natural language command processing

Related Requirements: FR1.5, FR1.15, UC1.2
Related Tasks: T11
Related Architecture: CC1.4
Related Tests: IT1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import json
import asyncio
import time
from datetime import datetime
from typing import Any, Set
from uuid import uuid4
import inspect
from cloud_dog_api_kit.clients import ClientTimeout, create_http_client
from fastapi import WebSocket, WebSocketDisconnect, Request, Header, HTTPException
from fastapi.responses import HTMLResponse

from ...config import get_config
from ...utils.logger import PlatformContextMiddleware, apply_platform_context, setup_logger
from cloud_dog_api_kit import create_app as platform_create_app, create_health_router
from cloud_dog_api_kit.a2a.card import create_a2a_card_router, A2ASkill
from cloud_dog_api_kit.lifecycle.hooks import LifecycleHooks


_temp_cfg = get_config()

# Global configuration
config = None
logger = None
heartbeat_task_handle = None
# Shared long-lived HTTP client for A2A-to-API calls (W28A-93b, AGENT-LESSONS §2.3)
_a2a_http_client: Any = None

# Active WebSocket connections
active_connections: Set[WebSocket] = set()
topic_subscriptions: dict = {}  # topic -> set of websockets


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _require_config(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _require_internal_api_key(x_api_key: str | None) -> str:
    expected = _require_config(config.get("a2a_server.api_key") or config.get("api_server.api_key"), "a2a_server.api_key/api_server.api_key")
    provided = (x_api_key or "").strip()
    if provided != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return provided


async def _startup(app):
    """Initialize server on startup via platform lifecycle hooks."""
    global config, logger, heartbeat_task_handle

    config = get_config()

    logger = setup_logger(
        name="a2a_server",
        log_file=_require_config(config.get("log.a2a_server_log"), "log.a2a_server_log"),
        log_level=_require_config(config.get("log.level"), "log.level"),
        log_format=_require_config(config.get("log.format"), "log.format"),
        console=_require_config(config.get("log.console"), "log.console"),
    )

    logger.info("Starting A2A server...")
    heartbeat_task_handle = asyncio.create_task(heartbeat_task())
    logger.info("A2A server started successfully")


async def _shutdown(app):
    """Shutdown hook for A2A lifecycle."""
    global heartbeat_task_handle
    if heartbeat_task_handle is not None:
        heartbeat_task_handle.cancel()
        try:
            await heartbeat_task_handle
        except asyncio.CancelledError:
            pass
        heartbeat_task_handle = None
    if logger:
        logger.info("A2A server shutting down")


_lifecycle_hooks = LifecycleHooks(on_post_router=_startup, on_shutdown=_shutdown)
_request_timeout = float(_temp_cfg.get("api_server.request_timeout") or 300)
_app_kwargs = {
    "title": "Notification Agent A2A Server",
    "version": "0.1.0",
    "description": "Agent-to-agent streaming and natural-language dispatch surface",
    "base_path": _temp_cfg.get("a2a_server.base_path", ""),
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

app.add_middleware(PlatformContextMiddleware, logger_name="a2a_server")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.monotonic()
    request_id = request.headers.get("x-request-id") or uuid4().hex
    client_ip = _get_client_ip(request)
    response = None
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        success = status_code < 400
        if logger:
            logger.info(
                "a2a_request",
                extra={
                    "client_ip": client_ip,
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "success": success,
                    "query_params": dict(request.query_params),
                },
            )
        if response is not None:
            response.headers["X-Request-Id"] = request_id


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with connection info"""
    ws_endpoint = _require_config(config.get("a2a_server.websocket_url"), "a2a_server.websocket_url")
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>A2A Server - Notification Agent</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f7fa;
        }
        .card {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2d3748;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #718096;
            margin-bottom: 30px;
        }
        .topic {
            background: #f7fafc;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        .topic h3 {
            margin: 0 0 8px 0;
            color: #4a5568;
        }
        .topic p {
            margin: 0;
            color: #718096;
            font-size: 14px;
        }
        code {
            background: #edf2f7;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }
        .status {
            color: #48bb78;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>🔗 A2A Server</h1>
        <p class="subtitle">Agent-to-Agent Real-time Streaming</p>
        
        <p><strong>Status:</strong> <span class="status">● Online</span></p>
        <p><strong>WebSocket Endpoint:</strong> <code>__WS_ENDPOINT__</code></p>
        
        <h2>Available Topics</h2>
        
        <div class="topic">
            <h3>notifications.events</h3>
            <p>Stream all notification events (submit, send, deliver, fail)</p>
        </div>
        
        <div class="topic">
            <h3>deliveries.{{id}}</h3>
            <p>Stream updates for a specific delivery by ID</p>
        </div>
        
        <div class="topic">
            <h3>channels.state</h3>
            <p>Stream channel state changes (enabled, disabled, circuit breaker events)</p>
        </div>
        
        <h2>Connection Example</h2>
        <pre style="background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 5px; overflow-x: auto;">
const ws = new WebSocket('__WS_ENDPOINT__');

ws.onopen = () => {{
  // Subscribe to topic
  ws.send(JSON.stringify({{
    action: 'subscribe',
    topic: 'notifications.events'
  }}));
}};

ws.onmessage = (event) => {{
  const data = JSON.parse(event.data);
  console.log('Received:', data);
}};
        </pre>
    </div>
</body>
</html>
"""
    html = (
        html_template
        .replace("__WS_ENDPOINT__", ws_endpoint)
        .replace("{{", "{")
        .replace("}}", "}")
    )
    return HTMLResponse(content=html)


# Platform health via create_health_router().
_a2a_health_paths = {"/health", "/ready", "/live", "/status"}
app.router.routes = [
    r for r in app.router.routes if getattr(r, "path", None) not in _a2a_health_paths
]
_a2a_env_file = ""
if config:
    _a2a_env_file = str(config.get("app.env_file") or "")
app.include_router(create_health_router(
    application_name="notification-agent-mcp-server",
    version="0.1.0",
    env_file=_a2a_env_file,
))

# --- A2A skill handlers (real service logic) ---


async def _a2a_list_channels(text: str) -> str:
    """List configured notification channels from the database."""
    try:
        from ...database import get_db_manager
        from ...database.repositories import ChannelRepository
        from ...config import get_config as _get_cfg
        _cfg = _get_cfg()
        db_uri = _cfg.get("db.uri")
        if not db_uri:
            return "Error: db.uri not configured"
        db = get_db_manager(db_uri)
        repo = ChannelRepository(db)
        channels = repo.list_all()
        if not channels:
            return "No notification channels configured"
        lines = [
            f"- {ch.get('name', '?')} (type={ch.get('channel_type', '?')}, enabled={ch.get('enabled', '?')})"
            for ch in channels[:30]
        ]
        return f"Found {len(channels)} channels:\n" + "\n".join(lines)
    except Exception as exc:
        return f"Error listing channels: {exc}"


async def _a2a_send_notification(text: str) -> str:
    """Send a notification by forwarding to the /notify/natural endpoint logic."""
    try:
        from ...database import get_db_manager
        from ...core.resolvers import NaturalLanguageParser
        _cfg = get_config()
        db_uri = _cfg.get("db.uri")
        if not db_uri:
            return "Error: db.uri not configured"
        db = get_db_manager(db_uri)
        db.connect()
        parser = NaturalLanguageParser(db)
        parsed = parser.parse(text)

        api_base_url = _cfg.get("api_server.base_url") or _cfg.get("a2a_server.api_base_url")
        if not api_base_url:
            return "Error: api_server.base_url not configured"
        api_key = _cfg.get("a2a_server.api_key") or _cfg.get("api_server.api_key") or ""

        destinations = []
        default_channel = _cfg.get("default_channel") or "loopback"
        for recipient in parsed.get("recipients", []):
            destinations.append({"channel": default_channel, "address": recipient})
        for group_name in parsed.get("groups", []):
            destinations.append({"channel": default_channel, "address": f"group:{group_name}"})

        if not destinations:
            return f"No recipients resolved from: {text}"

        payload = {
            "destinations": destinations,
            "content": parsed.get("content", [{"type": "text", "body": text}]),
            "options": {},
        }
        if parsed.get("subject"):
            payload["options"]["subject"] = parsed["subject"]

        global _a2a_http_client
        if _a2a_http_client is None or _a2a_http_client.is_closed:
            _a2a_http_client = create_http_client(
                timeout=ClientTimeout(connect=5.0, read=30.0, total=30.0)
            )
        resp = await _a2a_http_client.post(
            f"{api_base_url}/messages",
            json=payload,
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        result = resp.json()
        return f"Notification sent. message_id={result.get('message_id', '?')}"
    except Exception as exc:
        return f"Error sending notification: {exc}"


async def _a2a_get_status(text: str) -> str:
    """Return notification system status."""
    try:
        from ...database import get_db_manager
        from ...database.repositories import ChannelRepository
        from ...config import get_config as _get_cfg
        _cfg = _get_cfg()
        db_uri = _cfg.get("db.uri")
        if not db_uri:
            return "Error: db.uri not configured"
        db = get_db_manager(db_uri)
        channels = ChannelRepository(db).list_all()
        enabled = [c for c in channels if c.get("enabled")]
        return (
            f"Notification system status:\n"
            f"- Total channels: {len(channels)}\n"
            f"- Enabled channels: {len(enabled)}\n"
            f"- WebSocket connections: {len(active_connections)}\n"
            f"- Active topics: {len(topic_subscriptions)}"
        )
    except Exception as exc:
        return f"Error getting status: {exc}"


# A2A agent card and task submission router
_a2a_skills = [
    A2ASkill(id="send_notification", name="Send Notification", description="Send a notification via configured channels", handler=_a2a_send_notification),
    A2ASkill(id="list_channels", name="List Channels", description="List available notification channels", handler=_a2a_list_channels),
    A2ASkill(id="get_status", name="Get Status", description="Get notification delivery status", handler=_a2a_get_status),
]
_a2a_card_router = create_a2a_card_router(
    name="notification-agent",
    description="Notification agent A2A server for real-time notification streaming and dispatch",
    skills=_a2a_skills,
)
app.include_router(_a2a_card_router)


@app.post("/notify/natural")
async def notify_natural(request: Request, body: dict = None):
    """
    Send notification using natural language command

    Example:
    {
        "command": "Send notification to Fred that JOB XXXX has finished",
        "channels": ["<DEFAULT_CHANNEL_NAME>"]  # Optional
    }
    """
    # Parse body from request if not injected by FastAPI
    if body is None:
        try:
            body = await request.json()
        except Exception:
            body = {}
    # PS-70 UM3 RBAC: require notification:send:execute permission
    user = getattr(getattr(request, "state", None), "user", None)
    if user is not None:
        uid = str(getattr(user, "user_id", ""))
        if uid and uid not in {"notification-api", "bootstrap-admin", "api-runtime"}:
            from ...core.idam.runtime import get_idam_runtime
            rt = get_idam_runtime()
            if not (rt.rbac_engine.has_permission(uid, "notification:send:execute")
                    or rt.rbac_engine.has_permission(uid, "*")):
                raise HTTPException(status_code=403, detail="Permission denied: notification:send:execute")
    from ...database import get_db_manager
    from ...core.resolvers import NaturalLanguageParser
    command = body.get("command", "")
    specified_channels = body.get("channels", [])
    
    if not command:
        return {"error": "command is required"}
    
    # Parse natural language command
    from ...config import get_config
    temp_config = get_config()
    db_uri = _require_config(temp_config.get("db.uri"), "db.uri")
    db = get_db_manager(db_uri)
    db.connect()
    parser = NaturalLanguageParser(db)
    parsed = parser.parse(command)
    
    # Get API configuration - prioritize api_server.base_url over a2a_server.api_base_url
    # This ensures A2A server uses the same API server as configured for the system
    api_base_url = config.get("api_server.base_url") or config.get("a2a_server.api_base_url")
    api_base_url = _require_config(api_base_url, "api_server.base_url/a2a_server.api_base_url")
    api_key = config.get("a2a_server.api_key") or config.get("api_server.api_key")
    api_key = _require_config(api_key, "a2a_server.api_key/api_server.api_key")
    
    # Build destinations from parsed recipients and groups
    destinations = []
    
    # Add individual recipients
    for recipient in parsed.get("recipients", []):
        if specified_channels:
            for channel in specified_channels:
                destinations.append({
                    "channel": channel,
                    "address": recipient,
                })
        else:
            default_channel = _require_config(config.get("default_channel"), "default_channel")
            destinations.append({
                "channel": default_channel,
                "address": recipient,
            })
    
    # Add group destinations
    for group_name in parsed.get("groups", []):
        if specified_channels:
            for channel in specified_channels:
                destinations.append({
                    "channel": channel,
                    "address": f"group:{group_name}",
                })
        else:
            default_channel = _require_config(config.get("default_channel"), "default_channel")
            destinations.append({
                "channel": default_channel,
                "address": f"group:{group_name}",
            })
    
    # Build message payload
    if not destinations:
        logger.warning("Natural notification command resolved no recipients or groups", extra={"command": command})
        return {
            "success": False,
            "error": "No recipients or groups could be resolved from the command",
            "parsed": parsed,
        }

    payload = {
        "destinations": destinations,
        "content": parsed.get("content", [{"type": "text", "body": command}]),
        "options": {},
    }
    
    if parsed.get("subject"):
        payload["options"]["subject"] = parsed["subject"]
    
    # Send via API using shared long-lived client
    try:
        global _a2a_http_client
        if _a2a_http_client is None or _a2a_http_client.is_closed:
            _a2a_http_client = create_http_client(
                timeout=ClientTimeout(connect=5.0, read=30.0, total=30.0)
            )
        response = await _a2a_http_client.post(
            f"{api_base_url}/messages",
            json=payload,
            headers={"X-API-Key": api_key},
        )
        response.raise_for_status()
        result = response.json()

        return {
            "success": True,
            "message_id": result.get("message_id"),
            "parsed": parsed,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return {
            "success": False,
            "error": str(e),
            "parsed": parsed,
        }


@app.post("/internal/events/broadcast")
async def internal_broadcast_event(
    request: dict,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Receive authenticated internal events from the API process and relay to subscribers."""
    _require_internal_api_key(x_api_key)
    topic = _require_config(request.get("topic"), "topic")
    data = request.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="data must be an object")

    await broadcast_event(topic, data)
    return {"success": True, "topic": topic, "subscriber_count": len(topic_subscriptions.get(topic, set()))}


@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming"""
    apply_platform_context("a2a_server")
    conn_id = uuid4().hex
    client_ip = websocket.client.host if websocket.client else "unknown"
    session_id = websocket.headers.get("x-session-id") or websocket.query_params.get("session_id")
    await websocket.accept()
    active_connections.add(websocket)
    
    logger.info(
        "a2a_ws_connect",
        extra={
            "client_ip": client_ip,
            "session_id": session_id,
            "request_id": conn_id,
            "success": True,
        },
    )
    logger.info(f"New WebSocket connection. Total connections: {len(active_connections)}")
    
    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to A2A streaming server",
            "timestamp": datetime.now().isoformat(),
        })
        
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            action = message.get("action")
            topic = message.get("topic")
            
            if action == "subscribe" and topic:
                # Subscribe to topic
                if topic not in topic_subscriptions:
                    topic_subscriptions[topic] = set()
                topic_subscriptions[topic].add(websocket)
                
                await websocket.send_json({
                    "type": "subscribed",
                    "topic": topic,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info(
                    "a2a_ws_subscribe",
                    extra={
                        "client_ip": client_ip,
                        "session_id": session_id,
                        "request_id": conn_id,
                        "success": True,
                        "path": f"topic:{topic}",
                    },
                )
                logger.info(f"Client subscribed to topic: {topic}")
            
            elif action == "unsubscribe" and topic:
                # Unsubscribe from topic
                if topic in topic_subscriptions:
                    topic_subscriptions[topic].discard(websocket)
                    if not topic_subscriptions[topic]:
                        del topic_subscriptions[topic]
                
                await websocket.send_json({
                    "type": "unsubscribed",
                    "topic": topic,
                    "timestamp": datetime.now().isoformat(),
                })
                logger.info(
                    "a2a_ws_unsubscribe",
                    extra={
                        "client_ip": client_ip,
                        "session_id": session_id,
                        "request_id": conn_id,
                        "success": True,
                        "path": f"topic:{topic}",
                    },
                )
                logger.info(f"Client unsubscribed from topic: {topic}")
            
            elif action == "ping":
                # Respond to ping
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown action: {action}",
                    "timestamp": datetime.now().isoformat(),
                })
    
    except WebSocketDisconnect:
        logger.info(
            "a2a_ws_disconnect",
            extra={
                "client_ip": client_ip,
                "session_id": session_id,
                "request_id": conn_id,
                "success": True,
            },
        )
        logger.info("WebSocket disconnected")
    
    except Exception as e:
        logger.error(
            f"WebSocket error: {e}",
            extra={
                "client_ip": client_ip,
                "session_id": session_id,
                "request_id": conn_id,
                "success": False,
            },
        )
    
    finally:
        # Clean up on disconnect
        active_connections.discard(websocket)
        
        # Remove from all topic subscriptions
        for topic, subscribers in list(topic_subscriptions.items()):
            subscribers.discard(websocket)
            if not subscribers:
                del topic_subscriptions[topic]
        
        logger.info(f"Connection closed. Remaining connections: {len(active_connections)}")


async def broadcast_event(topic: str, event_data: dict):
    """Broadcast an event to all subscribers of a topic
    
    Args:
        topic: Topic to broadcast to
        event_data: Event data to send
    """
    if topic not in topic_subscriptions:
        return
    
    subscribers = topic_subscriptions[topic].copy()
    
    message = {
        "type": "event",
        "topic": topic,
        "data": event_data,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Send to all subscribers
    disconnected = set()
    for websocket in subscribers:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send to subscriber: {e}")
            disconnected.add(websocket)
    
    # Clean up disconnected websockets
    for websocket in disconnected:
        active_connections.discard(websocket)
        topic_subscriptions[topic].discard(websocket)


# Example: Background task to send periodic heartbeats
async def heartbeat_task():
    """Send periodic heartbeat to all connections"""
    while True:
        await asyncio.sleep(30)  # Every 30 seconds
        
        if active_connections:
            disconnected = set()
            for websocket in active_connections.copy():
                try:
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception:
                    disconnected.add(websocket)
            
            # Clean up disconnected
            for websocket in disconnected:
                active_connections.discard(websocket)


if __name__ == "__main__":
    import uvicorn
    
    temp_config = get_config()
    port = temp_config.get("a2a_server.port", 8082)
    host = temp_config.get("a2a_server.host", "0.0.0.0")
    
    getattr(uvicorn, "run")(app, host=host, port=port)
