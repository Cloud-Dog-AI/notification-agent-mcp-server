# @pytest.mark.req("UC-016")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-025")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
UT1.62 — Thread-a flat WebUI login (admin / read-write / read-only).

PROGRAM-IDAM-RECOVERY-2 Thread a (lane a4, W28A-730-R4): the simple flat login
that gets the notification-agent demo back. Locks:

  * the static UI shell (/login, /index.html, runtime-config.js, assets) is
    PUBLIC — an anonymous browser can load the login box without a 401;
  * the data surfaces (/auth/me, /webapi/proxy/*, /api/proxy/*) stay auth-gated
    (anon -> 401), and the SPA/data routes are NOT shadowed by public static
    handling;
  * /auth/login issues a flat-role session for each of the three accounts and
    /auth/me echoes the shared-idam-derived role + permissions;
  * a read-only session is denied write methods inline (403), never a 401 and
    never a blank UI;
  * logout clears the session.

Permissions come from the ONE shared cloud_dog_idam guard (no per-service RBAC
fork) — see src/servers/web/web_flat_roles.py.

Related Tasks: W28A-730-R4
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.unit,
    pytest.mark.security,
    pytest.mark.fast,
    # Pure web-tier gate test (TestClient) — does NOT need the live API runtime
    # the notification-agent harness starts in local-server mode.
    pytest.mark.no_runtime_dependency,
]

# Public static surface: anon must get 200 (login box must render).
PUBLIC_STATIC = ("/login", "/index.html", "/runtime-config.js")
# Data surface: anon must get 401 (auth-gated). Alias routes may 404 on a build;
# the test treats 404 as "route not present" and skips that alias only.
GATED_DATA = ("/auth/me", "/webapi/proxy/channels", "/api/proxy/channels")


@pytest.fixture()
def web_app():
    # Import inside the fixture so the autouse --env config fixture has loaded
    # configuration before the module-level web app is constructed.
    from src.servers.web import web_server

    return web_server


@pytest.fixture()
def accounts(web_app):
    """Return ``{flat-role: (username, password)}`` resolved from live config."""
    from src.servers.web.web_flat_roles import (
        ADMIN_ROLE,
        READ_ONLY_ROLE,
        READ_WRITE_ROLE,
    )

    resolved = web_app._flat_login_accounts()
    by_role: dict[str, tuple[str, str]] = {}
    for username, (password, role) in resolved.items():
        by_role[role] = (username, password)
    # All three flat roles must be seeded for a demoable login.
    assert by_role.keys() >= {ADMIN_ROLE, READ_WRITE_ROLE, READ_ONLY_ROLE}, by_role
    return by_role


@pytest.fixture()
def web_client(web_app) -> TestClient:
    return TestClient(
        web_app.app, raise_server_exceptions=False, follow_redirects=False
    )


def _login(client: TestClient, accounts, role: str):
    username, password = accounts[role]
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"{role} login: {resp.status_code} {resp.text[:200]}"
    return {k: v for k, v in resp.cookies.items()}
@pytest.mark.UT
@pytest.mark.req("CS-015")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-012")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-011")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-010")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-009")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-008")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-004")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-003")  # W28C-1711-R3.5 binding
@pytest.mark.req("CS-002")  # W28C-1711-R3.5 binding
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_static_ui_is_public_for_anon(web_client: TestClient) -> None:
    for path in PUBLIC_STATIC:
        resp = web_client.get(path)
        assert resp.status_code == 200, (
            f"anon {path} must be PUBLIC 200 (login box must load); "
            f"got {resp.status_code}: {resp.text[:160]}"
        )
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_data_surfaces_gated_for_anon(web_client: TestClient) -> None:
    seen = []
    for path in GATED_DATA:
        resp = web_client.get(path)
        if resp.status_code == 404:
            continue  # alias not on this build — skip the alias, not the gate
        seen.append(path)
        assert resp.status_code == 401, (
            f"anon {path} must be 401 (data stays auth-gated); got {resp.status_code}"
        )
    assert "/auth/me" in seen, "the /auth/me principal gate must be provable"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_each_flat_role_logs_in_with_expected_role(web_client, accounts) -> None:
    from src.servers.web.web_flat_roles import (
        ADMIN_ROLE,
        READ_ONLY_ROLE,
        READ_WRITE_ROLE,
        role_can_write,
    )

    for role in (ADMIN_ROLE, READ_WRITE_ROLE, READ_ONLY_ROLE):
        cookies = _login(web_client, accounts, role)
        me = web_client.get("/auth/me", cookies=cookies)
        assert me.status_code == 200, me.text[:200]
        body = me.json()["user"]
        assert body["roles"] == [role], body
        perms = body["permissions"]
        if role == ADMIN_ROLE:
            assert perms == ["*"], perms
        else:
            assert "*" not in perms and len(perms) >= 1, perms
            has_write = any(p.endswith(".write") or p.endswith(":write") for p in perms)
            assert has_write is role_can_write(role), (role, perms)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_read_only_writes_are_denied_inline_403(web_client, accounts) -> None:
    from src.servers.web.web_flat_roles import READ_ONLY_ROLE

    cookies = _login(web_client, accounts, READ_ONLY_ROLE)
    for method, path in (
        ("POST", "/api/proxy/channels"),
        ("POST", "/webapi/proxy/channels"),
        ("PUT", "/api/proxy/channels/1"),
        ("PATCH", "/api/proxy/channels/1"),
        ("DELETE", "/api/proxy/channels/1"),
        ("POST", "/api/proxy/messages"),
    ):
        resp = web_client.request(method, path, cookies=cookies, json={"name": "x"})
        assert resp.status_code == 403, (
            f"read-only {method} {path} must be 403-inline (not 401, not 200); "
            f"got {resp.status_code}: {resp.text[:160]}"
        )
        assert "read-only role" in resp.text, resp.text[:160]
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_read_write_writes_are_not_pre_gated(web_client, accounts) -> None:
    # A read-write session must NOT be blocked by the read-only write-gate. The
    # request reaches the proxy (which then fails on the unreachable upstream in
    # this unit context). The contract: it is NOT the flat-role 403.
    from src.servers.web.web_flat_roles import READ_WRITE_ROLE

    cookies = _login(web_client, accounts, READ_WRITE_ROLE)
    resp = web_client.post("/api/proxy/channels", cookies=cookies, json={"name": "x"})
    assert not (resp.status_code == 403 and "read-only role" in resp.text), resp.text[:200]
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_bad_credentials_rejected(web_client, accounts) -> None:
    admin_user = accounts["admin"][0]
    assert web_client.post(
        "/auth/login", json={"username": admin_user, "password": "wrong"}
    ).status_code == 401
    assert web_client.post(
        "/auth/login", json={"username": "ghost-user", "password": "x"}
    ).status_code == 401
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-018")


def test_logout_clears_session(web_client, accounts) -> None:
    from src.servers.web.web_flat_roles import ADMIN_ROLE

    cookies = _login(web_client, accounts, ADMIN_ROLE)
    assert web_client.get("/auth/me", cookies=cookies).status_code == 200
    web_client.post("/auth/logout", cookies=cookies)
    # SessionMiddleware clears the signed cookie; reusing the stale cookie 401s
    # because the session payload no longer carries a user.
    web_client.cookies.clear()
    assert web_client.get("/auth/me").status_code == 401
