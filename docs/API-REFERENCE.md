---
template-id: T-API
template-version: 1.0
applies-to: docs/API-REFERENCE.md
registry: service
required: must-have
when-applicable: ""
template-last-updated: 2026-06-12
template-owner: platform-standards

project: notification-agent-mcp-server
doc-last-updated: 2026-06-18
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: 90d
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# API Reference

## REST API

Base URL is configured via `CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL`.

### Authentication
- Public: `/`, `/health`, `/ready`, `/live`, `/storage/{file_path:path}` and callback health endpoints.
- Protected endpoints require API key header:
  - `X-API-Key: <api_key>`

### Request/Response Envelope
- Most endpoints accept/return JSON.
- Common error envelope:
```json
{"detail": "error message"}
```

### Core Payload Schemas

#### Message create request (`POST /messages`)
```json
{
  "audience_type": "direct|group|broadcast|personalised",
  "destinations": [{"channel": "string", "address": "string", "preferences": {}}],
  "content": [{"type": "text|markdown|html|json", "body": "string"}],
  "template_ref": "optional-string",
  "variables": {},
  "options": {"ttl_hours": 24, "idempotency_key": "optional-string"}
}
```

#### Delivery state response (representative)
```json
{
  "id": 123,
  "message_id": 456,
  "state": "queued|formatting|sending|sent|delivered|read|soft_failed|hard_failed|ttl_expired",
  "attempt_no": 1,
  "last_error": null
}
```

### Endpoint Inventory (source-derived)

The table below is generated from FastAPI route decorators in `src/servers/api/`.

