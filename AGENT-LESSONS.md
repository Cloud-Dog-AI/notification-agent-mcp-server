---
template-id: T-AGL
template-version: 1.0
applies-to: AGENT-LESSONS.md
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

# AGENT-LESSONS.md

## Central Programme Lesson Authority

The canonical programme lessons are in `/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-platform-standards/AGENT-LESSONS.md`. This repository file is a service-specific overlay only. If this file conflicts with the central programme file, the central file wins.

Before project work, every agent must read the central `RULES.md`, central `AGENT-LESSONS.md`, `AGENT-BOOTSTRAP-DIRECTIVE.md`, the live `AGENT-DISPATCH-TABLE.md`, the exact lane instruction, and this overlay. Do not copy central rules here; add only service-specific deltas and feed reusable lessons back to the central file.


## Platform Alignment (Binding - 2026-06-01)

- Project lessons extend but never override `/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-platform-standards/RULES.md`, `/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-platform-standards/AGENT-LESSONS.md`, or `/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-platform-standards/AGENT-BOOTSTRAP-DIRECTIVE.md`.
- Read those three platform files, this file, and instruction-specific docs before project work; report PRE-FLIGHT proof.
- Every lane must fill the CONTRACT EVIDENCE SELF-REJECTION GATE and Evidence Matrix. Any NO row means `HAVE_ALL_REQUIREMENTS_BEEN_MET: NO` or a truthful blocked return.
- In fix/remediation lanes, if a required test fails and the fix is inside the target repo, fix it. "Pre-existing" is only a baseline classifier, not an escape hatch.
- No Vault writes without explicit per-action user authorization; no SSH/firewall/live-container code or config hotfixes; no coordinator-owned state mutation unless assigned.
- Local-Docker-First and Clean Git Before Deploy apply to runtime/deploy work; source, Docker, Terraform, and package-publication mutations require quoted coordinator authorization.

This file captures repo-specific lessons that materially affected recent delivery work in `notification-agent-mcp-server`. It is intended as practical guidance for future agents working in this repository.

## Code

### DELIVERY WORKER MUST STAY OUT OF THE API PROCESS (W28A-984b)

Do not start the delivery worker from API startup with `asyncio.ensure_future(...)` or similar in-process backgrounding. The stable contract in this repo is now:

- API server is one process
- delivery worker is a separate process
- coordination happens through the database
- the worker has its own health endpoint

If API and worker share one OS process again, LLM/load pressure can still turn into API `Connection refused` failures instead of being isolated to the worker domain.

### RECOVERED CLAIMED DELIVERIES MUST BYPASS STARTUP BACKLOG DEFER (W28A-984b)

Startup backlog protection should apply to old queued backlog, not to deliveries that were already claimed and then recovered after a restart. In `src/core/delivery_worker.py`, recovered delivery IDs must always be added to the startup-exempt set, including in tests. Otherwise restart-resilience cases stall for the defer window and look like message-loss bugs.

### QUEUE LIMITS MUST BE ENFORCED AT MESSAGE SUBMISSION TIME (W28A-984b)

The useful guardrail is not "worker notices the backlog later"; it is "API refuses to accept new work once the queue is full". The correct behavior in this repo is:

- configurable `delivery.max_queued`
- warning log at 80% of limit
- HTTP `503` with `Retry-After` when the queue is full

This prevents LLM outages or slow formatting paths from growing the database queue without bound.

### WORKER HEALTH MUST EXPOSE RUNNING STATE AND BACKLOG, NOT JUST PROCESS LIVENESS (W28A-984b)

The dedicated worker endpoint needs to prove useful worker state, not just that a socket answers. The practical minimum that mattered in verification was:

- `database.status`
- `worker.running`
- `worker.queue_backlog`

That is enough to distinguish "process is up" from "worker loop is actually active and idle/healthy".

### LLM FORMATTER NOW REQUIRES `llm.token_estimate_chars_per_token` TO BE SET (W28A-925)

`src/core/formatters/llm_formatter.py` now hard-fails if `llm.token_estimate_chars_per_token` is unset or blank. In this repo `defaults.yaml` had it as an empty string, which caused translation/summary formatting to silently degrade or fail inside AT runs. The safe baseline is `4.0`, and LLM test overlays should set it explicitly so model-matrix runs do not depend on ambient defaults.

### ENDPOINT PREFIX FIXES MUST STAY CONFIG-DRIVEN AND SMALL (W28A-971)

When the platform standard changes an API prefix such as `/api` -> `/api/v1`, the correct fix is the small canonical cascade only:

- API router registration
- web proxy target path
- tests that call the API
- docs/examples

Do **not** expand the scope into config-resolution rewrites, API key fallback logic, MCP startup changes, or unrelated route refactors. Notification-agent already has a config package and proxy pattern; use them.

### CALLBACK ROUTES MUST NOT HARD-FAIL AT IMPORT TIME ON OPTIONAL CONFIG (W28A-957)

`src/servers/api/routes/callbacks.py` previously read runtime config eagerly during module import. That can kill API startup before the app even boots if optional callback settings are unresolved in a given test/runtime environment. Keep optional config access inside request-time or startup-time functions with defensive handling, not at module import top level.

### FILE DELIVERIES MUST NOT STUFF LARGE RENDERED BODIES INTO METADATA (W28A-957)

The file-channel crash path was amplified by storing oversized rendered/translated payloads and media blobs in metadata structures that later flowed into SQLite/JSON paths. For file outputs, keep metadata lightweight:

- avoid caching giant `full_content_text` payloads in delivery metadata
- strip data URIs / bulky media fields before persistence
- prefer storage references over duplicated inline content

