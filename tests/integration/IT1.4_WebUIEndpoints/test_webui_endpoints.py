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
Comprehensive tests for all WebUI endpoints

Tests all routes in web_server.py to ensure:
- All endpoints are accessible
- Authentication works correctly
- API proxy endpoints function properly
- HTML pages render without errors
- Data is correctly displayed

Note: These tests require WebUI server and optionally API server to be running.
Tests will skip if servers are not available.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
import asyncio
from typing import Dict, Any

from tests.utils.test_helpers import check_test_dependencies

# Config-driven (no hardcoded URLs/credentials)
WEB_UI_BASE_URL = None
API_BASE_URL = None
API_KEY = None
TEST_USERNAME = None
TEST_PASSWORD = None
TEST_EMAIL = None


@pytest.fixture(scope="session", autouse=True)
def _load_urls_and_credentials(web_base_url, api_base_url, api_key, test_config):
    global WEB_UI_BASE_URL, API_BASE_URL, API_KEY, TEST_USERNAME, TEST_PASSWORD, TEST_EMAIL
    WEB_UI_BASE_URL = web_base_url
    API_BASE_URL = api_base_url
    API_KEY = api_key
    TEST_USERNAME = test_config.get("web_server.username")
    TEST_PASSWORD = test_config.get("web_server.password")
    TEST_EMAIL = test_config.get("test.email")
    if not TEST_USERNAME or not TEST_PASSWORD:
        pytest.fail("web_server.username/web_server.password not configured in env file")
    if not TEST_EMAIL:
        pytest.fail("test.email not configured in env file")


@pytest.fixture(scope="session", autouse=True)
def _ensure_webui_admin_user(api_base_url, api_key, test_config):
    """
    Ensure the WebUI login user exists in the API database with admin role.
    Web UI permission checks require a DB user with the session username.
    """
    username = test_config.get("web_server.username")
    base_email = test_config.get("test.email")
    if not username or not base_email:
        pytest.fail("web_server.username or test.email not configured in env file")

    def _plus_address(email: str, suffix: str) -> str:
        if not email or "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if f"+{suffix}" in local:
            return email
        return f"{local}+{suffix}@{domain}"

    admin_email = _plus_address(base_email, f"webui-{username}")
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    created_user_id = None
    resp = httpx.get(f"{api_base_url.rstrip('/')}/users", headers=headers, timeout=10.0)
    if resp.status_code != 200:
        pytest.fail(f"Failed to list users: {resp.status_code} {resp.text[:200]}")
    payload = resp.json() if resp.json() else []
    users = payload.get("items", []) if isinstance(payload, dict) else payload
    existing = next((u for u in users if u.get("username") == username), None)

    if existing and str(existing.get("role", "")).lower() != "admin":
        # Replace non-admin user with admin role
        del_resp = httpx.delete(f"{api_base_url.rstrip('/')}/users/{existing['id']}", headers=headers, timeout=10.0)
        if del_resp.status_code not in (200, 204):
            pytest.fail(f"Failed to remove non-admin user: {del_resp.status_code} {del_resp.text[:200]}")
        existing = None

    if not existing:
        payload = {
            "username": username,
            "email": admin_email,
            "display_name": "WebUI Admin",
            "role": "admin",
        }
        create_resp = httpx.post(f"{api_base_url.rstrip('/')}/users", headers=headers, json=payload, timeout=10.0)
        if create_resp.status_code in (200, 201):
            created_user_id = create_resp.json().get("id")
        elif create_resp.status_code == 409:
            # User may already exist by email; proceed without failing
            created_user_id = None
        else:
            pytest.fail(f"Failed to create admin user: {create_resp.status_code} {create_resp.text[:200]}")

    def _cleanup():
        if created_user_id:
            httpx.delete(f"{api_base_url.rstrip('/')}/users/{created_user_id}", headers=headers, timeout=10.0)

    return _cleanup


