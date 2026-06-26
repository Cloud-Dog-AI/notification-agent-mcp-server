---
template-id: T-ARC
template-version: 1.0
applies-to: docs/ARCHITECTURE.md
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
doc-age-policy: indefinite
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# Notification Agent MCP Server — Architecture

## W28A-421 Review Status
- Reviewed for external/shareable publication during W28A-421.
- Source basis: `defaults.yaml`, 12 server source files, 226 discovered routes/endpoints, and 12 MCP tools.
- Internal-only absolute paths, environment-specific hosts, and private registries have been removed from this shareable document set.

## 1. Overview
`notification-agent-mcp-server` is a multi-channel notification orchestration service with REST API, Web UI, MCP, and A2A interfaces. It manages message creation, channel delivery, callbacks, retries, user/group targeting, and compliance/audit workflows.

The service is stateful and queue-oriented: messages and deliveries are persisted, processed through channel adapters, and tracked through lifecycle states (`queued`, `sent`, `delivered`, `read`, `failed`, `soft_failed`).

Within Cloud-Dog AI, it serves as the platform notification backend for other agent services and interactive clients.

## 2. System Context Diagram
```mermaid
graph TB
    subgraph External
        USER[Admin/User]
        APP[Client/App]
        LLM[LLM Formatter Provider]
        SMTP[SMTP/SMS/Chat Providers]
        CALLBACK[Provider Callback Webhooks]
        DB[(SQLite/MySQL/PostgreSQL)]
        VAULT[HashiCorp Vault]
    end

    subgraph "Cloud-Dog AI Platform"
        THIS[<b>notification-agent-mcp-server</b>]
        CHAT[chat-client]
        EXP[expert-agent-mcp-server]
        FILE[file-mcp-server]
    end

    USER -->|Web UI/REST| THIS
    APP -->|MCP/API/A2A| THIS
    CHAT -->|notification calls| THIS
    EXP -->|notification calls| THIS
    THIS -->|optional content formatting| LLM
    THIS -->|send messages| SMTP
    CALLBACK -->|delivery callbacks| THIS
    THIS -->|template/user/delivery state| DB
    THIS -->|secrets/config| VAULT
    THIS -->|attachment/storage links| FILE
```

The service bridges internal message intents to external delivery providers while preserving full auditability and policy controls.

## 3. Component Architecture
```mermaid
graph LR
    subgraph Transport Layer
        API[API Server<br/>src/servers/api/api_server.py]
        WEB[Web Server<br/>src/servers/web/web_server.py]
        MCP[MCP Server<br/>src/servers/mcp/mcp_server.py]
        A2A[A2A Server<br/>src/servers/a2a/a2a_server.py]
    end

    subgraph Domain Layer
        ROUTER[Notification Router]
        CHAN[Channel Adapters<br/>email/sms/chat/...]
        CONF[Confirmations + Callback Processing]
        USERS[User + Group Managers]
        PROMPTS[Prompt/LLM Formatting]
        REL[Reliability<br/>queue/rate/circuit]
        JOBS[Persistent Jobs Runtime<br/>cloud_dog_jobs SQL/Redis]
        AUTH[IDAM + RBAC]
        AUDIT[Audit + Compliance]
    end

    subgraph Data Layer
        REPO[Repository Layer<br/>src/database/repositories.py]
        DBM[Database Manager<br/>src/database/db_manager.py]
        STORE[(messages/deliveries/users/groups/...)]
    end

    API --> AUTH --> ROUTER
    WEB --> AUTH --> ROUTER
    MCP --> AUTH --> ROUTER
    A2A --> AUTH --> ROUTER
    ROUTER --> CHAN
    ROUTER --> CONF
    ROUTER --> USERS
    ROUTER --> PROMPTS
    ROUTER --> REL
    REL --> JOBS
    ROUTER --> AUDIT
    ROUTER --> REPO
    REPO --> DBM --> STORE
```

All interfaces drive the same routing and repository core, so delivery state and policy are consistent regardless of entry transport.

