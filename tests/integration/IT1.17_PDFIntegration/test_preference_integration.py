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

"""Integration Tests for PDF Preference Integration"""
import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import tempfile
import os
import sqlite3
from src.core.formatters.pdf_preferences import PDFPreferenceResolver, PDFPreference
from src.database.db_manager import DatabaseManager

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
    for migration_file in ["002_add_message_guid.sql", "002_user_management_personalization.sql", "003_notification_storage_and_media.sql"]:
        migration_path = migrations_dir / migration_file
        if migration_path.exists():
            if migration_file == "002_add_message_guid.sql":
                existing = db_manager.fetchone(
                    "SELECT name FROM pragma_table_info('messages') WHERE name = ?",
                    ("guid",),
                )
                if existing:
                    continue
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
            try:
                db_manager.connection.executescript(migration_sql)
                db_manager.connection.commit()
            except sqlite3.OperationalError as exc:
                if "duplicate column name" in str(exc).lower() or "already exists" in str(exc).lower():
                    continue
                raise
    
    yield db_manager
    db_manager.disconnect()
    try:
        os.unlink(db_path)
    except:
        pass

class TestPreferenceIntegration:
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    def test_user_channel_preference_integration(self, temp_db, test_email_domain):
        """Test user and channel preference integration"""
        resolver = PDFPreferenceResolver(db=temp_db)
        
        # Create user and channel
        temp_db.execute("INSERT INTO users (username, email, password_hash, pdf_preference) VALUES (?, ?, ?, ?)",
                       ("user1", f"u1{test_email_domain}", "hash", "attach"))
        temp_db.execute("INSERT INTO channels (name, type, enabled, pdf_preference) VALUES (?, ?, ?, ?)",
                       ("chan1", "smtp", True, "link"))
        temp_db.commit()
        
        user_id = temp_db.fetchone("SELECT id FROM users WHERE username = ?", ("user1",))["id"]
        channel_id = temp_db.fetchone("SELECT id FROM channels WHERE name = ?", ("chan1",))["id"]
        
        # User preference should win
        pref = resolver.resolve_preference(user_id=user_id, channel_id=channel_id)
        assert pref == PDFPreference.ATTACH

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]
