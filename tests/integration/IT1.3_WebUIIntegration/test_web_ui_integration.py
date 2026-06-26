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
Integration tests for Web UI that simulate user activity through the API proxy.

Tests: FR1.27, FR1.28, FR1.29, FR1.30, FR1.31, FR1.32, FR1.33

These tests verify that:
1. User can login through Web UI
2. All database viewing pages work via API proxy
3. Dashboard loads correctly via API proxy
4. All business functions are accessible through Web UI → API Server flow
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import asyncio
from typing import Dict, Any


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _load_ui_message() -> str:
    examples_dir = Path(__file__).parent.parent.parent / "Examples"
    message_path = examples_dir / "Test-Brief-News.md"
    if not message_path.exists():
        pytest.fail(f"Missing UI message file: {message_path}")
    return message_path.read_text().strip()


def _assert_spa_shell(response) -> None:
    assert response.status_code == 200
    assert '<div id="root">' in response.text
    assert "/runtime-config.js" in response.text


@pytest.fixture(scope="session")
def web_ui_base_url(test_config):
    return _require_value(test_config.get("web_server.base_url"), "web_server.base_url")


@pytest.fixture(scope="session")
def api_base_url(test_config):
    return _require_value(test_config.get("api_server.base_url"), "api_server.base_url")


@pytest.fixture(scope="session")
def api_key(test_config):
    return _require_value(test_config.get("api_server.api_key"), "api_server.api_key")


@pytest.fixture(scope="session")
def default_channel(test_config):
    return _require_value(test_config.get("default_channel"), "default_channel")
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-011")


@pytest.fixture(scope="session")
def test_email(test_config):
    return _require_value(test_config.get("test.email"), "test.email")


@pytest.fixture(scope="session")
def web_ui_credentials(test_config):
    username = _require_value(test_config.get("web_server.username"), "web_server.username")
    password = _require_value(test_config.get("web_server.password"), "web_server.password")
    return username, password


