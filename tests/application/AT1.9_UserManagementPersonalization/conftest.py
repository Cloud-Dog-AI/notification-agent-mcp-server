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
AT1.9: User Management & Personalization (Application tests)

RULES.md compliance:
- Config-driven (no hardcoded URLs/keys/emails/timeouts)
- API-only interactions + best-effort cleanup
- One test node at a time (no parametrised mega-tests)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest


@pytest.fixture(scope="session")
def require_at19_env_loaded(test_config: Any) -> None:
    if not test_config.get("test.at19_env_loaded"):
        pytest.fail("❌ CRITICAL: AT1.9 env file not loaded! Use --env private/env-test-at19")


@pytest.fixture(scope="session")
def api_timeout(test_config: Any) -> float:
    value = test_config.get("api.timeout")
    if value is None or value == "":
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    return float(value)


@pytest.fixture(scope="function")
def api_client(api_base_url: str, api_key: str, api_timeout: float):
    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture(scope="function")
def test_output_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "at19_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