| Method | Path | Source |
|---|---|---|
| `GET` | `/` | `src/servers/api/api_server.py:538` |
| `GET` | `/api/v1/groups` | `src/servers/api/routes/groups.py:79` |
| `POST` | `/api/v1/groups` | `src/servers/api/routes/groups.py:90` |
| `DELETE` | `/api/v1/groups/{group_id}` | `src/servers/api/routes/groups.py:149` |
| `GET` | `/api/v1/groups/{group_id}` | `src/servers/api/routes/groups.py:110` |
| `PUT` | `/api/v1/groups/{group_id}` | `src/servers/api/routes/groups.py:124` |
| `POST` | `/api/v1/groups/{group_id}/keywords` | `src/servers/api/routes/groups.py:223` |
| `DELETE` | `/api/v1/groups/{group_id}/keywords/{keyword}` | `src/servers/api/routes/groups.py:244` |
| `POST` | `/api/v1/groups/{group_id}/members` | `src/servers/api/routes/groups.py:162` |
| `DELETE` | `/api/v1/groups/{group_id}/members/{user_id}` | `src/servers/api/routes/groups.py:188` |
| `PUT` | `/api/v1/groups/{group_id}/members/{user_id}/role` | `src/servers/api/routes/groups.py:205` |
| `GET` | `/api/v1/users` | `src/servers/api/routes/users.py:88` |
| `POST` | `/api/v1/users` | `src/servers/api/routes/users.py:117` |
| `GET` | `/api/v1/users/search/{query}` | `src/servers/api/routes/users.py:188` |
| `DELETE` | `/api/v1/users/{user_id}` | `src/servers/api/routes/users.py:172` |
| `GET` | `/api/v1/users/{user_id}` | `src/servers/api/routes/users.py:157` |
| `POST` | `/api/v1/users/{user_id}/destinations` | `src/servers/api/routes/users.py:225` |
| `DELETE` | `/api/v1/users/{user_id}/destinations/{destination_id}` | `src/servers/api/routes/users.py:250` |
| `POST` | `/api/v1/users/{user_id}/destinations/{destination_id}/primary` | `src/servers/api/routes/users.py:266` |
| `POST` | `/api/v1/users/{user_id}/keywords` | `src/servers/api/routes/users.py:282` |
| `DELETE` | `/api/v1/users/{user_id}/keywords/{keyword}` | `src/servers/api/routes/users.py:304` |
| `PUT` | `/api/v1/users/{user_id}/preferences` | `src/servers/api/routes/users.py:200` |
| `POST` | `/callbacks/chat` | `src/servers/api/routes/callbacks.py:231` |
| `POST` | `/callbacks/email` | `src/servers/api/routes/callbacks.py:64` |
| `GET` | `/callbacks/health` | `src/servers/api/routes/callbacks.py:284` |
| `POST` | `/callbacks/sms` | `src/servers/api/routes/callbacks.py:118` |
| `POST` | `/callbacks/whatsapp` | `src/servers/api/routes/callbacks.py:178` |
| `GET` | `/channels` | `src/servers/api/api_server.py:2988` |
| `POST` | `/channels` | `src/servers/api/api_server.py:3030` |
| `DELETE` | `/channels/{channel_id}` | `src/servers/api/api_server.py:3149` |
| `GET` | `/channels/{channel_id}` | `src/servers/api/api_server.py:3005` |
| `PATCH` | `/channels/{channel_id}` | `src/servers/api/api_server.py:3125` |
| `POST` | `/channels/{channel_id}/disable` | `src/servers/api/api_server.py:3118` |
| `POST` | `/channels/{channel_id}/enable` | `src/servers/api/api_server.py:3111` |
| `POST` | `/channels/{channel_id}/test` | `src/servers/api/api_server.py:3061` |
| `GET` | `/config` | `src/servers/api/api_server.py:825` |
| `POST` | `/config/query` | `src/servers/api/api_server.py:628` |
| `POST` | `/config/update` | `src/servers/api/api_server.py:768` |
| `GET` | `/deliveries` | `src/servers/api/api_server.py:2266` |
| `GET` | `/deliveries/{delivery_id}` | `src/servers/api/api_server.py:2466` |
| `POST` | `/deliveries/{delivery_id}/abort` | `src/servers/api/api_server.py:2501` |
| `POST` | `/deliveries/{delivery_id}/resend` | `src/servers/api/api_server.py:2404` |
| `GET` | `/groups` | `src/servers/api/api_server.py:3407` |
| `POST` | `/groups` | `src/servers/api/api_server.py:3441` |
| `DELETE` | `/groups/{group_id}` | `src/servers/api/api_server.py:3532` |
| `GET` | `/groups/{group_id}` | `src/servers/api/api_server.py:3421` |
| `PUT` | `/groups/{group_id}` | `src/servers/api/routes/groups.py:124` |
| `POST` | `/groups/{group_id}/keywords` | `src/servers/api/routes/groups.py:223` |
| `DELETE` | `/groups/{group_id}/keywords/{keyword}` | `src/servers/api/routes/groups.py:244` |
| `GET` | `/groups/{group_id}/members` | `src/servers/api/api_server.py:3470` |
| `POST` | `/groups/{group_id}/members` | `src/servers/api/api_server.py:3484` |
| `DELETE` | `/groups/{group_id}/members/{member_id}` | `src/servers/api/api_server.py:3518` |
| `DELETE` | `/groups/{group_id}/members/{user_id}` | `src/servers/api/routes/groups.py:188` |
| `PUT` | `/groups/{group_id}/members/{user_id}/role` | `src/servers/api/routes/groups.py:205` |
| `GET` | `/health` | `src/servers/api/api_server.py:550` |
| `GET` | `/live` | `src/servers/api/api_server.py:609` |
| `GET` | `/llm/status` | `src/servers/api/api_server.py:831` |
| `GET` | `/messages` | `src/servers/api/api_server.py:2249` |
| `POST` | `/messages` | `src/servers/api/api_server.py:860` |
| `POST` | `/messages/preview` | `src/servers/api/api_server.py:665` |
| `DELETE` | `/messages/{message_identifier}` | `src/servers/api/api_server.py:2327` |
| `GET` | `/messages/{message_identifier}` | `src/servers/api/api_server.py:1107` |
| `POST` | `/messages/{message_identifier}/cancel` | `src/servers/api/api_server.py:2287` |
| `GET` | `/messages/{message_identifier}/deliveries` | `src/servers/api/api_server.py:2179` |
| `DELETE` | `/messages/{message_id}` | `src/servers/api/api_server.py:3366` |
| `GET` | `/prompts` | `src/servers/api/api_server.py:3249` |
| `POST` | `/prompts` | `src/servers/api/api_server.py:3194` |
| `DELETE` | `/prompts/{prompt_id}` | `src/servers/api/api_server.py:3342` |
| `GET` | `/prompts/{prompt_id}` | `src/servers/api/api_server.py:3281` |
| `PATCH` | `/prompts/{prompt_id}` | `src/servers/api/api_server.py:3301` |
| `GET` | `/ready` | `src/servers/api/api_server.py:596` |
| `GET` | `/status` | `src/servers/api/api_server.py:797` |
| `DELETE` | `/storage/files/{backend_type}/{filename:path}` | `src/servers/api/api_server.py:2828` |
| `GET` | `/storage/files/{backend_type}/{filename:path}` | `src/servers/api/api_server.py:2763` |
| `PUT` | `/storage/files/{backend_type}/{filename:path}` | `src/servers/api/api_server.py:2613` |
| `GET` | `/storage/files/{backend_type}/{filename:path}/exists` | `src/servers/api/api_server.py:2704` |
| `GET` | `/storage/{file_path:path}` | `src/servers/api/api_server.py:2905` |
| `POST` | `/tests/llm/run` | `src/servers/api/api_server.py:3897` |
| `GET` | `/tests/llm/status` | `src/servers/api/api_server.py:4006` |
| `GET` | `/users` | `src/servers/api/api_server.py:3628` |
| `POST` | `/users` | `src/servers/api/api_server.py:3676` |
| `DELETE` | `/users/{user_id}` | `src/servers/api/api_server.py:3781` |
| `GET` | `/users/{user_id}` | `src/servers/api/api_server.py:3656` |
| `PATCH` | `/users/{user_id}` | `src/servers/api/api_server.py:3735` |
| `GET` | `/users/{user_id}/keywords` | `src/servers/api/api_server.py:3816` |
| `POST` | `/users/{user_id}/keywords` | `src/servers/api/api_server.py:3840` |
| `DELETE` | `/users/{user_id}/keywords/{keyword}` | `src/servers/api/api_server.py:3873` |

