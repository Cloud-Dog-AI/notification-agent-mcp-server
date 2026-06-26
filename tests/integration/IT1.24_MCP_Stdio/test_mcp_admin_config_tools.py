#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from mcp.client import session, stdio
from mcp.client.stdio import StdioServerParameters

from tests.utils.mcp_helpers import build_stdio_server_env, require_env_marker_any, require_config


def _tool_payload(result) -> dict:
    assert result.content, "Expected tool content"
    return json.loads(result.content[0].text)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_it124_stdio_admin_config_tools(test_config):
    require_env_marker_any(
        test_config,
        ["test.mcp_stdio_env_loaded", "test.mcp_docker_env_loaded"],
        "private/env-test-mcp-stdio or private/env-docker-local-smoke",
    )

    protocol_version = require_config(test_config, "mcp_server.protocol_version")
    env_file = require_config(test_config, "test.mcp_stdio_env_file")
    api_base_url = require_config(test_config, "api_server.base_url").rstrip("/")
    api_key = require_config(test_config, "api_server.api_key")
    message_base_url = require_config(test_config, "messages.base_url")

    repo_root = Path(__file__).resolve().parents[3]
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["start_mcp_server.py", "--env", env_file],
        env=build_stdio_server_env(),
        cwd=str(repo_root),
    )

    run_id = uuid4().hex[:8]
    channel_id = None
    user_id = None
    api_key_id = None

    async with stdio.stdio_client(server_params) as (read_stream, write_stream):
        async with session.ClientSession(read_stream, write_stream) as client:
            init_result = await client.initialize()
            assert str(init_result.protocolVersion) == str(protocol_version)

            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            assert "admin_create_channel" in tool_names
            assert "admin_create_user" in tool_names
            assert "admin_create_api_key" in tool_names

            create_channel = await client.call_tool(
                "admin_create_channel",
                {
                    "name": f"it124_loopback_{run_id}",
                    "type": "loopback",
                    "enabled": True,
                    "config": {"base_url": message_base_url},
                },
            )
            create_channel_payload = _tool_payload(create_channel)
            channel_id = int(create_channel_payload["id"])
            assert channel_id > 0

            list_channels = await client.call_tool("admin_list_channels", {})
            list_channels_payload = _tool_payload(list_channels)
            assert any(ch.get("id") == channel_id for ch in list_channels_payload["channels"])

            create_user = await client.call_tool(
                "admin_create_user",
                {
                    "username": f"it124_user_{run_id}",
                    "email": f"gary+it124-{run_id}@cloud-dog.net",
                    "display_name": f"IT124 User {run_id}",
                    "role": "user",
                    "language": "en",
                    "preferred_channel": "email",
                },
            )
            create_user_payload = _tool_payload(create_user)
            user_id = int(create_user_payload["id"])
            assert user_id > 0

            list_users = await client.call_tool("admin_list_users", {"email": f"gary+it124-{run_id}@cloud-dog.net"})
            list_users_payload = _tool_payload(list_users)
            items = list_users_payload.get("items", list_users_payload)
            assert any(int(item["id"]) == user_id for item in items)

            create_key = await client.call_tool(
                "admin_create_api_key",
                {"owner_user_id": f"it124-owner-{run_id}", "ttl_days": 3, "key_prefix": "it124"},
            )
            create_key_payload = _tool_payload(create_key)
            api_key_id = create_key_payload["api_key_id"]
            assert create_key_payload["api_key"].startswith("it124")

            revoke_key = await client.call_tool("admin_revoke_api_key", {"key_id": api_key_id})
            revoke_key_payload = _tool_payload(revoke_key)
            assert revoke_key_payload["revoked"] is True

            delete_channel = await client.call_tool("admin_delete_channel", {"channel_id": channel_id})
            delete_channel_payload = _tool_payload(delete_channel)
            assert delete_channel_payload["deleted"] is True
            channel_id = None

    headers = {"X-API-Key": api_key}
    async with httpx.AsyncClient(timeout=10.0) as http_client:
        if channel_id is not None:
            await http_client.delete(f"{api_base_url}/channels/{channel_id}", headers=headers)
        if user_id is not None:
            await http_client.delete(f"{api_base_url}/users/{user_id}", headers=headers)
        if api_key_id is not None:
            await http_client.delete(f"{api_base_url}/admin/api-keys/{api_key_id}", headers=headers)
