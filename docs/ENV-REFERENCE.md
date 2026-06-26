---
template-id: T-ENV
template-version: 1.0
applies-to: docs/ENV-REFERENCE.md
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

# Environment Reference

This reference is generated from `defaults.yaml` and the standard Cloud-Dog environment override pattern.

## `a2a_server`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__A2A_SERVER__ENABLED` | `true` | Optional | `true` | Toggle for a2a server. |
| `CLOUD_DOG__A2A_SERVER__PORT` | `-` | Optional | `8080` | Port for a2a server connections. |
| `CLOUD_DOG__A2A_SERVER__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for a2a server. |
| `CLOUD_DOG__A2A_SERVER__BASE_PATH` | `-` | Optional | `<set as needed>` | Configuration value for a2a server base path. |
| `CLOUD_DOG__A2A_SERVER__MAX_STARTUP_RETRIES` | `3` | Optional | `3` | Configuration value for a2a server max startup retries. |
| `CLOUD_DOG__A2A_SERVER__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for a2a server base. |
| `CLOUD_DOG__A2A_SERVER__API_BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__A2A_SERVER__WEBSOCKET_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for a2a server websocket. |
| `CLOUD_DOG__A2A_SERVER__REQUEST_TIMEOUT` | `60` | Optional | `60` | Timeout or duration control for a2a server request. |

## `api`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__API__TIMEOUT` | `300` | Optional | `300` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API__READ_TIMEOUT` | `300` | Optional | `300` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API__CONNECT_TIMEOUT` | `30` | Optional | `30` | Credential or authentication setting for the related subsystem. |

## `api_server`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__API_SERVER__ENABLED` | `true` | Optional | `true` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for api server. |
| `CLOUD_DOG__API_SERVER__PORT` | `-` | Optional | `8080` | Port for api server connections. |
| `CLOUD_DOG__API_SERVER__BASE_PATH` | `-` | Optional | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__CORS_ORIGINS` | `["*"]` | Optional | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__REQUEST_TIMEOUT` | `300` | Optional | `300` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__MESSAGE_FETCH_TIMEOUT` | `60` | Optional | `60` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__MAX_REQUEST_SIZE` | `10485760` | Optional | `10485760` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__API_SERVER__MAX_STARTUP_RETRIES` | `3` | Optional | `3` | Credential or authentication setting for the related subsystem. |

## `app`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__APP__ID` | `1` | Optional | `1` | Configuration value for app id. |
| `CLOUD_DOG__APP__VERSION` | `-` | Optional | `<set as needed>` | Configuration value for app version. |
| `CLOUD_DOG__APP__TITLE` | `Notification Agent MCP Server` | Optional | `Notification Agent MCP Server` | Configuration value for app title. |
| `CLOUD_DOG__APP__DESCRIPTION` | `-` | Optional | `<set as needed>` | Configuration value for app description. |
| `CLOUD_DOG__APP__SERVER_NAME` | `-` | Optional | `<set as needed>` | Configuration value for app server name. |
| `CLOUD_DOG__APP__SERVER_ID` | `notification-agent` | Optional | `notification-agent` | Configuration value for app server id. |
| `CLOUD_DOG__APP__DEFAULT_LANGUAGE` | `-` | Optional | `<set as needed>` | Configuration value for app default language. |
| `CLOUD_DOG__APP__CERTIFICATE` | `-` | Optional | `<set as needed>` | Configuration value for app certificate. |
| `CLOUD_DOG__APP__KEY` | `-` | Optional | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__APP__ENV_WRITE_ENABLED` | `false` | Optional | `false` | Toggle for app env write. |

## `auth`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__AUTH__PROVIDER` | `-` | Optional | `<set as needed>` | Configuration value for auth provider. |
| `CLOUD_DOG__AUTH__JWT_SECRET` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__AUTH__JWT_ALGORITHM` | `-` | Optional | `<set as needed>` | Configuration value for auth jwt algorithm. |
| `CLOUD_DOG__AUTH__JWT_EXPIRY_MINUTES` | `-` | Optional | `<set as needed>` | Configuration value for auth jwt expiry minutes. |

## `cache`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__CACHE__ENABLED` | `true` | Optional | `true` | Toggle for cache. |
| `CLOUD_DOG__CACHE__BACKEND` | `memory` | Optional | `memory` | Configuration value for cache backend. |
| `CLOUD_DOG__CACHE__TTL_SECONDS` | `3600` | Optional | `3600` | Timeout or duration control for cache ttl. |
| `CLOUD_DOG__CACHE__MAX_ENTRIES` | `1000` | Optional | `1000` | Configuration value for cache max entries. |

