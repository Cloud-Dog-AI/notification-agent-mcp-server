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
AT1.5 Use Case UC1.6: Group Notification with Multimedia and Multi-Language PDFs

Tests group notification with multimedia content and PDF generation.

Related Requirements: UC1.6, FR1.2, FR1.18
Related Architecture: CC4.1.1, CC5.2.1
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
validate_pdf = _helpers_module.validate_pdf
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-009")


def test_at1_5_uc1_6_multimedia(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_email: str,
    test_output_dir: Path,
    smtp_channel_name: str,
):
    """
    Test UC1.6: Group Notification with Multimedia and Multi-Language PDFs
    
    Validates group notification with multimedia content and PDF generation
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
        test_name="AT1.5_UC1_6_MULTIMEDIA"
    )
    
    print(f"\n{'='*80}")
    print("AT1.5 USE CASE UC1.6: MULTIMEDIA & MULTI-LANGUAGE PDFS")
    print(f"{'='*80}\n")
    
    # Get test configuration
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured")
    
    max_wait = test_config.get("test.at15.max_wait")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at15.max_wait not configured in env file")
    
    target_language = test_config.get("test.at15.uc1_6.language")
    if not target_language:
        pytest.fail(
            "❌ HARD FAIL: test.at15.uc1_6.language not configured in env file.\n"
            "Set CLOUD_DOG__NOTIFY__TEST__AT15__UC1_6__LANGUAGE in env file"
        )
    
    # Load test message
    try:
        message_content = load_test_message("en", 2000)
        print(f"✅ Loaded test message: {len(message_content)} chars (EN)")
    except FileNotFoundError as e:
        pytest.fail(f"Test message file not found: {e}")
    
    # Create message with PDF generation
    print("\n" + "=" * 80)
    print("STEP 1: CREATE MESSAGE WITH PDF GENERATION")
    print("=" * 80)
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": smtp_channel_name,
            "address": test_email,
            "preferences": {
                "language": target_language,
                "content_style": "html",
                "generate_pdf": True,
                "pdf_preference": "attach",
                "output_formats": ["summary", "full", "pdf"]
            }
        }],
        "content": [{
            "type": "text",
            "body": message_content
        }],
        "options": {"subject": None}
    }
    subject = test_config.get("test.at15.uc1_6.subject")
    if not subject:
        pytest.fail("❌ HARD FAIL: test.at15.uc1_6.subject not configured in env file")
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
    
    # Validate multimedia content
    print("\n" + "=" * 80)
    print("STEP 3: VALIDATE MULTIMEDIA CONTENT")
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
        attachments = payload_data.get("attachments", [])
    elif isinstance(payload_data, list) and len(payload_data) > 0:
        email_body = payload_data[0].get("body", "")
        attachments = payload_data[0].get("attachments", [])
    else:
        pytest.fail(f"❌ Unexpected payload format")
    
    # Validate PDF delivery (attachment OR link) - REQUIRED when generate_pdf=True
    links = payload_data.get("links", []) if isinstance(payload_data, dict) else []
    pdf_urls = []
    pdf_attachments = []

    # Attachments may contain inline PDF or a URL
    for a in attachments or []:
        if a.get("content_type") == "application/pdf" or a.get("type") == "pdf" or str(a.get("filename", "")).lower().endswith(".pdf"):
            pdf_attachments.append(a)
            if a.get("url"):
                pdf_urls.append(a["url"])

    # Links may contain a PDF access URL
    for link in links or []:
        url = link.get("url")
        label = str(link.get("label", "")).lower()
        if url and (url.lower().endswith(".pdf") or "pdf" in label):
            pdf_urls.append(url)

    pdf_urls = list(dict.fromkeys(pdf_urls))  # de-dupe, preserve order
    if not pdf_attachments and not pdf_urls:
        pytest.fail("❌ PDF was explicitly requested (generate_pdf=True) but no PDF attachment/link was found in payload")

    if pdf_attachments:
        print(f"✅ PDF attachment(s) found: {len(pdf_attachments)}")
        pdf_att = pdf_attachments[0]
        try:
            import base64
            pdf_b64 = pdf_att.get("content")
            if not pdf_b64:
                pytest.fail("❌ PDF attachment present but missing 'content'")
            pdf_bytes = base64.b64decode(pdf_b64) if isinstance(pdf_b64, str) else pdf_b64
            pdf_valid, pdf_info = validate_pdf(pdf_bytes, target_language, expected_min_size=1000)
            assert pdf_valid, f"❌ PDF validation failed: {pdf_info}"
            print(f"✅ PDF validated (attachment): {pdf_info}")
        except Exception as e:
            pytest.fail(f"❌ PDF attachment validation error: {e}")
    else:
        print(f"✅ PDF link(s) found: {len(pdf_urls)}")
        for pdf_url in pdf_urls:
            print(f"   PDF: {pdf_url}")

        # Fetch and validate the first PDF URL
        pdf_url = pdf_urls[0]
        try:
            with httpx.Client(timeout=api_timeout) as client:
                response = client.get(
                    pdf_url,
                    headers={"X-API-Key": api_key} if pdf_url.startswith(api_base_url) else {},
                    timeout=api_timeout
                )
            assert response.status_code == 200, f"PDF URL not accessible: {response.status_code}"
            assert response.headers.get("content-type", "").startswith("application/pdf"), f"PDF content-type incorrect: {response.headers.get('content-type')}"
            pdf_content = response.content
            pdf_valid, pdf_info = validate_pdf(pdf_content, target_language, expected_min_size=1000)
            assert pdf_valid, f"❌ PDF validation failed: {pdf_info}"
            print(f"✅ PDF validated (link): {pdf_info}")
        except Exception as e:
            pytest.fail(f"❌ PDF link validation error: {e}")
    
    # Validate language
    if target_language != "en":
        is_valid, details = validate_language(email_body, target_language)
        assert is_valid, f"❌ Language validation failed: {details}"
        print(f"✅ Language validated: {target_language.upper()}")
    
    # Save test log
    test_log_file = test_output_dir / "uc1_6_multimedia_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: AT1.5 UC1.6 - Multimedia & Multi-Language PDFs\n")
        f.write(f"Message ID: {message_id}\n")
        f.write(f"Message GUID: {message_guid}\n")
        f.write(f"Language: {target_language.upper()}\n")
        f.write(f"PDF Attachments: {len(pdf_attachments)}\n")
        f.write(f"Delivery State: sent\n")
        f.write(f"Status: PASSED\n")
    
    print(f"✅ Test log saved: {test_log_file}")
    
    print(f"\n✅ UC1.6 Multimedia & PDF test complete")
    print(f"   Message ID: {message_id}")
    print(f"   Language: {target_language.upper()}")
    print(f"   PDFs: {len(pdf_attachments)}")

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
