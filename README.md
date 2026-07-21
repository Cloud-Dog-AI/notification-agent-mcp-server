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
- Python 3.13 or newer if you run the package locally (project runtime contract, W28R-3017/NF-005)
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
python3.13 -m venv .venv
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
- [docs/PARAMETERS.md](docs/PARAMETERS.md) — full configuration reference (per-section `Key | Default | Environment Override | Description` tables)

## Configuration & Environment Variable Matrix (W28E-1874 NA-AD-06)

Every setting is loaded through `cloud_dog_config` with precedence
`os.environ → env-file(s) → config.yaml → defaults.yaml`. Each `<section>.<key>` config path has a
deterministic environment override `CLOUD_DOG__<SECTION>__<KEY>` (dots → `__`, upper-cased). The full
per-section matrix (all keys, defaults, overrides, descriptions) is generated in
[docs/PARAMETERS.md](docs/PARAMETERS.md); representative rows:

| Config section | Example key | Environment override | Purpose |
|---|---|---|---|
| `app` | `app.env_write_enabled` | `CLOUD_DOG__APP__ENV_WRITE_ENABLED` | Toggle in-app env writes (default `false`) |
| `api_server` | `api_server.base_url` | `CLOUD_DOG__API_SERVER__BASE_URL` | Backend API base the web proxy targets |
| `web_server` | `web_server.proxy_timeout_seconds` | `CLOUD_DOG__WEB_SERVER__PROXY_TIMEOUT_SECONDS` | Proxy timeout (must exceed LLM latency, e.g. `480`) |
| `db` | `db.uri` | `CLOUD_DOG__DB__URI` | Database URI |
| `default_channel` | `default_channel` | `CLOUD_DOG__DEFAULT_CHANNEL` | Fallback delivery channel |
| `channels` | `channels.<name>.*` | `CLOUD_DOG__CHANNELS__<NAME>__*` | Per-channel config (type, limits, restrictions, preferences) |
| `delivery_worker` | `delivery.max_queued` | `CLOUD_DOG__DELIVERY__MAX_QUEUED` | Admission-control queue cap |
| `llm` | `llm.base_url` | `CLOUD_DOG__LLM__BASE_URL` | LLM endpoint for formatting/translation |
| `email` | `email.smtp.default.host` | `CLOUD_DOG__EMAIL__SMTP__DEFAULT__HOST` | SMTP host for the default email channel |
| `log` | `log.level` | `CLOUD_DOG__LOG__LEVEL` | Structured (`cloud_dog_logging`) log level |
| bootstrap | — | `VAULT_ADDR` / `VAULT_TOKEN` / `VAULT_MOUNT_POINT` / `VAULT_CONFIG_PATH` | Vault bootstrap tier (only exempt `os.environ` reads); plus `CLOUD_DOG_ENV_FILES` for chained env files |

Secrets are never embedded — external credentials are resolved from the platform secret store at runtime.
See [env.example](env.example) for the operator-facing template. Cross-project standardisation of this
matrix as a dedicated Web-UI **API Docs** panel tab is tracked as a shared-component item under the
NA-X-08 platform ruling (see W28E-1874 evidence).

## Licence

Apache-2.0 - Copyright (c) 2026 Cloud-Dog, Viewdeck Engineering Limited

## Security & Publication Notes

Authentication and authorisation use the platform IDAM credential/cert model; do not commit secrets.
This public source mirror excludes internal operations material; build artefacts (e.g. the UI bundle) are regenerated at build time.
