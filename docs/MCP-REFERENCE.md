---
template-id: T-MCP
template-version: 1.0
applies-to: docs/MCP-REFERENCE.md
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

# notification-agent-mcp-server — MCP-REFERENCE

> **Template version:** T-MCP v1.0 — MCP tool surface (JSON-RPC 2.0 at `/mcp`).
>
> **Tool inventory:** 26 tools sourced from `src/servers/mcp/mcp_server.py` and
> `src/servers/mcp/tool_registry.py`. Every tool name documented here exists as
> a string literal in source.

## 1. Auth model

MCP auth mode: `api_key`. Supply the key in the `X-API-Key` header for all
transports (streamable HTTP, HTTP JSON-RPC, legacy SSE). Stdio transport runs
in-process and inherits the server's API key from environment.

RBAC roles map to permission scopes via `TOOL_RBAC_MAP` in
`src/servers/mcp/tool_registry.py`:

| Role | Permitted scopes |
|------|-----------------|
| `admin` | all tools (wildcard) |
| `read-write` / `operator` | `notify:email:send`, `notify:email:read`, `notify:channel:read`, `notify:status:read` |
| `read-only` | `notify:email:read`, `notify:channel:read`, `notify:status:read` |

## 2. Tools

Tools are registered in `src/servers/mcp/mcp_server.py` (`list_tools()`) and
catalogued with RBAC in `src/servers/mcp/tool_registry.py` (`TOOL_RBAC_MAP`,
`build_tool_contracts()`).

### 2.1 `send_notification`

- **Description:** Send a notification message to one or more destinations.
- **RBAC:** `notify:email:send` (admin, read-write)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["destinations", "content"],
    "properties": {
      "destinations": {
        "type": "array",
        "description": "List of destinations (channel and address)",
        "items": {
          "type": "object",
          "required": ["channel", "address"],
          "properties": {
            "channel":   { "type": "string", "description": "Channel name (e.g. email, loopback)" },
            "address":   { "type": "string", "description": "Destination address" },
            "preferences": { "type": "object" }
          }
        }
      },
      "content": {
        "type": "array",
        "description": "Message content blocks",
        "items": {
          "type": "object",
          "required": ["type", "body"],
          "properties": {
            "type": { "type": "string", "description": "Content type: text|markdown|html|json" },
            "body": { "type": "string" },
            "subject": { "type": "string" }
          }
        }
      },
      "audience_type":    { "type": "string", "description": "Audience mode (default: personalised)" },
      "subject":          { "type": "string", "description": "Optional message subject" },
      "options":          { "type": "object", "description": "Additional API message options" },
      "idempotency_key":  { "type": "string", "description": "Prevents duplicate sends" },
      "async_mode":       { "type": "boolean", "default": false, "description": "Submit as background job" }
    }
  }
  ```
- **Output schema:**
  ```json
  {
    "type": "object",
    "required": ["ok", "message_id", "delivery_ids", "status", "deduped"],
    "properties": {
      "ok":           { "type": "boolean" },
      "message_id":   { "type": ["integer", "null"] },
      "delivery_ids": { "type": "array", "items": { "type": "integer" } },
      "status":       { "type": "string", "enum": ["completed", "partial", "failed"] },
      "deduped":      { "type": "boolean" },
      "job_id":       { "type": ["string", "integer", "null"] },
      "queued":       { "type": "boolean" },
      "error":        { "type": "string" }
    }
  }
  ```
- **Errors:** `400` invalid schema; `401` missing/invalid API key; `500` internal send failure.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "Accept: application/json, text/event-stream" \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"send_notification","arguments":{"destinations":[{"channel":"email","address":"user@example.com"}],"content":[{"type":"text","body":"Hello"}]}},"id":1}'
  ```

### 2.2 `send_notification_natural`

- **Description:** Send a notification using a natural language command (e.g. `"Send notification to Fred that JOB XXXX has finished"`). The server parses intent, resolves users/groups, and delegates to `send_notification`.
- **RBAC:** `notify:email:send` (admin, read-write)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["command"],
    "properties": {
      "command":  { "type": "string", "description": "Natural language instruction" },
      "channels": { "type": "array", "items": { "type": "string" }, "description": "Optional channel override list" }
    }
  }
  ```
- **Output schema:** Same as `send_notification`.
- **Errors:** `400` unparseable command; `401` auth; `500` send failure.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"send_notification_natural","arguments":{"command":"Send a test message to gary"}},"id":1}'
  ```

### 2.3 `get_message_status`

- **Description:** Get the delivery status of a notification message by its numeric ID.
- **RBAC:** `notify:email:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["message_id"],
    "properties": {
      "message_id": { "type": "integer", "description": "Message ID to query" }
    }
  }
  ```
