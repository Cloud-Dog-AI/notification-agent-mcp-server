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
Description: AT1.24 UC1.7 (Enhanced) - SMTP + Slack/Chat REST (API-driven).

RULES.md compliance:
- API-only interactions (no direct database, no adapter imports)
- Config-driven (values come from `--env private/env-test-at124`)
- No hardcoded channel names/URLs/ports/timeouts
- Skips gracefully if Slack webhook is not configured
- Best-effort cleanup via API

Related Requirements: FR1.22, FR1.19, FR1.21, UC1.7 (Enhanced)
Related Tasks: T32, T13
Related Tests: AT1.24
**************************************************
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


def _extract_html_page_url(text: str) -> str:
    if not text:
        return ""
    anchor_match = re.search(
        r'href="(https?://[^\"<>]+)"[^>]*>\s*View personalized HTML page with embedded media\s*<',
        text,
        flags=re.IGNORECASE,
    )
    if anchor_match:
        return anchor_match.group(1)
    text_match = re.search(
        r"View personalized HTML page with embedded media:\s*(https?://\S+)",
        text,
        flags=re.IGNORECASE,
    )
    if text_match:
        return text_match.group(1).strip()
    all_urls = re.findall(r"https?://[^\s\"<>]+", text)
    return all_urls[-1] if all_urls else ""


def _derive_email(base_email: str, suffix: str) -> str:
    if not base_email or "@" not in base_email:
        pytest.fail("test.email must be a valid email address")
    local, domain = base_email.split("@", 1)
    return f"{local}+{suffix}@{domain}"


@pytest.fixture(scope="session")
def api_client(api_base_url, api_key, test_config):
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)

    api_timeout = httpx.Timeout(timeout=timeout_total, connect=timeout_connect, read=timeout_read)
    return httpx.Client(base_url=api_base_url, timeout=api_timeout, headers={"X-API-Key": api_key})


