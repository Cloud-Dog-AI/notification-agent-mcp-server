---
template-id: T-DEP
template-version: 1.0
applies-to: docs/DEPLOY.md
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

# Deployment Guide

## Option 1: Docker (recommended)

### Without Vault
```bash
cat > .env <<EOF
CLOUD_DOG__WEB_SERVER__PORT=8080
CLOUD_DOG__MCP_SERVER__PORT=8081
CLOUD_DOG__A2A_SERVER__PORT=8082
CLOUD_DOG__API_SERVER__PORT=8083
CLOUD_DOG__WEB_SERVER__USERNAME=admin
CLOUD_DOG__WEB_SERVER__PASSWORD=your-secure-password
CLOUD_DOG__API_SERVER__API_KEY=your-api-key
EOF

docker build -t notification-agent:latest .
docker run -d --name notification-agent \
  --env-file .env \
  -p 8080:8080 -p 8081:8081 -p 8082:8082 -p 8083:8083 \
  notification-agent:latest
```

### With Vault
```bash
cat > .env <<EOF
VAULT_ADDR=https://your-vault-server
VAULT_TOKEN=your-vault-token
VAULT_MOUNT_POINT=secret
VAULT_CONFIG_PATH=services/your-service
CLOUD_DOG__WEB_SERVER__PORT=8080
CLOUD_DOG__MCP_SERVER__PORT=8081
CLOUD_DOG__A2A_SERVER__PORT=8082
CLOUD_DOG__API_SERVER__PORT=8083
EOF

docker run -d --name notification-agent \
  --env-file .env \
  -p 8080:8080 -p 8081:8081 -p 8082:8082 -p 8083:8083 \
  notification-agent:latest
```

### With Custom CA Certificates
```bash
docker run -d --name notification-agent \
  --env-file .env \
  -v /path/to/ca-bundle.pem:/app/certs/ca-bundle.pem \
  -e REQUESTS_CA_BUNDLE=/app/certs/ca-bundle.pem \
  -e SSL_CERT_FILE=/app/certs/ca-bundle.pem \
  notification-agent:latest
```

## Option 2: Direct (no Docker)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
./server_control.sh --env env.example start all
```

## Example Environment File
- See `docs/ENV-REFERENCE.md` for the full variable catalogue.
- Use only generic examples in shared documentation; inject secrets at runtime.

## Health Checks
```bash
curl -f http://127.0.0.1:8083/health
curl -f http://127.0.0.1:8081/health
```

## Deployment Notes
- Service focus: Multi-channel notification orchestration for email, chat, webhook, file, and LLM-assisted message formatting with delivery state tracking.
- Primary capabilities: message submission, delivery tracking, prompt-driven formatting, user/group targeting, admin channel configuration.
- Review the published environment reference before deploying to a shared environment.
