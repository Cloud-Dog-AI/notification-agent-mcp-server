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
Test: Send message to Slack webhook (transparentbordes channel)

This test:
1. Verifies the transparentbordes Slack channel is configured
2. Sends a test message via API
3. Verifies the message is delivered
4. Creates a summary document with link to the message
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)
from tests.utils.test_helpers import check_test_dependencies


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"Missing required configuration: {key}")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"{key} must be a {number_type}: {e}")


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


def _get_slack_timeouts(test_config):
    wait_timeout = test_config.get("test.slack.wait_timeout") or test_config.get("api.timeout")
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "Missing Slack wait timeout. Configure test.slack.wait_timeout or api.timeout in env file."
        )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "Missing Slack poll interval. Configure test.slack.poll_interval, api.connect_timeout, or api.timeout in env file."
        )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "Missing Slack request timeout. Configure test.slack.request_timeout, api.connect_timeout, or api.timeout in env file."
        )
    return float(wait_timeout), float(poll_interval), float(request_timeout)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.fixture(scope="session")
def test_message_path(test_config):
    filename = _require_value(test_config.get("test.message_file"), "test.message_file")
    candidate = Path(filename)
    project_root = Path(__file__).resolve().parents[3]
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] in {"test", "tests"}:
        return project_root / candidate
    return project_root / "tests" / "Examples" / candidate


