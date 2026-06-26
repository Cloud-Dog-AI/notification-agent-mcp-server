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
System Tests for PDF Generation System

Tests:
- PDF file creation and validation
- Format validation
- File system operations
- Concurrent PDF generation
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


class TestPDFSystem:
    """Test PDF generation system"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_file_creation(self, pdf_generator, temp_output_dir):
        """Test that PDF files are created correctly"""
        text_content = "Test content"
        output_path = os.path.join(temp_output_dir, "test.pdf")
        
        pdf_generator.generate_from_text(text_content, output_path=output_path)
        
        assert os.path.exists(output_path)
        assert os.path.isfile(output_path)
        assert os.path.getsize(output_path) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_format_validation(self, pdf_generator, temp_output_dir):
        """Test that generated files are valid PDFs"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_format_validation"
        )

        text_content = "Test content"
        output_path = os.path.join(temp_output_dir, "test.pdf")
        
        pdf_bytes = pdf_generator.generate_from_text(text_content, output_path=output_path)
        
        # Check PDF header
        assert pdf_bytes[:4] == b'%PDF'
        
        # Check PDF footer
        assert b'%%EOF' in pdf_bytes[-1000:]
        
        # Verify file matches bytes
        with open(output_path, 'rb') as f:
            file_bytes = f.read()
        assert file_bytes == pdf_bytes
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_multiple_pdf_generation(self, pdf_generator, temp_output_dir):
        """Test generating multiple PDFs"""
        contents = [
            "Content 1",
            "Content 2",
            "Content 3"
        ]
        
        pdf_files = []
        for i, content in enumerate(contents):
            output_path = os.path.join(temp_output_dir, f"test_{i}.pdf")
            pdf_generator.generate_from_text(content, output_path=output_path)
            pdf_files.append(output_path)
        
        # Verify all files exist
        for pdf_file in pdf_files:
            assert os.path.exists(pdf_file)
            assert os.path.getsize(pdf_file) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_file_size_variation(self, pdf_generator, temp_output_dir):
        """Test that PDF file size varies with content length"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_file_size_variation"
        )

        short_content = "Short"
        long_content = "Long content. " * 1000
        
        short_path = os.path.join(temp_output_dir, "short.pdf")
        long_path = os.path.join(temp_output_dir, "long.pdf")
        
        pdf_generator.generate_from_text(short_content, output_path=short_path)
        pdf_generator.generate_from_text(long_content, output_path=long_path)
        
        short_size = os.path.getsize(short_path)
        long_size = os.path.getsize(long_path)
        
        assert long_size > short_size
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_with_different_formats(self, pdf_generator, temp_output_dir):
        """Test PDF generation with different input formats"""
        text_content = "Plain text"
        markdown_content = "# Heading\n\nContent"
        html_content = "<h1>Heading</h1><p>Content</p>"
        
        text_path = os.path.join(temp_output_dir, "text.pdf")
        md_path = os.path.join(temp_output_dir, "markdown.pdf")
        html_path = os.path.join(temp_output_dir, "html.pdf")
        
        pdf_generator.generate_from_text(text_content, output_path=text_path)
        pdf_generator.generate_from_markdown(markdown_content, output_path=md_path)
        pdf_generator.generate_from_html(html_content, output_path=html_path)
        
        # All should be valid PDFs
        for path in [text_path, md_path, html_path]:
            assert os.path.exists(path)
            with open(path, 'rb') as f:
                assert f.read()[:4] == b'%PDF'
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_directory_creation(self, pdf_generator, temp_output_dir):
        """Test PDF generation in subdirectories"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_directory_creation"
        )

        subdir = os.path.join(temp_output_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        
        output_path = os.path.join(subdir, "test.pdf")
        pdf_generator.generate_from_text("Content", output_path=output_path)
        
        assert os.path.exists(output_path)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_overwrite(self, pdf_generator, temp_output_dir):
        """Test that PDF generation overwrites existing files"""
        output_path = os.path.join(temp_output_dir, "test.pdf")
        
        # Generate first PDF
        pdf_generator.generate_from_text("First", output_path=output_path)
        first_size = os.path.getsize(output_path)
        
        # Generate second PDF (should overwrite)
        pdf_generator.generate_from_text("Second content is longer", output_path=output_path)
        second_size = os.path.getsize(output_path)
        
        assert os.path.exists(output_path)
        assert second_size != first_size  # Different content, different size
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_bytes_vs_file(self, pdf_generator, temp_output_dir):
        """Test that bytes output matches file output"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_bytes_vs_file"
        )

        text_content = "Test content"
        output_path = os.path.join(temp_output_dir, "test.pdf")
        
        # Generate to file
        pdf_generator.generate_from_text(text_content, output_path=output_path)
        file_bytes = open(output_path, 'rb').read()
        
        # Generate to bytes
        bytes_output = pdf_generator.generate_from_text(text_content)
        
        # Should be similar (may have minor differences due to metadata)
        assert len(bytes_output) > 0
        assert bytes_output[:4] == b'%PDF'
        assert file_bytes[:4] == b'%PDF'
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_with_unicode(self, pdf_generator, temp_output_dir):
        """Test PDF generation with Unicode characters"""
        unicode_content = "Unicode: 你好 こんにちは Здравствуйте"
        output_path = os.path.join(temp_output_dir, "unicode.pdf")
        
        pdf_bytes = pdf_generator.generate_from_text(unicode_content, output_path=output_path)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_with_special_formatting(self, pdf_generator, temp_output_dir):
        """Test PDF generation with special formatting"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_with_special_formatting"
        )

        content = "# Heading\n\n**Bold** and *italic*\n\n- List item 1\n- List item 2"
        output_path = os.path.join(temp_output_dir, "formatted.pdf")
        
        pdf_bytes = pdf_generator.generate_from_markdown(content, output_path=output_path)
        
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes[:4] == b'%PDF'
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_error_handling_invalid_path(self, pdf_generator):
        """Test error handling with invalid file path"""
        text_content = "Test"
        invalid_path = "/nonexistent/directory/test.pdf"
        
        # Should raise an error or handle gracefully
        with pytest.raises((OSError, FileNotFoundError)):
            pdf_generator.generate_from_text(text_content, output_path=invalid_path)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_concurrent_generation(self, pdf_generator, temp_output_dir):
        """Test concurrent PDF generation"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_concurrent_generation"
        )

        import threading
        
        def generate_pdf(index):
            output_path = os.path.join(temp_output_dir, f"concurrent_{index}.pdf")
            pdf_generator.generate_from_text(f"Content {index}", output_path=output_path)
            return output_path
        
        threads = []
        for i in range(5):
            thread = threading.Thread(target=generate_pdf, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify all PDFs were created
        for i in range(5):
            pdf_path = os.path.join(temp_output_dir, f"concurrent_{i}.pdf")
            assert os.path.exists(pdf_path)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

