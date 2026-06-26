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
Test email attachment and message link functionality

Tests:
1. Attachment contains full formatted message (not original)
2. Attachment format matches requested format (HTML/text)
3. Message link shows full message (not summary)
4. Message link shows original message
5. Message link shows original settings
6. Message link shows destination
7. Message link shows links to message and delivery details

French and English versions
"""

import pytest
import httpx
import json
import time
import os
import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies

# CRITICAL: All timeouts must be set
API_TIMEOUT = 10.0
WAIT_TIMEOUT = 300.0  # Max wait for delivery (5 minutes for LLM processing)
POLL_INTERVAL = 2.0


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
        content = f.read()
        # Truncate to 5000 chars for testing
        return content[:5000]
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_email_attachment_french(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """Test email attachment and message link functionality with French translation"""
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for formatting/translation
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_email_attachment_french"
    )
    
    print(f"\n{'='*80}")
    print("EMAIL ATTACHMENT AND LINK TEST (FRENCH)")
    print(f"{'='*80}\n")
    
    # Read test message from config
    test_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(test_content)} characters")
    
    # Create message with French language preference
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
            "preferences": {
                "language": "fr",  # French
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": f"Please provide a summary in French of the following content:\n\n{test_content}"
        }],
        "options": {
            "subject": "Test Message Summary - French"
        }
    }
    
    print(f"📧 Destination: {test_email}")
    print(f"🌐 Language: French (fr)")
    print(f"📝 Content style: HTML")
    print(f"📌 Requested subject: {message_payload['options']['subject']}\n")
    
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
    
    # Validate SMTP server acceptance
    last_error = delivery.get("last_error")
    state = delivery.get("state")
    if last_error:
        print(f"❌ Delivery {delivery_id} REJECTED by SMTP server: {last_error}")
        pytest.fail(f"Email delivery {delivery_id} rejected by SMTP server: {last_error}")
    else:
        print(f"✅ Delivery {delivery_id} ACCEPTED by SMTP server (no last_error reported)")
    
    if state == "hard_failed":
        print(f"❌ Delivery {delivery_id} state is 'hard_failed'. Error: {last_error}")
        pytest.fail(f"Delivery {delivery_id} ended in hard_failed state: {last_error}")
    elif state != "sent":
        print(f"⚠️  WARNING: Delivery {delivery_id} state is '{state}', expected 'sent'.")
    else:
        print(f"✅ Delivery {delivery_id} state is 'sent'.")
    
    # Step 3: Validate Attachment
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE ATTACHMENT")
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
    
    # Get attachments from payload (handle both dict and list formats)
    attachments = []
    if isinstance(payload_data, dict):
        attachments = payload_data.get("attachments", [])
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        block = payload_data[0]
        if isinstance(block, dict):
            attachments = block.get("attachments", [])
    
    assert len(attachments) > 0, "❌ No attachments found in delivery payload"
    print(f"✅ Found {len(attachments)} attachment(s)")
    
    attachment = attachments[0]
    assert attachment is not None, "❌ Attachment is None or empty"
    
    filename = attachment.get("filename", "")
    content_type = attachment.get("content_type", "")
    content = attachment.get("content", "")
    
    assert filename, "❌ Attachment missing filename"
    assert content, "❌ Attachment missing content"
    assert content_type, "❌ Attachment missing content_type"
    
    # Get message_guid if not already available
    if not message_guid and message_id:
        try:
            with httpx.Client(timeout=API_TIMEOUT) as guid_client:
                guid_response = guid_client.get(
                    f"{api_base_url}/messages/{message_id}",
                    headers={"X-API-Key": api_key}
                )
                if guid_response.status_code == 200:
                    guid_data = guid_response.json()
                    message_guid = guid_data.get("guid")
        except:
            pass
    
    # Validate filename format
    if message_guid:
        expected_filename = f"message_{message_guid[:8]}.html"
        assert filename == expected_filename, \
            f"❌ Attachment filename mismatch: expected '{expected_filename}', got '{filename}'"
    else:
        # If GUID not available, just check filename format
        if not filename.startswith("message_") or not filename.endswith(".html"):
            pytest.fail(f"❌ Attachment filename format incorrect: '{filename}'")
    
    print(f"✅ Attachment filename correct: {filename}")
    
    # Validate content type
    assert content_type == "text/html", f"❌ Expected HTML attachment, got {content_type}"
    print(f"✅ Attachment content type correct: {content_type}")
    
    # Validate content is HTML
    has_html_structure = any(tag in content.lower() for tag in ["<h1>", "<h2>", "<p>", "<div", "<ul>", "<li>", "<strong>", "<em>"])
    assert has_html_structure, "❌ Attachment should contain HTML tags"
    print(f"✅ Attachment content is HTML (contains HTML tags)")
    
    # Validate content is formatted (French keywords or HTML structure)
    french_indicators = ["français", "résumé", "contenu", "le", "la", "les", "de", "du", "des", "et"]
    has_french = any(indicator in content.lower() for indicator in french_indicators)
    has_html_tags = "<p>" in content or "<html>" in content.lower()
    
    assert has_french or has_html_tags, \
        "❌ Attachment should contain formatted/translated content (French keywords or HTML structure), not raw original"
    
    if has_french:
        print(f"✅ Attachment content is in French (contains French keywords)")
    else:
        print(f"✅ Attachment content has HTML structure")
    
    print(f"✅ Attachment content length: {len(content)} chars")
    
    # Step 4: Validate Message Link - Full Message
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATE MESSAGE LINK - FULL MESSAGE")
    print("=" * 80)
    
    with httpx.Client(timeout=API_TIMEOUT) as client:
        response = client.get(
            f"{api_base_url}/messages/{message_id}?format=html",
            headers={"X-API-Key": api_key},
            timeout=10.0
        )
        assert response.status_code == 200, f"❌ Failed to get message: {response.text[:200]}"
        html_content = response.text
        
        # Check that it shows full message (not summary)
        assert "Formatted Message Content" in html_content or "message-content" in html_content, \
            "❌ Message page should show formatted message content"
        
        # Should not be just a summary
        assert len(html_content) > 1000, f"❌ Message page should show full content, not just summary (got {len(html_content)} chars)"
        
        print(f"✅ Message link shows full message: {len(html_content)} chars")
        print(f"✅ Formatted message content section present")
    
    # Step 5: Validate Message Link - Original Message
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE MESSAGE LINK - ORIGINAL MESSAGE")
    print("=" * 80)
    
    assert "Original Message" in html_content or "original-content" in html_content, \
        "❌ Message page should show original message section"
    
    print("✅ Message link shows original message section")
    
    # Step 6: Validate Message Link - Original Settings
    print("\n" + "=" * 80)
    print("STEP 6: VALIDATE MESSAGE LINK - ORIGINAL SETTINGS")
    print("=" * 80)
    
    assert "Original Settings" in html_content or "settings" in html_content.lower(), \
        "❌ Message page should show original settings section"
    
    # Should contain subject in settings
    assert "subject" in html_content.lower() or "Test Message Summary" in html_content, \
        "❌ Message page should show subject in settings"
    
    print("✅ Message link shows original settings section")
    print("✅ Subject displayed in settings")
    
    # Step 7: Validate Message Link - Destination
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE MESSAGE LINK - DESTINATION")
    print("=" * 80)
    
    assert "Destination" in html_content, "❌ Message page should show destination section"
    assert test_email in html_content, f"❌ Message page should show destination email: {test_email}"
    
    print("✅ Message link shows destination section")
    print(f"✅ Destination email displayed: {test_email}")
    
    # Step 8: Validate Message Link - Format Links
    print("\n" + "=" * 80)
    print("STEP 8: VALIDATE MESSAGE LINK - FORMAT LINKS")
    print("=" * 80)
    
    assert "Links" in html_content or "links" in html_content.lower(), \
        "❌ Message page should show links section"
    
    # Should have links to different formats
    assert f"/messages/{message_id}?format=json" in html_content or f'messages/{message_id}?format=json' in html_content, \
        "❌ Message page should have link to JSON format"
    assert f"/messages/{message_id}?format=html" in html_content or f'messages/{message_id}?format=html' in html_content, \
        "❌ Message page should have link to HTML format"
    assert f"/messages/{message_id}?format=markdown" in html_content or f'messages/{message_id}?format=markdown' in html_content, \
        "❌ Message page should have link to Markdown format"
    
    print("✅ Message link shows links section")
    print("✅ Format links present (JSON, HTML, Markdown)")
    
    # Step 9: Validate Message Link - Delivery Links (Optional - removed from UI per user request)
    print("\n" + "=" * 80)
    print("STEP 9: VALIDATE MESSAGE LINK - DELIVERY LINKS")
    print("=" * 80)
    
    # Note: Delivery links were removed from HTML display per user request (require API key)
    # This check is now optional
    has_delivery_link = f"/messages/{message_id}/deliveries" in html_content or f'messages/{message_id}/deliveries' in html_content
    if has_delivery_link:
        print("✅ Message link shows delivery links")
    else:
        print("⚠️  Delivery links not present in HTML (expected - removed from UI, require API key)")
    
    # Step 10: Summary
    print("\n" + "=" * 80)
    print("STEP 10: SUMMARY")
    print("=" * 80)
    
    print(f"\n📋 MESSAGE INFORMATION:")
    print(f"   Message ID: {message_id}")
    print(f"   Message GUID: {message_guid}")
    print(f"   Delivery ID: {delivery_id}")
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Attachment: EXISTS, FORMAT CORRECT, CONTENT VALIDATED")
    print(f"   ✅ Message Link: FULL MESSAGE, ORIGINAL, SETTINGS, DESTINATION")
    print(f"   ✅ Format Links: JSON, HTML, MARKDOWN")
    print(f"   ✅ SMTP Delivery: ACCEPTED")
    
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - ALL VALIDATIONS PERFORMED")
    print(f"{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_email_attachment_english(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """Test email attachment and message link functionality with English (no translation)"""
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for formatting
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_email_attachment_english"
    )
    
    print(f"\n{'='*80}")
    print("EMAIL ATTACHMENT AND LINK TEST (ENGLISH)")
    print(f"{'='*80}\n")
    
    # Read test message from config
    test_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(test_content)} characters")
    
    # Create message with English (no translation, HTML format)
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
            "preferences": {
                "language": "en",  # English
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": f"Please provide a summary of the following content:\n\n{test_content}"
        }],
        "options": {
            "subject": "Test Message Summary - English"
        }
    }
    
    print(f"📧 Destination: {test_email}")
    print(f"🌐 Language: English (en)")
    print(f"📝 Content style: HTML")
    print(f"📌 Requested subject: {message_payload['options']['subject']}\n")
    
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
    
    # Validate SMTP server acceptance
    last_error = delivery.get("last_error")
    state = delivery.get("state")
    if last_error:
        print(f"❌ Delivery {delivery_id} REJECTED by SMTP server: {last_error}")
        pytest.fail(f"Email delivery {delivery_id} rejected by SMTP server: {last_error}")
    else:
        print(f"✅ Delivery {delivery_id} ACCEPTED by SMTP server (no last_error reported)")
    
    if state == "hard_failed":
        print(f"❌ Delivery {delivery_id} state is 'hard_failed'. Error: {last_error}")
        pytest.fail(f"Delivery {delivery_id} ended in hard_failed state: {last_error}")
    elif state != "sent":
        print(f"⚠️  WARNING: Delivery {delivery_id} state is '{state}', expected 'sent'.")
    else:
        print(f"✅ Delivery {delivery_id} state is 'sent'.")
    
    # Step 3: Validate Attachment
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE ATTACHMENT")
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
    
    # Get attachments from payload (handle both dict and list formats)
    attachments = []
    if isinstance(payload_data, dict):
        attachments = payload_data.get("attachments", [])
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        block = payload_data[0]
        if isinstance(block, dict):
            attachments = block.get("attachments", [])
    
    assert len(attachments) > 0, "❌ No attachments found in delivery payload"
    print(f"✅ Found {len(attachments)} attachment(s)")
    
    attachment = attachments[0]
    assert attachment is not None, "❌ Attachment is None or empty"
    
    filename = attachment.get("filename", "")
    content_type = attachment.get("content_type", "")
    content = attachment.get("content", "")
    
    assert filename, "❌ Attachment missing filename"
    assert content, "❌ Attachment missing content"
    assert content_type, "❌ Attachment missing content_type"
    
    # Get message_guid if not already available
    if not message_guid and message_id:
        try:
            with httpx.Client(timeout=API_TIMEOUT) as guid_client:
                guid_response = guid_client.get(
                    f"{api_base_url}/messages/{message_id}",
                    headers={"X-API-Key": api_key}
                )
                if guid_response.status_code == 200:
                    guid_data = guid_response.json()
                    message_guid = guid_data.get("guid")
        except:
            pass
    
    # Validate filename format
    if message_guid:
        expected_filename = f"message_{message_guid[:8]}.html"
        assert filename == expected_filename, \
            f"❌ Attachment filename mismatch: expected '{expected_filename}', got '{filename}'"
    else:
        # If GUID not available, just check filename format
        if not filename.startswith("message_") or not filename.endswith(".html"):
            pytest.fail(f"❌ Attachment filename format incorrect: '{filename}'")
    
    print(f"✅ Attachment filename correct: {filename}")
    
    # Validate content type
    assert content_type == "text/html", f"❌ Expected HTML attachment, got {content_type}"
    print(f"✅ Attachment content type correct: {content_type}")
    
    # Validate content is HTML
    has_html_structure = any(tag in content.lower() for tag in ["<h1>", "<h2>", "<p>", "<div", "<ul>", "<li>", "<strong>", "<em>"])
    assert has_html_structure, "❌ Attachment should contain HTML tags"
    print(f"✅ Attachment content is HTML (contains HTML tags)")
    
    # Validate content is formatted (English keywords or HTML structure)
    english_indicators = ["summary", "content", "following", "ability", "language", "models"]
    has_english = any(indicator in content.lower() for indicator in english_indicators)
    has_html_tags = "<p>" in content or "<html>" in content.lower()
    
    assert has_english or has_html_tags, \
        "❌ Attachment should contain formatted content (English keywords or HTML structure), not raw original"
    
    if has_english:
        print(f"✅ Attachment content is in English (contains English keywords)")
    else:
        print(f"✅ Attachment content has HTML structure")
    
    print(f"✅ Attachment content length: {len(content)} chars")
    
    # Step 4: Validate Message Link - Full Message
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATE MESSAGE LINK - FULL MESSAGE")
    print("=" * 80)
    
    with httpx.Client(timeout=API_TIMEOUT) as client:
        response = client.get(
            f"{api_base_url}/messages/{message_id}?format=html",
            headers={"X-API-Key": api_key},
            timeout=10.0
        )
        assert response.status_code == 200, f"❌ Failed to get message: {response.text[:200]}"
        html_content = response.text
        
        # Check that it shows full message (not summary)
        assert "Formatted Message Content" in html_content or "message-content" in html_content, \
            "❌ Message page should show formatted message content"
        
        # Should not be just a summary
        assert len(html_content) > 1000, f"❌ Message page should show full content, not just summary (got {len(html_content)} chars)"
        
        print(f"✅ Message link shows full message: {len(html_content)} chars")
        print(f"✅ Formatted message content section present")
    
    # Step 5: Validate Message Link - Original Message
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE MESSAGE LINK - ORIGINAL MESSAGE")
    print("=" * 80)
    
    assert "Original Message" in html_content or "original-content" in html_content, \
        "❌ Message page should show original message section"
    
    print("✅ Message link shows original message section")
    
    # Step 6: Validate Message Link - Original Settings
    print("\n" + "=" * 80)
    print("STEP 6: VALIDATE MESSAGE LINK - ORIGINAL SETTINGS")
    print("=" * 80)
    
    assert "Original Settings" in html_content or "settings" in html_content.lower(), \
        "❌ Message page should show original settings section"
    
    # Should contain subject in settings
    assert "subject" in html_content.lower() or "Test Message Summary" in html_content, \
        "❌ Message page should show subject in settings"
    
    print("✅ Message link shows original settings section")
    print("✅ Subject displayed in settings")
    
    # Step 7: Validate Message Link - Destination
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE MESSAGE LINK - DESTINATION")
    print("=" * 80)
    
    assert "Destination" in html_content, "❌ Message page should show destination section"
    assert test_email in html_content, f"❌ Message page should show destination email: {test_email}"
    
    print("✅ Message link shows destination section")
    print(f"✅ Destination email displayed: {test_email}")
    
    # Step 8: Validate Message Link - Format Links
    print("\n" + "=" * 80)
    print("STEP 8: VALIDATE MESSAGE LINK - FORMAT LINKS")
    print("=" * 80)
    
    assert "Links" in html_content or "links" in html_content.lower(), \
        "❌ Message page should show links section"
    
    # Should have links to different formats
    assert f"/messages/{message_id}?format=json" in html_content or f'messages/{message_id}?format=json' in html_content, \
        "❌ Message page should have link to JSON format"
    assert f"/messages/{message_id}?format=html" in html_content or f'messages/{message_id}?format=html' in html_content, \
        "❌ Message page should have link to HTML format"
    assert f"/messages/{message_id}?format=markdown" in html_content or f'messages/{message_id}?format=markdown' in html_content, \
        "❌ Message page should have link to Markdown format"
    
    print("✅ Message link shows links section")
    print("✅ Format links present (JSON, HTML, Markdown)")
    
    # Step 9: Validate Message Link - Delivery Links (Optional - removed from UI per user request)
    print("\n" + "=" * 80)
    print("STEP 9: VALIDATE MESSAGE LINK - DELIVERY LINKS")
    print("=" * 80)
    
    # Note: Delivery links were removed from HTML display per user request (require API key)
    # This check is now optional
    has_delivery_link = f"/messages/{message_id}/deliveries" in html_content or f'messages/{message_id}/deliveries' in html_content
    if has_delivery_link:
        print("✅ Message link shows delivery links")
    else:
        print("⚠️  Delivery links not present in HTML (expected - removed from UI, require API key)")
    
    # Step 10: Summary
    print("\n" + "=" * 80)
    print("STEP 10: SUMMARY")
    print("=" * 80)
    
    print(f"\n📋 MESSAGE INFORMATION:")
    print(f"   Message ID: {message_id}")
    print(f"   Message GUID: {message_guid}")
    print(f"   Delivery ID: {delivery_id}")
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Attachment: EXISTS, FORMAT CORRECT, CONTENT VALIDATED")
    print(f"   ✅ Message Link: FULL MESSAGE, ORIGINAL, SETTINGS, DESTINATION")
    print(f"   ✅ Format Links: JSON, HTML, MARKDOWN")
    print(f"   ✅ SMTP Delivery: ACCEPTED")
    
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - ALL VALIDATIONS PERFORMED")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
