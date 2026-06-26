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
Unit Tests for Notification Storage Schema

Tests:
- Database schema creation
- Table structure validation
- Foreign key constraints
- Index creation
- Column types and constraints
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.database.db_manager import DatabaseManager


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    # initialize_schema already applies all migrations in order
    
    yield db_manager
    
    db_manager.disconnect()
    try:
        os.unlink(db_path)
    except:
        pass


class TestNotificationStorageSchema:
    """Test notification_storage table schema"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_table_exists(self, temp_db):
        """Test that notification_storage table exists"""
        result = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='notification_storage'"
        )
        assert result is not None
        assert result["name"] == "notification_storage"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_table_columns(self, temp_db):
        """Test that all required columns exist"""
        result = temp_db.fetchall("PRAGMA table_info(notification_storage)")
        columns = {row["name"]: row for row in result}
        
        required_columns = [
            "id", "message_id", "delivery_id", "file_type", "storage_path",
            "storage_uri", "access_url", "file_size", "mime_type", "created_at"
        ]
        
        for col in required_columns:
            assert col in columns, f"Column {col} not found"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_primary_key(self, temp_db):
        """Test that id is primary key"""
        result = temp_db.fetchall("PRAGMA table_info(notification_storage)")
        id_column = next((row for row in result if row["name"] == "id"), None)
        assert id_column is not None
        assert id_column["pk"] == 1  # Primary key
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_foreign_key_message_id(self, temp_db):
        """Test foreign key constraint on message_id"""
        # Create a message first
        temp_db.execute(
            "INSERT INTO messages (created_by, audience_type, content_json, guid) VALUES (?, ?, ?, ?)",
            ("test_user", "personalised", '[]', "test-guid-123")
        )
        temp_db.commit()
        
        message_id = temp_db.fetchone("SELECT id FROM messages WHERE guid = ?", ("test-guid-123",))["id"]
        
        # Insert into notification_storage with valid message_id
        temp_db.execute(
            """
            INSERT INTO notification_storage 
            (message_id, file_type, storage_path) 
            VALUES (?, ?, ?)
            """,
            (message_id, "pdf", "pdf/2025/12/01/test.pdf")
        )
        temp_db.commit()
        
        # Verify insert succeeded
        result = temp_db.fetchone(
            "SELECT * FROM notification_storage WHERE message_id = ?",
            (message_id,)
        )
        assert result is not None
        assert result["message_id"] == message_id
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_foreign_key_delivery_id(self, temp_db, test_email_domain):
        """Test foreign key constraint on delivery_id"""
        # Create message and delivery
        temp_db.execute(
            "INSERT INTO messages (created_by, audience_type, content_json, guid) VALUES (?, ?, ?, ?)",
            ("test_user", "personalised", '[]', "test-guid-456")
        )
        temp_db.commit()
        message_id = temp_db.fetchone("SELECT id FROM messages WHERE guid = ?", ("test-guid-456",))["id"]
        
        # Create channel first
        temp_db.execute(
            "INSERT INTO channels (name, type, enabled) VALUES (?, ?, ?)",
            ("test_channel", "smtp", 1)
        )
        temp_db.commit()
        channel_id = temp_db.fetchone("SELECT id FROM channels WHERE name = ?", ("test_channel",))["id"]
        
        # Create delivery
        temp_db.execute(
            "INSERT INTO deliveries (message_id, channel_id, destination, state) VALUES (?, ?, ?, ?)",
            (message_id, channel_id, _synthetic_email("test", test_email_domain), "queued")
        )
        temp_db.commit()
        delivery_id = temp_db.fetchone(
            "SELECT id FROM deliveries WHERE message_id = ?",
            (message_id,)
        )["id"]
        
        # Insert into notification_storage with valid delivery_id
        temp_db.execute(
            """
            INSERT INTO notification_storage 
            (message_id, delivery_id, file_type, storage_path) 
            VALUES (?, ?, ?, ?)
            """,
            (message_id, delivery_id, "pdf", "pdf/2025/12/01/test.pdf")
        )
        temp_db.commit()
        
        # Verify insert succeeded
        result = temp_db.fetchone(
            "SELECT * FROM notification_storage WHERE delivery_id = ?",
            (delivery_id,)
        )
        assert result is not None
        assert result["delivery_id"] == delivery_id
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_indexes_exist(self, temp_db):
        """Test that indexes are created"""
        indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='notification_storage'"
        )
        index_names = [idx["name"] for idx in indexes]
        
        required_indexes = [
            "idx_notification_storage_message_id",
            "idx_notification_storage_delivery_id",
            "idx_notification_storage_file_type",
            "idx_notification_storage_created_at"
        ]
        
        for idx_name in required_indexes:
            assert idx_name in index_names, f"Index {idx_name} not found"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_file_type_not_null(self, temp_db):
        """Test that file_type cannot be NULL"""
        with pytest.raises(Exception):  # SQLite will raise an exception
            temp_db.execute(
                "INSERT INTO notification_storage (storage_path) VALUES (?)",
                ("tests/path.pdf",)
            )
            temp_db.commit()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_storage_path_not_null(self, temp_db):
        """Test that storage_path cannot be NULL"""
        with pytest.raises(Exception):  # SQLite will raise an exception
            temp_db.execute(
                "INSERT INTO notification_storage (file_type) VALUES (?)",
                ("pdf",)
            )
            temp_db.commit()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_created_at_default(self, temp_db):
        """Test that created_at has default value"""
        temp_db.execute(
            "INSERT INTO notification_storage (file_type, storage_path) VALUES (?, ?)",
            ("pdf", "pdf/2025/12/01/test.pdf")
        )
        temp_db.commit()
        
        result = temp_db.fetchone(
            "SELECT created_at FROM notification_storage WHERE storage_path = ?",
            ("pdf/2025/12/01/test.pdf",)
        )
        assert result is not None
        assert result["created_at"] is not None


class TestMediaFilesSchema:
    """Test media_files table schema"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_table_exists(self, temp_db):
        """Test that media_files table exists"""
        result = temp_db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='media_files'"
        )
        assert result is not None
        assert result["name"] == "media_files"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_table_columns(self, temp_db):
        """Test that all required columns exist"""
        result = temp_db.fetchall("PRAGMA table_info(media_files)")
        columns = {row["name"]: row for row in result}
        
        required_columns = [
            "id", "message_id", "media_type", "format", "storage_method",
            "original_uri", "cached_path", "file_size", "created_at"
        ]
        
        for col in required_columns:
            assert col in columns, f"Column {col} not found"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_foreign_key_message_id(self, temp_db):
        """Test foreign key constraint on message_id"""
        # Create a message first
        temp_db.execute(
            "INSERT INTO messages (created_by, audience_type, content_json, guid) VALUES (?, ?, ?, ?)",
            ("test_user", "personalised", '[]', "test-guid-789")
        )
        temp_db.commit()
        message_id = temp_db.fetchone("SELECT id FROM messages WHERE guid = ?", ("test-guid-789",))["id"]
        
        # Insert into media_files with valid message_id
        temp_db.execute(
            """
            INSERT INTO media_files 
            (message_id, media_type, storage_method) 
            VALUES (?, ?, ?)
            """,
            (message_id, "image", "uri")
        )
        temp_db.commit()
        
        # Verify insert succeeded
        result = temp_db.fetchone(
            "SELECT * FROM media_files WHERE message_id = ?",
            (message_id,)
        )
        assert result is not None
        assert result["message_id"] == message_id
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_media_type_not_null(self, temp_db):
        """Test that media_type cannot be NULL"""
        with pytest.raises(Exception):
            temp_db.execute(
                "INSERT INTO media_files (message_id, storage_method) VALUES (?, ?)",
                (1, "uri")
            )
            temp_db.commit()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_storage_method_not_null(self, temp_db):
        """Test that storage_method cannot be NULL"""
        with pytest.raises(Exception):
            temp_db.execute(
                "INSERT INTO media_files (message_id, media_type) VALUES (?, ?)",
                (1, "image")
            )
            temp_db.commit()


