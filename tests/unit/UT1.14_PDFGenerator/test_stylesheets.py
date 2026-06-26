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
Unit Tests for Stylesheet Manager

Tests:
- Stylesheet manager initialization
- Stylesheet loading and saving
- CSS validation
- Channel-specific stylesheets
"""

import pytest
import tempfile
import os
from pathlib import Path

from src.core.formatters.stylesheets import StylesheetManager


@pytest.fixture
def temp_stylesheets_dir():
    """Create temporary stylesheets directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    for file in Path(temp_dir).glob("*.css"):
        try:
            os.remove(file)
        except:
            pass
    try:
        os.rmdir(temp_dir)
    except:
        pass


@pytest.fixture
def stylesheet_manager(temp_stylesheets_dir):
    """Create StylesheetManager instance"""
    return StylesheetManager(stylesheets_dir=temp_stylesheets_dir)


class TestStylesheetManager:
    """Test stylesheet manager functionality"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_initialization(self, temp_stylesheets_dir):
        """Test stylesheet manager initialization"""
        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        assert manager is not None
        assert manager.stylesheets_dir == Path(temp_stylesheets_dir)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_save_and_load_stylesheet(self, stylesheet_manager):
        """Test saving and loading a stylesheet"""
        css_content = "body { font-family: Arial; }"
        
        # Save
        result = stylesheet_manager.save_stylesheet("test.css", css_content)
        assert result is True
        
        # Load
        loaded = stylesheet_manager.load_stylesheet("test.css")
        assert loaded == css_content
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_load_nonexistent_stylesheet(self, stylesheet_manager):
        """Test loading a non-existent stylesheet"""
        loaded = stylesheet_manager.load_stylesheet("nonexistent.css")
        assert loaded is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_stylesheet_path(self, stylesheet_manager):
        """Test getting stylesheet path"""
        css_content = "body { color: black; }"
        stylesheet_manager.save_stylesheet("test.css", css_content)
        
        path = stylesheet_manager.get_stylesheet_path("test.css")
        assert path is not None
        assert path.exists()
        assert path.name == "test.css"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_nonexistent_stylesheet_path(self, stylesheet_manager):
        """Test getting path for non-existent stylesheet"""
        path = stylesheet_manager.get_stylesheet_path("nonexistent.css")
        assert path is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_css_validation_valid(self, stylesheet_manager):
        """Test CSS validation with valid CSS"""
        valid_css = """
        body {
            font-family: Arial;
            color: #000000;
        }
        h1 {
            font-size: 18pt;
        }
        """
        result = stylesheet_manager.save_stylesheet("valid.css", valid_css)
        assert result is True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_css_validation_invalid_braces(self, stylesheet_manager):
        """Test CSS validation with unbalanced braces"""
        invalid_css = "body { font-family: Arial; "  # Missing closing brace
        # Should still save but log warning
        result = stylesheet_manager.save_stylesheet("invalid.css", invalid_css)
        # Manager still saves but validates
        assert result is True  # Manager saves even if validation fails
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_list_stylesheets(self, stylesheet_manager):
        """Test listing all stylesheets"""
        stylesheet_manager.save_stylesheet("style1.css", "body { }")
        stylesheet_manager.save_stylesheet("style2.css", "h1 { }")
        stylesheet_manager.save_stylesheet("style3.css", "p { }")
        
        stylesheets = stylesheet_manager.list_stylesheets()
        assert len(stylesheets) == 3
        assert "style1.css" in stylesheets
        assert "style2.css" in stylesheets
        assert "style3.css" in stylesheets
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delete_stylesheet(self, stylesheet_manager):
        """Test deleting a stylesheet"""
        css_content = "body { }"
        stylesheet_manager.save_stylesheet("delete_test.css", css_content)
        
        # Verify exists
        assert stylesheet_manager.get_stylesheet_path("delete_test.css") is not None
        
        # Delete
        result = stylesheet_manager.delete_stylesheet("delete_test.css")
        assert result is True
        
        # Verify deleted
        assert stylesheet_manager.get_stylesheet_path("delete_test.css") is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delete_nonexistent_stylesheet(self, stylesheet_manager):
        """Test deleting a non-existent stylesheet"""
        result = stylesheet_manager.delete_stylesheet("nonexistent.css")
        assert result is False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channel_stylesheet(self, stylesheet_manager):
        """Test channel-specific stylesheet"""
        channel_id = 1
        css_content = "body { background: blue; }"
        
        # Set channel stylesheet
        result = stylesheet_manager.set_channel_stylesheet(channel_id, css_content)
        assert result is True
        
        # Get channel stylesheet
        loaded = stylesheet_manager.get_channel_stylesheet(channel_id)
        assert loaded == css_content
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channel_stylesheet_fallback_to_default(self, stylesheet_manager):
        """Test channel stylesheet falls back to default"""
        # Create default
        default_css = "body { color: black; }"
        stylesheet_manager.save_stylesheet("default.css", default_css)
        
        # Get channel stylesheet (should fall back to default)
        loaded = stylesheet_manager.get_channel_stylesheet(999)
        assert loaded == default_css
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_default_stylesheet_loading(self, stylesheet_manager):
        """Test loading default stylesheet"""
        default_css = "body { font-family: Arial; }"
        stylesheet_manager.save_stylesheet("default.css", default_css)
        
        loaded = stylesheet_manager.load_stylesheet()  # None = default
        assert loaded == default_css
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_multiple_channel_stylesheets(self, stylesheet_manager):
        """Test multiple channel-specific stylesheets"""
        channel1_css = "body { color: red; }"
        channel2_css = "body { color: blue; }"
        
        stylesheet_manager.set_channel_stylesheet(1, channel1_css)
        stylesheet_manager.set_channel_stylesheet(2, channel2_css)
        
        assert stylesheet_manager.get_channel_stylesheet(1) == channel1_css
        assert stylesheet_manager.get_channel_stylesheet(2) == channel2_css

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