### FILE CHANNELS SHOULD USE THE LIGHTER TRANSLATION PATH, NOT FULL LLM FORMATTING (W28A-957)

For file outputs the service does not need the same heavy formatting pipeline used for rich conversational/slack rendering. Using the lighter translation path materially reduced crash pressure and made file-channel AT cases stable again.

### FILE ADAPTERS MUST NOT LOG FULL PAYLOADS AT CRITICAL LEVEL (W28A-957)

The bespoke `logger.critical(...)` payload dumps in `src/adapters/file_adapter.py` were actively harmful: noisy logs, huge output volume, and poor operational signal. File delivery errors should log concise structured context, never full content bodies or giant metadata dumps.

### A2A HEALTH CONTRACT IN THIS STACK RETURNS `status == \"ok\"` (W28A-971/W28A-957)

The notification-agent A2A/health router contract in this platform returns `status: "ok"` and the application name, not `healthy`. Tests should align to the shared router contract instead of inventing service-specific health wording.

### MCP STDIO TESTS MUST SANITISE PARENT `CLOUD_DOG__NOTIFY__*` ENV (W28A-957)

If integration tests spawn a child MCP process for stdio verification, the child must not inherit parent transport settings like HTTP/streamable config from the test runner environment. Otherwise the child starts in the wrong mode and the stdio tests fail for the wrong reason. The helper launching stdio subprocesses must explicitly clean those parent env vars.

### BUILT UI BUNDLES MAY BE THE ONLY EDITABLE WEBUI SURFACE IN THIS REPO (W28A-957)

For some notification-agent admin flows the repo only contained `ui/dist` assets rather than source TSX for the relevant screen. When that is the reality, acknowledge it explicitly and patch the built bundle carefully rather than pretending source files exist. This is slower and riskier, so keep changes minimal and verify the exact UI behavior end-to-end.

### RBAC FOR JOBS MUST BE EXPLICIT

If the WebUI is expected to expose job visibility or job mutation, add dedicated permissions such as `read_jobs` and `write_jobs` instead of trying to reuse unrelated admin flags. The session payload also needs to return concrete permissions for non-admin users, otherwise the frontend cannot truthfully gate actions.

### RBAC SERVICE USER BYPASS IN ROUTE FILES (W28A-844)

The `_require_admin()` function in `routes/groups.py` and `routes/users.py` must recognise bootstrap service users (`notification-api`, `bootstrap-admin`, `api-runtime`) as admin-equivalent. Without this, the web proxy (which authenticates via API key mapped to `notification-api`) gets 403 on all group/user CRUD operations. The fix matches the pattern in `api_server.py:verify_admin`.

### BROADCAST CONFIG EVENT MUST BE BEST-EFFORT (W28A-844)

`_broadcast_config_event()` in `api_server.py` sends POST requests to the A2A server to notify of config changes (channel created, etc.). This MUST be wrapped in `try/except` with errors silently caught — otherwise CRUD operations fail when A2A is slow or unavailable. The broadcast is informational; the CRUD operation itself must always succeed.

### HTTPX CLIENT LEAKS CAUSE OOM UNDER SUSTAINED LOAD (W28A-844)

**Critical.** The health check endpoints in `web_server.py` created 3 new `httpx.AsyncClient()` instances per call without closing them. Under Playwright E2E testing (which hits `/health` constantly), this leaked hundreds of clients over a 20-minute run, causing server OOM. Fix: use `async with httpx.AsyncClient() as client:` context managers, or a shared module-level client.

### WEBAPPROXY CREATES NEW CLIENT PER REQUEST (W28A-844)

`cloud_dog_api_kit.WebApiProxy.request()` creates a new `httpx.AsyncClient` for every request. Under sustained proxy load, this leaks connections. Fix: create a shared `httpx.AsyncClient` at web server startup (`_shared_http_client`) and use it for all proxy calls. Close it in `_shutdown()`.

### CLIENT DISCONNECT MIDDLEWARE MUST BE OUTERMOST (W28A-844)

`ClientDisconnect` exceptions from Starlette are wrapped in `ExceptionGroup` by anyio. The suppression middleware must: (1) recursively check sub-exceptions, (2) be registered as the OUTERMOST middleware (via `app.add_middleware()` registered AFTER logging middleware, so it runs FIRST). If it runs inside the logging middleware, the error is logged before being caught.

### STARTUP CONFIG ERRORS SHOULD BE INFO NOT ERROR (W28A-844)

When vault resolution uses `unresolved_policy="empty"`, missing SMTP host and LLM base_url configs cause startup failures that log as ERROR. These should be INFO level ("Channel registration deferred", "LLM client deferred") because they're expected in test environments without full vault access. ERROR entries in startup logs cause the P3 monitoring test to fail.

### MUTAGEN WARNING IS DEBUG NOT WARNING (W28A-844)

The `audio_handler.py` mutagen availability check logs at WARNING level. Since mutagen is optional and not needed for E2E testing, this should be DEBUG to avoid polluting the P3 log test.

### TDZ (TEMPORAL DEAD ZONE) IN REACT USEMEMO DEPENDENCIES (W28A-844)

If a `useMemo` dependency array references a `const` function defined LATER in the component body, Vite's production build creates a TDZ error (`Cannot access 'X' before initialization`). This happens in GroupsPage where `columns` useMemo at line 115 referenced `deleteGroups` at line 224. Fix: move `deleteGroups` above `columns` and wrap in `useCallback`.

### LUCIDE RADIO ICON RENDERS AS FORM RADIO INPUT (W28A-844)

The Lucide `Radio` icon renders an SVG that browsers/Playwright interpret as `role="radio"`. This causes WCAG `label` violations (unlabelled radio input). Fix: use a different icon (e.g., `Antenna`) for the A2A Console nav item. Always check icon accessibility when using Lucide icons in navigation.

