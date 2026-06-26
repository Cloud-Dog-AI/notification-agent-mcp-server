# @pytest.mark.req("UC-101")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-109")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
UT1.60 — Unauthenticated auth-gate (negative-auth) regression guard.

W28A-889-B estate unauth auth-gate hardening. The missing NEGATIVE-auth test for
the unauthenticated front door (the index-retriever WebApiProxy admin-key
injection class, W28A-734-R2).

notification-agent's web tier:
  - serves /auth/me LOCALLY from the signed cookie session (auth_routes.py ->
    _session_user_payload) and raises 401 for an anonymous caller (no session),
    never a populated/admin principal — it never proxies the principal and never
    injects the notification-api service key onto it;
  - guards the /webapi/proxy/* routes with Depends(get_current_user) -> 401 for an
    anonymous caller, so the bootstrap notification-api key is never forwarded for
    an unauthenticated request.

This test fails if either gate is removed. The bootstrap _SERVICE_ADMINS
admin-equivalence is an AUTHENTICATED-context concern (the key is only injected
for an authenticated session) tracked separately as W28A-890 — out of scope for
this unauth front-door lane.

Related Tasks: W28A-889-B

Recent Changes:
- 2026-06-09: W28A-889-B — initial negative-auth regression guard.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.unit,
    pytest.mark.security,
    pytest.mark.fast,
    # This is a pure web-tier gate test (TestClient) — it does NOT need the live
    # API runtime the notification-agent harness starts in local-server mode.
    pytest.mark.no_runtime_dependency,
]

PRINCIPAL_PATH = "/auth/me"
PROTECTED_DATA_PATHS = ("/webapi/proxy/channels", "/api/proxy/channels")


@pytest.fixture()
def web_client() -> TestClient:
    # Import inside the fixture so the autouse --env config fixture has loaded
    # configuration before the module-level web app is constructed.
    from src.servers.web import web_server

    return TestClient(web_server.app, raise_server_exceptions=False)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


def test_unauth_principal_denied(web_client: TestClient) -> None:
    resp = web_client.get(PRINCIPAL_PATH)
    assert resp.status_code == 401, f"anon {PRINCIPAL_PATH} must be 401: {resp.status_code} {resp.text[:200]}"
    assert '"roles"' not in resp.text and '"permissions"' not in resp.text, resp.text
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


def test_unauth_protected_data_denied(web_client: TestClient) -> None:
    seen = []
    for path in PROTECTED_DATA_PATHS:
        resp = web_client.get(path)
        if resp.status_code == 404:
            # Route alias may not exist on this build; skip the alias, not the gate.
            continue
        seen.append(path)
        assert resp.status_code in (401, 403), (
            f"anon {path} must be denied (get_current_user gate); "
            f"got {resp.status_code}: {resp.text[:200]}"
        )
    assert seen, f"none of {PROTECTED_DATA_PATHS} were routable — cannot prove the data gate"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-017")


def test_forged_session_cookie_does_not_bypass(web_client: TestClient) -> None:
    web_client.cookies.set("session", "forged.not-a-valid-signed-session")
    resp = web_client.get(PRINCIPAL_PATH)
    assert resp.status_code == 401, f"forged session cookie must not authenticate: {resp.status_code} {resp.text[:200]}"
