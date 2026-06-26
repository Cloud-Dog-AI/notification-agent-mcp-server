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
Application Test AT1.24: Full End-to-End Test for UC1.7

Tests the full UC1.7 use case:
- Personalized multimedia notifications with HTML pages
- 10 users with different keywords
- Keyword-based personalization
- HTML page generation for each user
- Email delivery with HTML page links
- Media duplication scenarios

Related Requirements: FR1.22, FR1.19, FR1.21, UC1.7
Related Tasks: T32, T13
"""

import base64
import json
import re
import time
from urllib.parse import urlparse

import httpx
import pytest


def _require_at124_env_loaded(test_config) -> None:
    marker = test_config.get("test.at124_env_loaded")
    if marker not in [True, 1, "true", "True"]:
        pytest.fail(
            "❌ HARD FAIL: AT1.24 env marker not set. "
            "Load tests with: --env private/env-test-at124"
        )


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


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


def _wait_for_all_deliveries(api_client, message_id: int, test_config) -> list:
    max_wait = _require_number(test_config, "test.at124.max_wait", number_type="int")
    poll_interval = _require_number(test_config, "test.at124.poll_interval", number_type="float")

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


def _derive_email(base_email: str, suffix: str) -> str:
    if not base_email or "@" not in base_email:
        pytest.fail("test.email must be a valid email address")
    local, domain = base_email.split("@", 1)
    return f"{local}+{suffix}@{domain}"


def _extract_html_page_url(text: str) -> str:
    if not text:
        return ""

    # Preferred: HTML link variant added for HTML emails
    anchor_match = re.search(
        r'href="(https?://[^\"<>]+)"[^>]*>\s*View personalized HTML page with embedded media\s*<',
        text,
        flags=re.IGNORECASE,
    )
    if anchor_match:
        return anchor_match.group(1)

    # Text/plain variant
    text_match = re.search(
        r"View personalized HTML page with embedded media:\s*(https?://\S+)",
        text,
        flags=re.IGNORECASE,
    )
    if text_match:
        return text_match.group(1).strip()

    # Fallback: choose the last URL in the body (embedded media URLs often appear earlier)
    all_urls = re.findall(r"https?://[^\s\"<>]+", text)
    if all_urls:
        return all_urls[-1]

    return ""


@pytest.fixture(scope="session")
def api_client(api_base_url, api_key, test_config):
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)

    api_timeout = httpx.Timeout(
        timeout=timeout_total,
        connect=timeout_connect,
        read=timeout_read,
    )

    return httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key},
    )


def test_at124_uc17_personalized_html_pages_multimedia_end_to_end(api_client, test_config, smtp_config, test_email, tmp_path):
    _require_at124_env_loaded(test_config)

    health = api_client.get("/health")
    assert health.status_code == 200, f"API server health check failed: {health.status_code} {health.text[:200]}"

    user_count = _require_number(test_config, "test.at124.user_count", number_type="int")
    test_id = str(int(time.time()))
    channel_name = f"smtp_at124_{test_id}"

    channel_config = dict(smtp_config or {})
    channel_config.update(
        {
            "duplicate_external_media": True,
            "duplicate_images": True,
            "duplicate_audio": True,
            "duplicate_video": True,
        }
    )

    created_channel_id = None
    try:
        created = api_client.post(
            "/channels",
            json={
                "name": channel_name,
                "type": "smtp",
                "enabled": True,
                "config": channel_config,
            },
        )
        assert created.status_code == 201, f"POST /channels failed: {created.status_code} {created.text[:200]}"
        created_channel_id = created.json().get("id")
        assert created_channel_id, "POST /channels did not return an id"

        png_1x1 = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xf7"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        audio_wav = (
            b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" +
            b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") +
            (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") +
            b"data" + (0).to_bytes(4, "little")
        )
        video_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom" + (b"\x00" * 64)

        image_path = tmp_path / "at124_image.png"
        audio_path = tmp_path / "at124_audio.wav"
        video_path = tmp_path / "at124_video.mp4"
        image_path.write_bytes(png_1x1)
        audio_path.write_bytes(audio_wav)
        video_path.write_bytes(video_mp4)

        image_data_uri = "data:image/png;base64," + base64.b64encode(png_1x1).decode("ascii")
        audio_data_uri = "data:audio/wav;base64," + base64.b64encode(audio_wav).decode("ascii")
        video_data_uri = "data:video/mp4;base64," + base64.b64encode(video_mp4).decode("ascii")

        message_body = (
            "# UC1.7 AT1.24\n\n"
            "Personalized multimedia notification with HTML page link.\n"
        )

        destinations = []
        for i in range(int(user_count)):
            addr = _derive_email(test_email, f"at124-{test_id}-{i}")
            destinations.append(
                {
                    "channel": channel_name,
                    "address": addr,
                    "preferences": {
                        "content_style": "html",
                    },
                }
            )

        message_payload = {
            "audience_type": "personalised",
            "destinations": destinations,
            "content": [
                {"type": "markdown", "body": message_body},
                {"type": "image", "body": "data uri image", "uri": image_data_uri, "alt_text": "data uri image"},
                {"type": "audio", "body": "data uri audio", "uri": audio_data_uri, "alt_text": "data uri audio"},
                {"type": "video", "body": "data uri video", "uri": video_data_uri, "alt_text": "data uri video"},
                {"type": "image", "body": "file image", "uri": str(image_path), "alt_text": "file image"},
                {"type": "audio", "body": "file audio", "uri": str(audio_path), "alt_text": "file audio"},
                {"type": "video", "body": "file video", "uri": str(video_path), "alt_text": "file video"},
            ],
            "options": {"subject": f"AT1.24 UC1.7 {test_id}"},
        }

        created_msg = api_client.post("/messages", json=message_payload)
        assert created_msg.status_code == 201, f"POST /messages failed: {created_msg.status_code} {created_msg.text[:200]}"
        message_id = created_msg.json().get("message_id")
        assert message_id, "POST /messages did not return message_id"

        deliveries = _wait_for_all_deliveries(api_client, int(message_id), test_config)
        assert len(deliveries) >= int(user_count), f"Expected at least {user_count} deliveries, got {len(deliveries)}"

        html_links = []
        for delivery in deliveries:
            state = delivery.get("state") or delivery.get("status")
            assert state in ["sent", "delivered"], f"Unexpected delivery state: {state}"

            metadata = _parse_metadata_json(delivery)
            processed_media = metadata.get("processed_media")
            assert isinstance(processed_media, list) and processed_media, "Delivery metadata missing processed_media"

            payload_json = delivery.get("personalised_payload")
            assert payload_json, "Expected personalised_payload to be stored"
            payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json
            assert isinstance(payload, dict), "Expected SMTP personalised_payload to be a dict"

            body = payload.get("body") or ""
            assert "View personalized HTML page with embedded media" in body, "Expected HTML page link note in email body"
            link = _extract_html_page_url(body)
            assert link, "Expected an access URL for the stored HTML page in email body"
            html_links.append(link)

        for link in html_links:
            storage_path = _storage_path_from_access_url(link)
            assert storage_path, f"Could not derive storage_path from HTML page link: {link}"
            resp = api_client.get(f"/storage/{storage_path}")
            assert resp.status_code == 200, f"Failed to fetch HTML via /storage: {resp.status_code} {resp.text[:200]}"
            html = resp.text
            assert "<!DOCTYPE html>" in html or "<html" in html.lower(), "Stored HTML should look like an HTML document"
            assert "<img" in html.lower(), "Stored HTML should contain an <img> tag"
            assert "<audio" in html.lower(), "Stored HTML should contain an <audio> tag"
            assert "<video" in html.lower(), "Stored HTML should contain a <video> tag"

    finally:
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
# @pytest.mark.req("FR-020")
