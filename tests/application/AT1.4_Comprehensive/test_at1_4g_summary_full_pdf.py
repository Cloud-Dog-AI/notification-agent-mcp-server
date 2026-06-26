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
AT1.4g: Summary + Full + PDF (All Saved)

Test: Source message → Summary + Full + PDF (all 3 saved to files, all validated)
- Generates summary (target language, target size)
- Generates full translated message (target language, full size)
- Generates PDF (target language, full size)
- Saves all 3 to files
- Validates all 3
"""

import pytest
import httpx
import json
import time
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import (
    load_test_message,
    validate_language,
    validate_size,
    validate_pdf,
    get_test_matrix
)

from tests.utils.test_helpers import check_test_dependencies


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ {key} not configured in env file")
    try:
        return int(value) if number_type == "int" else float(value)
    except (TypeError, ValueError):
        pytest.fail(f"❌ {key} must be a valid {number_type}")


def _require_bool(test_config, key: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ {key} not configured in env file")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes"}:
            return True
        if value.lower() in {"false", "0", "no"}:
            return False
    pytest.fail(f"❌ {key} must be a boolean")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_4g_summary_full_pdf(api_client, test_output_dir, loopback_channel, test_config):
    """AT1.4g: Summary + Full + PDF (all saved and validated)"""
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="AT1.4g:test_at1_4g_summary_full_pdf",
    )
    _, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ test.email_domain not configured in env file")

    summary_size = _require_number(test_config, "test.at14g.summary_size", number_type="int")
    summary_tolerance = _require_number(test_config, "test.at14g.summary_tolerance", number_type="float")
    full_size_tolerance = _require_number(test_config, "test.at14g.full_size_tolerance", number_type="float")
    max_wait = _require_number(test_config, "test.at14g.max_wait", number_type="int")
    pdf_min_size_ratio = _require_number(test_config, "test.at14g.pdf_min_size_ratio", number_type="float")
    generate_pdf = _require_bool(test_config, "test.at14g.generate_pdf")
    format_pref = test_config.get("test.at14g.format")
    if not format_pref:
        pytest.fail("❌ test.at14g.format not configured in env file")
    test_cases = [tc for tc in get_test_matrix() if tc["size"] == 5000][:2]
    
    for test_case in test_cases:
        source_lang = test_case["source"]
        target_lang = test_case["target"]
        source_size = test_case["size"]
        if source_lang == target_lang:
            continue
        
        print(f"\n{'='*80}")
        print(f"AT1.4g Test: {source_lang.upper()} → {target_lang.upper()}")
        print(f"  Summary: {summary_size} chars, Full: {source_size} chars, PDF: Full")
        print(f"{'='*80}")
        
        try:
            source_content = load_test_message(source_lang, source_size)
        except FileNotFoundError:
            continue
        
        # Create message with summary size and PDF format
        message_payload = {
            "content": [{"type": "text", "body": source_content}],
            "destinations": [{
                "channel": channel_name,
                "address": f"test_{source_lang}_{target_lang}{email_domain}",
                "preferences": {
                    "language": target_lang,
                    "max_length": summary_size,
                    "format": format_pref,
                    "generate_pdf": generate_pdf,
                }
            }]
        }
        
        response = api_client.post("/messages", json=message_payload)
        assert response.status_code == 201
        response_data = response.json()
        message_id = response_data.get("message_id") or response_data.get("id")
        assert message_id, f"No message id in response: {response_data}"
        
        # Wait for delivery
        wait_time = 0
        while wait_time < max_wait:
            time.sleep(5)
            wait_time += 5
            deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
            if deliveries_response.status_code != 200:
                continue

            deliveries_data = deliveries_response.json()
            deliveries_list = deliveries_data.get("items", []) if isinstance(deliveries_data, dict) else deliveries_data
            if not deliveries_list:
                continue

            delivery = deliveries_list[0]
            if delivery.get("state") != "sent":
                continue

            payload_str = delivery.get("personalised_payload", "{}")
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

            summary_text = ""
            links = []
            attachments = []
            if isinstance(payload, list):
                for block in payload:
                    if isinstance(block, dict) and block.get("type") == "text":
                        summary_text += block.get("body", "")
                    if isinstance(block, dict) and block.get("links"):
                        links.extend(block.get("links") or [])
                    if isinstance(block, dict) and block.get("attachments"):
                        attachments.extend(block.get("attachments") or [])
            elif isinstance(payload, dict):
                summary_text = payload.get("body", "")
                links = payload.get("links", []) or []
                attachments = payload.get("attachments", []) or []

            full_message_url = None
            for link in links:
                if "full" in link.get("label", "").lower():
                    full_message_url = link.get("url")
                    break

            pdf_url = None
            for att in attachments:
                if att.get("type") == "pdf" or att.get("url", "").endswith(".pdf"):
                    pdf_url = att.get("url")
                    break

            if summary_text and full_message_url and pdf_url:
                summary_lang_valid, _ = validate_language(summary_text, target_lang, source_lang)
                assert summary_lang_valid
                summary_size_valid, _ = validate_size(summary_text, summary_size, tolerance=summary_tolerance)
                assert summary_size_valid
                print(f"✅ Summary validated")

                full_response = api_client.get(full_message_url)
                assert full_response.status_code == 200
                full_html = full_response.text
                content_match = re.search(r'<div[^>]*class="message-content"[^>]*>(.*?)</div>', full_html, re.DOTALL)
                if content_match:
                    full_text = re.sub(r'<[^>]+>', '', content_match.group(1))
                else:
                    full_text = full_html

                full_lang_valid, _ = validate_language(full_text, target_lang, source_lang)
                assert full_lang_valid
                full_size_valid, _ = validate_size(full_text, source_size, tolerance=full_size_tolerance)
                assert full_size_valid
                print(f"✅ Full message validated")

                pdf_response = api_client.get(pdf_url)
                assert pdf_response.status_code == 200
                pdf_content = pdf_response.content
                pdf_min_size = int(source_size * pdf_min_size_ratio)
                pdf_valid, pdf_details = validate_pdf(
                    pdf_content,
                    target_lang,
                    expected_min_size=pdf_min_size,
                )
                assert pdf_valid, f"PDF invalid: {pdf_details}"
                print(f"✅ PDF validated")

                summary_file = test_output_dir / f"at1_4g_{source_lang}_{target_lang}_summary.txt"
                summary_file.write_text(summary_text, encoding='utf-8')
                full_file = test_output_dir / f"at1_4g_{source_lang}_{target_lang}_full.txt"
                full_file.write_text(full_text, encoding='utf-8')
                pdf_file = test_output_dir / f"at1_4g_{source_lang}_{target_lang}_full.pdf"
                pdf_file.write_bytes(pdf_content)
                print(f"✅ All 3 saved")
                break
        else:
            pytest.fail(f"Timeout")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

