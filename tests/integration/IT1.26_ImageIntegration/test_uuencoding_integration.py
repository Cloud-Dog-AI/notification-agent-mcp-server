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
Integration Tests for UUEncoding Integration

Tests:
- UUEncoding integration with message content
- Storage integration
"""
import pytest
import sys

# Add project root to path
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
import tempfile
from PIL import Image

from src.core.media.uuencoding import UUEncoding
from src.core.media.image_handler import ImageHandler
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def storage_manager(temp_storage_dir, storage_base_url):
    """Create storage manager"""
    backend = LocalStorage(base_path=temp_storage_dir)
    return StorageManager(backend=backend, base_url=storage_base_url)


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


class TestUUEncodingIntegration:
    """Test UUEncoding integration"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_uuencode_and_store(self, image_handler, storage_manager):
        """Test UUEncoding and storing image"""
        # Create image
        img = Image.new('RGB', (100, 100), color='red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        # Validate image
        is_valid, _ = image_handler.validate_image(image_data)
        assert is_valid is True
        
        # UUEncode
        encoded = UUEncoding.encode(image_data, "png")
        assert UUEncoding.is_uuencoded(encoded) is True
        
        # Decode and store
        result = UUEncoding.decode(encoded)
        assert result is not None
        decoded_data, format = result
        
        # Store decoded image
        metadata = image_handler.extract_metadata(decoded_data)
        storage_result = storage_manager.store_file(
            file_content=decoded_data,
            file_type="image",
            message_id=1,
            metadata={"mime_type": metadata.mime_type}
        )
        
        assert storage_result is not None
        assert storage_result["storage_path"] is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_uuencoded_image_in_message_content(self, image_handler):
        """Test UUEncoded image in message content"""
    


        # Create image
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        image_data = buffer.getvalue()
        
        # UUEncode
        encoded = UUEncoding.encode(image_data, "png")
        
        # Simulate message content with UUEncoded image
        message_content = {
            "type": "text",
            "body": "Here is an image:",
            "images": [{"type": "uuencoded", "data": encoded}]
        }
        
        # Extract and decode image
        if message_content.get("images"):
            for img_data in message_content["images"]:
                if img_data.get("type") == "uuencoded":
                    result = UUEncoding.decode(img_data["data"])
                    assert result is not None
                    decoded_data, format = result
                    
                    # Validate decoded image
                    is_valid, _ = image_handler.validate_image(decoded_data)
                    assert is_valid is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_multiple_uuencoded_images(self, image_handler, storage_manager):
        """Test multiple UUEncoded images"""
        images = []
        for i, color in enumerate(['red', 'blue', 'green']):
            img = Image.new('RGB', (50 + i * 10, 50 + i * 10), color=color)
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            
            # UUEncode
            encoded = UUEncoding.encode(image_data, "png")
            images.append(encoded)
        
        # Decode and store all
        for i, encoded in enumerate(images):
            result = UUEncoding.decode(encoded)
            assert result is not None
            decoded_data, format = result
            
            metadata = image_handler.extract_metadata(decoded_data)
            storage_result = storage_manager.store_file(
                file_content=decoded_data,
                file_type="image",
                message_id=1,
                delivery_id=i + 1,
                metadata={"mime_type": metadata.mime_type}
            )
            assert storage_result is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]

