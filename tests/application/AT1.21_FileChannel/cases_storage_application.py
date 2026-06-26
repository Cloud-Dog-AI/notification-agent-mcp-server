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
AT1.29: Storage application validation (renamed from AT1.22_StorageApplication).

Checks:
- File channel stores notification output to filesystem backend.
- Stored output can be retrieved through Storage Files API.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

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


def _filesystem_base_path(test_config) -> str:
    base_path = (
        test_config.get("file_channel.filesystem.base_path")
        or test_config.get("storage.local.base_path")
        or test_config.get("storage.filesystem.base_path")
    )
    if not base_path:
        pytest.fail("Filesystem base path not configured (file_channel.filesystem.base_path/storage.*)")
    return str(base_path)


def _create_file_channel(api_client, test_config, test_id: str) -> tuple[int, str]:
    channel_name = f"at129_file_{test_id}"
    channel_config = {
        "storage_type": "filesystem",
        "base_path": _filesystem_base_path(test_config),
        "create_subdirs": False,
        "file_name_pattern": "{message_id}_{lang}.{format}",
        "permissions": "0644",
        "dir_permissions": "0755",
    }
    response = api_client.post(
        "/channels",
        json={
            "name": channel_name,
            "type": "file",
            "enabled": True,
            "config": channel_config,
        },
    )
    assert response.status_code == 201, f"Failed to create file channel: {response.status_code} {response.text[:200]}"
    channel_id = response.json().get("id")
    assert isinstance(channel_id, int), f"Missing channel id: {response.text[:200]}"
    return channel_id, channel_name


def _create_file_message(api_client, channel_name: str, body: str) -> int:
    payload = {
        "audience_type": "direct",
        "destinations": [
            {
                "channel": channel_name,
                "address": "filesystem",
                "preferences": {"language": "en", "output_formats": ["txt"], "generate_pdf": False},
            }
        ],
        "content": [{"type": "text", "body": body}],
        "options": {"subject": "AT1.29 Storage Application"},
    }
    response = api_client.post("/messages", json=payload)
    assert response.status_code == 201, f"POST /messages failed: {response.status_code} {response.text[:200]}"
    message_id = response.json().get("message_id")
    assert isinstance(message_id, int), f"Missing message_id: {response.text[:200]}"
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


def _extract_stored_path(delivery: dict) -> str:
    metadata = delivery.get("metadata_json") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata) if metadata else {}
        except Exception:
            metadata = {}
    stored_files = []
    if isinstance(metadata, dict):
        stored_files = metadata.get("stored_files") or []
    if not stored_files:
        tracking = delivery.get("provider_tracking_id") or ""
        if isinstance(tracking, str) and tracking:
            try:
                parsed = json.loads(tracking)
                if isinstance(parsed, list):
                    stored_files = parsed
            except Exception:
                stored_files = []
    assert stored_files, f"No stored_files metadata found in delivery: {delivery}"
    first = stored_files[0]
    assert isinstance(first, dict), f"Unexpected stored_file entry: {first}"
    path = str(first.get("path") or "")
    assert path, f"Stored file path missing in entry: {first}"
    return path


def _to_filesystem_filename(stored_path: str, base_path: str) -> str:
    try:
        rel = Path(stored_path).resolve().relative_to(Path(base_path).resolve())
        return str(rel)
    except Exception:
        return ""


def test_at129_store_notification_output_filesystem(api_client, test_config):
    test_id = str(int(time.time()))
    channel_id, channel_name = _create_file_channel(api_client, test_config, test_id)
    message_id = _create_file_message(api_client, channel_name, f"AT1.29 store test {test_id}")
    base_path = _filesystem_base_path(test_config)

    try:
        delivery = _wait_delivery_sent(api_client, message_id, test_config)
        stored_path = _extract_stored_path(delivery)
        filename = _to_filesystem_filename(stored_path, base_path)
        assert filename, f"Could not resolve relative filename from stored path: {stored_path}"

        exists_response = api_client.get(f"/storage/files/filesystem/{filename}/exists")
        assert exists_response.status_code == 200, (
            f"exists API failed: {exists_response.status_code} {exists_response.text[:200]}"
        )
        assert bool((exists_response.json() or {}).get("exists")) is True
    finally:
        api_client.delete(f"/messages/{message_id}")
        api_client.post(f"/channels/{channel_id}/disable")


def test_at129_retrieve_stored_notification_output(api_client, test_config):
    test_id = str(int(time.time()))
    channel_id, channel_name = _create_file_channel(api_client, test_config, test_id)
    body = f"AT1.29 retrieve test {test_id}"
    message_id = _create_file_message(api_client, channel_name, body)
    base_path = _filesystem_base_path(test_config)

    try:
        delivery = _wait_delivery_sent(api_client, message_id, test_config)
        stored_path = _extract_stored_path(delivery)
        filename = _to_filesystem_filename(stored_path, base_path)
        assert filename, f"Could not resolve relative filename from stored path: {stored_path}"

        read_response = api_client.get(f"/storage/files/filesystem/{filename}")
        assert read_response.status_code == 200, (
            f"read API failed: {read_response.status_code} {read_response.text[:200]}"
        )
        content = read_response.content.decode("utf-8", errors="ignore")
        assert content.strip(), "Retrieved content must be non-empty"

        payload_raw = delivery.get("personalised_payload") or ""
        expected_body = ""
        if isinstance(payload_raw, str) and payload_raw:
            try:
                parsed = json.loads(payload_raw)
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    expected_body = str(parsed[0].get("body") or "").strip()
            except Exception:
                expected_body = ""
        if expected_body:
            assert content.strip() == expected_body
    finally:
        api_client.delete(f"/messages/{message_id}")
        api_client.post(f"/channels/{channel_id}/disable")

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
# @pytest.mark.req("FR-018")
