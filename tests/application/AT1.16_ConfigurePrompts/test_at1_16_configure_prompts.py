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
AT1.16: Configure LLM Prompts Test

Focus: prompt configuration via API + selection at runtime.

Validates:
- Creating keyword and language prompts via `/prompts`
- Assigning user keyword / language preferences via `/api/v1/users/*`
- Sending a message uses the configured prompt (marker present in personalised payload)

All values are config-driven via --env private/env-test-at116.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

import pytest


def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)


def _pick_enabled_smtp_channel_name(api_client) -> str:
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code} {r.text[:200]}"
    channels = r.json()
    assert isinstance(channels, list), "Expected /channels to return a list"
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        if str(ch.get("type", "")).lower() == "smtp" and bool(ch.get("enabled")) is True:
            name = ch.get("name")
            if name:
                return str(name)
    pytest.fail("No enabled SMTP channel found via API /channels (required for AT1.16)")


def _wait_for_delivery_sent(
    api_client,
    message_id: int,
    *,
    max_wait: float,
    poll_interval: float,
) -> Dict[str, Any]:
    t0 = time.time()
    last_state: str | None = None
    while time.time() - t0 < max_wait:
        r = api_client.get(f"/messages/{message_id}/deliveries")
        assert r.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else None
        deliveries = items if isinstance(items, list) else (data if isinstance(data, list) else [])
        if deliveries and isinstance(deliveries[0], dict):
            d = deliveries[0]
            last_state = str(d.get("state") or d.get("status") or "").lower()
            elapsed = time.time() - t0
            print(f"[{elapsed:6.1f}s] message {message_id}: delivery_state={last_state}")
            if last_state in ("sent", "delivered"):
                return d
            if last_state in ("hard_failed", "soft_failed", "failed", "cancelled", "canceled"):
                pytest.fail(f"❌ Delivery reached terminal failure state: {last_state}")
        time.sleep(poll_interval)
    pytest.fail(f"❌ Timed out waiting for delivery (last_state={last_state!r}, waited {max_wait}s)")


def _payload_body_and_subject(delivery: Dict[str, Any]) -> tuple[str, str]:
    pp = delivery.get("personalised_payload")
    assert pp is not None, "❌ personalised_payload missing on delivery"
    pp_obj = json.loads(pp) if isinstance(pp, str) else pp
    if isinstance(pp_obj, dict):
        return str(pp_obj.get("body") or ""), str(pp_obj.get("subject") or "")
    if isinstance(pp_obj, list) and pp_obj and isinstance(pp_obj[0], dict):
        # Some channels return content blocks; no subject.
        return str(pp_obj[0].get("body") or ""), ""
    pytest.fail("❌ Unexpected personalised_payload shape")


def _delivery_prompt_used(delivery: Dict[str, Any]) -> str | None:
    metadata = delivery.get("metadata_json")
    if not metadata:
        return None
    try:
        meta_obj = json.loads(metadata) if isinstance(metadata, str) else metadata
    except Exception:
        return None
    if isinstance(meta_obj, dict):
        return meta_obj.get("prompt_used")
    return None


def _best_effort_delete(api_client, path: str) -> None:
    try:
        api_client.delete(path)
    except Exception:
        pass
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-001")


