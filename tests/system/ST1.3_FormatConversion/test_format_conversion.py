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
Tests for generic format conversion (PDF→HTML, DOC→text, etc.)
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.database.db_manager import DatabaseManager
from src.core.llm.runtime_client import LLMManager
from src.core.formatters.format_converter import FormatConverter
from src.config import get_config


@pytest.fixture
def db():
    """Create test database"""
    import os
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    test_db_path = project_root / "database" / "test_format_converter.db"
    
    if test_db_path.exists():
        test_db_path.unlink()
    
    test_db_path.parent.mkdir(parents=True, exist_ok=True)
    
    db = DatabaseManager(f"sqlite3:///{test_db_path}")
    db.connect()
    
    yield db
    
    db.disconnect()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def llm_manager(monkeypatch):
    """Create LLM manager (mocked for unit tests)"""
    config = get_config()
    
    # Mock LLM manager to avoid real LLM calls in unit tests
    class MockLLMManager:
        def __init__(self, config):
            self.config = config
            self.llm = self
            self.provider = "mock"
        
        def connect(self):
            return True
        
        def get_llm(self):
            return self
        
        def invoke(self, prompt, **kwargs):
            # Return mock response that simulates actual conversion
            # Check the prompt to return appropriate mock content
            prompt_lower = prompt.lower()
            
            # Check source and target format from prompt
            # Prompt format: "Convert the following TEXT content to HTML format..."
            if "convert the following text" in prompt_lower and "to html" in prompt_lower:
                # TEXT→HTML conversion
                if "Subtitle" in prompt:
                    return "<h1>Title</h1><h2>Subtitle</h2><ul><li>Item 1</li><li>Item 2</li></ul>"
                return "<h1>Title</h1><p>Subtitle</p><ul><li>Item 1</li><li>Item 2</li></ul>"
            elif "convert the following markdown" in prompt_lower and "to html" in prompt_lower:
                # MARKDOWN→HTML conversion
                if "Title" in prompt:
                    return "<h1>Title</h1><h2>Subtitle</h2><ul><li>Item 1</li><li>Item 2</li></ul><p><strong>Bold text</strong> and <em>italic text</em></p>"
                return "<h1>Title</h1><h2>Subtitle</h2><ul><li>Item 1</li><li>Item 2</li></ul>"
            elif "convert the following html" in prompt_lower and "to text" in prompt_lower:
                # HTML→TEXT conversion
                return "Title\nParagraph with bold text.\nItem 1\nItem 2"
            elif "convert the following pdf" in prompt_lower and "to html" in prompt_lower:
                # PDF→HTML conversion
                return "<h1>Document Title</h1><p>Author: Test</p><p>Date: 2025-11-11</p><h2>Section 1</h2><p>Content paragraph 1.</p><p>Content paragraph 2.</p><h2>Section 2</h2><p>More content here.</p>"
            elif "convert the following doc" in prompt_lower and "to text" in prompt_lower:
                # DOC→TEXT conversion
                return "Document Title\nAuthor: Test\nDate: 2025-11-11\n\nSection 1\nContent here."
            else:
                # Generic fallback based on content
                if "Title" in prompt and "Subtitle" in prompt:
                    return "<h1>Title</h1><h2>Subtitle</h2><ul><li>Item 1</li><li>Item 2</li></ul>"
                elif "Title" in prompt:
                    return "Title\nSubtitle\nItem 1\nItem 2"
                return "Mock converted content"
    
    return MockLLMManager(config)


@pytest.fixture
def format_converter(llm_manager):
    """Create format converter"""
    return FormatConverter(llm_manager)


class TestFormatConverter:
    """Test format conversion functionality"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_1_convert_markdown_to_html(self, format_converter):
        """V20.1: Convert Markdown to HTML"""
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_1_convert_markdown_to_html"
        )
        markdown_content = """# Title
