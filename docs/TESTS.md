---
template-id: T-TST
template-version: 1.1
applies-to: docs/TESTS.md
project: notification-agent-mcp-server
doc-last-updated: 2026-06-18T00:00:00Z
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: 90d
doc-conformance-stamp: 2026-06-17T00:00:00Z
authored-by: W28E-1807A Stream-A (probe rebind + UC bindings + WebUI-feedback TEST-DESIGN-TODO)
req-trace-version: 1.0
total-tests: 0
coverage-percent: 0
---

# Notification Agent MCP Server — TESTS.md

## Service Scope
Multi-channel notification orchestration for email, loopback, chat/webhook, and
file delivery with prompt management, delivery lifecycle control, queue/jobs,
storage APIs, audit logging, and an administrative WebUI.

## Evidence Model
- This document is a forensic catalogue of current test coverage as inspected on
  `2026-04-09`.
- Coverage labels below mean:
  - `COVERED`: direct backend evidence exists and the relevant UI flow is either
    Playwright-covered or not applicable.
  - `PARTIAL`: implementation evidence exists, but either backend depth or UI
    Playwright coverage is incomplete for the merged requirement.
  - `GAP`: the required behaviour is not fully surfaced today and/or no suitable
    UI test exists because the UI surface is missing.
  - `IMPLEMENTED`: W28A-999 verified the former follow-on gap was already
    implemented; the missing piece was matrix wording or test-depth alignment,
    not product capability.
  - `ACCEPTED-GAP`: W28A-999 confirmed the capability is still narrower than the
    merged requirement wording and recorded it in `docs/ACCEPTED-GAPS.md` with a
    revisit date.
- This document does not claim a release verdict. Re-run the referenced suites
  against the intended environment before shipping.

## Test Inventory
| Tier | Present | Notes |
|---|---|---|
| Quality | Yes | Repository contains the `quality` test tier. |
| Unit | Yes | Repository contains the `unit` test tier. |
| System | Yes | Repository contains the `system` test tier. |
| Integration | Yes | Repository contains the `integration` test tier. |
| Application | Yes | Repository contains the `application` test tier. |
| `database` | Yes | Repository contains the `database` test tier. |
| `Examples` | Yes | Repository contains the `Examples` test tier. |

## Standard Commands
```bash
python3 -m pytest tests/quality --env tests/env-QT -q
python3 -m pytest tests/unit --env tests/env-UT -q
python3 -m pytest tests/system --env tests/env-ST -q
python3 -m pytest tests/integration --env tests/env-IT -q
python3 -m pytest tests/application --env tests/env-AT -q
```

## Marker Gate Commands
Use these selectors for marker-safe gate runs. The fast non-LLM selectors
explicitly exclude LLM and live-provider delivery coverage, so they do not
trigger LLM dependency warm-up or live provider delivery checks.

| Gate | Command |
|---|---|
| Marker taxonomy collection | `.venv/bin/python -m pytest tests/quality/QT_MARKER_GATES --env tests/env-QT --env tests/env-marker-collection --collect-only -m "quality and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Fast QT non-LLM marker gate | `.venv/bin/python -m pytest tests/quality/QT_MARKER_GATES --env tests/env-QT --env tests/env-marker-collection -m "quality and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Fast UT non-LLM shard | `.venv/bin/python -m pytest tests/unit/UT_CircuitBreakerDefer --env tests/env-UT --env tests/env-marker-collection -m "unit and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| All fast UT non-LLM collection | `.venv/bin/python -m pytest tests/unit --env tests/env-UT --env tests/env-marker-collection --collect-only -m "unit and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Fast WebUI/API contract shard | `.venv/bin/python -m pytest tests/integration/IT1.4_WebUIEndpoints/test_webui_api_contracts.py --env tests/env-IT -m "integration and api and webui and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery and not worker" -q` |
| Fast WebUI/API contract collection | `.venv/bin/python -m pytest tests/integration/IT1.4_WebUIEndpoints/test_webui_api_contracts.py --env tests/env-IT --collect-only -m "integration and api and webui and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery and not worker" -q` |
| API non-LLM collection | `.venv/bin/python -m pytest tests/integration --env tests/env-IT --collect-only -m "integration and api and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| WebUI non-LLM collection | `.venv/bin/python -m pytest tests/integration tests/application --env tests/env-IT --collect-only -m "webui and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| MCP non-LLM collection | `.venv/bin/python -m pytest tests/unit tests/integration --env tests/env-IT --collect-only -m "mcp and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| DB non-LLM collection | `.venv/bin/python -m pytest tests/unit tests/integration --env tests/env-IT --collect-only -m "db and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Media non-LLM collection | `.venv/bin/python -m pytest tests/unit tests/application --env tests/env-AT --collect-only -m "media and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| W28A-109F focused media local-contract collection | `.venv/bin/python -m pytest tests/application/AT1.20_MediaSupport/cases_w28a_109f_media_local_contract.py tests/application/AT1.20_MediaSupport/cases_image_all_channels.py --env tests/env-AT --collect-only -m "application and media and non_llm and no_runtime_dependency and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| W28A-109F focused media local-contract gate | `.venv/bin/python -m pytest tests/application/AT1.20_MediaSupport/cases_w28a_109f_media_local_contract.py tests/application/AT1.20_MediaSupport/cases_image_all_channels.py --env tests/env-AT -m "application and media and non_llm and no_runtime_dependency and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| W28A-109F AT Slack/live-provider collection | `.venv/bin/python -m pytest tests/application/AT1.24_HTMLPageMultimedia tests/application/AT1.27_SlackSummaryLink --env tests/env-AT --collect-only -m "live_provider or live_delivery" -q` |
| W28A-109F IT Slack/live-provider collection | `.venv/bin/python -m pytest tests/integration/IT1.13_SlackRealIntegration tests/integration/IT1.14_SlackWebhook --env tests/env-IT --collect-only -m "live_provider or live_delivery" -q` |
| Worker non-LLM collection | `.venv/bin/python -m pytest tests/unit tests/integration --env tests/env-IT --env tests/env-marker-collection --collect-only -m "worker and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Forensic non-LLM collection | `.venv/bin/python -m pytest tests/quality tests/application --env tests/env-AT --collect-only -m "forensic and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| LLM/live-provider collection only | `.venv/bin/python -m pytest tests --env tests/env-AT --env tests/env-marker-collection --collect-only -m "llm or llm_real or generated_answer or live_provider or live_delivery" -q` |

