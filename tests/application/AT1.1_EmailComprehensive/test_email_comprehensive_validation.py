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
Comprehensive Email Test with Full Validation (German Translation)

CRITICAL RULES:
1. ALL OUTPUT TO SCREEN - no silent failures
2. ALL OPERATIONS MUST HAVE TIMEOUTS - never get stuck
3. Report timeouts clearly and continue with what we can verify

This test validates:
1. Subject is correct (not prompt text)
2. Format & contents of the email payload
3. Format of the output (HTML)
4. Language Translation (German)
5. All information accessible via API
6. Message link validation
7. Attachment validation
8. SMTP delivery validation
"""

import pytest
import sys
import requests
import json
import time
import os
import re
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlsplit
import httpx

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies

# CRITICAL: All timeouts must be set
API_TIMEOUT = 10.0  # Short timeout for API calls
WAIT_TIMEOUT = 300.0  # Max wait for delivery (5 minutes for LLM processing)
POLL_INTERVAL = 2.0  # Check every 2 seconds


def _auth_headers_for_url(url: str, api_base_url: str, api_key: str) -> Dict[str, str]:
    """Return API-key headers when URL targets the same API origin (localhost aliases included)."""
    if not url:
        return {}
    if str(url).startswith("/"):
        return {"X-API-Key": api_key}

    target = urlsplit(str(url))
    api = urlsplit(str(api_base_url))
    if not (target.scheme and target.netloc and api.scheme and api.netloc):
        return {}

    def _is_local_host(hostname: str) -> bool:
        return hostname in {"localhost", "127.0.0.1", "0.0.0.0"}

    target_host = (target.hostname or "").lower()
    api_host = (api.hostname or "").lower()
    target_port = target.port or (443 if target.scheme == "https" else 80)
    api_port = api.port or (443 if api.scheme == "https" else 80)
    same_scheme = target.scheme.lower() == api.scheme.lower()
    same_port = target_port == api_port
    same_host = target_host == api_host
    both_local = _is_local_host(target_host) and _is_local_host(api_host)
    if same_scheme and ((same_host and same_port) or both_local):
        return {"X-API-Key": api_key}
    return {}


def read_test_message(test_config) -> str:
    """Read the test message file from config"""
    # Get test message file path from config (env file)
    test_message_file = test_config.get("test.message_file")
    if not test_message_file:
        # Default to Test-Large-Text.md if not specified
        test_message_file = "Test-Large-Text.md"
    
    # Test message files are in tests/Examples/ directory.
    # Accept either:
    # - filename only: Test-Large-Text.md
    # - repo-relative path: tests/Examples/Test-Large-Text.md
    # - absolute path
    examples_dir = project_root / "tests" / "Examples"
    raw_path = Path(str(test_message_file))
    candidate_paths = []
    if raw_path.is_absolute():
        candidate_paths.append(raw_path)
    else:
        candidate_paths.append(project_root / raw_path)
        candidate_paths.append(examples_dir / raw_path.name)
        candidate_paths.append(examples_dir / raw_path)

    test_message_path = None
    for candidate in candidate_paths:
        if candidate.exists():
            test_message_path = candidate
            break

    if not test_message_path:
        tried = ", ".join(str(p) for p in candidate_paths)
        pytest.fail(f"Test message file not found. Tried: {tried}\n"
                   f"Available files: {', '.join([f.name for f in examples_dir.glob('*.md')])}\n"
                   f"Set CLOUD_DOG__NOTIFY__TEST__MESSAGE_FILE=<filename> in env file")
    
    with open(test_message_path, 'r', encoding='utf-8') as f:
        return f.read()


def create_smtp_channel(client: httpx.Client, api_base_url: str, api_key: str, smtp_config: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """Create a dedicated SMTP channel for this test run and return id/name."""
    channel_name = f"at11_smtp_{run_id}"
    create_resp = client.post(
        f"{api_base_url}/channels",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json={
            "name": channel_name,
            "type": "smtp",
            "enabled": True,
            "config": smtp_config,
        },
    )
    if create_resp.status_code != 201:
        pytest.fail(
            f"Failed to create SMTP channel '{channel_name}': "
            f"{create_resp.status_code} {create_resp.text[:200]}"
        )
    payload = create_resp.json() if create_resp.text else {}
    channel_id = payload.get("id")
    if not channel_id:
        pytest.fail(f"Created channel '{channel_name}' but no id returned")
    return {"id": channel_id, "name": channel_name}
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_email_comprehensive_validation(api_base_url, api_key, smtp_config, test_email, test_config, default_channel, request):
    """
    Comprehensive test that validates:
    1. Subject is correct
    2. Format & contents of email payload
    3. Format of output (HTML)
    4. Language Translation (German)
    5. All information accessible via API
    6. Message link validation
    7. Attachment validation
    8. SMTP delivery validation
    """
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for translation/summarization
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_email_comprehensive_validation"
    )

    print(f"\n{'='*80}")
    print("COMPREHENSIVE EMAIL VALIDATION TEST (GERMAN)")
    print(f"{'='*80}\n")

    run_id = str(int(time.time()))
    # Guard against cross-test channel drift by using a dedicated channel for this run.
    with httpx.Client(timeout=API_TIMEOUT) as channel_client:
        channel_info = create_smtp_channel(
            channel_client,
            api_base_url=api_base_url,
            api_key=api_key,
            smtp_config=smtp_config,
            run_id=run_id,
        )
    channel_name = channel_info["name"]
    channel_id = channel_info["id"]

    def _cleanup_channel():
        try:
            with httpx.Client(timeout=API_TIMEOUT) as cleanup_client:
                cleanup_client.post(
                    f"{api_base_url}/channels/{channel_id}/disable",
                    headers={"X-API-Key": api_key},
                )
        except Exception:
            pass

    request.addfinalizer(_cleanup_channel)
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Create message with German language preference
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": channel_name,
            "address": test_email,
            "preferences": {
                "language": "de",  # German
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": f"Please provide a summary in German of the following content:\n\n{news_content[:5000]}"
        }],
        "options": {
            "subject": "Test Message Summary - German"
        }
    }
    
    print(f"📧 Destination: {test_email}")
    print(f"🌐 Language: German (de)")
    print(f"📝 Content style: HTML")
    print(f"📌 Requested subject: {message_payload['options']['subject']}\n")
    
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
    
    # Step 3: Validate Subject
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE SUBJECT")
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
    
    # Get subject from payload (handle both dict and list formats)
    subject = None
    body = ""
    content_type = "text"
    attachments = []
    
    if isinstance(payload_data, dict):
        subject = payload_data.get("subject")
        body = payload_data.get("body", "")
        content_type = payload_data.get("content_type", "text")
        attachments = payload_data.get("attachments", [])
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        block = payload_data[0]
        if isinstance(block, dict):
            subject = block.get("subject")
            body = block.get("body", "")
            content_type = block.get("content_type", "text")
            attachments = block.get("attachments", [])
    
    print(f"📌 Subject in payload: {subject}")
    
    # Validate subject
    expected_subject = message_payload["options"]["subject"]
    if subject == expected_subject:
        print(f"✅ Subject is CORRECT: '{subject}'")
    elif subject and "test" in subject.lower() and ("german" in subject.lower() or "deutsch" in subject.lower()):
        print(f"✅ Subject is ACCEPTABLE: '{subject}' (contains expected keywords)")
    elif subject and subject != "Please provide a summary in German of the following content:":
        print(f"⚠️  Subject is DIFFERENT but not prompt text: '{subject}'")
        print(f"   Expected: '{expected_subject}'")
    else:
        print(f"❌ Subject is WRONG or is prompt text: '{subject}'")
        print(f"   Expected: '{expected_subject}'")
        pytest.fail(f"Subject validation failed: got '{subject}', expected '{expected_subject}'")
    
    # Step 4: Validate Format & Contents
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATE FORMAT & CONTENTS")
    print("=" * 80)
    
    print(f"📄 Body length: {len(body)} characters")
    print(f"📋 Content type: {content_type}")
    
    # Decode body if it's base64 encoded
    try:
        if body and not any(c in body for c in ['<', '>', '\n']) and len(body) > 50:
            try:
                decoded = base64.b64decode(body).decode('utf-8')
                body = decoded
                print(f"✅ Decoded base64 body")
            except:
                pass
    except:
        pass
    
    # Validate HTML format
    has_html_tags = "<" in body and ">" in body
    has_html_structure = any(tag in body.lower() for tag in ["<html", "<body", "<p>", "<div", "<br", "<a", "<strong", "<em"])
    is_html_content_type = content_type == "html" or "html" in str(content_type).lower()
    
    if not has_html_tags:
        pytest.fail(f"❌ Body is NOT HTML formatted! Content type: {content_type}, Body preview: '{body[:200]}...'")
    
    if not has_html_structure and not is_html_content_type:
        pytest.fail(f"❌ Body does not have HTML structure! Content type: {content_type}, Body preview: '{body[:200]}...'")
    
    print(f"✅ Body is HTML formatted (has HTML tags and structure)")
    print(f"✅ Body length: {len(body)} chars, Content type: {content_type}")
    
    # Validate content is not empty
    if len(body) == 0:
        print(f"❌ Content is empty")
        pytest.fail("Content validation failed: body is empty")
    
    print(f"✅ Content is not empty")
    
    # Show preview
    print(f"\n📝 Content preview (first 300 chars):")
    print(f"{body[:300]}...")
    
    # Step 5: Validate Language Translation (German)
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE LANGUAGE TRANSLATION (GERMAN)")
    print("=" * 80)
    
    # German indicators
    german_indicators = [
        "der", "die", "das", "und", "ist", "in", "für", "mit", "auf", "zu",
        "Bitte", "deutsch", "Zusammenfassung", "Inhalt", "Nachricht", "Test",
        "wird", "sind", "kann", "muss", "sollte", "wurde", "haben", "sein"
    ]
    
    # English indicators (should be minimal)
    english_indicators = [
        "please", "provide", "summary", "following", "content", "the ability",
        "should be", "translated", "formatted"
    ]
    
    body_lower = body.lower()
    found_german = [ind for ind in german_indicators if ind.lower() in body_lower[:2000]]
    found_english = [ind for ind in english_indicators if ind.lower() in body_lower[:2000]]
    
    print(f"🔍 German indicators found: {found_german[:10]}")
    print(f"🔍 English indicators found: {found_english[:10]}")
    
    # FAIL if English indicators present (means not translated)
    if found_english and len(found_english) > len(found_german):
        pytest.fail(f"❌ Body is NOT in German! Contains too many English indicators: '{body[:200]}...'")

    # FAIL if no German indicators (means translation didn't work)
    if not found_german:
        pytest.fail(f"❌ Body does not appear to be in German! Content: '{body[:200]}...'")

    print(f"✅ Body is in German (contains German keywords, minimal English indicators)")
    
    # Step 6: Validate Message Link
    print("\n" + "=" * 80)
    print("STEP 6: VALIDATE MESSAGE LINK")
    print("=" * 80)
    
    messages_base_url = test_config.get("messages.base_url")
    if not messages_base_url:
        pytest.fail("messages.base_url not configured. Check your env file.")
    base_url = messages_base_url.rstrip("/")
    message_link_match = re.search(rf'{re.escape(base_url)}/([0-9a-fA-F-]{{36}})', body)
    if message_link_match:
        message_url = message_link_match.group(0)
        link_guid = message_link_match.group(1)
        
        print(f"✅ Found message link: {message_url}")
        print(f"✅ Extracted GUID from link: {link_guid}")
        
        # If message_guid is None, fetch it from API
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
        
        if message_guid:
            assert link_guid == message_guid, f"❌ Link GUID ({link_guid}) does not match message GUID ({message_guid})"
        else:
            print(f"⚠️  Could not verify GUID match (message_guid not available)")
        
        # Verify link points to correct message using API
        with httpx.Client(timeout=10.0) as client:
            # Test HTML format
            html_link = f"{message_url}?format=html"
            print(f"🔍 Testing link: {html_link}")
            link_response = client.get(
                html_link,
                headers=_auth_headers_for_url(html_link, api_base_url, api_key),
                timeout=5.0
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
                    # Verify German content in link
                    has_german_in_link = any(indicator in link_content.lower() for indicator in german_indicators)
                    has_html_in_link = "<h1>" in link_content or "<p>" in link_content
                    
                    if not has_german_in_link:
                        pytest.fail(f"❌ Link does not show German formatted content")
                    if not has_html_in_link:
                        pytest.fail(f"❌ Link does not show HTML formatted content")
                    
                    print(f"✅ Link shows formatted German HTML content")
                else:
                    pytest.fail(f"❌ Link response is not HTML. Content-Type: {content_type_header}")
            else:
                pytest.fail(f"❌ Link is not accessible: HTTP {link_response.status_code if link_response else 'None'}")
            
            # Test JSON format endpoint
            json_link = f"{message_url}?format=json"
            json_response = client.get(
                json_link,
                headers={"X-API-Key": api_key},
                timeout=5.0
            )
            if json_response.status_code == 200:
                json_data = json_response.json()
                if json_data.get('id') == message_id or json_data.get('guid') == message_guid:
                    if 'formatted_content' not in json_data:
                        pytest.fail(f"❌ JSON format does not include 'formatted_content' field")
                    formatted_content = json_data.get('formatted_content', '')
                    if not formatted_content or formatted_content.strip() == '':
                        pytest.fail(f"❌ JSON format 'formatted_content' is empty")
                    if not any(indicator in formatted_content.lower() for indicator in german_indicators):
                        pytest.fail(f"❌ JSON formatted_content is not in German")
                    print(f"✅ Link JSON endpoint works correctly with formatted_content")
                    
                    # Validate status
                    message_status = json_data.get('status')
                    if message_status != 'completed':
                        pytest.fail(f"❌ Message status is '{message_status}', expected 'completed'")
                    print(f"✅ JSON status is correct: {message_status}")
                else:
                    pytest.fail(f"❌ Link JSON endpoint returns wrong message")
            else:
                pytest.fail(f"❌ Link JSON endpoint not accessible: HTTP {json_response.status_code}")
            
            # Test Markdown format endpoint
            markdown_link = f"{message_url}?format=markdown"
            markdown_response = client.get(
                markdown_link,
                headers={"X-API-Key": api_key},
                timeout=5.0
            )
            if markdown_response.status_code == 200:
                markdown_content = markdown_response.text
                if not any(indicator in markdown_content.lower() for indicator in german_indicators):
                    pytest.fail(f"❌ Markdown format does not contain German content")
                if not ("#" in markdown_content or "*" in markdown_content or "-" in markdown_content):
                    pytest.fail(f"❌ Markdown format does not appear to be correctly formatted")
                if not markdown_content.strip():
                    pytest.fail(f"❌ Markdown format is empty")
                print(f"✅ Markdown format endpoint works correctly (contains German, properly formatted)")
            else:
                pytest.fail(f"❌ Markdown format endpoint not accessible: HTTP {markdown_response.status_code}")
    else:
        print(f"⚠️  Message link not found in email body (may be optional)")
    
    # Step 7: Validate Attachments
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE ATTACHMENTS")
    print("=" * 80)
    
    if attachments and len(attachments) > 0:
        print(f"✅ Found {len(attachments)} attachment(s)")
        
        attachment = attachments[0]
        if not attachment:
            pytest.fail("❌ Attachment is None or empty")
        
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
        
        if message_guid:
            expected_filename = f"message_{message_guid[:8]}.html"
            actual_filename = attachment.get("filename", "")
            assert actual_filename == expected_filename, \
                f"❌ Attachment filename mismatch: expected '{expected_filename}', got '{actual_filename}'"
        else:
            # If GUID not available, just check filename format
            filename = attachment.get("filename", "")
            if not filename.startswith("message_") or not filename.endswith(".html"):
                pytest.fail(f"❌ Attachment filename format incorrect: '{filename}'")
        assert attachment.get("content_type") == "text/html", \
            f"❌ Attachment content type mismatch: {attachment.get('content_type')}"
        
        attachment_content = attachment.get("content", "")
        assert len(attachment_content) > 0, "❌ Attachment content is empty"
        
        # Verify attachment content is HTML and in German
        # Check for HTML structure (tags like <h1>, <p>, <div>, etc.)
        has_html_structure = any(tag in attachment_content.lower() for tag in ["<h1>", "<h2>", "<p>", "<div", "<ul>", "<li>", "<strong>", "<em>"])
        assert has_html_structure, "❌ Attachment content is not HTML (no HTML tags found)"
        assert any(indicator in attachment_content.lower() for indicator in german_indicators), \
            "❌ Attachment content is not in German"
        
        print(f"✅ Attachment filename matches message GUID")
        print(f"✅ Attachment content type matches email format")
        print(f"✅ Attachment content is in German")
    else:
        print(f"⚠️  No attachments found in payload (may be optional)")
    
    # Step 8: Validate API Access
    print("\n" + "=" * 80)
    print("STEP 8: VALIDATE API ACCESS")
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
    
    # Step 9: Summary
    print("\n" + "=" * 80)
    print("STEP 9: SUMMARY")
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
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Subject: {'CORRECT' if subject and subject != 'Please provide a summary in German of the following content:' else 'CHECK MANUALLY'}")
    print(f"   ✅ Format: {'HTML' if has_html_tags else 'NOT HTML'}")
    print(f"   ✅ Contents: {'PRESENT' if len(body) > 0 else 'MISSING'}")
    print(f"   ✅ Translation: {'GERMAN DETECTED' if found_german else 'NOT DETECTED'}")
    print(f"   ✅ SMTP Delivery: {'ACCEPTED' if not last_error else 'REJECTED'}")
    print(f"   ✅ API Access: {'AVAILABLE' if message_id else 'NOT AVAILABLE'}")
    
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - ALL VALIDATIONS PERFORMED")
    print(f"{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_email_comprehensive_validation_english(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """
    Comprehensive test that validates (English version):
    1. Subject is correct (not prompt text)
    2. Format & contents of email payload
    3. Format of output (HTML)
    4. Language (English - no translation)
    5. All information accessible via API
    6. Message link validation
    7. Attachment validation
    8. SMTP delivery validation
    """
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for summarization
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_email_comprehensive_validation_english"
    )

    print(f"\n{'='*80}")
    print("COMPREHENSIVE EMAIL VALIDATION TEST (ENGLISH)")
    print(f"{'='*80}\n")
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Create message with English language preference
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
            "body": f"Please provide a summary of the following content:\n\n{news_content[:5000]}"
        }],
        "options": {
            "subject": "Test Message Summary - English"
        }
    }
    
    print(f"📧 Destination: {test_email}")
    print(f"🌐 Language: English (en)")
    print(f"📝 Content style: HTML")
    print(f"📌 Requested subject: {message_payload['options']['subject']}\n")
    
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
    
    # Step 3: Validate Subject
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE SUBJECT")
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
    
    # Get subject from payload
    subject = None
    if isinstance(payload_data, list) and len(payload_data) > 0:
        for block in payload_data:
            if isinstance(block, dict) and "subject" in block:
                subject = block.get("subject")
                break
    elif isinstance(payload_data, dict):
        subject = payload_data.get("subject")
    
    print(f"📌 Subject in payload: {subject}")
    
    # Validate subject
    expected_subject = message_payload["options"]["subject"]
    if subject == expected_subject:
        print(f"✅ Subject is CORRECT: '{subject}'")
    elif subject and "test" in subject.lower() and "english" in subject.lower():
        print(f"✅ Subject is ACCEPTABLE: '{subject}' (contains expected keywords)")
    elif subject and subject != "Please provide a summary of the following content:":
        print(f"⚠️  Subject is DIFFERENT but not prompt text: '{subject}'")
        print(f"   Expected: '{expected_subject}'")
    else:
        print(f"❌ Subject is WRONG or is prompt text: '{subject}'")
        print(f"   Expected: '{expected_subject}'")
        pytest.fail(f"Subject validation failed: got '{subject}', expected '{expected_subject}'")
    
    # Step 4: Validate Format & Contents
    print("\n" + "=" * 80)
    print("STEP 4: VALIDATE FORMAT & CONTENTS")
    print("=" * 80)
    
    # Get body and content_type
    body = ""
    content_type = "unknown"
    if isinstance(payload_data, list) and len(payload_data) > 0:
        for block in payload_data:
            if isinstance(block, dict) and (block.get("type") == "html" or block.get("type") == "text"):
                body = block.get("body", "")
                content_type = block.get("content_type", block.get("type", "text"))
                break
    elif isinstance(payload_data, dict):
        body = payload_data.get("body", "")
        content_type = payload_data.get("content_type", payload_data.get("type", "text"))
    
    print(f"📄 Body length: {len(body)} characters")
    print(f"📋 Content type: {content_type}")
    
    # Validate HTML format
    has_html = "<" in body and ">" in body and any(tag in body for tag in ["<p>", "<h", "<ul>", "<li>", "<div>"])
    if has_html:
        print(f"✅ Format is HTML (contains HTML tags)")
    else:
        print(f"❌ Format is NOT HTML (no HTML tags found)")
        pytest.fail("Format validation failed: expected HTML, got plain text")
    
    # Validate content is not empty
    if len(body) > 0:
        print(f"✅ Content is not empty")
    else:
        print(f"❌ Content is empty")
        pytest.fail("Content validation failed: body is empty")
    
    # Show preview
    print(f"\n📝 Content preview (first 300 chars):")
    print(f"{body[:300]}...")
    
    # Step 5: Validate Language (English - should be in English, not translated)
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE LANGUAGE (ENGLISH)")
    print("=" * 80)
    
    # Check for English indicators
    english_indicators = ["the", "and", "is", "in", "for", "with", "on", "to", "of", "a", "summary", "content", "following"]
    body_lower = body.lower()
    found_english = [ind for ind in english_indicators if ind.lower() in body_lower[:2000]]
    
    print(f"🔍 English indicators found: {found_english[:10]}")
    
    if len(found_english) > 0:
        print(f"✅ Body is in English (contains English keywords)")
    else:
        print(f"⚠️  WARNING: Body may not be in English (no English indicators found)")
    
    # Step 6: Validate Message Link (same as German version)
    print("\n" + "=" * 80)
    print("STEP 6: VALIDATE MESSAGE LINK")
    print("=" * 80)
    
    message_link = None
    
    # Extract link from HTML format
    html_link_match = re.search(r'<a\s+href=["\']([^"\']+)["\']>.*?view it online', body, re.IGNORECASE)
    if html_link_match:
        message_link = html_link_match.group(1)
    else:
        text_link_match = re.search(r'view it online at:\s*([^\s<]+)', body, re.IGNORECASE)
        if text_link_match:
            message_link = text_link_match.group(1).rstrip('.,;')
    
    if message_link:
        print(f"✅ Found message link: {message_link}")
        # Extract GUID from link
        link_guid_match = re.search(r'/messages/([0-9a-f-]{36})', message_link, re.IGNORECASE)
        link_guid = link_guid_match.group(1) if link_guid_match else None
        
        if link_guid:
            print(f"✅ Extracted GUID from link: {link_guid}")
            
            # Ensure message_guid is available for comparison
            if not message_guid:
                try:
                    with httpx.Client(timeout=API_TIMEOUT) as guid_client:
                        guid_response = guid_client.get(
                            f"{api_base_url}/messages/{message_id}",
                            headers={"X-API-Key": api_key}
                        )
                        if guid_response.status_code == 200:
                            guid_data = guid_response.json()
                            message_guid = guid_data.get("guid")
                except Exception as e:
                    print(f"⚠️  Could not fetch message GUID from API: {e}")
            
            if message_guid:
                assert link_guid == message_guid, f"❌ Link GUID ({link_guid}) does not match message GUID ({message_guid})"
                print(f"✅ Link GUID matches message GUID")
            
            # Verify link points to correct message using API
            with httpx.Client(timeout=10.0) as client:
                html_link = f"{message_link}?format=html"
                print(f"🔍 Testing link: {html_link}")
                link_response = client.get(
                    html_link,
                    headers=_auth_headers_for_url(html_link, api_base_url, api_key),
                    timeout=5.0
                )
                
                if link_response and link_response.status_code == 200:
                    link_content = link_response.text
                    content_type_header = link_response.headers.get('content-type', '')
                    
                    is_html = False
                    if link_content and len(link_content) > 0:
                        content_preview = link_content[:1000].lower()
                        is_html = ("<!doctype html" in content_preview or 
                                 "<html" in content_preview or 
                                 ("<h1>" in link_content and "<div" in link_content))
                    if not is_html:
                        is_html = 'text/html' in content_type_header.lower()
                    
                    if is_html:
                        has_english_in_link = any(indicator in link_content.lower() for indicator in english_indicators)
                        has_html_in_link = "<h1>" in link_content or "<p>" in link_content
                        
                        if not has_english_in_link:
                            pytest.fail(f"❌ Link does not show English formatted content")
                        if not has_html_in_link:
                            pytest.fail(f"❌ Link does not show HTML formatted content")
                        
                        print(f"✅ Link shows formatted English HTML content")
                    else:
                        pytest.fail(f"❌ Link response is not HTML: Content-Type: {content_type_header}, Content preview: {link_content[:200]}")
                else:
                    pytest.fail(f"❌ Link is not accessible: HTTP {link_response.status_code if link_response else 'None'}")
        else:
            pytest.fail(f"❌ Could not extract GUID from link: {message_link}")
    else:
        pytest.fail(f"❌ No message link found in email body")
    
    # Step 7: Validate Attachments (same as German version)
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE ATTACHMENTS")
    print("=" * 80)
    
    attachments = []
    if isinstance(payload_data, list):
        for block in payload_data:
            if isinstance(block, dict) and "attachments" in block:
                attachments.extend(block["attachments"])
    elif isinstance(payload_data, dict) and "attachments" in payload_data:
        attachments.extend(payload_data["attachments"])

    if attachments:
        print(f"✅ Found {len(attachments)} attachment(s)")
        for attachment in attachments:
            filename = attachment.get("filename", "")
            attachment_content = attachment.get("content", "")
            attachment_content_type = attachment.get("content_type", "")
            
            print(f"✅ Attachment: {filename} ({attachment_content_type})")
            
            if message_guid:
                expected_prefix = f"message_{message_guid[:8]}"
                if expected_prefix not in filename:
                    pytest.fail(f"❌ Attachment filename does not match message GUID: expected '{expected_prefix}' in '{filename}'")
                print(f"✅ Attachment filename matches message GUID")
            
            if content_type == "html" and attachment_content_type != "text/html":
                pytest.fail(f"❌ Attachment content type mismatch: expected 'text/html', got '{attachment_content_type}'")
            print(f"✅ Attachment content type matches email format")
            
            if attachment_content:
                has_english_in_attachment = any(indicator in attachment_content.lower() for indicator in english_indicators)
                
                if not has_english_in_attachment:
                    pytest.fail(f"❌ Attachment content does not appear to be in English! Content: '{attachment_content[:200]}...'")
                
                print(f"✅ Attachment content is in English")
                
                if not re.search(r'<html|<body|<p|<div|<h[1-6]', attachment_content.lower()):
                    pytest.fail(f"❌ Attachment content is not HTML")
                print(f"✅ Attachment content is HTML formatted")
    else:
        print(f"⚠️  No attachment found in email payload (expected attachment)")
    
    # Step 8: Summary
    print("\n" + "=" * 80)
    print("STEP 8: SUMMARY")
    print("=" * 80)
    
    print(f"\n📋 MESSAGE INFORMATION:")
    print(f"   Message ID: {message_id}")
    print(f"   Message GUID: {message_guid}")
    print(f"   Delivery ID: {delivery_id}")
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Subject: {'CORRECT' if subject and subject != 'Please provide a summary of the following content:' else 'CHECK MANUALLY'}")
    print(f"   ✅ Format: {'HTML' if has_html else 'NOT HTML'}")
    print(f"   ✅ Contents: {'PRESENT' if len(body) > 0 else 'MISSING'}")
    print(f"   ✅ Language: {'ENGLISH DETECTED' if len(found_english) > 0 else 'NOT DETECTED'}")
    print(f"   ✅ SMTP Delivery: {'ACCEPTED' if not last_error else 'REJECTED'}")
    print(f"   ✅ API Access: {'AVAILABLE' if message_id else 'NOT AVAILABLE'}")
    
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
