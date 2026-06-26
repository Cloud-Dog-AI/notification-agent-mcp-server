---
template-id: T-DOK
template-version: 1.0
applies-to: docs/DOCKER.md
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

# Docker Guide

## Build
```bash
docker build -t notification-agent:latest .
```

## Run
```bash
docker run --rm -it --env-file .env -p 8080:8080 -p 8081:8081 -p 8082:8082 -p 8083:8083 notification-agent:latest
```

## Push
```bash
docker tag notification-agent:latest registry.example.com/your-team/notification-agent:latest
docker push registry.example.com/your-team/notification-agent:latest
```

## Compose Files
- `docker-compose.local-docker.yml`
- `docker-compose.yml`

## Notes
- Keep secrets out of committed compose files and environment examples.
- Use `docs/DEPLOY.md` for Vault-backed runs and custom CA certificate instructions.
