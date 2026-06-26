# @pytest.mark.req("UC-010")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Unit Tests for PDF Preference Resolution

Tests:
- Preference resolution logic
- User preference priority
- Channel preference priority
- Default preference fallback
"""

import pytest
import tempfile
import os
import json
from pathlib import Path

from src.core.formatters.pdf_preferences import PDFPreferenceResolver, PDFPreference
from src.database.db_manager import DatabaseManager


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    import tempfile
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


@pytest.fixture
def resolver(temp_db):
    """Create PDFPreferenceResolver instance"""
    return PDFPreferenceResolver(db=temp_db)


class TestPDFPreferenceResolver:
    """Test PDF preference resolution"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_user_preference(self, resolver, temp_db, test_email_domain):
        """Test resolving user preference"""
        # Create user with PDF preference
        temp_db.execute(
            "INSERT INTO users (username, email, password_hash, pdf_preference) VALUES (?, ?, ?, ?)",
            ("testuser", f"test{test_email_domain}", "hash", "attach")
        )
        temp_db.commit()
        
        user_id = temp_db.fetchone("SELECT id FROM users WHERE username = ?", ("testuser",))["id"]
        
        # Resolve preference
        preference = resolver.resolve_preference(user_id=user_id)
        
        assert preference == PDFPreference.ATTACH
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_channel_preference(self, resolver, temp_db):
        """Test resolving channel preference"""
        # Create channel with PDF preference
        temp_db.execute(
            "INSERT INTO channels (name, type, enabled, pdf_preference) VALUES (?, ?, ?, ?)",
            ("test_channel", "smtp", True, "link")
        )
        temp_db.commit()
        
        channel_id = temp_db.fetchone("SELECT id FROM channels WHERE name = ?", ("test_channel",))["id"]
        
        # Resolve preference (no user preference)
        preference = resolver.resolve_preference(channel_id=channel_id)
        
        assert preference == PDFPreference.LINK
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_user_overrides_channel(self, resolver, temp_db, test_email_domain):
        """Test that user preference overrides channel preference"""
        # Create user with preference
        temp_db.execute(
            "INSERT INTO users (username, email, password_hash, pdf_preference) VALUES (?, ?, ?, ?)",
            ("testuser", f"test{test_email_domain}", "hash", "attach")
        )
        temp_db.commit()
        user_id = temp_db.fetchone("SELECT id FROM users WHERE username = ?", ("testuser",))["id"]
        
        # Create channel with different preference
        temp_db.execute(
            "INSERT INTO channels (name, type, enabled, pdf_preference) VALUES (?, ?, ?, ?)",
            ("test_channel", "smtp", True, "link")
        )
        temp_db.commit()
        channel_id = temp_db.fetchone("SELECT id FROM channels WHERE name = ?", ("test_channel",))["id"]
        
        # Resolve - user should win
        preference = resolver.resolve_preference(user_id=user_id, channel_id=channel_id)
        
        assert preference == PDFPreference.ATTACH
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_default_preference(self, resolver):
        """Test resolving default preference when no user/channel preference"""
        preference = resolver.resolve_preference()
        
        # Should use default (link)
        assert preference == PDFPreference.LINK
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_with_explicit_preferences(self, resolver):
        """Test resolving with explicitly provided preferences"""
        # User preference provided explicitly
        preference = resolver.resolve_preference(user_preference="attach")
        assert preference == PDFPreference.ATTACH
        
        # Channel preference provided explicitly
        preference = resolver.resolve_preference(channel_preference="link")
        assert preference == PDFPreference.LINK
        
        # User overrides channel even when explicit
        preference = resolver.resolve_preference(
            user_preference="attach",
            channel_preference="link"
        )
        assert preference == PDFPreference.ATTACH
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_resolve_none_preference(self, resolver):
        """Test resolving 'none' preference"""
        preference = resolver.resolve_preference(user_preference="none")
        assert preference == PDFPreference.NONE
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_should_generate_pdf(self, resolver):
        """Test should_generate_pdf method"""
        assert resolver.should_generate_pdf(PDFPreference.ATTACH) is True
        assert resolver.should_generate_pdf(PDFPreference.LINK) is True
        assert resolver.should_generate_pdf(PDFPreference.NONE) is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_should_attach_pdf(self, resolver):
        """Test should_attach_pdf method"""
        assert resolver.should_attach_pdf(PDFPreference.ATTACH) is True
        assert resolver.should_attach_pdf(PDFPreference.LINK) is False
        assert resolver.should_attach_pdf(PDFPreference.NONE) is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_should_link_pdf(self, resolver):
        """Test should_link_pdf method"""
        assert resolver.should_link_pdf(PDFPreference.LINK) is True
        assert resolver.should_link_pdf(PDFPreference.ATTACH) is False
        assert resolver.should_link_pdf(PDFPreference.NONE) is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_invalid_preference_fallback(self, resolver):
        """Test that invalid preferences fall back correctly"""
        # Invalid user preference falls to channel
        preference = resolver.resolve_preference(
            user_preference="invalid",
            channel_preference="link"
        )
        assert preference == PDFPreference.LINK
        
        # Invalid channel preference falls to default
        preference = resolver.resolve_preference(channel_preference="invalid")
        assert preference == PDFPreference.LINK  # Default

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
