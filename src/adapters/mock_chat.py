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
Description: Mock Chat REST Adapter for testing - provides mock implementation of chat/webhook adapter (Slack/Teams/Discord-like) for unit and integration tests

Related Requirements: FR1.8
Related Tasks: T6, T19
Related Architecture: CC5.1.3
Related Tests: UT1.4

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import re
import uuid
import time
from typing import Dict, Any
from .base import BaseChannelAdapter, SendResult, ConfirmResult, ErrorClass
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MockChatAdapter(BaseChannelAdapter):
    """Mock chat webhook adapter for testing"""
    
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    def validate_destination(self, destination: str) -> bool:
        """Validate webhook URL"""
        return bool(self.URL_PATTERN.match(destination))
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """Mock send - always succeeds"""
        start_time = time.time()
        
        destination = delivery.get("destination")
        payload = delivery.get("personalised_payload", "")
        
        if not self.validate_destination(destination):
            return SendResult(
                success=False,
                error="Invalid webhook URL",
                error_class=ErrorClass.PERMANENT,
            )
        
        # Simulate sending
        tracking_id = f"mock-chat-{uuid.uuid4().hex[:8]}"
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        # Log to console
        logger.info(f"[MOCK CHAT] Webhook: {destination}")
        logger.info(f"[MOCK CHAT] Tracking ID: {tracking_id}")
        logger.info(f"[MOCK CHAT] Payload: {payload[:100]}...")
        
        return SendResult(
            success=True,
            tracking_id=tracking_id,
            latency_ms=latency_ms,
        )
    
    async def confirm(self, tracking_id: str) -> ConfirmResult:
        """Mock confirm - always returns delivered"""
        return ConfirmResult(
            status="delivered",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        )
    
    def parse_callback(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse mock chat callback"""
        return {
            "provider_event": raw_data.get("event", "delivered"),
            "status": raw_data.get("status", "delivered"),
            "tracking_id": raw_data.get("tracking_id"),
            "timestamp": raw_data.get("timestamp"),
        }
    
    def classify_error(self, error: Exception) -> ErrorClass:
        """Classify error"""
        if isinstance(error, (TimeoutError, ConnectionError)):
            return ErrorClass.TRANSIENT
        return ErrorClass.PERMANENT
