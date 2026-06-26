---
template-id: T-REQ
template-version: 1.1
applies-to: docs/REQUIREMENTS.md
project: notification-agent-mcp-server
doc-last-updated: 2026-06-18T00:00:00Z
doc-git-commit: 8399d7e0ffce654e4712506a7bde80cb48fcdd17
doc-git-branch: main
doc-source-shas: []
doc-age-policy: indefinite
doc-conformance-stamp: 2026-06-17T00:00:00Z
authored-by: W28E-1807A Stream-A (NF-NNN canonical rows + WebUI feedback trace)
req-trace-version: 1.0
req-id-prefixes-used: [SV, BO, BR, FR, UC, CS, NF, R, F]
surface-coverage: [api, mcp, a2a, webui]
---

# Notification Agent MCP Server — REQUIREMENTS.md
## W28A-421 Review Status
- Reviewed for external/shareable publication during W28A-421.
- Source basis: `defaults.yaml`, 12 server source files, 226 discovered routes/endpoints, and 12 MCP tools.
- Internal-only absolute paths, environment-specific hosts, and private registries have been removed from this shareable document set.

Version: 0.4 • 2025-12-20

## Document Structure

This document follows the structure defined in RULES.md:
- **SV** = Scope/Vision (Section 1)
- **BO** = Business Goals/Objectives (Section 2)
- **BR** = Business/Application Requirements (Section 3)
- **FR** = Project/Functional Requirements/Features
- **UC** = Use Cases (Section 4)
- **CS** = Cyber Security (Section 5)
- **NF** = Non-Functional Requirements: Operational, Audit, Deployment (Section 6)

**Numbering Logic**: Each prefix restarts from 1.1 (e.g., SV1.1, SV1.2, BO1.1, BO1.2, BR1.1, BR1.2, FR1.1, FR1.2, UC1.1, UC1.2, CS1.1, NF1.1)

---

## 1. Scope/Vision (SV)

### SV1.1: System Overview
A multi-channel notification platform composed of four servers (API/REST, MCP, A2A, Web UI/Admin). It accepts requests to notify users across email (SMTP), SMS, WhatsApp, and generic chat (via REST). It formats content with an LLM, tracks confirmations (callbacks/receipts/polling), enforces quotas and TTL-based queuing, and offers rich admin/observability.

