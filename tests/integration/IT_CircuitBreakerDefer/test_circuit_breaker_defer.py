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

"""Integration coverage for defer-on-breaker-open with the real worker runtime."""

from __future__ import annotations

import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import httpx
import pytest


_FAKE_OPENAI_PORT = 18021
_SUCCESS_STATES = {"sent", "accepted", "delivered", "read"}


class _FakeOpenAIState:
    def __init__(self) -> None:
        self.mode = "timeout"
        self.timeout_seconds = 2.0
        self.chat_requests = 0


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
    state: _FakeOpenAIState

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
        del format, args

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        if self.path.rstrip("/") == "/v1/models":
            self._send_json(200, {"object": "list", "data": [{"id": "fake-qwen3"}]})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send_json(404, {"error": "not found"})
            return

        self.state.chat_requests += 1
        if self.state.mode == "timeout":
            time.sleep(self.state.timeout_seconds)
            return

        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length) if content_length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")
        prompt_messages = payload.get("messages") or []
        prompt_text = ""
        if prompt_messages:
            prompt_text = str(prompt_messages[-1].get("content") or "")
        prompt_tail = prompt_text.strip().splitlines()[-1] if prompt_text.strip() else "ok"
        self._send_json(
            200,
            {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "model": str(payload.get("model") or "fake-qwen3"),
                "choices": [{"message": {"role": "assistant", "content": f"Recovered: {prompt_tail}"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            },
        )


@pytest.fixture
def api_client(api_base_url, api_key):
    client = httpx.Client(
        base_url=api_base_url,
        headers={"X-API-Key": api_key},
        timeout=15.0,
    )
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def fake_openai_server():
    state = _FakeOpenAIState()
    _FakeOpenAIHandler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", _FAKE_OPENAI_PORT), _FakeOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                response = httpx.get(f"http://127.0.0.1:{_FAKE_OPENAI_PORT}/v1/models", timeout=1.0)
                if response.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.1)
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _create_loopback_channel(api_client: httpx.Client, api_base_url: str) -> tuple[int, str]:
    channel_name = f"it-breaker-defer-{uuid.uuid4().hex[:10]}"
    response = api_client.post(
        "/channels",
        json={
            "name": channel_name,
            "type": "loopback",
            "enabled": True,
            "config": {"base_url": api_base_url},
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"]), channel_name


def _create_message(api_client: httpx.Client, channel_name: str, body: str) -> int:
    response = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [
                {
                    "channel": channel_name,
                    "address": f"user-{uuid.uuid4().hex[:8]}",
                    "preferences": {"language": "fr"},
                }
            ],
            "content": [{"type": "text", "body": body}],
            "options": {"subject": "Circuit breaker defer"},
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["message_id"])


def _get_message_deliveries(api_client: httpx.Client, message_id: int) -> list[dict[str, Any]]:
    response = api_client.get(f"/messages/{message_id}/deliveries")
    assert response.status_code == 200, response.text
    payload = response.json()
    return list(payload.get("items") or [])


def _wait_for_delivery_id(api_client: httpx.Client, message_id: int, timeout_seconds: float = 20.0) -> int:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        deliveries = _get_message_deliveries(api_client, message_id)
        if deliveries:
            return int(deliveries[0]["id"])
        time.sleep(0.2)
    pytest.fail(f"Delivery record not created for message {message_id} within {timeout_seconds}s")


def _fetch_delivery(api_client: httpx.Client, delivery_id: int) -> dict[str, Any]:
    response = api_client.get(f"/deliveries/{delivery_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _wait_for_llm_status(
    api_client: httpx.Client,
    *,
    expected_connection_status: str,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = api_client.get("/llm/status")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload.get("connection_status") == expected_connection_status:
            return payload
        time.sleep(0.25)
    pytest.fail(
        f"/llm/status did not reach connection_status={expected_connection_status!r} within {timeout_seconds}s"
    )


def _wait_for_all_states(
    api_client: httpx.Client,
    delivery_ids: list[int],
    *,
    expected_state: str | None = None,
    acceptable_states: set[str] | None = None,
    timeout_seconds: float = 45.0,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        deliveries = [_fetch_delivery(api_client, delivery_id) for delivery_id in delivery_ids]
        states = {str(delivery.get("state") or "") for delivery in deliveries}
        if expected_state is not None and states == {expected_state}:
            return deliveries
        if acceptable_states is not None and states.issubset(acceptable_states):
            return deliveries
        time.sleep(0.5)
    pytest.fail(
        f"Deliveries {delivery_ids} did not reach the expected states within {timeout_seconds}s: "
        f"{[_fetch_delivery(api_client, delivery_id).get('state') for delivery_id in delivery_ids]}"
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_breaker_open_defers_and_retries_real_worker(api_client, api_base_url, fake_openai_server, test_config):
    llm_base_url = str(test_config.get("llm.base_url") or "")
    llm_model = str(test_config.get("llm.model") or "")
    if "127.0.0.1:18021" not in llm_base_url or llm_model != "fake-qwen3":
        pytest.skip(
            "Circuit-breaker defer integration requires tests/env-IT-circuit-breaker-defer "
            "with the local fake OpenAI runtime."
        )

    channel_id, channel_name = _create_loopback_channel(api_client, api_base_url)
    created_message_ids: list[int] = []
    try:
        warmup_message_ids = []
        for index in range(5):
            warmup_message_ids.append(
                _create_message(api_client, channel_name, f"Warm up breaker {index} with French formatting.")
            )
        created_message_ids.extend(warmup_message_ids)

        breaker_status = _wait_for_llm_status(
            api_client,
            expected_connection_status="breaker_open",
            timeout_seconds=40.0,
        )
        assert breaker_status["available"] is False

        measured_message_ids = []
        measured_delivery_ids = []
        for index in range(5):
            message_id = _create_message(
                api_client,
                channel_name,
                f"Deferred delivery {index}: translate this for breaker-open coverage.",
            )
            measured_message_ids.append(message_id)
            measured_delivery_ids.append(_wait_for_delivery_id(api_client, message_id))
        created_message_ids.extend(measured_message_ids)

        deferred_deliveries = _wait_for_all_states(
            api_client,
            measured_delivery_ids,
            expected_state="deferred",
            timeout_seconds=30.0,
        )
        assert len(deferred_deliveries) == 5

        for delivery in deferred_deliveries:
            assert delivery["state"] == "deferred"
            assert delivery.get("personalised_payload") in (None, "")
            assert delivery.get("next_action_at")
            metadata = json.loads(delivery.get("metadata_json") or "{}")
            assert metadata.get("llm_deferred_reason") == "breaker_open"
            assert metadata.get("llm_retry_after")

        fake_openai_server.mode = "success"

        recovered_deliveries = _wait_for_all_states(
            api_client,
            measured_delivery_ids,
            acceptable_states=_SUCCESS_STATES,
            timeout_seconds=90.0,
        )
        assert len(recovered_deliveries) == 5
        assert all(delivery.get("state") in _SUCCESS_STATES for delivery in recovered_deliveries)
    finally:
        for message_id in created_message_ids:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass
        try:
            api_client.delete(f"/channels/{channel_id}")
        except Exception:
            pass


pytestmark = [
    pytest.mark.integration,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.no_llm_dependency,
]
