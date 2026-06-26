# Test Scope Map — notification-agent-mcp-server

## Source to test mapping

Note: this project keeps legacy tiers under `tests/` as well as standards checks under `tests/`.

| Source module | QT | UT | ST | IT | AT |
|--------------|----|----|----|----|-----|
| `src/core/llm/llm_manager.py` | `tests/quality/QT*`, `tests/quality/QT*` | `tests/unit/UT1.5_LLMFormatter`, `tests/unit/UT1.6_LLMManager` | `tests/system/ST1.2_LLMQueueStatus`, `tests/system/ST1.18_LLMFunctionality` | `tests/integration/IT1.9_DeliveriesComprehensive` | `tests/application/AT1.5_FrenchSummary`, `tests/application/AT1.7_Translation` |
| `src/adapters/smtp_adapter.py` | `tests/quality/QT*`, `tests/quality/QT*` | `tests/unit/UT1.4_ChannelAdapters` | `tests/system/ST1.15_Availability` | `tests/integration/IT1.9_DeliveriesComprehensive` | `tests/application/AT1.1_EmailComprehensive`, `AT1.3_EmailAttachments`, `AT1.17_EmailValidation` |
| `src/core/storage/storage_manager.py` | `tests/quality/QT*`, `tests/quality/QT*` | `tests/unit/UT1.13_StorageManager` | `tests/system/ST1.4_StorageSystem` | `tests/integration/IT1.17_PDFIntegration` | `tests/application/AT1.25_StorageOutputChannel`, `AT1.29_StorageApplication` |
| `src/core/formatters/pdf_generator.py` | `tests/quality/QT*`, `tests/quality/QT*` | `tests/unit/UT1.14_PDFGenerator` | `tests/system/ST1.5_PDFSystem` | `tests/integration/IT1.17_PDFIntegration` | `tests/application/AT1.19_PDFGeneration`, `AT1.23_MultimediaPDF` |
| `src/core/media/media_processor.py` | — | `tests/unit/UT1.15_ImageHandler`, `UT1.16_AudioHandler`, `UT1.17_VideoHandler` | `tests/system/ST1.6_ImageSystem` | `tests/integration/IT1.17_PDFIntegration` | `tests/application/AT1.22_AudioVideoMedia`, `AT1.28_AudioVideoSupport` |
| `src/servers/api/api_server.py` | `tests/quality/QT*` | `tests/unit/UT1.1_ConfigurationSystem` | `tests/system/ST1.1_APIDocumentation`, `ST1.19_StartupServices` | `tests/integration/IT1.9_DeliveriesComprehensive` | `tests/application/AT1.4_Comprehensive`, `AT1.18_T26Comprehensive` |
| `src/core/resolvers/natural_language_parser.py` | — | `tests/unit/UT1.11_NaturalLanguageParser` | `tests/system/ST1.3_FormatConversion` | `tests/integration/IT1.9_DeliveriesComprehensive` | `tests/application/AT1.11_NaturalLanguage`, `AT1.14_NaturalLanguage` |
| `src/core/users/user_manager.py` | `tests/quality/QT*` | `tests/unit/UT1.8_UserManagement`, `UT1.10_GroupPersonalization` | `tests/system/ST1.16_Scalability` | `tests/integration/IT1.9_DeliveriesComprehensive` | `tests/application/AT1.9_UserManagementPersonalization`, `AT1.15_UserPreferences` |

## Scoped run examples

If you changed `src/core/llm/llm_manager.py`, run:

```bash
pytest tests/unit/UT1.5*/ tests/unit/UT1.6*/ tests/system/ST1.2*/ tests/system/ST1.18*/ tests/integration/IT1.9*/ tests/application/AT1.5*/ tests/application/AT1.7*/ -v
```

If you changed `src/core/storage/storage_manager.py`, run:

```bash
pytest tests/unit/UT1.13*/ tests/system/ST1.4*/ tests/integration/IT1.17*/ tests/application/AT1.25*/ tests/application/AT1.29*/ -v
```

If you changed `src/adapters/smtp_adapter.py`, run:

```bash
pytest tests/unit/UT1.4*/ tests/system/ST1.15*/ tests/integration/IT1.9*/ tests/application/AT1.1*/ tests/application/AT1.3*/ tests/application/AT1.17*/ -v
```

## W28E-1807A Stream-A refresh (2026-06-17)

Added source->test scope rows for the RBAC/audit/jobs/MCP/A2A surfaces consumed by the
UC inventory (ROLES-AND-USECASES.md) and the WebUI feedback trace (REQUIREMENTS.md).

| Source module | QT | UT | ST | IT | AT |
|--------------|----|----|----|----|-----|
| `src/core/rbac/` (IDAM resolver/cascade) | `tests/quality/QT*` | `tests/unit/UT1.62_FlatRoleLogin`, `UT1.60_UnauthAuthGate`, `UT1.61_AuthedNonAdminGate` | `tests/smoke/test_cascade_resolves.py` | `tests/integration/IT1.11_RBACIntegration` | `tests/application/AT_WEBUI_AdminCrud` |
| `src/core/audit/` (PS-40 audit log) | `tests/quality/QT_LoggingCompliance` | `tests/unit/UT_AuditLogFormat`, `UT1.12_LogFormatValidation` | — | — | `tests/application/AT_WEBUI_Forensic` |
| `src/core/job_manager.py` (PS-AJOBS) | `tests/quality/QT*` | `tests/unit/UT1.3_JobManager` | — | `tests/integration/IT1.23_MCP_AsyncJobs`, `IT1.25_AsyncMessageSubmission`, `IT1.8_AsyncMessageDelivery` | — |
| `src/servers/mcp/` | `tests/quality/QT*` | `tests/unit/UT1.22_MCPContracts` | — | `tests/integration/IT1.20_MCP_StreamableHTTP`, `IT1.21_MCP_HTTP_JSONRPC`, `IT1.24_MCP_Stdio` | — |
| `src/servers/a2a/` | `tests/quality/QT*` | — | — | `tests/integration/IT1.29_A2AInterfaceVerification` | — |
| `src/servers/web/` (channels/messages/deliveries/prompts/users/groups CRUD) | `tests/quality/QT*` | `tests/unit/UT1.21_AdminConfigCrud`, `UT1.9_GroupManagement` | — | `tests/integration/IT1.19_MessageManagement`, `IT1.9_DeliveriesComprehensive`, `IT1.27_DeliveryResendAbort` | `tests/application/AT_WEBUI_GroupChannelMessaging`, `AT_WEBUI_PromptManagement` |

Scoped-run rule unchanged: run the tiers in the touched source row before claiming a change is safe (RULES.md §5.8).