**Alignment**: [ARCH:OV1.1](ARCHITECTURE.md#ov11), [TASK:T1](TASKS.md#t1)

### SV1.2: In-Scope (v1)
- Channels: email (SMTP), SMS, WhatsApp, Chat via REST webhook/HTTP
- Content types: text, Markdown, JSON, media (binary) and arrays of these
- Delivery states: queued → formatting → sending → sent → accepted → delivered → read; soft/hard failures; ttl_expired
- Confirmations: callback webhooks, synchronous send receipts, polling
- LLM formatter with guardrails (length/markup rules, preferences, link strategy)
- Per-channel/per-destination quotas and error thresholds
- Default channel must be configured for service readiness
- **User Management**: Local users, LDAP/Keycloak integration, groups, preferences
- **Personalization**: Language preferences, channel preferences, keyword-based customization, LLM prompt selection
- **Destination Management**: Email addresses, SMS numbers, WhatsApp numbers, Slack/Teams individual notifications
- Local user auth (username/password/email) with admin role
- API key auth for API/MCP/A2A; session auth for Web UI
- Web UI: queue/jobs, messages/deliveries, channels, users, groups, status, logs/config

**Alignment**: [ARCH:SA1.1](ARCHITECTURE.md#sa11), [TASK:T2](TASKS.md#t2)

### SV1.3: Out-of-Scope (v1)
- Advanced journey orchestration; complex segmentation
- Push/mobile APNs/FCM adapters (planned v1.2)
- Full multi-tenant isolation

**Alignment**: [ARCH:OV1.1](ARCHITECTURE.md#ov11)

---

## 2. Business Goals/Objectives (BO)

### BO1.1: Reliable Delivery
Provide reliable, auditable delivery across multiple channels.

**Alignment**: [ARCH:RR1.1](ARCHITECTURE.md#rr11), [TASK:T12](TASKS.md#t12), [TEST:AT1.1](TESTS.md#at11)

### BO1.2: Broadcast and Personalised Sends
Support both broadcast and personalised notification sends.

**Alignment**: [ARCH:CC2.1.1](ARCHITECTURE.md#cc211), [TASK:T5](TASKS.md#t5), [TEST:AT1.2](TESTS.md#at12)

### BO1.3: LLM-Assisted Formatting
Provide LLM-assisted formatting per domain/channel/user.

**Alignment**: [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T8](TASKS.md#t8), [TEST:UT1.5](TESTS.md#ut15)

### BO1.4: Operational Controls
Provide clear operational controls (rate limits, circuit breakers, TTL, retries).

**Alignment**: [ARCH:CP1.1](ARCHITECTURE.md#cp11), [TASK:T12](TASKS.md#t12), [TEST:ST1.2](TESTS.md#st12)

### BO1.5: Admin Experience
Deliver first-class admin experience in Web UI.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:AT1.3](TESTS.md#at13)

### BO1.6: Code Reuse
Strong reuse of the existing SQL Agent MCP project patterns.

**Alignment**: [ARCH:DO1.1](ARCHITECTURE.md#do11), [TASK:T8](TASKS.md#t8)

---

## 3. Business/Application Requirements (BR)

### BR1.1: Multi-Channel Support
System shall support multiple notification channels (email, SMS, WhatsApp, Chat REST).

**Alignment**: [ARCH:CC5.1](ARCHITECTURE.md#cc51), [TASK:T6](TASKS.md#t6), [TEST:IT1.2](TESTS.md#it12)

### BR1.2: User Management
System shall provide comprehensive user management including local users, LDAP/Keycloak integration, groups, and preferences.

**Alignment**: [ARCH:CC3.1.1](ARCHITECTURE.md#cc311), [TASK:T16](TASKS.md#t16), [TASK:T17](TASKS.md#t17), [TEST:AT1.9](TESTS.md#at19)

### BR1.3: Personalization
System shall support personalization including language preferences, channel preferences, keyword-based customization, and LLM prompt selection.

**Alignment**: [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T8](TASKS.md#t8), [TASK:T20](TASKS.md#t20), [TEST:AT1.5](TESTS.md#at15)

---

## 4. Functional Requirements/Features (FR)

### FR1.1: Submission & Modes
System shall accept broadcast and personalised sends. Support idempotency keys, per-message TTL (default 24h). Optionally restrict to subset of channels; default channel required.

**Alignment**: [ARCH:AI1.1](ARCHITECTURE.md#ai11), [TASK:T9](TASKS.md#t9), [TEST:IT1.1](TESTS.md#it11), [TEST:IT1.3](TESTS.md#it13)

### FR1.2: Content & Templates
System shall accept raw content and/or template + variables. LLM formats content according to channel and user preferences (language, rich vs summary+link, timezone). For risky/limited channels, send summary + secure link (unguessable GUID) to full content.

**Alignment**: [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T8](TASKS.md#t8), [TASK:T20](TASKS.md#t20), [TEST:UT1.5](TESTS.md#ut15), [TEST:AT1.5](TESTS.md#at15)

### FR1.3: LLM Prompt Management
System shall provide LLM Prompt Management: Default prompts per channel type, with overrides for groups, languages, and keywords. Prompt Selection Logic: System selects prompt based on priority: explicit directive → user keyword → user language → group keyword → group language → channel default.

**Alignment**: [ARCH:CC4.1.2](ARCHITECTURE.md#cc412), [TASK:T18](TASKS.md#t18), [TEST:AT1.6](TESTS.md#at16), [TEST:AT1.10](TESTS.md#at110)

### FR1.4: Translation
System shall provide automatic translation based on user language preference.

**Alignment**: [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T15](TASKS.md#t15), [TEST:AT1.7](TESTS.md#at17)

### FR1.5: Channel Restrictions
System shall enforce channel-specific constraints (no images, max 140 chars, HTML format, etc.).

**Alignment**: [ARCH:CC5.1](ARCHITECTURE.md#cc51), [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T6](TASKS.md#t6), [TASK:T20](TASKS.md#t20), [TEST:UT1.5](TESTS.md#ut15)

### FR1.6: SMTP Channel Adapter
System shall support SMTP channel with from/reply-to, attachments, bounce handling.

**Alignment**: [ARCH:CC5.1.1](ARCHITECTURE.md#cc511), [TASK:T17](TASKS.md#t17), [TEST:AT1.17](TESTS.md#at117)

### FR1.7: SMS Channel Adapter
System shall support SMS via provider REST, unicode/length split, receipts.

**Alignment**: [ARCH:CC5.1.2](ARCHITECTURE.md#cc512), [TASK:T18](TASKS.md#t18), [TEST:IT1.6](TESTS.md#it16)

### FR1.8: WhatsApp Channel Adapter
System shall support WhatsApp with template IDs, media, fallbacks.

**Alignment**: [ARCH:CC5.1.3](ARCHITECTURE.md#cc513), [TASK:T19](TASKS.md#t19), [TEST:IT1.7](TESTS.md#it17)

### FR1.9: Chat REST Channel Adapter
System shall support Chat REST: Slack/Teams/Discord-like incoming webhooks or REST APIs.

**Alignment**: [ARCH:CC5.1.4](ARCHITECTURE.md#cc514), [TASK:T20](TASKS.md#t20), [TEST:IT1.8](TESTS.md#it18)

### FR1.10: Confirmations
System shall provide webhook endpoints per channel with signature verification. Poll providers when required. Maintain normalised states and timestamps (sent/accepted/delivered/read).

**Alignment**: [ARCH:CP2.1](ARCHITECTURE.md#cp21), [TASK:T7](TASKS.md#t7), [TEST:IT1.9](TESTS.md#it19)

### FR1.11: Reliability & Controls
System shall provide per-channel and per-destination rate limits (N per minute/hour/day). Circuit breaker: soft/hard error thresholds flip to degraded/unavailable. Backoff with jitter; categorise errors as transient/permanent. TTL expiry transitions pending jobs to `ttl_expired`.

**Alignment**: [ARCH:CP1.1](ARCHITECTURE.md#cp11), [TASK:T12](TASKS.md#t12), [TEST:ST1.2](TESTS.md#st12)

### FR1.12: Observability
System shall provide structured logs with redaction. Metrics: send_rate, delivery_rate, error_rate, retry_count, ttl_drops, queue_depth. Traces around adapter operations.

**Alignment**: [ARCH:MO1.1](ARCHITECTURE.md#mo11), [TASK:T33](TASKS.md#t33), [TEST:ST1.3](TESTS.md#st13)

### FR1.13: Web UI/Admin
System shall provide Web UI/Admin with: Queue/Jobs dashboard (filters, bulk actions). Messages & deliveries with receipts and audit. Channels CRUD (+enable/disable, test send, limits, preferences, restrictions). Users CRUD (admin only): password reset, preferences, destinations, group membership. Groups CRUD: Create/manage groups, assign preferences, keywords, language defaults. LLM Prompts Management: Create/edit prompts for channels, groups, languages, keywords. User Lookup: Search users by name, email, username; view destinations and preferences. LDAP/Keycloak Integration: Configure and sync external user sources. Status/metrics, logs/config (masked).

Additional Web UI requirements:
- **RBAC Enforcement**: Admin-only actions guarded by permissions (create/update/delete users, channels, groups, prompts).
- **Config Testing & Updates**: Provide config visibility plus admin-only config update endpoint (runtime, optional env persistence).
- **Message Management**: Review, cancel, resend, and inspect delivery metadata.
- **Prompt Generation**: Create language- and keyword-specific prompts for multi-language flows.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TASK:T23](TASKS.md#t23), [TASK:T24](TASKS.md#t24), [TEST:IT1.4](TESTS.md#it14), [TEST:IT1.5](TESTS.md#it15), [TEST:IT1.6](TESTS.md#it16), [TEST:IT1.7](TESTS.md#it17), [TEST:AT1.8](TESTS.md#at18)

### FR1.14: User Management & Personalization
System shall provide User Management & Personalization:
- **User Types**: System users (service accounts) and real users (people).
- **User Destinations**: Store email addresses, SMS numbers (E.164), WhatsApp numbers (E.164), Slack user IDs, Teams user IDs.
- **User Preferences**: Language preference (ISO 639-1 codes: en, fr, de, etc.), Preferred channel (email, SMS, WhatsApp, Slack, Teams), Content style preference (short, detailed, summary+link, rich), Timezone preference, Personalization keywords (tags that influence message structure/content).
- **Groups**: Users belong to one or more groups (many-to-many).
- **Group Preferences**: Groups can have default language, channel preferences, keywords.
- **LDAP/Keycloak Integration**: Pull user data from external sources (LDAP, Keycloak, corporate databases), Enhance remote data with local preferences/destinations, Merge strategy: remote data as base, local data as overrides/enhancements, Sync schedule: on-demand, scheduled, or real-time via webhooks.
- **User Lookup**: Fast lookup by username, email, or display name for MCP/A2A interfaces.

**Alignment**: [ARCH:CC3.1.1](ARCHITECTURE.md#cc311), [TASK:T16](TASKS.md#t16), [TASK:T17](TASKS.md#t17), [TASK:T19](TASKS.md#t19), [TEST:AT1.9](TESTS.md#at19)

### FR1.15: LLM Prompt Management
System shall provide LLM Prompt Management:
- **Default Prompts**: One default prompt per channel type (email, SMS, WhatsApp, Slack, Teams).
- **Group Prompts**: Override defaults for specific groups.
- **Language Prompts**: Override defaults for specific languages.
- **Keyword Prompts**: Override defaults for specific personalization keywords.
- **Combined Prompts**: Support for group+language, group+keyword, language+keyword combinations.
- **Prompt Selection Priority** (highest to lowest): Explicit prompt directive in message request, User keyword-specific prompt, User language-specific prompt, Group keyword-specific prompt, Group language-specific prompt, Channel default prompt.
- **Prompt Variables**: Support for user context, message content, channel restrictions, etc.

**Alignment**: [ARCH:CC4.1.2](ARCHITECTURE.md#cc412), [TASK:T18](TASKS.md#t18), [TEST:AT1.10](TESTS.md#at110)

### FR1.16: Channel Preferences & Restrictions
System shall provide Channel Preferences & Restrictions:
- **Channel Preferences**: Language defaults, content style hints.
- **Channel Restrictions**: Max length (e.g., SMS: 140 chars, Twitter: 280 chars), Allowed formats (text, HTML, Markdown, JSON, media), Media restrictions (no images, max image size, allowed MIME types), Link strategy (inline, summary+link, no links).
- **Restriction Enforcement**: LLM formatter must respect restrictions when generating content.

**Alignment**: [ARCH:CC5.1](ARCHITECTURE.md#cc51), [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T6](TASKS.md#t6), [TASK:T8](TASKS.md#t8), [TASK:T20](TASKS.md#t20), [TEST:UT1.5](TESTS.md#ut15)

### FR1.17: MCP/A2A Interface Enhancements
System shall provide MCP/A2A Interface Enhancements:
- **Natural Language Commands**: "Send a notification to Fred that JOB XXXX has finished", "Send all the results to the Admin Users", "Send a Personalised Message on the latest News summarised and personalised for each user".
- **User Resolution**: Resolve "Fred" to user record, retrieve preferences, destinations, group memberships.
- **Group Resolution**: Resolve "Admin Users" to group, expand to member list.
- **Automatic Personalization**: Apply user preferences, select appropriate channel, format with correct prompt, translate if needed.

**Alignment**: [ARCH:CC1.1.3](ARCHITECTURE.md#cc113), [ARCH:CC1.1.4](ARCHITECTURE.md#cc114), [ARCH:AI1.2](ARCHITECTURE.md#ai12), [ARCH:AI1.3](ARCHITECTURE.md#ai13), [TASK:T11](TASKS.md#t11), [TASK:T21](TASKS.md#t21), [TEST:AT1.11](TESTS.md#at111), [TEST:AT1.14](TESTS.md#at114)

### FR1.18: PDF Output & Generation
System shall provide PDF output and generation capabilities:
- **PDF Generation**: Generate PDF documents from formatted content (text, Markdown, HTML) with optional stylesheet attachment for rendering using WeasyPrint for proper Unicode, RTL, and CSS support.
- **Channel & User Preferences**: Support PDF delivery preference at both channel and user level. When PDF preference is set, system generates PDF from formatted content.
- **Delivery Methods**:
  - **Email/Slack Channels**: PDF sent as attachment to the message.
  - **Other Channels**: PDF stored in notification storage, user receives link to view/download document.
- **Stylesheet Support**: Optional application-level stylesheet (CSS) for Markdown-to-PDF rendering, allowing custom formatting and branding.
- **Format Support**: PDF generation supports text, Markdown, and HTML input formats with proper conversion.
- **Language Support**: PDF generation respects user language preferences and applies translation before PDF generation. Supports:
  - **RTL Languages**: Arabic, Hebrew with proper right-to-left text flow and alignment.
  - **CJK Languages**: Chinese, Japanese, Korean with appropriate font support.
  - **Latin Scripts**: English, German, French, Polish, Spanish, Italian with proper character rendering.
  - **Numbered Lists**: Post-processing to restore numbered lists that LLMs may convert to ordinals (supports 10 languages: EN, DE, FR, ES, IT, PL, RU, ZH, AR, numeric styles).
- **Summary Support**: PDF generation respects content style preferences (short, detailed, summary+link) and generates appropriate PDF content.
- **LLM Integration**: Handles LLM quirks transparently:
  - **Thinking Mode**: Strips `<think>` tags from LLM responses (Qwen3 model compatibility).
  - **Timeouts**: Configurable timeouts for translation (default 900s), formatting (default 600s), and summarization (default 600s).
  - **Script correctness**: For RTL/CJK targets, translated content MUST be produced in the target language’s native script (not Latin-only “leakage” or transliteration), including for PDF-only flows.

**Alignment**: [ARCH:CC5.2](ARCHITECTURE.md#cc52), [ARCH:CC6.1.2](ARCHITECTURE.md#cc612), [TASK:T29](TASKS.md#t29), [TEST:AT1.19](TESTS.md#at119), [TEST:AT1.4_Comprehensive](TESTS.md#at14_comprehensive)

### FR1.19: Multi-Media Support
System shall provide embedded and referenced multi-media support:
- **Image Support**: Support PNG, GIF, JPEG image formats in notifications.
- **Audio Support**: Support common audio formats (MP3, WAV, OGG, AAC) in notifications.
- **Video Support**: Support common video formats (MP4, WebM, OGV, AVI) in notifications.
- **Transfer Methods**:
  - **UUEncoded Media**: Images, audio, and video can be UUEncoded and embedded directly in messages. UUEncoded media is saved to local storage.
  - **URI References**: Media can be referenced via URIs (HTTP/HTTPS URLs or local file system paths).
- **Media Handling Options**:
  - **Render into PDF**: Images referenced or embedded can be rendered directly into PDF documents. Audio/video references included as links in PDF.
  - **Embed in HTML**: Images, audio, and video can be embedded in HTML pages with proper tags and references.
  - **Reference in MD/TXT**: Media can be referenced in Markdown or text formats with appropriate syntax.
  - **Attach as Separate Link/File**: Media can be attached as separate files or links depending on channel capabilities.
- **Storage Strategy**:
  - **Channel-Level Duplication Setting**: Channels can be configured to duplicate all external media references to local storage.
  - **Local Cache Option**: System can copy referenced media to local cache/storage and serve from local cache.
  - **Remote URL Option**: System can serve media from original/remote URL (when duplication disabled).
  - **Storage Location**: Media stored in notification storage with appropriate access controls and organized by type (images/, audio/, video/).
  - **Selective Duplication**: System supports per-media-type duplication settings (e.g., duplicate images but not videos).
- **PDF Integration**:
  - **Image Embedding**: Images are embedded directly in PDF documents.
  - **Audio/Video References**: Audio and video files are referenced as links in PDF (with <LOCAL_BASE_URL> URLs when duplicated).
  - **Multilingual PDFs**: PDFs generated in user's preferred language with embedded/referenced media.
- **HTML Page Generation**:
  - **Complete HTML Pages**: System can generate complete HTML pages with embedded media for personalized content.
  - **Media Embedding**: Images embedded as `<img>` tags, audio as `<audio>` tags, video as `<video>` tags.
  - **Local Storage References**: When duplicated, media references use <LOCAL_BASE_URL> URLs pointing to notification storage.
  - **External References**: When not duplicated, media references use original external URLs.
- **Channel Support**: All channels (Email, Slack, SMS, WhatsApp, File) support appropriate media handling based on channel capabilities.
- **Format Support**: Media works with all output formats (MD, TXT, PDF, HTML).

**Alignment**: [ARCH:CC5.3](ARCHITECTURE.md#cc53), [ARCH:CC6.1.2](ARCHITECTURE.md#cc612), [TASK:T30](TASKS.md#t30), [TASK:T32](TASKS.md#t32), [TEST:AT1.20](TESTS.md#at120), [TEST:AT1.23](TESTS.md#at123)

### FR1.20: File Output Channel
System shall provide File Output Channel for saving notifications to file storage:
- **Channel Type**: New channel type "file" for file-based delivery.
- **Storage Backends**: Support multiple storage backends:
  - **File System**: Local file system storage (file:// URIs).
  - **WebDAV**: WebDAV protocol storage (https:// URIs with WebDAV authentication).
  - **FTP**: FTP protocol storage (ftp:// URIs with FTP authentication).
  - **S3**: S3-compatible object storage (s3:// URIs or HTTP/HTTPS endpoints with S3 authentication).
- **Format Support**: File channel supports all output formats:
  - **Language Formats**: Respects user language preferences and generates files in appropriate language.
  - **Content Formats**: Supports Markdown (MD), Plain Text (TXT), and PDF formats.
  - **Format Selection**: Format determined by user preference, channel configuration, or message options.
- **File Naming**: Files saved with appropriate naming convention including message ID, timestamp, format, and language.
- **Directory Structure**: Support for organized directory structure (e.g., by date, user, message type).
- **Authentication**: Proper authentication and credential management for each storage backend type.
- **Error Handling**: Robust error handling for storage failures, network issues, and authentication problems.
- **API management**: Stored files MUST be accessible via API endpoints for read/update/delete and verification, using backend+filename addressing (e.g. `/storage/files/{backend_type}/{filename}`).

**Alignment**: [ARCH:CC5.1.5](ARCHITECTURE.md#cc515), [ARCH:CC6.1.2](ARCHITECTURE.md#cc612), [TASK:T31](TASKS.md#t31), [TEST:AT1.21](TESTS.md#at121)

### FR1.21: Audio and Video Media Support
System shall provide support for audio and video media formats in addition to images:
- **Audio Format Support**: Support common audio formats (MP3, WAV, OGG, AAC) with format detection, validation, and metadata extraction.
- **Video Format Support**: Support common video formats (MP4, WebM, OGV, AVI) with format detection, validation, and metadata extraction.
- **Audio/Video Transfer Methods**:
  - **UUEncoded Audio/Video**: Audio and video files can be UUEncoded and embedded in messages (for smaller files).
  - **URI References**: Audio and video can be referenced via HTTP/HTTPS URLs or local file paths.
- **Storage and Caching**:
  - **Local Storage**: Audio and video files can be stored in notification storage (organized in audio/ and video/ directories).
  - **Channel Duplication Setting**: Channels can be configured to duplicate external audio/video references to local storage.
  - **Selective Duplication**: System supports per-media-type duplication (e.g., duplicate images/audio but not videos).
- **PDF Integration**:
  - **Audio/Video Links in PDF**: Audio and video files are referenced as clickable links in PDF documents.
  - **Localhost URLs**: When duplicated, audio/video links use <LOCAL_BASE_URL> URLs pointing to notification storage.
  - **Metadata Display**: PDF can display audio/video metadata (duration, format, size) as text.
- **HTML Integration**:
  - **Audio Tags**: Audio files embedded in HTML using `<audio>` tags with proper source references.
  - **Video Tags**: Video files embedded in HTML using `<video>` tags with proper source references.
  - **Fallback Content**: HTML includes fallback text for browsers that don't support audio/video tags.
  - **Local vs External**: HTML references use <LOCAL_BASE_URL> URLs when duplicated, external URLs when not.
- **Channel Support**: All channels support audio/video references appropriately (links in text channels, embedded in HTML/PDF).

**Alignment**: [ARCH:CC5.3.4](ARCHITECTURE.md#cc534), [ARCH:CC6.1.3](ARCHITECTURE.md#cc613), [TASK:T32](TASKS.md#t32), [TEST:AT1.22](TESTS.md#at122)

### FR1.22: HTML Page Generation for Personalized Content
System shall provide HTML page generation capabilities for personalized multimedia content:
- **HTML Page Generation**: Generate complete, standalone HTML pages from formatted content with embedded media.
- **Personalization Integration**: HTML pages support personalized content based on user keywords and preferences.
- **Media Embedding**: HTML pages can embed images, audio, and video using appropriate HTML tags.
- **Storage and Access**:
  - **HTML Storage**: Generated HTML pages stored in notification storage with organized paths.
  - **Access URLs**: HTML pages accessible via <LOCAL_BASE_URL> URLs for email links and references.
  - **Security**: HTML pages stored with appropriate access controls and authentication if needed.
- **Format Support**: HTML pages support all content formats (text, Markdown converted to HTML, existing HTML).
- **Language Support**: HTML pages generated in user's preferred language with proper character encoding.
- **Email Integration**: Email notifications can include links to personalized HTML pages.
- **Media Reference Strategy**: HTML pages support both local storage references (<LOCAL_BASE_URL> URLs) and external references based on channel settings.

**Alignment**: [ARCH:CC5.3.5](ARCHITECTURE.md#cc535), [ARCH:CC6.1.3](ARCHITECTURE.md#cc613), [TASK:T32](TASKS.md#t32), [TEST:AT1.24](TESTS.md#at124)

### FR1.23: Channel-Level Media Duplication Settings
System shall provide channel-level configuration for media duplication behaviour:
- **Duplication Setting**: Channels can be configured with a setting to duplicate all external media references to local storage.
- **Per-Media-Type Settings**: System supports selective duplication (e.g., duplicate images and audio but not videos).
- **Default Behaviour**: Default duplication behaviour configurable at system level.
- **Override Capability**: User or message-level preferences can override channel duplication settings.
- **Storage Management**: Duplicated media stored in organized structure (images/, audio/, video/ directories).
- **URL Generation**: When duplicated, media references use <LOCAL_BASE_URL> URLs. When not duplicated, original URLs are used.

**Alignment**: [ARCH:CC5.1](ARCHITECTURE.md#cc51), [ARCH:CC5.3.6](ARCHITECTURE.md#cc536), [TASK:T32](TASKS.md#t32), [TEST:ST1.6](TESTS.md#st16)

### FR1.24: Message Management API
System shall provide API endpoints for message management: DELETE /messages/{id} to permanently delete messages and all associated data (deliveries, receipts), POST /messages/{id}/cancel to cancel pending deliveries without deletion. All database operations must go through API endpoints; direct database access is prohibited.

**Alignment**: [ARCH:AI1.1](ARCHITECTURE.md#ai11), [TASK:T9](TASKS.md#t9), [TEST:IT1.19](TESTS.md#it119)

### FR1.25: LLM Context Budget & Chunking Guardrails
System shall enforce LLM context window limits and guardrails for all LLM operations (formatting, summarization, translation):
- **Context Budget**: Use `llm.num_ctx` as the total context window (e.g., 32,768 tokens).
- **Output Budget**: Use `llm.max_tokens` (or `llm.num_predict`) as the maximum output tokens (e.g., 16,384).
- **Input Budget**: Enforce `max_input_tokens = llm.num_ctx - llm.max_tokens` (e.g., 16,384).
- **Pre-flight Token Estimation**: Before every LLM call, estimate tokens for `prompt + message`.
- **Mandatory Chunking**: If `prompt + message > max_input_tokens`, the system MUST split the content and use multi-step chunking (map‑reduce or chunk‑then‑summarize/translate/format) to stay within limits.
- **Fail Fast on Overflow**: If chunking still cannot fit within limits after configured rounds, the system MUST fail with a clear, actionable error.
- **Configuration-Driven**: All limits and chunking behaviour must be configurable and logged.

**Alignment**: [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T20](TASKS.md#t20), [TEST:UT1.5](TESTS.md#ut15)

### FR1.26: MCP Transport & JSON-RPC Compliance
System shall provide full MCP transport compatibility and JSON-RPC compliance across all supported modes:
- **Transport Modes**:
  - **streamable_http**: JSON-RPC over HTTP with optional SSE streaming; session lifecycle with explicit termination.
  - **http_jsonrpc**: JSON-RPC over HTTP using a messages endpoint (request/response in the same call).
  - **http_jsonrpc + async jobs**: `wait=false` flow returns job reference; status polling to completion/timeout.
  - **legacy_sse**: SSE stream + message POST endpoint with JSON-RPC correlation by `id`.
  - **stdio**: Local process transport with JSON-RPC framing over stdin/stdout.
  - **Note**: `http_jsonrpc_async` is accepted as an alias for `http_jsonrpc` when async jobs are enabled.
- **Transport endpoints** (defaults):
  - streamable_http: `POST/DELETE /mcp`
  - http_jsonrpc: `POST /messages`
  - legacy_sse: `GET /sse` + `POST /message`
  - async job status: `GET /jobs/{job_id}`
- **JSON-RPC Correctness**:
  - Accept valid JSON-RPC requests (`jsonrpc`, `id`, `method`, `params`).
  - Return valid `result` or structured `error` responses (invalid requests, invalid params, unknown tool).
- **Lifecycle**:
  - Support `initialise` and `notifications/initialized`.
  - For streamable HTTP, support explicit session termination (`DELETE /mcp` with `Mcp-Session-Id`).
  - Respect configured `protocol_version` for compatibility.
- **Tool Contract**:
  - `tools/list` returns a stable, parseable tool surface.
  - `tools/call` executes tools with schema-valid arguments and returns structured output.
- **Session & Reliability**:
  - For streamable HTTP and legacy SSE, support clean session open/use/terminate behaviour.
  - For async jobs, resolve to completion within configured timeout, returning explicit error on timeout.

**Alignment**: [ARCH:CC1.1.3](ARCHITECTURE.md#cc113), [ARCH:AI1.2](ARCHITECTURE.md#ai12), [TASK:T11](TASKS.md#t11), [TEST:IT1.20](TESTS.md#it120), [TEST:IT1.21](TESTS.md#it121), [TEST:IT1.22](TESTS.md#it122), [TEST:IT1.23](TESTS.md#it123), [TEST:IT1.24](TESTS.md#it124), [TEST:ST1.20](TESTS.md#st120)

### FR1.27: Notification Web UI Route Contract (`UI-P5-NTFY-REQ`)
The monorepo frontend app `@cloud-dog/app-notification-agent` SHALL expose and maintain the following route contract:
- `/login`
- `/` (Users landing page after authentication)
- `/channels`
- `/messages`
- `/deliveries`
- `/settings`
- `/groups`
- `/jobs`

Unknown or unauthorized navigation SHALL resolve deterministically to login or an authenticated shell route according to session state.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.28: Users Page Contract (`UI-P5-NTFY-REQ`)
The Users page SHALL provide user management capabilities:
- list users
- search/filter users
- create user
- update user
- delete user

The page SHALL be reachable from authenticated navigation and integrated with real backend APIs through runtime configuration.

**Alignment**: [ARCH:CC3.1.1](ARCHITECTURE.md#cc311), [TASK:T16](TASKS.md#t16), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.29: Channels Page Contract (`UI-P5-NTFY-REQ`)
The Channels page SHALL provide channel management capabilities:
- list channels
- create channel
- edit channel
- delete channel

Channel actions SHALL be wired to backend channel APIs and enforce authenticated access.

**Alignment**: [ARCH:CC5.1](ARCHITECTURE.md#cc51), [TASK:T6](TASKS.md#t6), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.30: Notifications Page Contract (`UI-P5-NTFY-REQ`)
The notifications workflow (Messages + Deliveries pages) SHALL support:
- message list and inspection
- notification send/initiation flow
- delivery status tracking (including retries/error states)

UI status views SHALL reflect backend delivery state without synthetic success fallbacks.

**Alignment**: [ARCH:AI1.1](ARCHITECTURE.md#ai11), [ARCH:CP2.1](ARCHITECTURE.md#cp21), [TASK:T9](TASKS.md#t9), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.31: Settings and Runtime Config Contract (`UI-P5-NTFY-REQ`)
The Settings page SHALL expose runtime-relevant configuration visibility for operators.

The UI runtime contract SHALL be provided via `window.__RUNTIME_CONFIG__` and include, at minimum:
- `ENV`
- `API_BASE_URL`
- `MCP_BASE_URL`
- `A2A_BASE_URL`
- `AUTH_MODE`

Frontend components SHALL read runtime endpoints/auth mode from `__RUNTIME_CONFIG__` rather than hardcoded values.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.32: Web UI Auth Flow (`UI-P5-NTFY-REQ`)
The UI SHALL implement login/logout and authenticated session flow:
- unauthenticated users are redirected to `/login`
- valid login reaches authenticated shell routes
- logout returns user to login state
- admin-protected routes require authenticated/authorized session

Auth mode SHALL support configured cookie or OIDC operation.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.33: Web UI Accessibility Baseline (`UI-P5-NTFY-REQ`)
Core notification UI routes SHALL meet WCAG 2.x AA baseline checks in automated a11y validation.

Interactive controls SHALL expose accessible names suitable for role-based and assistive-technology usage.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR1.34: Job Control WebUI (`UI-P5-NTFY-REQ`)
The Jobs page SHALL comply with PS-76 Job Control WebUI Standard using `@cloud-dog/ui` `DataTable`, `EntityDialog`, `JsonBlock`, `Badge`, and summary metrics.

The common PS-76 columns SHALL appear first in this order:
- Job ID
- Type
- Status
- Priority
- Submitted By
- Created
- Started
- Duration
- Attempt
- Outcome

Notification-agent project-specific Jobs page extensions SHALL be appended after the common columns:
- `message_id`
- `channel_name`
- `destination`

The Jobs page SHALL expose:
- row actions for Detail, Cancel, Retry, and Delete/Archive
- bulk actions for Cancel Selected, Retry Selected, Delete Selected, and Export Selected
- queue summary metrics for Total Jobs, Queue Depth, Active Jobs, and Failed (24h)
- RBAC enforcement using `read_jobs`, `write_jobs`, and admin-only archive/delete

All mutating Jobs actions SHALL emit audit events via `cloud_dog_logging`.

**Alignment**: [ARCH:CC1.1.2](ARCHITECTURE.md#cc112), [TASK:T10](TASKS.md#t10), [TEST:UI-P5-NTFY-TST](TESTS.md#web-ui-traceability-ui-p5-ntfy-tst)

### FR-P001: Delivery Resend/Abort
The server SHALL provide resend and abort operations on delivery resources.
Resend SHALL re-queue the delivery for execution. Abort SHALL cancel an in-progress delivery.

**Alignment**: [ARCH:SW1.1](ARCHITECTURE.md#sw11), [TASK:T12](TASKS.md#t12), [TEST:IT1.27](TESTS.md#it127)

### FR-P002: A2A Event Streaming
The server SHALL publish delivery lifecycle events (created, queued, started, completed, failed)
via A2A event streaming topics for real-time monitoring.

**Alignment**: [ARCH:CC1.1.4](ARCHITECTURE.md#cc114), [TASK:T11](TASKS.md#t11)

---

## 5. Use Cases (UC)

### UC1.1: Send Broadcast Notification
As a system administrator, I want to send a broadcast notification to all users via their preferred channel so that important announcements reach everyone.

**Alignment**: [REQ:FR1.1](REQUIREMENTS.md#fr11), [ARCH:AI1.1](ARCHITECTURE.md#ai11), [ARCH:CC2.1.1](ARCHITECTURE.md#cc211), [TASK:T5](TASKS.md#t5), [TASK:T6](TASKS.md#t6), [TASK:T9](TASKS.md#t9), [TEST:AT1.12](TESTS.md#at112)

### UC1.2: Send Personalised Notification
As a user, I want to receive personalised notifications formatted according to my language, channel preference, and content style so that information is presented in the most useful way for me.

**Alignment**: [REQ:FR1.2](REQUIREMENTS.md#fr12), [ARCH:CC3.1.1](ARCHITECTURE.md#cc311), [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T8](TASKS.md#t8), [TASK:T16](TASKS.md#t16), [TASK:T20](TASKS.md#t20), [TEST:AT1.13](TESTS.md#at113)

### UC1.3: Natural Language Command
As an agent, I want to send notifications using natural language commands like "Send a notification to Fred that JOB XXXX has finished" so that I can interact with the system naturally.

**Alignment**: [REQ:FR1.17](REQUIREMENTS.md#fr117), [ARCH:CC1.1.3](ARCHITECTURE.md#cc113), [ARCH:CC1.1.4](ARCHITECTURE.md#cc114), [ARCH:AI1.2](ARCHITECTURE.md#ai12), [ARCH:AI1.3](ARCHITECTURE.md#ai13), [TASK:T11](TASKS.md#t11), [TASK:T21](TASKS.md#t21), [TEST:AT1.14](TESTS.md#at114)

### UC1.4: Manage User Preferences
As an administrator, I want to manage user preferences including language, channel preferences, and personalization keywords so that notifications are properly customized.

**Alignment**: [REQ:FR1.14](REQUIREMENTS.md#fr114), [ARCH:CC3.1.1](ARCHITECTURE.md#cc311), [TASK:T16](TASKS.md#t16), [TASK:T17](TASKS.md#t17), [TEST:AT1.15](TESTS.md#at115)

### UC1.5: Configure LLM Prompts
As an administrator, I want to configure LLM prompts for different channels, groups, languages, and keywords so that message formatting matches organizational needs.

**Alignment**: [REQ:FR1.15](REQUIREMENTS.md#fr115), [ARCH:CC4.1.2](ARCHITECTURE.md#cc412), [TASK:T18](TASKS.md#t18), [TEST:AT1.16](TESTS.md#at116)

### UC1.6: Group Notification with Multimedia and Multi-Language PDFs (Enhanced)
As an agent flow, I want to send markdown content with images and video to a group of users across multiple channels, with each user receiving content in their preferred language and format, so that all users receive personalized multimedia notifications in their preferred format and channel.

**Scenario**: Agent flow generates markdown output with image and video references. System sends to group where:
- Two users prefer English PDF (same Slack channel) → single Slack message with PDF link
- One user prefers French PDF → Email with summary and attached PDF
- One user prefers German PDF → different Slack channel with summary and PDF link
- One user prefers Polish PDF → Email with PDF attachment
- Storage/Output Channel: Saves messages in all formats (MD, PDF, HTML, TXT) and all languages (EN, FR, DE, PL) with embedded images and video links
- Channel setting duplicates external references to local storage
- PDFs include embedded images and <LOCAL_BASE_URL> references to video files
- All formats include proper image embedding and video references

**Alignment**: [REQ:FR1.18](REQUIREMENTS.md#fr118), [REQ:FR1.19](REQUIREMENTS.md#fr119), [REQ:FR1.21](REQUIREMENTS.md#fr121), [REQ:FR1.20](REQUIREMENTS.md#fr120), [REQ:FR1.2](REQUIREMENTS.md#fr12), [ARCH:CC5.2](ARCHITECTURE.md#cc52), [ARCH:CC5.3](ARCHITECTURE.md#cc53), [TASK:T29](TASKS.md#t29), [TASK:T30](TASKS.md#t30), [TASK:T32](TASKS.md#t32), [TASK:T31](TASKS.md#t31), [TEST:AT1.23](TESTS.md#at123)

### UC1.7: Personalized Multimedia Notifications with HTML Pages (Enhanced)
As an agentic flow, I want to send a detailed description personalized for multiple users (via keywords) across multiple channels, with each user receiving content in their preferred channel and format, so that users receive highly customized multimedia content.

**Scenario**: Agentic flow generates long detailed description. System:
- Personalizes content for 10+ users based on their keywords
- Generates personalized HTML page for each user
- Embeds images from local storage
- Embeds videos (from local storage if duplicated, or external reference if not)
- Sends via multiple channels:
  - Email with link to HTML page
  - Slack with summary and link to HTML page
  - Storage/Output channel saves HTML pages in all formats (MD, PDF, HTML, TXT) and all languages (EN, FR, DE, PL)
- All formats include embedded images and video references
- All languages properly translated with media preserved

**Alignment**: [REQ:FR1.22](REQUIREMENTS.md#fr122), [REQ:FR1.19](REQUIREMENTS.md#fr119), [REQ:FR1.21](REQUIREMENTS.md#fr121), [REQ:FR1.20](REQUIREMENTS.md#fr120), [REQ:FR1.2](REQUIREMENTS.md#fr12), [REQ:FR1.14](REQUIREMENTS.md#fr114), [ARCH:CC5.3.5](ARCHITECTURE.md#cc535), [ARCH:CC4.1.1](ARCHITECTURE.md#cc411), [TASK:T30](TASKS.md#t30), [TASK:T32](TASKS.md#t32), [TASK:T31](TASKS.md#t31), [TASK:T13](TASKS.md#t13), [TEST:AT1.24](TESTS.md#at124)

### UC1.8: Storage/Output Channel with Multi-Format and Multi-Language Support
As a system administrator, I want to save notifications to storage in multiple formats and languages with embedded multimedia, so that I have a complete archive of all notifications in all supported formats and languages.

**Scenario**: System receives notification with images and video. Storage/Output channel:
- Saves message in Markdown format (MD) with image references and video links
- Saves message in PDF format with embedded images and video references
- Saves message in HTML format with embedded images and video tags
- Saves message in Text format (TXT) with image URLs and video links
- Generates all formats in multiple languages:
  - English (EN) - original
  - French (FR) - translated
  - German (DE) - translated
  - Polish (PL) - translated
- All formats include:
  - Embedded images (where format supports it)
  - Video links/references (all formats)
  - Proper language translation
  - Media metadata

**Output Structure**:
```
storage/output/
  {message_id}/
    en/
      message.md
      message.pdf
      message.html
      message.txt
    fr/
      message.md
      message.pdf
      message.html
      message.txt
    de/
      message.md
      message.pdf
      message.html
      message.txt
    pl/
      message.md
      message.pdf
      message.html
      message.txt
```

**Alignment**: [REQ:FR1.20](REQUIREMENTS.md#fr120), [REQ:FR1.18](REQUIREMENTS.md#fr118), [REQ:FR1.19](REQUIREMENTS.md#fr119), [REQ:FR1.21](REQUIREMENTS.md#fr121), [TASK:T31](TASKS.md#t31), [TEST:AT1.25](TESTS.md#at125)

### UC1.9: Multi-Channel Multimedia Delivery with All Formats
As an agentic flow, I want to send multimedia notifications to users via multiple channels simultaneously, with each channel receiving content in the appropriate format, so that users can access notifications through their preferred channel in their preferred format.

**Scenario**: System sends notification with images and video to user via:
- **Email**: HTML body with embedded images, PDF attachment with embedded images, link to HTML page with video
- **Slack**: Summary text with image references, PDF link, HTML page link
- **Storage/Output**: All formats (MD, PDF, HTML, TXT) in all languages (EN, FR, DE, PL) with images and video

**Requirements**:
- Same message delivered to multiple channels
- Each channel receives format-appropriate content
- All channels include multimedia references
- Storage channel saves all variants

**Alignment**: [REQ:FR1.2](REQUIREMENTS.md#fr12), [REQ:FR1.18](REQUIREMENTS.md#fr118), [REQ:FR1.19](REQUIREMENTS.md#fr119), [REQ:FR1.20](REQUIREMENTS.md#fr120), [REQ:FR1.21](REQUIREMENTS.md#fr121), [REQ:FR1.22](REQUIREMENTS.md#fr122), [TEST:AT1.26](TESTS.md#at126)

---

## 6. Cyber Security (CS)

### CS1.1: Authentication
System shall provide local auth (bcrypt/argon2), session cookies (HttpOnly, Secure). API keys for programmatic access; key rotation; scope/role binding.

**Alignment**: [ARCH:SE1.1](ARCHITECTURE.md#se11), [TASK:T29](TASKS.md#t29), [TEST:ST1.4](TESTS.md#st14)

### CS1.2: Secret Management
System shall provide secret management; TLS in production.

**Alignment**: [ARCH:SE1.2](ARCHITECTURE.md#se12), [TASK:T30](TASKS.md#t30), [TEST:ST1.5](TESTS.md#st15)

### CS1.3: Audit Events
System shall provide audit events for all admin actions.

**Alignment**: [ARCH:SE1.3](ARCHITECTURE.md#se13), [TASK:T31](TASKS.md#t31), [TEST:ST1.6](TESTS.md#st16)

---

## 7. Non-Functional Requirements (NF)

### NF1.1: Performance
System shall provide submit-to-queue < 50ms p95; adapter latency surfaced in metrics.

**Alignment**: [ARCH:SP1.1](ARCHITECTURE.md#sp11), [TASK:T32](TASKS.md#t32), [TEST:ST1.14](TESTS.md#st114)

### NF1.2: Availability
System shall provide health checks, degraded modes, default channel required.
- `/health` MUST return `app`, `server`, and `env_file` metadata for each server.

**Alignment**: [ARCH:RR1.1](ARCHITECTURE.md#rr11), [TASK:T33](TASKS.md#t33), [TEST:ST1.8](TESTS.md#st18), [TEST:ST1.19](TESTS.md#st119)

**Additional Availability Expectations**:
- The system SHALL detect and recover from deliveries stuck in intermediate workflow states (e.g. `formatting`) by transitioning them to a retryable state (e.g. `soft_failed`) with backoff, to avoid indefinite stalls.
- The system SHALL tolerate LLM resets and transient timeouts by applying a configurable grace period with retries before failing LLM-dependent operations or tests.

### NF1.3: Scalability
System shall support horizontal workers; stateless API nodes; work-queue backed.

**Alignment**: [ARCH:SP1.2](ARCHITECTURE.md#sp12), [TASK:T34](TASKS.md#t34), [TEST:ST1.9](TESTS.md#st19)

### NF1.4: Compliance
System shall provide configurable retention; PII minimisation; GDPR-friendly exports.

**Alignment**: [ARCH:SE1.4](ARCHITECTURE.md#se14), [TASK:T35](TASKS.md#t35), [TEST:ST1.10](TESTS.md#st110)

### NF1.5: Portability
System shall be containerised build; env-driven configuration.

Additional portability requirements:
- Support mounting custom CA bundles for outbound TLS trust (`/app/certs/ca.crt`).
- Support mounting TLS key/cert for MCP HTTPS when `mcp_server.tls=true`.

**CRITICAL RULE - NEVER HARD-CODE CONFIGURATION VALUES:**
- All configuration MUST use the hierarchy: os.environ -> env file (--env) -> config.yaml -> defaults.yaml
- Server control script MUST pass `--env` flag to Python scripts when provided: `./server_control.sh --env <file> start api`
- Code MUST read from config using `get_config()`, never hard-code ports, URLs, keys, or any values
- Tests MUST use environment variables or `--env` flag, never hard-code values
- Configuration priority: OS Environment Variables (highest) -> env file (--env) -> config.yaml -> defaults.yaml (lowest)

**Alignment**: [ARCH:DA1.1](ARCHITECTURE.md#da11), [ARCH:CM1.1](ARCHITECTURE.md#cm11), [TASK:T36](TASKS.md#t36), [TEST:ST1.11](TESTS.md#st111), [TEST:ST1.20](TESTS.md#st120)

### NF1.6: Testability
System shall provide unit/integration/E2E suites; provider simulators; fixtures.

**Alignment**: [ARCH:TS1.1](ARCHITECTURE.md#ts11), [TASK:T37](TASKS.md#t37), [TEST:UT1.3](TESTS.md#ut13)

### NF1.7: Auditability
System shall maintain a per-message auditable log containing all significant events: message submission, formatted content, send attempts, channel transactions, confirmation callbacks, state transitions, and errors. Each auditable log entry must be signed with a cryptographic certificate generated from a provided or generated key, ensuring authenticity and non-repudiation. All entries include a precise datetime stamp, referencing the origin message, sender context, delivery details, and associated transaction/confirmation records. Allow export or verification of the signed audit trail for compliance and dispute resolution.

**Alignment**: [ARCH:SE1.3](ARCHITECTURE.md#se13), [TASK:T38](TASKS.md#t38), [TEST:ST1.12](TESTS.md#st112)

### NF1.8: Data Retention & Privacy
System shall provide configurable retention windows for messages, deliveries, receipts and logs. Redact or hash sensitive content at rest where possible; store links for large payloads. Data lifecycle management and deletion based on settings, to remove content inline with DPA.

**Alignment**: [ARCH:DM1.1](ARCHITECTURE.md#dm11), [TASK:T39](TASKS.md#t39), [TEST:ST1.13](TESTS.md#st113)

---

## 8. Database Abstraction (R-DB)

- R-DB-01: All database access MUST use `cloud_dog_db` engine/session/CRUD abstractions.
- R-DB-02: Engine creation MUST use `cloud_dog_db` engine factories.
- R-DB-03: Session management MUST use `cloud_dog_db.session.SyncSessionManager`/`AsyncSessionManager`.
- R-DB-04: Schema migrations MUST use `cloud_dog_db` migration runner.
- R-DB-05: Direct `sqlite3`/`create_engine()`/`sessionmaker()`/raw `Session()` are FORBIDDEN in application code.
- R-DB-06: DB health MUST use `cloud_dog_db.health.probe_database()`.
- R-DB-07: DB connection config MUST come from `cloud_dog_config` + Vault-backed env hierarchy.
- R-DB-08: Schema versioning MUST be tested across SQLite, MySQL, and PostgreSQL.
- R-DB-09: Schema upgrade/downgrade MUST be validated with at least two migrations per dialect.
- R-DB-10: CRUD outcomes MUST be consistent across SQLite, MySQL, and PostgreSQL.

---

## Open Questions

- LLM provider + deployment mode - ollama, openai compatible. onprem focus - keep all information secure
- Preferred SMS/WhatsApp providers vs generic REST adapter only. ( Twillo and other )
- LDAP/Keycloak sync frequency and conflict resolution strategy
- Keyword taxonomy and management approach

---

## Support/Technical

- Database Support: MySQL/PostgreSQL/SQLite3

---

## 9. W28A-879 Forensic Requirements Merge (Phase 1)

This section records the Phase 1 forensic merge performed for W28A-879 on
2026-04-09. The `Source` marker below answers the instruction requirement to
label each merged item as `EXISTING` or `NEW` relative to this document set.
Implementation completeness is assessed separately in `docs/TESTS.md` and the
W28A-879 working report.

### W879-REQ-01: Channel Configuration CRUD, Type-Specific Forms, Live Test & RBAC
**Source**: `EXISTING`

The system shall provide channel CRUD through backend APIs and the notification
WebUI. The WebUI shall render type-specific configuration forms for the
implemented channel types, support live test sends, and gate configuration
changes behind administrative/config-write permissions.

Phase 1 forensic note: CRUD, type-specific forms, and live tests exist in the
current WebUI for `loopback`, `smtp`, `chat_rest`, and `file`, but RBAC remains
coarse and inconsistent across Web/API (`notification:*`) and MCP
(`notify:*`) surfaces.

### W879-REQ-02: Message Composition, Sending & Template Integration
**Source**: `EXISTING`

The system shall provide message composition and sending through backend APIs and
the notification WebUI, including channel selection, destination entry, message
body editing, message cancellation, and delivery inspection. Prompt/template
selection shall be available to prefill or drive composed content.

Phase 1 forensic note: the current WebUI exposes template selection, but the
compose flow copies prompt text into the body editor rather than exposing a
full template-variable send workflow.

### W879-REQ-03: Delivery Tracking, Retry, Abort & Dead-Letter Lifecycle
**Source**: `EXISTING`

The system shall expose delivery lifecycle state through backend APIs and the
WebUI, including status badges, retry/resend actions, abort/cancel actions, and
visibility of failed or dead-lettered work through the delivery and job-control
surfaces.

Phase 1 forensic note: retry and abort are first-class delivery actions, while
dead-letter visibility is primarily surfaced through the Jobs page and runtime
state model.

### W879-REQ-04: Prompt Templates, Multi-Language, Channel Scope & Variables
**Source**: `EXISTING`

The system shall provide prompt-template CRUD across backend APIs and the
notification WebUI, including language-specific, keyword-specific, group-scoped,
and channel-type-scoped prompt variants plus editable prompt variables payloads.

Phase 1 forensic note: the current prompt surface stores `variables_json` and
channel/language/keyword/group selectors directly; dedicated Playwright CRUD
coverage for the prompt page still needs strengthening.

W28A-999 disposition: implemented already in the current product; the former
matrix gap was missing browser-test depth, not missing prompt capability.

### W879-REQ-05: End-to-End Delivery Through Real SMTP
**Source**: `EXISTING`

The system shall support real SMTP delivery end to end, including channel
configuration, authenticated delivery, and downstream verification against the
real mail environment when those credentials are supplied.

### W879-REQ-06: End-to-End Delivery Through Loopback
**Source**: `EXISTING`

The system shall support loopback delivery end to end for local and integration
verification, including message submission, delivery-state tracking, and
rendered output/message-centre verification.

### W879-REQ-07: End-to-End Delivery Through File Channel
**Source**: `EXISTING`

The system shall support file-channel delivery end to end across the configured
storage backends, including persisted output, retrieval, overwrite/update, and
deletion through the verified storage APIs.

W28A-999 disposition: implemented already in the current product; this
requirement is satisfied by the verified storage API workflows and does not
require a dedicated file-channel-only WebUI page.

### W879-REQ-08: Storage & Archival Browser Workflow
**Source**: `NEW`

The system shall provide an operator-facing storage and archival browser that
allows users to inspect stored notification outputs and file-channel artefacts
from the WebUI rather than relying only on backend storage endpoints.

Phase 1 forensic note: backend storage/file APIs exist, but the notification
WebUI currently has no dedicated storage browser or file-management page.

W28A-999 disposition: accepted gap; tracked in `docs/ACCEPTED-GAPS.md`
(`W879-REQ-08`) until a dedicated operator-facing storage browser exists.

### W879-REQ-09: Delivery Worker & Queue Health Surface
**Source**: `NEW`

The system shall provide a dedicated operator-facing queue-health surface for
delivery-worker status, queue depth, retry backlog, job lifecycle control, and
forensic inspection of queued or dead-lettered work.

Phase 1 forensic note: the current Jobs page provides queue depth, job metrics,
lifecycle actions, and detail inspection, but it does not expose an explicit
delivery-worker heartbeat or worker roster.

W28A-999 disposition: accepted gap; tracked in `docs/ACCEPTED-GAPS.md`
(`W879-REQ-09`) until a dedicated worker-status surface exists.

### W879-REQ-10: Dashboard Real-Time Operational Metrics
**Source**: `NEW`

The system shall provide a real-time operational dashboard showing health,
channel/message/delivery/job inventory, queue depth, delivery success, recent
activity, and quick actions backed by live runtime APIs.

Phase 1 forensic note: the dashboard is live-backed today, but the metric set is
not exhaustive for every operational dimension called out in the expanded Phase
1 specification.

### W879-REQ-11: Monitoring, Delivery Health & Multi-Surface Logs
**Source**: `EXISTING`

The system shall provide a monitoring surface backed by live runtime APIs and a
multi-surface structured log viewer spanning at least audit, API, web, MCP, and
A2A log sources with filtering and search.

### W879-REQ-12: Export & Download Capabilities
**Source**: `NEW`

The system shall provide operator-facing export and download capabilities for
administrative list pages and message/delivery data, and document which
download workflows remain backend-only until a storage browser exists.

Phase 1 forensic note: several WebUI pages already export JSON, while stored
artefact download remains primarily a backend/API concern.

W28A-999 disposition: implemented already in the current product because the
requirement explicitly allows stored-artifact download workflows to remain
backend-only until a storage browser exists.

### W879-REQ-13: Full Audit-Trail Verification
**Source**: `EXISTING`

The system shall preserve and expose a full audit trail covering notification,
job, and administrative events, with AU-3-style structured fields, export or
verification support, and multi-surface inspection through the WebUI.

Phase 1 forensic note: current audit coverage spans signed audit helpers,
job-lifecycle audit emission, and a structured multi-surface log reader.

---

**Document Status**: Restructured per RULES.md requirements with SV/BO/BR/FR/UC/CS/NF prefixes and alignment links.

## W28A-883 PS-78 Cross-Platform File Handling Addendum

### Verified current state

- The service has storage-oriented API endpoints under `/storage/files/{backend_type}/{filename:path}` for put/get/delete, plus internal attachment and PDF-generation flows.
- The storage layer mixes `cloud_dog_storage` local delegation with separate S3, FTP, and WebDAV service adapters.
- No standard `/files/upload` or `/files/{id}/download` API contract, no file inventory/list endpoint, and no dedicated file-handling WebUI or MCP tool surface were found.

### Required additions to satisfy PS-78

- Standardise the public file contract on `/files/upload`, `/files/upload_base64`, `/files`, `/files/{id}`, `DELETE /files/{id}`, and `/files/{id}/download`.
- Replace bespoke remote-storage lifecycle paths with thin adapters over `cloud_dog_storage` wherever platform backends already exist.
- Add MCP file upload/download contracts for attachment and archival workflows.
- Add WebUI upload/download/browser surfaces for stored artifacts and attachments.
- Add A2A file transfer support for message payloads and delivery artifacts.

### Required PS-78 test plan

- API: upload, list, metadata, download, delete across configured storage backends.
- MCP: base64 upload/download plus URI-source handling.
- A2A: transfer message attachments or generated artifacts between agents.
- WebUI: upload file, browse inventory, download artifact, delete artifact.
- Delivery workflow: verify a generated attachment can be stored, listed, downloaded, and referenced from the delivery UI.

## PS-40 / W28A-619 Logging and Audit Requirements

The service MUST use `cloud_dog_logging` as the only application and audit logging implementation. Raw stdlib logging setup, direct `logging.getLogger()` calls, bespoke audit emitters, and print-based operational logging are not compliant except inside the platform logging package itself.

Every auditable event MUST emit a PS-40/NIST AU-3 audit record with: `event_type`, `action`, `timestamp`, `service`, `component`, `service_instance`, `environment`, `source_host`, `source_process`, `source_application`, `source_address` where available, `destination_address` where available, `outcome`, actor identity including user/service/system plus account/process/device identifiers where available, `target`, `process_id`, `affected_files` where relevant, `correlation_id`, `trace_id`, and `request_id`.

Auditable events MUST include authentication and authorisation decisions, user/group/API-key/RBAC changes, channel/template/message/media/provider/delivery operations, MCP/A2A/API calls, job lifecycle changes, configuration changes, data access and mutation, denials, failures, and privileged operations. Secrets MUST be redacted before persistence. Tests MUST cover schema fields, event coverage, redaction, append-only audit persistence, retention/integrity, and WebUI observability rendering/filtering.

## 5. Cyber Security & Negative Flows

Mandatory schema per PS-REQ-TEST-TRACE v1.0 §3.4. Every project covers anon-denied, wrong-role-denied, missing-param-error per declared surface. The CS rows below are platform-baseline; project-specific extensions append in §5.1.

| ID | Threat / negative scenario | Surface | Role(s) attempted | Expected | Tests |
|---|---|---|---|---|---|
| `CS-001` | Anon attempts data read | `api`, `mcp`, `a2a`, `webui` | `anon` | `401` | (to be bound in Instruction 4 by operator) |
| `CS-002` | read-only attempts write | `api`, `mcp` | `read-only` | `403` | (to be bound in Instruction 4 by operator) |
| `CS-003` | Missing required param | `api` | `admin` | `422` | (to be bound in Instruction 4 by operator) |
| `CS-004` | Wrong-role privileged op | `mcp` | `read-write` | `403` | (to be bound in Instruction 4 by operator) |



<!-- W28C-1710a recovery: full content from archive/2026-06-12/DESCRIPTION.md (archived sha256=090e152ba8d1, 65 lines) -->

## Recovered domain content — `archive/2026-06-12/DESCRIPTION.md` (65 lines)

_This section carries forward the full content of the archived predecessor doc verbatim. Topic checklist + SHA256 chain in `cloud-dog-ai-platform-standards/working/evidence/W28C-1710a/per-doc/notification-agent-mcp-server/DESCRIPTION.md.topics.tsv`. Archive contents are unchanged (sha256 stable)._

# Apache-2.0 (C) Cloud-Dog, Cloud-Dog Engineering

# Notification Agent MCP Server — Description

## Overview (50 words)
Notification Agent MCP Server is a multi-channel notification platform running API, Web UI, MCP tools, and A2A streaming. It formats messages with LLMs, manages users and groups, enforces preferences, and tracks deliveries. Designed for secure, portable deployment, it integrates with SMTP, SMS, WhatsApp, and webhook channels across regulated enterprise environments.

## Features and Benefits

| Features | Benefits |
| --- | --- |
| API + Web UI administration | Centralised operations with fast admin workflows |
| MCP tools with multi-transport | Agent integration without custom glue |
| A2A natural-language endpoint | Human-friendly automation for operators |
| LLM formatting and translation | Consistent messages across languages and channels |
| SMTP/SMS/WhatsApp/webhook adapters | Reliable delivery across enterprise messaging providers |
| Prompt management by language and group | Tailored content by audience and locale |
| Config-driven Docker deployment | Portable deployments for dev, test, production |
| Structured audit and delivery logs | Traceable actions for compliance and debugging |

## Product Overview
Teams need reliable, auditable notifications across many channels, without custom integrations per system. This server centralises delivery, formatting, and user/group routing so operators and systems can send messages consistently. It helps when multiple teams, channels, and languages are in play, and it reduces manual escalation work.

It supports admin workflows for channels, users, groups, and prompts, and it enforces delivery preferences and restrictions. It helps engineering teams, operations, and support with consistent delivery, while compliance teams benefit from audit trails and traceable delivery metadata.

## Technical Capabilities
The platform runs four coordinated services: API, Web UI, MCP, and A2A. The API handles CRUD, message submission, status, and configuration queries. The MCP server exposes tools over stdio, streamable HTTP, JSON-RPC, and legacy SSE. A2A provides natural-language command processing, and the Web UI exposes admin workflows and API proxy endpoints.

Operationally, it supports Docker deployment, external storage mounts, TLS, and configuration via `default.yaml`, `config.yaml`, env files, and environment variables. Tests validate multi-transport MCP compliance, Web UI integration, and real adapter flows across supported environments.

## Where it Fits
Notification Agent MCP Server fits alongside enterprise service platforms, workflow orchestration, and AI assistant ecosystems. It integrates with databases, file storage, LLM providers, and messaging providers, and it works with upstream systems that need a consistent notification backbone.

It complements existing monitoring, ITSM, and incident-response tooling by acting as a delivery layer rather than replacing those systems. It also acts as an MCP tool server, enabling agentic workflows to interact safely with notification operations.

## ARCHITECTURE
Deployment typically runs as a single container for API, Web UI, MCP, and A2A in smoke or small-scale deployments. For scale-out deployments, services can be separated behind a load balancer with shared database and storage. Persistent volumes handle logs and file storage, and TLS can be enabled for MCP endpoints.

Security uses API keys, session authentication for the Web UI, and optional external identity providers (LDAP/Keycloak). Observability includes structured logs, health endpoints, and delivery metadata for auditing.

## Technical Design
Configuration follows a strict hierarchy to avoid hardcoded values and to support repeatable deployments. Health endpoints return service metadata and environment file references for operational visibility. The API enforces structured responses and supports key admin workflows for channels, messages, deliveries, users, groups, and prompts.

Prompt selection and multi-language handling are implemented through per-channel, per-group, and per-language prompt records. The MCP server implements JSON-RPC compliance, session lifecycle control, and async jobs for long-running requests. The Web UI proxies API calls and enforces access control for admin actions.

## Key Capabilities
Multi-channel delivery: send a critical update to email, SMS, and chat channels during an incident, with enforced length restrictions and retry handling.

MCP tool interface: an assistant calls `tools/list` and `tools/call` to dispatch a notification from an agent workflow without direct API integration.

Admin operations: an operator uses the Web UI to add a new channel, enable it, and run a test send before a release.

Prompt management and localisation: a team creates French prompts for a group, ensuring consistent language in customer updates.

Audit and observability: compliance reviewers trace a delivery from message creation through channel attempts using structured logs.

## Example Use Cases
- Centralised notification hub for multi-team operations with shared channels.
- MCP tool server for AI assistants managing incident notifications.
- Automated status updates from CI/CD pipelines with channel-specific formatting.
- Multi-language customer communications with group-specific prompts.
- Disaster recovery announcements with rapid channel enable/disable.

## Deployment
Supported patterns include all-in-one Docker containers for local smoke runs, multi-container deployments for scaled environments, and on-host service deployments. Use MariaDB or compatible databases for persistence, mount `/app/storage` for file artefacts, and configure TLS and custom CA bundles where required. Config updates are controlled via admin settings and env file policy.


<!-- W28C-1710b design-delta additions (2026-06-14T18:01:23Z); SHA chain in working/W28C-1710b/KNOWLEDGE-PRESERVATION-DELTA.md -->

## PS-REQ-TEST-TRACE schema completion (W28C-1710b)

Per the binding contract (`docs/standards/PS-REQ-TEST-TRACE.md` §2 + §3), every FR-NNN row in this file declares the following schema (default values; operator amends per row in W28C-1711):

```yaml
surface: ['api', 'mcp', 'a2a', 'webui']  # programme default for notification-agent-mcp-server
priority: must  # default; operator amends per FR
since: 2026-06-14  # carried forward unless older anchor known
last-verified: 2026-06-14
tests: []  # populated by W28C-1711 binding
crud: N/A  # default; operator amends per FR
```

## Baseline CS-NNN rows (PS-REQ-TEST-TRACE §3.4 — added by W28C-1710b)

Every project MUST have CS-NNN rows for `anon-denied`, `wrong-role-denied`, `missing-param-error` per surface. Programme baseline:

| CS-NNN | Scenario | Surface | Expected | Roles |
|---|---|---|---|---|
| `CS-005` | anon-denied | `api` | `401` | `anon` |
| `CS-006` | anon-denied | `mcp` | `401` | `anon` |
| `CS-007` | anon-denied | `a2a` | `401` | `anon` |
| `CS-008` | anon-denied | `webui` | `401` | `anon` |
| `CS-009` | wrong-role-denied | `api` | `403` | `read-only` |
| `CS-010` | wrong-role-denied | `mcp` | `403` | `read-only` |
| `CS-011` | wrong-role-denied | `a2a` | `403` | `read-only` |
| `CS-012` | wrong-role-denied | `webui` | `403` | `read-only` |
| `CS-013` | missing-param-error | `api` | `422` | `*` |
| `CS-014` | missing-param-error | `mcp` | `422` | `*` |
| `CS-015` | missing-param-error | `a2a` | `422` | `*` |
| `CS-016` | missing-param-error | `webui` | `422` | `*` |

_These CS-NNN rows are pending W28C-1711 test binding. Each row binds to one or more `@pytest.mark.negative` tests with explicit expected denial code._


<!-- W28C-1711-R3 forensic: canonical FR-NNN rows derived from legacy R-NNN/FR1.NN test bindings (2026-06-15T15:21:28Z) -->

## Functional Requirements (W28C-1711-R3 canonical-FR expansion)

Per PS-REQ-TEST-TRACE §2: every test req() must reference a backtick-wrapped FR/CS/NF-NNN row. This section adds canonical FR-NNN rows derived from existing legacy R-NNN / FR1.NN bindings + ADD-REQ probe-test functional capabilities. Test bindings rewritten to use these canonical FR-NNN IDs.

| ID | Source (legacy) | Test count | Surface (inferred) | Priority | Description |
|---|---|---:|---|---|---|
| `FR-001` | BO-1.3 | 3 | `internal` | `should` | Functional capability covered by legacy binding `BO-1.3` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-002` | BO-1.6 | 3 | `internal` | `should` | Functional capability covered by legacy binding `BO-1.6` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-003` | BR-1.1 | 22 | `internal` | `should` | Functional capability covered by legacy binding `BR-1.1` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-004` | BR-1.3 | 25 | `internal` | `should` | Functional capability covered by legacy binding `BR-1.3` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-005` | CS-1.3 | 4 | `internal` | `should` | Functional capability covered by legacy binding `CS-1.3` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-006` | FR-1.1 | 1 | `internal` | `should` | Functional capability covered by legacy binding `FR-1.1` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-007` | FR-1.15 | 8 | `internal` | `should` | Functional capability covered by legacy binding `FR-1.15` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-008` | FR-1.16 | 7 | `internal` | `should` | Functional capability covered by legacy binding `FR-1.16` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-009` | FR-1.2 | 3 | `internal` | `should` | Functional capability covered by legacy binding `FR-1.2` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-010` | FR-1.26 | 5 | `mcp` | `should` | Functional capability covered by legacy binding `FR-1.26` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-011` | FR-1.27 | 25 | `webui` | `should` | Functional capability covered by legacy binding `FR-1.27` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-012` | FR-1.6 | 18 | `internal` | `should` | Functional capability covered by legacy binding `FR-1.6` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-013` | NF-1.1 | 2 | `internal` | `should` | Functional capability covered by legacy binding `NF-1.1` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-014` | NF-1.2 | 3 | `internal` | `should` | Functional capability covered by legacy binding `NF-1.2` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-015` | NF-1.3 | 4 | `internal` | `should` | Functional capability covered by legacy binding `NF-1.3` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-016` | NF-1.5 | 5 | `internal` | `should` | Functional capability covered by legacy binding `NF-1.5` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-017` | R2 | 8 | `internal` | `should` | Functional capability covered by legacy binding `R2` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-018` | R4 | 7 | `internal` | `should` | Functional capability covered by legacy binding `R4` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-019` | SV-1.1 | 3 | `internal` | `should` | Functional capability covered by legacy binding `SV-1.1` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-020` | UC-1.3 | 18 | `internal` | `should` | Functional capability covered by legacy binding `UC-1.3` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |
| `FR-021` | UC-1.4 | 18 | `internal` | `should` | Functional capability covered by legacy binding `UC-1.4` (W28C-1711-R3 derivation; see new-or-updated-tests.tsv for test list) |


<!-- W28C-1711-R3 forensic: ADD-REQ FR rows derived from probe-test clusters (2026-06-15T15:21:28Z) -->

## Functional Requirements (W28C-1711-R3 ADD-REQ derivation)

Per W28C-1711 spec rule: ADD-REQ — create the requirement and bind the test. This section adds FR-NNN rows derived from functional probe-test clusters that had no matching FR in REQUIREMENTS.md. Each row's description is derived from the cluster's test names.

| ID | Cluster | Test count | Surface (inferred) | Priority | Description |
|---|---|---:|---|---|---|
| `FR-022` | unit | 38 | `api,mcp` | `should` | Unit (W28C-1711-R3 ADD-REQ cluster derivation) |
| `FR-023` | application | 34 | `a2a,webui` | `should` | Application (W28C-1711-R3 ADD-REQ cluster derivation) |
| `FR-024` | llm_test | 1 | `internal` | `should` | Llm Test (W28C-1711-R3 ADD-REQ cluster derivation) |
| `FR-025` | system | 19 | `api` | `should` | System (W28C-1711-R3 ADD-REQ cluster derivation) |
| `FR-026` | integration | 39 | `a2a,api,mcp,webui` | `should` | Integration (W28C-1711-R3 ADD-REQ cluster derivation) |


<!-- W28E-1807A Stream-A: canonical NF-NNN standards-conformance rows + WebUI Feedback Trace (2026-06-17) -->

## W28E-1807A Non-Functional Requirements (canonical NF-NNN — standards conformance)

Per PS-REQ-TEST-TRACE section 2: every test `req()` must reference a backtick-wrapped FR/CS/NF-NNN row.
This section gives canonical backtick `NF-NNN` IDs to the standards-conformance quality gates that were
previously bound only to `@pytest.mark.probe`. The legacy narrative `NF1.1`..`NF1.8` rows remain; these
canonical rows are the test-binding anchors. Surface = `internal`.

| ID | Requirement | Surface | Priority | Tests |
|---|---|---|---|---|
| `NF-001` | Service ships a valid `defaults.yaml` / configuration contract (no secret values; vault-referenced). | `internal` | `must` | `tests/quality/QT_STANDARDS/test_qt_defaults_yaml_exists.py` |
| `NF-002` | Service reuses approved platform packages with zero bespoke replacements (PS-COMMON-SVC-REQ CSR-001). | `internal` | `must` | `tests/quality/QT_COMPLIANCE/test_qt_package_adoption.py`; QT_PACKAGE_COMPLIANCE; QT_COMPLIANCE/test_qt_platform_package_imports.py; test_qt27_bespoke_code_scan.py; test_qt_migration_completeness.py |
| `NF-003` | Service carries the required documentation + rules-conformance doc set (PS-DOCS-CANONICAL). | `internal` | `must` | `tests/quality/QT_COMPLIANCE/test_qt3_documentation_suite.py`; test_qt_rules_compliance.py |
| `NF-004` | Test suite declares the canonical PS-REQ-TEST-TRACE marker taxonomy + req() binding gate. | `internal` | `must` | `tests/quality/QT_MARKER_GATES/test_marker_taxonomy.py` |

## W28E-1807A WebUI Feedback Trace (GarysWorkingNotes NA-* lines 2363-2575)

Per template T-W28E-A D1/D3, every atomic WebUI observation item maps to a NEW or EXISTING REQ/CS/UC row
and a test/stream owner. Source: operator GarysWorkingNotes "Notification Agent — Web UI Feedback Capture
(ENHANCED v2)". Reconciled against accepted W28A-870-R2 (`origin/main 2a5b568`, 69/69 UAT PASS_FIXED_VERIFIED)
and current `origin/main`.

Status legend: **CLOSED-870R2** = surface proven on `origin/main` by accepted W28A-870-R2 live UAT;
**STREAM-B** = functional drive-out target for W28E-1807B; **STREAM-C** = WebUI/E2E drive-out target for
W28E-1807C; **X-1825** = cross-cutting, routed to W28E-1825 (WebUI style/url canonical) per template section "Cross-cutting".

Atomic-item count: 143 (NA-D 15, NA-C 24, NA-M 15, NA-DV 4, NA-P 12, NA-AL 10, NA-U 10, NA-G 8, NA-AK 6, NA-RB 5, NA-AD 6, NA-MC 1, NA-A2 1, NA-J 7, NA-S 5, NA-X 8, NA-PR 6).
Disposition: CLOSED-870R2=73, STREAM-B=26, STREAM-C=38, X-1825=6.

| GWN item | type | maps-to REQ/UC | CSR | status | stream owner | note |
|---|---|---|---|---|---|---|
| `NA-D-01` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-02` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-03` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-04` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-05` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-06` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-07` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-08` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-09` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-10` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | CLOSED-870R2 | W28E-1807C | dashboard surface |
| `NA-D-11` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | STREAM-C | W28E-1807C | remove dashboard action-button row |
| `NA-D-12` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | STREAM-C | W28E-1807C | remove Recent Messages panel |
| `NA-D-13` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | STREAM-C | W28E-1807C | remove Runtime Summary panel |
| `NA-D-14` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | STREAM-C | W28E-1807C | remove Inventory panel |
| `NA-D-15` | functional+ui | FR-011, UC-006, UC-017 | `CSR-035` | STREAM-C | W28E-1807C | version display -> canonical self-probing footer XC-001 |
| `NA-C-01` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-02` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-03` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-04` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-05` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-06` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-07` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-08` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-09` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-10` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-11` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-12` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-13` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-14` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-15` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | STREAM-C | W28E-1807C | Create form -> popup dialog |
| `NA-C-16` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | STREAM-B | W28E-1807B | config_json -> structured per-type form |
| `NA-C-17` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-18` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-19` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-20` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-21` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | STREAM-B | W28E-1807B | Messages Sent column counter |
| `NA-C-22` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | CLOSED-870R2 | W28E-1807C | channels surface |
| `NA-C-23` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | STREAM-B | W28E-1807B | add Last Used column |
| `NA-C-24` | functional+ui | FR-008, FR-012, UC-001, UC-002, W879-REQ-01 | `CSR-035` | STREAM-B | W28E-1807B | Delete Selected bulk action no-op |
| `NA-M-01` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-02` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-03` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-04` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-05` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-06` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-07` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-08` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-09` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | STREAM-C | W28E-1807C | add Channel filter |
| `NA-M-10` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | STREAM-B | W28E-1807B | Sender column = sending user/api-key owner |
| `NA-M-11` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | STREAM-B | W28E-1807B | Subject column population |
| `NA-M-12` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-13` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-14` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | CLOSED-870R2 | W28E-1807C | messages surface |
| `NA-M-15` | functional+ui | FR-024, UC-003, UC-006, W879-REQ-02 | `CSR-035` | STREAM-C | W28E-1807C | detail dialog: explicit input/output/delivery links |
| `NA-DV-01` | functional+ui | FR-011, FR-P001, UC-007, UC-008, W879-REQ-03 | `CSR-020` | CLOSED-870R2 | W28E-1807C | deliveries surface |
| `NA-DV-02` | functional+ui | FR-011, FR-P001, UC-007, UC-008, W879-REQ-03 | `CSR-020` | CLOSED-870R2 | W28E-1807C | deliveries surface |
| `NA-DV-03` | functional+ui | FR-011, FR-P001, UC-007, UC-008, W879-REQ-03 | `CSR-020` | CLOSED-870R2 | W28E-1807C | deliveries surface |
| `NA-DV-04` | functional+ui | FR-011, FR-P001, UC-007, UC-008, W879-REQ-03 | `CSR-020` | STREAM-C | W28E-1807C | filter set: channel/date/destination/free-text |
| `NA-P-01` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-02` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-03` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-04` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-05` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-06` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-07` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-08` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-09` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | CLOSED-870R2 | W28E-1807C | prompts surface |
| `NA-P-10` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | STREAM-C | W28E-1807C | remove banner text |
| `NA-P-11` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | STREAM-C | W28E-1807C | Group ID -> group picklist |
| `NA-P-12` | functional+ui | FR-007, FR-009, UC-009, W879-REQ-04 | `CSR-035` | STREAM-C | W28E-1807C | Language ISO code/name disambiguation |
| `NA-AL-01` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | CLOSED-870R2 | W28E-1807C | audit & log surface |
| `NA-AL-02` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | CLOSED-870R2 | W28E-1807C | audit & log surface |
| `NA-AL-03` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | CLOSED-870R2 | W28E-1807C | audit & log surface |
| `NA-AL-04` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | CLOSED-870R2 | W28E-1807C | audit & log surface |
| `NA-AL-05` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | STREAM-C | W28E-1807C | relative-time render bug |
| `NA-AL-06` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | STREAM-C | W28E-1807C | remove top metric tiles |
| `NA-AL-07` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | STREAM-C | W28E-1807C | remove blurb |
| `NA-AL-08` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | STREAM-B | W28E-1807B | audit row channel column |
| `NA-AL-09` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | STREAM-C | W28E-1807C | remove Delivery Tracking sub-panel |
| `NA-AL-10` | functional+ui | CS-003, UC-020, W879-REQ-11, W879-REQ-13 | `CSR-023` | X-1825 | W28E-1807C | CROSS-PROJECT: no UI affordance to delete audit entries (PS-40/NIST AU-9); UC-110 |
| `NA-U-01` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | CLOSED-870R2 | W28E-1807C | users surface |
| `NA-U-02` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | CLOSED-870R2 | W28E-1807C | users surface |
| `NA-U-03` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | CLOSED-870R2 | W28E-1807C | users surface |
| `NA-U-04` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-C | W28E-1807C | Create User -> popup |
| `NA-U-05` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | CLOSED-870R2 | W28E-1807C | users surface |
| `NA-U-06` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-B | W28E-1807B | preferred_channel picklist of enabled channels |
| `NA-U-07` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-B | W28E-1807B | Display Name defaults to username |
| `NA-U-08` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-C | W28E-1807C | group membership multi-select in popup |
| `NA-U-09` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-C | W28E-1807C | Groups column |
| `NA-U-10` | functional+ui | FR-014, UC-010, UC-012 | `CSR-003` | STREAM-C | W28E-1807C | row-action label normalisation |
| `NA-G-01` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | CLOSED-870R2 | W28E-1807C | groups surface |
| `NA-G-02` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | CLOSED-870R2 | W28E-1807C | groups surface |
| `NA-G-03` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | CLOSED-870R2 | W28E-1807C | groups surface |
| `NA-G-04` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | CLOSED-870R2 | W28E-1807C | groups surface |
| `NA-G-05` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | STREAM-C | W28E-1807C | Create Group -> popup |
| `NA-G-06` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | STREAM-C | W28E-1807C | group detail: RBAC + API Keys links |
| `NA-G-07` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | STREAM-C | W28E-1807C | group detail: View Logs link |
| `NA-G-08` | functional+ui | FR-014, FR-021, UC-011 | `CSR-003` | STREAM-C | W28E-1807C | row-action label normalisation |
| `NA-AK-01` | functional+ui | CS-002, UC-016 | `CSR-034` | STREAM-B | W28E-1807B | api keys surface |
| `NA-AK-02` | functional+ui | CS-002, UC-016 | `CSR-034` | STREAM-C | W28E-1807C | enable/disable verb/icon/state badge |
| `NA-AK-03` | functional+ui | CS-002, UC-016 | `CSR-034` | STREAM-B | W28E-1807B | api keys surface |
| `NA-AK-04` | functional+ui | CS-002, UC-016 | `CSR-034` | STREAM-C | W28E-1807C | remove banner |
| `NA-AK-05` | functional+ui | CS-002, UC-016 | `CSR-034` | STREAM-B | W28E-1807B | Owner ID picklist + group-owned key |
| `NA-AK-06` | functional+ui | CS-002, UC-016 | `CSR-034` | X-1825 | W28E-1807C | cross-project canonical anchor |
| `NA-RB-01` | functional+ui | CS-002, CS-004, UC-014 | `CSR-006, CSR-016` | STREAM-B | W28E-1807B | rbac surface |
| `NA-RB-02` | functional+ui | CS-002, CS-004, UC-014 | `CSR-006, CSR-016` | STREAM-B | W28E-1807B | rbac surface |
| `NA-RB-03` | functional+ui | CS-002, CS-004, UC-014 | `CSR-006, CSR-016` | X-1825 | W28E-1807C | cross-project canonical layout |
| `NA-RB-04` | functional+ui | CS-002, CS-004, UC-014 | `CSR-006, CSR-016` | STREAM-C | W28E-1807C | end-to-end Playwright coverage |
| `NA-RB-05` | functional+ui | CS-002, CS-004, UC-014 | `CSR-006, CSR-016` | CLOSED-870R2 | W28E-1807B | RbacPage/RolesPage landed via 870 forward-port |
| `NA-AD-01` | ui | CSR-012, UC-021 | `CSR-012` | STREAM-C | W28E-1807C | api docs surface |
| `NA-AD-02` | ui | CSR-012, UC-021 | `CSR-012` | STREAM-C | W28E-1807C | api docs surface |
| `NA-AD-03` | ui | CSR-012, UC-021 | `CSR-012` | STREAM-C | W28E-1807C | api docs surface |
| `NA-AD-04` | ui | CSR-012, UC-021 | `CSR-012` | STREAM-C | W28E-1807C | api docs surface |
| `NA-AD-05` | ui | CSR-012, UC-021 | `CSR-012` | STREAM-C | W28E-1807C | api docs surface |
| `NA-AD-06` | ui | CSR-012, UC-021 | `CSR-012` | X-1825 | W28E-1807C | CROSS-PROJECT: docs must list all env-var settings |
| `NA-MC-01` | functional+ui | FR-010, UC-021 | `CSR-014` | STREAM-C | W28E-1807C | mcp console |
| `NA-A2-01` | functional+ui | FR-P002, UC-022 | `CSR-015` | STREAM-C | W28E-1807C | a2a console |
| `NA-J-01` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-C | W28E-1807C | page layout to platform standard |
| `NA-J-02` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-J-03` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-J-04` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-J-05` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-J-06` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-J-07` | functional+ui | FR-022, FR-026, UC-017 | `CSR-017` | STREAM-B | W28E-1807B | jobs surface |
| `NA-S-01` | functional+ui | FR-016, UC-019 | `CSR-009, CSR-010` | STREAM-C | W28E-1807C | settings surface |
| `NA-S-02` | functional+ui | FR-016, UC-019 | `CSR-009, CSR-010` | STREAM-B | W28E-1807B | Health Status must not dump DB; platform health summary |
| `NA-S-03` | functional+ui | FR-016, UC-019 | `CSR-009, CSR-010` | X-1825 | W28E-1807C | cross-project canonical Settings |
| `NA-S-04` | functional+ui | FR-016, UC-019 | `CSR-009, CSR-010` | STREAM-C | W28E-1807C | settings surface |
| `NA-S-05` | functional+ui | FR-016, UC-019 | `CSR-009, CSR-010` | STREAM-B | W28E-1807B | Profile Groups + Last login wiring |
| `NA-X-01` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | CLOSED-870R2 | W28E-1807C | cross-cutting layout/footer/runtime |
| `NA-X-02` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | CLOSED-870R2 | W28E-1807C | cross-cutting layout/footer/runtime |
| `NA-X-03` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | CLOSED-870R2 | W28E-1807C | cross-cutting layout/footer/runtime |
| `NA-X-04` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | CLOSED-870R2 | W28E-1807C | cross-cutting layout/footer/runtime |
| `NA-X-05` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | CLOSED-870R2 | W28E-1807C | cross-cutting layout/footer/runtime |
| `NA-X-06` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | STREAM-B | W28E-1807B | public message permalink page (restore) |
| `NA-X-07` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | STREAM-B | W28E-1807B | message archive navigator (W879-REQ-08 storage/archival) |
| `NA-X-08` | cross-cutting | FR-011, UC-025 | `CSR-016, CSR-035` | X-1825 | W28E-1807C | cross-project layout/icons super-task |
| `NA-PR-01` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | CLOSED-870R2 | W28E-1807B | per-user/group/channel preferences |
| `NA-PR-02` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | CLOSED-870R2 | W28E-1807B | per-user/group/channel preferences |
| `NA-PR-03` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | CLOSED-870R2 | W28E-1807B | per-user/group/channel preferences |
| `NA-PR-04` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | STREAM-B | W28E-1807B | preference->LLM propagation tests (UT+IT+AT) |
| `NA-PR-05` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | STREAM-C | W28E-1807C | active-preference indicator on message detail |
| `NA-PR-06` | functional | FR-014, FR-016, FR-021, UC-012, UC-013 | `CSR-007` | STREAM-B | W28E-1807B | cross-link REQ to preference test-evidence matrix |
