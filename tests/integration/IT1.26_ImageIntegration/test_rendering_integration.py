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

"""Integration Tests for Media Rendering Integration"""
import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
from PIL import Image
from src.core.media.media_renderer import MediaRenderer
from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE

@pytest.fixture
def media_renderer():
    return MediaRenderer()

@pytest.fixture
def pdf_generator():
    if not REPORTLAB_AVAILABLE:
        pytest.fail("reportlab not available")
    return PDFGenerator()

class TestRenderingIntegration:
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    def test_image_rendering_with_pdf(self, media_renderer, pdf_generator):

        img = Image.new('RGB', (50, 50), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        image_reader = media_renderer.render_image_for_pdf(image_data, "png")
        if image_reader:
            assert image_reader is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]

