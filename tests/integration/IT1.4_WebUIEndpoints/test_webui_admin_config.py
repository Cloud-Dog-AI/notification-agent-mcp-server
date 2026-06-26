#!/usr/bin/env python3

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest


def _assert_spa_shell(response) -> None:
    assert response.status_code == 200
    body = response.text
    assert '<div id="root">' in body
    assert "/runtime-config.js" in body


@pytest.fixture
async def authed_web_client(web_base_url, test_config):
    username = test_config.get("web_server.username")
    password = test_config.get("web_server.password")
    if not username or not password:
        pytest.fail("web_server.username/web_server.password not configured in env file")

    async with httpx.AsyncClient(base_url=web_base_url, follow_redirects=False) as client:
        login = await client.post(
            "/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        assert login.status_code in (200, 302)
        yield client
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_admin_api_keys_page_renders(authed_web_client):
    response = await authed_web_client.get("/admin/api-keys", follow_redirects=False)
    _assert_spa_shell(response)
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_admin_api_keys_proxy_create_and_revoke(authed_web_client):
    run_id = uuid4().hex[:8]

    create = await authed_web_client.post(
        "/webapi/proxy/admin/api-keys",
        json={"owner_user_id": f"it14-owner-{run_id}", "ttl_days": 1, "key_prefix": "it14"},
    )
    assert create.status_code in (200, 201), create.text[:200]
    payload = create.json()
    assert payload["api_key"].startswith("it14")
    key_id = payload["api_key_id"]

    listing = await authed_web_client.get("/webapi/proxy/admin/api-keys")
    assert listing.status_code == 200, listing.text[:200]
    listing_payload = listing.json()
    assert any(item["api_key_id"] == key_id for item in listing_payload["items"])

    revoke = await authed_web_client.delete(f"/webapi/proxy/admin/api-keys/{key_id}")
    assert revoke.status_code == 200, revoke.text[:200]
    revoke_payload = revoke.json()
    assert revoke_payload["revoked"] is True


pytestmark = [
    pytest.mark.integration,
    pytest.mark.non_llm,
    pytest.mark.api,
    pytest.mark.webui,
    pytest.mark.db,
    pytest.mark.fast,
    pytest.mark.no_llm_dependency,
]
