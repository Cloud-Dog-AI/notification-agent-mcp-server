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
Description: Group Manager for Notification Agent MCP Server - Handles group management, membership, and keywords

Related Requirements: FR1.13, FR1.14
Covers: BR1.3
Related Tasks: T19, T22
Related Architecture: CC4.2
Related Tests: UT1.9, UT1.10

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Optional, List, Dict
from src.database.repositories import (
    GroupRepository,
    GroupMemberRepository,
    GroupKeywordRepository,
    UserRepository
)
from src.database.db_manager import DatabaseManager


class GroupManager:
    """Manages groups, members, and keywords"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize group manager
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.group_repo = GroupRepository(db)
        self.member_repo = GroupMemberRepository(db)
        self.keyword_repo = GroupKeywordRepository(db)
        self.user_repo = UserRepository(db)
    
    def create_group(
        self,
        name: str,
        description: Optional[str] = None,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        enabled: bool = True,
    ) -> int:
        """
        Create a new group
        
        Args:
            name: Group name (must be unique)
            description: Group description
            language: Default language for group
            preferred_channel: Default preferred channel
            content_style: Default content style
            
        Returns:
            Group ID
        """
        return self.group_repo.create(
            name=name,
            description=description,
            language=language,
            preferred_channel=preferred_channel,
            content_style=content_style,
            enabled=enabled,
        )
    
    def get_group(self, group_id: int) -> Optional[Dict]:
        """
        Get group by ID with members and keywords
        
        Args:
            group_id: Group ID
            
        Returns:
            Group dict with members and keywords, or None
        """
        group = self.group_repo.get_by_id(group_id)
        if not group:
            return None
        
        members = self.member_repo.get_group_members(group_id)
        keywords = self.keyword_repo.get_by_group_id(group_id)
        
        return {
            **group,
            "members": members,
            "keywords": [kw["keyword"] for kw in keywords]
        }
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        """
        Get group by name
        
        Args:
            name: Group name
            
        Returns:
            Group dict or None
        """
        return self.group_repo.get_by_name(name)
    
    def list_groups(self, enabled_only: bool = True) -> List[Dict]:
        """
        List all groups
        
        Args:
            enabled_only: Only return enabled groups
            
        Returns:
            List of group dicts
        """
        return self.group_repo.list_all(enabled_only=enabled_only)
    
    def update_group(
        self,
        group_id: int,
        description: Optional[str] = None,
        language: Optional[str] = None,
        preferred_channel: Optional[str] = None,
        content_style: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        """
        Update group settings
        
        Args:
            group_id: Group ID
            description: New description
            language: New language
            preferred_channel: New preferred channel
            content_style: New content style
            enabled: Enable/disable group
        """
        self.group_repo.update(
            group_id=group_id,
            description=description,
            language=language,
            preferred_channel=preferred_channel,
            content_style=content_style,
            enabled=enabled
        )

    def delete_group(self, group_id: int) -> None:
        """
        Delete a group and related membership/keyword data.
        """
        self.member_repo.remove_group_members(group_id)
        self.keyword_repo.remove_group_keywords(group_id)
        self.group_repo.delete(group_id)
    
    def add_member(self, group_id: int, user_id: int, role: str = "member") -> bool:
        """
        Add a user to a group
        
        Args:
            group_id: Group ID
            user_id: User ID
            role: Member role (member, admin, etc.)
            
        Returns:
            True if added, False if already exists
        """
        result = self.member_repo.add_member(group_id, user_id, role)
        return result is not None
    
    def remove_member(self, group_id: int, user_id: int):
        """
        Remove a user from a group
        
        Args:
            group_id: Group ID
            user_id: User ID
        """
        self.member_repo.remove_member(group_id, user_id)
    
    def update_member_role(self, group_id: int, user_id: int, role: str):
        """
        Update a member's role
        
        Args:
            group_id: Group ID
            user_id: User ID
            role: New role
        """
        self.member_repo.update_role(group_id, user_id, role)
    
    def get_group_members(self, group_id: int) -> List[Dict]:
        """
        Get all members of a group
        
        Args:
            group_id: Group ID
            
        Returns:
            List of member dicts with user info
        """
        return self.member_repo.get_group_members(group_id)
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        """
        Get all groups a user belongs to
        
        Args:
            user_id: User ID
            
        Returns:
            List of group dicts with role
        """
        return self.member_repo.get_user_groups(user_id)
    
    def add_keyword(self, group_id: int, keyword: str) -> bool:
        """
        Add a keyword to a group
        
        Args:
            group_id: Group ID
            keyword: Keyword to add
            
        Returns:
            True if added, False if already exists
        """
        result = self.keyword_repo.add(group_id, keyword)
        return result is not None
    
    def remove_keyword(self, group_id: int, keyword: str):
        """
        Remove a keyword from a group
        
        Args:
            group_id: Group ID
            keyword: Keyword to remove
        """
        self.keyword_repo.remove(group_id, keyword)
    
    def get_group_keywords(self, group_id: int) -> List[str]:
        """
        Get all keywords for a group
        
        Args:
            group_id: Group ID
            
        Returns:
            List of keywords
        """
        keywords = self.keyword_repo.get_by_group_id(group_id)
        return [kw["keyword"] for kw in keywords]
