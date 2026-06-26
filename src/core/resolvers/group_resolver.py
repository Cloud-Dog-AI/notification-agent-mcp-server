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
Description: Group Resolver - Resolves natural language group references to actual groups (e.g., "Admin Users" -> Group with name "Admin Users")

Related Requirements: FR1.15, UC1.2
Related Tasks: T21
Related Architecture: CC4.3
Related Tests: UT1.11

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import re
from typing import Optional, Dict, Any, List
from ...database.repositories import GroupRepository
from ...utils.logger import get_logger

logger = get_logger(__name__)


class GroupResolver:
    """Resolves natural language group references to Group objects"""
    
    def __init__(self, db):
        """
        Initialize GroupResolver
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.group_repo = GroupRepository(db)
    
    def resolve(self, reference: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a natural language group reference to a group
        
        Args:
            reference: Natural language reference (e.g., "Admin Users", "the users group")
            
        Returns:
            Group dict if found, None otherwise
        """
        reference = reference.strip()
        
        # Remove common prefixes/suffixes
        cleaned = re.sub(r'^(the|a|an)\s+', '', reference.lower())
        cleaned = re.sub(r'\s+group$', '', cleaned)
        cleaned = cleaned.strip()
        
        # Try exact name match (case-insensitive)
        groups = self.group_repo.list_all(enabled_only=False)
        for group in groups:
            if group.get('name', '').lower() == cleaned or group.get('name', '').lower() == reference.lower():
                logger.debug(f"Resolved '{reference}' to group by exact name: {group['id']}")
                return group
        
        # Try partial name match
        for group in groups:
            group_name = group.get('name', '').lower()
            if cleaned in group_name or group_name in cleaned:
                logger.debug(f"Resolved '{reference}' to group by partial match: {group['id']}")
                return group
        
        # Try exact match with original reference
        group = self.group_repo.get_by_name(reference)
        if group:
            logger.debug(f"Resolved '{reference}' to group by name: {group['id']}")
            return group
        
        logger.warning(f"Could not resolve group reference: '{reference}'")
        return None
    
    def resolve_multiple(self, references: List[str]) -> List[Dict[str, Any]]:
        """
        Resolve multiple group references
        
        Args:
            references: List of natural language references
            
        Returns:
            List of resolved groups (may contain None for unresolved references)
        """
        return [self.resolve(ref) for ref in references]
    
    def list_all(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all groups
        
        Args:
            enabled_only: Only return enabled groups
            
        Returns:
            List of groups
        """
        return self.group_repo.list_all(enabled_only=enabled_only)
