---
template-id: T-PAR
template-version: 1.0
applies-to: docs/PARAMETERS.md
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

# Parameters

This reference is generated from `defaults.yaml`. Each key can be overridden by the corresponding environment variable.

## `a2a_server`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `a2a_server.enabled` | `true` | `CLOUD_DOG__A2A_SERVER__ENABLED` | Toggle for a2a server. |
| `a2a_server.port` | `-` | `CLOUD_DOG__A2A_SERVER__PORT` | Port for a2a server connections. |
| `a2a_server.host` | `-` | `CLOUD_DOG__A2A_SERVER__HOST` | Host binding or upstream host for a2a server. |
| `a2a_server.base_path` | `-` | `CLOUD_DOG__A2A_SERVER__BASE_PATH` | Configuration value for a2a server base path. |
| `a2a_server.max_startup_retries` | `3` | `CLOUD_DOG__A2A_SERVER__MAX_STARTUP_RETRIES` | Configuration value for a2a server max startup retries. |
| `a2a_server.base_url` | `-` | `CLOUD_DOG__A2A_SERVER__BASE_URL` | Endpoint or connection URL for a2a server base. |
| `a2a_server.api_base_url` | `-` | `CLOUD_DOG__A2A_SERVER__API_BASE_URL` | Credential or authentication setting for the related subsystem. |
| `a2a_server.websocket_url` | `-` | `CLOUD_DOG__A2A_SERVER__WEBSOCKET_URL` | Endpoint or connection URL for a2a server websocket. |
| `a2a_server.request_timeout` | `60` | `CLOUD_DOG__A2A_SERVER__REQUEST_TIMEOUT` | Timeout or duration control for a2a server request. |

## `api`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `api.timeout` | `300` | `CLOUD_DOG__API__TIMEOUT` | Credential or authentication setting for the related subsystem. |
| `api.read_timeout` | `300` | `CLOUD_DOG__API__READ_TIMEOUT` | Credential or authentication setting for the related subsystem. |
| `api.connect_timeout` | `30` | `CLOUD_DOG__API__CONNECT_TIMEOUT` | Credential or authentication setting for the related subsystem. |

## `api_server`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `api_server.enabled` | `true` | `CLOUD_DOG__API_SERVER__ENABLED` | Credential or authentication setting for the related subsystem. |
| `api_server.host` | `-` | `CLOUD_DOG__API_SERVER__HOST` | Host binding or upstream host for api server. |
| `api_server.port` | `-` | `CLOUD_DOG__API_SERVER__PORT` | Port for api server connections. |
| `api_server.base_path` | `-` | `CLOUD_DOG__API_SERVER__BASE_PATH` | Credential or authentication setting for the related subsystem. |
| `api_server.base_url` | `-` | `CLOUD_DOG__API_SERVER__BASE_URL` | Credential or authentication setting for the related subsystem. |
| `api_server.api_key` | `-` | `CLOUD_DOG__API_SERVER__API_KEY` | Credential or authentication setting for the related subsystem. |
| `api_server.cors_origins` | `["*"]` | `CLOUD_DOG__API_SERVER__CORS_ORIGINS` | Credential or authentication setting for the related subsystem. |
| `api_server.request_timeout` | `300` | `CLOUD_DOG__API_SERVER__REQUEST_TIMEOUT` | Credential or authentication setting for the related subsystem. |
| `api_server.message_fetch_timeout` | `60` | `CLOUD_DOG__API_SERVER__MESSAGE_FETCH_TIMEOUT` | Credential or authentication setting for the related subsystem. |
| `api_server.max_request_size` | `10485760` | `CLOUD_DOG__API_SERVER__MAX_REQUEST_SIZE` | Credential or authentication setting for the related subsystem. |
| `api_server.max_startup_retries` | `3` | `CLOUD_DOG__API_SERVER__MAX_STARTUP_RETRIES` | Credential or authentication setting for the related subsystem. |

## `app`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `app.id` | `1` | `CLOUD_DOG__APP__ID` | Configuration value for app id. |
| `app.version` | `-` | `CLOUD_DOG__APP__VERSION` | Configuration value for app version. |
| `app.title` | `Notification Agent MCP Server` | `CLOUD_DOG__APP__TITLE` | Configuration value for app title. |
| `app.description` | `-` | `CLOUD_DOG__APP__DESCRIPTION` | Configuration value for app description. |
| `app.server_name` | `-` | `CLOUD_DOG__APP__SERVER_NAME` | Configuration value for app server name. |
| `app.server_id` | `notification-agent` | `CLOUD_DOG__APP__SERVER_ID` | Configuration value for app server id. |
| `app.default_language` | `-` | `CLOUD_DOG__APP__DEFAULT_LANGUAGE` | Configuration value for app default language. |
| `app.certificate` | `-` | `CLOUD_DOG__APP__CERTIFICATE` | Configuration value for app certificate. |
| `app.key` | `-` | `CLOUD_DOG__APP__KEY` | Credential or authentication setting for the related subsystem. |
| `app.env_write_enabled` | `false` | `CLOUD_DOG__APP__ENV_WRITE_ENABLED` | Toggle for app env write. |

## `auth`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `auth.provider` | `-` | `CLOUD_DOG__AUTH__PROVIDER` | Configuration value for auth provider. |
| `auth.jwt_secret` | `-` | `CLOUD_DOG__AUTH__JWT_SECRET` | Credential or authentication setting for the related subsystem. |
| `auth.jwt_algorithm` | `-` | `CLOUD_DOG__AUTH__JWT_ALGORITHM` | Configuration value for auth jwt algorithm. |
| `auth.jwt_expiry_minutes` | `-` | `CLOUD_DOG__AUTH__JWT_EXPIRY_MINUTES` | Configuration value for auth jwt expiry minutes. |

