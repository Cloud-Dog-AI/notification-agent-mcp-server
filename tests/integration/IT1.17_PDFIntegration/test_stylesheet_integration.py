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
Integration Tests for Stylesheet Integration with PDF Generator

Tests:
- Stylesheet integration with PDF generator
- PDF generation with stylesheets
- Channel-specific stylesheet application
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

from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE
from src.core.formatters.stylesheets import StylesheetManager


@pytest.fixture
def temp_stylesheets_dir():
    """Create temporary stylesheets directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    for file in Path(temp_dir).glob("*.css"):
        try:
            os.remove(file)
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass


@pytest.fixture
def stylesheet_manager(temp_stylesheets_dir):
    """Create StylesheetManager instance"""
    return StylesheetManager(stylesheets_dir=temp_stylesheets_dir)


@pytest.fixture
def pdf_generator_with_stylesheet(temp_stylesheets_dir):
    """Create PDF generator with stylesheet"""
    if not REPORTLAB_AVAILABLE:
        pytest.fail("reportlab not available")
    
    default_css = "body { font-family: Arial; }"
    stylesheet_path = os.path.join(temp_stylesheets_dir, "default.css")
    with open(stylesheet_path, 'w') as f:
        f.write(default_css)
    
    return PDFGenerator(stylesheet_path=stylesheet_path)


class TestStylesheetIntegration:
    """Test stylesheet integration with PDF generator"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_generation_with_stylesheet(self, pdf_generator_with_stylesheet):
        """Test PDF generation with stylesheet"""
        html_content = "<h1>Test</h1><p>Content</p>"
        
        pdf_bytes = pdf_generator_with_stylesheet.generate_from_html(html_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_pdf_generation_without_stylesheet(self):
        """Test PDF generation without stylesheet"""
    


        if not REPORTLAB_AVAILABLE:
            pytest.fail("reportlab not available")
        
        pdf_generator = PDFGenerator()  # No stylesheet
        html_content = "<h1>Test</h1><p>Content</p>"
        
        pdf_bytes = pdf_generator.generate_from_html(html_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_stylesheet_manager_with_pdf_generator(self, stylesheet_manager, temp_stylesheets_dir):
        """Test stylesheet manager integration with PDF generator"""
        if not REPORTLAB_AVAILABLE:
            pytest.fail("reportlab not available")
        
        # Create stylesheet
        css_content = "body { font-family: 'Times New Roman'; }"
        stylesheet_manager.save_stylesheet("custom.css", css_content)
        
        # Get stylesheet path
        stylesheet_path = stylesheet_manager.get_stylesheet_path("custom.css")
        
        # Create PDF generator with stylesheet
        pdf_generator = PDFGenerator(stylesheet_path=str(stylesheet_path))
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_from_text("Test content")
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_channel_stylesheet_with_pdf(self, stylesheet_manager, temp_stylesheets_dir):
        """Test channel-specific stylesheet with PDF generation"""
    


        if not REPORTLAB_AVAILABLE:
            pytest.fail("reportlab not available")
        
        channel_id = 5
        channel_css = "body { color: #333333; }"
        stylesheet_manager.set_channel_stylesheet(channel_id, channel_css)
        
        # Get channel stylesheet path
        channel_stylesheet_path = stylesheet_manager.get_stylesheet_path(f"channel_{channel_id}.css")
        
        # Create PDF generator with channel stylesheet
        pdf_generator = PDFGenerator(stylesheet_path=str(channel_stylesheet_path))
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_from_text("Channel-specific content")
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_default_stylesheet_fallback(self, stylesheet_manager, temp_stylesheets_dir):
        """Test default stylesheet fallback"""
        if not REPORTLAB_AVAILABLE:
            pytest.fail("reportlab not available")
        
        # Create default stylesheet
        default_css = "body { font-size: 12pt; }"
        stylesheet_manager.save_stylesheet("default.css", default_css)
        
        # Get default path
        default_path = stylesheet_manager.get_stylesheet_path()
        
        # Create PDF generator
        pdf_generator = PDFGenerator(stylesheet_path=str(default_path))
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_from_text("Test")
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_stylesheet_application_to_markdown(self, pdf_generator_with_stylesheet):
        """Test stylesheet application to Markdown-generated PDF"""
    


        markdown_content = "# Heading\n\nContent here."
        
        pdf_bytes = pdf_generator_with_stylesheet.generate_from_markdown(markdown_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_stylesheet_application_to_html(self, pdf_generator_with_stylesheet):
        """Test stylesheet application to HTML-generated PDF"""
        html_content = "<h1>Heading</h1><p>Content</p>"
        
        pdf_bytes = pdf_generator_with_stylesheet.generate_from_html(html_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]

