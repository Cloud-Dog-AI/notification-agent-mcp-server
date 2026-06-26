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
Description: MCP HTTP JSON-RPC compliance tests.

Related Requirements: FR1.26
Related Tasks: T11
Related Architecture: CC1.1.3, AI1.2
Related Tests: IT1.21

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import pytest
import httpx

from tests.utils.mcp_helpers import (
    require_env_marker_any,
    require_config,
    build_url,
    build_auth_headers,
)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-010")


@pytest.mark.asyncio
async def test_it121_http_jsonrpc_compliance(test_config):
    require_env_marker_any(
        test_config,
        ["test.mcp_jsonrpc_env_loaded", "test.mcp_docker_env_loaded"],
        "private/env-test-mcp-jsonrpc or private/env-docker-local-smoke",
    )

    base_url = require_config(test_config, "mcp_server.base_url")
    jsonrpc_path = require_config(test_config, "mcp_server.jsonrpc_path")
    protocol_version = require_config(test_config, "mcp_server.protocol_version")
    endpoint = build_url(base_url, jsonrpc_path)
    headers = build_auth_headers(test_config)

    # Optional auth enforcement check
    if test_config.get("mcp_server.client_api_key"):
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": protocol_version,
                        "capabilities": {},
                        "clientInfo": {"name": "notify-test", "version": "1.0"},
                    },
                },
            )
            assert resp.status_code == 401

    async with httpx.AsyncClient(timeout=30) as client:
        init_resp = await client.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "notify-test", "version": "1.0"},
                },
            },
            headers=headers,
        )
        assert init_resp.status_code == 200
        init_json = init_resp.json()
        assert init_json.get("result", {}).get("protocolVersion") == protocol_version

        notify_resp = await client.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            headers=headers,
        )
        assert notify_resp.status_code in [202, 204]

        tools_resp = await client.post(
            endpoint,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
        assert tools_resp.status_code == 200
        tools_json = tools_resp.json()
        tools = tools_json.get("result", {}).get("tools", [])
        assert any(tool.get("name") == "get_status" for tool in tools)

        call_resp = await client.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_status", "arguments": {}},
            },
            headers=headers,
        )
        assert call_resp.status_code == 200
        call_json = call_resp.json()
        assert "content" in call_json.get("result", {})

        invalid_resp = await client.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "non_existent_tool", "arguments": {}},
            },
            headers=headers,
        )
        assert invalid_resp.status_code == 200
        error_json = invalid_resp.json().get("error")
        assert error_json and error_json.get("code") == -32602

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.mcp, pytest.mark.docker, pytest.mark.heavy]

