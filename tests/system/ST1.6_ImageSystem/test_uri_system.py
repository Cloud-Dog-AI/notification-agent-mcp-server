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
System Tests for URI System

Tests:
- URI reference system
- Network operations
- File operations
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

from src.core.media.media_fetcher import URIHandler
from src.core.media.image_handler import ImageHandler


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


@pytest.fixture
def uri_handler(image_handler):
    """Create URIHandler instance"""
    return URIHandler(image_handler=image_handler)


@pytest.fixture
def temp_image_files():
    """Create multiple temporary image files"""
    files = []
    formats = ['PNG', 'JPEG', 'GIF']
    for fmt in formats:
        img = Image.new('RGB', (50, 50), color='red')
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{fmt.lower()}')
        img.save(temp_file, format=fmt)
        temp_file.close()
        files.append(temp_file.name)
    yield files
    for f in files:
        os.unlink(f)


class TestURISystemOperations:
    """Test URI system operations"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_fetch_multiple_files(self, uri_handler, temp_image_files):
        """Test fetching multiple files"""
        results = []
        for file_path in temp_image_files:
            result = uri_handler.fetch_from_file(file_path)
            results.append(result)
        
        assert len(results) == 3
        assert all(r is not None for r in results)
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_validate_multiple_files(self, uri_handler, temp_image_files):
        """Test validating multiple files"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_validate_multiple_files"
        )

        for file_path in temp_image_files:
            is_valid, error = uri_handler.validate_uri(file_path)
            assert is_valid is True
            assert error is None
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_uri_system_with_different_paths(self, uri_handler):
        """Test URI system with different path formats"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_uri_system_with_different_paths"
        )
        # Create temp file
        img = Image.new('RGB', (50, 50), color='blue')
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        img.save(temp_file, format='PNG')
        temp_file.close()
        
        try:
            # Test with absolute path
            abs_path = os.path.abspath(temp_file.name)
            result = uri_handler.fetch_from_file(abs_path)
            assert result is not None
            
            # Test with relative path (if possible)
            rel_path = os.path.relpath(temp_file.name)
            if os.path.exists(rel_path):
                result = uri_handler.fetch_from_file(rel_path)
                assert result is not None
        finally:
            os.unlink(temp_file.name)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]
