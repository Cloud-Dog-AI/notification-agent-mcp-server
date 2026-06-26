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

"""System Tests for Image Cache System"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
import tempfile
from PIL import Image
from src.core.media.image_cache import ImageCacheManager
from src.core.storage.storage_manager import StorageManager
from src.core.storage.local_storage import LocalStorage

@pytest.fixture
def temp_storage_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def cache_manager(temp_storage_dir, storage_base_url):
    storage = StorageManager(backend=LocalStorage(base_path=temp_storage_dir), base_url=storage_base_url)
    return ImageCacheManager(storage_manager=storage)

class TestCacheSystem:
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    def test_cache_multiple_images(self, cache_manager):
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_cache_multiple_images"
        )

        import tempfile as tf
        import os
        files = []
        for i in range(3):
            img = Image.new('RGB', (50, 50), color='red')
            temp_file = tf.NamedTemporaryFile(delete=False, suffix='.png')
            img.save(temp_file, format='PNG')
            temp_file.close()
            files.append(temp_file.name)
        
        try:
            for file_path in files:
                result = cache_manager.cache_image(file_path)
                assert result is not None
        finally:
            for f in files:
                os.unlink(f)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