Total endpoints: 87

## MCP Tools

MCP server supports streamable HTTP, JSON-RPC, legacy SSE, and stdio modes.

### Tool Inventory

| Tool | Description | Source |
|---|---|---|
| `send_notification` | Send a notification to one or more destinations | `src/servers/mcp/mcp_server.py:79` |
| `get_message_status` | Get the status of a notification message | `src/servers/mcp/mcp_server.py:117` |
| `list_channels` | List all available notification channels | `src/servers/mcp/mcp_server.py:131` |
| `cancel_message` | Cancel a pending notification message | `src/servers/mcp/mcp_server.py:139` |
| `send_notification_natural` | Send a notification using natural language (e.g., 'Send notification to Fred that JOB XXXX has finished') | `src/servers/mcp/mcp_server.py:153` |
| `list_messages` | List recent messages with optional filtering | `src/servers/mcp/mcp_server.py:172` |
| `get_message` | Get detailed information about a specific message | `src/servers/mcp/mcp_server.py:195` |
| `list_deliveries` | List deliveries for a specific message | `src/servers/mcp/mcp_server.py:209` |
| `resend_delivery` | Resend a failed or cancelled delivery | `src/servers/mcp/mcp_server.py:233` |
| `abort_delivery` | Abort a pending delivery immediately | `src/servers/mcp/mcp_server.py:247` |
| `get_status` | Get system status and metrics | `src/servers/mcp/mcp_server.py:261` |

Total tools: 11

### MCP Request/Response Shape
- `call_tool(name, arguments)` receives:
  - `name`: tool name from the table above
  - `arguments`: JSON object per tool schema
- Returns `TextContent` JSON string payload from handler result.
- Errors return `{ "error": "..." }` content.

## A2A Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `GET` | `/` | A2A UI/banner root | None |
| `GET` | `/health` | A2A health status | None |
| `POST` | `/notify/natural` | Natural-language notification entrypoint | API-key style validation in payload/header path |

Representative `POST /notify/natural` request:
```json
{
  "command": "Send a notification to Alice that job 123 finished",
  "channels": ["email_default"]
}
```

Representative response:
```json
{
  "status": "accepted",
  "message_id": 123,
  "deliveries": []
}
```

## OpenAPI
- Runtime: `GET /openapi.json`
- Snapshot file: [docs/openapi.json](openapi.json)

## Notes
- This document is source-derived and should be refreshed when routes or tool schemas change.
- For Web UI page/proxy routes, see `src/servers/web/web_server.py` and `docs/WEB_UI.md`.



<!-- W28C-1710a recovery: full content from archive/2026-06-12/API_DOCUMENTATION.md (archived sha256=09731e2f3109, 258 lines) -->

## Recovered domain content — `archive/2026-06-12/API_DOCUMENTATION.md` (258 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/API_DOCUMENTATION.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# API Documentation

## Base URLs
- Local development: `http://localhost:8083`
- Deployed: `https://notification-agent.your-domain.com`

## Authentication
Use a session cookie for web administration or bearer-token authorisation for API, MCP, and A2A access.

## Verification Basis
- Source files reviewed: `src/servers/a2a/a2a_server.py`, `src/servers/api/api_server.py`, `src/servers/api/routes/__init__.py`, `src/servers/api/routes/callbacks.py`, `src/servers/api/routes/groups.py`, `src/servers/api/routes/users.py`, `src/servers/mcp/mcp_server.py`, `src/servers/web/web_server.py`, `start_a2a_server.py`, `start_api_server.py`, `start_mcp_server.py`, `start_web_server.py`
- Route inventory size: 184 unique (226 raw, with 42 `/webapi/proxy/*` duplicates collapsed)
- Note: Many endpoints are registered under both `/api/proxy/*` and `/webapi/proxy/*` prefixes pointing to the same handler. The 42 `/webapi/proxy/*` duplicates that have identical `/api/proxy/*` counterparts are counted once. Seven `/webapi/proxy/*`-only routes (status, health, structured-logs, a2a/notify/natural GET+POST, tests/llm/status, tests/llm/run) remain as distinct entries.

