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
Unit tests for Database Layer

Tests:
- Database connection
- Schema initialization
- Repository CRUD operations
- Transaction handling
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    MessageRepository,
    DeliveryRepository,
    ChannelRepository,
    UserRepository,
)


@pytest.fixture
def db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    yield db_manager
    
    db_manager.disconnect()
    try:
        os.unlink(db_path)
    except:
        pass


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


class TestDatabaseManager:
    """Test DatabaseManager class"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_connection(self, db):
        """Test database connection"""
        assert db.connection is not None
        assert db.health_check() == True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_execute_query(self, db):
        """Test executing a query"""
        result = db.execute("SELECT 1 as test")
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetchone(self, db):
        """Test fetchone method"""
        row = db.fetchone("SELECT 1 as test")
        assert row is not None
        assert row["test"] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetchall(self, db):
        """Test fetchall method"""
        rows = db.fetchall("SELECT 1 as test UNION SELECT 2")
        assert len(rows) == 2
        assert rows[0]["test"] == 1
        assert rows[1]["test"] == 2


class TestMessageRepository:
    """Test MessageRepository"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_create_message(self, db):
        """Test creating a message"""
        repo = MessageRepository(db)
        
        message_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
            ttl_at=datetime.now() + timedelta(hours=24),
        )
        
        assert message_id is not None
        assert message_id > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_message_by_id(self, db):
        """Test retrieving message by ID"""
        repo = MessageRepository(db)
        
        # Create a message
        message_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        # Retrieve it
        message = repo.get_by_id(message_id)
        assert message is not None
        assert message["id"] == message_id
        assert message["created_by"] == "test_user"
        assert message["status"] == "queued"
        repo.delete(message_id)
        assert repo.get_by_id(message_id) is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_message_by_idempotency_key(self, db):
        """Test retrieving message by idempotency key"""
        repo = MessageRepository(db)
        
        # Create with idempotency key
        message_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
            idempotency_key="test-key-123",
        )
        
        # Retrieve by key
        message = repo.get_by_idempotency_key("test-key-123")
        assert message is not None
        assert message["id"] == message_id
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_update_status(self, db):
        """Test updating message status"""
        repo = MessageRepository(db)
        
        message_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        repo.update_status(message_id, "completed")
        
        message = repo.get_by_id(message_id)
        assert message["status"] == "completed"
        repo.delete(message_id)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_expired_messages(self, db):
        """Test getting expired messages"""
        repo = MessageRepository(db)
        
        # Create expired message (TTL in the past)
        expired_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Expired"}]',
            ttl_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # Create non-expired message
        valid_id = repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Valid"}]',
            ttl_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        
        expired = repo.get_expired()
        expired_ids = [msg["id"] for msg in expired]
        
        assert expired_id in expired_ids
        assert valid_id not in expired_ids


class TestDeliveryRepository:
    """Test DeliveryRepository"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_create_delivery(self, db, test_email_domain):
        """Test creating a delivery"""
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        delivery_repo = DeliveryRepository(db)
        
        # Create message
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        # Get a channel
        channels = channel_repo.list_all()
        channel_id = channels[0]["id"]
        
        # Create delivery
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=_synthetic_email("test", test_email_domain),
        )
        
        assert delivery_id is not None
        assert delivery_id > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_delivery_by_id(self, db, test_email_domain):
        """Test retrieving delivery by ID"""
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        delivery_repo = DeliveryRepository(db)
        
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        channels = channel_repo.list_all()
        channel_id = channels[0]["id"]
        
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=_synthetic_email("test", test_email_domain),
        )
        
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery is not None
        assert delivery["destination"] == _synthetic_email("test", test_email_domain)
        assert delivery["state"] == "queued"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_update_delivery_state(self, db, test_email_domain):
        """Test updating delivery state"""
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        delivery_repo = DeliveryRepository(db)
        
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        channels = channel_repo.list_all()
        channel_id = channels[0]["id"]
        
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=_synthetic_email("test", test_email_domain),
        )
        
        delivery_repo.update_state(
            delivery_id=delivery_id,
            state="sent",
            provider_tracking_id="track-123",
        )
        
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["state"] == "sent"
        assert delivery["provider_tracking_id"] == "track-123"
        assert delivery["sent_at"] is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_increment_attempt(self, db, test_email_domain):
        """Test incrementing attempt counter"""
        message_repo = MessageRepository(db)
        channel_repo = ChannelRepository(db)
        delivery_repo = DeliveryRepository(db)
        
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json='[{"type":"text","body":"Test"}]',
        )
        
        channels = channel_repo.list_all()
        channel_id = channels[0]["id"]
        
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=_synthetic_email("test", test_email_domain),
        )
        
        delivery_repo.increment_attempt(delivery_id)
        
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["attempt_no"] == 1
        
        delivery_repo.increment_attempt(delivery_id)
        delivery = delivery_repo.get_by_id(delivery_id)
        assert delivery["attempt_no"] == 2


class TestChannelRepository:
    """Test ChannelRepository"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_list_channels(self, db, default_channel, test_config):
        """Test listing channels"""
        repo = ChannelRepository(db)
        
        channels = repo.list_all()
        assert len(channels) >= 2  # Should have default channels
        
        # Check default channels exist
        names = [ch["name"] for ch in channels]
        sms_channel = test_config.get("test.default_sms_channel")
        if not sms_channel:
            pytest.fail("test.default_sms_channel not configured. Check your env file.")
        assert default_channel in names
        assert sms_channel in names
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_channel_by_name(self, db, default_channel):
        """Test getting channel by name"""
        repo = ChannelRepository(db)
        
        channel = repo.get_by_name(default_channel)
        assert channel is not None
        assert channel["type"] in {"smtp", "loopback"}
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_create_channel(self, db, smtp_config):
        """Test creating a channel"""
        repo = ChannelRepository(db)
        
        channel_id = repo.create(
            name="test_channel",
            channel_type="smtp",
            enabled=True,
            config_json=json.dumps({"host": smtp_config.get("host")}),
        )
        
        assert channel_id > 0
        
        channel = repo.get_by_id(channel_id)
        assert channel["name"] == "test_channel"
        # CRUD delete
        db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        assert repo.get_by_id(channel_id) is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_update_channel(self, db, default_channel):
        """Test updating channel"""
        repo = ChannelRepository(db)
        
        channel = repo.get_by_name(default_channel)
        channel_id = channel["id"]
        
        repo.update(channel_id, {"enabled": False})
        
        updated = repo.get_by_id(channel_id)
        assert updated["enabled"] == 0  # SQLite stores as integer


class TestUserRepository:
    """Test UserRepository"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_default_admin_user(self, db):
        """Test that default admin user is not seeded by default"""
        repo = UserRepository(db)
        
        user = repo.get_by_username("admin")
        assert user is None, "Default admin should not be seeded without explicit config"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_create_user(self, db, test_email_domain):
        """Test creating a user"""
        repo = UserRepository(db)
        
        user_id = repo.create(
            username="testuser",
            email=_synthetic_email("test", test_email_domain),
            password_hash="hashed_password",
            role="viewer",
        )
        
        assert user_id > 0
        
        user = repo.get_by_username("testuser")
        assert user is not None
        assert user["email"] == _synthetic_email("test", test_email_domain)
        repo.delete(user["id"])
        assert repo.get_by_username("testuser") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