## Subtitle
- Item 1
- Item 2
**Bold text** and *italic text*
"""
        result = format_converter.convert(
            content=markdown_content,
            source_format="markdown",
            target_format="html",
        )
        
        assert "<h1>" in result or "<h2>" in result or "<ul>" in result
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_2_convert_markdown_to_text(self, format_converter):
        """V20.2: Convert Markdown to plain text with formatting"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_2_convert_markdown_to_text"
        )
        markdown_content = """# Title
## Subtitle
- Item 1
- Item 2
"""
        result = format_converter.convert(
            content=markdown_content,
            source_format="markdown",
            target_format="text",
        )
        
        # Should preserve structure (underlines, bullets)
        assert "Title" in result
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_3_convert_html_to_text(self, format_converter):
        """V20.3: Convert HTML to plain text"""
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_3_convert_html_to_text"
        )
        html_content = """<h1>Title</h1>
<p>Paragraph with <strong>bold</strong> text.</p>
<ul>
<li>Item 1</li>
<li>Item 2</li>
</ul>
"""
        result = format_converter.convert(
            content=html_content,
            source_format="html",
            target_format="text",
        )
        
        # Should strip HTML tags
        assert "<h1>" not in result
        assert "Title" in result
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_4_convert_text_to_html(self, format_converter):
        """V20.4: Convert plain text to HTML"""
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_4_convert_text_to_html"
        )
        text_content = """Title
Subtitle
- Item 1
- Item 2
"""
        result = format_converter.convert(
            content=text_content,
            source_format="text",
            target_format="html",
        )
        
        # Should add HTML structure
        assert "<" in result and ">" in result
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_5_convert_with_options(self, format_converter):
        """V20.5: Convert with options (preserve_structure, include_metadata)"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_5_convert_with_options"
        )
        markdown_content = """# Document Title
Author: Test Author
Date: 2025-11-11

## Section 1
Content here.
"""
        result = format_converter.convert(
            content=markdown_content,
            source_format="markdown",
            target_format="html",
            options={
                "preserve_structure": True,
                "include_metadata": True,
            },
        )
        
        assert len(result) > 0
        # Structure should be preserved
        assert "Document Title" in result or "Title" in result
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_6_fallback_conversion(self, format_converter):
        """V20.6: Fallback conversion when LLM unavailable"""
        # This test works even if LLM is unavailable
        markdown_content = "# Title\n\nContent"
        result = format_converter.convert(
            content=markdown_content,
            source_format="markdown",
            target_format="html",
        )
        
        # Should return something (even if fallback)
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_7_unsupported_format_handling(self, format_converter):
        """V20.7: Handle unsupported format gracefully"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_7_unsupported_format_handling"
        )

        content = "Some content"
        result = format_converter.convert(
            content=content,
            source_format="unknown_format",
            target_format="text",
        )
        
        # Should default to text and return content
        assert len(result) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_8_pdf_to_html_simulation(self, format_converter):
        """V20.8: Simulate PDF to HTML conversion (using text as PDF content)"""
        # Simulate PDF content (structured text)
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_8_pdf_to_html_simulation"
        )
        pdf_like_content = """DOCUMENT TITLE
Author: Test
Date: 2025-11-11

SECTION 1
Content paragraph 1.
Content paragraph 2.

SECTION 2
More content here.
"""
        result = format_converter.convert(
            content=pdf_like_content,
            source_format="pdf",
            target_format="html",
        )
        
        assert len(result) > 0
        # Should convert to HTML structure
        assert "<" in result and ">" in result
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_v20_9_doc_to_text_simulation(self, format_converter):
        """V20.9: Simulate DOC to text conversion"""
        # Simulate DOC content (structured text)
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_v20_9_doc_to_text_simulation"
        )
        doc_like_content = """Title: Document Title
Author: Test Author

Paragraph 1 with formatting.
Paragraph 2 with more content.
"""
        result = format_converter.convert(
            content=doc_like_content,
            source_format="doc",
            target_format="text",
        )
        
        assert len(result) > 0
        # Should be plain text
        assert "Document Title" in result or "Title" in result

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.db, pytest.mark.smtp, pytest.mark.slow]

