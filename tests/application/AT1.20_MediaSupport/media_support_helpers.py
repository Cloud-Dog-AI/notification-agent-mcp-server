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

import base64
import json
import time
from pathlib import Path

import pytest


def require_at120_env_loaded(test_config) -> None:
    marker = test_config.get("test.at120_env_loaded")
    if marker not in [True, 1, "true", "True"]:
        pytest.fail(
            "❌ HARD FAIL: AT1.20 env marker not set. "
            "Load tests with: --env private/env-test-at120"
        )


def wait_for_delivery(
    api_client,
    message_id: str,
    test_config,
    *,
    require_processed_media: bool = False,
    min_processed_media: int = 1,
    expected_media_types: list[str] | None = None,
) -> dict:
    max_wait = test_config.get("test.at120.max_wait")
    poll_interval = test_config.get("test.at120.poll_interval")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at120.max_wait not configured")
    if not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at120.poll_interval not configured")

    max_wait = int(max_wait)
    poll_interval = float(poll_interval)

    start = time.time()
    last_delivery = None
    loopback_ok = None
    last_processed_media = []

    def processed_media_ready(delivery: dict) -> bool:
        nonlocal last_processed_media
        if not require_processed_media:
            return True

        processed = get_processed_media(delivery)
        last_processed_media = processed
        if len(processed) < min_processed_media:
            return False

        if expected_media_types:
            seen_types = {item.get("type") for item in processed if isinstance(item, dict)}
            return all(media_type in seen_types for media_type in expected_media_types)

        return True

    while time.time() - start < max_wait:
        resp = api_client.get(f"/messages/{message_id}/deliveries")
        assert resp.status_code == 200, f"Failed to get deliveries: {resp.text}"
        deliveries = (resp.json() or {}).get("items", [])
        if deliveries:
            last_delivery = deliveries[0]
            status = last_delivery.get("state") or last_delivery.get("status")
            if status in ("sent", "delivered"):
                if processed_media_ready(last_delivery):
                    return last_delivery
            if status == "sending":
                if loopback_ok is None:
                    channel_id = last_delivery.get("channel_id")
                    if channel_id:
                        ch = api_client.get(f"/channels/{channel_id}")
                        if ch.status_code == 200:
                            loopback_ok = str(ch.json().get("type", "")).lower() == "loopback"
                        else:
                            loopback_ok = False
                    else:
                        loopback_ok = False
                if loopback_ok:
                    if processed_media_ready(last_delivery):
                        return last_delivery
        time.sleep(poll_interval)

    if require_processed_media:
        pytest.fail(
            "❌ Delivery did not expose required processed_media within "
            f"{max_wait}s; min_processed_media={min_processed_media}; "
            f"expected_media_types={expected_media_types}; "
            f"last_processed_media={last_processed_media}; last_delivery={last_delivery}"
        )
    pytest.fail(f"❌ Delivery did not complete within {max_wait}s; last_delivery={last_delivery}")


def wait_for_delivery_with_processed_media(
    api_client,
    message_id: str,
    test_config,
    *,
    min_items: int,
    expected_media_types: list[str] | None = None,
) -> dict:
    return wait_for_delivery(
        api_client,
        message_id,
        test_config,
        require_processed_media=True,
        min_processed_media=min_items,
        expected_media_types=expected_media_types,
    )


def extract_metadata(delivery: dict) -> dict:
    metadata = delivery.get("metadata_json")
    if not metadata:
        return {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def get_processed_media(delivery: dict) -> list:
    metadata = extract_metadata(delivery)
    processed = metadata.get("processed_media") if isinstance(metadata, dict) else None
    return processed if isinstance(processed, list) else []


def read_asset_bytes(relative_path: str) -> bytes:
    p = Path(relative_path)
    if not p.exists():
        pytest.fail(f"❌ HARD FAIL: asset not found: {p}")
    return p.read_bytes()


def data_uri_from_file_bytes(image_bytes: bytes, mime: str) -> str:
    if not image_bytes:
        pytest.fail("❌ HARD FAIL: empty image bytes")
    if not mime or "/" not in mime:
        pytest.fail("❌ HARD FAIL: invalid mime type")
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def create_loopback_channel_for_media(api_client, api_base_url: str, test_id: str):
    """Create a loopback channel configured to request media duplication."""
    channel_name = f"loopback_media_{test_id}_{int(time.time())}"

    channel_config = {
        "name": channel_name,
        "type": "loopback",
        "enabled": True,
        "config": {
            "base_url": f"{api_base_url}/messages",
            "message_path_template": "/messages/{message_guid}",
            "duplicate_external_media": True,
            "duplicate_images": True,
        },
    }

    resp = api_client.post("/channels", json=channel_config)
    assert resp.status_code == 201, f"Failed to create loopback channel: {resp.text}"

    channel_id = resp.json().get("id")
    assert channel_id, "No channel id returned"

    return channel_id, channel_name


def disable_channel(api_client, channel_id: int) -> None:
    resp = api_client.post(f"/channels/{channel_id}/disable")
    assert resp.status_code in [200, 204], f"Failed to disable channel: {resp.text}"


def assert_duplicated_media_accessible(api_client, processed_media: list) -> None:
    assert processed_media, "processed_media should not be empty"

    local_items = [m for m in processed_media if m.get("type") == "image" and m.get("is_local") is True]
    assert local_items, "Expected at least one duplicated local image (is_local=True)"

    for item in local_items:
        storage_info = item.get("storage_info")
        assert isinstance(storage_info, dict), "storage_info missing for duplicated media"
        storage_path = storage_info.get("storage_path")
        assert storage_path, "storage_info.storage_path missing"

        resp = api_client.get(f"/storage/{storage_path}")
        assert resp.status_code == 200, f"Failed to fetch stored media via /storage: {resp.text}"
        assert len(resp.content or b"") > 0, "Stored media content should be non-empty"
