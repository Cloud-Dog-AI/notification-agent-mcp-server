---
template-id: T-PRE
template-version: 1.0
applies-to: docs/PREPROD.md
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
doc-age-policy: 30d
doc-conformance-stamp: 2026-06-18T00:00:00Z
---

# PREPROD Deployment — Notification Agent MCP Server

This document describes the pre-production operator/deployment overlay for this service. The Terraform container environment is the runtime source of truth, and `private/env-PREPROD` is the operator/test overlay used for local control commands and pytest runs against the deployed preprod service. Defaults and non-preprod settings remain documented in `docs/ENV-REFERENCE.md`, `docs/ARCHITECTURE.md`, and `defaults.yaml`.

## 1. Overview
- Service URL: `https://notificationagent0.your-domain.com`
- Container hostname: `notificationagent0.internal.example`
- Health endpoint verified during W28A-241: `https://notificationagent0.your-domain.com/api/v1/health`
- Docker image: `registry.example.com/cloud-dog/notification-agent-mcp-server:latest`
- Active Terraform container definition: `terraform/primary-environment/notificationagent_containers.tf.json`
- Legacy/parallel Terraform definition to cross-check when investigating drift: `terraform/legacy-environment/notificationagent_containers.tf.json`
- Operator overlay file: `./notification-agent-mcp-server/private/env-PREPROD`

### Port allocation
| Surface | Internal port | External URL |
|---|---:|---|
| Web UI | 8080 | `https://notificationagent0.your-domain.com` |
| MCP | 8081 | `https://notificationagent0.your-domain.com/mcp` |
| A2A | 8082 | `wss://notificationagent0.your-domain.com/a2a` |
| API | 8083 | `https://notificationagent0.your-domain.com/api` |

## 2. Configuration
Section 2 documents the full preprod environment surface that differs from or materially specialises the defaults. Use it together with `defaults.yaml` and `docs/ENV-REFERENCE.md` when tracing a value through the precedence chain `os.environ -> --env file -> config.yaml -> defaults.yaml`.

### Server, runtime, and database settings
| Setting(s) | Default / baseline | Preprod source | Preprod change? | Notes |
|---|---|---|---|---|
| `CLOUD_DOG_ENVIRONMENT` | not set in defaults | `private/env-PREPROD` | Yes | Marks the runtime as preprod. |
| `CLOUD_DOG__NOTIFY__DB__URI` | Vault-backed MySQL by default in `defaults.yaml` | Terraform + `private/env-PREPROD` | Yes | Current preprod container uses SQLite under `/app/database/data/notify.db`. |
| `CLOUD_DOG__NOTIFY__API_SERVER__*`, `...WEB_SERVER__*`, `...MCP_SERVER__*`, `...A2A_SERVER__*` | blank host/base URLs and local ports in defaults | Terraform + `private/env-PREPROD` | Yes | External URLs are exposed through Traefik; container-internal defaults still point at localhost for intra-process proxying. |
| `TEST_RUNTIME_MODE`, `TEST_USE_EXTERNAL_RUNTIME`, `TEST_API_BASE_URL`, `TEST_MCP_BASE_URL` | unset | `private/env-PREPROD` | Yes | Operator/test overlay talks to the deployed preprod service instead of a local server. |

### LLM and channel settings
| Setting(s) | Default / baseline | Preprod source | Preprod change? | Notes |
|---|---|---|---|---|
| `CLOUD_DOG__NOTIFY__LLM__*` | blank provider/base/model in defaults | Terraform + `private/env-PREPROD` | Yes | Preprod pins Ollama `qwen3:14b` with 900s timeouts for long formatting tasks. |
| `CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__*` | blank/placeholder in defaults | Vault-backed Terraform + `private/env-PREPROD` | Yes | Operations SMTP service is the primary delivery channel. |
| `CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__*` | disabled/blank in defaults | Vault-backed Terraform + `private/env-PREPROD` | Yes | Slack/webhook channel is enabled for chat_rest validation. |
| `CLOUD_DOG__NOTIFY__CHANNELS__SMS__DEFAULT__*`, Twilio test vars | unset in defaults | Vault-backed `private/env-PREPROD` | Yes | Twilio SMS/WhatsApp validation is wired through Vault-backed credentials. |
| `CLOUD_DOG__NOTIFY__STORAGE__*` | local backend defaults | Terraform + `private/env-PREPROD` | Partial | Current preprod keeps local storage and exposes `/storage`. |