## `cache`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `cache.enabled` | `true` | `CLOUD_DOG__CACHE__ENABLED` | Toggle for cache. |
| `cache.backend` | `memory` | `CLOUD_DOG__CACHE__BACKEND` | Configuration value for cache backend. |
| `cache.ttl_seconds` | `3600` | `CLOUD_DOG__CACHE__TTL_SECONDS` | Timeout or duration control for cache ttl. |
| `cache.max_entries` | `1000` | `CLOUD_DOG__CACHE__MAX_ENTRIES` | Configuration value for cache max entries. |

## `channels`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `channels.smtp.default.enabled` | `false` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__ENABLED` | Toggle for channels smtp default. |
| `channels.smtp.default.host` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__HOST` | Host binding or upstream host for channels smtp default. |
| `channels.smtp.default.port` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__PORT` | Port for channels smtp default connections. |
| `channels.smtp.default.username` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__USERNAME` | Configuration value for channels smtp default username. |
| `channels.smtp.default.password` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__PASSWORD` | Credential or authentication setting for the related subsystem. |
| `channels.smtp.default.from_address` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__FROM_ADDRESS` | Configuration value for channels smtp default from address. |
| `channels.smtp.default.use_tls` | `-` | `CLOUD_DOG__CHANNELS__SMTP__DEFAULT__USE_TLS` | Configuration value for channels smtp default use tls. |
| `channels.sms.default.enabled` | `false` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__ENABLED` | Toggle for channels sms default. |
| `channels.sms.default.provider` | `twilio` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__PROVIDER` | Configuration value for channels sms default provider. |
| `channels.sms.default.api_key` | `-` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__API_KEY` | Credential or authentication setting for the related subsystem. |
| `channels.sms.default.sender` | `-` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__SENDER` | Configuration value for channels sms default sender. |
| `channels.sms.default.account_sid` | `-` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__ACCOUNT_SID` | Configuration value for channels sms default account sid. |
| `channels.sms.default.base_url` | `-` | `CLOUD_DOG__CHANNELS__SMS__DEFAULT__BASE_URL` | Endpoint or connection URL for channels sms default base. |
| `channels.whatsapp.default.enabled` | `false` | `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__ENABLED` | Toggle for channels whatsapp default. |
| `channels.whatsapp.default.base_url` | `-` | `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__BASE_URL` | Endpoint or connection URL for channels whatsapp default base. |
| `channels.whatsapp.default.token` | `-` | `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__TOKEN` | Credential or authentication setting for the related subsystem. |
| `channels.whatsapp.default.account_sid` | `-` | `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__ACCOUNT_SID` | Configuration value for channels whatsapp default account sid. |
| `channels.whatsapp.default.from_number` | `-` | `CLOUD_DOG__CHANNELS__WHATSAPP__DEFAULT__FROM_NUMBER` | Configuration value for channels whatsapp default from number. |
| `channels.chat_rest.default.enabled` | `false` | `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__ENABLED` | Toggle for channels chat rest default. |
| `channels.chat_rest.default.endpoint` | `-` | `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__ENDPOINT` | Configuration value for channels chat rest default endpoint. |
| `channels.chat_rest.default.api_token` | `-` | `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__API_TOKEN` | Credential or authentication setting for the related subsystem. |
| `channels.chat_rest.default.channel_id` | `-` | `CLOUD_DOG__CHANNELS__CHAT_REST__DEFAULT__CHANNEL_ID` | Configuration value for channels chat rest default channel id. |

## `circuit`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `circuit.soft_error_threshold` | `5` | `CLOUD_DOG__CIRCUIT__SOFT_ERROR_THRESHOLD` | Configuration value for circuit soft error threshold. |
| `circuit.hard_error_threshold` | `10` | `CLOUD_DOG__CIRCUIT__HARD_ERROR_THRESHOLD` | Configuration value for circuit hard error threshold. |
| `circuit.cooldown_seconds` | `300` | `CLOUD_DOG__CIRCUIT__COOLDOWN_SECONDS` | Timeout or duration control for circuit cooldown. |

## `confirmations`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `confirmations.signature.secret` | `-` | `CLOUD_DOG__CONFIRMATIONS__SIGNATURE__SECRET` | Credential or authentication setting for the related subsystem. |
| `confirmations.signature.algorithm` | `sha256` | `CLOUD_DOG__CONFIRMATIONS__SIGNATURE__ALGORITHM` | Configuration value for confirmations signature algorithm. |
| `confirmations.polling.enabled` | `true` | `CLOUD_DOG__CONFIRMATIONS__POLLING__ENABLED` | Toggle for confirmations polling. |
| `confirmations.polling.interval_seconds` | `60` | `CLOUD_DOG__CONFIRMATIONS__POLLING__INTERVAL_SECONDS` | Timeout or duration control for confirmations polling interval. |

## `db`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `db.uri` | `${vault.dev.databases.notification_mysql.uri}` | `CLOUD_DOG__DB__URI` | Endpoint or connection URL for db. |

## `default_channel`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `default_channel` | `-` | `CLOUD_DOG__DEFAULT_CHANNEL` | Configuration value for default channel. |

## `delivery_worker`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `delivery_worker.enabled` | `true` | `CLOUD_DOG__DELIVERY_WORKER__ENABLED` | Toggle for delivery worker. |
| `delivery_worker.poll_interval` | `1.0` | `CLOUD_DOG__DELIVERY_WORKER__POLL_INTERVAL` | Configuration value for delivery worker poll interval. |
| `delivery_worker.batch_size` | `10` | `CLOUD_DOG__DELIVERY_WORKER__BATCH_SIZE` | Configuration value for delivery worker batch size. |
| `delivery_worker.max_concurrent_deliveries` | `2` | `CLOUD_DOG__DELIVERY_WORKER__MAX_CONCURRENT_DELIVERIES` | Configuration value for delivery worker max concurrent deliveries. |

