# @pytest.mark.req("UC-022")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-104")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from uuid import uuid4

import httpx
import pytest


def _require_value(value, key: str) -> str:
    text = str(value or "").strip()
    if not text:
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return text


def _build_ws_url(test_config) -> str:
    explicit = str(test_config.get("a2a_server.websocket_url") or "").strip()
    if explicit:
        return explicit
    base = _require_value(test_config.get("a2a_server.base_url"), "a2a_server.base_url").rstrip("/")
    if base.startswith("https://"):
        return base.replace("https://", "wss://", 1) + "/stream"
    return base.replace("http://", "ws://", 1) + "/stream"


def _websocket_probe(ws_url: str) -> subprocess.Popen[str]:
    python_bin = "/usr/bin/python3" if shutil.which("/usr/bin/python3") else shutil.which("python3")
    if not python_bin:
        pytest.fail("python3 not available for websocket probe")

    script = textwrap.dedent(
        """
        import asyncio
        import json
        import sys
        import websockets

        async def main():
            ws_url = sys.argv[1]
            async with websockets.connect(ws_url) as ws:
                await ws.recv()  # connected banner
                for topic in ("config.events", "channels.state"):
                    await ws.send(json.dumps({"action": "subscribe", "topic": topic}))
                    while True:
                        payload = json.loads(await ws.recv())
                        if payload.get("type") == "subscribed" and payload.get("topic") == topic:
                            break
                print("READY", flush=True)
                events = []
                while len(events) < 5:
                    payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=30.0))
                    if payload.get("type") == "event":
                        events.append(payload)
                print(json.dumps(events), flush=True)

        asyncio.run(main())
        """
    ).strip()

    return subprocess.Popen(
        [python_bin, "-c", script, ws_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.dependency_services("api", "a2a")
def test_it129_a2a_broadcasts_config_events(test_config):
    ws_url = _build_ws_url(test_config)
    api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url").rstrip("/")
    api_key = _require_value(test_config.get("api_server.api_key"), "api_server.api_key")
    messages_base_url = _require_value(test_config.get("messages.base_url"), "messages.base_url")
    run_id = uuid4().hex[:8]

    channel_id = None
    user_id = None
    group_id = None
    key_id = None
    probe = _websocket_probe(ws_url)

    try:
        ready_line = (probe.stdout.readline() if probe.stdout else "").strip()
        assert ready_line == "READY", (ready_line, probe.stderr.read() if probe.stderr else "")

        with httpx.Client(timeout=15.0, headers={"X-API-Key": api_key}) as client:
            create_channel = client.post(
                f"{api_base_url}/channels",
                json={
                    "name": f"it129_cfg_channel_{run_id}",
                    "type": "loopback",
                    "enabled": True,
                    "config": {"base_url": messages_base_url},
                },
            )
            assert create_channel.status_code in (200, 201), create_channel.text[:200]
            channel_id = create_channel.json()["id"]

            create_user = client.post(
                f"{api_base_url}/users",
                json={
                    "username": f"it129_cfg_user_{run_id}",
                    "email": f"gary+it129-cfg-{run_id}@cloud-dog.net",
                    "display_name": f"IT129 Config {run_id}",
                    "role": "user",
                },
            )
            assert create_user.status_code in (200, 201), create_user.text[:200]
            user_id = create_user.json()["id"]

            create_group = client.post(
                f"{api_base_url}/groups",
                json={"name": f"it129_cfg_group_{run_id}", "description": "cfg event group", "enabled": True},
            )
            assert create_group.status_code in (200, 201), create_group.text[:200]
            create_group_payload = create_group.json()
            group_id = create_group_payload.get("id") or create_group_payload.get("group_id")
            assert group_id is not None

            create_key = client.post(
                f"{api_base_url}/admin/api-keys",
                json={"owner_user_id": f"it129-owner-{run_id}", "ttl_days": 2, "key_prefix": "it129"},
            )
            assert create_key.status_code in (200, 201), create_key.text[:200]
            key_id = create_key.json()["api_key_id"]

            events_line = (probe.stdout.readline() if probe.stdout else "").strip()
            assert events_line, probe.stderr.read() if probe.stderr else "No websocket event output"
            events = json.loads(events_line)

            config_events = [event for event in events if event.get("topic") == "config.events"]
            channel_events = [event for event in events if event.get("topic") == "channels.state"]

            assert any(
                event["data"]["resource"] == "channel"
                and event["data"]["action"] == "created"
                and int(event["data"]["payload"]["id"]) == channel_id
                for event in config_events
            )
            assert any(
                event["data"]["resource"] == "user"
                and event["data"]["action"] == "created"
                and int(event["data"]["payload"]["id"]) == user_id
                for event in config_events
            )
            assert any(
                event["data"]["resource"] == "group"
                and event["data"]["action"] == "created"
                and int(event["data"]["payload"]["id"]) == group_id
                for event in config_events
            )
            assert any(
                event["data"]["resource"] == "api_key"
                and event["data"]["action"] == "created"
                and event["data"]["payload"]["api_key_id"] == key_id
                for event in config_events
            )
            assert any(
                event["data"]["resource"] == "channel"
                and event["data"]["action"] == "created"
                for event in channel_events
            )

            if key_id is not None:
                client.delete(f"{api_base_url}/admin/api-keys/{key_id}")
            if group_id is not None:
                client.delete(f"{api_base_url}/groups/{group_id}")
            if user_id is not None:
                client.delete(f"{api_base_url}/users/{user_id}")
            if channel_id is not None:
                client.delete(f"{api_base_url}/channels/{channel_id}")
    finally:
        probe.terminate()
        try:
            probe.wait(timeout=5)
        except subprocess.TimeoutExpired:
            probe.kill()