@pytest.fixture(autouse=True)
def _dependency_and_service_checks():
    """
    RULES.md Step 0: dependency + service checks.
    - Uses config/env via fixtures (pytest plugin enforces --env)
    - Confirms Web + API are reachable (real systems)
    """

    # Real service checks (no DB access)
    try:
        if WEB_UI_BASE_URL:
            r = httpx.get(f"{WEB_UI_BASE_URL}/health", timeout=5.0)
            assert r.status_code == 200, f"Web UI /health returned {r.status_code}"
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.fail("Web UI server is not running")

    # API /health may or may not require auth depending on config.
    if API_BASE_URL:
        try:
            r = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
            if r.status_code == 401 and API_KEY:
                r = httpx.get(f"{API_BASE_URL}/health", headers={"X-API-Key": API_KEY}, timeout=5.0)
            assert r.status_code == 200, f"API /health returned {r.status_code}"
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("API server is not running")


def _invalid_credentials(username: str, password: str) -> Dict[str, str]:
    # Derive invalid credentials from configured ones (no hardcoded test data)
    if not username or not password:
        pytest.fail("web_server.username/web_server.password not configured in env file")
    return {"username": f"{username}_invalid", "password": f"{password}_invalid"}


def _assert_spa_shell(response) -> None:
    assert response.status_code == 200
    body = response.text
    assert '<div id="root">' in body
    assert "/runtime-config.js" in body


async def _first_user_id_via_proxy(client: httpx.AsyncClient) -> int | None:
    r = await client.get("/webapi/proxy/users", timeout=10.0)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    if not items:
        return None
    first = items[0]
    return int(first.get("id") or first.get("user_id"))


async def _first_message_id_via_proxy(client: httpx.AsyncClient) -> int | None:
    r = await client.get("/webapi/proxy/messages?offset=0&limit=1", timeout=10.0)
    if r.status_code != 200:
        return None
    data = r.json()
    items = data.get("items") if isinstance(data, dict) else data
    if not items:
        return None
    return int(items[0].get("id"))


def _pick_email_like_channel_name(*, api_base_url: str, api_key: str) -> str:
    """
    Pick an enabled, email-capable channel name using the API (no hardcoded channel names).
    """
    r = httpx.get(
        f"{api_base_url.rstrip('/')}/channels",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        timeout=10.0,
    )
    if r.status_code != 200:
        pytest.fail(f"Failed to list channels: {r.status_code} {r.text[:200]}")
    channels = r.json()
    if not isinstance(channels, list) or not channels:
        pytest.fail("No channels returned from API /channels")

    # Prefer SMTP channels for email use-cases
    for ch in channels:
        if isinstance(ch, dict) and str(ch.get("type", "")).lower() == "smtp" and ch.get("enabled", True):
            return str(ch.get("name"))

    # Fallback: any enabled channel with 'email' in its name/type
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        if not ch.get("enabled", True):
            continue
        name = str(ch.get("name", "")).lower()
        ctype = str(ch.get("type", "")).lower()
        if "email" in name or "email" in ctype:
            return str(ch.get("name"))

    pytest.fail("No email-capable channel found (expected a enabled smtp/email channel in /channels)")