## `llm`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `llm.provider` | `-` | `CLOUD_DOG__LLM__PROVIDER` | Configuration value for llm provider. |
| `llm.base_url` | `-` | `CLOUD_DOG__LLM__BASE_URL` | Endpoint or connection URL for llm base. |
| `llm.model` | `-` | `CLOUD_DOG__LLM__MODEL` | Configuration value for llm model. |
| `llm.temperature` | `0.5` | `CLOUD_DOG__LLM__TEMPERATURE` | Configuration value for llm temperature. |
| `llm.ignore_tls` | `false` | `CLOUD_DOG__LLM__IGNORE_TLS` | Configuration value for llm ignore tls. |
| `llm.openai_api_key` | `-` | `CLOUD_DOG__LLM__OPENAI_API_KEY` | Credential or authentication setting for the related subsystem. |
| `llm.anthropic_api_key` | `-` | `CLOUD_DOG__LLM__ANTHROPIC_API_KEY` | Credential or authentication setting for the related subsystem. |
| `llm.azure_openai_api_key` | `-` | `CLOUD_DOG__LLM__AZURE_OPENAI_API_KEY` | Credential or authentication setting for the related subsystem. |
| `llm.azure_openai_endpoint` | `-` | `CLOUD_DOG__LLM__AZURE_OPENAI_ENDPOINT` | Configuration value for llm azure openai endpoint. |
| `llm.azure_openai_api_version` | `-` | `CLOUD_DOG__LLM__AZURE_OPENAI_API_VERSION` | Credential or authentication setting for the related subsystem. |
| `llm.google_api_key` | `-` | `CLOUD_DOG__LLM__GOOGLE_API_KEY` | Credential or authentication setting for the related subsystem. |
| `llm.aws_region` | `-` | `CLOUD_DOG__LLM__AWS_REGION` | Configuration value for llm aws region. |
| `llm.num_ctx` | `32768` | `CLOUD_DOG__LLM__NUM_CTX` | Configuration value for llm num ctx. |
| `llm.num_predict` | `16384` | `CLOUD_DOG__LLM__NUM_PREDICT` | Configuration value for llm num predict. |
| `llm.max_tokens` | `<secret>` | `CLOUD_DOG__LLM__MAX_TOKENS` | Configuration value for llm max tokens. |
| `llm.token_estimate_chars_per_token` | `<secret>` | `CLOUD_DOG__LLM__TOKEN_ESTIMATE_CHARS_PER_TOKEN` | Credential or authentication setting for the related subsystem. |
| `llm.chunk_max_rounds` | `2` | `CLOUD_DOG__LLM__CHUNK_MAX_ROUNDS` | Configuration value for llm chunk max rounds. |
| `llm.timeout` | `300` | `CLOUD_DOG__LLM__TIMEOUT` | Timeout or duration control for llm. |
| `llm.query_timeout` | `300` | `CLOUD_DOG__LLM__QUERY_TIMEOUT` | Timeout or duration control for llm query. |
| `llm.retry_attempts` | `1` | `CLOUD_DOG__LLM__RETRY_ATTEMPTS` | Configuration value for llm retry attempts. |
| `llm.retry_delay` | `5` | `CLOUD_DOG__LLM__RETRY_DELAY` | Configuration value for llm retry delay. |
| `llm.auto_pull` | `true` | `CLOUD_DOG__LLM__AUTO_PULL` | Configuration value for llm auto pull. |
| `llm.model_load_timeout` | `300` | `CLOUD_DOG__LLM__MODEL_LOAD_TIMEOUT` | Timeout or duration control for llm model load. |
| `llm.startup_timeout` | `5` | `CLOUD_DOG__LLM__STARTUP_TIMEOUT` | Timeout or duration control for llm startup. |
| `llm.top_p` | `1` | `CLOUD_DOG__LLM__TOP_P` | Configuration value for llm top p. |
| `llm.top_k` | `0` | `CLOUD_DOG__LLM__TOP_K` | Configuration value for llm top k. |
| `llm.repeat_penalty` | `1.1` | `CLOUD_DOG__LLM__REPEAT_PENALTY` | Configuration value for llm repeat penalty. |
| `llm.seed` | `1234` | `CLOUD_DOG__LLM__SEED` | Configuration value for llm seed. |
| `llm.mirostat` | `0` | `CLOUD_DOG__LLM__MIROSTAT` | Configuration value for llm mirostat. |
| `llm.mirostat_tau` | `5.0` | `CLOUD_DOG__LLM__MIROSTAT_TAU` | Configuration value for llm mirostat tau. |
| `llm.mirostat_eta` | `0.1` | `CLOUD_DOG__LLM__MIROSTAT_ETA` | Configuration value for llm mirostat eta. |
| `llm.translation_timeout` | `300` | `CLOUD_DOG__LLM__TRANSLATION_TIMEOUT` | Timeout or duration control for llm translation. |
| `llm.translation_chunk_chars` | `2000` | `CLOUD_DOG__LLM__TRANSLATION_CHUNK_CHARS` | Configuration value for llm translation chunk chars. |
| `llm.translation_chunk_parallelism` | `2` | `CLOUD_DOG__LLM__TRANSLATION_CHUNK_PARALLELISM` | Configuration value for llm translation chunk parallelism. |
| `llm.formatting_timeout` | `300` | `CLOUD_DOG__LLM__FORMATTING_TIMEOUT` | Timeout or duration control for llm formatting. |
| `llm.summarization_timeout` | `300` | `CLOUD_DOG__LLM__SUMMARIZATION_TIMEOUT` | Timeout or duration control for llm summarization. |
| `llm.default_system_prompt` | `You are a helpful assistant for notification delivery. 
Gener...` | `CLOUD_DOG__LLM__DEFAULT_SYSTEM_PROMPT` | Configuration value for llm default system prompt. |
| `llm.format_instructions.markdown` | `═══════════════════════════════════════════════════════════
⚠...` | `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__MARKDOWN` | Configuration value for llm format instructions markdown. |
| `llm.format_instructions.html` | `═══════════════════════════════════════════════════════════
⚠...` | `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__HTML` | Configuration value for llm format instructions html. |
| `llm.format_instructions.plain` | `Format the output as plain text, preserving readability with ...` | `CLOUD_DOG__LLM__FORMAT_INSTRUCTIONS__PLAIN` | Configuration value for llm format instructions plain. |
| `llm.language_instruction_template` | `═══════════════════════════════════════════════════════════
⚠...` | `CLOUD_DOG__LLM__LANGUAGE_INSTRUCTION_TEMPLATE` | Configuration value for llm language instruction template. |
| `llm.summarization_prompt_template` | `═══════════════════════════════════════════════════════════
⚠...` | `CLOUD_DOG__LLM__SUMMARIZATION_PROMPT_TEMPLATE` | Configuration value for llm summarization prompt template. |
| `llm.post_processing.strip_english_boilerplate` | `["Full message content is attached", "View full message", "Click here to view", "See attached", "Read more at", "For mor...` | `CLOUD_DOG__LLM__POST_PROCESSING__STRIP_ENGLISH_BOILERPLATE` | Configuration value for llm post processing strip english boilerplate. |
| `llm.model_prompts.granite4_tiny_h.summarization_prompt_template` | `You are a summarization engine. Output ONLY the summary text....` | `CLOUD_DOG__LLM__MODEL_PROMPTS__GRANITE4_TINY_H__SUMMARIZATION_PROMPT_TEMPLATE` | Configuration value for llm model prompts granite4 tiny h summarization prompt template. |
| `llm.model_prompts.granite4_tiny_h.language_instruction_template` | `ABSOLUTE RULE: Every single word of your response MUST be in ...` | `CLOUD_DOG__LLM__MODEL_PROMPTS__GRANITE4_TINY_H__LANGUAGE_INSTRUCTION_TEMPLATE` | Configuration value for llm model prompts granite4 tiny h language instruction template. |