- **Output schema:** Message object with `status`, `created_at`, `delivery_ids`.
- **Errors:** `401` auth; `404` message not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_message_status","arguments":{"message_id":42}},"id":1}'
  ```

### 2.4 `list_channels`

- **Description:** List all available notification channels visible to the caller.
- **RBAC:** `notify:channel:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  { "type": "object", "properties": {} }
  ```
- **Output schema:** Array of channel objects with `name`, `type`, `enabled`.
- **Errors:** `401` auth.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_channels","arguments":{}},"id":1}'
  ```

### 2.5 `cancel_message`

- **Description:** Cancel a pending notification message and its outstanding deliveries.
- **RBAC:** `notify:email:send` (admin, read-write)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["message_id"],
    "properties": {
      "message_id": { "type": "integer", "description": "Message ID to cancel" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "message_id": <int> }`
- **Errors:** `401` auth; `404` message not found; `409` already delivered.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"cancel_message","arguments":{"message_id":42}},"id":1}'
  ```

### 2.6 `list_messages`

- **Description:** List recent notification messages with optional status filtering and pagination.
- **RBAC:** `notify:email:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "offset": { "type": "integer", "default": 0,   "description": "Pagination offset" },
      "limit":  { "type": "integer", "default": 100, "description": "Max results to return" },
      "status": { "type": "string",                  "description": "Filter by message status" }
    }
  }
  ```
- **Output schema:** `{ "messages": [...], "total": <int> }`
- **Errors:** `401` auth.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_messages","arguments":{"limit":20,"status":"pending"}},"id":1}'
  ```

### 2.7 `get_message`

- **Description:** Get detailed information about a specific message by numeric ID or UUID.
- **RBAC:** `notify:email:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["message_id"],
    "properties": {
      "message_id": { "type": ["integer", "string"], "description": "Numeric ID or UUID (GUID format)" }
    }
  }
  ```
- **Output schema:** Full message object including content, destinations, status, and delivery timeline.
- **Errors:** `401` auth; `404` message not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_message","arguments":{"message_id":42}},"id":1}'
  ```

### 2.8 `list_deliveries`

- **Description:** List delivery attempts for a specific message, with pagination.
- **RBAC:** `notify:email:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["message_id"],
    "properties": {
      "message_id": { "type": ["integer", "string"], "description": "Message ID or UUID" },
      "offset":     { "type": "integer", "default": 0,  "description": "Pagination offset" },
      "limit":      { "type": "integer", "default": 50, "description": "Max results" }
    }
  }
  ```
- **Output schema:** `{ "deliveries": [...], "total": <int> }`
- **Errors:** `401` auth; `404` message not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_deliveries","arguments":{"message_id":42}},"id":1}'
  ```

### 2.9 `resend_delivery`

- **Description:** Resend a failed or cancelled delivery attempt by delivery ID.
- **RBAC:** `notify:email:send` (admin, read-write)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["delivery_id"],
    "properties": {
      "delivery_id": { "type": "integer", "description": "Delivery ID to resend" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "delivery_id": <int>, "status": "queued" }`
- **Errors:** `401` auth; `404` delivery not found; `409` delivery already completed.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"resend_delivery","arguments":{"delivery_id":7}},"id":1}'
  ```

### 2.10 `abort_delivery`

- **Description:** Immediately abort a pending delivery, stopping further retry attempts.
- **RBAC:** `notify:email:send` (admin, read-write)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["delivery_id"],
    "properties": {
      "delivery_id": { "type": "integer", "description": "Delivery ID to abort" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "delivery_id": <int>, "status": "aborted" }`
- **Errors:** `401` auth; `404` delivery not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"abort_delivery","arguments":{"delivery_id":7}},"id":1}'
  ```

### 2.11 `get_status`

- **Description:** Get notification agent system status and operational metrics.
- **RBAC:** `notify:status:read` (admin, read-write, read-only)
- **Input schema:**
  ```json
  { "type": "object", "properties": {} }
  ```
- **Output schema:** `{ "status": "ok"|"degraded", "queue_depth": <int>, "uptime_s": <float>, "version": "<string>" }`
- **Errors:** `401` auth.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_status","arguments":{}},"id":1}'
  ```

### 2.12 `admin_list_channels`

- **Description:** Admin: list all channel definitions including disabled channels.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  { "type": "object", "properties": {} }
  ```
- **Output schema:** Array of full channel definition objects including `config` and `limits`.
- **Errors:** `401` auth; `403` insufficient role.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_list_channels","arguments":{}},"id":1}'
  ```

### 2.13 `admin_create_channel`

