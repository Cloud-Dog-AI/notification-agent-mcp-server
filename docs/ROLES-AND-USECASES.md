---
template-id: T-RUC
template-version: 1.1
applies-to: docs/ROLES-AND-USECASES.md
registry: service
required: must-have
when-applicable: ""
template-last-updated: 2026-06-17
template-owner: platform-standards

project: notification-agent-mcp-server
doc-last-updated: 2026-06-18
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: indefinite
doc-conformance-stamp: 2026-06-17T00:00:00Z
req-trace-version: 1.0
surface-coverage: [api, mcp, a2a, webui]
authored-by: W28E-1807A Stream-A
baseline-state: notification-agent origin/main @ W28A-870-R2 accepted (2a5b568) + W28C-1714 reqtrace closeout
---

# notification-agent-mcp-server — ROLES-AND-USECASES

> **Template version:** T-RUC v1.1 (W28E-1807A Stream-A full UC inventory).
> Cross-cutting role/RBAC behaviour is **pinned by reference** to `PS-83-canonical-role-catalog.md`,
> `PS-82-access-control-session-test-matrix.md`, and `PS-COMMON-SVC-REQ.md` (CSR-005/006/016/032/035)
> — it is not restated here. Every UC-NNN maps to one OR MORE FR/CS-NNN in
> [REQUIREMENTS.md](REQUIREMENTS.md) and binds to >=1 test row in [TESTS.md](TESTS.md) per
> PS-REQ-TEST-TRACE section 3.5.

## 1. Roles

Canonical roles from `PS-83-canonical-role-catalog.md` plus the notification-agent system actor.

| Role | From | Notes |
|---|---|---|
| `admin` | platform | Full access — channels, users, groups, RBAC, API keys, prompts, settings, jobs, audit (read), live-test. |
| `read-write` | platform | Data write — compose/send notifications, manage prompts, retry/abort deliveries; cannot manage RBAC/users/API keys. |
| `read-only` | platform | Data read only — view dashboards, messages, deliveries, prompts, audit; every write path returns `403`. |
| `anon` | platform | Unauthenticated — every non-public API/MCP/A2A/WebUI route returns `401` before service logic runs. |
| `system` | local | Non-interactive actors: the async delivery **worker/queue**, the **scheduler** trigger, the **IDAM resolver** cascade, and the LLM formatting step. Operate under service identity with a propagated `correlation_id`. |

## 2. Personas

| Persona | Description | Roles |
|---|---|---|
| Platform Operator | Configures channels, prompts, RBAC, users/groups, API keys; monitors deliveries/jobs/audit. | `admin` |
| Notification Author | Composes and sends broadcast/personalised notifications; manages own prompts; retries deliveries. | `read-write` |
| Auditor / Viewer | Reviews dashboards, message/delivery history, and the tamper-resistant audit log. | `read-only` |
| Calling Agent / Service | Another Cloud-Dog service or agent driving notification via MCP tools or A2A tasks. | `read-write` (scoped key) |
| End Recipient User | A managed user/group whose preferences (language/channel/style/timezone/keywords) shape delivery. | data subject |
| Delivery Worker / Scheduler | Background actor draining the queue, running scheduled sends, applying the RBAC cascade. | `system` |
| Intruder | Unauthorised or wrong-role caller probing any surface. | `anon` / wrong-role |

## 3. Use cases (positive)

**Coverage rule:** UC-001…UC-026 cover every primary entity (channel, message/notification, delivery, prompt, user, group, RBAC/role, API key, job, settings, audit-log, preference, MCP, A2A, output-artifact, auth, LLM) across the `admin / read-write / read-only / system` actors and the `api / mcp / a2a / webui` surfaces.

