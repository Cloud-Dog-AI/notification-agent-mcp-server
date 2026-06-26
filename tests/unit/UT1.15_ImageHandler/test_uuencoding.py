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
Unit Tests for UUEncoding

Tests:
- UUEncoding encoding/decoding
- Storage operations
- Data URI format
"""
import pytest
import io
import base64
from PIL import Image

from src.core.media.uuencoding import UUEncoding


@pytest.fixture
def sample_image():
    """Create sample image"""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestUUEncoding:
    """Test UUEncoding encoding/decoding"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_encode_png(self, sample_image):
        """Test encoding PNG image"""
        encoded = UUEncoding.encode(sample_image, "png")
        assert encoded.startswith("data:image/png;base64,")
        assert len(encoded) > len("data:image/png;base64,")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_encode_jpeg(self):
        """Test encoding JPEG image"""
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        encoded = UUEncoding.encode(image_data, "jpeg")
        assert encoded.startswith("data:image/jpeg;base64,")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_encode_gif(self):
        """Test encoding GIF image"""
        img = Image.new('RGB', (50, 50), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='GIF')
        image_data = buffer.getvalue()
        
        encoded = UUEncoding.encode(image_data, "gif")
        assert encoded.startswith("data:image/gif;base64,")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_encode_empty_data(self):
        """Test encoding empty data"""
        with pytest.raises(ValueError):
            UUEncoding.encode(b"", "png")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_decode_png(self, sample_image):
        """Test decoding PNG image"""
        encoded = UUEncoding.encode(sample_image, "png")
        result = UUEncoding.decode(encoded)
        
        assert result is not None
        decoded_data, format = result
        assert decoded_data == sample_image
        assert format == "png"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_decode_jpeg(self):
        """Test decoding JPEG image"""
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        image_data = buffer.getvalue()
        
        encoded = UUEncoding.encode(image_data, "jpeg")
        result = UUEncoding.decode(encoded)
        
        assert result is not None
        decoded_data, format = result
        assert decoded_data == image_data
        assert format == "jpeg"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_decode_invalid_format(self):
        """Test decoding invalid data URI"""
        result = UUEncoding.decode("not a data uri")
        assert result is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_decode_malformed_uri(self):
        """Test decoding malformed data URI"""
        result = UUEncoding.decode("data:image/png;base64")
        assert result is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_is_uuencoded(self, sample_image):
        """Test is_uuencoded check"""
        encoded = UUEncoding.encode(sample_image, "png")
        assert UUEncoding.is_uuencoded(encoded) is True
        assert UUEncoding.is_uuencoded("not encoded") is False
        assert UUEncoding.is_uuencoded("data:text/plain;base64,test") is False  # Not image
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_format_from_uri(self, sample_image):
        """Test format extraction from URI"""
        encoded = UUEncoding.encode(sample_image, "png")
        format = UUEncoding.extract_format_from_uri(encoded)
        assert format == "png"
        
        # Test with JPEG
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        encoded_jpeg = UUEncoding.encode(buffer.getvalue(), "jpeg")
        format = UUEncoding.extract_format_from_uri(encoded_jpeg)
        assert format == "jpeg"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_round_trip_encoding(self, sample_image):
        """Test round-trip encoding/decoding"""
        encoded = UUEncoding.encode(sample_image, "png")
        result = UUEncoding.decode(encoded)
        
        assert result is not None
        decoded_data, format = result
        assert decoded_data == sample_image
        assert format == "png"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

