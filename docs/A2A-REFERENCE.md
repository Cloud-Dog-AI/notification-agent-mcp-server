---
template-id: T-A2A
template-version: 1.0
applies-to: docs/A2A-REFERENCE.md
registry: service
required: must-have
when-applicable: ""
template-last-updated: 2026-06-12
template-owner: platform-standards

project: notification-agent-mcp-server
doc-last-updated: 2026-06-12
doc-git-commit: 8f1c4ef96bb22e6efad26b5a38027df0a0b7ef41
doc-git-branch: main
doc-source-shas: []
doc-age-policy: 90d
doc-conformance-stamp: 2026-06-12T12:00:00Z
---

# notification-agent-mcp-server — A2A-REFERENCE

> **Template version:** T-A2A v1.0 — Agent-to-Agent endpoint surface.

## 1. Auth model
A2A auth (`api_key` typically); service-key vs role-key forwarding; RBAC enforcement point.

## 2. Endpoints

| Method | Path | Auth | RBAC | Summary |
|---|---|---|---|---|

## 3. Message envelope
A2A request/response shape; correlation IDs; streaming behaviour.

## 4. Tools (re-exposed)
List of tools available via A2A and their MCP-equivalent.

## 5. Examples
**You MUST include:** at least one worked A2A call from an upstream service.

## 6. Cross-references
- [API-REFERENCE.md](API-REFERENCE.md)
- [MCP-REFERENCE.md](MCP-REFERENCE.md)
- PS-72-mcp-a2a-webui.md
- PS-72b-agent-to-agent.md

## 7. Project-specific notes



<!-- W28C-1710a recovery: full content from archive/2026-06-12/A2A_SERVER.md (archived sha256=a992b8566967, 161 lines) -->

## Recovered domain content — `archive/2026-06-12/A2A_SERVER.md` (161 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/A2A_SERVER.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# A2A Server Documentation
**Version:** 1.0 • 2025-11-26

## Overview
The A2A (Agent-to-Agent) Server provides a WebSocket-based interface for real-time bidirectional communication between autonomous agents and the Notification Agent system.

**Port:** 8007 (configurable via `CLOUD_DOG__NOTIFY__A2A_SERVER__PORT`)

## Key Features

### 1. WebSocket Communication
- Real-time bidirectional messaging
- Event streaming
- Status updates
- Natural language command processing

### 2. Topics/Channels
- `notifications.events`: Notification events stream
- `deliveries.{id}`: Delivery-specific updates
- `channels.state`: Channel state changes

### 3. Natural Language Commands
- Send notifications via natural language
- Query system status
- Manage deliveries

## Main Components

### A2A Server (`src/servers/a2a/a2a_server.py`)
- WebSocket server implementation
- Topic-based message routing
- Natural language parser integration
- Event broadcasting

## Key Flows

### WebSocket Connection Flow
```
Client connects via WebSocket
  ↓
Server authenticates (API key)
  ↓
Client subscribes to topics
  ↓
Server streams events to client
  ↓
Client sends commands
  ↓
Server processes and responds
```

### Natural Language Command Flow
```
WebSocket message with command
  ↓
Parse natural language
  ↓
Resolve users/groups/destinations
  ↓
Execute notification request
  ↓
Stream results back via WebSocket
```

## Usage Examples

### Connect via WebSocket
```javascript
const ws = new WebSocket('<A2A_WS_URL>?api_key=<API_KEY>');

ws.on('open', () => {
  // Subscribe to topics
  ws.send(JSON.stringify({
    type: 'subscribe',
    topics: ['notifications.events', 'channels.state']
  }));
  
  // Send natural language command
  ws.send(JSON.stringify({
    type: 'command',
    command: 'Send a test message to user gary'
  }));
});

ws.on('message', (data) => {
  const message = JSON.parse(data);
  console.log('Received:', message);
});
```

### Python Example
```python
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"Received: {data}")

ws = websocket.WebSocketApp(
    "<A2A_WS_URL>?api_key=<API_KEY>",
    on_message=on_message
)

ws.run_forever()
```

## Message Format

### Client → Server
```json
{
  "type": "command",
  "command": "Send notification to group admins",
  "options": {}
}
```

### Server → Client
```json
{
  "type": "event",
  "topic": "notifications.events",
  "data": {
    "message_id": "123",
    "status": "queued",
    "delivery_count": 2
  }
}
```

## Configuration

See `docs/PARAMETERS.md` for all configuration options.

Key settings:
- `a2a_server.port`: Server port (default: 8007)
- `a2a_server.enabled`: Enable/disable A2A server
- `a2a_server.api_key`: API key for authentication

## Startup

```bash
python3 start_a2a_server.py --env <ENV_FILE>
# or
./server_control.sh start a2a
```

## Status Check

```bash
curl <A2A_BASE_URL>/health
```

## Use Cases

- Multi-agent systems requiring real-time notification coordination
- Autonomous agents that need to send notifications
- Event-driven architectures
- Real-time monitoring and alerting systems
