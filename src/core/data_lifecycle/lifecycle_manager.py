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
Description: Data Lifecycle Manager - Automated deletion based on retention policies

Related Requirements: NF1.8
Related Tasks: T39
Related Architecture: DM1.1
Related Tests: ST1.13

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
from typing import Dict, Any, Optional

from ..compliance.retention import RetentionManager
from ..compliance.pii_redaction import PIIRedactor

logger = get_logger(__name__)


class DataLifecycleManager:
    """Manages data lifecycle and automated deletion"""
    
    def __init__(
        self,
        retention_manager: Optional[RetentionManager] = None,
        pii_redactor: Optional[PIIRedactor] = None
    ):
        """
        Initialize data lifecycle manager
        
        Args:
            retention_manager: Retention manager instance
            pii_redactor: PII redactor instance
        """
        self.retention_manager = retention_manager or RetentionManager()
        self.pii_redactor = pii_redactor or PIIRedactor()
        
        logger.info("DataLifecycleManager initialized")
    
    def cleanup_expired_data(
        self,
        db,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Clean up expired data based on retention policies
        
        Args:
            db: Database connection
            dry_run: If True, only report what would be deleted
            
        Returns:
            Dictionary with deletion counts
        """
        counts = {
            "messages": 0,
            "deliveries": 0,
            "receipts": 0,
            "audit_events": 0
        }
        
        # Clean up messages
        messages_cutoff = self.retention_manager.get_retention_cutoff("messages")
        if messages_cutoff:
            if dry_run:
                # Count only
                result = db.execute(
                    "SELECT COUNT(*) FROM messages WHERE created_at < ?",
                    (messages_cutoff,)
                ).fetchone()
                counts["messages"] = result[0] if result else 0
            else:
                # Delete
                cursor = db.execute(
                    "DELETE FROM messages WHERE created_at < ?",
                    (messages_cutoff,)
                )
                counts["messages"] = cursor.rowcount
                db.commit()
        
        # Clean up deliveries
        deliveries_cutoff = self.retention_manager.get_retention_cutoff("deliveries")
        if deliveries_cutoff:
            if dry_run:
                result = db.execute(
                    "SELECT COUNT(*) FROM deliveries WHERE created_at < ?",
                    (deliveries_cutoff,)
                ).fetchone()
                counts["deliveries"] = result[0] if result else 0
            else:
                cursor = db.execute(
                    "DELETE FROM deliveries WHERE created_at < ?",
                    (deliveries_cutoff,)
                )
                counts["deliveries"] = cursor.rowcount
                db.commit()
        
        # Clean up receipts
        receipts_cutoff = self.retention_manager.get_retention_cutoff("receipts")
        if receipts_cutoff:
            if dry_run:
                result = db.execute(
                    "SELECT COUNT(*) FROM receipts WHERE created_at < ?",
                    (receipts_cutoff,)
                ).fetchone()
                counts["receipts"] = result[0] if result else 0
            else:
                cursor = db.execute(
                    "DELETE FROM receipts WHERE created_at < ?",
                    (receipts_cutoff,)
                )
                counts["receipts"] = cursor.rowcount
                db.commit()
        
        # Clean up audit events
        audit_cutoff = self.retention_manager.get_retention_cutoff("audit_events")
        if audit_cutoff:
            if dry_run:
                result = db.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE created_at < ?",
                    (audit_cutoff,)
                ).fetchone()
                counts["audit_events"] = result[0] if result else 0
            else:
                cursor = db.execute(
                    "DELETE FROM audit_events WHERE created_at < ?",
                    (audit_cutoff,)
                )
                counts["audit_events"] = cursor.rowcount
                db.commit()
        
        logger.info(f"Data cleanup {'(dry run)' if dry_run else ''}: {counts}")
        return counts
    
    def redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive data in-place
        
        Args:
            data: Data dictionary
            
        Returns:
            Redacted data dictionary
        """
        return self.pii_redactor.redact_dict(data)
