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
IT1.5: Web UI Links (smoke)

RULES.md compliance:
- No hardcoded URLs/credentials
- Uses web_base_url + test_config fixtures
"""

import httpx
import pytest

from tests.utils.test_helpers import check_test_dependencies
@pytest.mark.IT
@pytest.mark.webui
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_webui_main_pages_accessible(web_base_url, test_config):

    username = test_config.get("web_server.username")
    password = test_config.get("web_server.password")
    if not username or not password:
        pytest.fail("web_server.username/web_server.password not configured")

    timeout_total = test_config.get("api.timeout")
    if timeout_total is None or timeout_total == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    timeout_total = float(timeout_total)

    pages = [
        "/dashboard",
        "/users",
        "/groups",
        "/channels",
        "/messages",
        "/deliveries",
        "/services",
        "/status",
        "/storage",
        "/settings",
        "/logs",
        "/web-api-docs",
    ]

    async with httpx.AsyncClient(base_url=web_base_url, follow_redirects=False, timeout=timeout_total) as client:
        # login
        resp = await client.post("/login", data={"username": username, "password": password})
        assert resp.status_code in (200, 302)

        for p in pages:
            r = await client.get(p, follow_redirects=True, timeout=timeout_total)
            assert r.status_code in (200, 302, 401, 403, 422), f"{p} unexpected {r.status_code}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]
