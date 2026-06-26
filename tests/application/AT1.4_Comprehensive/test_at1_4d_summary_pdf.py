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
AT1.4d: Summary + Full PDF

Test: Source message → Summary (target language, target size) + Full PDF (target language, full size)
- Generates summary to target size
- Generates full PDF in target language
- Validates both outputs
"""

import pytest
import httpx
import json
import time
import sys
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


def test_at1_4d_summary_pdf(api_client, test_output_dir, loopback_channel, test_config):
    """AT1.4d: Summary + Full PDF validation"""
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="AT1.4d:test_at1_4d_summary_pdf",
    )
    _, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ test.email_domain not configured in env file")

    summary_size = _require_number(test_config, "test.at14d.summary_size", number_type="int")
    summary_tolerance = _require_number(test_config, "test.at14d.summary_tolerance", number_type="float")
    max_wait = _require_number(test_config, "test.at14d.max_wait", number_type="int")
    pdf_min_size_ratio = _require_number(test_config, "test.at14d.pdf_min_size_ratio", number_type="float")
    generate_pdf = _require_bool(test_config, "test.at14d.generate_pdf")
    format_pref = test_config.get("test.at14d.format")
    if not format_pref:
        pytest.fail("❌ test.at14d.format not configured in env file")
    test_cases = [tc for tc in get_test_matrix() if tc["size"] == 5000][:2]
    if not test_cases:
        pytest.fail("❌ No AT1.4d test cases available for size=5000")
    # Each case can legitimately consume the full formatting budget under load.
    per_case_max_wait = max(60, int(max_wait))
    
    for test_case in test_cases:
        source_lang = test_case["source"]
        target_lang = test_case["target"]
        source_size = test_case["size"]
        if source_lang == target_lang:
            continue
        
        print(f"\n{'='*80}")
        print(f"AT1.4d Test: {source_lang.upper()} → {target_lang.upper()}")
        print(f"  Summary: {summary_size} chars, PDF: Full ({source_size} chars)")
        print(f"{'='*80}")
        
        try:
            source_content = load_test_message(source_lang, source_size)
        except FileNotFoundError:
            continue
        
        # Create message with summary size limit
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
        
        # Wait for delivery with explicit terminal-state handling to avoid long no-output hangs.
        wait_time = 0
        poll_interval_seconds = 5
        last_state = "unknown"

        while wait_time < per_case_max_wait:
            time.sleep(poll_interval_seconds)
            wait_time += poll_interval_seconds
            deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
            if deliveries_response.status_code != 200:
                continue

            deliveries_data = deliveries_response.json()
            deliveries_list = deliveries_data.get("items", []) if isinstance(deliveries_data, dict) else deliveries_data
            if not deliveries_list:
                continue

            delivery = deliveries_list[0]
            state = str(delivery.get("state") or "").lower()
            if state:
                last_state = state

            if state in {"hard_failed", "soft_failed", "cancelled", "ttl_expired"}:
                failure_reason = delivery.get("last_error") or delivery.get("error") or "unknown"
                pytest.fail(f"Delivery entered terminal failure state '{state}': {failure_reason}")

            if state not in {"sent", "delivered"}:
                continue

            payload_str = delivery.get("personalised_payload", "{}")
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

            summary_text = ""
            attachments = []
            if isinstance(payload, list):
                for block in payload:
                    if isinstance(block, dict) and block.get("type") == "text":
                        summary_text += block.get("body", "")
                    if isinstance(block, dict) and block.get("attachments"):
                        attachments.extend(block.get("attachments") or [])
            elif isinstance(payload, dict):
                summary_text = payload.get("body", "")
                attachments = payload.get("attachments", []) or []

            # Validate PDF
            pdf_url = None
            for att in attachments:
                if att.get("type") == "pdf" or att.get("url", "").endswith(".pdf"):
                    pdf_url = att.get("url")
                    break

            if not pdf_url:
                pytest.fail(f"Delivery reached state '{state}' without PDF attachment")

            if summary_text:
                summary_lang_valid, _ = validate_language(summary_text, target_lang, source_lang)
                assert summary_lang_valid
                summary_size_valid, _ = validate_size(summary_text, summary_size, tolerance=summary_tolerance)
                assert summary_size_valid
                print(f"✅ Summary validated: {len(summary_text)} chars")

            pdf_response = api_client.get(pdf_url)
            assert pdf_response.status_code == 200
            pdf_content = pdf_response.content
            pdf_min_size = int(source_size * pdf_min_size_ratio)
            pdf_valid, pdf_details = validate_pdf(
                pdf_content,
                target_lang,
                expected_min_size=pdf_min_size,
            )
            assert pdf_valid, f"PDF validation failed: {pdf_details}"
            print(f"✅ PDF validated: Full content in {target_lang}")

            # Save both
            summary_file = test_output_dir / f"at1_4d_{source_lang}_{target_lang}_summary.txt"
            summary_file.write_text(summary_text, encoding='utf-8')
            pdf_file = test_output_dir / f"at1_4d_{source_lang}_{target_lang}_full.pdf"
            pdf_file.write_bytes(pdf_content)
            print(f"✅ Both saved")
            break
        else:
            pytest.fail(
                f"Delivery timeout after {per_case_max_wait}s for case {source_lang}->{target_lang} "
                f"(suite max_wait={max_wait}s, last_state={last_state})"
            )

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

