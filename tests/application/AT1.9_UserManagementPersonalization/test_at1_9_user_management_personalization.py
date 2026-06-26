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
AT1.9: User Management & Personalization (API-only)

Covers:
- Users: create/get/search/update preferences/delete
- User destinations: add/remove
- User keywords: add/remove
- Groups: create/get/add member/keywords + disable (no delete endpoint)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import pytest


def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)


def _unique_plus_email(base_email: str, suffix: str) -> str:
    if "@" not in base_email:
        pytest.fail("❌ HARD FAIL: test.at19.user_email_base must contain '@' for plus-addressing")
    local, domain = base_email.split("@", 1)
    return f"{local}+{suffix}@{domain}"


def _pick_enabled_smtp_channel(api_client) -> Dict[str, Any]:
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code} {r.text[:200]}"
    channels = r.json()
    assert isinstance(channels, list), "Expected /channels to return a list"
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        if str(ch.get("type", "")).lower() == "smtp" and bool(ch.get("enabled")) is True:
            if ch.get("name"):
                return ch
    pytest.fail("No enabled SMTP channel found via GET /channels (required for AT1.9 destinations)")


def _extract_items(resp_json: Any) -> List[Dict[str, Any]]:
    if isinstance(resp_json, dict) and isinstance(resp_json.get("items"), list):
        return resp_json["items"]
    pytest.fail("Expected response JSON to be an object with an 'items' list")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9a_user_crud_roundtrip(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")

    username = f"at19_user_{run_id}"
    email = _unique_plus_email(base_email, f"at19a{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is None:
            return
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Test User",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), f"POST /api/v1/users failed: {create.status_code} {create.text[:200]}"
    data = create.json()
    assert bool(data.get("success")) is True
    created_user_id = int(data.get("user_id"))

    get_u = api_client.get(f"/api/v1/users/{created_user_id}")
    assert get_u.status_code == 200, f"GET /api/v1/users/{{id}} failed: {get_u.status_code} {get_u.text[:200]}"
    u = get_u.json()
    assert str(u.get("username")) == username
    assert str(u.get("email")) == email
    assert str(u.get("role")) == role
    assert str(u.get("user_type")) == user_type
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9b_user_search_finds_created_user(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")

    username = f"at19_search_{run_id}"
    email = _unique_plus_email(base_email, f"at19b{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is None:
            return
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Search User",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), create.text[:200]
    created_user_id = int(create.json().get("user_id"))

    r = api_client.get("/api/v1/users", params={"q": username, "limit": 50})
    assert r.status_code == 200, f"GET /api/v1/users?q= failed: {r.status_code} {r.text[:200]}"
    items = _extract_items(r.json())
    assert any(str(it.get("username")) == username for it in items), "Expected search to return created user"
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9c_update_user_preferences_persists(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")
    pref_language = _require_str(test_config, "test.at19.pref_language")
    pref_style = _require_str(test_config, "test.at19.pref_content_style")
    pref_timezone = _require_str(test_config, "test.at19.pref_timezone")

    username = f"at19_prefs_{run_id}"
    email = _unique_plus_email(base_email, f"at19c{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is None:
            return
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Prefs User",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), create.text[:200]
    created_user_id = int(create.json().get("user_id"))

    upd = api_client.put(
        f"/api/v1/users/{created_user_id}/preferences",
        json={"language": pref_language, "content_style": pref_style, "timezone": pref_timezone},
    )
    assert upd.status_code == 200, f"PUT /api/v1/users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"
    assert bool(upd.json().get("success")) is True

    get_u = api_client.get(f"/api/v1/users/{created_user_id}")
    assert get_u.status_code == 200
    u = get_u.json()
    assert str(u.get("language") or "") == pref_language
    assert str(u.get("content_style") or "") == pref_style
    assert str(u.get("timezone") or "") == pref_timezone
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9d_user_destinations_add_and_remove(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")

    smtp_channel = _pick_enabled_smtp_channel(api_client)
    channel_type = str(smtp_channel.get("type"))

    username = f"at19_dest_{run_id}"
    email = _unique_plus_email(base_email, f"at19d{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None
    created_destination_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is None:
            return
        try:
            if created_destination_id is not None:
                api_client.delete(f"/api/v1/users/{created_user_id}/destinations/{created_destination_id}")
        except Exception:
            pass
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Dest User",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), create.text[:200]
    created_user_id = int(create.json().get("user_id"))

    add = api_client.post(
        f"/api/v1/users/{created_user_id}/destinations",
        json={
            "channel_type": channel_type,
            "destination": email,
            "is_primary": True,
            "metadata": {"source": "at19"},
        },
    )
    assert add.status_code == 200, f"POST /api/v1/users/{{id}}/destinations failed: {add.status_code} {add.text[:200]}"
    created_destination_id = int(add.json().get("destination_id"))

    get_u = api_client.get(f"/api/v1/users/{created_user_id}")
    assert get_u.status_code == 200
    u = get_u.json()
    destinations = u.get("destinations") or []
    assert isinstance(destinations, list)
    assert any(str(d.get("destination")) == email for d in destinations if isinstance(d, dict)), "Destination not present on user"

    rm = api_client.delete(f"/api/v1/users/{created_user_id}/destinations/{created_destination_id}")
    assert rm.status_code == 200, f"DELETE destination failed: {rm.status_code} {rm.text[:200]}"
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9e_user_keywords_add_and_remove(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")
    keyword = _require_str(test_config, "test.at19.user_keyword")

    username = f"at19_kw_{run_id}"
    email = _unique_plus_email(base_email, f"at19e{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is None:
            return
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}/keywords/{keyword}")
        except Exception:
            pass
        try:
            api_client.delete(f"/api/v1/users/{created_user_id}")
        except Exception:
            pass

    request.addfinalizer(_cleanup)

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Keywords User",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), create.text[:200]
    created_user_id = int(create.json().get("user_id"))

    add = api_client.post(f"/api/v1/users/{created_user_id}/keywords", json={"keyword": keyword})
    assert add.status_code in (200, 409), f"POST keyword failed: {add.status_code} {add.text[:200]}"

    get_u = api_client.get(f"/api/v1/users/{created_user_id}")
    assert get_u.status_code == 200
    u = get_u.json()
    keywords = u.get("keywords") or []
    assert isinstance(keywords, list)
    assert any(str(k).lower() == keyword.lower() for k in keywords), "Keyword not present on user"

    rm = api_client.delete(f"/api/v1/users/{created_user_id}/keywords/{keyword}")
    assert rm.status_code == 200, f"DELETE keyword failed: {rm.status_code} {rm.text[:200]}"
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_9f_group_membership_and_keywords(api_client, test_config, request) -> None:
    run_id = str(int(time.time()))
    base_email = _require_str(test_config, "test.at19.user_email_base")
    role = _require_str(test_config, "test.at19.user_role")
    user_type = _require_str(test_config, "test.at19.user_type")
    group_keyword = _require_str(test_config, "test.at19.group_keyword")
    group_language = _require_str(test_config, "test.at19.group_language")

    # Create a user
    username = f"at19_grp_user_{run_id}"
    email = _unique_plus_email(base_email, f"at19f{run_id}")
    password = f"pw_{run_id}"

    created_user_id: int | None = None
    created_group_id: int | None = None

    def _cleanup() -> None:
        # Best-effort cleanup: remove member + keyword, disable group, delete user
        if created_group_id is not None and created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/groups/{created_group_id}/members/{created_user_id}")
            except Exception:
                pass
        if created_group_id is not None:
            try:
                api_client.delete(f"/api/v1/groups/{created_group_id}/keywords/{group_keyword}")
            except Exception:
                pass
            try:
                api_client.put(f"/api/v1/groups/{created_group_id}", json={"enabled": False})
            except Exception:
                pass
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    create_u = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": password,
            "display_name": "AT1.9 Group Member",
            "role": role,
            "user_type": user_type,
        },
    )
    assert create_u.status_code in (200, 201), create_u.text[:200]
    created_user_id = int(create_u.json().get("user_id"))

    # Create group
    group_name = f"at19_group_{run_id}"
    create_g = api_client.post(
        "/api/v1/groups",
        json={
            "name": group_name,
            "description": "AT1.9 group test",
            "language": group_language,
        },
    )
    assert create_g.status_code in (200, 201), f"POST /api/v1/groups failed: {create_g.status_code} {create_g.text[:200]}"
    created_group_id = int(create_g.json().get("group_id"))

    # Add member
    add_m = api_client.post(f"/api/v1/groups/{created_group_id}/members", json={"user_id": created_user_id, "role": "member"})
    assert add_m.status_code in (200, 409), f"POST member failed: {add_m.status_code} {add_m.text[:200]}"

    # Add keyword
    add_kw = api_client.post(f"/api/v1/groups/{created_group_id}/keywords", json={"keyword": group_keyword})
    assert add_kw.status_code in (200, 409), f"POST group keyword failed: {add_kw.status_code} {add_kw.text[:200]}"

    # Verify group content
    g = api_client.get(f"/api/v1/groups/{created_group_id}")
    assert g.status_code == 200, f"GET /api/v1/groups/{{id}} failed: {g.status_code} {g.text[:200]}"
    grp = g.json()
    assert str(grp.get("name")) == group_name
    assert str(grp.get("language") or "") == group_language
    members = grp.get("members") or []
    assert isinstance(members, list)
    assert any(int(m.get("user_id") or m.get("id") or 0) == int(created_user_id) for m in members if isinstance(m, dict)), "User not present in group members"
    keywords = grp.get("keywords") or []
    assert isinstance(keywords, list)
    assert any(str(k).lower() == group_keyword.lower() for k in keywords), "Keyword not present on group"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
