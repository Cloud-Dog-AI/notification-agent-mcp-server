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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: Stylesheet Manager for Notification Agent MCP Server - Manages CSS stylesheets for PDF generation

Related Requirements: FR1.18
Related Tasks: T29
Related Architecture: CC5.2.2
Related Tests: UT1.14, ST1.5, IT1.17, AT1.19

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import os
from pathlib import Path
from typing import Optional
import re

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

from src.config import get_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

_fs = _PlatformLocalStorage(root_path="/")


class StylesheetManager:
    """Manages CSS stylesheets for PDF generation"""
    
    def __init__(self, stylesheets_dir: Optional[str] = None):
        """
        Initialize stylesheet manager
        
        Args:
            stylesheets_dir: Directory containing stylesheet files (default: stylesheets/)
        """
        config = get_config()
        # Default to src/stylesheets (code location)
        default_dir = Path(__file__).parent.parent.parent / "stylesheets"
        self.stylesheets_dir = Path(stylesheets_dir or config.get("stylesheets.directory", str(default_dir)))
        _fs.create_dir(str(self.stylesheets_dir), parents=True, exist_ok=True)
        self.default_stylesheet = config.get("stylesheets.default", "default.css")
        logger.info(f"StylesheetManager initialized with directory: {self.stylesheets_dir}")
    
    def get_stylesheet_path(self, stylesheet_name: Optional[str] = None) -> Optional[Path]:
        """
        Get path to a stylesheet file
        
        Args:
            stylesheet_name: Name of stylesheet file (None for default)
            
        Returns:
            Path to stylesheet file, or None if not found
        """
        if stylesheet_name is None:
            stylesheet_name = self.default_stylesheet
        
        stylesheet_path = self.stylesheets_dir / stylesheet_name

        _stat = _fs.stat(str(stylesheet_path))
        if _stat is not None and not _stat.is_dir:
            return stylesheet_path
        
        logger.warning(f"Stylesheet not found: {stylesheet_name}")
        return None
    
    def load_stylesheet(self, stylesheet_name: Optional[str] = None) -> Optional[str]:
        """
        Load stylesheet content
        
        Args:
            stylesheet_name: Name of stylesheet file (None for default)
            
        Returns:
            Stylesheet content as string, or None if not found
        """
        stylesheet_path = self.get_stylesheet_path(stylesheet_name)
        
        if stylesheet_path is None:
            return None
        
        try:
            content = _fs.read_bytes(str(stylesheet_path)).decode("utf-8")
            logger.debug(f"Loaded stylesheet: {stylesheet_name or 'default'}")
            return content
        except Exception as e:
            logger.error(f"Error loading stylesheet {stylesheet_name}: {e}")
            return None
    
    def save_stylesheet(self, stylesheet_name: str, content: str) -> bool:
        """
        Save stylesheet content
        
        Args:
            stylesheet_name: Name of stylesheet file
            content: CSS content
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self._validate_css(content):
            logger.warning(f"CSS validation failed for {stylesheet_name}")
            # Still save, but log warning
        
        stylesheet_path = self.stylesheets_dir / stylesheet_name
        
        try:
            _fs.write_bytes(str(stylesheet_path), content.encode("utf-8"))
            logger.info(f"Saved stylesheet: {stylesheet_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving stylesheet {stylesheet_name}: {e}")
            return False
    
    def _validate_css(self, css_content: str) -> bool:
        """
        Basic CSS validation
        
        Args:
            css_content: CSS content to validate
            
        Returns:
            True if CSS appears valid, False otherwise
        """
        # Basic validation: check for balanced braces
        open_braces = css_content.count('{')
        close_braces = css_content.count('}')
        
        if open_braces != close_braces:
            return False
        
        # Check for basic CSS structure (selectors and properties)
        if not re.search(r'[a-zA-Z][^{]*\{[^}]*\}', css_content):
            # No valid CSS rules found
            return False
        
        return True
    
    def list_stylesheets(self) -> list:
        """
        List all available stylesheets
        
        Returns:
            List of stylesheet filenames
        """
        stylesheets = []
        
        if not _fs.exists(str(self.stylesheets_dir)):
            return stylesheets

        for entry in _fs.list_dir(str(self.stylesheets_dir)):
            if not entry.is_dir and entry.path.endswith(".css"):
                stylesheets.append(os.path.basename(entry.path))
        
        return sorted(stylesheets)
    
    def delete_stylesheet(self, stylesheet_name: str) -> bool:
        """
        Delete a stylesheet
        
        Args:
            stylesheet_name: Name of stylesheet file to delete
            
        Returns:
            True if deleted, False otherwise
        """
        stylesheet_path = self.stylesheets_dir / stylesheet_name
        stylesheet_path_str = str(stylesheet_path)

        if not _fs.exists(stylesheet_path_str):
            logger.warning(f"Stylesheet not found for deletion: {stylesheet_name}")
            return False

        try:
            _fs.delete_path(stylesheet_path_str)
            logger.info(f"Deleted stylesheet: {stylesheet_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting stylesheet {stylesheet_name}: {e}")
            return False
    
    def get_channel_stylesheet(self, channel_id: int) -> Optional[str]:
        """
        Get stylesheet for a specific channel
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Stylesheet content, or default if channel-specific not found
        """
        channel_stylesheet = f"channel_{channel_id}.css"
        content = self.load_stylesheet(channel_stylesheet)
        
        if content is None:
            # Fall back to default
            content = self.load_stylesheet()
        
        return content
    
    def set_channel_stylesheet(self, channel_id: int, content: str) -> bool:
        """
        Set stylesheet for a specific channel
        
        Args:
            channel_id: Channel ID
            content: CSS content
            
        Returns:
            True if saved successfully, False otherwise
        """
        channel_stylesheet = f"channel_{channel_id}.css"
        return self.save_stylesheet(channel_stylesheet, content)
