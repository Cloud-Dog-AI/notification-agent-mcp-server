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
Description: User Resolver - Resolves natural language user references to actual users (e.g., "Fred" -> User with display_name "Fred" or username "fred")

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
from ...database.repositories import UserRepository
from ...utils.logger import get_logger

logger = get_logger(__name__)


class UserResolver:
    """Resolves natural language user references to User objects"""
    
    def __init__(self, db):
        """
        Initialize UserResolver
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.user_repo = UserRepository(db)
    
    def resolve(self, reference: str) -> Optional[Dict[str, Any]]:
        """
        Resolve a natural language user reference to a user
        
        Args:
            reference: Natural language reference (e.g., "Fred", "user@example.com", "the admin")
            
        Returns:
            User dict if found, None otherwise
        """
        reference = reference.strip()
        
        # Try exact email match first
        if '@' in reference:
            user = self.user_repo.get_by_email(reference)
            if user:
                logger.debug(f"Resolved '{reference}' to user by email: {user['id']}")
                return user
        
        # Try exact username match
        user = self.user_repo.get_by_username(reference.lower())
        if user:
            logger.debug(f"Resolved '{reference}' to user by username: {user['id']}")
            return user
        
        # Try display name match (case-insensitive)
        user = self.user_repo.get_by_display_name(reference)
        if user:
            logger.debug(f"Resolved '{reference}' to user by display_name: {user['id']}")
            return user
        
        # Try partial display name match
        users = self.user_repo.search(reference, limit=10)
        if users:
            # Prefer exact matches
            for u in users:
                if u.get('display_name', '').lower() == reference.lower():
                    logger.debug(f"Resolved '{reference}' to user by exact display_name: {u['id']}")
                    return u
            # Use first result if no exact match
            logger.debug(f"Resolved '{reference}' to user by partial match: {users[0]['id']}")
            return users[0]
        
        # Try role-based resolution (e.g., "the admin", "an admin")
        role_match = re.match(r'^(the|an?)\s+(admin|administrator|viewer|editor)$', reference.lower())
        if role_match:
            role = role_match.group(2)
            if role == 'administrator':
                role = 'admin'
            users = self.user_repo.list_all(limit=100)
            for u in users:
                if u.get('role') == role:
                    logger.debug(f"Resolved '{reference}' to user by role: {u['id']}")
                    return u
        
        logger.warning(f"Could not resolve user reference: '{reference}'")
        return None
    
    def resolve_multiple(self, references: List[str]) -> List[Dict[str, Any]]:
        """
        Resolve multiple user references
        
        Args:
            references: List of natural language references
            
        Returns:
            List of resolved users (may contain None for unresolved references)
        """
        return [self.resolve(ref) for ref in references]
    
    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for users by query string
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching users
        """
        return self.user_repo.search(query, limit=limit)
