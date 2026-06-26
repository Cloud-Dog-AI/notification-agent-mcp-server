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
Description: Natural Language Parser - Parses natural language notification commands (e.g., "Send notification to Fred that JOB XXXX has finished")

Related Requirements: FR1.15, UC1.2
Covers: UC1.3
Related Tasks: T21
Related Architecture: CC4.3
Related Tests: UT1.11

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import re
from typing import Dict, Any, List
from .user_resolver import UserResolver
from .group_resolver import GroupResolver
from ...utils.logger import get_logger

logger = get_logger(__name__)


class NaturalLanguageParser:
    """Parses natural language notification commands"""
    
    def __init__(self, db):
        """
        Initialize NaturalLanguageParser
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.user_resolver = UserResolver(db)
        self.group_resolver = GroupResolver(db)
    
    def parse(self, command: str) -> Dict[str, Any]:
        """
        Parse a natural language notification command
        
        Args:
            command: Natural language command string
            
        Returns:
            Parsed command dict with:
            - recipients: List of user emails/addresses
            - groups: List of group names
            - content: Message content
            - subject: Optional subject
            - channels: Optional channel names
        """
        command = command.strip()
        
        result = {
            "recipients": [],
            "groups": [],
            "content": [],
            "subject": None,
            "channels": [],
            "raw_command": command,
        }
        
        # Pattern 1: "Send [notification/message] to {recipient} that {content}"
        pattern1 = re.compile(
            r'send\s+(?:a\s+)?(?:notification|message|email|text|sms)?\s+to\s+(.+?)\s+that\s+(.+)',
            re.IGNORECASE
        )
        match = pattern1.match(command)
        if match:
            recipients_str = match.group(1)
            content_str = match.group(2)
            
            # Extract recipients
            recipients = self._extract_recipients(recipients_str)
            result["recipients"] = recipients
            
            # Extract content
            result["content"] = [{"type": "text", "body": content_str}]
            
            # Try to extract subject from content
            subject_match = re.match(r'^(.+?)\s+has\s+(finished|completed|failed|started)', content_str, re.IGNORECASE)
            if subject_match:
                result["subject"] = content_str.split('.')[0] if '.' in content_str else content_str[:60]
            
            return result
        
        # Pattern 4: "Send to {group}" or "Send all the results to {group}" (check before pattern 2)
        pattern4 = re.compile(
            r'send\s+(?:to|all\s+the\s+results\s+to)\s+(.+)',
            re.IGNORECASE
        )
        match = pattern4.match(command)
        if match:
            recipients_str = match.group(1)
            
            # Extract groups first
            groups = self._extract_groups(recipients_str)
            result["groups"] = groups
            
            # Extract recipients (excluding groups)
            recipients = self._extract_recipients(recipients_str)
            result["recipients"] = recipients
            
            # Default content if not specified
            result["content"] = [{"type": "text", "body": "Notification"}]
            
            return result
        
        # Pattern 2: "Send {content} to {recipient}"
        pattern2 = re.compile(
            r'send\s+(.+?)\s+to\s+(.+)',
            re.IGNORECASE
        )
        match = pattern2.match(command)
        if match:
            content_str = match.group(1)
            recipients_str = match.group(2)
            
            # Extract recipients
            recipients = self._extract_recipients(recipients_str)
            result["recipients"] = recipients
            
            # Extract content
            result["content"] = [{"type": "text", "body": content_str}]
            
            return result
        
        # Pattern 3: "Notify {recipient} about {topic}"
        pattern3 = re.compile(
            r'notify\s+(.+?)\s+about\s+(.+)',
            re.IGNORECASE
        )
        match = pattern3.match(command)
        if match:
            recipients_str = match.group(1)
            topic_str = match.group(2)
            
            # Extract recipients
            recipients = self._extract_recipients(recipients_str)
            result["recipients"] = recipients
            
            # Extract content
            result["content"] = [{"type": "text", "body": f"Notification about: {topic_str}"}]
            result["subject"] = topic_str
            
            return result
        
        # Fallback: Try to extract recipients and use entire command as content
        recipients = self._extract_recipients(command)
        if recipients:
            result["recipients"] = recipients
            result["content"] = [{"type": "text", "body": command}]
        else:
            # No recipients found, use entire command as content
            result["content"] = [{"type": "text", "body": command}]
        
        return result
    
    def _extract_recipients(self, text: str) -> List[str]:
        """Extract recipient references from text"""
        recipients = []
        
        # Split by common separators
        parts = re.split(r'[,\s]+(?:and|&)\s+', text, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        for part in parts:
            # Check if it's an email
            if '@' in part:
                recipients.append(part)
            else:
                # First check if it's a group (groups take precedence for group-like names)
                group = self.group_resolver.resolve(part)
                if group:
                    # Don't add groups to recipients - they'll be handled separately
                    continue
                
                # Try to resolve as user
                user = self.user_resolver.resolve(part)
                if user:
                    # Get user's primary email destination
                    from ...database.repositories import UserDestinationRepository
                    dest_repo = UserDestinationRepository(self.db)
                    primary = dest_repo.get_primary(user['id'], 'smtp')
                    if primary:
                        recipients.append(primary['destination'])
                    elif user.get('email'):
                        recipients.append(user['email'])
        
        return recipients
    
    def _extract_groups(self, text: str) -> List[str]:
        """Extract group references from text"""
        groups = []
        
        # Split by common separators
        parts = re.split(r'[,\s]+(?:and|&)\s+', text, flags=re.IGNORECASE)
        parts = [p.strip() for p in parts if p.strip()]
        
        for part in parts:
            # Try to resolve as group
            group = self.group_resolver.resolve(part)
            if group:
                groups.append(group['name'])
        
        return groups
