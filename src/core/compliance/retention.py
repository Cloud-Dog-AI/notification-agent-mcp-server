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
Description: Retention Manager - Configurable retention windows

Related Requirements: NF1.4, NF1.8
Related Tasks: T35, T39
Related Architecture: SE1.4, DM1.1
Related Tests: ST1.10, ST1.13

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = get_logger(__name__)


class RetentionManager:
    """Manages data retention and lifecycle"""
    
    def __init__(
        self,
        messages_days: int = 30,
        deliveries_days: int = 30,
        receipts_days: int = 30,
        logs_days: int = 30,
        audit_events_days: int = 90
    ):
        """
        Initialize retention manager
        
        Args:
            messages_days: Retention period for messages (days)
            deliveries_days: Retention period for deliveries (days)
            receipts_days: Retention period for receipts (days)
            logs_days: Retention period for logs (days)
            audit_events_days: Retention period for audit events (days)
        """
        self.messages_days = messages_days
        self.deliveries_days = deliveries_days
        self.receipts_days = receipts_days
        self.logs_days = logs_days
        self.audit_events_days = audit_events_days
        
        logger.info(f"RetentionManager initialized: messages={messages_days}d, deliveries={deliveries_days}d")
    
    def get_retention_cutoff(self, entity_type: str) -> Optional[datetime]:
        """
        Get retention cutoff date for entity type
        
        Args:
            entity_type: Type of entity (messages, deliveries, receipts, logs, audit_events)
            
        Returns:
            Cutoff datetime or None if no retention
        """
        days = getattr(self, f"{entity_type}_days", None)
        if days is None or days <= 0:
            return None
        
        return datetime.now() - timedelta(days=days)
    
    def should_retain(self, entity_type: str, created_at: datetime) -> bool:
        """
        Check if entity should be retained
        
        Args:
            entity_type: Type of entity
            created_at: Creation timestamp
            
        Returns:
            True if should be retained, False if should be deleted
        """
        cutoff = self.get_retention_cutoff(entity_type)
        if cutoff is None:
            return True  # No retention policy
        
        return created_at >= cutoff
    
    def get_retention_config(self) -> Dict[str, int]:
        """Get current retention configuration"""
        return {
            "messages_days": self.messages_days,
            "deliveries_days": self.deliveries_days,
            "receipts_days": self.receipts_days,
            "logs_days": self.logs_days,
            "audit_events_days": self.audit_events_days
        }
