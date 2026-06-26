# @pytest.mark.req("UC-009")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Tests for LLM Prompt Management (T18)

V18.1-V18.10: LLM Prompt Management
"""

import pytest
import json
from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    LLMPromptRepository,
    GroupRepository
)
from src.core.prompts.prompt_manager import PromptManager


@pytest.fixture
def db():
    """Database fixture"""
    import os
    from pathlib import Path
    test_db_path = Path(__file__).parent.parent / "database" / "test_prompt.db"
    # Remove existing test DB
    if test_db_path.exists():
        os.remove(test_db_path)
    db = DatabaseManager(f"sqlite3:///{test_db_path}")
    db.connect()
    # Initialize schema
    try:
        db.initialize_schema()
    except:
        pass
    # Run migration
    try:
        migration_file = Path(__file__).parent.parent / "database" / "migrations" / "002_user_management_personalization.sql"
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        db.connection.executescript(migration_sql)
        db.commit()
    except Exception as e:
        # Ignore "duplicate column" errors (already migrated)
        if "duplicate column" not in str(e).lower():
            print(f"Migration note: {e}")
    yield db
    db.disconnect()
    # Clean up
    if test_db_path.exists():
        os.remove(test_db_path)


@pytest.fixture
def prompt_repo(db):
    """LLMPromptRepository fixture"""
    return LLMPromptRepository(db)


@pytest.fixture
def prompt_manager(db):
    """PromptManager fixture"""
    return PromptManager(db)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.fixture
def test_group(db):
    """Create a test group"""
    group_repo = GroupRepository(db)
    existing = group_repo.get_by_name("Test Group")
    if existing:
        return existing["id"]
    group_id = group_repo.create(name="Test Group", language="fr")
    return group_id


class TestLLMPromptRepository:
    """V18.1-V18.6: LLMPromptRepository tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_1_create_prompt(self, prompt_repo):
        """V18.1: Create prompt"""
        prompt_id = prompt_repo.create(
            name="Email Default",
            prompt_text="Format as email: {content}",
            channel_type="email",
            priority=10
        )
        assert prompt_id > 0
        
        prompt = prompt_repo.get_by_id(prompt_id)
        assert prompt["name"] == "Email Default"
        assert prompt["channel_type"] == "email"
        assert prompt["priority"] == 10
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_2_get_prompt_by_name(self, prompt_repo):
        """V18.2: Get prompt by name"""
        # Check if default prompts exist (from migration)
        existing = prompt_repo.get_by_name("SMS Default")
        if existing:
            # Use existing prompt
            assert existing is not None
        else:
            # Create new one
            prompt_id = prompt_repo.create(
                name="SMS Default",
                prompt_text="Format as SMS: {content}",
                channel_type="sms"
            )
            
            prompt = prompt_repo.get_by_name("SMS Default")
            assert prompt is not None
            assert prompt["id"] == prompt_id
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_3_find_best_match_channel_only(self, prompt_repo):
        """V18.3: Find best match - channel only"""
        # Create default prompt (no channel)
        default_id = prompt_repo.create(
            name="Default",
            prompt_text="Default: {content}",
            priority=1000
        )
        
        # Create channel-specific prompt
        email_id = prompt_repo.create(
            name="Email Specific",
            prompt_text="Email: {content}",
            channel_type="email",
            priority=1100
        )
        
        # Should find email-specific prompt
        match = prompt_repo.find_best_match(channel_type="email")
        assert match is not None
        assert match["channel_type"] == "email"
        assert match["prompt_text"] == "Email: {content}"
        assert match["priority"] == 1100
        
        # For unknown channel, should find default
        match = prompt_repo.find_best_match(channel_type="unknown")
        assert match is not None
        assert match["channel_type"] is None or match["channel_type"] == ""
        assert match["prompt_text"] == "Default: {content}"
        assert match["priority"] == 1000
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_4_find_best_match_with_language(self, prompt_repo):
        """V18.4: Find best match - channel + language"""
        # French email prompt (specific language)
        french_email_id = prompt_repo.create(
            name="Email French Test",
            prompt_text="Email FR: {content}",
            channel_type="email",
            language="fr",
            priority=10
        )
        
        # Should find French email prompt (more specific)
        match = prompt_repo.find_best_match(channel_type="email", language="fr")
        assert match is not None
        assert match["language"] == "fr"
        assert match["channel_type"] == "email"
        assert match["prompt_text"] == "Email FR: {content}"
        
        # English email should find a default (language IS NULL matches all)
        # This could be the migration default or a newly created one
        match = prompt_repo.find_best_match(channel_type="email", language="en")
        assert match is not None
        # Should match a prompt with language IS NULL (default from migration or test)
        assert match["language"] is None or match["language"] == "", f"Expected NULL language, got {match['language']}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_5_find_best_match_with_group(self, prompt_repo, test_group):
        """V18.5: Find best match - channel + group"""
        # Default email prompt
        default_id = prompt_repo.create(
            name="Email Default",
            prompt_text="Email: {content}",
            channel_type="email",
            priority=0
        )
        
        # Group-specific email prompt
        group_id = prompt_repo.create(
            name="Email Group",
            prompt_text="Email Group: {content}",
            channel_type="email",
            group_id=test_group,
            priority=10
        )
        
        # Should find group-specific prompt
        match = prompt_repo.find_best_match(channel_type="email", group_id=test_group)
        assert match is not None
        assert match["group_id"] == test_group
        assert match["channel_type"] == "email"
        assert match["prompt_text"] == "Email Group: {content}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_6_list_prompts(self, prompt_repo):
        """V18.6: List prompts with filters"""
        prompt_repo.create(name="Email 1", prompt_text="E1", channel_type="email")
        prompt_repo.create(name="SMS 1", prompt_text="S1", channel_type="sms")
        prompt_repo.create(name="Email 2", prompt_text="E2", channel_type="email", enabled=False)
        
        # List all enabled
        all_prompts = prompt_repo.list_all(enabled_only=True)
        assert len(all_prompts) >= 2
        
        # List email only
        email_prompts = prompt_repo.list_all(channel_type="email", enabled_only=True)
        assert len(email_prompts) >= 1
        assert all(p["channel_type"] == "email" for p in email_prompts)


