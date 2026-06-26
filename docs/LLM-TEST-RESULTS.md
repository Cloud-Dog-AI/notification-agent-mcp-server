---
template-id: T-LTR
template-version: 1.0
applies-to: docs/LLM-TEST-RESULTS.md
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

# W28A-925 Notification Agent LLM Test Results

## Status

**COMPLETE — 12/12 models, 12/12 smoke PASS, 12/12 AT subset PASS.**

## Test Environment

- Service: `notification-agent-mcp-server`
- Base env: `tests/env-AT-local-server`
- Model overlays: `working/w28a-925/envs/*.env`
- Secret resolution: `env-vault` sourced in-process
- AT subset: AT1.1 + AT1.4a + AT1.16 + AT1.17 + AT1.18 (12 tests, ~8-10 min per model)

## Bug Fixes Applied (Prerequisites)

| Fix | File | Change |
|-----|------|--------|
| File channel formatter | `src/core/delivery_worker.py:751-754` | `in ('smtp', 'file')` → `== 'smtp'` |
| Shared PDF executor (file_channel) | `src/core/adapters/file_channel_adapter.py:25-32` | Module-level `_pdf_executor` |
| Shared LLM executor | `src/core/llm/llm_manager.py:33-44` | Module-level `_llm_executor` |
| Shared PDF executor (delivery_worker) | `src/core/delivery_worker.py:33-42` | Module-level `_pdf_executor` |
| Web proxy timeout | `defaults.yaml:86` | `proxy_timeout_seconds: 480` |
| Config default | `defaults.yaml:197` | `token_estimate_chars_per_token: 4.0` |

## Phase 1: Ollama — 7/7 PASS

| Model | Endpoint | Smoke | AT Subset (12 tests) | Duration | Notes |
|-------|----------|-------|---------------------|----------|-------|
| qwen3:14b | llm1 | PASS (17s) | 12/12 PASS | 8:26 | Also ran full 240-test AT: 221/240 pass (3:39:47) |
| qwen3.5:9b | llm1 | PASS (42s) | 12/12 PASS | 9:10 | Required NUM_CTX=16384 (32768 caused OOM) |
| gemma4:e4b | llm1 | PASS (39s) | 12/12 PASS | 8:38 | |
| qwen3.5:27b | llm2 | PASS (24s) | 12/12 PASS | 7:58 | |
| ibm/granite4:tiny-h | llm2 | PASS (3s) | 12/12 PASS | 7:58 | Fastest smoke |
| ibm/granite4:small-h | llm2 | PASS (10s) | 12/12 PASS | 8:15 | |
| gemma4:26b | llm2 | PASS (15s) | 12/12 PASS | 8:08 | |

## Phase 2: OpenRouter — 5/5 PASS

| Model | Smoke | AT Subset (12 tests) | Duration | Notes |
|-------|-------|---------------------|----------|-------|
| qwen/qwen3.5-27b | PASS (6s) | 12/12 PASS | 8:15 | |
| qwen/qwen3.5-35b-a3b | PASS | 12/12 PASS | 8:26 | Thinking model. Required temp=0.3, top_k=40, NUM_CTX=16384, MAX_TOKENS=2400 |
| openai/gpt-5.4 | PASS (2s) | 12/12 PASS | 8:08 | |
| google/gemma-4-31b-it | PASS (1s) | 12/12 PASS | 8:15 | |
| anthropic/claude-sonnet-4.6 | PASS (1s) | 12/12 PASS | 8:27 | |

## Model-Specific Settings

Most models use the default overlay settings. Two required tuning:

| Setting | Default | qwen3.5:9b | qwen3.5-35b-a3b |
|---------|---------|------------|------------------|
| NUM_CTX | 32768 | **16384** | **16384** |
| TEMPERATURE | 0.4 | 0.4 | **0.3** |
| TOP_K | 0 | 0 | **40** |
| MAX_TOKENS | 1800 | 1800 | **2400** |

## Evidence Paths

- Platform report: `cloud-dog-ai-platform-standards/working/W28A-925-NOTIFICATION-AGENT-LLM-TESTS-REPORT.md`
- Ollama matrix log: `working/w28a-925-ollama-matrix.log`
- OpenRouter matrix log: `working/w28a-925-openrouter-matrix.log`
- Per-model AT subset logs: `working/w28a-925-{model}-subset.log`
- Model overlay envs: `working/w28a-925/envs/*.env`
- Full AT run (qwen3:14b): `working/w28a-925-qwen3-14b-at-run3.log`