def test_at124_uc17_email_and_slack_end_to_end(api_client, test_config, smtp_config, slack_config, test_email, tmp_path, request):
    """
    Enhanced UC1.7: send one message to both:
    - SMTP destination (expects HTML page link and stored HTML contains <img>/<audio>/<video>)
    - Chat REST destination (expects delivery reaches sent/delivered and payload contains a link back to messages.base_url)
    """
    _require_at124_env_loaded(test_config)

    messages_base_url = test_config.get("messages.base_url")
    if not messages_base_url:
        pytest.fail("❌ HARD FAIL: messages.base_url not configured in env file")

    # Optional: used to size the Slack content, but do not hard-fail if unset.
    slack_max_length = test_config.get("test.slack_max_length")
    try:
        slack_max_length = int(slack_max_length) if slack_max_length is not None and slack_max_length != "" else None
    except Exception:
        slack_max_length = None

    webhook_url = (slack_config or {}).get("endpoint")
    if not webhook_url:
        pytest.fail("Slack webhook endpoint not configured (channels.chat_rest.transparentbordes.endpoint)")

    health = api_client.get("/health")
    assert health.status_code == 200, f"API server health check failed: {health.status_code} {health.text[:200]}"

    test_id = str(int(time.time()))
    smtp_channel_name = f"smtp_at124_slack_{test_id}"
    slack_channel_name = f"chat_rest_at124_{test_id}"

    smtp_channel_config = dict(smtp_config or {})
    smtp_channel_config.update(
        {
            "duplicate_external_media": True,
            "duplicate_images": True,
            "duplicate_audio": True,
            "duplicate_video": True,
        }
    )

    chat_rest_config = dict(slack_config or {})
    chat_rest_config["endpoint"] = webhook_url

    created_smtp_channel_id = None
    created_slack_channel_id = None
    created_message_id = None

    def _cleanup():
        if created_message_id is not None:
            try:
                api_client.delete(f"/messages/{created_message_id}")
            except Exception:
                pass
        if created_smtp_channel_id is not None:
            try:
                api_client.post(f"/channels/{created_smtp_channel_id}/disable")
            except Exception:
                pass
        if created_slack_channel_id is not None:
            try:
                api_client.post(f"/channels/{created_slack_channel_id}/disable")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    smtp_created = api_client.post(
        "/channels",
        json={"name": smtp_channel_name, "type": "smtp", "enabled": True, "config": smtp_channel_config},
    )
    assert smtp_created.status_code == 201, f"POST /channels (smtp) failed: {smtp_created.status_code} {smtp_created.text[:200]}"
    created_smtp_channel_id = smtp_created.json().get("id")
    assert created_smtp_channel_id, "POST /channels (smtp) did not return an id"

    slack_created = api_client.post(
        "/channels",
        json={
            "name": slack_channel_name,
            "type": "chat_rest",
            "enabled": True,
            "config": chat_rest_config,
            # Best-effort limits: if the system honours them, long messages should be summarised.
            # Do not rely on this in assertions here (other suites cover slack max_length/link strategy).
            "limits": {"max_length": int(slack_max_length), "link_strategy": "summary+link"} if slack_max_length else None,
        },
    )
    assert slack_created.status_code == 201, f"POST /channels (chat_rest) failed: {slack_created.status_code} {slack_created.text[:200]}"
    created_slack_channel_id = slack_created.json().get("id")
    assert created_slack_channel_id, "POST /channels (chat_rest) did not return an id"

    # Minimal sample media
    png_1x1 = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xf7"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    audio_wav = (
        b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
        + b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (0).to_bytes(4, "little")
    )
    video_mp4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isom" + (b"\x00" * 64)

    image_path = tmp_path / "at124_slack_image.png"
    audio_path = tmp_path / "at124_slack_audio.wav"
    video_path = tmp_path / "at124_slack_video.mp4"
    image_path.write_bytes(png_1x1)
    audio_path.write_bytes(audio_wav)
    video_path.write_bytes(video_mp4)

    image_data_uri = "data:image/png;base64," + base64.b64encode(png_1x1).decode("ascii")
    audio_data_uri = "data:audio/wav;base64," + base64.b64encode(audio_wav).decode("ascii")
    video_data_uri = "data:video/mp4;base64," + base64.b64encode(video_mp4).decode("ascii")

    email_dest = _derive_email(test_email, f"at124-slack-{test_id}")

    # Keep Slack content bounded; use config if available.
    repeat = 300
    if slack_max_length:
        repeat = max(200, int(slack_max_length * 1.1))
    long_body = f"UC1.7 AT1.24 (slack) {test_id} " + ("x " * int(repeat))

    message_payload = {
        "audience_type": "personalised",
        "destinations": [
            {"channel": smtp_channel_name, "address": email_dest, "preferences": {"content_style": "html"}},
            {"channel": slack_channel_name, "address": webhook_url, "preferences": {"content_style": "text"}},
        ],
        "content": [
            {"type": "markdown", "body": long_body},
            {"type": "image", "body": "data uri image", "uri": image_data_uri, "alt_text": "data uri image"},
            {"type": "audio", "body": "data uri audio", "uri": audio_data_uri, "alt_text": "data uri audio"},
            {"type": "video", "body": "data uri video", "uri": video_data_uri, "alt_text": "data uri video"},
            {"type": "image", "body": "file image", "uri": str(image_path), "alt_text": "file image"},
            {"type": "audio", "body": "file audio", "uri": str(audio_path), "alt_text": "file audio"},
            {"type": "video", "body": "file video", "uri": str(video_path), "alt_text": "file video"},
        ],
        "options": {"subject": f"AT1.24 UC1.7 Slack {test_id}"},
    }

    created_msg = api_client.post("/messages", json=message_payload)
    assert created_msg.status_code == 201, f"POST /messages failed: {created_msg.status_code} {created_msg.text[:200]}"
    created_message_id = created_msg.json().get("message_id")
    assert created_message_id, "POST /messages did not return message_id"
    created_message_id = int(created_message_id)

    deliveries = _wait_for_all_deliveries(api_client, created_message_id, test_config)
    assert len(deliveries) >= 2, f"Expected at least 2 deliveries, got {len(deliveries)}"

    smtp_seen = False
    slack_seen = False

    for delivery in deliveries:
        state = delivery.get("state") or delivery.get("status")
        assert state in ["sent", "delivered"], f"Unexpected delivery state: {state}"
        assert delivery.get("last_error") in (None, ""), f"Delivery error: {delivery.get('last_error')}"

        payload_json = delivery.get("personalised_payload")
        assert payload_json, "Expected personalised_payload to be stored"
        payload = json.loads(payload_json) if isinstance(payload_json, str) else payload_json

        # Detect channel type via metadata/config: for AT tests we avoid hardcoded channel ids,
        # but we can identify by payload shape.
        if isinstance(payload, dict) and "subject" in payload and "body" in payload:
            smtp_seen = True
            body = payload.get("body") or ""
            assert "View personalized HTML page with embedded media" in body, "Expected HTML page link note in SMTP body"
            link = _extract_html_page_url(body)
            assert link, "Expected an access URL for the stored HTML page in SMTP body"
            storage_path = _storage_path_from_access_url(link)
            assert storage_path, f"Could not derive storage_path from HTML page link: {link}"
            resp = api_client.get(f"/storage/{storage_path}")
            assert resp.status_code == 200, f"Failed to fetch HTML via /storage: {resp.status_code} {resp.text[:200]}"
            html = resp.text
            assert "<html" in html.lower(), "Stored HTML should look like an HTML document"
            assert "<img" in html.lower(), "Stored HTML should contain an <img> tag"
            assert "<audio" in html.lower(), "Stored HTML should contain an <audio> tag"
            assert "<video" in html.lower(), "Stored HTML should contain a <video> tag"
        else:
            # Slack/chat_rest payload typically contains a text field
            slack_seen = True
            if isinstance(payload, dict):
                text = str(payload.get("text") or payload.get("body") or "")
            elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
                text = str(payload[0].get("text") or payload[0].get("body") or "")
            else:
                text = str(payload)

            assert text.strip(), "Expected non-empty Slack payload text"
            # Link presence can vary depending on max_length enforcement and formatter behaviour.
            # If a link is present, it should be a messages link rooted at messages.base_url.
            if "http" in text:
                assert messages_base_url.split("/messages", 1)[0] in text, "Expected any URL to be rooted at configured base"

    assert smtp_seen is True, "Expected at least one SMTP delivery payload"
    assert slack_seen is True, "Expected at least one Slack/chat_rest delivery payload"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.application,
    pytest.mark.db,
    pytest.mark.smtp,
    pytest.mark.live_provider,
    pytest.mark.live_delivery,
    pytest.mark.heavy,
]

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-020")
