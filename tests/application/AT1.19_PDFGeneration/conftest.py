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
AT1.19: PDF Output & Generation (Application tests)

RULES.md compliance:
- Config-driven (no hardcoded URLs/keys/timeouts/addresses/channel names)
- API-only interactions (no direct DB/filesystem)
- Best-effort cleanup via API
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import httpx
import pytest
from pathlib import Path

from tests.conftest import (
    _ensure_api_ready_for_test,
)


@pytest.fixture(scope="session")
def require_at119_env_loaded(test_config: Any) -> None:
    if not test_config.get("test.at119_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.19 env file not loaded! Use --env private/env-test-at119")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    v = test_config.get("api.timeout")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at119_max_wait(test_config: Any) -> float:
    v = test_config.get("test.at119.max_wait")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at119.max_wait not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def at119_poll_interval(test_config: Any) -> float:
    v = test_config.get("test.at119.poll_interval")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at119.poll_interval not configured in env file")
    return float(v)


@pytest.fixture(scope="session")
def pdf_language(test_config: Any) -> str:
    v = test_config.get("test.at119.pdf_language")
    if not v:
        pytest.fail("❌ HARD FAIL: test.at119.pdf_language not configured in env file")
    return str(v)


@pytest.fixture(scope="session")
def at119_source_lang(test_config: Any) -> str:
    v = test_config.get("test.at119.source_lang")
    if not v:
        pytest.fail("❌ HARD FAIL: test.at119.source_lang not configured in env file")
    return str(v)


@pytest.fixture(scope="session")
def at119_source_size(test_config: Any) -> int:
    v = test_config.get("test.at119.source_size")
    if v is None or v == "":
        pytest.fail("❌ HARD FAIL: test.at119.source_size not configured in env file")
    return int(v)


@pytest.fixture(scope="session")
def pdf_output_formats(test_config: Any) -> List[str]:
    v = test_config.get("test.at119.output_formats")
    if not v:
        pytest.fail("❌ HARD FAIL: test.at119.output_formats not configured in env file (JSON list)")
    try:
        import json

        out = json.loads(v) if isinstance(v, str) else v
        if not isinstance(out, list) or not out:
            raise ValueError("not a list")
        return [str(x) for x in out]
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: test.at119.output_formats invalid JSON list: {e}")


@pytest.fixture(scope="session")
def messages_base_url(test_config: Any) -> str:
    v = test_config.get("messages.base_url")
    if not v:
        pytest.fail("❌ HARD FAIL: messages.base_url not configured in env file")
    return str(v).rstrip("/")


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
            "❌ HARD FAIL: SMTP configuration incomplete for AT1.19. "
            f"Missing/invalid: {', '.join(sorted(set(missing)))}. "
            "Set CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__* in the env file."
        )
    return smtp


@pytest.fixture(scope="function")
def restart_api_per_test(api_base_url: str, api_key: str) -> None:
    """
    AT1.19 mutates queue state heavily, but the useful boundary is a healthy API
    with stale queued work cleared. That is materially lighter than a full
    process restart and preserves the test contract.
    """
    _, cancelled = _ensure_api_ready_for_test(
        api_base_url,
        api_key,
        timeout_seconds=60.0,
        context_label="AT1.19 test execution",
    )
    if cancelled:
        print(f"✅ AT1.19 cancelled {cancelled} stale queued message(s) before test")


@pytest.fixture(scope="function")
def api_client(api_base_url: str, api_key: str, api_timeout: float, restart_api_per_test):
    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def loopback_channel_name(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    messages_base_url: str,
    restart_api_per_test,
    request,
) -> str:
    """
    Create a dedicated loopback channel via API.
    Ensures adapter registration and full CRUD coverage for AT1.19.
    """
    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"at119_loopback_{run_suffix}"
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
            if resp.status_code in (200, 204):
                return
            if resp.status_code == 409:
                disable = client.post(f"{api_base_url}/channels/{channel_id}/disable", headers=headers)
                assert disable.status_code in (200, 204), (
                    f"POST /channels/{{id}}/disable failed after delete 409: "
                    f"{disable.status_code} - {disable.text[:200]}"
                )
                return
            assert resp.status_code in (200, 204), (
                f"DELETE /channels failed: {resp.status_code} - {resp.text[:200]}"
            )

    request.addfinalizer(_cleanup)
    return channel_name


@pytest.fixture(scope="function")
def smtp_channel_name(
    api_base_url: str,
    api_key: str,
    api_timeout: float,
    smtp_config: Dict[str, Any],
    restart_api_per_test,
    request,
) -> str:
    """
    Create a dedicated, fully-configured SMTP channel via API.
    Ensures adapter registration and full CRUD coverage for AT1.19.
    """
    headers = {"X-API-Key": api_key}
    channel_id = None
    channel_name = None

    with httpx.Client(timeout=api_timeout) as client:
        run_suffix = int(time.time())
        channel_name = f"at119_smtp_{run_suffix}"
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
            if resp.status_code in (200, 204):
                return
            if resp.status_code == 409:
                disable = client.post(f"{api_base_url}/channels/{channel_id}/disable", headers=headers)
                assert disable.status_code in (200, 204), (
                    f"POST /channels/{{id}}/disable failed after delete 409: "
                    f"{disable.status_code} - {disable.text[:200]}"
                )
                return
            assert resp.status_code in (200, 204), (
                f"DELETE /channels failed: {resp.status_code} - {resp.text[:200]}"
            )

    request.addfinalizer(_cleanup)
    return channel_name


@pytest.fixture(scope="function")
def test_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "at119_outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out
