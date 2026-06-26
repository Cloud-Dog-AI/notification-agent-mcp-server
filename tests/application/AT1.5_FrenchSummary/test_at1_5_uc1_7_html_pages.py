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
AT1.5 Use Case UC1.7: Personalized Multimedia Notifications with HTML Pages

Tests personalised multimedia notifications with HTML page rendering.

Related Requirements: UC1.7, FR1.2, FR1.18
Related Architecture: CC4.1.1, CC5.1.1
Related Tests: AT1.5
"""

import pytest
import sys
import json
import time
import importlib.util
from pathlib import Path
from typing import Dict, Any
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
validate_language = _helpers_module.validate_language
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-009")


def test_at1_5_uc1_7_html_pages(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_email: str,
    test_output_dir: Path,
    smtp_channel_name: str,
):
    """
    Test UC1.7: Personalized Multimedia Notifications with HTML Pages
    
    Validates HTML page rendering in email notifications
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
        test_name="AT1.5_UC1_7_HTML_PAGES"
    )
    
    print(f"\n{'='*80}")
    print("AT1.5 USE CASE UC1.7: HTML PAGES")
    print(f"{'='*80}\n")
    
    # Get test configuration
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured")
    
    max_wait = test_config.get("test.at15.max_wait")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at15.max_wait not configured in env file")
    
    target_language = test_config.get("test.at15.uc1_7.language")
    if not target_language:
        pytest.fail(
            "❌ HARD FAIL: test.at15.uc1_7.language not configured in env file.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__AT15__UC1_7__LANGUAGE in env file"
        )
    
    # Load test message
    try:
        message_content = load_test_message("en", 2000)
        print(f"✅ Loaded test message: {len(message_content)} chars (EN)")
    except FileNotFoundError as e:
        pytest.fail(f"Test message file not found: {e}")
    
    # Create message with HTML content style
    print("\n" + "=" * 80)
    print("STEP 1: CREATE MESSAGE WITH HTML CONTENT")
    print("=" * 80)
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": smtp_channel_name,
            "address": test_email,
            "preferences": {
                "language": target_language,
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": message_content
        }],
        "options": {"subject": None}
    }
    subject = test_config.get("test.at15.uc1_7.subject")
    if not subject:
        pytest.fail("❌ HARD FAIL: test.at15.uc1_7.subject not configured in env file")
    message_payload["options"]["subject"] = subject
    
    try:
        with httpx.Client(timeout=api_timeout) as client:
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload
            )
            
            assert response.status_code == 201, f"Message creation failed: {response.status_code}"
            
            result = response.json()
            message_id = result.get("message_id")
            message_guid = result.get("guid")
            
            assert message_id, "Message ID not returned"
            print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
            
    except Exception as e:
        pytest.fail(f"❌ Message creation failed: {e}")
    
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
    
    # Validate HTML page content
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE HTML PAGE CONTENT")
    print("=" * 80)
    
    personalised_payload = delivery.get("personalised_payload")
    assert personalised_payload, "❌ No personalised_payload"
    
    if isinstance(personalised_payload, str):
        payload_data = json.loads(personalised_payload)
    else:
        payload_data = personalised_payload
    
    # Extract payload
    if isinstance(payload_data, dict):
        email_body = payload_data.get("body", "")
        email_content_type = payload_data.get("content_type", "text")
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        email_body = payload_data[0].get("body", "")
        email_content_type = payload_data[0].get("content_type", "text")
    else:
        pytest.fail(f"❌ Unexpected payload format")
    
    # Validate HTML structure
    assert "<" in email_body and ">" in email_body, "❌ Body is not HTML"
    assert any(tag in email_body.lower() for tag in ["<html", "<body", "<p>", "<div", "<h1", "<h2"]), "❌ Missing HTML structure"
    assert email_content_type == "html" or "html" in str(email_content_type).lower(), "❌ Content type not HTML"
    
    print(f"✅ HTML structure validated")
    print(f"   Content type: {email_content_type}")
    print(f"   Body length: {len(email_body)} chars")
    
    # Validate language
    if target_language != "en":
        is_valid, details = validate_language(email_body, target_language)
        assert is_valid, f"❌ Language validation failed: {details}"
        print(f"✅ Language validated: {target_language.upper()}")
        print(f"   Details: {details}")
    
    # Validate message link (HTML page link)
    import re
    link_match = re.search(r'href=["\']([^"\']+/messages/[^"\']+)["\']', email_body, re.IGNORECASE)
    
    if link_match:
        message_link = link_match.group(1)
        print(f"✅ Found message link: {message_link}")
        
        # Validate link points to HTML page
        try:
            with httpx.Client(timeout=api_timeout) as client:
                separator = "&" if "?" in message_link else "?"
                html_link = f"{message_link}{separator}format=html"
                response = client.get(
                    html_link,
                    headers={"X-API-Key": api_key},
                    timeout=api_timeout
                )
                
                if response.status_code == 200:
                    html_content = response.text
                    assert "<html" in html_content.lower() or "<!doctype html" in html_content.lower(), "❌ Link does not return HTML"
                    print(f"✅ Message link returns HTML page")
        except Exception as e:
            print(f"⚠️  Link validation error: {e}")
    
    # Save test log
    test_log_file = test_output_dir / "uc1_7_html_pages_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: AT1.5 UC1.7 - HTML Pages\n")
        f.write(f"Message ID: {message_id}\n")
        f.write(f"Message GUID: {message_guid}\n")
        f.write(f"Language: {target_language.upper()}\n")
        f.write(f"Content Type: {email_content_type}\n")
        f.write(f"Body Length: {len(email_body)} chars\n")
        f.write(f"HTML Validated: Yes\n")
        f.write(f"Delivery State: sent\n")
        f.write(f"Status: PASSED\n")
    
    print(f"✅ Test log saved: {test_log_file}")
    
    print(f"\n✅ UC1.7 HTML Pages test complete")
    print(f"   Message ID: {message_id}")
    print(f"   Language: {target_language.upper()}")
    print(f"   HTML validated: ✅")

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
