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
AT1.4b: Full Translation (Same Size)

Test: Source message (source language, source size) → Target full message (target language, same size)
- Validates source language and size
- Translates full message to target language (same size)
- Saves to file
- Validates: target language, target size matches source, no prompt artifacts
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
    validate_no_prompt_artifacts,
    get_test_matrix
)

from tests.utils.test_helpers import check_test_dependencies


FULL_CASES = [tc for tc in get_test_matrix() if tc["source"] != tc["target"]][:3]


@pytest.mark.parametrize(
    "test_case",
    FULL_CASES,
    ids=lambda tc: f"{tc['source']}_{tc['target']}_{tc['size']}_full",
)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")
def test_at1_4b_translation_full(api_client, loopback_channel, test_output_dir, test_config, test_case):
    """AT1.4b: Full translation with same size validation (one case per run)"""
    # RULES.md: validate dependencies/services before test logic
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="AT1.4b:test_at1_4b_translation_full",
    )

    if not test_config.get("at14b_env_loaded"):
        pytest.fail("❌ HARD FAIL: --env file not loaded. Run with: pytest --env private/env-test-at14b")

    channel_id, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")

    # RULES.md: no hardcoded defaults - env must provide test.email_domain
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ test.email_domain not configured in env file (set CLOUD_DOG__NOTIFY__TEST__EMAIL_DOMAIN)")

    max_wait = test_config.get("test.at14b.max_wait", 480)

    source_lang = test_case["source"]
    target_lang = test_case["target"]
    source_size = test_case["size"]

    print(f"\n{'='*80}")
    print(f"AT1.4b Test: {source_lang.upper()} → {target_lang.upper()} (Full translation, {source_size} chars)")
    print(f"{'='*80}")

    try:
        source_content = load_test_message(source_lang, source_size)
    except FileNotFoundError:
        pytest.fail(f"Test message file not found for {source_lang}")

    source_lang_valid, _ = validate_language(source_content, source_lang)
    assert source_lang_valid, f"Source not in {source_lang}"
    source_size_valid, _ = validate_size(source_content, source_size, tolerance=0.1)
    assert source_size_valid, "Source size invalid"

    message_payload = {
        "content": [{"type": "text", "body": source_content}],
        "destinations": [{
            "channel": channel_name,
            "address": f"test_{source_lang}_{target_lang}{email_domain}",
            "preferences": {"language": target_lang}
        }]
    }

    response = api_client.post("/messages", json=message_payload)
    assert response.status_code == 201, f"Failed to create message: {response.text}"
    response_data = response.json()
    message_id = response_data.get("message_id") or response_data.get("id")
    assert message_id, f"No message_id in response: {response_data}"
    print(f"✅ Message created: ID={message_id}")

    max_failures = 3
    wait_time = 0
    failed_count = 0
    delivery = None
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
            print(f"✅ Delivery complete ({wait_time}s)")
            break
        if state in ['hard_failed', 'soft_failed', 'failed']:
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

    assert delivery, "No delivery found"
    payload_str = delivery.get("personalised_payload", "{}")
    payload_list = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    translated_text = ""
    if isinstance(payload_list, list) and payload_list:
        for block in payload_list:
            if isinstance(block, dict) and block.get("type") == "text":
                translated_text += (block.get("body", "") or "") + "\n"
    else:
        translated_text = payload_list.get("body", "") if isinstance(payload_list, dict) else str(payload_list)

    translated_text = translated_text.strip()
    assert translated_text, "No translated text found in delivery"
    print(f"✅ Translation received: {len(translated_text)} chars")

    target_lang_valid, target_indicators = validate_language(translated_text, target_lang, source_lang)
    assert target_lang_valid, f"Translation not in {target_lang}: {target_indicators}"
    print(f"✅ Target language validated: {target_lang}")

    # Quality guardrail: do not accept "lenient pass" for substantial translations
    if isinstance(target_indicators, list) and any(str(x).startswith("No clear indicators found") for x in target_indicators):
        pytest.fail(f"❌ Language validation inconclusive for {target_lang}: {target_indicators}")

    # Extra depth: ensure obvious English section headings do not leak through when translating from English
    if source_lang == "en" and target_lang != "en":
        leaked = []
        for phrase in ("Applications of Summarization", "Personalization begins", "Channel-Specific Adaptations"):
            if phrase.lower() in translated_text.lower():
                leaked.append(phrase)
        assert not leaked, f"English leakage detected in {target_lang}: {leaked}"

    tolerance = 0.50
    target_size_valid, size_msg = validate_size(translated_text, source_size, tolerance=tolerance, language=target_lang)
    assert target_size_valid, f"Size mismatch: {size_msg}"
    print(f"✅ Target size validated: {size_msg}")

    no_artifacts, artifacts = validate_no_prompt_artifacts(translated_text)
    assert no_artifacts, f"Artifacts found: {artifacts}"
    print(f"✅ No prompt artifacts found")

    output_file = test_output_dir / f"at1_4b_{source_lang}_{target_lang}_full.txt"
    output_file.write_text(translated_text, encoding='utf-8')
    print(f"✅ Full translation saved to: {output_file}")

    print(f"\n{'='*80}")
    print(f"TRANSLATED TEXT ({target_lang}, first 500 chars):")
    print(f"{'='*80}")
    print(translated_text[:500] + ("..." if len(translated_text) > 500 else ""))
    print(f"{'='*80}\n")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

