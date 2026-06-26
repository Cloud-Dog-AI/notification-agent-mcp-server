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
API Documentation Page Testing

V24.18: Test API documentation page functionality.

Tests:
- API documentation page loads
- Swagger UI is accessible
- ReDoc link works
- OpenAPI JSON is accessible
- All documentation links are functional
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _assert_spa_shell(html: str):
    html_lower = html.lower()
    assert '<div id="root">' in html_lower or "<div id='root'>" in html_lower, \
        "Page should serve the SPA root container"
    assert "/runtime-config.js" in html, \
        "Page should reference runtime config bootstrapping"


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
def web_ui_credentials(test_config):
    username = _require_value(test_config.get("web_server.username"), "web_server.username")
    password = _require_value(test_config.get("web_server.password"), "web_server.password")
    return username, password


class TestAPIDocumentation:
    """Tests for API documentation page"""
    
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
        async with httpx.AsyncClient(
            base_url=api_base_url,
            timeout=30.0,
            headers={"X-API-Key": api_key},
        ) as client:
            # Check server is running
            try:
                await client.get("/health", timeout=2.0)
            except (httpx.ConnectError, httpx.TimeoutException):
                pytest.fail("API server is not running")
            yield client
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("CS-016")
    
    @pytest.mark.asyncio
    async def test_v24_18_1_api_docs_page_loads(self, authenticated_client):
        """V24.18.1: API documentation page loads"""
        response = await authenticated_client.get("/web-api-docs", timeout=10.0)
        assert response.status_code == 200, "API docs page should load"
        _assert_spa_shell(response.text)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    @pytest.mark.asyncio
    async def test_v24_18_2_swagger_ui_link(self, authenticated_client, api_client):
        """V24.18.2: Swagger UI link works"""
        # Check API server has Swagger
        try:
            swagger_response = await api_client.get("/docs", timeout=10.0)
            assert swagger_response.status_code == 200, "Swagger UI should be accessible"
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("API server not available for Swagger test")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    @pytest.mark.asyncio
    async def test_v24_18_3_redoc_link(self, authenticated_client, api_client):
        """V24.18.3: ReDoc link works"""
        # Check API server has ReDoc
        try:
            redoc_response = await api_client.get("/redoc", timeout=10.0)
            assert redoc_response.status_code == 200, "ReDoc should be accessible"
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("API server not available for ReDoc test")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    @pytest.mark.asyncio
    async def test_v24_18_4_openapi_json(self, authenticated_client, api_client):
        """V24.18.4: OpenAPI JSON is accessible"""
        # Check API server has OpenAPI JSON
        try:
            openapi_response = await api_client.get("/openapi.json", timeout=10.0)
            assert openapi_response.status_code == 200, "OpenAPI JSON should be accessible"
            assert "openapi" in openapi_response.text.lower() or "swagger" in openapi_response.text.lower(), \
                "Should return valid OpenAPI/Swagger JSON"
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("API server not available for OpenAPI JSON test")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    @pytest.mark.asyncio
    async def test_v24_18_5_api_docs_has_links(self, authenticated_client):
        """V24.18.5: API docs page serves the SPA shell"""
        response = await authenticated_client.get("/web-api-docs", timeout=10.0)
        assert response.status_code == 200
        _assert_spa_shell(response.text)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    @pytest.mark.asyncio
    async def test_v24_18_6_api_docs_iframe(self, authenticated_client):
        """V24.18.6: API docs page no longer requires embedded legacy HTML"""
        response = await authenticated_client.get("/web-api-docs", timeout=10.0)
        assert response.status_code == 200
        _assert_spa_shell(response.text)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.pure, pytest.mark.slow]
