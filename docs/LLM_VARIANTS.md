---
template-id: T-LLV
template-version: 1.0
applies-to: docs/LLM-VARIANTS.md
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

# LLM Variants: Settings and Test Success

## Purpose
- Provide a concise, RULES-aligned view of LLM variants and validated test coverage.
- Avoid sensitive values (endpoints, credentials, emails). Concrete settings live in `private/env-*`.

## Rules-Aligned Configuration
- Configuration hierarchy is enforced: `os.environ` → `--env` file → `config.yaml` → `default.yaml`.
- Tests require `--env private/env-<name>` and real adapters (no mocks in AT/IT/ST).
- No hardcoded values are used in tests; environment files carry credentials and endpoints.

---

## Variant A: MariaDB + Ollama Granite4
- **Provider**: `ollama`
- **Model**: `ibm/granite4:tiny-h`
- **Scenario envs**: `private/env-test-mariadb-granite4`, per-suite `private/env-test-mariadb-granite4-at112` … `-at126`
- **Settings summary**:
  - LLM tuning and timeouts are configured via env files (temperature/top_p/top_k/repeat_penalty/seed/timeouts).
  - Context and token limits are aligned to the model’s supported window.
  - Database backend is MariaDB via env configuration.
- **Recorded coverage (see `docs/TESTS.md`)**:
  - **ST**: ST1.18, ST1.19 PASS
  - **IT**: IT1.1, IT1.19 PASS
  - **AT**: AT1.12–AT1.26 per-suite rerun PASS

---

## Variant B: MariaDB + OpenRouter Qwen3 (OpenAI-compatible)
- **Provider**: `openai` (OpenRouter)
- **Model**: `qwen/qwen3-14b`
- **Scenario envs**: `private/env-test-mariadb-openrouter`, per-suite `private/env-test-mariadb-openrouter-at112` … `-at126`
- **Settings summary**:
  - Uses the same LLM tuning keys as the Ollama variants (timeouts tuned for long LLM operations).
  - Provider-specific settings are contained in env files (no secrets in code/docs).
  - MariaDB backend via env configuration.
- **Recorded coverage (see `docs/TESTS.md`)**:
  - **ST**: ST1.18, ST1.19 PASS
  - **IT**: IT1.1, IT1.19 PASS
  - **AT**: AT1.4A–AT1.4K PASS (OpenRouter), AT1.12–AT1.26 per-suite PASS
  - **Notes**: AT1.21/AT1.24 max-wait values adjusted for OpenRouter latency.

---

## Variant C: Baseline Ollama Qwen3
- **Provider**: `ollama`
- **Model**: `qwen3:14b`
- **Scenario envs**: `private/env-test`, per-suite `private/env-test-at*` (baseline suites)
- **Settings summary**:
  - LLM tuning keys mirror the other variants for consistency.
  - Provider and DB settings are configured via env files (baseline uses SQLite by default).
- **Recorded coverage (see `docs/TESTS.md`)**:
  - **ST**: baseline ST suite PASS (with documented skips)
  - **IT**: IT1.1, IT1.19 PASS (baseline env)
  - **AT**: Baseline AT1.4A–AT1.4K, AT1.22, AT1.23, AT1.26 PASS

---

## Consistency Review (Variants)
- **Configuration keys are consistent** across variants (LLM tuning + timeouts + context settings).
- **Differences are intentional and isolated** to provider/model and DB backend selection.
- **Test structure is consistent**: AT/IT/ST tests are API-driven and env-configured.

## Confidence Summary
- All three variants are validated with real adapters and configuration-driven tests.
- MariaDB variants have per-suite AT1.12–AT1.26 coverage recorded.
- Legacy noncompliant modules are removed; the suite now collects API-driven tests only.