## `channels`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__ENABLED` | `false` | Optional | `false` | Toggle for channels smtp default. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for channels smtp default. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__PORT` | `-` | Optional | `8080` | Port for channels smtp default connections. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__USERNAME` | `-` | Optional | `service-admin` | Configuration value for channels smtp default username. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__PASSWORD` | `-` | Deployment dependent | `your-secure-password` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__FROM_ADDRESS` | `-` | Optional | `<set as needed>` | Configuration value for channels smtp default from address. |
| `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__USE_TLS` | `-` | Optional | `<set as needed>` | Configuration value for channels smtp default use tls. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__ENABLED` | `false` | Optional | `false` | Toggle for channels sms default. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__PROVIDER` | `twilio` | Optional | `twilio` | Configuration value for channels sms default provider. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__SENDER` | `-` | Optional | `<set as needed>` | Configuration value for channels sms default sender. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__ACCOUNT_SID` | `-` | Optional | `<set as needed>` | Configuration value for channels sms default account sid. |
| `CLOUD_DOG__CHANNELS__SMS__DEFAULT__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for channels sms default base. |
| `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__ENABLED` | `false` | Optional | `false` | Toggle for channels whatsapp default. |
| `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for channels whatsapp default base. |
| `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__TOKEN` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__ACCOUNT_SID` | `-` | Optional | `<set as needed>` | Configuration value for channels whatsapp default account sid. |
| `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__FROM_NUMBER` | `-` | Optional | `<set as needed>` | Configuration value for channels whatsapp default from number. |
| `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__ENABLED` | `false` | Optional | `false` | Toggle for channels chat rest default. |
| `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__ENDPOINT` | `-` | Optional | `<set as needed>` | Configuration value for channels chat rest default endpoint. |
| `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__API_TOKEN` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__CHANNEL_ID` | `-` | Optional | `<set as needed>` | Configuration value for channels chat rest default channel id. |

## `circuit`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__CIRCUIT__SOFT_ERROR_THRESHOLD` | `5` | Optional | `5` | Configuration value for circuit soft error threshold. |
| `CLOUD_DOG__CIRCUIT__HARD_ERROR_THRESHOLD` | `10` | Optional | `10` | Configuration value for circuit hard error threshold. |
| `CLOUD_DOG__CIRCUIT__COOLDOWN_SECONDS` | `300` | Optional | `300` | Timeout or duration control for circuit cooldown. |

## `confirmations`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__CONFIRMATIONS__SIGNATURE__SECRET` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__CONFIRMATIONS__SIGNATURE__ALGORITHM` | `sha256` | Optional | `sha256` | Configuration value for confirmations signature algorithm. |
| `CLOUD_DOG__CONFIRMATIONS__POLLING__ENABLED` | `true` | Optional | `true` | Toggle for confirmations polling. |
| `CLOUD_DOG__CONFIRMATIONS__POLLING__INTERVAL_SECONDS` | `60` | Optional | `60` | Timeout or duration control for confirmations polling interval. |

## `db`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__DB__URI` | `${vault.dev.databases.notification_mysql.uri}` | Deployment dependent | `https://service.example.com` | Endpoint or connection URL for db. |

## `default_channel`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__DEFAULT_CHANNEL` | `-` | Optional | `<set as needed>` | Configuration value for default channel. |

## `delivery_worker`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__DELIVERY_WORKER__ENABLED` | `true` | Optional | `true` | Toggle for delivery worker. |
| `CLOUD_DOG__DELIVERY_WORKER__POLL_INTERVAL` | `1.0` | Optional | `1.0` | Configuration value for delivery worker poll interval. |
| `CLOUD_DOG__DELIVERY_WORKER__BATCH_SIZE` | `10` | Optional | `10` | Configuration value for delivery worker batch size. |
| `CLOUD_DOG__DELIVERY_WORKER__MAX_CONCURRENT_DELIVERIES` | `2` | Optional | `2` | Configuration value for delivery worker max concurrent deliveries. |

