# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
AT1.4c: PDF Generation with Font/Stylesheet Validation

Test: Message (known language, known size) → PDF (rendered, correct font, all text)
- Validates source size and language
- Generates PDF with rendered stylesheet
- Validates: PDF format, font supports language, all text present, proper formatting
"""

import pytest
import json
import time
import sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0, str(Path(__file__).parent))
from helpers import (
    load_test_message,
    validate_language,
    validate_size,
    validate_pdf
)

from tests.utils.test_helpers import check_test_dependencies


# RULES.md: one test node = one case
PDF_CASES = [
    ("en", 5000),
    ("en", 400),
    ("pl", 5000),
    ("pl", 400),
    ("zh", 5000),
    ("zh", 400),
    ("de", 5000),
    ("de", 400),
]


def _extract_pdf_url(payload):
    """Return first PDF attachment URL in a delivery payload."""
    if payload is None:
        return None

    if isinstance(payload, dict):
        payload_items = [payload]
    elif isinstance(payload, list):
        payload_items = payload
    else:
        return None

    for item in payload_items:
        if not isinstance(item, dict):
            continue
        attachments = item.get("attachments") or []
        if not isinstance(attachments, list):
            continue
        for att in attachments:
            if not isinstance(att, dict):
                continue
            url = att.get("url")
            if not url:
                continue
            if att.get("type") == "pdf" or str(url).lower().endswith(".pdf"):
                return str(url)

    return None


def _normalize_api_path(url):
    """Normalize absolute/relative PDF URL to API-relative path."""
    if not url:
        return url

    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path

    return url if url.startswith("/") else f"/{url}"


@pytest.mark.parametrize(
    "lang,size",
    PDF_CASES,
    ids=lambda v: str(v),
)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")
def test_at1_4c_pdf_generation(api_client, loopback_channel, test_output_dir, test_config, lang, size):
    """AT1.4c: PDF generation with font/stylesheet validation (one case per run)."""
    # RULES.md: validate dependencies/services before any test logic
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="AT1.4c:test_at1_4c_pdf_generation",
    )

    # RULES.md: explicit --env requirement
    if not test_config.get("at14c_env_loaded"):
        pytest.fail("❌ HARD FAIL: --env file not loaded. Run with: pytest --env private/env-test-at14c")

    channel_id, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")

    # RULES.md: no hardcoded defaults - env must provide test.email_domain
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ test.email_domain not configured in env file (set CLOUD_DOG__NOTIFY__TEST__EMAIL_DOMAIN)")

    # RULES.md: avoid hardcoded timeouts - env must provide max_wait
    max_wait = test_config.get("test.at14c.max_wait")
    if not max_wait:
        pytest.fail("❌ test.at14c.max_wait not configured in env file (set CLOUD_DOG__NOTIFY__TEST__AT14C__MAX_WAIT)")
    max_wait = int(max_wait)

    print(f"\n{'='*80}")
    print(f"AT1.4c Test: PDF Generation ({lang.upper()}, {size} chars)")
    print(f"{'='*80}")

    try:
        source_content = load_test_message(lang, size)
    except FileNotFoundError:
        pytest.fail(f"Test message file not found for {lang} size={size}")

    if "PLACEHOLDER" in source_content.upper():
        pytest.fail(f"❌ INVALID SOURCE for {lang} ({size}): file contains PLACEHOLDER text")

    source_lang_valid, source_lang_msg = validate_language(source_content, lang)
    assert source_lang_valid, f"Source language mismatch for {lang}: {source_lang_msg}"

    # CJK fixtures are often shorter for the same nominal "size" bucket; allow wider tolerance.
    size_tolerance = 0.7 if (lang in ("zh",)) else 0.5
    source_size_valid, size_msg = validate_size(source_content, size, tolerance=size_tolerance)
    assert source_size_valid, f"Source size invalid: {size_msg}"

    actual_size = len(source_content)
    print(f"✅ Source validated: {lang.upper()}, {actual_size} chars ({size_msg})")

    message_payload = {
        "content": [{"type": "text", "body": source_content}],
        "destinations": [{
            "channel": channel_name,
            "address": f"test_{lang}_pdf{email_domain}",
            "preferences": {
                "language": lang,
                "generate_pdf": True,
            }
        }]
    }

    response = api_client.post("/messages", json=message_payload)
    assert response.status_code == 201, f"Failed to create message: {response.text}"
    response_data = response.json()
    message_id = response_data.get("message_id") or response_data.get("id")
    assert message_id, f"No message_id in response: {response_data}"
    print(f"✅ Message created: ID={message_id}")

    wait_time = 0
    pdf_url = None
    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5

        deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
        if deliveries_response.status_code != 200:
            if wait_time % 30 == 0:
                print(f"⚠️  Waiting for deliveries... ({wait_time}s/{max_wait}s)")
            continue

        deliveries_data = deliveries_response.json()
        deliveries_list = deliveries_data.get("items", []) if isinstance(deliveries_data, dict) else deliveries_data
        if not deliveries_list:
            if wait_time % 30 == 0:
                print(f"⚠️  No deliveries yet... ({wait_time}s/{max_wait}s)")
            continue

        delivery = deliveries_list[0]
        state = delivery.get("state")
        if state == "hard_failed":
            pytest.fail(f"Delivery hard failed: {delivery.get('error_message', 'Unknown error')}")

        if state != "sent":
            if wait_time % 30 == 0:
                print(f"⚠️  Delivery state: {state} (waiting for 'sent')... ({wait_time}s/{max_wait}s)")
            continue

        payload_str = delivery.get("personalised_payload", "{}")
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        pdf_url = _extract_pdf_url(payload)
        print(f"✅ Delivery complete ({wait_time}s)")
        break

    assert pdf_url, f"No PDF attachment generated after {max_wait}s"

    # Download and validate PDF (support absolute or relative URLs)
    pdf_path = _normalize_api_path(pdf_url)
    api_base = str(api_client.base_url).rstrip("/")
    pdf_response = api_client.get(pdf_path)
    assert pdf_response.status_code == 200, "PDF download failed"
    assert pdf_response.headers.get("content-type") == "application/pdf"
    pdf_content = pdf_response.content

    pdf_valid, pdf_details = validate_pdf(
        pdf_content,
        lang,
        expected_min_size=actual_size,
        source_content=source_content,
    )

    print(f"\n{'='*80}")
    print(f"PDF Validation Results for {lang.upper()} {size}:")
    print(f"{'='*80}")
    print(f"  Pages: {pdf_details.get('pages', 'N/A')}")
    print(f"  Extracted text length: {pdf_details.get('text_length', 'N/A')} chars")
    print(f"  Language valid: {pdf_details.get('language_valid', False)}")
    print(f"  Language indicators: {pdf_details.get('language_indicators', [])}")
    print(f"  Size valid: {pdf_details.get('size_valid', False)}")
    print(f"  Size message: {pdf_details.get('size_message', 'N/A')}")
    if pdf_details.get("cjk_corruption"):
        print(f"  ❌ CJK CORRUPTION: {pdf_details.get('cjk_message', 'Unknown')}")
    if pdf_details.get("formatting_issues"):
        print("  ❌ FORMATTING ISSUES:")
        for issue in pdf_details["formatting_issues"]:
            print(f"     - {issue}")
    if pdf_details.get("markdown_markers"):
        print(f"  ❌ MARKDOWN ARTIFACTS: {pdf_details['markdown_markers']}")
    if pdf_details.get("wrong_headers"):
        print(f"  ❌ PROMPT ARTIFACTS: {pdf_details['wrong_headers']}")
    print(f"{'='*80}\n")

    assert pdf_valid, f"❌ PDF VALIDATION FAILED for {lang} {size}:\n{json.dumps(pdf_details, indent=2)}"
    print("✅ PDF fully validated: All checks passed")

    output_file = test_output_dir / f"at1_4c_{lang}_{size}_output.pdf"
    output_file.write_bytes(pdf_content)
    print(f"✅ PDF saved: {output_file}")

    print(f"📎 PDF URL: {pdf_url}")
    print(f"📄 Message Center: {api_base}/messages/{message_id}")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

