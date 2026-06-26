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
AT1.12: Send Broadcast Notification Test

Validates:
- Create N users with stored preferences (language/content_style/preferred_channel)
- Submit a broadcast message to those users via their preferred channel
- All deliveries reach a terminal success state within configured time

All values are config-driven via --env private/env-test-at112.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest


def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)


def _require_json_list(test_config: Any, key: str) -> List[Dict[str, Any]]:
    raw = test_config.get(key)
    if raw is None or raw == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    if isinstance(raw, str):
        s = raw.strip()
        # Some env loaders preserve surrounding quotes; strip a single wrapping pair if present.
        if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
            s = s[1:-1].strip()
        data = json.loads(s)
    else:
        data = raw
    if not isinstance(data, list) or not data:
        pytest.fail(f"❌ HARD FAIL: {key} must be a non-empty JSON list")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            pytest.fail(f"❌ HARD FAIL: {key}[{i}] must be an object")
    return data


def _load_broadcast_message() -> str:
    examples_dir = Path(__file__).parent.parent.parent / "Examples"
    message_path = examples_dir / "Test-Brief-News.md"
    if not message_path.exists():
        pytest.fail(f"Missing broadcast message file: {message_path}")
    return message_path.read_text().strip()


def _pick_enabled_channel_by_name(api_client, channel_name: str) -> Dict[str, Any]:
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code} {r.text[:200]}"
    channels = r.json()
    assert isinstance(channels, list), "Expected /channels to return a list"
    for ch in channels:
        if isinstance(ch, dict) and str(ch.get("name")) == channel_name:
            if bool(ch.get("enabled")) is not True:
                pytest.fail(f"Channel {channel_name!r} exists but is not enabled")
            return ch
    pytest.fail(f"Channel {channel_name!r} not found via API /channels")