| UC ID | Persona | Goal | Surface | Requirements | Tests |
|---|---|---|---|---|---|
| `UC-001` | Operator | Create + configure a channel with type-specific config (SMTP/SMS/WhatsApp/chat-REST/file/loopback) | REST/WEBUI/MCP | `FR-012`, `FR-008`, `CS-002` | `tests/unit/UT1.4_ChannelAdapters/test_adapters.py`; AT_WEBUI_AdminCrud |
| `UC-002` | Operator | Run a live test against a configured channel | REST/WEBUI | `FR-008`, `FR-012` | `tests/integration/IT1.12_RealChannelAdapters`; UT1.4_ChannelAdapters |
| `UC-003` | Author | Compose + send a broadcast notification to a group | REST/MCP/WEBUI | `FR-003`, `FR-006`, `FR-024` | `tests/integration/IT1.19_MessageManagement/test_message_management.py`; AT1.12_Broadcast |
| `UC-004` | Author | Send a personalised notification with per-recipient content | REST/MCP | `FR-004`, `FR-016` | `tests/application/AT1.13_Personalised`; IT1.2_MultiChannelDelivery |
| `UC-005` | Author | Issue a natural-language notification command | REST/MCP/A2A | `FR-020`, `FR-009` | `tests/application/AT1.11_NaturalLanguage`; AT1.14_NaturalLanguage |
| `UC-006` | Author/Viewer | View a message and its delivery detail (request/output/deliveries) | REST/WEBUI | `FR-024`, `FR-011` | `tests/integration/IT1.19_MessageManagement/test_message_management.py` |
| `UC-007` | Author | Retry or abort a failed/queued delivery; honour dead-letter | REST/WEBUI | `FR-P001`, `FR-011` | `tests/integration/IT1.27_DeliveryResendAbort/test_delivery_resend_abort.py` |
| `UC-008` | Author/Viewer | Browse deliveries with channel/date/destination/free-text filters | REST/WEBUI | `FR-011`, `FR-024` | `tests/integration/IT1.9_DeliveriesComprehensive/test_deliveries_comprehensive.py` |
| `UC-009` | Operator | Manage prompt templates: CRUD, multi-language, channel scope, variables | REST/WEBUI | `FR-007`, `FR-009` | `tests/unit/UT1.7_PromptManagement/test_prompt_management.py`; AT1.6_PromptManagement |
| `UC-010` | Operator | Create + manage users (display name, owner metadata, enable/disable) | REST/WEBUI | `FR-014`, `CS-002` | `tests/unit/UT1.8_UserManagement`; AT1.9_UserManagementPersonalization |
| `UC-011` | Operator | Create + manage groups and user/group membership | REST/WEBUI | `FR-014`, `FR-021` | `tests/unit/UT1.9_GroupManagement/test_group_admin_api.py` |
| `UC-012` | End User | Self-service preferences: language (ISO 639-1), preferred channel, content style, timezone, keywords | REST/WEBUI | `FR-014`, `FR-021`, `FR-016` | `tests/application/AT1.15_UserPreferences`; UT1.8_UserManagement |
| `UC-013` | Operator | Set group/channel preference defaults consumed by the delivery path | REST/WEBUI | `FR-016`, `FR-021` | `tests/unit/UT1.10_GroupPersonalization/test_group_personalization.py` |
| `UC-014` | Operator | Assign RBAC roles + per-channel scope to users/groups | REST/WEBUI/MCP | `CS-002`, `CS-004`, `FR-005` | `tests/integration/IT1.11_RBACIntegration/test_rbac_integration.py` |
| `UC-015` | System | Resolve group->channel access cascade for a restricted user | internal/MCP | `CS-001`, `FR-005` | `tests/smoke/test_cascade_resolves.py` |
| `UC-016` | Operator | Issue + revoke owner/group-scoped API keys | REST/WEBUI | `CS-002`, `FR-014` | `tests/unit/UT1.62_FlatRoleLogin/test_flat_role_login.py`; admin_routes |
| `UC-017` | Operator | Monitor async jobs: status, result, error, schedule/run/duration, correlation | REST/WEBUI/MCP | `FR-022`, `FR-026` | `tests/unit/UT1.3_JobManager/test_job_manager.py`; IT1.23_MCP_AsyncJobs |
| `UC-018` | System | Drain the delivery queue / run scheduled sends via the worker | internal | `FR-011`, `FR-026` | `tests/integration/IT1.25_AsyncMessageSubmission`; IT1.8_AsyncMessageDelivery |
| `UC-019` | Operator | View + apply runtime settings through the platform config precedence chain | REST/WEBUI | `FR-016`, `CS-002` | `tests/unit/UT1.1_ConfigurationSystem/test_config_after_cleanup.py`; UT1.21_AdminConfigCrud |
| `UC-020` | Viewer/Operator | Read the tamper-resistant audit & log (channel/user/job filters; no delete affordance) | REST/WEBUI | `CS-003`, `FR-012` | `tests/unit/UT_AuditLogFormat/test_audit_log_format.py`; AT_WEBUI_Forensic |
| `UC-021` | Calling Agent | Invoke an MCP tool (e.g. `send_notification`) with JSON-serialisable I/O and stock-client-compatible response | MCP | `FR-010`, `FR-026` | `tests/unit/UT1.22_MCPContracts/test_send_notification_structured_content.py`; IT1.20_MCP_StreamableHTTP |
| `UC-022` | Calling Agent | Drive an A2A task / event stream and correlate task/result | A2A | `FR-P002`, `FR-026` | `tests/integration/IT1.29_A2AInterfaceVerification/test_a2a_config_events.py` |
| `UC-023` | Author | Generate multimedia / PDF / HTML output for a notification | REST/MCP | `FR-018`, `FR-022` | `tests/unit/UT1.14_PDFGenerator/test_pdf_generator.py`; AT1.19_PDFGeneration |
| `UC-024` | System | Persist + reference an output artifact through the storage abstraction | internal/REST | `FR-018`, `FR-016` | `tests/integration/IT1.16_StorageIntegration/test_storage_integration.py` |
| `UC-025` | All authenticated | Authenticate via WebUI flat login (admin / read-write / read-only cookie) | WEBUI | `CS-001`, `FR-011` | `tests/unit/UT1.62_FlatRoleLogin/test_flat_role_login.py` |
| `UC-026` | System | LLM-assisted formatting / translation of notification content | internal | `FR-001`, `FR-009` | `tests/unit/UT1.5_LLMFormatter/test_llm_formatter.py`; IT1.15_LLMRealIntegration |