Run slow or live gates only with the matching coordinator slot and environment:
LLM gates use `-m "llm or llm_real or generated_answer"`; live provider delivery
gates use `-m "live_provider or live_delivery"`. Do not combine those selectors
with the fast non-LLM gates above.

## W28A-109 Marker/Gate Traceability

The accepted W28A-109 split work changed the test catalogue from broad tier
runs into marker-addressable gates. This section is the traceability index for
those accepted splits; it does not replace the command tables above, but records
which evidence proves each gate boundary.

| Accepted work | Gate boundary | Traceability impact | Evidence anchor |
|---|---|---|---|
| `W28A-109A` marker taxonomy | `quality`, `unit`, `integration`, `application`, `non_llm`, `llm`, `llm_real`, `generated_answer`, `live_provider`, `live_delivery`, `api`, `webui`, `mcp`, `db`, `media`, `worker`, `forensic`, `fast`, `slow`, `heavy`, `no_llm_dependency`, `no_runtime_dependency`, and `dependency_services(...)` are declared markers. | Fast non-LLM selectors can be audited by marker expression instead of by filename convention. | `working/W28A-109A-NOTIFICATION-TEST-MARKERS-GATES-RESULT.md`; `tests/quality/QT_MARKER_GATES/test_marker_taxonomy.py`; `pytest.ini`. |
| `W28A-109B` dependency gate narrowing | LLM availability and warm-up are required only for selected LLM-capable tests; API remains the default local runtime dependency unless QT/no-runtime selections or explicit `dependency_services(...)` markers narrow it. | Non-LLM API/WebUI/MCP/db selections no longer inherit LLM provider checks before collection or runtime. | `working/W28A-109B-NOTIFICATION-CONFTEST-DEPENDENCY-GATES.md`; `tests/unit/UT1.20_RuntimeArchitectureContracts/test_conftest_dependency_gates.py`; `tests/conftest.py`. |
| `W28A-109X` consolidation of `W28A-109C`, `W28A-109D`, and `W28A-109E` | Fast WebUI/API contracts, worker/queue forensic checks, LLM/generated-answer inventory, and live-provider/live-delivery inventory have separate selectors. | WebUI/API contract gates exclude worker/forensic scenarios; worker forensic gates are opt-in; live/LLM inventory is collection-only unless a coordinator-approved slot is used. | `working/W28A-109X-NOTIFICATION-GATE-SPLIT-CONSOLIDATION-RESULT.md`; `working/W28A-109C-NOTIFICATION-WEBUI-API-CONTRACT-SPLIT-RESULT.md`; `tests/env-marker-collection`. |
| `W28A-109F` media and Slack scenario split | Local media rendering/contracts run as `media and non_llm and no_runtime_dependency`; Slack and external delivery checks are marked `live_provider`/`live_delivery`, with generated Slack summary flows also marked `llm`/`generated_answer`. | Local media coverage is safe for fast non-LLM gates, while HTML multimedia, Slack summary, and Slack IT provider coverage remain excluded from fast gates. | `working/W28A-109F-NOTIFICATION-MEDIA-SLACK-SCENARIO-SPLIT-RESULT.md`; `cases_w28a_109f_media_local_contract.py`; Slack summary application suite. |

Traceability rule: use the fast non-LLM selectors for routine docs, marker, and
contract validation. Use the `Live And LLM Gate Commands` section only for
collection proof, or for runtime execution after a coordinator-approved LLM or
live-provider slot is assigned.

## Live And LLM Gate Commands

The commands below are the approved selectors for collection-only proof and
slot-approved runtime shards. Collection-only commands do not execute tests or
make provider calls. Runtime commands require an explicit coordinator slot
before use.

