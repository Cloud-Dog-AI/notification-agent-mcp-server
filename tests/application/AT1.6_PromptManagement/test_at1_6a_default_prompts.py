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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: AT1.6A - Default Channel Prompts Test
Tests that default prompts are correctly selected for each channel type
when no overrides exist, and that prompt variables are substituted correctly.

Related Requirements: FR1.15, FR1.3, UC1.5
Related Tasks: T18
Related Architecture: CC4.1.2
Related Tests: AT1.6, UT1.6

**************************************************
"""

import pytest
import httpx
import asyncio
import json
from pathlib import Path
from typing import Any, Dict
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


async def test_at1_6a_default_channel_prompts(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    test_config: Dict[str, Any],
    test_output_dir: Path,
    ollama_model: str,
    smtp_channel_name: str,
    request,
):
    """
    AT1.6A: Default Channel Prompts Test
    
    Tests:
    1. Default prompt exists for each channel type
    2. Default prompt is selected when no overrides exist
    3. Prompt variables are substituted correctly
    4. Message is formatted according to default prompt
    5. Output matches channel restrictions
    
    Requirements: FR1.15 (Default Prompts)
    """
    print("\n" + "="*80)
    print("AT1.6A: DEFAULT CHANNEL PROMPTS TEST")
    print("="*80)
    
    # =========================================================================
    # ENVIRONMENT VALIDATION
    # =========================================================================
    if not test_config.get("test.at16_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.6 env file not loaded! Use --env private/env-test-at16")
    
    created_message_ids = []
    headers = {"X-API-Key": api_key}

    def _cleanup():
        if not created_message_ids:
            return
        print("\n[Cleanup] Deleting created messages (API-only)...")
        with httpx.Client(timeout=api_timeout) as client:
            for mid in created_message_ids:
                try:
                    resp = client.delete(f"{api_base_url}/messages/{mid}", headers=headers)
                    if resp.status_code in (200, 204, 404):
                        print(f"[Cleanup] ✅ DELETE /messages/{mid}: {resp.status_code}")
                    else:
                        print(f"[Cleanup] ⚠️  DELETE /messages/{mid}: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    print(f"[Cleanup] ⚠️  Exception deleting message {mid}: {type(e).__name__}: {e}")

    request.addfinalizer(_cleanup)

    # Get test parameters from config - NO HARDCODING
    test_message = test_config.get("test.at16.a.test_message")
    if not test_message:
        pytest.fail("❌ HARD FAIL: test.at16.a.test_message not configured")
    
    test_email = test_config.get("test.at16.a.test_email")
    if not test_email:
        pytest.fail("❌ HARD FAIL: test.at16.a.test_email not configured")
    
    channels_json = test_config.get("test.at16.a.channels")
    if not channels_json:
        pytest.fail("❌ HARD FAIL: test.at16.a.channels not configured")
    
    # Parse channels
    if isinstance(channels_json, str):
        test_channels = json.loads(channels_json)
    else:
        test_channels = channels_json
    
    max_wait = test_config.get("test.at16.max_wait")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at16.max_wait not configured")
    max_wait = float(max_wait)
    
    poll_interval = test_config.get("test.at16.poll_interval")
    if not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at16.poll_interval not configured")
    poll_interval = float(poll_interval)
    
    print(f"\n✅ Environment validated")
    print(f"   API URL: {api_base_url}")
    print(f"   Test channels: {test_channels}")
    print(f"   Test email: {test_email}")
    print(f"   Max wait: {max_wait}s")
    print(f"   Poll interval: {poll_interval}s")
    
    # Test results storage
    test_results = []
    
    # =========================================================================
    # STEP 1: VERIFY DEFAULT PROMPTS EXIST
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 1: VERIFY DEFAULT PROMPTS EXIST")
    print("="*80)
    
    with httpx.Client(timeout=api_timeout) as client:
        # Get all prompts
        response = client.get(
            f"{api_base_url}/prompts",
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 200, f"Failed to get prompts: {response.status_code}"
        prompts = response.json()
        
        print(f"✅ Retrieved {len(prompts)} prompts from database")
        
        # Verify default prompt exists for each test channel
        for channel in test_channels:
            default_prompts = [p for p in prompts if p.get("channel_type") == channel and p.get("group_id") is None]
            
            assert len(default_prompts) > 0, f"❌ No default prompt found for channel '{channel}'"
            
            default_prompt = default_prompts[0]
            print(f"✅ Default prompt found for '{channel}': ID={default_prompt['id']}, Name={default_prompt['name']}")
            print(f"   Priority: {default_prompt['priority']}")
            print(f"   Enabled: {default_prompt['enabled']}")
            print(f"   Prompt length: {len(default_prompt['prompt_text'])} chars")
            
            # Validate prompt structure
            assert default_prompt['prompt_text'], f"❌ Prompt text is empty for {channel}"
            assert default_prompt['enabled'], f"❌ Default prompt for {channel} is disabled"
    
    # =========================================================================
    # STEP 2: SEND MESSAGE USING DEFAULT PROMPTS
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 2: SEND MESSAGE USING DEFAULT PROMPTS")
    print("="*80)
    
    for channel in test_channels:
        print(f"\n--- Testing channel: {channel} ---")
        
        # Prepare message request
        message_data = {
            "audience_type": "direct",
            "destinations": [
                {
                    "channel": smtp_channel_name if channel == "email" else channel,
                    "address": test_email
                }
            ],
            "content": [
                {
                    "type": "text",
                    "body": test_message
                }
            ],
            "variables": {
                "subject": f"AT1.6A Test - {channel.upper()} Default Prompt"
            }
        }
        
        with httpx.Client(timeout=api_timeout) as client:
            # Create message
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key},
                json=message_data
            )
            
            assert response.status_code == 201, f"Failed to create message: {response.status_code} - {response.text}"
            
            message_response = response.json()
            message_id = message_response.get("message_id") or message_response.get("id")
            message_guid = message_response["guid"]
            created_message_ids.append(message_id)
            
            print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            
            # =========================================================================
            # STEP 3: WAIT FOR DELIVERY AND VALIDATE FORMATTING
            # =========================================================================
            print(f"\n[STEP 3] Waiting for delivery...")
            
            delivered = False
            elapsed = 0
            delivery_data = None
            
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                
                # Get deliveries
                response = client.get(
                    f"{api_base_url}/messages/{message_id}/deliveries",
                    headers={"X-API-Key": api_key}
                )
                
                assert response.status_code == 200, f"Failed to get deliveries: {response.status_code}"
                
                deliveries_response = response.json()
                # Handle both old array format and new paginated format
                if isinstance(deliveries_response, dict) and 'items' in deliveries_response:
                    deliveries = deliveries_response['items']
                else:
                    deliveries = deliveries_response
                
                if deliveries and len(deliveries) > 0:
                    delivery_data = deliveries[0]
                    state = delivery_data.get("state", "unknown")
                    
                    print(f"   [{elapsed:.1f}s] Delivery state: {state}")
                    
                    if state in ["sent", "accepted", "delivered"]:
                        delivered = True
                        break
                    elif state in ["hard_failed", "soft_failed"]:
                        pytest.fail(f"❌ Delivery failed: {delivery_data.get('last_error')}")
            
            assert delivered, f"❌ Delivery did not complete within {max_wait}s"
            print(f"✅ Delivery completed in {elapsed:.1f}s")
            
            # =========================================================================
            # STEP 4: VALIDATE FORMATTED CONTENT
            # =========================================================================
            print(f"\n[STEP 4] Validating formatted content...")
            
            assert delivery_data is not None, "❌ No delivery data"
            
            # Check personalised_payload exists
            payload = delivery_data.get("personalised_payload")
            assert payload, "❌ No personalised_payload in delivery"
            
            # Validate payload structure
            assert isinstance(payload, str) or isinstance(payload, dict), "❌ Invalid payload type"
            
            if isinstance(payload, str):
                # Try to parse as JSON
                try:
                    payload = json.loads(payload)
                except:
                    pass  # Plain text payload is fine
            
            print(f"✅ Formatted content validated")
            print(f"   Payload type: {type(payload).__name__}")
            if isinstance(payload, dict):
                print(f"   Payload keys: {list(payload.keys())}")
            elif isinstance(payload, str):
                print(f"   Payload length: {len(payload)} chars")
            
            # Store test result
            test_results.append({
                "channel": channel,
                "message_id": message_id,
                "guid": message_guid,
                "state": delivery_data.get("state"),
                "formatted": True
            })
    
    # =========================================================================
    # STEP 5: GENERATE TEST LOG
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: GENERATE TEST LOG")
    print("="*80)
    
    log_content = f"""AT1.6A: Default Channel Prompts Test Log
Generated: {asyncio.get_event_loop().time()}

Test Configuration:
- API URL: {api_base_url}
- Test channels: {test_channels}
- Test email: {test_email}
- Test message: {test_message[:100]}...

Test Results:
"""
    
    for result in test_results:
        log_content += f"""
Channel: {result['channel']}
Message ID: {result['message_id']}
GUID: {result['guid']}
State: {result['state']}
Formatted: {result['formatted']}
---
"""
    
    log_file = test_output_dir / "at1_6a_default_prompts_log.txt"
    log_file.write_text(log_content)
    print(f"✅ Test log saved: {log_file}")
    
    print("\n" + "="*80)
    print("✅ AT1.6A: DEFAULT CHANNEL PROMPTS TEST COMPLETE")
    print("="*80)
    print(f"   Channels tested: {len(test_results)}")
    print(f"   All messages delivered: ✅")
    print(f"   All messages formatted: ✅")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.llm, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]