### LUCIDE ICONS MUST BE IMPORTED FROM `lucide-react` DIRECTLY (W28A-844)

Re-exporting all lucide icons via `export * from "lucide-react"` in `@cloud-dog/ui/index.ts` causes Vite bundler TDZ errors (`Cannot access 'X' before initialization`) due to circular module initialization. Import icons directly from `lucide-react` in the app, not through `@cloud-dog/ui`.

### AWAIT LOADX() BEFORE SETDIALOGOPEN(FALSE) (W28A-844)

In CRUD save functions, always `await loadGroups()` (or equivalent) BEFORE `setDialogOpen(false)`. If the dialog closes before data refetches, the DataTable may render stale data. Also set the status message AFTER the refetch completes so it isn't overwritten by a captureFailure from a failed reload.

### GETROWNAME PROP CONTROLS ROW ACCESSIBLE NAME (W28A-844)

DataTable rows include checkbox cell content in their computed accessible name (e.g., "Select 55 group_name ..."). Playwright's `getByRole('row', { name: /^group_name/ })` won't match because the name starts with "Select". Fix: add `getRowName` prop to DataTable that sets `aria-label` on the `<tr>`, overriding the computed name with just the entity data.

### JOB WEBUI ADOPTION REQUIRES SERVICE-SPECIFIC FIELDS

PS-76 gives the standard job columns, actions, and metrics, but notification-agent also needs service-specific fields to be useful. For this service the practical extras are `message_id`, `channel_name`, and `destination`. If those are missing from the API payload, the UI may look compliant while still being operationally weak.

### AUDIT LOG MUTATING JOB ACTIONS AT THE API BOUNDARY

Cancel, retry, and delete/archive operations need audit emission at the API route handling the user action. Relying on deeper worker internals is too indirect for WebUI-originated control paths and makes traceability harder during compliance review.

### SHARED WEBUI TABLES STILL NEED SERVICE-SPECIFIC DATA SHAPING

Using `@cloud-dog/ui` `DataTable` is required for consistency, but the backend still has to normalize job status, outcome text, queue summaries, and delivery-specific metadata into a frontend-friendly record. PS-76 compliance is not only a UI swap.

### `@require_permission` WEB ROUTES MUST ACCEPT `Request`

In this repo the permission decorator expects to find the active `Request` object in the route signature. A proxy handler that is decorated with `@require_permission(...)` but omits `request: Request` will fail at runtime with `500 "Request not found for permission check"`. W28A-669 hit this on the Jobs proxy routes for queue status, detail, cancel, and retry.

### STATE MACHINE MUST REGISTER ALL 16 LIFECYCLE STATES (W28A-678)

The `DeliveryState` enum must include all states with proper transitions. The full set of 16 lifecycle states is: `queued`, `scheduled`, `dispatched`, `formatting`, `sending`, `sent`, `accepted`, `delivered`, `read`, `paused`, `soft_failed`, `hard_failed`, `dead_lettered`, `ttl_expired`, `cancelled`, `archived`. The `archived` state is terminal.

### SHARED httpx.Client FOR OLLAMA TLS — NEVER CREATE PER-CONNECT (W28A-925b)

`src/core/llm/llm_manager.py` previously created a new `httpx.Client(verify=False)` on every call to `connect()` (line 273). Each client holds open TLS sockets and file descriptors. Under sustained LLM workload (AT tests with translations + formatting), leaked clients exhausted file descriptors and the process was killed. Fix: module-level `_shared_httpx_client` singleton reused by all `ChatOllama` instances.

### SHARED ThreadPoolExecutor — NEVER CREATE PER-CALL (W28A-925b)

Three locations previously created `ThreadPoolExecutor()` per invocation:
- `llm_manager.py:_invoke_with_timeout()` — per LLM call
- `delivery_worker.py` — per PDF generation
- `file_channel_adapter.py` — per file PDF

All three now use module-level shared executors (`_llm_executor`, `_pdf_executor`). Creating executors per-call leaks threads and their associated resources.

### NEVER CREATE NEW LLMFormatter INSTANCES PER-BLOCK (W28A-925b)

`delivery_worker.py` line ~5614 previously created `formatter = LLMFormatter(self.db, self.config)` per markdown block. Each LLMFormatter creates an LLMManager which creates a ChatOllama + httpx.Client. Use `self.formatter` (the single instance created at worker init).

### FILE CHANNEL DOES NOT NEED LLM EMAIL FORMATTING (W28A-925)

`delivery_worker.py` had `if channel_type in ('smtp', 'file'): formatter_channel_type = 'email'`. File channel already receives translated content — routing through the full LLM email formatter was redundant, doubling LLM load. Fixed to `if channel_type == 'smtp'` only.

### WEB PROXY TIMEOUT MUST EXCEED LLM LATENCY (W28A-925)

`defaults.yaml` was missing `web_server.proxy_timeout_seconds`. LLM formatting takes 20-90s. Without explicit timeout, the web proxy returns 504 before delivery completes. Set `proxy_timeout_seconds: 480`.

### MODEL-SPECIFIC SETTINGS FOR AT RUNS (W28A-925)

Not all models work with the same settings. Two required tuning for 12/12 AT subset pass:
- **qwen3.5:9b** — `NUM_CTX=16384` (32768 caused resource exhaustion)
- **qwen3.5-35b-a3b** (thinking model) — `temp=0.3, top_k=40, NUM_CTX=16384, MAX_TOKENS=2400`

Store model-specific overrides in `working/w28a-925/envs/{model}.env`.

### INDICATOR WORD ASSERTIONS MUST USE STEMS NOT EXACT WORDS (W28A-925b)

