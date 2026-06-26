# @pytest.mark.req("UC-004")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
AT1.13: Send Personalised Notification Test

Validates:
- Create a user with stored preferences (language/content_style/preferred_channel)
- Submit a personalised message to that user without per-destination preferences
- Delivery reaches sent/delivered and contains a personalised payload

All values are config-driven via --env private/env-test-at113.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

import pytest


def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)


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


def _wait_for_delivery_sent(api_client, message_id: int, *, max_wait: float, poll_interval: float) -> Dict[str, Any]:
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
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_13a_personalised_message_uses_stored_user_preferences(
    api_client,
    test_config,
    request,
    at113_max_wait: float,
    at113_poll_interval: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at113.user_email_base")
    user_role = _require_str(test_config, "test.at113.user_role")
    user_type = _require_str(test_config, "test.at113.user_type")
    user_password = _require_str(test_config, "test.at113.user_password")
    display_name = _require_str(test_config, "test.at113.user_display_name")
    pref_language = _require_str(test_config, "test.at113.pref_language")
    pref_content_style = _require_str(test_config, "test.at113.pref_content_style")
    message_subject = _require_str(test_config, "test.at113.subject")
    message_body = _require_str(test_config, "test.at113.message")
    preferred_channel = smtp_channel_name

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

    email = user_email_base.replace("@", f"+at113{run_id}@") if "@" in user_email_base else f"{user_email_base}+at113{run_id}"
    username = f"at113_user_{run_id}"

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
    assert create.status_code in (200, 201), f"POST /api/v1/users failed: {create.status_code} {create.text[:200]}"
    js = create.json()
    assert bool(js.get("success")) is True, f"Unexpected create user response: {js}"
    created_user_id = int(js.get("user_id"))

    upd = api_client.put(
        f"/api/v1/users/{created_user_id}/preferences",
        json={"language": pref_language, "content_style": pref_content_style, "preferred_channel": preferred_channel},
    )
    assert upd.status_code in (200, 201), f"PUT /api/v1/users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"

    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": preferred_channel, "address": email}],
            "content": [{"type": "text", "body": message_body}],
            "options": {"subject": message_subject},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))
    assert created_message_id > 0

    delivery = _wait_for_delivery_sent(
        api_client,
        created_message_id,
        max_wait=at113_max_wait,
        poll_interval=at113_poll_interval,
    )

    pp = delivery.get("personalised_payload")
    assert pp is not None, "❌ personalised_payload missing on delivery"
    if isinstance(pp, str):
        pp_obj = json.loads(pp)
    else:
        pp_obj = pp

    if isinstance(pp_obj, dict):
        body = str(pp_obj.get("body") or "")
        ctype = str(pp_obj.get("content_type") or "")
    elif isinstance(pp_obj, list) and pp_obj and isinstance(pp_obj[0], dict):
        # Some channels return content blocks directly; treat `type` as content style indicator.
        body = str(pp_obj[0].get("body") or "")
        ctype = str(pp_obj[0].get("content_type") or pp_obj[0].get("type") or "")
    else:
        pytest.fail("❌ Unexpected personalised_payload shape")

    assert body.strip() != "", "❌ Empty personalised body"
    # Validate content style preference is reflected.
    if pref_content_style.lower() == "html":
        assert "html" in ctype.lower() or ("<" in body and ">" in body), "❌ Expected HTML output for html preference"
    elif pref_content_style.lower() in ("text", "plain", "plain_text"):
        assert "html" not in body.lower(), "❌ Expected plain text output (no HTML tags)"
    else:
        # For non-standard styles, at least ensure content type is set.
        assert ctype.strip() != "", "❌ content_type missing"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
