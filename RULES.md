---
template-id: T-RUL
template-version: 1.0
applies-to: RULES.md
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

# notification-agent-mcp-server — RULES.md

## Common Rules

This project follows the [Cloud-Dog AI Platform Common Rules](../cloud-dog-ai-platform-standards/RULES.md) v2.7+.
Common rules are NOT restated here; consult central for: integrity (§1), environment+config (§2),
server+process management (§3), code+change management (§4), testing (§5), documentation (§6),
repo structure (§7), operational controls (§8), security boundaries (§9), infrastructure
protection (§10), Vault path verification (§11), implementation truthfulness (§12),
sandbox dispatch preconditions (§13, W28A-882 Phase F), completion standards (§14), mandatory reading (§15).

Platform-incident relevance for this service:
- Central §1.1 Falsification — directly relevant to delivery-state claims, template/channel CRUD evidence, and report claims.
- Central §1.3 Fabrication — directly relevant to channel provider names, webhook endpoints, SMTP hostnames, and port assignments.
- Central §1.5 Production firewall — directly relevant to any Docker/Terraform deployment or remote validation involving this service.

## Project-Specific Rules

### Four-Server Architecture (Verified Port Assignments)

This project runs the canonical four-surface pattern; all four servers MUST be controlled via `server_control.sh`. Verified against [tests/env-ST](/opt/iac/Development/cloud-dog-ai/notification-agent-mcp-server/tests/env-ST):

| Surface | Verified port (tests/env-ST) | Section-5 dev port | Role |
|---------|------------------------------|---------------------|------|
| API server | `8020` | `8004` | REST API for message operations |
| Web UI server | `8021` | `8005` | Browser-based management interface |
| MCP server | `8022` | `8006` | Model Context Protocol interface |
| A2A server | `8023` | `8007` | Agent-to-Agent communication |

```bash
# CORRECT — always with --env:
./server_control.sh --env tests/env-IT start all
./server_control.sh --env tests/env-IT status
./server_control.sh --env tests/env-IT stop api

# FORBIDDEN — never without --env, never direct process commands:
./server_control.sh status                    # missing --env
pkill -f start_api_server.py                  # direct process kill
python3 start_api_server.py &                 # direct process start
ENV_FILE=<file> ./server_control.sh start api # wrong syntax
```

### Vault Sections Used by This Project

Load before any operation:
```bash
set -a; source /opt/iac/Development/cloud-dog-ai/env-vault; set +a
bash scripts/validate-vault.sh
```

Vault sections consumed by this service:
- `dev.databases` — PostgreSQL/SQLite connection for system database
- `dev.models` — LLM model definitions (Ollama endpoints, model names)
- `dev.email` — SMTP credentials for email channel adapter
- `dev.channels` — Channel adapter configurations
- `dev.storage` — Storage backend credentials (S3, WebDAV, FTP)
- `dev.redis` — Redis/Valkey connection for job queue
- `dev.keys` — API keys
- `dev.repository` — PyPI/NPM registry credentials

### Test Env Files

- `tests/env-UT` — unit test config
- `tests/env-ST` — system test config
- `tests/env-IT` — integration test config
- `tests/env-AT` — application test config

These contain non-secret configuration and `${vault.dev.*}` expressions only. `private/` overlays are NOT required if all credentials are in Vault.

### Data Management

- **NEVER** delete logs, jobs, messages, or deliveries via direct database access.
- Use API endpoints: `POST /messages/{id}/cancel`, `POST /deliveries/{id}/abort`.
- Use cleanup scripts: `scripts/cleanup_stuck_messages.py`.
- Database schema changes MUST use migrations, not direct SQL.

### LLM and Prompt Handling

- **NEVER** modify LLM prompts or user/group preferences without testing first — changes to prompts affect ALL message formatting across ALL channels; changes to user/group preferences affect personalisation.
- LLM timeout default is 480 seconds — do not reduce without testing.
- Always test prompt changes with a small message before bulk operations.

### LLM Formatter Token-Estimation Guard

The LLM formatter MUST estimate input tokens before dispatching a formatting call and refuse work that would exceed the model's context budget. Bypassing the token-estimation guard converts a recoverable formatter rejection into an LLM-side hang that blocks the delivery worker and grows queue depth. See `src/core/formatters/token_utils.py` and `src/core/formatters/llm_formatter.py`.

### Queue Admission Control

`delivery.max_queued` is not just a validation rule — it is part of the stability model for the service. Without queue admission control, slow or unavailable LLM formatting turns every outage into persistent backlog growth and makes recovery progressively worse after restart. Do not raise, suppress, or short-circuit `delivery.max_queued` without an explicit coordinator-warranted change to the stability model. (See `AGENT-LESSONS.md` for the rationale carried forward from prior incidents.)

### Delivery Worker — Split-Process Architecture

The delivery worker runs as a SEPARATE process from the API/Web/MCP/A2A servers (see `start_delivery_worker.py` and `src/core/delivery_worker.py`, with the worker server surface in `src/servers/worker/worker_server.py`). Rules:

