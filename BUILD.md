---
template-id: T-BLR
template-version: 1.0
applies-to: BUILD.md
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

# Build Instructions

## Project
`notification-agent-mcp-server` - multi-channel notification delivery service.

## Prerequisites
- Python 3.11+
- Docker
- pip

## Development Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

Install from a single public index (the `cloud-dog-*` platform packages must be
available there — see EXTERNAL-BUILD.md):
```bash
pip install -e ".[dev]" --index-url https://pypi.org/simple
```

## Local Configuration
```bash
cat > .env.local <<'ENV'
CLOUD_DOG__NOTIFY__API_SERVER__PORT=8004
CLOUD_DOG__NOTIFY__WEB_SERVER__PORT=8005
CLOUD_DOG__NOTIFY__MCP_SERVER__PORT=8006
CLOUD_DOG__NOTIFY__A2A_SERVER__PORT=8007
CLOUD_DOG__NOTIFY__DB__URI=sqlite:///./data/notification.db
SMTP_HOST=mail.example.com
SMTP_PORT=587
ENV
```

## Run Locally
```bash
./server_control.sh --env ./.env.local start-all
./server_control.sh --env ./.env.local status-all
./server_control.sh --env ./.env.local stop-all
```

## Run Tests
```bash
python -m pytest tests/quality --env ./.env.test -v
python -m pytest tests/unit --env ./.env.test -v
python -m pytest tests/system --env ./.env.test -v
python -m pytest tests/integration --env ./.env.test -v
python -m pytest tests/application --env ./.env.test -v
```

## Build
### Python Package
```bash
python -m pip install build
python -m build
```

### Docker Container
```bash
# Public boundary (default index https://pypi.org/simple):
./docker-build.sh --variant public latest
```

Build with explicit (public) package index, proxy, and CA inputs:
```bash
PYPI_URL=https://pypi.org/simple \
PYPI_USERNAME=build-user \
PYPI_PASSWORD=build-password \
HTTP_PROXY=http://proxy.example.com:3128 \
HTTPS_PROXY=http://proxy.example.com:3128 \
CUSTOM_CA_CERT=./certs/ca.pem \
./docker-build.sh --variant public latest
```

## Docker Push
```bash
docker tag cloud-dog/notification-agent-mcp-server:latest registry.example.com/team/notification-agent-mcp-server:latest
docker push registry.example.com/team/notification-agent-mcp-server:latest
```

## Configuration
Runtime configuration is resolved from environment variables, the env file passed to `server_control.sh`, and `defaults.yaml`.

## Local Secrets
Put local-only values in the env file passed to `server_control.sh` or mounted into Docker. Do not commit real credentials.

## Publication test tag isolation (W28A-831)

`docker-build.sh` honours `PUBLICATION_TAG_SUFFIX` for building isolated
publication **test** images that never collide with reserved runtime/release tags
(default unset ⇒ behaviour unchanged):

```bash
PUBLICATION_TAG_SUFFIX=gitea-test ./docker-build.sh <version>
# builds <image>:<version>-gitea-test; registry tag is skipped
```

- Preview only: `PUBLICATION_DRY_RUN=1 PUBLICATION_TAG_SUFFIX=gitea-test ./docker-build.sh <version>`
