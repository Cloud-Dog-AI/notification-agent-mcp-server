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
Description: MCP legacy SSE compliance tests.

Related Requirements: FR1.26
Related Tasks: T11
Related Architecture: CC1.1.3, AI1.2
Related Tests: IT1.22

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import pytest
from mcp.client import session, sse
from mcp.shared.exceptions import McpError

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
@pytest.mark.timeout(300)
async def test_it122_legacy_sse_compliance(test_config):
    require_env_marker_any(
        test_config,
        ["test.mcp_legacy_sse_env_loaded", "test.mcp_docker_env_loaded"],
        "private/env-test-mcp-legacy-sse or private/env-docker-local-smoke",
    )

    base_url = require_config(test_config, "mcp_server.base_url")
    sse_path = require_config(test_config, "mcp_server.legacy_sse_path")
    protocol_version = require_config(test_config, "mcp_server.protocol_version")
    endpoint = build_url(base_url, sse_path)
    headers = build_auth_headers(test_config)

    async with sse.sse_client(endpoint, headers=headers) as (read_stream, write_stream):
        async with session.ClientSession(read_stream, write_stream) as client:
            init_result = await client.initialize()
            assert str(init_result.protocolVersion) == str(protocol_version)

            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            assert "get_status" in tool_names

            tool_result = await client.call_tool("get_status", {})
            assert tool_result.content

            try:
                result = await client.call_tool("non_existent_tool", {})
                assert result.isError
            except McpError as excinfo:
                assert excinfo.error.code in [-32602, -32601]

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.mcp, pytest.mark.docker, pytest.mark.heavy]

