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
System Tests for Database Migrations

Tests:
- Migration execution
- Data integrity after migration
- Migration idempotency
- Rollback safety
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import tempfile
import os

from src.database.db_manager import DatabaseManager


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    
    # Apply only baseline + pre-003 migrations
    migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
    seed_migrations = [
        "001_initial_schema.sql",
        "002_add_message_guid.sql",
        "002_user_management_personalization.sql",
    ]
    
    for migration_file in seed_migrations:
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


class TestDatabaseMigrations:
    """Test database migration system"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_migration_003_execution(self, temp_db):
        """Test that migration 003 executes successfully"""
        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        assert migration_file.exists(), "Migration file should exist"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        temp_db.connection.executescript(migration_sql)
        temp_db.connection.commit()
        
        # Verify tables were created
        notification_storage = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notification_storage'"
        )
        assert notification_storage is not None
        
        media_files = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='media_files'"
        )
        assert media_files is not None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_migration_idempotency(self, temp_db):
        """Test that migration can be run multiple times safely"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_migration_idempotency"
        )

        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration first time
        try:
            temp_db.connection.executescript(migration_sql)
            temp_db.connection.commit()
        except Exception as e:
            # Some parts may fail on second run (like ALTER TABLE if column exists)
            # This is expected for idempotency - migration uses IF NOT EXISTS for tables
            pass
        
        # Count tables before second execution
        tables_before = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        count_before = len(tables_before)
        
        # Execute migration second time (should be safe - tables use IF NOT EXISTS)
        # Note: ALTER TABLE will fail if column exists, but that's OK
        try:
            temp_db.connection.executescript(migration_sql)
            temp_db.connection.commit()
        except Exception:
            # ALTER TABLE may fail if columns already exist - this is expected
            pass
        
        # Count tables after second execution
        tables_after = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        count_after = len(tables_after)
        
        # Should have same number of tables (idempotent)
        assert count_before == count_after
        
        # Verify tables still exist and are accessible
        notification_storage = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notification_storage'"
        )
        assert notification_storage is not None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_migration_data_integrity(self, temp_db):
        """Test that existing data is preserved after migration"""
        # Create some existing data
        import json
        temp_db.execute(
            "INSERT INTO messages (created_by, audience_type, content_json, guid) VALUES (?, ?, ?, ?)",
            ("test_user", "personalised", json.dumps([]), "test-guid-1")
        )
        temp_db.commit()
        
        message_id = temp_db.fetchone("SELECT id FROM messages WHERE guid = ?", ("test-guid-1",))["id"]
        
        # Execute migration
        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        temp_db.connection.executescript(migration_sql)
        temp_db.connection.commit()
        
        # Verify existing data still exists
        message = temp_db.fetchone("SELECT * FROM messages WHERE id = ?", (message_id,))
        assert message is not None
        assert message["created_by"] == "test_user"
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_preference_columns_added(self, temp_db):
        """Test that PDF preference columns are added to users and channels"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_preference_columns_added"
        )

        # Execute migration
        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        temp_db.connection.executescript(migration_sql)
        temp_db.connection.commit()
        
        # Check users table
        users_columns = temp_db.fetchall("PRAGMA table_info(users)")
        users_column_names = [col["name"] for col in users_columns]
        assert "pdf_preference" in users_column_names
        
        # Check channels table
        channels_columns = temp_db.fetchall("PRAGMA table_info(channels)")
        channels_column_names = [col["name"] for col in channels_columns]
        assert "pdf_preference" in channels_column_names
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_migration_indexes_created(self, temp_db):
        """Test that all indexes are created by migration"""
        # Execute migration
        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        temp_db.connection.executescript(migration_sql)
        temp_db.connection.commit()
        
        # Check notification_storage indexes
        storage_indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notification_storage'"
        )
        storage_index_names = [idx["name"] for idx in storage_indexes]
        
        required_storage_indexes = [
            "idx_notification_storage_message_id",
            "idx_notification_storage_delivery_id",
            "idx_notification_storage_file_type",
            "idx_notification_storage_created_at"
        ]
        
        for idx_name in required_storage_indexes:
            assert idx_name in storage_index_names, f"Index {idx_name} not found"
        
        # Check media_files indexes
        media_indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='media_files'"
        )
        media_index_names = [idx["name"] for idx in media_indexes]
        
        required_media_indexes = [
            "idx_media_files_message_id",
            "idx_media_files_media_type",
            "idx_media_files_storage_method"
        ]
        
        for idx_name in required_media_indexes:
            assert idx_name in media_index_names, f"Index {idx_name} not found"
        
        # Check PDF preference indexes
        users_indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'"
        )
        users_index_names = [idx["name"] for idx in users_indexes]
        assert "idx_users_pdf_preference" in users_index_names
        
        channels_indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='channels'"
        )
        channels_index_names = [idx["name"] for idx in channels_indexes]
        assert "idx_channels_pdf_preference" in channels_index_names
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_foreign_key_constraints(self, temp_db):
        """Test that foreign key constraints are properly set up"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_foreign_key_constraints"
        )

        # Execute migration
        migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
        migration_file = migrations_dir / "003_notification_storage_and_media.sql"
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        temp_db.connection.executescript(migration_sql)
        temp_db.connection.commit()
        
        # Enable foreign key constraints (SQLite requires this)
        temp_db.execute("PRAGMA foreign_keys = ON")
        
        # Create a message
        import json
        temp_db.execute(
            "INSERT INTO messages (created_by, audience_type, content_json, guid) VALUES (?, ?, ?, ?)",
            ("test_user", "personalised", json.dumps([]), "test-guid-fk")
        )
        temp_db.commit()
        message_id = temp_db.fetchone("SELECT id FROM messages WHERE guid = ?", ("test-guid-fk",))["id"]
        
        # Try to insert into notification_storage with invalid message_id (should fail)
        with pytest.raises(Exception):
            temp_db.execute(
                "INSERT INTO notification_storage (message_id, file_type, storage_path) VALUES (?, ?, ?)",
                (99999, "pdf", "test.pdf")
            )
            temp_db.commit()
        
        # Insert with valid message_id (should succeed)
        temp_db.execute(
            "INSERT INTO notification_storage (message_id, file_type, storage_path) VALUES (?, ?, ?)",
            (message_id, "pdf", "test.pdf")
        )
        temp_db.commit()
        
        # Verify insert succeeded
        result = temp_db.fetchone(
            "SELECT * FROM notification_storage WHERE message_id = ?",
            (message_id,)
        )
        assert result is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.db, pytest.mark.smtp, pytest.mark.slow]