## `llm`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__LLM__PROVIDER` | `-` | Optional | `<set as needed>` | Configuration value for llm provider. |
| `CLOUD_DOG__LLM__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for llm base. |
| `CLOUD_DOG__LLM__MODEL` | `-` | Optional | `<set as needed>` | Configuration value for llm model. |
| `CLOUD_DOG__LLM__TEMPERATURE` | `0.5` | Optional | `0.5` | Configuration value for llm temperature. |
| `CLOUD_DOG__LLM__IGNORE_TLS` | `false` | Optional | `false` | Configuration value for llm ignore tls. |
| `CLOUD_DOG__LLM__OPENAI_API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__ANTHROPIC_API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__AZURE_OPENAI_API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__AZURE_OPENAI_ENDPOINT` | `-` | Optional | `<set as needed>` | Configuration value for llm azure openai endpoint. |
| `CLOUD_DOG__LLM__AZURE_OPENAI_API_VERSION` | `-` | Optional | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__GOOGLE_API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__AWS_REGION` | `-` | Optional | `<set as needed>` | Configuration value for llm aws region. |
| `CLOUD_DOG__LLM__NUM_CTX` | `32768` | Optional | `32768` | Configuration value for llm num ctx. |
| `CLOUD_DOG__LLM__NUM_PREDICT` | `16384` | Optional | `16384` | Configuration value for llm num predict. |
| `CLOUD_DOG__LLM__MAX_TOKENS` | `<secret>` | Deployment dependent | `your-secret-value` | Configuration value for llm max tokens. |
| `CLOUD_DOG__LLM__TOKEN_ESTIMATE_CHARS_PER_TOKEN` | `<secret>` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LLM__CHUNK_MAX_ROUNDS` | `2` | Optional | `2` | Configuration value for llm chunk max rounds. |
| `CLOUD_DOG__LLM__TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm. |
| `CLOUD_DOG__LLM__QUERY_TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm query. |
| `CLOUD_DOG__LLM__RETRY_ATTEMPTS` | `1` | Optional | `1` | Configuration value for llm retry attempts. |
| `CLOUD_DOG__LLM__RETRY_DELAY` | `5` | Optional | `5` | Configuration value for llm retry delay. |
| `CLOUD_DOG__LLM__AUTO_PULL` | `true` | Optional | `true` | Configuration value for llm auto pull. |
| `CLOUD_DOG__LLM__MODEL_LOAD_TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm model load. |
| `CLOUD_DOG__LLM__STARTUP_TIMEOUT` | `5` | Optional | `5` | Timeout or duration control for llm startup. |
| `CLOUD_DOG__LLM__TOP_P` | `1` | Optional | `1` | Configuration value for llm top p. |
| `CLOUD_DOG__LLM__TOP_K` | `0` | Optional | `0` | Configuration value for llm top k. |
| `CLOUD_DOG__LLM__REPEAT_PENALTY` | `1.1` | Optional | `1.1` | Configuration value for llm repeat penalty. |
| `CLOUD_DOG__LLM__SEED` | `1234` | Optional | `1234` | Configuration value for llm seed. |
| `CLOUD_DOG__LLM__MIROSTAT` | `0` | Optional | `0` | Configuration value for llm mirostat. |
| `CLOUD_DOG__LLM__MIROSTAT_TAU` | `5.0` | Optional | `5.0` | Configuration value for llm mirostat tau. |
| `CLOUD_DOG__LLM__MIROSTAT_ETA` | `0.1` | Optional | `0.1` | Configuration value for llm mirostat eta. |
| `CLOUD_DOG__LLM__TRANSLATION_TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm translation. |
| `CLOUD_DOG__LLM__TRANSLATION_CHUNK_CHARS` | `2000` | Optional | `2000` | Configuration value for llm translation chunk chars. |
| `CLOUD_DOG__LLM__TRANSLATION_CHUNK_PARALLELISM` | `2` | Optional | `2` | Configuration value for llm translation chunk parallelism. |
| `CLOUD_DOG__LLM__FORMATTING_TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm formatting. |
| `CLOUD_DOG__LLM__SUMMARIZATION_TIMEOUT` | `300` | Optional | `300` | Timeout or duration control for llm summarization. |
| `CLOUD_DOG__LLM__DEFAULT_SYSTEM_PROMPT` | `You are a helpful assistant for notification delivery. 
Gener...` | Optional | `You are a helpful assistant for notification delivery. 
Gener...` | Configuration value for llm default system prompt. |
| `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__MARKDOWN` | `═══════════════════════════════════════════════════════════
⚠...` | Optional | `═══════════════════════════════════════════════════════════
⚠...` | Configuration value for llm format instructions markdown. |
| `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__HTML` | `═══════════════════════════════════════════════════════════
⚠...` | Optional | `═══════════════════════════════════════════════════════════
⚠...` | Configuration value for llm format instructions html. |
| `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__PLAIN` | `Format the output as plain text, preserving readability with ...` | Optional | `Format the output as plain text, preserving readability with ...` | Configuration value for llm format instructions plain. |
| `CLOUD_DOG__LLM__LANGUAGE_INSTRUCTION_TEMPLATE` | `═══════════════════════════════════════════════════════════
⚠...` | Optional | `═══════════════════════════════════════════════════════════
⚠...` | Configuration value for llm language instruction template. |
| `CLOUD_DOG__LLM__SUMMARIZATION_PROMPT_TEMPLATE` | `═══════════════════════════════════════════════════════════
⚠...` | Optional | `═══════════════════════════════════════════════════════════
⚠...` | Configuration value for llm summarization prompt template. |
| `CLOUD_DOG__LLM__POST_PROCESSING__STRIP_ENGLISH_BOILERPLATE` | `["Full message content is attached", "View full message", "Click here to view", "See attached", "Read more at", "For mor...` | Optional | `<set as needed>` | Configuration value for llm post processing strip english boilerplate. |
| `CLOUD_DOG__LLM__MODEL_PROMPTS__GRANITE4_TINY_H__SUMMARIZATION_PROMPT_TEMPLATE` | `You are a summarization engine. Output ONLY the summary text....` | Optional | `You are a summarization engine. Output ONLY the summary text....` | Configuration value for llm model prompts granite4 tiny h summarization prompt template. |
| `CLOUD_DOG__LLM__MODEL_PROMPTS__GRANITE4_TINY_H__LANGUAGE_INSTRUCTION_TEMPLATE` | `ABSOLUTE RULE: Every single word of your response MUST be in ...` | Optional | `ABSOLUTE RULE: Every single word of your response MUST be in ...` | Configuration value for llm model prompts granite4 tiny h language instruction template. |

