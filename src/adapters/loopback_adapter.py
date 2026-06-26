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
Description: Loop-back Channel Adapter - Saves messages to system and returns message center URL (no actual delivery)

Related Requirements: FR1.21 (Test Channel Support)
Related Tasks: T32
Related Architecture: CC5.1.6
Related Tests: AT1.4a-AT1.4k

Recent Changes (max 10):
- (Initial implementation for AT1.4 test suite)
**************************************************
"""

import json
from typing import Dict, Any

from .base import BaseChannelAdapter, SendResult, ConfirmResult, ErrorClass
from ..config import get_config
from ..utils.logger import get_context_logger, get_logger

logger = get_logger(__name__)


class LoopBackAdapter(BaseChannelAdapter):
    """
    Loop-back adapter - saves messages to system and returns message center URL.
    
    This adapter does NOT send messages externally. Instead, it:
    1. Validates the delivery is properly formatted
    2. Returns immediately with success
    3. Provides a message center URL in the tracking_id
    
    Configuration:
        base_url: Base URL for message center (default: from config)
        message_path_template: URL template for message links (default: "/messages/{message_guid}")
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize loop-back adapter
        
        Args:
            config: Channel configuration dict with:
                - base_url: Base URL for message center (optional)
                - message_path_template: URL template (optional, default: "/messages/{message_guid}")
        """
        super().__init__(config)
        self.config = config
        
        # Get base URL from config or use default
        runtime_config = get_config()
        messages_base_url = runtime_config.get("messages.base_url")
        if not messages_base_url:
            raise RuntimeError("Missing required configuration: messages.base_url")
        
        self.base_url = config.get("base_url") or messages_base_url
        self.message_path_template = config.get("message_path_template", "/messages/{message_guid}")
        
        get_context_logger(
            logger.name,
            base_url=self.base_url,
            message_path_template=self.message_path_template,
        ).info("LoopBackAdapter initialized")
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate destination - loop-back accepts any destination string
        
        Args:
            destination: Any string (user identifier, email, etc.)
            
        Returns:
            True (always valid for loop-back)
        """
        return bool(destination and destination.strip())
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """
        Process delivery through loop-back channel.
        
        This does NOT send externally. Instead:
        1. Validates delivery format
        2. Extracts message_guid from delivery metadata
        3. Returns success with message center URL as tracking_id
        
        Args:
            delivery: Delivery dict with:
                - message_id: Message ID
                - message_guid: Message GUID (for URL generation)
                - metadata_json: JSON string with message_guid, preferences, etc.
                - personalised_payload: Formatted payload (for validation)
        
        Returns:
            SendResult with:
                - success: True
                - tracking_id: Message center URL
                - provider_response: Additional metadata
        """
        try:
            # Extract message_guid from delivery
            message_guid = delivery.get("message_guid")
            message_id = delivery.get("message_id")
            
            # Try to get from metadata if not in delivery dict
            if not message_guid:
                metadata_str = delivery.get("metadata_json", "{}")
                if isinstance(metadata_str, str):
                    metadata = json.loads(metadata_str)
                else:
                    metadata = metadata_str or {}
                message_guid = metadata.get("message_guid") or metadata.get("guid")
                message_id = message_id or metadata.get("message_id")
            
            # Validate we have at least message_id or message_guid
            if not message_guid and not message_id:
                raise ValueError("Loop-back adapter requires message_guid or message_id in delivery")
            
            # Construct message center URL
            if message_guid:
                message_url = f"{self.base_url.rstrip('/')}{self.message_path_template.format(message_guid=message_guid)}"
            else:
                # Fallback to message_id if no GUID
                message_url = f"{self.base_url.rstrip('/')}/messages/{message_id}"
            
            # Extract language from metadata for URL
            metadata_str = delivery.get("metadata_json", "{}")
            if isinstance(metadata_str, str):
                metadata = json.loads(metadata_str)
            else:
                metadata = metadata_str or {}
            
            preferences = metadata.get("preferences", {})
            target_language = preferences.get("language")
            
            # Add language parameter if available
            if target_language:
                separator = "&" if "?" in message_url else "?"
                message_url = f"{message_url}{separator}language={target_language}"
            
            get_context_logger(
                logger.name,
                message_id=message_id,
                message_guid=message_guid,
                message_url=message_url,
                target_language=target_language,
            ).info("Loop-back delivery processed")
            
            return SendResult(
                success=True,
                tracking_id=message_guid or str(message_id)  # Use message GUID as tracking_id
            )
            
        except Exception as e:
            logger.error(f"Loop-back delivery failed: {e}", exc_info=True)
            return SendResult(
                success=False,
                error=str(e),
                error_class=ErrorClass.PERMANENT
            )
    
    async def confirm(self, tracking_id: str) -> ConfirmResult:
        """
        Confirm delivery - for loop-back, delivery is always confirmed immediately
        
        Args:
            tracking_id: Message center URL (returned from send())
            
        Returns:
            ConfirmResult with "delivered" status
        """
        return ConfirmResult(
            confirmed=True,
            status="delivered",
            provider_response={
                "message_center_url": tracking_id,
                "delivery_method": "loop_back"
            }
        )
    
    def parse_callback(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse callback - loop-back doesn't use callbacks
        
        Args:
            raw_data: Raw callback data (not used)
            
        Returns:
            Empty dict
        """
        return {}
    
    def classify_error(self, error: Exception) -> ErrorClass:
        """
        Classify error - loop-back errors are usually permanent (configuration issues)
        
        Args:
            error: Exception that occurred
            
        Returns:
            ErrorClass.PERMANENT (loop-back errors are usually config issues)
        """
        return ErrorClass.PERMANENT
