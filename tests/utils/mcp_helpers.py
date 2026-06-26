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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: MCP integration test helpers (config-driven and RULES compliant).

Related Requirements: FR1.26
Related Tasks: T11
Related Architecture: CC1.1.3, AI1.2
Related Tests: IT1.20, IT1.21, IT1.22, IT1.23, IT1.24

Recent Changes (max 10):
- (Initial helpers for MCP compliance tests)

**************************************************
"""

import os
from typing import Dict, Iterable
from urllib.parse import urljoin

import pytest


def _is_truthy(value) -> bool:
    return value in [True, 1, "true", "True"]


def _marker_missing(test_config, env_hint: str) -> None:
    message = (
        "❌ MCP env marker not set for this transport-specific suite. "
        f"Load tests with: --env {env_hint}"
    )
    if _is_truthy(test_config.get("test.mcp_env_marker_strict")):
        pytest.fail(message)
    pytest.skip(message)


def require_env_marker(test_config, marker_key: str, env_hint: str) -> None:
    marker = test_config.get(marker_key)
    if not _is_truthy(marker):
        _marker_missing(test_config, env_hint)


def require_env_marker_any(test_config, marker_keys: Iterable[str], env_hint: str) -> None:
    for marker_key in marker_keys:
        marker = test_config.get(marker_key)
        if _is_truthy(marker):
            return
    _marker_missing(test_config, env_hint)


def require_config(test_config, key: str) -> str:
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return value


def build_url(base_url: str, path: str) -> str:
    if not path:
        return base_url
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def build_auth_headers(test_config) -> Dict[str, str]:
    api_key = test_config.get("mcp_server.client_api_key")
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def build_stdio_server_env() -> Dict[str, str]:
    """Keep Vault/general runtime env, but let the stdio env file own service config."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CLOUD_DOG__NOTIFY__")
    }
