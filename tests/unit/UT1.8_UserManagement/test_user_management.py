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
Tests for User Management (T16)

Tests: BR1.2, UC1.4

V16.1-V16.15: User Management & Destinations
"""

import pytest
import json
from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    UserRepository,
    UserDestinationRepository,
    UserKeywordRepository
)
from src.core.users.user_manager import UserManager


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


@pytest.fixture
def db():
    """Database fixture"""
    import os
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = DatabaseManager(f"sqlite3://{db_path}")
    db.connect()
    # Initialize schema
    try:
        db.initialize_schema()
    except:
        pass
    yield db
    db.disconnect()
    # Clean up
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def user_repo(db):
    """UserRepository fixture"""
    return UserRepository(db)


@pytest.fixture
def dest_repo(db):
    """UserDestinationRepository fixture"""
    return UserDestinationRepository(db)


@pytest.fixture
def keyword_repo(db):
    """UserKeywordRepository fixture"""
    return UserKeywordRepository(db)


@pytest.fixture
def user_manager(db):
    """UserManager fixture"""
    return UserManager(db)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-021")


@pytest.fixture
def test_user(user_repo, test_email_domain):
    """Create a test user"""
    import hashlib
    existing = user_repo.get_by_username("testuser")
    if existing:
        return existing["id"]
    password_hash = hashlib.sha256("testpass".encode()).hexdigest()
    user_id = user_repo.create(
        username="testuser",
        email=_synthetic_email("test", test_email_domain),
        password_hash=password_hash,
        display_name="Test User",
        language="en",
        preferred_channel="email",
        content_style="short"
    )
    return user_id


class TestUserRepository:
    """V16.1-V16.5: UserRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_1_create_user_with_preferences(self, user_repo, test_email_domain):
        """V16.1: Create user with preferences"""
        import hashlib
        import uuid
        password_hash = hashlib.sha256("pass".encode()).hexdigest()
        unique_suffix = uuid.uuid4().hex[:8]
        username = f"fred_{unique_suffix}"
        email = _synthetic_email(f"fred_{unique_suffix}", test_email_domain)
        user_id = user_repo.create(
            username=username,
            email=email,
            password_hash=password_hash,
            display_name="Fred Smith",
            language="fr",
            preferred_channel="whatsapp",
            content_style="short",
            timezone="Europe/Paris"
        )
        assert user_id > 0
        
        user = user_repo.get_by_id(user_id)
        assert user["username"] == username
        assert user["display_name"] == "Fred Smith"
        assert user["language"] == "fr"
        assert user["preferred_channel"] == "whatsapp"
        assert user["content_style"] == "short"
        assert user["timezone"] == "Europe/Paris"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_2_get_user_by_email(self, user_repo, test_user, test_email_domain):
        """V16.2: Get user by email"""
        user = user_repo.get_by_email(_synthetic_email("test", test_email_domain))
        assert user is not None
        assert user["username"] == "testuser"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_3_get_user_by_display_name(self, user_repo, test_user):
        """V16.3: Get user by display name"""
        user = user_repo.get_by_display_name("Test User")
        assert user is not None
        assert user["username"] == "testuser"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_4_search_users(self, user_repo, test_user):
        """V16.4: Search users"""
        users = user_repo.search("test", limit=10)
        assert len(users) >= 1
        assert any(u["username"] == "testuser" for u in users)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_5_update_user_preferences(self, user_repo, test_user):
        """V16.5: Update user preferences"""
        user_repo.update_preferences(
            user_id=test_user,
            language="de",
            preferred_channel="sms",
            content_style="detailed"
        )
        
        user = user_repo.get_by_id(test_user)
        assert user["language"] == "de"
        assert user["preferred_channel"] == "sms"
        assert user["content_style"] == "detailed"


