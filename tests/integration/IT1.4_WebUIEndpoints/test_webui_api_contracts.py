#!/usr/bin/env python3

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.non_llm,
    pytest.mark.api,
    pytest.mark.webui,
    pytest.mark.db,
    pytest.mark.fast,
    pytest.mark.no_llm_dependency,
]


def _plus_address(email: str, suffix: str) -> str:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local}+{suffix}@{domain}"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _json_object(response: httpx.Response) -> dict:
    payload = response.json()
    assert isinstance(payload, dict), response.text[:200]
    return payload


def _extract_items(payload: object) -> list:
    if isinstance(payload, dict):
        items = payload.get("items", [])
    else:
        items = payload
    assert isinstance(items, list)
    return items


def _ensure_webui_admin_user(api_base_url: str, api_key: str, test_config) -> int | None:
    username = test_config.get("web_server.username")
    base_email = test_config.get("test.email")
    if not username or not base_email:
        pytest.fail("web_server.username and test.email must be configured")

    headers = _headers(api_key)
    users_response = httpx.get(
        f"{api_base_url.rstrip('/')}/users",
        headers=headers,
        params={"q": username, "limit": 50},
        timeout=10.0,
    )
    assert users_response.status_code == 200, users_response.text[:200]
    users = _extract_items(users_response.json())
    existing = next((user for user in users if user.get("username") == username), None)

    if existing and str(existing.get("role", "")).lower() == "admin":
        return None

    if existing:
        delete_response = httpx.delete(
            f"{api_base_url.rstrip('/')}/users/{existing['id']}",
            headers=headers,
            timeout=10.0,
        )
        assert delete_response.status_code in (200, 204), delete_response.text[:200]

    create_response = httpx.post(
        f"{api_base_url.rstrip('/')}/users",
        headers=headers,
        json={
            "username": username,
            "email": _plus_address(base_email, f"webui-{uuid4().hex[:8]}"),
            "display_name": "WebUI Contract Admin",
            "role": "admin",
        },
        timeout=10.0,
    )
    assert create_response.status_code in (200, 201), create_response.text[:200]
    return int(create_response.json()["id"])


@pytest.fixture
async def authed_web_client(web_base_url, api_base_url, api_key, test_config):
    created_admin_id = _ensure_webui_admin_user(api_base_url, api_key, test_config)
    username = test_config.get("web_server.username")
    password = test_config.get("web_server.password")
    if not username or not password:
        pytest.fail("web_server.username and web_server.password must be configured")

    async with httpx.AsyncClient(base_url=web_base_url, follow_redirects=False) as client:
        login = await client.post("/login", data={"username": username, "password": password})
        assert login.status_code in (200, 302), login.text[:200]
        yield client

    if created_admin_id:
        httpx.delete(
            f"{api_base_url.rstrip('/')}/users/{created_admin_id}",
            headers=_headers(api_key),
            timeout=10.0,
        )
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_webui_api_health_and_proxy_json_contracts(authed_web_client, api_base_url, api_key):
    api_health = httpx.get(f"{api_base_url.rstrip('/')}/health", timeout=10.0)
    if api_health.status_code == 401:
        api_health = httpx.get(
            f"{api_base_url.rstrip('/')}/health",
            headers=_headers(api_key),
            timeout=10.0,
        )
    assert api_health.status_code == 200, api_health.text[:200]
    assert any(key in _json_object(api_health) for key in ("status", "health"))

    web_health = await authed_web_client.get("/health")
    assert web_health.status_code == 200, web_health.text[:200]
    assert any(key in _json_object(web_health) for key in ("status", "health"))

    proxy_health = await authed_web_client.get("/webapi/proxy/health")
    assert proxy_health.status_code == 200, proxy_health.text[:200]
    assert any(key in _json_object(proxy_health) for key in ("status", "health"))
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_webui_proxy_user_and_preferences_json_contract(authed_web_client, test_email):
    user_id = None
    run_id = uuid4().hex[:8]
    create = await authed_web_client.post(
        "/webapi/proxy/users",
        json={
            "username": f"it14_contract_{run_id}",
            "email": _plus_address(test_email, f"it14-contract-{run_id}"),
            "display_name": "IT1.4 Contract User",
            "role": "user",
        },
    )
    assert create.status_code in (200, 201), create.text[:200]
    created = _json_object(create)
    user_id = created.get("id") or created.get("user_id")
    assert isinstance(user_id, int)

    try:
        update = await authed_web_client.put(
            f"/webapi/proxy/users/{user_id}/preferences",
            json={"language": "en", "preferred_channel": "email", "content_style": "plain"},
        )
        assert update.status_code == 200, update.text[:200]
        updated = _json_object(update)
        preferences = updated.get("preferences") or updated
        assert str(preferences.get("language") or updated.get("language")) == "en"
        assert str(preferences.get("content_style") or updated.get("content_style")) == "plain"

        fetched = await authed_web_client.get(f"/webapi/proxy/users/{user_id}")
        assert fetched.status_code == 200, fetched.text[:200]
        fetched_user = _json_object(fetched)
        assert int(fetched_user.get("id") or fetched_user.get("user_id")) == user_id
    finally:
        if user_id:
            await authed_web_client.delete(f"/webapi/proxy/users/{user_id}")
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_webui_proxy_admin_api_key_json_contract(authed_web_client):
    run_id = uuid4().hex[:8]
    key_id = None
    create = await authed_web_client.post(
        "/webapi/proxy/admin/api-keys",
        json={"owner_user_id": f"it14-contract-owner-{run_id}", "ttl_days": 1, "key_prefix": "it14c"},
    )
    assert create.status_code in (200, 201), create.text[:200]
    payload = _json_object(create)
    assert str(payload["api_key"]).startswith("it14c")
    key_id = payload["api_key_id"]

    try:
        listing = await authed_web_client.get("/webapi/proxy/admin/api-keys")
        assert listing.status_code == 200, listing.text[:200]
        listing_payload = _json_object(listing)
        assert any(item["api_key_id"] == key_id for item in listing_payload["items"])
    finally:
        if key_id:
            revoke = await authed_web_client.delete(f"/webapi/proxy/admin/api-keys/{key_id}")
            assert revoke.status_code == 200, revoke.text[:200]
            assert _json_object(revoke)["revoked"] is True
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.media
def test_webui_media_metadata_json_shape_contract():
    media_payload = {
        "processed_media": [
            {
                "type": "image",
                "url": "https://example.invalid/media/example.png",
                "format": "png",
                "metadata": {"width": 640, "height": 480, "alt": "Example image"},
                "storage_info": {"backend": "local", "path": "media/example.png"},
            }
        ],
        "preferences": {"language": "en", "content_style": "plain"},
    }

    processed_media = media_payload["processed_media"]
    assert isinstance(processed_media, list)
    media = processed_media[0]
    assert {"type", "url", "format", "metadata"}.issubset(media)
    assert media["type"] == "image"
    assert media["metadata"]["width"] == 640
    assert media["metadata"]["height"] == 480
