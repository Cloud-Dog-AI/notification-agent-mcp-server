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
Integration Tests for Image Integration

Tests:
- Image handler integration with storage manager
- Image storage and retrieval
- Database integration
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

from src.core.media.image_handler import ImageHandler, ImageFormat
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


@pytest.fixture
def sample_image():
    """Create sample image"""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


class TestImageStorageIntegration:
    """Test image storage integration"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_store_and_retrieve_image(self, image_handler, storage_manager, sample_image):
        """Test storing and retrieving image"""
        # Validate image first
        is_valid, error = image_handler.validate_image(sample_image)
        assert is_valid is True
        
        # Extract metadata
        metadata = image_handler.extract_metadata(sample_image)
        assert metadata is not None
        
        # Store image
        storage_result = storage_manager.store_file(
            file_content=sample_image,
            file_type="image",
            message_id=1,
            metadata={"mime_type": metadata.mime_type}
        )
        
        assert storage_result is not None
        assert storage_result["storage_path"] is not None
        
        # Retrieve image
        retrieved_data = storage_manager.retrieve_file(storage_result["storage_path"])
        assert retrieved_data is not None
        assert len(retrieved_data) == len(sample_image)
        
        # Validate retrieved image
        is_valid_retrieved, _ = image_handler.validate_image(retrieved_data)
        assert is_valid_retrieved is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_store_multiple_images(self, image_handler, storage_manager):
        """Test storing multiple images"""
    


        images = []
        for i, color in enumerate(['red', 'blue', 'green']):
            img = Image.new('RGB', (50 + i * 10, 50 + i * 10), color=color)
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            images.append(buffer.getvalue())
        
        storage_paths = []
        for i, image_data in enumerate(images):
            metadata = image_handler.extract_metadata(image_data)
            storage_result = storage_manager.store_file(
                file_content=image_data,
                file_type="image",
                message_id=1,
                delivery_id=i + 1,
                metadata={"mime_type": metadata.mime_type}
            )
            storage_paths.append(storage_result["storage_path"])
        
        assert len(storage_paths) == 3
        
        # Verify all can be retrieved
        for path in storage_paths:
            retrieved = storage_manager.retrieve_file(path)
            assert retrieved is not None
            is_valid, _ = image_handler.validate_image(retrieved)
            assert is_valid is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_image_metadata_in_storage(self, image_handler, storage_manager, sample_image):
        """Test image metadata stored with image"""
        metadata = image_handler.extract_metadata(sample_image)
        
        storage_result = storage_manager.store_file(
            file_content=sample_image,
            file_type="image",
            message_id=1,
            metadata={
                "mime_type": metadata.mime_type,
                "width": metadata.width,
                "height": metadata.height,
                "format": metadata.format.value
            }
        )
        
        # Get file info
        file_info = storage_manager.get_file_info(storage_result["storage_path"])
        assert file_info is not None
        # Verify storage was successful (mime_type is in storage_result)
        assert storage_result.get("mime_type") == metadata.mime_type

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.heavy]

