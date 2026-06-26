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
AT1.4g: File Storage Tests - COMPLETE CRUD LIFECYCLE
Tests file channel integration with ALL storage backends (filesystem, WebDAV, S3, FTP).

Each test includes COMPLETE CRUD lifecycle:
1. CREATE: Create file channel via API
2. CREATE: Send message and save files to storage
3. READ: Verify file storage and content
4. READ: Retrieve and validate file content
5. UPDATE: Modify file content and verify
6. DELETE: Delete file from storage
7. READ: Verify file no longer exists
8. DELETE: Remove/cleanup file channel

Test Coverage:
- 40 parametrized test cases (10 per backend × 4 backends)
- Backends: filesystem, webdav, s3, ftp
- Languages: EN, FR, DE, PL, ZH, AR
- Formats: MD, TXT, PDF
- Validation: 10 layers (full CRUD + cleanup)

Requirements:
- --env private/env-test MUST be specified (HARD FAIL if not)
- 100% API-driven (channel creation, message send, file CRUD, cleanup)
- NO hardcoding (credentials from env file)
- All core functionality from src/
- Tests are glue code only
"""

import pytest
import os
import re
import time
import json
from pathlib import Path
import pdfplumber
import tempfile
from urllib.parse import urlparse

# Import validation helpers
from helpers import (
    validate_pdf,
    validate_language
)


# Test cases for AT1.4g - 10 scenarios × 4 backends = 40 tests
TEST_SCENARIOS = [
    {
        "id": "scenario_0",
        "description": "EN MD+PDF (no translation)",
        "source_lang": "en",
        "target_lang": "en",
        "size": 2000,
        "formats": ["md"],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 2,  # MD + PDF
        "expected_translations": False
    },
    {
        "id": "scenario_1",
        "description": "EN TXT+PDF (no translation)",
        "source_lang": "en",
        "target_lang": "en",
        "size": 2000,
        "formats": ["txt"],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 2,  # TXT + PDF
        "expected_translations": False
    },
    {
        "id": "scenario_2",
        "description": "EN PDF only (no translation)",
        "source_lang": "en",
        "target_lang": "en",
        "size": 2000,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 1,  # PDF only
        "expected_translations": False
    },
    {
        "id": "scenario_3",
        "description": "EN→FR MD+PDF with summary",
        "source_lang": "en",
        "target_lang": "fr",
        "size": 2000,
        "formats": ["md"],
        "generate_pdf": True,
        "generate_summary": True,
        "expected_files": 2,  # MD + PDF
        "expected_translations": True
    },
    {
        "id": "scenario_4",
        "description": "EN→AR RTL PDF",
        "source_lang": "en",
        "target_lang": "ar",
        "size": 2000,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 1,  # PDF only
        "expected_translations": True,
        "expect_rtl": True
    },
    {
        "id": "scenario_5",
        "description": "EN→ZH CJK PDF",
        "source_lang": "en",
        "target_lang": "zh",
        "size": 2000,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 1,  # PDF only
        "expected_translations": True,
        "expect_cjk": True
    },
    {
        "id": "scenario_6",
        "description": "PL→DE MD+TXT+PDF with summary",
        "source_lang": "pl",
        "target_lang": "de",
        "size": 2000,
        "formats": ["md", "txt"],
        "generate_pdf": True,
        "generate_summary": True,
        "expected_files": 3,  # MD + TXT + PDF
        "expected_translations": True
    },
    {
        "id": "scenario_7",
        "description": "EN→FR small PDF",
        "source_lang": "en",
        "target_lang": "fr",
        "size": 400,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 1,  # PDF only
        "expected_translations": True
    },
    {
        "id": "scenario_8",
        "description": "ZH→EN PDF",
        "source_lang": "zh",
        "target_lang": "en",
        "size": 2000,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": False,
        "expected_files": 1,  # PDF only
        "expected_translations": True
    },
    {
        "id": "scenario_9",
        "description": "EN→DE large PDF with summary",
        "source_lang": "en",
        "target_lang": "de",
        "size": 5000,
        "formats": [],
        "generate_pdf": True,
        "generate_summary": True,
        "expected_files": 1,  # PDF only
        "expected_translations": True
    },
]

# Storage backends configuration
STORAGE_BACKENDS = [
    {
        "id": "filesystem",
        "name": "Local Filesystem",
        "type": "filesystem",
        "config_key": "file_channel.filesystem"
    },
    {
        "id": "webdav",
        "name": "WebDAV",
        "type": "webdav",
        "config_key": "file_channel.webdav"
    },
    {
        "id": "s3",
        "name": "S3 Storage",
        "type": "s3",
        "config_key": "file_channel.s3"
    },
    {
        "id": "ftp",
        "name": "FTP Storage",
        "type": "ftp",
        "config_key": "file_channel.ftp"
    }
]

# Generate all test cases (10 scenarios × 4 backends = 40 tests)
TEST_CASES = []
for backend in STORAGE_BACKENDS:
    for scenario in TEST_SCENARIOS:
        test_case = {
            **scenario,
            "backend_id": backend["id"],
            "backend_name": backend["name"],
            "backend_type": backend["type"],
            "backend_config_key": backend["config_key"],
            "test_id": f"{backend['id']}_{scenario['id']}"
        }
        TEST_CASES.append(test_case)


def create_file_channel(api_client, test_config, backend_type, test_id):
    """
    Create a file channel via API for the specified backend.
    Uses credentials from test_config (env file).
    
    Returns: (channel_id, channel_name, cleanup_info)
    """
    channel_name = f"test_file_{backend_type}_{test_id}_{int(time.time())}"
    
    # Get backend configuration from test_config
    config_key = f"file_channel.{backend_type}"
    
    if backend_type == "filesystem":
        base_path = test_config.get(f"{config_key}.base_path")
        assert base_path, f"❌ HARD FAIL: {config_key}.base_path not in env file"

        # RULES.md: no hardcoded defaults in tests - require all backend config keys explicitly
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
        
        channel_config = {
            "storage_type": "filesystem",
            "base_path": base_path,
            "create_subdirs": create_subdirs,
            "subdir_pattern": subdir_pattern,
            "file_name_pattern": file_name_pattern,
            "permissions": permissions,
        }
        
    elif backend_type == "webdav":
        url = test_config.get(f"{config_key}.url")
        username = test_config.get(f"{config_key}.username")
        password = test_config.get(f"{config_key}.password")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        
        assert url, f"❌ HARD FAIL: {config_key}.url not in env file"
        assert username, f"❌ HARD FAIL: {config_key}.username not in env file"
        assert password, f"❌ HARD FAIL: {config_key}.password not in env file"
        assert file_name_pattern, f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file"
        
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
        
        assert endpoint, f"❌ HARD FAIL: {config_key}.endpoint not in env file"
        assert bucket, f"❌ HARD FAIL: {config_key}.bucket not in env file"
        assert access_key, f"❌ HARD FAIL: {config_key}.access_key not in env file"
        assert secret_key, f"❌ HARD FAIL: {config_key}.secret_key not in env file"
        # Region may be intentionally blank, but config key must exist (RULES.md: no hidden defaults)
        if region is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.region not in env file (may be blank, but must be set)")
        assert file_name_pattern, f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file"
        
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
        username = test_config.get(f"{config_key}.username")
        password = test_config.get(f"{config_key}.password")
        port = test_config.get(f"{config_key}.port")
        passive_mode = test_config.get(f"{config_key}.passive_mode")
        file_name_pattern = test_config.get(f"{config_key}.file_name_pattern")
        
        assert host, f"❌ HARD FAIL: {config_key}.host not in env file"
        assert username, f"❌ HARD FAIL: {config_key}.username not in env file"
        assert password, f"❌ HARD FAIL: {config_key}.password not in env file"
        if port is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.port not in env file")
        if passive_mode is None:
            pytest.fail(f"❌ HARD FAIL: {config_key}.passive_mode not in env file")
        assert file_name_pattern, f"❌ HARD FAIL: {config_key}.file_name_pattern not in env file"
        
        channel_config = {
            "storage_type": "ftp",
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "passive_mode": passive_mode,
            "file_name_pattern": file_name_pattern,
        }
    
    # Create channel via API
    channel_data = {
        "name": channel_name,
        "type": "file",
        "enabled": True,
        "config": channel_config
    }
    
    response = api_client.post("/channels", json=channel_data)
    assert response.status_code == 201, f"Failed to create channel: {response.text}"
    
    channel_info = response.json()
    channel_id = channel_info.get("id")
    assert channel_id, "No channel ID returned"
    
    print(f"  ✅ Channel created: {channel_name} (ID: {channel_id})")
    
    return channel_id, channel_name, channel_config


def _storage_filename_for_api(backend_type: str, stored_path: str, channel_config: dict) -> str:
    """
    Convert a stored_files 'path' value to the filename expected by API storage endpoints:
      GET/PUT/DELETE /storage/files/{backend_type}/{filename}
      GET /storage/files/{backend_type}/{filename}/exists
    """
    if not stored_path:
        return ""

    if backend_type == "filesystem":
        # For filesystem, API endpoints expect a path relative to configured base_path.
        parsed = urlparse(stored_path)
        candidate = parsed.path if parsed.scheme == "file" else stored_path

        base_path = ""
        if isinstance(channel_config, dict):
            base_path = os.path.abspath(os.path.expanduser(channel_config.get("base_path") or ""))

        if base_path:
            abs_candidate = os.path.abspath(os.path.expanduser(candidate))
            base_norm = base_path.rstrip(os.sep)
            if abs_candidate.startswith(base_norm + os.sep):
                return abs_candidate[len(base_norm + os.sep):]

        return candidate.lstrip("/")

    if backend_type == "webdav":
        base_url = (channel_config.get("url") or "").rstrip("/")
        if base_url and stored_path.startswith(base_url):
            return stored_path[len(base_url):].lstrip("/")
        parsed = urlparse(stored_path)
        return (parsed.path or "").lstrip("/")

    if backend_type == "s3":
        bucket = channel_config.get("bucket") or ""
        if stored_path.startswith("s3://"):
            # s3://bucket/key
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

    return stored_path


def _read_storage_bytes(api_client, backend_type: str, file_path: str, channel_config: dict):
    """Read file bytes from local path if accessible, otherwise via storage API."""
    if backend_type == "filesystem" and file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()

    filename = _storage_filename_for_api(backend_type, file_path, channel_config)
    if not filename:
        return None

    response = api_client.get(f"/storage/files/{backend_type}/{filename}")
    if response.status_code == 200:
        return response.content

    return None


def _file_accessible(api_client, backend_type: str, file_path: str, channel_config: dict) -> bool:
    """True if file is accessible locally or via storage API."""
    if backend_type == "filesystem" and file_path and os.path.exists(file_path):
        return True

    filename = _storage_filename_for_api(backend_type, file_path, channel_config)
    if not filename:
        return False

    response = api_client.get(f"/storage/files/{backend_type}/{filename}")
    return response.status_code == 200


def delete_files_from_storage(api_client, test_config, backend_type, file_paths, channel_config):
    """
    Delete files from storage via API or direct access.
    """
    deleted_count = 0

    for file_path in file_paths:
        try:
            if backend_type == "filesystem" and file_path and os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
                print(f"    ✅ Deleted: {os.path.basename(file_path)}")
                continue

            filename = _storage_filename_for_api(backend_type, file_path, channel_config)
            if not filename:
                print(f"    ⚠️  Could not derive storage filename for deletion: {file_path}")
                continue

            response = api_client.delete(f"/storage/files/{backend_type}/{filename}")
            if response.status_code in [200, 204]:
                deleted_count += 1
                print(f"    ✅ Deleted from {backend_type}: {file_path}")
            elif response.status_code == 404:
                print(f"    ⚠️  Already deleted/not found: {file_path}")
            else:
                print(f"    ⚠️  Could not delete {file_path}: {response.status_code}")

        except Exception as e:
            print(f"    ⚠️  Error deleting {file_path}: {e}")

    return deleted_count


def delete_file_channel(api_client, channel_id, channel_name):
    """
    Disable file channel via API (deletion not supported, so we disable instead).
    """
    response = api_client.post(f"/channels/{channel_id}/disable")
    assert response.status_code in [200, 204], f"Failed to disable channel: {response.text}"
    print(f"  ✅ Channel disabled: {channel_name}")


def verify_files_deleted(api_client, test_config, backend_type, file_paths, channel_config):
    """
    Verify that files no longer exist after deletion.
    Returns count of files that still exist (should be 0).
    """
    still_exist_count = 0

    for file_path in file_paths:
        try:
            if backend_type == "filesystem" and file_path and os.path.exists(file_path):
                still_exist_count += 1
                print(f"    ❌ File still exists on host: {os.path.basename(file_path)}")
                continue

            filename = _storage_filename_for_api(backend_type, file_path, channel_config)
            if not filename:
                continue

            response = api_client.get(f"/storage/files/{backend_type}/{filename}")
            if response.status_code == 200:
                still_exist_count += 1
                print(f"    ❌ File still exists in backend: {filename}")

        except Exception:
            # If we get an error, assume file doesn't exist (which is good)
            pass

    return still_exist_count


def update_file_in_storage(api_client, test_config, backend_type, file_path, new_content, channel_config):
    """
    Update/overwrite a file in storage with new content.
    Returns True if successful.
    """
    try:
        if backend_type == "filesystem" and file_path and os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"    ✅ Updated: {os.path.basename(file_path)}")
            return True

        filename = _storage_filename_for_api(backend_type, file_path, channel_config)
        if not filename:
            print(f"    ❌ Could not derive storage filename for update: {file_path}")
            return False

        response = api_client.put(
            f"/storage/files/{backend_type}/{filename}",
            json={"content": new_content}
        )

        if response.status_code in [200, 204]:
            print(f"    ✅ Updated: {filename}")
            return True

        print(f"    ❌ Update failed: {response.status_code}")
        return False

    except Exception as e:
        print(f"    ❌ Error updating {file_path}: {e}")
        return False


def read_file_from_storage(api_client, test_config, backend_type, file_path, channel_config):
    """
    Read file content from storage.
    Returns file content as string or None if failed.
    """
    try:
        file_content = _read_storage_bytes(api_client, backend_type, file_path, channel_config)
        if file_content is None:
            return None
        return file_content.decode('utf-8')
    except Exception as e:
        print(f"    ⚠️  Error reading {file_path}: {e}")

    return None
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


@pytest.mark.parametrize("test_case", TEST_CASES, ids=[tc["test_id"] for tc in TEST_CASES])
def test_at1_4g_file_storage_lifecycle(test_case, api_client, test_output_dir, test_config):
    """
    Test file channel COMPLETE CRUD LIFECYCLE with comprehensive validation.
    
    CRUD Lifecycle Steps:
    1. CREATE: Create file channel via API
    2. CREATE: Send message and save files to storage
    3. READ: Verify file storage and content
    4. READ: Retrieve and validate file content
    5. UPDATE: Modify file content and verify
    6. DELETE: Delete files from storage
    7. READ: Verify files no longer exist
    8. DELETE: Remove/cleanup file channel
    
    Validation Layers:
    1. Environment validation (--env file required, HARD FAIL)
    2. Channel creation validation
    3. Message creation & delivery
    4. File storage validation (CREATE)
    5. File format validation (READ)
    6. Translation validation (READ)
    7. PDF-specific validation (READ)
    8. UPDATE operation validation
    9. DELETE operation validation
    10. Channel cleanup validation
    """
    
    test_id = test_case["test_id"]
    backend_type = test_case["backend_type"]
    backend_name = test_case["backend_name"]
    
    print(f"\n{'='*80}")
    print(f"Running: {test_id}")
    print(f"Backend: {backend_name}")
    print(f"Scenario: {test_case['description']}")
    print(f"{'='*80}\n")
    
    channel_id = None
    channel_name = None
    stored_file_paths = []
    
    try:
        # ============================================================================
        # LAYER 1: Environment Validation (HARD FAIL if not present)
        # ============================================================================
        assert test_config is not None, "❌ HARD FAIL: --env file not specified"
        
        api_base_url = test_config.get("api_server.base_url")
        assert api_base_url, "❌ HARD FAIL: API base URL not configured in env file"
        
        api_key = test_config.get("api_server.api_key")
        assert api_key, "❌ HARD FAIL: API key not configured in env file"
        
        llm_base_url = test_config.get("llm.base_url")
        assert llm_base_url, "❌ HARD FAIL: LLM base URL not configured in env file"
        
        # Validate backend-specific configuration exists
        config_key = test_case["backend_config_key"]
        # Try to get a key-specific config value to verify backend is configured
        if backend_type == "filesystem":
            backend_configured = test_config.get(f"{config_key}.base_path") is not None
        elif backend_type == "webdav":
            backend_configured = test_config.get(f"{config_key}.url") is not None
        elif backend_type == "s3":
            backend_configured = test_config.get(f"{config_key}.endpoint") is not None
        elif backend_type == "ftp":
            backend_configured = test_config.get(f"{config_key}.host") is not None
        else:
            backend_configured = False
            
        assert backend_configured, f"❌ HARD FAIL: {backend_type} configuration not in env file"
        
        print("✅ Layer 1: Environment validated")
        
        # ============================================================================
        # LAYER 2: Channel Creation Validation
        # ============================================================================
        channel_id, channel_name, channel_config = create_file_channel(
            api_client, test_config, backend_type, test_id
        )
        
        # Verify channel exists via API
        response = api_client.get(f"/channels/{channel_id}")
        assert response.status_code == 200, f"Channel not found after creation: {channel_id}"
        
        channel_data = response.json()
        assert channel_data.get("enabled") in [True, 1], "Channel not enabled"
        assert channel_data.get("type") == "file", "Wrong channel type"
        
        print("✅ Layer 2: Channel creation validated")
        
        # ============================================================================
        # LAYER 3: Message Creation & Delivery
        # ============================================================================
        
        # Load test content
        if test_case["size"] == 400:
            content_file = "tests/Examples/Test-400chars-en.md"
        elif test_case["size"] == 2000:
            # Use Test-Brief-News.md which is ~5000 chars, then trim
            content_file = "tests/Examples/Test-Brief-News.md"
        else:  # 5000
            content_file = "tests/Examples/Test-5000chars-en.md"
        
        with open(content_file, 'r', encoding='utf-8') as f:
            source_content = f.read()
        
        # Trim to expected size
        source_content = source_content[:test_case["size"]]
        
        # Build destination preferences
        destination_prefs = {
            "language": test_case["target_lang"],
            "generate_pdf": test_case["generate_pdf"],
            "output_formats": test_case["formats"]
        }
        
        if test_case["generate_summary"]:
            summary_size = test_config.get("test.at14g.summary_size")
            if not summary_size:
                pytest.fail(
                    "❌ HARD FAIL: test.at14g.summary_size not configured in env file "
                    "(set CLOUD_DOG__NOTIFY__TEST__AT14G__SUMMARY_SIZE)"
                )
            destination_prefs["max_length"] = int(summary_size)
        
        # Create message via API
        message_payload = {
            "audience_type": "direct",
            "destinations": [
                {
                    "channel": channel_name,
                    "address": "storage",  # For file channel
                    "preferences": destination_prefs
                }
            ],
            "content": [
                {
                    "type": "text",
                    "body": source_content
                }
            ]
        }
        
        response = api_client.post("/messages", json=message_payload)
        assert response.status_code == 201, f"Failed to create message: {response.text}"
        message_data = response.json()
        message_id = message_data.get("message_id")
        assert message_id, "No message_id returned"
        
        print(f"✅ Message created: {message_id}")
        
        # Wait for delivery to complete
        max_wait = test_config.get("test.at14g.max_wait")
        if not max_wait:
            pytest.fail(
                "❌ HARD FAIL: test.at14g.max_wait not configured in env file "
                "(set CLOUD_DOG__NOTIFY__TEST__AT14G__MAX_WAIT)"
            )
        max_wait = int(max_wait)
        poll_interval = test_config.get("test.at14g.poll_interval")
        if not poll_interval:
            pytest.fail(
                "❌ HARD FAIL: test.at14g.poll_interval not configured in env file "
                "(set CLOUD_DOG__NOTIFY__TEST__AT14G__POLL_INTERVAL)"
            )
        poll_interval = float(poll_interval)
        start_time = time.time()
        delivery_complete = False
        delivery_data = None
        
        while time.time() - start_time < max_wait:
            response = api_client.get(f"/messages/{message_id}/deliveries")
            assert response.status_code == 200, f"Failed to get deliveries: {response.text}"
            
            deliveries_response = response.json()
            deliveries = deliveries_response.get("items", [])
            
            if deliveries:
                delivery_data = deliveries[0]
                status = delivery_data.get("state") or delivery_data.get("status")
                
                if status == "sent":
                    delivery_complete = True
                    print(f"✅ Delivery complete: {status}")
                    break
                elif status in ["failed", "error", "hard_failed", "soft_failed", "rejected"]:
                    pytest.fail(f"❌ Delivery failed: {status}, error: {delivery_data.get('error_message')}")
                
            time.sleep(poll_interval)
        
        assert delivery_complete, f"❌ Delivery did not complete within {max_wait}s"
        
        print("✅ Layer 3: Message creation & delivery validated")
        
        # ============================================================================
        # LAYER 4: File Storage Validation
        # ============================================================================
        
        # Extract stored file list.
        # File adapter stores stored_files JSON in delivery.tracking_id (see src/adapters/file_adapter.py).
        metadata = delivery_data.get("metadata_json", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        stored_files = []
        if isinstance(metadata, dict):
            stored_files = metadata.get("stored_files", []) or []

        if not stored_files:
            # Delivery table stores provider tracking id; API exposes it as provider_tracking_id
            tracking = delivery_data.get("provider_tracking_id") or delivery_data.get("tracking_id")
            if tracking:
                try:
                    stored_files = json.loads(tracking) if isinstance(tracking, str) else tracking
                except Exception as e:
                    print(f"    ⚠️  Failed to parse tracking_id stored_files JSON: {e}")
                    stored_files = []

        if not isinstance(stored_files, list):
            stored_files = []
        assert len(stored_files) == test_case["expected_files"], \
            f"❌ Expected {test_case['expected_files']} files, got {len(stored_files)}"
        
        print(f"✅ Expected file count correct: {len(stored_files)} files")
        
        # Collect file paths for cleanup
        stored_file_paths = [sf.get("path") for sf in stored_files]
        
        # Validate each stored file
        for stored_file in stored_files:
            file_path = stored_file.get("path")
            file_format = stored_file.get("format")
            
            assert _file_accessible(api_client, backend_type, file_path, channel_config),                 f"❌ File not accessible via host/API: {file_path}"
            print(f"  ✅ File accessible on {backend_type}: {os.path.basename(file_path)}")
            
            # Validate file naming
            file_name = os.path.basename(file_path)
            assert str(message_id) in file_name, f"❌ Message ID not in filename: {file_name}"
            assert test_case["target_lang"] in file_name, f"❌ Language not in filename: {file_name}"
        
        print("✅ Layer 4: File storage validated")
        
        # ============================================================================
        # LAYER 5: File Format Validation
        # ============================================================================
        
        for stored_file in stored_files:
            file_path = stored_file.get("path")
            file_format = stored_file.get("format")
            
            # Download/read file content (host path when available, else storage API)
            file_content = _read_storage_bytes(api_client, backend_type, file_path, channel_config)
            assert file_content is not None, f"Failed to download: {file_path}"
            
            # Validate format-specific content
            if file_format == "md":
                content_str = file_content.decode('utf-8')
                # Markdown output can be a plain-text summary (no headings) when max_length is requested.
                if not test_case.get("generate_summary"):
                    assert (
                        "##" in content_str
                        or "###" in content_str
                        or "# " in content_str
                        or "**" in content_str
                        or "- " in content_str
                    ), "❌ Markdown structure not preserved"
                print(f"  ✅ Markdown format validated: {os.path.basename(file_path)}")
                
            elif file_format == "txt":
                content_str = file_content.decode('utf-8')
                assert len(content_str) > 100, "❌ TXT file too small"
                print(f"  ✅ TXT format validated: {os.path.basename(file_path)}")
                
            elif file_format == "pdf":
                # PDF validation in Layer 7
                pass
        
        print("✅ Layer 5: File format validated")
        
        # ============================================================================
        # LAYER 6: Translation Validation
        # ============================================================================
        
        if test_case["expected_translations"]:
            for stored_file in stored_files:
                file_path = stored_file.get("path")
                file_format = stored_file.get("format")
                
                if file_format in ["md", "txt"]:
                    file_content = read_file_from_storage(api_client, test_config, backend_type, file_path, channel_config)
                    assert file_content is not None, f"Failed to read translated file: {file_path}"

                    # Strip markdown links and raw URLs before validation to avoid
                    # short summary files being skewed by English link labels.
                    content_for_validation = re.sub(r"\[[^\]]+\]\(([^)]+)\)", " ", file_content)
                    content_for_validation = re.sub(r"https?://\S+", " ", content_for_validation)
                    target_lang_code = test_case["target_lang"][:2]
                    source_lang_code = test_case["source_lang"][:2]
                    is_valid, validation_info = validate_language(
                        content_for_validation,
                        target_lang_code,
                        source_language=source_lang_code if source_lang_code != target_lang_code else None,
                    )

                    assert is_valid, (
                        f"❌ Language mismatch for {os.path.basename(file_path)}: "
                        f"expected {target_lang_code}, details={validation_info}"
                    )

                    print(
                        f"  ✅ Translation validated: {target_lang_code} in {os.path.basename(file_path)} "
                        f"({validation_info})"
                    )
        
        print("✅ Layer 6: Translation validated")
        
        # ============================================================================
        # LAYER 7: PDF-Specific Validation
        # ============================================================================
        
        pdf_files = [sf for sf in stored_files if sf.get("format") == "pdf"]
        
        for pdf_file in pdf_files:
            pdf_path = pdf_file.get("path")
            
            # Read PDF content (host path when available, else storage API)
            pdf_content_bytes = _read_storage_bytes(api_client, backend_type, pdf_path, channel_config)
            assert pdf_content_bytes is not None, f"Failed to download PDF: {pdf_path}"
            
            # Validate PDF
            # NOTE: helpers.validate_pdf() treats `expected_min_size` as an *expected size* (with wide tolerance),
            # and also uses it to derive content-quality thresholds. So:
            # - If a summary was requested (max_length), expect roughly that size.
            # - Otherwise, expect roughly the source content size (translations can expand, so we keep it high).
            if test_case.get("generate_summary"):
                expected_min_size = int(summary_size)  # set earlier when generate_summary=True
            else:
                expected_min_size = len(source_content)

            is_valid, pdf_validation = validate_pdf(
                pdf_content=pdf_content_bytes,
                expected_language=test_case["target_lang"],
                expected_min_size=expected_min_size,
                source_content=source_content
            )
            
            assert is_valid, f"❌ PDF validation failed: {pdf_validation}"
            
            print(f"  ✅ PDF validated: {os.path.basename(pdf_path)}")
            print(f"     - Size: {pdf_validation.get('size_bytes', 'unknown')} bytes")
            print(f"     - Characters: {pdf_validation.get('char_count', 'unknown')}")
            
            if test_case.get("expect_rtl"):
                rtl_correct = pdf_validation.get('rtl_correct', False)
                assert rtl_correct, "❌ RTL text flow not correct"
                print(f"     - RTL: ✅ Correct")
            
            if test_case.get("expect_cjk"):
                # helpers.validate_pdf() already fails hard on missing/garbled CJK.
                assert not pdf_validation.get("cjk_corruption"), f"❌ CJK corruption detected: {pdf_validation.get('cjk_message')}"
                print("     - CJK: ✅ Rendering checks passed")
        
        print("✅ Layer 7: PDF-specific validation complete")
        
        # ============================================================================
        # LAYER 8: UPDATE Operation - Modify file content
        # ============================================================================
        
        print("\n📝 Testing UPDATE operation...")
        
        # Select first MD or TXT file for update test (skip PDFs as they're binary)
        updateable_files = [f for f in stored_file_paths if f.endswith(('.md', '.txt'))]
        
        if updateable_files:
            test_file = updateable_files[0]
            original_content = read_file_from_storage(
                api_client, test_config, backend_type, test_file, channel_config
            )
            
            assert original_content is not None, f"Could not read file for update test: {test_file}"
            print(f"  ✅ Read original content ({len(original_content)} chars)")
            
            # Update with new content
            updated_content = f"{original_content}\n\n# UPDATED\nThis content was added during CRUD test."
            success = update_file_in_storage(
                api_client, test_config, backend_type, test_file, updated_content, channel_config
            )
            
            assert success, f"Failed to update file: {test_file}"
            
            # Re-read and verify update
            re_read_content = read_file_from_storage(
                api_client, test_config, backend_type, test_file, channel_config
            )
            
            assert re_read_content is not None, "Could not re-read file after update"
            assert "# UPDATED" in re_read_content, "Updated content not found in file"
            assert len(re_read_content) > len(original_content), "File size did not increase after update"
            
            print(f"  ✅ File updated and verified ({len(re_read_content)} chars)")
        else:
            print("  ⚠️  No updateable files (MD/TXT) found, skipping UPDATE test")
        
        print("✅ Layer 8: UPDATE operation validated")
        
        # ============================================================================
        # LAYER 9: DELETE Operation - Remove files
        # ============================================================================
        
        print("\n🗑️  Testing DELETE operation...")
        
        # Delete files from storage
        deleted_count = delete_files_from_storage(
            api_client, test_config, backend_type, stored_file_paths, channel_config
        )
        print(f"  ✅ Deleted {deleted_count}/{len(stored_file_paths)} files")
        
        # Verify files are actually deleted
        still_exist_count = verify_files_deleted(
            api_client, test_config, backend_type, stored_file_paths, channel_config
        )
        
        assert still_exist_count == 0, f"❌ {still_exist_count} files still exist after deletion!"
        print(f"  ✅ Verified all {len(stored_file_paths)} files are deleted")
        
        # Try to read deleted file - should fail
        if stored_file_paths:
            test_file = stored_file_paths[0]
            content = read_file_from_storage(
                api_client, test_config, backend_type, test_file, channel_config
            )
            assert content is None, f"❌ Can still read deleted file: {test_file}"
            print(f"  ✅ Confirmed deleted files cannot be read")
        
        print("✅ Layer 9: DELETE operation validated")
        
        # ============================================================================
        # LAYER 10: Cleanup - Remove channel
        # ============================================================================
        # ============================================================================
        # LAYER 10: Cleanup - Remove channel
        # ============================================================================
        
        # Delete channel
        print("\n🧹 Cleaning up file channel...")
        delete_file_channel(api_client, channel_id, channel_name)
        
        # Verify channel is disabled
        response = api_client.get(f"/channels/{channel_id}")
        assert response.status_code == 200, "Channel GET failed"
        channel_status = response.json()
        assert channel_status.get("enabled") in [False, 0], "Channel still enabled after cleanup"
        
        print("✅ Layer 10: Channel cleanup validated")
        
        # ============================================================================
        # Save Test Output
        # ============================================================================
        
        output_file = test_output_dir / f"{test_id}_results.json"
        output_data = {
            "test_id": test_id,
            "backend_type": backend_type,
            "backend_name": backend_name,
            "scenario": test_case["description"],
            "message_id": message_id,
            "channel_id": channel_id,
            "channel_name": channel_name,
            "source_lang": test_case["source_lang"],
            "target_lang": test_case["target_lang"],
            "size": test_case["size"],
            "formats": test_case["formats"],
            "generate_pdf": test_case["generate_pdf"],
            "generate_summary": test_case["generate_summary"],
            "stored_files": stored_files,
            "files_updated": len(updateable_files) if 'updateable_files' in locals() else 0,
            "files_deleted": deleted_count,
            "channel_deleted": True,
            "validation_passed": True,
            "layers_validated": 10,
            "crud_operations": {
                "create": True,
                "read": True,
                "update": len(updateable_files) > 0 if 'updateable_files' in locals() else False,
                "delete": True
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved: {output_file}")
        
        print(f"\n{'='*80}")
        print(f"✅ AT1.4g PASSED: {test_id}")
        print(f"   Backend: {backend_name}")
        print(f"   Scenario: {test_case['description']}")
        print(f"{'='*80}\n")
        
    except Exception as e:
        # Cleanup on failure
        print(f"\n❌ Test failed: {e}")
        
        if stored_file_paths:
            print("\n🧹 Attempting cleanup after failure...")
            try:
                delete_files_from_storage(api_client, test_config, backend_type, 
                                        stored_file_paths, channel_config if 'channel_config' in locals() else {})
            except Exception as cleanup_error:
                print(f"  ⚠️  Cleanup error: {cleanup_error}")
        
        if channel_id:
            try:
                delete_file_channel(api_client, channel_id, channel_name)
            except Exception as cleanup_error:
                print(f"  ⚠️  Channel cleanup error: {cleanup_error}")
        
        raise

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.pure, pytest.mark.heavy]