## `log`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__LOG__LEVEL` | `INFO` | Optional | `INFO` | Configuration value for log level. |
| `CLOUD_DOG__LOG__FORMAT` | `standard` | Optional | `standard` | Configuration value for log format. |
| `CLOUD_DOG__LOG__CONSOLE` | `true` | Optional | `true` | Configuration value for log console. |
| `CLOUD_DOG__LOG__SERVICE_INSTANCE` | `${HOSTNAME:notification-agent-local}` | Optional | `${HOSTNAME:notification-agent-local}` | Configuration value for log service instance. |
| `CLOUD_DOG__LOG__ENVIRONMENT` | `${CLOUD_DOG_ENVIRONMENT:dev}` | Optional | `${CLOUD_DOG_ENVIRONMENT:dev}` | Configuration value for log environment. |
| `CLOUD_DOG__LOG__DUMP_CONFIG` | `false` | Optional | `false` | Configuration value for log dump config. |
| `CLOUD_DOG__LOG__API_SERVER_LOG` | `./logs/api_server.log` | Optional | `./logs/api_server.log` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__LOG__WEB_SERVER_LOG` | `./logs/web_server.log` | Optional | `./logs/web_server.log` | Configuration value for log web server log. |
| `CLOUD_DOG__LOG__WEB_ACCESS_LOG` | `./logs/web_access.log` | Optional | `./logs/web_access.log` | Configuration value for log web access log. |
| `CLOUD_DOG__LOG__MCP_SERVER_LOG` | `./logs/mcp_server.log` | Optional | `./logs/mcp_server.log` | Configuration value for log mcp server log. |
| `CLOUD_DOG__LOG__A2A_SERVER_LOG` | `./logs/a2a_server.log` | Optional | `./logs/a2a_server.log` | Configuration value for log a2a server log. |
| `CLOUD_DOG__LOG__ENABLE_ACCESS_LOG` | `false` | Optional | `false` | Configuration value for log enable access log. |
| `CLOUD_DOG__LOG__MAX_BYTES` | `10485760` | Optional | `10485760` | Configuration value for log max bytes. |
| `CLOUD_DOG__LOG__BACKUP_COUNT` | `10` | Optional | `10` | Configuration value for log backup count. |
| `CLOUD_DOG__LOG__COMPRESS` | `true` | Optional | `true` | Configuration value for log compress. |
| `CLOUD_DOG__LOG__ROTATION_TYPE` | `size` | Optional | `size` | Configuration value for log rotation type. |
| `CLOUD_DOG__LOG__RETENTION_DAYS` | `30` | Optional | `30` | Configuration value for log retention days. |
| `CLOUD_DOG__LOG__RETENTION__HOT_DAYS` | `14` | Optional | `14` | Configuration value for log retention hot days. |
| `CLOUD_DOG__LOG__RETENTION__COLD_DAYS` | `60` | Optional | `60` | Configuration value for log retention cold days. |
| `CLOUD_DOG__LOG__RETENTION__ARCHIVE_FORMAT` | `gz` | Optional | `gz` | Configuration value for log retention archive format. |
| `CLOUD_DOG__LOG__INTEGRITY__ENABLED` | `true` | Optional | `true` | Toggle for log integrity. |
| `CLOUD_DOG__LOG__INTEGRITY__INTERVAL_SECONDS` | `300` | Optional | `300` | Timeout or duration control for log integrity interval. |
| `CLOUD_DOG__LOG__INTEGRITY__LOG_FILE` | `./logs/audit-integrity.log` | Optional | `./logs/audit-integrity.log` | Configuration value for log integrity log file. |
| `CLOUD_DOG__LOG__INTEGRITY__HASH_ALGORITHM` | `sha256` | Optional | `sha256` | Configuration value for log integrity hash algorithm. |
| `CLOUD_DOG__LOG__ROTATION__MODE` | `size` | Optional | `size` | Configuration value for log rotation mode. |
| `CLOUD_DOG__LOG__ROTATION__MAX_BYTES` | `10485760` | Optional | `10485760` | Configuration value for log rotation max bytes. |
| `CLOUD_DOG__LOG__ROTATION__BACKUP_COUNT` | `10` | Optional | `10` | Configuration value for log rotation backup count. |
| `CLOUD_DOG__LOG__ROTATION__WHEN` | `midnight` | Optional | `midnight` | Configuration value for log rotation when. |
| `CLOUD_DOG__LOG__ROTATION__INTERVAL` | `1` | Optional | `1` | Configuration value for log rotation interval. |
| `CLOUD_DOG__LOG__ROTATION__COMPRESS` | `true` | Optional | `true` | Configuration value for log rotation compress. |

## `mcp_server`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__MCP_SERVER__ENABLED` | `true` | Optional | `true` | Toggle for mcp server. |
| `CLOUD_DOG__MCP_SERVER__TRANSPORT` | `-` | Optional | `<set as needed>` | Configuration value for mcp server transport. |
| `CLOUD_DOG__MCP_SERVER__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for mcp server base. |
| `CLOUD_DOG__MCP_SERVER__BASE_PATH` | `-` | Optional | `<set as needed>` | Configuration value for mcp server base path. |
| `CLOUD_DOG__MCP_SERVER__PORT` | `-` | Optional | `8080` | Port for mcp server connections. |
| `CLOUD_DOG__MCP_SERVER__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for mcp server. |
| `CLOUD_DOG__MCP_SERVER__PROTOCOL_VERSION` | `2024-11-05` | Optional | `2024-11-05` | Configuration value for mcp server protocol version. |
| `CLOUD_DOG__MCP_SERVER__MAX_STARTUP_RETRIES` | `3` | Optional | `3` | Configuration value for mcp server max startup retries. |
| `CLOUD_DOG__MCP_SERVER__NAME` | `-` | Optional | `<set as needed>` | Configuration value for mcp server name. |
| `CLOUD_DOG__MCP_SERVER__VERSION` | `-` | Optional | `<set as needed>` | Configuration value for mcp server version. |
| `CLOUD_DOG__MCP_SERVER__TLS` | `false` | Optional | `false` | Configuration value for mcp server tls. |
| `CLOUD_DOG__MCP_SERVER__API_BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__MCP_SERVER__API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__MCP_SERVER__REQUEST_TIMEOUT` | `60` | Optional | `60` | Timeout or duration control for mcp server request. |
| `CLOUD_DOG__MCP_SERVER__MAX_CONCURRENT_REQUESTS` | `5` | Optional | `5` | Configuration value for mcp server max concurrent requests. |
| `CLOUD_DOG__MCP_SERVER__CLIENT_API_KEY` | `-` | Deployment dependent | `your-api-key` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__MCP_SERVER__SESSION_TTL_SECONDS` | `3600` | Optional | `3600` | Timeout or duration control for mcp server session ttl. |
| `CLOUD_DOG__MCP_SERVER__STREAMABLE_HTTP_PATH` | `/mcp` | Optional | `/mcp` | Configuration value for mcp server streamable http path. |
| `CLOUD_DOG__MCP_SERVER__JSONRPC_PATH` | `/messages` | Optional | `/messages` | Configuration value for mcp server jsonrpc path. |
| `CLOUD_DOG__MCP_SERVER__LEGACY_SSE_PATH` | `/sse` | Optional | `/sse` | Configuration value for mcp server legacy sse path. |
| `CLOUD_DOG__MCP_SERVER__LEGACY_SSE_MESSAGE_PATH` | `/message` | Optional | `/message` | Configuration value for mcp server legacy sse message path. |
| `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_ENABLED` | `false` | Optional | `false` | Toggle for mcp server async jobs. |
| `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_STATUS_PATH` | `/jobs/{job_id}` | Optional | `/jobs/{job_id}` | Configuration value for mcp server async jobs status path. |
| `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_TIMEOUT_SECONDS` | `900` | Optional | `900` | Timeout or duration control for mcp server async jobs timeout. |
| `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_POLL_INTERVAL_SECONDS` | `2` | Optional | `2` | Timeout or duration control for mcp server async jobs poll interval. |

## `messages`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__MESSAGES__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for messages base. |
| `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__DEFAULT` | `Message #{message_id} | Job #{job_id}` | Optional | `Message #{message_id} | Job #{job_id}` | Configuration value for messages header templates default. |
| `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__WITH_GUID` | `Message #{message_id} ({message_guid}) | Job #{job_id}` | Optional | `Message #{message_id} ({message_guid}) | Job #{job_id}` | Configuration value for messages header templates with guid. |
| `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__SIMPLE` | `Notification #{message_id}` | Optional | `Notification #{message_id}` | Configuration value for messages header templates simple. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_FULL_MESSAGE` | `View full message` | Optional | `View full message` | Configuration value for messages link labels view full message. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_SOURCE_MESSAGE` | `View source message` | Optional | `View source message` | Configuration value for messages link labels view source message. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_PDF` | `PDF version` | Optional | `PDF version` | Configuration value for messages link labels view pdf. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_MESSAGE_CENTER` | `View in message center` | Optional | `View in message center` | Configuration value for messages link labels view message center. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__CHARACTERS` | `characters` | Optional | `characters` | Configuration value for messages link labels characters. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__ZNAKÓW` | `znaków` | Optional | `znaków` | Configuration value for messages link labels znaków. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__ZEICHEN` | `Zeichen` | Optional | `Zeichen` | Configuration value for messages link labels Zeichen. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__字符` | `字符` | Optional | `字符` | Configuration value for messages link labels 字符. |
| `CLOUD_DOG__MESSAGES__LINK_LABELS__أحرف` | `أحرف` | Optional | `أحرف` | Configuration value for messages link labels أحرف. |