## 4. Negative use cases (admin/security)

Required to prove RBAC per surface. Cross-cutting denial semantics are pinned to `PS-COMMON-SVC-REQ` CSR-005/006/025/032 and the `CS-001`…`CS-016` baseline.

| UC ID | Persona | Attempted | Expected | Test |
|---|---|---|---|---|
| `UC-101` | Intruder (`anon`) | Read notification data on the API without auth | `401` | `tests/unit/UT1.60_UnauthAuthGate/test_unauth_auth_gate.py` (`CS-001`, `CS-005`) |
| `UC-102` | `read-only` | POST/PUT/DELETE a write API route | `403` | `tests/unit/UT1.61_AuthedNonAdminGate/test_authed_non_admin_gate.py` (`CS-002`, `CS-009`) |
| `UC-103` | `read-only` | Invoke a mutating MCP tool | `403` | `tests/integration/IT1.11_RBACIntegration/test_rbac_integration.py` (`CS-002`, `CS-010`) |
| `UC-104` | `read-only` | Submit a mutating A2A task | `403` | `tests/integration/IT1.29_A2AInterfaceVerification/test_a2a_config_events.py` (`CS-011`) |
| `UC-105` | `read-only` | Trigger a WebUI write action | `403` | `tests/unit/UT1.61_AuthedNonAdminGate/test_authed_non_admin_gate.py` (`CS-012`) |
| `UC-106` | Any | Submit a request with a missing required parameter | `422` | `tests/unit/UT1.22_MCPContracts/test_send_notification_structured_content.py` (`CS-003`, `CS-013`) |
| `UC-107` | `read-write` | Perform an admin-privileged op (RBAC/user/API-key) | `403` | `tests/integration/IT1.11_RBACIntegration/test_rbac_integration.py` (`CS-004`) |
| `UC-108` | Restricted `system`/user | Read a channel not granted by any group binding | denied | `tests/smoke/test_cascade_resolves.py` (`CS-001`) |
| `UC-109` | Intruder (`anon`) | Reach an authenticated WebUI page | `401`/redirect | `tests/unit/UT1.60_UnauthAuthGate/test_unauth_auth_gate.py` (`CS-008`) |
| `UC-110` | Any | Find a UI affordance to delete an audit/log entry | none (tamper-resistant, PS-40/NIST AU-9) | `tests/application/AT_WEBUI_Forensic` (`CS-003`, GWN `NA-AL-10`) |

## 5. Cross-references

- [REQUIREMENTS.md](REQUIREMENTS.md) — FR/CS/NF rows these UCs realise; section "W28E-1807A WebUI Feedback Trace".
- [TESTS.md](TESTS.md) — TEST-DESIGN rows and the section 2 Coverage map.
- `PS-82-access-control-session-test-matrix.md`, `PS-83-canonical-role-catalog.md` — canonical roles + access matrix (pinned, not restated).
- `PS-COMMON-SVC-REQ.md` — CSR-005/006/016/032/035 (auth, RBAC, WebUI same-path, negative matrix, operator taxonomy).

## 6. Cross-surface UC mappings (per T-RUC v1.1 + PS-REQ-TEST-TRACE section 3.5)

This service's surface set: **api, mcp, a2a, webui** (plus `internal` system actors).

Default declaration for every UC-NNN (operator amends per UC in the table above):

```yaml
surfaces: ['api', 'mcp', 'a2a', 'webui']
roles: [admin, read-write, read-only, anon, system]
FR-mapping: see section 3/4 "Requirements" / "Test" columns
```

UC->Stream ownership: positive UC-001…UC-026 drive Stream-B functional + Stream-C WebUI/E2E scope; negative UC-101…UC-110 are the mandatory RBAC drive-out set carried into Stream-B/C per `PS-COMMON-SVC-REQ` CSR-032.

## 7. Project-specific notes

- Baseline state consumed: W28A-870-R2 accepted on `origin/main 2a5b568` (69/69 UAT rows PASS_FIXED_VERIFIED; NA-PR-01..10 preference contract proven; deployed digest `sha256:8e83b79c…`), and the W28C-1714 reqtrace closeout at current `origin/main`.
- `system` actor RBAC cascade (UC-015/UC-108) is the W28A-744 IDAM 0.5.x `group->channel` resolver proven live as T3-NA-CASCADE; the resolver-level smoke is `tests/smoke/test_cascade_resolves.py`.