## 4. Module Decomposition
| Module | Path | Responsibility | Platform Package |
|---|---|---|---|
| API server | `src/servers/api/api_server.py` | Core REST endpoints for messages, deliveries, users, groups, channels | `fastapi` |
| Web server | `src/servers/web/web_server.py` | Admin UI and API proxy views | `fastapi` |
| MCP server | `src/servers/mcp/mcp_server.py` | MCP tool catalogue and tool execution | `mcp` |
| A2A server | `src/servers/a2a/a2a_server.py` | A2A health and natural-notification endpoint | `fastapi` |
| Channel adapters | `src/adapters/*`, `src/core/adapters/*` | Provider-specific delivery integrations | — |
| Confirmation processor | `src/core/confirmations/*` | Callback ingestion and delivery-state updates | — |
| User/group domain | `src/core/users/*`, `src/core/groups/*` | Targeting and recipient policy | — |
| Compliance/audit | `src/core/compliance/*`, `src/core/audit/*` | Redaction, signature, audit persistence | `cloud_dog_logging` patterns |
| Config runtime | `src/config/*` | Runtime config loading and coercion | `cloud_dog_config` patterns |
| Jobs runtime | `src/core/jobs/runtime.py` | Persistent delivery job backend selection, claims, retry state | `cloud_dog_jobs` |
| Persistence | `src/database/db_manager.py`, `src/database/repositories.py` | SQL runtime and repository layer | `cloud_dog_db` integration |

## 5. Data Model
```mermaid
erDiagram
    MESSAGE ||--o{ DELIVERY : has
    DELIVERY ||--o{ RECEIPT : records
    CHANNEL ||--o{ DELIVERY : routes
    USER ||--o{ MESSAGE : creates
    USER ||--o{ USER_DESTINATION : owns
    USER ||--o{ USER_KEYWORD : has
    GROUP ||--o{ GROUP_MEMBER : has
    GROUP ||--o{ GROUP_KEYWORD : has
    USER ||--o{ GROUP_MEMBER : member_of
    MESSAGE ||--o{ AUDIT_EVENT : audited
    TEMPLATE ||--o{ MESSAGE : renders

    MESSAGE { int id string guid string status }
    DELIVERY { int id int message_id string state int attempt_no }
    CHANNEL { int id string type bool enabled }
    USER { int id string username string preferred_channel }
    GROUP { int id string name }
    TEMPLATE { int id string name string content }
```

The persistent schema is repository-managed with migration scripts for SQLite/MySQL/Postgres under `database/migrations/`.

## 6. Interface Specifications
### 6.1 REST API
| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | Service health | None |
| GET | `/ready` / `/live` | Readiness/liveness | None |
| POST | `/messages` | Create notification message | API key |
| GET | `/messages` | List messages | API key |
| GET | `/messages/{message_identifier}` | Message details | API key |
| POST | `/messages/{message_identifier}/cancel` | Cancel message processing | API key |
| GET | `/deliveries` | List deliveries | API key |
| POST | `/deliveries/{delivery_id}/resend` | Resend delivery | API key |
| POST | `/channels/{channel_id}/test` | Channel test send | API key |
| POST | `/callbacks/email|sms|whatsapp|chat` | Provider callbacks | Provider/API key |

### 6.2 MCP Tools
| Tool | Description | Category |
|---|---|---|
| `send_notification_tool` | Send message with structured payload | delivery |
| `send_notification_natural_tool` | Natural-language notification request | delivery |
| `get_message_status_tool` / `get_message_tool` | Message lookup/status | tracking |
| `list_messages_tool` | List messages | tracking |
| `list_channels_tool` | Channel catalogue | admin |
| `cancel_message_tool` | Cancel message | control |
| `list_deliveries_tool` | Delivery list | tracking |
| `resend_delivery_tool` / `abort_delivery_tool` | Delivery lifecycle controls | control |
| `get_status_tool` | Service status summary | ops |

### 6.3 A2A Endpoints
| Endpoint | Description | Protocol |
|---|---|---|
| `/health` (A2A app) | A2A server health | HTTP GET |
| `/notify/natural` | Natural-language notify action | HTTP POST |

## 7. Dependencies & External Services
### 7.1 Platform Packages
| Package | Version | Usage in this project |
|---|---|---|
| `cloud_dog_config` (runtime usage) | project-integrated | Config loading/runtime adapters |
| `cloud_dog_logging` (runtime usage) | project-integrated | Structured logs + audit support |
| `cloud_dog_idam` (runtime usage) | project-integrated | Auth and RBAC runtime |
| `cloud_dog_db` (runtime usage) | project-integrated | DB engine abstraction |
| `fastapi` / `mcp` | dependency | Transport layer implementation |

### 7.2 External Services
| Service | Purpose | Connection | Vault Path |
|---|---|---|---|
| SQL database | Message/delivery/user/group persistence | `db.*` / URI | `dev.databases.*` |
| SMTP/SMS/chat providers | Delivery execution | channel adapter config | `dev.notifications.*` |
| LLM provider | Content formatting/generation | `llm.*` | `dev.models.*` |
| Vault | Secrets/config | env + vault client | `secret/*` |

