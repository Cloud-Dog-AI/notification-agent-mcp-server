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
AT1.28: Audio/Video support validation (renamed from AT1.22_AudioVideoSupport).

Checks:
- Audio payloads can be submitted and delivered via loopback channel.
- Video URI payloads can be submitted and delivered via loopback channel.
"""

from __future__ import annotations

import base64
import time

import httpx
import pytest


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config, restart_api_per_test):
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)
    timeout = httpx.Timeout(timeout=timeout_total, connect=timeout_connect, read=timeout_read)
    with httpx.Client(base_url=api_base_url, timeout=timeout, headers={"X-API-Key": api_key}) as client:
        yield client


def _loopback_channel_name(api_client, test_config) -> str:
    preferred = str(test_config.get("test.loopback_channel_name") or "").strip()
    response = api_client.get("/channels")
    assert response.status_code == 200, f"GET /channels failed: {response.status_code} {response.text[:200]}"
    payload = response.json()
    channels = payload if isinstance(payload, list) else payload.get("items", [])

    loopback_enabled = [
        c for c in channels
        if isinstance(c, dict) and c.get("type") == "loopback" and c.get("enabled")
    ]
    assert loopback_enabled, "No enabled loopback channel available for AT1.28"

    if preferred and any(c.get("name") == preferred for c in loopback_enabled):
        return preferred
    return str(loopback_enabled[0]["name"])


def _create_message(api_client, channel_name: str, content_blocks: list[dict]) -> int:
    payload = {
        "audience_type": "direct",
        "destinations": [{"channel": channel_name, "address": "loopback"}],
        "content": content_blocks,
        "options": {"subject": "AT1.28 Audio/Video Support"},
    }
    response = api_client.post("/messages", json=payload)
    assert response.status_code == 201, f"POST /messages failed: {response.status_code} {response.text[:200]}"
    message_id = response.json().get("message_id")
    assert isinstance(message_id, int), f"Missing message_id in response: {response.text[:200]}"
    return message_id


def _wait_delivery_sent(api_client, message_id: int, test_config) -> dict:
    max_wait = int(test_config.get("test.at117.max_wait") or 180)
    poll = float(test_config.get("test.at117.poll_interval") or 2.0)

    deadline = time.time() + max_wait
    last = None
    while time.time() < deadline:
        response = api_client.get(f"/messages/{message_id}/deliveries")
        assert response.status_code == 200, (
            f"GET /messages/{message_id}/deliveries failed: "
            f"{response.status_code} {response.text[:200]}"
        )
        payload = response.json()
        items = payload.get("items") or []
        if items:
            last = items[0]
            state = str(last.get("state") or "")
            if state == "sent":
                return last
            if state in {"hard_failed", "cancelled", "ttl_expired"}:
                pytest.fail(f"Delivery entered terminal failure state '{state}': {last}")
        time.sleep(poll)

    pytest.fail(f"Delivery did not reach sent within {max_wait}s. Last={last}")


def _extract_processed_media(delivery: dict) -> list[dict]:
    metadata = delivery.get("metadata_json") or {}
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata) if metadata else {}
        except Exception:
            metadata = {}
    if not isinstance(metadata, dict):
        return []
    media = metadata.get("processed_media") or []
    return media if isinstance(media, list) else []


def test_at128_audio_payload_delivery(api_client, test_config):
    channel_name = _loopback_channel_name(api_client, test_config)

    wav_bytes = (
        b"RIFF$\x00\x00\x00WAVEfmt "
        b"\x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"
        b"\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    audio_uri = "data:audio/wav;base64," + base64.b64encode(wav_bytes).decode("ascii")

    message_id = _create_message(
        api_client,
        channel_name,
        [
            {"type": "text", "body": "AT1.28 audio support check"},
            {"type": "audio", "body": "sample wav", "uri": audio_uri},
        ],
    )
    try:
        delivery = _wait_delivery_sent(api_client, message_id, test_config)
        processed_media = _extract_processed_media(delivery)
        assert any(m.get("type") == "audio" for m in processed_media), (
            "Expected audio item in delivery processed_media metadata"
        )
    finally:
        api_client.delete(f"/messages/{message_id}")


def test_at128_video_uri_delivery(api_client, test_config):
    channel_name = _loopback_channel_name(api_client, test_config)
    video_uri = "https://example.com/test-video.mp4"

    message_id = _create_message(
        api_client,
        channel_name,
        [
            {"type": "text", "body": "AT1.28 video support check"},
            {"type": "video", "body": "sample mp4 reference", "uri": video_uri},
        ],
    )
    try:
        delivery = _wait_delivery_sent(api_client, message_id, test_config)
        processed_media = _extract_processed_media(delivery)
        assert any(m.get("type") == "video" for m in processed_media), (
            "Expected video item in delivery processed_media metadata"
        )
    finally:
        api_client.delete(f"/messages/{message_id}")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.pure, pytest.mark.heavy]

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-007")
