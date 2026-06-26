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
AT1.12: Broadcast notifications (Application tests)

RULES.md compliance:
- Config-driven (no hardcoded URLs/keys/addresses/timeouts/preferences)
- API-only interactions + best-effort cleanup
- One test node at a time
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict

import pytest
import httpx
from tests.utils.api_tracking import build_tracked_client


@pytest.fixture(scope="session")
def require_at112_env_loaded(test_config: Any) -> None:
    if not test_config.get("test.at112_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.12 env file not loaded! Use --env private/env-test-at112")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    v = test_config.get("api.timeout")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at112_max_wait(test_config: Any) -> float:
    v = test_config.get("test.at112.max_wait")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at112.max_wait not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at112_poll_interval(test_config: Any) -> float:
    v = test_config.get("test.at112.poll_interval")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at112.poll_interval not configured in env file")
    return float(v)


@pytest.fixture(scope="function")
def api_client(api_base_url: str, api_key: str, api_timeout: float, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=api_timeout,
        registry=api_cleanup_registry,
    ) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def require_api_running(api_base_url: str, api_timeout: float) -> None:
    try:
        response = httpx.get(f"{api_base_url}/health", timeout=api_timeout)
    except httpx.ConnectError:
        pytest.fail(
            "API server is not running. Start with "
            "`./server_control.sh --env private/env-test-at112 start api`"
        )
    if response.status_code != 200:
        pytest.fail(f"API server health check failed: {response.status_code}")


@pytest.fixture(scope="function")
def test_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "at112_outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture(scope="session")
def messages_base_url(test_config: Dict[str, Any]) -> str:
    v = test_config.get("messages.base_url")
    if not v:
        pytest.fail("❌ HARD FAIL: messages.base_url not configured in env file")
    return str(v).rstrip("/")


@pytest.fixture(scope="session")
def preferred_channel_name(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    messages_base_url: str,
    test_config: Dict[str, Any],
    request,
) -> str:
    """
    Create a dedicated loopback channel via API for AT1.12.
    Ensures adapter registration and full CRUD coverage.
    """
    base_name = test_config.get("test.at112.preferred_channel")
    if not base_name:
        pytest.fail("❌ HARD FAIL: test.at112.preferred_channel not configured in env file")

    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"{base_name}_{run_suffix}"
        payload = {
            "name": channel_name,
            "type": "loopback",
            "enabled": True,
            "config": {
                "base_url": messages_base_url,
                "message_path_template": "/{message_guid}",
            },
        }

        create_resp = client.post(f"{api_base_url}/channels", headers=headers, json=payload)
        assert create_resp.status_code == 201, (
            f"POST /channels failed: {create_resp.status_code} - {create_resp.text}"
        )
        channel_id = create_resp.json().get("id")
        assert channel_id, "Channel ID missing from create response"

        # READ: verify channel appears in list
        list_resp = client.get(f"{api_base_url}/channels", headers=headers)
        assert list_resp.status_code == 200, f"GET /channels failed: {list_resp.status_code} - {list_resp.text}"
        channels = list_resp.json()
        if not isinstance(channels, list):
            pytest.fail(f"❌ /channels did not return a list: {type(channels)}")
        if not any(isinstance(ch, dict) and ch.get("id") == channel_id for ch in channels):
            pytest.fail(f"❌ Created channel ID {channel_id} not found in /channels list")

        # UPDATE: rename channel to prove update path
        updated_name = f"{channel_name}_updated"
        update_resp = client.patch(
            f"{api_base_url}/channels/{channel_id}",
            headers=headers,
            json={"name": updated_name},
        )
        assert update_resp.status_code == 200, (
            f"PATCH /channels/{channel_id} failed: {update_resp.status_code} - {update_resp.text}"
        )
        channel_name = updated_name

    def _cleanup():
        if not channel_id:
            return
        with httpx.Client(timeout=api_timeout) as client:
            resp = client.delete(f"{api_base_url}/channels/{channel_id}", headers=headers)
            assert resp.status_code in (200, 204), (
                f"DELETE /channels failed: {resp.status_code} - {resp.text[:200]}"
            )

    request.addfinalizer(_cleanup)
    return channel_name

