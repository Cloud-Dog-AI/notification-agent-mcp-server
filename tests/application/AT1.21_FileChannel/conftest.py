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

"""Shared pytest fixtures for AT1.21 File Channel Test Suite"""

import pytest
import httpx

from tests.conftest import (
    _ensure_api_ready_for_test,
)


@pytest.fixture(scope="function")
def restart_api_per_test(api_base_url, api_key):
    """
    AT1.21 follows the heavy media suite, but the required boundary is a
    healthy API with no stale queued deliveries, not a full API restart.
    """
    _, cancelled = _ensure_api_ready_for_test(
        api_base_url,
        api_key,
        timeout_seconds=60.0,
        context_label="AT1.21 test execution",
    )
    if cancelled:
        print(f"✅ AT1.21 cancelled {cancelled} stale queued message(s) before test")


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config, restart_api_per_test):
    """HTTP client for API calls"""
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)

    api_timeout = httpx.Timeout(
        timeout=timeout_total,
        connect=timeout_connect,
        read=timeout_read,
    )

    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key},
    ) as client:
        yield client
