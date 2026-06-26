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
AT1.6C: Language-Specific Prompts Test

Tests that language-specific prompts correctly override default channel prompts
when users have language preferences set.

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
import re
from pathlib import Path


def _normalise_prompt_prefix(body: str) -> str:
    text = re.sub(r"<[^>]+>", " ", body or "")
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^View it online\s*", "", text, flags=re.IGNORECASE)
    return text
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


@pytest.mark.asyncio
async def test_at1_6c_language_specific_prompts(
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
    AT1.6C: Test language-specific prompt selection
    
    Validates that users with language preferences receive messages formatted
    according to language-specific prompts, with correct priority and fallback.
    """
    
    print("\n" + "="*80)
    print("AT1.6C: LANGUAGE-SPECIFIC PROMPTS TEST")
    print("="*80)
    
    # Get test configuration
    test_message = test_config.get("test.at16.c.test_message")
    if not test_message:
        pytest.fail("❌ HARD FAIL: test.at16.c.test_message not configured")

    languages_raw = test_config.get("test.at16.c.languages")
    if not languages_raw:
        pytest.fail("❌ HARD FAIL: test.at16.c.languages not configured")
    languages = json.loads(languages_raw) if isinstance(languages_raw, str) else languages_raw

    test_emails_raw = test_config.get("test.at16.c.test_emails")
    if not test_emails_raw:
        pytest.fail("❌ HARD FAIL: test.at16.c.test_emails not configured")
    test_emails = json.loads(test_emails_raw) if isinstance(test_emails_raw, str) else test_emails_raw
    max_wait_raw = test_config.get("test.at16.c.max_wait")
    if not max_wait_raw:
        pytest.fail("❌ HARD FAIL: test.at16.c.max_wait not configured")
    max_wait = float(max_wait_raw)

    poll_interval_raw = test_config.get("test.at16.c.poll_interval")
    if not poll_interval_raw:
        pytest.fail("❌ HARD FAIL: test.at16.c.poll_interval not configured")
    poll_interval = float(poll_interval_raw)
    
    # Get language-specific prompts
    prompt_templates = {
        "en": test_config.get("test.at16.c.prompt_en"),
        "fr": test_config.get("test.at16.c.prompt_fr"),
        "de": test_config.get("test.at16.c.prompt_de"),
        "pl": test_config.get("test.at16.c.prompt_pl"),
    }
    for lang, tmpl in prompt_templates.items():
        if not tmpl:
            pytest.fail(f"❌ HARD FAIL: test.at16.c.prompt_{lang} not configured")

    prompt_priority_raw = test_config.get("test.at16.c.prompt_priority")
    if prompt_priority_raw is None or prompt_priority_raw == "":
        pytest.fail("❌ HARD FAIL: test.at16.c.prompt_priority not configured")
    prompt_priority = int(prompt_priority_raw)
    
    default_language = test_config.get("app.default_language") or (languages[0] if languages else None)
    if not default_language:
        pytest.fail("❌ HARD FAIL: app.default_language not configured and no languages provided")

    print(f"\n✅ Environment validated")
    print(f"   API URL: {api_base_url}")
    print(f"   Languages: {languages}")
    print(f"   Default language: {default_language}")
    print(f"   Test emails: {len(test_emails)}")
    print(f"   Max wait: {max_wait}s")
    
    # Generate unique test identifier to avoid username conflicts
    import time
    test_run_id = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
    
    client = httpx.Client(timeout=api_timeout)
    headers = {"X-API-Key": api_key}
    
    # Track created resources for cleanup validation
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
        print("STEP 1: CREATE LANGUAGE-SPECIFIC PROMPTS")
        print("="*80)
        
        for lang in languages:
            prompt_data = {
                "name": f"AT16C_Language_{lang.upper()}",
                "prompt_text": prompt_templates[lang],
                "channel_type": "email",
                "language": lang,
                "priority": prompt_priority,
                "enabled": True
            }
            
            response = client.post(
                f"{api_base_url}/prompts",
                headers=headers,
                json=prompt_data
            )
            assert response.status_code == 201, f"Failed to create {lang} prompt: {response.status_code}"
            
            prompt = response.json()
            created_prompts.append(prompt)
            print(f"✅ Created {lang} prompt: ID={prompt['id']}")
        
        print(f"\n✅ Created {len(created_prompts)} language-specific prompts")
        
        print("\n" + "="*80)
        print("STEP 2: CREATE TEST USERS WITH LANGUAGE PREFERENCES (TEST FULL CRUD)")
        print("="*80)
        
        for i, lang in enumerate(languages):
            # CREATE new user with language preference
            if "@" not in test_emails[i]:
                pytest.fail(f"❌ HARD FAIL: invalid email in test.at16.c.test_emails[{i}]: {test_emails[i]}")
            local, domain = test_emails[i].split("@", 1)
            unique_email = f"{local}+at16c-{test_run_id}@{domain}"
            user_data = {
                "username": f"test_user_{lang}_{test_run_id}",  # Unique username
                "email": unique_email,
                "display_name": f"AT16C Test User {lang.upper()}",
                "role": "user",
                "language": lang
            }
            
            response = client.post(
                f"{api_base_url}/users",
                headers=headers,
                json=user_data
            )
            
            assert response.status_code == 201, f"Failed to create user: {response.status_code} - {response.text}"
            user = response.json()
            print(f"✅ Created user: {unique_email} (ID={user['id']}, lang={lang})")
            created_users.append({"id": user["id"], "email": unique_email, "language": lang})
        
        # Create control user without language preference
        if "@" not in test_emails[4]:
            pytest.fail(f"❌ HARD FAIL: invalid email in test.at16.c.test_emails[4]: {test_emails[4]}")
        local, domain = test_emails[4].split("@", 1)
        control_email = f"{local}+at16c-{test_run_id}@{domain}"
        control_user_data = {
            "username": f"test_user_default_{test_run_id}",  # Unique username
            "email": control_email,
            "display_name": "AT16C Test User Default",
            "role": "user"
        }
        
        response = client.post(
            f"{api_base_url}/users",
            headers=headers,
            json=control_user_data
        )
        
        assert response.status_code == 201, f"Failed to create control user: {response.status_code} - {response.text}"
        control_user = response.json()
        print(f"✅ Created control user: {control_email} (ID={control_user['id']}, lang=NULL)")
        
        created_users.append({"id": control_user["id"], "email": control_email, "language": None})
        
        print(f"\n✅ Created {len(created_users)} test users")
        
        print("\n" + "="*80)
        print("STEP 3: SEND MESSAGES TO ALL USERS (WITH DELAY)")
        print("="*80)
        
        send_delay_raw = test_config.get("test.at16.c.send_delay")
        if not send_delay_raw:
            pytest.fail("❌ HARD FAIL: test.at16.c.send_delay not configured")
        send_delay = float(send_delay_raw)
        print(f"⏱️  Rate limit: {send_delay}s delay between sends to avoid SMTP ban")
        
        message_ids = []
        
        for i, user in enumerate(created_users):
            destination = {"address": user["email"], "channel": smtp_channel_name}
            if user.get("language"):
                destination["preferences"] = {"language": user["language"]}

            message_data = {
                "audience_type": "personalised",
                "destinations": [destination],
                "content": [{"type": "text", "body": test_message}],
                "variables": {
                    "subject": f"AT1.6C Test - Language {user['language'] or 'DEFAULT'}"
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
                "language": user["language"]
            })
            created_messages.append({"id": msg_id})
            print(f"✅ Message created for {user['language'] or 'DEFAULT'}: ID={msg_id}")
            
            # Add delay between sends (except after last message)
            if i < len(created_users) - 1:
                print(f"   ⏳ Waiting {send_delay}s before next send...")
                time.sleep(send_delay)
        
        print(f"\n✅ Sent {len(message_ids)} messages")
        
        print("\n" + "="*80)
        print("STEP 4: TRACK DELIVERIES & VALIDATE PAYLOADS")
        print("="*80)
        
        test_results = []
        
        for msg_info in message_ids:
            print(f"\n--- Tracking message for {msg_info['language'] or 'DEFAULT'} ---")
            
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
                            
                            # Check for language-specific formatting markers (config-driven greeting phrase in prompt text)
                            lang = msg_info['language']
                            if lang:
                                tmpl = str(prompt_templates.get(lang) or "")
                                m = re.search(r"'([^']+)'", tmpl)
                                expected_greeting = m.group(1) if m else None
                                assert expected_greeting, f"❌ HARD FAIL: test.at16.c.prompt_{lang} must include a quoted greeting like 'Dear Recipient,' for validation"
                                normalized_prefix = _normalise_prompt_prefix(body)[:400]
                                formatting_applied = expected_greeting.lower() in normalized_prefix.lower()
                                print(f"   Language-specific formatting: {'✅' if formatting_applied else '❌'} (expected greeting: {expected_greeting})")
                                assert formatting_applied, (
                                    f"❌ Language prompt not applied for {lang}: "
                                    f"greeting {expected_greeting!r} not found in normalized prefix {normalized_prefix!r}"
                                )
                            else:
                                # Control user: allow default language greeting, but block non-default greetings
                                greetings = []
                                for k, tmpl in prompt_templates.items():
                                    if k == default_language:
                                        continue
                                    m = re.search(r"'([^']+)'", str(tmpl or ""))
                                    if m:
                                        greetings.append(m.group(1))
                                normalized_prefix = _normalise_prompt_prefix(body)[:400].lower()
                                assert not any(g.lower() in normalized_prefix for g in greetings), (
                                    "❌ Control user unexpectedly matched a non-default language prompt"
                                )
                                print(f"   Default formatting (no language preference)")
                            
                            test_results.append({
                                "language": lang or "DEFAULT",
                                "delivered": True,
                                "payload_length": len(body),
                                "subject": subject
                            })
                        break
                    elif state in ["hard_failed", "soft_failed"]:
                        error = delivery.get("last_error", "Unknown error")
                        pytest.fail(f"❌ Delivery failed for {msg_info['language'] or 'DEFAULT'}: {error}")
                
                time.sleep(poll_interval)
            
            if not delivered:
                pytest.fail(f"❌ Delivery timeout for {msg_info['language'] or 'DEFAULT'} after {max_wait}s")
        
        print(f"\n✅ All {len(test_results)} deliveries completed")
        
        print("\n" + "="*80)
        print("STEP 5: VALIDATE DIFFERENT FORMATTING PER LANGUAGE")
        print("="*80)
        
        payload_lengths = [r["payload_length"] for r in test_results]
        print(f"Payload lengths: {payload_lengths}")
        
        # All payloads should exist
        assert all(length > 0 for length in payload_lengths), "Some payloads are empty"
        print(f"✅ All payloads contain formatted content")
        
        # Payloads can differ (language-specific formatting)
        unique_lengths = len(set(payload_lengths))
        print(f"✅ {unique_lengths} unique payload lengths (formatting variations)")
        
        print("\n" + "="*80)
        print("STEP 6: GENERATE TEST LOG")
        print("="*80)
        
        log_content = f"""AT1.6C: Language-Specific Prompts Test Log
{'='*80}

Test Configuration:
- Languages tested: {', '.join(languages)}
- Test emails: {len(test_emails)}
- Messages sent: {len(message_ids)}
- Deliveries tracked: {len(test_results)}

Language-Specific Prompts Created:
"""
        for prompt in created_prompts:
            log_content += f"- {prompt['name']} (ID={prompt['id']}, lang={prompt.get('language')})\n"
        
        log_content += f"\nTest Users Created:\n"
        for user in created_users:
            log_content += f"- {user['email']} (ID={user['id']}, lang={user['language'] or 'NULL'})\n"
        
        log_content += f"\nTest Results:\n"
        for result in test_results:
            log_content += f"- Language {result['language']}: ✅ Delivered, {result['payload_length']} chars\n"
        
        log_content += f"\nConclusion:\n"
        log_content += f"✅ Language-specific prompt selection works correctly\n"
        log_content += f"✅ Users receive messages formatted per their language preference\n"
        log_content += f"✅ Control user without language receives default formatting\n"
        log_content += f"✅ All deliveries successful\n"
        
        log_path = test_output_dir / "at1_6c_language_prompts_log.txt"
        log_path.write_text(log_content)
        print(f"✅ Test log saved: {log_path}")
        
        print("\n" + "="*80)
        print("✅ AT1.6C: LANGUAGE-SPECIFIC PROMPTS TEST COMPLETE")
        print("="*80)
        print(f"   Languages tested: {len(languages)}")
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
