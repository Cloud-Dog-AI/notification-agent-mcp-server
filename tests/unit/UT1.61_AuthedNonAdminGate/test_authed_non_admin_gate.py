# @pytest.mark.req("UC-102")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-105")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
#
# Description: Authenticated-non-admin -> 403 gate (W28A-889-B-R2 / W28A-890).
# Related tests: UT1.61

"""
UT1.61 - notification-agent authenticated-non-admin -> 403 (W28A-889-B-R2 / W28A-890).

W28A-889-B (UT1.60) covered only the UNAUTH front door and explicitly deferred the
`_SERVICE_ADMINS` authenticated-context collapse to W28A-890. The web proxy
authenticates to the API with the `notification-api` service key (a _SERVICE_ADMINS
member) and now forwards the real web user (X-Request-Source=webui +
X-Request-User/Role). `_require_admin` must authorize as the FORWARDED user.

Imports are deferred into the fixture/test bodies so the autouse --env config
fixture loads configuration before the route modules are imported (cf. UT1.60).
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

pytestmark = [pytest.mark.unit, pytest.mark.security, pytest.mark.fast, pytest.mark.no_runtime_dependency]


class _FakeRBAC:
    def has_permission(self, user_id, perm):  # forwarded user has no direct "*" grant
        return False


class _FakeRuntime:
    rbac_engine = _FakeRBAC()


class _FakeChecker:
    def __init__(self, is_admin: bool):
        self._is_admin = is_admin

    def has_permission(self, perm):
        return self._is_admin


@pytest.fixture()
def patched(monkeypatch):
    idam_runtime_mod = importlib.import_module("src.core.idam.runtime")
    rbac_mod = importlib.import_module("src.core.rbac")
    monkeypatch.setattr(idam_runtime_mod, "get_idam_runtime", lambda: _FakeRuntime())
    monkeypatch.setattr(idam_runtime_mod, "require_authenticated_request", lambda req: req.state.user)

    def fake_checker(user_data, owned_groups=None):
        return _FakeChecker(str(user_data.get("role") or "").strip().lower() == "admin")

    monkeypatch.setattr(rbac_mod, "get_checker_for_user", fake_checker)
    yield monkeypatch


def _require_admin(module_name: str):
    mod = importlib.import_module(f"src.servers.api.routes.{module_name}")
    return mod._require_admin


def _request(headers: dict[str, str], principal) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/users",
        "query_string": b"",
        "headers": raw,
        "state": {"user": principal},
    }
    return Request(scope)


def _service_principal():
    return SimpleNamespace(user_id="notification-api", role="viewer")


MODULES = pytest.mark.parametrize("module_name", ["users", "groups"])
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


@MODULES
def test_webui_forwarded_nonadmin_is_denied(patched, module_name) -> None:
    require_admin = _require_admin(module_name)
    req = _request(
        {"X-Request-Source": "webui", "X-Request-User": "analyst1", "X-Request-Role": "viewer"},
        _service_principal(),
    )
    with pytest.raises(HTTPException) as exc:
        require_admin(req)
    assert exc.value.status_code == 403
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


@MODULES
def test_webui_forwarded_admin_is_allowed(patched, module_name) -> None:
    require_admin = _require_admin(module_name)
    req = _request(
        {"X-Request-Source": "webui", "X-Request-User": "admin", "X-Request-Role": "admin"},
        _service_principal(),
    )
    require_admin(req)  # must not raise
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


@MODULES
def test_genuine_service_principal_without_forwarding_is_allowed(patched, module_name) -> None:
    require_admin = _require_admin(module_name)
    req = _request({}, _service_principal())
    require_admin(req)  # MCP/A2A/direct service call — must not raise
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


@MODULES
def test_nonservice_nonadmin_principal_is_denied(patched, module_name) -> None:
    require_admin = _require_admin(module_name)
    req = _request({}, SimpleNamespace(user_id="alice", role="viewer"))
    with pytest.raises(HTTPException) as exc:
        require_admin(req)
    assert exc.value.status_code == 403
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


@MODULES
def test_nonservice_admin_principal_is_allowed(patched, module_name) -> None:
    require_admin = _require_admin(module_name)
    req = _request({}, SimpleNamespace(user_id="bob", role="admin"))
    require_admin(req)  # normal RBAC admin — must not raise
