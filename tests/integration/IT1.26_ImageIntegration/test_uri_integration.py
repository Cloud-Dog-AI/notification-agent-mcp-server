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
Integration Tests for URI Integration

Tests:
- URI handler integration with storage
- Message system integration
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
import os
from PIL import Image

from src.core.media.media_fetcher import URIHandler
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


@pytest.fixture
def uri_handler(image_handler):
    """Create URIHandler instance"""
    return URIHandler(image_handler=image_handler)


@pytest.fixture
def temp_image_file():
    """Create temporary image file"""
    img = Image.new('RGB', (100, 100), color='red')
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file, format='PNG')
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)


class TestURIIntegration:
    """Test URI integration"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_fetch_and_store_from_file(self, uri_handler, storage_manager, temp_image_file):
        """Test fetching from file and storing"""
        # Fetch image from file
        result = uri_handler.fetch_from_file(temp_image_file)
        assert result is not None
        image_data, format = result
        
        # Store fetched image
        metadata = uri_handler.image_handler.extract_metadata(image_data)
        storage_result = storage_manager.store_file(
            file_content=image_data,
            file_type="image",
            message_id=1,
            metadata={"mime_type": metadata.mime_type}
        )
        
        assert storage_result is not None
        assert storage_result["storage_path"] is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")
    
    def test_uri_in_message_content(self, uri_handler, temp_image_file):
        """Test URI in message content"""
    


        # Simulate message with URI reference
        message_content = {
            "type": "text",
            "body": "Check out this image:",
            "images": [{"type": "uri", "uri": temp_image_file}]
        }
        
        # Fetch image from URI
        if message_content.get("images"):
            for img_ref in message_content["images"]:
                if img_ref.get("type") == "uri":
                    result = uri_handler.fetch_image(img_ref["uri"])
                    assert result is not None
                    image_data, format = result
                    
                    # Validate
                    is_valid, _ = uri_handler.image_handler.validate_image(image_data)
                    assert is_valid is True

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.pure, pytest.mark.heavy]
