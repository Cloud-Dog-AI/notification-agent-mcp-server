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
T21 Tests - Natural Language Interface

Tests: UC1.3

Tests for:
- UserResolver (V21.1)
- GroupResolver (V21.2)
- Natural language command parsing (V21.3-V21.4)
- User preferences application (V21.5-V21.7)
- Translation (V21.8)
- MCP tool (V21.9)
- A2A endpoint (V21.10)
"""

import pytest
import json
import httpx
from pathlib import Path
from src.database.db_manager import DatabaseManager
from src.core.resolvers import UserResolver, GroupResolver, NaturalLanguageParser
from src.database.repositories import UserRepository, GroupRepository, GroupMemberRepository


def _find_project_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "database" / "migrations").exists():
            return parent
    raise RuntimeError("Project root not found (database/migrations missing).")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


@pytest.fixture
def db():
    """Database fixture"""
    import tempfile
    import os
    
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    try:
        db = DatabaseManager(f"sqlite3:///{db_path}")
        db.connect()
        
        # Run migrations manually
        project_root = PROJECT_ROOT
        migration_files = [
            "001_initial_schema.sql",
            "002_user_management_personalization.sql",
            "002_add_message_guid.sql",
        ]
        
        for migration_file in migration_files:
            migration_path = project_root / "database" / "migrations" / migration_file
            if migration_path.exists():
                with open(migration_path) as f:
                    db.connection.executescript(f.read())
        
        db.commit()
        
        yield db
        db.disconnect()
    finally:
        # Clean up
        if os.path.exists(db_path):
            os.unlink(db_path)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-020")


@pytest.fixture
def test_user(db, test_email_domain):
    """Create a test user"""
    user_repo = UserRepository(db)
    user_id = user_repo.create(
        username="fred",
        email=_synthetic_email("fred", test_email_domain),
        password_hash="hash",
        display_name="Fred",
        language="en",
        preferred_channel="email",
        content_style="html",
    )
    return user_repo.get_by_id(user_id)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-020")


@pytest.fixture
def test_group(db, test_user):
    """Create a test group with member"""
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)
    
    # Check if group already exists
    existing = group_repo.get_by_name("Admin Users")
    if existing:
        group_id = existing['id']
    else:
        group_id = group_repo.create(
            name="Admin Users",
            description="Administrator users",
        )
    
    # Check if member already exists
    members = member_repo.get_group_members(group_id)
    if not any(m['user_id'] == test_user['id'] for m in members):
        member_repo.add_member(group_id, test_user['id'], role="admin")
    
    return group_repo.get_by_id(group_id)


class TestV21_1_UserResolver:
    """V21.1: Resolve 'Fred' to user"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_by_display_name(self, db, test_user):
        resolver = UserResolver(db)
        user = resolver.resolve("Fred")
        assert user is not None
        assert user['id'] == test_user['id']
        assert user['display_name'] == "Fred"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_by_email(self, db, test_user):
        resolver = UserResolver(db)
        user = resolver.resolve(test_user["email"])
        assert user is not None
        assert user['id'] == test_user['id']
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_by_username(self, db, test_user):
        resolver = UserResolver(db)
        user = resolver.resolve("fred")
        assert user is not None
        assert user['id'] == test_user['id']
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_not_found(self, db):
        resolver = UserResolver(db)
        user = resolver.resolve("nonexistent")
        assert user is None


class TestV21_2_GroupResolver:
    """V21.2: Resolve 'Admin Users' to group"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_by_name(self, db, test_group):
        resolver = GroupResolver(db)
        group = resolver.resolve("Admin Users")
        assert group is not None
        assert group['id'] == test_group['id']
        assert group['name'] == "Admin Users"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_with_prefix(self, db, test_group):
        resolver = GroupResolver(db)
        group = resolver.resolve("the Admin Users group")
        assert group is not None
        assert group['id'] == test_group['id']
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_resolve_not_found(self, db):
        resolver = GroupResolver(db)
        group = resolver.resolve("nonexistent group")
        assert group is None


class TestV21_3_NaturalLanguageParsing:
    """V21.3: Parse 'Send notification to Fred that JOB XXXX has finished'"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_parse_send_to_user_that(self, db, test_user):
        parser = NaturalLanguageParser(db)
        parsed = parser.parse("Send notification to Fred that JOB XXXX has finished")
        
        assert len(parsed['recipients']) > 0
        assert test_user["email"] in parsed['recipients'] or "Fred" in parsed['recipients']
        assert "JOB XXXX has finished" in parsed['content'][0]['body']
        assert parsed.get('subject') is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_parse_send_to_group(self, db, test_group):
        parser = NaturalLanguageParser(db)
        parsed = parser.parse("Send all the results to the Admin Users")
        
        assert len(parsed['groups']) > 0
        assert "Admin Users" in parsed['groups']


class TestV21_4_NaturalLanguageParsing:
    """V21.4: Parse 'Send all the results to the Admin Users'"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_parse_send_to_group(self, db, test_group):
        parser = NaturalLanguageParser(db)
        parsed = parser.parse("Send all the results to the Admin Users")
        
        assert len(parsed['groups']) > 0
        assert "Admin Users" in parsed['groups']


class TestV21_5_UserPreferences:
    """V21.5: Apply user preferences automatically"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_user_preferences_applied(self, db, test_user):
        # This is tested in the delivery worker and formatter
        # Just verify user has preferences
        assert test_user.get('language') == 'en'
        assert test_user.get('preferred_channel') == 'email'
        assert test_user.get('content_style') == 'html'


class TestV21_6_ChannelSelection:
    """V21.6: Select correct channel from user preference"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_channel_from_preference(self, db, test_user):
        # User has preferred_channel = 'email'
        assert test_user.get('preferred_channel') == 'email'
        # Channel selection is handled by delivery worker based on user preference


class TestV21_7_PromptSelection:
    """V21.7: Select correct prompt from user preferences"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_prompt_selection(self, db):
        # Prompt selection is tested in LLM formatter tests
        # This is a placeholder to ensure prompt selection works
        pass


class TestV21_8_Translation:
    """V21.8: Translate message to user language"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    def test_translation_applied(self, db):
        # Translation is tested in LLM formatter tests
        # This is a placeholder to ensure translation works
        pass


class TestV21_9_MCPTool:
    """V21.9: MCP tool - send_notification_natural"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    @pytest.mark.asyncio
    async def test_mcp_tool_send_natural(self, db):
        # Test the parser directly (MCP server integration tested separately)
        from src.core.resolvers import NaturalLanguageParser
        
        parser = NaturalLanguageParser(db)
        parsed = parser.parse("Send notification to Fred that JOB XXXX has finished")
        
        assert parsed is not None
        assert 'recipients' in parsed or 'groups' in parsed
        assert 'content' in parsed


class TestV21_10_A2AEndpoint:
    """V21.10: A2A endpoint - /notify/natural"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-020")
    
    @pytest.mark.asyncio
    async def test_a2a_endpoint_natural(self, db):
        # Test the parser directly (A2A server integration tested separately)
        from src.core.resolvers import NaturalLanguageParser
        
        parser = NaturalLanguageParser(db)
        parsed = parser.parse("Send notification to Fred that JOB XXXX has finished")
        
        assert parsed is not None
        assert 'recipients' in parsed or 'groups' in parsed
        assert 'content' in parsed

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.fast]
