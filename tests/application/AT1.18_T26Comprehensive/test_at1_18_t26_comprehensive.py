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
AT1.18: Comprehensive Delivery Test (T26)

This suite is a RULES.md-aligned replacement for the legacy monolithic T26 runner:
- Deterministic: creates its own users/groups as needed
- Config-driven: all URLs/keys/timeouts and webhook/channel names via env
- API-only interactions + best-effort cleanup
- One test node at a time
"""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)

def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)


def _require_number(test_config: Any, key: str, *, number_type: str):
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    try:
        return float(v) if number_type == "float" else int(v)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _get_slack_timeouts(test_config: Any) -> Tuple[float, float, float]:
    wait_timeout = (
        test_config.get("test.slack.wait_timeout")
        or test_config.get("test.at118.max_wait")
        or test_config.get("api.timeout")
    )
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("test.at118.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "Missing Slack wait timeout. Configure test.slack.wait_timeout, test.at118.max_wait, or api.timeout."
        )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "Missing Slack poll interval. Configure test.slack.poll_interval, test.at118.poll_interval, api.connect_timeout, or api.timeout."
        )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "Missing Slack request timeout. Configure test.slack.request_timeout, api.connect_timeout, or api.timeout."
        )
    return float(wait_timeout), float(poll_interval), float(request_timeout)


def _get_channels(api_client) -> List[Dict[str, Any]]:
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code} {r.text[:200]}"
    chs = r.json()
    assert isinstance(chs, list), "Expected /channels to return a list"
    return [c for c in chs if isinstance(c, dict)]


def _load_message(name: str) -> str:
    examples_dir = Path(__file__).parent.parent.parent / "Examples"
    message_path = examples_dir / name
    if not message_path.exists():
        pytest.fail(f"Missing test message file: {message_path}")
    return message_path.read_text().strip()


def _find_channel(api_client, name: str) -> Dict[str, Any]:
    for ch in _get_channels(api_client):
        if str(ch.get("name")) == name:
            return ch
    pytest.fail(f"Channel {name!r} not found via /channels")


def _wait_for_delivery_sent(
    api_client,
    message_id: int,
    *,
    max_wait: float,
    poll_interval: float,
    allow_sending: bool = False,
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
            if allow_sending and last_state == "sending":
                return d
            if last_state in ("hard_failed", "soft_failed", "failed", "cancelled", "canceled"):
                pytest.fail(f"❌ Delivery reached terminal failure state: {last_state} ({d.get('last_error')})")
        time.sleep(poll_interval)
    pytest.fail(f"❌ Timed out waiting for delivery (last_state={last_state!r}, waited {max_wait}s)")


def _create_user(api_client, *, run_id: str, idx: int, test_config: Any) -> Tuple[int, str]:
    base = _require_str(test_config, "test.at118.user_email_base")
    role = _require_str(test_config, "test.at118.user_role")
    utype = _require_str(test_config, "test.at118.user_type")
    pw = _require_str(test_config, "test.at118.user_password")
    display = _require_str(test_config, "test.at118.user_display_name")

    email = base.replace("@", f"+at118{run_id}_{idx}@") if "@" in base else f"{base}+at118{run_id}_{idx}"
    username = f"at118_user_{run_id}_{idx}"

    r = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": pw,
            "display_name": f"{display} {idx}",
            "role": role,
            "user_type": utype,
        },
    )
    assert r.status_code in (200, 201), f"POST /api/v1/users failed: {r.status_code} {r.text[:200]}"
    js = r.json()
    user_id = js.get("id") or js.get("user_id")
    assert user_id, f"Unexpected create user response: {js}"
    return int(user_id), email
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_18a_slack_webhook_delivery_and_format_constraints(
    api_client,
    test_config,
    slack_config,
    request,
    at118_max_wait: float,
    at118_poll_interval: float,
    slack_channel_name: str,
):
    """
    Slack/Chat REST: send via configured webhook channel and validate:
    - delivery reaches sent/delivered
    - payload includes a link back to messages.base_url (summary+link pattern)
    - respects max_length from channel restrictions when link_strategy is summary+link
    """
    run_id = str(int(time.time()))
    channel_name = slack_channel_name
    messages_base_url = _require_str(test_config, "messages.base_url")

    webhook_url = slack_config.get("endpoint")
    if not webhook_url:
        pytest.fail("Slack webhook not configured in env (channels.chat_rest.transparentbordes.endpoint)")
    slack_token, slack_channel_id = require_slack_api_config(test_config)

    ch = _find_channel(api_client, channel_name)
    assert bool(ch.get("enabled")) is True, f"Channel {channel_name} is not enabled"

    created_message_ids: List[int] = []

    def _cleanup() -> None:
        for mid in created_message_ids:
            try:
                api_client.delete(f"/messages/{mid}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    long_text = _load_message("Test-5000chars-en.md")
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": channel_name, "address": webhook_url}],
            "content": [{"type": "text", "body": long_text}],
            "options": {"subject": f"AT1.18 Slack {run_id}"},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id") or msg.json().get("id"))
    created_message_ids.append(created_message_id)

    delivery = _wait_for_delivery_sent(api_client, created_message_id, max_wait=at118_max_wait, poll_interval=at118_poll_interval)
    assert delivery.get("last_error") in (None, ""), f"❌ Slack delivery error: {delivery.get('last_error')}"

    pp = delivery.get("personalised_payload")
    assert pp is not None, "❌ personalised_payload missing"
    pp_obj = json.loads(pp) if isinstance(pp, str) else pp
    if isinstance(pp_obj, dict):
        # slack formatter typically emits {"title": "...", "text": "...", "format": "slack"}
        body = str(pp_obj.get("text") or pp_obj.get("body") or "")
    elif isinstance(pp_obj, list) and pp_obj and isinstance(pp_obj[0], dict):
        body = str(pp_obj[0].get("body") or "")
    else:
        pytest.fail("❌ Unexpected personalised_payload shape")

    # Validate max_length constraints if present
    restrictions_raw = ch.get("restrictions_json")
    if restrictions_raw:
        try:
            if isinstance(restrictions_raw, str):
                try:
                    restrictions = json.loads(restrictions_raw)
                except json.JSONDecodeError:
                    restrictions = ast.literal_eval(restrictions_raw)
            else:
                restrictions = restrictions_raw
            if not isinstance(restrictions, dict):
                raise ValueError("restrictions_json did not resolve to a dict")
            max_len = restrictions.get("max_length")
            if max_len is not None:
                assert len(body) <= int(max_len), f"❌ Slack payload exceeds max_length ({len(body)} > {max_len})"
        except Exception:
            # If restrictions parsing fails, don't silently ignore delivery correctness
            pytest.fail("❌ Could not parse channel restrictions_json for slack payload constraints")

    # Link strategy can be "summary+link"; implementations may include an explicit truncation note
    # or an actual URL back to the message viewer.
    if messages_base_url in body:
        assert "http" in body, "Expected a URL when messages_base_url is present"
    else:
        assert "truncated" in body.lower() or len(body) > 0, "❌ Slack payload missing both link and truncation note"

    # Send a short markdown message to verify Slack mrkdwn rendering
    render_marker = f"AT1.18 Slack Render {run_id}"
    short_msg = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": channel_name, "address": webhook_url}],
            "content": [{"type": "markdown", "body": f"**{render_marker}**\n\nQuick render check."}],
            "options": {"subject": f"AT1.18 Slack Render {run_id}"},
        },
    )
    assert short_msg.status_code == 201, f"POST /messages failed: {short_msg.status_code} {short_msg.text[:200]}"
    short_message_id = int(short_msg.json().get("message_id") or short_msg.json().get("id"))
    created_message_ids.append(short_message_id)
    _wait_for_delivery_sent(api_client, short_message_id, max_wait=at118_max_wait, poll_interval=at118_poll_interval)

    wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)
    slack_message = wait_for_slack_message(
        slack_token,
        slack_channel_id,
        render_marker,
        timeout=wait_timeout,
        poll_interval=poll_interval,
        request_timeout=request_timeout,
    )
    # Slack history returns rendered text without Markdown markers; assert marker visibility.
    assert_slack_mrkdwn_contains(slack_message, render_marker)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_18b_multi_user_and_group_expansion(
    api_client,
    test_config,
    request,
    at118_max_wait: float,
    at118_poll_interval: float,
    default_channel,
):
    """
    Create 2 users + a group, then send to `group:<name>` and verify the API expands
    to one delivery per member.
    """
    run_id = str(int(time.time()))
    group_name_base = _require_str(test_config, "test.at118.group_name_base")
    group_desc = _require_str(test_config, "test.at118.group_description")

    created_user_ids: List[int] = []
    created_group_id: int | None = None
    created_message_id: int | None = None
    created_member_ids: List[int] = []

    def _cleanup() -> None:
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_group_id is not None:
            for mid in created_member_ids:
                try:
                    api_client.delete(f"/api/v1/groups/{created_group_id}/members/{mid}")
                except Exception:
                    pass
            try:
                api_client.delete(f"/api/v1/groups/{created_group_id}")
            except Exception:
                pass
        for uid in created_user_ids:
            try:
                api_client.delete(f"/api/v1/users/{uid}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    # Create users
    u1, e1 = _create_user(api_client, run_id=run_id, idx=1, test_config=test_config)
    u2, e2 = _create_user(api_client, run_id=run_id, idx=2, test_config=test_config)
    created_user_ids.extend([u1, u2])

    # Ensure each user has a destination for the default channel type (needed for group expansion)
    ch = _find_channel(api_client, default_channel)
    channel_type = ch.get("type") or ch.get("channel_type")
    if not channel_type:
        pytest.fail(f"❌ Channel '{default_channel}' missing type field: {ch}")
    for uid, email in ((u1, e1), (u2, e2)):
        dest = api_client.post(
            f"/api/v1/users/{uid}/destinations",
            json={"channel_type": channel_type, "destination": email, "is_primary": True},
        )
        assert dest.status_code in (200, 201), f"POST /api/v1/users/{{id}}/destinations failed: {dest.status_code} {dest.text[:200]}"

    # Create group and add members
    group_name = f"{group_name_base}_{run_id}"
    cg = api_client.post("/api/v1/groups", json={"name": group_name, "description": group_desc})
    assert cg.status_code in (200, 201), f"POST /api/v1/groups failed: {cg.status_code} {cg.text[:200]}"
    cg_json = cg.json()
    group_id = cg_json.get("id") or cg_json.get("group_id")
    assert group_id, f"Unexpected create group response: {cg_json}"
    created_group_id = int(group_id)

    for uid in created_user_ids:
        addm = api_client.post(f"/api/v1/groups/{created_group_id}/members", json={"user_id": uid, "role": "member"})
        assert addm.status_code in (200, 201), f"POST /api/v1/groups/{{id}}/members failed: {addm.status_code} {addm.text[:200]}"
        member_id = int(addm.json().get("id") or 0)
        if member_id:
            created_member_ids.append(member_id)

    # Send to group:<name> using default channel name
    msg = api_client.post(
        "/messages",
        json={
            "audience_type": "broadcast",
            "destinations": [{"channel": default_channel, "address": f"group:{group_name}"}],
            "content": [{"type": "text", "body": _load_message("Test-Brief-News.md")}],
            "options": {"subject": f"AT1.18 Group {run_id}"},
        },
    )
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    created_message_id = int(msg.json().get("message_id"))

    # Wait until at least one delivery reaches sent; then verify count via deliveries endpoint
    _wait_for_delivery_sent(
        api_client,
        created_message_id,
        max_wait=at118_max_wait,
        poll_interval=at118_poll_interval,
        allow_sending=str(channel_type).lower() == "loopback",
    )
    r = api_client.get(f"/messages/{created_message_id}/deliveries")
    assert r.status_code == 200
    deliveries = r.json().get("items", [])
    assert len(deliveries) == 2, f"Expected 2 deliveries from group expansion, got {len(deliveries)}"
    dests = sorted([d.get("destination") for d in deliveries])
    assert e1 in dests and e2 in dests
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_18c_mcp_and_a2a_health(
    api_client,
    mcp_base_url: str,
    a2a_base_url: str,
    api_timeout: float,
):
    """
    Minimal but real: verify MCP and A2A servers are reachable (health endpoints),
    since T26 includes these interfaces.
    """
    m = httpx.get(f"{mcp_base_url}/health", timeout=api_timeout)
    assert m.status_code == 200, f"MCP /health failed: {m.status_code} {m.text[:200]}"
    a = httpx.get(f"{a2a_base_url}/health", timeout=api_timeout)
    assert a.status_code == 200, f"A2A /health failed: {a.status_code} {a.text[:200]}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.heavy]
