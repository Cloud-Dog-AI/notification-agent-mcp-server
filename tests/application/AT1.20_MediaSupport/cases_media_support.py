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

"""Application Test AT1.20: Multi-Media Support (Images)

RULES.md compliance:
- API-driven only
- No hardcoded configuration values (read from test_config / env)
- Exercises real API endpoints: /channels, /messages, /messages/{id}/deliveries, /storage/{path}
"""

import io
import time

import pytest
from PIL import Image

from media_support_helpers import (
    assert_duplicated_media_accessible,
    create_loopback_channel_for_media,
    data_uri_from_file_bytes,
    disable_channel,
    get_processed_media,
    require_at120_env_loaded,
    wait_for_delivery_with_processed_media,
)


def _wait_for_message_exists(api_client, message_id: str, test_config):
    max_wait = test_config.get("test.at120.max_wait")
    poll_interval = test_config.get("test.at120.poll_interval")
    if not max_wait or not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at120.max_wait and test.at120.poll_interval must be configured")
    max_wait = int(max_wait)
    poll_interval = float(poll_interval)

    start = time.time()
    while time.time() - start < max_wait:
        resp = api_client.get(f"/messages/{message_id}")
        if resp.status_code == 200:
            return
        time.sleep(poll_interval)

    pytest.fail(f"❌ Message did not become available within {max_wait}s: {message_id}")


def test_at120_media_support_image_uuencoded_and_uri(api_client, api_base_url, test_config):
    require_at120_env_loaded(test_config)

    channel_id = None
    message_id = None

    try:
        test_id = str(int(time.time()))
        channel_id, channel_name = create_loopback_channel_for_media(api_client, api_base_url, test_id)

        # Build media inputs without external network dependency
        img = Image.new("RGB", (16, 16), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        png_bytes = buffer.getvalue()
        uuencoded_png = data_uri_from_file_bytes(png_bytes, "image/png")

        local_jpg_path = "tests/assets/images/unsplash_1.jpg"

        message_payload = {
            "audience_type": "direct",
            "destinations": [
                {
                    "channel": channel_name,
                    "address": "loopback",
                }
            ],
            "content": [
                {"type": "text", "body": "AT1.20 media support test"},
                {
                    "type": "image",
                    "body": "uuencoded test image",
                    "uri": uuencoded_png,
                    "alt_text": "uuencoded test image",
                },
                {
                    "type": "image",
                    "body": "local file test image",
                    "uri": local_jpg_path,
                    "alt_text": "local file test image",
                },
            ],
        }

        resp = api_client.post("/messages", json=message_payload)
        assert resp.status_code == 201, f"Failed to create message: {resp.text}"
        message_id = resp.json().get("message_id")
        assert message_id, "No message_id returned"

        # Ensure message exists via API
        _wait_for_message_exists(api_client, message_id, test_config)

        delivery = wait_for_delivery_with_processed_media(
            api_client,
            message_id,
            test_config,
            min_items=2,
            expected_media_types=["image"],
        )
        processed_media = get_processed_media(delivery)

        # Validate that both media references were processed
        assert any(
            m.get("type") == "image" and str(m.get("original_uri") or "").startswith("data:")
            for m in processed_media
        ), "Expected uuencoded (data URI) image to be detected in processed_media"

        assert any(
            m.get("type") == "image" and str(m.get("original_uri") or "") == local_jpg_path
            for m in processed_media
        ), "Expected file-path URI image to be detected in processed_media"

        # Validate duplication happened and stored media is accessible via API
        assert_duplicated_media_accessible(api_client, processed_media)

    finally:
        if message_id:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass
        if channel_id:
            try:
                disable_channel(api_client, channel_id)
            except Exception:
                pass


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class _FakeProcessedMediaClient:
    def __init__(self):
        self.delivery_calls = 0

    def get(self, path: str):
        if path == "/channels/123":
            return _FakeResponse({"type": "loopback"})
        if path != "/messages/42/deliveries":
            return _FakeResponse({}, status_code=404)

        self.delivery_calls += 1
        if self.delivery_calls == 1:
            return _FakeResponse(
                {
                    "items": [
                        {
                            "id": 1,
                            "state": "sending",
                            "channel_id": 123,
                            "metadata_json": {"processed_media": []},
                        }
                    ]
                }
            )

        return _FakeResponse(
            {
                "items": [
                    {
                        "id": 1,
                        "state": "sending",
                        "channel_id": 123,
                        "metadata_json": {
                            "processed_media": [
                                {"type": "image", "original_uri": "data:image/png;base64,abc"},
                                {"type": "image", "original_uri": "tests/assets/images/unsplash_1.jpg"},
                            ]
                        },
                    }
                ]
            }
        )


def test_at120_wait_for_processed_media_does_not_return_on_loopback_sending(test_config):
    """The helper must keep polling loopback sending until processed_media is persisted."""
    require_at120_env_loaded(test_config)

    client = _FakeProcessedMediaClient()
    delivery = wait_for_delivery_with_processed_media(
        client,
        "42",
        test_config,
        min_items=2,
        expected_media_types=["image"],
    )

    assert client.delivery_calls == 2
    assert len(get_processed_media(delivery)) == 2

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
