---
template-id: T-WUI
template-version: 1.0
applies-to: docs/WEBUI-REFERENCE.md
registry: service
required: conditional
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

# notification-agent-mcp-server — WEBUI-REFERENCE

> **Template version:** T-WUI v1.0 — conditional: service has a WebUI panel.

## 1. Panel structure
Routes, panels, navigation, role gating.

| Route | Panel | Roles | Backend route |
|---|---|---|---|

## 2. Login
Flow (cookie vs api_key vs bootstrap), session storage, logout.

## 3. RBAC visibility matrix
**You MUST include:** what each role sees / can do per panel.

| Panel | admin | read-write | read-only | other |
|---|---|---|---|---|

## 4. Static routes
List of static UI routes registered in `_SPA_ENTRY_ROUTES` (see AGENT-LESSONS for the anon-gate trap).

## 5. Cross-references
- [API-REFERENCE.md](API-REFERENCE.md)
- [ROLES-AND-USECASES.md](ROLES-AND-USECASES.md)
- PS-77-webui-comprehensive.md
- PS-30-ui.md

## 6. Project-specific notes



<!-- W28C-1710a recovery: full content from archive/2026-06-12/WEB_UI.md (archived sha256=bbd25ca3d8b5, 162 lines) -->

## Recovered domain content — `archive/2026-06-12/WEB_UI.md` (162 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/WEB_UI.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# Web UI Documentation
**Version:** 1.0 • 2025-11-26

## Overview
The Web UI Server provides a browser-based administrative interface for managing the Notification Agent system. It acts as a proxy to the API server and provides user-friendly dashboards and management tools.

**Port:** 8005 (configurable via `CLOUD_DOG__NOTIFY__WEB_SERVER__PORT`)

## Key Features

### 1. Dashboard Views
- Message queue and status
- Delivery tracking
- Channel health monitoring
- System statistics

### 2. Management Interfaces
- User management (CRUD operations)
- Group management
- Channel configuration
- Prompt management (language/group-specific)
- System configuration (masked) and admin updates

### 3. Testing Tools
- Send test messages
- View message details
- Inspect delivery status
- Test channel connectivity

### 4. Authentication
- Session-based authentication
- User login/logout
- Role-based access control

## Main Components

### Web Server (`src/servers/web/web_server.py`)
- FastAPI-based web server
- Jinja2 template rendering
- Session management
- API proxy functionality

### Templates
- Dashboard views
- Management forms
- Status displays
- Message viewers

## Key Flows

### User Login Flow
```
GET /login
  ↓
Display login form
  ↓
POST /login (credentials)
  ↓
Validate credentials
  ↓
Create session
  ↓
Redirect to dashboard
```

### Message View Flow
```
GET /messages/{id}
  ↓
Proxy request to API server
  ↓
Fetch message and delivery data
  ↓
Render HTML view
  ↓
Display formatted message, original content, settings, links
```

## Pages/Endpoints

### Public
- `/`: Landing page
- `/login`: Login page
- `/health`: Health check

### Authenticated
- `/dashboard`: Main dashboard
- `/db/messages`: Message list
- `/db/messages/{id}`: Message details
- `/db/deliveries`: Delivery list
- `/db/channels`: Channel management
- `/db/users`: User management
- `/db/groups`: Group management
- `/db/prompts`: Prompt management
- `/db/config`: Configuration (masked)
- `/settings`: System settings
- `/logs`: Log viewer
- `/services`: Service status
- `/mcp-test`: MCP/A2A test console

## Usage

### Access Web UI
```
<WEB_BASE_URL>
```

### Default Credentials
- Username: `<WEB_USERNAME>`
- Password: `<WEB_PASSWORD>`

### Send Test Message
1. Navigate to Dashboard
2. Click "Send Test Message"
3. Fill in destination, content, variables
4. Submit and view delivery status

## Configuration

See `docs/PARAMETERS.md` for all configuration options.

Key settings:
- `web_server.port`: Server port
- `web_server.enabled`: Enable/disable web server
- `web_server.api_base_url`: API server URL

## Startup

```bash
python3 start_web_server.py --env <ENV_FILE>
# or
./server_control.sh start web
```

## Status Check

```bash
curl <WEB_BASE_URL>/health
```

## Features

### Message View
- Formatted message content (HTML/Markdown/Text)
- Original message content
- Original settings (variables)
- Destination details
- Delivery status and links
- Links to view in different formats (JSON, HTML, Markdown, Text)

### User Management
- Create/edit/delete users
- Set user preferences (language, format, channel)
- Manage user destinations
- Add/remove keywords

### Group Management
- Create/edit/delete groups
- Manage group members
- Set group preferences
- Add/remove keywords