## `log`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `log.level` | `INFO` | `CLOUD_DOG__LOG__LEVEL` | Configuration value for log level. |
| `log.format` | `standard` | `CLOUD_DOG__LOG__FORMAT` | Configuration value for log format. |
| `log.console` | `true` | `CLOUD_DOG__LOG__CONSOLE` | Configuration value for log console. |
| `log.service_instance` | `${HOSTNAME:notification-agent-local}` | `CLOUD_DOG__LOG__SERVICE_INSTANCE` | Configuration value for log service instance. |
| `log.environment` | `${CLOUD_DOG_ENVIRONMENT:dev}` | `CLOUD_DOG__LOG__ENVIRONMENT` | Configuration value for log environment. |
| `log.dump_config` | `false` | `CLOUD_DOG__LOG__DUMP_CONFIG` | Configuration value for log dump config. |
| `log.api_server_log` | `./logs/api_server.log` | `CLOUD_DOG__LOG__API_SERVER_LOG` | Credential or authentication setting for the related subsystem. |
| `log.web_server_log` | `./logs/web_server.log` | `CLOUD_DOG__LOG__WEB_SERVER_LOG` | Configuration value for log web server log. |
| `log.web_access_log` | `./logs/web_access.log` | `CLOUD_DOG__LOG__WEB_ACCESS_LOG` | Configuration value for log web access log. |
| `log.mcp_server_log` | `./logs/mcp_server.log` | `CLOUD_DOG__LOG__MCP_SERVER_LOG` | Configuration value for log mcp server log. |
| `log.a2a_server_log` | `./logs/a2a_server.log` | `CLOUD_DOG__LOG__A2A_SERVER_LOG` | Configuration value for log a2a server log. |
| `log.enable_access_log` | `false` | `CLOUD_DOG__LOG__ENABLE_ACCESS_LOG` | Configuration value for log enable access log. |
| `log.max_bytes` | `10485760` | `CLOUD_DOG__LOG__MAX_BYTES` | Configuration value for log max bytes. |
| `log.backup_count` | `10` | `CLOUD_DOG__LOG__BACKUP_COUNT` | Configuration value for log backup count. |
| `log.compress` | `true` | `CLOUD_DOG__LOG__COMPRESS` | Configuration value for log compress. |
| `log.rotation_type` | `size` | `CLOUD_DOG__LOG__ROTATION_TYPE` | Configuration value for log rotation type. |
| `log.retention_days` | `30` | `CLOUD_DOG__LOG__RETENTION_DAYS` | Configuration value for log retention days. |
| `log.retention.hot_days` | `14` | `CLOUD_DOG__LOG__RETENTION__HOT_DAYS` | Configuration value for log retention hot days. |
| `log.retention.cold_days` | `60` | `CLOUD_DOG__LOG__RETENTION__COLD_DAYS` | Configuration value for log retention cold days. |
| `log.retention.archive_format` | `gz` | `CLOUD_DOG__LOG__RETENTION__ARCHIVE_FORMAT` | Configuration value for log retention archive format. |
| `log.integrity.enabled` | `true` | `CLOUD_DOG__LOG__INTEGRITY__ENABLED` | Toggle for log integrity. |
| `log.integrity.interval_seconds` | `300` | `CLOUD_DOG__LOG__INTEGRITY__INTERVAL_SECONDS` | Timeout or duration control for log integrity interval. |
| `log.integrity.log_file` | `./logs/audit-integrity.log` | `CLOUD_DOG__LOG__INTEGRITY__LOG_FILE` | Configuration value for log integrity log file. |
| `log.integrity.hash_algorithm` | `sha256` | `CLOUD_DOG__LOG__INTEGRITY__HASH_ALGORITHM` | Configuration value for log integrity hash algorithm. |
| `log.rotation.mode` | `size` | `CLOUD_DOG__LOG__ROTATION__MODE` | Configuration value for log rotation mode. |
| `log.rotation.max_bytes` | `10485760` | `CLOUD_DOG__LOG__ROTATION__MAX_BYTES` | Configuration value for log rotation max bytes. |
| `log.rotation.backup_count` | `10` | `CLOUD_DOG__LOG__ROTATION__BACKUP_COUNT` | Configuration value for log rotation backup count. |
| `log.rotation.when` | `midnight` | `CLOUD_DOG__LOG__ROTATION__WHEN` | Configuration value for log rotation when. |
| `log.rotation.interval` | `1` | `CLOUD_DOG__LOG__ROTATION__INTERVAL` | Configuration value for log rotation interval. |
| `log.rotation.compress` | `true` | `CLOUD_DOG__LOG__ROTATION__COMPRESS` | Configuration value for log rotation compress. |

