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
Unit Tests for Image Handler

Tests:
- Image format detection (PNG, GIF, JPEG)
- Image validation
- Metadata extraction
- Error handling
"""
import pytest
import io
from PIL import Image

from src.core.media.image_handler import ImageHandler, ImageFormat, ImageMetadata


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


@pytest.fixture
def sample_png():
    """Create sample PNG image"""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


@pytest.fixture
def sample_jpeg():
    """Create sample JPEG image"""
    img = Image.new('RGB', (100, 100), color='blue')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


@pytest.fixture
def sample_gif():
    """Create sample GIF image"""
    img = Image.new('RGB', (100, 100), color='green')
    buffer = io.BytesIO()
    img.save(buffer, format='GIF')
    return buffer.getvalue()


class TestImageFormatDetection:
    """Test image format detection"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_png_format(self, image_handler, sample_png):
        """Test PNG format detection"""
        format = image_handler.detect_format(sample_png)
        assert format == ImageFormat.PNG
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_jpeg_format(self, image_handler, sample_jpeg):
        """Test JPEG format detection"""
        format = image_handler.detect_format(sample_jpeg)
        assert format == ImageFormat.JPEG
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_gif_format(self, image_handler, sample_gif):
        """Test GIF format detection"""
        format = image_handler.detect_format(sample_gif)
        assert format == ImageFormat.GIF
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_empty_data(self, image_handler):
        """Test format detection with empty data"""
        format = image_handler.detect_format(b"")
        assert format is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_invalid_data(self, image_handler):
        """Test format detection with invalid data"""
        format = image_handler.detect_format(b"not an image")
        assert format is None


class TestImageValidation:
    """Test image validation"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_png(self, image_handler, sample_png):
        """Test PNG validation"""
        is_valid, error = image_handler.validate_image(sample_png)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_jpeg(self, image_handler, sample_jpeg):
        """Test JPEG validation"""
        is_valid, error = image_handler.validate_image(sample_jpeg)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_gif(self, image_handler, sample_gif):
        """Test GIF validation"""
        is_valid, error = image_handler.validate_image(sample_gif)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_empty_data(self, image_handler):
        """Test validation with empty data"""
        is_valid, error = image_handler.validate_image(b"")
        assert is_valid is False
        assert "empty" in error.lower()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_invalid_data(self, image_handler):
        """Test validation with invalid data"""
        is_valid, error = image_handler.validate_image(b"not an image")
        assert is_valid is False
        assert error is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_oversized_image(self, image_handler):
        """Test validation with oversized image"""
        # Create a large image (exceeds default 10MB limit)
        large_data = b"x" * (11 * 1024 * 1024)  # 11MB
        is_valid, error = image_handler.validate_image(large_data)
        assert is_valid is False
        assert "size" in error.lower() or "exceeds" in error.lower()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_custom_limits(self):
        """Test validation with custom size limits"""
        handler = ImageHandler(max_width=50, max_height=50, max_size_bytes=1024)
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        is_valid, error = handler.validate_image(image_data)
        # Should fail due to dimensions exceeding limits
        assert is_valid is False or error is not None


class TestMetadataExtraction:
    """Test metadata extraction"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_png_metadata(self, image_handler, sample_png):
        """Test PNG metadata extraction"""
        metadata = image_handler.extract_metadata(sample_png)
        assert metadata is not None
        assert metadata.format == ImageFormat.PNG
        assert metadata.width == 100
        assert metadata.height == 100
        assert metadata.mime_type == "image/png"
        assert metadata.size_bytes == len(sample_png)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_jpeg_metadata(self, image_handler, sample_jpeg):
        """Test JPEG metadata extraction"""
        metadata = image_handler.extract_metadata(sample_jpeg)
        assert metadata is not None
        assert metadata.format == ImageFormat.JPEG
        assert metadata.width == 100
        assert metadata.height == 100
        assert metadata.mime_type == "image/jpeg"
        assert metadata.size_bytes == len(sample_jpeg)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_gif_metadata(self, image_handler, sample_gif):
        """Test GIF metadata extraction"""
        metadata = image_handler.extract_metadata(sample_gif)
        assert metadata is not None
        assert metadata.format == ImageFormat.GIF
        assert metadata.width == 100
        assert metadata.height == 100
        assert metadata.mime_type == "image/gif"
        assert metadata.size_bytes == len(sample_gif)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_empty_data(self, image_handler):
        """Test metadata extraction with empty data"""
        metadata = image_handler.extract_metadata(b"")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_invalid_data(self, image_handler):
        """Test metadata extraction with invalid data"""
        metadata = image_handler.extract_metadata(b"not an image")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_metadata_to_dict(self, image_handler, sample_png):
        """Test metadata to_dict conversion"""
        metadata = image_handler.extract_metadata(sample_png)
        assert metadata is not None
        metadata_dict = metadata.to_dict()
        assert isinstance(metadata_dict, dict)
        assert "format" in metadata_dict
        assert "width" in metadata_dict
        assert "height" in metadata_dict
        assert "mime_type" in metadata_dict


class TestImageInfo:
    """Test comprehensive image info"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_image_info_png(self, image_handler, sample_png):
        """Test get_image_info for PNG"""
        info = image_handler.get_image_info(sample_png)
        assert info is not None
        assert info["format"] == "png"
        assert info["is_valid"] is True
        assert info["metadata"] is not None
        assert info["size_bytes"] == len(sample_png)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_image_info_jpeg(self, image_handler, sample_jpeg):
        """Test get_image_info for JPEG"""
        info = image_handler.get_image_info(sample_jpeg)
        assert info is not None
        assert info["format"] == "jpeg"
        assert info["is_valid"] is True
        assert info["metadata"] is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_image_info_invalid(self, image_handler):
        """Test get_image_info with invalid data"""
        info = image_handler.get_image_info(b"not an image")
        assert info is not None
        assert info["is_valid"] is False
        assert info["error"] is not None
        assert info["metadata"] is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