| Gate | Command |
|---|---|
| All live/LLM collection proof | `.venv/bin/python -m pytest tests --env tests/env-AT --env tests/env-marker-collection --collect-only -m "llm or llm_real or generated_answer or live_provider or live_delivery" -q` |
| Non-LLM all-tier collection proof | `.venv/bin/python -m pytest tests --env tests/env-AT --env tests/env-marker-collection --collect-only -m "non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| LLM/generated-answer slot shard | `.venv/bin/python -m pytest tests --env tests/env-AT --env private/env-llm-slot -m "(llm or llm_real or generated_answer) and not live_provider and not live_delivery" -ra` |
| Focused W28A-109E LLM slot shard | `.venv/bin/python -m pytest tests/integration/IT1.15_LLMRealIntegration/test_llm_real_integration.py --env tests/env-AT --env private/env-llm-slot -m "llm_real and not live_provider and not live_delivery" -ra` |
| Live provider delivery slot shard | `.venv/bin/python -m pytest tests --env tests/env-AT --env private/env-live-provider-slot -m "(live_provider or live_delivery) and not llm and not llm_real and not generated_answer" -ra` |
| Combined LLM plus live-provider slot shard | `.venv/bin/python -m pytest tests --env tests/env-AT --env private/env-live-llm-slot -m "(llm or llm_real or generated_answer) and (live_provider or live_delivery)" -ra` |
| W28A-109F Slack/live-provider slot shard | `.venv/bin/python -m pytest tests/application/AT1.24_HTMLPageMultimedia tests/application/AT1.27_SlackSummaryLink --env tests/env-AT --env private/env-live-llm-slot -m "live_provider or live_delivery" -ra` |

## Worker And Queue Forensic Gates

Worker/queue forensic tests are isolated from the fast API/WebUI contract gates.
Use these selectors when investigating queue saturation, worker restart,
readiness, and defer/retry behaviour. Runtime gates may restart supported
services through test harnesses or `server_control.sh`; do not run them in the
default fast non-LLM API/WebUI shards.

| Gate | Command |
|---|---|
| Fast worker-readiness forensic shard | `.venv/bin/python -m pytest tests/unit/UT1.20_RuntimeArchitectureContracts/test_delivery_worker_startup_backlog.py tests/unit/UT_CircuitBreakerDefer --env tests/env-UT --env tests/env-marker-collection -m "unit and worker and forensic and non_llm and fast and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Queue saturation gate | `.venv/bin/python -m pytest tests/integration/IT1.25_AsyncMessageSubmission/test_async_message_submission.py::test_message_submission_rejects_when_delivery_queue_is_full --env tests/env-IT -m "integration and worker and forensic and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Worker restart gate | `.venv/bin/python -m pytest tests/integration/IT1.8_AsyncMessageDelivery/test_async_message_delivery.py::test_delivery_survives_server_restart --env tests/env-IT -m "integration and worker and forensic and llm and not live_provider and not live_delivery" -q` |
| MCP async job worker gate | `.venv/bin/python -m pytest tests/integration/IT1.23_MCP_AsyncJobs/test_mcp_async_jobs.py --env tests/env-IT -m "integration and mcp and worker and forensic and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Circuit-breaker defer worker gate | `.venv/bin/python -m pytest tests/integration/IT_CircuitBreakerDefer --env tests/env-IT-circuit-breaker-defer -m "integration and worker and forensic and non_llm and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Fast API contract exclusion proof | `.venv/bin/python -m pytest tests/integration --env tests/env-IT --collect-only -m "integration and api and non_llm and not worker and not forensic and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |
| Fast WebUI contract exclusion proof | `.venv/bin/python -m pytest tests/integration tests/application --env tests/env-IT --collect-only -m "webui and non_llm and not worker and not forensic and not llm and not llm_real and not generated_answer and not live_provider and not live_delivery" -q` |

No named db-lock recovery test exists in the current tree. The closest accepted
forensic coverage is worker restart/backlog recovery plus circuit-breaker
defer/retry. Add a dedicated `worker and forensic and db` command here if a
future db-lock test is introduced.

## W28A-957 AT Suite Consolidation
- Application test file count was reduced from `76` collected `test_*.py` files to `51`.
- Consolidation keeps the absorbed modules as `cases_*.py` files collected by
  suite-local `conftest.py` hooks, so pytest still executes each absorbed case
  as its own module with native fixture resolution.

