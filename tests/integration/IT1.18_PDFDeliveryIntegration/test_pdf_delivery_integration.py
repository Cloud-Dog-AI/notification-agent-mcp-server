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
Integration Tests for PDF Delivery Integration

Tests:
- PDF generation in delivery workflow
- PDF attachment for email
- PDF link for Slack
- PDF link for other channels
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
import json

from src.core.formatters.pdf_delivery import PDFDeliveryHelper
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE
from src.core.formatters.pdf_preferences import PDFPreferenceResolver, PDFPreference
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup handled by tempfile


@pytest.fixture
def pdf_helper(temp_storage_dir, storage_base_url):
    """Create PDFDeliveryHelper instance"""
    if not REPORTLAB_AVAILABLE:
        pytest.fail("reportlab not available")
    
    pdf_generator = PDFGenerator()
    preference_resolver = PDFPreferenceResolver()
    storage_manager = StorageManager(
        backend=LocalStorage(base_path=temp_storage_dir),
        base_url=storage_base_url
    )
    
    return PDFDeliveryHelper(
        pdf_generator=pdf_generator,
        preference_resolver=preference_resolver,
        storage_manager=storage_manager
    )


class TestPDFDeliveryIntegration:
    """Test PDF delivery integration"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_generation_for_email_attachment(self, pdf_helper):
        """Test PDF generation for email attachment"""
        content = [{"type": "text", "body": "Test notification content"}]
        
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            user_id=None,
            channel_id=None,
            message_id=1,
            delivery_id=1
        )
        
        assert pdf_info is not None
        assert pdf_info["pdf_bytes"] is not None
        assert len(pdf_info["pdf_bytes"]) > 0
        
        # Test attachment preparation
        attachment = pdf_helper.prepare_pdf_attachment(pdf_info, filename="test.pdf")
        assert attachment is not None
        assert attachment["filename"] == "test.pdf"
        assert attachment["content_type"] == "application/pdf"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_generation_for_slack_link(self, pdf_helper):
        """Test PDF generation for Slack link"""
    


        content = [{"type": "text", "body": "Test notification"}]
        
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            user_id=None,
            channel_id=None,
            message_id=1,
            delivery_id=1
        )
        
        assert pdf_info is not None
        
        # Test link preparation
        pdf_link = pdf_helper.prepare_pdf_link(pdf_info)
        assert pdf_link is not None
        assert "storage" in pdf_link or "pdf" in pdf_link.lower()
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_user_preference_attach(self, pdf_helper):
        """Test PDF generation with user preference for attachment"""
        content = [{"type": "text", "body": "Test"}]
        
        # Use preference resolver directly to set preference
        pdf_helper.preference_resolver.default_preference = "attach"
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            user_id=None,
            channel_id=None,
            message_id=1
        )
        
        assert pdf_info is not None
        assert pdf_info["should_attach"] is True
        assert pdf_info["should_link"] is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_channel_preference_link(self, pdf_helper):
        """Test PDF generation with channel preference for link"""
    


        content = [{"type": "text", "body": "Test"}]
        
        # Use preference resolver directly to set preference
        pdf_helper.preference_resolver.default_preference = "link"
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            user_id=None,
            channel_id=None,
            message_id=1
        )
        
        assert pdf_info is not None
        assert pdf_info["should_attach"] is False
        assert pdf_info["should_link"] is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_language_support(self, pdf_helper):
        """Test PDF generation with language support (Phase 2.5)"""
        content = [{"type": "text", "body": "Test notification"}]
        
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            language="fr",
            message_id=1
        )
        
        assert pdf_info is not None
        assert pdf_info["pdf_bytes"] is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_content_style(self, pdf_helper):
        """Test PDF generation with different content styles (Phase 2.5)"""
    


        content = [{"type": "markdown", "body": "# Heading\n\nContent here."}]
        
        pdf_info = pdf_helper.generate_and_prepare_pdf(
            content=content,
            content_style="markdown",
            message_id=1
        )
        
        assert pdf_info is not None
        assert pdf_info["pdf_bytes"] is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.smtp, pytest.mark.heavy]

