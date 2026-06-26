# @pytest.mark.req("UC-012")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
AT1.15: Manage User Preferences Test

Tests: UC1.4

Validates:
- Update preferences via API
- Preferences persist and are returned by API
- Missing user returns 404 on update

All values are config-driven via --env private/env-test-at115.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import pytest


def _require_str(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(v)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-021")


def test_at1_15a_update_user_preferences_persists(
    api_client,
    test_config,
    request,
):
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at115.user_email_base")
    user_role = _require_str(test_config, "test.at115.user_role")
    user_type = _require_str(test_config, "test.at115.user_type")
    user_password = _require_str(test_config, "test.at115.user_password")
    display_name = _require_str(test_config, "test.at115.user_display_name")

    pref_language = _require_str(test_config, "test.at115.pref_language")
    pref_content_style = _require_str(test_config, "test.at115.pref_content_style")
    pref_timezone = _require_str(test_config, "test.at115.pref_timezone")
    pref_channel = _require_str(test_config, "test.at115.pref_channel")

    created_user_id: int | None = None

    def _cleanup() -> None:
        if created_user_id is not None:
            try:
                api_client.delete(f"/api/v1/users/{created_user_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    email = user_email_base.replace("@", f"+at115{run_id}@") if "@" in user_email_base else f"{user_email_base}+at115{run_id}"
    username = f"at115_user_{run_id}"

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": user_password,
            "display_name": display_name,
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), f"POST /api/v1/users failed: {create.status_code} {create.text[:200]}"
    js = create.json()
    assert bool(js.get("success")) is True, f"Unexpected create user response: {js}"
    created_user_id = int(js.get("user_id"))

    upd = api_client.put(
        f"/api/v1/users/{created_user_id}/preferences",
        json={
            "language": pref_language,
            "content_style": pref_content_style,
            "timezone": pref_timezone,
            "preferred_channel": pref_channel,
        },
    )
    assert upd.status_code in (200, 201), f"PUT /api/v1/users/{{id}}/preferences failed: {upd.status_code} {upd.text[:200]}"

    get_u = api_client.get(f"/api/v1/users/{created_user_id}")
    assert get_u.status_code == 200, f"GET /api/v1/users/{{id}} failed: {get_u.status_code} {get_u.text[:200]}"
    u: Dict[str, Any] = get_u.json()

    assert str(u.get("language") or "") == pref_language
    assert str(u.get("content_style") or "") == pref_content_style
    assert str(u.get("timezone") or "") == pref_timezone
    assert str(u.get("preferred_channel") or "") == pref_channel
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-021")


def test_at1_15b_update_preferences_missing_user_404(
    api_client,
    test_config,
):
    """
    Deterministic missing-user validation: create then delete a user, then update preferences -> 404.
    """
    run_id = str(int(time.time()))

    user_email_base = _require_str(test_config, "test.at115.user_email_base")
    user_role = _require_str(test_config, "test.at115.user_role")
    user_type = _require_str(test_config, "test.at115.user_type")
    user_password = _require_str(test_config, "test.at115.user_password")
    display_name = _require_str(test_config, "test.at115.user_display_name")

    pref_language = _require_str(test_config, "test.at115.pref_language")

    email = user_email_base.replace("@", f"+at115b{run_id}@") if "@" in user_email_base else f"{user_email_base}+at115b{run_id}"
    username = f"at115b_user_{run_id}"

    create = api_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": email,
            "password": user_password,
            "display_name": display_name,
            "role": user_role,
            "user_type": user_type,
        },
    )
    assert create.status_code in (200, 201), f"POST /api/v1/users failed: {create.status_code} {create.text[:200]}"
    created_user_id = int(create.json().get("user_id"))

    # Delete
    d = api_client.delete(f"/api/v1/users/{created_user_id}")
    assert d.status_code in (200, 204), f"DELETE /api/v1/users/{{id}} failed: {d.status_code} {d.text[:200]}"

    # Update should 404
    upd = api_client.put(
        f"/api/v1/users/{created_user_id}/preferences",
        json={"language": pref_language},
    )
    assert upd.status_code == 404, f"Expected 404 updating deleted user, got {upd.status_code} {upd.text[:200]}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
