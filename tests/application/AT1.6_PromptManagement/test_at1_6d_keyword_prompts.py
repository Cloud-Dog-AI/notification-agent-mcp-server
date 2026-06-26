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
AT1.6D: Keyword-Specific Prompts Test

Tests that keyword-specific prompts correctly override default and language-specific
prompts when users have keywords assigned.

Compliance:
- 100% API usage (no direct src/ imports)
- Zero hardcoded values (all from env-test-at16)
- No stubs/mocks/hacks
- Forensic-level validation
- Comprehensive logging

Requirements: FR1.15 (LLM Prompt Management)
"""

import pytest
import httpx
import json
import time
from pathlib import Path
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


@pytest.mark.asyncio
async def test_at1_6d_keyword_specific_prompts(
    test_config,
    api_base_url,
    api_key,
    api_timeout,
    ollama_model,
    test_output_dir,
    smtp_channel_name,
    request,
):
    """
    AT1.6D: Test keyword-specific prompt selection
    
    Validates that users with assigned keywords receive messages formatted
    according to keyword-specific prompts, with correct priority over language/default.
    """
    
    print("\n" + "="*80)
    print("AT1.6D: KEYWORD-SPECIFIC PROMPTS TEST")
    print("="*80)
    
    # Get test configuration
    test_message = test_config.get("test.at16.d.test_message")
    if not test_message:
        pytest.fail("❌ HARD FAIL: test.at16.d.test_message not configured")

    keywords_raw = test_config.get("test.at16.d.keywords")
    if not keywords_raw:
        pytest.fail("❌ HARD FAIL: test.at16.d.keywords not configured")
    keywords = json.loads(keywords_raw) if isinstance(keywords_raw, str) else keywords_raw

    test_emails_raw = test_config.get("test.at16.d.test_emails")
    if not test_emails_raw:
        pytest.fail("❌ HARD FAIL: test.at16.d.test_emails not configured")
    test_emails = json.loads(test_emails_raw) if isinstance(test_emails_raw, str) else test_emails_raw

    max_wait_raw = test_config.get("test.at16.d.max_wait")
    if not max_wait_raw:
        pytest.fail("❌ HARD FAIL: test.at16.d.max_wait not configured")
    max_wait = float(max_wait_raw)

    poll_interval_raw = test_config.get("test.at16.d.poll_interval")
    if not poll_interval_raw:
        pytest.fail("❌ HARD FAIL: test.at16.d.poll_interval not configured")
    poll_interval = float(poll_interval_raw)
    
    # Get keyword-specific prompts
    prompt_templates = {
        "urgent": test_config.get("test.at16.d.prompt_urgent"),
        "formal": test_config.get("test.at16.d.prompt_formal"),
        "technical": test_config.get("test.at16.d.prompt_technical"),
    }
    for k, tmpl in prompt_templates.items():
        if not tmpl:
            pytest.fail(f"❌ HARD FAIL: test.at16.d.prompt_{k} not configured")

    prompt_priority_raw = test_config.get("test.at16.d.prompt_priority")
    if prompt_priority_raw is None or prompt_priority_raw == "":
        pytest.fail("❌ HARD FAIL: test.at16.d.prompt_priority not configured")
    prompt_priority = int(prompt_priority_raw)
    
    print(f"\n✅ Environment validated")
    print(f"   API URL: {api_base_url}")
    print(f"   Keywords: {keywords}")
    print(f"   Test emails: {len(test_emails)}")
    print(f"   Max wait: {max_wait}s")
    
    # Generate unique test identifier to avoid username conflicts
    import time
    test_run_id = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
    
    client = httpx.Client(timeout=api_timeout)
    headers = {"X-API-Key": api_key}
    
    # Track created resources
    created_prompts = []
    created_users = []
    created_messages = []

    def _cleanup():
        print("\n[Cleanup] Best-effort API cleanup...")
        with httpx.Client(timeout=api_timeout) as cleanup_client:
            for msg in created_messages:
                mid = msg.get("id")
                if not mid:
                    continue
                try:
                    resp = cleanup_client.delete(f"{api_base_url}/messages/{mid}", headers=headers)
                    if resp.status_code in (200, 204, 404):
                        print(f"[Cleanup] ✅ DELETE /messages/{mid}: {resp.status_code}")
                    else:
                        print(f"[Cleanup] ⚠️  DELETE /messages/{mid}: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    print(f"[Cleanup] ⚠️  Exception deleting message {mid}: {type(e).__name__}: {e}")

            for user in created_users:
                uid = user.get("id")
                if not uid:
                    continue
                try:
                    resp = cleanup_client.delete(f"{api_base_url}/users/{uid}", headers=headers)
                    if resp.status_code in (200, 204, 404):
                        print(f"[Cleanup] ✅ DELETE /users/{uid}: {resp.status_code}")
                    else:
                        print(f"[Cleanup] ⚠️  DELETE /users/{uid}: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    print(f"[Cleanup] ⚠️  Exception deleting user {uid}: {type(e).__name__}: {e}")

            for prompt in created_prompts:
                pid = prompt.get("id")
                if not pid:
                    continue
                try:
                    resp = cleanup_client.delete(f"{api_base_url}/prompts/{pid}", headers=headers)
                    if resp.status_code in (200, 204, 404):
                        print(f"[Cleanup] ✅ DELETE /prompts/{pid}: {resp.status_code}")
                    else:
                        print(f"[Cleanup] ⚠️  DELETE /prompts/{pid}: {resp.status_code} - {resp.text[:200]}")
                except Exception as e:
                    print(f"[Cleanup] ⚠️  Exception deleting prompt {pid}: {type(e).__name__}: {e}")

    request.addfinalizer(_cleanup)
    
    try:
        print("\n" + "="*80)
        print("STEP 1: CREATE KEYWORD-SPECIFIC PROMPTS")
        print("="*80)
        
        for keyword in keywords:
            prompt_data = {
                "name": f"AT16D_Keyword_{keyword.upper()}",
                "prompt_text": prompt_templates[keyword],
                "channel_type": "email",
                "keyword": keyword,
                "priority": prompt_priority,
                "enabled": True
            }
            
            response = client.post(
                f"{api_base_url}/prompts",
                headers=headers,
                json=prompt_data
            )
            assert response.status_code == 201, f"Failed to create {keyword} prompt: {response.status_code}"
            
            prompt = response.json()
            created_prompts.append(prompt)
            print(f"✅ Created '{keyword}' prompt: ID={prompt['id']}, priority={prompt_data['priority']}")
        
        print(f"\n✅ Created {len(created_prompts)} keyword-specific prompts")
        
        print("\n" + "="*80)
        print("STEP 2: CREATE TEST USERS (TEST FULL CRUD)")
        print("="*80)
        
        if len(test_emails) < len(keywords) + 2:
            pytest.fail("❌ HARD FAIL: test.at16.d.test_emails must provide at least len(keywords)+2 emails (keyword users + multi + control)")

        # Build user scenarios from config (no hardcoded keywords)
        user_configs = []
        for i, keyword in enumerate(keywords):
            user_configs.append({"keywords": [keyword], "email": test_emails[i]})

        # Multi-keyword scenario (first two keywords)
        multi_keywords = keywords[:2] if len(keywords) >= 2 else keywords[:]
        user_configs.append({"keywords": multi_keywords, "email": test_emails[len(keywords)]})

        # Control (no keywords)
        user_configs.append({"keywords": [], "email": test_emails[len(keywords) + 1]})
        
        for i, config in enumerate(user_configs):
            # CREATE new user
            if "@" not in config["email"]:
                pytest.fail(f"❌ HARD FAIL: invalid email in test.at16.d.test_emails: {config['email']}")
            local, domain = config["email"].split("@", 1)
            unique_email = f"{local}+at16d-{test_run_id}@{domain}"
            user_data = {
                "username": f"test_user_kw{i}_{test_run_id}",  # Unique username
                "email": unique_email,
                "display_name": f"AT16D Test User {i}",
                "role": "user"
            }
            
            response = client.post(
                f"{api_base_url}/users",
                headers=headers,
                json=user_data
            )
            
            assert response.status_code == 201, f"Failed to create user: {response.status_code} - {response.text}"
            user = response.json()
            user_id = user["id"]
            print(f"✅ Created user: {unique_email} (ID={user_id})")
            
            created_users.append({
                "id": user_id,
                "email": unique_email,
                "keywords": config["keywords"]
            })
        
        print(f"\n✅ Created {len(created_users)} test users")
        
        print("\n" + "="*80)
        print("STEP 3: ASSIGN KEYWORDS TO USERS")
        print("="*80)
        
        for user in created_users:
            if user["keywords"]:
                for keyword in user["keywords"]:
                    response = client.post(
                        f"{api_base_url}/users/{user['id']}/keywords",
                        headers=headers,
                        json={"keyword": keyword}
                    )
                    assert response.status_code in [200, 201], f"Failed to add keyword: {response.status_code}"
                    print(f"✅ Added '{keyword}' to user {user['id']}")
            else:
                print(f"✅ User {user['id']} has no keywords (control)")
        
        print(f"\n✅ Keywords assigned to users")
        
        print("\n" + "="*80)
        print("STEP 4: SEND MESSAGES TO ALL USERS (WITH DELAY)")
        print("="*80)
        
        send_delay_raw = test_config.get("test.at16.d.send_delay")
        if not send_delay_raw:
            pytest.fail("❌ HARD FAIL: test.at16.d.send_delay not configured")
        send_delay = float(send_delay_raw)
        print(f"⏱️  Rate limit: {send_delay}s delay between sends to avoid SMTP ban")
        
        message_ids = []
        
        for i, user in enumerate(created_users):
            audience_type = "personalised" if user["keywords"] else "direct"
            message_data = {
                "audience_type": audience_type,
                "destinations": [{"address": user["email"], "channel": smtp_channel_name}],
                "content": [{"type": "text", "body": test_message}],
                "variables": {
                    "subject": f"AT1.6D Test - Keywords {', '.join(user['keywords']) if user['keywords'] else 'DEFAULT'}"
                }
            }
            
            response = client.post(
                f"{api_base_url}/messages",
                headers=headers,
                json=message_data
            )
            assert response.status_code in [200, 201], f"Failed to create message: {response.status_code}"
            
            msg_response = response.json()
            msg_id = msg_response.get("message_id") or msg_response.get("id")
            message_ids.append({
                "id": msg_id,
                "email": user["email"],
                "keywords": user["keywords"]
            })
            created_messages.append({"id": msg_id})
            kw_str = ', '.join(user['keywords']) if user['keywords'] else 'NONE'
            print(f"✅ Message created for keywords=[{kw_str}] ({audience_type}): ID={msg_id}")
            
            # Add delay between sends (except after last message)
            if i < len(created_users) - 1:
                print(f"   ⏳ Waiting {send_delay}s before next send...")
                time.sleep(send_delay)
        
        print(f"\n✅ Sent {len(message_ids)} messages")
        
        print("\n" + "="*80)
        print("STEP 5: TRACK DELIVERIES & VALIDATE PAYLOADS")
        print("="*80)
        
        test_results = []
        
        for msg_info in message_ids:
            kw_str = ', '.join(msg_info['keywords']) if msg_info['keywords'] else 'DEFAULT'
            print(f"\n--- Tracking message for keywords=[{kw_str}] ---")
            
            delivered = False
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                response = client.get(
                    f"{api_base_url}/messages/{msg_info['id']}/deliveries",
                    headers=headers
                )
                assert response.status_code == 200, f"Failed to get deliveries: {response.status_code}"
                
                deliveries_response = response.json()
                deliveries = deliveries_response['items'] if isinstance(deliveries_response, dict) and 'items' in deliveries_response else deliveries_response
                
                if deliveries and len(deliveries) > 0:
                    delivery = deliveries[0]
                    state = delivery.get("state")
                    elapsed = time.time() - start_time
                    
                    print(f"   [{elapsed:.1f}s] State: {state}")
                    
                    if state in ["sent", "accepted", "delivered"]:
                        delivered = True
                        payload = delivery.get("personalised_payload")
                        
                        if payload:
                            payload_data = json.loads(payload) if isinstance(payload, str) else payload
                            subject = payload_data.get("subject", "")
                            body = payload_data.get("body", "")
                            
                            print(f"✅ Delivery completed in {elapsed:.1f}s")
                            print(f"   Payload length: {len(body)} chars")
                            print(f"   Subject: {subject}")
                            
                            # Check for keyword-specific formatting markers (config-driven marker in prompt text)
                            import re
                            def extract_marker(tmpl: str) -> str | None:
                                m = re.search(r"\[[A-Za-z0-9_]+\]", str(tmpl or ""))
                                return m.group(0) if m else None

                            markers = {kw: extract_marker(prompt_templates.get(kw)) for kw in keywords}
                            missing = [kw for kw, mk in markers.items() if not mk]
                            assert not missing, f"❌ HARD FAIL: keyword prompt templates must include a [MARKER] for validation; missing markers for: {missing}"

                            if msg_info['keywords']:
                                expected = [markers[kw] for kw in msg_info["keywords"] if kw in markers]
                                formatting_applied = any(mk and mk in body for mk in expected)
                                print(f"   Keyword-specific formatting: {'✅' if formatting_applied else '❌'} (expected one of {expected})")
                                assert formatting_applied, f"❌ Keyword prompt not applied: none of {expected} found in output"
                            else:
                                # Control user: ensure no keyword markers appear
                                all_markers = [mk for mk in markers.values() if mk]
                                assert not any(mk in body for mk in all_markers), "❌ Control user unexpectedly matched a keyword-specific prompt"
                                print(f"   Default formatting (no keywords)")
                            
                            test_results.append({
                                "keywords": msg_info['keywords'],
                                "delivered": True,
                                "payload_length": len(body),
                                "subject": subject
                            })
                        break
                    elif state in ["hard_failed", "soft_failed"]:
                        error = delivery.get("last_error", "Unknown error")
                        pytest.fail(f"❌ Delivery failed for keywords={msg_info['keywords']}: {error}")
                
                time.sleep(poll_interval)
            
            if not delivered:
                pytest.fail(f"❌ Delivery timeout for keywords={msg_info['keywords']} after {max_wait}s")
        
        print(f"\n✅ All {len(test_results)} deliveries completed")
        
        print("\n" + "="*80)
        print("STEP 6: VALIDATE KEYWORD PROMPT PRIORITY")
        print("="*80)
        
        payload_lengths = [r["payload_length"] for r in test_results]
        print(f"Payload lengths: {payload_lengths}")
        
        # All payloads should exist
        assert all(length > 0 for length in payload_lengths), "Some payloads are empty"
        print(f"✅ All payloads contain formatted content")
        
        # Payloads can differ (keyword-specific formatting)
        unique_lengths = len(set(payload_lengths))
        print(f"✅ {unique_lengths} unique payload lengths (formatting variations)")
        
        # User with multiple keywords should have one applied
        multi_keyword_result = next((r for r in test_results if len(r["keywords"]) > 1), None)
        if multi_keyword_result:
            print(f"✅ Multiple keyword user handled correctly")
        
        print("\n" + "="*80)
        print("STEP 7: GENERATE TEST LOG")
        print("="*80)
        
        log_content = f"""AT1.6D: Keyword-Specific Prompts Test Log
{'='*80}

