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
Integration Tests for PDF Generator Integration

Tests:
- PDF generator integration with storage manager
- PDF generator integration with LLM formatter
- End-to-end PDF generation workflow
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

from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage


@pytest.fixture
def pdf_generator():
    """Create PDF generator instance"""
    if not REPORTLAB_AVAILABLE:
        pytest.fail("reportlab not available")
    return PDFGenerator()


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def storage_manager(temp_storage_dir, storage_base_url):
    """Create StorageManager with LocalStorage"""
    local_storage = LocalStorage(base_path=temp_storage_dir)
    return StorageManager(backend=local_storage, base_url=storage_base_url)


class TestPDFIntegration:
    """Test PDF generator integration"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_generation_with_storage(self, pdf_generator, storage_manager):
        """Test PDF generation and storage integration"""
        text_content = "Test notification content"
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        assert result is not None
        assert result["storage_path"] is not None
        assert result["file_size"] == len(pdf_bytes)
        assert result["mime_type"] == "application/pdf"
        
        # Verify file exists in storage
        assert storage_manager.file_exists(result["storage_path"])
        
        # Retrieve and verify
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved == pdf_bytes
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_from_markdown_with_storage(self, pdf_generator, storage_manager):
        """Test Markdown to PDF with storage"""
    


        markdown_content = "# Notification\n\nThis is a **test** notification."
        
        # Generate PDF from Markdown
        pdf_bytes = pdf_generator.generate_from_markdown(markdown_content)
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        assert result is not None
        assert storage_manager.file_exists(result["storage_path"])
        
        # Verify PDF content
        retrieved = storage_manager.retrieve_file(result["storage_path"])
        assert retrieved[:4] == b'%PDF'
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_from_html_with_storage(self, pdf_generator, storage_manager):
        """Test HTML to PDF with storage"""
        html_content = "<h1>Notification</h1><p>This is a test notification.</p>"
        
        # Generate PDF from HTML
        pdf_bytes = pdf_generator.generate_from_html(html_content)
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        assert result is not None
        assert storage_manager.file_exists(result["storage_path"])
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_metadata_storage(self, pdf_generator, storage_manager):
        """Test PDF generation with metadata and storage"""
    


        text_content = "Test content"
        metadata = {
            "author": "Test System",
            "subject": "Test Notification"
        }
        
        # Generate PDF with metadata
        pdf_bytes = pdf_generator.generate_from_text(
            text_content,
            metadata=metadata
        )
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf",
            metadata={"author": metadata["author"], "subject": metadata["subject"]}
        )
        
        assert result is not None
        assert result["mime_type"] == "application/pdf"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_multiple_pdfs_storage(self, pdf_generator, storage_manager):
        """Test storing multiple PDFs"""
        contents = [
            "Notification 1",
            "Notification 2",
            "Notification 3"
        ]
        
        stored_paths = []
        for i, content in enumerate(contents):
            # Generate PDF
            pdf_bytes = pdf_generator.generate_from_text(content)
            
            # Store PDF
            result = storage_manager.store_file(
                file_content=pdf_bytes,
                file_type="pdf"
            )
            
            stored_paths.append(result["storage_path"])
        
        # Verify all PDFs are stored
        for path in stored_paths:
            assert storage_manager.file_exists(path)
            retrieved = storage_manager.retrieve_file(path)
            assert retrieved[:4] == b'%PDF'
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_storage_retrieval_workflow(self, pdf_generator, storage_manager):
        """Test complete PDF storage and retrieval workflow"""
    


        text_content = "Complete workflow test"
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        original_size = len(pdf_bytes)
        
        # Store PDF
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        storage_path = result["storage_path"]
        
        # Retrieve PDF
        retrieved_bytes = storage_manager.retrieve_file(storage_path)
        
        # Verify
        assert retrieved_bytes is not None
        assert len(retrieved_bytes) == original_size
        assert retrieved_bytes == pdf_bytes
        assert retrieved_bytes[:4] == b'%PDF'
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_storage_info(self, pdf_generator, storage_manager):
        """Test PDF storage info retrieval"""
        text_content = "Test for storage info"
        
        # Generate and store PDF
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        # Get file info
        info = storage_manager.get_file_info(result["storage_path"])
        
        assert info is not None
        assert info["file_size"] == len(pdf_bytes)
        # mime_type may or may not be in info depending on backend
        if "mime_type" in info:
            assert info["mime_type"] == "application/pdf"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_storage_deletion(self, pdf_generator, storage_manager):
        """Test PDF storage and deletion"""
    


        text_content = "Test for deletion"
        
        # Generate and store PDF
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        result = storage_manager.store_file(
            file_content=pdf_bytes,
            file_type="pdf"
        )
        
        storage_path = result["storage_path"]
        assert storage_manager.file_exists(storage_path)
        
        # Delete PDF
        storage_manager.delete_file(storage_path)
        
        # Verify deletion
        assert not storage_manager.file_exists(storage_path)
        assert storage_manager.retrieve_file(storage_path) is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]

