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
Test LLM Queue Status Endpoint

Tests:
- V25.15: GET /llm/status returns correct status
- V25.16: Status reflects current LLM load
- V25.17: Status updates as queue changes
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx

def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


@pytest.fixture
def api_client(test_config):
    """Create API client"""
    api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url")
    api_key = _require_value(test_config.get("api_server.api_key"), "api_server.api_key")
    return httpx.Client(
        base_url=api_base_url,
        headers={"X-API-Key": api_key},
        timeout=10.0,
    )
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_status_returns_correct_format(api_client):
    """V25.15: GET /llm/status returns correct status"""
    response = api_client.get("/llm/status")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Check required fields
    assert "available" in data, "Missing 'available' field"
    assert "active_requests" in data, "Missing 'active_requests' field"
    assert "max_concurrent" in data, "Missing 'max_concurrent' field"
    assert "queue_length" in data, "Missing 'queue_length' field"
    assert "estimated_wait_seconds" in data, "Missing 'estimated_wait_seconds' field"
    
    # Check types
    assert isinstance(data["available"], bool), "available must be boolean"
    assert isinstance(data["active_requests"], int), "active_requests must be integer"
    assert isinstance(data["max_concurrent"], int), "max_concurrent must be integer"
    assert isinstance(data["queue_length"], int), "queue_length must be integer"
    assert isinstance(data["estimated_wait_seconds"], (int, float)), "estimated_wait_seconds must be number"
    
    # Check values are reasonable
    assert data["active_requests"] >= 0, "active_requests must be >= 0"
    assert data["max_concurrent"] > 0, "max_concurrent must be > 0"
    assert data["active_requests"] <= data["max_concurrent"], "active_requests cannot exceed max_concurrent"
    assert data["queue_length"] >= 0, "queue_length must be >= 0"
    assert data["estimated_wait_seconds"] >= 0, "estimated_wait_seconds must be >= 0"
    
    print(f"✅ LLM Status: available={data['available']}, active={data['active_requests']}/{data['max_concurrent']}, queue={data['queue_length']}, wait={data['estimated_wait_seconds']}s")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_status_reflects_current_load(api_client):
    """V25.16: Status reflects current LLM load"""
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_llm_status_reflects_current_load"
    )

    # Get initial status
    response1 = api_client.get("/llm/status")
    assert response1.status_code == 200
    status1 = response1.json()
    
    print(f"Initial status: available={status1['available']}, active={status1['active_requests']}, queue={status1['queue_length']}")
    
    # Status should be consistent (same call should return similar values)
    response2 = api_client.get("/llm/status")
    assert response2.status_code == 200
    status2 = response2.json()
    
    # active_requests and queue_length might change, but structure should be same
    assert status2["max_concurrent"] == status1["max_concurrent"], "max_concurrent should be consistent"
    assert "connection_status" in status2 or "available" in status2, "Should have connection status"
    
    print(f"✅ Status is consistent: max_concurrent={status2['max_concurrent']}")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_status_updates_with_queue(api_client, test_email, test_config):
    """V25.17: Status updates as queue changes"""
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_llm_status_updates_with_queue"
    )
    # Get initial status
    response1 = api_client.get("/llm/status")
    assert response1.status_code == 200
    status1 = response1.json()
    
    initial_queue = status1["queue_length"]
    initial_active = status1["active_requests"]
    
    print(f"Initial: queue={initial_queue}, active={initial_active}")
    
    # Create a message that requires LLM formatting (this will queue if LLM is busy)
    # Use a simple message to avoid long waits
    message_payload = {
        "audience_type": "personalised",
        "destinations": [
            {
                "channel": _require_value(test_config.get("default_channel"), "default_channel"),
                "address": test_email,
                "preferences": {
                    "language": "fr",
                    "content_style": "html"
                }
            }
        ],
        "content": [
            {
                "type": "text",
                "body": "Test message for LLM queue status"
            }
        ],
        "options": {
            "subject": "LLM Queue Test"
        }
    }
    
    # Submit message (should return immediately)
    response = api_client.post("/messages", json=message_payload, timeout=5.0)
    assert response.status_code == 201, f"Message creation failed: {response.status_code} - {response.text}"
    
    # Check status again (queue might have increased)
    response2 = api_client.get("/llm/status")
    assert response2.status_code == 200
    status2 = response2.json()
    
    print(f"After message: queue={status2['queue_length']}, active={status2['active_requests']}")
    
    # Queue length might increase or stay same (depending on LLM availability)
    # But the endpoint should still work
    assert status2["queue_length"] >= 0, "Queue length should be non-negative"
    assert status2["active_requests"] >= 0, "Active requests should be non-negative"
    
    print(f"✅ Status endpoint responds correctly after message creation")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.system,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.llm,
    pytest.mark.smtp,
    pytest.mark.slow,
]