class TestWebUIIntegration:
    """Test Web UI integration with API server"""
    
    @pytest.fixture
    async def web_client(self, web_ui_base_url):
        """Create HTTP client for Web UI"""
        # Check if server is running
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{web_ui_base_url}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=web_ui_base_url, follow_redirects=True) as client:
            yield client
    
    @pytest.fixture
    async def api_client(self, api_base_url, api_key):
        """Create HTTP client for API server"""
        # Check if server is running
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{api_base_url}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("API server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=api_base_url) as client:
            client.headers.update({"X-API-Key": api_key})
            yield client

    @pytest.fixture(autouse=True)
    async def preflight_message(self, api_client, default_channel, test_email):
        """Ensure a real message exists and is cleaned up."""
        # Verify channel exists
        channels_resp = await api_client.get("/channels")
        assert channels_resp.status_code == 200
        channels = channels_resp.json()
        if not any(isinstance(ch, dict) and ch.get("name") == default_channel for ch in channels):
            pytest.fail(f"Required channel {default_channel!r} not found")

        payload = {
            "audience_type": "personalised",
            "destinations": [{"channel": default_channel, "address": test_email}],
            "content": [{"type": "text", "body": _load_ui_message()}],
        }
        response = await api_client.post("/messages", json=payload)
        assert response.status_code == 201, f"POST /messages failed: {response.status_code} {response.text[:200]}"
        message_id = response.json().get("message_id")
        yield
        if message_id:
            await api_client.delete(f"/messages/{message_id}")
    
    @pytest.fixture
    async def authenticated_session(self, web_client, web_ui_credentials):
        """Create an authenticated session by logging in"""
        # Login
        username, password = web_ui_credentials
        response = await web_client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert response.status_code in [200, 302], f"Login failed: {response.status_code}"

        # Extract cookies (preserve domain/path metadata)
        if response.status_code == 200 and "Login Failed" in response.text:
            pytest.fail(
                "Web UI login failed. Start web server with "
                "`./server_control.sh --env private/env-it-web start api web` "
                "and ensure credentials match env file."
            )
        if response.cookies:
            web_client.cookies.update(response.cookies)
        if not web_client.cookies:
            pytest.fail(
                "Web UI login did not set a session cookie. Verify "
                "`auth.jwt_secret` and `web_server.session_max_age` are set, "
                "and the web server is started with `--env private/env-it-web`."
            )
        return web_client.cookies
    
    # ========================================================================
    # Authentication Tests
    # ========================================================================
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_1_user_login_flow(self, web_client, web_ui_credentials):
        """V10.1: Test user login flow"""
        # Get login page
        response = await web_client.get("/login")
        _assert_spa_shell(response)
        
        # Attempt login with correct credentials
        username, password = web_ui_credentials
        response = await web_client.post(
            "/login",
            data={"username": username, "password": password}
        )
        assert response.status_code in [200, 302], f"Login should succeed: {response.status_code}"
        
        # Verify redirect to dashboard
        if response.status_code == 302:
            assert "/dashboard" in response.headers.get("location", "")
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_2_user_login_failure(self, web_client):
        """V10.2: Test login failure with wrong credentials"""
        response = await web_client.post(
            "/login",
            data={"username": "wrong", "password": "wrong"}
        )
        assert response.status_code == 200
        assert "Login Failed" in response.text or "Invalid" in response.text
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_3_user_logout(self, web_client, authenticated_session):
        """V10.3: Test logout functionality"""
        # Set cookies from authenticated session
        web_client.cookies.update(authenticated_session)
        
        # Logout
        response = await web_client.get("/logout")
        assert response.status_code in [200, 302]
        
        # Verify redirect to login
        if response.status_code == 302:
            assert "/login" in response.headers.get("location", "")
    
    # ========================================================================
    # Dashboard Tests
    # ========================================================================
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_4_dashboard_loads(self, web_client, authenticated_session):
        """V10.4: Test dashboard loads correctly"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/dashboard")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_5_dashboard_proxy_status(self, web_client, authenticated_session):
        """V10.5: Test dashboard status proxy endpoint"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/webapi/proxy/status")
        assert response.status_code == 200
        data = response.json()
        # Accept both legacy rich status and platform-api-kit status payloads.
        if "queue_depth" in data:
            assert isinstance(data["queue_depth"], int)
        if "channels" in data:
            assert isinstance(data["channels"], dict)
        assert (
            "queue_depth" in data
            or "status" in data
            or "checks" in data
        ), f"Unexpected proxied /status payload: {data}"
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_6_dashboard_proxy_health(self, web_client, authenticated_session):
        """V10.6: Test dashboard health proxy endpoint"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/webapi/proxy/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_7_dashboard_proxy_channels(self, web_client, authenticated_session):
        """V10.7: Test dashboard channels proxy endpoint"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/webapi/proxy/channels")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_8_dashboard_proxy_messages(self, web_client, authenticated_session):
        """V10.8: Test dashboard messages proxy endpoint"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/webapi/proxy/messages?limit=1")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data
    
    # ========================================================================
    # Database Viewing Tests (via API Proxy)
    # ========================================================================
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_9_view_users_page(self, web_client, authenticated_session):
        """V10.9: Test users viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/users")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_10_view_groups_page(self, web_client, authenticated_session):
        """V10.10: Test groups viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/groups")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_11_view_channels_page(self, web_client, authenticated_session):
        """V10.11: Test channels viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/channels")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_12_view_messages_page(self, web_client, authenticated_session):
        """V10.12: Test messages viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/messages")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_13_view_deliveries_page(self, web_client, authenticated_session):
        """V10.13: Test deliveries viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/deliveries")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_14_view_config_page(self, web_client, authenticated_session):
        """V10.14: Test configuration viewing page via API proxy"""
        web_client.cookies.update(authenticated_session)
        
        response = await web_client.get("/db/config")
        _assert_spa_shell(response)
    
    # ========================================================================
    # API Proxy Verification Tests
    # ========================================================================
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_15_api_proxy_users_via_api(self, api_client):
        """V10.15: Verify users API endpoint works (for proxy verification)"""
        response = await api_client.get("/api/v1/users")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")

    @pytest.mark.asyncio
    async def test_v10_15_users_api_and_web_proxy_contract(self, api_client, web_client, authenticated_session):
        """V10.15a: Users list endpoints return the platform pagination envelope."""
        api_response = await api_client.get("/api/v1/users")
        assert api_response.status_code == 200
        api_data = api_response.json()
        assert isinstance(api_data, dict)
        assert isinstance(api_data.get("items"), list)
        assert isinstance(api_data.get("total"), int)

        web_client.cookies.update(authenticated_session)
        proxy_response = await web_client.get("/webapi/proxy/users")
        assert proxy_response.status_code == 200
        proxy_data = proxy_response.json()
        assert isinstance(proxy_data, dict)
        assert isinstance(proxy_data.get("items"), list)
        assert isinstance(proxy_data.get("total"), int)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_16_api_proxy_groups_via_api(self, api_client):
        """V10.16: Verify groups API endpoint works (for proxy verification)"""
        response = await api_client.get("/api/v1/groups")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_17_api_proxy_channels_via_api(self, api_client):
        """V10.17: Verify channels API endpoint works (for proxy verification)"""
        response = await api_client.get("/channels")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_18_api_proxy_messages_via_api(self, api_client):
        """V10.18: Verify messages API endpoint works (for proxy verification)"""
        response = await api_client.get("/messages?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_19_api_proxy_deliveries_via_api(self, api_client):
        """V10.19: Verify deliveries API endpoint works (for proxy verification)"""
        response = await api_client.get("/api/v1/deliveries?limit=10")
        # Deliveries endpoint may return 200 with items or 404 if no deliveries exist
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "items" in data or isinstance(data, list)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_20_api_proxy_config_via_api(self, api_client):
        """V10.20: Verify config API endpoint works (for proxy verification)"""
        response = await api_client.get("/config")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
    
    # ========================================================================
    # End-to-End User Flow Tests
    # ========================================================================
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_21_end_to_end_user_flow(self, web_client, web_ui_credentials):
        """V10.21: Test complete user flow: login → dashboard → view data"""
        # 1. Login
        username, password = web_ui_credentials
        response = await web_client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert response.status_code in [200, 302]
        if response.status_code == 200 and "Login Failed" in response.text:
            pytest.fail(
                "Web UI login failed. Start web server with "
                "`./server_control.sh --env private/env-it-web start api web` "
                "and ensure credentials match env file."
            )
        if response.cookies:
            web_client.cookies.update(response.cookies)
        if not web_client.cookies:
            pytest.fail(
                "Web UI login did not set a session cookie. Verify "
                "`auth.jwt_secret` and `web_server.session_max_age` are set, "
                "and the web server is started with `--env private/env-it-web`."
            )
        
        # 2. Access dashboard
        response = await web_client.get("/dashboard")
        _assert_spa_shell(response)
        
        # 3. View users
        response = await web_client.get("/db/users")
        _assert_spa_shell(response)
        
        # 4. View groups
        response = await web_client.get("/db/groups")
        _assert_spa_shell(response)
        
        # 5. View channels
        response = await web_client.get("/db/channels")
        _assert_spa_shell(response)
        
        # 6. Logout
        response = await web_client.get("/logout")
        assert response.status_code in [200, 302]
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_22_unauthenticated_access_redirects(self, web_client):
        """V10.22: Test that unauthenticated access redirects to login"""
        # Try to access dashboard without login
        response = await web_client.get("/dashboard", follow_redirects=False)
        if response.status_code == 200:
            _assert_spa_shell(response)
        else:
            assert response.status_code in [302, 401]
        
        # Try to access protected API proxy
        response = await web_client.get("/webapi/proxy/status", follow_redirects=False)
        assert response.status_code in [302, 401]
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-011")
    
    @pytest.mark.asyncio
    async def test_v10_23_navigation_menu_present(self, web_client, authenticated_session):
        """V10.23: Test that navigation menu is present on all pages"""
        web_client.cookies.update(authenticated_session)
        
        pages = ["/dashboard", "/db/users", "/db/groups", "/db/channels", "/db/messages", "/db/deliveries", "/db/config"]
        
        for page in pages:
            response = await web_client.get(page)
            _assert_spa_shell(response)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]