AT1.27 multilanguage tests check for English content indicators. Different LLMs produce different word forms ("summarize" vs "summarization"). Use stems: `['llm', 'summar', 'distribut', 'channel', 'privacy', 'hallucinat']` with case-insensitive substring matching.

## Test Environment

### TEST SELECTION IN THIS REPO IS GATED BY `TEST_ENV_TIER` (W28A-984b)

`tests/conftest.py` filters the suite by `TEST_ENV_TIER`. That means the literal command:

```bash
.venv/bin/python -m pytest tests/unit/ --env tests/env-AT -v
```

does **not** run the unit suite here; it selects AT-tier tests and can yield zero collected/executed unit tests. When a platform instruction requires AT base runtime plus UT/IT validation, the honest pattern is:

- preserve the literal run as evidence if required
- use small overlay env files in `working/` to set `TEST_ENV_TIER=UT` or `TEST_ENV_TIER=IT`
- keep `tests/env-AT` as the base runtime contract

### `tests/env-AT` FUNCTIONS AS A BASE RUNTIME CONTRACT, NOT JUST AN AT SWITCH (W28A-984b)

For recent IT/AT work, `tests/env-AT` needed to carry integration/application settings that were missing but operationally required, including:

- MCP stdio env-file wiring
- AT18 timeout/cancel values
- IT18 channel selection

If those keys are missing, full IT can fail even when the product code is correct. In this repo, `tests/env-AT` is effectively a reusable local runtime contract for the stack, not merely a marker for the application suite.

### FOREGROUND WORKER PROOF SHOULD BE CAPTURED AS ITS OWN STEP (W28A-984b)

When the instruction asks for a foreground worker proof, do it literally:

- start `start_delivery_worker.py` in the foreground in one terminal/session
- query `/worker/health` from another
- capture the log and JSON proof
- then stop the worker explicitly

Do not replace this with "worker was running during the full suite" or with a later public API health check. The whole point is proving the split worker can start and report health independently.

### NEVER RUN TESTS THAT RESTART SERVICES ON PORTS OWNED BY ANOTHER AGENT (W28A-925b)

**CRITICAL.** The test conftest has a dependency restart mechanism that calls `server_control.sh start` when it detects the API is unresponsive. If another agent is running on those ports (e.g., 984a on 8020), YOUR test framework will kill THEIR server. This caused 8 port collisions in one session.

**Rule:** If running tests against a Docker container on different ports (e.g., 9020), ensure the conftest dependency checker points at YOUR container's URL, not the default 8020. The `api_server.base_url` in the env file controls where the conftest checks and restarts.

### AT1.9 REQUIRES EXPLICIT ENV CONFIG (W28A-925b)

`tests/application/AT1.9_UserManagementPersonalization/` requires 9 config keys not present in the default env file. Add to `tests/env-AT-local-server`:
```
CLOUD_DOG__NOTIFY__TEST__AT19__USER_EMAIL_BASE=gary+at19@cloud-dog.net
CLOUD_DOG__NOTIFY__TEST__AT19__USER_ROLE=user
CLOUD_DOG__NOTIFY__TEST__AT19__USER_TYPE=internal
CLOUD_DOG__NOTIFY__TEST__AT19__PREF_LANGUAGE=de
CLOUD_DOG__NOTIFY__TEST__AT19__PREF_CONTENT_STYLE=formal
CLOUD_DOG__NOTIFY__TEST__AT19__PREF_TIMEZONE=Europe/Berlin
CLOUD_DOG__NOTIFY__TEST__AT19__USER_KEYWORD=security
CLOUD_DOG__NOTIFY__TEST__AT19__GROUP_KEYWORD=engineering
CLOUD_DOG__NOTIFY__TEST__AT19__GROUP_LANGUAGE=en
```

### WEBUI TESTS NEED `pytestmark = pytest.mark.webui` (W28A-925b)

WebUI Playwright tests in `AT_WEBUI_*/` folders are marked with `pytestmark = pytest.mark.webui`. The conftest skips them automatically when port 8021 (web server) isn't responding. This prevents false failures in API-only test runs.

### `tests/env-AT-local-server` DISABLES AT1.22 AV RENDERING UNLESS YOU OVERRIDE IT (W28A-925)

`tests/env-AT-local-server` includes the AT1.22 fixture block but sets `CLOUD_DOG__NOTIFY__TEST__AT122__AV_ENABLED=false`. That makes `tests/application/AT1.20_MediaSupport/cases_audio_video_rendering.py::test_at122_audio_video_rendering_ready` fail even when the product code is fine. For real AT matrix runs, add an overlay override with:

- `CLOUD_DOG__NOTIFY__TEST__AT122__AV_ENABLED=true`

Do not misclassify that gate as an LLM/model failure.

### IF `AT1.21` PASSES IN ISOLATION BUT FAILS IN THE PARAMETERIZED FILE, TREAT IT AS RUNTIME/STABILITY (W28A-925)

During W28A-925, `AT1.21` `filesystem` could pass in isolation after a fresh API restart, while the parameterized backend sweep still failed later with `Connection refused` / `RemoteProtocolError`. That pattern means the next investigation target is API stability during cumulative file-channel/storage processing, not the first backend assertion that happened to trip the poller.

### NEVER `source` TEST ENV FILES THAT CONTAIN `${vault...}` PLACEHOLDERS (W28A-957)

Notification-agent test env files are meant to be consumed by the config loader, not by bash. `source tests/env-IT` or similar will not resolve `${vault.dev...}` placeholders correctly and can produce misleading failures. The safe pattern is:

- `source /opt/iac/Development/cloud-dog-ai/env-vault`
- pass the env file via `pytest ... --env tests/env-IT`

