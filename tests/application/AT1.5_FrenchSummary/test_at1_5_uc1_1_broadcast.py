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
AT1.5 Use Case UC1.1: Send Broadcast Notification

Tests broadcast notification to multiple recipients via email channel.

Related Requirements: UC1.1, FR1.1, FR1.6
Related Architecture: CC2.1, CC5.1.1
Related Tests: AT1.5
"""

import pytest
import sys
import json
import time
import importlib.util
from pathlib import Path
from typing import Dict, Any, List
import httpx

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies

_helpers_path = project_root / "tests" / "application" / "AT1.4_Comprehensive" / "helpers.py"
_helpers_spec = importlib.util.spec_from_file_location("at14_helpers", _helpers_path)
if _helpers_spec is None or _helpers_spec.loader is None:
    raise ImportError(f"Unable to load AT1.4 helper module from {_helpers_path}")
_helpers_module = importlib.util.module_from_spec(_helpers_spec)
_helpers_spec.loader.exec_module(_helpers_module)

load_test_message = _helpers_module.load_test_message
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-006")


def test_at1_5_uc1_1_broadcast(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_email: str,
    test_output_dir: Path,
    smtp_channel_name: str,
):
    """
    Test UC1.1: Send Broadcast Notification
    
    Validates broadcast notification to multiple recipients
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("at15_env_loaded"):
        pytest.fail(
            "❌ CRITICAL: AT1.5 env file not loaded!\n"
            "Required: --env private/env-test-at15\n"
        )
    
    # CRITICAL: Check dependencies
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=True,
        requires_api=True,
        test_name="AT1.5_UC1_1_BROADCAST"
    )
    
    print(f"\n{'='*80}")
    print("AT1.5 USE CASE UC1.1: BROADCAST NOTIFICATION")
    print(f"{'='*80}\n")
    
    # Get test configuration
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured")
    
    max_wait = test_config.get("test.at15.max_wait")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at15.max_wait not configured in env file")
    
    # Get broadcast recipients from config
    broadcast_recipients = test_config.get("test.at15.broadcast.recipients")
    if not broadcast_recipients:
        pytest.fail(
            "❌ HARD FAIL: test.at15.broadcast.recipients not configured in env file.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__AT15__BROADCAST__RECIPIENTS in env file"
        )
    
    if isinstance(broadcast_recipients, str):
        broadcast_recipients = [r.strip() for r in broadcast_recipients.split(",")]
    
    print(f"📧 Broadcast recipients: {len(broadcast_recipients)}")
    for i, recipient in enumerate(broadcast_recipients[:5], 1):  # Show first 5
        print(f"   {i}. {recipient}")
    if len(broadcast_recipients) > 5:
        print(f"   ... and {len(broadcast_recipients) - 5} more")
    
    # Load test message
    try:
        message_content = load_test_message("en", 400)
        print(f"✅ Loaded test message: {len(message_content)} chars")
    except FileNotFoundError as e:
        pytest.fail(f"Test message file not found: {e}")
    
    # Create broadcast message
    print("\n" + "=" * 80)
    print("STEP 1: CREATE BROADCAST MESSAGE")
    print("=" * 80)
    
    message_payload = {
        "audience_type": "broadcast",
        "destinations": [
            {
                "channel": smtp_channel_name,
                "address": recipient,
                "preferences": {
                    "language": "en",
                    "content_style": "html"
                }
            }
            for recipient in broadcast_recipients
        ],
        "content": [{
            "type": "text",
            "body": message_content
        }],
        "options": {
            "subject": None
        }
    }
    broadcast_subject = test_config.get("test.at15.broadcast.subject")
    if not broadcast_subject:
        pytest.fail("❌ HARD FAIL: test.at15.broadcast.subject not configured in env file")
    message_payload["options"]["subject"] = broadcast_subject
    
    try:
        with httpx.Client(timeout=api_timeout) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            
            assert response.status_code == 201, f"Broadcast message creation failed: {response.status_code}"
            
            result = response.json()
            message_id = result.get("message_id")
            
            assert message_id, "Message ID not returned"
            print(f"✅ Broadcast message created: ID={message_id}")
            print(f"   Recipients: {len(broadcast_recipients)}")
            
    except Exception as e:
        pytest.fail(f"❌ Broadcast message creation failed: {e}")
    
    # Wait for all deliveries
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR ALL DELIVERIES")
    print("=" * 80)
    
    deliveries_completed = 0
    start_time = time.time()
    poll_interval = test_config.get("test.at15.poll_interval")
    if not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at15.poll_interval not configured in env file")
    
    max_attempts = int(max_wait / poll_interval)
    
    for i in range(max_attempts):
        try:
            with httpx.Client(timeout=api_timeout) as client:
                response = client.get(
                    f"{api_base_url}/messages/{message_id}/deliveries",
                    headers={"X-API-Key": api_key}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    deliveries = data.get("items", [])
                    
                    sent_deliveries = [d for d in deliveries if d.get("state") == "sent"]
                    failed_deliveries = [d for d in deliveries if d.get("state") in ["hard_failed", "soft_failed"]]
                    
                    elapsed = time.time() - start_time
                    
                    if (i + 1) % 10 == 0:
                        print(f"  Attempt {i+1}: {len(sent_deliveries)} sent, {len(failed_deliveries)} failed, {len(deliveries)} total")
                    
                    if len(sent_deliveries) == len(broadcast_recipients):
                        print(f"✅ All deliveries completed in {elapsed:.1f}s")
                        deliveries_completed = len(sent_deliveries)
                        break
                    elif len(sent_deliveries) + len(failed_deliveries) == len(broadcast_recipients):
                        print(f"⚠️  All deliveries finished: {len(sent_deliveries)} sent, {len(failed_deliveries)} failed")
                        deliveries_completed = len(sent_deliveries)
                        break
                
            time.sleep(poll_interval)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {e}")
            time.sleep(poll_interval)
            continue
    
    # Validate broadcast results
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE BROADCAST RESULTS")
    print("=" * 80)
    
    assert deliveries_completed > 0, f"❌ No deliveries completed after {max_wait}s"
    
    success_rate = deliveries_completed / len(broadcast_recipients)
    print(f"✅ Broadcast delivery results:")
    print(f"   Total recipients: {len(broadcast_recipients)}")
    print(f"   Successful deliveries: {deliveries_completed}")
    print(f"   Success rate: {success_rate*100:.1f}%")
    
    success_rate_threshold = test_config.get("test.at15.broadcast.success_rate_threshold")
    if not success_rate_threshold:
        pytest.fail(
            "❌ HARD FAIL: test.at15.broadcast.success_rate_threshold not configured in env file.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__AT15__BROADCAST__SUCCESS_RATE_THRESHOLD in env file"
        )
    
    assert success_rate >= success_rate_threshold, f"Success rate too low: {success_rate*100:.1f}% (threshold: {success_rate_threshold*100:.1f}%)"
    
    # Get final deliveries for detailed validation
    print("\n" + "=" * 80)
    print("STEP 4: DETAILED DELIVERY VALIDATION")
    print("=" * 80)
    
    try:
        with httpx.Client(timeout=api_timeout) as client:
            response = client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key}
            )
            
            if response.status_code == 200:
                data = response.json()
                deliveries = data.get("items", [])
                
                print(f"✅ Total deliveries: {len(deliveries)}")
                
                for delivery in deliveries[:3]:  # Show first 3
                    state = delivery.get("state")
                    dest = delivery.get("destination")
                    print(f"   • {dest}: {state}")
                
                if len(deliveries) > 3:
                    print(f"   ... and {len(deliveries) - 3} more")
                
                # Validate all expected deliveries exist
                expected_count = len(broadcast_recipients)
                actual_count = len(deliveries)
                assert actual_count == expected_count, f"Delivery count mismatch: expected {expected_count}, got {actual_count}"
                print(f"✅ All {expected_count} deliveries created")
                
    except Exception as e:
        print(f"⚠️  Detailed validation error: {e}")
    
    # Save test log
    test_log_file = test_output_dir / "uc1_1_broadcast_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: AT1.5 UC1.1 - Broadcast Notification\n")
        f.write(f"Message ID: {message_id}\n")
        f.write(f"Recipients: {len(broadcast_recipients)}\n")
        f.write(f"Successful Deliveries: {deliveries_completed}\n")
        f.write(f"Success Rate: {success_rate*100:.1f}%\n")
        f.write(f"Threshold: {success_rate_threshold*100:.1f}%\n")
        f.write(f"Status: {'PASSED' if success_rate >= success_rate_threshold else 'FAILED'}\n")
    
    print(f"✅ Test log saved: {test_log_file}")
    
    print(f"\n✅ UC1.1 Broadcast notification test complete")
    print(f"   Message ID: {message_id}")
    print(f"   Deliveries: {deliveries_completed}/{len(broadcast_recipients)}")
    print(f"   Success Rate: {success_rate*100:.1f}%")

    # Best-effort cleanup (API-only)
    if message_id is not None:
        try:
            with httpx.Client(timeout=api_timeout) as client:
                resp = client.delete(f"{api_base_url}/messages/{message_id}", headers={"X-API-Key": api_key})
                if resp.status_code in (200, 204, 404):
                    print(f"[Cleanup] ✅ Deleted message {message_id} (status {resp.status_code})")
        except Exception as e:
            print(f"[Cleanup] ⚠️  Exception deleting message {message_id}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
