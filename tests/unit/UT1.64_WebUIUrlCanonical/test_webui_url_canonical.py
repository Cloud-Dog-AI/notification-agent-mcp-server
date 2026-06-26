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

"""UT1.64 — PS-WEBUI-URL-CANONICAL web-tier redirect contract."""

# @pytest.mark.webui  # PS-REQ-TEST-TRACE file-level surface anchor.

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.unit,
    pytest.mark.webui,
    pytest.mark.security,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
]


@pytest.fixture()
def web_server_module():
    from src.servers.web import web_server

    return web_server


@pytest.fixture()
def web_client(web_server_module) -> TestClient:
    return TestClient(web_server_module.app, raise_server_exceptions=False, follow_redirects=False)


def _login_admin(client: TestClient, web_server_module) -> None:
    from src.servers.web.web_flat_roles import ADMIN_ROLE

    accounts = web_server_module._flat_login_accounts()
    for username, (password, role) in accounts.items():
        if role == ADMIN_ROLE:
            response = client.post("/auth/login", json={"username": username, "password": password})
            assert response.status_code == 200, response.text[:200]
            return
    pytest.fail("No admin flat-login account is configured")


@pytest.mark.UT
@pytest.mark.req("FR-026")
def test_public_login_aliases_return_http_308(web_client: TestClient) -> None:
    response = web_client.get("/ui/login?next=/system/jobs")
    assert response.status_code == 308
    assert response.headers["location"] == "/login?next=/system/jobs"

    response = web_client.get("/auth/login?next=/system/jobs")
    assert response.status_code == 308
    assert response.headers["location"] == "/login?next=/system/jobs"


@pytest.mark.UT
@pytest.mark.req("CS-008")
@pytest.mark.req("UC-109")
def test_anonymous_protected_alias_uses_auth_gate_before_canonical_redirect(web_client: TestClient) -> None:
    response = web_client.get("/idam/users?role=admin")
    assert response.status_code == 307
    assert response.headers["location"] == "/login"


@pytest.mark.UT
@pytest.mark.req("FR-026")
def test_authenticated_legacy_aliases_return_http_308_with_query_preserved(
    web_client: TestClient,
    web_server_module,
) -> None:
    _login_admin(web_client, web_server_module)

    aliases = {
        "/diagnostics-audit?actor=stream-c": "/audit-log?actor=stream-c",
        "/idam/users?role=admin": "/admin/users?role=admin",
        "/idam/groups?group=ops": "/admin/groups?group=ops",
        "/idam/api-keys?owner=group%3A1": "/admin/api-keys?owner=group%3A1",
        "/idam/roles": "/admin/roles",
        "/idam/rbac?user=web_test": "/admin/rbac?user=web_test",
        "/api-docs": "/developer/api-docs",
        "/mcp-console": "/developer/mcp-console",
        "/a2a-console": "/developer/a2a-console",
        "/jobs": "/system/jobs",
        "/settings": "/system/settings",
        "/about": "/system/about",
    }
    for source, target in aliases.items():
        response = web_client.get(source)
        assert response.status_code == 308, source
        assert response.headers["location"] == target


@pytest.mark.UT
@pytest.mark.req("FR-026")
def test_authenticated_canonical_routes_serve_spa_shell(web_client: TestClient, web_server_module) -> None:
    _login_admin(web_client, web_server_module)

    for path in (
        "/audit-log",
        "/admin/users",
        "/admin/groups",
        "/admin/api-keys",
        "/admin/roles",
        "/admin/rbac",
        "/developer/api-docs",
        "/developer/mcp-console",
        "/developer/a2a-console",
        "/system/jobs",
        "/system/settings",
        "/system/about",
    ):
        response = web_client.get(path)
        assert response.status_code == 200, path
        assert '<div id="root">' in response.text
        assert "/runtime-config.js" in response.text


@pytest.mark.UT
@pytest.mark.req("FR-026")
def test_unknown_webui_route_is_not_spa_masked(web_client: TestClient, web_server_module) -> None:
    _login_admin(web_client, web_server_module)

    response = web_client.get("/not-a-notification-route")
    assert response.status_code == 404
    assert "Page not found" in response.text


@pytest.mark.UT
@pytest.mark.req("FR-026")
def test_runtime_config_and_openapi_json_are_not_webui_redirected(web_client: TestClient) -> None:
    runtime = web_client.get("/runtime-config.js")
    assert runtime.status_code == 200
    assert "window.__RUNTIME_CONFIG__" in runtime.text

    openapi = web_client.get("/openapi.json")
    assert openapi.status_code != 308
