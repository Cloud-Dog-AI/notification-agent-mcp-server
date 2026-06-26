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

"""System Tests for PDF Language and Summary System"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE

@pytest.fixture
def pdf_generator():
    if not REPORTLAB_AVAILABLE:
        pytest.skip("reportlab not available")
    return PDFGenerator()

class TestPDFLanguageSummarySystem:
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    def test_pdf_multilingual_system(self, pdf_generator):
        """Test PDF system with multiple languages"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_multilingual_system"
        )
        languages = {
            "en": "English content",
            "fr": "Contenu français",
            "es": "Contenido español",
            "de": "Deutscher Inhalt"
        }
        
        for lang, content in languages.items():
            pdf = pdf_generator.generate_from_text(content)
            assert pdf is not None
            assert len(pdf) > 0
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_pdf_summary_formats_system(self, pdf_generator):
        """Test PDF system with different summary formats"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_pdf_summary_formats_system"
        )

        formats = {
            "text": "Plain text summary",
            "markdown": "# Markdown Summary\n\nContent here.",
            "html": "<h1>HTML Summary</h1><p>Content</p>"
        }
        
        for fmt, content in formats.items():
            if fmt == "text":
                pdf = pdf_generator.generate_from_text(content)
            elif fmt == "markdown":
                pdf = pdf_generator.generate_from_markdown(content)
            else:
                pdf = pdf_generator.generate_from_html(content)
            
            assert pdf is not None
            assert len(pdf) > 0

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