## `observability`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__OBSERVABILITY__METRICS_ENABLED` | `true` | Optional | `true` | Toggle for observability metrics. |
| `CLOUD_DOG__OBSERVABILITY__TRACING_ENABLED` | `false` | Optional | `false` | Toggle for observability tracing. |
| `CLOUD_DOG__OBSERVABILITY__HEALTH_CHECK_INTERVAL_SECONDS` | `30` | Optional | `30` | Timeout or duration control for observability health check interval. |

## `queue`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__QUEUE__BACKEND` | `sql` | Optional | `sql` | Configuration value for queue backend. |
| `CLOUD_DOG__QUEUE__SQL_DATABASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for queue sql database. |
| `CLOUD_DOG__QUEUE__REDIS_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for queue redis. |
| `CLOUD_DOG__QUEUE__REDIS_KEY_PREFIX` | `cloud_dog_notify_jobs` | Optional | `cloud_dog_notify_jobs` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__QUEUE__DEFAULT_TTL_HOURS` | `24` | Optional | `24` | Configuration value for queue default ttl hours. |
| `CLOUD_DOG__QUEUE__MAX_RETRIES` | `5` | Optional | `5` | Configuration value for queue max retries. |
| `CLOUD_DOG__QUEUE__BACKOFF_BASE_SECONDS` | `2` | Optional | `2` | Timeout or duration control for queue backoff base. |
| `CLOUD_DOG__QUEUE__BACKOFF_MAX_SECONDS` | `3600` | Optional | `3600` | Timeout or duration control for queue backoff max. |
| `CLOUD_DOG__QUEUE__WORKER_POLL_INTERVAL_SECONDS` | `5` | Optional | `5` | Timeout or duration control for queue worker poll interval. |
| `CLOUD_DOG__QUEUE__WORKER_BATCH_SIZE` | `10` | Optional | `10` | Configuration value for queue worker batch size. |
| `CLOUD_DOG__QUEUE__SENDING_TIMEOUT_SECONDS` | `600` | Optional | `600` | Timeout or duration control for queue sending timeout. |
| `CLOUD_DOG__QUEUE__WATCHDOG__FORMATTING_STUCK_MINUTES_NULL_PAYLOAD` | `5` | Optional | `5` | Configuration value for queue watchdog formatting stuck minutes null payload. |
| `CLOUD_DOG__QUEUE__WATCHDOG__FORMATTING_STUCK_MINUTES_WITH_PAYLOAD` | `10` | Optional | `10` | Configuration value for queue watchdog formatting stuck minutes with payload. |
| `CLOUD_DOG__QUEUE__WATCHDOG__SENDING_STUCK_MINUTES` | `10` | Optional | `10` | Configuration value for queue watchdog sending stuck minutes. |

## `rate_limit`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_MINUTE` | `600` | Optional | `600` | Configuration value for rate limit per channel per minute. |
| `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_HOUR` | `10000` | Optional | `10000` | Configuration value for rate limit per channel per hour. |
| `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_DAY` | `100000` | Optional | `100000` | Configuration value for rate limit per channel per day. |
| `CLOUD_DOG__RATE_LIMIT__PER_DESTINATION_PER_MINUTE` | `60` | Optional | `60` | Configuration value for rate limit per destination per minute. |
| `CLOUD_DOG__RATE_LIMIT__PER_DESTINATION_PER_HOUR` | `500` | Optional | `500` | Configuration value for rate limit per destination per hour. |

