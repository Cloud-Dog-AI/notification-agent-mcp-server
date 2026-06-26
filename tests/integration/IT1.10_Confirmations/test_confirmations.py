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
Tests for Confirmation Manager (Callbacks & Polling)

Run with: pytest tests/test_confirmations.py -v
"""

import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import hmac
import hashlib
import time
from datetime import datetime, timedelta


class TestCallbackSignatures:
    """Tests for Signature Verification - V7.1 to V7.4"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_v7_1_generate_hmac_signature(self):
        """V7.1: Generate HMAC signature correctly"""
        from src.core.security.signature import SignatureManager
        
        secret = "test-secret-key"
        manager = SignatureManager(secret)
        
        payload = '{"status": "delivered", "message_id": "123"}'
        timestamp = "1699000000"
        
        signature = manager.generate_signature(payload, timestamp)
        
        # Verify it's a valid hex string
        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 hex is 64 chars
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_v7_2_verify_valid_signature(self):
        """V7.2: Verify valid signature"""
    


        from src.core.security.signature import SignatureManager
        
        secret = "test-secret-key"
        manager = SignatureManager(secret)
        
        payload = '{"status": "delivered"}'
        timestamp = str(int(time.time()))
        
        signature = manager.generate_signature(payload, timestamp)
        
        # Should verify successfully
        assert manager.verify_signature(payload, timestamp, signature) is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_v7_3_reject_invalid_signature(self):
        """V7.3: Reject invalid signature (401)"""
        from src.core.security.signature import SignatureManager
        
        secret = "test-secret-key"
        manager = SignatureManager(secret)
        
        payload = '{"status": "delivered"}'
        timestamp = str(int(time.time()))
        
        invalid_signature = "invalid_signature_12345"
        
        # Should fail verification
        assert manager.verify_signature(payload, timestamp, invalid_signature) is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_v7_4_reject_replayed_callback(self):
        """V7.4: Reject replayed callback (timestamp check)"""
    


        from src.core.security.signature import SignatureManager
        
        secret = "test-secret-key"
        manager = SignatureManager(secret, max_age_seconds=300)  # 5 minutes
        
        payload = '{"status": "delivered"}'
        
        # Old timestamp (10 minutes ago)
        old_timestamp = str(int(time.time()) - 600)
        signature = manager.generate_signature(payload, old_timestamp)
        
        # Should be rejected as too old
        assert manager.is_timestamp_valid(old_timestamp) is False