### TEST HARNESS VAULT RESOLUTION MUST USE KV V2 `/data/` PATHS (W28A-957)

The local pytest/config harness must resolve Vault secrets through the KV v2 API shape `/<mount>/data/<path>`. Using `/<mount>/<path>` causes false "unresolved placeholder" failures even when Vault credentials are valid. If Vault-backed tests suddenly start failing on placeholders, inspect the harness path before touching service code.

### `AT1.27` IS A SEPARATE RUNTIME-STABILITY BUG, NOT A SWEEP ASSERTION TWEAK (W28A-957)

The long Chinese Slack summary/translation path can still kill the API process during application testing. This is not the kind of issue to hide inside expectation changes or sweep-report spin. Treat it as its own worker/runtime investigation once the rest of the sweep is closed honestly.

### `AT1.21` FAILURES WERE REAL SERVICE PROBLEMS, NOT JUST TEST NOISE (W28A-957)

The file-channel crashes were caused by real product behavior under load and were worth fixing inside the sweep. Do not dismiss these as flaky tests when the API actually dies and the reproduction is stable enough to isolate by backend (`filesystem`, `webdav`, `s3`).

### APPLICATION TEST DEDUP MUST HAPPEN BEFORE BROAD SWEEP RUNS (W28A-957)

Notification-agent had a massively duplicated AT surface. The useful pattern was:

1. map AT areas to requirements/use-cases
2. merge duplicate modules into parameterised `cases_*` files
3. only then run the broader AT sweep

Running the huge redundant suite first wastes days and obscures the real failures.

### FILE OUTPUT ASSERTIONS MUST USE THE REAL STORAGE CONTRACT (W28A-957)

Filesystem-backed output retrieval in this service uses `/storage/files/filesystem/{relative-path}`. Tests that call generic `/storage/{path}` will produce false `404` failures. Always align AT expectations to the actual storage route contract implemented by the service.

### VAULT $$ CORRUPTION IN BASH (W28A-844)

**Critical.** `tests/env-ST` uses `$${vault.xxx}` syntax for vault references. When `source tests/env-ST` runs in bash, `$$` expands to the shell PID, corrupting the vault reference (e.g., `1234{vault.dev.models...}`). The `cloud_dog_config` loader reads the corrupted value from `os.environ` (higher precedence than the file), causing auth failures. **Fix:** Only `source env-vault` (for VAULT_TOKEN/VAULT_ADDR). Pass env-ST via `--env tests/env-ST` flag — the config loader reads the file directly and resolves vault refs properly.

### VAULT FALLBACK PASSWORD IS `st-local-secret` (W28A-844)

When vault resolution fails with `unresolved_policy="empty"`, the web server password falls back to `st-local-secret` (from the `runtime.a2a_test_api_key` default). Playwright tests must use `E2E_PASSWORD=st-local-secret` in this scenario. The 73-character vault API key will NOT work — always verify the actual password by testing login with curl before running Playwright.

### PLAYWRIGHT FIXTURE HEADING MUST MATCH ROOT ROUTE (W28A-844)

The signIn fixture at `tests/fixtures.ts:162` asserts a heading is visible at `/`. When the root route renders UsersPage, the heading must be `/^users$/i`. When it renders DashboardPage, use `/^dashboard$/i`. The smoke test at `tests/smoke.spec.ts:23` has the same assertion. Both MUST agree with the actual route.

### PLAYWRIGHT TIMEOUT CONFIGURATION (W28A-844)

`playwright.config.ts` supports configurable timeouts via env vars: `E2E_TEST_TIMEOUT_MS` (default 30s), `E2E_EXPECT_TIMEOUT_MS` (default 10s), `E2E_ACTION_TIMEOUT_MS` (default 10s). Do NOT increase these to mask timing bugs — fix the underlying code instead. With proper httpx client management, all 40 tests complete in 2 minutes with `--workers=1`.

### INLINE QUICK-CREATE FORMS FOR E2E CRUD TESTS (W28A-844)

The CRUD E2E tests (audit-observability, channel-crud, users-crud, delivery-status, template-management) expect inline form fields visible on the page WITHOUT opening a dialog. Each CRUD page needs an inline quick-create bar above the DataTable with the expected labeled inputs and a "Create X" button. The EntityDialog is kept for edit/view. Use `idPrefix="inline"` on the inline EntityForm to avoid ID conflicts with the dialog's EntityForm.

### E2E TESTS REQUIRE ALL 4 SERVERS (W28A-844)

The channel creation endpoint calls `_broadcast_config_event()` which POSTs to the A2A server. If only API + Web are running (without MCP + A2A), channel creation fails with "All connection attempts failed". Always start all 4 servers: `./server_control.sh --env tests/env-ST start all`.

### `--workers=1` IS SAFE WHEN HTTPX LEAKS ARE FIXED (W28A-844)

With proper httpx client management (shared clients, context managers, no leaks), the 40-test Playwright suite completes in 2 minutes with `--workers=1`. Without the fix, servers OOM after 20 minutes. The fix is in the CODE, not in the worker count.

### IMAGE CACHE CLEANUP WAS A STUB (W28A-844)

`image_cache.py:cleanup_cache()` was a placeholder returning 0. If E2E tests triggered media processing, the cache grew unbounded. Now implemented with proper age-based file deletion.

### LOCAL ST WEBUI PROOF NEEDS EXPLICIT IMAP OVERRIDES

Recent local server runs needed explicit IMAP environment overrides in addition to `tests/env-ST-local-server` before the web/API stack would start cleanly. When local proof unexpectedly fails during startup, check the resolved IMAP settings first.

### REAL JOB EVIDENCE IS A DIFFERENT QUESTION FROM PAGE RENDERING

