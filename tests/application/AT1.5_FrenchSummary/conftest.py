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
Pytest configuration for AT1.5 Email Channel Comprehensive Tests
"""

import pytest
import httpx
from pathlib import Path


@pytest.fixture(scope="function")
def test_output_dir(tmp_path):
    """
    Create a temporary directory for test outputs (logs, artifacts, etc.)
    Each test gets its own isolated directory.
    """
    return tmp_path


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config):
    """
    HTTP client for API calls (AT1.5).
    
    CRITICAL: Timeouts MUST come from config; no hardcoded defaults.
    """
    timeout_total = test_config.get("api.timeout")
    if not timeout_total:
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")

    # Use a single timeout value for all phases (config-driven, no hardcoded defaults).
    api_timeout = httpx.Timeout(timeout=float(timeout_total))
    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def smtp_channel_name(api_client, smtp_config, request):
    """
    Resolve or create an enabled SMTP channel via API (no hardcoded channel names).
    Creates a channel if none are suitable, and deletes it on teardown.
    """
    resp = api_client.get("/channels")
    assert resp.status_code == 200, f"GET /channels failed: {resp.status_code} - {resp.text}"
    channels = resp.json()
    if not isinstance(channels, list):
        pytest.fail(f"❌ /channels did not return a list: {type(channels)}")

    def _is_valid_config(config):
        if not isinstance(config, dict):
            return False
        required = ["host", "port", "username", "password", "from_address", "timeout"]
        return all(config.get(k) for k in required)

    for ch in channels:
        if isinstance(ch, dict) and ch.get("type") == "smtp" and bool(ch.get("enabled")) is True:
            name = ch.get("name")
            if name and _is_valid_config(ch.get("config") or {}):
                return name

    channel_name = f"at15_smtp_{int(__import__('time').time())}"
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
    created = api_client.post("/channels", json=payload)
    assert created.status_code == 201, f"POST /channels failed: {created.status_code} - {created.text}"
    channel_id = created.json().get("id")
    assert channel_id, "Channel ID missing from create response"

    def _cleanup():
        resp = api_client.delete(f"/channels/{channel_id}")
        assert resp.status_code in (200, 204), f"DELETE /channels failed: {resp.status_code} - {resp.text[:200]}"

    request.addfinalizer(_cleanup)
    return channel_name