| Legacy AT scope | Consolidated suite | Absorbed case modules |
|---|---|---|
| `AT1.20`, `AT1.22`, `AT1.28` | `tests/application/AT1.20_MediaSupport/` | `cases_media_support.py`, `cases_http_image_reference.py`, `cases_image_all_channels.py`, `cases_image_all_formats.py`, `cases_image_formats.py`, `cases_image_local_cache.py`, `cases_image_markdown_reference.py`, `cases_image_pdf_rendering.py`, `cases_image_text_handling.py`, `cases_local_file_image.py`, `cases_uri_reference_image.py`, `cases_uuencoded_image.py`, `cases_audio_video_media.py`, `cases_audio_video_rendering.py`, `cases_audio_video_support.py`, `cases_w28a_109f_media_local_contract.py` |
| `AT1.21`, `AT1.25`, `AT1.29` | `tests/application/AT1.21_FileChannel/` | `cases_file_channel.py`, `cases_storage_output_all_formats_languages.py`, `cases_storage_application.py` |
| `AT1.19`, `AT1.23` | `tests/application/AT1.19_PDFGeneration/` | `cases_at1_19_pdf_generation.py`, `cases_comprehensive_multimedia_validation.py`, `cases_multimedia_pdf.py` |
| `AT1.24`, `AT1.26` | `tests/application/AT1.24_HTMLPageMultimedia/` | `cases_html_page_multimedia.py`, `cases_uc1_7_end_to_end.py`, `cases_uc1_7_with_slack.py`, `cases_multichannel_all_formats.py` |

## Application Suite Traceability
The current TESTS catalogue already references the consolidated multimedia,
storage, prompt, channel, delivery, and WebUI suites. Additional application
directories that remain traceable to functional requirements are `AT1.1`,
`AT1.2`, `AT1.3`, `AT1.7`, `AT1.9`, `AT1.11`, `AT1.14`, `AT1.15`, `AT1.18`,
and `AT1.27`.

Primary requirement anchors include `SV1.1`, `SV1.2`, `SV1.3`, `BO1.1`,
`BO1.2`, `BO1.3`, `BR1.1`, `BR1.2`, `BR1.3`, `UC1.1`, `UC1.2`, `UC1.3`,
`UC1.4`, `UC1.5`, `UC1.6`, `UC1.7`, `UC1.8`, `UC1.9`, `FR1.1`, `FR1.2`,
`FR1.3`, `FR1.4`, `FR1.5`, `FR1.6`, `FR1.7`, `FR1.8`, `FR1.9`, `FR1.10`,
`FR1.11`, `FR1.12`, `FR1.13`, `FR1.14`, `FR1.15`, `FR1.16`, `FR1.17`,
`FR1.18`, `FR1.19`, `FR1.20`, `FR1.21`, `FR1.22`, `FR1.23`, `FR1.24`,
`FR1.25`, `FR1.26`, `FR1.27`, `FR1.28`, `FR1.29`, `FR1.30`, `FR1.31`,
`FR1.32`, `FR1.33`, `FR1.34`, `CS1.1`, `CS1.2`, `CS1.3`, `NF1.1`,
`NF1.2`, `NF1.3`, `NF1.4`, `NF1.5`, `NF1.6`, `NF1.7`, and `NF1.8`.

## Web UI Traceability
Web UI coverage is split between backend route coverage in this repository and
Playwright evidence in `cloud-dog-ai-ui-monorepo/apps/notification-agent`.
Channel CRUD, prompts, delivery status, queue/jobs, audit observability, and
runtime configuration map to the W28A-879 table below.

## W28A-201 Non-UI Traceability
Non-UI backend coverage includes prompt selection and template delivery
requirements `FR1.16`, `FR1.17`, multimedia and storage requirements
`FR1.24`, `FR1.25`, and prompt-platform requirements `FR-P001` and `FR-P002`.
The relevant evidence lives in Unit, System, Integration, and Application
suites, with package and static policy checks enforced in Quality.

## W28A-879 Requirement Coverage Map