## `mcp_server`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `mcp_server.enabled` | `true` | `CLOUD_DOG__MCP_SERVER__ENABLED` | Toggle for mcp server. |
| `mcp_server.transport` | `-` | `CLOUD_DOG__MCP_SERVER__TRANSPORT` | Configuration value for mcp server transport. |
| `mcp_server.base_url` | `-` | `CLOUD_DOG__MCP_SERVER__BASE_URL` | Endpoint or connection URL for mcp server base. |
| `mcp_server.base_path` | `-` | `CLOUD_DOG__MCP_SERVER__BASE_PATH` | Configuration value for mcp server base path. |
| `mcp_server.port` | `-` | `CLOUD_DOG__MCP_SERVER__PORT` | Port for mcp server connections. |
| `mcp_server.host` | `-` | `CLOUD_DOG__MCP_SERVER__HOST` | Host binding or upstream host for mcp server. |
| `mcp_server.protocol_version` | `2024-11-05` | `CLOUD_DOG__MCP_SERVER__PROTOCOL_VERSION` | Configuration value for mcp server protocol version. |
| `mcp_server.max_startup_retries` | `3` | `CLOUD_DOG__MCP_SERVER__MAX_STARTUP_RETRIES` | Configuration value for mcp server max startup retries. |
| `mcp_server.name` | `-` | `CLOUD_DOG__MCP_SERVER__NAME` | Configuration value for mcp server name. |
| `mcp_server.version` | `-` | `CLOUD_DOG__MCP_SERVER__VERSION` | Configuration value for mcp server version. |
| `mcp_server.tls` | `false` | `CLOUD_DOG__MCP_SERVER__TLS` | Configuration value for mcp server tls. |
| `mcp_server.api_base_url` | `-` | `CLOUD_DOG__MCP_SERVER__API_BASE_URL` | Credential or authentication setting for the related subsystem. |
| `mcp_server.api_key` | `-` | `CLOUD_DOG__MCP_SERVER__API_KEY` | Credential or authentication setting for the related subsystem. |
| `mcp_server.request_timeout` | `60` | `CLOUD_DOG__MCP_SERVER__REQUEST_TIMEOUT` | Timeout or duration control for mcp server request. |
| `mcp_server.max_concurrent_requests` | `5` | `CLOUD_DOG__MCP_SERVER__MAX_CONCURRENT_REQUESTS` | Configuration value for mcp server max concurrent requests. |
| `mcp_server.client_api_key` | `-` | `CLOUD_DOG__MCP_SERVER__CLIENT_API_KEY` | Credential or authentication setting for the related subsystem. |
| `mcp_server.session_ttl_seconds` | `3600` | `CLOUD_DOG__MCP_SERVER__SESSION_TTL_SECONDS` | Timeout or duration control for mcp server session ttl. |
| `mcp_server.streamable_http_path` | `/mcp` | `CLOUD_DOG__MCP_SERVER__STREAMABLE_HTTP_PATH` | Configuration value for mcp server streamable http path. |
| `mcp_server.jsonrpc_path` | `/messages` | `CLOUD_DOG__MCP_SERVER__JSONRPC_PATH` | Configuration value for mcp server jsonrpc path. |
| `mcp_server.legacy_sse_path` | `/sse` | `CLOUD_DOG__MCP_SERVER__LEGACY_SSE_PATH` | Configuration value for mcp server legacy sse path. |
| `mcp_server.legacy_sse_message_path` | `/message` | `CLOUD_DOG__MCP_SERVER__LEGACY_SSE_MESSAGE_PATH` | Configuration value for mcp server legacy sse message path. |
| `mcp_server.async_jobs_enabled` | `false` | `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_ENABLED` | Toggle for mcp server async jobs. |
| `mcp_server.async_jobs_status_path` | `/jobs/{job_id}` | `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_STATUS_PATH` | Configuration value for mcp server async jobs status path. |
| `mcp_server.async_jobs_timeout_seconds` | `900` | `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_TIMEOUT_SECONDS` | Timeout or duration control for mcp server async jobs timeout. |
| `mcp_server.async_jobs_poll_interval_seconds` | `2` | `CLOUD_DOG__MCP_SERVER__ASYNC_JOBS_POLL_INTERVAL_SECONDS` | Timeout or duration control for mcp server async jobs poll interval. |

## `messages`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `messages.base_url` | `-` | `CLOUD_DOG__MESSAGES__BASE_URL` | Endpoint or connection URL for messages base. |
| `messages.header_templates.default` | `Message #{message_id} | Job #{job_id}` | `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__DEFAULT` | Configuration value for messages header templates default. |
| `messages.header_templates.with_guid` | `Message #{message_id} ({message_guid}) | Job #{job_id}` | `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__WITH_GUID` | Configuration value for messages header templates with guid. |
| `messages.header_templates.simple` | `Notification #{message_id}` | `CLOUD_DOG__MESSAGES__HEADER_TEMPLATES__SIMPLE` | Configuration value for messages header templates simple. |
| `messages.link_labels.view_full_message` | `View full message` | `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_FULL_MESSAGE` | Configuration value for messages link labels view full message. |
| `messages.link_labels.view_source_message` | `View source message` | `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_SOURCE_MESSAGE` | Configuration value for messages link labels view source message. |
| `messages.link_labels.view_pdf` | `PDF version` | `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_PDF` | Configuration value for messages link labels view pdf. |
| `messages.link_labels.view_message_center` | `View in message center` | `CLOUD_DOG__MESSAGES__LINK_LABELS__VIEW_MESSAGE_CENTER` | Configuration value for messages link labels view message center. |
| `messages.link_labels.characters` | `characters` | `CLOUD_DOG__MESSAGES__LINK_LABELS__CHARACTERS` | Configuration value for messages link labels characters. |
| `messages.link_labels.znaków` | `znaków` | `CLOUD_DOG__MESSAGES__LINK_LABELS__ZNAKÓW` | Configuration value for messages link labels znaków. |
| `messages.link_labels.Zeichen` | `Zeichen` | `CLOUD_DOG__MESSAGES__LINK_LABELS__ZEICHEN` | Configuration value for messages link labels Zeichen. |
| `messages.link_labels.字符` | `字符` | `CLOUD_DOG__MESSAGES__LINK_LABELS__字符` | Configuration value for messages link labels 字符. |
| `messages.link_labels.أحرف` | `أحرف` | `CLOUD_DOG__MESSAGES__LINK_LABELS__أحرف` | Configuration value for messages link labels أحرف. |

