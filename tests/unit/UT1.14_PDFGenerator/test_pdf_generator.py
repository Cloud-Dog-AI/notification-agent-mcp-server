# @pytest.mark.req("UC-023")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Unit Tests for PDF Generator

Tests:
- PDF generator initialization
- Text to PDF conversion
- Markdown to PDF conversion
- HTML to PDF conversion
- Error handling
"""

import pytest
import tempfile
import os
from pathlib import Path

import src.core.formatters.pdf_generator as pdf_generator_module
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE


@pytest.fixture
def pdf_generator():
    """Create PDF generator instance"""
    if not REPORTLAB_AVAILABLE:
        pytest.skip("reportlab not available")
    return PDFGenerator()


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    for file in Path(temp_dir).glob("*.pdf"):
        try:
            os.remove(file)
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass


class TestPDFGenerator:
    """Test PDF generator functionality"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_initialization(self):
        """Test PDF generator initialization"""
        if not REPORTLAB_AVAILABLE:
            pytest.skip("reportlab not available")
        
        generator = PDFGenerator()
        assert generator is not None
        assert generator.styles is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_initialization_with_stylesheet(self, temp_output_dir):
        """Test PDF generator initialization with stylesheet path"""
        if not REPORTLAB_AVAILABLE:
            pytest.skip("reportlab not available")
        
        stylesheet_path = os.path.join(temp_output_dir, "test.css")
        with open(stylesheet_path, 'w') as f:
            f.write("body { font-family: Arial; }")
        
        generator = PDFGenerator(stylesheet_path=stylesheet_path)
        assert generator is not None
        assert generator.stylesheet_path == stylesheet_path
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_text_basic(self, pdf_generator, temp_output_dir):
        """Test basic text to PDF conversion"""
        text_content = "This is a test message.\nIt has multiple lines."
        output_path = os.path.join(temp_output_dir, "test_text.pdf")
        
        pdf_bytes = pdf_generator.generate_from_text(
            text_content,
            output_path=output_path
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
        # Verify PDF header
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_text_with_title(self, pdf_generator, temp_output_dir):
        """Test text to PDF with title"""
        text_content = "This is the body content."
        output_path = os.path.join(temp_output_dir, "test_title.pdf")
        
        pdf_bytes = pdf_generator.generate_from_text(
            text_content,
            output_path=output_path,
            title="Test Document"
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert os.path.exists(output_path)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_text_bytes_output(self, pdf_generator):
        """Test text to PDF returning bytes (no file)"""
        text_content = "This is a test message."
        
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_markdown_basic(self, pdf_generator, temp_output_dir):
        """Test basic Markdown to PDF conversion"""
        markdown_content = "# Heading 1\n\nThis is **bold** text.\n\n## Heading 2\n\nRegular text."
        output_path = os.path.join(temp_output_dir, "test_markdown.pdf")
        
        pdf_bytes = pdf_generator.generate_from_markdown(
            markdown_content,
            output_path=output_path
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert os.path.exists(output_path)
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_markdown_with_title(self, pdf_generator, temp_output_dir):
        """Test Markdown to PDF with title"""
        markdown_content = "This is markdown content."
        output_path = os.path.join(temp_output_dir, "test_md_title.pdf")
        
        pdf_bytes = pdf_generator.generate_from_markdown(
            markdown_content,
            output_path=output_path,
            title="Markdown Document"
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_html_basic(self, pdf_generator, temp_output_dir):
        """Test basic HTML to PDF conversion"""
        html_content = "<h1>Heading 1</h1><p>This is a paragraph.</p><h2>Heading 2</h2>"
        output_path = os.path.join(temp_output_dir, "test_html.pdf")
        
        pdf_bytes = pdf_generator.generate_from_html(
            html_content,
            output_path=output_path
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert os.path.exists(output_path)
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_from_html_with_title(self, pdf_generator, temp_output_dir):
        """Test HTML to PDF with title"""
        html_content = "<p>HTML content here.</p>"
        output_path = os.path.join(temp_output_dir, "test_html_title.pdf")
        
        pdf_bytes = pdf_generator.generate_from_html(
            html_content,
            output_path=output_path,
            title="HTML Document"
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_auto_detect_text(self, pdf_generator):
        """Test generate() method with text content"""
        text_content = "Plain text content."
        
        pdf_bytes = pdf_generator.generate(content=text_content, content_type='text')
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_auto_detect_markdown(self, pdf_generator):
        """Test generate() method with markdown content"""
        markdown_content = "# Heading\n\nContent here."
        
        pdf_bytes = pdf_generator.generate(content=markdown_content, content_type='markdown')
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_auto_detect_html(self, pdf_generator):
        """Test generate() method with HTML content"""
        html_content = "<h1>Heading</h1><p>Content</p>"
        
        pdf_bytes = pdf_generator.generate(content=html_content, content_type='html')
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_generate_with_metadata(self, pdf_generator, temp_output_dir):
        """Test PDF generation with metadata"""
        text_content = "Test content"
        output_path = os.path.join(temp_output_dir, "test_metadata.pdf")
        metadata = {
            "author": "Test Author",
            "subject": "Test Subject",
            "keywords": "test, pdf, generation"
        }
        
        pdf_bytes = pdf_generator.generate_from_text(
            text_content,
            output_path=output_path,
            metadata=metadata
        )
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_empty_content(self, pdf_generator):
        """Test PDF generation with empty content"""
        pdf_bytes = pdf_generator.generate_from_text("")
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_multiline_content(self, pdf_generator):
        """Test PDF generation with multiline content"""
        text_content = "Line 1\nLine 2\nLine 3\n\nParagraph 2\nMore text."
        
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_special_characters(self, pdf_generator):
        """Test PDF generation with special characters"""
        text_content = "Special chars: <>&\"' &amp; &lt; &gt;"
        
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_long_content(self, pdf_generator):
        """Test PDF generation with long content"""
        text_content = "This is a long line. " * 100 + "\n\n" + "Another paragraph. " * 50
        
        pdf_bytes = pdf_generator.generate_from_text(text_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_markdown_headings(self, pdf_generator):
        """Test Markdown heading conversion"""
        markdown_content = "# H1\n## H2\n### H3\n\nRegular text."
        
        pdf_bytes = pdf_generator.generate_from_markdown(markdown_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_html_paragraphs(self, pdf_generator):
        """Test HTML paragraph conversion"""
        html_content = "<p>Paragraph 1</p><p>Paragraph 2</p><div>Div content</div>"
        
        pdf_bytes = pdf_generator.generate_from_html(html_content)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_error_handling_missing_reportlab(self, monkeypatch):
        """Test error handling when reportlab is not available"""
        monkeypatch.setattr(pdf_generator_module, "REPORTLAB_AVAILABLE", False)
        with pytest.raises(ImportError):
            pdf_generator_module.PDFGenerator()

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

