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
Description: Enhanced Audit Logger - Per-message auditable log with cryptographic signatures

Related Requirements: NF1.7
Covers: CS1.3
Related Tasks: T38
Related Architecture: SE1.3
Related Tests: ST1.12

Recent Changes (max 10):
- 2026-02-24: Migrated audit emission to cloud_dog_logging audit logger with compatibility DB writes
**************************************************
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from cloud_dog_logging import get_audit_logger
from cloud_dog_logging.audit_schema import Actor, Target
from cloud_dog_logging.audit_logger import AuditLogger
from cloud_dog_idam.audit.models import AuditEvent

from ...utils.logger import get_logger
from ...core.idam.runtime import get_idam_runtime
from .signer import AuditSigner
from ...database.repositories import AuditEventRepository

logger = get_logger(__name__)


class EnhancedAuditLogger:
    """Enhanced audit logger with cloud_dog_logging-backed audit emission."""

    def __init__(
        self,
        audit_repo: Optional[AuditEventRepository] = None,
        signer: Optional[AuditSigner] = None,
        audit_logger: Optional[AuditLogger] = None,
        idam_emitter: Any = None,
    ):
        self.audit_repo = audit_repo
        self.signer = signer
        self.audit_logger = audit_logger or get_audit_logger()
        self.idam_emitter = idam_emitter or get_idam_runtime().audit_emitter
        logger.info("EnhancedAuditLogger initialized")

    def log_message_submission(
        self,
        message_id: int,
        actor: str,
        content_preview: str,
        destinations_count: int,
        **kwargs: Any,
    ) -> None:
        audit_data = {
            "kind": "message_submission",
            "actor": actor,
            "ref_type": "message",
            "ref_id": message_id,
            "data_json": {
                "content_preview": content_preview[:100],
                "destinations_count": destinations_count,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_formatted_content(
        self,
        message_id: int,
        delivery_id: int,
        actor: str,
        format_type: str,
        language: str,
        **kwargs: Any,
    ) -> None:
        audit_data = {
            "kind": "formatted_content",
            "actor": actor,
            "ref_type": "delivery",
            "ref_id": delivery_id,
            "data_json": {
                "message_id": message_id,
                "format": format_type,
                "language": language,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_send_attempt(
        self,
        delivery_id: int,
        actor: str,
        channel_type: str,
        success: bool,
        error: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        audit_data = {
            "kind": "send_attempt",
            "actor": actor,
            "ref_type": "delivery",
            "ref_id": delivery_id,
            "data_json": {
                "channel_type": channel_type,
                "success": success,
                "error": error,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_state_transition(
        self,
        entity_type: str,
        entity_id: int,
        actor: str,
        old_state: str,
        new_state: str,
        **kwargs: Any,
    ) -> None:
        audit_data = {
            "kind": "state_transition",
            "actor": actor,
            "ref_type": entity_type,
            "ref_id": entity_id,
            "data_json": {
                "old_state": old_state,
                "new_state": new_state,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_job_dead_letter(
        self,
        delivery_id: int,
        actor: str,
        error: str,
        dead_letter_job_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Audit: delivery exhausted retries, moved to dead-letter queue (PS-75 JQ7.3)."""
        audit_data = {
            "kind": "job.dead_letter",
            "actor": actor,
            "ref_type": "delivery",
            "ref_id": delivery_id,
            "data_json": {
                "error": error[:200],
                "dead_letter_job_id": dead_letter_job_id,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_job_timeout(
        self,
        delivery_id: int,
        actor: str,
        age_seconds: int,
        **kwargs: Any,
    ) -> None:
        """Audit: delivery job timed out or stuck (PS-75 JQ7.1 / JQ9)."""
        audit_data = {
            "kind": "job.timeout",
            "actor": actor,
            "ref_type": "delivery",
            "ref_id": delivery_id,
            "data_json": {
                "age_seconds": age_seconds,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def log_callback(
        self,
        delivery_id: int,
        actor: str,
        channel_type: str,
        state: str,
        **kwargs: Any,
    ) -> None:
        audit_data = {
            "kind": "callback",
            "actor": actor,
            "ref_type": "delivery",
            "ref_id": delivery_id,
            "data_json": {
                "channel_type": channel_type,
                "state": state,
                **kwargs,
            },
        }
        self._create_signed_audit_entry(audit_data)

    def _emit_platform_audit(self, audit_data: Dict[str, Any]) -> None:
        details = audit_data.get("data_json") or {}
        actor = Actor(type="service", id=str(audit_data.get("actor", "system")))
        target = Target(type=str(audit_data.get("ref_type", "event")), id=str(audit_data.get("ref_id", "")))
        outcome = "success"
        if isinstance(details, dict) and details.get("success") is False:
            outcome = "failure"

        self.audit_logger.log_crud(
            actor=actor,
            action=str(audit_data.get("kind", "event")),
            target=target,
            outcome=outcome,
            **({"details": details} if details else {}),
        )
        if self.idam_emitter:
            actor_id_value = str(audit_data.get("actor", "system"))
            actor_type_value = str(audit_data.get("actor_type", "service"))
            idam_details = details if isinstance(details, dict) else {}
            idam_details = {
                **idam_details,
                "actor_type": actor_type_value,
                "target_type": str(audit_data.get("ref_type", "event")),
                "target_id": str(audit_data.get("ref_id", "")),
            }
            self.idam_emitter.emit(
                AuditEvent(
                    actor_id=actor_id_value,
                    action=str(audit_data.get("kind", "event")),
                    target=f"{audit_data.get('ref_type', 'event')}:{audit_data.get('ref_id', '')}",
                    outcome=outcome,
                    details=idam_details,
                )
            )

    def _create_signed_audit_entry(self, audit_data: Dict[str, Any]) -> None:
        try:
            signed_entry = self.signer.sign_audit_entry(audit_data) if self.signer else audit_data.copy()
            self._emit_platform_audit(signed_entry)

            if not self.audit_repo:
                return

            self.audit_repo.create(
                kind=signed_entry["kind"],
                actor=signed_entry["actor"],
                target_type=signed_entry.get("ref_type"),
                target_id=signed_entry.get("ref_id"),
                details_json=json.dumps(
                    {
                        "data": signed_entry.get("data_json", {}),
                        "signature": signed_entry.get("signature"),
                        "signed_at": signed_entry.get("signed_at"),
                    }
                ),
            )
        except Exception as exc:
            logger.error(f"Failed to create audit entry: {exc}")
