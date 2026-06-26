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
AT1.4a: Translation with Summary Size Validation

Test: Source message (source language, source size) → Target summary (target language, target size)
- Validates source language and size
- Generates summary in target language to target size
- Outputs to console/file
- Validates: target language, target size, no prompt artifacts
"""

import pytest
import httpx
from pathlib import Path
from helpers import (
    load_test_message,
    validate_language,
    validate_size,
    validate_no_prompt_artifacts,
    get_test_matrix
)


import json
import time


# Keep scope small and runnable one-at-a-time (RULES.md): first 3 summary cases at 5000 chars.
SUMMARY_CASES = [tc for tc in get_test_matrix() if tc["size"] == 5000][:3]


@pytest.mark.parametrize(
    "test_case",
    SUMMARY_CASES,
    ids=lambda tc: f"{tc['source']}_{tc['target']}_{tc['size']}_summary",
)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")
def test_at1_4a_translation_summary(api_client, loopback_channel, test_output_dir, test_config, test_case, test_email_domain):
    """
    AT1.4a: Test translation with summary size validation
    
    For each test case:
    1. Load source message
    2. Validate source language and size
    3. Generate summary via API
    4. Validate target language, size, no artifacts
    """
    # Check for --env requirement
    if not test_config.get("at14a_env_loaded"):
        pytest.fail("❌ HARD FAIL: --env file not loaded. Run with: pytest --env private/env-test-at14a")
    
    channel_id, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")

    source_lang = test_case["source"]
    target_lang = test_case["target"]
    source_size = test_case["size"]
    target_summary_size = test_config.get("test.at14a.summary_size", 400)

    print(f"\n{'='*80}")
    print(f"AT1.4a Test: {source_lang.upper()} → {target_lang.upper()} (Summary: {target_summary_size} chars)")
    print(f"{'='*80}")

    # 1. Load source message
    try:
        source_content = load_test_message(source_lang, source_size)
    except FileNotFoundError as e:
        pytest.fail(f"Test message file not found: {e}")

    print(f"✅ Loaded source message: {len(source_content)} chars ({source_lang})")

    # 2. Validate source language and size
    source_lang_valid, source_indicators = validate_language(source_content, source_lang)
    assert source_lang_valid, f"Source content not in {source_lang}: {source_indicators}"
    print(f"✅ Source language validated: {source_lang}")

    source_size_valid, size_msg = validate_size(source_content, source_size, tolerance=0.1)
    assert source_size_valid, f"Source size invalid: {size_msg}"
    print(f"✅ Source size validated: {size_msg}")

    # 3. Generate summary via API
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ HARD FAIL: test.email_domain not configured in env file")
    message_payload = {
        "content": [{"type": "text", "body": source_content}],
        "destinations": [{
            "channel": channel_name,
            "address": f"test_{source_lang}_{target_lang}{email_domain}",
            "preferences": {
                "language": target_lang,
                "max_length": target_summary_size
            }
        }]
    }

    response = api_client.post("/messages", json=message_payload)
    assert response.status_code == 201, f"Failed to create message: {response.text}"

    message_data = response.json()
    message_id = message_data.get("id") or message_data.get("message_id")
    assert message_id, f"Message ID not found in response: {message_data}"
    print(f"✅ Message created: {message_id}")

    # Wait for delivery to complete
    summary_text = None  # Initialize
    max_wait = test_config.get("test.at14a.max_wait", 300)
    wait_time = 0
    failed_count = 0
    max_failures = 3

    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5

        deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
        if deliveries_response.status_code != 200:
            print(f"⚠️  Waiting for deliveries... ({wait_time}s/{max_wait}s)")
            continue

        deliveries_data = deliveries_response.json()
        deliveries_list = deliveries_data.get('items', []) if isinstance(deliveries_data, dict) else deliveries_data

        if not deliveries_list:
            print(f"⚠️  No deliveries found yet... ({wait_time}s/{max_wait}s)")
            continue

        delivery = deliveries_list[0]
        state = delivery.get('state')

        if state == 'sent':
            payload_str = delivery.get('personalised_payload', '{}')
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

            if isinstance(payload, list) and len(payload) > 0:
                summary_text = payload[0].get('body', '') if isinstance(payload[0], dict) else str(payload[0])
            elif isinstance(payload, dict):
                summary_text = payload.get('body', '') or payload.get('text', '')
            else:
                summary_text = str(payload)

            if summary_text:
                print(f"✅ Summary generated: {len(summary_text)} chars")
                break
            else:
                print(f"⚠️  Delivery sent but no summary text found... ({wait_time}s/{max_wait}s)")
        elif state in ['hard_failed', 'soft_failed', 'failed']:
            failed_count += 1
            error_msg = delivery.get('error_message', 'No error message')
            print(f"❌ Delivery {state}: {error_msg}")
            if failed_count >= max_failures:
                pytest.fail(f"Delivery failed {failed_count} times: {error_msg}")
            print(f"⚠️  Retrying... ({failed_count}/{max_failures}) ({wait_time}s/{max_wait}s)")
        else:
            print(f"⚠️  Delivery state: {state} (waiting for 'sent')... ({wait_time}s/{max_wait}s)")
    else:
        pytest.fail(f"Delivery did not complete within {max_wait} seconds")

    assert summary_text, "No summary text generated"

    # 4. Validate target language
    target_lang_valid, target_indicators = validate_language(
        summary_text, target_lang, source_language=source_lang
    )
    assert target_lang_valid, f"Summary not in {target_lang}: {target_indicators}"
    print(f"✅ Target language validated: {target_lang} ({len(target_indicators)} indicators)")

    target_size_valid, target_size_msg = validate_size(
        summary_text, target_summary_size, tolerance=0.40, language=target_lang
    )
    assert target_size_valid, f"Summary size invalid: {target_size_msg}"
    print(f"✅ Target size validated: {target_size_msg}")

    no_artifacts, artifacts = validate_no_prompt_artifacts(summary_text)
    assert no_artifacts, f"Prompt artifacts found: {artifacts}"
    print(f"✅ No prompt artifacts found")

    output_file = test_output_dir / f"at1_4a_{source_lang}_{target_lang}_summary.txt"
    output_file.write_text(summary_text, encoding='utf-8')
    print(f"✅ Summary saved to: {output_file}")

    print(f"\n{'─'*80}")
    print(f"SUMMARY ({target_lang.upper()}):")
    print(f"{'─'*80}")
    print(summary_text[:500] + ("..." if len(summary_text) > 500 else ""))
    print(f"{'─'*80}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