class TestPromptManager:
    """V18.7-V18.10: PromptManager tests"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_7_get_prompt_selection(self, prompt_manager):
        """V18.7: Prompt selection with priority"""
        # Create prompts with different priorities
        default_id = prompt_manager.create_prompt(
            name="Default",
            prompt_text="Default: {content}",
            priority=1000
        )
        
        email_id = prompt_manager.create_prompt(
            name="Email",
            prompt_text="Email: {content}",
            channel_type="email",
            priority=1100
        )
        
        # Should select email-specific prompt
        prompt = prompt_manager.get_prompt(channel_type="email")
        assert prompt is not None
        assert prompt["channel_type"] == "email"
        assert prompt["prompt_text"] == "Email: {content}"
        assert prompt["priority"] == 1100
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_8_prompt_variable_substitution(self, prompt_manager):
        """V18.8: Variable substitution in prompts"""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt",
            prompt_text="Hello {name}, your {item} is ready.",
            channel_type="email"
        )
        
        prompt = prompt_manager.get_prompt_by_id(prompt_id)
        
        rendered = prompt_manager.render_prompt(
            prompt["prompt_text"],
            variables={"name": "Fred", "item": "order"}
        )
        
        assert "Hello Fred, your order is ready." == rendered
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_9_prompt_missing_variables(self, prompt_manager):
        """V18.9: Handle missing variables gracefully"""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt",
            prompt_text="Hello {name}, your {item} is ready.",
            channel_type="email"
        )
        
        prompt = prompt_manager.get_prompt_by_id(prompt_id)
        
        # Missing variables - should return original
        rendered = prompt_manager.render_prompt(
            prompt["prompt_text"],
            variables={"name": "Fred"}  # Missing 'item'
        )
        
        # Should return original text (format fails gracefully)
        assert "Hello {name}, your {item} is ready." in rendered or "Hello Fred" in rendered
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_v18_10_update_prompt(self, prompt_manager):
        """V18.10: Update prompt"""
        prompt_id = prompt_manager.create_prompt(
            name="Original",
            prompt_text="Original text",
            channel_type="email",
            priority=5
        )
        
        prompt_manager.update_prompt(
            prompt_id=prompt_id,
            name="Updated",
            prompt_text="Updated text",
            priority=10
        )
        
        prompt = prompt_manager.get_prompt_by_id(prompt_id)
        assert prompt["name"] == "Updated"
        assert prompt["prompt_text"] == "Updated text"
        assert prompt["priority"] == 10

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]

