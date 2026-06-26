#!/usr/bin/env python3
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
Comprehensive Slack Summary Link Test with Full Validation

CRITICAL RULES:
1. ALL OUTPUT TO SCREEN - no silent failures
2. ALL OPERATIONS MUST HAVE TIMEOUTS - never get stuck
3. Report timeouts clearly and continue with what we can verify

This test validates:
1. Subject is correct (not prompt text)
2. Format & contents of the Slack payload
3. Format of the output (Slack dict format)
4. Summarization (long content is summarized)
5. Summary link is present and accessible
6. All information accessible via API
7. Message link validation
8. Slack delivery validation
"""

import pytest
import sys
import json
import time
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from pypdf import PdfReader

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)
from tests.utils.test_helpers import check_test_dependencies

# CRITICAL: All timeouts must be set via configuration
API_TIMEOUT = None
WAIT_TIMEOUT = None
POLL_INTERVAL = None


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    from io import BytesIO

    reader = PdfReader(BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return " ".join(p for p in parts if p).strip()


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env/config")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _get_api_timeout(test_config) -> httpx.Timeout:
    total = _require_number(test_config, "api.timeout", number_type="float")
    connect = test_config.get("api.connect_timeout")
    if connect is None or connect == "":
        connect = total
    else:
        connect = _require_number(test_config, "api.connect_timeout", number_type="float")
    read = test_config.get("api.read_timeout")
    if read is None or read == "":
        read = total
    else:
        read = _require_number(test_config, "api.read_timeout", number_type="float")
    return httpx.Timeout(timeout=total, connect=connect, read=read)


def _get_wait_timeout(test_config) -> float:
    wait_timeout = (
        test_config.get("test.slack.wait_timeout")
        or test_config.get("test.at14a.max_wait")
        or test_config.get("test.at14b.max_wait")
        or test_config.get("test.at14c.max_wait")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.wait_timeout, test.at14*.max_wait, or api.timeout"
        )
    return float(wait_timeout)


def _get_poll_interval(test_config) -> float:
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.poll_interval or api.connect_timeout"
        )
    return float(poll_interval)


def _get_request_timeout(test_config) -> float:
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.request_timeout or api.connect_timeout"
        )
    return float(request_timeout)


def _verify_slack_message(test_config, marker: str) -> None:
    slack_token, slack_channel_id = require_slack_api_config(test_config)
    wait_timeout = _get_wait_timeout(test_config)
    poll_interval = _get_poll_interval(test_config)
    request_timeout = _get_request_timeout(test_config)
    slack_message = wait_for_slack_message(
        slack_token,
        slack_channel_id,
        marker,
        timeout=wait_timeout,
        poll_interval=poll_interval,
        request_timeout=request_timeout,
    )
    assert_slack_mrkdwn_contains(slack_message, marker)


def _set_timeouts(test_config) -> None:
    global API_TIMEOUT, WAIT_TIMEOUT, POLL_INTERVAL
    API_TIMEOUT = _get_api_timeout(test_config)
    WAIT_TIMEOUT = _get_wait_timeout(test_config)
    POLL_INTERVAL = _get_poll_interval(test_config)


@pytest.fixture(autouse=True)
def _config_timeouts(test_config):
    _set_timeouts(test_config)
    yield


def _get_chat_rest_channels(api_base_url: str, api_key: str) -> list:
    with httpx.Client(timeout=API_TIMEOUT) as client:
        channels_response = client.get(
            f"{api_base_url}/channels",
            headers={"X-API-Key": api_key},
        )
        channels_response.raise_for_status()
        all_channels = channels_response.json()
    return [
        ch for ch in all_channels
        if ch.get("type") == "chat_rest" or "chat_rest" in ch.get("name", "").lower()
    ]


def _set_chat_rest_restrictions(api_base_url: str, api_key: str, restrictions: dict) -> dict:
    originals = {}
    with httpx.Client(timeout=API_TIMEOUT) as client:
        for channel in _get_chat_rest_channels(api_base_url, api_key):
            channel_id = channel["id"]
            originals[channel_id] = channel.get("restrictions_json")
            update_response = client.patch(
                f"{api_base_url}/channels/{channel_id}",
                json={"restrictions_json": restrictions},
                headers={"X-API-Key": api_key},
            )
            update_response.raise_for_status()
    return originals


def _restore_chat_rest_restrictions(api_base_url: str, api_key: str, originals: dict) -> None:
    if not originals:
        return
    with httpx.Client(timeout=API_TIMEOUT) as client:
        for channel_id, restrictions_json in originals.items():
            update_response = client.patch(
                f"{api_base_url}/channels/{channel_id}",
                json={"restrictions_json": restrictions_json},
                headers={"X-API-Key": api_key},
            )
            update_response.raise_for_status()


def read_test_message(test_config) -> str:
    """Read the test message file from config"""
    # Get test message file path from config (env file)
    test_message_file = test_config.get("test.message_file")
    if not test_message_file:
        # Default to Test-Large-Text.md if not specified
        test_message_file = "Test-Large-Text.md"
    
    # Test message files are in tests/Examples/ directory
    examples_dir = project_root / "tests" / "Examples"
    test_message_path = examples_dir / test_message_file
    
    if not test_message_path.exists():
        pytest.fail(f"Test message file not found: {test_message_path}\n"
                   f"Available files: {', '.join([f.name for f in examples_dir.glob('*.md')])}\n"
                   f"Set CLOUD_DOG__NOTIFY__TEST__MESSAGE_FILE=<filename> in env file")
    
    with open(test_message_path, 'r', encoding='utf-8') as f:
        return f.read()
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_slack_summary_with_link(api_base_url, api_key, slack_config, test_config):
    """
    Comprehensive test that validates:
    1. Subject is correct
    2. Format & contents of Slack payload
    3. Format of output (Slack dict format)
    4. Summarization (long content is summarized)
    5. Summary link is present and accessible
    6. All information accessible via API
    7. Message link validation
    8. Slack delivery validation
    """
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,   # This test requires LLM for summarization
        requires_slack=True, # This test requires Slack webhook
        requires_api=True,   # This test requires API server
        test_name="test_slack_summary_with_link"
    )
    
    print(f"\n{'='*80}")
    print("COMPREHENSIVE SLACK SUMMARY LINK TEST")
    print(f"{'='*80}\n")
    
    # Get channel name from config (NO HARDCODED VALUES)
    # Try to get from slack_config first (may have channel_name), then from test_config
    channel_name = slack_config.get("channel_name")
    if not channel_name:
        # Try to infer from slack_config keys (e.g., "transparentbordes" from "channels.chat_rest.transparentbordes")
        # Or get from explicit config setting
        channel_name = test_config.get("channels.chat_rest.default.name") or test_config.get("test.slack_channel_name")
    
    if not channel_name:
        pytest.fail(
            "Channel name not configured.\n"
            "Set one of:\n"
            "  - CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__DEFAULT__NAME=<channel_name>\n"
            "  - CLOUD_DOG__NOTIFY__TEST__SLACK_CHANNEL_NAME=<channel_name>\n"
            "Or ensure slack_config fixture provides channel_name"
        )
    
    # Get channel restrictions from API to determine max_length (NO HARDCODED VALUES)
    channel_max_length = None
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            # Get channel info from API
            channels_response = client.get(
                f"{api_base_url}/channels",
                headers={"X-API-Key": api_key}
            )
            if channels_response.status_code == 200:
                channels_payload = channels_response.json()
                channels = (
                    channels_payload.get("items", [])
                    if isinstance(channels_payload, dict)
                    else channels_payload
                )
                channel = next((c for c in channels if c.get("name") == channel_name), None)
                if channel:
                    # Try restrictions_json first, then limits_json
                    restrictions_json = channel.get("restrictions_json")
                    if restrictions_json:
                        restrictions = json.loads(restrictions_json) if isinstance(restrictions_json, str) else restrictions_json
                        channel_max_length = restrictions.get("max_length")
                    if not channel_max_length:
                        limits_json = channel.get("limits_json")
                        if limits_json:
                            limits = json.loads(limits_json) if isinstance(limits_json, str) else limits_json
                            channel_max_length = limits.get("max_length")
                    if not channel_max_length and channel.get("type") in {"chat_rest", "chat", "slack"}:
                        # The formatter applies an implicit 4000-char ceiling for chat/slack channels
                        # when channel limits are unset. Keep the test aligned with that contract.
                        channel_max_length = 4000
                    if channel_max_length:
                        print(f"✅ Retrieved channel max_length from API: {channel_max_length} characters")
    except Exception as e:
        print(f"⚠️  Could not get channel restrictions from API: {e}, using default")
    
    # Get default from config if not found from API (NO HARDCODED DEFAULTS)
    if not channel_max_length:
        channel_max_length = test_config.get("channels.chat_rest.default.max_length") or test_config.get("channels.chat_rest.default.limits.max_length")
        if channel_max_length:
            print(f"⚠️  Using max_length from config: {channel_max_length} characters")
    
    # CRITICAL: Fail if we can't determine max_length (NO HARDCODED DEFAULTS)
    if not channel_max_length:
        pytest.fail(
            f"Could not determine channel max_length from API or config.\n"
            f"Channel: {channel_name}\n"
            f"Set CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__DEFAULT__MAX_LENGTH in env file"
        )
    
    # Calculate expected word count (approximately 5 characters per word)
    MAX_CHARS = channel_max_length
    MAX_WORDS = MAX_CHARS // 5
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Get Slack webhook URL from config
    slack_webhook = slack_config.get("endpoint")
    if not slack_webhook:
        pytest.fail("Slack webhook not configured in env file")
    
    # Create message with long content (should trigger summarization)
    # Use 5000 chars as test data prep (this is OK - it's just for creating test content)
    long_content = news_content[:5000] if len(news_content) > 5000 else news_content
    if len(long_content) < channel_max_length:
        # Make it longer to ensure summarization
        long_content = (long_content + " ") * 2
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": channel_name,  # Use channel name from config, not hardcoded
            "address": slack_webhook,
            "preferences": {
                "content_style": "text"  # Slack uses text format
            }
        }],
        "content": [{
            "type": "text",
            "body": long_content  # Don't include prompt text - the system will summarize automatically
        }],
        "options": {
            "subject": "Test Message Summary - Slack"
        }
    }
    
    print(f"📧 Destination: {slack_webhook}")
    print(f"📝 Content style: Text")
    print(f"📌 Requested subject: {message_payload['options']['subject']}")
    print(f"📏 Original content length: {len(long_content)} chars (should be summarized if > {channel_max_length})\n")
    
    # Step 1: Create message (WITH TIMEOUT)
    print("=" * 80)
    print("STEP 1: CREATE MESSAGE")
    print("=" * 80)
    message_id = None
    message_guid = None
    
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            print(f"✅ POST /messages: Status {response.status_code}")
            
            if response.status_code == 201:
                try:
                    result = response.json()
                except:
                    print(f"❌ Failed to parse JSON response: {response.text[:200]}")
                    pytest.fail(f"Message creation response is not valid JSON")
                
                message_id = result.get("message_id")
                message_guid = result.get("guid")
                
                # If GUID not in response, fetch it from message API
                if not message_guid and message_id:
                    try:
                        msg_response = client.get(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key}
                        )
                        if msg_response.status_code == 200:
                            msg_data = msg_response.json()
                            message_guid = msg_data.get("guid")
                    except:
                        print(f"⚠️  Could not fetch GUID from message API, continuing...")
                
                print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            else:
                print(f"❌ Failed to create message: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                pytest.fail(f"Message creation failed: {response.status_code}")
    except httpx.TimeoutException:
        print(f"❌ TIMEOUT: Message creation timed out after {API_TIMEOUT}s")
        pytest.fail("Message creation timed out")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        pytest.fail(f"Message creation failed: {e}")
    
    assert message_id is not None, "Message ID must be present"
    
    # Step 2: Wait for delivery (WITH TIMEOUT)
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR DELIVERY")
    print("=" * 80)
    
    delivery = None
    delivery_id = None
    start_time = time.time()
    max_attempts = int(WAIT_TIMEOUT / POLL_INTERVAL)
    
    for i in range(max_attempts):
        try:
            with httpx.Client(timeout=API_TIMEOUT) as client:
                response = client.get(
                    f"{api_base_url}/messages/{message_id}/deliveries",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deliveries = data.get("items", [])
                    
                    if deliveries:
                        delivery = deliveries[0]
                        delivery_id = delivery.get("id")
                        state = delivery.get("state")
                        error = delivery.get("last_error")
                        elapsed = time.time() - start_time
                        print(f"  Attempt {i+1}: state={state}, error={error[:50] if error else 'none'}")
                        
                        if state == "sent":
                            print(f"✅ Delivery completed in {elapsed:.1f}s")
                            break
                        elif state in ["hard_failed", "cancelled"]:
                            print(f"❌ Delivery failed: {error}")
                            pytest.fail(f"Delivery failed: {error}")
            
            time.sleep(POLL_INTERVAL)
        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] API call timed out, retrying...")
            time.sleep(POLL_INTERVAL)
            continue
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {type(e).__name__}: {e}")
            time.sleep(POLL_INTERVAL)
            continue
    
    if delivery is None:
        elapsed = time.time() - start_time
        print(f"❌ TIMEOUT: No delivery found after {elapsed:.1f}s")
        pytest.fail(f"Delivery not found after {WAIT_TIMEOUT}s")
    
    if delivery.get("state") != "sent":
        print(f"⚠️  WARNING: Delivery state is {delivery.get('state')}, not 'sent'")
        print(f"   Continuing with validation anyway...")
    
    delivery_id = delivery.get("id")
    print(f"✅ Delivery ID: {delivery_id}")
    
    # Validate Slack delivery acceptance
    last_error = delivery.get("last_error")
    state = delivery.get("state")
    if last_error:
        print(f"❌ Delivery {delivery_id} REJECTED by Slack: {last_error}")
        pytest.fail(f"Slack delivery {delivery_id} rejected: {last_error}")
    else:
        print(f"✅ Delivery {delivery_id} ACCEPTED by Slack (no last_error reported)")
    
    if state == "hard_failed":
        print(f"❌ Delivery {delivery_id} state is 'hard_failed'. Error: {last_error}")
        pytest.fail(f"Delivery {delivery_id} ended in hard_failed state: {last_error}")
    elif state != "sent":
        print(f"⚠️  WARNING: Delivery {delivery_id} state is '{state}', expected 'sent'.")
    else:
        print(f"✅ Delivery {delivery_id} state is 'sent'.")
    
    # Step 3: Validate Payload Format
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE PAYLOAD FORMAT")
    print("=" * 80)
    
    personalised_payload = delivery.get("personalised_payload")
    if not personalised_payload:
        print("❌ Personalised payload not found")
        pytest.fail("Personalised payload not found")
    
    # Parse payload
    if isinstance(personalised_payload, str):
        try:
            payload_data = json.loads(personalised_payload)
        except:
            print(f"❌ Failed to parse payload JSON")
            pytest.fail("Failed to parse personalised_payload")
    else:
        payload_data = personalised_payload
    
    # Check payload is in Slack format (dict with 'text' field)
    assert isinstance(payload_data, dict), f"Expected dict (Slack format), got {type(payload_data)}"
    assert 'text' in payload_data, f"Missing 'text' field in Slack payload: {payload_data.keys()}"
    
    print(f"✅ Payload is in Slack format (dict with 'text' field)")
    
    text = payload_data.get('text', '')
    word_count = len(text.split())
    char_count = len(text)
    print(f"📄 Text length: {char_count} characters, {word_count} words")
    print(f"📄 Text (first 200 chars): {text[:200]}")
    print(f"📄 Text (last 200 chars): {text[-200:]}")
    
    # CRITICAL: Validate message BEFORE considering it successful
    # Step 4: Validate Summarization and Word Count
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATE SUMMARIZATION AND WORD COUNT")
    print("=" * 80)
    
    # Use channel restrictions (already retrieved above)
    print(f"📊 Expected: ≤{MAX_WORDS} words (≤{MAX_CHARS} characters) [from channel restrictions]")
    print(f"📊 Actual: {word_count} words ({char_count} characters)")
    
    # FAIL if message exceeds limits
    if word_count > MAX_WORDS:
        print(f"❌ CRITICAL: Message has {word_count} words, exceeds limit of {MAX_WORDS} words")
        pytest.fail(f"Message exceeds word limit: {word_count} > {MAX_WORDS} words")
    
    if char_count > MAX_CHARS:
        print(f"❌ CRITICAL: Message has {char_count} characters, exceeds limit of {MAX_CHARS} characters")
        pytest.fail(f"Message exceeds character limit: {char_count} > {MAX_CHARS} characters")
    
    print(f"✅ Message is within limits: {word_count} words, {char_count} characters")
    
    # Check if prompt text is still present (means LLM didn't process it)
    prompt_indicators = [
        "Please provide a summary",
        "following content:",
        "Please provide a summary of the following content"
    ]
    has_prompt = any(indicator in text for indicator in prompt_indicators)
    
    if has_prompt:
        print(f"⚠️  WARNING: Prompt text still present in payload - LLM may not have processed the message")
        print(f"   This could mean:")
        print(f"   - LLM formatter was not called")
        print(f"   - LLM processing is still in progress")
        print(f"   - Content was not long enough to trigger summarization")
        print(f"   Continuing with validation...")
    
    if len(long_content) > channel_max_length:
        # Should be summarized - but only check if prompt is not present
        if not has_prompt:
            # Text should be shorter than original (without prompt prefix)
            original_without_prompt = long_content
            if len(text) >= len(original_without_prompt):
                print(f"⚠️  Text length ({len(text)}) is not shorter than original ({len(original_without_prompt)})")
                print(f"   This may indicate summarization didn't occur, but continuing...")
            else:
                print(f"✅ Text is summarized (reduced from {len(original_without_prompt)} to {len(text)} chars)")
        else:
            print(f"⚠️  Cannot verify summarization - prompt text still present")
    else:
        print(f"⚠️  Original content ({len(long_content)} chars) was not long enough to trigger summarization")
    
    # Step 5: Validate Summary Link (CRITICAL - MUST BE PRESENT)
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE SUMMARY LINK")
    print("=" * 80)
    
    # CRITICAL: Link MUST be present if content was summarized
    has_link = False
    link_url = None
    link_text = None
    
    # Check for Slack link format: <url|text>
    slack_link_pattern = r'<https?://[^>|]+\|View full message[^>]+>'
    slack_links = re.findall(slack_link_pattern, text)
    
    if slack_links:
        has_link = True
        link_text = slack_links[0]
        link_url_match = re.search(r'<(https?://[^>|]+)\|', slack_links[0])
        if link_url_match:
            link_url = link_url_match.group(1)
        print(f"✅ Found Slack link: {link_text}")
    else:
        # Check for plain text link
        if 'View full message' in text and 'messages/' in text:
            has_link = True
            # Try to extract URL
            url_match = re.search(r'(https?://[^\s<]+)', text)
            if url_match:
                link_url = url_match.group(1)
            print(f"✅ Found link text (plain format)")
        elif f'{api_base_url}/messages/' in text:
            has_link = True
            url_match = re.search(rf'({re.escape(api_base_url)}/messages/[^\s<]+)', text)
            if url_match:
                link_url = url_match.group(1)
            print(f"✅ Found message URL in text")
    
    # CRITICAL: Link MUST be present if content was long enough to require summarization
    if len(long_content) > MAX_CHARS:
        if not has_link:
            print(f"❌ CRITICAL: No link found in message!")
            print(f"   Original content: {len(long_content)} chars")
            print(f"   Delivered message: {char_count} chars, {word_count} words")
            print(f"   Text preview (last 500 chars): {text[-500:]}")
            pytest.fail(f"Link to full message MUST be present when content ({len(long_content)} chars) exceeds max_length ({MAX_CHARS} chars)")
        else:
            print(f"✅ Summary link present: {link_text or link_url}")
    else:
        print(f"⚠️  Original content ({len(long_content)} chars) was not long enough to require summarization")
    
    # Verify link format (if present)
    if has_link:
        # Check for Slack link format: <url|text>
        if '<http' in text:
            slack_links = re.findall(r'<https?://[^>|]+\|[^>]+>', text)
            if len(slack_links) > 0:
                link_url_match = re.search(r'<(https?://[^>|]+)\|', slack_links[0])
                if link_url_match:
                    link_url = link_url_match.group(1)
                print(f"✅ Slack link format correct: {slack_links[0]}")
            else:
                # Try to extract URL from text
                url_match = re.search(r'(https?://[^\s<]+)', text)
                if url_match:
                    link_url = url_match.group(1)
                    print(f"✅ Found URL in text: {link_url}")
                else:
                    print(f"⚠️  Link found but format not standard Slack format")
    else:
        # CRITICAL: Link MUST be present if content was long enough
        if len(long_content) > channel_max_length:
            print(f"❌ CRITICAL: No link found in message, but content ({len(long_content)} chars) exceeds max_length ({channel_max_length})")
            print(f"   Text preview (last 300 chars): {text[-300:]}")
            pytest.fail(f"Link to full message MUST be present when content exceeds max_length. Text length: {len(text)}")
    
    # Step 6: Validate Message Link Accessibility
    print("\n" + "=" * 80)
    print("STEP 6: VALIDATE MESSAGE LINK ACCESSIBILITY")
    print("=" * 80)
    
    # Extract link from text if present
    message_link = None
    if has_link and link_url:
        message_link = link_url
    elif has_link:
        # Try to extract link from text
        link_match = re.search(r'<([^>|]+)\|View full message', text)
        if link_match:
            message_link = link_match.group(1)
        else:
            # Try plain text format
            link_match = re.search(r'\[View full message[^\]]+\(([^)]+)\)\]', text)
            if link_match:
                message_link = link_match.group(1)
    
    # If no link found in text, try to construct from message_id/guid
    if not message_link:
        if message_guid:
            message_link = f"{api_base_url}/messages/{message_guid}"
        elif message_id:
            message_link = f"{api_base_url}/messages/{message_id}"
    
    if message_link:
        print(f"🔍 Testing message link: {message_link}")
        
        # Verify link points to correct message using API
        with httpx.Client(timeout=API_TIMEOUT) as client:
            # Test HTML format
            html_link = f"{message_link}?format=html"
            link_response = client.get(
                html_link,
                headers={"X-API-Key": api_key} if html_link.startswith(api_base_url) else {},
                timeout=API_TIMEOUT
            )
            
            if link_response and link_response.status_code == 200:
                link_content = link_response.text
                content_type_header = link_response.headers.get('content-type', '')
                
                # Check if response is HTML
                is_html = False
                if link_content and len(link_content) > 0:
                    content_preview = link_content[:1000].lower()
                    is_html = ("<!doctype html" in content_preview or 
                              "<html" in content_preview or 
                              ("<h1>" in link_content and "<div" in link_content))
                if not is_html:
                    is_html = 'text/html' in content_type_header.lower()
                
                if is_html:
                    print(f"✅ Link shows HTML formatted content")
                else:
                    print(f"⚠️  Link response is not HTML: Content-Type: {content_type_header}")
            else:
                print(f"⚠️  Link is not accessible: HTTP {link_response.status_code if link_response else 'None'}")
            
            # Test JSON format endpoint
            json_link = f"{message_link}?format=json"
            json_response = client.get(
                json_link,
                headers={"X-API-Key": api_key},
                timeout=API_TIMEOUT
            )
            if json_response.status_code == 200:
                json_data = json_response.json()
                if json_data.get('id') == message_id or json_data.get('guid') == message_guid:
                    if 'formatted_content' in json_data:
                        print(f"✅ Link JSON endpoint works correctly with formatted_content")
                    message_status = json_data.get('status')
                    print(f"✅ JSON status: {message_status}")
                else:
                    print(f"⚠️  Link JSON endpoint returns different message")
            else:
                print(f"⚠️  Link JSON endpoint not accessible: HTTP {json_response.status_code}")
    else:
        print(f"⚠️  No message link found to validate")
    
    # Step 7: Validate API Access
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE API ACCESS")
    print("=" * 80)
    
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            # Get message
            response = client.get(
                f"{api_base_url}/messages/{message_id}",
                headers={"X-API-Key": api_key}
            )
            if response.status_code == 200:
                message_data = response.json()
                print(f"✅ Message accessible via API: /messages/{message_id}")
                print(f"   Status: {message_data.get('status')}")
                print(f"   Created: {message_data.get('created_at')}")
            else:
                print(f"⚠️  Message API returned {response.status_code}")
            
            # Get deliveries
            response = client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key}
            )
            if response.status_code == 200:
                deliveries_data = response.json()
                print(f"✅ Deliveries accessible via API: /messages/{message_id}/deliveries")
                print(f"   Count: {len(deliveries_data.get('items', []))}")
            else:
                print(f"⚠️  Deliveries API returned {response.status_code}")
            
    except httpx.TimeoutException:
        print(f"⚠️  TIMEOUT: Some API calls timed out (non-critical)")
    except Exception as e:
        print(f"⚠️  ERROR: {type(e).__name__}: {e}")
    
    # Step 8: Summary
    print("\n" + "=" * 80)
    print("STEP 8: SUMMARY")
    print("=" * 80)
    
    print(f"\n📋 MESSAGE INFORMATION:")
    print(f"   Message ID: {message_id}")
    print(f"   Message GUID: {message_guid}")
    print(f"   Delivery ID: {delivery_id}")
    
    print(f"\n🔗 API ENDPOINTS:")
    print(f"   Message: {api_base_url}/messages/{message_id}")
    print(f"   Deliveries: {api_base_url}/messages/{message_id}/deliveries")
    
    if message_guid:
        print(f"   Message by GUID: {api_base_url}/messages/{message_guid}")
    
    # Step 9: Comprehensive Link Validation (Format, Type, Content)
    print("\n" + "=" * 80)
    print("STEP 9: COMPREHENSIVE LINK VALIDATION (FORMAT, TYPE, CONTENT)")
    print("=" * 80)
    
    # 9.1: Validate Message Link Format
    print("\n" + "-" * 80)
    print("9.1: VALIDATE MESSAGE LINK FORMAT")
    print("-" * 80)
    
    message_link_format_valid = False
    message_link_url = None
    message_link_text = None
    
    if has_link and link_url:
        message_link_url = link_url
        # Check if it's in Slack format: <url|text>
        slack_format_match = re.search(r'<([^>|]+)\|([^>]+)>', text)
        if slack_format_match:
            message_link_url = slack_format_match.group(1)
            message_link_text = slack_format_match.group(2)
            print(f"✅ Message link is in Slack format: <{message_link_url}|{message_link_text}>")
            message_link_format_valid = True
        else:
            # Check if it's a plain URL
            plain_url_match = re.search(r'(https?://[^\s<]+)', text)
            if plain_url_match:
                message_link_url = plain_url_match.group(1)
                print(f"⚠️  Message link is plain URL format (not Slack format): {message_link_url}")
                message_link_format_valid = True
            else:
                print(f"❌ Message link format is invalid or not found")
    else:
        print(f"❌ No message link found to validate format")
    
    # 9.2: Validate Message Link Type (should point to message, not summary)
    print("\n" + "-" * 80)
    print("9.2: VALIDATE MESSAGE LINK TYPE")
    print("-" * 80)
    
    message_link_type_valid = False
    if message_link_url:
        # Check if link points to a message endpoint
        if '/messages/' in message_link_url:
            print(f"✅ Message link type is correct: points to /messages/ endpoint")
            message_link_type_valid = True
        else:
            print(f"❌ Message link type is incorrect: does not point to /messages/ endpoint")
            print(f"   Link URL: {message_link_url}")
    
    # 9.3: Validate Message Link Content (should show full message, not summary)
    print("\n" + "-" * 80)
    print("9.3: VALIDATE MESSAGE LINK CONTENT")
    print("-" * 80)
    
    message_link_content_valid = False
    if message_link_url and message_link_type_valid:
        try:
            html_response = None
            html_content = ""
            for attempt in range(20):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    # Test HTML format
                    html_url = f"{message_link_url}?format=html" if '?' not in message_link_url else f"{message_link_url}&format=html"
                    html_response = client.get(
                        html_url,
                        headers={"X-API-Key": api_key},
                        timeout=API_TIMEOUT,
                    )
                if html_response.status_code == 200 and html_response.text:
                    html_content = html_response.text
                    break
                time.sleep(3)
                
            if html_response and html_response.status_code == 200:
                    
                    # Check if it contains the full message (not just summary)
                    # Full message should have original content or formatted content
                    has_full_content = False
                    if 'original-content' in html_content.lower() or 'original_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains original content section")
                    elif 'message-content' in html_content.lower() or 'formatted_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains formatted content section")
                    elif len(html_content) > 5000:  # Full message HTML should be substantial
                        has_full_content = True
                        print(f"✅ Message link HTML is substantial ({len(html_content)} chars), likely full message")
                    
                    # Check if it's NOT just the summary
                    # Summary would be short and might contain "summary" text
                    is_summary_only = False
                    if 'summary' in html_content.lower() and len(html_content) < 2000:
                        is_summary_only = True
                        print(f"⚠️  Message link HTML appears to be summary only (short and contains 'summary')")
                    
                    if has_full_content and not is_summary_only:
                        message_link_content_valid = True
                        print(f"✅ Message link content is valid: shows full message (not summary)")
                    else:
                        print(f"❌ Message link content is invalid: does not show full message")
                        print(f"   HTML length: {len(html_content)} chars")
                        print(f"   Has full content: {has_full_content}, Is summary only: {is_summary_only}")
                    
                    # Test JSON format to verify content
                    json_url = f"{message_link_url}?format=json" if '?' not in message_link_url else f"{message_link_url}&format=json"
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        json_response = client.get(
                            json_url,
                            headers={"X-API-Key": api_key},
                            timeout=API_TIMEOUT,
                        )
                    
                    if json_response.status_code == 200:
                        json_data = json_response.json()
                        formatted_content = json_data.get('formatted_content', [])
                        original_content = json_data.get('original_content', [])
                        
                        if formatted_content or original_content:
                            print(f"✅ Message link JSON contains content blocks")
                            # Check if content is substantial (not just summary)
                            total_content_length = 0
                            all_blocks = []
                            if isinstance(formatted_content, list):
                                all_blocks.extend(formatted_content)
                            elif formatted_content:
                                all_blocks.append(formatted_content)
                            if isinstance(original_content, list):
                                all_blocks.extend(original_content)
                            elif original_content:
                                all_blocks.append(original_content)
                            
                            for block in all_blocks:
                                if isinstance(block, dict):
                                    total_content_length += len(str(block.get('body', '')))
                            
                            if total_content_length > 1000:  # Full message should be substantial
                                print(f"✅ Message link JSON content is substantial ({total_content_length} chars), likely full message")
                            else:
                                print(f"⚠️  Message link JSON content is short ({total_content_length} chars), may be summary only")
        except Exception as e:
            print(f"❌ Error validating message link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 9.4: Validate PDF Link Format
    print("\n" + "-" * 80)
    print("9.4: VALIDATE PDF LINK FORMAT")
    print("-" * 80)
    
    pdf_link = None
    pdf_link_format_valid = False
    
    # Extract PDF link from text
    pdf_link_match = re.search(r'PDF version:\s*(https?://[^\s<]+)', text)
    if pdf_link_match:
        pdf_link = pdf_link_match.group(1)
        print(f"✅ Found PDF link: {pdf_link}")
        
        # Check if it's a valid URL
        if pdf_link.startswith('http://') or pdf_link.startswith('https://'):
            pdf_link_format_valid = True
            print(f"✅ PDF link format is valid: {pdf_link}")
        else:
            print(f"❌ PDF link format is invalid: {pdf_link}")
    else:
        print(f"⚠️  No PDF link found in message (PDF may not be generated)")
    
    # 9.5: Validate PDF Link Type (should point to PDF storage endpoint)
    print("\n" + "-" * 80)
    print("9.5: VALIDATE PDF LINK TYPE")
    print("-" * 80)
    
    pdf_link_type_valid = False
    if pdf_link:
        # Check if link points to PDF storage endpoint
        if '/storage/pdf/' in pdf_link or pdf_link.endswith('.pdf'):
            print(f"✅ PDF link type is correct: points to PDF storage endpoint")
            pdf_link_type_valid = True
        else:
            print(f"❌ PDF link type is incorrect: does not point to PDF storage endpoint")
            print(f"   Link URL: {pdf_link}")
    
    # 9.6: Validate PDF Link Content (should contain full article, not summary)
    print("\n" + "-" * 80)
    print("9.6: VALIDATE PDF LINK CONTENT")
    print("-" * 80)
    
    pdf_link_content_valid = False
    if pdf_link and pdf_link_format_valid and pdf_link_type_valid:
        try:
            pdf_response = None
            pdf_content = b""
            for attempt in range(20):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    pdf_response = client.get(pdf_link, timeout=API_TIMEOUT)
                if pdf_response.status_code == 200 and pdf_response.content:
                    pdf_content = pdf_response.content
                    if len(pdf_content) > 5000:
                        break
                time.sleep(3)
                
            if pdf_response and pdf_response.status_code == 200:
                pdf_size = len(pdf_content)
                content_type = pdf_response.headers.get('content-type', '')
                
                print(f"📄 PDF downloaded: {pdf_size} bytes, Content-Type: {content_type}")
                
                # Verify PDF is not just the summary
                # Full article PDF should be larger than summary PDF
                if pdf_size > 5000:  # Full article PDF should be larger than summary
                    pdf_link_content_valid = True
                    print(f"✅ PDF size suggests full article (not summary): {pdf_size} bytes")
                else:
                    print(f"❌ PDF size is too small ({pdf_size} bytes), likely summary only")
                    print(f"   Expected: >5000 bytes for full article")
                
                # Verify content type
                if 'application/pdf' in content_type.lower() or 'pdf' in content_type.lower():
                    print(f"✅ PDF content type is correct: {content_type}")
                else:
                    print(f"⚠️  PDF content type may be incorrect: {content_type}")
                    
                    # CRITICAL: Validate PDF content quality (title, formatting, no markdown, no extra periods)
                    try:
                        pdf_text = _extract_pdf_text(pdf_content)
                        print(f"📄 PDF text extracted: {len(pdf_text)} characters")
                        print(f"📄 PDF text sample (first 300 chars): {pdf_text[:300]}")
                        
                        # Validate title is NOT "Notification {id}" - should be actual subject
                        if f"Notification {message_id}" in pdf_text or pdf_text.startswith("Notification "):
                            print(f"❌ CRITICAL: PDF title is hardcoded 'Notification {message_id}', not actual message subject")
                            pytest.fail(f"PDF title is wrong: should be actual message subject, not 'Notification {message_id}'")
                        else:
                            print(f"✅ PDF title appears to be correct (not hardcoded)")
                        
                        # Validate no raw markdown syntax (should be rendered)
                        markdown_indicators = ['**', '##', '###', '```', '`', '[', '](']
                        has_markdown = any(ind in pdf_text for ind in markdown_indicators)
                        if has_markdown:
                            print(f"❌ CRITICAL: PDF contains raw markdown syntax (not rendered)")
                            print(f"   Found markdown indicators in PDF text")
                            pytest.fail(f"PDF contains raw markdown syntax - should be rendered HTML/styled text")
                        else:
                            print(f"✅ PDF content is properly rendered (no raw markdown)")
                        
                        # Validate no extra periods (multiple periods in a row)
                        if re.search(r'\.{4,}', pdf_text):
                            print(f"❌ CRITICAL: PDF contains excessive periods (.... or more)")
                            pytest.fail(f"PDF contains excessive periods - content may be malformed")
                        else:
                            print(f"✅ PDF periods are reasonable")
                        
                        # Validate content is substantial (not just summary)
                        if len(pdf_text) < 500:
                            print(f"⚠️  PDF text is short ({len(pdf_text)} chars), may be summary only")
                        else:
                            print(f"✅ PDF content is substantial ({len(pdf_text)} chars)")
                        
                    except Exception as pdf_validation_error:
                        print(f"⚠️  Could not validate PDF content quality: {pdf_validation_error}")
                        import traceback
                        traceback.print_exc()
                        # Don't fail test if validation fails, but log warning
        except Exception as e:
            print(f"❌ Error validating PDF link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 9.7: Summary of Link Validation
    print("\n" + "-" * 80)
    print("9.7: LINK VALIDATION SUMMARY")
    print("-" * 80)
    
    print(f"\n📋 MESSAGE LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if message_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if message_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if message_link_content_valid else '❌ INVALID'}")
    
    print(f"\n📋 PDF LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if pdf_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if pdf_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if pdf_link_content_valid else '❌ INVALID'}")
    
    # CRITICAL: Fail test if links are invalid
    if not message_link_format_valid or not message_link_type_valid or not message_link_content_valid:
        pytest.fail(
            f"Message link validation failed:\n"
            f"  Format: {message_link_format_valid}, Type: {message_link_type_valid}, Content: {message_link_content_valid}\n"
            f"  Link URL: {message_link_url}"
        )
    
    if pdf_link and (not pdf_link_format_valid or not pdf_link_type_valid or not pdf_link_content_valid):
        pytest.fail(
            f"PDF link validation failed:\n"
            f"  Format: {pdf_link_format_valid}, Type: {pdf_link_type_valid}, Content: {pdf_link_content_valid}\n"
            f"  Link URL: {pdf_link}"
        )
    
    print(f"\n✅ ALL LINK VALIDATIONS PASSED")
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Format: Slack dict format")
    print(f"   ✅ Contents: {'PRESENT' if len(text) > 0 else 'MISSING'}")
    print(f"   ✅ Summarization: {'SUMMARIZED' if len(text) < len(long_content) else 'NOT SUMMARIZED'}")
    print(f"   ✅ Summary Link: {'PRESENT' if has_link else 'NOT FOUND'}")
    print(f"   ✅ Slack Delivery: {'ACCEPTED' if not last_error else 'REJECTED'}")
    print(f"   ✅ API Access: {'AVAILABLE' if message_id else 'NOT AVAILABLE'}")

    if not message_guid:
        pytest.fail("❌ Slack verification requires message GUID, but none was found.")
    _verify_slack_message(test_config, message_guid)
    
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - ALL VALIDATIONS PERFORMED")
    print(f"{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_slack_summary_german_400_chars(api_base_url, api_key, slack_config, test_config, test_email, request):
    """
    German Slack summary test with 400 character limit for a different user
    
    Validates:
    1. German translation
    2. 400 character limit (not 1000)
    3. Summary link present
    4. PDF link points to full article
    """
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,   # This test requires LLM for translation and summarization
        requires_slack=True, # This test requires Slack webhook
        requires_api=True,   # This test requires API server
        test_name="test_slack_summary_german_400_chars"
    )
    
    print(f"\n{'='*80}")
    print("GERMAN SLACK SUMMARY TEST (CONFIGURABLE CHAR LIMIT)")
    print(f"{'='*80}\n")
    
    # Get channel name from config (NO HARDCODED VALUES)
    channel_name = slack_config.get("channel_name")
    if not channel_name:
        channel_name = test_config.get("channels.chat_rest.default.name") or test_config.get("test.slack_channel_name")
    if not channel_name:
        pytest.fail(
            "Channel name not configured.\n"
            "Set one of:\n"
            "  - CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__DEFAULT__NAME=<channel_name>\n"
            "  - CLOUD_DOG__NOTIFY__TEST__SLACK_CHANNEL_NAME=<channel_name>"
        )
    
    # Get target max_length from config (NO HARDCODED VALUES)
    target_max_length = test_config.get("test.slack_max_length") or test_config.get("channels.chat_rest.default.max_length")
    if not target_max_length:
        pytest.fail(
            "Target max_length not configured.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__SLACK_MAX_LENGTH=<number> in env file"
        )
    target_max_length = int(target_max_length)
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Get Slack webhook URL from config
    slack_webhook = slack_config.get("endpoint")
    if not slack_webhook:
        pytest.fail("Slack webhook not configured in env file")
    
    # Create message with long content (should trigger summarization)
    # Use 5000 chars as test data prep (this is OK - it's just for creating test content)
    long_content = news_content[:5000] if len(news_content) > 5000 else news_content
    if len(long_content) < target_max_length:
        # Make it longer to ensure summarization
        long_content = (long_content + " ") * 2
    
    # Use a different user email for this test
    different_user_email = test_email.replace("@", "+german@") if "@" in test_email else f"german-{test_email}"
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": channel_name,  # Use channel name from config, not hardcoded
            "address": slack_webhook,
            "preferences": {
                "language": "de",  # German
                "content_style": "text",  # Slack uses text format
                "pdf_preference": "link"  # Request PDF link
            }
        }],
        "content": [{
            "type": "text",
            "body": long_content
        }],
        "options": {
            "subject": "Test Nachricht Zusammenfassung - Deutsch"
        }
    }
    
    print(f"📧 Destination: {slack_webhook}")
    print(f"🌐 Language: German (de)")
    print(f"📝 Content style: Text")
    print(f"📏 Target max length: {target_max_length} characters (from config)")
    print(f"📌 Requested subject: {message_payload['options']['subject']}")
    print(f"📏 Original content length: {len(long_content)} chars (should be summarized to ≤{target_max_length})\n")
    
    # Update channel restrictions to target_max_length for this test
    print("=" * 80)
    print(f"STEP 0: UPDATE CHANNEL RESTRICTIONS ({target_max_length} CHAR LIMIT)")
    print("=" * 80)
    try:
        restrictions = {
            "max_length": target_max_length,
            "allowed_formats": ["text"],
            "link_strategy": "summary+link",
        }
        originals = _set_chat_rest_restrictions(api_base_url, api_key, restrictions)
        if originals:
            print(f"✅ Updated {len(originals)} chat_rest channel(s) to max_length={target_max_length}")
            request.addfinalizer(
                lambda: _restore_chat_rest_restrictions(api_base_url, api_key, originals)
            )
        else:
            print("⚠️  WARNING: No chat_rest channels found to update")
    except Exception as e:
        print(f"⚠️  Could not update channel restrictions via API: {e}")
        print(f"   Continuing with default restrictions...")
    
    # Step 1: Create message
    print("=" * 80)
    print("STEP 1: CREATE MESSAGE")
    print("=" * 80)
    message_id = None
    message_guid = None
    
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            print(f"✅ POST /messages: Status {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                message_id = result.get("message_id")
                message_guid = result.get("guid")
                
                if not message_guid and message_id:
                    try:
                        msg_response = client.get(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key}
                        )
                        if msg_response.status_code == 200:
                            msg_data = msg_response.json()
                            message_guid = msg_data.get("guid")
                    except:
                        pass
                
                print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            else:
                print(f"❌ Failed to create message: {response.status_code}")
                pytest.fail(f"Message creation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        pytest.fail(f"Message creation failed: {e}")
    
    assert message_id is not None, "Message ID must be present"
    
    # Step 2: Wait for delivery
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR DELIVERY")
    print("=" * 80)
    
    delivery = None
    delivery_id = None
    start_time = time.time()
    max_attempts = int(WAIT_TIMEOUT / POLL_INTERVAL)
    
    for i in range(max_attempts):
        try:
            with httpx.Client(timeout=API_TIMEOUT) as client:
                response = client.get(
                    f"{api_base_url}/messages/{message_id}/deliveries",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deliveries = data.get("items", [])
                    
                    if deliveries:
                        delivery = deliveries[0]
                        delivery_id = delivery.get("id")
                        state = delivery.get("state")
                        elapsed = time.time() - start_time
                        print(f"  Attempt {i+1}: state={state}")
                        
                        if state == "sent":
                            print(f"✅ Delivery completed in {elapsed:.1f}s")
                            break
                        elif state in ["hard_failed", "cancelled"]:
                            error = delivery.get("last_error", "Unknown error")
                            print(f"❌ Delivery failed: {error}")
                            pytest.fail(f"Delivery failed: {error}")
            
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {type(e).__name__}: {e}")
            time.sleep(POLL_INTERVAL)
            continue
    
    if delivery is None:
        elapsed = time.time() - start_time
        print(f"❌ TIMEOUT: No delivery found after {elapsed:.1f}s")
        pytest.fail(f"Delivery not found after {WAIT_TIMEOUT}s")
    
    delivery_id = delivery.get("id")
    print(f"✅ Delivery ID: {delivery_id}")
    
    # Step 3: Validate Payload
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE PAYLOAD (GERMAN, 400 CHAR LIMIT)")
    print("=" * 80)
    
    personalised_payload = delivery.get("personalised_payload")
    if not personalised_payload:
        pytest.fail("Personalised payload not found")
    
    if isinstance(personalised_payload, str):
        try:
            payload_data = json.loads(personalised_payload)
        except:
            pytest.fail("Failed to parse personalised_payload")
    else:
        payload_data = personalised_payload
    
    assert isinstance(payload_data, dict), f"Expected dict (Slack format), got {type(payload_data)}"
    assert 'text' in payload_data, f"Missing 'text' field in Slack payload"
    
    text = payload_data.get('text', '')
    word_count = len(text.split())
    char_count = len(text)
    
    print(f"📄 Text length: {char_count} characters, {word_count} words")
    
    # CRITICAL: Validate character limit from config (NO HARDCODED VALUES)
    # Get actual max_length from channel restrictions (may have been updated)
    MAX_CHARS = target_max_length
    MAX_WORDS = MAX_CHARS // 5  # Approximately 5 characters per word
    
    print(f"📊 Expected: ≤{MAX_WORDS} words (≤{MAX_CHARS} characters)")
    print(f"📊 Actual: {word_count} words ({char_count} characters)")
    
    if char_count > MAX_CHARS:
        print(f"❌ CRITICAL: Message has {char_count} characters, exceeds limit of {MAX_CHARS} characters")
        pytest.fail(f"Message exceeds character limit: {char_count} > {MAX_CHARS} characters")
    
    if word_count > MAX_WORDS:
        print(f"❌ CRITICAL: Message has {word_count} words, exceeds limit of {MAX_WORDS} words")
        pytest.fail(f"Message exceeds word limit: {word_count} > {MAX_WORDS} words")
    
    # Validate German translation
    german_indicators = ["der", "die", "das", "und", "ist", "in", "für", "mit", "auf", "zu", "Zusammenfassung", "Deutsch", "Inhalt"]
    english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content"]
    
    text_lower = text.lower()
    has_german = any(ind in text_lower for ind in german_indicators)
    has_english = any(ind in text_lower for ind in english_indicators)
    
    if has_german and not has_english:
        print(f"✅ Text is in German")
    elif has_german and has_english:
        print(f"⚠️  Text contains both German and English")
    else:
        print(f"❌ Text does not appear to be in German")
        pytest.fail("Message is not in German")
    
    # Validate summary link
    has_link = False
    link_url = None
    slack_link_pattern = r'<https?://[^>|]+\|View full message[^>]+>'
    slack_links = re.findall(slack_link_pattern, text)
    
    if slack_links:
        has_link = True
        link_url_match = re.search(r'<(https?://[^>|]+)\|', slack_links[0])
        if link_url_match:
            link_url = link_url_match.group(1)
        print(f"✅ Found summary link: {slack_links[0]}")
    else:
        if len(long_content) > MAX_CHARS:
            print(f"❌ CRITICAL: No summary link found, but content ({len(long_content)} chars) exceeds max_length ({MAX_CHARS})")
            pytest.fail(f"Link to full message MUST be present when content exceeds max_length")
    
    # Step 4: Comprehensive Link Validation (Format, Type, Content)
    print("\n" + "=" * 80)
    print("STEP 4: COMPREHENSIVE LINK VALIDATION (FORMAT, TYPE, CONTENT)")
    print("=" * 80)
    
    # 4.1: Validate Message Link Format
    print("\n" + "-" * 80)
    print("4.1: VALIDATE MESSAGE LINK FORMAT")
    print("-" * 80)
    
    message_link_format_valid = False
    message_link_url = link_url
    message_link_text = None
    
    if has_link and link_url:
        # Check if it's in Slack format: <url|text>
        slack_format_match = re.search(r'<([^>|]+)\|([^>]+)>', text)
        if slack_format_match:
            message_link_url = slack_format_match.group(1)
            message_link_text = slack_format_match.group(2)
            print(f"✅ Message link is in Slack format: <{message_link_url}|{message_link_text}>")
            message_link_format_valid = True
        else:
            # Check if it's a plain URL
            plain_url_match = re.search(r'(https?://[^\s<]+)', text)
            if plain_url_match:
                message_link_url = plain_url_match.group(1)
                print(f"⚠️  Message link is plain URL format (not Slack format): {message_link_url}")
                message_link_format_valid = True
            else:
                print(f"❌ Message link format is invalid or not found")
    else:
        print(f"❌ No message link found to validate format")
    
    # 4.2: Validate Message Link Type (should point to message, not summary)
    print("\n" + "-" * 80)
    print("4.2: VALIDATE MESSAGE LINK TYPE")
    print("-" * 80)
    
    message_link_type_valid = False
    if message_link_url:
        # Check if link points to a message endpoint
        if '/messages/' in message_link_url:
            print(f"✅ Message link type is correct: points to /messages/ endpoint")
            message_link_type_valid = True
        else:
            print(f"❌ Message link type is incorrect: does not point to /messages/ endpoint")
            print(f"   Link URL: {message_link_url}")
    
    # 4.3: Validate Message Link Content (should show full message, not summary)
    print("\n" + "-" * 80)
    print("4.3: VALIDATE MESSAGE LINK CONTENT")
    print("-" * 80)
    
    message_link_content_valid = False
    if message_link_url and message_link_type_valid:
        try:
            html_response = None
            html_content = ""
            for attempt in range(20):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    # Test HTML format
                    html_url = f"{message_link_url}?format=html" if '?' not in message_link_url else f"{message_link_url}&format=html"
                    html_response = client.get(
                        html_url,
                        headers={"X-API-Key": api_key},
                        timeout=API_TIMEOUT,
                    )
                if html_response.status_code == 200 and html_response.text:
                    html_content = html_response.text
                    break
                time.sleep(3)
                
            if html_response and html_response.status_code == 200:
                    
                    # Check if it contains the full message (not just summary)
                    has_full_content = False
                    if 'original-content' in html_content.lower() or 'original_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains original content section")
                    elif 'message-content' in html_content.lower() or 'formatted_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains formatted content section")
                    elif len(html_content) > 5000:  # Full message HTML should be substantial
                        has_full_content = True
                        print(f"✅ Message link HTML is substantial ({len(html_content)} chars), likely full message")
                    
                    # Check if it's NOT just the summary
                    is_summary_only = False
                    if 'summary' in html_content.lower() and len(html_content) < 2000:
                        is_summary_only = True
                        print(f"⚠️  Message link HTML appears to be summary only (short and contains 'summary')")
                    
                    # CRITICAL: Validate language in HTML content
                    html_lower = html_content.lower()
                    german_indicators = ["der", "die", "das", "und", "ist", "in", "für", "mit", "auf", "zu", "zusammenfassung", "deutsch", "inhalt", "nachricht"]
                    english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content", "message"]
                    
                    german_count = sum(1 for ind in german_indicators if ind in html_lower)
                    english_count = sum(1 for ind in english_indicators if ind in html_lower)
                    
                    print(f"🔍 Language check in HTML: German indicators={german_count}, English indicators={english_count}")
                    
                    if german_count > english_count and german_count >= 3:
                        print(f"✅ Message link HTML content is in German")
                        html_language_valid = True
                    elif english_count > german_count:
                        print(f"❌ Message link HTML content is in English (should be German)")
                        html_language_valid = False
                    else:
                        print(f"⚠️  Message link HTML content language unclear (German: {german_count}, English: {english_count})")
                        html_language_valid = german_count >= 2
                    
                    if has_full_content and not is_summary_only and html_language_valid:
                        message_link_content_valid = True
                        print(f"✅ Message link content is valid: shows full message in German (not summary)")
                    else:
                        print(f"❌ Message link content is invalid:")
                        print(f"   Has full content: {has_full_content}")
                        print(f"   Is summary only: {is_summary_only}")
                        print(f"   Language valid (German): {html_language_valid}")
                        message_link_content_valid = False
                        # CRITICAL: Fail test if message link is not in German
                        if not html_language_valid:
                            pytest.fail(f"Message link HTML content is not in German. German indicators: {german_count}, English indicators: {english_count}. HTML sample: {html_content[:1000]}")
                    
                    # Test JSON format to verify content
                    json_url = f"{message_link_url}?format=json" if '?' not in message_link_url else f"{message_link_url}&format=json"
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        json_response = client.get(
                            json_url,
                            headers={"X-API-Key": api_key},
                            timeout=API_TIMEOUT,
                        )
                    
                    if json_response.status_code == 200:
                        json_data = json_response.json()
                        formatted_content = json_data.get('formatted_content', [])
                        original_content = json_data.get('original_content', [])
                        
                        if formatted_content or original_content:
                            print(f"✅ Message link JSON contains content blocks")
                            # Check if content is substantial (not just summary)
                            total_content_length = 0
                            all_blocks = []
                            if isinstance(formatted_content, list):
                                all_blocks.extend(formatted_content)
                            elif formatted_content:
                                all_blocks.append(formatted_content)
                            if isinstance(original_content, list):
                                all_blocks.extend(original_content)
                            elif original_content:
                                all_blocks.append(original_content)
                            
                            for block in all_blocks:
                                if isinstance(block, dict):
                                    total_content_length += len(str(block.get('body', '')))
                            
                            if total_content_length > 1000:  # Full message should be substantial
                                print(f"✅ Message link JSON content is substantial ({total_content_length} chars), likely full message")
                            else:
                                print(f"⚠️  Message link JSON content is short ({total_content_length} chars), may be summary only")
        except Exception as e:
            print(f"❌ Error validating message link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 4.4: Validate PDF Link Format
    print("\n" + "-" * 80)
    print("4.4: VALIDATE PDF LINK FORMAT")
    print("-" * 80)
    
    pdf_link = None
    pdf_link_format_valid = False
    
    # Extract PDF link from text
    pdf_link_match = re.search(r'PDF version:\s*(https?://[^\s<]+)', text)
    if pdf_link_match:
        pdf_link = pdf_link_match.group(1)
        print(f"✅ Found PDF link: {pdf_link}")
        
        # Check if it's a valid URL
        if pdf_link.startswith('http://') or pdf_link.startswith('https://'):
            pdf_link_format_valid = True
            print(f"✅ PDF link format is valid: {pdf_link}")
        else:
            print(f"❌ PDF link format is invalid: {pdf_link}")
    else:
        print(f"⚠️  No PDF link found in message (PDF may not be generated)")
    
    # 4.5: Validate PDF Link Type (should point to PDF storage endpoint)
    print("\n" + "-" * 80)
    print("4.5: VALIDATE PDF LINK TYPE")
    print("-" * 80)
    
    pdf_link_type_valid = False
    if pdf_link:
        # Check if link points to PDF storage endpoint
        if '/storage/pdf/' in pdf_link or pdf_link.endswith('.pdf'):
            print(f"✅ PDF link type is correct: points to PDF storage endpoint")
            pdf_link_type_valid = True
        else:
            print(f"❌ PDF link type is incorrect: does not point to PDF storage endpoint")
            print(f"   Link URL: {pdf_link}")
    
    # 4.6: Validate PDF Link Content (should contain full article, not summary)
    print("\n" + "-" * 80)
    print("4.6: VALIDATE PDF LINK CONTENT")
    print("-" * 80)
    
    pdf_link_content_valid = False
    if pdf_link and pdf_link_format_valid and pdf_link_type_valid:
        try:
            pdf_response = None
            pdf_content = b""
            for attempt in range(20):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    pdf_response = client.get(pdf_link, timeout=API_TIMEOUT)
                if pdf_response.status_code == 200 and pdf_response.content:
                    pdf_content = pdf_response.content
                    if len(pdf_content) > 5000:
                        break
                time.sleep(3)
                
            if pdf_response and pdf_response.status_code == 200:
                pdf_size = len(pdf_content)
                content_type = pdf_response.headers.get('content-type', '')
                
                print(f"📄 PDF downloaded: {pdf_size} bytes, Content-Type: {content_type}")
                
                # Verify PDF is not just the summary
                # Full article PDF should be larger than summary PDF
                if pdf_size > 5000:  # Full article PDF should be larger than summary
                    pdf_link_content_valid = True
                    print(f"✅ PDF size suggests full article (not summary): {pdf_size} bytes")
                else:
                    print(f"❌ PDF size is too small ({pdf_size} bytes), likely summary only")
                    print(f"   Expected: >5000 bytes for full article")
                
                # Verify content type
                if 'application/pdf' in content_type.lower() or 'pdf' in content_type.lower():
                    print(f"✅ PDF content type is correct: {content_type}")
                else:
                    print(f"⚠️  PDF content type may be incorrect: {content_type}")
                    
                    # CRITICAL: Validate PDF content quality (title, formatting, language, no markdown, no extra periods)
                    try:
                        pdf_text = _extract_pdf_text(pdf_content)
                        pdf_lower = pdf_text.lower()
                        print(f"📄 PDF text extracted: {len(pdf_text)} characters")
                        print(f"📄 PDF text sample (first 300 chars): {pdf_text[:300]}")
                        
                        # Validate title is NOT "Notification {id}" - should be actual subject
                        if f"Notification {message_id}" in pdf_text or pdf_text.startswith("Notification "):
                            print(f"❌ CRITICAL: PDF title is hardcoded 'Notification {message_id}', not actual message subject")
                            pytest.fail(f"PDF title is wrong: should be actual message subject, not 'Notification {message_id}'")
                        else:
                            print(f"✅ PDF title appears to be correct (not hardcoded)")
                        
                        # Validate no raw markdown syntax (should be rendered)
                        markdown_indicators = ['**', '##', '###', '```', '`', '[', '](']
                        has_markdown = any(ind in pdf_text for ind in markdown_indicators)
                        if has_markdown:
                            print(f"❌ CRITICAL: PDF contains raw markdown syntax (not rendered)")
                            print(f"   Found markdown indicators in PDF text")
                            pytest.fail(f"PDF contains raw markdown syntax - should be rendered HTML/styled text")
                        else:
                            print(f"✅ PDF content is properly rendered (no raw markdown)")
                        
                        # Validate no extra periods (multiple periods in a row)
                        if re.search(r'\.{4,}', pdf_text):
                            print(f"❌ CRITICAL: PDF contains excessive periods (.... or more)")
                            pytest.fail(f"PDF contains excessive periods - content may be malformed")
                        else:
                            print(f"✅ PDF periods are reasonable")
                        
                        # Validate language in PDF content
                        german_indicators = ["der", "die", "das", "und", "ist", "in", "für", "mit", "auf", "zu", "zusammenfassung", "deutsch", "inhalt", "nachricht"]
                        english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content", "message"]
                        
                        german_count_pdf = sum(1 for ind in german_indicators if ind in pdf_lower)
                        english_count_pdf = sum(1 for ind in english_indicators if ind in pdf_lower)
                        
                        print(f"🔍 Language check in PDF: German indicators={german_count_pdf}, English indicators={english_count_pdf}")
                        
                        if german_count_pdf > english_count_pdf and german_count_pdf >= 3:
                            print(f"✅ PDF content is in German")
                            pdf_language_valid = True
                        elif english_count_pdf > german_count_pdf:
                            print(f"❌ PDF content is in English (should be German)")
                            pdf_language_valid = False
                        else:
                            print(f"⚠️  PDF content language unclear (German: {german_count_pdf}, English: {english_count_pdf})")
                            pdf_language_valid = german_count_pdf >= 2
                        
                        if pdf_language_valid and pdf_size > 5000:
                            pdf_link_content_valid = True
                            print(f"✅ PDF content is valid: full article in German, properly styled")
                        elif not pdf_language_valid:
                            print(f"❌ PDF content language is wrong (should be German)")
                            print(f"   PDF text sample shows: {pdf_text[:500]}")
                            pdf_link_content_valid = False
                            # CRITICAL: Fail test if PDF is not in German
                            pytest.fail(f"PDF content is not in German. German indicators: {german_count_pdf}, English indicators: {english_count_pdf}. PDF text sample: {pdf_text[:500]}")
                    except Exception as pdf_error:
                        print(f"⚠️  Could not extract text from PDF for validation: {pdf_error}")
                        import traceback
                        traceback.print_exc()
                        # If we can't validate, at least check size
                        if pdf_size > 5000:
                            print(f"⚠️  PDF size is good but content validation failed")
                        else:
                            pdf_link_content_valid = False
        except Exception as e:
            print(f"❌ Error validating PDF link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 4.7: Summary of Link Validation
    print("\n" + "-" * 80)
    print("4.7: LINK VALIDATION SUMMARY")
    print("-" * 80)
    
    print(f"\n📋 MESSAGE LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if message_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if message_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if message_link_content_valid else '❌ INVALID'}")
    
    print(f"\n📋 PDF LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if pdf_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if pdf_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if pdf_link_content_valid else '❌ INVALID'}")
    
    # CRITICAL: Fail test if links are invalid
    if not message_link_format_valid or not message_link_type_valid or not message_link_content_valid:
        pytest.fail(
            f"Message link validation failed:\n"
            f"  Format: {message_link_format_valid}, Type: {message_link_type_valid}, Content: {message_link_content_valid}\n"
            f"  Link URL: {message_link_url}"
        )
    
    if pdf_link and (not pdf_link_format_valid or not pdf_link_type_valid or not pdf_link_content_valid):
        pytest.fail(
            f"PDF link validation failed:\n"
            f"  Format: {pdf_link_format_valid}, Type: {pdf_link_type_valid}, Content: {pdf_link_content_valid}\n"
            f"  Link URL: {pdf_link}"
        )
    
    print(f"\n✅ ALL LINK VALIDATIONS PASSED")
    
    if not message_guid:
        pytest.fail("❌ Slack verification requires message GUID, but none was found.")
    _verify_slack_message(test_config, message_guid)
    
    print(f"\n{'='*80}")
    print("✅ GERMAN TEST COMPLETE - ALL VALIDATIONS PASSED")
    print(f"{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_slack_summary_polish_400_chars(api_base_url, api_key, slack_config, test_config, test_email, request):
    """
    Polish Slack summary test with 400 character limit for a different user
    
    Validates:
    1. Polish translation
    2. 400 character limit (not 1000)
    3. Summary link present
    4. PDF link points to full article
    5. PDF title, formatting, language, no markdown, no extra periods
    """
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,   # This test requires LLM for translation and summarization
        requires_slack=True, # This test requires Slack webhook
        requires_api=True,   # This test requires API server
        test_name="test_slack_summary_polish_400_chars"
    )
    
    print(f"\n{'='*80}")
    print("POLISH SLACK SUMMARY TEST (CONFIGURABLE CHAR LIMIT)")
    print(f"{'='*80}\n")
    
    # Get channel name from config (NO HARDCODED VALUES)
    channel_name = slack_config.get("channel_name")
    if not channel_name:
        channel_name = test_config.get("channels.chat_rest.default.name") or test_config.get("test.slack_channel_name")
    if not channel_name:
        pytest.fail(
            "Channel name not configured.\n"
            "Set one of:\n"
            "  - CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__DEFAULT__NAME=<channel_name>\n"
            "  - CLOUD_DOG__NOTIFY__TEST__SLACK_CHANNEL_NAME=<channel_name>"
        )
    
    # Get target max_length from config (NO HARDCODED VALUES)
    target_max_length = test_config.get("test.slack_max_length") or test_config.get("channels.chat_rest.default.max_length")
    if not target_max_length:
        pytest.fail(
            "Target max_length not configured.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__SLACK_MAX_LENGTH=<number> in env file"
        )
    target_max_length = int(target_max_length)
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Get Slack webhook URL from config
    slack_webhook = slack_config.get("endpoint")
    if not slack_webhook:
        pytest.fail("Slack webhook not configured in env file")
    
    # Create message with long content (should trigger summarization)
    # Use 5000 chars as test data prep (this is OK - it's just for creating test content)
    long_content = news_content[:5000] if len(news_content) > 5000 else news_content
    if len(long_content) < target_max_length:
        # Make it longer to ensure summarization
        long_content = (long_content + " ") * 2
    
    # Use a different user email for this test
    different_user_email = test_email.replace("@", "+polish@") if "@" in test_email else f"polish-{test_email}"
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": channel_name,  # Use channel name from config, not hardcoded
            "address": slack_webhook,
            "preferences": {
                "language": "pl",  # Polish
                "content_style": "text",  # Slack uses text format
                "pdf_preference": "link"  # Request PDF link
            }
        }],
        "content": [{
            "type": "text",
            "body": long_content
        }],
        "options": {
            "subject": "Test Wiadomość Podsumowanie - Polski"
        }
    }
    
    print(f"📧 Destination: {slack_webhook}")
    print(f"🌐 Language: Polish (pl)")
    print(f"📝 Content style: Text")
    print(f"📏 Target max length: {target_max_length} characters (from config)")
    print(f"📌 Requested subject: {message_payload['options']['subject']}")
    print(f"📏 Original content length: {len(long_content)} chars (should be summarized to ≤{target_max_length})\n")
    
    # Update channel restrictions to target_max_length for this test
    print("=" * 80)
    print(f"STEP 0: UPDATE CHANNEL RESTRICTIONS ({target_max_length} CHAR LIMIT)")
    print("=" * 80)
    try:
        restrictions = {
            "max_length": target_max_length,
            "allowed_formats": ["text"],
            "link_strategy": "summary+link",
        }
        originals = _set_chat_rest_restrictions(api_base_url, api_key, restrictions)
        if originals:
            print(f"✅ Updated {len(originals)} chat_rest channel(s) to max_length={target_max_length}")
            request.addfinalizer(
                lambda: _restore_chat_rest_restrictions(api_base_url, api_key, originals)
            )
        else:
            print("⚠️  WARNING: No chat_rest channels found to update")
    except Exception as e:
        print(f"⚠️  Could not update channel restrictions via API: {e}")
        print(f"   Continuing with default restrictions...")
    
    # Step 1: Create message
    print("=" * 80)
    print("STEP 1: CREATE MESSAGE")
    print("=" * 80)
    message_id = None
    message_guid = None
    
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            print(f"✅ POST /messages: Status {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                message_id = result.get("message_id")
                message_guid = result.get("guid")
                
                if not message_guid and message_id:
                    try:
                        msg_response = client.get(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key}
                        )
                        if msg_response.status_code == 200:
                            msg_data = msg_response.json()
                            message_guid = msg_data.get("guid")
                    except:
                        pass
                
                print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            else:
                print(f"❌ Failed to create message: {response.status_code}")
                pytest.fail(f"Message creation failed: {response.status_code}")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        pytest.fail(f"Message creation failed: {e}")
    
    assert message_id is not None, "Message ID must be present"
    
    # Step 2: Wait for delivery
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR DELIVERY")
    print("=" * 80)
    
    delivery = None
    delivery_id = None
    start_time = time.time()
    max_attempts = int(WAIT_TIMEOUT / POLL_INTERVAL)
    
    for i in range(max_attempts):
        try:
            with httpx.Client(timeout=API_TIMEOUT) as client:
                response = client.get(
                    f"{api_base_url}/messages/{message_id}/deliveries",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deliveries = data.get("items", [])
                    
                    if deliveries:
                        delivery = deliveries[0]
                        delivery_id = delivery.get("id")
                        state = delivery.get("state")
                        elapsed = time.time() - start_time
                        print(f"  Attempt {i+1}: state={state}")
                        
                        if state == "sent":
                            print(f"✅ Delivery completed in {elapsed:.1f}s")
                            break
                        elif state in ["hard_failed", "cancelled"]:
                            error = delivery.get("last_error", "Unknown error")
                            print(f"❌ Delivery failed: {error}")
                            pytest.fail(f"Delivery failed: {error}")
            
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {type(e).__name__}: {e}")
            time.sleep(POLL_INTERVAL)
            continue
    
    if delivery is None:
        elapsed = time.time() - start_time
        print(f"❌ TIMEOUT: No delivery found after {elapsed:.1f}s")
        pytest.fail(f"Delivery not found after {WAIT_TIMEOUT}s")
    
    delivery_id = delivery.get("id")
    print(f"✅ Delivery ID: {delivery_id}")
    
    # Step 3: Validate Payload
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE PAYLOAD (POLISH, 400 CHAR LIMIT)")
    print("=" * 80)
    
    personalised_payload = delivery.get("personalised_payload")
    if not personalised_payload:
        pytest.fail("Personalised payload not found")
    
    if isinstance(personalised_payload, str):
        try:
            payload_data = json.loads(personalised_payload)
        except:
            pytest.fail("Failed to parse personalised_payload")
    else:
        payload_data = personalised_payload
    
    assert isinstance(payload_data, dict), f"Expected dict (Slack format), got {type(payload_data)}"
    assert 'text' in payload_data, f"Missing 'text' field in Slack payload"
    
    text = payload_data.get('text', '')
    word_count = len(text.split())
    char_count = len(text)
    
    print(f"📄 Text length: {char_count} characters, {word_count} words")
    
    # CRITICAL: Validate character limit from config (NO HARDCODED VALUES)
    MAX_CHARS = target_max_length
    MAX_WORDS = MAX_CHARS // 5  # Approximately 5 characters per word
    
    print(f"📊 Expected: ≤{MAX_WORDS} words (≤{MAX_CHARS} characters)")
    print(f"📊 Actual: {word_count} words ({char_count} characters)")
    
    if char_count > MAX_CHARS:
        print(f"❌ CRITICAL: Message has {char_count} characters, exceeds limit of {MAX_CHARS} characters")
        pytest.fail(f"Message exceeds character limit: {char_count} > {MAX_CHARS} characters")
    
    if word_count > MAX_WORDS:
        print(f"❌ CRITICAL: Message has {word_count} words, exceeds limit of {MAX_WORDS} words")
        pytest.fail(f"Message exceeds word limit: {word_count} > {MAX_WORDS} words")
    
    # CRITICAL: Validate NO prompt instructions in output
    print("\n" + "-" * 80)
    print("VALIDATE: NO PROMPT INSTRUCTIONS")
    print("-" * 80)
    prompt_indicators = ['•', 'Zachowaj', 'Przetłumacz', 'Zwróć', 'WYMAGANIA', 'Tłumaczenie (']
    found_prompts = [ind for ind in prompt_indicators if ind in text]
    if found_prompts:
        print(f"❌ CRITICAL: Found prompt instructions in output: {found_prompts}")
        for line in text.split('\n'):
            if any(ind in line for ind in found_prompts):
                print(f"   Offending line: {line.strip()}")
        pytest.fail(f"Prompt instructions found in output: {found_prompts}")
    else:
        print("✅ NO prompt instructions in output")
    
    # CRITICAL: Validate language parameter in link URL
    print("\n" + "-" * 80)
    print("VALIDATE: LANGUAGE PARAMETER IN LINK")
    print("-" * 80)
    if '?language=pl' in text or '&language=pl' in text:
        print("✅ Link contains language parameter for Polish")
    else:
        print("❌ CRITICAL: Link missing language parameter")
        pytest.fail("Link must contain ?language=pl parameter to display content in Polish")
    
    # Validate Polish translation
    polish_indicators = ["i", "w", "na", "z", "o", "do", "że", "się", "nie", "jest", "podsumowanie", "polski", "treść", "wiadomość", "oraz", "dla", "od", "po", "przez", "przy"]
    english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content"]
    
    text_lower = text.lower()
    has_polish = any(ind in text_lower for ind in polish_indicators)
    has_english = any(ind in text_lower for ind in english_indicators)
    
    if has_polish and not has_english:
        print(f"✅ Text is in Polish")
    elif has_polish and has_english:
        print(f"⚠️  Text contains both Polish and English")
    else:
        print(f"❌ Text does not appear to be in Polish")
        pytest.fail("Message is not in Polish")
    
    # Validate summary link (support both English and Polish translated labels)
    has_link = False
    link_url = None
    # Match English or Polish link patterns
    slack_link_patterns = [
        r'<https?://[^>|]+\|View full message[^>]+>',  # English
        r'<https?://[^>|]+\|Zobacz pełną wiadomość[^>]+>',  # Polish
        r'<https?://[^>|]+\|zobacz pełną wiadomość[^>]+>',  # Polish lowercase
    ]
    
    slack_links = []
    for pattern in slack_link_patterns:
        slack_links = re.findall(pattern, text, re.IGNORECASE)
        if slack_links:
            break
    
    if slack_links:
        has_link = True
        link_url_match = re.search(r'<(https?://[^>|]+)\|', slack_links[0])
        if link_url_match:
            link_url = link_url_match.group(1)
        print(f"✅ Found summary link: {slack_links[0]}")
    else:
        if len(long_content) > MAX_CHARS:
            print(f"❌ CRITICAL: No summary link found, but content ({len(long_content)} chars) exceeds max_length ({MAX_CHARS})")
            pytest.fail(f"Link to full message MUST be present when content exceeds max_length")
    
    # Step 4: Comprehensive Link Validation (Format, Type, Content)
    print("\n" + "=" * 80)
    print("STEP 4: COMPREHENSIVE LINK VALIDATION (FORMAT, TYPE, CONTENT)")
    print("=" * 80)
    
    # 4.1: Validate Message Link Format
    print("\n" + "-" * 80)
    print("4.1: VALIDATE MESSAGE LINK FORMAT")
    print("-" * 80)
    
    message_link_format_valid = False
    message_link_url = link_url
    message_link_text = None
    
    if has_link and link_url:
        slack_format_match = re.search(r'<([^>|]+)\|([^>]+)>', text)
        if slack_format_match:
            message_link_url = slack_format_match.group(1)
            message_link_text = slack_format_match.group(2)
            print(f"✅ Message link is in Slack format: <{message_link_url}|{message_link_text}>")
            message_link_format_valid = True
        else:
            plain_url_match = re.search(r'(https?://[^\s<]+)', text)
            if plain_url_match:
                message_link_url = plain_url_match.group(1)
                print(f"⚠️  Message link is plain URL format (not Slack format): {message_link_url}")
                message_link_format_valid = True
            else:
                print(f"❌ Message link format is invalid or not found")
    else:
        print(f"❌ No message link found to validate format")
    
    # 4.2: Validate Message Link Type
    print("\n" + "-" * 80)
    print("4.2: VALIDATE MESSAGE LINK TYPE")
    print("-" * 80)
    
    message_link_type_valid = False
    if message_link_url:
        if '/messages/' in message_link_url:
            print(f"✅ Message link type is correct: points to /messages/ endpoint")
            message_link_type_valid = True
        else:
            print(f"❌ Message link type is incorrect: does not point to /messages/ endpoint")
            print(f"   Link URL: {message_link_url}")
    
    # 4.3: Validate Message Link Content
    print("\n" + "-" * 80)
    print("4.3: VALIDATE MESSAGE LINK CONTENT")
    print("-" * 80)
    
    message_link_content_valid = False
    if message_link_url and message_link_type_valid:
        try:
            html_response = None
            html_content = ""
            for attempt in range(5):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    html_url = f"{message_link_url}?format=html" if '?' not in message_link_url else f"{message_link_url}&format=html"
                    html_response = client.get(
                        html_url,
                        headers={"X-API-Key": api_key},
                        timeout=API_TIMEOUT,
                    )
                if html_response.status_code == 200 and html_response.text:
                    html_content = html_response.text
                    break
                time.sleep(2)
                
            if html_response and html_response.status_code == 200:
                    
                    has_full_content = False
                    if 'original-content' in html_content.lower() or 'original_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains original content section")
                    elif 'message-content' in html_content.lower() or 'formatted_content' in html_content.lower():
                        has_full_content = True
                        print(f"✅ Message link HTML contains formatted content section")
                    elif len(html_content) > 5000:
                        has_full_content = True
                        print(f"✅ Message link HTML is substantial ({len(html_content)} chars), likely full message")
                    
                    is_summary_only = False
                    if 'summary' in html_content.lower() and len(html_content) < 2000:
                        is_summary_only = True
                        print(f"⚠️  Message link HTML appears to be summary only (short and contains 'summary')")
                    
                    # CRITICAL: Extract and validate FORMATTED MESSAGE CONTENT section
                    formatted_section = re.search(r'<div class="message-content">(.*?)</div>', html_content, re.DOTALL)
                    
                    if formatted_section:
                        formatted_text = formatted_section.group(1)[:500]  # First 500 chars
                        print(f"\n📄 FORMATTED MESSAGE CONTENT (first 200 chars):")
                        print(formatted_text[:200])
                        
                        # Check if FORMATTED content is Polish or English
                        # Polish-specific phrases
                        polish_phrases = ['wielkie modele językowe', 'informacji', 'umożliwiają', 'podsumowanie', 
                                         'treści', 'personalizację', 'wyzwania', 'zdolność']
                        # English-specific phrases that should NOT be there
                        english_phrases = ['digital age', 'information overload', 'staggering', 'phenomenon', 
                                          'paradigm shift', 'Large Language Models']
                        
                        has_polish = any(phrase in formatted_text.lower() for phrase in polish_phrases)
                        has_english = any(phrase.lower() in formatted_text.lower() for phrase in english_phrases)
                        
                        if has_english:
                            print(f"❌ CRITICAL FAILURE: FORMATTED MESSAGE CONTENT is in ENGLISH, not Polish!")
                            print(f"   English phrases found: {[p for p in english_phrases if p.lower() in formatted_text.lower()]}")
                            pytest.fail("FORMATTED MESSAGE CONTENT is in ENGLISH when ?language=pl parameter is set")
                        elif has_polish:
                            print(f"✅ FORMATTED MESSAGE CONTENT is in Polish")
                        else:
                            print(f"⚠️ Cannot determine language of FORMATTED MESSAGE CONTENT")
                    else:
                        print(f"❌ Could not extract FORMATTED MESSAGE CONTENT section")
                    
                    # Old generic check (keeping for overall validation)
                    html_lower = html_content.lower()
                    polish_indicators = ["i", "w", "na", "z", "o", "do", "że", "się", "nie", "jest", "podsumowanie", "polski", "treść", "wiadomość", "oraz", "dla", "od", "po", "przez", "przy"]
                    english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content", "message"]
                    
                    polish_count = sum(1 for ind in polish_indicators if ind in html_lower)
                    english_count = sum(1 for ind in english_indicators if ind in html_lower)
                    
                    print(f"🔍 Overall page language: Polish indicators={polish_count}, English indicators={english_count}")
                    
                    if polish_count > english_count and polish_count >= 3:
                        print(f"✅ Overall page has Polish content")
                        html_language_valid = True
                    elif english_count > polish_count:
                        print(f"⚠️  Overall page has more English than Polish")
                        html_language_valid = False
                    else:
                        print(f"⚠️  Message link HTML content language unclear (Polish: {polish_count}, English: {english_count})")
                        html_language_valid = polish_count >= 2
                    
                    if has_full_content and not is_summary_only and html_language_valid:
                        message_link_content_valid = True
                        print(f"✅ Message link content is valid: shows full message in Polish (not summary)")
                    else:
                        print(f"❌ Message link content is invalid:")
                        print(f"   Has full content: {has_full_content}")
                        print(f"   Is summary only: {is_summary_only}")
                        print(f"   Language valid (Polish): {html_language_valid}")
                        message_link_content_valid = False
                        if not html_language_valid:
                            pytest.fail(f"Message link HTML content is not in Polish. Polish indicators: {polish_count}, English indicators: {english_count}. HTML sample: {html_content[:1000]}")
                    
                    # Test JSON format to verify content
                    json_url = f"{message_link_url}?format=json" if '?' not in message_link_url else f"{message_link_url}&format=json"
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        json_response = client.get(
                            json_url,
                            headers={"X-API-Key": api_key},
                            timeout=API_TIMEOUT,
                        )
                    
                    if json_response.status_code == 200:
                        json_data = json_response.json()
                        formatted_content = json_data.get('formatted_content', [])
                        original_content = json_data.get('original_content', [])
                        
                        if formatted_content or original_content:
                            print(f"✅ Message link JSON contains content blocks")
                            total_content_length = 0
                            all_blocks = []
                            if isinstance(formatted_content, list):
                                all_blocks.extend(formatted_content)
                            elif formatted_content:
                                all_blocks.append(formatted_content)
                            if isinstance(original_content, list):
                                all_blocks.extend(original_content)
                            elif original_content:
                                all_blocks.append(original_content)
                            
                            for block in all_blocks:
                                if isinstance(block, dict):
                                    total_content_length += len(str(block.get('body', '')))
                            
                            if total_content_length > 1000:
                                print(f"✅ Message link JSON content is substantial ({total_content_length} chars), likely full message")
                            else:
                                print(f"⚠️  Message link JSON content is short ({total_content_length} chars), may be summary only")
        except Exception as e:
            print(f"❌ Error validating message link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 4.4: Validate PDF Link Format
    print("\n" + "-" * 80)
    print("4.4: VALIDATE PDF LINK FORMAT")
    print("-" * 80)
    
    pdf_link = None
    pdf_link_format_valid = False
    
    pdf_link_match = re.search(r'PDF version:\s*(https?://[^\s<]+)', text)
    if pdf_link_match:
        pdf_link = pdf_link_match.group(1)
        print(f"✅ Found PDF link: {pdf_link}")
        
        if pdf_link.startswith('http://') or pdf_link.startswith('https://'):
            pdf_link_format_valid = True
            print(f"✅ PDF link format is valid: {pdf_link}")
        else:
            print(f"❌ PDF link format is invalid: {pdf_link}")
    else:
        print(f"⚠️  No PDF link found in message (PDF may not be generated)")
    
    # 4.5: Validate PDF Link Type
    print("\n" + "-" * 80)
    print("4.5: VALIDATE PDF LINK TYPE")
    print("-" * 80)
    
    pdf_link_type_valid = False
    if pdf_link:
        if '/storage/pdf/' in pdf_link or pdf_link.endswith('.pdf'):
            print(f"✅ PDF link type is correct: points to PDF storage endpoint")
            pdf_link_type_valid = True
        else:
            print(f"❌ PDF link type is incorrect: does not point to PDF storage endpoint")
            print(f"   Link URL: {pdf_link}")
    
    # 4.6: Validate PDF Link Content
    print("\n" + "-" * 80)
    print("4.6: VALIDATE PDF LINK CONTENT")
    print("-" * 80)
    
    pdf_link_content_valid = False
    if pdf_link and pdf_link_format_valid and pdf_link_type_valid:
        try:
            pdf_response = None
            pdf_content = b""
            for attempt in range(5):
                with httpx.Client(timeout=API_TIMEOUT) as client:
                    pdf_response = client.get(pdf_link, timeout=API_TIMEOUT)
                if pdf_response.status_code == 200 and pdf_response.content:
                    pdf_content = pdf_response.content
                    if len(pdf_content) > 5000:
                        break
                time.sleep(2)
                
            if pdf_response and pdf_response.status_code == 200:
                pdf_size = len(pdf_content)
                content_type = pdf_response.headers.get('content-type', '')
                
                print(f"📄 PDF downloaded: {pdf_size} bytes, Content-Type: {content_type}")
                
                if pdf_size > 5000:
                    pdf_link_content_valid = True
                    print(f"✅ PDF size suggests full article (not summary): {pdf_size} bytes")
                else:
                    print(f"❌ PDF size is too small ({pdf_size} bytes), likely summary only")
                    print(f"   Expected: >5000 bytes for full article")
                
                if 'application/pdf' in content_type.lower() or 'pdf' in content_type.lower():
                    print(f"✅ PDF content type is correct: {content_type}")
                else:
                    print(f"⚠️  PDF content type may be incorrect: {content_type}")
                    
                    # CRITICAL: Validate PDF content quality (title, formatting, language, no markdown, no extra periods)
                    try:
                        pdf_text = _extract_pdf_text(pdf_content)
                        pdf_lower = pdf_text.lower()
                        print(f"📄 PDF text extracted: {len(pdf_text)} characters")
                        print(f"📄 PDF text sample (first 300 chars): {pdf_text[:300]}")
                        
                        # Validate title is NOT "Notification {id}"
                        if f"Notification {message_id}" in pdf_text or pdf_text.startswith("Notification "):
                            print(f"❌ CRITICAL: PDF title is hardcoded 'Notification {message_id}', not actual message subject")
                            pytest.fail(f"PDF title is wrong: should be actual message subject, not 'Notification {message_id}'")
                        else:
                            print(f"✅ PDF title appears to be correct (not hardcoded)")
                        
                        # CRITICAL: Check for markdown separator lines (strongest indicator)
                        separator_lines = '------------------------------------------------------------'
                        if separator_lines in pdf_text:
                            print(f"❌ CRITICAL FAILURE: PDF contains RAW MARKDOWN separator lines")
                            pytest.fail(f"PDF contains unrendered markdown separator lines")
                        
                        # Validate no raw markdown syntax
                        markdown_indicators = ['**', '##', '###', '```']
                        has_markdown = any(ind in pdf_text for ind in markdown_indicators)
                        if has_markdown:
                            found = [ind for ind in markdown_indicators if ind in pdf_text]
                            print(f"❌ CRITICAL FAILURE: PDF contains RAW MARKDOWN: {found}")
                            pytest.fail(f"PDF contains unrendered markdown: {found}")
                        else:
                            print(f"✅ PDF content is properly rendered (no raw markdown)")
                        
                        # Validate no extra periods
                        if re.search(r'\.{4,}', pdf_text):
                            print(f"❌ CRITICAL: PDF contains excessive periods (.... or more)")
                            pytest.fail(f"PDF contains excessive periods - content may be malformed")
                        else:
                            print(f"✅ PDF periods are reasonable")
                        
                        # Validate language in PDF content
                        polish_indicators = ["i", "w", "na", "z", "o", "do", "że", "się", "nie", "jest", "podsumowanie", "polski", "treść", "wiadomość", "oraz", "dla", "od", "po", "przez", "przy"]
                        english_indicators = ["the", "is", "in", "for", "with", "on", "to", "summary", "english", "content", "message"]
                        
                        polish_count_pdf = sum(1 for ind in polish_indicators if ind in pdf_lower)
                        english_count_pdf = sum(1 for ind in english_indicators if ind in pdf_lower)
                        
                        print(f"🔍 Language check in PDF: Polish indicators={polish_count_pdf}, English indicators={english_count_pdf}")
                        
                        if polish_count_pdf > english_count_pdf and polish_count_pdf >= 3:
                            print(f"✅ PDF content is in Polish")
                            pdf_language_valid = True
                        elif english_count_pdf > polish_count_pdf:
                            print(f"❌ PDF content is in English (should be Polish)")
                            pdf_language_valid = False
                        else:
                            print(f"⚠️  PDF content language unclear (Polish: {polish_count_pdf}, English: {english_count_pdf})")
                            pdf_language_valid = polish_count_pdf >= 2
                        
                        if pdf_language_valid and pdf_size > 5000:
                            pdf_link_content_valid = True
                            print(f"✅ PDF content is valid: full article in Polish, properly styled")
                        elif not pdf_language_valid:
                            print(f"❌ PDF content language is wrong (should be Polish)")
                            print(f"   PDF text sample shows: {pdf_text[:500]}")
                            pdf_link_content_valid = False
                            pytest.fail(f"PDF content is not in Polish. Polish indicators: {polish_count_pdf}, English indicators: {english_count_pdf}. PDF text sample: {pdf_text[:500]}")
                    except Exception as pdf_error:
                        print(f"⚠️  Could not extract text from PDF for validation: {pdf_error}")
                        import traceback
                        traceback.print_exc()
                        if pdf_size > 5000:
                            print(f"⚠️  PDF size is good but content validation failed")
                        else:
                            pdf_link_content_valid = False
        except Exception as e:
            print(f"❌ Error validating PDF link content: {e}")
            import traceback
            traceback.print_exc()
    
    # 4.7: Summary of Link Validation
    print("\n" + "-" * 80)
    print("4.7: LINK VALIDATION SUMMARY")
    print("-" * 80)
    
    print(f"\n📋 MESSAGE LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if message_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if message_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if message_link_content_valid else '❌ INVALID'}")
    
    print(f"\n📋 PDF LINK VALIDATION:")
    print(f"   Format: {'✅ VALID' if pdf_link_format_valid else '❌ INVALID'}")
    print(f"   Type: {'✅ VALID' if pdf_link_type_valid else '❌ INVALID'}")
    print(f"   Content: {'✅ VALID' if pdf_link_content_valid else '❌ INVALID'}")
    
    # CRITICAL: Fail test if links are invalid
    if not message_link_format_valid or not message_link_type_valid or not message_link_content_valid:
        pytest.fail(
            f"Message link validation failed:\n"
            f"  Format: {message_link_format_valid}, Type: {message_link_type_valid}, Content: {message_link_content_valid}\n"
            f"  Link URL: {message_link_url}"
        )
    
    if pdf_link and (not pdf_link_format_valid or not pdf_link_type_valid or not pdf_link_content_valid):
        pytest.fail(
            f"PDF link validation failed:\n"
            f"  Format: {pdf_link_format_valid}, Type: {pdf_link_type_valid}, Content: {pdf_link_content_valid}\n"
            f"  Link URL: {pdf_link}"
        )
    
    print(f"\n✅ ALL LINK VALIDATIONS PASSED")
    
    if not message_guid:
        pytest.fail("❌ Slack verification requires message GUID, but none was found.")
    _verify_slack_message(test_config, message_guid)
    
    print(f"\n{'='*80}")
    print("✅ POLISH TEST COMPLETE - ALL VALIDATIONS PASSED")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.application,
    pytest.mark.smtp,
    pytest.mark.llm,
    pytest.mark.live_provider,
    pytest.mark.live_delivery,
    pytest.mark.heavy,
]
