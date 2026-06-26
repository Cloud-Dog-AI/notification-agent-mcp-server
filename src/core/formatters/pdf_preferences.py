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
Description: PDF Preference Resolver for Notification Agent MCP Server - Resolves PDF preferences from user, channel, and defaults

Related Requirements: FR1.18
Related Tasks: T29
Related Architecture: CC5.2.3
Related Tests: UT1.8, ST1.5, IT1.17, AT1.19

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

from typing import Optional
from enum import Enum

from src.utils.logger import get_logger
from src.config import get_config

logger = get_logger(__name__)


class PDFPreference(Enum):
    """PDF delivery preference options"""
    ATTACH = "attach"  # Attach PDF to message (email, Slack)
    LINK = "link"      # Store PDF and send link
    NONE = "none"      # Do not generate PDF


class PDFPreferenceResolver:
    """Resolves PDF preferences from user, channel, and defaults"""
    
    def __init__(self, db=None):
        """
        Initialize PDF preference resolver
        
        Args:
            db: DatabaseManager instance (optional, for direct DB access)
        """
        self.db = db
        self.config = get_config()
        self.default_preference = self.config.get("pdf.default_preference", "link")
        logger.info(f"PDFPreferenceResolver initialized with default: {self.default_preference}")
    
    def resolve_preference(
        self,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        user_preference: Optional[str] = None,
        channel_preference: Optional[str] = None
    ) -> PDFPreference:
        """
        Resolve PDF preference using priority: user > channel > default
        
        Args:
            user_id: User ID (to lookup preference if user_preference not provided)
            channel_id: Channel ID (to lookup preference if channel_preference not provided)
            user_preference: User PDF preference (optional, will lookup if not provided)
            channel_preference: Channel PDF preference (optional, will lookup if not provided)
            
        Returns:
            PDFPreference enum value
        """
        # Priority 1: User preference
        if user_id and user_preference is None:
            user_preference = self._get_user_preference(user_id)
        
        if user_preference:
            try:
                preference = PDFPreference(user_preference.lower())
                logger.debug(f"Using user PDF preference: {preference.value}")
                return preference
            except ValueError:
                logger.warning(f"Invalid user PDF preference: {user_preference}, falling back to channel/default")
        
        # Priority 2: Channel preference
        if channel_id and channel_preference is None:
            channel_preference = self._get_channel_preference(channel_id)
        
        if channel_preference:
            try:
                preference = PDFPreference(channel_preference.lower())
                logger.debug(f"Using channel PDF preference: {preference.value}")
                return preference
            except ValueError:
                logger.warning(f"Invalid channel PDF preference: {channel_preference}, falling back to default")
        
        # Priority 3: Default preference
        try:
            preference = PDFPreference(self.default_preference.lower())
            logger.debug(f"Using default PDF preference: {preference.value}")
            return preference
        except ValueError:
            logger.warning(f"Invalid default PDF preference: {self.default_preference}, using 'link'")
            return PDFPreference.LINK
    
    def _get_user_preference(self, user_id: int) -> Optional[str]:
        """
        Get user PDF preference from database
        
        Args:
            user_id: User ID
            
        Returns:
            User PDF preference or None
        """
        if not self.db:
            return None
        
        try:
            from src.database.repositories import UserRepository
            user_repo = UserRepository(self.db)
            user = user_repo.get_by_id(user_id)
            if user:
                return user.get("pdf_preference")
        except Exception as e:
            logger.error(f"Error getting user PDF preference: {e}")
        
        return None
    
    def _get_channel_preference(self, channel_id: int) -> Optional[str]:
        """
        Get channel PDF preference from database
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Channel PDF preference or None
        """
        if not self.db:
            return None
        
        try:
            from src.database.repositories import ChannelRepository
            channel_repo = ChannelRepository(self.db)
            channel = channel_repo.get_by_id(channel_id)
            if channel:
                return channel.get("pdf_preference")
        except Exception as e:
            logger.error(f"Error getting channel PDF preference: {e}")
        
        return None
    
    def should_generate_pdf(self, preference: PDFPreference) -> bool:
        """
        Check if PDF should be generated based on preference
        
        Args:
            preference: PDFPreference enum value
            
        Returns:
            True if PDF should be generated, False otherwise
        """
        return preference != PDFPreference.NONE
    
    def should_attach_pdf(self, preference: PDFPreference) -> bool:
        """
        Check if PDF should be attached (vs linked)
        
        Args:
            preference: PDFPreference enum value
            
        Returns:
            True if PDF should be attached, False if linked
        """
        return preference == PDFPreference.ATTACH
    
    def should_link_pdf(self, preference: PDFPreference) -> bool:
        """
        Check if PDF should be linked (vs attached)
        
        Args:
            preference: PDFPreference enum value
            
        Returns:
            True if PDF should be linked, False if attached
        """
        return preference == PDFPreference.LINK