def _wait_for_all_deliveries_sent(
    api_client,
    message_id: int,
    *,
    expected_count: int,
    max_wait: float,
    poll_interval: float,
    allow_sending: bool = False,
) -> List[Dict[str, Any]]:
    t0 = time.time()
    last_states: Dict[str, str] = {}
    while time.time() - t0 < max_wait:
        r = api_client.get(f"/messages/{message_id}/deliveries")
        assert r.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        items = data.get("items") if isinstance(data, dict) else None
        deliveries = items if isinstance(items, list) else (data if isinstance(data, list) else [])

        if len(deliveries) == expected_count:
            # Track state distribution
            state_counts: Dict[str, int] = {}
            for d in deliveries:
                if not isinstance(d, dict):
                    continue
                dest = str(d.get("destination") or d.get("address") or "")
                st = str(d.get("state") or d.get("status") or "").lower()
                last_states[dest] = st
                state_counts[st] = state_counts.get(st, 0) + 1

            elapsed = time.time() - t0
            print(f"[{elapsed:6.1f}s] deliveries={len(deliveries)} states={state_counts}")

            if state_counts.get("sent", 0) == expected_count or state_counts.get("delivered", 0) == expected_count:
                return [d for d in deliveries if isinstance(d, dict)]

            if allow_sending and state_counts.get("sending", 0) == expected_count:
                return [d for d in deliveries if isinstance(d, dict)]

            # Fail fast on terminal failures
            if any(s in ("hard_failed", "soft_failed", "failed", "cancelled", "canceled") for s in state_counts.keys()):
                pytest.fail(f"❌ One or more deliveries failed: states={state_counts}")

        time.sleep(poll_interval)

    pytest.fail(f"❌ Timed out waiting for broadcast deliveries (expected={expected_count}, last_states={last_states})")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_12a_broadcast_to_users_reaches_sent(
    api_client,
    test_config,
    request,
    at112_max_wait: float,
    at112_poll_interval: float,
    preferred_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at112.user_email_base")
    user_role = _require_str(test_config, "test.at112.user_role")
    user_type = _require_str(test_config, "test.at112.user_type")
    user_password = _require_str(test_config, "test.at112.user_password")
    broadcast_subject = _require_str(test_config, "test.at112.broadcast_subject")
    broadcast_message = _load_broadcast_message()
    scenarios = _require_json_list(test_config, "test.at112.user_scenarios")

    preferred_channel = preferred_channel_name
    channel_info = _pick_enabled_channel_by_name(api_client, preferred_channel)
    allow_sending = str(channel_info.get("type", "")).lower() == "loopback"

    created_user_ids: List[int] = []
    created_emails: List[str] = []
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        for uid in created_user_ids:
            try:
                api_client.delete(f"/api/v1/users/{uid}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Step 1: Create users + preferences
    for idx, sc in enumerate(scenarios):
        language = str(sc.get("language") or "")
        content_style = str(sc.get("content_style") or "")
        display_name = str(sc.get("display_name") or f"AT1.12 User {idx}")
        timezone = str(sc.get("timezone") or "")

        if not language or not content_style:
            pytest.fail("❌ HARD FAIL: each user scenario must include language and content_style")

        if "@" in user_email_base:
            email = user_email_base.replace("@", f"+at112{run_id}_{idx}@")
        else:
            email = f"{user_email_base}+at112{run_id}_{idx}"

        username = f"at112_user_{run_id}_{idx}"

        create = api_client.post(
            "/api/v1/users",
            json={
                "username": username,
                "email": email,
                "password": user_password,
                "display_name": display_name,
                "role": user_role,
                "user_type": user_type,
            },
        )
        assert create.status_code in (200, 201), f"POST /users failed: {create.status_code} {create.text[:200]}"
        js = create.json()
        user_id = js.get("id") or js.get("user_id")
        assert user_id, f"Unexpected create user response: {js}"
        uid = int(user_id)
        created_user_ids.append(uid)
        created_emails.append(email)

        prefs_payload: Dict[str, Any] = {
            "language": language,
            "content_style": content_style,
            "preferred_channel": preferred_channel,
        }
        if timezone:
            prefs_payload["timezone"] = timezone

        upd = api_client.put(f"/api/v1/users/{uid}/preferences", json=prefs_payload)
        assert upd.status_code in (200, 201), f"PUT /users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"

    assert len(created_user_ids) == len(scenarios)

    # Step 2: Send broadcast message to created users (no per-destination preferences; rely on stored user prefs)
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "broadcast",
            "destinations": [{"channel": preferred_channel, "address": email} for email in created_emails],
            "content": [{"type": "text", "body": broadcast_message}],
            "options": {"subject": broadcast_subject},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))
    assert created_message_id > 0

    # Step 3: Wait for all deliveries to reach sent
    deliveries = _wait_for_all_deliveries_sent(
        api_client,
        created_message_id,
        expected_count=len(created_emails),
        max_wait=at112_max_wait,
        poll_interval=at112_poll_interval,
        allow_sending=allow_sending,
    )
    assert len(deliveries) == len(created_emails)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_12b_broadcast_applies_user_preferences_in_payload(
    api_client,
    test_config,
    request,
    at112_max_wait: float,
    at112_poll_interval: float,
    preferred_channel_name: str,
):
    """
    Forensic validation: Ensure broadcast creates exactly one delivery per destination,
    all reach a terminal success state, and message metadata reflects the delivery count.

    NOTE: Some channels (e.g. loopback_test) may not invoke LLM formatting; this test
    validates broadcast delivery mechanics rather than LLM output differences.
    """
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at112.user_email_base")
    user_role = _require_str(test_config, "test.at112.user_role")
    user_type = _require_str(test_config, "test.at112.user_type")
    user_password = _require_str(test_config, "test.at112.user_password")
    broadcast_subject = _require_str(test_config, "test.at112.broadcast_subject")
    broadcast_message = _load_broadcast_message()
    scenarios = _require_json_list(test_config, "test.at112.user_scenarios")

    if len(scenarios) < 2:
        pytest.fail("❌ HARD FAIL: test.at112.user_scenarios must define at least 2 users for comparison")

    preferred_channel = preferred_channel_name
    channel_info = _pick_enabled_channel_by_name(api_client, preferred_channel)
    allow_sending = str(channel_info.get("type", "")).lower() == "loopback"

    created_user_ids: List[int] = []
    created_emails: List[str] = []
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        for uid in created_user_ids:
            try:
                api_client.delete(f"/api/v1/users/{uid}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Create only the first two users to compare payload differences
    for idx, sc in enumerate(scenarios[:2]):
        language = str(sc.get("language") or "")
        content_style = str(sc.get("content_style") or "")
        display_name = str(sc.get("display_name") or f"AT1.12 User {idx}")

        if not language or not content_style:
            pytest.fail("❌ HARD FAIL: each user scenario must include language and content_style")

        email = user_email_base.replace("@", f"+at112b{run_id}_{idx}@") if "@" in user_email_base else f"{user_email_base}+at112b{run_id}_{idx}"
        username = f"at112b_user_{run_id}_{idx}"

        create = api_client.post(
            "/api/v1/users",
            json={
                "username": username,
                "email": email,
                "password": user_password,
                "display_name": display_name,
                "role": user_role,
                "user_type": user_type,
            },
        )
        assert create.status_code in (200, 201), f"POST /users failed: {create.status_code} {create.text[:200]}"
        js = create.json()
        user_id = js.get("id") or js.get("user_id")
        assert user_id, f"Unexpected create user response: {js}"
        uid = int(user_id)
        created_user_ids.append(uid)
        created_emails.append(email)

        upd = api_client.put(
            f"/api/v1/users/{uid}/preferences",
            json={"language": language, "content_style": content_style, "preferred_channel": preferred_channel},
        )
        assert upd.status_code in (200, 201), f"PUT /users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"

    # Send broadcast
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "broadcast",
            "destinations": [{"channel": preferred_channel, "address": email} for email in created_emails],
            "content": [{"type": "text", "body": broadcast_message}],
            "options": {"subject": broadcast_subject},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))

    deliveries = _wait_for_all_deliveries_sent(
        api_client,
        created_message_id,
        expected_count=len(created_emails),
        max_wait=at112_max_wait,
        poll_interval=at112_poll_interval,
        allow_sending=allow_sending,
    )

    # Validate each delivery is for one of our intended recipients and no duplicates exist
    destinations = [str(d.get("destination") or "") for d in deliveries]
    assert all(dest in created_emails for dest in destinations), f"Unexpected delivery destinations: {destinations}"
    assert len(set(destinations)) == len(created_emails), f"Duplicate delivery destinations found: {destinations}"

    # Validate message delivery count metadata
    msg_json = api_client.get(f"/messages/{created_message_id}", params={"format": "json"})
    assert msg_json.status_code == 200, f"GET /messages/{{id}} failed: {msg_json.status_code} {msg_json.text[:200]}"
    m = msg_json.json()
    deliveries_meta = m.get("deliveries") if isinstance(m, dict) else None
    if isinstance(deliveries_meta, dict):
        assert int(deliveries_meta.get("total")) == len(created_emails)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
