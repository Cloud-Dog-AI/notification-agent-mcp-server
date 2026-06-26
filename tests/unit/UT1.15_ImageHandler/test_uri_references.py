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
Unit Tests for URI References

Tests:
- URI parsing
- HTTP fetching
- Local file access
- Error handling
"""
import pytest
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
def temp_image_file():
    """Create temporary image file"""
    img = Image.new('RGB', (100, 100), color='red')
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    img.save(temp_file, format='PNG')
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)


class TestURIParsing:
    """Test URI parsing"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_http_url(self, uri_handler, test_config):
        """Test parsing HTTP URL"""
        http_url = test_config.get("test.media.http_image_url")
        if not http_url:
            pytest.fail("test.media.http_image_url not configured. Check your env file.")
        parsed = uri_handler.parse_uri(http_url)
        assert parsed["type"] == "http"
        assert parsed["is_local"] is False
        assert "url" in parsed
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_https_url(self, uri_handler, test_config):
        """Test parsing HTTPS URL"""
        https_url = test_config.get("test.media.https_image_url")
        if not https_url:
            pytest.fail("test.media.https_image_url not configured. Check your env file.")
        parsed = uri_handler.parse_uri(https_url)
        assert parsed["type"] == "https"
        assert parsed["is_local"] is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_file_path(self, uri_handler, temp_image_file):
        """Test parsing file path"""
        parsed = uri_handler.parse_uri(temp_image_file)
        assert parsed["type"] == "file"
        assert parsed["is_local"] is True
        assert "path" in parsed
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_relative_path(self, uri_handler):
        """Test parsing relative path"""
        parsed = uri_handler.parse_uri("./test.png")
        # May or may not be detected as file depending on existence
        assert parsed["type"] in ["file", None]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_parse_empty_uri(self, uri_handler):
        """Test parsing empty URI"""
        parsed = uri_handler.parse_uri("")
        assert parsed["type"] is None


class TestLocalFileAccess:
    """Test local file access"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetch_from_file(self, uri_handler, temp_image_file):
        """Test fetching from local file"""
        result = uri_handler.fetch_from_file(temp_image_file)
        assert result is not None
        image_data, format = result
        assert len(image_data) > 0
        assert format in ["png", "jpeg", "gif"]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetch_from_nonexistent_file(self, uri_handler):
        """Test fetching from nonexistent file"""
        result = uri_handler.fetch_from_file("/nonexistent/file.png")
        assert result is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetch_from_directory(self, uri_handler):
        """Test fetching from directory (should fail)"""
        import tempfile as tf
        import shutil
        temp_dir = tf.mkdtemp()
        try:
            result = uri_handler.fetch_from_file(temp_dir)
            assert result is None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestURIValidation:
    """Test URI validation"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_file_uri(self, uri_handler, temp_image_file):
        """Test validating file URI"""
        is_valid, error = uri_handler.validate_uri(temp_image_file)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_nonexistent_file(self, uri_handler):
        """Test validating nonexistent file"""
        is_valid, error = uri_handler.validate_uri("/nonexistent/file.png")
        assert is_valid is False
        assert error is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_empty_uri(self, uri_handler):
        """Test validating empty URI"""
        is_valid, error = uri_handler.validate_uri("")
        assert is_valid is False
        assert "empty" in error.lower()


class TestErrorHandling:
    """Test error handling"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetch_invalid_uri(self, uri_handler):
        """Test fetching invalid URI"""
        result = uri_handler.fetch_image("not a valid uri")
        assert result is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_fetch_empty_uri(self, uri_handler):
        """Test fetching empty URI"""
        result = uri_handler.fetch_image("")
        assert result is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]