### Auth, test, and TLS settings
| Setting(s) | Default / baseline | Preprod source | Preprod change? | Notes |
|---|---|---|---|---|
| `CLOUD_DOG__NOTIFY__API_SERVER__API_KEY`, `...AUTH__JWT_SECRET`, `...WEBHOOK__SECRET`, web username/password | blank in defaults | Vault-backed Terraform + `private/env-PREPROD` | Yes | Required for API, UI, and webhook security. |
| Slack/Twilio test variables | unset | Vault-backed `private/env-PREPROD` | Yes | Used by the preprod acceptance suite. |
| CA bundle variables | unset | `private/env-PREPROD` | Yes | Host overlay uses system CA bundle; container uses `/app/certs/trusted-ca-bundle.pem`. |

## 3. Preprod-Specific Overrides
Only settings that differ materially from defaults or that must be supplied for preprod are listed here. The literal operator/test overlay is `./notification-agent-mcp-server/private/env-PREPROD`.

| Override | Why preprod differs | Source of truth |
|---|---|---|
| SQLite DB path under `/app/database/data` | Current preprod rollout uses container-local SQLite rather than the Vault-backed MySQL default. | Terraform 60-container file |
| External API/Web/MCP/A2A URLs | Traefik exposes public HTTPS/WSS routes that differ from the localhost intra-container defaults. | Terraform + `private/env-PREPROD` |
| Long LLM timeouts (900s) | Shared preprod formatting/summarisation jobs are intentionally tolerant of slow LLM responses. | Terraform + `private/env-PREPROD` |
| SMTP/Slack/Twilio credentials | Delivery verification depends on real external services. | Vault + `private/env-PREPROD` |
| Test runtime overlay variables | Preprod test harnesses call the already-deployed service, not a local runtime. | `private/env-PREPROD` |

## 4. Vault Configuration
This service reads preprod secrets from the shared Vault config blob at `cloud_dog_ai/config`.

### Required Vault paths
- `dev.services.notificationagent0` for API/UI/JWT/webhook secrets
- `dev.email.smtp_operations_cloud_dog_net` for SMTP delivery settings
- `dev.channels.slack`, `dev.channels.twilio_sms`, `dev.channels.twilio_whatsapp` for non-email delivery tests
- `dev.models.ollama_qwen3_14b_llm2` for the formatter LLM

### Operator setup
```bash
set -a; source .env.local
vault kv get -mount=cloud_dog_ai config
```

### Populate or refresh missing entries
Use a merged JSON payload rather than editing Terraform or the running container.

```bash
vault kv put -mount=cloud_dog_ai config   content=@/tmp/cloud-dog-ai-config.preprod.json
```

Example payload fragment:
```json
{
  "dev": {
    "services": {"notificationagent0": {"api_key": "<API_KEY>", "jwt_secret": "<JWT>", "webhook_secret": "<WEBHOOK_SECRET>"}},
    "email": {"smtp_operations_cloud_dog_net": {"host": "<HOST>", "username": "<USER>", "password": "<PASSWORD>"}}
  }
}
```

## 5. Deployment Steps
The project rules forbid ad-hoc `docker build`; use the repo entrypoint script.

1. Load Vault-backed build credentials.
```bash
set -a; source .env.local
```
2. Build the image.
```bash
cd ./notification-agent-mcp-server && bash docker-build.sh latest
```
3. Tag and push the image.
```bash
docker tag cloud-dog/notification-agent-mcp-server:latest registry.example.com/cloud-dog/notification-agent-mcp-server:latest
docker push registry.example.com/cloud-dog/notification-agent-mcp-server:latest
```
4. Plan and apply the Terraform update from the shared preprod workspace.
```bash
cd 'terraform/60 Cloud-Dog AI Containers'
terraform plan -out=tfplan.out
terraform apply tfplan.out
```
5. Verify the deployed service.
```bash
curl -fsS https://notificationagent0.your-domain.com/api/v1/health
```

## 6. Testing Against Preprod
Use the committed tier env file plus `private/env-PREPROD` as the environment-specific overlay.

1. `pytest tests/system --env tests/env-ST --env private/env-PREPROD -q`
2. `pytest tests/integration --env tests/env-IT --env private/env-PREPROD -q`
3. Application tests against preprod should be limited to non-destructive channels or explicitly coordinated delivery accounts.

Known limitations:
- Notification preprod is a shared delivery environment; avoid bulk or destructive AT runs without coordination.
- The service is still tracked as pending W28A-228-R2 in deployment history, so verify health before each run.

## 7. Troubleshooting
- `curl -fsS https://notificationagent0.your-domain.com/api/v1/health` should return API health with database/channel checks.
- `docker -H your-docker-host logs notificationagent0.internal.example` for runtime logs.
- If Slack/Twilio tests fail, compare the Vault paths above against `private/env-PREPROD` instead of hardcoding values into tests.
