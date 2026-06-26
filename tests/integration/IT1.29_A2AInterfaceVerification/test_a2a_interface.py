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
IT1.29: A2A interface verification for notification-agent

Smoke-level verification of the existing A2A task-submission surface:
- A2A health endpoint responds
- A2A natural-language submission creates a real message through the API
- The created message can be retrieved from the API

This test validates the current implemented A2A surface. It does not claim
tool-list or tool-exec coverage because the notification-agent A2A server does
not expose those routes.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest


pytestmark = [pytest.mark.integration]


def _require_value(value: Any, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return text


@pytest.fixture(scope="session")
def api_base_url(test_config: Any) -> str:
    return _require_value(test_config.get("api_server.base_url"), "api_server.base_url").rstrip("/")


@pytest.fixture(scope="session")
def api_key(test_config: Any) -> str:
    return _require_value(test_config.get("api_server.api_key"), "api_server.api_key")


@pytest.fixture(scope="session")
def a2a_base_url(test_config: Any) -> str:
    return _require_value(test_config.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")


@pytest.fixture(scope="session")
def default_channel(test_config: Any) -> str:
    return _require_value(test_config.get("default_channel"), "default_channel")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    raw_value = test_config.get("api.timeout")
    if raw_value is None or str(raw_value).strip() == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(raw_value)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_it129_a2a_natural_submission_creates_message(
    api_base_url: str,
    api_key: str,
    a2a_base_url: str,
    default_channel: str,
    api_timeout: float,
) -> None:
    run_id = f"it129-{int(time.time())}"
    username = f"it129_user_{run_id}"
    display_name = f"IT129 User {run_id}"
    email = f"gary+{run_id}@cloud-dog.net"

    created_user_id: int | None = None
    created_message_id: int | None = None

    with httpx.Client(timeout=api_timeout) as api_client, httpx.Client(timeout=api_timeout) as a2a_client:
        health = a2a_client.get(f"{a2a_base_url}/health")
        assert health.status_code == 200, f"A2A health failed: {health.status_code} {health.text[:200]}"
        health_payload = health.json()
        assert health_payload.get("status") == "ok"
        assert health_payload.get("application") == "notification-agent-mcp-server"

        user_response = api_client.post(
            f"{api_base_url}/api/users",
            headers={"X-API-Key": api_key},
            json={
                "username": username,
                "email": email,
                "password": f"pw-{run_id}",
                "display_name": display_name,
                "role": "user",
                "user_type": "internal",
            },
        )
        assert user_response.status_code in (200, 201), (
            f"POST /api/users failed: {user_response.status_code} {user_response.text[:200]}"
        )
        user_payload = user_response.json()
        assert user_payload.get("success") is True, f"Unexpected user payload: {user_payload}"
        created_user_id = int(user_payload["user_id"])

        a2a_response = a2a_client.post(
            f"{a2a_base_url}/notify/natural",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={
                "command": f"Send notification to {display_name} that IT1.29 completed successfully",
                "channels": [default_channel],
            },
        )
        assert a2a_response.status_code == 200, (
            f"A2A notify/natural failed: {a2a_response.status_code} {a2a_response.text[:200]}"
        )
        a2a_payload = a2a_response.json()
        assert a2a_payload.get("success") is True, f"Unexpected A2A payload: {a2a_payload}"
        assert isinstance(a2a_payload.get("parsed"), dict), f"Missing parsed payload: {a2a_payload}"
        created_message_id = int(a2a_payload["message_id"])
        assert created_message_id > 0

        message_response = api_client.get(
            f"{api_base_url}/messages/{created_message_id}",
            headers={"X-API-Key": api_key},
            params={"format": "json"},
        )
        assert message_response.status_code == 200, (
            f"GET /messages/{{id}} failed: {message_response.status_code} {message_response.text[:200]}"
        )
        message_payload = message_response.json()
        assert int(message_payload.get("id")) == created_message_id

        if created_message_id is not None:
            delete_message = api_client.delete(
                f"{api_base_url}/messages/{created_message_id}",
                headers={"X-API-Key": api_key},
            )
            assert delete_message.status_code in (200, 204), (
                f"DELETE /messages/{{id}} failed: {delete_message.status_code} {delete_message.text[:200]}"
            )

        if created_user_id is not None:
            delete_user = api_client.delete(
                f"{api_base_url}/api/users/{created_user_id}",
                headers={"X-API-Key": api_key},
            )
            assert delete_user.status_code in (200, 204), (
                f"DELETE /api/users/{{id}} failed: {delete_user.status_code} {delete_user.text[:200]}"
            )
