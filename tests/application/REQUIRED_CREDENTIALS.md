# Required Credentials for Application/Business Tests

**Date**: 2025-12-04  
**Status**: ⚠️ **CRITICAL** - Tests will fail without these credentials

---

## Overview

**CRITICAL RULE**: Application/Business Tests (AT) **MUST** use real adapters. Mock adapters are **NOT ALLOWED** in AT tests.

All AT tests that use email or Slack channels **REQUIRE** real credentials to be configured.

---

## SMTP/Email Credentials

### Required for Tests
- AT1.1: Email Comprehensive Validation
- AT1.2: Email French Translation
- AT1.3: Email Attachments
- AT1.5: French Summary
- AT1.17: Email Validation
- AT1.18: T26 Comprehensive (70 subtests)
- AT1.19: PDF Email Attachment
- AT1.20: Media Email
- AT1.22: Audio/Video Email
- AT1.23: Multimedia PDF (UC1.6)
- AT1.24: HTML Pages (UC1.7)
- AT1.25: Storage Output
- AT1.26: Multi-Channel Multimedia

**Total**: 13 tests require SMTP credentials

### Required Configuration

**Channel Name**: `<DEFAULT_CHANNEL_NAME>`

**Environment Variables**:
```bash
# SMTP Server Configuration
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__HOST=<SMTP_SERVER_HOST>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__PORT=<SMTP_PORT>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USERNAME=<SMTP_USERNAME>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__PASSWORD=<SMTP_PASSWORD>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__FROM_ADDRESS=<FROM_EMAIL>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USE_TLS=<true|false>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USE_STARTTLS=<true|false>
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__TIMEOUT=<seconds>
```

**Example**:
```bash
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__HOST=smtp.example.com
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__PORT=587
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USERNAME=notify@cloud-dog.net
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__PASSWORD=your-password
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__FROM_ADDRESS=noreply@cloud-dog.net
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USE_TLS=false
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__<DEFAULT_CHANNEL_NAME>__USE_STARTTLS=true
```

**Status**: ❌ **MISSING** - Need user to provide:
- SMTP server host
- SMTP server port
- SMTP username
- SMTP password
- From email address

---

## Slack Webhook Credentials

### Required for Tests
- AT1.4: Slack Summary Link
- AT1.18: T26 Comprehensive
- AT1.19: PDF Slack Attachment
- AT1.20: Media Slack
- AT1.23: Multimedia PDF (UC1.6)
- AT1.24: HTML Pages (UC1.7)
- AT1.26: Multi-Channel Multimedia

**Total**: 7 tests require Slack credentials

### Required Configuration

**Channel Name**: `chat_rest_transparentbordes`

**Environment Variables**:
```bash
# Slack Webhook Configuration
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT=<SLACK_WEBHOOK_URL>
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__AUTH_TYPE=none
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__TIMEOUT=30
```

**Example**:
```bash
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT=<SLACK_WEBHOOK_URL>
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__AUTH_TYPE=none
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__TIMEOUT=30
```

**Current Value Found**:
- Test code references: `<SLACK_WEBHOOK_URL>`
- **Needs verification**: Is this webhook still valid?

**Status**: ⚠️ **NEEDS VERIFICATION** - Webhook URL exists but needs validation

---

## Test Recipients

### Email Recipients Used in Tests

**Test Recipients** (must be valid email addresses):
- `<TEST_EMAIL>`
- `<SMTP_USERNAME>`
- `idp-test1@cloud-dog.net`
- `idp-test2@cloud-dog.net`
- `idp-test3@cloud-dog.net`
- `<TEST_EMAIL_ALT_1>`
- `<TEST_EMAIL_ALT_2>`

**Status**: ⚠️ **NEEDS VERIFICATION** - Are these email addresses valid and accessible?

---

## File Storage Credentials

### Required for Tests
- AT1.21: File Channel
- AT1.25: Storage Output
- AT1.26: Multi-Channel Multimedia

**Status**: ✅ **CONFIGURED** - File storage uses local filesystem (no credentials needed)

**Optional Storage Backends** (if configured):
- WebDAV: URL, username, password
- FTP: Host, port, username, password
- S3: Endpoint, bucket, access_key, secret_key, region

---

## Credentials Template

Create a file `tests/application/test.env` with:

```bash
# SMTP/Email Configuration
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__HOST=
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__PORT=
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__USERNAME=
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__PASSWORD=
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__FROM_ADDRESS=
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__USE_TLS=false
CLOUD_DOG__NOTIFY__CHANNELS__SMTP__EMAIL_DEFAULT__USE_STARTTLS=true

# Slack Webhook Configuration
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT=
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__AUTH_TYPE=none
CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__TIMEOUT=30
```

**Usage**:
```bash
# Load credentials before running tests
source tests/application/test.env

# Run tests
pytest tests/application/ -v
```

---

## Questions for User

### SMTP Credentials
1. **What SMTP server should be used for tests?**
   - Host: _______________
   - Port: _______________
   - Username: _______________
   - Password: _______________
   - From Address: _______________

2. **Should tests use a test SMTP server or production?**
   - [ ] Test SMTP server (recommended)
   - [ ] Production SMTP server

3. **Are test email recipients valid?**
   - `<TEST_EMAIL>` - [ ] Valid [ ] Invalid
   - `<SMTP_USERNAME>` - [ ] Valid [ ] Invalid
   - Others - [ ] Valid [ ] Invalid

### Slack Credentials
1. **Is the Slack webhook URL still valid?**
   - URL: `<SLACK_WEBHOOK_URL>`
   - [ ] Valid [ ] Invalid [ ] Needs new webhook

2. **Should tests post to a test channel or production?**
   - [ ] Test Slack channel (recommended)
   - [ ] Production Slack channel

3. **What Slack channel should receive test messages?**
   - Channel: _______________

---

## Next Steps

1. **User provides credentials** (SMTP and Slack)
2. **Update test environment** with credentials
3. **Verify credentials** work (test SMTP connection, test Slack webhook)
4. **Update tests** to use real adapters
5. **Run tests** to verify actual delivery

---

**Last Updated**: 2025-12-04

