---
template-id: T-CHG
template-version: 1.0
applies-to: docs/CHANGELOG.md
project: notification-agent-mcp-server
doc-last-updated: 2026-06-18T00:00:00Z
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: indefinite
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# notification-agent-mcp-server — Changelog

_Created by W28C-1710a recovery to receive carry-forward content from `archive/2026-06-12/`._



<!-- W28C-1710a recovery: full content from archive/2026-06-12/ACCEPTED-GAPS.md (archived sha256=9be96141cd5f, 19 lines) -->

## Recovered domain content — `archive/2026-06-12/ACCEPTED-GAPS.md` (19 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/ACCEPTED-GAPS.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# Accepted Gaps

This document records requirement gaps that remain intentionally narrower than
their current wording. Each accepted gap includes the current state, rationale,
revisit date, and sign-off.

## W28A-999 Accepted Gaps

| Requirement | Current state | Rationale | Revisit date | Sign-off |
|---|---|---|---|---|
| `W879-REQ-08` | Backend storage/file APIs and AT/IT coverage exist, but the notification WebUI still has no dedicated storage browser or file-management page. | Keep the gap explicit rather than over-claiming browser capability. The requirement is still useful, but it depends on a dedicated operator-facing storage surface that does not exist in the current product. | 2026-07-21 | W28A-999 forensic triage on 2026-04-22 |
| `W879-REQ-09` | `JobsPage` and monitoring views expose queue depth, lifecycle actions, and forensic detail, but they do not expose an explicit worker heartbeat or worker roster. | Keep the requirement active but accept the narrower current scope. Existing jobs/queue tooling is operationally useful; the missing worker-status surface is a product-level UI enhancement, not a hidden backend defect. | 2026-07-21 | W28A-999 forensic triage on 2026-04-22 |

## ACCEPTED-GAP: stdio MCP transport - server-side bespoke

- Date: 2026-04-22
- Reason: `src/servers/mcp/mcp_server.py` stdio surface is not covered by `cloud_dog_api_kit==0.8.3`. Platform migration in W28A-927p is limited to the HTTP MCP surface; stdio remains the accepted F-10 gap.
- Closes-on: platform stdio transport extension landing.
- Revisit trigger: `register_mcp_routes` or peer platform surface gains explicit stdio hosting support.


<!-- W28C-1710a recovery: full content from archive/2026-06-12/TASKS.md (archived sha256=dd7c943362f7, 16 lines) -->

## Recovered domain content — `archive/2026-06-12/TASKS.md` (16 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/TASKS.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# Tasks

## Current Delivery Tracks
| Workstream | Status | Notes |
|------------|--------|-------|
| Runtime surfaces | Complete | Source files detected: `src/servers/a2a/a2a_server.py`, `src/servers/api/api_server.py`, `src/servers/api/routes/__init__.py`, `src/servers/api/routes/callbacks.py`, `src/servers/api/routes/groups.py`, `src/servers/api/routes/users.py`, `src/servers/mcp/mcp_server.py`, `src/servers/web/web_server.py`. |
| API documentation | Complete | `docs/API_DOCUMENTATION.md` reviewed against source inventory. |
| MCP documentation | Complete | `docs/MCP_DOCUMENTATION.md` reviewed against source inventory. |
| Configuration reference | Complete | `docs/PARAMETERS.md` and `docs/ENV-REFERENCE.md` regenerated from `defaults.yaml`. |
| Deployment guidance | Complete | `docs/DEPLOY.md` and `docs/DOCKER.md` refreshed with shareable examples. |
| Test catalogue | Complete | `docs/TESTS.md` refreshed from the current repository inventory. |

## Next Review Cycle
1. Re-run the release-relevant test tiers in the intended deployment environment.
2. Update API and MCP inventories whenever routes or tool contracts change.
3. Keep any non-standard topical docs aligned with the canonical set listed in this repository.
