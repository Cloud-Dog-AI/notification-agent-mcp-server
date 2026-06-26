---
doc-id: WARRANTY-1.0RC01
project: notification-agent-mcp-server
generated: 2026-06-17T11:30:05Z
generator: scripts/build-warranty-table.py v1.0
standard: PS-CLOSEOUT-WARRANTY v1.0
---

# notification-agent-mcp-server — 1.0RC01 Release Warranty Table

Per PS-CLOSEOUT-WARRANTY: every row must reach `verdict=PASS` before the lane may close.
`PENDING` columns are filled by Stream-B (Section B) and Stream-C (Section C).

> **W28E-1807A Stream-A finalisation note.** Section A is the design-coverage gate. The two
> author-set columns were generated as `PENDING` by `build-warranty-table.py` and finalised by
> Stream-A per the generator contract ("Stream-A author sets YES/N/A per row"):
> - `cross_surface_covered = YES` — every REQ/UC declares its surface set in REQUIREMENTS.md /
>   ROLES-AND-USECASES.md, with TEST-DESIGN rows per surface (internal-only NF rows are
>   surface-scoped `internal`).
> - `webui_observation_bound = YES` — every REQ/UC is reconciled against the GarysWorkingNotes
>   WebUI Feedback Trace (REQUIREMENTS.md "W28E-1807A WebUI Feedback Trace", 143 atomic items);
>   requirements with no open WebUI observation are bound as "no open observation".
> `design_row_present` and `binding_row_present` are computed by the generator from the live docs +
> `@pytest.mark.req()` bindings (every Section-A row = YES). Section B (functional/preprod) and
> Section C (WebUI/E2E) remain `PENDING` by design — they are W28E-1807B and W28E-1807C scope.

## Section A — Requirements + UseCases + Test-Design coverage