### 7.3 Cross-Project Dependencies
```mermaid
graph LR
    THIS[<b>notification-agent-mcp-server</b>]
    CHAT[chat-client]
    EXP[expert-agent]
    FILE[file-mcp]

    CHAT -->|trigger notifications| THIS
    EXP -->|trigger notifications| THIS
    THIS -->|attachment/storage references| FILE
```

## 8. Configuration Architecture
```mermaid
graph TD
    ENV[os.environ] --> MERGE
    ENVFILE[tests/env-* + private/env-*] --> MERGE
    YAML[defaults.yaml/config files] --> MERGE
    VAULT[Vault secrets] --> MERGE
    MERGE[Runtime config model] --> APP[Notification services]
```

Important config sections include `api_server`, `web_server`, `mcp_server`, `a2a_server`, `channels`, `queue`, `rate_limit`, `circuit`, `auth`, `retention`, and `storage`.

`queue.backend` defaults to `sql`, using the same SQL database URL as the service unless `queue.sql_database_url` overrides it. `queue.backend=redis` is supported through `queue.redis_url` and `queue.redis_key_prefix`. `app.server_id` is injected into all log records and is also used by the jobs runtime to claim work and recover this server's in-flight jobs after restart.

## 8.1 Persistent Delivery Job Flow
```mermaid
sequenceDiagram
    participant API as API Server
    participant JM as Job Manager
    participant JQ as cloud_dog_jobs backend
    participant DW as Delivery Worker
    participant DB as Delivery Repository

    API->>JM: enqueue_message(...)
    JM->>DB: create message + deliveries
    JM->>JQ: ensure queued delivery jobs
    loop worker cycle
        DW->>DB: list pending queued/soft_failed deliveries
        DW->>JQ: claim matching delivery jobs with server_id
        DW->>DB: set delivery state formatting/sending/sent
        DW->>JQ: update job status running/retry_wait/succeeded/failed
    end
    Note over DW,JQ: On restart, jobs claimed by the same server_id are requeued and their deliveries return to queued for immediate recovery.
```

## 9. Security Architecture
- Authentication: API-key protected operational endpoints plus UI auth flows.
- Authorisation: role-aware endpoint restrictions and group/user policy checks.
- Secrets: provider credentials and DB secrets resolved through env/Vault mechanisms.
- Audit: event-level audit records and callback/change logging.
- Network: separate interface ports and callback endpoints with health/readiness checks.

## 10. Deployment Architecture
```mermaid
graph TB
    subgraph Development
        DEV[Local venv<br/>start_*_server.py]
    end

    subgraph Preprod
        PRE[Container runtime]
        PREDB[(SQL DB)]
        PREPROV[Provider integrations]
        PREV[Vault]
    end

    subgraph Production
        PROD[Managed deployment]
        PRODDB[(Managed SQL)]
        PRODPROV[Provider integrations]
        PRODV[Vault]
        PROXY[TLS Proxy]
    end

    DEV -.->|promote| PRE
    PRE -.->|promote| PROD
    PRE --> PREDB
    PRE --> PREPROV
    PRE --> PREV
    PROD --> PRODDB
    PROD --> PRODPROV
    PROD --> PRODV
```

## 11. Key Flows
### 11.1 Message-to-Delivery Flow
```mermaid
sequenceDiagram
    participant C as Client
    participant API as Notification API
    participant R as Router
    participant DB as Repository/DB
    participant P as Provider Adapter

    C->>API: POST /messages
    API->>R: validate + route
    R->>DB: create message + deliveries
    R->>P: dispatch queued delivery
    P-->>R: provider response
    R->>DB: update delivery state
    API-->>C: message/delivery identifiers
```

### 11.2 Callback Reconciliation Flow
```mermaid
sequenceDiagram
    participant PR as Provider
    participant API as /callbacks/*
    participant CONF as Confirmation Processor
    participant DB as Repository
    participant AUD as Audit

    PR->>API: callback event
    API->>CONF: parse + verify
    CONF->>DB: update receipt/delivery state
    CONF->>AUD: emit audit event
    API-->>PR: ack
```

## 12. Non-Functional Characteristics
| Characteristic | Approach |
|---|---|
| Scalability | Queue-backed delivery processing and decoupled channel adapters |
| Reliability | Retry/soft-fail states, callback reconciliation, health/readiness probes |
| Observability | Structured logs, audit trails, status endpoints, and delivery traceability |
| Performance | Async endpoints and batched repository access patterns |
| Maintainability | Transport/domain/persistence split with explicit repository abstraction |
