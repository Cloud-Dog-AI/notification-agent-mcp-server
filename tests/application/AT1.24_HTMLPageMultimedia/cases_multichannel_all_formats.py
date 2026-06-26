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
Description: Application Test AT1.26 - Multi-Channel Multimedia Delivery with All Formats

Scope (UC1.9):
- Multi-channel delivery of same message via Email, Slack, and File channels
- Email: HTML body with images, PDF attachment, HTML page link
- Slack: Text summary with image references, PDF link, HTML page link
- File: All formats (MD, HTML, TXT, PDF) for all configured languages

RULES.md compliance:
- API-only: no direct DB access, no direct filesystem reads
- Config-driven: no hardcoded URLs/ports/keys/timeouts/channel names
- Best-effort cleanup: API delete for messages; disable channels

Related Requirements: FR1.2, FR1.18, FR1.19, FR1.20, FR1.21, FR1.22, UC1.9
Related Architecture: CC5.1, CC5.2, CC5.3, CC6.1.3
Related Tasks: T29, T30, T31, T32
Related Tests: AT1.26

Recent Changes (max 10):
- 2026-01-18: Complete refactor for 100% RULES.md compliance
**************************************************
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import pytest

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)
from tests.utils.test_helpers import check_test_dependencies

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _require_at126_env_loaded(test_config: Any) -> None:
    """AT1.26 suite requires dedicated env file with AT126_ENV_LOADED marker."""
    at126 = test_config.get("test.at126_env_loaded")
    if at126 in [True, 1, "true", "True"]:
        return
    pytest.fail(
        "❌ HARD FAIL: AT1.26 env marker not set.\n"
        "Load tests with: --env private/env-test-at126"
    )


def _require_value(test_config: Any, key: str) -> str:
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env/config")
    return str(v)


def _require_number(test_config: Any, key: str, *, number_type: str):
    """Read required numeric config value."""
    v = test_config.get(key)
    if v is None or v == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env/config")
    try:
        return float(v) if number_type == "float" else int(v)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _get_slack_timeouts(test_config: Any) -> tuple[float, float, float]:
    wait_timeout = (
        test_config.get("test.slack.wait_timeout")
        or test_config.get("test.at126.max_wait")
        or test_config.get("api.timeout")
    )
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("test.at126.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.wait_timeout, test.at126.max_wait, or api.timeout"
        )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.poll_interval, test.at126.poll_interval, api.connect_timeout, or api.timeout"
        )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.slack.request_timeout, api.connect_timeout, or api.timeout"
        )
    return float(wait_timeout), float(poll_interval), float(request_timeout)


def _parse_json_list(test_config: Any, key: str) -> list:
    """Parse JSON list from config."""
    raw = test_config.get(key)
    if raw is None or raw == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured (expected JSON list string)")
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, str):
        pytest.fail(f"❌ HARD FAIL: {key} must be a JSON list string")
    try:
        parsed = json.loads(raw)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: failed to parse {key} as JSON list: {e}")
    if not isinstance(parsed, list):
        pytest.fail(f"❌ HARD FAIL: {key} must parse to a list")
    return parsed


def _parse_json_dict(test_config: Any, key: str) -> Dict[str, Any]:
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


def _load_message_body(test_config: Any) -> str:
    message_file = test_config.get("test.at126.message_file")
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
    return _require_value(test_config, "test.at126.message_body")


def _get_smtp_config(test_config: Any) -> Dict[str, Any]:
    smtp = test_config.get("channels.smtp.default", {})
    required = ["host", "port", "username", "password", "from_address", "timeout"]
    missing = [k for k in required if not smtp.get(k)]
    if missing:
        pytest.fail(
            "SMTP credentials missing: "
            + ", ".join(missing)
            + ". Configure CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__* in env file."
        )
    if smtp.get("enabled") is False:
        pytest.fail("SMTP adapter disabled; set channels.smtp.default.enabled=true")
    return {
        "host": smtp.get("host"),
        "port": smtp.get("port"),
        "username": smtp.get("username"),
        "password": smtp.get("password"),
        "from_address": smtp.get("from_address"),
        "use_tls": smtp.get("use_tls", False),
        "use_starttls": smtp.get("use_starttls", False),
        "timeout": smtp.get("timeout"),
    }


