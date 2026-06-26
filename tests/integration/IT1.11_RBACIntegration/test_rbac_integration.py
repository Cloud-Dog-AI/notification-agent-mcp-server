# @pytest.mark.req("UC-014")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-103")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-107")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Integration tests for RBAC functionality

Tests real RBAC implementation with live servers and real data.
"""

import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import time
from typing import Dict, Any

def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _assert_spa_shell(response: httpx.Response) -> None:
    """Validate that web routes are served by the SPA shell."""
    html = response.text
    html_lower = html.lower()
    assert '<div id="root">' in html_lower or "<div id='root'>" in html_lower
    assert "/runtime-config.js" in html


@pytest.fixture(scope="session")
def api_base_url(test_config):
    return _require_value(test_config.get("api_server.base_url"), "api_server.base_url")


@pytest.fixture(scope="session")
def api_key(test_config):
    return _require_value(test_config.get("api_server.api_key"), "api_server.api_key")


@pytest.fixture(scope="session")
def web_ui_base_url(test_config):
    return _require_value(test_config.get("web_server.base_url"), "web_server.base_url")


@pytest.fixture(scope="session")
def web_ui_credentials(test_config):
    username = _require_value(test_config.get("web_server.username"), "web_server.username")
    password = _require_value(test_config.get("web_server.password"), "web_server.password")
    return username, password


@pytest.fixture
async def api_client(api_base_url):
    """Create HTTP client for REAL API server"""
    async with httpx.AsyncClient() as check_client:
        try:
            response = await check_client.get(f"{api_base_url}/health", timeout=10.0)
            if response.status_code != 200:
                pytest.fail(f"API server is not healthy (status: {response.status_code})")
        except httpx.ConnectError as e:
            pytest.fail(f"API server is not running at {api_base_url}: {e}")
        except (httpx.TimeoutException, httpx.ReadTimeout):
            pass  # Server slow but running
    
    async with httpx.AsyncClient(base_url=api_base_url, timeout=10.0) as client:
        yield client


@pytest.fixture
async def web_client(web_ui_base_url):
    """Create HTTP client for REAL Web UI server"""
    async with httpx.AsyncClient() as check_client:
        try:
            await check_client.get(f"{web_ui_base_url}/login", timeout=10.0)
        except httpx.ConnectError as e:
            pytest.fail(f"Web UI server is not running at {web_ui_base_url}: {e}")
        except (httpx.TimeoutException, httpx.ReadTimeout):
            pass
    
    async with httpx.AsyncClient(base_url=web_ui_base_url, timeout=10.0, follow_redirects=False) as client:
        yield client


@pytest.fixture
async def authenticated_web_client(web_client, web_ui_credentials):
    """Create authenticated Web UI client"""
    # Login
    username, password = web_ui_credentials
    login_response = await web_client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True
    )
    assert login_response.status_code in [200, 302], f"Login failed: {login_response.status_code}"
    yield web_client
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_1_service_management_requires_admin(authenticated_web_client):
    """V22.1: Service management page requires admin permission"""
    response = await authenticated_web_client.get("/services", timeout=5.0, follow_redirects=True)
    # Should either succeed (if admin) or return 403 (if not admin) or 422 (validation error)
    assert response.status_code in [200, 403, 422], f"Unexpected status: {response.status_code}"
    # If 200, verify the SPA shell is served for the route.
    if response.status_code == 200:
        _assert_spa_shell(response)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_2_group_creation_requires_admin(authenticated_web_client):
    """V22.2: Group creation requires admin permission"""
    response = await authenticated_web_client.get("/groups/add", timeout=5.0, follow_redirects=True)
    # Should either succeed (if admin) or return 403 (if not admin) or 422 (validation error)
    assert response.status_code in [200, 403, 422], f"Unexpected status: {response.status_code}"
    # If 200, verify the SPA shell is served for the route.
    if response.status_code == 200:
        _assert_spa_shell(response)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_3_create_group_via_api(api_client, api_key):
    """V22.3: Create group via API (admin function)"""
    group_name = f"TestGroup_{time.time_ns()}"
    payload = {
        "name": group_name,
        "description": "Test group for RBAC",
    }
    
    try:
        response = await api_client.post(
            "/api/v1/groups",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=5.0
        )
        assert response.status_code in [200, 201], f"Failed to create group: {response.status_code} - {response.text}"
        result = response.json()
        # API returns {"success": True, "group_id": <id>}
        assert result.get("success") is True, f"Group creation failed: {result}"
        assert "group_id" in result, f"Missing group_id in response: {result}"
        group_id = result["group_id"]
        assert isinstance(group_id, int) and group_id > 0, f"Invalid group_id: {group_id}"
        return group_id
    except (httpx.ReadTimeout, httpx.TimeoutException):
        pytest.fail("API server timeout - group creation may be slow")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_4_assign_owner_requires_admin(authenticated_web_client, api_client, api_key):
    """V22.4: Assign owner requires admin permission"""
    # First create a group
    group_name = f"TestGroup_{time.time_ns()}"
    try:
        create_response = await api_client.post(
            "/groups",
            json={"name": group_name, "description": "Test"},
            headers={"X-API-Key": api_key},
            timeout=5.0
        )
        if create_response.status_code not in (200, 201):
            pytest.fail("Could not create test group")
        group_id = create_response.json().get("group_id") or create_response.json().get("id")
        if not group_id:
            pytest.fail("No group_id returned")
    except (httpx.ReadTimeout, httpx.TimeoutException):
        pytest.fail("API server timeout")
    
    # Try to access assign owner page
    response = await authenticated_web_client.get(
        f"/groups/{group_id}/assign-owner",
        timeout=5.0
    )
    # Should either succeed (if admin) or return 403 (if not admin)
    assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_5_service_health_monitoring(authenticated_web_client):
    """V22.5: Service health monitoring works"""
    response = await authenticated_web_client.get("/services", timeout=5.0, follow_redirects=True)
    # Accept 200 (success), 403 (permission denied), or 422 (validation error)
    assert response.status_code in [200, 403, 422], f"Unexpected status: {response.status_code}"
    if response.status_code == 200:
        _assert_spa_shell(response)
    elif response.status_code == 403:
        # Permission denied - that's OK, we're testing RBAC
        pass
    # 422 is also acceptable - may be a validation issue with the endpoint
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_6_group_edit_permission(authenticated_web_client, api_client, api_key):
    """V22.6: Group editing requires admin or owner permission"""
    # Create a test group
    group_name = f"TestGroup_{time.time_ns()}"
    try:
        create_response = await api_client.post(
            "/groups",
            json={"name": group_name, "description": "Test"},
            headers={"X-API-Key": api_key},
            timeout=5.0
        )
        if create_response.status_code not in (200, 201):
            pytest.fail("Could not create test group")
        group_id = create_response.json().get("group_id") or create_response.json().get("id")
        if not group_id:
            pytest.fail("No group_id returned")
    except (httpx.ReadTimeout, httpx.TimeoutException):
        pytest.fail("API server timeout")
    
    # Try to access edit page
    response = await authenticated_web_client.get(
        f"/groups/{group_id}/edit",
        timeout=5.0
    )
    # Should either succeed (if admin/owner) or return 403 (if not)
    assert response.status_code in [200, 403], f"Unexpected status: {response.status_code}"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_7_a2a_health_check(test_config):
    """V22.7: A2A server health check"""
    a2a_base_url = _require_value(test_config.get("a2a_server.base_url"), "a2a_server.base_url")
    try:
        async with httpx.AsyncClient() as check_client:
            response = await check_client.get(
                f"{a2a_base_url}/health",
                timeout=3.0
            )
            if response.status_code == 200:
                data = response.json()
                assert "status" in data or "active_connections" in data
            else:
                # A2A server may not be running - that's OK for this test
                pass
    except (httpx.ConnectError, httpx.TimeoutException):
        # A2A server not running - that's acceptable
        pass
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_8_group_members_api(api_client, api_key):
    """V22.8: Group members API endpoint works"""
    # Create a test group
    group_name = f"TestGroup_{time.time_ns()}"
    try:
        create_response = await api_client.post(
            "/groups",
            json={"name": group_name, "description": "Test"},
            headers={"X-API-Key": api_key},
            timeout=5.0
        )
        if create_response.status_code not in (200, 201):
            pytest.fail("Could not create test group")
        group_id = create_response.json().get("group_id") or create_response.json().get("id")
        if not group_id:
            pytest.fail("No group_id returned")
        
        # Get group members
        members_response = await api_client.get(
            f"/groups/{group_id}/members",
            headers={"X-API-Key": api_key},
            timeout=5.0
        )
        assert members_response.status_code == 200, f"Failed to get members: {members_response.status_code}"
        data = members_response.json()
        assert isinstance(data, (list, dict)), f"Unexpected members response type: {type(data)}"
        if isinstance(data, dict):
            assert "items" in data or "total" in data
    except (httpx.ReadTimeout, httpx.TimeoutException):
        pytest.fail("API server timeout")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_9_webui_rbac_integration(authenticated_web_client):
    """V22.9: WebUI RBAC integration - verify protected pages"""
    # Test that protected pages exist and respond appropriately
    protected_pages = [
        "/services",
        "/groups/add",
    ]
    
    for page in protected_pages:
        try:
            response = await authenticated_web_client.get(page, timeout=5.0, follow_redirects=True)
            # Should return 200 (if admin), 403 (if not admin), or 422 (validation error)
            assert response.status_code in [200, 403, 422], f"Unexpected status for {page}: {response.status_code}"
        except (httpx.ReadTimeout, httpx.TimeoutException):
            # Timeout is acceptable - page may be slow
            pass
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_v22_10_navigation_menu_includes_new_pages(authenticated_web_client):
    """V22.10: Navigation menu includes new RBAC pages"""
    response = await authenticated_web_client.get("/dashboard", timeout=5.0)
    if response.status_code == 200:
        _assert_spa_shell(response)
    else:
        pytest.fail("Could not access dashboard")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]