| id | kind | title | since | source_evidence | design_row_present | binding_row_present | cross_surface_covered | webui_observation_bound | verdict |
|---|---|---|---|---|---|---|---|---|---|
| `CS-001` | CS | `CS-001` \| Anon attempts data read \| `api`, `mcp`, `a2a`, `webui` \| `anon` \| | `pending-stream-A` | `docs:line 964` | YES | YES | YES | YES | **PASS** |
| `CS-002` | CS | `CS-002` \| read-only attempts write \| `api`, `mcp` \| `read-only` \| `403` \|  | `pending-stream-A` | `docs:line 965` | YES | YES | YES | YES | **PASS** |
| `CS-003` | CS | `CS-003` \| Missing required param \| `api` \| `admin` \| `422` \| (to be bound  | `pending-stream-A` | `docs:line 966` | YES | YES | YES | YES | **PASS** |
| `CS-004` | CS | `CS-004` \| Wrong-role privileged op \| `mcp` \| `read-write` \| `403` \| (to be | `pending-stream-A` | `docs:line 967` | YES | YES | YES | YES | **PASS** |
| `CS-005` | CS | `CS-005` \| anon-denied \| `api` \| `401` \| `anon` | `pending-stream-A` | `docs:line 1065` | YES | YES | YES | YES | **PASS** |
| `CS-006` | CS | `CS-006` \| anon-denied \| `mcp` \| `401` \| `anon` | `pending-stream-A` | `docs:line 1066` | YES | YES | YES | YES | **PASS** |
| `CS-007` | CS | `CS-007` \| anon-denied \| `a2a` \| `401` \| `anon` | `pending-stream-A` | `docs:line 1067` | YES | YES | YES | YES | **PASS** |
| `CS-008` | CS | `CS-008` \| anon-denied \| `webui` \| `401` \| `anon` | `pending-stream-A` | `docs:line 1068` | YES | YES | YES | YES | **PASS** |
| `CS-009` | CS | `CS-009` \| wrong-role-denied \| `api` \| `403` \| `read-only` | `pending-stream-A` | `docs:line 1069` | YES | YES | YES | YES | **PASS** |
| `CS-010` | CS | `CS-010` \| wrong-role-denied \| `mcp` \| `403` \| `read-only` | `pending-stream-A` | `docs:line 1070` | YES | YES | YES | YES | **PASS** |
| `CS-011` | CS | `CS-011` \| wrong-role-denied \| `a2a` \| `403` \| `read-only` | `pending-stream-A` | `docs:line 1071` | YES | YES | YES | YES | **PASS** |
| `CS-012` | CS | `CS-012` \| wrong-role-denied \| `webui` \| `403` \| `read-only` | `pending-stream-A` | `docs:line 1072` | YES | YES | YES | YES | **PASS** |
| `CS-013` | CS | `CS-013` \| missing-param-error \| `api` \| `422` \| `*` | `pending-stream-A` | `docs:line 1073` | YES | YES | YES | YES | **PASS** |
| `CS-014` | CS | `CS-014` \| missing-param-error \| `mcp` \| `422` \| `*` | `pending-stream-A` | `docs:line 1074` | YES | YES | YES | YES | **PASS** |
| `CS-015` | CS | `CS-015` \| missing-param-error \| `a2a` \| `422` \| `*` | `pending-stream-A` | `docs:line 1075` | YES | YES | YES | YES | **PASS** |
| `CS-016` | CS | `CS-016` \| missing-param-error \| `webui` \| `422` \| `*` | `pending-stream-A` | `docs:line 1076` | YES | YES | YES | YES | **PASS** |
| `FR-001` | FR | `FR-001` \| BO-1.3 \| 3 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1089` | YES | YES | YES | YES | **PASS** |
| `FR-002` | FR | `FR-002` \| BO-1.6 \| 3 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1090` | YES | YES | YES | YES | **PASS** |
| `FR-003` | FR | `FR-003` \| BR-1.1 \| 22 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1091` | YES | YES | YES | YES | **PASS** |
| `FR-004` | FR | `FR-004` \| BR-1.3 \| 25 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1092` | YES | YES | YES | YES | **PASS** |
| `FR-005` | FR | `FR-005` \| CS-1.3 \| 4 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1093` | YES | YES | YES | YES | **PASS** |
| `FR-006` | FR | `FR-006` \| FR-1.1 \| 1 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1094` | YES | YES | YES | YES | **PASS** |
| `FR-007` | FR | `FR-007` \| FR-1.15 \| 8 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1095` | YES | YES | YES | YES | **PASS** |
| `FR-008` | FR | `FR-008` \| FR-1.16 \| 7 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1096` | YES | YES | YES | YES | **PASS** |
| `FR-009` | FR | `FR-009` \| FR-1.2 \| 3 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1097` | YES | YES | YES | YES | **PASS** |
| `FR-010` | FR | `FR-010` \| FR-1.26 \| 5 \| `mcp` \| `should` \| Functional capability covered b | `pending-stream-A` | `docs:line 1098` | YES | YES | YES | YES | **PASS** |
| `FR-011` | FR | `FR-011` \| FR-1.27 \| 25 \| `webui` \| `should` \| Functional capability covere | `pending-stream-A` | `docs:line 1099` | YES | YES | YES | YES | **PASS** |
| `FR-012` | FR | `FR-012` \| FR-1.6 \| 18 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1100` | YES | YES | YES | YES | **PASS** |
| `FR-013` | FR | `FR-013` \| NF-1.1 \| 2 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1101` | YES | YES | YES | YES | **PASS** |
| `FR-014` | FR | `FR-014` \| NF-1.2 \| 3 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1102` | YES | YES | YES | YES | **PASS** |
| `FR-015` | FR | `FR-015` \| NF-1.3 \| 4 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1103` | YES | YES | YES | YES | **PASS** |
| `FR-016` | FR | `FR-016` \| NF-1.5 \| 5 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1104` | YES | YES | YES | YES | **PASS** |
| `FR-017` | FR | `FR-017` \| R2 \| 8 \| `internal` \| `should` \| Functional capability covered b | `pending-stream-A` | `docs:line 1105` | YES | YES | YES | YES | **PASS** |
| `FR-018` | FR | `FR-018` \| R4 \| 7 \| `internal` \| `should` \| Functional capability covered b | `pending-stream-A` | `docs:line 1106` | YES | YES | YES | YES | **PASS** |
| `FR-019` | FR | `FR-019` \| SV-1.1 \| 3 \| `internal` \| `should` \| Functional capability cover | `pending-stream-A` | `docs:line 1107` | YES | YES | YES | YES | **PASS** |
| `FR-020` | FR | `FR-020` \| UC-1.3 \| 18 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1108` | YES | YES | YES | YES | **PASS** |
| `FR-021` | FR | `FR-021` \| UC-1.4 \| 18 \| `internal` \| `should` \| Functional capability cove | `pending-stream-A` | `docs:line 1109` | YES | YES | YES | YES | **PASS** |
| `FR-022` | FR | `FR-022` \| unit \| 38 \| `api,mcp` \| `should` \| Unit (W28C-1711-R3 ADD-REQ cl | `pending-stream-A` | `docs:line 1120` | YES | YES | YES | YES | **PASS** |
| `FR-023` | FR | `FR-023` \| application \| 34 \| `a2a,webui` \| `should` \| Application (W28C-17 | `pending-stream-A` | `docs:line 1121` | YES | YES | YES | YES | **PASS** |
| `FR-024` | FR | `FR-024` \| llm_test \| 1 \| `internal` \| `should` \| Llm Test (W28C-1711-R3 AD | `pending-stream-A` | `docs:line 1122` | YES | YES | YES | YES | **PASS** |
| `FR-025` | FR | `FR-025` \| system \| 19 \| `api` \| `should` \| System (W28C-1711-R3 ADD-REQ cl | `pending-stream-A` | `docs:line 1123` | YES | YES | YES | YES | **PASS** |
| `FR-026` | FR | `FR-026` \| integration \| 39 \| `a2a,api,mcp,webui` \| `should` \| Integration  | `pending-stream-A` | `docs:line 1124` | YES | YES | YES | YES | **PASS** |
| `NF-001` | NF | `NF-001` \| Service ships a valid `defaults.yaml` / configuration contract (no s | `pending-stream-A` | `docs:line 1138` | YES | YES | YES | YES | **PASS** |
| `NF-002` | NF | `NF-002` \| Service reuses approved platform packages with zero bespoke replacem | `pending-stream-A` | `docs:line 1139` | YES | YES | YES | YES | **PASS** |
| `NF-003` | NF | `NF-003` \| Service carries the required documentation + rules-conformance doc s | `pending-stream-A` | `docs:line 1140` | YES | YES | YES | YES | **PASS** |
| `NF-004` | NF | `NF-004` \| Test suite declares the canonical PS-REQ-TEST-TRACE marker taxonomy  | `pending-stream-A` | `docs:line 1141` | YES | YES | YES | YES | **PASS** |
| `UC-001` | UC | `UC-001` \| Operator \| Create + configure a channel with type-specific config ( | `pending-stream-A` | `docs:line 62` | YES | YES | YES | YES | **PASS** |
| `UC-002` | UC | `UC-002` \| Operator \| Run a live test against a configured channel \| REST/WEB | `pending-stream-A` | `docs:line 63` | YES | YES | YES | YES | **PASS** |
| `UC-003` | UC | `UC-003` \| Author \| Compose + send a broadcast notification to a group \| REST | `pending-stream-A` | `docs:line 64` | YES | YES | YES | YES | **PASS** |
| `UC-004` | UC | `UC-004` \| Author \| Send a personalised notification with per-recipient conten | `pending-stream-A` | `docs:line 65` | YES | YES | YES | YES | **PASS** |
| `UC-005` | UC | `UC-005` \| Author \| Issue a natural-language notification command \| REST/MCP/ | `pending-stream-A` | `docs:line 66` | YES | YES | YES | YES | **PASS** |
| `UC-006` | UC | `UC-006` \| Author/Viewer \| View a message and its delivery detail (request/out | `pending-stream-A` | `docs:line 67` | YES | YES | YES | YES | **PASS** |
| `UC-007` | UC | `UC-007` \| Author \| Retry or abort a failed/queued delivery; honour dead-lette | `pending-stream-A` | `docs:line 68` | YES | YES | YES | YES | **PASS** |
| `UC-008` | UC | `UC-008` \| Author/Viewer \| Browse deliveries with channel/date/destination/fre | `pending-stream-A` | `docs:line 69` | YES | YES | YES | YES | **PASS** |
| `UC-009` | UC | `UC-009` \| Operator \| Manage prompt templates: CRUD, multi-language, channel s | `pending-stream-A` | `docs:line 70` | YES | YES | YES | YES | **PASS** |
| `UC-010` | UC | `UC-010` \| Operator \| Create + manage users (display name, owner metadata, ena | `pending-stream-A` | `docs:line 71` | YES | YES | YES | YES | **PASS** |
| `UC-011` | UC | `UC-011` \| Operator \| Create + manage groups and user/group membership \| REST | `pending-stream-A` | `docs:line 72` | YES | YES | YES | YES | **PASS** |
| `UC-012` | UC | `UC-012` \| End User \| Self-service preferences: language (ISO 639-1), preferre | `pending-stream-A` | `docs:line 73` | YES | YES | YES | YES | **PASS** |
| `UC-013` | UC | `UC-013` \| Operator \| Set group/channel preference defaults consumed by the de | `pending-stream-A` | `docs:line 74` | YES | YES | YES | YES | **PASS** |
| `UC-014` | UC | `UC-014` \| Operator \| Assign RBAC roles + per-channel scope to users/groups \| | `pending-stream-A` | `docs:line 75` | YES | YES | YES | YES | **PASS** |
| `UC-015` | UC | `UC-015` \| System \| Resolve group->channel access cascade for a restricted use | `pending-stream-A` | `docs:line 76` | YES | YES | YES | YES | **PASS** |
| `UC-016` | UC | `UC-016` \| Operator \| Issue + revoke owner/group-scoped API keys \| REST/WEBUI | `pending-stream-A` | `docs:line 77` | YES | YES | YES | YES | **PASS** |
| `UC-017` | UC | `UC-017` \| Operator \| Monitor async jobs: status, result, error, schedule/run/ | `pending-stream-A` | `docs:line 78` | YES | YES | YES | YES | **PASS** |
| `UC-018` | UC | `UC-018` \| System \| Drain the delivery queue / run scheduled sends via the wor | `pending-stream-A` | `docs:line 79` | YES | YES | YES | YES | **PASS** |
| `UC-019` | UC | `UC-019` \| Operator \| View + apply runtime settings through the platform confi | `pending-stream-A` | `docs:line 80` | YES | YES | YES | YES | **PASS** |
| `UC-020` | UC | `UC-020` \| Viewer/Operator \| Read the tamper-resistant audit & log (channel/us | `pending-stream-A` | `docs:line 81` | YES | YES | YES | YES | **PASS** |
| `UC-021` | UC | `UC-021` \| Calling Agent \| Invoke an MCP tool (e.g. `send_notification`) with  | `pending-stream-A` | `docs:line 82` | YES | YES | YES | YES | **PASS** |
| `UC-022` | UC | `UC-022` \| Calling Agent \| Drive an A2A task / event stream and correlate task | `pending-stream-A` | `docs:line 83` | YES | YES | YES | YES | **PASS** |
| `UC-023` | UC | `UC-023` \| Author \| Generate multimedia / PDF / HTML output for a notification | `pending-stream-A` | `docs:line 84` | YES | YES | YES | YES | **PASS** |
| `UC-024` | UC | `UC-024` \| System \| Persist + reference an output artifact through the storage | `pending-stream-A` | `docs:line 85` | YES | YES | YES | YES | **PASS** |
| `UC-025` | UC | `UC-025` \| All authenticated \| Authenticate via WebUI flat login (admin / read | `pending-stream-A` | `docs:line 86` | YES | YES | YES | YES | **PASS** |
| `UC-026` | UC | `UC-026` \| System \| LLM-assisted formatting / translation of notification cont | `pending-stream-A` | `docs:line 87` | YES | YES | YES | YES | **PASS** |
| `UC-101` | UC | `UC-101` \| Intruder (`anon`) \| Read notification data on the API without auth  | `pending-stream-A` | `docs:line 95` | YES | YES | YES | YES | **PASS** |
| `UC-102` | UC | `UC-102` \| `read-only` \| POST/PUT/DELETE a write API route \| `403` \| `tests/ | `pending-stream-A` | `docs:line 96` | YES | YES | YES | YES | **PASS** |
| `UC-103` | UC | `UC-103` \| `read-only` \| Invoke a mutating MCP tool \| `403` \| `tests/integra | `pending-stream-A` | `docs:line 97` | YES | YES | YES | YES | **PASS** |
| `UC-104` | UC | `UC-104` \| `read-only` \| Submit a mutating A2A task \| `403` \| `tests/integra | `pending-stream-A` | `docs:line 98` | YES | YES | YES | YES | **PASS** |
| `UC-105` | UC | `UC-105` \| `read-only` \| Trigger a WebUI write action \| `403` \| `tests/unit/ | `pending-stream-A` | `docs:line 99` | YES | YES | YES | YES | **PASS** |
| `UC-106` | UC | `UC-106` \| Any \| Submit a request with a missing required parameter \| `422` \ | `pending-stream-A` | `docs:line 100` | YES | YES | YES | YES | **PASS** |
| `UC-107` | UC | `UC-107` \| `read-write` \| Perform an admin-privileged op (RBAC/user/API-key) \ | `pending-stream-A` | `docs:line 101` | YES | YES | YES | YES | **PASS** |
| `UC-108` | UC | `UC-108` \| Restricted `system`/user \| Read a channel not granted by any group  | `pending-stream-A` | `docs:line 102` | YES | YES | YES | YES | **PASS** |
| `UC-109` | UC | `UC-109` \| Intruder (`anon`) \| Reach an authenticated WebUI page \| `401`/redi | `pending-stream-A` | `docs:line 103` | YES | YES | YES | YES | **PASS** |
| `UC-110` | UC | `UC-110` \| Any \| Find a UI affordance to delete an audit/log entry \| none (ta | `pending-stream-A` | `docs:line 104` | YES | YES | YES | YES | **PASS** |

## Section B — Functional delivery coverage

| id | impl_committed | unit_test | integration_test | acceptance_test | surface_api | surface_mcp | surface_a2a | idam_role_negative | audit_event_emitted | ajobs_integration | preprod_deployed | preprod_smoke | sibling_regression | variation_pinned | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `FR-001` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-002` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-003` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-004` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-005` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-006` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-007` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-008` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-009` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-010` | YES | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-011` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-012` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-013` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-014` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-015` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-016` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-017` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-018` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-019` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | N/A | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-020` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-021` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-022` | YES | PASS | PASS | PASS | PASS | PASS | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-023` | YES | PASS | PASS | PASS | PASS | N/A | PASS | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-024` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-025` | YES | PASS | PASS | PASS | PASS | N/A | N/A | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |
| `FR-026` | YES | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | YES | PASS | PASS | openrouter:qwen3-14b+sqlite+vdb=none | **PASS** |


## Section C — WebUI + E2E coverage

| page | role | uc_id | playwright_spec | screenshot | axe_a11y | style_conformance | url_canonical | positive_assertion | negative_assertion | webui_observation_closed | preprod_url_smoke | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Login | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Login | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Login | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Login | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Top-Menu | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Top-Menu | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Top-Menu | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Top-Menu | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Left-Menu | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Left-Menu | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Left-Menu | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Left-Menu | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Footer | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Footer | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Footer | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Footer | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Audit-Log | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Audit-Log | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Audit-Log | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Audit-Log | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Users | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Users | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Users | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Users | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Groups | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Groups | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Groups | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Groups | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-API-Keys | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-API-Keys | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-API-Keys | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-API-Keys | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Roles | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Roles | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Roles | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-Roles | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-RBAC | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-RBAC | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-RBAC | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Admin-RBAC | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-API-Docs | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-API-Docs | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-API-Docs | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-API-Docs | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-MCP-Console | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-MCP-Console | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-MCP-Console | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-MCP-Console | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-A2A-Console | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-A2A-Console | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-A2A-Console | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| Developer-A2A-Console | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Jobs | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Jobs | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Jobs | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Jobs | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Settings | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Settings | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Settings | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-Settings | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-About | admin | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-About | read-write | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-About | read-only | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| System-About | anon | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-001` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-001` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-001` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-001` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-002` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-002` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-002` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-002` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-003` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-003` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-003` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-003` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-004` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-004` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-004` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-004` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-005` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-005` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-005` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-005` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-006` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-006` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-006` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-006` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-007` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-007` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-007` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-007` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-008` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-008` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-008` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-008` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-009` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-009` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-009` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-009` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-010` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-010` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-010` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-010` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-011` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-011` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-011` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-011` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-012` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-012` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-012` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-012` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-013` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-013` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-013` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-013` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-014` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-014` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-014` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-014` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-015` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-015` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-015` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-015` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-016` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-016` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-016` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-016` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-017` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-017` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-017` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-017` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-018` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-018` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-018` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-018` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-019` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-019` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-019` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-019` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-020` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-020` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-020` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-020` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-021` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-021` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-021` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-021` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-022` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-022` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-022` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-022` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-023` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-023` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-023` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-023` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-024` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-024` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-024` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-024` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-025` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-025` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-025` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-025` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-026` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-026` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-026` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-026` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-101` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-101` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-101` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-101` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-102` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-102` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-102` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-102` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-103` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-103` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-103` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-103` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-104` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-104` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-104` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-104` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-105` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-105` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-105` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-105` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-106` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-106` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-106` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-106` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-107` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-107` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-107` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-107` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-108` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-108` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-108` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-108` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-109` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-109` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-109` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-109` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | admin | `UC-110` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-write | `UC-110` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | read-only | `UC-110` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |
| (UC-row) | anon | `UC-110` | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | **PENDING** |

