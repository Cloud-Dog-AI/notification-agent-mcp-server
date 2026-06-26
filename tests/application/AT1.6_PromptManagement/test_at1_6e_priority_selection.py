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
AT1.6E: Prompt Priority & Selection Logic (refactored)

RULES.md compliance:
- API-only (no direct database access)
- No hardcoded URLs/keys/ports (all via config/env fixtures)
- One scenario per test (E1, E2, E3) to allow stop-on-first-failure usage
- Regular progress output while waiting (30s interval)

Requirements: FR1.15 (LLM Prompt Management - Priority Chain)
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest

# Allow importing local helpers from this folder (folder name contains dots; not a package)
sys.path.insert(0, str(Path(__file__).parent))

from at16_helpers import (
    require_env_loaded,
    cfg_required,
    cfg_json_required,
    unique_suffix,
    plus_address,
    wait_for_delivery,
    payload_to_text,
    api_post_json,
    api_delete,
)


def _create_group(client: httpx.Client, api_base_url: str, api_key: str, name: str) -> int:
    group = api_post_json(
        client,
        api_base_url,
        api_key,
        "/api/v1/groups",
        {"name": name, "description": "AT1.6E test group (isolated)"},
    )
    group_id = group.get("id") or group.get("group_id")
    if not group_id:
        raise AssertionError("❌ Group create did not return id")
    return int(group_id)


def _add_group_keywords(client: httpx.Client, api_base_url: str, api_key: str, group_id: int, keywords: List[str]) -> None:
    for kw in keywords:
        resp = client.post(
            f"{api_base_url}/api/v1/groups/{group_id}/keywords",
            headers={"X-API-Key": api_key},
            json={"keyword": kw},
        )
        if resp.status_code not in (200, 201, 409):
            raise AssertionError(f"❌ Failed to add group keyword '{kw}': {resp.status_code} {resp.text[:200]}")


def _add_group_member(client: httpx.Client, api_base_url: str, api_key: str, group_id: int, user_id: int) -> None:
    resp = client.post(
        f"{api_base_url}/api/v1/groups/{group_id}/members",
        headers={"X-API-Key": api_key},
        json={"user_id": user_id, "role": "member"},
    )
    if resp.status_code not in (200, 201, 409):
        raise AssertionError(f"❌ Failed to add user to group: {resp.status_code} {resp.text[:200]}")


def _create_user(client: httpx.Client, api_base_url: str, api_key: str, *, username: str, email: str, display_name: str, language: Optional[str] = None) -> int:
    payload: Dict[str, Any] = {
        "username": username,
        "email": email,
        "display_name": display_name,
        "role": "user",
    }
    if language:
        payload["language"] = language
    user = api_post_json(client, api_base_url, api_key, "/users", payload)
    return int(user["id"])


def _add_user_keyword(client: httpx.Client, api_base_url: str, api_key: str, user_id: int, keyword: str) -> None:
    resp = client.post(
        f"{api_base_url}/users/{user_id}/keywords",
        headers={"X-API-Key": api_key},
        json={"keyword": keyword},
    )
    if resp.status_code not in (200, 201, 409):
        raise AssertionError(f"❌ Failed to add user keyword '{keyword}': {resp.status_code} {resp.text[:200]}")


def _create_prompt(client: httpx.Client, api_base_url: str, api_key: str, payload: Dict[str, Any]) -> int:
    prompt = api_post_json(client, api_base_url, api_key, "/prompts", payload)
    return int(prompt["id"])


