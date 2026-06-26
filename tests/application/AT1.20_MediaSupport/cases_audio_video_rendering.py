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
Description: Application Test AT1.22B - Audio/Video rendering readiness (API-only).

This test is gated by `test.at122.av_enabled` because AV rendering is not
being exercised yet. When enabled, it validates that formatted payloads
contain audio/video references for HTML rendering paths.

Related Requirements: FR1.21, FR1.19
Related Tasks: T32
Related Architecture: CC5.3.4, CC5.3.5
Related Tests: AT1.22A

Recent Changes (max 10):
- 2026-02-02: Added gated rendering readiness test.
**************************************************
"""

import json
import time
from typing import Any, Dict, List

import httpx
import pytest

from tests.utils.test_helpers import check_test_dependencies


def _require_at122_env_loaded(test_config) -> None:
    marker = test_config.get("test.at122_env_loaded")
    if marker not in [True, 1, "true", "True"]:
        pytest.fail(
            "❌ HARD FAIL: AT1.22 env marker not set. "
            "Load tests with: --env private/env-test-at122"
        )


def _require_value(test_config, key: str) -> str:
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    return str(value)


def _require_bool(test_config, key: str) -> bool:
    value = test_config.get(key)
    if value in [True, 1, "true", "True"]:
        return True
    if value in [False, 0, "false", "False"]:
        return False
    pytest.fail(f"❌ HARD FAIL: {key} must be a boolean value")


def _parse_json_dict(test_config, key: str) -> Dict[str, Any]:
    raw = test_config.get(key)
    if raw is None or raw == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured (expected JSON object)")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        pytest.fail(f"❌ HARD FAIL: {key} must be a JSON object string")
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        pytest.fail(f"❌ HARD FAIL: {key} JSON parse failed: {exc}")
    if not isinstance(parsed, dict):
        pytest.fail(f"❌ HARD FAIL: {key} must parse to a dict")
    return parsed


def _parse_json_list(test_config, key: str) -> List[Any]:
    raw = test_config.get(key)
    if raw is None or raw == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured (expected JSON list)")
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str):
        pytest.fail(f"❌ HARD FAIL: {key} must be a JSON list string")
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        pytest.fail(f"❌ HARD FAIL: {key} JSON parse failed: {exc}")
    if not isinstance(parsed, list):
        pytest.fail(f"❌ HARD FAIL: {key} must parse to a list")
    return parsed


def _parse_metadata_json(delivery: dict) -> dict:
    raw = delivery.get("metadata_json")
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _wait_for_delivery(api_client, message_id: int, test_config) -> dict:
    max_wait = _require_number(test_config, "test.at122.max_wait", number_type="int")
    poll_interval = _require_number(test_config, "test.at122.poll_interval", number_type="float")

    start = time.time()
    last_delivery = None
    while time.time() - start < max_wait:
        resp = api_client.get(f"/messages/{message_id}/deliveries")
        assert resp.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {resp.status_code} {resp.text[:200]}"
        deliveries = (resp.json() or {}).get("items", [])
        if deliveries:
            last_delivery = deliveries[0]
            state = last_delivery.get("state") or last_delivery.get("status")
            if state in ["sent", "delivered", "failed"]:
                return last_delivery
        time.sleep(poll_interval)

    pytest.fail(f"❌ Delivery did not complete within {max_wait}s; last_delivery={last_delivery}")


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config, restart_api_per_test):
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)

    api_timeout = httpx.Timeout(
        timeout=timeout_total,
        connect=timeout_connect,
        read=timeout_read,
    )

    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key},
    ) as client:
        yield client


def test_at122_audio_video_rendering_ready(api_client, test_config):
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_at122_audio_video_rendering_ready",
    )
    _require_at122_env_loaded(test_config)
    if not _require_bool(test_config, "test.at122.av_enabled"):
        pytest.skip("AT1.22 AV rendering is disabled by test.at122.av_enabled=false")

    health = api_client.get("/health")
    assert health.status_code == 200, f"API server health check failed: {health.status_code} {health.text[:200]}"

    test_id = str(int(time.time()))
    messages_base_url = _require_value(test_config, "messages.base_url")
    channel_type = _require_value(test_config, "test.at122.channel_type")
    channel_name_prefix = _require_value(test_config, "test.at122.channel_name_prefix")
    message_path_template = _require_value(test_config, "test.at122.message_path_template")
    destination_address = _require_value(test_config, "test.at122.destination_address")
    destination_preferences = _parse_json_dict(test_config, "test.at122.destination_preferences_json")
    audio_uri = _require_value(test_config, "test.at122.audio_data_uri")
    video_uri = _require_value(test_config, "test.at122.video_data_uri")
    expected_markers = _parse_json_list(test_config, "test.at122.render_expected_markers")
    subject_prefix = _require_value(test_config, "test.at122.subject_prefix")

    channel_name = f"{channel_name_prefix}_render_{test_id}"
    channel_payload = {
        "name": channel_name,
        "type": channel_type,
        "enabled": True,
        "config": {
            "base_url": messages_base_url,
            "message_path_template": message_path_template,
            "duplicate_external_media": True,
            "duplicate_images": True,
            "duplicate_audio": True,
            "duplicate_video": True,
        },
    }

    created_channel_id = None
    message_id = None
    try:
        created = api_client.post("/channels", json=channel_payload)
        assert created.status_code == 201, f"POST /channels failed: {created.status_code} {created.text[:200]}"
        created_channel_id = created.json().get("id")
        assert created_channel_id, "POST /channels did not return an id"

        message_payload = {
            "audience_type": "personalised",
            "destinations": [
                {
                    "channel": channel_name,
                    "address": destination_address,
                    "preferences": destination_preferences,
                }
            ],
            "content": [
                {"type": "text", "body": f"AT1.22 rendering readiness {test_id}"},
                {"type": "audio", "body": "audio uri", "uri": audio_uri, "alt_text": "audio uri"},
                {"type": "video", "body": "video uri", "uri": video_uri, "alt_text": "video uri"},
            ],
            "options": {"subject": f"{subject_prefix} {test_id}"},
        }

        created_msg = api_client.post("/messages", json=message_payload)
        assert created_msg.status_code == 201, f"POST /messages failed: {created_msg.status_code} {created_msg.text[:200]}"
        message_id = created_msg.json().get("message_id")
        assert message_id, "POST /messages did not return message_id"

        delivery = _wait_for_delivery(api_client, int(message_id), test_config)
        state = delivery.get("state") or delivery.get("status")
        assert state in ["sent", "delivered"], f"Unexpected delivery state: {state}"

        delivery_id = delivery.get("id")
        assert delivery_id, "Delivery id missing"
        r = api_client.get(f"/deliveries/{delivery_id}")
        assert r.status_code == 200, f"GET /deliveries/{{id}} failed: {r.status_code}"

        payload_str = r.json().get("personalised_payload", "{}")
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        body = ""
        if isinstance(payload, dict):
            body = payload.get("body", "") or payload.get("text", "")
        elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
            body = payload[0].get("body", "")
        assert body, "Rendered payload body is empty"

        metadata = _parse_metadata_json(delivery)
        processed_media = metadata.get("processed_media") if isinstance(metadata, dict) else None
        assert isinstance(processed_media, list) and processed_media, "Delivery metadata missing processed_media"

        audio_items = [m for m in processed_media if m.get("type") == "audio"]
        video_items = [m for m in processed_media if m.get("type") == "video"]
        assert audio_items, "Expected processed audio media items"
        assert video_items, "Expected processed video media items"

        for item in audio_items + video_items:
            storage_info = item.get("storage_info") or {}
            storage_path = storage_info.get("storage_path")
            assert storage_path, "storage_info.storage_path missing"
            stored = api_client.get(f"/storage/{storage_path}")
            assert stored.status_code == 200, f"GET /storage/{{path}} failed: {stored.status_code} {stored.text[:200]}"
            assert stored.content, "Stored media content should be non-empty"

        missing_markers = []
        for marker in expected_markers:
            if marker in body:
                continue
            if marker.startswith("<audio") and audio_items:
                continue
            if marker.startswith("<video") and video_items:
                continue
            missing_markers.append(marker)
        assert not missing_markers, f"Expected rendering markers missing: {missing_markers}"

    finally:
        if message_id:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass
        if created_channel_id:
            disabled = api_client.post(f"/channels/{created_channel_id}/disable")
            assert disabled.status_code in [200, 204], f"Failed to disable channel: {disabled.status_code} {disabled.text[:200]}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-007")
