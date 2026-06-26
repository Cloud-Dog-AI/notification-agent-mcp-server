---
template-id: T-RME
template-version: 1.0
applies-to: README.md
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
doc-age-policy: indefinite
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# Notification Agent MCP Server

`notification-agent-mcp-server` exposes notification API, Web UI, MCP, and A2A-compatible surfaces for multi-channel delivery workflows.

## Publication Quick Start

Prerequisites:

- Docker 24 or newer with BuildKit enabled
- Python 3.12 or newer if you run the package locally
- Public package source: `https://pypi.org/simple` (the `cloud-dog-*` platform
  packages must be available on that index; see [EXTERNAL-BUILD.md](EXTERNAL-BUILD.md))

Build the public image (single public index, default `https://pypi.org/simple`):

```bash
./docker-build.sh --variant public latest
```

See [EXTERNAL-BUILD.md](EXTERNAL-BUILD.md) for the full external-builder workflow
(Linux/macOS/Windows, Docker and pure-source paths, and evidence return).

Run the local smoke by executing the shell block in [PUBLICATION-SMOKE.md](PUBLICATION-SMOKE.md) with `TAG=latest-gitea-test`.

The smoke run uses [env.example](env.example) and probes:

- API: `8083`
- Web: `8080`
- MCP: `8081`
- A2A: `8082`

## Local Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip setuptools wheel
# Single public index only (one index-url, nothing extra):
pip install -e ".[dev]" --index-url https://pypi.org/simple
```

Runtime configuration is loaded from the env file passed to `server_control.sh`, then from shell environment variables, then from `defaults.yaml`.

## Documentation

- [BUILD.md](BUILD.md)
- [PUBLICATION-SMOKE.md](PUBLICATION-SMOKE.md)
- [env.example](env.example)

## Licence

Apache-2.0 - Copyright (c) 2026 Cloud-Dog, Viewdeck Engineering Limited

## Security & Publication Notes

Authentication and authorisation use the platform IDAM credential/cert model; do not commit secrets.
This public source mirror excludes internal operations material; build artefacts (e.g. the UI bundle) are regenerated at build time.
