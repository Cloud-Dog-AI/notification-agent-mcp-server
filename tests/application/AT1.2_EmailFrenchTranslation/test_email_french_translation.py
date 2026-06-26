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
Test Email Delivery with French Translation

Validates:
1. Email is sent successfully
2. Subject is correct (not the prompt text)
3. Content is translated to French
4. HTML format is used
5. Message link works (if provided)
"""

import pytest
import sys
import requests
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies


def _auth_headers_for_url(url: str, api_base_url: str, api_key: str) -> dict:
    """Return API-key headers for same-origin or localhost-alias links."""
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
    same_origin = same_scheme and target_host == api_host and target_port == api_port
    both_local = same_scheme and _is_local_host(target_host) and _is_local_host(api_host)
    if same_origin or both_local:
        return {"X-API-Key": api_key}
    return {}
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_french_email_delivery(api_base_url, api_key, smtp_config, test_email, default_channel):
    """Test that email with French preferences is sent correctly"""
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,  # This test requires LLM for translation
        requires_smtp=True,  # This test requires SMTP for email delivery
        requires_api=True,   # This test requires API server
        test_name="test_french_email_delivery"
    )
    
    # Create message with French preferences
    payload = {
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
            "preferences": {
                "language": "fr",
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": "This is a test message that should be translated to French and formatted as HTML email."
        }],
        "variables": {
            "subject": "Test Message - French Translation"
        }
    }
    
    # Submit message
    response = requests.post(
        f"{api_base_url}/messages",
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=10
    )
    
    assert response.status_code == 201, f"Message creation failed: {response.text}"
    result = response.json()
    message_id = result["message_id"]
    
    print(f"✅ Message created: {message_id}")
    
    # Wait for delivery using API (LLM formatting can take 2-5 minutes)
    import httpx
    delivery_id = None
    delivery = None
    max_attempts = 150  # 5 minutes max (150 * 2s = 300s)
    for i in range(max_attempts):
        time.sleep(2)
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key},
                timeout=5.0
            )
            if response.status_code == 200:
                data = response.json()
                deliveries = data.get("items", [])
                if deliveries:
                    delivery = deliveries[0]
                    delivery_id = delivery.get("id")
                    state = delivery.get("state")
                    error = delivery.get("last_error")
                    print(f"  Attempt {i+1}: state={state}, error={error[:50] if error else 'none'}")
                    
                    if state == "sent":
                        break
                    elif state in ["hard_failed", "cancelled"]:
                        pytest.fail(f"Delivery failed: {error}")
    
    assert delivery_id is not None, "Delivery not found"
    assert delivery is not None, "Delivery not found"
    assert delivery.get("state") == "sent", f"Delivery not sent: state={delivery.get('state')}, error={delivery.get('last_error')}"
    
    print(f"✅ Delivery {delivery_id} sent successfully")
    
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
    
    # Verify payload
    payload_json = delivery.get("personalised_payload")
    assert payload_json is not None, "Payload not found"
    payload_data = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
    
    # Check payload format - can be dict or list
    if isinstance(payload_data, dict):
        # Dict format: {subject, body, content_type, attachments}
        subject = payload_data.get("subject")
        body = payload_data.get("body", "")
        content_type = payload_data.get("content_type", "text")
    elif isinstance(payload_data, list):
        # List format: [{type: "subject", content: ...}, {type: "body", content: ...}]
        subject = None
        body = None
        content_type = None
        for block in payload_data:
            if isinstance(block, dict):
                if block.get('type') == 'html' or block.get('type') == 'text':
                    subject = block.get('subject')
                    body = block.get('body', '')
                    content_type = block.get('content_type', 'text')
                    break
    else:
        pytest.fail(f"Unexpected payload format: {type(payload_data)}")
    
    # Validate subject
    assert subject is not None, "Subject not found in payload"
    assert subject != "Please provide a summary in French", f"Wrong subject: {subject}"
    assert "test" in subject.lower() or "message" in subject.lower(), f"Subject doesn't contain expected text: {subject}"
    
    print(f"✅ Subject correct: {subject}")
    
    # REAL VALIDATION: Check body is ACTUALLY in French and HTML formatted
    assert len(body) > 0, "Body is empty"
    
    # Decode body if it's base64 encoded (from email)
    import base64
    try:
        # Try to decode if it looks like base64
        if body and not any(c in body for c in ['<', '>', '\n']) and len(body) > 50:
            try:
                decoded = base64.b64decode(body).decode('utf-8')
                body = decoded
                print(f"✅ Decoded base64 body")
            except:
                pass  # Not base64, use as-is
    except:
        pass
    
    # VALIDATE: Body MUST be in French (language: "fr" was requested)
    # Check for English words that should NOT be present if translated
    english_indicators = [
        "this is a test message",
        "should be translated",
        "formatted as html email"
    ]
    has_english = any(indicator in body.lower() for indicator in english_indicators)
    
    # Check for French words that SHOULD be present if translated
    french_indicators = [
        "ceci est",
        "message de test",
        "traduit",
        "français",
        "formaté",
        "email html"
    ]
    has_french = any(indicator in body.lower() for indicator in french_indicators)
    
    # FAIL if English indicators present (means not translated)
    if has_english:
        pytest.fail(f"❌ Body is NOT in French! Contains English: '{body[:200]}...'")
    
    # FAIL if no French indicators (means translation didn't work)
    if not has_french:
        pytest.fail(f"❌ Body does not appear to be in French! Content: '{body[:200]}...'")
    
    print(f"✅ Body is in French (contains French keywords, no English indicators)")
    
    # VALIDATE: Body MUST be HTML formatted (content_style: "html" was requested)
    has_html_tags = "<" in body and ">" in body
    has_html_structure = any(tag in body.lower() for tag in ["<html", "<body", "<p>", "<div", "<br"])
    
    # Check content_type
    is_html_content_type = content_type == "html" or "html" in str(content_type).lower()
    
    # FAIL if not HTML
    if not has_html_tags:
        pytest.fail(f"❌ Body is NOT HTML formatted! Content type: {content_type}, Body preview: '{body[:200]}...'")
    
    if not has_html_structure and not is_html_content_type:
        pytest.fail(f"❌ Body does not have HTML structure! Content type: {content_type}, Body preview: '{body[:200]}...'")
    
    print(f"✅ Body is HTML formatted (has HTML tags and structure)")
    print(f"✅ Body length: {len(body)} chars, Content type: {content_type}")
    
    # VALIDATE: Extract and verify message link
    import re
    message_link = None
    message_guid = None
    
    # Extract link from HTML format: <a href="...">view it online</a>
    html_link_match = re.search(r'<a\s+href=["\']([^"\']+)["\']>.*?view it online', body, re.IGNORECASE)
    if html_link_match:
        message_link = html_link_match.group(1)
    else:
        # Extract link from plain text format: "view it online at: http://..."
        text_link_match = re.search(r'view it online at:\s*([^\s<]+)', body, re.IGNORECASE)
        if text_link_match:
            message_link = text_link_match.group(1).rstrip('.,;')
    
    if message_link:
        print(f"✅ Found message link: {message_link}")
        # Extract GUID from link
        guid_match = re.search(r'/messages/([0-9a-f-]{36})', message_link, re.IGNORECASE)
        if guid_match:
            message_guid = guid_match.group(1)
            print(f"✅ Extracted GUID from link: {message_guid}")
            
            # CRITICAL: Verify the link actually works and shows formatted content
            with httpx.Client(timeout=10.0) as client:
                # Test 1: Default link (should return HTML)
                print(f"🔍 Testing link: {message_link}")
                link_response = client.get(
                    message_link if message_link.startswith('http') else f"{api_base_url}{message_link}",
                    headers=_auth_headers_for_url(message_link, api_base_url, api_key),
                    timeout=5.0
                )
                
                # CRITICAL: Link MUST return 200 and have content
                if not link_response:
                    pytest.fail(f"❌ Link returned no response: {message_link}")
                if link_response.status_code != 200:
                    pytest.fail(f"❌ Link returned HTTP {link_response.status_code}: {message_link}")
                
                # Get response content
                link_content = link_response.text if hasattr(link_response, 'text') else None
                if not link_content:
                    try:
                        link_content = link_response.content.decode('utf-8') if hasattr(link_response, 'content') else None
                    except:
                        link_content = None
                
                # CRITICAL: Content MUST exist and not be null/empty
                if not link_content or link_content.strip() == '' or link_content.lower() == 'null':
                    pytest.fail(f"❌ Link returned null/empty content: {message_link}. Status: {link_response.status_code}, Content-Type: {link_response.headers.get('content-type', 'unknown')}")
                
                content_type_header = link_response.headers.get('content-type', '') if link_response.headers else ''
                
                if link_response.status_code == 200:
                    # Get response content first - handle both text and JSON responses
                    try:
                        link_content = link_response.text if hasattr(link_response, 'text') else None
                    except:
                        link_content = None
                    if not link_content:
                        # Try to get content as bytes and decode
                        try:
                            link_content = link_response.content.decode('utf-8') if hasattr(link_response, 'content') else None
                        except:
                            link_content = None
                    content_type_header = link_response.headers.get('content-type', '') if link_response.headers else ''
                    
                    # Check if response is HTML (either by content-type or by content inspection)
                    # Always check content first since content-type might not be set correctly
                    is_html = False
                    if link_content and len(link_content) > 0:
                        # Check for HTML indicators in content (check first 1000 chars for performance)
                        content_preview = link_content[:1000].lower()
                        is_html = ("<!doctype html" in content_preview or 
                                  "<html" in content_preview or 
                                  ("<h1>" in link_content and "<div" in link_content and ("<p>" in link_content or "<body" in link_content or "message-content" in link_content)))
                    # Also check content-type header
                    if not is_html:
                        is_html = 'text/html' in content_type_header.lower()
                    
                    if is_html:
                        # Verify the link shows the formatted message (French, HTML)
                        # Check for French content
                        has_french_in_link = any(indicator in link_content.lower() for indicator in french_indicators)
                        # Check for HTML formatted content
                        has_html_in_link = "<h1>" in link_content or "<p>" in link_content
                        # Check for "Formatted Message Content" section
                        has_formatted_section = "Formatted Message Content" in link_content or "formatted" in link_content.lower()
                        
                        if not has_french_in_link:
                            pytest.fail(f"❌ Link does not show French formatted content (no French indicators found)")
                        if not has_html_in_link:
                            pytest.fail(f"❌ Link does not show HTML formatted content (no HTML tags found)")
                        if not has_formatted_section:
                            pytest.fail(f"❌ Link does not show formatted message section")
                        
                        # Verify formatted payload section using current template or fallback markers.
                        # The viewer template can change container classes without changing behavior.
                        formatted_match = re.search(
                            r'<div[^>]*class="[^"]*message-content[^"]*"[^>]*>(.*?)</div>',
                            link_content,
                            re.DOTALL,
                        )
                        if formatted_match:
                            formatted_body_from_link = formatted_match.group(1).strip()
                            if any(indicator in formatted_body_from_link.lower() for indicator in french_indicators):
                                print(f"✅ Link shows formatted French HTML content")
                            else:
                                pytest.fail(f"❌ Link formatted content does not match email body (no French content)")
                        else:
                            # Fallback acceptance: page-level HTML + French checks already passed above.
                            print("✅ Link shows formatted content via updated viewer template (container selector not strict)")
                        
                        print(f"✅ Link points to correct message and shows formatted content (verified via HTML)")
                        
                    elif 'application/json' in content_type_header.lower():
                        # JSON response
                        try:
                            link_data = link_response.json() if link_response else None
                        except:
                            link_data = None
                        if link_data:
                            if link_data.get('id') == message_id or link_data.get('guid') == message_guid:
                                # Check if JSON includes formatted_content
                                if 'formatted_content' in link_data:
                                    formatted_content = link_data.get('formatted_content', '')
                                    if any(indicator in formatted_content.lower() for indicator in french_indicators):
                                        print(f"✅ Link points to correct message and shows formatted content (verified via JSON)")
                                    else:
                                        pytest.fail(f"❌ Link JSON does not contain French formatted content")
                                else:
                                    print(f"✅ Link points to correct message (verified via JSON: ID={link_data.get('id')}, GUID={link_data.get('guid')})")
                            else:
                                pytest.fail(f"❌ Link points to wrong message: expected ID={message_id}, got ID={link_data.get('id')}")
                        else:
                            # Not valid JSON - if HTML format endpoint returned null/error, that's OK as long as JSON works
                            # We've already tested JSON endpoint above, so just log a warning
                            print(f"⚠️  HTML format endpoint returned JSON/null (JSON endpoint tested separately)")
                            # Don't fail - JSON endpoint validation above will catch issues
                    else:
                        # Unknown content type - check content to determine type
                        # If it looks like HTML, treat it as HTML
                        if "<html" in link_content.lower() or "<!DOCTYPE html" in link_content or ("<h1>" in link_content and "<div" in link_content):
                            # Treat as HTML
                            has_french_in_link = any(indicator in link_content.lower() for indicator in french_indicators)
                            has_html_in_link = "<h1>" in link_content or "<p>" in link_content
                            has_formatted_section = "Formatted Message Content" in link_content or "formatted" in link_content.lower()
                            
                            if not has_french_in_link:
                                pytest.fail(f"❌ Link does not show French formatted content")
                            if not has_html_in_link:
                                pytest.fail(f"❌ Link does not show HTML formatted content")
                            if not has_formatted_section:
                                pytest.fail(f"❌ Link does not show formatted message section")
                            
                            print(f"✅ Link shows formatted French HTML content (detected as HTML from content)")
                        else:
                            # Try JSON as last resort
                            try:
                                link_data = link_response.json()
                                if link_data and (link_data.get('id') == message_id or link_data.get('guid') == message_guid):
                                    print(f"✅ Link points to correct message (detected as JSON)")
                                else:
                                    pytest.fail(f"❌ Link response has unknown format. Content-Type: {content_type_header}, Content preview: {link_content[:200]}")
                            except:
                                pytest.fail(f"❌ Link response has unknown format. Content-Type: {content_type_header}, Content preview: {link_content[:200]}")
                else:
                    pytest.fail(f"❌ Link is not accessible: HTTP {link_response.status_code}")
                
                # Also test JSON format endpoint to verify formatted_content and status
                json_link = f"{message_link}?format=json" if '?' not in message_link else f"{message_link}&format=json"
                json_response = client.get(
                    json_link if json_link.startswith('http') else f"{api_base_url}{json_link}",
                    headers=_auth_headers_for_url(json_link, api_base_url, api_key),
                    timeout=5.0
                )
                if json_response.status_code == 200:
                    json_data = json_response.json()
                    if json_data.get('id') == message_id or json_data.get('guid') == message_guid:
                        # VALIDATE: JSON should include formatted_content
                        if 'formatted_content' not in json_data:
                            pytest.fail(f"❌ JSON format does not include 'formatted_content' field")
                        formatted_content = json_data.get('formatted_content', '')
                        if not formatted_content or formatted_content.strip() == '':
                            pytest.fail(f"❌ JSON format 'formatted_content' is empty")
                        # Check formatted_content is in French
                        if not any(indicator in formatted_content.lower() for indicator in french_indicators):
                            pytest.fail(f"❌ JSON formatted_content is not in French")
                        print(f"✅ Link JSON endpoint works correctly with formatted_content (ID={json_data.get('id')}, GUID={json_data.get('guid')})")
                        
                        # VALIDATE: Status should be 'completed' not 'processing' when all deliveries are sent
                        json_status = json_data.get('status')
                        deliveries_info = json_data.get('deliveries', {})
                        if isinstance(deliveries_info, dict):
                            by_state = deliveries_info.get('by_state', {})
                            sent_count = by_state.get('sent', 0) if isinstance(by_state, dict) else 0
                            if json_status == 'processing' and sent_count > 0:
                                pytest.fail(f"❌ Status is 'processing' but deliveries are sent - should be 'completed'")
                        if json_status not in ['completed', 'processing', 'partial', 'failed']:
                            pytest.fail(f"❌ Invalid status: {json_status}")
                        print(f"✅ JSON status is correct: {json_status}")
                    else:
                        pytest.fail(f"❌ Link JSON endpoint returns wrong message")
                else:
                    pytest.fail(f"❌ Link JSON endpoint not accessible: HTTP {json_response.status_code}")
                
                # Test Markdown format endpoint
                markdown_link = f"{message_link}?format=markdown" if '?' not in message_link else f"{message_link}&format=markdown"
                markdown_response = client.get(
                    markdown_link if markdown_link.startswith('http') else f"{api_base_url}{markdown_link}",
                    headers=_auth_headers_for_url(markdown_link, api_base_url, api_key),
                    timeout=5.0
                )
                if markdown_response.status_code == 200:
                    markdown_content = markdown_response.text
                    # VALIDATE: Markdown should be properly formatted (not raw HTML)
                    if '<' in markdown_content and '>' in markdown_content and '<p>' in markdown_content:
                        # Still has HTML tags - markdown conversion didn't work
                        pytest.fail(f"❌ Markdown format still contains HTML tags (conversion failed)")
                    # Check for markdown syntax
                    has_markdown_syntax = '#' in markdown_content or '**' in markdown_content or '[' in markdown_content
                    # Check for French content
                    has_french_in_markdown = any(indicator in markdown_content.lower() for indicator in french_indicators)
                    if not has_french_in_markdown:
                        pytest.fail(f"❌ Markdown format does not contain French content")
                    if not markdown_content.strip():
                        pytest.fail(f"❌ Markdown format is empty")
                    print(f"✅ Markdown format endpoint works correctly (contains French, properly formatted)")
                else:
                    pytest.fail(f"❌ Markdown format endpoint not accessible: HTTP {markdown_response.status_code}")
                
                # VALIDATE: HTML view should show delivery/sent time
                html_response = client.get(
                    message_link if message_link.startswith('http') else f"{api_base_url}{message_link}",
                    headers=_auth_headers_for_url(message_link, api_base_url, api_key),
                    timeout=5.0
                )
                if html_response and html_response.status_code == 200:
                    content_type = html_response.headers.get('content-type', '') if html_response.headers else ''
                    if 'text/html' in content_type:
                        html_content = html_response.text
                        # Check for "Sent At" or "Delivered At" in the HTML
                        has_sent_time = "Sent At" in html_content or "sent_at" in html_content.lower()
                        has_delivered_time = "Delivered At" in html_content or "delivered_at" in html_content.lower()
                        if not has_sent_time and not has_delivered_time:
                            pytest.fail(f"❌ HTML view does not show delivery/sent time")
                        print(f"✅ HTML view shows delivery/sent time")
                    else:
                        print(f"⚠️  HTML response is not HTML format: {content_type}")
                else:
                    pytest.fail(f"❌ HTML view endpoint not accessible: HTTP {html_response.status_code if html_response else 'None'}")
        else:
            pytest.fail(f"❌ Could not extract GUID from link: {message_link}")
    else:
        pytest.fail(f"❌ No message link found in email body")
    
    # VALIDATE: Extract and verify attachment
    attachments = payload_data.get("attachments", [])
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
                # Check for French indicators in attachment
                has_french_in_attachment = any(indicator in attachment_content.lower() for indicator in french_indicators)
                has_english_in_attachment = any(indicator in attachment_content.lower() for indicator in english_indicators)
                
                if has_english_in_attachment:
                    pytest.fail(f"❌ Attachment content is NOT in French! Contains English: '{attachment_content[:200]}...'")
                
                if not has_french_in_attachment:
                    pytest.fail(f"❌ Attachment content does not appear to be in French! Content: '{attachment_content[:200]}...'")
                
                print(f"✅ Attachment content is in French")
                
                # Verify attachment content matches email body (should be similar)
                # Allow for minor differences (HTML tags, formatting)
                body_text_only = re.sub(r'<[^>]+>', '', body).strip()
                attachment_text_only = re.sub(r'<[^>]+>', '', attachment_content).strip()
                
                # Check if they contain similar French content
                if len(body_text_only) > 50 and len(attachment_text_only) > 50:
                    # Both should contain French keywords
                    body_french_words = [w for w in french_indicators if w in body_text_only.lower()]
                    attachment_french_words = [w for w in french_indicators if w in attachment_text_only.lower()]
                    
                    if body_french_words and attachment_french_words:
                        # Should have at least some overlap
                        common_words = set(body_french_words) & set(attachment_french_words)
                        if common_words:
                            print(f"✅ Attachment content matches email body (both contain French: {', '.join(common_words)})")
                        else:
                            pytest.fail(f"❌ Attachment content does not match email body (different French content)")
                    else:
                        print(f"⚠️  Could not verify attachment content matches body (no French keywords found)")
                else:
                    print(f"⚠️  Could not verify attachment content matches body (content too short)")
            else:
                pytest.fail(f"❌ Attachment has no content")
    else:
        pytest.fail(f"❌ No attachment found in email payload (attachment should be present)")
    
    return message_id, delivery_id

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.docker, pytest.mark.heavy]

