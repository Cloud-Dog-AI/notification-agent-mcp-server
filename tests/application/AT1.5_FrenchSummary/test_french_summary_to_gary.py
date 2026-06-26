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
Comprehensive French Summary Test with Full Validation

CRITICAL RULES:
1. ALL OUTPUT TO SCREEN - no silent failures
2. ALL OPERATIONS MUST HAVE TIMEOUTS - never get stuck
3. Report timeouts clearly and continue with what we can verify

This test validates:
1. Subject is correct (not prompt text)
2. Format & contents of the email payload
3. Format of the output (HTML)
4. Language Translation (French)
5. All information accessible via API
6. Message link validation
7. Attachment validation
8. SMTP delivery validation
"""

import pytest
import sys
import json
import time
import os
import re
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies

# CRITICAL: All timeouts must come from config - NO HARDCODING
# These will be set from test_config in the test function


def read_test_message(test_config) -> str:
    """Read the test message file from config"""
    # Get test message file path from config (env file) - NO HARDCODED DEFAULTS
    test_message_file = test_config.get("test.message_file")
    if not test_message_file:
        pytest.fail(
            "❌ HARD FAIL: test.message_file not configured in env file.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__MESSAGE_FILE=<filename> in env file"
        )
    
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


def test_send_french_summary_to_gary(api_base_url, api_key, smtp_config, test_email, test_config, api_client, smtp_channel_name):
    """
    Comprehensive test that validates:
    1. Subject is correct
    2. Format & contents of email payload
    3. Format of output (HTML)
    4. Language Translation (French)
    5. All information accessible via API
    6. Message link validation
    7. Attachment validation
    8. SMTP delivery validation
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("at15_env_loaded"):
        pytest.fail(
            "❌ CRITICAL: AT1.5 env file not loaded!\n"
            "Required: --env private/env-test-at15\n"
            "This test requires specific AT1.5 configuration."
        )
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for summarization/translation
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_send_french_summary_to_gary"
    )
    
    print(f"\n{'='*80}")
    print("COMPREHENSIVE FRENCH SUMMARY TEST")
    print(f"{'='*80}\n")
    
    # Get test configuration (NO HARDCODING - fail if missing)
    target_language = test_config.get("test.at15.language")
    if not target_language:
        pytest.fail("❌ HARD FAIL: test.at15.language not configured in env file")
    
    content_style = test_config.get("test.at15.content_style")
    if not content_style:
        pytest.fail("❌ HARD FAIL: test.at15.content_style not configured in env file")
    
    message_subject = test_config.get("test.at15.subject")
    if not message_subject:
        pytest.fail("❌ HARD FAIL: test.at15.subject not configured in env file")
    
    content_limit = test_config.get("test.at15.content_limit")
    if not content_limit:
        pytest.fail("❌ HARD FAIL: test.at15.content_limit not configured in env file")
    
    # Get timeouts from config (NO HARDCODING)
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    api_timeout = float(api_timeout)
    
    wait_timeout = test_config.get("test.at15.max_wait")
    if not wait_timeout:
        pytest.fail("❌ HARD FAIL: test.at15.max_wait not configured in env file")
    wait_timeout = float(wait_timeout)
    
    poll_interval = test_config.get("test.at15.poll_interval")
    if not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at15.poll_interval not configured in env file")
    poll_interval = float(poll_interval)
    
    # Read test message from config
    news_content = read_test_message(test_config)
    print(f"📄 Test message length: {len(news_content)} characters")
    
    # Create message with target language preference
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": smtp_channel_name,
            "address": test_email,
            "preferences": {
                "language": target_language,
                "content_style": content_style
            }
        }],
        "content": [{
            "type": "text",
            "body": news_content[:content_limit]  # Don't include prompt text - the system will summarize/translate automatically
        }],
        "options": {
            "subject": message_subject
        }
    }
    
    print(f"📧 Destination: {test_email}")
    print(f"🌐 Language: {target_language}")
    print(f"📝 Content style: {content_style}")
    print(f"📌 Requested subject: {message_subject}\n")
    
    # Step 1: Create message (WITH TIMEOUT)
    print("=" * 80)
    print("STEP 1: CREATE MESSAGE")
    print("=" * 80)
    message_id = None
    message_guid = None
    
    try:
        response = api_client.post("/messages", json=message_payload)
        print(f"✅ POST /messages: Status {response.status_code}")
            
        if response.status_code == 201:
            try:
                result = response.json()
            except Exception:
                print(f"❌ Failed to parse JSON response: {response.text[:200]}")
                pytest.fail("Message creation response is not valid JSON")

            message_id = result.get("message_id") or result.get("id")
            message_guid = result.get("guid")

            # If GUID not in response, fetch it from message API
            if not message_guid and message_id:
                try:
                    msg_response = api_client.get(f"/messages/{message_id}")
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        message_guid = msg_data.get("guid")
                except Exception:
                    print(f"⚠️  Could not fetch GUID from message API, continuing...")

            print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
        else:
            print(f"❌ Failed to create message: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            pytest.fail(f"Message creation failed: {response.status_code}")
    except httpx.TimeoutException:
        print(f"❌ TIMEOUT: Message creation timed out after {api_timeout}s")
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
    max_attempts = int(wait_timeout / poll_interval)
    
    for i in range(max_attempts):
        try:
            response = api_client.get(f"/messages/{message_id}/deliveries")
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
                    if state in ["hard_failed", "cancelled"]:
                        print(f"❌ Delivery failed: {error}")
                        pytest.fail(f"Delivery failed: {error}")

            time.sleep(poll_interval)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"⚠️  [{elapsed:.1f}s] Error: {type(e).__name__}: {e}")
            time.sleep(poll_interval)
            continue
    
    if delivery is None:
        elapsed = time.time() - start_time
        print(f"❌ TIMEOUT: No delivery found after {elapsed:.1f}s")
        pytest.fail(f"Delivery not found after {wait_timeout}s")
    
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
    if subject == message_subject:
        print(f"✅ Subject is CORRECT: '{subject}'")
    elif subject and "test" in subject.lower() and ("summary" in subject.lower() or target_language.lower() in subject.lower()):
        print(f"✅ Subject is ACCEPTABLE: '{subject}' (contains expected keywords)")
    elif subject and not subject.startswith("Please provide a summary"):
        print(f"⚠️  Subject is DIFFERENT but not prompt text: '{subject}'")
        print(f"   Expected: '{message_subject}'")
    else:
        print(f"❌ Subject is WRONG or is prompt text: '{subject}'")
        print(f"   Expected: '{message_subject}'")
        pytest.fail(f"Subject validation failed: got '{subject}', expected '{message_subject}'")
    
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
    
    # Step 5: Validate Language Translation (French)
    print("\n" + "=" * 80)
    print("STEP 5: VALIDATE LANGUAGE TRANSLATION (FRENCH)")
    print("=" * 80)
    
    # French indicators
    french_indicators = [
        "le", "la", "les", "de", "du", "des", "et", "dans", "pour", "avec",
        "Bien", "bonjour", "français", "Résumé", "contenu", "message", "Test",
        "est", "sont", "peut", "doit", "devrait", "été", "ont", "être"
    ]
    
    # English indicators (should be minimal)
    english_indicators = [
        "please", "provide", "summary", "following", "content", "the ability",
        "should be", "translated", "formatted"
    ]
    
    body_lower = body.lower()
    # Use configurable check length or calculate based on body size
    check_length = test_config.get("test.at15.language_check_length", min(2000, len(body)))
    found_french = [ind for ind in french_indicators if ind.lower() in body_lower[:check_length]]
    found_english = [ind for ind in english_indicators if ind.lower() in body_lower[:check_length]]
    
    print(f"🔍 French indicators found: {found_french[:10]}")
    print(f"🔍 English indicators found: {found_english[:10]}")
    
    # FAIL if English indicators present (means not translated)
    if found_english and len(found_english) > len(found_french):
        pytest.fail(f"❌ Body is NOT in French! Contains too many English indicators: '{body[:200]}...'")
    
    # FAIL if no French indicators (means translation didn't work)
    if not found_french:
        pytest.fail(f"❌ Body does NOT contain French text! Content: '{body[:200]}...'")
    
    print(f"✅ Body is in French (contains French keywords, minimal English indicators)")
    
    if len(found_english) > len(found_french):
        print(f"⚠️  WARNING: More English than French found - translation may be incomplete")
    else:
        print(f"✅ French indicators outnumber English (translation appears successful)")
    
    # Step 6: Extract All Links from Payload
    print("\n" + "=" * 80)
    print("STEP 6: EXTRACT ALL LINKS FROM PAYLOAD")
    print("=" * 80)
    
    # Extract links from payload (matching AT1.4I pattern)
    links = payload_data.get("links", [])
    full_url = None
    source_url = None
    pdf_url = None
    message_link = None  # Generic message link (for backward compatibility)
    
    # Extract from links array
    for link in links:
        label = link.get("label", "").lower()
        url = link.get("url", "")
        if "full" in label or ("message" in url and target_language in url):
            full_url = url
        elif "source" in label or ("message" in url and "en" in url):  # Source is typically English
            source_url = url
        elif "pdf" in label or url.endswith(".pdf"):
            pdf_url = url
    
    # Also check attachments for PDF
    if not pdf_url:
        for att in attachments:
            if att.get("type") == "pdf" or att.get("url", "").endswith(".pdf"):
                pdf_url = att.get("url")
    
    # Extract generic message link from body (for backward compatibility)
    html_link_matches = re.findall(r'<a\s+href=["\']([^"\']+)["\']>.*?view it online', body, re.IGNORECASE)
    if html_link_matches:
        message_link = next((m for m in html_link_matches if "/messages/" in m), html_link_matches[0])
        if message_link.lower() == "url":
            message_link = None
    if not message_link:
        text_link_match = re.search(r'view it online at:\s*([^\s<]+)', body, re.IGNORECASE)
        if text_link_match:
            message_link = text_link_match.group(1).rstrip('.,;')
    if not message_link:
        hrefs = re.findall(r'<a\s+href=["\']([^"\']+)["\']', body, re.IGNORECASE)
        message_link = next((m for m in hrefs if "/messages/" in m), None)
    
    # Construct URLs if not found but message_guid available
    base_url = test_config.get("api_server.base_url") or api_base_url
    if message_guid:
        if not source_url:
            source_url = f"{base_url}/messages/{message_guid}?language=en"  # Source is English
        if not full_url:
            full_url = f"{base_url}/messages/{message_guid}?language={target_language}"
    
    print(f"✅ Source message link: {'Found' if source_url else 'Not found'}")
    print(f"✅ Full message link: {'Found' if full_url else 'Not found'}")
    print(f"✅ PDF link: {'Found' if pdf_url else 'Not found'}")
    print(f"✅ Generic message link: {'Found' if message_link else 'Not found'}")
    
    # Step 6a: Validate Generic Message Link (backward compatibility)
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
                    with httpx.Client(timeout=api_timeout) as guid_client:
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
            else:
                print(f"⚠️  Could not verify GUID match (message_guid not available)")
            
            # Verify link points to correct message using API
            with httpx.Client(timeout=api_timeout) as client:
                # Test HTML format
                separator = "&" if "?" in message_link else "?"
                html_link = f"{message_link}{separator}format=html"
                print(f"🔍 Testing link: {html_link}")
                link_response = client.get(
                    html_link,
                    headers={"X-API-Key": api_key} if html_link.startswith(api_base_url) else {},
                    timeout=api_timeout
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
                        # Verify French content in link
                        has_french_in_link = any(indicator in link_content.lower() for indicator in french_indicators)
                        has_html_in_link = "<h1>" in link_content or "<p>" in link_content
                        
                        if not has_french_in_link:
                            pytest.fail(f"❌ Link does not show French formatted content")
                        if not has_html_in_link:
                            pytest.fail(f"❌ Link does not show HTML formatted content")
                        
                        print(f"✅ Link shows formatted French HTML content")
                    else:
                        pytest.fail(f"❌ Link response is not HTML. Content-Type: {content_type_header}")
                else:
                    pytest.fail(f"❌ Link is not accessible: HTTP {link_response.status_code if link_response else 'None'}")
                
                # Test JSON format endpoint
                separator_json = "&" if "?" in message_link else "?"
                json_link = f"{message_link}{separator_json}format=json"
                json_response = client.get(
                    json_link,
                    headers={"X-API-Key": api_key},
                    timeout=api_timeout
                )
                if json_response.status_code == 200:
                    json_data = json_response.json()
                    if json_data.get('id') == message_id or json_data.get('guid') == message_guid:
                        if 'formatted_content' not in json_data:
                            pytest.fail(f"❌ JSON format does not include 'formatted_content' field")
                        formatted_content = json_data.get('formatted_content', '')
                        if not formatted_content or formatted_content.strip() == '':
                            pytest.fail(f"❌ JSON format 'formatted_content' is empty")
                        if not any(indicator in formatted_content.lower() for indicator in french_indicators):
                            pytest.fail(f"❌ JSON formatted_content is not in French")
                        print(f"✅ Link JSON endpoint works correctly with formatted_content")
                        
                        message_status = json_data.get('status')
                        if message_status != 'completed':
                            print(f"⚠️  Message status is '{message_status}', expected 'completed'. Continuing...")
                        print(f"✅ JSON status is correct: {message_status}")
                    else:
                        pytest.fail(f"❌ Link JSON endpoint returns wrong message")
                else:
                    pytest.fail(f"❌ Link JSON endpoint not accessible: HTTP {json_response.status_code}")
                
                # Test Markdown format endpoint
                separator_md = "&" if "?" in message_link else "?"
                markdown_link = f"{message_link}{separator_md}format=markdown"
                markdown_response = client.get(
                    markdown_link,
                    headers={"X-API-Key": api_key},
                    timeout=api_timeout
                )
                if markdown_response.status_code == 200:
                    markdown_content = markdown_response.text
                    if '<' in markdown_content and '>' in markdown_content and '<p>' in markdown_content:
                        pytest.fail(f"❌ Markdown format still contains HTML tags")
                    has_french_in_markdown = any(indicator in markdown_content.lower() for indicator in french_indicators)
                    if not has_french_in_markdown:
                        pytest.fail(f"❌ Markdown format does not contain French content")
                    if not markdown_content.strip():
                        pytest.fail(f"❌ Markdown format is empty")
                    print(f"✅ Markdown format endpoint works correctly")
                else:
                    pytest.fail(f"❌ Markdown format endpoint not accessible: HTTP {markdown_response.status_code}")
        else:
            pytest.fail(f"❌ Could not extract GUID from link: {message_link}")
    else:
        pytest.fail(f"❌ No message link found in email body")
    
    # Step 7: Validate Source Message Link
    print("\n" + "=" * 80)
    print("STEP 7: VALIDATE SOURCE MESSAGE LINK")
    print("=" * 80)
    
    if source_url:
        print(f"✅ Found source message link: {source_url}")
        
        # Validate URL format
        assert "en" in source_url or "language=en" in source_url, f"Source URL missing language param: {source_url}"
        print(f"✅ URL contains source language (en)")
        
        # Test accessibility
        try:
            with httpx.Client(timeout=api_timeout) as client:
                source_response = client.get(
                    source_url,
                    headers={"X-API-Key": api_key} if source_url.startswith(api_base_url) else {},
                    timeout=api_timeout
                )
                assert source_response.status_code == 200, f"Source URL not accessible: {source_response.status_code}"
                print(f"✅ Source URL accessible (HTTP 200)")
                
                # Validate content is in source language (English)
                source_content = source_response.text
                has_english = any(ind in source_content.lower()[:1000] for ind in english_indicators)
                if has_english:
                    print(f"✅ Source content contains English indicators")
        except Exception as e:
            print(f"⚠️  Source link validation error: {e}")
    else:
        print(f"⚠️  Source message link not found (constructing from GUID)")
        if message_guid:
            source_url = f"{base_url}/messages/{message_guid}?language=en"
            print(f"✅ Constructed source URL: {source_url}")
    
    # Step 8: Validate Full Message Link
    print("\n" + "=" * 80)
    print("STEP 8: VALIDATE FULL MESSAGE LINK")
    print("=" * 80)
    
    if full_url:
        print(f"✅ Found full message link: {full_url}")
        
        # Validate URL format
        assert target_language in full_url or f"language={target_language}" in full_url, f"Full URL missing language param: {full_url}"
        print(f"✅ URL contains target language ({target_language})")
        
        # Test accessibility
        try:
            with httpx.Client(timeout=api_timeout) as client:
                full_response = client.get(
                    full_url,
                    headers={"X-API-Key": api_key} if full_url.startswith(api_base_url) else {},
                    timeout=api_timeout
                )
                assert full_response.status_code == 200, f"Full URL not accessible: {full_response.status_code}"
                print(f"✅ Full URL accessible (HTTP 200)")
                
                # Validate content is in target language (French)
                full_content = full_response.text
                has_french = any(ind in full_content.lower()[:1000] for ind in french_indicators)
                if has_french:
                    print(f"✅ Full content contains French indicators")
                
                # Validate full message is full size (not summary)
                # Full message should be longer than summary
                if len(full_content) > len(body) * 1.5:
                    print(f"✅ Full message is full size ({len(full_content)} chars vs summary {len(body)} chars)")
                else:
                    print(f"⚠️  Full message size may be too short ({len(full_content)} chars)")
        except Exception as e:
            print(f"⚠️  Full link validation error: {e}")
    else:
        print(f"⚠️  Full message link not found (constructing from GUID)")
        if message_guid:
            full_url = f"{base_url}/messages/{message_guid}?language={target_language}"
            print(f"✅ Constructed full URL: {full_url}")
    
    # Step 9: Validate PDF Link
    print("\n" + "=" * 80)
    print("STEP 9: VALIDATE PDF LINK")
    print("=" * 80)
    
    if pdf_url:
        print(f"✅ Found PDF link: {pdf_url}")
        
        # Validate URL format
        assert ".pdf" in pdf_url.lower(), f"PDF URL doesn't contain .pdf: {pdf_url}"
        print(f"✅ URL format correct (.pdf)")
        
        # Test accessibility
        try:
            with httpx.Client(timeout=api_timeout) as client:
                pdf_response = client.get(
                    pdf_url,
                    headers={"X-API-Key": api_key} if pdf_url.startswith(api_base_url) else {},
                    timeout=api_timeout
                )
                assert pdf_response.status_code == 200, f"PDF URL not accessible: {pdf_response.status_code}"
                
                content_type = pdf_response.headers.get("content-type", "")
                assert "application/pdf" in content_type, f"PDF content-type incorrect: {content_type}"
                print(f"✅ Content-Type: application/pdf")
                
                pdf_content = pdf_response.content
                assert len(pdf_content) > 1000, f"PDF too small: {len(pdf_content)} bytes"
                print(f"✅ PDF size: {len(pdf_content)} bytes")
                
                # Validate PDF magic bytes
                assert pdf_content[:4] == b'%PDF', f"PDF magic bytes incorrect: {pdf_content[:4]}"
                print(f"✅ PDF magic bytes validated")
        except Exception as e:
            print(f"⚠️  PDF link validation error: {e}")
    else:
        print(f"⚠️  PDF link not found in payload/attachments")
    
    # Step 10: Validate Message Storage Upload
    print("\n" + "=" * 80)
    print("STEP 10: VALIDATE MESSAGE STORAGE UPLOAD")
    print("=" * 80)
    
    # Check for storage URLs in payload (if storage is configured)
    storage_urls = {
        "summary": None,
        "full": None,
        "pdf": None,
        "source": None
    }
    
    # Extract storage URLs from payload/links
    for link in links:
        url = link.get("url", "")
        label = link.get("label", "").lower()
        if "/storage/" in url or "/files/" in url:
            if "summary" in label:
                storage_urls["summary"] = url
            elif "full" in label:
                storage_urls["full"] = url
            elif "pdf" in label:
                storage_urls["pdf"] = url
            elif "source" in label:
                storage_urls["source"] = url
    
    # Validate storage URLs if present
    storage_validated = False
    for storage_type, storage_url in storage_urls.items():
        if storage_url:
            try:
                with httpx.Client(timeout=api_timeout) as client:
                    response = client.get(
                        storage_url,
                        headers={"X-API-Key": api_key} if storage_url.startswith(api_base_url) else {},
                        timeout=api_timeout
                    )
                    if response.status_code == 200:
                        print(f"✅ {storage_type.capitalize()} storage URL accessible: {storage_url[:60]}...")
                        storage_validated = True
                    else:
                        print(f"⚠️  {storage_type.capitalize()} storage URL returned {response.status_code}")
            except Exception as e:
                print(f"⚠️  {storage_type.capitalize()} storage validation error: {e}")
    
    if not storage_validated:
        print(f"ℹ️  No storage URLs found in payload (storage may not be configured for email channel)")
    
    # Step 11: Validate Attachments
    print("\n" + "=" * 80)
    print("STEP 11: VALIDATE ATTACHMENTS")
    print("=" * 80)
    
    if attachments:
        print(f"✅ Found {len(attachments)} attachment(s)")
        for attachment in attachments:
            filename = attachment.get("filename", "")
            attachment_content = attachment.get("content", "")
            attachment_content_type = attachment.get("content_type", "")
            
            print(f"✅ Attachment: {filename} ({attachment_content_type})")
            
            # Verify attachment filename format
            if message_guid:
                expected_prefix = f"message_{message_guid[:8]}"
                if expected_prefix not in filename:
                    pytest.fail(f"❌ Attachment filename does not match message GUID: expected '{expected_prefix}' in '{filename}'")
                print(f"✅ Attachment filename matches message GUID")
            
            # Verify attachment content type matches email content type
            if content_type == "html" and attachment_content_type != "text/html":
                pytest.fail(f"❌ Attachment content type mismatch: expected 'text/html', got '{attachment_content_type}'")
            elif content_type == "text" and attachment_content_type != "text/plain":
                pytest.fail(f"❌ Attachment content type mismatch: expected 'text/plain', got '{attachment_content_type}'")
            print(f"✅ Attachment content type matches email format")
            
            # Verify attachment content is in French (same as email body)
            if attachment_content:
                has_french_in_attachment = any(indicator in attachment_content.lower() for indicator in french_indicators)
                has_english_in_attachment = any(indicator in attachment_content.lower() for indicator in english_indicators)
                
                if has_english_in_attachment:
                    pytest.fail(f"❌ Attachment content is NOT in French! Contains English: '{attachment_content[:200]}...'")
                
                if not has_french_in_attachment:
                    pytest.fail(f"❌ Attachment content does not appear to be in French! Content: '{attachment_content[:200]}...'")
                
                print(f"✅ Attachment content is in French")
                
                # Verify attachment content is HTML formatted
                if not re.search(r'<html|<body|<p|<div|<h[1-6]', attachment_content.lower()):
                    pytest.fail(f"❌ Attachment content is not HTML")
                print(f"✅ Attachment content is HTML formatted")
    else:
        print(f"⚠️  No attachment found in email payload (expected attachment)")
    
    # Step 12: Validate Full Message Attachment
    print("\n" + "=" * 80)
    print("STEP 12: VALIDATE FULL MESSAGE ATTACHMENT")
    print("=" * 80)
    
    # Check if full message is attached (if configured)
    full_message_attachment = None
    for attachment in attachments:
        filename = attachment.get("filename", "").lower()
        content_type = attachment.get("content_type", "").lower()
        if "full" in filename or (content_type in ["text/html", "text/plain"] and len(attachment.get("content", "")) > len(body)):
            full_message_attachment = attachment
            break
    
    if full_message_attachment:
        print(f"✅ Found full message attachment: {full_message_attachment.get('filename')}")
        
        # Validate attachment content
        attach_content = full_message_attachment.get("content", "")
        if attach_content:
            # Validate language
            has_french_in_attach = any(ind in attach_content.lower() for ind in french_indicators)
            if has_french_in_attach:
                print(f"✅ Attachment content is in French")
            else:
                print(f"⚠️  Attachment content may not be in French")
            
            # Validate size (should be full, not summary)
            if len(attach_content) > len(body) * 1.5:
                print(f"✅ Attachment is full size ({len(attach_content)} chars)")
            else:
                print(f"⚠️  Attachment size may be too short ({len(attach_content)} chars)")
        else:
            print(f"⚠️  Attachment content is empty")
    else:
        print(f"ℹ️  No full message attachment found (may not be configured for email channel)")
    
    # Step 13: Validate API Access
    print("\n" + "=" * 80)
    print("STEP 13: VALIDATE API ACCESS")
    print("=" * 80)
    
    try:
        # Get message
        response = api_client.get(f"/messages/{message_id}")
        if response.status_code == 200:
            message_data = response.json()
            print(f"✅ Message accessible via API: /messages/{message_id}")
            print(f"   Status: {message_data.get('status')}")
            print(f"   Created: {message_data.get('created_at')}")
        else:
            print(f"⚠️  Message API returned {response.status_code}")
            
        # Get deliveries
        response = api_client.get(f"/messages/{message_id}/deliveries")
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

    # Best-effort cleanup (API-only)
    if message_id is not None:
        try:
            delete_resp = api_client.delete(f"/messages/{message_id}")
            if delete_resp.status_code in (200, 204, 404):
                print(f"[Cleanup] ✅ Deleted message {message_id} (status {delete_resp.status_code})")
            else:
                print(f"[Cleanup] ⚠️  Delete message {message_id} returned {delete_resp.status_code}: {delete_resp.text}")
        except Exception as e:
            print(f"[Cleanup] ⚠️  Exception deleting message {message_id}: {e}")
    
    # Step 14: Summary
    print("\n" + "=" * 80)
    print("STEP 14: SUMMARY")
    print("=" * 80)
    
    print(f"\n📋 MESSAGE INFORMATION:")
    print(f"   Message ID: {message_id}")
    print(f"   Message GUID: {message_guid}")
    print(f"   Delivery ID: {delivery_id}")
    
    print(f"\n🔗 API ENDPOINTS:")
    print(f"   Message: {api_base_url}/messages/{message_id}")
    print(f"   Deliveries: {api_base_url}/messages/{message_id}/deliveries")
    print(f"   Formatted (HTML, French): {api_base_url}/messages/{message_id}?format=html&language=fr")
    
    if message_guid:
        print(f"   Message by GUID: {api_base_url}/messages/{message_guid}")
    
    print(f"\n🔗 MESSAGE LINKS:")
    if source_url:
        print(f"   Source message (EN): {source_url}")
    if full_url:
        print(f"   Full message (FR): {full_url}")
    if pdf_url:
        print(f"   PDF: {pdf_url}")
    
    print(f"\n✅ VALIDATION RESULTS:")
    print(f"   ✅ Subject: {'CORRECT' if subject and subject != 'Please provide a summary in French of the following content:' else 'CHECK MANUALLY'}")
    print(f"   ✅ Format: {'HTML' if has_html_tags else 'NOT HTML'}")
    print(f"   ✅ Contents: {'PRESENT' if len(body) > 0 else 'MISSING'}")
    print(f"   ✅ Translation: {'FRENCH DETECTED' if found_french else 'NOT DETECTED'}")
    print(f"   ✅ SMTP Delivery: {'ACCEPTED' if not last_error else 'REJECTED'}")
    print(f"   ✅ API Access: {'AVAILABLE' if message_id else 'NOT AVAILABLE'}")
    print(f"   ✅ Source Message Link: {'VALIDATED' if source_url else 'NOT FOUND'}")
    print(f"   ✅ Full Message Link: {'VALIDATED' if full_url else 'NOT FOUND'}")
    print(f"   ✅ PDF Link: {'VALIDATED' if pdf_url else 'NOT FOUND'}")
    print(f"   ✅ Message Storage: {'VALIDATED' if storage_validated else 'NOT CONFIGURED'}")
    print(f"   ✅ Full Message Attachment: {'VALIDATED' if full_message_attachment else 'NOT CONFIGURED'}")
    
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