def test_at1_16c_llm_unavailable_uses_fallback_formatting(
    api_client,
    test_config,
    request,
    at116_max_wait: float,
    at116_poll_interval: float,
):
    """
    BO1.3 evidence test:
    Force LLM endpoint unreachable at runtime and verify delivery still completes
    with non-empty personalised payload (fallback formatting path).
    """
    run_id = str(int(time.time()))
    created_user_id: int | None = None
    created_channel_id: int | None = None
    created_message_id: int | None = None

    # Save current config values and restore in finalizer.
    q = api_client.post(
        "/config/query",
        json={"keys": ["llm.base_url", "llm.query_timeout", "llm.timeout", "api_server.port"]},
    )
    assert q.status_code == 200, f"POST /config/query failed: {q.status_code} {q.text[:200]}"
    current = q.json() if isinstance(q.json(), dict) else {}

    original_base_url = str(current.get("llm.base_url") or "")
    original_query_timeout = current.get("llm.query_timeout")
    original_timeout = current.get("llm.timeout")
    api_port = int(current.get("api_server.port") or test_config.get("api_server.port") or 8004)
    unreachable_port = api_port + 10000
    unreachable_base_url = f"http://127.0.0.1:{unreachable_port}"

    def _cleanup() -> None:
        if created_message_id is not None:
            _best_effort_delete(api_client, f"/messages/{created_message_id}")
        if created_user_id is not None:
            _best_effort_delete(api_client, f"/api/v1/users/{created_user_id}")
        if created_channel_id is not None:
            _best_effort_delete(api_client, f"/channels/{created_channel_id}")

        restore_updates: Dict[str, Any] = {"llm.base_url": original_base_url}
        if original_query_timeout is not None:
            restore_updates["llm.query_timeout"] = original_query_timeout
        if original_timeout is not None:
            restore_updates["llm.timeout"] = original_timeout
        try:
            api_client.post("/config/update", json={"updates": restore_updates, "persist": False})
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    # Force LLM runtime unavailability for this test window.
    upd = api_client.post(
        "/config/update",
        json={
            "updates": {
                "llm.base_url": unreachable_base_url,
                "llm.query_timeout": 1,
                "llm.timeout": 1,
            },
            "persist": False,
        },
    )
    assert upd.status_code == 200, f"POST /config/update failed: {upd.status_code} {upd.text[:200]}"

    # Create loopback channel (config-driven endpoint, no external dependency).
    loopback_name = f"at116_loopback_fallback_{run_id}"
    cr = api_client.post(
        "/channels",
        json={
            "name": loopback_name,
            "type": "loopback",
            "enabled": True,
            "config": {"base_url": str(api_client.base_url).rstrip("/")},
        },
    )
    assert cr.status_code in (200, 201), f"POST /channels failed: {cr.status_code} {cr.text[:200]}"
    created_channel_id = int(cr.json().get("id"))

    # Create user and send message requiring formatting.
    user_email_base = _require_str(test_config, "test.at116.user_email_base")
    user_password = _require_str(test_config, "test.at116.user_password")
    user_role = _require_str(test_config, "test.at116.user_role")
    user_type = _require_str(test_config, "test.at116.user_type")
    email = user_email_base.replace("@", f"+at116c{run_id}@") if "@" in user_email_base else f"{user_email_base}+at116c{run_id}"

    cu = api_client.post(
        "/api/v1/users",
        json={
            "username": f"at116_fallback_user_{run_id}",
            "email": email,
            "password": user_password,
            "display_name": f"AT1.16 Fallback User {run_id}",
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert cu.status_code in (200, 201), f"POST /api/v1/users failed: {cu.status_code} {cu.text[:200]}"
    created_user_id = int(cu.json().get("user_id"))

    marker = f"AT116-FALLBACK-{run_id}"
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": loopback_name, "address": email, "preferences": {"language": "fr", "content_style": "html"}}],
            "content": [{"type": "text", "body": f"{marker} :: fallback validation message body"}],
            "options": {"subject": f"AT1.16 fallback {run_id}"},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))

    # BO1.3 validation target: fallback formatting should still produce payload
    # even if downstream adapter delivery fails for unrelated reasons.
    t0 = time.time()
    delivery: Dict[str, Any] | None = None
    while time.time() - t0 < min(at116_max_wait, 120.0):
        dr = api_client.get(f"/messages/{created_message_id}/deliveries")
        assert dr.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {dr.status_code} {dr.text[:200]}"
        data = dr.json()
        items = data.get("items") if isinstance(data, dict) else None
        deliveries = items if isinstance(items, list) else (data if isinstance(data, list) else [])
        if deliveries and isinstance(deliveries[0], dict):
            candidate = deliveries[0]
            if candidate.get("personalised_payload"):
                delivery = candidate
                break
        time.sleep(at116_poll_interval)

    assert delivery is not None, "❌ Fallback path did not produce personalised_payload"
    body, _subject = _payload_body_and_subject(delivery)

    assert body.strip(), "❌ Fallback path produced empty personalised payload"
    assert marker in body, "❌ Expected original marker to survive fallback formatting path"
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-001")


