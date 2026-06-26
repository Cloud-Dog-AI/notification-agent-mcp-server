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
Description: LLM Availability Manager - Tracks LLM connection status and manages concurrent request limits, enforces max_concurrent limit, estimates wait time, provides slot acquisition/release

Related Requirements: NF1.1, NF1.3
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: ST1.2

Recent Changes (max 10):
- W28A-984a: asyncio.Lock replaces threading.RLock; check_connection uses is_healthy()

**************************************************
"""

import asyncio
import time
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

from ...config import get_config
from ...utils.logger import get_logger

logger = get_logger(__name__)


class LLMAvailabilityManager:
    """Manages LLM availability and concurrent request limits"""

    def __init__(self, config=None, llm_manager=None):
        """
        Initialize LLM availability manager

        Args:
            config: RuntimeConfig instance (optional)
            llm_manager: LLMManager instance (optional, for connection status)
        """
        self.config = config or get_config()
        self.llm_manager = llm_manager

        # Async-safe tracking (W28A-984a Fix 3)
        self._lock = asyncio.Lock()
        self._active_requests = 0
        self._active_slots: Dict[str, datetime] = {}  # slot_id -> acquired_at
        self._queue_length = 0

        # Configuration
        self.max_concurrent = int(self.config.get('llm.max_concurrent', 3))
        self.avg_request_duration = float(self.config.get('llm.avg_request_duration', 60.0))  # seconds
        self.queue_check_interval = int(self.config.get('llm.queue_check_interval', 5))  # seconds

        # Connection status (W28A-984a Fix 2)
        self._connection_status: Optional[bool] = None
        self._connection_status_label: str = "connected"
        self._last_connection_check: Optional[datetime] = None

        logger.info(f"LLM Availability Manager initialized: max_concurrent={self.max_concurrent}")

    def _connection_snapshot(self) -> Tuple[bool, str]:
        """
        Return connection availability plus a stable status label.

        Breaker state is read on every call so OPEN/HALF_OPEN becomes visible
        immediately on `/llm/status`. Closed-state health is lightly cached.
        """
        if self.llm_manager is None:
            return True, "connected"

        now = datetime.now()
        try:
            if hasattr(self.llm_manager, "get_connection_status"):
                status_label = str(self.llm_manager.get_connection_status() or "").strip().lower()
                if status_label == "breaker_open":
                    self._connection_status = False
                    self._connection_status_label = "breaker_open"
                    self._last_connection_check = now
                    return False, "breaker_open"
                if status_label == "probing":
                    # HALF_OPEN still permits the shared breaker to probe recovery,
                    # but monitoring must present the runtime as unavailable.
                    self._connection_status = True
                    self._connection_status_label = "probing"
                    self._last_connection_check = now
                    return True, "probing"
        except Exception as e:
            logger.warning(f"LLM breaker status check failed: {e}")

        if self._last_connection_check and (now - self._last_connection_check).total_seconds() < 5:
            return (
                self._connection_status if self._connection_status is not None else True,
                self._connection_status_label,
            )

        try:
            if hasattr(self.llm_manager, 'is_healthy'):
                self._connection_status = bool(self.llm_manager.is_healthy())
            elif hasattr(self.llm_manager, 'llm') and self.llm_manager.llm is not None:
                self._connection_status = True
            else:
                self._connection_status = False

            self._connection_status_label = "connected" if self._connection_status else "disconnected"
            self._last_connection_check = now
            return self._connection_status, self._connection_status_label
        except Exception as e:
            logger.warning(f"LLM connection check failed: {e}")
            self._connection_status = False
            self._connection_status_label = "disconnected"
            self._last_connection_check = now
            return False, "disconnected"

    def check_connection(self, *, allow_probe: bool = False) -> bool:
        """
        Check if the worker may attempt an LLM request.

        HALF_OPEN still returns True here so the shared circuit breaker can run
        probe calls and recover without manual intervention.
        """
        connection_available, status_label = self._connection_snapshot()
        if allow_probe and status_label == "breaker_open":
            return True
        return connection_available

    def get_connection_status(self) -> str:
        """Return the current LLM connection status label."""
        _, status_label = self._connection_snapshot()
        return status_label

    def _check_availability_unlocked(self, *, allow_probe: bool = False) -> Tuple[bool, int, int]:
        """
        Internal availability check — caller must hold the lock.

        Returns:
            Tuple of (available, wait_time_seconds, queue_length)
        """
        if not self.check_connection(allow_probe=allow_probe):
            wait_time = self.queue_check_interval * 2
            return False, wait_time, self._queue_length

        if self._active_requests >= self.max_concurrent:
            estimated_active_time = self.avg_request_duration
            estimated_queue_time = (self._queue_length * self.avg_request_duration) / self.max_concurrent
            wait_time = int(estimated_active_time + estimated_queue_time)
            return False, wait_time, self._queue_length

        return True, 0, self._queue_length

    async def check_availability(self, *, allow_probe: bool = False) -> Tuple[bool, int, int]:
        """
        Check if LLM can accept a new request

        Returns:
            Tuple of (available: bool, wait_time_seconds: int, queue_length: int)
        """
        async with self._lock:
            return self._check_availability_unlocked(allow_probe=allow_probe)

    async def acquire_slot(self, *, allow_probe: bool = False) -> Optional[str]:
        """
        Acquire a slot for an LLM request

        Returns:
            slot_id (str) if slot acquired, None if no slots available
        """
        async with self._lock:
            available, _, _ = self._check_availability_unlocked(allow_probe=allow_probe)
            if not available:
                return None

            slot_id = f"slot_{int(time.time() * 1000)}_{id(self)}"
            self._active_requests += 1
            self._active_slots[slot_id] = datetime.now()

            logger.debug(f"LLM slot acquired: {slot_id} (active: {self._active_requests}/{self.max_concurrent})")
            return slot_id

    async def release_slot(self, slot_id: str):
        """
        Release a slot after LLM request completes

        Args:
            slot_id: Slot ID returned by acquire_slot()
        """
        async with self._lock:
            if slot_id in self._active_slots:
                duration = (datetime.now() - self._active_slots[slot_id]).total_seconds()
                del self._active_slots[slot_id]
                self._active_requests = max(0, self._active_requests - 1)

                if duration > 0:
                    self.avg_request_duration = (self.avg_request_duration * 0.9) + (duration * 0.1)

                logger.debug(f"LLM slot released: {slot_id} (duration: {duration:.1f}s, active: {self._active_requests}/{self.max_concurrent})")
            else:
                logger.warning(f"Attempted to release unknown slot: {slot_id}")

    async def update_queue_length(self, length: int):
        """
        Update the queue length (called by delivery worker)

        Args:
            length: Current number of queued deliveries waiting for LLM
        """
        async with self._lock:
            self._queue_length = max(0, length)

    async def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status

        Returns:
            Dictionary with queue status information
        """
        async with self._lock:
            available, wait_time, queue_len = self._check_availability_unlocked()
            connection_status = self.get_connection_status()
            status_available = available and connection_status == "connected"
            if connection_status == "breaker_open":
                wait_time = max(
                    wait_time,
                    int(self.config.get("llm.circuit_breaker_recovery_seconds", 60) or 60),
                )
            elif connection_status == "probing":
                wait_time = max(wait_time, self.queue_check_interval)

            return {
                "available": status_available,
                "active_requests": self._active_requests,
                "max_concurrent": self.max_concurrent,
                "queue_length": queue_len,
                "estimated_wait_seconds": wait_time if not status_available else 0,
                "connection_status": connection_status,
                "avg_request_duration": self.avg_request_duration,
            }

    async def get_active_slots(self) -> Dict[str, datetime]:
        """
        Get currently active slots (for debugging)

        Returns:
            Dictionary of slot_id -> acquired_at timestamp
        """
        async with self._lock:
            return self._active_slots.copy()