@pytest.fixture
def api_client(api_base_url, api_key, test_config):
    """Create API client with config-driven timeouts."""
    api_timeout = _get_api_timeout(test_config)
    return httpx.Client(
        base_url=api_base_url,
        headers={"X-API-Key": api_key},
        timeout=api_timeout,
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_slack_webhook_transparentbordes(
    api_client,
    slack_config,
    test_message_path,
    api_base_url,
    web_base_url,
    test_config,
    request,
):
    """
    Test: Send message to transparentbordes Slack webhook
    
    This test verifies:
    - Channel is configured correctly
    - Message can be sent via API
    - Message is delivered to Slack
    - Summary document is created
    """

    slack_token, slack_channel_id = require_slack_api_config(test_config)
    marker = f"AT1.14 Slack {int(time.time())}"

    print("\n" + "="*70)
    print("TEST: Slack Webhook - Transparentbordes Channel")
    print("="*70)
    
    # Step 1: Verify channel is configured
    print(f"\n📋 Step 1: Verifying channel configuration...")
    try:
        channels_response = api_client.get("/channels")
        assert channels_response.status_code == 200, f"Failed to get channels: {channels_response.status_code}"
    except httpx.TimeoutException:
        pytest.fail("API server not responding - check if server is running")
    except Exception as e:
        pytest.fail(f"Failed to connect to API: {e}")
    
    channels = channels_response.json()
    channel_name = slack_config.get("channel_name")
    if not channel_name:
        pytest.fail("test.slack_channel_name not configured. Check your env file.")
    webhook_url = _require_value(slack_config.get("endpoint"), "channels.chat_rest.transparentbordes.endpoint")
    channel_found = None
    for channel in channels:
        if channel.get("name") == channel_name:
            channel_found = channel
            break
    
    assert channel_found is not None, f"Channel {channel_name} not found in channels list"
    assert channel_found.get("enabled") == 1, f"Channel {channel_name} is not enabled"
    print(f"✅ Channel found: {channel_name} (enabled: {channel_found.get('enabled')})")
    
    # Step 2: Create test message (using test message file)
    print(f"\n📨 Step 2: Creating test message...")
    test_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Read test message from file (no fallback)
    if not test_message_path.exists():
        pytest.fail(f"Test message file not found: {test_message_path}")
    with open(test_message_path, 'r', encoding='utf-8') as f:
        test_message_content = f.read()
    print(f"📄 Using test message from: {test_message_path.name} ({len(test_message_content)} chars)")
    
    message_payload = {
        "audience_type": "broadcast",
        "destinations": [
            {
                "channel": channel_name,
                "address": webhook_url
            }
        ],
        "content": [
            {
                "type": "markdown",
                "body": f"**{marker}**\n\n{test_message_content}"
            }
        ],
        "options": {
            "subject": f"Integration Test - {marker} - {test_timestamp}"
        }
    }
    
    print(f"📧 Sending to: {channel_name} channel")
    print(f"📄 Message length: {len(message_payload['content'][0]['body'])} characters")
    print(f"📝 Message preview: {test_message_content[:100]}...")
    
    # Step 3: Send message via API
    print(f"\n⏳ Step 3: Sending message via API...")
    try:
        response = api_client.post("/messages", json=message_payload)
        assert response.status_code == 201, f"Failed to create message: {response.status_code} - {response.text}"
    except httpx.TimeoutException:
        pytest.fail("Message creation timed out - API server may be overloaded")
    except Exception as e:
        pytest.fail(f"Failed to create message: {e}")
    result = response.json()
    
    message_id = result.get("message_id") or result.get("id")
    message_guid = result.get("guid")
    
    assert message_id is not None, "Message ID not returned"
    print(f"✅ Message created: ID={message_id}, GUID={message_guid}")

    def _cleanup() -> None:
        try:
            api_client.delete(f"/messages/{message_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)
    
    # Step 4: Wait for delivery (non-blocking with short timeouts)
    print(f"\n⏳ Step 4: Checking message delivery status...")
    max_wait = test_config.get("test.it114.max_wait") or test_config.get("api.timeout")
    wait_interval = test_config.get("test.it114.poll_interval") or test_config.get("api.connect_timeout")
    if max_wait is None or max_wait == "":
        pytest.fail("Missing max_wait. Configure test.it114.max_wait or api.timeout in env file.")
    if wait_interval is None or wait_interval == "":
        pytest.fail("Missing poll interval. Configure test.it114.poll_interval or api.connect_timeout in env file.")
    max_wait = int(max_wait)
    wait_interval = float(wait_interval)
    waited = 0
    delivery_completed = False
    message_data = None
    deliveries_data = None
    
    while waited < max_wait:
        time.sleep(wait_interval)
        waited += wait_interval
        
        # Check message status with SHORT timeout to avoid blocking
        try:
            msg_response = api_client.get(f"/messages/{message_id}")
            if msg_response.status_code == 200:
                message_data = msg_response.json()
                status = message_data.get("status", "unknown")
                print(f"   Status: {status} (waited {waited}s)")
                
                # Check deliveries with SHORT timeout
                try:
                    deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
                    if deliveries_response.status_code == 200:
                        deliveries_data = deliveries_response.json()
                        if deliveries_data.get("total", 0) > 0:
                            delivery = deliveries_data["items"][0]
                            delivery_state = delivery.get("state", "unknown")
                            print(f"   Delivery state: {delivery_state}")
                            
                            if delivery_state in ["sent", "delivered"]:
                                delivery_completed = True
                                print(f"✅ Delivery completed: {delivery_state}")
                                break
                except Exception as e:
                    print(f"   Delivery check timeout/error (non-blocking): {e}")
                    # Continue - don't block
                
                if status in ["completed", "failed"]:
                    break
        except httpx.TimeoutException:
            print(f"   Status check timeout (non-blocking, {waited}s) - continuing...")
            # Don't block - continue to next iteration or break
            if waited >= 10:  # After 10s, try to get data once more then proceed
                break
        except Exception as e:
            print(f"   Error checking status (non-blocking): {type(e).__name__} - continuing...")
            if waited >= 10:  # After 10s, proceed anyway
                break
            continue
    
    # If we don't have data yet, try one more quick check
    if not message_data:
        try:
            msg_response = api_client.get(f"/messages/{message_id}")
            if msg_response.status_code == 200:
                message_data = msg_response.json()
        except:
            pass  # Use what we have
    
    if not deliveries_data:
        try:
            deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
            if deliveries_response.status_code == 200:
                deliveries_data = deliveries_response.json()
        except:
            deliveries_data = {"total": 0, "items": []}  # Default
    
    # Step 5: Get full message details (if not already retrieved)
    print(f"\n📊 Step 5: Retrieving full message details...")
    if not message_data:
        try:
            message_response = api_client.get(f"/messages/{message_id}")
            if message_response.status_code == 200:
                message_data = message_response.json()
            else:
                message_data = {"status": "unknown", "created_at": "unknown"}
        except:
            message_data = {"status": "unknown", "created_at": "unknown"}
    
    if not deliveries_data or deliveries_data.get("total", 0) == 0:
        try:
            deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
            if deliveries_response.status_code == 200:
                deliveries_data = deliveries_response.json()
            else:
                deliveries_data = {"total": 0, "items": []}
        except:
            deliveries_data = {"total": 0, "items": []}
    
    # Step 6: Verify Slack rendering via Slack API
    print(f"\n🔎 Step 6: Verifying Slack rendering via Slack API...")
    wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)
    slack_message = wait_for_slack_message(
        slack_token,
        slack_channel_id,
        marker,
        timeout=wait_timeout,
        poll_interval=poll_interval,
        request_timeout=request_timeout,
    )
    assert_slack_mrkdwn_contains(slack_message, marker)

    # Step 7: Create summary document
    print(f"\n📝 Step 7: Creating summary document...")
    summary_dir = Path(__file__).parent.parent / "docs" / "test_results"
    summary_dir.mkdir(parents=True, exist_ok=True)
    
    summary_file = summary_dir / f"slack_webhook_test_{message_id}_{int(time.time())}.md"
    
    summary_content = f"""# Slack Webhook Test - Transparentbordes Channel

**Test Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Message ID**: {message_id}
**Message GUID**: {message_guid}

## Test Summary

✅ **Channel Configuration**: Verified
✅ **Message Creation**: Success (201 Created)
{'✅' if delivery_completed else '⏳'} **Message Delivery**: {'Completed' if delivery_completed else 'In Progress'}

## Channel Details

- **Channel Name**: `{channel_name}`
- **Webhook URL**: `{webhook_url}`
- **Channel Type**: `chat_rest`
- **Format**: `slack`

## Message Details

### Message Information
- **Message ID**: `{message_id}`
- **Message GUID**: `{message_guid}`
- **Status**: `{message_data.get('status', 'unknown')}`
- **Created At**: `{message_data.get('created_at', 'unknown')}`

### Content
```
{message_payload['content'][0]['body'][:500]}...
```

## Delivery Information

**Total Deliveries**: {deliveries_data.get('total', 0)}

"""
    
    if deliveries_data.get("total", 0) > 0:
        for idx, delivery in enumerate(deliveries_data.get("items", []), 1):
            summary_content += f"""
### Delivery {idx}
- **Delivery ID**: `{delivery.get('id')}`
- **State**: `{delivery.get('state', 'unknown')}`
- **Channel**: `{delivery.get('channel_name', 'unknown')}`
- **Destination**: `{delivery.get('destination', 'unknown')}`
- **Created At**: `{delivery.get('created_at', 'unknown')}`
- **Updated At**: `{delivery.get('updated_at', 'unknown')}`
"""
    
    summary_content += f"""
## API Links

### View Message
- **API Endpoint**: `GET {api_base_url}/messages/{message_id}`
- **Web UI**: `{web_base_url}/messages/{message_guid}`

### View Deliveries
- **API Endpoint**: `GET {api_base_url}/messages/{message_id}/deliveries`
- **Web UI**: `{web_base_url}/messages/{message_guid}`

## Test Results

{'✅ **SUCCESS**: Message delivered successfully to Slack webhook' if delivery_completed else '⏳ **IN PROGRESS**: Message delivery in progress'}
"""
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary_content)
    
    print(f"✅ Summary document created: {summary_file}")
    
    # Assertions (non-blocking - test passes if message was created)
    assert message_id is not None, "Message ID must be returned"
    # Note: Delivery may still be in progress, but message was created successfully
    if deliveries_data.get("total", 0) == 0:
        print("⚠️  Warning: No deliveries found yet (may still be processing)")
    else:
        print(f"✅ Found {deliveries_data.get('total', 0)} delivery(ies)")
    
    print("\n" + "="*70)
    print("TEST COMPLETED")
    print("="*70)
    print(f"✅ Message ID: {message_id}")
    print(f"✅ Summary: {summary_file}")
    print(f"{'✅' if delivery_completed else '⏳'} Delivery: {'Completed' if delivery_completed else 'In Progress'}")
    # Test completes without returning a value (pytest expects None).

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.integration,
    pytest.mark.live_provider,
    pytest.mark.live_delivery,
    pytest.mark.no_llm_dependency,
    pytest.mark.heavy,
]
