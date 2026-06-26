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
REST API Tests for Notification Agent MCP Server

Run with: pytest --env private/env-it-basic tests/integration/IT1.1_APIServer/test_api_server.py -v
"""

import pytest
import sys
import os
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import time
from tests.utils.api_tracking import build_tracked_client
from tests.utils.test_helpers import wait_for_delivery_with_diagnostics
from tests.conftest import process_deliveries
from src.database.db_manager import DatabaseManager
from src.core.job_manager import JobManager


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=10.0,
        registry=api_cleanup_registry,
    ) as client:
        yield client


def _load_example_message() -> str:
    examples_dir = Path(__file__).parent.parent.parent / "Examples"
    message_path = examples_dir / "Test-Brief-News.md"
    if not message_path.exists():
        pytest.fail(f"Missing test message file: {message_path}")
    return message_path.read_text().strip()


def _is_external_runtime_mode() -> bool:
    return str(os.environ.get("TEST_USE_EXTERNAL_RUNTIME", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_host_db_uri(db_uri: str) -> str:
    if not db_uri:
        return db_uri
    if db_uri.startswith("sqlite3:///app/"):
        rel_path = db_uri.replace("sqlite3:///app/", "", 1)
        host_path = (project_root / rel_path).resolve()
        return f"sqlite3:///{host_path}"
    return db_uri


def _open_test_db(db_uri: str) -> DatabaseManager:
    db = DatabaseManager(_resolve_host_db_uri(db_uri))
    db.connect()
    return db


def _destination_for_channel(channel: dict, test_email: str, test_config) -> str:
    channel_type = str(channel.get("type") or "").lower()
    if channel_type in {"smtp", "email"}:
        return test_email
    if channel_type in {"sms", "twilio_sms"}:
        recipient = test_config.get("test.sms.recipient")
        if not recipient:
            pytest.fail("Missing test.sms.recipient for SMS channel destination")
        return recipient
    if channel_type in {"chat_rest", "slack", "discord"}:
        config_endpoint = None
        if isinstance(channel.get("config"), dict):
            config_endpoint = channel.get("config", {}).get("endpoint")
        endpoint = (
            config_endpoint
            or test_config.get("channels.chat_rest.transparentbordes.endpoint")
            or test_config.get("test.webhook.slack_url")
        )
        if not endpoint:
            return ""
        return endpoint
    if channel_type in {"loopback"}:
        return test_email
    pytest.fail(f"Unsupported channel type for IT1.1: {channel_type!r}")


def _select_channel_with_destination(channels, test_email: str, test_config):
    for ch in channels:
        if not isinstance(ch, dict) or not ch.get("enabled"):
            continue
        destination = _destination_for_channel(ch, test_email, test_config)
        if destination:
            return ch, destination
    return None, None


def _require_config_value(test_config, key: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"Missing required config: {key}")
    return value


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _smtp_config_from_env(test_config) -> dict:
    return {
        "host": _require_config_value(test_config, "channels.smtp.default.host"),
        "port": int(_require_config_value(test_config, "channels.smtp.default.port")),
        "username": _require_config_value(test_config, "channels.smtp.default.username"),
        "password": _require_config_value(test_config, "channels.smtp.default.password"),
        "from_address": _require_config_value(test_config, "channels.smtp.default.from_address"),
        "use_tls": _coerce_bool(_require_config_value(test_config, "channels.smtp.default.use_tls")),
        "use_starttls": _coerce_bool(_require_config_value(test_config, "channels.smtp.default.use_starttls")),
        "timeout": int(_require_config_value(test_config, "channels.smtp.default.timeout")),
    }


def _create_smtp_channel(api_client, test_config) -> dict:
    name = f"it1_1_smtp_{uuid4().hex}"
    response = api_client.post(
        "/channels",
        json={
            "name": name,
            "type": "smtp",
            "enabled": True,
            "config": _smtp_config_from_env(test_config),
        },
    )
    if response.status_code not in (200, 201):
        pytest.fail(f"Failed to create SMTP channel: {response.status_code} {response.text[:200]}")
    payload = response.json()
    return {"id": payload.get("id"), "name": name, "type": "smtp", "enabled": True}


def _create_loopback_channel(api_client, test_config) -> dict:
    base_url = test_config.get("messages.base_url")
    if not base_url:
        pytest.fail("Missing messages.base_url for loopback channel creation")
    name = f"it1_1_loopback_{uuid4().hex}"
    response = api_client.post(
        "/channels",
        json={
            "name": name,
            "type": "loopback",
            "enabled": True,
            "config": {"base_url": base_url},
        },
    )
    if response.status_code not in (200, 201):
        return {}
    payload = response.json()
    return {"id": payload.get("id"), "name": payload.get("name"), "type": "loopback", "enabled": True}


@pytest.fixture
def message_channel(api_client, test_config, test_email, request):
    channel = _create_loopback_channel(api_client, test_config)
    if not channel:
        response = api_client.get("/channels")
        assert response.status_code == 200, f"GET /channels failed: {response.status_code} {response.text[:200]}"
        channels = response.json()
        channel, destination = _select_channel_with_destination(channels, test_email, test_config)
        if not channel:
            pytest.fail("No available channel for IT1.1 message delivery")
        created_channel_id = None
    else:
        destination = test_email
        created_channel_id = channel.get("id")

    def _cleanup():
        if created_channel_id:
            resp = api_client.delete(f"/channels/{created_channel_id}")
            assert resp.status_code in (200, 204), f"Failed to delete channel: {resp.status_code} {resp.text[:200]}"

    request.addfinalizer(_cleanup)
    return channel, destination


def check_server_available(api_base_url: str):
    """Check if API server is running, skip test if not"""
    try:
        response = httpx.get(f"{api_base_url}/health", timeout=2.0)
        if response.status_code != 200:
            pytest.fail("API server is not running or not healthy")
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.fail("API server is not running (connection refused)")


class TestBasicEndpoints:
    """Test basic endpoints (no auth required)"""
    
    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_root_endpoint(self, api_client):
        """Test GET / returns the API root JSON.

        In the unified app, GET / without an API key serves the browser SPA shell
        (PS-77 CW-M1). An API client must send X-API-Key to reach the JSON root —
        api_client carries it (unauthenticated httpx.get("/") returns the SPA HTML).
        """
        response = api_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "running"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_health_endpoint(self, api_base_url):
        """Test GET /health"""

        response = httpx.get(f"{api_base_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        # Support both legacy server health schema and platform-api-kit schema.
        assert "application" in data or "app" in data
        if "database" in data:
            assert data["database"] in {"connected", "disconnected"}
        if "checks" in data:
            assert isinstance(data["checks"], dict)


class TestAuthentication:
    """Test API key authentication"""
    
    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_protected_endpoint_without_key(self, api_base_url):
        """Test that protected endpoints require API key"""
        response = httpx.get(f"{api_base_url}/status")
        assert response.status_code == 401
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_protected_endpoint_with_invalid_key(self, api_base_url):
        """Test that invalid API key is rejected"""

        headers = {"X-API-Key": "invalid_key"}
        response = httpx.get(f"{api_base_url}/status", headers=headers)
        assert response.status_code == 401
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_protected_endpoint_with_valid_key(self, api_client):
        """Test that valid API key is accepted"""
        response = api_client.get("/status")
        assert response.status_code == 200


class TestStatusEndpoints:
    """Test status and config endpoints"""

    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_status_endpoint(self, api_client):
        """Test GET /status"""
        response = api_client.get("/status")
        assert response.status_code == 200
        data = response.json()
        # Support both legacy rich status payload and platform-api-kit status payload.
        if "queue_depth" in data:
            assert isinstance(data["queue_depth"], int)
        if "channels" in data:
            assert isinstance(data["channels"], dict)
        assert (
            "queue_depth" in data
            or "status" in data
            or "checks" in data
        ), f"Unexpected /status payload: {data}"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_config_endpoint_masks_secrets(self, api_client):
        """Test GET /config masks sensitive values"""

        response = api_client.get("/config")
        assert response.status_code == 200
        data = response.json()
        
        # Check that passwords/keys are redacted
        if "api_server" in data and "api_key" in data["api_server"]:
            assert "REDACTED" in data["api_server"]["api_key"]


class TestChannelsAPI:
    """Test channels endpoints"""
    
    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_list_channels(self, api_client):
        """Test GET /channels"""
        response = api_client.get("/channels")
        assert response.status_code == 200
        channels = response.json()
        assert isinstance(channels, list)
        assert len(channels) > 0  # Should have default channels
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_get_channel_by_id(self, api_client):
        """Test GET /channels/{id}"""

        # First get list to find an ID
        response = api_client.get("/channels")
        channels = response.json()
        
        if len(channels) > 0:
            channel_id = channels[0]["id"]
            response = api_client.get(f"/channels/{channel_id}")
            assert response.status_code == 200
            channel = response.json()
            assert channel["id"] == channel_id
            assert "name" in channel
            assert "type" in channel
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_get_nonexistent_channel(self, api_client):
        """Test GET /channels/{id} with invalid ID"""
        response = api_client.get("/channels/99999")
        assert response.status_code == 404
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_channel_crud(self, api_client, test_config):
        """Test POST/GET/PATCH/DELETE /channels"""

        created = _create_loopback_channel(api_client, test_config)
        channel_id = created.get("id")
        assert channel_id, "Channel ID missing from create response"

        try:
            get_resp = api_client.get(f"/channels/{channel_id}")
            assert get_resp.status_code == 200, f"GET /channels/{{id}} failed: {get_resp.status_code} {get_resp.text[:200]}"
            channel = get_resp.json()
            assert channel.get("id") == channel_id

            patch_resp = api_client.patch(
                f"/channels/{channel_id}",
                json={"enabled": False},
            )
            assert patch_resp.status_code == 200, f"PATCH /channels failed: {patch_resp.status_code} {patch_resp.text[:200]}"
            assert patch_resp.json().get("enabled") in (0, False)
        finally:
            del_resp = api_client.delete(f"/channels/{channel_id}")
            assert del_resp.status_code in (200, 204), f"DELETE /channels failed: {del_resp.status_code} {del_resp.text[:200]}"


class TestMessagesAPI:
    """Test messages endpoints"""
    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_create_message_success(self, api_client, api_base_url, api_key, message_channel, test_config):
        """Test POST /messages - successful creation AND delivery processing"""
        channel, destination = message_channel
        channel_name = str(channel.get("name"))
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {
                    "channel": channel_name,
                    "address": destination
                }
            ],
            "content": [
                {
                    "type": "text",
                    "body": _load_example_message()
                }
            ]
        }
        
        response = api_client.post("/messages", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "message_id" in data
        assert data["status"] == "queued"
        assert data["delivery_count"] == 1
        
        message_id = data["message_id"]
        assert message_id is not None

        try:
            if not _is_external_runtime_mode():
                db = _open_test_db(test_config.get("db.uri"))
                try:
                    job_manager = JobManager(db)
                    await process_deliveries(
                        db,
                        job_manager,
                        message_id=message_id,
                        max_cycles=10,
                        timeout=5.0,
                    )
                finally:
                    db.disconnect()

            # VERIFY ACTUAL DELIVERY PROCESSING (API-only)
            delivery = wait_for_delivery_with_diagnostics(
                api_client,
                message_id=message_id,
                api_base_url=api_base_url,
                api_key=api_key,
                max_wait=120.0,
                poll_interval=2.0,
                verbose=True,
            )
            assert delivery is not None
        finally:
            api_client.delete(f"/messages/{message_id}")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_create_message_missing_content(self, api_client, message_channel):
        """Test POST /messages - missing required field"""
        channel, destination = message_channel
        channel_name = str(channel.get("name"))
        payload = {
            "destinations": [
                {
                    "channel": channel_name,
                    "address": destination
                }
            ]
            # Missing content
        }
        
        response = api_client.post("/messages", json=payload)
        
        assert response.status_code == 422  # Validation error
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_create_message_invalid_channel(self, api_client, test_email):
        """Test POST /messages - invalid channel"""

        payload = {
            "destinations": [
                {
                    "channel": "invalid_channel",
                    "address": test_email
                }
            ],
            "content": [
                {
                    "type": "text",
                    "body": "Channel validation message"
                }
            ]
        }
        
        response = api_client.post("/messages", json=payload)
        
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_get_message_by_id(self, api_client, message_channel):
        """Test GET /messages/{id}"""
        channel, destination = message_channel
        channel_name = str(channel.get("name"))
        # First create a message
        payload = {
            "audience_type": "personalised",
            "destinations": [{"channel": channel_name, "address": destination}],
            "content": [{"type": "text", "body": _load_example_message()}]
        }
        response = api_client.post("/messages", json=payload)
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        try:
            # Now get it
            # Increase timeout for message retrieval as it may involve LLM formatting
            response = api_client.get(
                f"/messages/{message_id}",
                timeout=60.0,
                headers={"Accept": "application/json"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == message_id
            assert "deliveries_summary" in data or "deliveries" in data
        finally:
            api_client.delete(f"/messages/{message_id}")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_get_nonexistent_message(self, api_client):
        """Test GET /messages/{id} with invalid ID"""

        response = api_client.get("/messages/99999")
        assert response.status_code == 404
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_get_message_deliveries(self, api_client, message_channel):
        """Test GET /messages/{id}/deliveries"""
        channel, destination = message_channel
        channel_name = str(channel.get("name"))
        # First create a message
        payload = {
            "audience_type": "personalised",
            "destinations": [{"channel": channel_name, "address": destination}],
            "content": [{"type": "text", "body": _load_example_message()}]
        }
        response = api_client.post("/messages", json=payload)
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        try:
            # Get deliveries
            response = api_client.get(f"/messages/{message_id}/deliveries")
            assert response.status_code == 200
            data = response.json()
            assert "total" in data
            assert "items" in data
            assert data["total"] >= 1
        finally:
            api_client.delete(f"/messages/{message_id}")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_idempotency_key(self, api_client, message_channel):
        """Test idempotency key prevents duplicates"""
        channel, destination = message_channel
        channel_name = str(channel.get("name"))

        import time
        # Use unique idempotency key to avoid conflicts from previous test runs
        unique_key = f"test-idempotency-{int(time.time() * 1000)}"
        
        payload = {
            "idempotency_key": unique_key,
            "destinations": [
                {
                    "channel": channel_name,
                    "address": destination
                }
            ],
            "content": [
                {
                    "type": "text",
                    "body": _load_example_message()
                }
            ]
        }
        
        # First request should succeed
        response1 = api_client.post("/messages", json=payload)
        assert response1.status_code == 201
        message_id = response1.json().get("message_id")
        
        # Second request with same key should be rejected
        response2 = api_client.post("/messages", json=payload)
        assert response2.status_code == 409  # Conflict
        
        if message_id:
            api_client.delete(f"/messages/{message_id}")


class TestChannelOperations:
    """Test channel management operations"""
    
    @pytest.fixture(autouse=True)
    def _check_server(self, api_base_url):
        """Check server availability before each test"""
        check_server_available(api_base_url)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_test_channel(self, api_client, test_email, test_config):
        """Test POST /channels/{id}/test"""
        channel = _create_smtp_channel(api_client, test_config)
        channel_id = channel["id"]
        test_payload = {
            "destination": test_email,
            "test_message": _load_example_message(),
        }
        try:
            response = api_client.post(f"/channels/{channel_id}/test", json=test_payload)
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
        finally:
            api_client.post(f"/channels/{channel_id}/disable")


if __name__ == "__main__":
    print("Running API tests...")
    print("\nNote: Server must be running at the configured API base URL")
    print("Start server with: python start_api_server.py --env <ENV_FILE>\n")
    
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.heavy]
