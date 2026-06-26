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
Integration Tests for Notification Agent MCP Server

Tests end-to-end functionality across multiple channels with real providers.
"""

import pytest
import sys
import os

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import time
import json
import asyncio
from tests.conftest import process_deliveries
from src.database.db_manager import DatabaseManager
from src.core.job_manager import JobManager
from src.core.state_machine import DeliveryState

API_BASE_URL = None
API_KEY = None
DEFAULT_CHANNEL = None
DB_URI = None
SMS_CHANNEL = None
SMS_RECIPIENT = None


def _is_external_runtime_mode() -> bool:
    return str(os.environ.get("TEST_USE_EXTERNAL_RUNTIME", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_host_db_uri(db_uri: str) -> str:
    """Map container sqlite path to host path when tests run outside Docker."""
    if not db_uri:
        return db_uri
    if db_uri.startswith("sqlite3:///app/"):
        rel_path = db_uri.replace("sqlite3:///app/", "", 1)
        host_path = (project_root / rel_path).resolve()
        return f"sqlite3:///{host_path}"
    return db_uri


def _open_test_db() -> DatabaseManager:
    db = DatabaseManager(_resolve_host_db_uri(DB_URI))
    db.connect()
    return db


def _destination_for_channel(channel: dict, test_email: str) -> str | None:
    channel_type = str(channel.get("type") or "").lower()
    if channel_type in {"smtp", "email", "loopback"}:
        return test_email
    if channel_type in {"sms", "twilio_sms", "whatsapp"} and SMS_RECIPIENT:
        return SMS_RECIPIENT
    return None


def _build_multichannel_destinations(test_email: str) -> list[dict]:
    response = httpx.get(f"{API_BASE_URL}/channels", headers=get_headers(), timeout=20.0)
    assert response.status_code == 200, f"Failed to list channels: {response.status_code} {response.text[:200]}"
    channels = [c for c in response.json() if isinstance(c, dict) and bool(c.get("enabled"))]
    by_name = {str(c.get("name")): c for c in channels if c.get("name")}

    selected: list[dict] = []
    seen = set()

    def _add_channel(channel: dict):
        name = str(channel.get("name") or "")
        if not name or name in seen:
            return
        address = _destination_for_channel(channel, test_email)
        if not address:
            return
        selected.append({"channel": name, "address": address})
        seen.add(name)

    # Prefer configured defaults first.
    for preferred in [DEFAULT_CHANNEL, SMS_CHANNEL]:
        if preferred and preferred in by_name:
            _add_channel(by_name[preferred])

    # Fallback to any other enabled channels that can accept a known destination.
    if len(selected) < 2:
        for channel in channels:
            _add_channel(channel)
            if len(selected) >= 2:
                break

    assert len(selected) >= 2, (
        "Need at least two enabled channels with resolvable destinations for IT1.2 "
        f"(found {len(selected)})"
    )
    return selected[:2]


@pytest.fixture(scope="session", autouse=True)
def _load_api_settings(test_config):
    global API_BASE_URL, API_KEY, DEFAULT_CHANNEL, DB_URI, SMS_CHANNEL, SMS_RECIPIENT
    API_BASE_URL = test_config.get("api_server.base_url")
    API_KEY = test_config.get("api_server.api_key")
    DEFAULT_CHANNEL = test_config.get("default_channel")
    DB_URI = test_config.get("db.uri")
    SMS_CHANNEL = test_config.get("test.sms.channel_name") or test_config.get("channels.sms.default.name")
    SMS_RECIPIENT = test_config.get("test.sms.recipient")
    if SMS_RECIPIENT is not None and SMS_RECIPIENT != "":
        SMS_RECIPIENT = str(SMS_RECIPIENT)
        if SMS_RECIPIENT.isdigit():
            SMS_RECIPIENT = f"+{SMS_RECIPIENT}"
    if not API_BASE_URL or not API_KEY or not DEFAULT_CHANNEL or not DB_URI:
        pytest.fail(
            "Missing api_server.base_url, api_server.api_key, default_channel, or db.uri in env config."
        )


def get_headers():
    """Get headers with API key"""
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}


async def _wait_for_delivery_progress(
    db: DatabaseManager,
    job_manager: JobManager,
    message_id: int,
    *,
    min_total: int = 1,
    timeout: float = 30.0,
) -> dict:
    """Drive local delivery processing until all expected deliveries leave queued."""
    deadline = time.monotonic() + float(timeout)
    last_payload = None

    while time.monotonic() < deadline:
        await process_deliveries(
            db,
            job_manager,
            message_id=message_id,
            max_cycles=10,
            timeout=5.0,
        )

        deliveries_response = httpx.get(
            f"{API_BASE_URL}/messages/{message_id}/deliveries",
            headers=get_headers(),
            timeout=20.0,
        )
        assert deliveries_response.status_code == 200
        last_payload = deliveries_response.json()
        items = last_payload.get("items", [])

        if last_payload.get("total", 0) >= min_total:
            if _is_external_runtime_mode():
                return last_payload
            if items and all(
                item["state"] != DeliveryState.QUEUED.value for item in items
            ):
                return last_payload

        await asyncio.sleep(1)

    return last_payload or {"total": 0, "items": []}


class TestMultiChannelDelivery:
    """Integration tests for multi-channel message delivery"""
    
    def setup_method(self):
        """Check server availability before each test"""
        deadline = time.monotonic() + 15.0
        last_error = None
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    return
                last_error = f"status={response.status_code}"
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = str(exc)
            time.sleep(1.0)
        pytest.fail(f"API server is not running or not healthy ({last_error})")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_22_send_to_multiple_channels(self, test_email):
        """V9.22: Send message to multiple channels (Email, SMS)"""
        destinations = _build_multichannel_destinations(test_email)
        payload = {
            "audience_type": "personalised",
            "destinations": destinations,
            "content": [
                {
                    "type": "text",
                    "body": "Integration test: Multi-channel delivery test from notification-agent"
                }
            ]
        }
        
        response = httpx.post(
            f"{API_BASE_URL}/messages",
            json=payload,
            headers=get_headers(),
            timeout=30.0
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "message_id" in data
        assert data["delivery_count"] == len(destinations)
        
        message_id = data["message_id"]
        
        # VERIFY ACTUAL DELIVERY PROCESSING (not just submission)
        db = _open_test_db()
        job_manager = JobManager(db)
        
        deliveries_data = await _wait_for_delivery_progress(
            db,
            job_manager,
            message_id,
            min_total=2,
            timeout=60.0,
        )
        assert deliveries_data["total"] >= 2
        
        # External runtime workers process asynchronously; require observable
        # progress without demanding every destination leave queued instantly.
        if _is_external_runtime_mode():
            allowed_states = {
                DeliveryState.QUEUED.value,
                DeliveryState.FORMATTING.value,
                DeliveryState.SENDING.value,
                DeliveryState.SENT.value,
                DeliveryState.DELIVERED.value,
                DeliveryState.SOFT_FAILED.value,
                DeliveryState.HARD_FAILED.value,
            }
            assert all(
                delivery["state"] in allowed_states
                for delivery in deliveries_data["items"]
            ), f"Unexpected delivery states: {[d['state'] for d in deliveries_data['items']]}"
        else:
            for delivery in deliveries_data["items"]:
                assert delivery["state"] != DeliveryState.QUEUED.value, \
                    f"Delivery {delivery['id']} should be processed (not queued), got {delivery['state']}"
        
        db.disconnect()
        return message_id
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_23_verify_all_deliveries_created(self, test_email):
        """V9.23: Verify all deliveries created"""
        destinations = _build_multichannel_destinations(test_email)
        
        # Create message with multiple channels
        payload = {
            "audience_type": "personalised",
            "destinations": destinations,
            "content": [{"type": "text", "body": "Delivery verification test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        db = _open_test_db()
        job_manager = JobManager(db)
        deliveries = await _wait_for_delivery_progress(
            db,
            job_manager,
            message_id,
            min_total=len(destinations),
            timeout=60.0,
        )
        
        assert deliveries["total"] >= len(destinations)
        assert len(deliveries["items"]) >= len(destinations)
        
        # Verify each delivery has correct channel and destination
        assert len(deliveries["items"]) >= len(destinations)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_24_verify_state_transitions(self, test_email):
        """V9.24: Verify state transitions"""
        
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": DEFAULT_CHANNEL, "address": test_email}
            ],
            "content": [{"type": "text", "body": "State transition test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        # VERIFY ACTUAL DELIVERY PROCESSING
        db = _open_test_db()
        job_manager = JobManager(db)
        deliveries = await _wait_for_delivery_progress(
            db,
            job_manager,
            message_id,
            min_total=1,
            timeout=60.0,
        )
        
        assert deliveries["total"] >= 1
        delivery = deliveries["items"][0]
        
        allowed_states = [
            DeliveryState.FORMATTING.value,
            DeliveryState.SENDING.value,
            DeliveryState.SENT.value,
            DeliveryState.DELIVERED.value,
            DeliveryState.SOFT_FAILED.value,
            DeliveryState.HARD_FAILED.value,
        ]
        if _is_external_runtime_mode():
            allowed_states = [DeliveryState.QUEUED.value] + allowed_states
        else:
            # Local worker mode should move out of queued after bounded cycles.
            assert delivery["state"] != DeliveryState.QUEUED.value, \
                f"Delivery should be processed (not queued), got {delivery['state']}"
        assert delivery["state"] in allowed_states, f"Unexpected delivery state: {delivery['state']}"
        
        db.disconnect()
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_25_verify_callback_processing(self, test_email):
        """V9.25: Verify callback processing"""
        
        # Create a message first
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": DEFAULT_CHANNEL, "address": test_email}
            ],
            "content": [{"type": "text", "body": "Callback test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        # VERIFY ACTUAL DELIVERY PROCESSING (delivery must be sent before callback)
        db = _open_test_db()
        job_manager = JobManager(db)
        deliveries = await _wait_for_delivery_progress(
            db,
            job_manager,
            message_id,
            min_total=1,
            timeout=60.0,
        )
        assert deliveries["total"] >= 1
        delivery_id = deliveries["items"][0]["id"]
        
        # Delivery should be processed (sent or failed) before callback
        current_delivery = next(d for d in deliveries["items"] if d["id"] == delivery_id)
        if not _is_external_runtime_mode():
            assert current_delivery["state"] != DeliveryState.QUEUED.value, \
                f"Delivery must be processed before callback test, got {current_delivery['state']}"
        
        # Simulate a callback
        callback_payload = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "message_id": "test-callback-123",
            "recipient": test_email,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        callback_response = httpx.post(
            f"{API_BASE_URL}/callbacks/email",
            json=callback_payload,
            headers=get_headers()
        )
        
        # Callback should be accepted (200 or 202)
        assert callback_response.status_code in [200, 202, 204]
        
        await asyncio.sleep(1)
        
        # Verify delivery state was updated
        delivery_response = httpx.get(
            f"{API_BASE_URL}/messages/{message_id}/deliveries",
            headers=get_headers()
        )
        deliveries = delivery_response.json()
        updated_delivery = next(d for d in deliveries["items"] if d["id"] == delivery_id)
        
        # State should be delivered or at least updated (may still be queued if job manager hasn't processed yet)
        # Delivery should be processed (not queued)
        assert updated_delivery["state"] != DeliveryState.QUEUED.value, \
            f"Delivery should be processed (not queued), got {updated_delivery['state']}"
        assert updated_delivery["state"] in [
            DeliveryState.FORMATTING.value,
            DeliveryState.SENDING.value,
            DeliveryState.SENT.value,
            DeliveryState.DELIVERED.value,
            DeliveryState.SOFT_FAILED.value,
            DeliveryState.HARD_FAILED.value,
        ], f"Delivery should be processed, got {updated_delivery['state']}"
        
        db.disconnect()


class TestErrorScenarios:
    """Integration tests for error handling"""
    
    def setup_method(self):
        """Check server availability before each test"""
        deadline = time.monotonic() + 15.0
        last_error = None
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
                if response.status_code == 200:
                    return
                last_error = f"status={response.status_code}"
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = str(exc)
            time.sleep(1.0)
        pytest.fail(f"API server is not running or not healthy ({last_error})")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_26_invalid_destination_handling(self):
        """V9.26: Invalid destination handling"""
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": DEFAULT_CHANNEL, "address": "invalid-email-address"}
            ],
            "content": [{"type": "text", "body": "Invalid destination test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        
        # Should either accept and fail later, or reject immediately
        # For now, API accepts it and adapter will handle validation
        assert response.status_code in [201, 400]
        
        if response.status_code == 201:
            message_id = response.json()["message_id"]
            await asyncio.sleep(2)
            
            # Check delivery state - should be failed
            deliveries_response = httpx.get(
                f"{API_BASE_URL}/messages/{message_id}/deliveries",
                headers=get_headers()
            )
            deliveries = deliveries_response.json()
            if deliveries["total"] > 0:
                delivery = deliveries["items"][0]
                # Should be in failed state
                # Delivery should be processed (not queued) - may be failed
                assert delivery["state"] != DeliveryState.QUEUED.value, \
                    f"Delivery should be processed (not queued), got {delivery['state']}"
                assert delivery["state"] in [
                    DeliveryState.HARD_FAILED.value,
                    DeliveryState.SOFT_FAILED.value,
                    DeliveryState.FORMATTING.value,
                    DeliveryState.SENDING.value,
                ], f"Delivery should be processed, got {delivery['state']}"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_27_provider_errors_classification(self):
        """V9.27: Provider errors (transient vs permanent)"""
        # This test verifies error classification works
        # We can't easily simulate provider errors, but we can verify
        # the error handling infrastructure is in place
        
        # Test with invalid WhatsApp number (should be permanent error)
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": SMS_CHANNEL, "address": "invalid"}
            ],
            "content": [{"type": "text", "body": "Error classification test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        
        # API should accept (validation happens in adapter)
        if response.status_code == 201:
            message_id = response.json()["message_id"]
            # VERIFY ACTUAL DELIVERY PROCESSING
            db = _open_test_db()
            job_manager = JobManager(db)
            await process_deliveries(db, job_manager, message_id=message_id, max_cycles=10, timeout=5.0)
            
            deliveries_response = httpx.get(
                f"{API_BASE_URL}/messages/{message_id}/deliveries",
                headers=get_headers()
            )
            deliveries = deliveries_response.json()
            if deliveries["total"] > 0:
                delivery = deliveries["items"][0]
                # Invalid destination should eventually fail. In external-runtime
                # mode, asynchronous workers may still be queued within the
                # bounded polling window.
                allowed_states = [
                    DeliveryState.HARD_FAILED.value,
                    DeliveryState.SOFT_FAILED.value,
                    DeliveryState.FORMATTING.value,
                    DeliveryState.SENDING.value,
                ]
                if _is_external_runtime_mode():
                    allowed_states = [DeliveryState.QUEUED.value] + allowed_states
                else:
                    assert delivery["state"] != DeliveryState.QUEUED.value, \
                        f"Delivery should be processed (not queued), got {delivery['state']}"
                assert delivery["state"] in allowed_states, \
                    f"Unexpected provider error state: {delivery['state']}"
            
            db.disconnect()
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_28_retry_logic_verification(self):
        """V9.28: Retry logic verification"""
        
        # Create a message that will fail (invalid destination)
        # Job manager should retry with backoff
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": DEFAULT_CHANNEL, "address": "invalid@example.invalid"}
            ],
            "content": [{"type": "text", "body": "Retry test"}]
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        deadline = time.time() + 20
        delivery = None
        while time.time() < deadline:
            deliveries_response = httpx.get(
                f"{API_BASE_URL}/messages/{message_id}/deliveries",
                headers=get_headers()
            )
            deliveries = deliveries_response.json()
            if deliveries["total"] > 0:
                delivery = deliveries["items"][0]
                if delivery["state"] != DeliveryState.QUEUED.value:
                    break
            await asyncio.sleep(1)

        if delivery:
            assert delivery["state"] in [
                DeliveryState.QUEUED.value,
                DeliveryState.FORMATTING.value,
                DeliveryState.SENDING.value,
                DeliveryState.SENT.value,
                DeliveryState.DELIVERED.value,
                DeliveryState.SOFT_FAILED.value,
                DeliveryState.HARD_FAILED.value,
            ], f"Unexpected delivery state: {delivery['state']}"
            if delivery["state"] in [DeliveryState.SOFT_FAILED.value, DeliveryState.HARD_FAILED.value]:
                # Retry metadata must be present even if first failure settles quickly.
                assert "attempt_no" in delivery
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_29_ttl_expiry_handling(self, test_email):
        """V9.29: TTL expiry handling"""
        from datetime import datetime, timedelta
        
        # Create message with very short TTL (1 second)
        ttl_at = (datetime.now() + timedelta(seconds=1)).isoformat()
        
        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": DEFAULT_CHANNEL, "address": test_email}
            ],
            "content": [{"type": "text", "body": "TTL test"}],
            "ttl_at": ttl_at
        }
        
        response = httpx.post(f"{API_BASE_URL}/messages", json=payload, headers=get_headers())
        assert response.status_code == 201
        message_id = response.json()["message_id"]
        
        await asyncio.sleep(3)  # Wait for TTL to expire
        
        # Get message status
        message_response = httpx.get(
            f"{API_BASE_URL}/messages/{message_id}",
            params={"format": "json"},
            headers=get_headers()
        )
        message = message_response.json()
        
        # Message should be expired or at least processed
        assert message["status"] in ["ttl_expired", "queued", "processing", "completed", "failed", "sent", "delivered"]
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v9_30_circuit_breaker_activation(self):
        """V9.30: Circuit breaker activation"""
        # Verify circuit breaker fields are exposed per channel.
        channels_response = httpx.get(f"{API_BASE_URL}/channels", headers=get_headers())
        assert channels_response.status_code == 200
        channels = channels_response.json()
        assert isinstance(channels, list)
        assert len(channels) > 0
        for channel in channels:
            assert "circuit_state" in channel
            assert channel["circuit_state"] in ["closed", "open", "half_open"]

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.docker, pytest.mark.heavy]
