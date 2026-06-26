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
Description: Adapter Registry - manages channel adapter instances and provides factory methods

Related Requirements: FR1.6, FR1.7, FR1.8, FR1.9
Covers: BR1.1
Related Tasks: T6, T17, T18, T19, T20
Related Architecture: CC5.1
Related Tests: UT1.4, IT1.12

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Dict, Optional
from .base import BaseChannelAdapter
from .mock_email import MockEmailAdapter
from .mock_sms import MockSMSAdapter
from .mock_chat import MockChatAdapter

# Import real adapters
try:
    from .smtp_adapter import SMTPAdapter
except ImportError:
    SMTPAdapter = None

try:
    from .whatsapp_adapter import WhatsAppAdapter
except ImportError:
    WhatsAppAdapter = None

try:
    from .twilio_sms_adapter import TwilioSMSAdapter
except ImportError:
    TwilioSMSAdapter = None

try:
    from .chat_adapter import ChatAdapter
except ImportError:
    ChatAdapter = None


class AdapterRegistry:
    """Registry of channel adapters"""
    
    # Real adapters take precedence over mocks
    ADAPTER_TYPES = {
        "smtp": SMTPAdapter if SMTPAdapter else MockEmailAdapter,
        "email": SMTPAdapter if SMTPAdapter else MockEmailAdapter,
        "sms": TwilioSMSAdapter if TwilioSMSAdapter else MockSMSAdapter,
        "whatsapp": WhatsAppAdapter if WhatsAppAdapter else MockSMSAdapter,
        "chat_rest": ChatAdapter if ChatAdapter else MockChatAdapter,
        "chat": ChatAdapter if ChatAdapter else MockChatAdapter,
        "slack": ChatAdapter if ChatAdapter else MockChatAdapter,  # Slack uses ChatAdapter
        "file": None,  # Will be set below
    }
    
    # Import file adapter
    try:
        from .file_adapter import FileAdapter
        ADAPTER_TYPES["file"] = FileAdapter
    except ImportError:
        pass
    
    # Import loop-back adapter
    try:
        from .loopback_adapter import LoopBackAdapter
        ADAPTER_TYPES["loopback"] = LoopBackAdapter
        ADAPTER_TYPES["loop_back"] = LoopBackAdapter
        ADAPTER_TYPES["null"] = LoopBackAdapter  # Alias for "null" channel
    except ImportError:
        pass
    
    def __init__(self):
        self._adapters: Dict[int, BaseChannelAdapter] = {}
    
    def register_channel(self, channel_id: int, channel_type: str, config: Dict) -> BaseChannelAdapter:
        """Register a channel and create its adapter
        
        Args:
            channel_id: Channel ID
            channel_type: Channel type (smtp, sms, etc.)
            config: Channel configuration
            
        Returns:
            Adapter instance
        """
        adapter_class = self.ADAPTER_TYPES.get(channel_type.lower())
        
        if not adapter_class:
            raise ValueError(f"Unknown channel type: {channel_type}")
        
        adapter = adapter_class(config)
        self._adapters[channel_id] = adapter
        
        return adapter
    
    def get_adapter(self, channel_id: int) -> Optional[BaseChannelAdapter]:
        """Get adapter for a channel
        
        Args:
            channel_id: Channel ID
            
        Returns:
            Adapter instance or None
        """
        return self._adapters.get(channel_id)
    
    def unregister_channel(self, channel_id: int):
        """Remove channel adapter
        
        Args:
            channel_id: Channel ID
        """
        if channel_id in self._adapters:
            del self._adapters[channel_id]


# Global adapter registry
_adapter_registry: Optional[AdapterRegistry] = None


def get_adapter_registry() -> AdapterRegistry:
    """Get or create global adapter registry
    
    Returns:
        AdapterRegistry instance
    """
    global _adapter_registry
    
    if _adapter_registry is None:
        _adapter_registry = AdapterRegistry()
    
    return _adapter_registry