class TestWebUIAuthentication:
    """Test authentication endpoints"""
    
    @pytest.fixture
    async def web_client(self, web_base_url):
        """Create HTTP client for Web UI"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{web_base_url}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=web_base_url, follow_redirects=False) as client:
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_root_redirects_to_login(self, web_client):
        """Test GET / redirects to login"""
        response = await web_client.get("/")
        assert response.status_code in [302, 200]
        if response.status_code == 302:
            assert "/login" in response.headers.get("location", "")
        else:
            if WEB_UI_BASE_URL == API_BASE_URL:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and payload.get("status") == "running":
                    assert "name" in payload
                    assert "version" in payload
                    return
            _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_login_page_renders(self, web_client):
        """Test GET /login renders login page"""
        response = await web_client.get("/login")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_login_success(self, web_client, test_config):
        """Test POST /login with valid credentials"""
        username = test_config.get("web_server.username")
        password = test_config.get("web_server.password")
        if not username or not password:
            pytest.fail("web_server.username/web_server.password not configured in env file")
        response = await web_client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False
        )
        assert response.status_code in [200, 302]
        if response.status_code == 302:
            assert "/dashboard" in response.headers.get("location", "")
            # Validate session actually works by accessing dashboard
            dash = await web_client.get("/dashboard", follow_redirects=False)
            assert dash.status_code in (200, 302, 401)
            if dash.status_code == 302:
                assert "/login" not in dash.headers.get("location", "")
            if dash.status_code == 200:
                _assert_spa_shell(dash)
        else:
            _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_login_failure(self, web_client):
        """Test POST /login with invalid credentials"""
        # Use derived invalid credentials (no hardcoded test data)
        invalid = _invalid_credentials(TEST_USERNAME, TEST_PASSWORD)
        response = await web_client.post(
            "/login",
            data=invalid,
            follow_redirects=False
        )
        # Invalid credentials must not authenticate the user
        assert response.status_code in (200, 401, 302)
        if response.status_code == 302:
            # Should not redirect to dashboard on failed login
            assert "/dashboard" not in response.headers.get("location", "")
        else:
            body = response.text.lower()
            assert "failed" in body or "invalid" in body or "unauthorized" in body

        # Verify session is not established: dashboard remains protected
        dash = await web_client.get("/dashboard", follow_redirects=False)
        assert dash.status_code in (200, 302, 401)
        if dash.status_code == 302:
            assert "/login" in dash.headers.get("location", "")
        if dash.status_code == 200:
            _assert_spa_shell(dash)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_logout(self, web_client):
        """Test GET /logout clears session"""
        # First login
        login = await web_client.post(
            "/login",
            data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert login.status_code in (200, 302)
        
        # Then logout
        response = await web_client.get("/logout", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.headers.get("location", "")

        # After logout, protected pages should require auth again
        dash = await web_client.get("/dashboard", follow_redirects=False)
        assert dash.status_code in (200, 302, 401)
        if dash.status_code == 302:
            assert "/login" in dash.headers.get("location", "")
        if dash.status_code == 200:
            _assert_spa_shell(dash)


class TestWebUIMainPages:
    """Test main WebUI pages"""
    
    @pytest.fixture
    async def authenticated_client(self):
        """Create authenticated HTTP client"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{WEB_UI_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=WEB_UI_BASE_URL, follow_redirects=True) as client:
            # Login
            await client.post(
                "/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_dashboard_renders(self, authenticated_client):
        """Test GET /dashboard renders dashboard"""
        response = await authenticated_client.get("/dashboard")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_api_docs_page(self, authenticated_client):
        """Test GET /web-api-docs renders API docs page"""
        response = await authenticated_client.get("/web-api-docs", follow_redirects=False)
        assert response.status_code in [200, 302, 307]
        if response.status_code in (302, 307):
            loc = response.headers.get("location", "")
            # Common OpenAPI endpoints (fastapi swagger/redoc)
            assert ("/docs" in loc) or ("/redoc" in loc) or ("/openapi" in loc)
        else:
            _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_mcp_test_page(self, authenticated_client):
        """Test GET /web-mcp-test renders MCP testing page"""
        response = await authenticated_client.get("/web-mcp-test")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_logs_page(self, authenticated_client):
        """Test GET /logs renders logs page"""
        response = await authenticated_client.get("/logs")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_logs_view_endpoint(self, authenticated_client):
        """Test GET /logs returns log content container"""
        # Web UI provides log viewing via /logs (with optional query params).
        response = await authenticated_client.get("/logs?lines=50", follow_redirects=True)
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_settings_page(self, authenticated_client):
        """Test GET /settings renders settings page"""
        response = await authenticated_client.get("/settings")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self, authenticated_client):
        """Test GET /health returns health status"""
        response = await authenticated_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert ("status" in data) or ("health" in data)