def test_at1_16a_keyword_prompt_configuration_and_selection(
    api_client,
    test_config,
    request,
    at116_max_wait: float,
    at116_poll_interval: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at116.user_email_base")
    user_role = _require_str(test_config, "test.at116.user_role")
    user_type = _require_str(test_config, "test.at116.user_type")
    user_password = _require_str(test_config, "test.at116.user_password")
    keyword = _require_str(test_config, "test.at116.keyword")
    keyword_prompt_name_base = _require_str(test_config, "test.at116.keyword_prompt_name")
    keyword_prompt_text = _require_str(test_config, "test.at116.keyword_prompt_text")
    marker = _require_str(test_config, "test.at116.keyword_marker")
    channel_type = _require_str(test_config, "test.at116.channel_type")
    keyword_prompt_priority = int(_require_str(test_config, "test.at116.keyword_prompt_priority"))
    message_subject = _require_str(test_config, "test.at116.subject")
    message_body = _require_str(test_config, "test.at116.message")

    created_user_id: int | None = None
    created_prompt_id: int | None = None
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_prompt_id is not None:
            try:
                api_client.delete(f"/prompts/{created_prompt_id}")
            except Exception:
                pass
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Create keyword prompt
    keyword_prompt_name = f"{keyword_prompt_name_base}_{run_id}"
    pr = api_client.post(
        "/prompts",
        json={
            "name": keyword_prompt_name,
            "prompt_text": keyword_prompt_text,
            "channel_type": channel_type,
            "keyword": keyword,
            "priority": keyword_prompt_priority,
            "enabled": True,
        },
    )
    assert pr.status_code in (200, 201), f"POST /prompts failed: {pr.status_code} {pr.text[:200]}"
    created_prompt_id = int(pr.json().get("id"))

    # Create user
    email = user_email_base.replace("@", f"+at116a{run_id}@") if "@" in user_email_base else f"{user_email_base}+at116a{run_id}"
    username = f"at116_user_{run_id}"
    cu = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": user_password,
            "display_name": f"AT1.16 User {run_id}",
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert cu.status_code in (200, 201), f"POST /api/v1/users failed: {cu.status_code} {cu.text[:200]}"
    created_user_id = int(cu.json().get("user_id"))

    # Assign keyword
    kw = api_client.post(f"/api/v1/users/{created_user_id}/keywords", json={"keyword": keyword})
    assert kw.status_code in (200, 201), f"POST /api/v1/users/{{id}}/keywords failed: {kw.status_code} {kw.text[:200]}"

    # Send message (no destination prefs; rely on stored keyword -> prompt selection)
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": smtp_channel_name, "address": email}],
            "content": [{"type": "text", "body": message_body}],
            "options": {"subject": message_subject},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))

    delivery = _wait_for_delivery_sent(api_client, created_message_id, max_wait=at116_max_wait, poll_interval=at116_poll_interval)
    body, subject = _payload_body_and_subject(delivery)
    prompt_used = _delivery_prompt_used(delivery)

    if prompt_used:
        assert prompt_used == keyword_prompt_name, f"❌ Expected keyword prompt {keyword_prompt_name!r}, got {prompt_used!r}"
    else:
        assert marker in body, f"❌ Expected keyword prompt marker {marker!r} in body"
    assert marker not in subject, "❌ Marker must not appear in subject"
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-001")


def test_at1_16b_language_prompt_configuration_and_selection(
    api_client,
    test_config,
    request,
    at116_max_wait: float,
    at116_poll_interval: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at116.user_email_base")
    user_role = _require_str(test_config, "test.at116.user_role")
    user_type = _require_str(test_config, "test.at116.user_type")
    user_password = _require_str(test_config, "test.at116.user_password")
    language = _require_str(test_config, "test.at116.language")
    language_prompt_name_base = _require_str(test_config, "test.at116.language_prompt_name")
    language_prompt_text = _require_str(test_config, "test.at116.language_prompt_text")
    marker = _require_str(test_config, "test.at116.language_marker")
    channel_type = _require_str(test_config, "test.at116.channel_type")
    language_prompt_priority = int(_require_str(test_config, "test.at116.language_prompt_priority"))
    message_subject = _require_str(test_config, "test.at116.subject")
    message_body = _require_str(test_config, "test.at116.message")

    created_user_id: int | None = None
    created_prompt_id: int | None = None
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_prompt_id is not None:
            try:
                api_client.delete(f"/prompts/{created_prompt_id}")
            except Exception:
                pass
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Create language prompt
    language_prompt_name = f"{language_prompt_name_base}_{run_id}"
    pr = api_client.post(
        "/prompts",
        json={
            "name": language_prompt_name,
            "prompt_text": language_prompt_text,
            "channel_type": channel_type,
            "language": language,
            "priority": language_prompt_priority,
            "enabled": True,
        },
    )
    assert pr.status_code in (200, 201), f"POST /prompts failed: {pr.status_code} {pr.text[:200]}"
    created_prompt_id = int(pr.json().get("id"))

    # Create user
    email = user_email_base.replace("@", f"+at116b{run_id}@") if "@" in user_email_base else f"{user_email_base}+at116b{run_id}"
    username = f"at116_lang_user_{run_id}"
    cu = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": user_password,
            "display_name": f"AT1.16 Lang User {run_id}",
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert cu.status_code in (200, 201), f"POST /api/v1/users failed: {cu.status_code} {cu.text[:200]}"
    created_user_id = int(cu.json().get("user_id"))

    # Set language preference
    upd = api_client.put(f"/api/v1/users/{created_user_id}/preferences", json={"language": language, "preferred_channel": smtp_channel_name})
    assert upd.status_code in (200, 201), f"PUT /api/v1/users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"

    # Send message (no destination prefs)
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": smtp_channel_name, "address": email}],
            "content": [{"type": "text", "body": message_body}],
            "options": {"subject": message_subject},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))

    delivery = _wait_for_delivery_sent(api_client, created_message_id, max_wait=at116_max_wait, poll_interval=at116_poll_interval)
    body, subject = _payload_body_and_subject(delivery)
    prompt_used = _delivery_prompt_used(delivery)

    if prompt_used:
        assert prompt_used == language_prompt_name, f"❌ Expected language prompt {language_prompt_name!r}, got {prompt_used!r}"
    else:
        assert marker in body, f"❌ Expected language prompt marker {marker!r} in body"
    assert marker not in subject, "❌ Marker must not appear in subject"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