| Req ID | Section | Requirement | Backend test evidence | Playwright evidence | Coverage |
|---|---|---|---|---|---|
| `W879-REQ-01` | a | Channel configuration CRUD, type-specific forms, live test and RBAC | `tests/application/AT1.5_FrenchSummary/test_at1_5_email_channel_crud.py`, `tests/integration/IT1.4_WebUIEndpoints/test_webui_endpoints.py`, `tests/integration/IT1.11_RBACIntegration/test_rbac_integration.py` | `apps/notification-agent/tests/e2e/channel-crud.spec.ts`, `apps/notification-agent/tests/e2e/ui-review2.spec.ts` | `PARTIAL` |
| `W879-REQ-02` | b | Message composition, sending and template integration | `tests/application/AT1.12_Broadcast/test_at1_12_broadcast.py`, `tests/application/AT1.13_Personalised/test_at1_13_personalised.py`, `tests/integration/IT1.19_MessageManagement/test_message_management.py`, `tests/application/AT1.16_ConfigurePrompts/test_at1_16_configure_prompts.py` | `apps/notification-agent/tests/e2e/template-management.spec.ts` | `PARTIAL` |
| `W879-REQ-03` | c | Delivery tracking, retry, abort and dead-letter lifecycle | `tests/integration/IT1.27_DeliveryResendAbort/test_delivery_resend_abort.py`, `tests/integration/IT1.9_DeliveriesComprehensive/test_deliveries_comprehensive.py`, `tests/unit/UT1.3_JobManager/test_job_manager.py` | `apps/notification-agent/tests/e2e/delivery-status.spec.ts`, `apps/notification-agent/tests/e2e/jobs-ps76.spec.ts` | `PARTIAL` |
| `W879-REQ-04` | d | Prompt templates CRUD, multi-language, channel-specific variants and variables | `tests/application/AT1.6_PromptManagement/test_at1_6a_default_prompts.py`, `tests/application/AT1.6_PromptManagement/test_at1_6b_group_prompts.py`, `tests/application/AT1.6_PromptManagement/test_at1_6c_language_prompts.py`, `tests/application/AT1.6_PromptManagement/test_at1_6d_keyword_prompts.py`, `tests/application/AT1.6_PromptManagement/test_at1_6e_priority_selection.py` | Static UI evidence in `cloud-dog-ai-ui-monorepo/apps/notification-agent/src/views/PromptsPage.tsx` (CRUD actions, `variables_json`, export); dedicated Playwright CRUD depth is still thinner than channels/users/jobs | `IMPLEMENTED` |
| `W879-REQ-05` | e | End-to-end delivery through real SMTP | `tests/application/AT1.5_FrenchSummary/test_at1_5_smtp_variants.py`, `tests/application/AT1.5_FrenchSummary/test_at1_5_uc1_1_broadcast.py`, `tests/application/AT1.5_FrenchSummary/test_french_summary_to_gary.py`, `tests/application/AT1.17_EmailValidation/test_at1_17_email_validation.py` | `N/A` backend E2E requirement | `COVERED` |
| `W879-REQ-06` | f | End-to-end delivery through loopback | `tests/application/AT1.4_Comprehensive/test_at1_4j_loopback_message_center.py`, `tests/application/AT1.4_Comprehensive/test_at1_4k_full_end_to_end.py`, `tests/application/AT1.19_PDFGeneration/cases_at1_19_pdf_generation.py` | `apps/notification-agent/tests/e2e/template-management.spec.ts`, `apps/notification-agent/tests/e2e/delivery-status.spec.ts` | `COVERED` |
| `W879-REQ-07` | g | End-to-end delivery through file channel | `tests/application/AT1.21_FileChannel/cases_file_channel.py`, `tests/application/AT1.4_Comprehensive/test_at1_4g_file_storage.py`, `tests/application/AT1.21_FileChannel/cases_storage_application.py`, `tests/integration/IT1.16_StorageIntegration/test_storage_integration.py` | Shared channel configuration UI supports `file` channels in `cloud-dog-ai-ui-monorepo/apps/notification-agent/src/views/ChannelsPage.tsx`; this requirement is satisfied by verified storage APIs rather than a dedicated file-only browser flow | `IMPLEMENTED` |
| `W879-REQ-08` | h | Storage and archival verification plus operator-facing browser workflow | `tests/application/AT1.4_Comprehensive/test_at1_4e_pdf_storage_url.py`, `tests/application/AT1.4_Comprehensive/test_at1_4g_file_storage.py`, `tests/application/AT1.21_FileChannel/cases_storage_application.py`, `tests/integration/IT1.16_StorageIntegration/test_storage_integration.py` | Accepted gap: no dedicated storage browser/file-management page exists today; see `docs/ACCEPTED-GAPS.md` (`W879-REQ-08`) | `ACCEPTED-GAP` |
| `W879-REQ-09` | i | Delivery worker and queue health | `tests/system/ST1.2_LLMQueueStatus/test_llm_queue_status.py`, `tests/integration/IT1.23_MCP_AsyncJobs/test_mcp_async_jobs.py`, `tests/integration/IT1.25_AsyncMessageSubmission/test_async_message_submission.py`, `tests/unit/UT1.3_JobManager/test_job_manager.py` | Jobs/monitoring UI proves queue visibility and lifecycle control, but explicit worker-heartbeat/worker-roster UI is deferred; see `docs/ACCEPTED-GAPS.md` (`W879-REQ-09`) | `ACCEPTED-GAP` |
| `W879-REQ-10` | j | Dashboard real-time operational metrics | `tests/integration/IT1.3_WebUIIntegration/test_web_ui_integration.py`, `tests/integration/IT1.6_WebUIRealIntegration/test_webui_real_integration.py`, `tests/application/AT_WEBUI_Forensic/test_webui_forensic.py` | `apps/notification-agent/tests/e2e/ui-review2.spec.ts` | `PARTIAL` |
| `W879-REQ-11` | k | Monitoring, delivery health and multi-surface logs | `tests/unit/UT1.12_LogFormatValidation/test_log_format_validation.py`, `tests/quality/QT_LoggingCompliance/test_logging_compliance.py`, `tests/application/AT_WEBUI_Forensic/test_webui_forensic.py` | `apps/notification-agent/tests/e2e/audit-observability.spec.ts`, `apps/notification-agent/tests/e2e/ui-review2.spec.ts` | `COVERED` |
| `W879-REQ-12` | l | Export and download capabilities | `tests/application/AT1.4_Comprehensive/test_at1_4e_pdf_storage_url.py`, `tests/application/AT1.4_Comprehensive/test_at1_4g_file_storage.py`, `tests/integration/IT1.19_MessageManagement/test_message_management.py` | Shared WebUI export flows exist across channels, prompts, jobs, users, groups, messages, deliveries, and API keys; stored artefact download remains intentionally documented as backend/API-only until a storage browser exists | `IMPLEMENTED` |
| `W879-REQ-13` | m | Full audit-trail verification | `tests/unit/UT1.12_LogFormatValidation/test_web_auth_audit_logging.py`, `tests/quality/QT_LoggingCompliance/test_logging_compliance.py`, `tests/application/AT_WEBUI_Forensic/test_webui_forensic.py` | `apps/notification-agent/tests/e2e/audit-observability.spec.ts`, `apps/notification-agent/tests/e2e/ui-review2.spec.ts` | `COVERED` |