def _require_slack_webhook(test_config: Any) -> str:
    slack = test_config.get("channels.chat_rest.transparentbordes", {})
    endpoint = slack.get("endpoint") if isinstance(slack, dict) else None
    if not endpoint:
        pytest.fail(
            "Slack webhook endpoint not configured. "
            "Set CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__ENDPOINT in env file."
        )
    return endpoint


def _get_slack_channel_config(test_config: Any) -> Dict[str, Any]:
    slack = test_config.get("channels.chat_rest.transparentbordes", {})
    if not isinstance(slack, dict):
        pytest.fail("Slack channel config missing or invalid")
    required = ["endpoint", "auth_type", "format"]
    missing = [k for k in required if not slack.get(k)]
    if missing:
        pytest.fail(
            "Slack channel config missing: "
            + ", ".join(missing)
            + ". Configure CLOUD_DOG__NOTIFY__CHANNELS__CHAT_REST__TRANSPARENTBORDES__* in env file."
        )
    return {
        "endpoint": slack.get("endpoint"),
        "auth_type": slack.get("auth_type"),
        "format": slack.get("format"),
    }

def _wait_for_deliveries(api_client, message_id: int, *, expected_count: int, max_wait: float, poll_interval: float) -> List[Dict[str, Any]]:
    """Wait for all deliveries to reach terminal state."""
    start = time.time()
    last_deliveries = []
    
    while time.time() - start < max_wait:
        r = api_client.get(f"/messages/{message_id}/deliveries")
        assert r.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {r.status_code} {r.text[:200]}"
        items = (r.json() or {}).get("items", [])
        
        if len(items) >= expected_count:
            # Check if all complete
            all_terminal = all(
                (d.get("state") or d.get("status")) in ("sent", "hard_failed", "failed", "cancelled", "canceled")
                for d in items
            )
            if all_terminal:
                return items
            last_deliveries = items
        
        time.sleep(poll_interval)
    
    pytest.fail(
        f"❌ Timed out waiting for {expected_count} deliveries within {max_wait}s; "
        f"got {len(last_deliveries)} deliveries"
    )


def _resolve_smtp_channel_via_api(api_client) -> str:
    """Resolve SMTP channel name via API (no hardcoding)."""
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code}"
    channels = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    smtp_channels = [c for c in channels if c.get("type") == "smtp" and c.get("enabled")]
    if not smtp_channels:
        pytest.fail("❌ No enabled SMTP channel found via GET /channels API")
    return smtp_channels[0]["name"]


def _resolve_slack_channel_via_api(api_client) -> str:
    """Resolve Slack/chat_rest channel name via API (no hardcoding)."""
    r = api_client.get("/channels")
    assert r.status_code == 200, f"GET /channels failed: {r.status_code}"
    channels = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    slack_channels = [c for c in channels if c.get("type") == "chat_rest" and c.get("enabled")]
    if not slack_channels:
        pytest.fail("❌ No enabled Slack/chat_rest channel found via GET /channels API")
    return slack_channels[0]["name"]


