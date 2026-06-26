from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class _FakeAuditLogger:
    def __init__(self) -> None:
        self.login_calls: list[dict] = []
        self.security_calls: list[dict] = []

    def log_login(self, **kwargs):
        self.login_calls.append(kwargs)

    def log_security(self, **kwargs):
        self.security_calls.append(kwargs)


class _DummyRequest:
    def __init__(
        self,
        *,
        path: str,
        headers: dict | None = None,
        session: dict | None = None,
        json_payload: dict | None = None,
        client_host: str = "127.0.0.1",
    ) -> None:
        self.headers = headers or {"user-agent": "pytest-agent/1.0"}
        self.session = session or {}
        self.client = SimpleNamespace(host=client_host)
        self.url = SimpleNamespace(path=path)
        self._json_payload = json_payload or {}

    async def json(self):
        return self._json_payload


@pytest.fixture
def _web_auth_logging_state(monkeypatch):
    monkeypatch.setenv("CLOUD_DOG__NOTIFY__AUTH__JWT_SECRET", "ut-jwt-secret")
    module_name = "src.servers.web.web_server"
    sys.modules.pop(module_name, None)
    web_server = importlib.import_module(module_name)
    fake_audit = _FakeAuditLogger()
    cfg = {
        "app.server_id": "ut-web-auth",
        "web_server.username": "admin",
        "web_server.password": "secret",
        "idp.enabled": True,
        "idp.keycloak.enabled": True,
        "idp.keycloak.base_url": "https://idp.example.com",
        "idp.keycloak.realm": "cloud-dog",
        "idp.keycloak.client_id": "notification-web",
        "idp.keycloak.client_secret": "secret",
        "idp.keycloak.redirect_uri": "https://notification.example.com/auth/keycloak/callback",
        "idp.keycloak.scopes": "openid email profile",
    }
    monkeypatch.setattr(web_server, "get_audit_logger", lambda: fake_audit)
    monkeypatch.setattr(web_server, "config", cfg)
    return web_server, fake_audit
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_html_login_emits_structured_success_and_failure(_web_auth_logging_state):
    web_server, fake_audit = _web_auth_logging_state

    success_request = _DummyRequest(path="/login")
    response = await web_server.login(username="admin", password="secret", request=success_request)
    assert response.status_code == 302

    success = fake_audit.login_calls[-1]
    assert success["outcome"] == "success"
    assert success["actor"].id == "admin"
    assert success["actor"].ip == "127.0.0.1"
    assert success["actor"].user_agent == "pytest-agent/1.0"
    assert success["target"].type == "auth_flow"
    assert success["target"].id == "/login"
    assert success["server_id"] == "ut-web-auth"
    assert success["request_path"] == "/login"
    assert success["auth_method"] == "password_form"

    failure_request = _DummyRequest(path="/login")
    failure_response = await web_server.login(username="admin", password="wrong", request=failure_request)
    assert failure_response.status_code == 200

    failure = fake_audit.login_calls[-1]
    assert failure["outcome"] == "failure"
    assert failure["reason"] == "invalid_credentials"
    assert failure["target"].id == "/login"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_json_login_failure_emits_structured_login_event(_web_auth_logging_state):
    web_server, fake_audit = _web_auth_logging_state
    request = _DummyRequest(
        path="/auth/login",
        json_payload={"username": "admin", "password": "wrong"},
    )

    with pytest.raises(HTTPException) as exc:
        await web_server.auth_login(request)

    assert exc.value.status_code == 401
    failure = fake_audit.login_calls[-1]
    assert failure["outcome"] == "failure"
    assert failure["auth_method"] == "password_json"
    assert failure["reason"] == "invalid_credentials"
    assert failure["target"].id == "/auth/login"
    assert failure["server_id"] == "ut-web-auth"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "state", "code", "session", "expected_reason", "expected_outcome"),
    [
        ("access_denied", "state-1", None, {"oauth_state": "state-1"}, "provider_error", "error"),
        (None, "wrong-state", "code-1", {"oauth_state": "state-1"}, "state_mismatch", "denied"),
        (None, "state-1", None, {"oauth_state": "state-1"}, "missing_authorization_code", "error"),
    ],
)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")
async def test_keycloak_callback_error_paths_emit_structured_security_events(
    _web_auth_logging_state,
    error,
    state,
    code,
    session,
    expected_reason,
    expected_outcome,
):
    web_server, fake_audit = _web_auth_logging_state
    request = _DummyRequest(path="/auth/keycloak/callback", session=session)

    response = await web_server.keycloak_callback(request, code=code, state=state, error=error)
    assert response.status_code == 302

    security = fake_audit.security_calls[-1]
    assert security["action"] == "oauth_callback"
    assert security["outcome"] == expected_outcome
    assert security["actor"].ip == "127.0.0.1"
    assert security["target"].type == "auth_flow"
    assert security["target"].id == "callback"
    assert security["server_id"] == "ut-web-auth"
    assert security["request_path"] == "/auth/keycloak/callback"
    assert security["provider"] == "keycloak"
    assert security["reason"] == expected_reason
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_keycloak_login_redirect_emits_structured_security_event(_web_auth_logging_state):
    web_server, fake_audit = _web_auth_logging_state
    request = _DummyRequest(path="/auth/keycloak/login", session={})

    response = await web_server.keycloak_login(request)
    assert response.status_code == 302

    security = fake_audit.security_calls[-1]
    assert security["action"] == "oauth_redirect"
    assert security["outcome"] == "success"
    assert security["reason"] == "redirect_initiated"
    assert security["target"].type == "auth_flow"
    assert security["target"].name == "keycloak"
    assert security["server_id"] == "ut-web-auth"
    assert security["request_path"] == "/auth/keycloak/login"
    assert security["authorization_endpoint"] == "/realms/cloud-dog/protocol/openid-connect/auth"
    assert "auth_url" not in security