## W28A-999 Executed Dispositions

| Req ID | Former state | Executed decision | Evidence anchor |
|---|---|---|---|
| `W879-REQ-04` | `PARTIAL` | `IMPLEMENTED` | `PromptsPage.tsx` exposes prompt CRUD, `variables_json`, and export; backend AT coverage was already strong. |
| `W879-REQ-07` | `PARTIAL` | `IMPLEMENTED` | The requirement is backend/storage-API oriented and is already covered by AT/IT evidence; `ChannelsPage.tsx` also exposes `file` channel configuration. |
| `W879-REQ-08` | `GAP` | `ACCEPTED-GAP` | Deferred until a dedicated storage browser/file-management page exists; tracked in `docs/ACCEPTED-GAPS.md`. |
| `W879-REQ-09` | `PARTIAL` | `ACCEPTED-GAP` | Jobs/monitoring surfaces provide queue visibility and lifecycle controls, but explicit worker heartbeat/roster UI is still deferred; tracked in `docs/ACCEPTED-GAPS.md`. |
| `W879-REQ-12` | `PARTIAL` | `IMPLEMENTED` | Current WebUI already exports the relevant operational lists and documents stored-artifact download as backend/API-only until a storage browser exists. |

## Notes
- App-level Playwright evidence for the notification UI lives in
  `cloud-dog-ai-ui-monorepo/apps/notification-agent/tests/e2e/`.
- Backend test references above were selected because they directly support the
  W28A-879 merged requirements; they are not an exhaustive list of all tests in
  the repository.
- Environment overlays and private credentials are intentionally not duplicated
  in this document set.

## 2. Coverage map

Mandatory 10-column schema per PS-REQ-TEST-TRACE v1.0 §4.2. As of W28E-1807A Stream-A the suite is semantically bound: every `@pytest.mark.req()` references a backtick FR/CS/NF/UC-NNN row, and **zero** structural `probe` markers remain (the 16 structural-conformance gates were rebound — see the W28E-1807A probe-rebind table below). The per-observation TEST-DESIGN catalogue for the open WebUI feedback items is in the "W28E-1807A Stream-A — WebUI-feedback TEST-DESIGN-TODO" section below and in REQUIREMENTS.md "W28E-1807A WebUI Feedback Trace".

| Test ID | Tier | Use case | Requirement | Surface | Scenario | Variants | Env files | Known issue | Last run commit |
|---|---|---|---|---|---|---|---|---|---|


<!-- W28C-1710b design-delta additions (2026-06-14T18:01:23Z) -->

## W28C-1710b design-delta — planned tests catalogue (T-TST v1.1 10-col schema)

Per T-TST v1.1, the planned tests catalogue carries 10 columns: `test-id | tier | use-case | requirement | surface | scenario | variants | env-files | known-issue | last-run-commit`. Test binding (replacement of probe markers with `@pytest.mark.req("FR-NNN")`) is W28C-1711 work.

Consolidation rules (per W28C-1711):

1. One primary test per FR-NNN; variants via `pytest.parametrize`.
2. Common scenarios (login, RBAC matrix, anon-denied) in `tests/helpers/`.
3. Cross-surface FR uses parametrized test file; not duplicate files.
4. Every `surface: webui` FR has a Playwright test (cookie-login + RBAC matrix + screenshot + DOM-assert + console-error-gate + CW-pattern).
5. Every `surface: api|mcp|a2a` FR has a protocol-level test.
6. Every `CS-NNN` binds to `@pytest.mark.negative` test with expected denial code.
7. CRUD-applicable entities have C/R/U/D coverage.
8. Orphan retirement requires knowledge-extract worksheet.


<!-- W28E-1807A Stream-A test-design (2026-06-17) -->

## W28E-1807A Stream-A — probe-marker rebind (zero residual probes)

Per template T-W28E-A D4 + exit-criterion 2, every residual `@pytest.mark.probe` left by the
W28C-1711 R3.5 cleanup is replaced with a semantic `@pytest.mark.req("FR/CS/NF-NNN")` binding that
matches actual test intent. 16 structural-conformance gates rebound; **zero** `@pytest.mark.probe`
markers remain under `tests/`. The canonical `NF-001`..`NF-004` rows (REQUIREMENTS.md) were authored
to host the standards-conformance gates.