## `retention`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__RETENTION__MESSAGES_DAYS` | `30` | Optional | `30` | Configuration value for retention messages days. |
| `CLOUD_DOG__RETENTION__DELIVERIES_DAYS` | `30` | Optional | `30` | Configuration value for retention deliveries days. |
| `CLOUD_DOG__RETENTION__RECEIPTS_DAYS` | `30` | Optional | `30` | Configuration value for retention receipts days. |
| `CLOUD_DOG__RETENTION__LOGS_DAYS` | `30` | Optional | `30` | Configuration value for retention logs days. |
| `CLOUD_DOG__RETENTION__AUDIT_EVENTS_DAYS` | `90` | Optional | `90` | Configuration value for retention audit events days. |

## `storage`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__STORAGE__BACKEND` | `-` | Optional | `<set as needed>` | Configuration value for storage backend. |
| `CLOUD_DOG__STORAGE__LOCAL__BASE_PATH` | `-` | Optional | `<set as needed>` | Configuration value for storage local base path. |
| `CLOUD_DOG__STORAGE__LOCAL__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for storage local base. |
| `CLOUD_DOG__STORAGE__S3__ENDPOINT` | `-` | Optional | `<set as needed>` | Configuration value for storage s3 endpoint. |
| `CLOUD_DOG__STORAGE__S3__BUCKET` | `notification` | Optional | `notification` | Configuration value for storage s3 bucket. |
| `CLOUD_DOG__STORAGE__S3__ACCESS_KEY` | `-` | Optional | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__STORAGE__S3__SECRET_KEY` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__STORAGE__S3__REGION` | `-` | Optional | `<set as needed>` | Configuration value for storage s3 region. |
| `CLOUD_DOG__STORAGE__WEBDAV__URL` | `-` | Deployment dependent | `https://service.example.com` | Endpoint or connection URL for storage webdav. |
| `CLOUD_DOG__STORAGE__WEBDAV__USERNAME` | `-` | Optional | `service-admin` | Configuration value for storage webdav username. |
| `CLOUD_DOG__STORAGE__WEBDAV__PASSWORD` | `-` | Deployment dependent | `your-secure-password` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__STORAGE__FTP__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for storage ftp. |
| `CLOUD_DOG__STORAGE__FTP__PORT` | `-` | Optional | `8080` | Port for storage ftp connections. |
| `CLOUD_DOG__STORAGE__FTP__USERNAME` | `-` | Optional | `service-admin` | Configuration value for storage ftp username. |
| `CLOUD_DOG__STORAGE__FTP__PASSWORD` | `-` | Deployment dependent | `your-secure-password` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__STORAGE__FTP__PASSIVE_MODE` | `-` | Optional | `<set as needed>` | Configuration value for storage ftp passive mode. |

## `test`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__TEST__EMAIL_DOMAIN` | `@cloud-dog.net` | Optional | `@cloud-dog.net` | Configuration value for test email domain. |
| `CLOUD_DOG__TEST__DEFAULT_SMS_CHANNEL` | `sms_default` | Optional | `sms_default` | Configuration value for test default sms channel. |
| `CLOUD_DOG__TEST__MEDIA__IMAGE_URL` | `https://example.com/test-image.png` | Deployment dependent | `https://example.com/test-image.png` | Endpoint or connection URL for test media image. |
| `CLOUD_DOG__TEST__MEDIA__HTTP_IMAGE_URL` | `http://example.com/test.png` | Deployment dependent | `http://example.com/test.png` | Endpoint or connection URL for test media http image. |
| `CLOUD_DOG__TEST__MEDIA__HTTPS_IMAGE_URL` | `https://example.com/test.png` | Deployment dependent | `https://example.com/test.png` | Endpoint or connection URL for test media https image. |
| `CLOUD_DOG__TEST__WEBHOOK__SLACK_URL` | `https://hooks.slack.com/services/T000/B000/XXXX` | Deployment dependent | `https://hooks.slack.com/services/T000/B000/XXXX` | Endpoint or connection URL for test webhook slack. |
| `CLOUD_DOG__TEST__WEBHOOK__LOCAL_URL` | `http://localhost:9999/webhook` | Deployment dependent | `http://localhost:9999/webhook` | Endpoint or connection URL for test webhook local. |
| `CLOUD_DOG__TEST__WEBHOOK__EXAMPLE_URL` | `https://example.com/webhook` | Deployment dependent | `https://example.com/webhook` | Endpoint or connection URL for test webhook example. |
| `CLOUD_DOG__TEST__WEBHOOK__INVALID_URL` | `not-a-url` | Deployment dependent | `not-a-url` | Endpoint or connection URL for test webhook invalid. |
| `CLOUD_DOG__TEST__WEBHOOK__INVALID_SCHEME_URL` | `ftp://example.com` | Deployment dependent | `ftp://example.com` | Endpoint or connection URL for test webhook invalid scheme. |
| `CLOUD_DOG__TEST__WEBHOOK__BEARER_TOKEN` | `-` | Deployment dependent | `your-secret-value` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__TEST__PERFORMANCE__CHANNEL` | `loopback_test` | Optional | `loopback_test` | Configuration value for test performance channel. |
| `CLOUD_DOG__TEST__PERFORMANCE__ITERATIONS` | `10` | Optional | `10` | Configuration value for test performance iterations. |
| `CLOUD_DOG__TEST__PERFORMANCE__P95_THRESHOLD_MS` | `500` | Optional | `500` | Configuration value for test performance p95 threshold ms. |
| `CLOUD_DOG__TEST__PERFORMANCE__INTER_REQUEST_DELAY_MS` | `500` | Optional | `500` | Configuration value for test performance inter request delay ms. |
| `CLOUD_DOG__TEST__PERFORMANCE__SKIP_SQLITE` | `true` | Optional | `true` | Configuration value for test performance skip sqlite. |
| `CLOUD_DOG__TEST__AT15__MAX_WAIT` | `600` | Optional | `600` | Configuration value for test at15 max wait. |
| `CLOUD_DOG__TEST__AT15__POLL_INTERVAL` | `2.0` | Optional | `2.0` | Configuration value for test at15 poll interval. |
| `CLOUD_DOG__TEST__AT15__SUBJECT_TEMPLATE` | `AT1.5 Test: {source}->{target} ({size} chars, {format})` | Optional | `AT1.5 Test: {source}->{target} ({size} chars, {format})` | Configuration value for test at15 subject template. |
| `CLOUD_DOG__TEST__AT15__SCENARIOS` | `[{"source": "en", "target": "fr", "size": 400, "format": "html", "id": "default_en_fr_400_html"}]` | Optional | `<set as needed>` | Configuration value for test at15 scenarios. |
| `CLOUD_DOG__TEST__AT15__NEGATIVE__MAX_WAIT` | `60` | Optional | `60` | Configuration value for test at15 negative max wait. |
| `CLOUD_DOG__TEST__AT15__NEGATIVE__SCENARIOS` | `[{"id": "missing_destination", "description": "Missing destination should fail at API validation", "remove_destination":...` | Optional | `<set as needed>` | Configuration value for test at15 negative scenarios. |
| `CLOUD_DOG__TEST__AT15__SMTP_VARIANTS` | `[{"id": "port_25_plain", "description": "Port 25 - Plain SMTP", "port": 25, "use_tls": false, "use_starttls": false}]` | Optional | `<set as needed>` | Configuration value for test at15 smtp variants. |
| `CLOUD_DOG__TEST__AT15__PERSONALISED__SCENARIOS` | `[{"language": "fr", "content_style": "html", "description": "French HTML"}]` | Optional | `<set as needed>` | Configuration value for test at15 personalised scenarios. |
| `CLOUD_DOG__TEST__AT14D__SUMMARY_SIZE` | `400` | Optional | `400` | Configuration value for test at14d summary size. |
| `CLOUD_DOG__TEST__AT14D__SUMMARY_TOLERANCE` | `0.4` | Optional | `0.4` | Configuration value for test at14d summary tolerance. |
| `CLOUD_DOG__TEST__AT14D__MAX_WAIT` | `600` | Optional | `600` | Configuration value for test at14d max wait. |
| `CLOUD_DOG__TEST__AT14D__PDF_MIN_SIZE_RATIO` | `0.5` | Optional | `0.5` | Configuration value for test at14d pdf min size ratio. |
| `CLOUD_DOG__TEST__AT14D__FORMAT` | `pdf` | Optional | `pdf` | Configuration value for test at14d format. |
| `CLOUD_DOG__TEST__AT14D__GENERATE_PDF` | `true` | Optional | `true` | Configuration value for test at14d generate pdf. |
| `CLOUD_DOG__TEST__AT14G__SUMMARY_SIZE` | `400` | Optional | `400` | Configuration value for test at14g summary size. |
| `CLOUD_DOG__TEST__AT14G__SUMMARY_TOLERANCE` | `0.4` | Optional | `0.4` | Configuration value for test at14g summary tolerance. |
| `CLOUD_DOG__TEST__AT14G__FULL_SIZE_TOLERANCE` | `0.3` | Optional | `0.3` | Configuration value for test at14g full size tolerance. |
| `CLOUD_DOG__TEST__AT14G__MAX_WAIT` | `600` | Optional | `600` | Configuration value for test at14g max wait. |
| `CLOUD_DOG__TEST__AT14G__PDF_MIN_SIZE_RATIO` | `0.5` | Optional | `0.5` | Configuration value for test at14g pdf min size ratio. |
| `CLOUD_DOG__TEST__AT14G__FORMAT` | `pdf` | Optional | `pdf` | Configuration value for test at14g format. |
| `CLOUD_DOG__TEST__AT14G__GENERATE_PDF` | `true` | Optional | `true` | Configuration value for test at14g generate pdf. |

## `web_server`

| Variable | Default | Required | Example | Description |
|----------|---------|----------|---------|-------------|
| `CLOUD_DOG__WEB_SERVER__ENABLED` | `true` | Optional | `true` | Toggle for web server. |
| `CLOUD_DOG__WEB_SERVER__HOST` | `-` | Optional | `0.0.0.0` | Host binding or upstream host for web server. |
| `CLOUD_DOG__WEB_SERVER__PORT` | `-` | Optional | `8080` | Port for web server connections. |
| `CLOUD_DOG__WEB_SERVER__BASE_PATH` | `-` | Optional | `<set as needed>` | Configuration value for web server base path. |
| `CLOUD_DOG__WEB_SERVER__MAX_STARTUP_RETRIES` | `3` | Optional | `3` | Configuration value for web server max startup retries. |
| `CLOUD_DOG__WEB_SERVER__USERNAME` | `-` | Optional | `service-admin` | Configuration value for web server username. |
| `CLOUD_DOG__WEB_SERVER__PASSWORD` | `-` | Deployment dependent | `your-secure-password` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__WEB_SERVER__BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Endpoint or connection URL for web server base. |
| `CLOUD_DOG__WEB_SERVER__API_BASE_URL` | `-` | Deployment dependent | `<set as needed>` | Credential or authentication setting for the related subsystem. |
| `CLOUD_DOG__WEB_SERVER__SESSION_MAX_AGE` | `-` | Optional | `<set as needed>` | Configuration value for web server session max age. |
| `CLOUD_DOG__WEB_SERVER__SESSION_TIMEOUT` | `-` | Optional | `<set as needed>` | Timeout or duration control for web server session. |
| `CLOUD_DOG__WEB_SERVER__CORS_ORIGINS` | `[]` | Optional | `<set as needed>` | Configuration value for web server cors origins. |
| `CLOUD_DOG__WEB_SERVER__STATUS_REFRESH_INTERVAL` | `10000` | Optional | `10000` | Configuration value for web server status refresh interval. |
| `CLOUD_DOG__WEB_SERVER__JOBS_REFRESH_INTERVAL` | `10000` | Optional | `10000` | Configuration value for web server jobs refresh interval. |
| `CLOUD_DOG__WEB_SERVER__CONNECTION_CHECK_INTERVAL` | `5000` | Optional | `5000` | Configuration value for web server connection check interval. |

## Vault Support

| Variable | Purpose | Example |
|----------|---------|---------|
| `VAULT_ADDR` | Vault server URL when using secret-backed config resolution. | `https://your-vault-server` |
| `VAULT_TOKEN` | Token-based authentication for Vault when applicable. | `your-vault-token` |
| `VAULT_MOUNT_POINT` | Secret mount used by your Vault deployment. | `secret` |
| `VAULT_CONFIG_PATH` | Config path holding service settings. | `services/your-service` |
