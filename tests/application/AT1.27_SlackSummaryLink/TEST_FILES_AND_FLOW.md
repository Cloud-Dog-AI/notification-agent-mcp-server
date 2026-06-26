# AT1.4 Test Files and High-Level Flow

## Test Files Status

### Available Test Files in `tests/Examples/`:
- ✅ `Test-Large-Text.md` (English, ~15,500 chars) - Used by AT1.4.1
- ✅ `Test-Large-Text-Polish.md` (Polish, ~17,600 chars) - Used by AT1.4.2
- ✅ `Test-Large-Text-Chinese.md` (Chinese, ~12,500 chars) - Used by AT1.4.3
- `Test-Brief-News.md` (English, short)
- `Test-Simple.md` (English, short)
- `Test-Multimedia-*.md` (Various formats)

### Test Scripts in `AT1.27_SlackSummaryLink/`:
1. **`test_slack_summary_link.py`** - Original AT1.4.1 test (Polish summary with 400-char limit)
   - Uses: `Test-Large-Text.md` (configurable via `test.message_file`)
   - Tests: English source → Polish delivery with summary + links

2. **`test_multilang_simple.py`** - AT1.4.2 & AT1.4.3 multi-language tests
   - **AT1.4.2**: `test_polish_to_english_chinese()`
     - Uses: `Test-Large-Text-Polish.md` (Polish source)
     - Tests: Polish → English + Chinese deliveries
   - **AT1.4.3**: `test_chinese_to_multi()`
     - Uses: `Test-Large-Text-Chinese.md` (Chinese source)
     - Tests: Chinese → Chinese + English + German deliveries

3. **`test_slack_multilanguage.py`** - Alternative implementation (has hardcoded content in fixtures)
4. **`test_simple_multilang.py`** - Another alternative implementation

### Test File Helper Function:
```python
def read_test_message(language="en") -> str:
    """
    Read test message file based on language
    
    Args:
        language: "pl" for Polish, "zh" for Chinese, "en" for English (default)
    
    Returns:
        Content of the test message file
    """
```

---

## High-Level Flow: Message Creation → Slack Delivery with Links

### Step 1: Test Creates Message via API
```
POST /messages
{
  "subject": "Test Message",
  "content": [{"type": "text", "body": "<5000-char Polish/Chinese content>"}],
  "destinations": [{
    "channel": "chat_rest_transparentbordes",
    "address": "<slack_webhook_url>",
    "preferences": {
      "language": "en",  // Target language
      "content_style": "text",
      "pdf_preference": "link"
    }
  }]
}
```

**What happens:**
- API server receives request
- Message stored in `messages` table with `message_id` and `message_guid`
- Delivery record created in `deliveries` table with state `pending`
- Message queued for processing

---

### Step 2: Delivery Worker Picks Up Delivery
**Location:** `src/core/delivery_worker.py` → `_process_delivery()`

**What happens:**
1. Worker retrieves delivery from queue
2. Loads message content from database
3. Retrieves channel configuration (including `max_length` restriction)
4. Retrieves user/destination preferences (language, content_style, pdf_preference)

---

### Step 3: LLM Formatter Formats Message
**Location:** `src/core/formatters/llm_formatter.py` → `format_message()`

**Process:**
1. **Content Extraction**: Extracts text from message content array
2. **Channel Restrictions**: Applies `max_length` from channel config
3. **Summarization** (if content > `max_length`):
   - Calls `_summarize_content()` via LLM
   - Generates summary in target language
   - Creates "View full message" link with `message_guid` and `?language={target_lang}`
4. **Translation** (if target language ≠ source):
   - Calls `_translate()` via LLM
   - Translates summary/content to target language
   - Translates link labels ("View full message" → "Zobacz pełną wiadomość")
5. **Link Generation**:
   - Full message link: `{base_url}/messages/{guid}?language={target_lang}`
   - PDF link: `{base_url}/storage/pdf/{path}?language={target_lang}`
6. **Prompt Cleanup**: Removes LLM prompt instructions from output
7. **Returns**: Formatted text with embedded links

---

### Step 4: PDF Generation (if requested)
**Location:** `src/core/delivery_worker.py` → PDF generation logic

**Process:**
1. Checks if `pdf_preference == "link"` or `pdf_preference == "attachment"`
2. Retrieves original message content (full 5000 chars)
3. Translates content to target language (if needed)
4. Converts markdown → HTML (if markdown detected)
5. Generates PDF using ReportLab with proper fonts (DejaVuSans, Noto Sans CJK)
6. Saves PDF to `storage/pdf/{year}/{month}/{day}/{filename}.pdf`
7. Returns PDF URL for inclusion in Slack message