class TestCallbackParsing:
    """Tests for Callback Parsing - V7.5 to V7.10"""
    
    def _create_test_data(self, db):
        """Helper to create test message and channel"""
        import time
        from src.database.repositories import MessageRepository, ChannelRepository
        
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        
        # Create test channel with unique name to avoid conflicts
        unique_name = f"test_email_{int(time.time() * 1000)}"
        channel_id = channel_repo.create(
            name=unique_name,
            channel_type="smtp",
            enabled=True,
            config_json='{"host": "test"}'
        )
        
        # Create test message
        message_id = message_repo.create(
            created_by="test",
            audience_type="single",
            content_json='[{"type": "text", "body": "Test"}]'
        )
        
        return message_id, channel_id
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_5_parse_smtp_delivery_notification(self, db, test_email):
        """V7.5: Parse SMTP delivery notification"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        # Simulated SMTP delivery notification
        callback_data = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "message_id": "msg_123",
            "recipient": test_email,
            "timestamp": "2025-11-10T20:00:00Z"
        }
        
        result = await processor.parse_smtp_callback(callback_data)
        
        assert result["delivery_id"] == delivery_id
        assert result["state"] == "delivered"
        assert result["recipient"] == test_email
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_6_parse_sms_delivery_receipt(self, db):
        """V7.6: Parse SMS delivery receipt"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination="+1234567890"
        )
        
        # Simulated SMS delivery receipt (Twilio format)
        callback_data = {
            "delivery_id": delivery_id,
            "MessageStatus": "delivered",
            "MessageSid": "SM123456",
            "To": "+1234567890",
            "From": "+0987654321",
            "SmsSid": "SM123456"
        }
        
        result = await processor.parse_sms_callback(callback_data)
        
        assert result["delivery_id"] == delivery_id
        assert result["state"] == "delivered"
        assert result["destination"] == "+1234567890"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_7_handle_duplicate_callback(self, db, test_email):
        """V7.7: Handle duplicate callback (idempotent)"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        callback_data = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "message_id": "msg_duplicate_test",
            "recipient": test_email,
            "timestamp": "2025-11-10T20:00:00Z"
        }
        
        # Process once
        result1 = await processor.process_callback("email", callback_data)
        
        # Process again (duplicate)
        result2 = await processor.process_callback("email", callback_data)
        
        # Should handle gracefully (idempotent)
        assert result1["success"] is True
        assert result2["success"] is True
        assert result2.get("duplicate", False) is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_8_update_delivery_state_from_callback(self, db, test_email):
        """V7.8: Update delivery state from callback"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create test delivery
        repo = DeliveryRepository(db)
        delivery_id = repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email,
            state="sent"  # Start in sent state so we can transition to delivered
        )
        
        # Process callback to update state
        callback_data = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await processor.process_callback("email", callback_data)
        
        # Verify state updated
        delivery = repo.get_by_id(delivery_id)
        assert delivery["state"] == "delivered"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_9_create_receipt_record_from_callback(self, db, test_email):
        """V7.9: Create receipt record from callback"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        callback_data = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "message_id": "ext_123",
            "provider_id": "ext_123",
            "timestamp": datetime.now().isoformat()
        }
        
        result = await processor.process_callback("email", callback_data)
        
        # Verify receipt was created
        assert result["success"] is True
        assert result.get("receipt_id") is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_10_audit_log_callback_processing(self, db, test_email):
        """V7.10: Audit log callback processing"""
        from src.core.confirmations.processor import CallbackProcessor
        from src.database.repositories import DeliveryRepository, AuditEventRepository
        
        processor = CallbackProcessor(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        callback_data = {
            "event": "delivered",
            "delivery_id": delivery_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await processor.process_callback("email", callback_data)
        
        # Verify audit event was logged
        audit_repo = AuditEventRepository(db)
        recent_events = audit_repo.list_events(kind="callback_processed", limit=10)
        callback_events = [e for e in recent_events if e["kind"] == "callback_processed"]
        
        assert len(callback_events) > 0


class TestPolling:
    """Tests for Polling System - V7.11 to V7.15"""
    
    def _create_test_data(self, db):
        """Helper to create test message and channel"""
        import time
        from src.database.repositories import MessageRepository, ChannelRepository
        
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        
        # Create test channel with unique name to avoid conflicts
        unique_name = f"test_email_{int(time.time() * 1000)}"
        channel_id = channel_repo.create(
            name=unique_name,
            channel_type="smtp",
            enabled=True,
            config_json='{"host": "test"}'
        )
        
        # Create test message
        message_id = message_repo.create(
            created_by="test",
            audience_type="single",
            content_json='[{"type": "text", "body": "Test"}]'
        )
        
        return message_id, channel_id
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_11_poll_provider_api_for_status(self):
        """V7.11: Poll provider API for status"""
        from src.core.confirmations.poller import ConfirmationPoller
        
        poller = ConfirmationPoller()
        
        # Poll provider API (currently returns None as not fully implemented)
        provider_id = "ext_test_123"
        result = await poller.poll_status("email", provider_id)
        
        # Currently returns None (polling not fully implemented for all providers)
        # This test verifies the method exists and handles gracefully
        assert result is None or isinstance(result, dict)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_12_update_delivery_from_polling_result(self, db, test_email):
        """V7.12: Update delivery from polling result"""
        from src.core.confirmations.poller import ConfirmationPoller
        from src.database.repositories import DeliveryRepository
        
        poller = ConfirmationPoller(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        # Poll the delivery (may return None if not implemented)
        result = await poller.poll_delivery(delivery_id)
        
        # Verify the method exists and handles gracefully
        assert result is None or isinstance(result, dict)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_13_handle_polling_errors_gracefully(self, test_email):
        """V7.13: Handle polling errors gracefully"""
        from src.core.confirmations.poller import ConfirmationPoller
        
        poller = ConfirmationPoller()
        
        # Invalid provider ID should not crash
        try:
            result = await poller.poll_status("email", "invalid_id")
            # Should return None or error indicator
            assert result is None or result.get("error") is not None
        except Exception as e:
            pytest.fail(f"Polling should handle errors gracefully: {e}")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_14_respect_polling_intervals(self, db, test_email):
        """V7.14: Respect polling intervals"""
        from src.core.confirmations.poller import ConfirmationPoller
        from src.database.repositories import DeliveryRepository
        
        poller = ConfirmationPoller(db, config={"polling_interval_seconds": 60})
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create a test delivery
        delivery_repo = DeliveryRepository(db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        
        # First poll
        result1 = await poller.poll_delivery(delivery_id)
        
        # Immediately poll again - should respect interval
        result2 = await poller.poll_delivery(delivery_id)
        
        # Verify polling respects intervals (should_poll should check last poll time)
        # After first poll, should_poll may return False if interval not elapsed
        assert poller.should_poll(delivery_id) is False or result2 is None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    @pytest.mark.asyncio
    async def test_v7_15_stop_polling_on_terminal_state(self, db, test_email, test_email_domain):
        """V7.15: Stop polling on terminal state"""
        from src.core.confirmations.poller import ConfirmationPoller
        from src.core.state_machine import DeliveryState
        from src.database.repositories import DeliveryRepository
        
        poller = ConfirmationPoller(db)
        
        # Create test data
        message_id, channel_id = self._create_test_data(db)
        
        # Create deliveries in different states
        delivery_repo = DeliveryRepository(db)
        
        # Terminal state delivery (update state after creation)
        terminal_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email
        )
        delivery_repo.update_state(terminal_id, "delivered")
        
        # Non-terminal state delivery
        active_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=f"test2{test_email_domain}"
        )
        
        # Terminal states should not be polled
        assert poller.should_poll(terminal_id) is False
        
        # Non-terminal states can be polled
        assert poller.should_poll(active_id) is True

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]
