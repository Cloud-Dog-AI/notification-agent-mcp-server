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
System Tests for Storage System

Tests:
- Storage system functionality
- File system operations
- Access control
- Path organization
- Error handling
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
import shutil
from datetime import datetime

from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def local_storage(temp_storage_dir):
    """Create LocalStorage instance with temp directory"""
    return LocalStorage(base_path=temp_storage_dir)


@pytest.fixture
def storage_manager(local_storage):
    """Create StorageManager with LocalStorage"""
    return StorageManager(backend=local_storage)


@pytest.fixture
def storage_manager_with_url(local_storage, storage_base_url):
    """Create StorageManager with base URL"""
    return StorageManager(backend=local_storage, base_url=storage_base_url)


class TestStorageSystem:
    """Test storage system functionality"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_storage_directory_creation(self, temp_storage_dir):
        """Test that storage directory is created automatically"""
        storage = LocalStorage(base_path=temp_storage_dir)
        assert os.path.exists(temp_storage_dir)
        assert os.path.isdir(temp_storage_dir)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_store_and_retrieve_file(self, storage_manager):
        """Test storing and retrieving a file"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_store_and_retrieve_file"
        )

        content = b"test file content for system test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        # Verify file was stored
        assert storage_manager.file_exists(result["storage_path"])
        
        # Retrieve file
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == content
        assert len(retrieved) == len(content)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_file_size_calculation(self, storage_manager):
        """Test file size calculation"""
        content = b"x" * 1000  # 1000 bytes
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert result["file_size"] == 1000
        
        info = storage_manager.get_file_info(result["storage_path"])
        assert info["file_size"] == 1000
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_path_organization_structure(self, storage_manager):
        """Test that files are organized in date-based structure"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_path_organization_structure"
        )

        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        # Check path structure: pdf/YYYY/MM/DD/filename
        path_parts = result["storage_path"].split("/")
        assert len(path_parts) >= 4
        assert path_parts[0] == "pdf"
        
        # Verify date parts are valid
        year = int(path_parts[1])
        month = int(path_parts[2])
        day = int(path_parts[3])
        
        now = datetime.now()
        assert year == now.year
        assert month == now.month
        assert day == now.day
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_multiple_files_same_type(self, storage_manager):
        """Test storing multiple files of the same type"""
        files = []
        for i in range(5):
            content = f"test content {i}".encode()
            result = storage_manager.store_file(
                file_content=content,
                file_type="pdf",
                message_id=i
            )
            files.append(result)
        
        # Verify all files exist
        for file_info in files:
            assert storage_manager.file_exists(file_info["storage_path"])
            retrieved = storage_manager.retrieve_file(file_info["storage_path"])
            assert retrieved is not None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_different_file_types(self, storage_manager):
        """Test storing different file types"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_different_file_types"
        )

        pdf_content = b"PDF content"
        image_content = b"Image content"
        text_content = b"Text content"
        
        pdf_result = storage_manager.store_file(
            file_content=pdf_content,
            file_type="pdf"
        )
        image_result = storage_manager.store_file(
            file_content=image_content,
            file_type="image",
            metadata={"format": "png"}
        )
        text_result = storage_manager.store_file(
            file_content=text_content,
            file_type="text"
        )
        
        # Verify all files exist and are in correct directories
        assert "pdf/" in pdf_result["storage_path"]
        assert pdf_result["storage_path"].endswith(".pdf")
        assert pdf_result["mime_type"] == "application/pdf"
        
        assert "image/" in image_result["storage_path"]
        assert image_result["storage_path"].endswith(".png")
        assert "image/png" in image_result["mime_type"]
        
        assert "text/" in text_result["storage_path"] or "pdf/" in text_result["storage_path"]  # May be in same date folder
        assert text_result["storage_path"].endswith(".txt")
        assert text_result["mime_type"] == "text/plain"
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_delete_file(self, storage_manager):
        """Test deleting a file"""
        content = b"test content"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        # Verify file exists
        assert storage_manager.file_exists(result["storage_path"])
        
        # Delete file
        deleted = storage_manager.delete_file(result["storage_path"])
        assert deleted is True
        
        # Verify file no longer exists
        assert not storage_manager.file_exists(result["storage_path"])
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved is None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_delete_nonexistent_file(self, storage_manager):
        """Test deleting a non-existent file"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_delete_nonexistent_file"
        )

        deleted = storage_manager.delete_file("nonexistent/file.pdf")
        assert deleted is False
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_file_exists_check(self, storage_manager):
        """Test file existence checking"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert storage_manager.file_exists(result["storage_path"])
        assert not storage_manager.file_exists("nonexistent/file.pdf")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_access_url_generation(self, storage_manager_with_url):
        """Test access URL generation"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_access_url_generation"
        )

        content = b"test"
        result = storage_manager_with_url.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert "access_url" in result
        assert result["access_url"].startswith(storage_manager_with_url.base_url)
        assert result["storage_path"] in result["access_url"]
        
        info = storage_manager_with_url.get_file_info(result["storage_path"])
        assert info["access_url"] is not None
        assert info["access_url"].startswith(storage_manager_with_url.base_url)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_no_access_url_without_base(self, storage_manager):
        """Test that access URL is None without base URL"""
        content = b"test"
        result = storage_manager.store_file(
            file_content=content,
            file_type="pdf"
        )
        
        assert result.get("access_url") is None
        
        info = storage_manager.get_file_info(result["storage_path"])
        assert info.get("access_url") is None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_large_file_handling(self, storage_manager):
        """Test handling of large files"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_large_file_handling"
        )

        large_content = b"x" * (10 * 1024 * 1024)  # 10MB
        result = storage_manager.store_file(
            file_content=large_content,
            file_type="pdf"
        )
        
        assert result["file_size"] == 10 * 1024 * 1024
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert len(retrieved) == 10 * 1024 * 1024
        assert retrieved == large_content
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_concurrent_file_operations(self, storage_manager):
        """Test concurrent file operations"""
        import threading
        
        results = []
        errors = []
        
        def store_file(index):
            try:
                content = f"content {index}".encode()
                result = storage_manager.store_file(
                    file_content=content,
                    file_type="pdf",
                    message_id=index
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        threads = []
        for i in range(10):
            thread = threading.Thread(target=store_file, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all files were stored
        assert len(results) == 10
        assert len(errors) == 0
        
        # Verify all files exist and can be retrieved
        for result in results:
            assert storage_manager.file_exists(result["storage_path"])
            retrieved = storage_manager.retrieve_file(result["storage_path"])
            assert retrieved is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