def _send_message(
    client: httpx.Client,
    api_base_url: str,
    api_key: str,
    *,
    email: str,
    channel_name: str,
    body: str,
    prompt_name: Optional[str] = None,
) -> int:
    message_data: Dict[str, Any] = {
        "audience_type": "personalised",
        "destinations": [{"channel": channel_name, "address": email}],
        "content": [{"type": "text", "body": body}],
    }
    if prompt_name:
        message_data["prompt_name"] = prompt_name
    resp = client.post(f"{api_base_url}/messages", headers={"X-API-Key": api_key}, json=message_data)
    if resp.status_code not in (200, 201, 202):
        raise AssertionError(f"❌ Failed to send message: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    msg_id = data.get("message_id") or data.get("id")
    if not msg_id:
        raise AssertionError("❌ Message create response missing message_id")
    return int(msg_id)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


@pytest.mark.asyncio
async def test_at1_6e1_explicit_prompt(test_config, api_base_url, api_key, api_timeout, smtp_channel_name):
    """
    E1: Explicit prompt directive in message request (Priority #1).
    """
    require_env_loaded(test_config)
    run = unique_suffix()

    test_message = cfg_required(test_config, "test.at16.e.test_message")
    base_prompt_name = cfg_required(test_config, "test.at16.e.explicit_prompt_name")
    prompt_text = cfg_required(test_config, "test.at16.e.explicit_prompt_text")
    base_email = cfg_required(test_config, "test.at16.e.test_email_explicit")
    max_wait = float(test_config.get("test.at16.e.max_wait", 600))
    poll_interval = float(test_config.get("test.at16.e.poll_interval", 2.0))

    prompt_name = f"{base_prompt_name}_{run}"
    email = plus_address(base_email, f"at16e1{run}")

    created_prompt_id: Optional[int] = None
    created_user_id: Optional[int] = None

    with httpx.Client(timeout=api_timeout) as client:
        smtp_channel = smtp_channel_name

        created_prompt_id = _create_prompt(
            client,
            api_base_url,
            api_key,
            {
                "name": prompt_name,
                "prompt_text": prompt_text,
                "channel_type": "email",
                "keyword": f"__explicit_only_{run}__",
                "priority": 1000,
                "enabled": True,
            },
        )

        created_user_id = _create_user(
            client,
            api_base_url,
            api_key,
            username=f"at16e1_user_{run}",
            email=email,
            display_name="AT1.6E1 Explicit Prompt",
        )

        message_id = _send_message(
            client,
            api_base_url,
            api_key,
            email=email,
            channel_name=smtp_channel,
            body=f"{test_message} [Scenario: E1_explicit]",
            prompt_name=prompt_name,
        )

        delivery = wait_for_delivery(
            client,
            api_base_url,
            api_key,
            message_id,
            max_wait_seconds=max_wait,
            poll_interval_seconds=poll_interval,
            progress_interval_seconds=30.0,
        )
        payload = payload_to_text(delivery.get("personalised_payload"))
        assert "[E1Explicit]" in payload, "E1 FAILED: Tag [E1Explicit] not found in payload"

    # Cleanup (API-only)
    with httpx.Client(timeout=api_timeout) as client:
        if created_user_id:
            api_delete(client, api_base_url, api_key, f"/users/{created_user_id}")
        if created_prompt_id:
            api_delete(client, api_base_url, api_key, f"/prompts/{created_prompt_id}")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


@pytest.mark.asyncio
async def test_at1_6e2_group_keyword_prompt(test_config, api_base_url, api_key, api_timeout, smtp_channel_name):
    """
    E2: Group keyword prompt (Priority #4).
    """
    require_env_loaded(test_config)
    run = unique_suffix()

    test_message = cfg_required(test_config, "test.at16.e.test_message")
    base_email = cfg_required(test_config, "test.at16.e.test_email_group_keyword")
    group_keywords = list(cfg_json_required(test_config, "test.at16.e.group_keywords"))
    group_prompt_text = cfg_required(test_config, "test.at16.e.group_keyword_prompt_text")
    max_wait = float(test_config.get("test.at16.e.max_wait", 600))
    poll_interval = float(test_config.get("test.at16.e.poll_interval", 2.0))
    base_group_name = cfg_required(test_config, "test.at16.e.test_group_name")

    # Isolate keywords to avoid environmental collisions.
    # IMPORTANT: Avoid underscores because keyword extraction can normalise/strip them.
    group_keywords = [f"{kw}{run}" for kw in group_keywords]
    first_kw = sorted(group_keywords)[0]

    email = plus_address(base_email, f"at16e2{run}")
    group_name = f"{base_group_name}_{run}"

    created_prompt_id: Optional[int] = None
    created_user_id: Optional[int] = None
    created_group_id: Optional[int] = None

    try:
        with httpx.Client(timeout=api_timeout) as client:
            smtp_channel = smtp_channel_name

            created_group_id = _create_group(client, api_base_url, api_key, group_name)
            _add_group_keywords(client, api_base_url, api_key, created_group_id, group_keywords)

            created_prompt_id = _create_prompt(
                client,
                api_base_url,
                api_key,
                {
                    "name": f"AT16E_GroupKeyword_{run}",
                    "prompt_text": group_prompt_text,
                    "channel_type": "email",
                    "group_id": created_group_id,
                    "keyword": first_kw,
                    "priority": 9000,
                    "enabled": True,
                },
            )

            created_user_id = _create_user(
                client,
                api_base_url,
                api_key,
                username=f"at16e2_user_{run}",
                email=email,
                display_name="AT1.6E2 Group Keyword",
            )
            _add_group_member(client, api_base_url, api_key, created_group_id, created_user_id)

            # Include the keyword in the message body so keyword-based prompt selection can match (RULES: validate real behaviour)
            message_id = _send_message(
                client,
                api_base_url,
                api_key,
                email=email,
                channel_name=smtp_channel,
                body=f"{test_message} keyword={first_kw} [Scenario: E2_group_keyword]",
            )

            delivery = wait_for_delivery(
                client,
                api_base_url,
                api_key,
                message_id,
                max_wait_seconds=max_wait,
                poll_interval_seconds=poll_interval,
                progress_interval_seconds=30.0,
            )
            payload = payload_to_text(delivery.get("personalised_payload"))
            assert "[E2GroupKw]" in payload, "E2 FAILED: Tag [E2GroupKw] not found in payload"
    finally:
        # Cleanup (API-only) - must run even on assertion failure
        with httpx.Client(timeout=api_timeout) as client:
            try:
                if created_user_id:
                    api_delete(client, api_base_url, api_key, f"/users/{created_user_id}")
            except Exception:
                pass
            try:
                if created_prompt_id:
                    api_delete(client, api_base_url, api_key, f"/prompts/{created_prompt_id}")
            except Exception:
                pass
            try:
                if created_group_id:
                    api_delete(client, api_base_url, api_key, f"/api/v1/groups/{created_group_id}")
            except Exception:
                pass
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-007")


@pytest.mark.asyncio
async def test_at1_6e3_user_keyword_beats_group_keyword(test_config, api_base_url, api_key, api_timeout, smtp_channel_name):
    """
    E3: User keyword (Priority #2) should beat group keyword (Priority #4).
    """
    require_env_loaded(test_config)
    run = unique_suffix()

    test_message = cfg_required(test_config, "test.at16.e.test_message")
    base_email = cfg_required(test_config, "test.at16.e.test_email_competition")
    base_group_name = cfg_required(test_config, "test.at16.e.test_group_name")
    user_kw_base = cfg_required(test_config, "test.at16.e.competition_user_keyword")
    user_prompt_text = cfg_required(test_config, "test.at16.e.user_keyword_prompt_text")
    group_prompt_text = cfg_required(test_config, "test.at16.e.group_keyword_prompt_text")
    max_wait = float(test_config.get("test.at16.e.max_wait", 600))
    poll_interval = float(test_config.get("test.at16.e.poll_interval", 2.0))

    email = plus_address(base_email, f"at16e3{run}")
    group_name = f"{base_group_name}_{run}"
    # IMPORTANT: Avoid underscores because keyword extraction can normalise/strip them.
    kw = f"{user_kw_base}{run}"

    created_group_id: Optional[int] = None
    created_user_id: Optional[int] = None
    created_user_prompt_id: Optional[int] = None
    created_group_prompt_id: Optional[int] = None

    try:
        with httpx.Client(timeout=api_timeout) as client:
            smtp_channel = smtp_channel_name

            created_group_id = _create_group(client, api_base_url, api_key, group_name)
            _add_group_keywords(client, api_base_url, api_key, created_group_id, [kw])

            # Group keyword prompt (priority #4) - should LOSE
            created_group_prompt_id = _create_prompt(
                client,
                api_base_url,
                api_key,
                {
                    "name": f"AT16E_E3_GroupKw_{run}",
                    "prompt_text": f"{group_prompt_text}\n\nCRITICAL: Add the tag [E3GroupKw] at the very start.",
                    "channel_type": "email",
                    "group_id": created_group_id,
                    "keyword": kw,
                "priority": 9000,
                    "enabled": True,
                },
            )

            # User keyword prompt (priority #2) - should WIN
            created_user_prompt_id = _create_prompt(
                client,
                api_base_url,
                api_key,
                {
                    "name": f"AT16E_E3_UserKw_{run}",
                    "prompt_text": user_prompt_text,
                    "channel_type": "email",
                    "keyword": kw,  # user keyword
                "priority": 10000,
                    "enabled": True,
                },
            )

            created_user_id = _create_user(
                client,
                api_base_url,
                api_key,
                username=f"at16e3_user_{run}",
                email=email,
                display_name="AT1.6E3 User Keyword",
            )
            _add_user_keyword(client, api_base_url, api_key, created_user_id, kw)
            _add_group_member(client, api_base_url, api_key, created_group_id, created_user_id)

            # Include the keyword in the message body so keyword-based prompt selection can match
            message_id = _send_message(
                client,
                api_base_url,
                api_key,
                email=email,
                channel_name=smtp_channel,
                body=f"{test_message} keyword={kw} [Scenario: E3_competition]",
            )

            delivery = wait_for_delivery(
                client,
                api_base_url,
                api_key,
                message_id,
                max_wait_seconds=max_wait,
                poll_interval_seconds=poll_interval,
                progress_interval_seconds=30.0,
            )
            payload = payload_to_text(delivery.get("personalised_payload"))
            assert "[E3UserKw]" in payload, "E3 FAILED: Tag [E3UserKw] not found in payload"
            assert "[E3GroupKw]" not in payload, "E3 FAILED: Group keyword prompt should not be selected"
    finally:
        # Cleanup (API-only) - must run even on assertion failure
        with httpx.Client(timeout=api_timeout) as client:
            try:
                if created_user_id:
                    api_delete(client, api_base_url, api_key, f"/users/{created_user_id}")
            except Exception:
                pass
            try:
                if created_user_prompt_id:
                    api_delete(client, api_base_url, api_key, f"/prompts/{created_user_prompt_id}")
            except Exception:
                pass
            try:
                if created_group_prompt_id:
                    api_delete(client, api_base_url, api_key, f"/prompts/{created_group_prompt_id}")
            except Exception:
                pass
            try:
                if created_group_id:
                    api_delete(client, api_base_url, api_key, f"/api/v1/groups/{created_group_id}")
            except Exception:
                pass

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]