class TestPDFPreferenceSchema:
    """Test PDF preference columns in users and channels tables"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_users_pdf_preference_column(self, temp_db):
        """Test that users table has pdf_preference column"""
        result = temp_db.fetchall("PRAGMA table_info(users)")
        columns = {row["name"]: row for row in result}
        
        assert "pdf_preference" in columns
        pdf_pref_col = columns["pdf_preference"]
        assert pdf_pref_col["type"].upper() == "TEXT"
        # Default is NULL (no preference)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channels_pdf_preference_column(self, temp_db):
        """Test that channels table has pdf_preference column"""
        result = temp_db.fetchall("PRAGMA table_info(channels)")
        columns = {row["name"]: row for row in result}
        
        assert "pdf_preference" in columns
        pdf_pref_col = columns["pdf_preference"]
        assert pdf_pref_col["type"].upper() == "TEXT"
        # Default is NULL (no preference)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_users_pdf_preference_index(self, temp_db):
        """Test that index exists on users.pdf_preference"""
        indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='users'"
        )
        index_names = [idx["name"] for idx in indexes]
        assert "idx_users_pdf_preference" in index_names
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channels_pdf_preference_index(self, temp_db):
        """Test that index exists on channels.pdf_preference"""
        indexes = temp_db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='channels'"
        )
        index_names = [idx["name"] for idx in indexes]
        assert "idx_channels_pdf_preference" in index_names
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_users_pdf_preference_default_null(self, temp_db, test_email_domain):
        """Test that users.pdf_preference defaults to NULL"""
        temp_db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            ("testuser", _synthetic_email("test", test_email_domain), "hash")
        )
        temp_db.commit()
        
        result = temp_db.fetchone(
            "SELECT pdf_preference FROM users WHERE username = ?",
            ("testuser",)
        )
        assert result is not None
        assert result["pdf_preference"] is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channels_pdf_preference_default_null(self, temp_db):
        """Test that channels.pdf_preference defaults to NULL"""
        temp_db.execute(
            "INSERT INTO channels (name, type, enabled) VALUES (?, ?, ?)",
            ("test_channel", "smtp", 1)
        )
        temp_db.commit()
        
        result = temp_db.fetchone(
            "SELECT pdf_preference FROM channels WHERE name = ?",
            ("test_channel",)
        )
        assert result is not None
        assert result["pdf_preference"] is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
