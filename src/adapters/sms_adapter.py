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
Description: Real SMS Adapter for SMS Notifications - Implements the ChannelAdapter interface for actual SMS delivery via providers like Twilio

Related Requirements: FR1.7
Related Tasks: T18
Related Architecture: CC5.1.2
Related Tests: UT1.4, IT1.12

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import re
from typing import Dict, Any
from .base import ChannelAdapter


class SMSAdapter(ChannelAdapter):
    """
    Real SMS Adapter for sending SMS via provider APIs (Twilio, etc).
    
    Configuration:
        provider: SMS provider name ('twilio', 'aws_sns', etc.)
        account_sid: Provider account SID/ID
        auth_token: Provider authentication token
        from_number: Sender phone number (E.164 format)
        api_endpoint: Optional custom API endpoint
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider = config.get("provider", "twilio")
        self.account_sid = config.get("account_sid")
        self.auth_token = config.get("auth_token")
        self.from_number = config.get("from_number")
        self.api_endpoint = config.get("api_endpoint")
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate phone number (E.164 format).
        
        E.164 format: +[country code][number]
        Example: +1234567890
        
        Args:
            destination: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        # E.164 regex: + followed by 1-15 digits
        e164_pattern = r'^\+[1-9]\d{1,14}$'
        return bool(re.match(e164_pattern, destination))
    
    async def send(self, destination: str, content: Dict[str, Any]) -> Any:
        """
        Send SMS via provider API.
        
        Args:
            destination: Recipient phone number (E.164 format)
            content: SMS content dict with:
                - body: SMS message text
                - media_url: Optional MMS media URL
                
        Returns:
            Result object with success status and provider_id (message SID)
        """
        if not self.validate_destination(destination):
            return type('Result', (), {
                'success': False,
                'error': f'Invalid phone number: {destination}'
            })()
        
        # TODO: Implement actual provider integration
        # For now, return not implemented
        return type('Result', (), {
            'success': False,
            'error': 'SMS adapter not yet fully implemented - requires provider credentials'
        })()
    
    def classify_error(self, error: Any) -> str:
        """
        Classify SMS provider errors as transient or permanent.
        
        Transient: Rate limits, temporary provider issues, network errors
        Permanent: Invalid number, account issues, compliance violations
        
        Args:
            error: Exception or error object
            
        Returns:
            'transient' or 'permanent'
        """
        error_str = str(error).lower()
        
        # Permanent errors
        permanent_keywords = ['invalid', 'blocked', 'unsubscribed', 'compliance', 
                             'account', 'suspended', 'unauthorized']
        if any(kw in error_str for kw in permanent_keywords):
            return "permanent"
        
        # Rate limit = transient
        if 'rate' in error_str or 'limit' in error_str or '429' in error_str:
            return "transient"
        
        # Default to transient (can retry)
        return "transient"
    
    async def confirm(self, provider_id: str) -> Dict[str, Any]:
        """
        Query provider API for delivery status.
        
        Args:
            provider_id: Message SID from send operation
            
        Returns:
            Status dict with delivery information
        """
        # TODO: Implement provider API polling
        return {
            "status": "unknown",
            "note": "SMS status polling not yet implemented"
        }
    
    def parse_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SMS delivery receipt callback (e.g., from Twilio).
        
        Args:
            callback_data: Raw callback data from provider
            
        Returns:
            Parsed callback dict with status, message_id, etc.
        """
        # Twilio callback format
        if self.provider == "twilio":
            return {
                "message_id": callback_data.get("MessageSid"),
                "status": self._map_twilio_status(callback_data.get("MessageStatus")),
                "destination": callback_data.get("To"),
                "from": callback_data.get("From"),
                "timestamp": callback_data.get("DateSent"),
                "raw_data": callback_data
            }
        
        # Generic format
        return {
            "message_id": callback_data.get("message_id"),
            "status": callback_data.get("status", "unknown"),
            "destination": callback_data.get("destination"),
            "raw_data": callback_data
        }
    
    def _map_twilio_status(self, twilio_status: str) -> str:
        """Map Twilio status to our internal states."""
        status_map = {
            "queued": "queued",
            "sending": "sending",
            "sent": "sent",
            "delivered": "delivered",
            "undelivered": "hard_failed",
            "failed": "hard_failed"
        }
        return status_map.get(twilio_status, "unknown")