## Route Inventory
| Method | Path | Notes |
|--------|------|-------|
| GET | `/` | Handler `root` in `src/servers/a2a/a2a_server.py`. |
| POST | `/notify/natural` | Handler `notify_natural` in `src/servers/a2a/a2a_server.py`. |
| POST | `/internal/events/broadcast` | Handler `internal_broadcast_event` in `src/servers/a2a/a2a_server.py`. |
| GET | `/runtime-config.js` | Handler `runtime_config_js` in `src/servers/web/web_server.py`. |
| GET | `/` | Handler `root` in `src/servers/web/web_server.py`. |
| GET | `/login` | Handler `login_page` in `src/servers/web/web_server.py`. |
| POST | `/login` | Handler `login` in `src/servers/web/web_server.py`. |
| GET | `/logout` | Handler `logout` in `src/servers/web/web_server.py`. |
| POST | `/auth/login` | Handler `auth_login` in `src/servers/web/web_server.py`. |
| GET | `/auth/me` | Handler `auth_me` in `src/servers/web/web_server.py`. |
| POST | `/auth/logout` | Handler `auth_logout` in `src/servers/web/web_server.py`. |
| POST | `/auth/refresh` | Handler `auth_refresh` in `src/servers/web/web_server.py`. |
| GET | `/auth/keycloak/login` | Handler `keycloak_login` in `src/servers/web/web_server.py`. |
| GET | `/auth/keycloak/callback` | Handler `keycloak_callback` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/status` | Handler `proxy_status` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/health` | Handler `proxy_health` in `src/servers/web/web_server.py`. |
| POST | `/webapi/tests/login` | Handler `test_login` in `src/servers/web/web_server.py`. |
| POST | `/webapi/tests/logout` | Handler `test_logout` in `src/servers/web/web_server.py`. |
| GET | `/webapi/tests/session` | Handler `test_session` in `src/servers/web/web_server.py`. |
| GET | `/webapi/tests/endpoints` | Handler `test_endpoints` in `src/servers/web/web_server.py`. |
| GET | `/webapi/tests/api-connection` | Handler `test_api_connection` in `src/servers/web/web_server.py`. |
| POST | `/webapi/tests/mcp-test` | Handler `test_mcp_test` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/channels` | Handler `proxy_channels` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/channels` | Handler `proxy_channels` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/channels` | Handler `proxy_create_channel` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/channels` | Handler `proxy_create_channel` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/channels/{channel_id}` | Handler `proxy_get_channel` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/channels/{channel_id}` | Handler `proxy_get_channel` in `src/servers/web/web_server.py`. |
| PUT | `/api/proxy/channels/{channel_id}` | Handler `proxy_update_channel` in `src/servers/web/web_server.py`. |
| PUT | `/webapi/proxy/channels/{channel_id}` | Handler `proxy_update_channel` in `src/servers/web/web_server.py`. |
| PATCH | `/api/proxy/channels/{channel_id}` | Handler `proxy_update_channel` in `src/servers/web/web_server.py`. |
| PATCH | `/webapi/proxy/channels/{channel_id}` | Handler `proxy_update_channel` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/channels/{channel_id}` | Handler `proxy_delete_channel` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/channels/{channel_id}` | Handler `proxy_delete_channel` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/channels/{channel_id}/test` | Handler `proxy_test_channel` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/channels/{channel_id}/test` | Handler `proxy_test_channel` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/channels/{channel_id}/enable` | Handler `proxy_enable_channel` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/channels/{channel_id}/enable` | Handler `proxy_enable_channel` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/channels/{channel_id}/disable` | Handler `proxy_disable_channel` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/channels/{channel_id}/disable` | Handler `proxy_disable_channel` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/messages` | Handler `proxy_messages` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/messages` | Handler `proxy_messages` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/messages` | Handler `proxy_create_message` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/messages` | Handler `proxy_create_message` in `src/servers/web/web_server.py`. |
| GET | `/dashboard` | Handler `dashboard` in `src/servers/web/web_server.py`. |
| GET | `/status` | Handler `view_status` in `src/servers/web/web_server.py`. |
| GET | `/storage` | Handler `view_storage` in `src/servers/web/web_server.py`. |
| GET | `/web-api-docs` | Handler `api_docs` in `src/servers/web/web_server.py`. |
| GET | `/users` | Handler `view_users` in `src/servers/web/web_server.py`. |
| GET | `/db/users` | Handler `view_users` in `src/servers/web/web_server.py`. |
| GET | `/admin/api-keys` | Handler `view_api_keys` in `src/servers/web/web_server.py`. |
| GET | `/groups` | Handler `view_groups` in `src/servers/web/web_server.py`. |
| GET | `/db/groups` | Handler `view_groups` in `src/servers/web/web_server.py`. |
| GET | `/channels` | Handler `view_channels` in `src/servers/web/web_server.py`. |
| GET | `/db/channels` | Handler `view_channels` in `src/servers/web/web_server.py`. |
| GET | `/channels/add` | Handler `add_channel_page` in `src/servers/web/web_server.py`. |
| GET | `/channels/{channel_id}` | Handler `view_channel_definition` in `src/servers/web/web_server.py`. |
| GET | `/messages/{message_identifier}` | Handler `view_message` in `src/servers/web/web_server.py`. |
| GET | `/messages` | Handler `view_messages` in `src/servers/web/web_server.py`. |
| GET | `/db/messages` | Handler `view_messages` in `src/servers/web/web_server.py`. |
| GET | `/deliveries` | Handler `view_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/db/deliveries` | Handler `view_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/db/config` | Handler `view_config` in `src/servers/web/web_server.py`. |
| GET | `/web-mcp-test` | Handler `mcp_test_page` in `src/servers/web/web_server.py`. |
| GET | `/llm-test` | Handler `llm_test_page` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/tests/llm/status` | Handler `proxy_llm_test_status` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/tests/llm/run` | Handler `proxy_llm_test_run` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/a2a/notify/natural` | Handler `proxy_a2a_natural_get` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/a2a/notify/natural` | Handler `proxy_a2a_natural` in `src/servers/web/web_server.py`. |
| GET | `/logs` | Handler `view_logs` in `src/servers/web/web_server.py`. |
| GET | `/mcp-logs` | Handler `view_mcp_logs` in `src/servers/web/web_server.py`. |
| GET | `/settings` | Handler `view_settings` in `src/servers/web/web_server.py`. |
| GET | `/users/add` | Handler `add_user_page` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/users` | Handler `proxy_list_users` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/users` | Handler `proxy_list_users` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/users` | Handler `proxy_create_user` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/users` | Handler `proxy_create_user` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/admin/api-keys` | Handler `proxy_list_api_keys` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/admin/api-keys` | Handler `proxy_list_api_keys` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/admin/api-keys` | Handler `proxy_create_api_key` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/admin/api-keys` | Handler `proxy_create_api_key` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/admin/api-keys/{key_id}` | Handler `proxy_revoke_api_key` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/admin/api-keys/{key_id}` | Handler `proxy_revoke_api_key` in `src/servers/web/web_server.py`. |
| GET | `/users/{user_id}/edit` | Handler `edit_user_page` in `src/servers/web/web_server.py`. |
| PUT | `/api/proxy/users/{user_id}/preferences` | Handler `proxy_update_user_preferences` in `src/servers/web/web_server.py`. |
| PUT | `/webapi/proxy/users/{user_id}/preferences` | Handler `proxy_update_user_preferences` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/users/{user_id}` | Handler `proxy_get_user` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/users/{user_id}` | Handler `proxy_get_user` in `src/servers/web/web_server.py`. |
| PATCH | `/api/proxy/users/{user_id}` | Handler `proxy_patch_user` in `src/servers/web/web_server.py`. |
| PATCH | `/webapi/proxy/users/{user_id}` | Handler `proxy_patch_user` in `src/servers/web/web_server.py`. |
| PUT | `/api/proxy/users/{user_id}` | Handler `proxy_update_user` in `src/servers/web/web_server.py`. |
| PUT | `/webapi/proxy/users/{user_id}` | Handler `proxy_update_user` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/users/{user_id}` | Handler `proxy_delete_user` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/users/{user_id}` | Handler `proxy_delete_user` in `src/servers/web/web_server.py`. |
| GET | `/users/{user_id}/view` | Handler `view_user_page` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/messages/{message_id}/deliveries` | Handler `proxy_get_message_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/messages/{message_id}/deliveries` | Handler `proxy_get_message_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/deliveries` | Handler `proxy_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/deliveries` | Handler `proxy_deliveries` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/deliveries/{delivery_id}` | Handler `proxy_get_delivery` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/deliveries/{delivery_id}` | Handler `proxy_get_delivery` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/deliveries/{delivery_id}` | Handler `proxy_delete_delivery` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/deliveries/{delivery_id}` | Handler `proxy_delete_delivery` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/deliveries/{delivery_id}/resend` | Handler `proxy_resend_delivery` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/deliveries/{delivery_id}/resend` | Handler `proxy_resend_delivery` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/deliveries/{delivery_id}/abort` | Handler `proxy_abort_delivery` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/deliveries/{delivery_id}/abort` | Handler `proxy_abort_delivery` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/messages/{message_id}` | Handler `proxy_get_message` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/messages/{message_id}` | Handler `proxy_get_message` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/messages/{message_id}` | Handler `proxy_delete_message` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/messages/{message_id}` | Handler `proxy_delete_message` in `src/servers/web/web_server.py`. |
| POST | `/messages/{message_id}/cancel` | Handler `cancel_message_web` in `src/servers/web/web_server.py`. |
| GET | `/db/prompts` | Handler `view_prompts` in `src/servers/web/web_server.py`. |
| GET | `/services` | Handler `view_services` in `src/servers/web/web_server.py`. |
| GET | `/groups/add` | Handler `add_group_page` in `src/servers/web/web_server.py`. |
| GET | `/groups/{group_id}/edit` | Handler `edit_group_page` in `src/servers/web/web_server.py`. |
| GET | `/groups/{group_id}/assign-owner` | Handler `assign_owner_page` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/config/update` | Handler `proxy_config_update` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/prompts` | Handler `proxy_list_prompts` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/prompts` | Handler `proxy_list_prompts` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/prompts` | Handler `proxy_create_prompt` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/prompts` | Handler `proxy_create_prompt` in `src/servers/web/web_server.py`. |
| PATCH | `/api/proxy/prompts/{prompt_id}` | Handler `proxy_update_prompt` in `src/servers/web/web_server.py`. |
| PATCH | `/webapi/proxy/prompts/{prompt_id}` | Handler `proxy_update_prompt` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/prompts/{prompt_id}` | Handler `proxy_delete_prompt` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/prompts/{prompt_id}` | Handler `proxy_delete_prompt` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/groups` | Handler `proxy_list_groups` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/groups` | Handler `proxy_list_groups` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/groups/{group_id}` | Handler `proxy_get_group` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/groups/{group_id}` | Handler `proxy_get_group` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/groups` | Handler `proxy_create_group` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/groups` | Handler `proxy_create_group` in `src/servers/web/web_server.py`. |
| PUT | `/api/proxy/groups/{group_id}` | Handler `proxy_update_group` in `src/servers/web/web_server.py`. |
| PUT | `/webapi/proxy/groups/{group_id}` | Handler `proxy_update_group` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/groups/{group_id}` | Handler `proxy_delete_group` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/groups/{group_id}` | Handler `proxy_delete_group` in `src/servers/web/web_server.py`. |
| GET | `/api/proxy/groups/{group_id}/members` | Handler `proxy_get_group_members` in `src/servers/web/web_server.py`. |
| GET | `/webapi/proxy/groups/{group_id}/members` | Handler `proxy_get_group_members` in `src/servers/web/web_server.py`. |
| POST | `/api/proxy/groups/{group_id}/members` | Handler `proxy_add_group_member` in `src/servers/web/web_server.py`. |
| POST | `/webapi/proxy/groups/{group_id}/members` | Handler `proxy_add_group_member` in `src/servers/web/web_server.py`. |
| DELETE | `/api/proxy/groups/{group_id}/members/{user_id}` | Handler `proxy_remove_group_member` in `src/servers/web/web_server.py`. |
| DELETE | `/webapi/proxy/groups/{group_id}/members/{user_id}` | Handler `proxy_remove_group_member` in `src/servers/web/web_server.py`. |
| PUT | `/api/proxy/groups/{group_id}/members/{user_id}/role` | Handler `proxy_update_group_member_role` in `src/servers/web/web_server.py`. |
| PUT | `/webapi/proxy/groups/{group_id}/members/{user_id}/role` | Handler `proxy_update_group_member_role` in `src/servers/web/web_server.py`. |
| GET | `/` | Handler `root` in `src/servers/api/api_server.py`. |
| POST | `/config/query` | Handler `query_config` in `src/servers/api/api_server.py`. |
| POST | `/messages/preview` | Handler `preview_message_formatting` in `src/servers/api/api_server.py`. |
| POST | `/config/update` | Handler `update_config` in `src/servers/api/api_server.py`. |
| GET | `/status` | Handler `get_status` in `src/servers/api/api_server.py`. |
| GET | `/config` | Handler `get_config_dump` in `src/servers/api/api_server.py`. |
| GET | `/llm/status` | Handler `get_llm_status` in `src/servers/api/api_server.py`. |
| POST | `/messages` | Handler `create_message` in `src/servers/api/api_server.py`. |
| GET | `/messages/{message_identifier}` | Handler `get_message` in `src/servers/api/api_server.py`. |
| GET | `/messages/{message_identifier}/deliveries` | Handler `get_message_deliveries` in `src/servers/api/api_server.py`. |
| GET | `/messages` | Handler `list_messages` in `src/servers/api/api_server.py`. |
| GET | `/deliveries` | Handler `list_deliveries` in `src/servers/api/api_server.py`. |
| POST | `/messages/{message_identifier}/cancel` | Handler `cancel_message` in `src/servers/api/api_server.py`. |
| DELETE | `/messages/{message_identifier}` | Handler `delete_message` in `src/servers/api/api_server.py`. |
| POST | `/deliveries/{delivery_id}/resend` | Handler `resend_delivery` in `src/servers/api/api_server.py`. |
| GET | `/deliveries/{delivery_id}` | Handler `get_delivery` in `src/servers/api/api_server.py`. |
| POST | `/deliveries/{delivery_id}/abort` | Handler `abort_delivery` in `src/servers/api/api_server.py`. |
| PUT | `/storage/files/{backend_type}/{filename:path}` | Handler `update_storage_file` in `src/servers/api/api_server.py`. |
| GET | `/storage/files/{backend_type}/{filename:path}/exists` | Handler `check_file_exists` in `src/servers/api/api_server.py`. |
| GET | `/storage/files/{backend_type}/{filename:path}` | Handler `read_storage_file` in `src/servers/api/api_server.py`. |
| DELETE | `/storage/files/{backend_type}/{filename:path}` | Handler `delete_storage_file` in `src/servers/api/api_server.py`. |
| GET | `/storage/{file_path:path}` | Handler `serve_storage_file` in `src/servers/api/api_server.py`. |
| GET | `/channels` | Handler `list_channels` in `src/servers/api/api_server.py`. |
| GET | `/channels/{channel_id}` | Handler `get_channel` in `src/servers/api/api_server.py`. |
| POST | `/channels` | Handler `create_channel` in `src/servers/api/api_server.py`. |
| POST | `/channels/{channel_id}/test` | Handler `test_channel` in `src/servers/api/api_server.py`. |
| POST | `/channels/{channel_id}/enable` | Handler `enable_channel` in `src/servers/api/api_server.py`. |
| POST | `/channels/{channel_id}/disable` | Handler `disable_channel` in `src/servers/api/api_server.py`. |
| PATCH | `/channels/{channel_id}` | Handler `update_channel` in `src/servers/api/api_server.py`. |
| DELETE | `/channels/{channel_id}` | Handler `delete_channel` in `src/servers/api/api_server.py`. |
| POST | `/prompts` | Handler `create_prompt` in `src/servers/api/api_server.py`. |
| GET | `/prompts` | Handler `list_prompts` in `src/servers/api/api_server.py`. |
| GET | `/prompts/{prompt_id}` | Handler `get_prompt` in `src/servers/api/api_server.py`. |
| PATCH | `/prompts/{prompt_id}` | Handler `update_prompt` in `src/servers/api/api_server.py`. |
| DELETE | `/prompts/{prompt_id}` | Handler `delete_prompt` in `src/servers/api/api_server.py`. |
| DELETE | `/messages/{message_id}` | Handler `delete_message_by_id` in `src/servers/api/api_server.py`. |
| GET | `/groups` | Handler `list_groups` in `src/servers/api/api_server.py`. |
| GET | `/groups/{group_id}` | Handler `get_group` in `src/servers/api/api_server.py`. |
| POST | `/groups` | Handler `create_group` in `src/servers/api/api_server.py`. |
| GET | `/groups/{group_id}/members` | Handler `list_group_members` in `src/servers/api/api_server.py`. |
| POST | `/groups/{group_id}/members` | Handler `add_group_member` in `src/servers/api/api_server.py`. |
| DELETE | `/groups/{group_id}/members/{member_id}` | Handler `remove_group_member` in `src/servers/api/api_server.py`. |
| DELETE | `/groups/{group_id}` | Handler `delete_group` in `src/servers/api/api_server.py`. |
| GET | `/users` | Handler `list_users` in `src/servers/api/api_server.py`. |
| GET | `/users/{user_id}` | Handler `get_user` in `src/servers/api/api_server.py`. |
| POST | `/users` | Handler `create_user` in `src/servers/api/api_server.py`. |
| PATCH | `/users/{user_id}` | Handler `patch_user` in `src/servers/api/api_server.py`. |
| DELETE | `/users/{user_id}` | Handler `delete_user` in `src/servers/api/api_server.py`. |
| GET | `/users/{user_id}/keywords` | Handler `list_user_keywords` in `src/servers/api/api_server.py`. |
| POST | `/users/{user_id}/keywords` | Handler `add_user_keyword` in `src/servers/api/api_server.py`. |
| DELETE | `/users/{user_id}/keywords/{keyword}` | Handler `remove_user_keyword` in `src/servers/api/api_server.py`. |
| GET | `/admin/api-keys` | Handler `list_admin_api_keys` in `src/servers/api/api_server.py`. |
| POST | `/admin/api-keys` | Handler `create_admin_api_key` in `src/servers/api/api_server.py`. |
| DELETE | `/admin/api-keys/{key_id}` | Handler `revoke_admin_api_key` in `src/servers/api/api_server.py`. |
| POST | `/tests/llm/run` | Handler `run_llm_tests` in `src/servers/api/api_server.py`. |
| GET | `/tests/llm/status` | Handler `get_llm_test_status` in `src/servers/api/api_server.py`. |
| POST | `/callbacks/email` | Handler `email_callback` in `src/servers/api/routes/callbacks.py`. |
| POST | `/callbacks/sms` | Handler `sms_callback` in `src/servers/api/routes/callbacks.py`. |
| POST | `/callbacks/whatsapp` | Handler `whatsapp_callback` in `src/servers/api/routes/callbacks.py`. |
| POST | `/callbacks/chat` | Handler `chat_callback` in `src/servers/api/routes/callbacks.py`. |
| GET | `/callbacks/health` | Handler `callback_health` in `src/servers/api/routes/callbacks.py`. |
| GET | `` | Handler `list_users` in `src/servers/api/routes/users.py`. |
| POST | `` | Handler `create_user` in `src/servers/api/routes/users.py`. |
| GET | `/{user_id}` | Handler `get_user` in `src/servers/api/routes/users.py`. |
| DELETE | `/{user_id}` | Handler `delete_user` in `src/servers/api/routes/users.py`. |
| GET | `/search/{query}` | Handler `search_users` in `src/servers/api/routes/users.py`. |
| PUT | `/{user_id}/preferences` | Handler `update_user_preferences` in `src/servers/api/routes/users.py`. |
| POST | `/{user_id}/destinations` | Handler `add_destination` in `src/servers/api/routes/users.py`. |
| DELETE | `/{user_id}/destinations/{destination_id}` | Handler `remove_destination` in `src/servers/api/routes/users.py`. |
| POST | `/{user_id}/destinations/{destination_id}/primary` | Handler `set_primary_destination` in `src/servers/api/routes/users.py`. |
| POST | `/{user_id}/keywords` | Handler `add_keyword` in `src/servers/api/routes/users.py`. |
| DELETE | `/{user_id}/keywords/{keyword}` | Handler `remove_keyword` in `src/servers/api/routes/users.py`. |
| GET | `` | Handler `list_groups` in `src/servers/api/routes/groups.py`. |
| POST | `` | Handler `create_group` in `src/servers/api/routes/groups.py`. |
| GET | `/{group_id}` | Handler `get_group` in `src/servers/api/routes/groups.py`. |
| PUT | `/{group_id}` | Handler `update_group` in `src/servers/api/routes/groups.py`. |
| DELETE | `/{group_id}` | Handler `delete_group` in `src/servers/api/routes/groups.py`. |
| POST | `/{group_id}/members` | Handler `add_member` in `src/servers/api/routes/groups.py`. |
| DELETE | `/{group_id}/members/{user_id}` | Handler `remove_member` in `src/servers/api/routes/groups.py`. |
| PUT | `/{group_id}/members/{user_id}/role` | Handler `update_member_role` in `src/servers/api/routes/groups.py`. |
| POST | `/{group_id}/keywords` | Handler `add_keyword` in `src/servers/api/routes/groups.py`. |
| DELETE | `/{group_id}/keywords/{keyword}` | Handler `remove_keyword` in `src/servers/api/routes/groups.py`. |

