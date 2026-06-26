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
Integration Tests for Storage Database Integration

Tests:
- Database integration with storage manager
- Repository integration with storage
- End-to-end storage and database workflows
"""

import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import tempfile
import os
import shutil
import json
import sqlite3

from src.database.db_manager import DatabaseManager
from src.database.repositories import MessageRepository, DeliveryRepository, ChannelRepository
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    # Apply migrations
    migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
    migration_files = [
        "002_add_message_guid.sql",
        "002_user_management_personalization.sql",
        "003_notification_storage_and_media.sql"
    ]
    
    for migration_file in migration_files:
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


@pytest.fixture
def storage_manager(temp_storage_dir, storage_base_url):
    """Create StorageManager with LocalStorage"""
    local_storage = LocalStorage(base_path=temp_storage_dir)
    return StorageManager(backend=local_storage, base_url=storage_base_url)


class TestStorageDatabaseIntegration:
    """Test storage integration with database"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_store_file_and_record_in_database(self, storage_manager, temp_db):
        """Test storing a file and recording it in the database"""
        # Create a message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test message"}])
        )
        
        # Store file
        content = b"PDF content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            message_id=message_id
        )
        
        # Record in database
        temp_db.execute(
            """
    


            INSERT INTO notification_storage 
            (message_id, file_type, storage_path, storage_uri, access_url, file_size, mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                "pdf",  # file_type from store_file parameter
                result["storage_path"],
                result["storage_uri"],
                result.get("access_url"),
                result["file_size"],
                result["mime_type"]
            )
        )
        temp_db.commit()
        
        # Verify database record
        db_record = temp_db.fetchone(
            "SELECT * FROM notification_storage WHERE message_id = ?",
            (message_id,)
        )
        assert db_record is not None
        assert db_record["storage_path"] == result["storage_path"]
        assert db_record["file_size"] == result["file_size"]
        
        # Verify file exists in storage
        assert storage_manager.file_exists(result["storage_path"])
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == content
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_query_storage_by_message_id(self, storage_manager, temp_db):
        """Test querying storage records by message ID"""
        # Create message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test"}])
        )
        
        # Store multiple files
        files = []
        for i in range(3):
            content = f"PDF content {i}".encode()
            result = storage_manager.store_file(
                file_content=content,
                file_type="pdf",
                message_id=message_id
            )
            
            # Record in database
            temp_db.execute(
                """
    


                INSERT INTO notification_storage 
                (message_id, file_type, storage_path, storage_uri, file_size, mime_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, "pdf", result["storage_path"], 
                 result["storage_uri"], result["file_size"], result["mime_type"])
            )
            files.append(result)
        
        temp_db.commit()
        
        # Query by message_id
        records = temp_db.fetchall(
            "SELECT * FROM notification_storage WHERE message_id = ?",
            (message_id,)
        )
        
        assert len(records) == 3
        for record in records:
            assert record["message_id"] == message_id
            assert storage_manager.file_exists(record["storage_path"])
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_storage_with_delivery_tracking(self, storage_manager, temp_db, test_email):
        """Test storing files with delivery tracking"""
        # Create message and delivery
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test"}])
        )
        
        channel_repo = ChannelRepository(temp_db)
        channel_id = channel_repo.create(
            name="test_channel",
            channel_type="smtp",
            enabled=True
        )
        
        delivery_repo = DeliveryRepository(temp_db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=channel_id,
            destination=test_email,
            state="queued"
        )
        
        # Store file with delivery_id
        content = b"PDF for delivery"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            message_id=message_id,
            delivery_id=delivery_id
        )
        
        # Record in database
        temp_db.execute(
            """
    


            INSERT INTO notification_storage 
            (message_id, delivery_id, file_type, storage_path, storage_uri, file_size, mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, delivery_id, "pdf", result["storage_path"],
             result["storage_uri"], result["file_size"], result["mime_type"])
        )
        temp_db.commit()
        
        # Query by delivery_id
        records = temp_db.fetchall(
            "SELECT * FROM notification_storage WHERE delivery_id = ?",
            (delivery_id,)
        )
        
        assert len(records) == 1
        assert records[0]["delivery_id"] == delivery_id
        assert records[0]["message_id"] == message_id
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_media_files_tracking(self, storage_manager, temp_db):
        """Test tracking media files in database"""
        # Create message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test with image"}])
        )
        
        # Record media file
        temp_db.execute(
            """
    


            INSERT INTO media_files 
            (message_id, media_type, format, storage_method, original_uri, file_size)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, "image", "png", "uri", f"{storage_manager.base_url}/image.png", 1024)
        )
        temp_db.commit()
        
        # Query media files
        media_files = temp_db.fetchall(
            "SELECT * FROM media_files WHERE message_id = ?",
            (message_id,)
        )
        
        assert len(media_files) == 1
        assert media_files[0]["media_type"] == "image"
        assert media_files[0]["format"] == "png"
        assert media_files[0]["storage_method"] == "uri"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_preference_integration(self, storage_manager, temp_db, test_email):
        """Test PDF preference integration with users and channels"""
        # Create user with PDF preference
        temp_db.execute(
            """

            INSERT INTO users (username, email, password_hash, pdf_preference)
            VALUES (?, ?, ?, ?)
            """,
            ("testuser", test_email, "hash", "true")
        )
        temp_db.commit()
        
        user = temp_db.fetchone(
            "SELECT pdf_preference FROM users WHERE username = ?",
            ("testuser",)
        )
        assert user["pdf_preference"] == "true"
        
        # Create channel with PDF preference
        channel_repo = ChannelRepository(temp_db)
        channel_id = channel_repo.create(
            name="pdf_channel",
            channel_type="smtp",
            enabled=True
        )
        
        # Update channel PDF preference
        temp_db.execute(
            "UPDATE channels SET pdf_preference = ? WHERE id = ?",
            ("true", channel_id)
        )
        temp_db.commit()
        
        channel = temp_db.fetchone(
            "SELECT pdf_preference FROM channels WHERE id = ?",
            (channel_id,)
        )
        assert channel["pdf_preference"] == "true"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]

