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
Description: Application Test AT1.23 - Multimedia PDF (UC1.6) API-only flow.

Validates:
- API-driven channel CRUD for multimedia loopback delivery
- Multi-destination delivery with language preferences
- PDF generation (attachment/link) and storage retrieval
- Media duplication metadata and storage access

Related Requirements: FR1.18, FR1.19, FR1.21, UC1.6
Related Tasks: T29, T30, T32
Related Architecture: CC5.3, CC6.1.3
Related Tests: AT1.23, AT1.24

Recent Changes (max 10):
- 2026-02-02: Refactor to config-driven, API-only, CRUD-complete validation.
**************************************************
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
import pytest

from tests.utils.test_helpers import check_test_dependencies


def _require_at123_env_loaded(test_config) -> None:
    marker = test_config.get("test.at123_env_loaded")
    if marker not in [True, 1, "true", "True"]:
        pytest.fail(
            "❌ HARD FAIL: AT1.23 env marker not set. "
            "Load tests with: --env private/env-test-at123"
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
    message_file = test_config.get("test.at123.message_file")
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
    return _require_value(test_config, "test.at123.message_body")

def _wait_for_all_deliveries(api_client, message_id: int, test_config) -> list:
    max_wait = _require_number(test_config, "test.at123.max_wait", number_type="int")
    poll_interval = _require_number(test_config, "test.at123.poll_interval", number_type="float")

    start = time.time()
    last_items = []
    while time.time() - start < max_wait:
        resp = api_client.get(f"/messages/{message_id}/deliveries")
        assert resp.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {resp.status_code} {resp.text[:200]}"
        items = (resp.json() or {}).get("items", [])
        if items:
            last_items = items
            all_terminal = all((d.get("state") or d.get("status")) in ["sent", "delivered", "failed"] for d in items)
            if all_terminal:
                return items
        time.sleep(poll_interval)

    pytest.fail(f"❌ Deliveries did not complete within {max_wait}s; last_items={last_items}")


def _storage_path_from_access_url(access_url: str) -> str:
    if not access_url:
        return ""
    parsed = urlparse(access_url)
    path = parsed.path or ""
    if "/storage/" in path:
        return path.split("/storage/", 1)[1].lstrip("/")
    return ""


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


def test_at123_uc16_multimedia_pdf_multilanguage_end_to_end(api_client, test_config):
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_at123_uc16_multimedia_pdf_multilanguage_end_to_end",
    )
    _require_at123_env_loaded(test_config)

    health = api_client.get("/health")
    assert health.status_code == 200, f"API server health check failed: {health.status_code} {health.text[:200]}"

    test_id = str(int(time.time()))
    messages_base_url = _require_value(test_config, "messages.base_url")
    channel_type = _require_value(test_config, "test.at123.channel_type")
    channel_name_prefix = _require_value(test_config, "test.at123.channel_name_prefix")
    message_path_template = _require_value(test_config, "test.at123.message_path_template")
    duplicate_external_media = _require_bool(test_config, "test.at123.duplicate_external_media")
    duplicate_images = _require_bool(test_config, "test.at123.duplicate_images")
    duplicate_audio = _require_bool(test_config, "test.at123.duplicate_audio")
    update_duplicate_external_media = _require_bool(test_config, "test.at123.update_duplicate_external_media")
    destinations = _parse_json_list(test_config, "test.at123.destinations_json")
    if not destinations:
        pytest.fail("❌ HARD FAIL: test.at123.destinations_json must include at least one destination")
    has_attach = any(
        isinstance(d, dict)
        and isinstance(d.get("preferences"), dict)
        and d["preferences"].get("pdf_preference") == "attach"
        for d in destinations
    )
    if not has_attach:
        pytest.fail("❌ HARD FAIL: test.at123.destinations_json must include at least one pdf_preference=attach")
    image_data_uri = _require_value(test_config, "test.at123.image_data_uri")
    audio_data_uri = _require_value(test_config, "test.at123.audio_data_uri")
    expected_media_types = _parse_json_list(test_config, "test.at123.expected_media_types")
    subject_prefix = _require_value(test_config, "test.at123.subject_prefix")
    message_body = _load_message_body(test_config)

    channel_name = f"{channel_name_prefix}_{test_id}"
    channel_config = {
        "base_url": messages_base_url,
        "message_path_template": message_path_template,
        "duplicate_external_media": duplicate_external_media,
        "duplicate_images": duplicate_images,
        "duplicate_audio": duplicate_audio,
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

        markdown_content = (
            f"{message_body}\n\n"
            f"<img src=\"{image_data_uri}\" alt=\"AT1.23 image\">\n\n"
            f"<audio controls src=\"{audio_data_uri}\"></audio>\n"
        )

        destinations_payload = []
        for dest in destinations:
            if not isinstance(dest, dict):
                pytest.fail("❌ HARD FAIL: test.at123.destinations_json items must be objects")
            address = dest.get("address")
            preferences = dest.get("preferences")
            if not address or not isinstance(preferences, dict):
                pytest.fail("❌ HARD FAIL: each destination must include address + preferences dict")
            destinations_payload.append(
                {"channel": channel_name, "address": address, "preferences": preferences}
            )

        message_payload = {
            "audience_type": "personalised",
            "destinations": destinations_payload,
            "content": [
                {"type": "markdown", "body": markdown_content},
                {"type": "image", "body": "image uri", "uri": image_data_uri, "alt_text": "image uri"},
                {"type": "audio", "body": "audio uri", "uri": audio_data_uri, "alt_text": "audio uri"},
            ],
            "options": {"subject": f"{subject_prefix} {test_id}"},
        }

        created_msg = api_client.post("/messages", json=message_payload)
        assert created_msg.status_code == 201, f"POST /messages failed: {created_msg.status_code} {created_msg.text[:200]}"
        message_id = created_msg.json().get("message_id")
        assert message_id, "POST /messages did not return message_id"

        deliveries = _wait_for_all_deliveries(api_client, int(message_id), test_config)
        assert len(deliveries) >= len(destinations), (
            f"Expected at least {len(destinations)} deliveries, got {len(deliveries)}"
        )

        destinations_by_address = {
            d.get("address"): d for d in destinations if isinstance(d, dict) and d.get("address")
        }
        pdf_links = []

        for delivery in deliveries:
            state = delivery.get("state") or delivery.get("status")
            assert state in ["sent", "delivered"], f"Unexpected delivery state: {state}"

            metadata = _parse_metadata_json(delivery)
            processed_media = metadata.get("processed_media")
            assert isinstance(processed_media, list) and processed_media, "Delivery metadata missing processed_media"

            for media_type in expected_media_types:
                items = [m for m in processed_media if m.get("type") == media_type]
                assert items, f"Expected processed media items for type: {media_type}"
                local_items = [m for m in items if m.get("is_local") is True]
                assert local_items, f"Expected duplicated local media for type: {media_type}"
                for item in local_items:
                    storage_info = item.get("storage_info")
                    assert isinstance(storage_info, dict), "storage_info missing for duplicated media"
                    storage_path = storage_info.get("storage_path")
                    assert storage_path, "storage_info.storage_path missing"
                    stored = api_client.get(f"/storage/{storage_path}")
                    assert stored.status_code == 200, f"GET /storage/{{path}} failed: {stored.status_code} {stored.text[:200]}"
                    assert stored.content, "Stored media content should be non-empty"

            payload_json = delivery.get("personalised_payload")
            assert payload_json, "Expected personalised_payload to be stored"
            payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json

            attachments = None
            body_text = ""
            if isinstance(payload, dict):
                attachments = payload.get("attachments")
                body_text = payload.get("body") or payload.get("text") or ""
            elif isinstance(payload, list):
                parts = []
                for entry in payload:
                    if not isinstance(entry, dict):
                        continue
                    if attachments is None:
                        attachments = entry.get("attachments")
                    entry_text = entry.get("body") or entry.get("text") or ""
                    if entry_text:
                        parts.append(entry_text)
                body_text = "\n".join(parts)

            pdf_preference = None
            destination = delivery.get("destination")
            prefs = (destinations_by_address.get(destination) or {}).get("preferences") or {}
            if isinstance(prefs, dict):
                pdf_preference = prefs.get("pdf_preference")

            if pdf_preference == "attach":
                assert isinstance(attachments, list) and attachments, "Expected PDF attachment entries"
                pdf_attachment = next(
                    (
                        a for a in attachments
                        if a.get("type") == "pdf" or a.get("content_type") == "application/pdf"
                    ),
                    None,
                )
                assert pdf_attachment, "Expected PDF attachment entry"
                if pdf_attachment.get("url"):
                    pdf_links.append(pdf_attachment["url"])
            elif pdf_preference == "link":
                assert "http" in body_text.lower(), "Expected PDF link in payload body/text"
                if ".pdf" in body_text or "/storage/" in body_text:
                    pass
                else:
                    pytest.fail("Expected PDF link to reference .pdf or /storage/")

        for link in pdf_links:
            storage_path = _storage_path_from_access_url(link)
            assert storage_path, f"Could not derive storage_path from PDF link: {link}"
            resp = api_client.get(f"/storage/{storage_path}")
            assert resp.status_code == 200, f"Failed to fetch PDF via /storage: {resp.status_code} {resp.text[:200]}"
            assert resp.content and resp.content.startswith(b"%PDF"), "Stored PDF should start with %PDF"

    finally:
        if message_id:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass
        if created_channel_id:
            try:
                disabled = api_client.post(f"/channels/{created_channel_id}/disable")
                assert disabled.status_code in [200, 204], (
                    f"Failed to disable channel: {disabled.status_code} {disabled.text[:200]}"
                )
            except Exception:
                pass

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
# @pytest.mark.req("FR-020")