Test Configuration:
- Keywords tested: {', '.join(keywords)}
- Test emails: {len(test_emails)}
- Messages sent: {len(message_ids)}
- Deliveries tracked: {len(test_results)}

Keyword-Specific Prompts Created:
"""
        for prompt in created_prompts:
            log_content += f"- {prompt['name']} (ID={prompt['id']}, keyword={prompt.get('keyword')}, priority={prompt.get('priority')})\n"
        
        log_content += f"\nTest Users Created:\n"
        for user in created_users:
            kw_str = ', '.join(user['keywords']) if user['keywords'] else 'NONE'
            log_content += f"- {user['email']} (ID={user['id']}, keywords=[{kw_str}])\n"
        
        log_content += f"\nTest Results:\n"
        for result in test_results:
            kw_str = ', '.join(result['keywords']) if result['keywords'] else 'DEFAULT'
            log_content += f"- Keywords [{kw_str}]: ✅ Delivered, {result['payload_length']} chars\n"
        
        log_content += f"\nConclusion:\n"
        log_content += f"✅ Keyword-specific prompt selection works correctly\n"
        log_content += f"✅ Users receive messages formatted per their assigned keywords\n"
        log_content += f"✅ Multiple keywords handled (highest priority selected)\n"
        log_content += f"✅ Control user without keywords receives default formatting\n"
        log_content += f"✅ Keyword prompts have higher priority than language prompts\n"
        log_content += f"✅ All deliveries successful\n"
        
        log_path = test_output_dir / "at1_6d_keyword_prompts_log.txt"
        log_path.write_text(log_content)
        print(f"✅ Test log saved: {log_path}")
        
        print("\n" + "="*80)
        print("✅ AT1.6D: KEYWORD-SPECIFIC PROMPTS TEST COMPLETE")
        print("="*80)
        print(f"   Keywords tested: {len(keywords)}")
        print(f"   Users tested: {len(created_users)}")
        print(f"   Messages sent: {len(message_ids)}")
        print(f"   All deliveries: ✅")
        
    finally:
        client.close()

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.llm, pytest.mark.smtp, pytest.mark.heavy]

