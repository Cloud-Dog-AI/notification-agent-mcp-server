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
AT1.13: Personalised notifications (Application tests)

RULES.md compliance:
- Config-driven (no hardcoded URLs/keys/addresses/timeouts/preferences)
- API-only interactions + best-effort cleanup
- One test node at a time
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict

import httpx
import pytest


@pytest.fixture(scope="session")
def require_at113_env_loaded(test_config: Any) -> None:
    if not test_config.get("test.at113_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.13 env file not loaded! Use --env private/env-test-at113")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    v = test_config.get("api.timeout")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at113_max_wait(test_config: Any) -> float:
    v = test_config.get("test.at113.max_wait")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at113.max_wait not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at113_poll_interval(test_config: Any) -> float:
    v = test_config.get("test.at113.poll_interval")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at113.poll_interval not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def api_client(api_base_url: str, api_key: str, api_timeout: float):
    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def test_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "at113_outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture(scope="session")
def smtp_config(test_config: Dict[str, Any]) -> Dict[str, Any]:
    """Get SMTP configuration from config - fail hard if incomplete."""
    smtp = test_config.get("channels.smtp.default", {}) or {}
    required = [
        "host",
        "port",
        "username",
        "password",
        "from_address",
        "timeout",
        "use_tls",
        "use_starttls",
    ]
    missing = []
    for key in required:
        if key not in smtp:
            missing.append(key)
            continue
        value = smtp.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
            continue
        if key in ("port", "timeout"):
            try:
                if int(value) <= 0:
                    missing.append(key)
            except (TypeError, ValueError):
                missing.append(key)

    if missing:
        pytest.fail(
            "❌ HARD FAIL: SMTP configuration incomplete for AT1.13. "
            f"Missing/invalid: {', '.join(sorted(set(missing)))}. "
            "Set CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__* in the env file."
        )
    return smtp


@pytest.fixture(scope="session")
def smtp_channel_name(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    smtp_config: Dict[str, Any],
    request,
):
    """
    Create a dedicated, fully-configured SMTP channel via API.
    Ensures adapter registration and full CRUD coverage for AT1.13.
    """
    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"at113_smtp_{run_suffix}"
        payload = {
            "name": channel_name,
            "type": "smtp",
            "enabled": True,
            "config": {
                "host": smtp_config.get("host"),
                "port": smtp_config.get("port"),
                "username": smtp_config.get("username"),
                "password": smtp_config.get("password"),
                "from_address": smtp_config.get("from_address"),
                "use_tls": smtp_config.get("use_tls"),
                "use_starttls": smtp_config.get("use_starttls"),
                "timeout": smtp_config.get("timeout"),
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

