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
Tests for Group Management (T17)

V17.1-V17.12: Groups & Group Management
"""

import pytest
import json
from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    GroupRepository,
    GroupMemberRepository,
    GroupKeywordRepository,
    UserRepository
)
from src.core.groups.group_manager import GroupManager


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
def group_repo(db):
    """GroupRepository fixture"""
    return GroupRepository(db)


@pytest.fixture
def member_repo(db):
    """GroupMemberRepository fixture"""
    return GroupMemberRepository(db)


@pytest.fixture
def keyword_repo(db):
    """GroupKeywordRepository fixture"""
    return GroupKeywordRepository(db)


@pytest.fixture
def group_manager(db):
    """GroupManager fixture"""
    return GroupManager(db)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.fixture
def test_user(db, test_email_domain):
    """Create a test user"""
    import hashlib
    user_repo = UserRepository(db)
    existing = user_repo.get_by_username("testuser")
    if existing:
        return existing["id"]
    password_hash = hashlib.sha256("testpass".encode()).hexdigest()
    user_id = user_repo.create(
        username="testuser",
        email=f"test{test_email_domain}",
        password_hash=password_hash,
        display_name="Test User"
    )
    return user_id
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.fixture
def test_group(group_repo):
    """Create a test group"""
    existing = group_repo.get_by_name("Test Group")
    if existing:
        return existing["id"]
    group_id = group_repo.create(
        name="Test Group",
        description="A test group",
        language="en",
        preferred_channel="email"
    )
    return group_id


class TestGroupRepository:
    """V17.1-V17.5: GroupRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_1_create_group(self, group_repo):
        """V17.1: Create group"""
        import time
        unique_name = f"TestGroup_{int(time.time())}"
        group_id = group_repo.create(
            name=unique_name,
            description="Administrative users",
            language="en",
            preferred_channel="email",
            content_style="detailed"
        )
        assert group_id > 0
        
        group = group_repo.get_by_id(group_id)
        assert group["name"] == unique_name
        assert group["language"] == "en"
        assert group["preferred_channel"] == "email"
        assert group["content_style"] == "detailed"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_2_get_group_by_name(self, group_repo, test_group):
        """V17.2: Get group by name"""
        group = group_repo.get_by_name("Test Group")
        assert group is not None
        assert group["id"] == test_group
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_3_list_groups(self, group_repo, test_group):
        """V17.3: List groups"""
        groups = group_repo.list_all()
        assert len(groups) >= 1
        assert any(g["name"] == "Test Group" for g in groups)
        
        # Test enabled_only
        enabled_groups = group_repo.list_all(enabled_only=True)
        assert all(g["enabled"] == 1 for g in enabled_groups)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_4_update_group(self, group_repo, test_group):
        """V17.4: Update group"""
        group_repo.update(
            group_id=test_group,
            description="Updated description",
            language="fr",
            preferred_channel="whatsapp"
        )
        
        group = group_repo.get_by_id(test_group)
        assert group["description"] == "Updated description"
        assert group["language"] == "fr"
        assert group["preferred_channel"] == "whatsapp"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_5_disable_group(self, group_repo, test_group):
        """V17.5: Disable group"""
        group_repo.update(group_id=test_group, enabled=False)
        
        group = group_repo.get_by_id(test_group)
        assert group["enabled"] == 0


class TestGroupMemberRepository:
    """V17.6-V17.9: GroupMemberRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_6_add_member(self, member_repo, test_group, test_user):
        """V17.6: Add member to group"""
        result = member_repo.add_member(test_group, test_user, role="admin")
        assert result is not None
        
        members = member_repo.get_group_members(test_group)
        assert len(members) == 1
        assert members[0]["user_id"] == test_user
        assert members[0]["role"] == "admin"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_7_add_duplicate_member(self, member_repo, test_group, test_user):
        """V17.7: Add duplicate member (should be ignored)"""
        member_repo.add_member(test_group, test_user)
        result = member_repo.add_member(test_group, test_user)  # Duplicate
        assert result is None  # Already exists
        
        members = member_repo.get_group_members(test_group)
        assert len(members) == 1
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_8_get_user_groups(self, member_repo, group_repo, test_user):
        """V17.8: Get user groups"""
        group1_id = group_repo.create(name="Group 1")
        group2_id = group_repo.create(name="Group 2")
        
        member_repo.add_member(group1_id, test_user, role="admin")
        member_repo.add_member(group2_id, test_user, role="member")
        
        user_groups = member_repo.get_user_groups(test_user)
        assert len(user_groups) == 2
        assert any(g["id"] == group1_id and g["role"] == "admin" for g in user_groups)
        assert any(g["id"] == group2_id and g["role"] == "member" for g in user_groups)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_9_update_member_role(self, member_repo, test_group, test_user):
        """V17.9: Update member role"""
        member_repo.add_member(test_group, test_user, role="member")
        
        member_repo.update_role(test_group, test_user, "admin")
        
        members = member_repo.get_group_members(test_group)
        assert members[0]["role"] == "admin"


class TestGroupKeywordRepository:
    """V17.10-V17.11: GroupKeywordRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_10_add_keyword(self, keyword_repo, test_group):
        """V17.10: Add keyword to group"""
        result = keyword_repo.add(test_group, "security")
        assert result is not None
        
        keywords = keyword_repo.get_by_group_id(test_group)
        assert len(keywords) == 1
        assert keywords[0]["keyword"] == "security"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_11_remove_keyword(self, keyword_repo, test_group):
        """V17.11: Remove keyword from group"""
        keyword_repo.add(test_group, "devops")
        keyword_repo.add(test_group, "executive")
        
        keyword_repo.remove(test_group, "devops")
        
        keywords = keyword_repo.get_by_group_id(test_group)
        assert len(keywords) == 1
        assert keywords[0]["keyword"] == "executive"


class TestGroupManager:
    """V17.12: GroupManager integration test"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v17_12_group_management_integration(self, group_manager, test_user):
        """V17.12: Complete group management workflow"""
        import time
        unique_name = f"IntegrationGroup_{int(time.time())}"
        # Create group
        group_id = group_manager.create_group(
            name=unique_name,
            description="Administrative users",
            language="en",
            preferred_channel="email"
        )
        
        # Add member
        added = group_manager.add_member(group_id, test_user, role="admin")
        assert added is True
        
        # Add keyword
        keyword_added = group_manager.add_keyword(group_id, "security")
        assert keyword_added is True
        
        # Get group with members and keywords
        group = group_manager.get_group(group_id)
        assert group is not None
        assert len(group["members"]) == 1
        assert "security" in group["keywords"]
        
        # Get user groups
        user_groups = group_manager.get_user_groups(test_user)
        assert len(user_groups) == 1
        assert user_groups[0]["id"] == group_id

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
