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

"""Unit Tests for PDF Language and Summary Support"""
import pytest
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE

@pytest.fixture
def pdf_generator():
    if not REPORTLAB_AVAILABLE:
        pytest.skip("reportlab not available")
    return PDFGenerator()

class TestPDFLanguageSummary:
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    def test_pdf_with_different_languages(self, pdf_generator):
        """Test PDF generation with different languages"""
        content_en = "Hello, this is a test."
        content_fr = "Bonjour, ceci est un test."
        
        pdf_en = pdf_generator.generate_from_text(content_en)
        pdf_fr = pdf_generator.generate_from_text(content_fr)
        
        assert pdf_en is not None
        assert pdf_fr is not None
        assert len(pdf_en) > 0
        assert len(pdf_fr) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_pdf_with_markdown_summary(self, pdf_generator):
        """Test PDF generation from Markdown summary"""
        markdown = "# Summary\n\nThis is a summary of the notification."
        pdf = pdf_generator.generate_from_markdown(markdown)
        assert pdf is not None
        assert len(pdf) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_pdf_with_html_content(self, pdf_generator):
        """Test PDF generation from HTML content"""
        html = "<h1>Title</h1><p>Content</p>"
        pdf = pdf_generator.generate_from_html(html)
        assert pdf is not None
        assert len(pdf) > 0

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

