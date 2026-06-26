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
AT1.14: Natural Language Command Test

Validates:
- User resolution via A2A `/notify/natural`
- Group resolution via A2A `/notify/natural` and API-side group expansion (group:<name>)

All values are config-driven via --env private/env-test-at114.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx
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
    pytest.fail("No enabled SMTP channel found via API /channels (required for AT1.14)")


def _wait_for_deliveries(
    api_client,
    message_id: int,
    *,
    expected_count: int,
    max_wait: float,
    poll_interval: float,
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
            state_counts: Dict[str, int] = {}
            for d in deliveries:
                if not isinstance(d, dict):
                    continue
                dest = str(d.get("destination") or "")
                st = str(d.get("state") or d.get("status") or "").lower()
                last_states[dest] = st
                state_counts[st] = state_counts.get(st, 0) + 1

            elapsed = time.time() - t0
            print(f"[{elapsed:6.1f}s] deliveries={len(deliveries)} states={state_counts}")

            if state_counts.get("sent", 0) + state_counts.get("delivered", 0) == expected_count:
                return [d for d in deliveries if isinstance(d, dict)]

            if any(s in ("hard_failed", "soft_failed", "failed", "cancelled", "canceled") for s in state_counts.keys()):
                pytest.fail(f"❌ One or more deliveries failed: states={state_counts}")

        time.sleep(poll_interval)

    pytest.fail(f"❌ Timed out waiting for deliveries (expected={expected_count}, last_states={last_states})")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_14a_a2a_natural_to_user_creates_message_and_sends(
    api_client,
    a2a_base_url: str,
    test_config,
    request,
    at114_max_wait: float,
    at114_poll_interval: float,
    at114_a2a_timeout: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at114.user_email_base")
    user_role = _require_str(test_config, "test.at114.user_role")
    user_type = _require_str(test_config, "test.at114.user_type")
    user_password = _require_str(test_config, "test.at114.user_password")
    display_name_base = _require_str(test_config, "test.at114.user_display_name")
    command_template = _require_str(test_config, "test.at114.command_user_template")

    created_user_id: int | None = None
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    display_name = f"{display_name_base} {run_id}"
    email = user_email_base.replace("@", f"+at114a{run_id}@") if "@" in user_email_base else f"{user_email_base}+at114a{run_id}"
    username = f"at114_user_{run_id}"

    create_u = api_client.post(
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
    assert create_u.status_code in (200, 201), f"POST /api/v1/users failed: {create_u.status_code} {create_u.text[:200]}"
    js = create_u.json()
    assert bool(js.get("success")) is True, f"Unexpected create user response: {js}"
    created_user_id = int(js.get("user_id"))

    command = command_template.format(display_name=display_name, run_id=run_id)
    a2a = httpx.post(
        f"{a2a_base_url}/notify/natural",
        json={"command": command, "channels": [smtp_channel_name]},
        timeout=at114_a2a_timeout,
    )
    assert a2a.status_code == 200, f"A2A /notify/natural failed: {a2a.status_code} {a2a.text[:200]}"
    payload = a2a.json()
    assert bool(payload.get("success")) is True, f"A2A returned failure: {payload}"
    created_message_id = int(payload.get("message_id"))

    deliveries = _wait_for_deliveries(
        api_client,
        created_message_id,
        expected_count=1,
        max_wait=at114_max_wait,
        poll_interval=at114_poll_interval,
    )
    assert len(deliveries) == 1
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_14b_a2a_natural_to_group_expands_members_and_sends(
    api_client,
    a2a_base_url: str,
    test_config,
    request,
    at114_max_wait: float,
    at114_poll_interval: float,
    at114_a2a_timeout: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at114.user_email_base")
    user_role = _require_str(test_config, "test.at114.user_role")
    user_type = _require_str(test_config, "test.at114.user_type")
    user_password = _require_str(test_config, "test.at114.user_password")
    display_name_base = _require_str(test_config, "test.at114.user_display_name")
    group_name_base = _require_str(test_config, "test.at114.group_name_base")
    group_description = _require_str(test_config, "test.at114.group_description")
    group_member_role = _require_str(test_config, "test.at114.group_member_role")
    command_template = _require_str(test_config, "test.at114.command_group_template")

    created_user_id: int | None = None
    created_group_id: int | None = None
    created_message_id: int | None = None

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_group_id is not None:
            try:
                # No delete endpoint; disable the group.
                api_client.put(f"/api/v1/groups/{created_group_id}", json={"enabled": False})
            except Exception:
                pass
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Create user
    display_name = f"{display_name_base} {run_id}"
    email = user_email_base.replace("@", f"+at114b{run_id}@") if "@" in user_email_base else f"{user_email_base}+at114b{run_id}"
    username = f"at114_group_user_{run_id}"

    create_u = api_client.post(
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
    assert create_u.status_code in (200, 201), f"POST /api/v1/users failed: {create_u.status_code} {create_u.text[:200]}"
    created_user_id = int(create_u.json().get("user_id"))

    # Create group
    group_name = f"{group_name_base}_{run_id}"
    cg = api_client.post("/api/v1/groups", json={"name": group_name, "description": group_description})
    assert cg.status_code in (200, 201), f"POST /api/v1/groups failed: {cg.status_code} {cg.text[:200]}"
    created_group_id = int(cg.json().get("group_id"))

    # Add member
    addm = api_client.post(f"/api/v1/groups/{created_group_id}/members", json={"user_id": created_user_id, "role": group_member_role})
    assert addm.status_code in (200, 201), f"POST /api/v1/groups/{{id}}/members failed: {addm.status_code} {addm.text[:200]}"

    # Call A2A with group command
    command = command_template.format(group_name=group_name, run_id=run_id)
    a2a = httpx.post(
        f"{a2a_base_url}/notify/natural",
        json={"command": command, "channels": [smtp_channel_name]},
        timeout=at114_a2a_timeout,
    )
    assert a2a.status_code == 200, f"A2A /notify/natural failed: {a2a.status_code} {a2a.text[:200]}"
    payload = a2a.json()
    assert bool(payload.get("success")) is True, f"A2A returned failure: {payload}"
    created_message_id = int(payload.get("message_id"))

    deliveries = _wait_for_deliveries(
        api_client,
        created_message_id,
        expected_count=1,
        max_wait=at114_max_wait,
        poll_interval=at114_poll_interval,
    )
    assert len(deliveries) == 1
    assert str(deliveries[0].get("destination") or "") == email

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