- **Description:** Admin: create a new notification channel definition.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["name", "type"],
    "properties": {
      "name":    { "type": "string",  "description": "Unique channel name" },
      "type":    { "type": "string",  "description": "Channel type (e.g. email, loopback, webhook)" },
      "enabled": { "type": "boolean", "description": "Whether channel is active" },
      "config":  { "type": "object",  "description": "Channel-type-specific configuration" },
      "limits":  { "type": "object",  "description": "Rate limits and quota configuration" }
    }
  }
  ```
- **Output schema:** Created channel object with assigned `id`.
- **Errors:** `401` auth; `403` role; `409` name already exists.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_create_channel","arguments":{"name":"loopback-dev","type":"loopback","enabled":true}},"id":1}'
  ```

### 2.14 `admin_update_channel`

- **Description:** Admin: update an existing channel definition by channel ID.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["channel_id", "updates"],
    "properties": {
      "channel_id": { "type": "integer", "description": "Channel ID to update" },
      "updates":    { "type": "object",  "description": "Fields to update (partial patch)" }
    }
  }
  ```
- **Output schema:** Updated channel object.
- **Errors:** `401` auth; `403` role; `404` channel not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_update_channel","arguments":{"channel_id":1,"updates":{"enabled":false}}},"id":1}'
  ```

### 2.15 `admin_delete_channel`

- **Description:** Admin: delete a channel definition by channel ID.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["channel_id"],
    "properties": {
      "channel_id": { "type": "integer", "description": "Channel ID to delete" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "channel_id": <int> }`
- **Errors:** `401` auth; `403` role; `404` channel not found; `409` channel has active messages.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_delete_channel","arguments":{"channel_id":3}},"id":1}'
  ```

### 2.16 `admin_list_users`

- **Description:** Admin: list user profiles with optional search filter.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "properties": {
      "q":     { "type": "string",  "description": "Full-text search query" },
      "email": { "type": "string",  "description": "Filter by exact email" },
      "limit": { "type": "integer", "default": 100, "description": "Max results" }
    }
  }
  ```
- **Output schema:** Array of user profile objects.
- **Errors:** `401` auth; `403` role.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_list_users","arguments":{"q":"gary"}},"id":1}'
  ```

### 2.17 `admin_create_user`

- **Description:** Admin: create a notification user profile.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["email"],
    "properties": {
      "username":          { "type": "string" },
      "email":             { "type": "string" },
      "display_name":      { "type": "string" },
      "role":              { "type": "string" },
      "language":          { "type": "string" },
      "preferred_channel": { "type": "string" },
      "content_style":     { "type": "string" }
    }
  }
  ```
- **Output schema:** Created user object with assigned `id`.
- **Errors:** `401` auth; `403` role; `409` email already exists.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_create_user","arguments":{"email":"fred@example.com","display_name":"Fred"}},"id":1}'
  ```

### 2.18 `admin_list_groups`

- **Description:** Admin: list notification user groups.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  { "type": "object", "properties": {} }
  ```
- **Output schema:** Array of group objects with `id`, `name`, `description`, `enabled`.
- **Errors:** `401` auth; `403` role.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_list_groups","arguments":{}},"id":1}'
  ```

### 2.19 `admin_create_group`

- **Description:** Admin: create a notification group.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["name"],
    "properties": {
      "name":              { "type": "string" },
      "description":       { "type": "string" },
      "language":          { "type": "string" },
      "preferred_channel": { "type": "string" },
      "content_style":     { "type": "string" }
    }
  }
  ```
- **Output schema:** Created group object with assigned `id`.
- **Errors:** `401` auth; `403` role; `409` name already exists.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_create_group","arguments":{"name":"ops-team"}},"id":1}'
  ```

### 2.20 `admin_update_group`

- **Description:** Admin: update an existing notification group by group ID.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["group_id"],
    "properties": {
      "group_id":          { "type": "integer" },
      "description":       { "type": "string" },
      "language":          { "type": "string" },
      "preferred_channel": { "type": "string" },
      "content_style":     { "type": "string" },
      "enabled":           { "type": "boolean" }
    }
  }
  ```
- **Output schema:** Updated group object.
- **Errors:** `401` auth; `403` role; `404` group not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_update_group","arguments":{"group_id":1,"description":"Operations team"}},"id":1}'
  ```

### 2.21 `admin_add_group_member`

