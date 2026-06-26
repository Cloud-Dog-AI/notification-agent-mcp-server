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
Description: State machines for messages and deliveries - defines DeliveryState and MessageStatus enums

Related Requirements: FR1.1, FR1.2
Related Tasks: T5
Related Architecture: CC2.1.2
Related Tests: UT1.3

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from enum import Enum
from cloud_dog_jobs import JobStateMachine
from cloud_dog_jobs.extensions.state_extensions import register_state_extension


_JOB_TYPE = "notification_delivery"
_JOB_STATE_MACHINE = JobStateMachine()
register_state_extension(
    _JOB_TYPE,
    custom_states={
        "queued",
        "deferred",
        "scheduled",
        "dispatched",
        "formatting",
        "sending",
        "sent",
        "accepted",
        "delivered",
        "read",
        "paused",
        "soft_failed",
        "hard_failed",
        "dead_lettered",
        "ttl_expired",
        "cancelled",
        "archived",
    },
    custom_transitions={
        "queued": {"formatting", "sending", "soft_failed", "deferred", "ttl_expired", "cancelled", "scheduled", "dispatched"},
        "deferred": {"queued", "formatting", "soft_failed", "ttl_expired", "cancelled"},
        "scheduled": {"queued", "cancelled"},
        "dispatched": {"sending", "cancelled"},
        "formatting": {"sending", "soft_failed", "deferred", "hard_failed", "ttl_expired", "cancelled"},
        "sending": {"sent", "soft_failed", "hard_failed", "ttl_expired", "cancelled"},
        "sent": {"accepted", "delivered", "soft_failed", "hard_failed"},
        "accepted": {"delivered", "read"},
        "delivered": {"read", "archived"},
        "paused": {"queued", "cancelled"},
        "soft_failed": {"queued", "formatting", "sending", "hard_failed", "ttl_expired", "cancelled"},
        "hard_failed": {"dead_lettered", "archived"},
        "dead_lettered": {"archived"},
        "read": {"archived"},
        "ttl_expired": {"archived"},
        "cancelled": {"archived"},
    },
)


class DeliveryState(str, Enum):
    """Delivery state machine states"""
    QUEUED = "queued"
    DEFERRED = "deferred"
    SCHEDULED = "scheduled"  # Scheduled for future delivery
    DISPATCHED = "dispatched"  # Dispatched to channel adapter
    FORMATTING = "formatting"
    SENDING = "sending"
    SENT = "sent"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    READ = "read"
    PAUSED = "paused"  # Delivery paused by operator
    SOFT_FAILED = "soft_failed"  # Retry-able failure
    HARD_FAILED = "hard_failed"  # Permanent failure
    DEAD_LETTERED = "dead_lettered"  # Exhausted retries, moved to dead-letter queue
    TTL_EXPIRED = "ttl_expired"  # Expired before delivery
    CANCELLED = "cancelled"  # Manually cancelled
    ARCHIVED = "archived"  # Archived for audit retention
    
    def is_terminal(self) -> bool:
        """Check if state is terminal (no further processing)"""
        return _JOB_STATE_MACHINE.is_terminal(self.value, job_type=_JOB_TYPE)
    
    def is_retryable(self) -> bool:
        """Check if state allows retrying"""
        return self in {DeliveryState.SOFT_FAILED, DeliveryState.QUEUED, DeliveryState.DEFERRED}
    
    def can_transition_to(self, target) -> bool:
        """Check if transition to target state is valid"""
        target_state = target.value if isinstance(target, DeliveryState) else str(target)
        return _JOB_STATE_MACHINE.can_transition(self.value, target_state, job_type=_JOB_TYPE)


class MessageStatus(str, Enum):
    """Message status (aggregated from deliveries)"""
    QUEUED = "queued"  # All deliveries queued
    PROCESSING = "processing"  # Some deliveries in progress
    COMPLETED = "completed"  # All deliveries successfully delivered
    PARTIAL = "partial"  # Some failed, some succeeded
    FAILED = "failed"  # All deliveries failed
    TTL_EXPIRED = "ttl_expired"  # Message expired before completion
    CANCELLED = "cancelled"  # Message cancelled
