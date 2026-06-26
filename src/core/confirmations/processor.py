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
Description: Callback Processor for Delivery Confirmations - Processes incoming webhooks/callbacks from notification providers to update delivery status and create receipt records

Related Requirements: FR1.2
Related Tasks: T7
Related Architecture: CC2.1.4
Related Tests: IT1.10

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from typing import List as _List
from src.database.db_manager import DatabaseManager
from src.database.repositories import DeliveryRepository, ReceiptRepository, AuditEventRepository
from cloud_dog_jobs.callbacks.manager import CallbackManager
from src.core.state_machine import DeliveryState
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CallbackProcessor:
    """
    Processes delivery confirmation callbacks from providers.
    
    Features:
    - Provider-specific callback parsing
    - Idempotent callback handling (duplicates ignored)
    - Delivery state updates
    - Receipt record creation
    - Audit logging
    """
    
    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Initialize callback processor.
        
        Args:
            db: Database manager instance
        """
        self.db = db
        self.callback_manager = CallbackManager()
    
    async def process_callback(
        self,
        channel_type: str,
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a callback from a notification provider.
        
        Args:
            channel_type: Type of channel ('email', 'sms', 'chat')
            callback_data: Raw callback data from provider
            
        Returns:
            Processing result dict with:
                - success: bool
                - delivery_id: int (if found)
                - receipt_id: int (if created)
                - duplicate: bool (if already processed)
                - error: str (if failed)
        """
        try:
            # Parse callback based on channel type
            if channel_type == "email":
                parsed = await self.parse_smtp_callback(callback_data)
            elif channel_type == "sms":
                parsed = await self.parse_sms_callback(callback_data)
            elif channel_type == "chat":
                parsed = await self.parse_chat_callback(callback_data)
            else:
                return {
                    "success": False,
                    "error": f"Unknown channel type: {channel_type}"
                }
            
            # Find delivery record
            delivery_id = parsed.get("delivery_id")
            if not delivery_id:
                return {
                    "success": False,
                    "error": "Could not determine delivery_id from callback"
                }
            
            # Check if already processed (idempotency)
            if await self._is_duplicate(delivery_id, callback_data):
                logger.info(f"Duplicate callback for delivery {delivery_id}, ignoring")
                return {
                    "success": True,
                    "delivery_id": delivery_id,
                    "duplicate": True
                }
            
            # Update delivery state
            new_state = self._map_status_to_state(parsed.get("state", "unknown"))
            if new_state:
                await self._update_delivery_state(delivery_id, new_state)
                self.callback_manager.trigger_job_completion(
                    str(delivery_id),
                    status=new_state.value,
                    result_summary={"channel_type": channel_type, "provider_id": parsed.get("provider_id")},
                    duration_ms=0,
                )
            
            # Create receipt record
            receipt_id = await self._create_receipt(delivery_id, parsed, callback_data)
            
            # Audit log
            await self._audit_callback(delivery_id, channel_type, parsed)
            
            return {
                "success": True,
                "delivery_id": delivery_id,
                "receipt_id": receipt_id,
                "duplicate": False
            }
            
        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def parse_smtp_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SMTP/email delivery notification.
        
        Formats supported:
        - DSN (Delivery Status Notification)
        - SendGrid webhook
        - AWS SES notification
        - Generic bounce message
        
        Args:
            callback_data: Raw callback data
            
        Returns:
            Parsed data dict
        """
        return {
            "delivery_id": callback_data.get("delivery_id"),
            "state": callback_data.get("event", "unknown"),
            "recipient": callback_data.get("recipient"),
            "provider_id": callback_data.get("message_id"),
            "timestamp": callback_data.get("timestamp", datetime.now().isoformat()),
            "raw": callback_data
        }
    
    async def parse_sms_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse SMS delivery receipt.
        
        Formats supported:
        - Twilio status callback
        - AWS SNS delivery receipt
        - Generic SMS provider format
        
        Args:
            callback_data: Raw callback data
            
        Returns:
            Parsed data dict
        """
        # Twilio format
        if "MessageSid" in callback_data:
            return {
                "delivery_id": callback_data.get("delivery_id"),
                "state": self._map_twilio_status(callback_data.get("MessageStatus")),
                "destination": callback_data.get("To"),
                "provider_id": callback_data.get("MessageSid"),
                "timestamp": callback_data.get("DateSent", datetime.now().isoformat()),
                "raw": callback_data
            }
        
        # Generic format
        return {
            "delivery_id": callback_data.get("delivery_id"),
            "state": callback_data.get("status", "unknown"),
            "destination": callback_data.get("destination"),
            "provider_id": callback_data.get("message_id"),
            "timestamp": callback_data.get("timestamp", datetime.now().isoformat()),
            "raw": callback_data
        }
    
    async def parse_chat_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse chat/webhook callback.
        
        Args:
            callback_data: Raw callback data
            
        Returns:
            Parsed data dict
        """
        return {
            "delivery_id": callback_data.get("delivery_id"),
            "state": callback_data.get("status", "unknown"),
            "provider_id": callback_data.get("message_id"),
            "timestamp": callback_data.get("timestamp", datetime.now().isoformat()),
            "raw": callback_data
        }
    
    def _map_twilio_status(self, status: str) -> str:
        """Map Twilio status to our internal states."""
        status_map = {
            "queued": "queued",
            "sending": "sending",
            "sent": "sent",
            "delivered": "delivered",
            "undelivered": "hard_failed",
            "failed": "hard_failed"
        }
        return status_map.get(status.lower() if status else "", "unknown")
    
    def _map_status_to_state(self, status: str) -> Optional[DeliveryState]:
        """Map callback status to DeliveryState enum."""
        status_map = {
            "queued": DeliveryState.QUEUED,
            "sending": DeliveryState.SENDING,
            "sent": DeliveryState.SENT,
            "accepted": DeliveryState.ACCEPTED,
            "delivered": DeliveryState.DELIVERED,
            "read": DeliveryState.READ,
            "hard_failed": DeliveryState.HARD_FAILED,
            "soft_failed": DeliveryState.SOFT_FAILED
        }
        return status_map.get(status.lower() if status else "")

    def _find_state_path(self, start: DeliveryState, target: DeliveryState) -> Optional[list[DeliveryState]]:
        """
        Find a valid transition path between two delivery states.

        Provider callbacks can report later lifecycle states before local worker
        updates have advanced from queued/sending. We accept callback truth but
        still persist state transitions along valid edges.
        """
        if start == target:
            return [start]

        bfs_queue: list[tuple[DeliveryState, list[DeliveryState]]] = [(start, [start])]
        visited = {start}
        all_states = list(DeliveryState)

        while bfs_queue:
            current, path = bfs_queue.pop(0)
            for candidate in all_states:
                if candidate in visited:
                    continue
                if not current.can_transition_to(candidate):
                    continue
                next_path = path + [candidate]
                if candidate == target:
                    return next_path
                visited.add(candidate)
                bfs_queue.append((candidate, next_path))
        return None
    
    async def _is_duplicate(self, delivery_id: int, callback_data: Dict[str, Any]) -> bool:
        """
        Check if callback has already been processed.
        
        Uses receipt records to detect duplicates.
        """
        if not self.db:
            return False
        
        try:
            receipt_repo = ReceiptRepository(self.db)
            # Check if we have a receipt for this delivery with the same provider_id
            provider_id = callback_data.get("message_id") or callback_data.get("MessageSid")
            if provider_id:
                receipts = receipt_repo.get_by_delivery_id(delivery_id)
                for receipt in receipts:
                    # Check raw_data for provider_id
                    try:
                        raw_data = json.loads(receipt.get("raw_data", "{}"))
                        receipt_provider_id = raw_data.get("message_id") or raw_data.get("MessageSid")
                        if receipt_provider_id == provider_id:
                            return True
                    except Exception:
                        pass
            return False
        except Exception as e:
            logger.error(f"Error checking for duplicate: {e}")
            return False
    
    async def _update_delivery_state(self, delivery_id: int, new_state: DeliveryState):
        """Update delivery state in database."""
        if not self.db:
            return
        
        try:
            delivery_repo = DeliveryRepository(self.db)
            delivery = delivery_repo.get_by_id(delivery_id)
            
            if delivery:
                old_state = DeliveryState(delivery["state"])
                
                # Validate transition
                if old_state.can_transition_to(new_state):
                    delivery_repo.update_state(delivery_id, new_state.value)
                    logger.info(f"Updated delivery {delivery_id}: {old_state.value} → {new_state.value}")
                else:
                    path = self._find_state_path(old_state, new_state)
                    if path and len(path) > 1:
                        for state in path[1:]:
                            delivery_repo.update_state(delivery_id, state.value)
                        logger.info(
                            "Updated delivery %s via callback transition path: %s",
                            delivery_id,
                            " -> ".join(state.value for state in path),
                        )
                    else:
                        logger.warning(
                            f"Invalid state transition for delivery {delivery_id}: {old_state.value} → {new_state.value}"
                        )
        except Exception as e:
            logger.error(f"Error updating delivery state: {e}")
    
    async def _create_receipt(
        self,
        delivery_id: int,
        parsed_data: Dict[str, Any],
        raw_callback: Dict[str, Any]
    ) -> Optional[int]:
        """Create receipt record in database."""
        if not self.db:
            return None
        
        try:
            receipt_repo = ReceiptRepository(self.db)
            
            receipt_id = receipt_repo.create(
                delivery_id=delivery_id,
                provider_event=parsed_data.get("state", "unknown"),
                status=parsed_data.get("state", "unknown"),
                raw_data=json.dumps(raw_callback)
            )
            
            logger.info(f"Created receipt {receipt_id} for delivery {delivery_id}")
            return receipt_id
        except Exception as e:
            logger.error(f"Error creating receipt: {e}")
            return None
    
    async def _audit_callback(
        self,
        delivery_id: int,
        channel_type: str,
        parsed_data: Dict[str, Any]
    ):
        """Create audit log entry for callback processing."""
        if not self.db:
            return
        
        try:
            audit_repo = AuditEventRepository(self.db)
            
            audit_repo.create(
                kind="callback_processed",
                actor="system",
                target_type="delivery",
                target_id=delivery_id,
                details_json=json.dumps({
                    "channel_type": channel_type,
                    "status": parsed_data.get("state"),
                    "provider_id": parsed_data.get("provider_id")
                })
            )
        except Exception as e:
            logger.error(f"Error creating audit log: {e}")
