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
Unit Tests for Storage Manager

Tests:
- StorageManager initialization
- File path generation
- Metadata handling
- Extension and MIME type detection
- Storage backend abstraction
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

from src.core.storage.storage_manager import StorageManager, StorageBackend
from src.core.storage.local_storage import LocalStorage


class MockStorageBackend(StorageBackend):
    """Mock storage backend for testing"""
    
    def __init__(self):
        self.stored_files = {}
        self.file_sizes = {}
    
    def store_file(self, file_content: bytes, file_path: str, metadata=None):
        self.stored_files[file_path] = file_content
        self.file_sizes[file_path] = len(file_content)
        return {
            "storage_path": file_path,
            "storage_uri": f"mock://{file_path}",
            "file_size": len(file_content),
            "mime_type": metadata.get("mime_type") if metadata else None
        }
    
    def retrieve_file(self, file_path: str):
        return self.stored_files.get(file_path)
    
    def delete_file(self, file_path: str):
        if file_path in self.stored_files:
            del self.stored_files[file_path]
            del self.file_sizes[file_path]
            return True
        return False
    
    def file_exists(self, file_path: str):
        return file_path in self.stored_files
    
    def get_file_size(self, file_path: str):
        return self.file_sizes.get(file_path)


@pytest.fixture
def mock_backend():
    """Create a mock storage backend"""
    return MockStorageBackend()


@pytest.fixture
def storage_manager(mock_backend):
    """Create StorageManager with mock backend"""
    return StorageManager(backend=mock_backend)


@pytest.fixture
def storage_manager_with_url(mock_backend, storage_base_url):
    """Create StorageManager with base URL"""
    return StorageManager(backend=mock_backend, base_url=storage_base_url)


class TestStorageManager:
    """Test StorageManager class"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_initialization(self, mock_backend):
        """Test StorageManager initialization"""
        manager = StorageManager(backend=mock_backend)
        assert manager.backend == mock_backend
        assert manager.base_url == ""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_initialization_with_base_url(self, mock_backend, storage_base_url):
        """Test StorageManager initialization with base URL"""
        manager = StorageManager(backend=mock_backend, base_url=storage_base_url)
        assert manager.backend == mock_backend
        assert manager.base_url == storage_base_url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_basic(self, storage_manager):
        """Test storing a file with basic parameters"""
        content = b"test file content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert "storage_path" in result
        assert "storage_uri" in result
        assert "file_size" in result
        assert result["file_size"] == len(content)
        assert result["mime_type"] == "application/pdf"
        assert "pdf/" in result["storage_path"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_with_message_id(self, storage_manager):
        """Test storing a file with message ID"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            message_id=123
        )
        
        assert "123_" in result["storage_path"]
        assert result["file_size"] == len(content)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_with_delivery_id(self, storage_manager):
        """Test storing a file with message and delivery IDs"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="image",
            message_id=123,
            delivery_id=456
        )
        
        assert "123_456_" in result["storage_path"]
        assert "image/" in result["storage_path"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_generates_access_url(self, storage_manager_with_url):
        """Test that access URL is generated when base_url is set"""
        content = b"test content"
        result = storage_manager_with_url.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert "access_url" in result
        assert result["access_url"].startswith(storage_manager_with_url.base_url)
        assert result["storage_path"] in result["access_url"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_no_access_url_without_base(self, storage_manager):
        """Test that access URL is None when base_url is not set"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert result.get("access_url") is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_store_file_with_metadata(self, storage_manager):
        """Test storing a file with custom metadata"""
        content = b"test content"
        metadata = {
            "mime_type": "application/custom",
            "extension": "custom"
        }
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf",
            metadata=metadata
        )
        
        assert result["mime_type"] == "application/custom"
        assert result["storage_path"].endswith(".custom")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_retrieve_file(self, storage_manager):
        """Test retrieving a file"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == content
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_retrieve_file_not_found(self, storage_manager):
        """Test retrieving a non-existent file"""
        retrieved = storage_manager.retrieve_file("nonexistent/file.pdf")
        assert retrieved is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delete_file(self, storage_manager):
        """Test deleting a file"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert storage_manager.file_exists(result["storage_path"])
        deleted = storage_manager.delete_file(result["storage_path"])
        assert deleted is True
        assert not storage_manager.file_exists(result["storage_path"])
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delete_file_not_found(self, storage_manager):
        """Test deleting a non-existent file"""
        deleted = storage_manager.delete_file("nonexistent/file.pdf")
        assert deleted is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_file_exists(self, storage_manager):
        """Test checking if file exists"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert storage_manager.file_exists(result["storage_path"])
        assert not storage_manager.file_exists("nonexistent/file.pdf")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_file_info(self, storage_manager):
        """Test getting file information"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        info = storage_manager.get_file_info(result["storage_path"])
        assert info is not None
        assert info["storage_path"] == result["storage_path"]
        assert info["file_size"] == len(content)
        assert info["exists"] is True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_file_info_not_found(self, storage_manager):
        """Test getting info for non-existent file"""
        info = storage_manager.get_file_info("nonexistent/file.pdf")
        assert info is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_file_info_with_access_url(self, storage_manager_with_url):
        """Test getting file info with access URL"""
        content = b"test content"
        result = storage_manager_with_url.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        info = storage_manager_with_url.get_file_info(result["storage_path"])
        assert info is not None
        assert info["access_url"] is not None
        assert info["access_url"].startswith(storage_manager_with_url.base_url)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extension_detection_pdf(self, storage_manager):
        """Test PDF extension detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        assert result["storage_path"].endswith(".pdf")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extension_detection_image(self, storage_manager):
        """Test image extension detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="image",
            metadata={"format": "png"}
        )
        assert result["storage_path"].endswith(".png")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extension_detection_text(self, storage_manager):
        """Test text extension detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="text"
        )
        assert result["storage_path"].endswith(".txt")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extension_detection_markdown(self, storage_manager):
        """Test markdown extension detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="markdown"
        )
        assert result["storage_path"].endswith(".md")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_mime_type_detection_pdf(self, storage_manager):
        """Test PDF MIME type detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        assert result["mime_type"] == "application/pdf"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_mime_type_detection_image(self, storage_manager):
        """Test image MIME type detection"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="image",
            metadata={"format": "jpeg"}
        )
        assert result["mime_type"] == "image/jpeg"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_path_organization_by_date(self, storage_manager):
        """Test that files are organized by date"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        # Should have structure: pdf/YYYY/MM/DD/filename
        parts = result["storage_path"].split("/")
        assert parts[0] == "pdf"
        assert len(parts[1]) == 4  # Year
        assert len(parts[2]) == 2  # Month
        assert len(parts[3]) == 2  # Day

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

