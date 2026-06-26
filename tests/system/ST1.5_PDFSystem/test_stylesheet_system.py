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
System Tests for Stylesheet System

Tests:
- Stylesheet file system operations
- Default stylesheet loading
- Stylesheet directory management
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import tempfile
import os

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


class TestStylesheetSystem:
    """Test stylesheet system"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_stylesheet_directory_creation(self, temp_stylesheets_dir):
        """Test that stylesheet directory is created"""
        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        assert Path(temp_stylesheets_dir).exists()
        assert Path(temp_stylesheets_dir).is_dir()
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_default_stylesheet_file_operations(self, temp_stylesheets_dir):
        """Test default stylesheet file operations"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_default_stylesheet_file_operations"
        )

        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        default_css = "body { font-family: Arial; }"
        
        # Save default
        manager.save_stylesheet("default.css", default_css)
        
        # Verify file exists
        default_path = Path(temp_stylesheets_dir) / "default.css"
        assert default_path.exists()
        assert default_path.is_file()
        
        # Verify content
        with open(default_path, 'r') as f:
            content = f.read()
        assert content == default_css
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_multiple_stylesheet_files(self, temp_stylesheets_dir):
        """Test managing multiple stylesheet files"""
        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        stylesheets = {
            "default.css": "body { }",
            "custom.css": "h1 { }",
            "channel_1.css": "p { }"
        }
        
        for name, content in stylesheets.items():
            manager.save_stylesheet(name, content)
        
        # Verify all files exist
        for name in stylesheets.keys():
            path = Path(temp_stylesheets_dir) / name
            assert path.exists()
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_stylesheet_file_overwrite(self, temp_stylesheets_dir):
        """Test overwriting existing stylesheet"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_stylesheet_file_overwrite"
        )

        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        # Save initial
        manager.save_stylesheet("test.css", "body { color: red; }")
        
        # Overwrite
        manager.save_stylesheet("test.css", "body { color: blue; }")
        
        # Verify new content
        loaded = manager.load_stylesheet("test.css")
        assert "blue" in loaded
        assert "red" not in loaded
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_stylesheet_listing_system(self, temp_stylesheets_dir):
        """Test stylesheet listing system"""
        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        # Create multiple stylesheets
        for i in range(5):
            manager.save_stylesheet(f"style_{i}.css", f"body {{ }}")
        
        # List all
        stylesheets = manager.list_stylesheets()
        assert len(stylesheets) == 5
        for i in range(5):
            assert f"style_{i}.css" in stylesheets
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_channel_stylesheet_file_naming(self, temp_stylesheets_dir):
        """Test channel stylesheet file naming convention"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_channel_stylesheet_file_naming"
        )

        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        manager.set_channel_stylesheet(123, "body { }")
        
        # Verify file naming
        channel_path = Path(temp_stylesheets_dir) / "channel_123.css"
        assert channel_path.exists()
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_stylesheet_deletion_system(self, temp_stylesheets_dir):
        """Test stylesheet deletion system"""
        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        # Create and verify
        manager.save_stylesheet("delete_me.css", "body { }")
        path = Path(temp_stylesheets_dir) / "delete_me.css"
        assert path.exists()
        
        # Delete
        manager.delete_stylesheet("delete_me.css")
        assert not path.exists()
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_stylesheet_encoding(self, temp_stylesheets_dir):
        """Test stylesheet file encoding (UTF-8)"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_stylesheet_encoding"
        )

        manager = StylesheetManager(stylesheets_dir=temp_stylesheets_dir)
        
        # CSS with special characters
        css_with_unicode = "body { content: '你好'; }"
        manager.save_stylesheet("unicode.css", css_with_unicode)
        
        # Load and verify
        loaded = manager.load_stylesheet("unicode.css")
        assert loaded == css_with_unicode

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

