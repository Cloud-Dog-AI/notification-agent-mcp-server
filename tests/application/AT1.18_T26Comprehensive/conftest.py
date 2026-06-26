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
AT1.18: T26 Comprehensive Delivery (Application tests)

RULES.md compliance:
- Config-driven (no hardcoded URLs/keys/addresses/timeouts)
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


def _require_endpoint_ready(name: str, base_url: str, timeout: float, max_wait: float, poll_interval: float) -> None:
    endpoint = f"{str(base_url).rstrip('/')}/health"
    deadline = time.monotonic() + max_wait
    last_error = ""

    while time.monotonic() < deadline:
        try:
            response = httpx.get(endpoint, timeout=timeout)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(poll_interval)

    pytest.fail(
        f"❌ HARD FAIL: {name} endpoint not ready at {endpoint} within {max_wait}s. "
        f"Last error: {last_error}"
    )

@pytest.fixture(scope="session")
def require_at118_env_loaded(test_config: Any) -> None:
    if not test_config.get("test.at118_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.18 env file not loaded! Use --env private/env-test-at118")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    v = test_config.get("api.timeout")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at118_max_wait(test_config: Any) -> float:
    v = test_config.get("test.at118.max_wait")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at118.max_wait not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at118_poll_interval(test_config: Any) -> float:
    v = test_config.get("test.at118.poll_interval")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at118.poll_interval not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def a2a_base_url(test_config: Any) -> str:
    v = test_config.get("a2a_server.base_url")
    if not v:
        pytest.fail("❌ HARD FAIL: a2a_server.base_url not configured in env file")
    return str(v).rstrip("/")


@pytest.fixture(scope="session")
def mcp_base_url(test_config: Any) -> str:
    v = test_config.get("mcp_server.base_url")
    # Some configs don't expose base_url; derive from host/port if missing.
    if not v:
        host = test_config.get("mcp_server.host")
        port = test_config.get("mcp_server.port")
        if not host or not port:
            pytest.fail("mcp_server.base_url or mcp_server.host/mcp_server.port not configured in env file")
        v = f"http://{host}:{port}"
    return str(v).rstrip("/")


@pytest.fixture(scope="function")
def api_client(api_base_url: str, api_key: str, api_timeout: float, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=api_timeout,
        registry=api_cleanup_registry,
    ) as client:
        yield client



@pytest.fixture(scope="session")
def at118_preflight_window(test_config: Any, api_timeout: float) -> float:
    configured = test_config.get("test.at118.preflight_max_wait")
    if configured in (None, ""):
        # Keep strict but bounded startup preflight duration if not explicitly configured.
        return min(max(20.0, api_timeout / 10.0), 90.0)
    return float(configured)


@pytest.fixture(scope="session", autouse=True)
def require_runtime_endpoints_ready(
    api_base_url: str,
    mcp_base_url: str,
    a2a_base_url: str,
    api_timeout: float,
    at118_poll_interval: float,
    at118_preflight_window: float,
) -> None:
    _require_endpoint_ready("API", api_base_url, api_timeout, at118_preflight_window, at118_poll_interval)
    _require_endpoint_ready("MCP", mcp_base_url, api_timeout, at118_preflight_window, at118_poll_interval)
    _require_endpoint_ready("A2A", a2a_base_url, api_timeout, at118_preflight_window, at118_poll_interval)


@pytest.fixture(scope="function", autouse=True)
def require_runtime_endpoints_ready_per_test(
    api_base_url: str,
    mcp_base_url: str,
    a2a_base_url: str,
    api_timeout: float,
    at118_poll_interval: float,
) -> None:
    quick_window = max(6.0, at118_poll_interval * 3.0)
    _require_endpoint_ready("API", api_base_url, api_timeout, quick_window, at118_poll_interval)
    _require_endpoint_ready("MCP", mcp_base_url, api_timeout, quick_window, at118_poll_interval)
    _require_endpoint_ready("A2A", a2a_base_url, api_timeout, quick_window, at118_poll_interval)

@pytest.fixture(scope="function")
def test_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "at118_outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture(scope="session")
def default_channel(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    test_config: Dict[str, Any],
    request,
) -> str:
    """
    Create a dedicated loopback channel via API for AT1.18.
    Ensures adapter registration and full CRUD coverage.
    """
    messages_base_url = test_config.get("messages.base_url")
    if not messages_base_url:
        pytest.fail("❌ HARD FAIL: messages.base_url not configured in env file")

    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"at118_loopback_{run_suffix}"
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


@pytest.fixture(scope="session")
def slack_channel_name(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    test_config: Dict[str, Any],
    request,
) -> str:
    """
    Create a dedicated chat_rest channel via API for AT1.18.
    Ensures adapter registration and full CRUD coverage.
    """
    slack_config = test_config.get("channels.chat_rest.transparentbordes", {}) or {}
    endpoint = slack_config.get("endpoint")
    if not endpoint:
        pytest.fail("❌ HARD FAIL: channels.chat_rest.transparentbordes.endpoint not configured in env file")

    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"at118_chat_rest_{run_suffix}"
        payload = {
            "name": channel_name,
            "type": "chat_rest",
            "enabled": True,
            "config": {
                "endpoint": endpoint,
                "auth_type": slack_config.get("auth_type"),
                "format": slack_config.get("format"),
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

