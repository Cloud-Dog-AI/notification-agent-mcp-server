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
Description: Application Test AT1.22A - Audio/Video pipeline duplication (API-only).

Validates:
- API-driven channel CRUD (create/update/disable) for media duplication settings
- Audio/video media ingestion via data URIs (no local file dependencies)
- Storage duplication and retrieval via /storage/* endpoints
- Delivery completion with forensic validation

Related Requirements: FR1.21, FR1.19, FR1.22, FR1.23
Related Tasks: T32
Related Architecture: CC5.3.4, CC5.3.5, CC6.1.3
Related Tests: AT1.20, AT1.23, AT1.24

Recent Changes (max 10):
- 2026-02-02: Refactor to API-only, config-driven, CRUD-complete flow.
**************************************************
"""

import json
import time
from pathlib import Path
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


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


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


def _load_message_body(test_config) -> str:
    message_file = test_config.get("test.at122.message_file")
    if message_file:
        path = Path(str(message_file))
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[3]
            path = project_root / path
        if not path.exists():
            pytest.fail(f"❌ HARD FAIL: message file not found: {path}")
        body = path.read_text(encoding="utf-8").strip()
        if not body:
            pytest.fail(f"❌ HARD FAIL: message file is empty: {path}")
        return body
    return _require_value(test_config, "test.at122.message_body")


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


def test_at122_audio_video_media_duplication_end_to_end(api_client, test_config):
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_at122_audio_video_media_duplication_end_to_end",
    )
    _require_at122_env_loaded(test_config)

    health = api_client.get("/health")
    assert health.status_code == 200, f"API server health check failed: {health.status_code} {health.text[:200]}"

    test_id = str(int(time.time()))
    messages_base_url = _require_value(test_config, "messages.base_url")
    channel_type = _require_value(test_config, "test.at122.channel_type")
    channel_name_prefix = _require_value(test_config, "test.at122.channel_name_prefix")
    message_path_template = _require_value(test_config, "test.at122.message_path_template")
    duplicate_external_media = _require_bool(test_config, "test.at122.duplicate_external_media")
    duplicate_images = _require_bool(test_config, "test.at122.duplicate_images")
    duplicate_audio = _require_bool(test_config, "test.at122.duplicate_audio")
    duplicate_video = _require_bool(test_config, "test.at122.duplicate_video")
    update_duplicate_external_media = _require_bool(test_config, "test.at122.update_duplicate_external_media")
    destination_address = _require_value(test_config, "test.at122.destination_address")
    destination_preferences = _parse_json_dict(test_config, "test.at122.destination_preferences_json")
    audio_uri = _require_value(test_config, "test.at122.audio_data_uri")
    video_uri = _require_value(test_config, "test.at122.video_data_uri")
    expected_media_types = _parse_json_list(test_config, "test.at122.expected_media_types")
    subject_prefix = _require_value(test_config, "test.at122.subject_prefix")
    message_body = _load_message_body(test_config)

    channel_name = f"{channel_name_prefix}_{test_id}"
    channel_config = {
        "base_url": messages_base_url,
        "message_path_template": message_path_template,
        "duplicate_external_media": duplicate_external_media,
        "duplicate_images": duplicate_images,
        "duplicate_audio": duplicate_audio,
        "duplicate_video": duplicate_video,
    }
    channel_payload = {
        "name": channel_name,
        "type": channel_type,
        "enabled": True,
        "config": channel_config,
    }

    created_channel_id = None
    message_id = None
    try:
        created = api_client.post("/channels", json=channel_payload)
        assert created.status_code == 201, f"POST /channels failed: {created.status_code} {created.text[:200]}"
        created_channel_id = created.json().get("id")
        assert created_channel_id, "POST /channels did not return an id"

        updated_config = dict(channel_config)
        updated_config["duplicate_external_media"] = update_duplicate_external_media
        updated = api_client.patch(
            f"/channels/{created_channel_id}",
            json={"config_json": updated_config},
        )
        assert updated.status_code == 200, f"PATCH /channels failed: {updated.status_code} {updated.text[:200]}"

        channel_read = api_client.get(f"/channels/{created_channel_id}")
        assert channel_read.status_code == 200, f"GET /channels/{{id}} failed: {channel_read.status_code}"
        channel_config_read = (channel_read.json() or {}).get("config") or {}
        assert channel_config_read.get("duplicate_external_media") == update_duplicate_external_media

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
                {"type": "text", "body": message_body},
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

        msg_response = api_client.get(
            f"/messages/{message_id}",
            headers={"Accept": "application/json"},
        )
        assert msg_response.status_code == 200, f"GET /messages/{{id}} failed: {msg_response.status_code}"

        metadata = _parse_metadata_json(delivery)
        processed_media = metadata.get("processed_media")
        assert isinstance(processed_media, list) and processed_media, "Delivery metadata missing processed_media"

        for media_type in expected_media_types:
            items = [m for m in processed_media if m.get("type") == media_type]
            assert items, f"Expected processed media items for type: {media_type}"
            local_items = [m for m in items if m.get("is_local") is True and isinstance(m.get("storage_info"), dict)]
            assert local_items, f"Expected duplicated local media for type: {media_type}"
            for item in local_items:
                storage_info = item.get("storage_info") or {}
                storage_path = storage_info.get("storage_path")
                assert storage_path, "storage_info.storage_path missing"
                stored = api_client.get(f"/storage/{storage_path}")
                assert stored.status_code == 200, f"GET /storage/{{path}} failed: {stored.status_code} {stored.text[:200]}"
                assert stored.content, "Stored media content should be non-empty"

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
