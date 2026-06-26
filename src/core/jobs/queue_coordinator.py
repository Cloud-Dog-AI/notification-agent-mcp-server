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
Description: Notification queue coordinator backed by cloud_dog_jobs

Related Requirements: FR1.1, FR1.2, NF1.1
Related Tasks: T5
Related Architecture: CC2.1.2, CC2.1.3
Related Tests: UT1.3, IT1.7, IT1.8

Recent Changes (max 10):
- 2026-05-08: W28A-93.09 - Moved notification-specific queue coordination under core.jobs.
- (Initial header added)

**************************************************
"""

import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from cloud_dog_jobs.domain.enums import JobStatus
from ...database.db_manager import DatabaseManager
from ...database.repositories import MessageRepository, DeliveryRepository, UserRepository
from ...utils.logger import get_logger, get_context_logger
from ..state_machine import DeliveryState, MessageStatus
from .runtime import get_jobs_runtime


logger = get_logger(__name__)


_DELIVERY_PROGRESS_MAP = {
    DeliveryState.QUEUED.value: (0.0, "queued"),
    DeliveryState.DEFERRED.value: (0.0, "deferred"),
    DeliveryState.FORMATTING.value: (25.0, "formatting"),
    DeliveryState.SENDING.value: (50.0, "sending"),
    DeliveryState.SENT.value: (75.0, "sent"),
    DeliveryState.ACCEPTED.value: (85.0, "accepted"),
    DeliveryState.DELIVERED.value: (95.0, "delivered"),
    DeliveryState.READ.value: (100.0, "read"),
    DeliveryState.SOFT_FAILED.value: (0.0, "soft_failed"),
    DeliveryState.HARD_FAILED.value: (0.0, "hard_failed"),
    DeliveryState.DEAD_LETTERED.value: (0.0, "dead_lettered"),
    DeliveryState.TTL_EXPIRED.value: (0.0, "ttl_expired"),
    DeliveryState.CANCELLED.value: (0.0, "cancelled"),
}


class QueueCoordinator:
    """Queue orchestration backed by cloud_dog_jobs primitives."""

    def __init__(
        self,
        db: DatabaseManager,
        default_ttl_hours: int = 24,
        max_retries: int = 5,
        backoff_base_seconds: int = 2,
        backoff_max_seconds: int = 3600,
    ):
        """Initialize job manager

        Args:
            db: Database manager instance
            default_ttl_hours: Default TTL in hours
            max_retries: Maximum retry attempts
            backoff_base_seconds: Base for exponential backoff
            backoff_max_seconds: Maximum backoff time
        """
        self.db = db
        self.message_repo = MessageRepository(db)
        self.delivery_repo = DeliveryRepository(db)
        self.default_ttl_hours = default_ttl_hours
        self.max_retries = max_retries
        self.backoff_base = backoff_base_seconds
        self.backoff_max = backoff_max_seconds
        self.jobs_runtime = get_jobs_runtime(database_url_override=getattr(db, "db_uri", None))

    def track_delivery_progress(self, delivery_id: int, state: str) -> None:
        """Update job progress tracking based on delivery state (PS-75 JQ12)."""
        pct, stage = _DELIVERY_PROGRESS_MAP.get(state, (0.0, state))
        self.jobs_runtime.update_delivery_progress(
            delivery_id, percentage=pct, stage=stage,
        )

    def check_delivery_cancelled(self, delivery_id: int) -> bool:
        """Check if a delivery has been cancelled (cooperative cancellation, PS-75 JQ8.4)."""
        return self.jobs_runtime.is_delivery_cancelled(int(delivery_id))

    def heartbeat_delivery(self, delivery_id: int) -> bool:
        """Update heartbeat for a running delivery job (PS-75 JQ8.1)."""
        return self.jobs_runtime.heartbeat_delivery(int(delivery_id))

    def _delivery_ready_for_dispatch(self, delivery: Dict[str, Any]) -> bool:
        """Check DB and metadata retry guards before claiming a delivery job."""
        next_action_at = delivery.get("next_action_at")
        if next_action_at:
            try:
                retry_at = (
                    next_action_at
                    if isinstance(next_action_at, datetime)
                    else datetime.fromisoformat(str(next_action_at).replace("Z", "+00:00"))
                )
                now = datetime.now(retry_at.tzinfo) if retry_at.tzinfo else datetime.now()
                if retry_at > now:
                    return False
            except Exception:
                pass

        metadata_json = delivery.get("metadata_json")
        if not metadata_json:
            return True

        try:
            metadata = metadata_json if isinstance(metadata_json, dict) else json.loads(metadata_json)
        except Exception:
            return True

        llm_retry_after = metadata.get("llm_retry_after")
        if not llm_retry_after:
            return True
        try:
            retry_at = datetime.fromisoformat(str(llm_retry_after).replace("Z", "+00:00"))
            now = datetime.now(retry_at.tzinfo) if retry_at.tzinfo else datetime.now()
            return retry_at <= now
        except Exception:
            return True

    def enqueue_message(
        self,
        created_by: str,
        content: List[Dict[str, Any]],
        destinations: List[Dict[str, Any]],
        audience_type: str = "personalised",
        template_ref: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        ttl_hours: Optional[int] = None,
        request_source: Optional[str] = None,
        request_ip: Optional[str] = None,
        request_auth_method: Optional[str] = None,
        request_auth_identity: Optional[str] = None,
        request_user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enqueue a new message

        Args:
            created_by: User or API key identifier
            content: List of content blocks
            destinations: List of destination specifications
            audience_type: 'personalised' or 'broadcast'
            template_ref: Template reference
            variables: Template variables
            idempotency_key: Idempotency key for deduplication
            ttl_hours: Time-to-live in hours

        Returns:
            Dictionary with message_id, status, and delivery_count
        """

        # Check idempotency key
        if idempotency_key:
            existing = self.message_repo.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Duplicate message with idempotency_key: {idempotency_key}")
                return {
                    "message_id": existing["id"],
                    "status": "duplicate",
                    "delivery_count": 0,
                }

        # Calculate TTL
        ttl_at = None
        if ttl_hours is not None or self.default_ttl_hours:
            hours = ttl_hours if ttl_hours is not None else self.default_ttl_hours
            ttl_at = datetime.now(timezone.utc) + timedelta(hours=hours)

        # Create message
        message_id = self.message_repo.create(
            created_by=created_by,
            audience_type=audience_type,
            content_json=json.dumps(content),
            template_ref=template_ref,
            variables_json=json.dumps(variables) if variables else None,
            ttl_at=ttl_at,
            idempotency_key=idempotency_key,
            status=MessageStatus.QUEUED.value,
        )

        # Get the full message record to retrieve GUID
        message = self.message_repo.get_by_id(message_id)
        message_guid = message.get("guid") if message else None

        ctx_logger = get_context_logger(logger.name, message_id=message_id)
        ctx_logger.info(f"Created message with {len(destinations)} destinations", destination_count=len(destinations))

        # Create deliveries for each destination
        delivery_count = 0
        user_repo = UserRepository(self.db)
        for dest in destinations:
            channel_id = dest.get("channel_id")
            destination = dest.get("destination")

            if not channel_id:
                logger.warning(f"Invalid destination specification: {dest}")
                continue

            # For channel-based channels (e.g., Slack), destination might be None
            # The webhook URL will be taken from channel config
            if not destination:
                # Check if channel is channel-based
                from ...database.repositories import ChannelRepository
                channel_repo = ChannelRepository(self.db)
                channel = channel_repo.get_by_id(channel_id)
                if channel:
                    channel_config = json.loads(channel.get('config_json', '{}')) if channel.get('config_json') else {}
                    if channel_config.get('is_channel_based'):
                        # Use channel name as destination placeholder
                        destination = channel.get('name', 'channel')
                        logger.info(f"Channel-based delivery: using channel name as destination: {destination}")
                    else:
                        logger.warning(f"Destination required for non-channel-based channel: {channel.get('name')}")
                        continue
                else:
                    logger.warning(f"Channel {channel_id} not found")
                    continue

            # Build delivery metadata for downstream per-destination formatting.
            metadata_payload: Dict[str, Any] = {}
            preferences = dest.get("preferences")
            if preferences:
                metadata_payload["preferences"] = preferences

            user_email = dest.get("user_email")
            if user_email:
                metadata_payload["user_email"] = user_email
                try:
                    user = user_repo.get_by_email(user_email)
                except Exception:
                    user = None
                if user:
                    metadata_payload["user_id"] = user.get("id")
                    if "preferences" not in metadata_payload:
                        inferred_preferences: Dict[str, Any] = {}
                        if user.get("language"):
                            inferred_preferences["language"] = user.get("language")
                        if user.get("content_style"):
                            inferred_preferences["content_style"] = user.get("content_style")
                        if inferred_preferences:
                            metadata_payload["preferences"] = inferred_preferences

            metadata_json = json.dumps(metadata_payload or {})

            delivery_id = self.delivery_repo.create(
                message_id=message_id,
                channel_id=channel_id,
                destination=destination,
                state=DeliveryState.QUEUED.value,
                metadata_json=metadata_json,
            )
            self.jobs_runtime.enqueue_delivery_job(
                delivery_id=int(delivery_id),
                message_id=int(message_id),
                channel_id=int(channel_id),
                destination=str(destination),
                idempotency_key=f"{idempotency_key}:{delivery_id}" if idempotency_key else None,
                request_source=request_source,
                request_ip=request_ip,
                request_auth_method=request_auth_method,
                request_auth_identity=request_auth_identity,
                request_user_agent=request_user_agent,
            )
            delivery_count += 1

        logger.info(f"Created {delivery_count} deliveries for message {message_id}")

        return {
            "message_id": message_id,
            "guid": message_guid,
            "status": "queued",
            "delivery_count": delivery_count,
        }

    def get_pending_deliveries(self, limit: int = 10) -> List[Dict]:
        """Get deliveries ready for processing

        Args:
            limit: Maximum number of deliveries to fetch

        Returns:
            List of delivery records
        """
        pending = self.delivery_repo.get_pending(limit=max(limit * 4, limit))
        claimed_deliveries: List[Dict] = []

        for delivery in pending:
            delivery_id = int(delivery["id"])
            message_id = int(delivery["message_id"])
            channel_id = int(delivery["channel_id"])
            destination = str(delivery.get("destination") or "")
            job = self.jobs_runtime.ensure_delivery_job(
                delivery_id=delivery_id,
                message_id=message_id,
                channel_id=channel_id,
                destination=destination,
            )
            job_status = getattr(job.status, "value", str(job.status)).lower()

            if not self._delivery_ready_for_dispatch(delivery):
                if job_status != JobStatus.RETRY_WAIT.value:
                    self.jobs_runtime.mark_delivery_status(delivery_id, JobStatus.RETRY_WAIT.value)
                continue

            if job_status in {
                JobStatus.SUCCEEDED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
                JobStatus.TTL_EXPIRED.value,
            }:
                self.jobs_runtime.mark_delivery_status(delivery_id, JobStatus.QUEUED.value)
            elif job_status == JobStatus.RETRY_WAIT.value:
                self.jobs_runtime.mark_delivery_status(delivery_id, JobStatus.QUEUED.value)
            elif job_status == JobStatus.RUNNING.value:
                continue

            if not self.jobs_runtime.claim_delivery_job(delivery_id):
                continue

            claimed_deliveries.append(delivery)
            if len(claimed_deliveries) >= limit:
                break

        return claimed_deliveries

    def handle_delivery_failure(
        self,
        delivery_id: int,
        error: str,
        is_transient: bool = True,
    ):
        """Handle delivery failure with retry logic

        Args:
            delivery_id: Delivery ID
            error: Error message
            is_transient: Whether error is transient (retryable)
        """
        delivery = self.delivery_repo.get_by_id(delivery_id)
        if not delivery:
            logger.error(f"Delivery {delivery_id} not found")
            return

        attempt_no = delivery["attempt_no"]

        # Check if we should retry
        if is_transient and attempt_no < self.max_retries:
            # Calculate next retry time with exponential backoff + jitter
            delay_seconds = self.jobs_runtime.calculate_retry_delay(
                attempt_no=attempt_no,
                base_seconds=float(self.backoff_base),
                max_seconds=float(self.backoff_max),
            )
            next_action_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)

            # Update to soft_failed state
            self.delivery_repo.update_state(
                delivery_id=delivery_id,
                state=DeliveryState.SOFT_FAILED.value,
                last_error=error,
            )
            self.delivery_repo.increment_attempt(
                delivery_id=delivery_id,
                next_action_at=next_action_at,
            )
            self.jobs_runtime.mark_delivery_status(
                delivery_id, JobStatus.RETRY_WAIT.value,
                from_status=DeliveryState.SOFT_FAILED.value,
                last_error=error,
            )
            self.track_delivery_progress(delivery_id, DeliveryState.SOFT_FAILED.value)

            logger.info(
                f"Delivery {delivery_id} soft failed (attempt {attempt_no + 1}/{self.max_retries}), "
                f"retry in {delay_seconds:.1f}s"
            )
        else:
            # Permanent failure or max retries reached
            self.delivery_repo.update_state(
                delivery_id=delivery_id,
                state=DeliveryState.HARD_FAILED.value,
                last_error=error,
            )
            self.jobs_runtime.mark_delivery_status(
                delivery_id, JobStatus.FAILED.value,
                from_status=DeliveryState.SOFT_FAILED.value if is_transient else "",
                last_error=error,
            )

            logger.warning(
                f"Delivery {delivery_id} hard failed after {attempt_no} attempts: {error}"
            )

            # Dead-letter handling: move exhausted-retry jobs to dead-letter queue
            if is_transient and attempt_no >= self.max_retries:
                dl_job_id = self.jobs_runtime.dead_letter_delivery(
                    delivery_id, error=error,
                )
                if dl_job_id:
                    logger.info(
                        f"Delivery {delivery_id} moved to dead-letter queue, "
                        f"dead-letter job: {dl_job_id}"
                    )

            # Update message status
            self._update_message_status(delivery["message_id"])

    def mark_delivery_sent(
        self,
        delivery_id: int,
        provider_tracking_id: Optional[str] = None,
    ):
        """Mark delivery as sent

        Args:
            delivery_id: Delivery ID
            provider_tracking_id: External tracking ID from provider
        """
        self.delivery_repo.update_state(
            delivery_id=delivery_id,
            state=DeliveryState.SENT.value,
            provider_tracking_id=provider_tracking_id,
            last_error="",
        )
        self.jobs_runtime.mark_delivery_status(
            delivery_id, JobStatus.SUCCEEDED.value,
            from_status=DeliveryState.SENDING.value,
        )
        self.track_delivery_progress(delivery_id, DeliveryState.SENT.value)

        logger.info(f"Delivery {delivery_id} marked as sent")

    def handle_ttl_expiry(self) -> int:
        """Check for and handle expired messages

        Returns:
            Number of messages expired
        """
        expired = self.message_repo.get_expired()
        count = 0
        self.jobs_runtime.run_maintenance()

        for message in expired:
            message_id = message["id"]

            # Update message status
            self.message_repo.update_status(
                message_id=message_id,
                status=MessageStatus.TTL_EXPIRED.value,
            )

            # Update all pending deliveries
            deliveries = self.delivery_repo.get_by_message_id(message_id)
            for delivery in deliveries:
                if delivery["state"] in [
                    DeliveryState.QUEUED.value,
                    DeliveryState.SOFT_FAILED.value,
                    DeliveryState.DEFERRED.value,
                ]:
                    self.delivery_repo.update_state(
                        delivery_id=delivery["id"],
                        state=DeliveryState.TTL_EXPIRED.value,
                        last_error="Message TTL expired",
                    )

            count += 1
            logger.info(f"Message {message_id} expired due to TTL")

        return count

    def _update_message_status(self, message_id: int):
        """Update message status based on delivery states

        Args:
            message_id: Message ID
        """
        state_counts = self.delivery_repo.count_by_state(message_id)
        total = sum(state_counts.values())

        if total == 0:
            return

        # Determine message status
        if state_counts.get(DeliveryState.TTL_EXPIRED.value, 0) == total:
            status = MessageStatus.TTL_EXPIRED
        elif state_counts.get(DeliveryState.CANCELLED.value, 0) == total:
            status = MessageStatus.CANCELLED
        elif state_counts.get(DeliveryState.HARD_FAILED.value, 0) == total:
            status = MessageStatus.FAILED
        elif (state_counts.get(DeliveryState.DELIVERED.value, 0) +
              state_counts.get(DeliveryState.READ.value, 0) +
              state_counts.get(DeliveryState.SENT.value, 0) +
              state_counts.get(DeliveryState.ACCEPTED.value, 0)) == total:
            status = MessageStatus.COMPLETED
        elif state_counts.get(DeliveryState.HARD_FAILED.value, 0) > 0:
            status = MessageStatus.PARTIAL
        else:
            status = MessageStatus.PROCESSING

        self.message_repo.update_status(message_id, status.value)

    def cancel_message(self, message_id: int) -> int:
        """Cancel a message and all pending deliveries

        Args:
            message_id: Message ID

        Returns:
            Number of deliveries cancelled
        """
        deliveries = self.delivery_repo.get_by_message_id(message_id)
        cancelled_count = 0
        cancellable_states = {
            DeliveryState.QUEUED.value,
            DeliveryState.DEFERRED.value,
            DeliveryState.SOFT_FAILED.value,
            DeliveryState.FORMATTING.value,
            DeliveryState.SENDING.value,
        }

        for delivery in deliveries:
            if delivery["state"] in cancellable_states:
                self.delivery_repo.update_state(
                    delivery_id=delivery["id"],
                    state=DeliveryState.CANCELLED.value,
                    last_error="Cancelled by user",
                )
                self.jobs_runtime.mark_delivery_status(
                    int(delivery["id"]), JobStatus.CANCELLED.value,
                    from_status=delivery["state"],
                )
                self.track_delivery_progress(int(delivery["id"]), DeliveryState.CANCELLED.value)
                cancelled_count += 1

        if cancelled_count > 0:
            self.message_repo.update_status(message_id, MessageStatus.CANCELLED.value)
            logger.info(f"Cancelled message {message_id} ({cancelled_count} deliveries)")
        else:
            # Keep message status accurate when cancellation races with in-flight delivery updates.
            self._update_message_status(message_id)

        return cancelled_count


JobManager = QueueCoordinator
