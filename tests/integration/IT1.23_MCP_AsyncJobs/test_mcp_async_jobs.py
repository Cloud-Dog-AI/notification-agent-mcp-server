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
Description: MCP async jobs (wait=false) compliance tests.

Related Requirements: FR1.26
Related Tasks: T11
Related Architecture: CC1.1.3, AI1.2
Related Tests: IT1.23

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import asyncio
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
async def test_it123_http_jsonrpc_async_jobs(test_config):
    require_env_marker_any(
        test_config,
        ["test.mcp_async_env_loaded", "test.mcp_docker_env_loaded"],
        "private/env-test-mcp-async or private/env-docker-local-smoke",
    )

    base_url = require_config(test_config, "mcp_server.base_url")
    jsonrpc_path = require_config(test_config, "mcp_server.jsonrpc_path")
    status_path = require_config(test_config, "mcp_server.async_jobs_status_path")
    async_enabled = test_config.get("mcp_server.async_jobs_enabled")
    if async_enabled not in [True, 1, "true", "True"]:
        pytest.fail("❌ HARD FAIL: mcp_server.async_jobs_enabled must be true for async job tests")

    timeout_seconds = float(require_config(test_config, "mcp_server.async_jobs_timeout_seconds"))
    poll_interval = float(require_config(test_config, "mcp_server.async_jobs_poll_interval_seconds"))

    endpoint = build_url(base_url, jsonrpc_path)
    headers = build_auth_headers(test_config)

    async with httpx.AsyncClient(timeout=30) as client:
        call_resp = await client.post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_channels", "arguments": {"wait": False}},
            },
            headers=headers,
        )
        assert call_resp.status_code == 200
        call_json = call_resp.json()
        result = call_json.get("result", {})
        job_id = result.get("job_id") or result.get("guid")
        assert job_id, "Expected job reference in async response"

        status_url = build_url(base_url, status_path.replace("{job_id}", job_id))
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        final_payload = None

        while asyncio.get_event_loop().time() < deadline:
            status_resp = await client.get(status_url, headers=headers)
            assert status_resp.status_code in [200, 404]
            payload = status_resp.json()
            if payload.get("status") in ["completed", "failed", "timeout"]:
                final_payload = payload
                break
            await asyncio.sleep(poll_interval)

        assert final_payload, "Async job did not reach a terminal state before timeout"
        assert final_payload.get("status") == "completed"
        assert final_payload.get("result", {}).get("content")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.integration,
    pytest.mark.mcp,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.no_llm_dependency,
    pytest.mark.docker,
    pytest.mark.heavy,
]