W28A-669 proved that the Jobs page can render correctly while the runtime still returns zero jobs. Treat these as separate checks:
- did the PS-76 page shell, columns, metrics, and actions render correctly?
- did the selected runtime actually surface persisted job rows after a real domain action?

### DOCKER ON OFFSET PORTS FOR PARALLEL TESTING (W28A-925b)

When another agent owns ports 8020-8023, use Docker on 9020-9023:
1. `bash docker-build.sh` — builds the image
2. Create env file with ALL URLs pointing to 9020-9023
3. `docker run -d --network host -v env-file:/app/env:ro cloud-dog/notification-agent-mcp-server:latest`
4. Run tests with `--env` pointing to the offset-port env file

The conftest dependency checker reads `api_server.base_url` from the env file — if that points to 9020, it won't touch 8020.

## Infrastructure

### `docker-build.sh` BUILDS THE LOCAL IMAGE TAG; PUSHING MAY REQUIRE AN EXPLICIT RETAG (W28A-984b)

In this repo the attached build script can finish with the fresh image on:

- `cloud-dog/notification-agent-mcp-server:latest`

while the registry tag:

- `registry.cloud-dog.net:443/cloud-dog/notification-agent-mcp-server:latest`

still points at an older local image ID. Before pushing, verify which tag actually references the new build. If needed:

```bash
docker tag cloud-dog/notification-agent-mcp-server:latest \
  registry.cloud-dog.net:443/cloud-dog/notification-agent-mcp-server:latest
```

Then push and record the registry digest from the completed push, not from the pre-push local image listing.

### PUBLIC `/health` ON PREPROD DOES NOT PROVE THE SPLIT WORKER BY ITSELF (W28A-984b)

After Phase B, the public health check validates the API/container surface and channel/database state, but it is not the same thing as dedicated worker proof. Treat these as separate acceptance signals:

- worker proof: local foreground `/worker/health`
- deploy proof: public `https://notificationagent0.cloud-dog.net/health` after soak

Do not collapse them into one claim.

### NEVER RUN BARE `docker build` IN THIS REPO; USE `docker-build.sh` (W28A-957)

This repo already has an attached build path in [docker-build.sh](/opt/iac/Development/cloud-dog-ai/notification-agent-mcp-server/docker-build.sh). It handles:

- host-network build mode
- CA certificate injection
- Vault-backed package-index credentials
- pip config secret mounting
- build logging to `working/docker-build.log`

The correct build pattern is:

```bash
set -a; source /opt/iac/Development/cloud-dog-ai/env-vault; set +a
bash docker-build.sh 2>&1 | tee working/<run-specific-build-log>.log | tail -20
```

If a manual/bare docker build was run first, do not pretend that satisfies the repo rule; rerun the attached build script and report that result only.

### PREPROD REDEPLOY FOR NOTIFICATION-AGENT IS DIGEST-DRIVEN THROUGH TERRAFORM (W28A-957)

Preprod in `/opt/iac/cloud-dog-repo/terraform/server0.viewdeck.com/27 MLAgents` already tracks `registry.cloud-dog.net:443/cloud-dog/notification-agent-mcp-server:latest` via `docker_registry_image` + `docker_image.pull_triggers`. A targeted apply against:

- `docker_image.notificationagent`
- `docker_container.notificationagent0`

is enough to pull the new digest into preprod when the image has already been pushed.

### HEALTH VERIFICATION MUST INCLUDE BOTH PUBLIC AND API ROUTES (W28A-971/W28A-957)

For notification-agent preprod, useful close-out proof is:

- unauthenticated `GET /health`
- authenticated `GET /api/v1/health` with the preprod `X-API-Key`

Verifying only `/health` is not enough after API-prefix changes.

### HTTPX CLIENT LIFECYCLE IS A DEPLOYMENT CONCERN (W28A-844)

Leaked httpx clients accumulate file descriptors and memory. In production deployments with long-running uvicorn workers, even a slow health-check polling interval can exhaust resources over hours. Audit all `httpx.AsyncClient()` instantiations for proper `aclose()` or context manager usage.

### MCP SERVER HTTP CLIENT NEEDS SHUTDOWN HANDLER (W28A-844)

`MCPServerHTTP` and `MCPServerJSONRPC` in `mcp_server_http.py` create `self.http_client = httpx.AsyncClient(...)` in `__init__` but never close it. Added `async def close()` method. Wire this to server shutdown in production deployments.

### DOCKER CACHE CAN HIDE PLATFORM PACKAGE CHANGES

When validating package upgrades or logging fixes, do not trust a successful image build alone. Docker layer cache can leave an older package version effectively deployed unless the relevant install layer is invalidated.

### CONTAINERS THAT RELY ON VAULT-DRIVEN SETTINGS NEED THOSE VARS PRESENT AT STARTUP

Notification-agent depends on real runtime configuration, including secrets-backed values. A container can appear structurally healthy while still failing functional startup if the Vault-derived environment was not propagated into the process.

## Architecture

### PROCESS SEPARATION IS THE ACTUAL STABILITY FIX, NOT A COSMETIC REFACTOR (W28A-984b)

The key lesson from Phase B is architectural: when API and delivery worker share the same process, load in one failure domain becomes load in both. Under sustained LLM work, that shows up as API connection failures even though the root pressure is in delivery/formatting. Moving the worker to its own process is the fix because it restores fault isolation.

### THE DATABASE IS THE API/WORKER COORDINATION CONTRACT (W28A-984b)

This repo does not need bespoke IPC between API and delivery worker. The durable contract is:

- API writes messages/deliveries
- worker claims, resumes, retries, and completes deliveries from the DB
- restart recovery is validated at the DB-claim boundary

