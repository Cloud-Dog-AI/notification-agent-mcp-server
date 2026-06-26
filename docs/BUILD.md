---
template-id: T-BLD
template-version: 1.0
applies-to: docs/BUILD.md
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

# Build Guide

## Prerequisites
- Python 3.11+
- `pip`, `venv`
- Docker (for container image builds)
- Vault env file: `.env.local`

## Source Checkout
```bash
cd ./notification-agent-mcp-server
```

## Virtual Environment
```bash
python3 -m venv .venv
source ..venv/bin/activate
pip install --upgrade pip setuptools wheel
```

## Dependency Install

### Standard install
```bash
pip install -r requirements.txt
```

### Editable install (PEP 621)
```bash
pip install -e ".[dev]"
```

### Private PyPI (if required)
```bash
# Example only: use your internal index URL/credentials
export PIP_INDEX_URL=<PRIVATE_PYPI_URL>
export PIP_EXTRA_INDEX_URL=<PUBLIC_FALLBACK_URL>
pip install -e ".[dev]"
```

## Build Package
```bash
python -m build
```

## Build Docker Image
```bash
# Required project script
set -a; source .env.local
bash docker-build.sh latest
```

## Local Runtime Bring-up (single all-in-one container)
```bash
set -a; source .env.local
bash local-docker-server.sh --env tests/env-local-docker-server restart
curl -sf http://127.0.0.1:8020/health
curl -sf http://127.0.0.1:8020/mcp/health
```

## Lint / Type Check
```bash
# Ruff lint
python -m ruff check src

# Optional formatting check
python -m ruff format --check src

# Type check (if mypy configured)
python -m mypy src
```

## Test Execution by Tier

Always source Vault first:
```bash
set -a; source .env.local
```

```bash
# QT
pytest tests/quality --env tests/env-QT -q

# UT
pytest tests/unit --env tests/env-UT -q

# ST
pytest tests/system --env tests/env-ST-local-docker -q

# IT
pytest tests/integration --env tests/env-IT-runtime-external-8020 -q

# AT
pytest tests/application --env tests/env-AT-local-docker-vault-8020 -q
```

## Notes
- Use `server_control.sh` for local non-docker server process control.
- Use `local-docker-server.sh --env tests/env-local-docker-server ...` for single-container all-servers runtime.
- Do not hardcode secrets; use Vault-backed env overlays.

## Publication Build Reference

### Dockerfile Location

- Dockerfile: `Dockerfile`
- Build script: `docker-build.sh`
- Primary compose/runtime file: `docker-compose.yml`

### Registry Push

```bash
cd ./notification-agent-mcp-server
set -a; source .env.local
bash docker-build.sh latest
docker push registry.example.com/cloud-dog/notification-agent-mcp-server:latest
```

### Standard Build Arguments and Prerequisites

- `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` when required by the host environment
- Cloud-Dog CA bundle if private trust material is needed
- Vault-backed credentials for private package indexes and registry access
- BuildKit-enabled Docker where the project build script expects it
