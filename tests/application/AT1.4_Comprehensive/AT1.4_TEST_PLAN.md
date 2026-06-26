# AT1.4 Comprehensive Test Suite - Implementation Plan

## Overview

This document outlines the complete breakdown of AT1.4 into smaller, focused tests (AT1.4a through AT1.4k) that validate translation, summarization, PDF generation, and message center integration.

## Prerequisites

### 1. Loop-Back Channel ✅
- **Status**: Created (`src/adapters/loopback_adapter.py`)
- **Purpose**: Saves messages to system, returns message center URL (no external delivery)
- **Registration**: Added to `src/adapters/registry.py`
- **Configuration**: Available to all users, always saves

### 2. Test Message Files
**Location**: `tests/Examples/`
**Required Files**:
- `Test-5000chars-en.md` (English, 5000 chars)
- `Test-400chars-en.md` (English, 400 chars)
- `Test-5000chars-pl.md` (Polish, 5000 chars)
- `Test-400chars-pl.md` (Polish, 400 chars)
- `Test-5000chars-zh.md` (Chinese, 5000 chars)
- `Test-400chars-zh.md` (Chinese, 400 chars)
- `Test-5000chars-ar.md` (Arabic, 5000 chars)
- `Test-400chars-ar.md` (Arabic, 400 chars)
- `Test-5000chars-de.md` (German, 5000 chars)
- `Test-400chars-de.md` (German, 400 chars)
- `Test-5000chars-hi.md` (Hindi, 5000 chars)
- `Test-400chars-hi.md` (Hindi, 400 chars)

**Status**: ⏳ To be created

### 3. Configuration Updates ✅
- **Header/Intro Templates**: Added to `default.yaml` → `messages.header_templates`
- **Link Labels**: Added to `default.yaml` → `messages.link_labels`
- **Status**: ✅ Complete

## Test Structure

### Test Directory
```
tests/application/AT1.4_Comprehensive/
├── test_at1_4a_translation_summary.py      # AT1.4a
├── test_at1_4b_translation_full.py         # AT1.4b
├── test_at1_4c_pdf_generation.py           # AT1.4c
├── test_at1_4d_summary_pdf.py              # AT1.4d
├── test_at1_4e_pdf_storage_url.py          # AT1.4e
├── test_at1_4f_summary_full.py             # AT1.4f
├── test_at1_4g_summary_full_pdf.py          # AT1.4g
├── test_at1_4h_all_to_api.py               # AT1.4h
├── test_at1_4i_complete_message.py          # AT1.4i
├── test_at1_4j_loopback_delivery.py         # AT1.4j
├── test_at1_4k_full_validation.py           # AT1.4k
├── conftest.py                              # Shared fixtures
└── helpers.py                                # Test utilities
```

## Test Specifications

### AT1.4a: Translation with Summary Size Validation
**Input**: Source message (source language, source size), target language, target summary size
**Process**:
1. Load source message
2. Validate source language and size
3. Generate summary in target language to target size
4. Output to console/file
**Validations**:
- ✅ Target language correct
- ✅ Target size correct (within tolerance)
- ✅ Source language preserved in original
- ✅ No LLM prompt artifacts

### AT1.4b: Full Translation (Same Size)
**Input**: Source message (source language, source size), target language
**Process**:
1. Load source message
2. Validate source language and size
3. Translate full message to target language (same size)
4. Save to file
**Validations**:
- ✅ Source size preserved
- ✅ Source language correct
- ✅ Target size matches source (within translation variance)
- ✅ Target language correct
- ✅ No LLM prompt artifacts

### AT1.4c: PDF Generation with Font/Stylesheet
**Input**: Message (known language, known size)
**Process**:
1. Load message
2. Validate size and language
3. Generate PDF with rendered stylesheet
4. Validate PDF
**Validations**:
- ✅ PDF renders correctly
- ✅ Font supports language (CJK, Arabic, Hindi, etc.)
- ✅ All text present (right size/layout)
- ✅ Same language as source
- ✅ Proper formatting (no raw markdown)

### AT1.4d: Summary + Full PDF
**Input**: Source message, target language, target summary size
**Process**:
1. Generate summary (target language, target size)
2. Generate full PDF (target language, full original size)
3. Save both to files
**Validations**:
- ✅ Summary: target language, target size
- ✅ PDF: target language, full size, proper formatting

