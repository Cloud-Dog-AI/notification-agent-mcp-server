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
Application Test AT1.21: File Output Channel Test

Tests File Output Channel with all storage backends (filesystem, WebDAV, FTP, S3) 
and all formats (MD, TXT, PDF, HTML) and languages (EN, FR, DE, PL).

Related Requirements: FR1.20
Related Tasks: T31
Related Architecture: CC5.1.5, CC6.1.2, CC6.1.3
Related Tests: AT1.25

Recent Changes (max 10):
- (Initial implementation)
"""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import pytest


def _require_at121_env_loaded(test_config) -> None:
    marker = test_config.get("test.at121_env_loaded")
    if marker not in [True, 1, "true", "True"]:
        pytest.fail(
            "❌ HARD FAIL: AT1.21 env marker not set. "
            "Load tests with: --env private/env-test-at121"
        )


def _parse_json_list(test_config, key: str) -> list:
    raw = test_config.get(key)
    if raw is None or raw == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env file")
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


def _resolve_message_path(message_file: str) -> Path:
    """Resolve message file supporting filename-only, repo-relative, and absolute paths."""
    requested = Path(str(message_file))
    candidates = []

    if requested.is_absolute():
        candidates.append(requested)
    else:
        candidates.append(Path.cwd() / requested)
        candidates.append(Path.cwd() / "tests/Examples" / requested)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _create_file_channel(api_client, test_config, backend_type: str, test_id: str):
    channel_name = f"test_at121_{backend_type}_{test_id}_{int(time.time())}"
    config_key = f"file_channel.{backend_type}"

    if backend_type == "filesystem":
        base_path = test_config.get(f"{config_key}.base_path")
        if not base_path:
            pytest.fail(f"❌ HARD FAIL: {config_key}.base_path not in env file")
        create_subdirs = test_config.get(f"{config_key}.create_subdirs")
        if create_subdirs is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.create_subdirs not in env file")
        subdir_pattern = test_config.get(f"{config_key}.subdir_pattern")
        if not subdir_pattern:
            pytest.fail(f"❌ HARD FAIL: {config_key}.subdir_pattern not in env file")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        if not file_name_pattern:
            pytest.fail(f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file")
        permissions = test_config.get(f"{config_key}.permissions")
        if not permissions:
            pytest.fail(f"❌ HARD FAIL: {config_key}.permissions not in env file")
        dir_permissions = test_config.get(f"{config_key}.dir_permissions")
        if not dir_permissions:
            pytest.fail(f"❌ HARD FAIL: {config_key}.dir_permissions not in env file")

        channel_config = {
            "storage_type": "filesystem",
            "base_path": base_path,
            "create_subdirs": create_subdirs,
            "subdir_pattern": subdir_pattern,
            "file_name_pattern": file_name_pattern,
            "permissions": permissions,
            "dir_permissions": dir_permissions,
        }

    elif backend_type == "webdav":
        url = test_config.get(f"{config_key}.url")
        username = test_config.get(f"{config_key}.username")
        password = test_config.get(f"{config_key}.password")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        if not url:
            pytest.fail(f"❌ HARD FAIL: {config_key}.url not in env file")
        if not username:
            pytest.fail(f"❌ HARD FAIL: {config_key}.username not in env file")
        if not password:
            pytest.fail(f"❌ HARD FAIL: {config_key}.password not in env file")
        if not file_name_pattern:
            pytest.fail(f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file")

        channel_config = {
            "storage_type": "webdav",
            "url": url,
            "username": username,
            "password": password,
            "file_name_pattern": file_name_pattern,
        }

    elif backend_type == "s3":
        endpoint = test_config.get(f"{config_key}.endpoint")
        bucket = test_config.get(f"{config_key}.bucket")
        access_key = test_config.get(f"{config_key}.access_key")
        secret_key = test_config.get(f"{config_key}.secret_key")
        region = test_config.get(f"{config_key}.region")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        if not endpoint:
            pytest.fail(f"❌ HARD FAIL: {config_key}.endpoint not in env file")
        if not bucket:
            pytest.fail(f"❌ HARD FAIL: {config_key}.bucket not in env file")
        if not access_key:
            pytest.fail(f"❌ HARD FAIL: {config_key}.access_key not in env file")
        if not secret_key:
            pytest.fail(f"❌ HARD FAIL: {config_key}.secret_key not in env file")
        if region is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.region not in env file (may be blank, but must be set)")
        if not file_name_pattern:
            pytest.fail(f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file")

        channel_config = {
            "storage_type": "s3",
            "endpoint": endpoint,
            "bucket": bucket,
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region,
            "file_name_pattern": file_name_pattern,
        }

    elif backend_type == "ftp":
        host = test_config.get(f"{config_key}.host")
        port = test_config.get(f"{config_key}.port")
        username = test_config.get(f"{config_key}.username")
        password = test_config.get(f"{config_key}.password")
        passive_mode = test_config.get(f"{config_key}.passive_mode")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        if not host:
            pytest.fail(f"❌ HARD FAIL: {config_key}.host not in env file")
        if port is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.port not in env file")
        if not username:
            pytest.fail(f"❌ HARD FAIL: {config_key}.username not in env file")
        if not password:
            pytest.fail(f"❌ HARD FAIL: {config_key}.password not in env file")
        if passive_mode is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.passive_mode not in env file")
        if not file_name_pattern:
            pytest.fail(f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file")

        channel_config = {
            "storage_type": "ftp",
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "passive_mode": passive_mode,
            "file_name_pattern": file_name_pattern,
        }

    else:
        pytest.fail(f"❌ Unsupported backend_type: {backend_type}")

    response = api_client.post(
        "/channels",
        json={
            "name": channel_name,
            "type": "file",
            "enabled": True,
            "config": channel_config,
        },
    )
    assert response.status_code == 201, f"Failed to create channel: {response.text}"

    channel_id = response.json().get("id")
    assert channel_id, "No channel id returned"

    return channel_id, channel_name, channel_config


def _storage_filename_for_api(backend_type: str, stored_path: str, channel_config: dict, test_config) -> str:
    if not stored_path:
        return ""

    if backend_type == "filesystem":
        base_path = test_config.get("file_channel.filesystem.base_path")
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
            return stored_path[len(base_url) :].lstrip("/")
        parsed = urlparse(stored_path)
        return (parsed.path or "").lstrip("/")

    if backend_type == "s3":
        bucket = channel_config.get("bucket") or ""
        if stored_path.startswith("s3://"):
            without_scheme = stored_path[len("s3://") :]
            if bucket and without_scheme.startswith(f"{bucket}/"):
                return without_scheme[len(bucket) + 1 :]
            return without_scheme.split("/", 1)[-1]
        parsed = urlparse(stored_path)
        path = (parsed.path or "").lstrip("/")
        if bucket and path.startswith(f"{bucket}/"):
            return path[len(bucket) + 1 :]
        return path

    if backend_type == "ftp":
        if stored_path.startswith("ftp://"):
            parsed = urlparse(stored_path)
            return (parsed.path or "").lstrip("/")
        return stored_path.lstrip("/")

    return ""


def _wait_for_delivery(api_client, message_id: str, test_config):
    max_wait = test_config.get("test.at121.max_wait")
    poll_interval = test_config.get("test.at121.poll_interval")
    if not max_wait:
        pytest.fail("❌ HARD FAIL: test.at121.max_wait not configured")
    if not poll_interval:
        pytest.fail("❌ HARD FAIL: test.at121.poll_interval not configured")

    max_wait = int(max_wait)
    poll_interval = float(poll_interval)

    start = time.time()
    last_delivery = None

    while time.time() - start < max_wait:
        resp = api_client.get(f"/messages/{message_id}/deliveries")
        assert resp.status_code == 200, f"Failed to get deliveries: {resp.text}"
        deliveries = (resp.json() or {}).get("items", [])
        if deliveries:
            last_delivery = deliveries[0]
            status = last_delivery.get("state") or last_delivery.get("status")
            if status == "sent":
                return last_delivery
        time.sleep(poll_interval)

    pytest.fail(f"❌ Delivery did not complete within {max_wait}s; last_delivery={last_delivery}")


def _extract_stored_files(delivery_data: dict) -> list:
    metadata = delivery_data.get("metadata_json", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    stored_files = []
    if isinstance(metadata, dict):
        stored_files = metadata.get("stored_files", []) or []

    if not stored_files:
        tracking = delivery_data.get("provider_tracking_id") or delivery_data.get("tracking_id")
        if tracking:
            try:
                stored_files = json.loads(tracking) if isinstance(tracking, str) else tracking
            except Exception:
                stored_files = []

    if not isinstance(stored_files, list):
        stored_files = []

    return stored_files


def _disable_channel(api_client, channel_id: int) -> None:
    resp = api_client.post(f"/channels/{channel_id}/disable")
    assert resp.status_code in [200, 204], f"Failed to disable channel: {resp.text}"


@pytest.mark.parametrize("backend_type", ["filesystem", "webdav", "s3", "ftp"])
def test_at121_file_channel_all_backends(api_client, test_config, backend_type: str):
    """AT1.21 end-to-end file channel test across all storage backends."""

    _require_at121_env_loaded(test_config)

    languages = _parse_json_list(test_config, "test.at121.languages")
    requested_formats = _parse_json_list(test_config, "test.at121.output_formats")

    message_file = test_config.get("test.message_file")
    if not message_file:
        pytest.fail("❌ HARD FAIL: test.message_file not configured")

    content_path = _resolve_message_path(str(message_file))
    if not content_path.exists():
        pytest.fail(f"❌ HARD FAIL: test message file not found: {content_path}")

    source_content = content_path.read_text(encoding="utf-8")

    test_id = f"{backend_type}_{int(time.time())}"
    channel_id = None
    message_ids = []

    try:
        channel_id, channel_name, channel_config = _create_file_channel(
            api_client, test_config, backend_type, test_id
        )

        for lang in languages:
            if not isinstance(lang, str) or not lang:
                pytest.fail("❌ HARD FAIL: test.at121.languages must be a list of strings")

            output_formats = [f for f in requested_formats if f != "pdf"]
            generate_pdf = "pdf" in requested_formats
            expected_files = len(output_formats) + (1 if generate_pdf else 0)

            message_payload = {
                "audience_type": "personalised",
                "destinations": [
                    {
                        "channel": channel_name,
                        "address": "storage",
                        "preferences": {
                            "language": lang,
                            "output_formats": output_formats,
                            "generate_pdf": generate_pdf,
                        },
                    }
                ],
                "content": [
                    {
                        "type": "text",
                        "body": source_content,
                    }
                ],
            }

            resp = api_client.post("/messages", json=message_payload)
            assert resp.status_code == 201, f"Failed to create message: {resp.text}"
            message_id = resp.json().get("message_id")
            assert message_id, "No message_id returned"
            message_ids.append(message_id)

            delivery = _wait_for_delivery(api_client, message_id, test_config)
            stored_files = _extract_stored_files(delivery)
            assert len(stored_files) == expected_files, (
                f"❌ Expected {expected_files} files for backend={backend_type} lang={lang}, "
                f"got {len(stored_files)}"
            )

            filenames = []
            for sf in stored_files:
                stored_path = sf.get("path")
                filename = _storage_filename_for_api(backend_type, stored_path, channel_config, test_config)
                assert filename, f"❌ Could not derive filename for storage API: {stored_path}"
                filenames.append(filename)

                exists_resp = api_client.get(f"/storage/files/{backend_type}/{filename}/exists")
                assert exists_resp.status_code == 200, f"Exists check failed: {exists_resp.text}"
                assert (exists_resp.json() or {}).get("exists") is True, "File should exist"

                read_resp = api_client.get(f"/storage/files/{backend_type}/{filename}")
                assert read_resp.status_code == 200, f"Read failed: {read_resp.text}"
                assert len(read_resp.content or b"") > 0, "Read content should be non-empty"

            # UPDATE at least one non-PDF file
            update_target = None
            for sf, filename in zip(stored_files, filenames):
                if sf.get("format") != "pdf":
                    update_target = filename
                    break

            if update_target:
                new_content = f"AT1.21 update test - backend={backend_type} lang={lang}"
                upd_resp = api_client.put(
                    f"/storage/files/{backend_type}/{update_target}",
                    json={"content": new_content},
                )
                assert upd_resp.status_code == 200, f"Update failed: {upd_resp.text}"

                reread = api_client.get(f"/storage/files/{backend_type}/{update_target}")
                assert reread.status_code == 200, f"Re-read failed: {reread.text}"
                assert new_content.encode("utf-8") in (reread.content or b""), "Updated content not found"

            # DELETE all files
            for filename in filenames:
                del_resp = api_client.delete(f"/storage/files/{backend_type}/{filename}")
                assert del_resp.status_code in [200, 204], f"Delete failed: {del_resp.text}"
                exists_resp = api_client.get(f"/storage/files/{backend_type}/{filename}/exists")
                assert exists_resp.status_code == 200, f"Exists check failed: {exists_resp.text}"
                assert (exists_resp.json() or {}).get("exists") is False, "File should not exist after delete"

    finally:
        for mid in message_ids:
            try:
                api_client.delete(f"/messages/{mid}")
            except Exception:
                pass
        if channel_id:
            try:
                _disable_channel(api_client, channel_id)
            except Exception:
                pass

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