That is why restart-resilience tests are so important here: they are checking the architecture, not just timing.

### ADMISSION CONTROL IS PART OF THE SERVICE ARCHITECTURE (W28A-984b)

`delivery.max_queued` is not just a validation rule. It is part of the stability model for the service. Without queue admission control, slow or unavailable LLM formatting turns every outage into persistent backlog growth and makes recovery progressively worse after restart.

### NOTIFICATION-AGENT SWEEP WORK SHOULD DISTINGUISH STRUCTURAL FIXES FROM FOLLOW-UP BUGS (W28A-957)

There was real value in separating:

- structural sweep work: dedup, endpoint alignment, cache/file-channel stability, docs, deploy proof
- separate runtime bug investigations: e.g. `AT1.27` Chinese Slack summary kill path

If everything is treated as one giant sweep, the service stays in perpetual "almost done" mode and no honest closure happens.

### THIS SERVICE IS HIGHLY COUPLED ACROSS API, WEB, MCP, A2A, WORKER, AND UI (W28A-971/W28A-957)

Even small-looking changes, such as an API path prefix update or admin UI CRUD flow, can require verification across:

- API route mounts
- web proxy targets
- MCP/A2A health and config behavior
- application tests
- built UI bundle behavior
- preprod Traefik routing

Do not assume a change is localized just because the code edit is small; verify the dependent surfaces explicitly.

### ROOT ROUTE CHANGE: PS-77 CW-M1 (W28A-844)

The root route `/` was changed from DashboardPage to UsersPage during W28A-844 to satisfy the signIn fixture. The DashboardPage is at `/dashboard`. Both the fixture and smoke test must agree with whatever component renders at `/`. The nav's `homePath` should point to `/dashboard` for operational console use.

### ENTITYFORM PROPS: submitLabel AND idPrefix (W28A-844)

`@cloud-dog/ui` EntityForm supports `submitLabel` (override "Save" button text, e.g., "Create group", "Save changes") and `idPrefix` (prefix for field IDs to avoid conflicts when multiple forms exist on the same page, e.g., "inline" for the quick-create form vs "ef" for the dialog form).

### DATATABLE PROPS: getRowName AND getRowId (W28A-844)

`getRowName` sets `aria-label` on `<tr>` elements, controlling the row's accessible name for Playwright's `getByRole('row', { name: ... })` locator. Without it, the accessible name includes checkbox cell content ("Select 55 ...") which breaks regex assertions expecting the name to start with entity data.

### NOTIFICATION-AGENT HAS A FULL JOB LIFECYCLE

This service already has richer job semantics than a simple message sender: queueing, attempts, retries, outcomes, and delivery-linked records. Any job UI or API work should preserve that lifecycle instead of flattening everything into a generic "send result".

### `cloud_dog_api_kit` v0.4.1 PROVIDES WebApiProxy (W28A-849)

`WebApiProxy.from_config(config)` replaces the bespoke `api_request()` function in `web_server.py`. However, WebApiProxy creates a new httpx client per request — so the web server should use a shared `httpx.AsyncClient` for production workloads. The WebApiProxy is still used for config resolution (`api_base_url`, `api_key` from config).

### UNIFIED NOTIFICATION-AGENT PROCESS NEEDS EXPLICIT SURFACE STARTUP (W28A-93d)

When API, Web, MCP, and A2A share one HTTP process, do not assume mounted standalone apps have run their original startup hooks. Guard lazy startup and sync extracted route-module globals after runtime config/client creation. Shared-root routes are also ambiguous: unauthenticated browser `GET /` may see the API banner instead of the Web login redirect in unified mode. Live-runtime tests should prefer an already-running `server_control.sh` stack and must not restart API while the worker can hold SQLite locks.

### UNIFIED API COMPATIBILITY MUST COVER ROOT AND `/api/v1` PATHS (W28A-93d-R1)

The unified app can normalize `/api/v1` requests onto root API handlers. Keep legacy root and versioned admin/user/group compatibility aligned: preference updates, destination CRUD, group membership, keyword endpoints, and version probes must behave consistently through the unified surface.

### FILE CHANNEL ADAPTERS MUST NOT IMPORT DELIVERY WORKER PRIVATE EXECUTORS (W28A-93d-R1)

Channel adapters run outside the delivery worker in tests and admin flows. If an adapter needs a PDF executor, keep that executor local to the adapter or use a shared public helper; importing a private delivery-worker executor couples startup paths and can break non-worker execution.

### BROWSER PAGE ROUTES THAT LOOK LIKE API PATHS NEED EXPLICIT UNIFIED ROUTING (W28A-93d-R1)

In the unified process, unauthenticated browser `GET` requests for pages such as `/prompts` can collide with API routing. Add explicit browser-page classification for page-like GET/HEAD requests instead of relying on historical split-port behavior.

### LOCAL AT FILE STORAGE MUST SET THE STORAGE BASE PATH (W28A-93d-R1)

AT file-channel cases may read `storage.filesystem.base_path` before file-channel-specific settings. Local AT envs must set `CLOUD_DOG__NOTIFY__STORAGE__FILESYSTEM__BASE_PATH` to a writable test path, not only the file-channel path, or filesystem channel creation can try `/app/storage/filesystem`.

## Related Projects

### PLATFORM INSTRUCTIONS CAN COLLIDE WITH REPO-SPECIFIC TEST GATING; REPORT BOTH HONESTLY (W28A-984b)

Recent work showed that a platform instruction can require a literal pytest command that is technically valid but operationally misleading in this repo because of `TEST_ENV_TIER` gating. The right pattern is:

- keep the literal command/result as evidence when asked
- run the meaningful repo-native validation as a second step
- document why the difference exists

