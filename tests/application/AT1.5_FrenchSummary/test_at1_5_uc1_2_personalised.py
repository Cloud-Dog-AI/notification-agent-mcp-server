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
AT1.5 Use Case UC1.2: Send Personalised Notification

Tests personalised notification with user preferences (language, format, etc.).

Related Requirements: UC1.2, FR1.2, FR1.4
Related Architecture: CC4.1.1, CC5.1.1
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
from src.config import RuntimeConfig

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
validate_language = _helpers_module.validate_language


@pytest.fixture(scope="module")
def personalised_scenarios_from_config(test_config):
    """Load personalised scenarios from config - NO HARDCODING"""
    if not test_config.get("at15_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.5 env file not loaded!")
    
    scenarios_json = test_config.get("test.at15.personalised.scenarios")
    if scenarios_json:
        if isinstance(scenarios_json, str):
            return json.loads(scenarios_json)
        return scenarios_json
    
    pytest.fail(
        "❌ HARD FAIL: test.at15.personalised.scenarios not configured in env file.\n"
        "Set CLOUD_DOG__NOTIFY__TEST__AT15__PERSONALISED__SCENARIOS=<json> in env file"
    )
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-009")


def test_at1_5_uc1_2_personalised(
    scenario_id: str,
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_email: str,
    test_output_dir: Path,
    personalised_scenarios_from_config: list,
    smtp_channel_name: str,
):
    """
    Test UC1.2: Send Personalised Notification
    
    Validates personalised notification with user preferences
    """
    # Load the specific scenario from config
    scenario = None
    for sc in personalised_scenarios_from_config:
        if sc.get("description") == scenario_id:
            scenario = sc
            break
    
    if not scenario:
        pytest.fail(f"❌ Scenario '{scenario_id}' not found in config")
    
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
        test_name=f"AT1.5_UC1_2_PERSONALISED_{scenario['language']}"
    )
    
    print(f"\n{'='*80}")
    print(f"AT1.5 USE CASE UC1.2: PERSONALISED NOTIFICATION")
    print(f"{'='*80}")
    print(f"Language: {scenario['language'].upper()}")
    print(f"Format: {scenario['content_style'].upper()}")
    print(f"Description: {scenario['description']}")
    print(f"{'='*80}\n")
    
    # Get test configuration
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured")
    
    max_wait = test_config.get("test.at15.max_wait")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at15.max_wait not configured in env file")
    
    # Load test message
    try:
        message_content = load_test_message("en", 400)
        print(f"✅ Loaded test message: {len(message_content)} chars (EN)")
    except FileNotFoundError as e:
        pytest.fail(f"Test message file not found: {e}")
    
    # Create personalised message
    print("\n" + "=" * 80)
    print("STEP 1: CREATE PERSONALISED MESSAGE")
    print("=" * 80)
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": smtp_channel_name,
            "address": test_email,
            "preferences": {
                "language": scenario["language"],
                "content_style": scenario["content_style"]
            }
        }],
        "content": [{
            "type": "text",
            "body": message_content
        }],
        "options": {
            "subject": test_config.get("test.at15.personalised.subject")
        }
    }
    
    try:
        with httpx.Client(timeout=api_timeout) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            
            assert response.status_code == 201, f"Personalised message creation failed: {response.status_code}"
            
            result = response.json()
            message_id = result.get("message_id")
            
            assert message_id, "Message ID not returned"
            print(f"✅ Personalised message created: ID={message_id}")
            print(f"   Language: {scenario['language'].upper()}")
            print(f"   Format: {scenario['content_style'].upper()}")
            
    except Exception as e:
        pytest.fail(f"❌ Personalised message creation failed: {e}")
    
    # Wait for delivery
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR DELIVERY")
    print("=" * 80)
    
    delivery = None
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
                    
                    if deliveries:
                        delivery = deliveries[0]
                        state = delivery.get("state")
                        elapsed = time.time() - start_time
                        
                        if (i + 1) % 10 == 0:
                            print(f"  Attempt {i+1}: state={state}, elapsed={elapsed:.1f}s")
                        
                        if state == "sent":
                            print(f"✅ Delivery completed in {elapsed:.1f}s")
                            break
                        elif state in ["hard_failed", "cancelled"]:
                            pytest.fail(f"❌ Delivery failed: {delivery.get('last_error')}")
                
            time.sleep(poll_interval)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {e}")
            time.sleep(poll_interval)
            continue
    
    assert delivery is not None, f"❌ Delivery not found after {max_wait}s"
    assert delivery.get("state") == "sent", f"❌ Delivery state is '{delivery.get('state')}', expected 'sent'"
    
    # Validate personalisation
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE PERSONALISATION")
    print("=" * 80)
    
    personalised_payload = delivery.get("personalised_payload")
    assert personalised_payload, "❌ No personalised_payload"
    
    if isinstance(personalised_payload, str):
        payload_data = json.loads(personalised_payload)
    else:
        payload_data = personalised_payload
    
    if isinstance(payload_data, dict):
        email_body = payload_data.get("body", "")
        email_content_type = payload_data.get("content_type", "text")
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        email_body = payload_data[0].get("body", "")
        email_content_type = payload_data[0].get("content_type", "text")
    else:
        pytest.fail(f"❌ Unexpected payload format")
    
    # Validate format
    if scenario["content_style"] == "html":
        assert "<" in email_body and ">" in email_body, "❌ Body is not HTML"
        assert email_content_type == "html" or "html" in str(email_content_type).lower(), "❌ Content type not HTML"
        print(f"✅ Format validated: HTML")
    else:
        assert "<html" not in email_body.lower(), "❌ Plain text contains HTML"
        print(f"✅ Format validated: Plain Text")
    
    # Validate language (if not EN→EN)
    if scenario["language"] != "en":
        is_valid, details = validate_language(email_body, scenario["language"])
        assert is_valid, f"❌ Language validation failed: {details}"
        print(f"✅ Language validated: {scenario['language'].upper()}")
        print(f"   Details: {details}")
    else:
        print(f"✅ Language validated: English (baseline)")
    
    # Save test log
    test_log_file = test_output_dir / f"uc1_2_personalised_{scenario['language']}_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: AT1.5 UC1.2 - Personalised Notification\n")
        f.write(f"Message ID: {message_id}\n")
        f.write(f"Language: {scenario['language'].upper()}\n")
        f.write(f"Format: {scenario['content_style'].upper()}\n")
        f.write(f"Description: {scenario['description']}\n")
        f.write(f"Delivery State: sent\n")
        f.write(f"Status: PASSED\n")
    
    print(f"✅ Test log saved: {test_log_file}")
    
    print(f"\n✅ UC1.2 Personalised notification test complete")
    print(f"   Message ID: {message_id}")
    print(f"   Language: {scenario['language'].upper()}")
    print(f"   Format: {scenario['content_style'].upper()}")

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


def pytest_generate_tests(metafunc):
    """
    Parametrise personalised scenarios from env config (no hardcoded scenario list).
    """
    if "scenario_id" in metafunc.fixturenames:
        env_file = metafunc.config.getoption("--env")
        if not env_file:
            raise RuntimeError("AT1.5 requires --env private/env-test-at15")
        cfg = RuntimeConfig(env_file=env_file, load_env_file=True, unresolved_policy="empty")
        scenarios_json = cfg.get("test.at15.personalised.scenarios")
        if not scenarios_json:
            raise RuntimeError("test.at15.personalised.scenarios not configured in env file")
        scenarios = json.loads(scenarios_json) if isinstance(scenarios_json, str) else scenarios_json
        ids = [s["description"] for s in scenarios]
        metafunc.parametrize("scenario_id", ids, ids=ids)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