### AT1.4e: PDF Storage + URL + Link Text
**Input**: Message (known language, known size)
**Process**:
1. Generate PDF
2. Upload to API storage
3. Get URL
4. Validate URL returns correct PDF
5. Generate link text in target language
**Validations**:
- ✅ PDF uploaded successfully
- ✅ URL works and returns correct PDF
- ✅ PDF language correct
- ✅ PDF size correct
- ✅ Link text in target language

### AT1.4f: Summary + Full Translated Message
**Input**: Source message, target language, summary size
**Process**:
1. Generate summary (target size)
2. Generate full translated message
3. Save both to files
**Validations**:
- ✅ Summary: target size, target language
- ✅ Full message: full size, target language
- ✅ Both saved correctly

### AT1.4g: Summary + Full + PDF (All Saved)
**Input**: Source message, target language, summary size
**Process**:
1. Generate summary (target language, target size)
2. Generate full translated message (target language, full size)
3. Generate PDF (target language, full size)
4. Save all 3 to files
**Validations**:
- ✅ All 3 outputs: correct sizes, correct languages
- ✅ PDF format correct (font, stylesheet, layout)

### AT1.4h: All to API Storage
**Input**: Source message, target language, summary size
**Process**:
1. Generate summary, full, PDF, and save source
2. Save all 4 via API storage
3. Get 4 URLs
4. Validate all URLs point to correct files with correct content
**Validations**:
- ✅ All 4 files saved
- ✅ All 4 URLs work
- ✅ All 4 have correct content (size, language, format)

### AT1.4i: Complete Message with Links
**Input**: Source message, target language, summary size
**Process**:
1. Generate summary (target language)
2. Generate header/intro with message#/job# (target language)
3. Generate 3 links:
   - Source message link (source language label)
   - Full translated message link (target language label)
   - PDF link (target language label)
4. Combine into complete message
5. Display to console
**Validations**:
- ✅ Summary in target language
- ✅ Header/intro in target language with message#/job#
- ✅ All 3 links in correct languages
- ✅ Links point to correct URLs
- ✅ Complete message displayed

### AT1.4j: Loop-Back Channel Delivery
**Input**: Complete message (from AT1.4i)
**Process**:
1. Submit to loop-back channel
2. Get message center URL
3. Validate URL points to correct message
4. Validate message center shows:
   - Full message in target language (correct size)
   - Link to source message (source language, correct size)
   - Link to PDF (target language, correct font/language)
**Validations**:
- ✅ Delivery successful
- ✅ Message center URL works
- ✅ Full message in target language
- ✅ Source link works and shows source language
- ✅ PDF link works and shows target language PDF

### AT1.4k: Full End-to-End Validation
**Input**: Source message, target language, summary size
**Process**:
1. Complete AT1.4j flow
2. Return final "sent" message
**Validations**:
- ✅ Header/intro in target language with message#/job#
- ✅ Summary in target language
- ✅ Link to source (label in source language)
- ✅ Link to full message (label in target language)
- ✅ Link to PDF (label in target language, correct PDF)
- ✅ Link to message center (label in target language)

## Test Matrix

### 5000 Character Messages
**Test Combinations**:
- English → French, Polish, Chinese, Arabic
- Polish → English, Chinese, Arabic, German
- Chinese → English, Arabic, German
- Same language (no translation): English→English, Chinese→Chinese

### 400 Character Messages (No Summary)
**Test Combinations**:
- English → French, Polish, Chinese
- Polish → English, Arabic, German
- Chinese → English, German
- Same language: English→English, Chinese→Chinese

## Implementation Status

- [x] Loop-back adapter created
- [x] Loop-back adapter registered
- [x] Header/intro templates added to config
- [x] Link labels added to config
- [ ] Test message files created (12 files)
- [ ] Test framework created (conftest.py, helpers.py)
- [ ] AT1.4a implemented
- [ ] AT1.4b implemented
- [ ] AT1.4c implemented
- [ ] AT1.4d implemented
- [ ] AT1.4e implemented
- [ ] AT1.4f implemented
- [ ] AT1.4g implemented
- [ ] AT1.4h implemented
- [ ] AT1.4i implemented
- [ ] AT1.4j implemented
- [ ] AT1.4k implemented
- [ ] Test matrix implemented
- [ ] All prerequisites validated

## Next Steps

1. Create test message files (start with English, Polish, Chinese)
2. Create test framework (conftest.py, helpers.py)
3. Implement AT1.4a (simplest - translation + summary)
4. Implement remaining tests incrementally
5. Run test matrix for all language combinations