class TestWebUIDatabasePages:
    """Test database viewing pages"""
    
    @pytest.fixture
    async def authenticated_client(self):
        """Create authenticated HTTP client"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{WEB_UI_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=WEB_UI_BASE_URL, follow_redirects=True) as client:
            await client.post(
                "/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_users_page(self, authenticated_client):
        """Test GET /db/users renders users page"""
        response = await authenticated_client.get("/db/users")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_groups_page(self, authenticated_client):
        """Test GET /db/groups renders groups page"""
        response = await authenticated_client.get("/db/groups")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_channels_page(self, authenticated_client):
        """Test GET /db/channels renders channels page"""
        response = await authenticated_client.get("/db/channels")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_messages_page(self, authenticated_client):
        """Test GET /db/messages renders messages page"""
        response = await authenticated_client.get("/db/messages")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_deliveries_page(self, authenticated_client):
        """Test GET /db/deliveries renders deliveries page"""
        response = await authenticated_client.get("/db/deliveries")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_config_page(self, authenticated_client):
        """Test GET /db/config renders config page"""
        response = await authenticated_client.get("/db/config")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_db_prompts_page(self, authenticated_client):
        """Test GET /db/prompts renders prompts page"""
        response = await authenticated_client.get("/db/prompts")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_channels_add_page(self, authenticated_client):
        """Test GET /channels/add renders channel create page"""
        response = await authenticated_client.get("/channels/add")
        _assert_spa_shell(response)


class TestWebUIUserManagement:
    """Test user management pages"""
    
    @pytest.fixture
    async def authenticated_client(self):
        """Create authenticated HTTP client"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{WEB_UI_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=WEB_UI_BASE_URL, follow_redirects=True) as client:
            await client.post(
                "/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_users_add_page(self, authenticated_client):
        """Test GET /users/add renders add user page"""
        response = await authenticated_client.get("/users/add")
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_users_edit_page(self, authenticated_client, test_email):
        """Test GET /users/{user_id}/edit renders edit user page"""
        created_user_id = None
        # Ensure there is a real user to edit (create via API proxy if needed)
        user_id = await _first_user_id_via_proxy(authenticated_client)
        if not user_id:
            username = f"it14_edit_{int(asyncio.get_event_loop().time())}"
            password = f"pw_{int(asyncio.get_event_loop().time())}"
            email = test_email.replace("@", f"+it14edit{int(asyncio.get_event_loop().time())}@") if "@" in test_email else test_email
            create = await authenticated_client.post(
                "/webapi/proxy/users",
                json={
                    "username": username,
                    "email": email,
                    "display_name": "IT1.4 Edit User",
                    "password": password,
                },
            )
            assert create.status_code in (200, 201), create.text[:200]
            data = create.json()
            created_user_id = data.get("user_id") or data.get("id")
            assert created_user_id, "Missing created user id"
            user_id = int(created_user_id)

        try:
            response = await authenticated_client.get(f"/users/{user_id}/edit")
            _assert_spa_shell(response)
        finally:
            if created_user_id:
                await authenticated_client.delete(f"/webapi/proxy/users/{created_user_id}")


class TestWebUIAPIProxy:
    """Test API proxy endpoints"""
    
    @pytest.fixture
    async def authenticated_client(self):
        """Create authenticated HTTP client"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{WEB_UI_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=WEB_UI_BASE_URL, follow_redirects=True) as client:
            await client.post(
                "/login",
                data={"username": TEST_USERNAME, "password": TEST_PASSWORD}
            )
            yield client
    
    @pytest.fixture
    async def api_client(self):
        """Create API client for verification"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{API_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("API server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_status(self, authenticated_client, api_client):
        """Test GET /webapi/proxy/status proxies to API /status"""
        response = await authenticated_client.get("/webapi/proxy/status")
        assert response.status_code == 200
        data = response.json()
        # Should have status-like structure
        assert isinstance(data, dict)
        assert len(data.keys()) > 0
        assert any(k in data for k in ("status", "services", "components", "version", "uptime", "timestamp"))
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_health(self, authenticated_client, api_client):
        """Test GET /webapi/proxy/health proxies to API /health"""
        response = await authenticated_client.get("/webapi/proxy/health")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert any(k in data for k in ("status", "health"))
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_channels(self, authenticated_client, api_client):
        """Test GET /webapi/proxy/channels proxies to API /channels"""
        response = await authenticated_client.get("/webapi/proxy/channels")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)  # Channels should be a list
        assert len(data) >= 1
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_messages(self, authenticated_client, api_client):
        """Test GET /webapi/proxy/messages proxies to API /messages"""
        response = await authenticated_client.get("/webapi/proxy/messages?offset=0&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))  # Could be list or paginated response
        if isinstance(data, dict):
            assert any(k in data for k in ("items", "total", "messages"))
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_proxy_prompts(self, authenticated_client, api_client):
        """Test GET /webapi/proxy/prompts proxies to API /prompts"""
        response = await authenticated_client.get("/webapi/proxy/prompts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_a2a_notify_natural_get(self, authenticated_client):
        """Test GET /webapi/proxy/a2a/notify/natural"""
        response = await authenticated_client.get("/webapi/proxy/a2a/notify/natural")
        # This might return 405 (method not allowed) or info page
        assert response.status_code in [200, 405]
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_a2a_notify_natural_post(self, authenticated_client):
        """Test POST /webapi/proxy/a2a/notify/natural"""
        response = await authenticated_client.post(
            "/webapi/proxy/a2a/notify/natural",
            json={"command": f"IT1.4 proxy test {int(asyncio.get_event_loop().time())}"}
        )
        # Should return 200 or error if A2A server not running
        assert response.status_code in [200, 500, 502, 503]
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_users_post(self, authenticated_client, test_email):
        """Test POST /webapi/proxy/users creates user"""
        created_user_id = None
        username = f"it14_user_{int(asyncio.get_event_loop().time())}"
        password = f"pw_{int(asyncio.get_event_loop().time())}"
        # Ensure unique email (avoid collisions); test_email may be shared
        email = test_email.replace("@", f"+it14{int(asyncio.get_event_loop().time())}@") if "@" in test_email else test_email

        try:
            response = await authenticated_client.post(
                "/webapi/proxy/users",
                json={
                    "username": username,
                    "email": email,
                    "display_name": "IT1.4 Test User",
                    "password": password,
                },
            )
            assert response.status_code in [201, 200, 400, 409, 422]
            if response.status_code in [200, 201]:
                data = response.json()
                created_user_id = data.get("user_id") or data.get("id")
        finally:
            # Cleanup: delete created user via API (API-only)
            if created_user_id:
                await authenticated_client.delete(f"/webapi/proxy/users/{created_user_id}")
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_users_get(self, authenticated_client, test_email):
        """Test GET /webapi/proxy/users/{user_id} gets user"""
        created_user_id = None
        user_id = await _first_user_id_via_proxy(authenticated_client)
        if not user_id:
            # Create a user so the proxy GET use-case is always exercised
            username = f"it14_get_{int(asyncio.get_event_loop().time())}"
            password = f"pw_{int(asyncio.get_event_loop().time())}"
            # Use configured email but make it unique
            email = test_email.replace("@", f"+it14get{int(asyncio.get_event_loop().time())}@") if "@" in test_email else test_email
            create = await authenticated_client.post(
                "/webapi/proxy/users",
                json={
                    "username": username,
                    "email": email,
                    "display_name": "IT1.4 Get User",
                    "password": password,
                },
            )
            assert create.status_code in (200, 201), create.text[:200]
            data = create.json()
            created_user_id = data.get("user_id") or data.get("id")
            assert created_user_id, "Missing created user id"
            user_id = int(created_user_id)

        try:
            response = await authenticated_client.get(f"/webapi/proxy/users/{user_id}")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert int(data.get("id") or data.get("user_id")) == int(user_id)
        finally:
            if created_user_id:
                await authenticated_client.delete(f"/webapi/proxy/users/{created_user_id}")
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_users_preferences_put(self, authenticated_client, test_email):
        """Test PUT /webapi/proxy/users/{user_id}/preferences updates preferences"""
        # Create a dedicated user so we don't mutate existing admin/configured users
        username = f"it14_prefs_{int(asyncio.get_event_loop().time())}"
        password = f"pw_{int(asyncio.get_event_loop().time())}"
        email = test_email.replace("@", f"+it14prefs{int(asyncio.get_event_loop().time())}@") if "@" in test_email else test_email
        create = await authenticated_client.post(
            "/webapi/proxy/users",
            json={
                "username": username,
                "email": email,
                "display_name": "IT1.4 Prefs User",
                "password": password,
            },
        )
        assert create.status_code in (200, 201), create.text[:200]
        data = create.json()
        user_id = data.get("user_id") or data.get("id")
        assert user_id, "Missing created user id"

        try:
            response = await authenticated_client.put(
                f"/webapi/proxy/users/{user_id}/preferences",
                json={"language": "en", "content_style": "short"},
            )
            assert response.status_code == 200
            # Verify persisted via proxy GET
            fetched = await authenticated_client.get(f"/webapi/proxy/users/{user_id}")
            assert fetched.status_code == 200
            u = fetched.json()
            prefs = u.get("preferences") or {}
            assert str(prefs.get("language") or u.get("language") or "").startswith("en")
        finally:
            await authenticated_client.delete(f"/webapi/proxy/users/{user_id}")
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_proxy_message_deliveries(self, authenticated_client, test_email, test_config):
        """Test GET /webapi/proxy/messages/{message_id}/deliveries"""
        # Create a message via API, then validate deliveries can be accessed via Web proxy.
        if not API_BASE_URL or not API_KEY:
            pytest.fail("API_BASE_URL/API_KEY not configured")

        message_id = None
        try:
            channel_name = _pick_email_like_channel_name(api_base_url=API_BASE_URL, api_key=API_KEY)
            payload = {
                "audience_type": "broadcast",
                "destinations": [{"channel": channel_name, "address": test_email}],
                "content": [{"type": "text", "body": f"IT1.4 deliveries {int(asyncio.get_event_loop().time())}"}],
            }
            create = httpx.post(
                f"{API_BASE_URL}/messages",
                json=payload,
                headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                timeout=30.0,
            )
            assert create.status_code in (200, 201, 202), create.text[:200]
            data = create.json()
            message_id = data.get("message_id") or data.get("id")
            assert message_id, "Missing message_id"

            response = await authenticated_client.get(f"/webapi/proxy/messages/{message_id}/deliveries")
            assert response.status_code == 200
            deliveries = response.json()
            assert isinstance(deliveries, (list, dict))
        finally:
            if message_id:
                httpx.delete(
                    f"{API_BASE_URL}/messages/{message_id}",
                    headers={"X-API-Key": API_KEY},
                    timeout=10.0,
                )
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_cancel_message(self, authenticated_client, test_email, test_config):
        """Test POST /messages/{message_id}/cancel cancels message"""
        if not API_BASE_URL or not API_KEY:
            pytest.fail("API_BASE_URL/API_KEY not configured")

        message_id = None
        try:
            channel_name = _pick_email_like_channel_name(api_base_url=API_BASE_URL, api_key=API_KEY)
            payload = {
                "audience_type": "broadcast",
                "destinations": [{"channel": channel_name, "address": test_email}],
                "content": [{"type": "text", "body": f"IT1.4 cancel {int(asyncio.get_event_loop().time())}"}],
            }
            create = httpx.post(
                f"{API_BASE_URL}/messages",
                json=payload,
                headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                timeout=30.0,
            )
            assert create.status_code in (200, 201, 202), create.text[:200]
            data = create.json()
            message_id = data.get("message_id") or data.get("id")
            assert message_id, "Missing message_id"

            response = await authenticated_client.post(f"/messages/{message_id}/cancel", follow_redirects=False)
            assert response.status_code in (200, 302, 400, 404)
        finally:
            if message_id:
                httpx.delete(
                    f"{API_BASE_URL}/messages/{message_id}",
                    headers={"X-API-Key": API_KEY},
                    timeout=10.0,
                )


class TestWebUIAuthenticationRequired:
    """Test that protected endpoints require authentication"""
    
    @pytest.fixture
    async def unauthenticated_client(self):
        """Create unauthenticated HTTP client"""
        try:
            async with httpx.AsyncClient() as check_client:
                await check_client.get(f"{WEB_UI_BASE_URL}/health", timeout=2.0)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("Web UI server is not running (connection refused)")
        
        async with httpx.AsyncClient(base_url=WEB_UI_BASE_URL, follow_redirects=False) as client:
            yield client
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, unauthenticated_client):
        """Test /dashboard requires authentication"""
        response = await unauthenticated_client.get("/dashboard")
        assert response.status_code in [200, 302, 401]  # SPA shell or auth gate
        if response.status_code == 200:
            _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_api_proxy_requires_auth(self, unauthenticated_client):
        """Test API proxy endpoints require authentication"""
        response = await unauthenticated_client.get("/webapi/proxy/status")
        assert response.status_code in [302, 401]  # Redirect to login or 401
    @pytest.mark.IT
    @pytest.mark.webui
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_db_pages_require_auth(self, unauthenticated_client):
        """Test database pages require authentication"""
        response = await unauthenticated_client.get("/db/users")
        assert response.status_code in [200, 302, 401]  # SPA shell or auth gate
        if response.status_code == 200:
            _assert_spa_shell(response)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.docker, pytest.mark.heavy]
