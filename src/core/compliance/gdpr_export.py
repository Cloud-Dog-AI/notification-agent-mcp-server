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
Description: GDPR Export - GDPR-friendly data exports

Related Requirements: NF1.4
Related Tasks: T35
Related Architecture: SE1.4
Related Tests: ST1.10

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import json
from typing import Dict, Any, List
from datetime import datetime

logger = get_logger(__name__)


class GDPRExporter:
    """GDPR-friendly data exporter"""
    
    def __init__(self):
        """Initialize GDPR exporter"""
        logger.info("GDPRExporter initialized")
    
    def export_user_data(
        self,
        user_id: int,
        messages: List[Dict[str, Any]],
        deliveries: List[Dict[str, Any]],
        receipts: List[Dict[str, Any]],
        audit_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Export all user data in GDPR-friendly format
        
        Args:
            user_id: User ID
            messages: User's messages
            deliveries: User's deliveries
            receipts: User's receipts
            audit_events: User's audit events
            
        Returns:
            GDPR export dictionary
        """
        export = {
            "export_date": datetime.now().isoformat(),
            "user_id": user_id,
            "data_categories": {
                "messages": self._sanitize_messages(messages),
                "deliveries": self._sanitize_deliveries(deliveries),
                "receipts": self._sanitize_receipts(receipts),
                "audit_events": self._sanitize_audit_events(audit_events)
            },
            "metadata": {
                "total_messages": len(messages),
                "total_deliveries": len(deliveries),
                "total_receipts": len(receipts),
                "total_audit_events": len(audit_events)
            }
        }
        
        return export
    
    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize messages for export"""
        sanitized = []
        for msg in messages:
            sanitized.append({
                "id": msg.get("id"),
                "created_at": msg.get("created_at"),
                "status": msg.get("status"),
                "content_preview": self._preview_content(msg.get("content", [])),
                "destinations_count": len(msg.get("destinations", []))
            })
        return sanitized
    
    def _sanitize_deliveries(self, deliveries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize deliveries for export"""
        sanitized = []
        for deliv in deliveries:
            sanitized.append({
                "id": deliv.get("id"),
                "message_id": deliv.get("message_id"),
                "created_at": deliv.get("created_at"),
                "state": deliv.get("state"),
                "channel_type": deliv.get("channel_type"),
                "destination": "[REDACTED]"  # Don't export actual destinations
            })
        return sanitized
    
    def _sanitize_receipts(self, receipts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize receipts for export"""
        sanitized = []
        for receipt in receipts:
            sanitized.append({
                "id": receipt.get("id"),
                "delivery_id": receipt.get("delivery_id"),
                "created_at": receipt.get("created_at"),
                "state": receipt.get("state")
            })
        return sanitized
    
    def _sanitize_audit_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize audit events for export"""
        sanitized = []
        for event in events:
            sanitized.append({
                "id": event.get("id"),
                "kind": event.get("kind"),
                "created_at": event.get("created_at"),
                "actor": "[REDACTED]"  # Don't export actor details
            })
        return sanitized
    
    def _preview_content(self, content: List[Dict[str, Any]], max_length: int = 100) -> str:
        """Create preview of content"""
        if not content:
            return ""
        
        # Get first text block
        for block in content:
            if block.get("type") == "text":
                text = block.get("body", "")
                if len(text) > max_length:
                    return text[:max_length] + "..."
                return text
        
        return "[Content]"
    
    def export_to_json(self, export_data: Dict[str, Any]) -> str:
        """Export data to JSON string"""
        return json.dumps(export_data, indent=2, default=str)
