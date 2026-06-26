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
Description: User Manager for Notification Agent MCP Server - Handles user lookup, destination management, preferences, and keywords

Related Requirements: FR1.13, FR1.14
Covers: BR1.2, UC1.4
Related Tasks: T19, T22
Related Architecture: CC4.1
Related Tests: UT1.8

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Optional, List, Dict, Any
from src.database.repositories import (
    UserRepository,
    UserDestinationRepository,
    UserKeywordRepository
)
from src.database.db_manager import DatabaseManager


class UserManager:
    """Manages users, destinations, preferences, and keywords"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize user manager
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.user_repo = UserRepository(db)
        self.destination_repo = UserDestinationRepository(db)
        self.keyword_repo = UserKeywordRepository(db)
    
    def lookup_user(self, identifier: str, by: str = "username") -> Optional[Dict]:
        """
        Lookup user by username, email, or display_name
        
        Args:
            identifier: Username, email, or display_name
            by: Search method - 'username', 'email', or 'display_name'
            
        Returns:
            User dict or None
        """
        if by == "username":
            return self.user_repo.get_by_username(identifier)
        elif by == "email":
            return self.user_repo.get_by_email(identifier)
        elif by == "display_name":
            return self.user_repo.get_by_display_name(identifier)
        else:
            raise ValueError(f"Invalid lookup method: {by}")
    
    def search_users(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search users by username, email, or display_name
        
        Args:
            query: Search term
            limit: Maximum results
            
        Returns:
            List of user dicts
        """
        return self.user_repo.search(query, limit)
    
    def get_user_with_destinations(self, user_id: int) -> Optional[Dict]:
        """
        Get user with all destinations
        
        Args:
            user_id: User ID
            
        Returns:
            User dict with destinations list, or None
        """
        user = self.user_repo.get_by_id(user_id)
        if not user:
            return None
        
        destinations = self.destination_repo.get_by_user_id(user_id)
        keywords = self.keyword_repo.get_by_user_id(user_id)
        
        return {
            **user,
            "destinations": destinations,
            "keywords": [kw["keyword"] for kw in keywords]
        }
    
    def add_destination(
        self,
        user_id: int,
        channel_type: str,
        destination: str,
        is_primary: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add a destination for a user
        
        Args:
            user_id: User ID
            channel_type: Channel type (email, sms, whatsapp, slack, teams)
            destination: Destination address
            is_primary: Whether this is the primary destination for this channel type
            metadata: Optional metadata dict
            
        Returns:
            Destination ID
        """
        import json
        metadata_json = json.dumps(metadata) if metadata else None
        
        # If setting as primary, unset other primaries for this user/channel
        if is_primary:
            existing_primary = self.destination_repo.get_primary(user_id, channel_type)
            if existing_primary:
                self.destination_repo.set_primary(existing_primary["id"], user_id, channel_type)
        
        return self.destination_repo.create(
            user_id=user_id,
            channel_type=channel_type,
            destination=destination,
            is_primary=is_primary,
            metadata_json=metadata_json
        )
    
    def set_primary_destination(self, destination_id: int, user_id: int):
        """
        Set a destination as primary
        
        Args:
            destination_id: Destination ID
            user_id: User ID
        """
        destination = self.destination_repo.get_by_id(destination_id)
        if not destination or destination["user_id"] != user_id:
            raise ValueError("Destination not found or doesn't belong to user")
        
        self.destination_repo.set_primary(destination_id, user_id, destination["channel_type"])
    
    def remove_destination(self, destination_id: int, user_id: int):
        """
        Remove a destination
        
        Args:
            destination_id: Destination ID
            user_id: User ID
        """
        destination = self.destination_repo.get_by_id(destination_id)
        if not destination or destination["user_id"] != user_id:
            raise ValueError("Destination not found or doesn't belong to user")
        
        self.destination_repo.delete(destination_id, user_id)
    
    def update_preferences(
        self,
        user_id: int,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        timezone: Optional[str] = None,
    ):
        """
        Update user preferences
        
        Args:
            user_id: User ID
            language: Language preference (ISO 639-1)
            preferred_channel: Preferred channel type
            content_style: Content style (short, detailed, summary_link, rich)
            timezone: IANA timezone
        """
        self.user_repo.update_preferences(
            user_id=user_id,
            language=language,
            preferred_channel=preferred_channel,
            content_style=content_style,
            timezone=timezone
        )
    
    def add_keyword(self, user_id: int, keyword: str) -> bool:
        """
        Add a keyword to a user
        
        Args:
            user_id: User ID
            keyword: Keyword to add
            
        Returns:
            True if added, False if already exists
        """
        result = self.keyword_repo.add(user_id, keyword)
        return result is not None
    
    def remove_keyword(self, user_id: int, keyword: str):
        """
        Remove a keyword from a user
        
        Args:
            user_id: User ID
            keyword: Keyword to remove
        """
        self.keyword_repo.remove(user_id, keyword)
    
    def get_user_keywords(self, user_id: int) -> List[str]:
        """
        Get all keywords for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of keywords
        """
        keywords = self.keyword_repo.get_by_user_id(user_id)
        return [kw["keyword"] for kw in keywords]
    
    def get_primary_destination(self, user_id: int, channel_type: str) -> Optional[str]:
        """
        Get primary destination for a user and channel type
        
        Args:
            user_id: User ID
            channel_type: Channel type
            
        Returns:
            Destination address or None
        """
        destination = self.destination_repo.get_primary(user_id, channel_type)
        return destination["destination"] if destination else None