class TestUserDestinationRepository:
    """V16.6-V16.10: UserDestinationRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_6_create_destination(self, dest_repo, test_user, test_email_domain):
        """V16.6: Create user destination"""
        dest_id = dest_repo.create(
            user_id=test_user,
            channel_type="email",
            destination=_synthetic_email("test", test_email_domain),
            is_primary=True
        )
        assert dest_id > 0
        
        dest = dest_repo.get_by_id(dest_id)
        assert dest["user_id"] == test_user
        assert dest["channel_type"] == "email"
        assert dest["destination"] == _synthetic_email("test", test_email_domain)
        assert dest["is_primary"] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_7_get_destinations_by_user(self, dest_repo, test_user, test_email_domain):
        """V16.7: Get destinations by user"""
        dest_repo.create(test_user, "email", _synthetic_email("email1", test_email_domain), is_primary=True)
        dest_repo.create(test_user, "sms", "+447700900123")
        dest_repo.create(test_user, "whatsapp", "+447700900123")
        
        destinations = dest_repo.get_by_user_id(test_user)
        assert len(destinations) == 4
        channel_types = {dest["channel_type"] for dest in destinations}
        assert {"email", "sms", "whatsapp", "smtp"}.issubset(channel_types)
        
        email_dests = dest_repo.get_by_user_id(test_user, "email")
        assert len(email_dests) == 1
        assert email_dests[0]["destination"] == _synthetic_email("email1", test_email_domain)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_8_get_primary_destination(self, dest_repo, test_user, test_email_domain):
        """V16.8: Get primary destination"""
        dest_repo.create(test_user, "email", _synthetic_email("primary", test_email_domain), is_primary=True)
        dest_repo.create(test_user, "email", _synthetic_email("secondary", test_email_domain), is_primary=False)
        
        primary = dest_repo.get_primary(test_user, "email")
        assert primary is not None
        assert primary["destination"] == _synthetic_email("primary", test_email_domain)
        assert primary["is_primary"] == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_9_set_primary_destination(self, dest_repo, test_user, test_email_domain):
        """V16.9: Set primary destination"""
        dest1_id = dest_repo.create(test_user, "email", _synthetic_email("email1", test_email_domain), is_primary=True)
        dest2_id = dest_repo.create(test_user, "email", _synthetic_email("email2", test_email_domain), is_primary=False)
        
        dest_repo.set_primary(dest2_id, test_user, "email")
        
        primary = dest_repo.get_primary(test_user, "email")
        assert primary["id"] == dest2_id
        assert primary["is_primary"] == 1
        
        # Check dest1 is no longer primary
        dest1 = dest_repo.get_by_id(dest1_id)
        assert dest1["is_primary"] == 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_10_delete_destination(self, dest_repo, test_user, test_email_domain):
        """V16.10: Delete destination"""
        dest_id = dest_repo.create(test_user, "email", _synthetic_email("temp", test_email_domain))
        
        dest_repo.delete(dest_id, test_user)
        
        dest = dest_repo.get_by_id(dest_id)
        assert dest is None


class TestUserKeywordRepository:
    """V16.11-V16.13: UserKeywordRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_11_add_keyword(self, keyword_repo, test_user):
        """V16.11: Add keyword to user"""
        result = keyword_repo.add(test_user, "security")
        assert result is not None
        
        keywords = keyword_repo.get_by_user_id(test_user)
        assert len(keywords) == 1
        assert keywords[0]["keyword"] == "security"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_12_add_duplicate_keyword(self, keyword_repo, test_user):
        """V16.12: Add duplicate keyword (should be ignored)"""
        keyword_repo.add(test_user, "devops")
        result = keyword_repo.add(test_user, "devops")  # Duplicate
        assert result is None  # Already exists
        
        keywords = keyword_repo.get_by_user_id(test_user)
        assert len(keywords) == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_13_remove_keyword(self, keyword_repo, test_user):
        """V16.13: Remove keyword from user"""
        keyword_repo.add(test_user, "executive")
        keyword_repo.add(test_user, "technical")
        
        keyword_repo.remove(test_user, "executive")
        
        keywords = keyword_repo.get_by_user_id(test_user)
        assert len(keywords) == 1
        assert keywords[0]["keyword"] == "technical"


class TestUserManager:
    """V16.14-V16.15: UserManager integration tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_14_lookup_and_get_user_with_destinations(self, user_manager, test_user, test_email_domain):
        """V16.14: Lookup user and get with destinations"""
        # Add destinations
        user_manager.add_destination(test_user, "email", _synthetic_email("email", test_email_domain), is_primary=True)
        user_manager.add_destination(test_user, "whatsapp", "+447700900123")
        user_manager.add_keyword(test_user, "security")
        
        # Lookup by username
        user = user_manager.lookup_user("testuser", by="username")
        assert user is not None
        
        # Get with destinations
        user_full = user_manager.get_user_with_destinations(test_user)
        assert user_full is not None
        assert len(user_full["destinations"]) == 3
        channel_types = {dest["channel_type"] for dest in user_full["destinations"]}
        assert {"email", "whatsapp", "smtp"}.issubset(channel_types)
        assert "security" in user_full["keywords"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-021")
    
    def test_v16_15_primary_destination_management(self, user_manager, test_user, test_email_domain):
        """V16.15: Primary destination management"""
        # Add multiple email destinations
        dest1_id = user_manager.add_destination(test_user, "email", _synthetic_email("primary", test_email_domain), is_primary=True)
        dest2_id = user_manager.add_destination(test_user, "email", _synthetic_email("secondary", test_email_domain))
        
        # Get primary
        primary = user_manager.get_primary_destination(test_user, "email")
        assert primary == _synthetic_email("primary", test_email_domain)
        
        # Set new primary
        user_manager.set_primary_destination(dest2_id, test_user)
        primary = user_manager.get_primary_destination(test_user, "email")
        assert primary == _synthetic_email("secondary", test_email_domain)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
