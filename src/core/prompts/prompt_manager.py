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
Description: Prompt Manager for Notification Agent MCP Server - Handles LLM prompt selection, management, and variable substitution

Related Requirements: FR1.12
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: UT1.7

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Optional, Dict, Any, List
from src.database.repositories import LLMPromptRepository
from src.database.db_manager import DatabaseManager


class PromptManager:
    """Manages LLM prompts with priority-based selection"""
    
    def __init__(self, db: DatabaseManager):
        """Initialize prompt manager
        
        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.prompt_repo = LLMPromptRepository(db)
    
    def get_prompt(
        self,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        language: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Get the best matching prompt for given criteria.
        
        Selection priority:
        1. Most specific match (channel + group + language + keyword)
        2. Channel + group + language
        3. Channel + group
        4. Channel + language
        5. Channel only
        6. Default (no filters)
        
        Args:
            channel_type: Channel type (email, sms, whatsapp, etc.)
            group_id: Group ID
            language: Language code (en, fr, etc.)
            keyword: Personalization keyword
            
        Returns:
            Prompt dict or None
        """
        return self.prompt_repo.find_best_match(
            channel_type=channel_type,
            group_id=group_id,
            language=language,
            keyword=keyword
        )
    
    def create_prompt(
        self,
        name: str,
        prompt_text: str,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        language: Optional[str] = None,
        keyword: Optional[str] = None,
        variables_json: Optional[str] = None,
        priority: int = 0,
    ) -> int:
        """
        Create a new prompt
        
        Args:
            name: Prompt name
            prompt_text: The prompt template text
            channel_type: Channel type filter
            group_id: Group ID filter
            language: Language filter
            keyword: Keyword filter
            variables_json: JSON schema for prompt variables
            priority: Priority (higher = selected first for same specificity)
            
        Returns:
            Prompt ID
        """
        return self.prompt_repo.create(
            name=name,
            prompt_text=prompt_text,
            channel_type=channel_type,
            group_id=group_id,
            language=language,
            keyword=keyword,
            variables_json=variables_json,
            priority=priority
        )
    
    def get_prompt_by_id(self, prompt_id: int) -> Optional[Dict]:
        """Get prompt by ID"""
        return self.prompt_repo.get_by_id(prompt_id)
    
    def get_prompt_by_name(self, name: str) -> Optional[Dict]:
        """Get prompt by name"""
        return self.prompt_repo.get_by_name(name)
    
    def list_prompts(
        self,
        channel_type: Optional[str] = None,
        group_id: Optional[int] = None,
        enabled_only: bool = True,
    ) -> List[Dict]:
        """List prompts with optional filters"""
        return self.prompt_repo.list_all(
            channel_type=channel_type,
            group_id=group_id,
            enabled_only=enabled_only
        )
    
    def update_prompt(
        self,
        prompt_id: int,
        name: Optional[str] = None,
        prompt_text: Optional[str] = None,
        variables_json: Optional[str] = None,
        priority: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        """Update prompt"""
        self.prompt_repo.update(
            prompt_id=prompt_id,
            name=name,
            prompt_text=prompt_text,
            variables_json=variables_json,
            priority=priority,
            enabled=enabled
        )
    
    def render_prompt(
        self,
        prompt_text: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Render prompt with variable substitution.
        
        Variables are substituted using {variable_name} syntax.
        
        Args:
            prompt_text: Prompt template
            variables: Variable values
            
        Returns:
            Rendered prompt text
        """
        if not variables:
            return prompt_text
        
        try:
            return prompt_text.format(**variables)
        except KeyError:
            # Missing variable - return original text
            return prompt_text
        except Exception:
            # Format error - return original text
            return prompt_text