That keeps the reporting honest without pretending the repo behaves like every other project.

### TERRAFORM/PUBLIC HEALTH LIVE OUTSIDE THIS REPO'S INTERNAL PROCESS MODEL (W28A-984b)

The sibling Terraform repo and the public preprod route know how to deploy and probe the service container, but they do not automatically communicate every internal process boundary that now exists inside notification-agent. When Phase B or later work introduces separate worker processes, keep repo-local worker proof alongside deploy proof instead of assuming the external project will surface it for you.

### TERRAFORM PREPROD ROUTING FOR NOTIFICATION-AGENT LIVES OUTSIDE THIS REPO (W28A-971/W28A-957)

Notification-agent deploy completion often depends on the sibling terraform repo at:

- `/opt/iac/cloud-dog-repo/terraform/server0.viewdeck.com/27 MLAgents`

When service code is correct but live behavior is wrong, inspect the Traefik/router/container config there before over-editing the service itself.

### PLATFORM STANDARDS SHOULD DRIVE TEST MERGES, NOT JUST UI/ROUTE SHAPE (W28A-957)

The useful dedup work came from mapping notification-agent AT modules back to platform requirements and real use-cases, not just grouping tests by similar filenames. Future agents should use the standards/requirements matrix first and the historical folder names second.

### PS-76 DEFINES THE SHARED JOB WEBUI CONTRACT

For notification-agent job WebUI changes, PS-76 is the binding standard for common columns, summary metrics, row actions, bulk actions, detail dialog structure, and status badge behaviour. Service work should extend PS-76, not replace it with custom page patterns.

### `@cloud-dog/ui` MUST NOT RE-EXPORT `lucide-react` (W28A-844)

`export * from "lucide-react"` in `packages/ui/src/index.ts` causes Vite TDZ errors at runtime. Lucide icons must be imported directly by apps from `lucide-react`. The re-export was removed in W28A-844.

### `@cloud-dog/shell` NavItem aria-hidden (W28A-844)

The `NavItem.tsx` icon wrapper span had `aria-hidden="true"`. This is correct for decorative icons but caused WCAG `aria-hidden-focus` violations because the span is inside a focusable `<a>` link. Removed in W28A-844. App-level `navIcon()` helpers should also omit `aria-hidden="true"`.

### PACKAGE PUBLISHING MUST USE `pypi.cloud-dog.net` ONLY

Per platform rules and shared lessons, package publish workflows must use `pypi.cloud-dog.net` with Vault-provided credentials. Gitea is prohibited for package publication.

### cloud_dog_jobs PACKAGE PROVIDES THE JOB FRAMEWORK (W28A-678)

The `cloud_dog_jobs` package provides: `JobQueue`, `JobRequest`, `JobStateMachine`, `register_state_extension`, `FallbackPolicyManager`, `FallbackAction.DEAD_LETTER`. Notification-agent builds on this package for all job lifecycle management.

### PREPROD API PATH IS `/api/v1/messages`, NOT `/messages` (A.7 PW fix 2026-05-06)

On preprod, the notification-agent API is routed through Traefik with a `/api/v1/` prefix. Direct API calls in Playwright tests (e.g., `request.post()` using `E2E_DIRECT_API_BASE_URL`) must use `/api/v1/messages`, not `/messages`. The bare `/messages` path returns 404 on preprod. This affects `jobs-ps76.spec.ts` and any test that makes direct API calls outside the web proxy.

### COOKIE-TO-API-KEY BRIDGE REQUIRES EXPLICIT COOKIE CLEARING ON LOGOUT (A.7 PW fix 2026-05-06)

The A89 cookie-to-api-key bridge means that calling `/auth/logout` via `fetch()` alone does not invalidate the browser session. The bridge maps cookies to API keys, and the browser still holds valid cookies after a server-side logout. Tests that verify logout must call `context.clearCookies()` after the logout POST to ensure the session is fully terminated. Without cookie clearing, navigation to a protected route still succeeds.

### P3 LOG MONITORING MUST FILTER BY RECENCY ON LIVE SYSTEMS (A.7 PW fix 2026-05-06)

The P3 monitoring test asserts zero WARN/ERROR log entries. On a live preprod system with historical log accumulation, this is impossible. The test now filters entries by timestamp recency (last 60 seconds) when `E2E_USE_LOCAL_SERVER=0`, and skips entries without parseable timestamps since their age cannot be determined. Local/CI clean-start environments still enforce zero tolerance.

### PLAYWRIGHT RUNTIME-CONFIG OVERRIDES MUST USE `E2E_API_BASE_URL`, NOT PAGE `BASE_URL` (A.7 PW fix 2026-05-06)

In notification-agent Playwright tests, `/runtime-config.js` overrides drive the auth adapter endpoints (`/auth/login`, `/auth/me`, `/auth/logout`). When a preprod replay sets `E2E_BASE_URL=https://notificationagent0.cloud-dog.net` but does not set `BASE_URL`, using `process.env.BASE_URL ?? 'http://localhost:8021'` inside the injected runtime config silently points browser auth calls at localhost. The visible symptom is the login form showing `Failed to fetch` and the test staying on `/login`. For any runtime-config override in this app, source `API_BASE_URL` from `E2E_API_BASE_URL` first.

### GROUP DELETE DATATABLE REFRESH REQUIRES PAGE RELOAD (A.7 PW fix 2026-05-06)

After clicking the delete button on a group row, the DataTable's local state may not immediately reflect the server-side deletion. Clearing and re-filling the search field does not force a refetch from the API. The reliable pattern is `page.reload()` after a short wait, then re-search. This avoids flaky timeout failures where the row persists in the local DataTable cache.