## `observability`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `observability.metrics_enabled` | `true` | `CLOUD_DOG__OBSERVABILITY__METRICS_ENABLED` | Toggle for observability metrics. |
| `observability.tracing_enabled` | `false` | `CLOUD_DOG__OBSERVABILITY__TRACING_ENABLED` | Toggle for observability tracing. |
| `observability.health_check_interval_seconds` | `30` | `CLOUD_DOG__OBSERVABILITY__HEALTH_CHECK_INTERVAL_SECONDS` | Timeout or duration control for observability health check interval. |

## `queue`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `queue.backend` | `sql` | `CLOUD_DOG__QUEUE__BACKEND` | Configuration value for queue backend. |
| `queue.sql_database_url` | `-` | `CLOUD_DOG__QUEUE__SQL_DATABASE_URL` | Endpoint or connection URL for queue sql database. |
| `queue.redis_url` | `-` | `CLOUD_DOG__QUEUE__REDIS_URL` | Endpoint or connection URL for queue redis. |
| `queue.redis_key_prefix` | `cloud_dog_notify_jobs` | `CLOUD_DOG__QUEUE__REDIS_KEY_PREFIX` | Credential or authentication setting for the related subsystem. |
| `queue.default_ttl_hours` | `24` | `CLOUD_DOG__QUEUE__DEFAULT_TTL_HOURS` | Configuration value for queue default ttl hours. |
| `queue.max_retries` | `5` | `CLOUD_DOG__QUEUE__MAX_RETRIES` | Configuration value for queue max retries. |
| `queue.backoff_base_seconds` | `2` | `CLOUD_DOG__QUEUE__BACKOFF_BASE_SECONDS` | Timeout or duration control for queue backoff base. |
| `queue.backoff_max_seconds` | `3600` | `CLOUD_DOG__QUEUE__BACKOFF_MAX_SECONDS` | Timeout or duration control for queue backoff max. |
| `queue.worker_poll_interval_seconds` | `5` | `CLOUD_DOG__QUEUE__WORKER_POLL_INTERVAL_SECONDS` | Timeout or duration control for queue worker poll interval. |
| `queue.worker_batch_size` | `10` | `CLOUD_DOG__QUEUE__WORKER_BATCH_SIZE` | Configuration value for queue worker batch size. |
| `queue.sending_timeout_seconds` | `600` | `CLOUD_DOG__QUEUE__SENDING_TIMEOUT_SECONDS` | Timeout or duration control for queue sending timeout. |
| `queue.watchdog.formatting_stuck_minutes_null_payload` | `5` | `CLOUD_DOG__QUEUE__WATCHDOG__FORMATTING_STUCK_MINUTES_NULL_PAYLOAD` | Configuration value for queue watchdog formatting stuck minutes null payload. |
| `queue.watchdog.formatting_stuck_minutes_with_payload` | `10` | `CLOUD_DOG__QUEUE__WATCHDOG__FORMATTING_STUCK_MINUTES_WITH_PAYLOAD` | Configuration value for queue watchdog formatting stuck minutes with payload. |
| `queue.watchdog.sending_stuck_minutes` | `10` | `CLOUD_DOG__QUEUE__WATCHDOG__SENDING_STUCK_MINUTES` | Configuration value for queue watchdog sending stuck minutes. |

## `rate_limit`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `rate_limit.per_channel_per_minute` | `600` | `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_MINUTE` | Configuration value for rate limit per channel per minute. |
| `rate_limit.per_channel_per_hour` | `10000` | `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_HOUR` | Configuration value for rate limit per channel per hour. |
| `rate_limit.per_channel_per_day` | `100000` | `CLOUD_DOG__RATE_LIMIT__PER_CHANNEL_PER_DAY` | Configuration value for rate limit per channel per day. |
| `rate_limit.per_destination_per_minute` | `60` | `CLOUD_DOG__RATE_LIMIT__PER_DESTINATION_PER_MINUTE` | Configuration value for rate limit per destination per minute. |
| `rate_limit.per_destination_per_hour` | `500` | `CLOUD_DOG__RATE_LIMIT__PER_DESTINATION_PER_HOUR` | Configuration value for rate limit per destination per hour. |

## `retention`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `retention.messages_days` | `30` | `CLOUD_DOG__RETENTION__MESSAGES_DAYS` | Configuration value for retention messages days. |
| `retention.deliveries_days` | `30` | `CLOUD_DOG__RETENTION__DELIVERIES_DAYS` | Configuration value for retention deliveries days. |
| `retention.receipts_days` | `30` | `CLOUD_DOG__RETENTION__RECEIPTS_DAYS` | Configuration value for retention receipts days. |
| `retention.logs_days` | `30` | `CLOUD_DOG__RETENTION__LOGS_DAYS` | Configuration value for retention logs days. |
| `retention.audit_events_days` | `90` | `CLOUD_DOG__RETENTION__AUDIT_EVENTS_DAYS` | Configuration value for retention audit events days. |

