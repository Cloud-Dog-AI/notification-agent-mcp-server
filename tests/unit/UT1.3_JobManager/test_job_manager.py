# @pytest.mark.req("UC-017")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Unit tests for Job Manager

Tests:
- Message enqueuing
- Idempotency
- TTL expiry
- Retry logic
- State transitions
"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

from src.database.db_manager import DatabaseManager
from src.core.job_manager import JobManager
from src.core.state_machine import DeliveryState, MessageStatus


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


@pytest.fixture
def db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    # Apply additional migrations
    migrations_dir = Path(__file__).parent.parent / "database" / "migrations"
    migration_files = [
        "002_add_message_guid.sql",
        "002_user_management_personalization.sql"
    ]
    
    for migration_file in migration_files:
        migration_path = migrations_dir / migration_file
        if migration_path.exists():
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            db_manager.connection.executescript(migration_sql)
            db_manager.connection.commit()
    
    yield db_manager
    
    db_manager.disconnect()
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def job_manager(db):
    """Create a JobManager instance"""
    return JobManager(
        db=db,
        default_ttl_hours=24,
        max_retries=3,
        backoff_base_seconds=2,
        backoff_max_seconds=60,
    )


class TestJobManager:
    """Test JobManager class"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_enqueue_message(self, job_manager, test_email_domain):
        """Test enqueuing a message"""
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test message"}],
            destinations=[
                {"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}
            ],
        )
        
        assert result["message_id"] > 0
        assert result["status"] == "queued"
        assert result["delivery_count"] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_idempotency_key(self, job_manager, test_email_domain):
        """Test idempotency key prevents duplicates"""
        # First submission
        result1 = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}],
            idempotency_key="test-key-123",
        )
        
        assert result1["status"] == "queued"
        message_id1 = result1["message_id"]
        
        # Second submission with same key
        result2 = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Different content"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("other", test_email_domain)}],
            idempotency_key="test-key-123",
        )
        
        assert result2["status"] == "duplicate"
        assert result2["message_id"] == message_id1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_ttl_expiry(self, job_manager, test_email_domain):
        """Test TTL expiry handling"""
        # Create message with TTL in the past
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Expired"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}],
            ttl_hours=-1,  # Already expired
        )
        
        message_id = result["message_id"]
        
        # Run TTL expiry check
        count = job_manager.handle_ttl_expiry()
        
        assert count == 1
        
        # Verify message status updated
        from src.database.repositories import MessageRepository
        message_repo = MessageRepository(job_manager.db)
        message = message_repo.get_by_id(message_id)
        assert message["status"] == MessageStatus.TTL_EXPIRED.value
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_handle_delivery_failure_transient(self, job_manager, test_email_domain):
        """Test handling transient delivery failure"""
        # Create a message and delivery
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}],
        )
        
        message_id = result["message_id"]
        
        # Get the delivery
        from src.database.repositories import DeliveryRepository
        delivery_repo = DeliveryRepository(job_manager.db)
        deliveries = delivery_repo.get_by_message_id(message_id)
        delivery_id = deliveries[0]["id"]
        
        # Handle failure
        job_manager.handle_delivery_failure(
            delivery_id=delivery_id,
            error="Temporary network error",
            is_transient=True,
        )
        
        # Verify delivery state
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["state"] == DeliveryState.SOFT_FAILED.value
        assert delivery["attempt_no"] == 1
        assert delivery["next_action_at"] is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_handle_delivery_failure_permanent(self, job_manager):
        """Test handling permanent delivery failure"""
        # Create a message and delivery
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[{"channel_id": 1, "destination": "invalid-email"}],
        )
        
        message_id = result["message_id"]
        
        from src.database.repositories import DeliveryRepository
        delivery_repo = DeliveryRepository(job_manager.db)
        deliveries = delivery_repo.get_by_message_id(message_id)
        delivery_id = deliveries[0]["id"]
        
        # Handle permanent failure
        job_manager.handle_delivery_failure(
            delivery_id=delivery_id,
            error="Invalid email address",
            is_transient=False,
        )
        
        # Verify delivery state
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["state"] == DeliveryState.HARD_FAILED.value
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_max_retries_reached(self, job_manager, test_email_domain):
        """Test that max retries transitions to hard_failed"""
        # Create a message and delivery
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}],
        )
        
        message_id = result["message_id"]
        
        from src.database.repositories import DeliveryRepository
        delivery_repo = DeliveryRepository(job_manager.db)
        deliveries = delivery_repo.get_by_message_id(message_id)
        delivery_id = deliveries[0]["id"]
        
        # Fail multiple times (max_retries = 3)
        for i in range(4):
            job_manager.handle_delivery_failure(
                delivery_id=delivery_id,
                error=f"Failure {i+1}",
                is_transient=True,
            )
        
        # Should be hard failed after max retries
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["state"] == DeliveryState.HARD_FAILED.value
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_mark_delivery_sent(self, job_manager, test_email_domain):
        """Test marking delivery as sent"""
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("test", test_email_domain)}],
        )
        
        message_id = result["message_id"]
        
        from src.database.repositories import DeliveryRepository
        delivery_repo = DeliveryRepository(job_manager.db)
        deliveries = delivery_repo.get_by_message_id(message_id)
        delivery_id = deliveries[0]["id"]
        
        job_manager.mark_delivery_sent(
            delivery_id=delivery_id,
            provider_tracking_id="track-123",
        )
        
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["state"] == DeliveryState.SENT.value
        assert delivery["provider_tracking_id"] == "track-123"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_cancel_message(self, job_manager, test_email_domain):
        """Test cancelling a message"""
        result = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Test"}],
            destinations=[
                {"channel_id": 1, "destination": _synthetic_email("test1", test_email_domain)},
                {"channel_id": 1, "destination": _synthetic_email("test2", test_email_domain)},
            ],
        )
        
        message_id = result["message_id"]
        
        # Cancel the message
        cancelled_count = job_manager.cancel_message(message_id)
        assert cancelled_count == 2
        
        # Verify deliveries are cancelled
        from src.database.repositories import DeliveryRepository
        delivery_repo = DeliveryRepository(job_manager.db)
        deliveries = delivery_repo.get_by_message_id(message_id)
        
        for delivery in deliveries:
            assert delivery["state"] == DeliveryState.CANCELLED.value
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_pending_deliveries(self, job_manager, test_email_domain):
        """Test getting pending deliveries"""
        # Create some messages
        for i in range(3):
            job_manager.enqueue_message(
                created_by="test_user",
                content=[{"type": "text", "body": f"Test {i}"}],
                destinations=[{"channel_id": 1, "destination": _synthetic_email(f"test{i}", test_email_domain)}],
            )
        
        pending = job_manager.get_pending_deliveries(limit=10)
        assert len(pending) >= 3
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_get_pending_deliveries_prioritizes_fresh_attempts(self, job_manager, test_email_domain):
        """Fresh queued deliveries should be processed before retry backlog."""
        from src.database.repositories import DeliveryRepository

        # Create an older delivery that will become a retry candidate.
        older = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Older delivery"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("older", test_email_domain)}],
        )
        older_delivery = DeliveryRepository(job_manager.db).get_by_message_id(older["message_id"])[0]
        older_id = older_delivery["id"]

        # Move older delivery into soft_failed with attempt_no > 0 and ready-to-run next_action_at.
        job_manager.handle_delivery_failure(
            delivery_id=older_id,
            error="Transient failure for ordering test",
            is_transient=True,
        )
        job_manager.db.execute(
            "UPDATE deliveries SET next_action_at = CURRENT_TIMESTAMP WHERE id = ?",
            (older_id,),
        )
        job_manager.db.commit()

        # Create a fresh queued delivery after retry candidate exists.
        fresh = job_manager.enqueue_message(
            created_by="test_user",
            content=[{"type": "text", "body": "Fresh delivery"}],
            destinations=[{"channel_id": 1, "destination": _synthetic_email("fresh", test_email_domain)}],
        )
        fresh_id = DeliveryRepository(job_manager.db).get_by_message_id(fresh["message_id"])[0]["id"]

        pending = job_manager.get_pending_deliveries(limit=10)
        order = {int(d["id"]): idx for idx, d in enumerate(pending)}

        assert fresh_id in order
        assert older_id in order
        assert order[fresh_id] < order[older_id]


class TestStateMachine:
    """Test state machine logic"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delivery_state_is_terminal(self):
        """Test terminal state detection.

        Note: HARD_FAILED → DEAD_LETTERED (W28A-659), DEAD_LETTERED → ARCHIVED,
        READ → ARCHIVED, TTL_EXPIRED → ARCHIVED, CANCELLED → ARCHIVED.
        Only ARCHIVED has no outgoing transitions and is truly terminal.
        """
        assert DeliveryState.ARCHIVED.is_terminal() == True
        # READ can transition to ARCHIVED, so it is not terminal
        assert DeliveryState.READ.is_terminal() == False
        # HARD_FAILED → dead_lettered is valid (W28A-659 dead-letter support)
        assert DeliveryState.HARD_FAILED.is_terminal() == False
        # TTL_EXPIRED and CANCELLED can transition to archived in the base model
        assert DeliveryState.QUEUED.is_terminal() == False
        assert DeliveryState.SENT.is_terminal() == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delivery_state_is_retryable(self):
        """Test retryable state detection"""
        assert DeliveryState.SOFT_FAILED.is_retryable() == True
        assert DeliveryState.QUEUED.is_retryable() == True
        assert DeliveryState.HARD_FAILED.is_retryable() == False
        assert DeliveryState.SENT.is_retryable() == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_valid_state_transitions(self):
        """Test valid state transitions"""
        # queued can transition to formatting
        assert DeliveryState.QUEUED.can_transition_to(DeliveryState.FORMATTING) == True
        
        # sent can transition to accepted
        assert DeliveryState.SENT.can_transition_to(DeliveryState.ACCEPTED) == True
        
        # delivered can transition to read
        assert DeliveryState.DELIVERED.can_transition_to(DeliveryState.READ) == True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_invalid_state_transitions(self):
        """Test invalid state transitions"""
        # queued cannot jump to delivered
        assert DeliveryState.QUEUED.can_transition_to(DeliveryState.DELIVERED) == False
        
        # terminal states cannot transition
        assert DeliveryState.READ.can_transition_to(DeliveryState.SENT) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
