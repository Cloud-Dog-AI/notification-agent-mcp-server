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
System Test: Startup Services Verification

Confirms:
1. API health/status endpoints respond
2. LLM status endpoint responds
3. Minimal CRUD path works via API (create/get/delete)

All values are configuration-driven via --env file.
"""

from pathlib import Path
import time
from uuid import uuid4

import httpx
import pytest


def _require_value(test_config, key: str) -> str:
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(value)


def _api_timeout(test_config) -> httpx.Timeout:
    timeout = float(test_config.get("api.timeout") or 900)
    connect = float(test_config.get("api.connect_timeout") or 60)
    read = float(test_config.get("api.read_timeout") or timeout)
    return httpx.Timeout(timeout=timeout, connect=connect, read=read)


def _assert_health_payload(payload: dict, expected_server: str, test_config) -> None:
    # The health contract returns "status" in ("ok", "healthy") and "application" (not "server"/"app").
    assert payload.get("status") in ("ok", "healthy"), f"Expected healthy status for {expected_server}"
    assert payload.get("application") or payload.get("app"), "application missing from /health response"
    env_file = test_config.get("app.env_file")
    if env_file:
        payload_env = payload.get("env_file")
        if payload_env and payload_env != env_file:
            # Docker runs mount env at /app/env regardless of host path
            if payload_env != "/app/env":
                assert payload_env == env_file, "env_file mismatch in /health"


def _wait_for_health(base_url: str, timeout: httpx.Timeout, retries: int = 10, delay: float = 1.0) -> httpx.Response:
    last_error = None
    for _ in range(retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                return client.get(f"{str(base_url).rstrip('/')}/health")
        except httpx.ConnectError as exc:
            last_error = exc
            time.sleep(delay)
    if last_error:
        raise last_error
    raise httpx.ConnectError("Health check failed", request=None)


def _load_message_body(test_config) -> str:
    message_file = _require_value(test_config, "test.message_file")
    path = Path(str(message_file))
    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[3]
        path = project_root / path
    if not path.exists():
        pytest.fail(f"❌ HARD FAIL: message file not found: {path}")
    body = path.read_text(encoding="utf-8").strip()
    if not body:
        pytest.fail(f"❌ HARD FAIL: message file is empty: {path}")
    return body


def _get_smtp_channel_config(test_config) -> dict:
    host = _require_value(test_config, "channels.smtp.default.host")
    port = int(_require_value(test_config, "channels.smtp.default.port"))
    username = _require_value(test_config, "channels.smtp.default.username")
    password = _require_value(test_config, "channels.smtp.default.password")
    from_address = _require_value(test_config, "channels.smtp.default.from_address")
    use_tls = bool(test_config.get("channels.smtp.default.use_tls"))
    use_starttls = bool(test_config.get("channels.smtp.default.use_starttls"))
    timeout = int(test_config.get("channels.smtp.default.timeout") or 30)
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "from_address": from_address,
        "use_tls": use_tls,
        "use_starttls": use_starttls,
        "timeout": timeout,
    }


def _ensure_default_channel(api_base_url, api_key, default_channel, test_config, request) -> None:
    headers = {"X-API-Key": api_key}
    with httpx.Client(timeout=_api_timeout(test_config)) as client:
        resp = client.get(f"{api_base_url}/channels", headers=headers)
        resp.raise_for_status()
        channels = resp.json()

        existing = next((ch for ch in channels if ch.get("name") == default_channel), None)
        if not existing:
            config = _get_smtp_channel_config(test_config)
            create_resp = client.post(
                f"{api_base_url}/channels",
                headers=headers,
                json={
                    "name": default_channel,
                    "type": "smtp",
                    "enabled": True,
                    "config": config,
                },
            )
            create_resp.raise_for_status()
            created = create_resp.json()
            channel_id = created.get("id")

            def _cleanup():
                if channel_id:
                    with httpx.Client(timeout=_api_timeout(test_config)) as cleanup_client:
                        delete_resp = cleanup_client.delete(
                            f"{api_base_url}/channels/{channel_id}",
                            headers=headers,
                        )
                        assert delete_resp.status_code in (200, 204), (
                            f"Failed to delete channel: {delete_resp.status_code} {delete_resp.text[:200]}"
                        )

            request.addfinalizer(_cleanup)
            return

        channel_id = existing.get("id")
        was_enabled = existing.get("enabled")
        if not was_enabled:
            client.post(f"{api_base_url}/channels/{channel_id}/enable", headers=headers)

        def _restore():
            if channel_id is not None and was_enabled is False:
                with httpx.Client(timeout=_api_timeout(test_config)) as cleanup_client:
                    cleanup_client.post(
                        f"{api_base_url}/channels/{channel_id}/disable",
                        headers=headers,
                    )

        request.addfinalizer(_restore)


@pytest.fixture(scope="session")
def api_base_url(test_config):
    return _require_value(test_config, "api_server.base_url")


@pytest.fixture(scope="session")
def api_key(test_config):
    return _require_value(test_config, "api_server.api_key")


@pytest.fixture(scope="session")
def default_channel(test_config):
    return _require_value(test_config, "default_channel")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


@pytest.fixture(scope="session")
def test_email(test_config):
    return _require_value(test_config, "test.email")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st119_health_status(api_base_url, test_config):
    with httpx.Client(timeout=_api_timeout(test_config)) as client:
        resp = client.get(f"{api_base_url}/health")
    assert resp.status_code == 200, f"/health failed: {resp.status_code} {resp.text[:200]}"
    payload = resp.json()
    _assert_health_payload(payload, "api", test_config)
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st119_health_metadata_services(test_config):
    servers = [
        ("web", "web_server.base_url", "web_server.enabled"),
        ("mcp", "mcp_server.base_url", "mcp_server.enabled"),
        ("a2a", "a2a_server.base_url", "a2a_server.enabled"),
    ]
    timeout = _api_timeout(test_config)
    for server_name, base_key, enabled_key in servers:
        enabled = test_config.get(enabled_key)
        if enabled in [False, 0, "false", "False"]:
            continue
        base_url = test_config.get(base_key)
        if not base_url:
            continue
        resp = _wait_for_health(base_url, timeout)
        assert resp.status_code == 200, f"{server_name} /health failed: {resp.status_code} {resp.text[:200]}"
        payload = resp.json()
        _assert_health_payload(payload, server_name, test_config)
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st119_status_and_llm(api_base_url, api_key, test_config):
    headers = {"X-API-Key": api_key}
    with httpx.Client(timeout=_api_timeout(test_config)) as client:
        status_resp = client.get(f"{api_base_url}/status", headers=headers)
        llm_resp = client.get(f"{api_base_url}/llm/status", headers=headers)

    assert status_resp.status_code == 200, f"/status failed: {status_resp.status_code} {status_resp.text[:200]}"
    payload = status_resp.json()
    assert "queue_depth" in payload, "queue_depth missing from /status response"
    assert "channels" in payload, "channels missing from /status response"
    assert "timestamp" in payload, "timestamp missing from /status response"

    assert llm_resp.status_code == 200, f"/llm/status failed: {llm_resp.status_code} {llm_resp.text[:200]}"
    llm_payload = llm_resp.json()
    assert "available" in llm_payload, "available missing from /llm/status response"
    assert "queue_length" in llm_payload, "queue_length missing from /llm/status response"
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st119_channel_crud(api_base_url, api_key, test_config):
    base_url = _require_value(test_config, "messages.base_url")
    headers = {"X-API-Key": api_key}
    name = uuid4().hex
    payload = {
        "name": name,
        "type": "loopback",
        "enabled": True,
        "config": {"base_url": base_url},
    }
    with httpx.Client(timeout=_api_timeout(test_config)) as client:
        create_resp = client.post(f"{api_base_url}/channels", headers=headers, json=payload)
        assert create_resp.status_code == 201, f"POST /channels failed: {create_resp.status_code} {create_resp.text[:200]}"
        channel_id = create_resp.json().get("id")
        assert channel_id, "Channel ID missing from create response"

        get_resp = client.get(f"{api_base_url}/channels/{channel_id}", headers=headers)
        assert get_resp.status_code == 200, f"GET /channels/{{id}} failed: {get_resp.status_code} {get_resp.text[:200]}"

        patch_resp = client.patch(f"{api_base_url}/channels/{channel_id}", headers=headers, json={"enabled": False})
        assert patch_resp.status_code == 200, f"PATCH /channels failed: {patch_resp.status_code} {patch_resp.text[:200]}"

        delete_resp = client.delete(f"{api_base_url}/channels/{channel_id}", headers=headers)
        assert delete_resp.status_code in (200, 204), f"DELETE /channels failed: {delete_resp.status_code} {delete_resp.text[:200]}"
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st119_message_crud(api_base_url, api_key, default_channel, test_email, test_config, request):
    _ensure_default_channel(api_base_url, api_key, default_channel, test_config, request)
    headers = {"X-API-Key": api_key}
    message_body = _load_message_body(test_config)[:800]
    payload = {
        "audience_type": "personalised",
        "destinations": [
            {
                "channel": default_channel,
                "address": test_email,
                "preferences": {"language": "en", "content_style": "text"},
            }
        ],
        "content": [
            {
                "type": "text",
                "body": message_body,
            }
        ],
    }

    with httpx.Client(timeout=_api_timeout(test_config)) as client:
        create_resp = client.post(f"{api_base_url}/messages", json=payload, headers=headers)
        assert create_resp.status_code == 201, f"POST /messages failed: {create_resp.status_code} {create_resp.text[:200]}"
        created = create_resp.json()
        message_id = created.get("id") or created.get("message_id")
        assert message_id, "Message ID missing from create response"

        def _cleanup():
            with httpx.Client(timeout=_api_timeout(test_config)) as cleanup_client:
                cleanup_client.delete(f"{api_base_url}/messages/{message_id}", headers=headers)

        request.addfinalizer(_cleanup)

        get_resp = client.get(f"{api_base_url}/messages/{message_id}", headers=headers)
        assert get_resp.status_code == 200, f"GET /messages/{{id}} failed: {get_resp.status_code} {get_resp.text[:200]}"

        delete_resp = client.delete(f"{api_base_url}/messages/{message_id}", headers=headers)
        assert delete_resp.status_code == 200, f"DELETE /messages/{{id}} failed: {delete_resp.status_code} {delete_resp.text[:200]}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.docker, pytest.mark.slow]

