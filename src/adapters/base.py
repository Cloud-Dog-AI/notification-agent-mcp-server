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
Description: Base channel adapter interface - defines abstract base class and interfaces for all channel adapters

Related Requirements: FR1.6, FR1.7, FR1.8, FR1.9
Related Tasks: T6, T17, T18, T19, T20
Related Architecture: CC5.1
Related Tests: UT1.4, IT1.12

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass


class ErrorClass(str, Enum):
    """Error classification for retry logic"""
    TRANSIENT = "transient"  # Temporary error, should retry
    PERMANENT = "permanent"  # Permanent error, no retry


@dataclass
class SendResult:
    """Result of send operation"""
    success: bool
    tracking_id: Optional[str] = None
    error: Optional[str] = None
    error_class: Optional[ErrorClass] = None
    latency_ms: Optional[int] = None


@dataclass
class ConfirmResult:
    """Result of confirmation polling"""
    status: str  # sent, accepted, delivered, read, failed
    timestamp: Optional[str] = None
    error: Optional[str] = None


class BaseChannelAdapter(ABC):
    """Base class for channel adapters"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize adapter with configuration
        
        Args:
            config: Channel-specific configuration
        """
        self.config = config
    
    @abstractmethod
    def validate_destination(self, destination: str) -> bool:
        """Validate destination address/phone/URL
        
        Args:
            destination: Destination identifier
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """Send message through this channel
        
        Args:
            delivery: Delivery record with destination and payload
            
        Returns:
            SendResult with tracking ID or error
        """
        pass
    
    @abstractmethod
    async def confirm(self, tracking_id: str) -> ConfirmResult:
        """Poll provider for delivery confirmation
        
        Args:
            tracking_id: Provider tracking ID
            
        Returns:
            ConfirmResult with current status
        """
        pass
    
    @abstractmethod
    def parse_callback(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse provider callback webhook
        
        Args:
            raw_data: Raw webhook payload
            
        Returns:
            Normalized callback data
        """
        pass
    
    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorClass:
        """Classify error as transient or permanent
        
        Args:
            error: Exception that occurred
            
        Returns:
            ErrorClass indicating retry strategy
        """
        pass


# Alias for backwards compatibility
ChannelAdapter = BaseChannelAdapter
