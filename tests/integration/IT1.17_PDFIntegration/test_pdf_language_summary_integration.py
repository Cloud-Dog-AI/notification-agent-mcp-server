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

"""Integration Tests for PDF Language and Summary Integration"""
import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE
from src.core.formatters.pdf_delivery import PDFDeliveryHelper
from src.core.formatters.pdf_preferences import PDFPreferenceResolver
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage
import tempfile

@pytest.fixture
def pdf_helper(storage_base_url):
    if not REPORTLAB_AVAILABLE:
        pytest.fail("reportlab not available")
    temp_dir = tempfile.mkdtemp()
    pdf_gen = PDFGenerator()
    pref_res = PDFPreferenceResolver()
    storage = StorageManager(backend=LocalStorage(base_path=temp_dir), base_url=storage_base_url)
    return PDFDeliveryHelper(pdf_generator=pdf_gen, preference_resolver=pref_res, storage_manager=storage)

class TestPDFLanguageSummaryIntegration:
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    def test_pdf_with_language_integration(self, pdf_helper):
        """Test PDF generation with language integration"""
        content = [{"type": "text", "body": "Test content"}]
        pdf_info = pdf_helper.generate_and_prepare_pdf(content=content, language="fr", message_id=1)
        assert pdf_info is not None
        assert pdf_info["pdf_bytes"] is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_with_summary_integration(self, pdf_helper):
        """Test PDF generation with summary integration"""


        content = [{"type": "markdown", "body": "# Summary\n\nContent"}]
        pdf_info = pdf_helper.generate_and_prepare_pdf(content=content, content_style="markdown", message_id=1)
        assert pdf_info is not None
        assert pdf_info["pdf_bytes"] is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]