| Test file | Tier | Surface | Bound REQ | Intent |
|---|---|---|---|---|
| `tests/quality/QT_STANDARDS/test_qt_no_hardcoded_secrets.py` | QT | internal | `CS-002` | no hardcoded secrets in src (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt26_secrets_separation.py` | QT | internal | `CS-002` | secrets separation (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt_vault_config_contract.py` | QT | internal | `CS-002` | vault config contract (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt1_security_suite.py` | QT | internal | `CS-002` | secrets never logged (was `@pytest.mark.probe`) |
| `tests/quality/QT_STANDARDS/test_qt_env_file_gitignore.py` | QT | internal | `CS-002` | env file gitignored (was `@pytest.mark.probe`) |
| `tests/quality/QT_LoggingCompliance/test_logging_compliance.py` | QT | internal | `CS-003` | logging/audit integrity (was `@pytest.mark.probe`) |
| `tests/quality/QT_STANDARDS/test_qt_defaults_yaml_exists.py` | QT | internal | `NF-001` | defaults.yaml/config contract (was `@pytest.mark.probe`) |
| `tests/quality/QT_PACKAGE_COMPLIANCE/test_package_compliance.py` | QT | internal | `NF-002` | no bespoke replacements (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt_package_adoption.py` | QT | internal | `NF-002` | platform package adoption (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt_platform_package_imports.py` | QT | internal | `NF-002` | platform package imports (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt27_bespoke_code_scan.py` | QT | internal | `NF-002` | bespoke code scan (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt_migration_completeness.py` | QT | internal | `NF-002` | runtime bridges exist (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt3_documentation_suite.py` | QT | internal | `NF-003` | required docs exist (was `@pytest.mark.probe`) |
| `tests/quality/QT_COMPLIANCE/test_qt_rules_compliance.py` | QT | internal | `NF-003` | rules/doc conformance (was `@pytest.mark.probe`) |
| `tests/quality/QT_MARKER_GATES/test_marker_taxonomy.py` | QT | internal | `NF-004` | pytest marker taxonomy (was `@pytest.mark.probe`) |
| `tests/smoke/test_cascade_resolves.py` | ST | internal | `CS-001` | group->channel RBAC cascade (was `@pytest.mark.probe`) |

## W28E-1807A Stream-A — UC trace bindings

36 use cases (`UC-001`..`UC-026` positive, `UC-101`..`UC-110` negative) authored in
[ROLES-AND-USECASES.md](ROLES-AND-USECASES.md) and bound to a representative covering test via
`@pytest.mark.req("UC-NNN")` anchors (PS-REQ-TEST-TRACE section 3.5). See ROLES-AND-USECASES.md
section 3/4 for the per-UC test column.

## W28E-1807A Stream-A — WebUI-feedback TEST-DESIGN-TODO (open observations -> Stream-B/C)

Per template D3, every OPEN GarysWorkingNotes WebUI observation (status STREAM-B/STREAM-C in the
REQUIREMENTS.md "W28E-1807A WebUI Feedback Trace") gets an explicit acceptance test-design row so
Stream-B/C have concrete drive-out targets. Observations already proven on `origin/main` by accepted
W28A-870-R2 (status CLOSED-870R2, 73 items) are covered by the existing live UAT suite and are NOT
re-authored here; cross-cutting items (X-1825, 6 items) are routed to W28E-1825. Open rows below: 65.

| Test design ID | Tier | Use case | Requirement | Surface | Scenario | GWN source | Env files | Disposition | Last run |
|---|---|---|---|---|---|---|---|---|---|
| `TD-1807-NA-C-15` | AT | — | `FR-008` | webui | Create form -> popup | GWN `NA-C-15` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-C-16` | AT | — | `FR-008` | api | config_json structured per-type form | GWN `NA-C-16` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-C-21` | AT | — | `FR-024` | api | Messages Sent column counter | GWN `NA-C-21` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-C-23` | AT | — | `FR-008` | api | Last Used column | GWN `NA-C-23` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-C-24` | AT | — | `FR-024` | api | Delete Selected bulk action | GWN `NA-C-24` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-D-11` | AT | — | `FR-011` | webui | remove action-button row | GWN `NA-D-11` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-D-12` | AT | — | `FR-011` | webui | remove Recent Messages panel | GWN `NA-D-12` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-D-13` | AT | — | `FR-011` | webui | remove Runtime Summary panel | GWN `NA-D-13` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-D-14` | AT | — | `FR-011` | webui | remove Inventory panel | GWN `NA-D-14` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-D-15` | AT | — | `FR-011` | webui | version self-probing footer | GWN `NA-D-15` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-M-09` | AT | — | `FR-024` | webui | Channel filter | GWN `NA-M-09` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-M-10` | AT | — | `FR-024` | api | Sender = sending user/api-key owner | GWN `NA-M-10` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-M-11` | AT | — | `FR-024` | api | Subject column population | GWN `NA-M-11` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-M-15` | AT | — | `FR-024` | webui | detail input/output/delivery links | GWN `NA-M-15` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-DV-04` | AT | — | `FR-011` | webui | filter channel/date/destination/free-text | GWN `NA-DV-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-P-10` | AT | — | `FR-007` | webui | remove banner | GWN `NA-P-10` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-P-11` | AT | — | `FR-007` | webui | Group ID picklist | GWN `NA-P-11` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-P-12` | AT | — | `FR-009` | webui | Language ISO disambiguation | GWN `NA-P-12` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AL-05` | AT | UC-020 | `CS-003` | webui | relative-time render | GWN `NA-AL-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AL-06` | AT | UC-020 | `CS-003` | webui | remove metric tiles | GWN `NA-AL-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AL-07` | AT | UC-020 | `CS-003` | webui | remove blurb | GWN `NA-AL-07` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AL-08` | AT | UC-020 | `CS-003` | api | audit row channel column | GWN `NA-AL-08` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-AL-09` | AT | UC-020 | `CS-003` | webui | remove Delivery Tracking sub-panel | GWN `NA-AL-09` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AL-10` | AT | UC-020 | `CS-003` | webui | NO audit-delete affordance (UC-110) | GWN `NA-AL-10` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-U-04` | AT | — | `FR-014` | webui | Create User popup | GWN `NA-U-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-U-06` | AT | — | `FR-016` | api | preferred_channel picklist | GWN `NA-U-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-U-07` | AT | — | `FR-014` | api | Display Name defaults username | GWN `NA-U-07` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-U-08` | AT | — | `FR-014` | webui | group membership multi-select | GWN `NA-U-08` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-U-09` | AT | — | `FR-014` | webui | Groups column | GWN `NA-U-09` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-U-10` | AT | — | `FR-014` | webui | row-action labels | GWN `NA-U-10` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-G-05` | AT | — | `FR-014` | webui | Create Group popup | GWN `NA-G-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-G-06` | AT | — | `FR-014` | webui | RBAC+API Keys links | GWN `NA-G-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-G-07` | AT | — | `FR-014` | webui | View Logs link | GWN `NA-G-07` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-G-08` | AT | — | `FR-014` | webui | row-action labels | GWN `NA-G-08` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AK-01` | AT | — | `CS-002` | api | Created/Expires columns | GWN `NA-AK-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-AK-02` | AT | — | `CS-002` | webui | enable/disable badge | GWN `NA-AK-02` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AK-03` | AT | — | `CS-002` | api | Last Used column | GWN `NA-AK-03` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-AK-04` | AT | — | `CS-002` | webui | remove banner | GWN `NA-AK-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AK-05` | AT | — | `CS-002` | api | Owner picklist + group-owned key | GWN `NA-AK-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-RB-01` | AT | — | `CS-002` | api | CRUD surface | GWN `NA-RB-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-RB-02` | AT | — | `CS-004` | api | per-role channel/function assign | GWN `NA-RB-02` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-RB-04` | AT | — | `CS-002` | webui | Playwright coverage | GWN `NA-RB-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AD-01` | AT | — | `FR-010` | webui | page tested | GWN `NA-AD-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AD-02` | AT | — | `FR-010` | webui | Swagger/Redoc render | GWN `NA-AD-02` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AD-03` | AT | — | `FR-010` | webui | MCP tool guides | GWN `NA-AD-03` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AD-04` | AT | — | `FR-P002` | webui | A2A guides | GWN `NA-AD-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-AD-05` | AT | — | `FR-010` | webui | docs tab decision | GWN `NA-AD-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-MC-01` | AT | — | `FR-010` | webui | MCP console layout/spec | GWN `NA-MC-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-A2-01` | AT | — | `FR-P002` | webui | A2A console layout/spec | GWN `NA-A2-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-J-01` | AT | — | `FR-022` | webui | page layout | GWN `NA-J-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-J-02` | AT | — | `FR-026` | api | job context capture | GWN `NA-J-02` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-J-03` | AT | — | `FR-026` | api | human-readable Result | GWN `NA-J-03` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-J-04` | AT | — | `FR-026` | api | Error capture | GWN `NA-J-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-J-05` | AT | — | `FR-026` | api | scheduled/run/duration | GWN `NA-J-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-J-06` | AT | — | `FR-026` | webui | link to Audit&Log | GWN `NA-J-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-J-07` | AT | — | `FR-024` | webui | link to Message | GWN `NA-J-07` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-S-01` | AT | — | `FR-016` | webui | structured layout (JsonExplorer) | GWN `NA-S-01` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-S-02` | AT | — | `CS-002` | api | Health must not dump DB | GWN `NA-S-02` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-S-04` | AT | — | `FR-016` | webui | About version | GWN `NA-S-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-S-05` | AT | — | `FR-014` | api | Profile Groups/Last login | GWN `NA-S-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-X-06` | AT | — | `FR-024` | api | public message permalink | GWN `NA-X-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-X-07` | AT | — | `FR-018` | api | message archive navigator | GWN `NA-X-07` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-PR-04` | AT | — | `FR-016` | api | preference->LLM propagation tests | GWN `NA-PR-04` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
| `TD-1807-NA-PR-05` | AT | — | `FR-016` | webui | active-preference indicator | GWN `NA-PR-05` | env-AT* | TEST-DESIGN-TODO -> W28E-1807C | (design) |
| `TD-1807-NA-PR-06` | AT | — | `FR-016` | api | REQ<->preference test-evidence matrix | GWN `NA-PR-06` | env-AT* | TEST-DESIGN-TODO -> W28E-1807B | (design) |