## `storage`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `storage.backend` | `-` | `CLOUD_DOG__STORAGE__BACKEND` | Configuration value for storage backend. |
| `storage.local.base_path` | `-` | `CLOUD_DOG__STORAGE__LOCAL__BASE_PATH` | Configuration value for storage local base path. |
| `storage.local.base_url` | `-` | `CLOUD_DOG__STORAGE__LOCAL__BASE_URL` | Endpoint or connection URL for storage local base. |
| `storage.s3.endpoint` | `-` | `CLOUD_DOG__STORAGE__S3__ENDPOINT` | Configuration value for storage s3 endpoint. |
| `storage.s3.bucket` | `notification` | `CLOUD_DOG__STORAGE__S3__BUCKET` | Configuration value for storage s3 bucket. |
| `storage.s3.access_key` | `-` | `CLOUD_DOG__STORAGE__S3__ACCESS_KEY` | Credential or authentication setting for the related subsystem. |
| `storage.s3.secret_key` | `-` | `CLOUD_DOG__STORAGE__S3__SECRET_KEY` | Credential or authentication setting for the related subsystem. |
| `storage.s3.region` | `-` | `CLOUD_DOG__STORAGE__S3__REGION` | Configuration value for storage s3 region. |
| `storage.webdav.url` | `-` | `CLOUD_DOG__STORAGE__WEBDAV__URL` | Endpoint or connection URL for storage webdav. |
| `storage.webdav.username` | `-` | `CLOUD_DOG__STORAGE__WEBDAV__USERNAME` | Configuration value for storage webdav username. |
| `storage.webdav.password` | `-` | `CLOUD_DOG__STORAGE__WEBDAV__PASSWORD` | Credential or authentication setting for the related subsystem. |
| `storage.ftp.host` | `-` | `CLOUD_DOG__STORAGE__FTP__HOST` | Host binding or upstream host for storage ftp. |
| `storage.ftp.port` | `-` | `CLOUD_DOG__STORAGE__FTP__PORT` | Port for storage ftp connections. |
| `storage.ftp.username` | `-` | `CLOUD_DOG__STORAGE__FTP__USERNAME` | Configuration value for storage ftp username. |
| `storage.ftp.password` | `-` | `CLOUD_DOG__STORAGE__FTP__PASSWORD` | Credential or authentication setting for the related subsystem. |
| `storage.ftp.passive_mode` | `-` | `CLOUD_DOG__STORAGE__FTP__PASSIVE_MODE` | Configuration value for storage ftp passive mode. |

## `test`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `test.email_domain` | `@cloud-dog.net` | `CLOUD_DOG__TEST__EMAIL_DOMAIN` | Configuration value for test email domain. |
| `test.default_sms_channel` | `sms_default` | `CLOUD_DOG__TEST__DEFAULT_SMS_CHANNEL` | Configuration value for test default sms channel. |
| `test.media.image_url` | `https://example.com/test-image.png` | `CLOUD_DOG__TEST__MEDIA__IMAGE_URL` | Endpoint or connection URL for test media image. |
| `test.media.http_image_url` | `http://example.com/test.png` | `CLOUD_DOG__TEST__MEDIA__HTTP_IMAGE_URL` | Endpoint or connection URL for test media http image. |
| `test.media.https_image_url` | `https://example.com/test.png` | `CLOUD_DOG__TEST__MEDIA__HTTPS_IMAGE_URL` | Endpoint or connection URL for test media https image. |
| `test.webhook.slack_url` | `https://hooks.slack.com/services/T000/B000/XXXX` | `CLOUD_DOG__TEST__WEBHOOK__SLACK_URL` | Endpoint or connection URL for test webhook slack. |
| `test.webhook.local_url` | `http://localhost:9999/webhook` | `CLOUD_DOG__TEST__WEBHOOK__LOCAL_URL` | Endpoint or connection URL for test webhook local. |
| `test.webhook.example_url` | `https://example.com/webhook` | `CLOUD_DOG__TEST__WEBHOOK__EXAMPLE_URL` | Endpoint or connection URL for test webhook example. |
| `test.webhook.invalid_url` | `not-a-url` | `CLOUD_DOG__TEST__WEBHOOK__INVALID_URL` | Endpoint or connection URL for test webhook invalid. |
| `test.webhook.invalid_scheme_url` | `ftp://example.com` | `CLOUD_DOG__TEST__WEBHOOK__INVALID_SCHEME_URL` | Endpoint or connection URL for test webhook invalid scheme. |
| `test.webhook.bearer_token` | `-` | `CLOUD_DOG__TEST__WEBHOOK__BEARER_TOKEN` | Credential or authentication setting for the related subsystem. |
| `test.performance.channel` | `loopback_test` | `CLOUD_DOG__TEST__PERFORMANCE__CHANNEL` | Configuration value for test performance channel. |
| `test.performance.iterations` | `10` | `CLOUD_DOG__TEST__PERFORMANCE__ITERATIONS` | Configuration value for test performance iterations. |
| `test.performance.p95_threshold_ms` | `500` | `CLOUD_DOG__TEST__PERFORMANCE__P95_THRESHOLD_MS` | Configuration value for test performance p95 threshold ms. |
| `test.performance.inter_request_delay_ms` | `500` | `CLOUD_DOG__TEST__PERFORMANCE__INTER_REQUEST_DELAY_MS` | Configuration value for test performance inter request delay ms. |
| `test.performance.skip_sqlite` | `true` | `CLOUD_DOG__TEST__PERFORMANCE__SKIP_SQLITE` | Configuration value for test performance skip sqlite. |
| `test.at15.max_wait` | `600` | `CLOUD_DOG__TEST__AT15__MAX_WAIT` | Configuration value for test at15 max wait. |
| `test.at15.poll_interval` | `2.0` | `CLOUD_DOG__TEST__AT15__POLL_INTERVAL` | Configuration value for test at15 poll interval. |
| `test.at15.subject_template` | `AT1.5 Test: {source}->{target} ({size} chars, {format})` | `CLOUD_DOG__TEST__AT15__SUBJECT_TEMPLATE` | Configuration value for test at15 subject template. |
| `test.at15.scenarios` | `[{"source": "en", "target": "fr", "size": 400, "format": "html", "id": "default_en_fr_400_html"}]` | `CLOUD_DOG__TEST__AT15__SCENARIOS` | Configuration value for test at15 scenarios. |
| `test.at15.negative.max_wait` | `60` | `CLOUD_DOG__TEST__AT15__NEGATIVE__MAX_WAIT` | Configuration value for test at15 negative max wait. |
| `test.at15.negative.scenarios` | `[{"id": "missing_destination", "description": "Missing destination should fail at API validation", "remove_destination":...` | `CLOUD_DOG__TEST__AT15__NEGATIVE__SCENARIOS` | Configuration value for test at15 negative scenarios. |
| `test.at15.smtp_variants` | `[{"id": "port_25_plain", "description": "Port 25 - Plain SMTP", "port": 25, "use_tls": false, "use_starttls": false}]` | `CLOUD_DOG__TEST__AT15__SMTP_VARIANTS` | Configuration value for test at15 smtp variants. |
| `test.at15.personalised.scenarios` | `[{"language": "fr", "content_style": "html", "description": "French HTML"}]` | `CLOUD_DOG__TEST__AT15__PERSONALISED__SCENARIOS` | Configuration value for test at15 personalised scenarios. |
| `test.at14d.summary_size` | `400` | `CLOUD_DOG__TEST__AT14D__SUMMARY_SIZE` | Configuration value for test at14d summary size. |
| `test.at14d.summary_tolerance` | `0.4` | `CLOUD_DOG__TEST__AT14D__SUMMARY_TOLERANCE` | Configuration value for test at14d summary tolerance. |
| `test.at14d.max_wait` | `600` | `CLOUD_DOG__TEST__AT14D__MAX_WAIT` | Configuration value for test at14d max wait. |
| `test.at14d.pdf_min_size_ratio` | `0.5` | `CLOUD_DOG__TEST__AT14D__PDF_MIN_SIZE_RATIO` | Configuration value for test at14d pdf min size ratio. |
| `test.at14d.format` | `pdf` | `CLOUD_DOG__TEST__AT14D__FORMAT` | Configuration value for test at14d format. |
| `test.at14d.generate_pdf` | `true` | `CLOUD_DOG__TEST__AT14D__GENERATE_PDF` | Configuration value for test at14d generate pdf. |
| `test.at14g.summary_size` | `400` | `CLOUD_DOG__TEST__AT14G__SUMMARY_SIZE` | Configuration value for test at14g summary size. |
| `test.at14g.summary_tolerance` | `0.4` | `CLOUD_DOG__TEST__AT14G__SUMMARY_TOLERANCE` | Configuration value for test at14g summary tolerance. |
| `test.at14g.full_size_tolerance` | `0.3` | `CLOUD_DOG__TEST__AT14G__FULL_SIZE_TOLERANCE` | Configuration value for test at14g full size tolerance. |
| `test.at14g.max_wait` | `600` | `CLOUD_DOG__TEST__AT14G__MAX_WAIT` | Configuration value for test at14g max wait. |
| `test.at14g.pdf_min_size_ratio` | `0.5` | `CLOUD_DOG__TEST__AT14G__PDF_MIN_SIZE_RATIO` | Configuration value for test at14g pdf min size ratio. |
| `test.at14g.format` | `pdf` | `CLOUD_DOG__TEST__AT14G__FORMAT` | Configuration value for test at14g format. |
| `test.at14g.generate_pdf` | `true` | `CLOUD_DOG__TEST__AT14G__GENERATE_PDF` | Configuration value for test at14g generate pdf. |

