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
Description: Provider Simulators - Simulate external service providers for testing

Related Requirements: NF1.6
Related Tasks: T37
Related Architecture: TS1.1
Related Tests: IT1.5, IT1.6, IT1.7, IT1.8

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

import logging
from typing import Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

logger = logging.getLogger(__name__)


class SMTPSimulator:
    """Simulates SMTP server for testing"""
    
    def __init__(self, port: int = 1025):
        """
        Initialize SMTP simulator
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.received_messages = []
        self.should_fail = False
        self.failure_rate = 0.0  # 0.0 to 1.0
    
    def start(self):
        """Start simulator (mock implementation)"""
        logger.info(f"SMTP simulator started on port {self.port}")
    
    def stop(self):
        """Stop simulator"""
        logger.info("SMTP simulator stopped")
    
    def get_received_messages(self) -> list:
        """Get list of received messages"""
        return self.received_messages.copy()
    
    def clear_messages(self):
        """Clear received messages"""
        self.received_messages.clear()
    
    def set_failure_mode(self, should_fail: bool, failure_rate: float = 0.0):
        """
        Set failure mode
        
        Args:
            should_fail: Whether to fail all requests
            failure_rate: Rate of failures (0.0 to 1.0)
        """
        self.should_fail = should_fail
        self.failure_rate = failure_rate


class SlackSimulator:
    """Simulates Slack webhook for testing"""
    
    def __init__(self, port: int = 8888):
        """
        Initialize Slack simulator
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.received_messages = []
        self.should_fail = False
    
    def start(self):
        """Start simulator"""
        logger.info(f"Slack simulator started on port {self.port}")
    
    def stop(self):
        """Stop simulator"""
        logger.info("Slack simulator stopped")
    
    def get_received_messages(self) -> list:
        """Get list of received messages"""
        return self.received_messages.copy()
    
    def clear_messages(self):
        """Clear received messages"""
        self.received_messages.clear()


class SMSSimulator:
    """Simulates SMS provider for testing"""
    
    def __init__(self, port: int = 8889):
        """
        Initialize SMS simulator
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.received_messages = []
        self.should_fail = False
    
    def start(self):
        """Start simulator"""
        logger.info(f"SMS simulator started on port {self.port}")
    
    def stop(self):
        """Stop simulator"""
        logger.info("SMS simulator stopped")
    
    def get_received_messages(self) -> list:
        """Get list of received messages"""
        return self.received_messages.copy()
    
    def clear_messages(self):
        """Clear received messages"""
        self.received_messages.clear()


class WhatsAppSimulator:
    """Simulates WhatsApp provider for testing"""
    
    def __init__(self, port: int = 8890):
        """
        Initialize WhatsApp simulator
        
        Args:
            port: Port to listen on
        """
        self.port = port
        self.received_messages = []
        self.should_fail = False
    
    def start(self):
        """Start simulator"""
        logger.info(f"WhatsApp simulator started on port {self.port}")
    
    def stop(self):
        """Stop simulator"""
        logger.info("WhatsApp simulator stopped")
    
    def get_received_messages(self) -> list:
        """Get list of received messages"""
        return self.received_messages.copy()
    
    def clear_messages(self):
        """Clear received messages"""
        self.received_messages.clear()




