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
Description: Signature Manager for Webhook Security - Provides HMAC-SHA256 signature generation and verification for secure webhooks, prevents replay attacks by validating timestamps

Related Requirements: CS1.2
Related Tasks: T30
Related Architecture: SE1.2
Related Tests: ST1.5

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import hmac
import hashlib
import time
from typing import Optional


class SignatureManager:
    """
    Manages HMAC-SHA256 signatures for webhook security.
    
    Features:
    - HMAC-SHA256 signature generation
    - Signature verification
    - Timestamp-based replay attack prevention
    - Secret rotation support
    """
    
    def __init__(self, secret: str, max_age_seconds: int = 300):
        """
        Initialize signature manager.
        
        Args:
            secret: Secret key for HMAC signing
            max_age_seconds: Maximum age of timestamp to accept (default: 300 = 5 minutes)
        """
        self.secret = secret.encode('utf-8')
        self.max_age_seconds = max_age_seconds
    
    def generate_signature(self, payload: str, timestamp: str) -> str:
        """
        Generate HMAC-SHA256 signature for a payload.
        
        The signature is computed over: timestamp + payload
        This ensures the timestamp is part of the signed content.
        
        Args:
            payload: Request payload (typically JSON string)
            timestamp: Unix timestamp as string
            
        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        # Combine timestamp and payload
        message = f"{timestamp}.{payload}".encode('utf-8')
        
        # Compute HMAC-SHA256
        signature = hmac.new(
            self.secret,
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(self, payload: str, timestamp: str, provided_signature: str) -> bool:
        """
        Verify HMAC-SHA256 signature.
        
        Args:
            payload: Request payload
            timestamp: Unix timestamp as string
            provided_signature: Signature provided in request
            
        Returns:
            True if signature is valid, False otherwise
        """
        # Generate expected signature
        expected_signature = self.generate_signature(payload, timestamp)
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, provided_signature)
    
    def is_timestamp_valid(self, timestamp: str) -> bool:
        """
        Check if timestamp is within acceptable age.
        
        Prevents replay attacks by rejecting old requests.
        
        Args:
            timestamp: Unix timestamp as string
            
        Returns:
            True if timestamp is recent enough, False if too old
        """
        try:
            timestamp_value = int(timestamp)
            current_time = int(time.time())
            
            # Check if timestamp is too old
            age = current_time - timestamp_value
            
            # Also check if timestamp is in the future (clock skew protection)
            if timestamp_value > current_time + 60:  # Allow 60s future
                return False
            
            return age <= self.max_age_seconds
            
        except (ValueError, TypeError):
            return False
    
    def verify_webhook(self, payload: str, timestamp: str, signature: str) -> tuple[bool, Optional[str]]:
        """
        Verify webhook request (signature + timestamp).
        
        Args:
            payload: Request payload
            timestamp: Unix timestamp as string
            signature: Provided signature
            
        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if valid
            - (False, error_message) if invalid
        """
        # Check timestamp first (cheaper operation)
        if not self.is_timestamp_valid(timestamp):
            return False, "Timestamp too old or invalid (replay attack prevention)"
        
        # Verify signature
        if not self.verify_signature(payload, timestamp, signature):
            return False, "Invalid signature"
        
        return True, None
    
    def create_webhook_headers(self, payload: str) -> dict[str, str]:
        """
        Create headers for outgoing webhook requests.
        
        Args:
            payload: Request payload to sign
            
        Returns:
            Dict of headers with signature and timestamp
        """
        timestamp = str(int(time.time()))
        signature = self.generate_signature(payload, timestamp)
        
        return {
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp
        }