## Example Request
```bash
curl -H "<bearer-token-header>: Bearer your-api-key" http://localhost:8083/health
```

## Example Response
```json
{
  "ok": true,
  "result": {
    "status": "healthy"
  }
}
```


<!-- W28C-1710a recovery: full content from archive/2026-06-12/API_SERVER.md (archived sha256=c771d35906da, 134 lines) -->

## Recovered domain content — `archive/2026-06-12/API_SERVER.md` (134 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/API_SERVER.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# API Server Documentation
**Version:** 1.0 • 2025-11-26

## Overview
The API Server provides the primary REST API interface for the Notification Agent MCP Server. It handles message submission, delivery management, channel configuration, user/group management, and system monitoring.

**Port:** 8004 (configurable via `CLOUD_DOG__NOTIFY__API_SERVER__PORT`)

## Key Features

### 1. Message Submission & Management
- Create and enqueue notifications
- Retrieve message details and delivery status
- Cancel pending deliveries
- Resend failed deliveries

### 2. Channel Management
- List and configure channels
- Channel health monitoring
- Rate limit and quota management

### 3. User & Group Management
- User CRUD operations
- Group membership management
- User preferences and destinations
- Keyword-based personalization

### 4. Delivery Tracking
- Real-time delivery status
- Delivery history and retry management
- Callback webhook handling

