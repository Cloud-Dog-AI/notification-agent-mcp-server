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
AT1.5 Email Channel CRUD Operations Test

Tests CRUD operations for email channels:
- CREATE: Create new email channel
- READ: Retrieve channel configuration
- UPDATE: Update channel settings
- DELETE/DISABLE: Disable channel

Related Requirements: FR1.6
Related Architecture: CC5.1.1
Related Tests: AT1.5
"""

import pytest
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any
import httpx

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-012")


def test_at1_5_email_channel_crud(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    smtp_config: Dict[str, Any],
    test_output_dir: Path
):
    """
    Test CRUD operations for email channels
    
    Validates:
    1. CREATE: Create new email channel
    2. READ: Retrieve channel configuration
    3. UPDATE: Update channel settings
    4. DELETE/DISABLE: Disable channel
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("at15_env_loaded"):
        pytest.fail(
            "❌ CRITICAL: AT1.5 env file not loaded!\n"
            "Required: --env private/env-test-at15\n"
        )
    
    # CRITICAL: Check dependencies
    check_test_dependencies(
        requires_llm=False,
        requires_smtp=False,  # We're testing channel config, not delivery
        requires_api=True,
        test_name="AT1.5_EMAIL_CHANNEL_CRUD"
    )
    
    print(f"\n{'='*80}")
    print("AT1.5 EMAIL CHANNEL CRUD TEST")
    print(f"{'='*80}\n")
    
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured")
    api_timeout = float(api_timeout)

    smtp_host = smtp_config.get("host")
    smtp_port = smtp_config.get("port")
    smtp_username = smtp_config.get("username")
    smtp_password = smtp_config.get("password")
    smtp_from = smtp_config.get("from_address")
    if not all([smtp_host, smtp_port, smtp_username, smtp_password, smtp_from]):
        pytest.fail("❌ HARD FAIL: SMTP configuration incomplete in env file (channels.smtp.default.*)")

    test_channel_name = f"test_email_channel_{int(time.time())}"
    channel_id = None

    try:
        # =========================================================================
        # LAYER 1: CREATE
        # =========================================================================
        print("=" * 80)
        print("LAYER 1: CREATE EMAIL CHANNEL")
        print("=" * 80)

        channel_config = {
            "name": test_channel_name,
            "type": "smtp",
            "enabled": True,
            "config": {
                "host": smtp_host,
                "port": smtp_port,
                "username": smtp_username,
                "password": smtp_password,
                "from_address": smtp_from,
                "use_tls": smtp_config.get("use_tls"),
                "use_starttls": smtp_config.get("use_starttls"),
                "timeout": smtp_config.get("timeout"),
            },
        }

        with httpx.Client(timeout=api_timeout) as client:
            resp = client.post(
                f"{api_base_url}/channels",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=channel_config,
            )
        assert resp.status_code == 201, f"Channel creation failed: {resp.status_code} - {resp.text}"
        channel_id = resp.json().get("id")
        assert channel_id, "Channel ID not returned"
        print(f"✅ Channel created: ID={channel_id}, Name={test_channel_name}")

        # =========================================================================
        # LAYER 2: READ
        # =========================================================================
        print("\n" + "=" * 80)
        print("LAYER 2: READ CHANNEL CONFIGURATION")
        print("=" * 80)

        with httpx.Client(timeout=api_timeout) as client:
            resp = client.get(f"{api_base_url}/channels/{channel_id}", headers={"X-API-Key": api_key})
            assert resp.status_code == 200, f"Channel read failed: {resp.status_code}"
            channel_data = resp.json()
            assert channel_data.get("id") == channel_id, "Channel ID mismatch"
            assert channel_data.get("name") == test_channel_name, "Channel name mismatch"
            assert channel_data.get("type") == "smtp", "Channel type mismatch"
            assert bool(channel_data.get("enabled")) is True, "Channel not enabled"
            print("✅ Channel read OK")

        # =========================================================================
        # LAYER 3: UPDATE
        # =========================================================================
        print("\n" + "=" * 80)
        print("LAYER 3: UPDATE CHANNEL CONFIGURATION")
        print("=" * 80)

        update_data = {
            "enabled": True,
            "config_json": json.dumps({
                "host": smtp_host,
                "port": smtp_port,
                "username": smtp_username,
                "password": smtp_password,
                "from_address": smtp_from,
                "use_tls": not bool(smtp_config.get("use_tls")),
                "use_starttls": not bool(smtp_config.get("use_starttls")),
                "timeout": smtp_config.get("timeout"),
            }),
        }
        with httpx.Client(timeout=api_timeout) as client:
            resp = client.patch(
                f"{api_base_url}/channels/{channel_id}",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=update_data,
            )
            assert resp.status_code == 200, f"Channel update failed: {resp.status_code} - {resp.text}"
            updated = resp.json()
            assert updated.get("id") == channel_id, "Channel ID changed"
            assert bool(updated.get("enabled")) is True, "Channel not enabled after update"
            print("✅ Channel update OK")

        # =========================================================================
        # LAYER 4: DISABLE
        # =========================================================================
        print("\n" + "=" * 80)
        print("LAYER 4: DISABLE CHANNEL")
        print("=" * 80)

        with httpx.Client(timeout=api_timeout) as client:
            resp = client.post(f"{api_base_url}/channels/{channel_id}/disable", headers={"X-API-Key": api_key})
            assert resp.status_code == 200, f"Channel disable failed: {resp.status_code} - {resp.text}"
            # Verify disabled
            resp = client.get(f"{api_base_url}/channels/{channel_id}", headers={"X-API-Key": api_key})
            assert resp.status_code == 200, "Channel read after disable failed"
            assert bool(resp.json().get("enabled")) is False, "Channel still enabled after disable"
            print("✅ Channel disable verified")

        # =========================================================================
        # SUMMARY
        # =========================================================================
        print("\n" + "=" * 80)
        print("LAYER 5: CRUD OPERATIONS SUMMARY")
        print("=" * 80)
        print(f"✅ CREATE/READ/UPDATE/DISABLE validated for channel {channel_id}")

        test_log_file = test_output_dir / "at1_5_email_channel_crud_log.txt"
        with open(test_log_file, "w") as f:
            f.write("Test: AT1.5 Email Channel CRUD\n")
            f.write(f"Channel ID: {channel_id}\n")
            f.write(f"Channel Name: {test_channel_name}\n")
            f.write("Status: PASSED\n")
        print(f"\n✅ Test log saved: {test_log_file}")

    finally:
        # Best-effort cleanup: disable test channel
        if channel_id is not None:
            try:
                with httpx.Client(timeout=api_timeout) as client:
                    client.post(f"{api_base_url}/channels/{channel_id}/disable", headers={"X-API-Key": api_key})
            except Exception:
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

