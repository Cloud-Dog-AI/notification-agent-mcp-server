#!/usr/bin/env python3

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.utils.api_tracking import build_tracked_client


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=10.0,
        registry=api_cleanup_registry,
    ) as client:
        yield client
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_admin_api_key_crud(api_client):
    run_id = uuid4().hex[:8]

    create = api_client.post(
        "/admin/api-keys",
        json={"owner_user_id": f"it11-owner-{run_id}", "ttl_days": 3, "key_prefix": "it11"},
    )
    assert create.status_code in (200, 201), create.text[:200]
    create_payload = create.json()
    assert create_payload["owner_user_id"] == f"it11-owner-{run_id}"
    assert create_payload["api_key"].startswith("it11")
    key_id = create_payload["api_key_id"]

    listing = api_client.get("/admin/api-keys")
    assert listing.status_code == 200, listing.text[:200]
    listing_payload = listing.json()
    assert any(item["api_key_id"] == key_id for item in listing_payload["items"])
    assert all("key_hash" not in item for item in listing_payload["items"])

    revoke = api_client.delete(f"/admin/api-keys/{key_id}")
    assert revoke.status_code == 200, revoke.text[:200]
    revoke_payload = revoke.json()
    assert revoke_payload["revoked"] is True
