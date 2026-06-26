#!/usr/bin/env python3

from __future__ import annotations

import pytest
from cloud_dog_idam import APIKeyManager
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_serialise_api_key_item_hides_hash_and_keeps_metadata():
    from src.servers.api import api_server

    manager = APIKeyManager()
    raw_key, _ = manager.generate("ut-admin-owner", ttl_days=7, key_prefix="ut")
    item = manager.list_keys()[0]

    payload = api_server._serialise_api_key_item(item, include_raw_key=raw_key)

    assert payload["owner_user_id"] == "ut-admin-owner"
    assert payload["key_prefix"] == "ut"
    assert payload["api_key"] == raw_key
    assert "key_hash" not in payload
    assert payload["status"] == "active"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_broadcast_config_event_emits_expected_topics(monkeypatch):
    from src.servers.api import api_server

    captured: list[tuple[str, dict, dict]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        is_closed = False

        async def post(self, url: str, *, json: dict, headers: dict):
            captured.append((url, json, headers))
            return FakeResponse()

    monkeypatch.setattr(api_server, "config", None)
    # Patch the shared module-level client instead of httpx.AsyncClient constructor
    monkeypatch.setattr(api_server, "_api_http_client", FakeClient())

    await api_server._broadcast_config_event("channel", "updated", {"id": 7, "enabled": True})
    await api_server._broadcast_config_event("user", "created", {"id": 9})

    assert any(
        entry[1] == {
            "topic": "config.events",
            "data": {"resource": "channel", "action": "updated", "payload": {"id": 7, "enabled": True}},
        }
        for entry in captured
    )
    assert any(
        entry[1] == {
            "topic": "channels.state",
            "data": {"resource": "channel", "action": "updated", "payload": {"id": 7, "enabled": True}},
        }
        for entry in captured
    )
    assert any(
        entry[1] == {
            "topic": "config.events",
            "data": {"resource": "user", "action": "created", "payload": {"id": 9}},
        }
        for entry in captured
    )
    assert not any(entry[1].get("topic") == "channels.state" and entry[1]["data"]["resource"] == "user" for entry in captured)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_mcp_tool_registry_includes_admin_config_tools():
    from src.servers.mcp import mcp_server

    tools = await mcp_server.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "admin_list_channels" in tool_names
    assert "admin_create_channel" in tool_names
    assert "admin_update_channel" in tool_names
    assert "admin_delete_channel" in tool_names
    assert "admin_list_users" in tool_names
    assert "admin_create_user" in tool_names
    assert "admin_create_api_key" in tool_names
    assert "admin_revoke_api_key" in tool_names
