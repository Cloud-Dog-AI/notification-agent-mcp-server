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

"""Unit Tests for Media Rendering"""
import pytest
import io
from PIL import Image
from src.core.media.media_renderer import MediaRenderer
from src.core.media.image_handler import ImageHandler
from src.core.media.uuencoding import UUEncoding

@pytest.fixture
def media_renderer():
    return MediaRenderer()

@pytest.fixture
def sample_image():
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

class TestMediaRendering:
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    def test_render_image_for_markdown(self, media_renderer):
        result = media_renderer.render_image_for_markdown("http://example.com/image.png", "Test Image")
        assert "![Test Image]" in result
        assert "http://example.com/image.png" in result
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_render_image_for_text(self, media_renderer):
        result = media_renderer.render_image_for_text("http://example.com/image.png", "Test Image")
        assert "Image: Test Image" in result
        assert "http://example.com/image.png" in result
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_process_images_in_content_markdown(self, media_renderer, sample_image):
        # Use UUEncoded image for reliable test
        encoded = UUEncoding.encode(sample_image, "png")
        content = [{"type": "image", "uuencoded": encoded, "alt_text": "Test"}]
        processed, images = media_renderer.process_images_in_content(content, output_format="markdown")
        assert len(processed) > 0
        # Check if image was processed (may be in body or as separate image block)
        body_text = " ".join([str(b.get("body", "")) for b in processed])
        assert "![Test]" in body_text or len(images) > 0
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_process_images_in_content_text(self, media_renderer, sample_image):
        # Use UUEncoded image for reliable test
        encoded = UUEncoding.encode(sample_image, "png")
        content = [{"type": "image", "uuencoded": encoded, "alt_text": "Test"}]
        processed, images = media_renderer.process_images_in_content(content, output_format="text")
        assert len(processed) > 0
        # Check if image was processed
        body_text = " ".join([str(b.get("body", "")) for b in processed])
        assert "Image: Test" in body_text or len(images) > 0

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