def _extract_stored_files(delivery: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract stored_files metadata from delivery."""
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
        tracking = delivery.get("provider_tracking_id") or delivery.get("tracking_id")
        if tracking:
            try:
                stored_files = json.loads(tracking) if isinstance(tracking, str) else tracking
            except Exception:
                stored_files = []
    
    if not isinstance(stored_files, list):
        stored_files = []
    return [sf for sf in stored_files if isinstance(sf, dict)]


def _storage_filename_for_api(backend_type: str, stored_path: str, channel_config: Dict[str, Any], test_config: Any) -> str:
    if not stored_path:
        return ""

    if backend_type == "filesystem":
        base_path = test_config.get("file_channel.filesystem.base_path") or channel_config.get("base_path")
        if not base_path:
            return ""
        try:
            rel = os.path.relpath(stored_path, base_path)
        except Exception:
            return ""
        if rel.startswith(".."):
            return ""
        return rel

    if backend_type == "webdav":
        base_url = (channel_config.get("url") or "").rstrip("/")
        if base_url and stored_path.startswith(base_url):
            return stored_path[len(base_url):].lstrip("/")
        parsed = urlparse(stored_path)
        return (parsed.path or "").lstrip("/")

    if backend_type == "s3":
        bucket = channel_config.get("bucket") or ""
        if stored_path.startswith("s3://"):
            without_scheme = stored_path[len("s3://"):]
            if bucket and without_scheme.startswith(f"{bucket}/"):
                return without_scheme[len(bucket) + 1:]
            return without_scheme.split("/", 1)[-1]
        parsed = urlparse(stored_path)
        path = (parsed.path or "").lstrip("/")
        if bucket and path.startswith(f"{bucket}/"):
            return path[len(bucket) + 1:]
        return path

    if backend_type == "ftp":
        if stored_path.startswith("ftp://"):
            parsed = urlparse(stored_path)
            return (parsed.path or "").lstrip("/")
        return stored_path.lstrip("/")

    return ""


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def _validate_email_delivery(api_client, delivery: Dict[str, Any], test_config: Any) -> None:
    """Validate email delivery via API (personalised_payload)."""
    if not delivery:
        pytest.fail("❌ Email delivery not found in deliveries list")
    
    delivery_id = delivery.get("id")
    state = delivery.get("state") or delivery.get("status")
    assert state == "sent", f"Email delivery not in 'sent' state: {state}"
    
    r = api_client.get(f"/deliveries/{delivery_id}")
    assert r.status_code == 200, f"GET /deliveries/{{id}} failed: {r.status_code}"
    
    payload_str = r.json().get("personalised_payload", "{}")
    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str

    # Check HTML body
    body = ""
    if isinstance(payload, dict):
        body = payload.get("body", "")
    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        body = payload[0].get("body", "")
    assert body, "Email delivery has empty body"
    assert "<html" in body.lower() or "<!doctype" in body.lower() or "<img" in body.lower(), (
        "Expected HTML content in email body"
    )
    
    # Check for image reference
    assert "<img" in body.lower() or "image" in body.lower(), "Expected image reference in email"
    
    # Check for message link (if messages.base_url is configured)
    messages_base_url = test_config.get("messages.base_url")
    if messages_base_url:
        assert "http" in body.lower(), "Expected HTTP link (message view URL) in email body"


def _validate_slack_delivery(api_client, delivery: Dict[str, Any], test_config: Any) -> None:
    """Validate slack delivery via API (personalised_payload)."""
    if not delivery:
        pytest.fail("❌ Slack delivery not found in deliveries list")
    
    delivery_id = delivery.get("id")
    state = delivery.get("state") or delivery.get("status")
    assert state == "sent", f"Slack delivery not in 'sent' state: {state}"
    
    r = api_client.get(f"/deliveries/{delivery_id}")
    assert r.status_code == 200, f"GET /deliveries/{{id}} failed: {r.status_code}"
    
    payload_str = r.json().get("personalised_payload", "{}")
    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    
    # Slack payload typically has 'text' field
    text = payload.get("text", "") if isinstance(payload, dict) else str(payload)
    assert text, "Slack delivery has empty text"
    
    # Check for links (message view URL or PDF link)
    messages_base_url = test_config.get("messages.base_url")
    if messages_base_url:
        assert "http" in text.lower(), "Expected HTTP link in Slack text"


def _validate_file_deliveries(
    api_client,
    deliveries: List[Dict[str, Any]],
    output_formats: List[str],
    output_languages: List[str],
    channel_config: Dict[str, Any],
    test_config: Any,
) -> None:
    """Validate file deliveries via stored_files metadata (formats + languages)."""
    if not deliveries:
        pytest.fail("❌ File delivery not found in deliveries list")

    expected_formats_set = set(output_formats)
    expected_languages_set = set(output_languages)
    pairs_found = set()
    backend_type = str(channel_config.get("storage_type") or "filesystem")

    for delivery in deliveries:
        state = delivery.get("state") or delivery.get("status")
        assert state == "sent", f"File delivery not in 'sent' state: {state}"

        stored_files = _extract_stored_files(delivery)
        assert stored_files, "File delivery has no stored_files metadata"

        for sf in stored_files:
            fmt = sf.get("format") or sf.get("file_format")
            lang = sf.get("lang") or sf.get("language")
            if not lang:
                metadata = sf.get("metadata")
                if isinstance(metadata, dict):
                    lang = metadata.get("language")
            path = sf.get("path") or sf.get("storage_path")
            size_bytes = sf.get("size_bytes", 0)

            assert fmt, f"stored_file missing format: {sf}"
            assert path, f"stored_file missing path: {sf}"
            assert size_bytes > 0, f"stored_file has zero size: {sf}"

            if lang:
                pairs_found.add((str(lang), str(fmt)))

            filename = _storage_filename_for_api(backend_type, str(path), channel_config, test_config)
            assert filename, f"Could not derive storage API filename from path: {path}"
            stored = api_client.get(f"/storage/files/{backend_type}/{filename}")
            assert stored.status_code == 200, (
                f"GET /storage/files/{backend_type}/{{filename}} failed: "
                f"{stored.status_code} {stored.text[:200]}"
            )
            assert stored.content, "Stored file content should be non-empty"

    missing_pairs = [
        (lang, fmt)
        for lang in expected_languages_set
        for fmt in expected_formats_set
        if (lang, fmt) not in pairs_found
    ]
    assert not missing_pairs, f"Missing stored files for language/format pairs: {missing_pairs}"


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config):
    """Create httpx client for API access."""
    timeout_total = test_config.get("api.timeout", 900)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 900)
    api_timeout = httpx.Timeout(timeout=timeout_total, connect=timeout_connect, read=timeout_read)
    with httpx.Client(
        base_url=api_base_url,
        timeout=api_timeout,
        headers={"X-API-Key": api_key},
    ) as client:
        yield client


# ============================================================================
# MAIN TEST
# ============================================================================

def test_at126_multichannel_multimedia_delivery(api_client, test_config, request):
    """
    UC1.9: Multi-channel multimedia delivery
    
    Creates ONE message with THREE primary channel destinations:
    1. Email (SMTP): HTML body, PDF attachment, HTML page link
    2. Slack (chat_rest): Text summary with links (webhook)
    3. File (filesystem): All formats (MD/HTML/TXT/PDF) × configured languages
    
    Validates each delivery via API-only methods (no filesystem/database access).
    """
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=True,
        requires_slack=True,
        requires_api=True,
        test_name="test_at126_multichannel_multimedia_delivery",
    )
    _require_at126_env_loaded(test_config)

    smtp_config = _get_smtp_config(test_config)
    slack_endpoint = _require_slack_webhook(test_config)
    slack_token, slack_workspace_channel_id = require_slack_api_config(test_config)

    # Load config parameters
    max_wait = _require_number(test_config, "test.at126.max_wait", number_type="int")
    poll_interval = _require_number(test_config, "test.at126.poll_interval", number_type="float")
    expected_deliveries = _require_number(test_config, "test.at126.expected_deliveries", number_type="int")
    output_formats = _parse_json_list(test_config, "test.at126.output_formats")
    output_languages = _parse_json_list(test_config, "test.at126.languages")
    if not output_languages:
        pytest.fail("❌ HARD FAIL: test.at126.languages must include at least one language")
    computed_expected = 2 + len(output_languages)
    if int(expected_deliveries) != computed_expected:
        pytest.fail(
            f"❌ HARD FAIL: test.at126.expected_deliveries must equal 2 + len(languages) "
            f"({computed_expected}), got {expected_deliveries}"
        )
    smtp_timeout_update = _require_number(test_config, "test.at126.smtp_timeout_update", number_type="int")
    subject_prefix = _require_value(test_config, "test.at126.subject_prefix")
    slack_marker_prefix = _require_value(test_config, "test.at126.slack_marker_prefix")
    message_body = _load_message_body(test_config)
    image_data_uri = _require_value(test_config, "test.at126.image_data_uri")
    video_url = _require_value(test_config, "test.at126.video_url")
    messages_base_url = _require_value(test_config, "messages.base_url")
    slack_max_length = _require_number(test_config, "test.at126.slack_max_length", number_type="int")
    test_email = _require_value(test_config, "test.email")
    file_destination_address = _require_value(test_config, "test.at126.file_destination_address")

    email_preferences = _parse_json_dict(test_config, "test.at126.email_preferences_json")
    slack_preferences = _parse_json_dict(test_config, "test.at126.slack_preferences_json")
    file_preferences = _parse_json_dict(test_config, "test.at126.file_preferences_json")
    file_output_formats = file_preferences.get("output_formats")
    if not file_output_formats:
        pytest.fail("❌ HARD FAIL: test.at126.file_preferences_json must include output_formats")
    if set(file_output_formats) != set(output_formats):
        pytest.fail("❌ HARD FAIL: file_preferences.output_formats must match test.at126.output_formats")
    generate_pdf = file_preferences.get("generate_pdf")
    if generate_pdf is None:
        pytest.fail("❌ HARD FAIL: test.at126.file_preferences_json must include generate_pdf")
    if bool(generate_pdf) != ("pdf" in output_formats):
        pytest.fail("❌ HARD FAIL: file_preferences.generate_pdf must align with test.at126.output_formats")

    slack_channel_config = _get_slack_channel_config(test_config)

    # Test data
    test_id = str(int(time.time()))
    slack_marker = f"{slack_marker_prefix} {test_id}"
    slack_channel_name = f"slack_at126_{test_id}"
    smtp_channel_name = f"smtp_at126_{test_id}"
    file_channel_name = f"file_at126_{test_id}"
    slack_channel_db_id: Optional[int] = None
    smtp_channel_id: Optional[int] = None
    file_channel_id: Optional[int] = None
    message_ids: List[int] = []
    
    # Cleanup finalizer
    def _cleanup():
        for mid in message_ids:
            try:
                api_client.delete(f"/messages/{mid}")
            except Exception:
                pass
        if slack_channel_db_id:
            try:
                api_client.post(f"/channels/{slack_channel_db_id}/disable")
            except Exception:
                pass
        if smtp_channel_id:
            try:
                api_client.post(f"/channels/{smtp_channel_id}/disable")
            except Exception:
                pass
        if file_channel_id:
            try:
                api_client.post(f"/channels/{file_channel_id}/disable")
            except Exception:
                pass
    
    request.addfinalizer(_cleanup)
    
    # Get base path for file channel
    base_path = test_config.get("file_channel.filesystem.base_path")
    if not base_path:
        pytest.fail(
            "❌ HARD FAIL: file_channel.filesystem.base_path not configured.\n"
            "Set CLOUD_DOG__NOTIFY__FILE_CHANNEL__FILESYSTEM__BASE_PATH in env file"
        )

    # Create SMTP channel via API using config-driven settings
    smtp_payload = {
        "name": smtp_channel_name,
        "type": "smtp",
        "enabled": True,
        "config": smtp_config,
    }
    smtp_resp = api_client.post("/channels", json=smtp_payload)
    assert smtp_resp.status_code == 201, f"POST /channels failed: {smtp_resp.status_code} {smtp_resp.text[:200]}"
    smtp_channel_id = smtp_resp.json().get("id")
    assert smtp_channel_id, "POST /channels did not return id"
    smtp_channel = smtp_channel_name

    # Create Slack channel via API using config-driven settings
    slack_payload = {
        "name": slack_channel_name,
        "type": "chat_rest",
        "enabled": True,
        "config": slack_channel_config,
    }
    slack_resp = api_client.post("/channels", json=slack_payload)
    assert slack_resp.status_code == 201, f"POST /channels failed: {slack_resp.status_code} {slack_resp.text[:200]}"
    slack_channel_db_id = slack_resp.json().get("id")
    assert slack_channel_db_id, "POST /channels did not return id"
    slack_channel = slack_channel_name

    slack_restrictions = {"max_length": slack_max_length, "allowed_formats": ["text"], "link_strategy": "summary+link"}
    slack_update = api_client.patch(
        f"/channels/{slack_channel_db_id}",
        json={"restrictions_json": slack_restrictions},
    )
    assert slack_update.status_code == 200, f"PATCH /channels failed: {slack_update.status_code}"

    file_storage_type = _require_value(test_config, "test.at126.file_storage_type")
    file_name_pattern = _require_value(test_config, "test.at126.file_name_pattern")
    file_name_pattern_update = _require_value(test_config, "test.at126.file_name_pattern_update")

    # Create file channel via API
    file_channel_config = {
        "storage_type": file_storage_type,
        "base_path": base_path,
        "file_name_pattern": file_name_pattern,
    }
    ch = api_client.post("/channels", json={
        "name": file_channel_name,
        "type": "file",
        "enabled": True,
        "config": file_channel_config,
    })
    assert ch.status_code == 201, f"POST /channels failed: {ch.status_code} {ch.text[:200]}"
    file_channel_id = ch.json().get("id")
    assert file_channel_id, "POST /channels did not return id"

    updated_config = dict(file_channel_config)
    updated_config["file_name_pattern"] = file_name_pattern_update
    update_resp = api_client.patch(
        f"/channels/{file_channel_id}",
        json={"config_json": updated_config},
    )
    assert update_resp.status_code == 200, f"PATCH /channels failed: {update_resp.status_code} {update_resp.text[:200]}"

    channel_read = api_client.get(f"/channels/{file_channel_id}")
    assert channel_read.status_code == 200, f"GET /channels/{{id}} failed: {channel_read.status_code}"
    channel_config_read = (channel_read.json() or {}).get("config") or {}
    assert channel_config_read.get("file_name_pattern") == file_name_pattern_update

    markdown_body = (
        f"{message_body}\n\n"
        f'<img src="{image_data_uri}" alt="AT1.26 image">\n\n'
        f"<video controls src=\"{video_url}\"></video>\n\n"
        f"Link: {messages_base_url}\n\n"
        f"{slack_marker}\n"
    )

    file_destinations = []
    for lang in output_languages:
        if not isinstance(lang, str) or not lang:
            pytest.fail("❌ HARD FAIL: test.at126.languages must be a list of non-empty strings")
        prefs = dict(file_preferences)
        prefs["language"] = lang
        file_destinations.append(
            {
                "channel": file_channel_name,
                "address": file_destination_address,
                "preferences": prefs,
            }
        )

    # Create message with destinations via API (Email + Slack + File per language)
    msg = api_client.post("/messages", json={
        "audience_type": "personalised",
        "destinations": [
            {
                "channel": smtp_channel,
                "address": test_email,
                "preferences": email_preferences,
            },
            {
                "channel": slack_channel,
                "address": slack_endpoint,
                "preferences": slack_preferences,
            },
        ] + file_destinations,
        "content": [{"type": "markdown", "body": markdown_body}],
        "options": {"subject": f"{subject_prefix} {test_id} - {slack_marker}"}
    })
    assert msg.status_code == 201, f"POST /messages failed: {msg.status_code} {msg.text[:200]}"
    message_id = msg.json().get("message_id")
    assert message_id, "POST /messages did not return message_id"
    message_ids.append(message_id)
    
    # Wait for all deliveries to complete
    deliveries = _wait_for_deliveries(
        api_client, message_id,
        expected_count=expected_deliveries,
        max_wait=max_wait,
        poll_interval=poll_interval
    )
    
    # Separate deliveries by channel type (via API channel lookup)
    email_delivery = None
    slack_delivery = None
    file_deliveries: List[Dict[str, Any]] = []
    
    for d in deliveries:
        channel_id = d.get("channel_id")
        # Resolve channel type via API
        ch_resp = api_client.get(f"/channels/{channel_id}")
        if ch_resp.status_code == 200:
            ch_type = ch_resp.json().get("type")
            if ch_type == "smtp":
                email_delivery = d
            elif ch_type == "chat_rest":
                slack_delivery = d
            elif ch_type == "file":
                file_deliveries.append(d)
    
    # VALIDATION 1: Email Delivery (API-only)
    _validate_email_delivery(api_client, email_delivery, test_config)
    
    # VALIDATION 2: Slack Delivery (API-only)
    _validate_slack_delivery(api_client, slack_delivery, test_config)
    wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)
    slack_message = wait_for_slack_message(
        slack_token,
        slack_workspace_channel_id,
        slack_marker,
        timeout=wait_timeout,
        poll_interval=poll_interval,
        request_timeout=request_timeout,
    )
    assert_slack_mrkdwn_contains(slack_message, slack_marker)

    # VALIDATION 3: File Delivery (API-only via metadata)
    _validate_file_deliveries(
        api_client,
        file_deliveries,
        output_formats,
        output_languages,
        file_channel_config,
        test_config,
    )

    # CRUD validation: update SMTP channel config after deliveries complete
    updated_smtp_config = dict(smtp_config)
    updated_smtp_config["timeout"] = smtp_timeout_update
    smtp_update = api_client.patch(
        f"/channels/{smtp_channel_id}",
        json={"config_json": updated_smtp_config},
    )
    assert smtp_update.status_code == 200, f"PATCH /channels failed: {smtp_update.status_code}"
    smtp_read = api_client.get(f"/channels/{smtp_channel_id}")
    assert smtp_read.status_code == 200, f"GET /channels/{{id}} failed: {smtp_read.status_code}"
    smtp_config_read = (smtp_read.json() or {}).get("config") or {}
    assert smtp_config_read.get("timeout") == smtp_timeout_update

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.application,
    pytest.mark.db,
    pytest.mark.smtp,
    pytest.mark.llm,
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
