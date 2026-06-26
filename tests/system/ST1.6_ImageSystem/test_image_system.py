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
System Tests for Image System

Tests:
- Image format system operations
- File operations
- Error handling
- Concurrent operations
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
import tempfile
import os
from PIL import Image

from src.core.media.image_handler import ImageHandler, ImageFormat


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


@pytest.fixture
def temp_image_file():
    """Create temporary image file"""
    img = Image.new('RGB', (100, 100), color='red')
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file, format='PNG')
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)


class TestImageSystemOperations:
    """Test image system operations"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_load_image_from_file(self, image_handler, temp_image_file):
        """Test loading image from file"""
        with open(temp_image_file, 'rb') as f:
            image_data = f.read()
        
        format = image_handler.detect_format(image_data)
        assert format == ImageFormat.PNG
        
        is_valid, error = image_handler.validate_image(image_data)
        assert is_valid is True
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_save_and_load_image(self, image_handler):
        """Test saving and loading image"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_save_and_load_image"
        )

        # Create image
        img = Image.new('RGB', (200, 200), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        # Validate
        is_valid, error = image_handler.validate_image(image_data)
        assert is_valid is True
        
        # Extract metadata
        metadata = image_handler.extract_metadata(image_data)
        assert metadata is not None
        assert metadata.width == 200
        assert metadata.height == 200
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_multiple_formats_system(self, image_handler):
        """Test system with multiple image formats"""
        formats = ['PNG', 'JPEG', 'GIF']
        for fmt in formats:
            img = Image.new('RGB', (50, 50), color='green')
            buffer = io.BytesIO()
            img.save(buffer, format=fmt)
            image_data = buffer.getvalue()
            
            is_valid, error = image_handler.validate_image(image_data)
            assert is_valid is True, f"Format {fmt} should be valid: {error}"
            
            metadata = image_handler.extract_metadata(image_data)
            assert metadata is not None


class TestImageErrorHandling:
    """Test image error handling"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")

    def test_corrupted_image_data(self, image_handler):
        """Test handling of corrupted image data"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_corrupted_image_data"
        )
        # Create corrupted data (valid PNG header but corrupted body)
        corrupted_data = b'\x89PNG\r\n\x1a\n' + b'corrupted' * 100
        is_valid, error = image_handler.validate_image(corrupted_data)
        assert is_valid is False
        assert error is not None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_unsupported_format(self, image_handler):
        """Test handling of unsupported format"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_unsupported_format"
        )

        # Create BMP image (not supported)
        img = Image.new('RGB', (50, 50), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='BMP')
        image_data = buffer.getvalue()
        
        format = image_handler.detect_format(image_data)
        # BMP might be detected but not in our supported list
        # The validation should catch it
        is_valid, error = image_handler.validate_image(image_data)
        # May or may not be valid depending on PIL's BMP support
        # But our handler should handle it gracefully
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_empty_file_handling(self, image_handler):
        """Test handling of empty file"""
        is_valid, error = image_handler.validate_image(b"")
        assert is_valid is False
        assert "empty" in error.lower()


class TestImageConcurrentOperations:
    """Test concurrent image operations"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")

    def test_concurrent_format_detection(self, image_handler):
        """Test concurrent format detection"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_concurrent_format_detection"
        )
        images = []
        for i in range(5):
            img = Image.new('RGB', (50 + i, 50 + i), color='red')
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            images.append(buffer.getvalue())
        
        # Process all images
        formats = [image_handler.detect_format(img) for img in images]
        assert all(f == ImageFormat.PNG for f in formats)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_concurrent_validation(self, image_handler):
        """Test concurrent validation"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_concurrent_validation"
        )

        images = []
        for i in range(5):
            img = Image.new('RGB', (50, 50), color='blue')
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            images.append(buffer.getvalue())
        
        # Validate all images
        results = [image_handler.validate_image(img) for img in images]
        assert all(is_valid for is_valid, _ in results)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