### 5. System Monitoring
- Health checks
- Queue depth and status
- LLM availability status
- Config query and admin updates (`/config/query`, `/config/update`)

## Main Components

### API Endpoints (`src/servers/api/api_server.py`)
- FastAPI-based REST API
- OpenAPI/Swagger documentation
- API key authentication
- CORS support

### Routes
- **Messages**: `src/servers/api/routes/` (handled inline in api_server.py)
- **Users**: `src/servers/api/routes/users.py`
- **Groups**: `src/servers/api/routes/groups.py`
- **Callbacks**: `src/servers/api/routes/callbacks.py`

## Key Flows

### Message Submission Flow
```
POST /messages
  ↓
Validate request & authenticate
  ↓
Resolve destinations (users/groups/channels)
  ↓
Enqueue message via JobManager
  ↓
Return message_id and status
  ↓
Background: DeliveryWorker processes queue
```

### Delivery Status Flow
```
GET /messages/{id}/deliveries
  ↓
Query delivery repository
  ↓
Return paginated delivery list with states
```

## API Examples

### Create Message
```bash
curl -X POST <API_BASE_URL>/messages \
  -H "X-API-Key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "destinations": [{"channel": "<DEFAULT_CHANNEL_NAME>", "address": "<USER_EMAIL>"}],
    "content": [{"type": "text", "body": "Hello {{name}}"}],
    "variables": {"name": "Alice", "subject": "Test Message"}
  }'
```

### Get Message Status
```bash
curl -H "X-API-Key: <API_KEY>" \
  <API_BASE_URL>/messages/{message_id}
```

### Get Deliveries
```bash
curl -H "X-API-Key: <API_KEY>" \
  <API_BASE_URL>/messages/{message_id}/deliveries
```

## Configuration

See `docs/PARAMETERS.md` for all configuration options.

Key settings:
- `api_server.port`: Server port (default: 8004)
- `api_server.api_key`: API key for authentication
- `api_server.cors_origins`: Allowed CORS origins

## Startup

```bash
python3 start_api_server.py --env <ENV_FILE>
# or
./server_control.sh start api
```

## Health Check

```bash
curl <API_BASE_URL>/health
```

## OpenAPI Documentation

Interactive API documentation available at:
- Swagger UI: `<API_BASE_URL>/docs`
- ReDoc: `<API_BASE_URL>/redoc`
- OpenAPI JSON: `<API_BASE_URL>/openapi.json`
