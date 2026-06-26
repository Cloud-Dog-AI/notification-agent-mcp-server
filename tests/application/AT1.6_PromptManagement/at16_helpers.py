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
AT1.6 Test Helpers (API-only)

Purpose:
- Centralise common AT1.6 test logic
- Enforce RULES.md: no hardcoding, API-only operations, env required
- Reduce duplication across AT1.6 tests
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Sequence

import httpx


TERMINAL_DELIVERY_STATES = {
    "sent",
    "delivered",
    "failed",
    "hard_failed",
    "ttl_expired",
    "cancelled",
}


def require_env_loaded(test_config: Any, marker_key: str = "test.at16_env_loaded") -> None:
    if not test_config.get(marker_key):
        raise AssertionError(
            f"❌ CRITICAL: AT1.6 env file not loaded! Use --env private/env-test-at16 (missing {marker_key})"
        )


def cfg_required(test_config: Any, key: str) -> str:
    value = test_config.get(key)
    if value is None or value == "":
        raise AssertionError(f"❌ HARD FAIL: {key} not configured")
    return value


def cfg_json_required(test_config: Any, key: str) -> Any:
    raw = cfg_required(test_config, key)
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def api_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-Key": api_key}


def unique_suffix() -> str:
    return str(int(time.time()))[-6:]


def plus_address(email: str, suffix: str) -> str:
    """
    Create a unique email address without hardcoding new domains.
    Uses plus addressing when possible: local+suffix@domain
    """
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if f"+{suffix}" in local:
        return email
    return f"{local}+{suffix}@{domain}"


def _ok(status_code: int) -> bool:
    return status_code in (200, 201, 204, 409, 404)


def api_post_json(client: httpx.Client, api_base_url: str, api_key: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = client.post(f"{api_base_url}{path}", headers=api_headers(api_key), json=payload)
    if resp.status_code not in (200, 201):
        raise AssertionError(f"❌ POST {path} failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def api_get_json(client: httpx.Client, api_base_url: str, api_key: str, path: str) -> Any:
    resp = client.get(f"{api_base_url}{path}", headers=api_headers(api_key))
    if resp.status_code != 200:
        raise AssertionError(f"❌ GET {path} failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def api_delete(client: httpx.Client, api_base_url: str, api_key: str, path: str) -> None:
    resp = client.delete(f"{api_base_url}{path}", headers=api_headers(api_key))
    if not _ok(resp.status_code):
        raise AssertionError(f"❌ DELETE {path} failed: {resp.status_code} {resp.text[:200]}")


def wait_for_delivery(
    client: httpx.Client,
    api_base_url: str,
    api_key: str,
    message_id: int,
    *,
    max_wait_seconds: float,
    poll_interval_seconds: float,
    progress_interval_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Poll /messages/{id}/deliveries until terminal state or timeout.
    Prints progress every progress_interval_seconds.
    """
    start = time.time()
    next_progress = start
    last_state: Optional[str] = None

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait_seconds:
            raise AssertionError(
                f"❌ Timeout waiting for delivery: message_id={message_id}, last_state={last_state}, waited={elapsed:.1f}s"
            )

        resp = client.get(
            f"{api_base_url}/messages/{message_id}/deliveries",
            headers=api_headers(api_key),
        )
        if resp.status_code != 200:
            raise AssertionError(f"❌ Failed to fetch deliveries: {resp.status_code} message_id={message_id}")

        data = resp.json()
        items = data.get("items") if isinstance(data, dict) else None
        if not items:
            state = None
        else:
            delivery = items[0]
            state = str(delivery.get("state") or "").lower() or None

        now = time.time()
        if now >= next_progress:
            print(f"[{elapsed:6.1f}s] message {message_id}: state={state or 'none'}")
            next_progress = now + progress_interval_seconds

        if state and state in TERMINAL_DELIVERY_STATES:
            return items[0]

        if state != last_state:
            last_state = state

        time.sleep(poll_interval_seconds)


def payload_to_text(personalised_payload: Any) -> str:
    if personalised_payload is None:
        return ""
    if isinstance(personalised_payload, str):
        return personalised_payload
    try:
        return json.dumps(personalised_payload)
    except Exception:
        return str(personalised_payload)

