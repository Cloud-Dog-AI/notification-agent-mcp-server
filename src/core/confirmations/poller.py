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
Description: Confirmation Poller for Active Status Checking - Polls notification provider APIs for delivery status updates when callbacks are not available or reliable

Related Requirements: FR1.2
Related Tasks: T7
Related Architecture: CC2.1.4
Related Tests: IT1.10

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from src.database.db_manager import DatabaseManager
from src.database.repositories import DeliveryRepository
from src.core.state_machine import DeliveryState
from cloud_dog_jobs.polling.poller import PollPolicy, should_continue_polling
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConfirmationPoller:
    """
    Polls provider APIs for delivery status updates.
    
    Features:
    - Configurable polling intervals
    - Respects terminal states (stops polling when complete)
    - Error handling with backoff
    - Per-delivery tracking to avoid duplicate polls
    """
    
    def __init__(self, db: Optional[DatabaseManager] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize confirmation poller.
        
        Args:
            db: Database manager instance
            config: Configuration dict with:
                - polling_interval_seconds: Time between polls (default: 60)
                - max_poll_age_hours: Stop polling after this many hours (default: 24)
        """
        self.db = db
        self.config = config or {}
        self.polling_interval = self.config.get("polling_interval_seconds", 60)
        self.max_poll_age_hours = self.config.get("max_poll_age_hours", 24)
        self.poll_policy = PollPolicy(
            interval_seconds=int(self.polling_interval),
            max_age_seconds=int(self.max_poll_age_hours * 3600),
        )
        
        # Track last poll time per delivery
        self._last_poll_times: Dict[int, float] = {}
    
    async def poll_status(self, channel_type: str, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Poll provider API for delivery status.
        
        This is a placeholder - actual implementation would call provider APIs:
        - SMTP: No polling available (use bounce processing)
        - SMS: Poll Twilio API, AWS SNS, etc.
        - Chat: Poll webhook delivery status if available
        
        Args:
            channel_type: Type of channel ('email', 'sms', 'chat')
            provider_id: Provider's message/delivery ID
            
        Returns:
            Status dict or None if unavailable
        """
        try:
            logger.debug(f"Polling status for {channel_type}/{provider_id}")
            
            # TODO: Implement actual provider API calls
            # For now, return None to indicate polling not implemented
            
            return None
            
        except Exception as e:
            logger.error(f"Error polling status: {e}")
            return None
    
    async def poll_delivery(self, delivery_id: int) -> Optional[Dict[str, Any]]:
        """
        Poll status for a specific delivery.
        
        Args:
            delivery_id: Delivery ID to poll
            
        Returns:
            Poll result dict or None
        """
        # Check if we should poll this delivery
        if not self.should_poll(delivery_id):
            return None
        
        try:
            if not self.db:
                return None
            
            delivery_repo = DeliveryRepository(self.db)
            delivery = delivery_repo.get_by_id(delivery_id)
            
            if not delivery:
                return None
            
            # Check if delivery is in a terminal state
            state = DeliveryState(delivery["state"])
            if not self.should_poll_state(state):
                logger.debug(f"Delivery {delivery_id} in terminal state {state.value}, skipping poll")
                return None
            
            # Check if delivery is too old
            if self._is_too_old(delivery):
                logger.debug(f"Delivery {delivery_id} too old, skipping poll")
                return None
            
            # Get channel and provider info
            channel_type = delivery.get("channel_type", "unknown")
            provider_id = delivery.get("provider_tracking_id")  # Use provider_tracking_id from deliveries table
            
            if not provider_id:
                return None
            
            # Poll provider
            result = await self.poll_status(channel_type, provider_id)
            
            # Update last poll time
            self._last_poll_times[delivery_id] = asyncio.get_event_loop().time()
            
            # If we got a result, update delivery
            if result:
                await self.update_delivery_from_poll(delivery_id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error polling delivery {delivery_id}: {e}")
            return None
    
    async def update_delivery_from_poll(self, delivery_id: int, poll_result: Dict[str, Any]):
        """
        Update delivery state based on polling result.
        
        Args:
            delivery_id: Delivery ID to update
            poll_result: Result from polling with:
                - status: New status
                - timestamp: Status timestamp
        """
        if not self.db:
            return
        
        try:
            delivery_repo = DeliveryRepository(self.db)
            
            new_status = poll_result.get("status")
            if not new_status:
                return
            
            # Map status to state
            state_map = {
                "queued": DeliveryState.QUEUED.value,
                "sending": DeliveryState.SENDING.value,
                "sent": DeliveryState.SENT.value,
                "delivered": DeliveryState.DELIVERED.value,
                "failed": DeliveryState.HARD_FAILED.value
            }
            
            new_state = state_map.get(new_status.lower())
            if new_state:
                delivery_repo.update_state(delivery_id, new_state)
                logger.info(f"Updated delivery {delivery_id} from polling: {new_state}")
                    
        except Exception as e:
            logger.error(f"Error updating delivery from poll: {e}")
    
    def should_poll(self, delivery_id: int) -> bool:
        """
        Check if delivery should be polled now.
        
        Respects polling interval to avoid hammering provider APIs.
        Also checks if delivery is in a terminal state.
        
        Args:
            delivery_id: Delivery ID
            
        Returns:
            True if enough time has passed since last poll and state is not terminal
        """
        # Check delivery state if database is available
        if self.db:
            try:
                delivery_repo = DeliveryRepository(self.db)
                delivery = delivery_repo.get_by_id(delivery_id)
                if delivery:
                    state = DeliveryState(delivery["state"])
                    if not self.should_poll_state(state):
                        return False
            except Exception as e:
                logger.debug(f"Error checking delivery state: {e}")
        
        # Check polling interval
        last_poll = self._last_poll_times.get(delivery_id)
        if last_poll is None:
            return True
        
        elapsed = asyncio.get_event_loop().time() - last_poll
        return elapsed >= self.polling_interval
    
    def should_poll_state(self, state: DeliveryState) -> bool:
        """
        Check if delivery state should still be polled.
        
        Terminal states don't need polling.
        
        Args:
            state: Delivery state
            
        Returns:
            True if state is not terminal
        """
        terminal_states = [
            DeliveryState.DELIVERED,
            DeliveryState.READ,
            DeliveryState.HARD_FAILED,
            DeliveryState.TTL_EXPIRED,
            DeliveryState.CANCELLED
        ]
        return state not in terminal_states
    
    def _is_too_old(self, delivery: Dict[str, Any]) -> bool:
        """
        Check if delivery is too old to continue polling.
        
        Args:
            delivery: Delivery record
            
        Returns:
            True if delivery is older than max_poll_age_hours
        """
        try:
            created_at = delivery.get("created_at")
            if not created_at:
                return False
            
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age = datetime.now() - created_time.replace(tzinfo=None)
            
            return not should_continue_polling(int(age.total_seconds()), self.poll_policy)
            
        except Exception as e:
            logger.error(f"Error checking delivery age: {e}")
            return False
    
    async def poll_all_pending(self):
        """
        Poll all deliveries that are pending confirmation.
        
        Background task to poll all deliveries in non-terminal states.
        """
        if not self.db:
            logger.warning("No database configured for polling")
            return
        
        try:
            delivery_repo = DeliveryRepository(self.db)
            
            # Get pending deliveries (sent but not confirmed)
            pending_deliveries = delivery_repo.list(
                state=DeliveryState.SENT.value,
                limit=1000
            )
            
            logger.info(f"Polling {len(pending_deliveries)} pending deliveries")
            
            for delivery in pending_deliveries:
                await self.poll_delivery(delivery["id"])
                # Small delay between polls to avoid rate limits
                await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Error in poll_all_pending: {e}")
