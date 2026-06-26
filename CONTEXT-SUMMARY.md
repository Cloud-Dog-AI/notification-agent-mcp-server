# Context Summary

## Current State
- Active repo: `/opt/iac/Development/cloud-dog-ai/notification-agent-mcp-server`
- Related UI repo: `/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-ui-monorepo`
- Most recent completed instruction: `#90b / W28A-90b-FIX-NOTIFICATION-AGENT-PW-SESSION`
- Final status of `#90b`: complete, targeted replay green, full Playwright suite green
- Service repo state on `2026-05-07`: clean worktree

## #90b Outcome
- Failure replayed exactly against preprod from the monorepo app:
  - `tests/e2e/ui-review2.spec.ts:266`
  - failing case: `P11 Session timeout shows a live countdown once authenticated`
- Observed failure before fix:
  - login remained on `https://notificationagent0.cloud-dog.net/login`
  - page snapshot showed `Failed to fetch` on the sign-in form
- Root cause:
  - the Playwright `/runtime-config.js` override used `process.env.BASE_URL ?? 'http://localhost:8021'`
  - the replay command set `E2E_API_BASE_URL=https://notificationagent0.cloud-dog.net` but did not set `BASE_URL`
  - browser auth calls were therefore silently pointed at localhost instead of preprod
- Fix applied in related UI repo:
  - [apps/notification-agent/tests/e2e/ui-review2.spec.ts](/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-ui-monorepo/apps/notification-agent/tests/e2e/ui-review2.spec.ts)
  - runtime-config override now sources `API_BASE_URL` from `E2E_API_BASE_URL` first
  - `MCP_BASE_URL` and `A2A_BASE_URL` now derive from that same API base

## #90b Validation
- Reproduce log before/after path:
  - [apps/notification-agent/working/pw-90b-reproduce.log](/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-ui-monorepo/apps/notification-agent/working/pw-90b-reproduce.log)
- Full suite log:
  - [apps/notification-agent/working/pw-90b-full.log](/opt/iac/Development/cloud-dog-ai/cloud-dog-ai-ui-monorepo/apps/notification-agent/working/pw-90b-full.log)
- Targeted replay after fix:
  - `5 passed (26.4s)`
- Full app suite after fix:
  - `46 passed (2.0m)`

## Commits
- Service repo lesson update:
  - `172ef43 Document notification-agent Playwright runtime-config lesson`
- Related UI repo fix:
  - `e372891 Fix notification-agent session-timeout Playwright replay`

## Lessons Captured
- Project lessons were updated in:
  - [AGENT-LESSONS.md](/opt/iac/Development/cloud-dog-ai/notification-agent-mcp-server/AGENT-LESSONS.md)
- Relevant entry:
  - `PLAYWRIGHT RUNTIME-CONFIG OVERRIDES MUST USE E2E_API_BASE_URL, NOT PAGE BASE_URL`

## Repo State Notes
- This service repo is currently clean.
- The related UI monorepo is shared and not clean.
- Current unrelated monorepo changes still visible under `apps/notification-agent`:
  - `screenshots/W28A-A10-notification-about.png`
  - `screenshots/W28A-A10-notification-profile.png`
  - `screenshots/W28A-A10-notification-settings.png`
  - `screenshots/W28A-A14-notification-preprod-profile.png`
- Do not assume screenshot diffs in the monorepo belong to the `#90b` fix.

## Previous Major Closeout
- The prior major notification-agent closeout before `#90b` was `W28A-493`.
- That work covered the larger UI review-2 adoption and the `/api-docs` Traefik route correction.
- Historical evidence for that instruction remains valid, but `#90b` is now the latest completed instruction and should be read first.