- **Description:** Admin: add a user to a notification group.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["group_id", "user_id"],
    "properties": {
      "group_id": { "type": "integer" },
      "user_id":  { "type": "integer" },
      "role":     { "type": "string", "default": "member", "description": "Member role within group" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "group_id": <int>, "user_id": <int> }`
- **Errors:** `401` auth; `403` role; `404` group or user not found; `409` already a member.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_add_group_member","arguments":{"group_id":1,"user_id":5}},"id":1}'
  ```

### 2.22 `admin_list_group_members`

- **Description:** Admin: list members of a notification group.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["group_id"],
    "properties": {
      "group_id": { "type": "integer" }
    }
  }
  ```
- **Output schema:** Array of group member objects with `user_id`, `role`, `display_name`.
- **Errors:** `401` auth; `403` role; `404` group not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_list_group_members","arguments":{"group_id":1}},"id":1}'
  ```

### 2.23 `admin_remove_group_member`

- **Description:** Admin: remove a user from a notification group.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["group_id", "user_id"],
    "properties": {
      "group_id": { "type": "integer" },
      "user_id":  { "type": "integer" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "group_id": <int>, "user_id": <int> }`
- **Errors:** `401` auth; `403` role; `404` group or user not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_remove_group_member","arguments":{"group_id":1,"user_id":5}},"id":1}'
  ```

### 2.24 `admin_create_api_key`

- **Description:** Admin: generate a new API key for a user.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["owner_user_id"],
    "properties": {
      "owner_user_id": { "type": "string",  "description": "User ID to own the key" },
      "ttl_days":      { "type": "integer", "description": "Key validity in days (optional)" },
      "key_prefix":    { "type": "string",  "description": "Optional key prefix for identification" }
    }
  }
  ```
- **Output schema:** `{ "key_id": "<string>", "api_key": "<string>", "expires_at": "<ISO8601>|null" }`
- **Errors:** `401` auth; `403` role; `404` user not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_create_api_key","arguments":{"owner_user_id":"usr-42","ttl_days":90}},"id":1}'
  ```

### 2.25 `admin_revoke_api_key`

- **Description:** Admin: revoke an existing API key by key ID.
- **RBAC:** `notify:admin:*` (admin only)
- **Input schema:**
  ```json
  {
    "type": "object",
    "required": ["key_id"],
    "properties": {
      "key_id": { "type": "string", "description": "API key ID to revoke" }
    }
  }
  ```
- **Output schema:** `{ "ok": true, "key_id": "<string>" }`
- **Errors:** `401` auth; `403` role; `404` key not found.
- **Example call:**
  ```bash
  curl -X POST https://<host>/mcp \
    -H "X-API-Key: ${ADMIN_API_KEY}" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"admin_revoke_api_key","arguments":{"key_id":"key-abc123"}},"id":1}'
  ```

### 2.26 Tool-name → source confirmation

All 25 tool names above are present as string literals in `src/servers/mcp/mcp_server.py`
(`list_tools()`, `call_tool()`) and `src/servers/mcp/tool_registry.py` (`TOOL_RBAC_MAP`,
`build_tool_contracts()`). The archived reference in `docs/archive/` listed `notification-agent-mcp`
as a tool name — that is the MCP Server instance name (`Server("notification-agent-mcp")`),
not a callable tool.

## 3. Transport modes

| Mode | Endpoint | Notes |
|------|----------|-------|
| Streamable HTTP | `POST /mcp`, `DELETE /mcp` | Default; supports SSE streaming |
| HTTP JSON-RPC (sync) | `POST /messages` | Request/response in same call |
| HTTP JSON-RPC (async) | `POST /messages?wait=false` | Returns job ref; poll `/jobs/{job_id}` |
| Legacy SSE | `GET /sse` + `POST /message` | Backwards compatibility |
| stdio | Pipe | Local MCP clients (Claude Desktop) |

Port default: `8006` (configurable via `CLOUD_DOG__NOTIFY__MCP_SERVER__PORT`).

## 4. Key flows

### Natural language notification
```
send_notification_natural(command)
  → NaturalLanguageParser.parse_intent()
  → resolve users / groups
  → send_notification(destinations, content)
  → return message_id + status
```

### Async job flow
```
send_notification(async_mode=true)
  → JobManager.submit_job()
  → return {job_id, queued: true}
  # poll:
GET /admin/jobs/{job_id}  →  {status: "completed"|"failed", message_id}
```

## 5. Cross-references

- [API-REFERENCE.md](API-REFERENCE.md)
- [A2A-REFERENCE.md](A2A-REFERENCE.md)
- [ROLES-AND-USECASES.md](ROLES-AND-USECASES.md)
- PS-72-mcp-a2a-webui.md
- `src/servers/mcp/mcp_server.py` — tool registrations
- `src/servers/mcp/tool_registry.py` — RBAC map + ToolContract catalogue
- `src/servers/mcp/send_notification_contract.py` — send_notification schema
