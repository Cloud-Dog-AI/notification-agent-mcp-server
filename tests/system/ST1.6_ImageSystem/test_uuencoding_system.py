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
System Tests for UUEncoding System

Tests:
- UUEncoding system operations
- File operations
- Multiple images
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
from PIL import Image

from src.core.media.uuencoding import UUEncoding


class TestUUEncodingSystem:
    """Test UUEncoding system operations"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_encode_multiple_images(self):
        """Test encoding multiple images"""
        formats = ['PNG', 'JPEG', 'GIF']
        encoded_images = []
        
        for fmt in formats:
            img = Image.new('RGB', (50, 50), color='red')
            buffer = io.BytesIO()
            img.save(buffer, format=fmt)
            image_data = buffer.getvalue()
            
            encoded = UUEncoding.encode(image_data, fmt.lower())
            encoded_images.append(encoded)
            
            assert UUEncoding.is_uuencoded(encoded) is True
        
        assert len(encoded_images) == 3
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_decode_multiple_images(self):
        """Test decoding multiple images"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_decode_multiple_images"
        )

        formats = ['PNG', 'JPEG', 'GIF']
        
        for fmt in formats:
            img = Image.new('RGB', (50, 50), color='blue')
            buffer = io.BytesIO()
            img.save(buffer, format=fmt)
            original_data = buffer.getvalue()
            
            encoded = UUEncoding.encode(original_data, fmt.lower())
            result = UUEncoding.decode(encoded)
            
            assert result is not None
            decoded_data, format = result
            assert decoded_data == original_data
            assert format == fmt.lower()
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_uuencoding_with_storage_simulation(self):
        """Test UUEncoding with storage simulation"""
        # Create image
        img = Image.new('RGB', (100, 100), color='green')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        # Encode
        encoded = UUEncoding.encode(image_data, "png")
        
        # Simulate storage (as string)
        stored = encoded
        
        # Retrieve and decode
        result = UUEncoding.decode(stored)
        assert result is not None
        decoded_data, format = result
        assert decoded_data == image_data

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

