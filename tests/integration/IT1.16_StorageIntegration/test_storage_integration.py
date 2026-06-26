# @pytest.mark.req("UC-024")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Integration Tests for Storage Integration

Tests:
- Storage integration with database
- Storage integration with message system
- Storage integration with delivery system
- End-to-end storage workflows
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
from src.database.repositories import MessageRepository, DeliveryRepository
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
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    
    # Apply additional migrations
    migrations_dir = Path(__file__).parent.parent.parent.parent / "database" / "migrations"
    migration_files = [
        "002_add_message_guid.sql",
        "002_user_management_personalization.sql"
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
    
    def test_store_file_with_message_id(self, storage_manager, temp_db):
        """Test storing a file associated with a message"""
        # Create a message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test message"}])
        )
        
        # Store a file for this message
        content = b"PDF content for message"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            message_id=message_id
        )
        
        # Verify file was stored
        assert storage_manager.file_exists(result["storage_path"])
        assert str(message_id) in result["storage_path"]
        
        # Verify file can be retrieved
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == content
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_store_file_with_delivery_id(self, storage_manager, temp_db, test_email):
        """Test storing a file associated with a delivery"""
    


        # Create a message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test message"}])
        )
        
        # Create a delivery
        delivery_repo = DeliveryRepository(temp_db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=1,
            destination=test_email,
            state="queued"
        )
        
        # Store a file for this delivery
        content = b"PDF content for delivery"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            message_id=message_id,
            delivery_id=delivery_id
        )
        
        # Verify file was stored
        assert storage_manager.file_exists(result["storage_path"])
        assert str(message_id) in result["storage_path"]
        assert str(delivery_id) in result["storage_path"]
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_storage_with_multiple_messages(self, storage_manager, temp_db):
        """Test storing files for multiple messages"""
        message_repo = MessageRepository(temp_db)
        files = []
        
        # Create multiple messages and store files
        for i in range(5):
            message_id = message_repo.create(
                created_by="test_user",
                audience_type="personalised",
                content_json=json.dumps([{"type": "text", "body": f"Test message {i}"}])
            )
            
            content = f"PDF content for message {i}".encode()
            result = storage_manager.store_file(
                file_content=content,
                file_type="pdf",
                message_id=message_id
            )
            files.append((message_id, result))
        
        # Verify all files exist and can be retrieved
        for message_id, file_info in files:
            assert storage_manager.file_exists(file_info["storage_path"])
            retrieved = storage_manager.retrieve_file(file_info["storage_path"])
            assert retrieved is not None
            assert str(message_id) in file_info["storage_path"]


class TestStorageMessageSystemIntegration:
    """Test storage integration with message system"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    


    def test_store_pdf_for_message(self, storage_manager, temp_db):
        """Test storing PDF for a message"""
        # Create a message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test message"}])
        )
        
        # Generate PDF content (simulated)
        pdf_content = b"%PDF-1.4\nTest PDF Content"
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_content,
            file_type="pdf",
            message_id=message_id,
            metadata={"mime_type": "application/pdf"}
        )
        
        # Verify storage
        assert result["mime_type"] == "application/pdf"
        assert result["storage_path"].endswith(".pdf")
        assert result["access_url"] is not None
        
        # Verify file can be retrieved
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == pdf_content
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_store_image_for_message(self, storage_manager, temp_db):
        """Test storing image for a message"""



        # Create a message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test message with image"}])
        )
        
        # Generate image content (simulated PNG)
        image_content = b"\x89PNG\r\n\x1a\n" + b"x" * 100
        
        # Store image
        result = storage_manager.store_file(
            file_content=image_content,
            file_type="image",
            message_id=message_id,
            metadata={"format": "png", "mime_type": "image/png"}
        )
        
        # Verify storage
        assert "image/png" in result["mime_type"]
        assert result["storage_path"].endswith(".png")
        assert "image/" in result["storage_path"]
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_storage_path_organization(self, storage_manager, temp_db):
        """Test that storage paths are properly organized"""
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test"}])
        )
        
        # Store different file types
        pdf_result = storage_manager.store_file(
            file_content=b"PDF",
            file_type="pdf",
            message_id=message_id
        )
        
        image_result = storage_manager.store_file(
            file_content=b"Image",
            file_type="image",
            message_id=message_id,
            metadata={"format": "png"}
        )
        
        # Verify organization
        assert "pdf/" in pdf_result["storage_path"]
        assert "image/" in image_result["storage_path"]
        assert str(message_id) in pdf_result["storage_path"]
        assert str(message_id) in image_result["storage_path"]


class TestStorageDeliverySystemIntegration:
    """Test storage integration with delivery system"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    


    def test_store_file_for_delivery(self, storage_manager, temp_db, test_email):
        """Test storing file for a specific delivery"""
        # Create message and delivery
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test"}])
        )
        
        delivery_repo = DeliveryRepository(temp_db)
        delivery_id = delivery_repo.create(
            message_id=message_id,
            channel_id=1,
            destination=test_email,
            state="queued"
        )
        
        # Store PDF for delivery
        pdf_content = b"Delivery-specific PDF"
        result = storage_manager.store_file(
            file_content=pdf_content,
            file_type="pdf",
            message_id=message_id,
            delivery_id=delivery_id
        )
        
        # Verify file includes both message and delivery IDs
        assert str(message_id) in result["storage_path"]
        assert str(delivery_id) in result["storage_path"]
        assert storage_manager.file_exists(result["storage_path"])
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_multiple_deliveries_same_message(self, storage_manager, temp_db, test_email_domain):
        """Test storing files for multiple deliveries of the same message"""



        # Create message
        message_repo = MessageRepository(temp_db)
        message_id = message_repo.create(
            created_by="test_user",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": "Test"}])
        )
        
        # Create multiple deliveries
        delivery_repo = DeliveryRepository(temp_db)
        files = []
        
        for i in range(3):
            delivery_id = delivery_repo.create(
                message_id=message_id,
                channel_id=1,
                destination=f"user{i}{test_email_domain}",
                state="queued"
            )
            
            content = f"PDF for delivery {i}".encode()
            result = storage_manager.store_file(
                file_content=content,
                file_type="pdf",
                message_id=message_id,
                delivery_id=delivery_id
            )
            files.append((delivery_id, result))
        
        # Verify all files exist and are unique
        paths = [f[1]["storage_path"] for f in files]
        assert len(paths) == len(set(paths))  # All unique
        
        for delivery_id, file_info in files:
            assert str(delivery_id) in file_info["storage_path"]
            assert storage_manager.file_exists(file_info["storage_path"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]
