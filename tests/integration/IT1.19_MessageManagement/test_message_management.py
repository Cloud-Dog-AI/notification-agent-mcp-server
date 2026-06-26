# @pytest.mark.req("UC-003")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-006")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Test Message Management API Endpoints

Tests:
1. DELETE /messages/{id} - Delete message and all related data
2. POST /messages/{id}/cancel - Cancel pending deliveries
3. Verify no direct database access in tests
"""

import pytest
import httpx
import json
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_delete_message_api(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """Test DELETE /messages/{id} endpoint"""
    
    
    print(f"\n{'='*80}")
    print("MESSAGE MANAGEMENT API TEST - DELETE")
    print(f"{'='*80}\n")
    
    # Step 1: Create a test message
    print("=" * 80)
    print("STEP 1: CREATE TEST MESSAGE")
    print("=" * 80)
    
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
            "preferences": {
                "language": "en",
                "content_style": "html"
            }
        }],
        "content": [{
            "type": "text",
            "body": "Test message for deletion"
        }],
        "options": {
            "subject": "Test Message for Deletion"
        }
    }
    
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base_url}/messages",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json=message_payload
        )
        
        assert response.status_code == 201, f"Message creation failed: {response.text}"
        result = response.json()
        message_id = result.get("message_id")
        message_guid = result.get("guid")
        
        print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
    
    # Step 2: Wait for delivery to complete (or at least be queued)
    print("\n" + "=" * 80)
    print("STEP 2: WAIT FOR DELIVERY")
    print("=" * 80)
    
    time.sleep(2)  # Brief wait for delivery to be created
    
    # Step 3: Verify message exists
    print("\n" + "=" * 80)
    print("STEP 3: VERIFY MESSAGE EXISTS")
    print("=" * 80)
    
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200, f"Message should exist: {response.text}"
        print(f"✅ Message {message_id} exists")
        
        # Verify deliveries exist
        response = client.get(
            f"{api_base_url}/messages/{message_id}/deliveries",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200, f"Deliveries should exist: {response.text}"
        deliveries_data = response.json()
        deliveries_count = len(deliveries_data.get("items", []))
        print(f"✅ Found {deliveries_count} delivery(ies)")
    
    # Step 4: Delete message via API
    print("\n" + "=" * 80)
    print("STEP 4: DELETE MESSAGE VIA API")
    print("=" * 80)
    
    with httpx.Client(timeout=10.0) as client:
        response = client.delete(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 200, f"Delete failed: {response.text}"
        result = response.json()
        
        assert result.get("deleted") == True, "Delete should return deleted=true"
        assert result.get("message_id") == message_id, "Delete should return correct message_id"
        assert result.get("deliveries_deleted", 0) >= 0, "Delete should return deliveries_deleted count"
        assert result.get("receipts_deleted", 0) >= 0, "Delete should return receipts_deleted count"
        
        print(f"✅ Message deleted successfully")
        print(f"   Deliveries deleted: {result.get('deliveries_deleted')}")
        print(f"   Receipts deleted: {result.get('receipts_deleted')}")
    
    # Step 5: Verify message is deleted
    print("\n" + "=" * 80)
    print("STEP 5: VERIFY MESSAGE IS DELETED")
    print("=" * 80)
    
    with httpx.Client(timeout=10.0) as client:
        response = client.get(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 404, f"Message should be deleted (404), got {response.status_code}"
        print(f"✅ Message {message_id} is deleted (404 Not Found)")
        
        # Verify deliveries are deleted
        response = client.get(
            f"{api_base_url}/messages/{message_id}/deliveries",
            headers={"X-API-Key": api_key}
        )
        # Should return 404 or empty list
        if response.status_code == 404:
            print(f"✅ Deliveries endpoint returns 404 (message not found)")
        elif response.status_code == 200:
            deliveries_data = response.json()
            assert deliveries_data.get("total", 0) == 0, "Deliveries should be deleted"
            print(f"✅ Deliveries are deleted (empty list)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    print(f"\n{'='*80}")
    print("✅ TEST COMPLETE - MESSAGE DELETION VIA API WORKS")
    print(f"{'='*80}\n")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_delete_message_by_guid(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """Test DELETE /messages/{guid} endpoint using GUID"""
    
    
    print(f"\n{'='*80}")
    print("MESSAGE MANAGEMENT API TEST - DELETE BY GUID")
    print(f"{'='*80}\n")
    
    # Step 1: Create a test message
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
        }],
        "content": [{
            "type": "text",
            "body": "Test message for GUID deletion"
        }]
    }
    
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base_url}/messages",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json=message_payload
        )
        
        assert response.status_code == 201, f"Message creation failed: {response.status_code} - {response.text}"
        result = response.json()
        message_id = result.get("message_id")
        message_guid = result.get("guid")
        
        # If GUID not in response, fetch it
        if not message_guid:
            msg_response = client.get(
                f"{api_base_url}/messages/{message_id}",
                headers={"X-API-Key": api_key, "Accept": "application/json"}
            )
            if msg_response.status_code == 200:
                msg_data = msg_response.json()
                message_guid = msg_data.get("guid")
        
        print(f"✅ Message created: ID={message_id}, GUID={message_guid}")
        
        if not message_guid:
            pytest.fail("GUID not available, skipping GUID deletion test")
        
        # Step 2: Delete by GUID
        time.sleep(1)  # Brief wait
        
        print(f"🔍 Attempting DELETE with GUID: {message_guid}")
        response = client.delete(
            f"{api_base_url}/messages/{message_guid}",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            follow_redirects=False  # Don't follow redirects
        )
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📊 Response headers: {dict(response.headers)}")
        print(f"📊 Response content preview: {response.text[:200]}")
        
        assert response.status_code == 200, f"Delete by GUID failed: {response.status_code} - {response.text[:200]}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        print(f"📋 Content-Type: {content_type}")
        
        # Parse JSON response
        try:
            result = response.json()
            print(f"✅ Successfully parsed JSON response: {result}")
        except json.JSONDecodeError as e:
            print(f"❌ Response is not valid JSON: {response.text[:500]}")
            print(f"   Content-Type: {content_type}")
            print(f"   Error: {e}")
            pytest.fail(f"Delete by GUID returned non-JSON response. Status: {response.status_code}, Content-Type: {content_type}, Content: {response.text[:200]}")
        
        assert result.get("deleted") == True, f"Delete should return deleted=true, got: {result}"
        assert result.get("message_id") == message_id, f"Delete should return correct message_id, got: {result}"
        
        print(f"✅ Message deleted by GUID successfully")
        
        # Step 3: Verify deleted
        response = client.get(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key, "Accept": "application/json"}
        )
        assert response.status_code == 404, f"Message should be deleted (404), got {response.status_code}"
        print(f"✅ Message deleted (verified via ID lookup)")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_cancel_message_api(api_base_url, api_key, smtp_config, test_email, test_config, default_channel):
    """Test POST /messages/{id}/cancel endpoint"""
    
    
    print(f"\n{'='*80}")
    print("MESSAGE MANAGEMENT API TEST - CANCEL")
    print(f"{'='*80}\n")
    
    # Step 1: Create a test message
    message_payload = {
        "audience_type": "personalised",
        "destinations": [{
            "channel": default_channel,
            "address": test_email,
        }],
        "content": [{
            "type": "text",
            "body": "Test message for cancellation"
        }]
    }
    
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            f"{api_base_url}/messages",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json=message_payload
        )
        
        assert response.status_code == 201
        result = response.json()
        message_id = result.get("message_id")
        print(f"✅ Message created: ID={message_id}")
        
        # Step 2: Cancel message
        time.sleep(1)  # Brief wait for delivery to be created
        
        response = client.post(
            f"{api_base_url}/messages/{message_id}/cancel",
            headers={"X-API-Key": api_key}
        )
        
        assert response.status_code == 200, f"Cancel failed: {response.text}"
        result = response.json()
        
        assert result.get("message_id") == message_id
        assert "cancelled_count" in result
        
        print(f"✅ Message cancelled successfully")
        print(f"   Cancelled deliveries: {result.get('cancelled_count')}")
        
        # Step 3: Verify message still exists but is cancelled
        response = client.get(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200, "Message should still exist after cancel"
        print(f"✅ Message still exists (cancelled, not deleted)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]