- Do NOT in-process the delivery loop into the API/Web/MCP/A2A surfaces — it breaks shutdown semantics, lifecycle, and the httpx client lifecycle established under W28A-844.
- Each surface (API, Web, MCP, A2A) plus the delivery worker is its own process; `server_control.sh` is the only supported controller.
- The httpx client lifecycle (created at startup, closed at shutdown) is a deployment concern, not an inline-per-request concern — see `AGENT-LESSONS.md` W28A-844 notes.

### 16-State Job Lifecycle Registration

Messages and deliveries traverse a documented multi-state lifecycle (`queued → formatting → sending → sent` plus the additional retry/cancel/abort/error transitions). Any new state, transition, or terminal status MUST be registered in the lifecycle model — do NOT add ad-hoc states inside an adapter, worker, or route file. Lifecycle introspection in tests and operations depends on the registered state set being exhaustive.

### External Service Interfaces (Single Entry Points)

All external service calls MUST go through their designated manager — no scattered calls:

| External Service | Single Entry Point | Direct calls forbidden |
|------------------|--------------------|------------------------|
| LLM | `src/core/llm_manager.py` | No direct Ollama/OpenRouter calls |
| Database | Service layer | No direct SQL from business logic |
| Channel adapters | Adapter registry | No direct adapter instantiation |
| Storage | Storage service | No direct S3/WebDAV/FTP calls |

### API Endpoints

**Read-only endpoints (for status checks):**
- `GET /health` — server health (public, no auth)
- `GET /status` — queue depth, system status (requires API key)
- `GET /llm/status` — LLM queue status (requires API key)
- `GET /messages/{id}` — message details (requires API key)
- `GET /messages/{id}/deliveries` — delivery status (requires API key)

**Write endpoints (NEVER use for status checks):**
- `POST /messages` — creates messages
- `POST /messages/{id}/cancel` — cancels messages
- `POST /deliveries/{id}/resend` — resends deliveries
- `POST /deliveries/{id}/abort` — aborts deliveries

Authentication: `X-API-Key` header, from `CLOUD_DOG__NOTIFY__API_KEY` env var.

### Testing — Project-Specific Extensions

Platform testing rules (central §5) apply in full. This section adds notification-agent specifics.

**Test data:**
- Known test users: `gary@cloud-dog.net`, `operations@cloud-dog.net`
- Known test channels: `email`, `chat_rest_transparentbordes`
- Known test groups: `Admin Users`, `Operations Team`

**Delivery verification:**
- AT tests MUST verify actual delivery occurred (check external service), not just API response payloads.
- Wait for state transitions: `queued → formatting → sending → sent`.
- Check delivery payload for formatted content, attachments, links.

**LLM timeout handling in tests:**
- LLM formatting can take 5+ minutes — use `asyncio.wait_for()` with 480s timeout.
- Prompt/LLM setting changes affect ALL tests in that scenario — re-validate all.
- Check if in main thread before using `signal.SIGALRM`.

### W28A-844 Deliverable Counts (PS-77 CW-M1 alignment)

W28A-844 landed PS-77 CW-M1 alignment for this service. The deliverable count of E2E surfaces and adapter-level WebUI tests is recorded against the W28A-844 close-gate evidence; do NOT reduce the count without a coordinator-warranted scope change. See `AGENT-LESSONS.md` W28A-844 entries for the full set of behaviour rules carried forward (RBAC service-user gating in routes, broadcast-config best-effort, httpx client lifecycle, WebApiProxy client reuse, client-disconnect middleware outermost, startup config error severity, mutagen log severity, React useMemo TDZ, lucide icon import discipline, `getRowName`/`getRowId`, root-route + signIn fixture alignment, all-four-servers requirement for E2E, `--workers=1` safety once httpx leaks fixed, image cache cleanup honesty, Vault `$$` bash corruption, Vault fallback password, Playwright fixture heading + timeouts, inline quick-create forms).

## Incident Records

### Vault Key Mismatch (2026-03-04)

**Issue:** An agent wrote a W20A instruction referencing `vault.dev.storage.s3.access_key`, `vault.dev.storage.s3.secret_key`, and `vault.dev.storage.s3.bucket` — none of which exist in Vault. Actual keys: `access_key_id`, `secret_access_key`. No `bucket` key exists.

**Impact:** Executing agent blocked on AT tests for hours. Agent then attempted to edit Vault source `config.json` without authorisation — user had to intervene.

**Root cause:** Agent did not query Vault before writing the instruction. Agent then tried to "fix" by modifying infrastructure instead of reporting the mismatch.

**Rules added:** Platform RULES.md §10 (Infrastructure Protection), §11 (Vault Path Verification).

---

*Trimmed to W28A-881 §5 model under W28A-882 Phase D, 2026-06-08. Prior version was v3.0 (2026-04-13). No incident records deleted; fix-what-you-find default unchanged.*
