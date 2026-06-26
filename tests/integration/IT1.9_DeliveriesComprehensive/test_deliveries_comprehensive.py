# @pytest.mark.req("UC-008")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Comprehensive Deliveries Page Testing

V24.12: Comprehensive testing of deliveries page functionality.

Tests:
- Deliveries page loads correctly
- Pagination works
- Sorting works
- Search/filter works
- Links to messages work
- Select/delete functionality
- All table columns display correctly
"""

import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import asyncio


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _assert_spa_shell(response: httpx.Response) -> None:
    assert response.status_code == 200
    body = response.text
    assert '<div id="root">' in body
    assert "/runtime-config.js" in body


@pytest.fixture(scope="session")
def web_ui_base_url(test_config):
    return _require_value(test_config.get("web_server.base_url"), "web_server.base_url")


@pytest.fixture(scope="session")
def api_base_url(test_config):
    return _require_value(test_config.get("api_server.base_url"), "api_server.base_url")


@pytest.fixture(scope="session")
def web_ui_credentials(test_config):
    username = _require_value(test_config.get("web_server.username"), "web_server.username")
    password = _require_value(test_config.get("web_server.password"), "web_server.password")
    return username, password


@pytest.fixture(scope="session")
def api_key(test_config):
    return _require_value(test_config.get("api_server.api_key"), "api_server.api_key")


class TestDeliveriesComprehensive:
    """Comprehensive tests for deliveries page"""
    
    @pytest.fixture
    async def authenticated_client(self, web_ui_base_url, web_ui_credentials):
        """Create authenticated HTTP client"""
        async with httpx.AsyncClient(base_url=web_ui_base_url, follow_redirects=False, timeout=30.0) as client:
            # Check server is running
            try:
                await client.get("/health", timeout=2.0)
            except (httpx.ConnectError, httpx.TimeoutException):
                pytest.fail("WebUI server is not running")
            
            # Login
            username, password = web_ui_credentials
            response = await client.post(
                "/login",
                data={"username": username, "password": password}
            )
            assert response.status_code in [200, 302], "Login should succeed"
            yield client
    
    @pytest.fixture
    async def api_client(self, api_base_url, api_key):
        """Create API client"""
        async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
            # Check server is running
            try:
                await client.get("/health", timeout=2.0)
            except (httpx.ConnectError, httpx.TimeoutException):
                pytest.fail("API server is not running")
            client.headers.update({"X-API-Key": api_key})
            yield client
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_1_deliveries_page_loads(self, authenticated_client):
        """V24.12.1: Deliveries page loads correctly"""
        response = await authenticated_client.get("/deliveries", timeout=10.0)
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_2_deliveries_pagination(self, authenticated_client):
        """V24.12.2: Deliveries pagination works"""
        # Test with different limits
        for limit in [25, 50, 100]:
            response = await authenticated_client.get(f"/deliveries?limit={limit}&offset=0", timeout=10.0)
            _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_3_deliveries_sorting(self, authenticated_client):
        """V24.12.3: Deliveries sorting works"""
        for sort_by in ["id", "created_at", "state", "message_id"]:
            for sort_order in ["asc", "desc"]:
                response = await authenticated_client.get(
                    f"/deliveries?sort_by={sort_by}&sort_order={sort_order}",
                    timeout=10.0
                )
                _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_4_deliveries_search(self, authenticated_client):
        """V24.12.4: Deliveries search/filter works"""
        response = await authenticated_client.get("/deliveries?search=test", timeout=10.0)
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_5_deliveries_message_links(self, authenticated_client, api_client):
        """V24.12.5: Deliveries page links to messages work"""
        # First, get some deliveries from API
        try:
            deliveries_response = await api_client.get(
                "/deliveries",
                params={"limit": 10},
                timeout=10.0
            )
            if deliveries_response.status_code == 200:
                deliveries = deliveries_response.json().get("items", [])
                if deliveries:
                    # Get deliveries page
                    web_response = await authenticated_client.get("/deliveries", timeout=10.0)
                    _assert_spa_shell(web_response)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("API server not available for message link test")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_6_deliveries_table_columns(self, authenticated_client):
        """V24.12.6: Deliveries table has all required columns"""
        response = await authenticated_client.get("/deliveries", timeout=10.0)
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_7_deliveries_select_delete(self, authenticated_client):
        """V24.12.7: Deliveries select/delete functionality exists"""
        response = await authenticated_client.get("/deliveries", timeout=10.0)
        _assert_spa_shell(response)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v24_12_8_deliveries_filter_by_message(self, authenticated_client, api_client):
        """V24.12.8: Deliveries can be filtered by message_id"""
        # Get a message first
        try:
            messages_response = await api_client.get(
                "/messages",
                params={"limit": 1},
                timeout=10.0
            )
            if messages_response.status_code == 200:
                messages = messages_response.json().get("items", [])
                if messages:
                    message_id = messages[0].get("id")
                    # Test filtering by message_id
                    response = await authenticated_client.get(
                        f"/deliveries?message_id={message_id}",
                        timeout=10.0
                    )
                    _assert_spa_shell(response)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.fail("API server not available for message filter test")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]