---

### Step 5: Slack Payload Construction
**Location:** `src/core/delivery_worker.py` → `_format_content_for_slack()`

**Process:**
1. Takes formatted text from LLM formatter
2. Extracts existing links (if any)
3. Adds PDF link (if PDF was generated)
4. Ensures "View full message" link is present if:
   - Content exceeds `max_length` after translation, OR
   - Translation was applied, OR
   - Summary was created
5. Formats as Slack dict structure:
   ```python
   {
     "text": "<summary text> <link>",
     "blocks": [...]  # Optional rich formatting
   }
   ```

---

### Step 6: Delivery to Slack
**Location:** `src/core/delivery_worker.py` → Channel adapter

**Process:**
1. Converts Slack payload to HTTP POST request
2. Sends to Slack webhook URL
3. Receives response from Slack
4. Updates delivery record:
   - State: `pending` → `sent`
   - `personalised_payload`: JSON of what was sent
   - `metadata_json`: Includes language, preferences, etc.
   - `sent_at`: Timestamp

---

### Step 7: Full Message Link Access (when user clicks)
**Location:** `src/servers/api/api_server.py` → `GET /messages/{identifier}`

**Process:**
1. User clicks link: `http://server.example.com:8004/messages/{guid}?language=pl`
2. API extracts `message_guid` and `language` parameter
3. Retrieves original message content from database
4. **Caching Check**: Looks for existing translated delivery in target language
   - If found: Uses cached translation (avoids slow LLM call)
   - If not found: Translates on-demand via LLM
5. Converts markdown → HTML
6. Returns HTML page with full translated content

---

### Step 8: PDF Link Access (when user clicks)
**Location:** `src/servers/api/api_server.py` → PDF serving endpoint

**Process:**
1. User clicks PDF link: `http://server.example.com:8004/storage/pdf/...`
2. API retrieves PDF file from storage
3. Returns PDF with proper content-type headers
4. PDF contains full translated content (not summary) in proper format

---

## Key Components Summary

| Component | File | Responsibility |
|-----------|------|----------------|
| **API Server** | `src/servers/api/api_server.py` | Receives message creation requests, serves full message links |
| **Delivery Worker** | `src/core/delivery_worker.py` | Processes deliveries, orchestrates formatting, generates PDFs, sends to channels |
| **LLM Formatter** | `src/core/formatters/llm_formatter.py` | Summarizes, translates, generates links, cleans prompts |
| **PDF Generator** | `src/core/formatters/pdf_generator.py` | Converts content to PDF with proper fonts and formatting |
| **Channel Adapter** | `src/core/channels/chat_rest.py` | Formats Slack payload, sends HTTP POST to webhook |

---

## Critical Validations in Tests

For each delivery, tests validate:
1. ✅ **Slack Summary**: Contains translated summary text (not source language)
2. ✅ **Link Labels**: Translated (e.g., "Zobacz pełną wiadomość" not "View full message")
3. ✅ **Link URLs**: Include `?language={target_lang}` parameter
4. ✅ **Full Message Link**: When clicked, shows full 5000-char content in target language
5. ✅ **PDF Link**: When clicked, shows full 5000-char content in target language, properly formatted (not raw markdown)
6. ✅ **No Prompt Artifacts**: No bullet points or prompt instructions visible to users
7. ✅ **Character Limits**: Summary respects `max_length` restriction

---

## Test File Requirements

### AT1.4.2 (Polish → English/Chinese):
- **Source File**: `Test-Large-Text-Polish.md` (Polish, 5000+ chars)
- **Destinations**: English, Chinese
- **Validates**: Polish content translated to English and Chinese

### AT1.4.3 (Chinese → Chinese/English/German):
- **Source File**: `Test-Large-Text-Chinese.md` (Chinese, 5000+ chars)
- **Destinations**: Chinese (same), English, German
- **Validates**: Chinese content delivered in 3 languages

---

## Status: ✅ All Test Files Created and Tests Updated

- ✅ `Test-Large-Text-Polish.md` created (17,609 chars)
- ✅ `Test-Large-Text-Chinese.md` created (12,556 chars)
- ✅ `test_multilang_simple.py` updated to use correct source files
- ✅ Helper function `read_test_message(language)` implemented
