# @pytest.mark.req("UC-005")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
AT1.11: A2A natural language endpoint -> real message delivery

Validates:
- A2A `/notify/natural` accepts a command
- Creates a real message via API
- Message reaches a terminal delivery state (sent) within configured timeout

All values are config-driven via --env private/env-test-at111.
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


def _wait_for_delivery_state(
    api_client,
    message_id: int,
    *,
    max_wait: float,
    poll_interval: float,
) -> Dict[str, Any]:
    t0 = time.time()
    last_state: str | None = None
    last_delivery: Dict[str, Any] | None = None
    while time.time() - t0 < max_wait:
        r = api_client.get(f"/messages/{message_id}/deliveries")
        assert r.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {r.status_code} {r.text[:200]}"
        deliveries = r.json()
        # Response shape varies across endpoints/tests; support common forms:
        # - {"items": [..]}
        # - {"deliveries": [..]}
        # - [..]
        if isinstance(deliveries, dict) and isinstance(deliveries.get("items"), list):
            items = deliveries["items"]
        elif isinstance(deliveries, dict) and isinstance(deliveries.get("deliveries"), list):
            items = deliveries["deliveries"]
        elif isinstance(deliveries, list):
            items = deliveries
        else:
            items = []

        if items:
            last_delivery = items[0] if isinstance(items[0], dict) else None
            if last_delivery:
                last_state = str(last_delivery.get("state") or last_delivery.get("status") or "").lower()
                if last_state in ("sent", "delivered"):
                    return last_delivery
                if last_state in ("failed", "soft_failed", "cancelled", "canceled"):
                    pytest.fail(f"❌ Delivery reached terminal failure state: {last_state}")

        # Progress output (RULES.md: forensic validation)
        elapsed = time.time() - t0
        if int(elapsed) % max(int(poll_interval), 1) == 0:
            print(f"[{elapsed:6.1f}s] message {message_id}: delivery_state={last_state or 'none'}")

        time.sleep(poll_interval)

    pytest.fail(f"❌ Timed out waiting for delivery (last_state={last_state!r}, waited {max_wait}s)")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_11a_a2a_notify_natural_creates_message_and_sends(
    api_client,
    a2a_base_url: str,
    test_config,
    request,
    at111_max_wait: float,
    at111_poll_interval: float,
    at111_a2a_timeout: float,
    smtp_channel_name: str,
):
    run_id = str(int(time.time()))
    user_email_base = _require_str(test_config, "test.at111.user_email_base")
    user_role = _require_str(test_config, "test.at111.user_role")
    user_type = _require_str(test_config, "test.at111.user_type")
    username = f"at111_user_{run_id}"
    email = (
        user_email_base.replace("@", f"+at111{run_id}@")
        if "@" in user_email_base
        else user_email_base
    )
    password = f"pw_{run_id}"
    display_name = _require_str(test_config, "test.at111.user_display_name")
    command_template = _require_str(test_config, "test.at111.command_template")

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
                # user routes are mounted under /api
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Step 1: Create user (so A2A resolver can map display name -> email)
    create_u = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": display_name,
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert create_u.status_code in (200, 201), f"POST /api/v1/users failed: {create_u.status_code} {create_u.text[:200]}"
    js = create_u.json()
    user_id = js.get("id") or js.get("user_id")
    assert user_id, f"Unexpected create user response: {js}"
    created_user_id = int(user_id)

    # Step 2: Call A2A natural endpoint (explicit channels to avoid hardcoded defaults)
    command = command_template.format(display_name=display_name, run_id=run_id)
    a2a = httpx.post(
        f"{a2a_base_url}/notify/natural",
        json={"command": command, "channels": [smtp_channel_name]},
        timeout=at111_a2a_timeout,
    )
    assert a2a.status_code == 200, f"A2A /notify/natural failed: {a2a.status_code} {a2a.text[:200]}"
    payload = a2a.json()
    assert bool(payload.get("success")) is True, f"A2A returned failure: {payload}"
    created_message_id = int(payload.get("message_id"))
    assert created_message_id > 0

    # Step 3: Verify message exists and delivery completes
    msg = api_client.get(f"/messages/{created_message_id}", params={"format": "json"})
    assert msg.status_code == 200, f"GET /messages/{{id}} failed: {msg.status_code} {msg.text[:200]}"
    m = msg.json()
    assert int(m.get("id")) == created_message_id

    delivery = _wait_for_delivery_state(
        api_client,
        created_message_id,
        max_wait=at111_max_wait,
        poll_interval=at111_poll_interval,
    )
    assert str(delivery.get("state") or "").lower() in ("sent", "delivered")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
