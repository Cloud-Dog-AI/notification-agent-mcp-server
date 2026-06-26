# @pytest.mark.req("UC-021")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-106")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
# SPDX-License-Identifier: Apache-2.0

"""MCP contract tests for send_notification structuredContent."""

from __future__ import annotations

import json as _json

import pytest
import httpx

from src.servers.mcp import mcp_server
from src.servers.mcp.mcp_server_http import _PlatformMCPServer
from src.servers.mcp.send_notification_contract import SEND_NOTIFICATION_OUTPUT_SCHEMA, build_send_notification_api_payload
from src.servers.mcp.tool_registry import build_tool_contracts

pytestmark = [
    pytest.mark.unit,
    pytest.mark.mcp,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://notification.test/messages")

    def json(self) -> dict:
        return self._payload

    @property
    def text(self) -> str:
        # Mirror httpx.Response.text so error paths that read response.text
        # (e.g. mcp_server._call_api raising "<code>: <body>") behave faithfully.
        return _json.dumps(self._payload)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Duplicate idempotency key",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    json=self._payload,
                    request=self.request,
                ),
            )


class _FakeHttpClient:
    def __init__(self, *, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.posts: list[dict] = []
        self.gets: list[str] = []

    async def post(self, path: str, *, json: dict, timeout: int) -> _FakeResponse:
        del timeout
        self.posts.append({"path": path, "json": json})
        if self.duplicate:
            return _FakeResponse({"detail": "Duplicate idempotency key"}, status_code=409)
        return _FakeResponse({"message_id": 5001, "status": "queued"})

    async def get(self, path: str, *, params: dict, timeout: int) -> _FakeResponse:
        del params, timeout
        self.gets.append(path)
        return _FakeResponse({"items": [{"id": 6101}]})


def _server_with_fake_client(client: _FakeHttpClient) -> _PlatformMCPServer:
    server = _PlatformMCPServer.__new__(_PlatformMCPServer)
    server.http_client = client
    server.api_timeout = 30
    server.config = {}
    return server
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_send_notification_tool_registry_advertises_output_schema() -> None:
    server = _PlatformMCPServer.__new__(_PlatformMCPServer)
    registry = server._tool_registry()

    assert "get_status" in registry
    assert "send_notification" in registry
    assert registry["send_notification"]["output_schema"] == SEND_NOTIFICATION_OUTPUT_SCHEMA

    contracts = build_tool_contracts()
    assert "send_notification" in contracts
    assert contracts["send_notification"].output_schema == SEND_NOTIFICATION_OUTPUT_SCHEMA
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_send_notification_payload_normalises_llm_aliases_and_subject() -> None:
    payload = build_send_notification_api_payload(
        {
            "destinations": [
                {
                    "type": "email_default",
                    "recipient": "Ukraine Digest Demo Group",
                    "preferences": {"content_style": "html"},
                }
            ],
            "content": [
                {
                    "html": "<h1>Ukraine digest</h1>",
                    "subject": "Ukraine digest: 7-day situation update",
                }
            ],
            "idempotency_key": "w28c-llm-aliases",
        }
    )

    assert payload["destinations"] == [
        {
            "type": "email_default",
            "recipient": "Ukraine Digest Demo Group",
            "preferences": {"content_style": "html"},
            "channel": "email_default",
            "address": "group:Ukraine Digest Demo Group",
        }
    ]
    assert payload["content"][0]["type"] == "html"
    assert payload["content"][0]["body"] == "<h1>Ukraine digest</h1>"
    assert payload["options"]["subject"] == "Ukraine digest: 7-day situation update"
    assert payload["idempotency_key"] == "w28c-llm-aliases"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_stdio_list_tools_advertises_send_notification_output_schema() -> None:
    tools = await mcp_server.list_tools()
    send_tool = next(tool for tool in tools if tool.name == "send_notification")

    assert send_tool.outputSchema == SEND_NOTIFICATION_OUTPUT_SCHEMA
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_send_notification_success_returns_structured_content() -> None:
    client = _FakeHttpClient()
    server = _server_with_fake_client(client)

    result = await server._tool_send_notification(
        {
            "destinations": [{"channel": "email_default", "address": "user@example.test"}],
            "content": [{"type": "text", "body": "hello"}],
            "idempotency_key": "w28a334-first",
        }
    )

    assert result["isError"] is False
    assert result["content"][0]["type"] == "text"
    assert result["structuredContent"] == {
        "ok": True,
        "message_id": 5001,
        "delivery_ids": [6101],
        "status": "completed",
        "deduped": False,
    }
    assert client.posts[0]["json"]["idempotency_key"] == "w28a334-first"
    assert client.gets == ["/messages/5001/deliveries"]
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_structured_deduped_success(monkeypatch) -> None:
    client = _FakeHttpClient(duplicate=True)
    server = _server_with_fake_client(client)

    monkeypatch.setattr(
        "src.servers.mcp.mcp_server_http.resolve_duplicate_notification_from_db",
        lambda config, key: {"message_id": 5001, "delivery_ids": [6101]},
    )

    result = await server._tool_send_notification(
        {
            "destinations": [{"channel": "email_default", "address": "user@example.test"}],
            "content": [{"type": "text", "body": "hello again"}],
            "idempotency_key": "w28a334-duplicate",
        }
    )

    assert result["isError"] is False
    assert result["structuredContent"]["ok"] is True
    assert result["structuredContent"]["message_id"] == 5001
    assert result["structuredContent"]["delivery_ids"] == [6101]
    assert result["structuredContent"]["deduped"] is True