## `web_server`

| Key | Default | Environment Override | Description |
|-----|---------|----------------------|-------------|
| `web_server.enabled` | `true` | `CLOUD_DOG__WEB_SERVER__ENABLED` | Toggle for web server. |
| `web_server.host` | `-` | `CLOUD_DOG__WEB_SERVER__HOST` | Host binding or upstream host for web server. |
| `web_server.port` | `-` | `CLOUD_DOG__WEB_SERVER__PORT` | Port for web server connections. |
| `web_server.base_path` | `-` | `CLOUD_DOG__WEB_SERVER__BASE_PATH` | Configuration value for web server base path. |
| `web_server.max_startup_retries` | `3` | `CLOUD_DOG__WEB_SERVER__MAX_STARTUP_RETRIES` | Configuration value for web server max startup retries. |
| `web_server.username` | `-` | `CLOUD_DOG__WEB_SERVER__USERNAME` | Configuration value for web server username. |
| `web_server.password` | `-` | `CLOUD_DOG__WEB_SERVER__PASSWORD` | Credential or authentication setting for the related subsystem. |
| `web_server.base_url` | `-` | `CLOUD_DOG__WEB_SERVER__BASE_URL` | Endpoint or connection URL for web server base. |
| `web_server.api_base_url` | `-` | `CLOUD_DOG__WEB_SERVER__API_BASE_URL` | Credential or authentication setting for the related subsystem. |
| `web_server.session_max_age` | `-` | `CLOUD_DOG__WEB_SERVER__SESSION_MAX_AGE` | Configuration value for web server session max age. |
| `web_server.session_timeout` | `-` | `CLOUD_DOG__WEB_SERVER__SESSION_TIMEOUT` | Timeout or duration control for web server session. |
| `web_server.cors_origins` | `[]` | `CLOUD_DOG__WEB_SERVER__CORS_ORIGINS` | Configuration value for web server cors origins. |
| `web_server.status_refresh_interval` | `10000` | `CLOUD_DOG__WEB_SERVER__STATUS_REFRESH_INTERVAL` | Configuration value for web server status refresh interval. |
| `web_server.jobs_refresh_interval` | `10000` | `CLOUD_DOG__WEB_SERVER__JOBS_REFRESH_INTERVAL` | Configuration value for web server jobs refresh interval. |
| `web_server.connection_check_interval` | `5000` | `CLOUD_DOG__WEB_SERVER__CONNECTION_CHECK_INTERVAL` | Configuration value for web server connection check interval. |
