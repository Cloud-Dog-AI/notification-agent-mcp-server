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
Description: JOBS runtime integration backed by cloud_dog_jobs

Related Requirements: FR1.1, FR1.2
Related Tasks: T5
Related Architecture: CC2.1
Related Tests: UT1.3, ST1.2

Recent Changes (max 10):
- 2026-04-05: W28A-659 — Enhanced with dead-letter handling, progress tracking, PS-75 audit events,
  cooperative cancellation, heartbeat, and configurable timeouts.
- 2026-03-03: Added cloud_dog_jobs runtime bridge for queue, state-machine, backoff, and maintenance.

**************************************************
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from cloud_dog_jobs import (
    JobQueue, JobRequest, JobStateMachine, RedisQueueBackend, SQLQueueBackend,
    FallbackAction, FallbackPolicy, FallbackPolicyManager,
)
from cloud_dog_jobs.domain.enums import JobStatus
from cloud_dog_jobs.domain.models import Job
from cloud_dog_jobs.extensions.state_extensions import register_state_extension
from cloud_dog_jobs.maintenance.reaper import MaintenanceReaper
from cloud_dog_jobs.observability.audit import AuditEmitter
from cloud_dog_jobs.scheduler.concurrency import ConcurrencyLimits, ConcurrencyManager
from cloud_dog_jobs.scheduler.policies import exponential_backoff_seconds

from cloud_dog_logging import get_audit_logger
from cloud_dog_logging.audit_schema import Actor, Target

from ...config import get_config
from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

_fs = _PlatformLocalStorage(root_path="/")


_DELIVERY_JOB_TYPE = "notification_delivery"
_SQLITE_SCHEME = "sqlite"
_DEFAULT_WORKER_ID = "delivery-worker"
_TERMINAL_JOB_STATUSES = {
    JobStatus.SUCCEEDED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
    JobStatus.TTL_EXPIRED.value,
    JobStatus.DEAD_LETTERED.value,
}


def _normalise_backend_db_url(db_url: str) -> str:
    """Convert legacy sqlite3 URLs to SQLAlchemy-compatible URLs for jobs storage."""
    if db_url.startswith("sqlite3://"):
        raw_path = db_url.replace("sqlite3://", "", 1)
        if raw_path.startswith("/") and not raw_path.startswith(("/opt", "/home", "/app")):
            raw_path = raw_path.lstrip("/")
        path = Path(raw_path)
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[3]
            path = project_root / path
        _fs.create_dir(str(path.parent), parents=True, exist_ok=True)
        return f"{_SQLITE_SCHEME}:///{path}"
    return db_url


def _job_status_value(status: JobStatus | str | None) -> str:
    """Return a stable string value for job status comparisons."""
    if isinstance(status, JobStatus):
        return status.value
    return str(status or "").strip().lower()


class _PlatformAuditEmitter(AuditEmitter):
    """Bridge cloud_dog_jobs AuditEmitter to cloud_dog_logging audit logger."""

    def __init__(self) -> None:
        super().__init__()
        self._audit_logger = get_audit_logger()

    def emit(self, action: str, outcome: str, *, service: str = "notification-agent") -> dict:
        """Emit a PS-75 job audit event via cloud_dog_logging."""
        event = super().emit(action, outcome, service=service)
        actor = Actor(type="service", id=service)
        target = Target(type="queue", id="notification")
        self._audit_logger.log_crud(
            actor=actor,
            action=action,
            target=target,
            outcome=outcome,
        )
        return event


@dataclass
class JobsRuntime:
    backend: Any
    queue: JobQueue
    state_machine: JobStateMachine
    reaper: MaintenanceReaper
    concurrency: ConcurrencyManager
    fallback_manager: FallbackPolicyManager
    server_id: str
    backend_name: str
    database_url: str
    queue_name: str = "notification"
    run_timeout_ms: int = 900_000
    dead_letter_queue: str = "notification_dead_letter"
    _delivery_to_job: Dict[int, str] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)
    _audit_logger: Any = field(default=None)

    def __post_init__(self) -> None:
        if self._audit_logger is None:
            self._audit_logger = get_audit_logger()

    # ------------------------------------------------------------------
    # Audit helpers (PS-75 JQ15)
    # ------------------------------------------------------------------

    def _emit_job_audit(
        self,
        action: str,
        outcome: str,
        *,
        job_id: str = "",
        delivery_id: int | None = None,
        details: Dict[str, Any] | None = None,
    ) -> None:
        """Emit a PS-75 compliant audit event for a job lifecycle action."""
        actor = Actor(type="service", id=self.server_id)
        target = Target(type="queue", id=str(job_id or "notification"))
        detail_payload = dict(details or {})
        if delivery_id is not None:
            detail_payload["delivery_id"] = delivery_id
        self._audit_logger.log_crud(
            actor=actor,
            action=action,
            target=target,
            outcome=outcome,
            **({"details": detail_payload} if detail_payload else {}),
        )

    # ------------------------------------------------------------------
    # Progress tracking (PS-75 JQ12)
    # ------------------------------------------------------------------

    def update_delivery_progress(
        self,
        delivery_id: int,
        *,
        percentage: float,
        stage: str = "",
        counters: Dict[str, int] | None = None,
    ) -> bool:
        """Update progress tracking for a delivery job."""
        job = self.get_delivery_job(int(delivery_id))
        if job is None:
            return False
        progress = {
            "percentage": round(min(100.0, max(0.0, float(percentage))), 1),
            "stage": stage,
        }
        if counters:
            progress["counters"] = counters
        job.progress = progress
        return True

    # ------------------------------------------------------------------
    # Dead-letter handling (PS-75 JQ7.3)
    # ------------------------------------------------------------------

    def dead_letter_delivery(self, delivery_id: int, *, error: str) -> str | None:
        """Move an exhausted-retry delivery job to the dead-letter queue."""
        job = self.get_delivery_job(int(delivery_id))
        if job is None:
            return None
        decision = self.fallback_manager.apply(self.backend, job, RuntimeError(error))
        self._emit_job_audit(
            "job.dead_letter",
            "success",
            job_id=job.job_id,
            delivery_id=delivery_id,
            details={
                "error": error[:200],
                "dead_letter_job_id": decision.dead_letter_job_id,
                "dead_letter_queue": self.dead_letter_queue,
            },
        )
        return decision.dead_letter_job_id

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue_delivery_job(
        self,
        *,
        delivery_id: int,
        message_id: int,
        channel_id: int,
        destination: str,
        idempotency_key: str | None = None,
        request_source: str | None = None,
        request_ip: str | None = None,
        request_auth_method: str | None = None,
        request_auth_identity: str | None = None,
        request_user_agent: str | None = None,
    ) -> str:
        existing_job = self.get_delivery_job(int(delivery_id))
        if existing_job is not None:
            job_status = _job_status_value(existing_job.status)
            if job_status in _TERMINAL_JOB_STATUSES:
                self.backend.update_status(existing_job.job_id, JobStatus.QUEUED.value)
            return existing_job.job_id

        request = JobRequest(
            job_type=_DELIVERY_JOB_TYPE,
            queue_name=self.queue_name,
            payload={
                "delivery_id": int(delivery_id),
                "message_id": int(message_id),
                "channel_id": int(channel_id),
                "destination": str(destination),
            },
            resources={"llm-pool": 1},
            idempotency_key=idempotency_key,
            correlation_id=f"message:{message_id}",
            channel_id=str(channel_id),
            request_source=request_source,
            request_ip=request_ip,
            request_auth_method=request_auth_method,
            request_auth_identity=request_auth_identity,
            request_user_agent=request_user_agent,
        )
        job_id = self.queue.submit(request)
        with self._lock:
            self._delivery_to_job[int(delivery_id)] = job_id
        self._emit_job_audit(
            "job.submit",
            "success",
            job_id=job_id,
            delivery_id=delivery_id,
            details={"message_id": message_id, "channel_id": channel_id},
        )
        return job_id

    def ensure_delivery_job(
        self,
        *,
        delivery_id: int,
        message_id: int,
        channel_id: int,
        destination: str,
        idempotency_key: str | None = None,
    ) -> Job:
        job_id = self.enqueue_delivery_job(
            delivery_id=delivery_id,
            message_id=message_id,
            channel_id=channel_id,
            destination=destination,
            idempotency_key=idempotency_key,
        )
        job = self.backend.get(job_id)
        if job is None:
            raise RuntimeError(f"Jobs backend lost delivery job {job_id} for delivery {delivery_id}")
        return job

    def get_delivery_job_id(self, delivery_id: int) -> str | None:
        with self._lock:
            cached = self._delivery_to_job.get(int(delivery_id))
        if cached:
            return cached

        for job in self.backend.all_jobs():
            payload = job.payload or {}
            if int(payload.get("delivery_id", -1)) != int(delivery_id):
                continue
            with self._lock:
                self._delivery_to_job[int(delivery_id)] = job.job_id
            return job.job_id
        return None

    def get_delivery_job(self, delivery_id: int) -> Job | None:
        job_id = self.get_delivery_job_id(delivery_id)
        if not job_id:
            return None
        return self.backend.get(job_id)

    def claim_delivery_job(self, delivery_id: int, *, worker_id: str = _DEFAULT_WORKER_ID) -> bool:
        job_id = self.get_delivery_job_id(delivery_id)
        if not job_id:
            return False
        claimed = bool(self.backend.claim(job_id, self.server_id, worker_id))
        if claimed:
            self._emit_job_audit(
                "job.claim",
                "success",
                job_id=job_id,
                delivery_id=delivery_id,
                details={"worker_id": worker_id, "host_id": self.server_id},
            )
        return claimed

    def release_delivery_job(
        self,
        delivery_id: int,
        *,
        status: str = JobStatus.QUEUED.value,
    ) -> bool:
        return self.mark_delivery_status(delivery_id, status)

    def requeue_delivery_job(self, delivery_id: int) -> bool:
        return self.release_delivery_job(delivery_id, status=JobStatus.QUEUED.value)

    def requeue_claimed_running_jobs(self) -> list[int]:
        recovered_delivery_ids: list[int] = []
        prefix = f"{self.server_id}:"
        for job in self.backend.all_jobs():
            if job.job_type != _DELIVERY_JOB_TYPE:
                continue
            if _job_status_value(job.status) != JobStatus.RUNNING.value:
                continue
            claimed_by = str(getattr(job, "claimed_by", "") or "")
            if not claimed_by.startswith(prefix):
                continue
            payload = job.payload or {}
            delivery_id = payload.get("delivery_id")
            if delivery_id is None:
                continue
            if self.backend.update_status(job.job_id, JobStatus.QUEUED.value):
                recovered_delivery_ids.append(int(delivery_id))
        return recovered_delivery_ids

    def queue_status(self) -> dict[str, int]:
        return self.backend.get_queue_status()

    def mark_delivery_status(self, delivery_id: int, status: str, *, from_status: str = "", last_error: str | None = None) -> bool:
        """Update a delivery job's status and emit a transition audit event."""
        job_id = self.get_delivery_job_id(int(delivery_id))
        if not job_id:
            return False
        ok = self.backend.update_status(job_id, status)
        if ok and last_error:
            try:
                self.backend.record_attempt(job_id, error=last_error)
            except Exception:
                pass  # best-effort error propagation
        if ok:
            self._emit_job_audit(
                "job.transition",
                "success",
                job_id=job_id,
                delivery_id=delivery_id,
                details={"from_state": from_status, "to_state": status},
            )
        return ok

    def calculate_retry_delay(self, *, attempt_no: int, base_seconds: float, max_seconds: float) -> float:
        return float(
            exponential_backoff_seconds(
                attempt=max(0, int(attempt_no)),
                base=float(base_seconds),
                maximum=float(max_seconds),
                jitter=True,
            )
        )

    def run_maintenance(self, *, ttl_seconds: int = 86_400, retention_seconds: int = 2_592_000) -> dict[str, int]:
        summary = {"ttl_expired": 0, "stuck_recovered": 0, "retention_purged": 0}
        now_utc = datetime.now(timezone.utc)

        for job in self.backend.all_jobs():
            created_at = getattr(job, "created_at", None)
            if created_at is None:
                continue
            if isinstance(created_at, datetime):
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                else:
                    created_at = created_at.astimezone(timezone.utc)
            job_status = _job_status_value(job.status)

            # Stuck detection: running jobs beyond claim timeout
            if job_status == JobStatus.RUNNING.value:
                updated_at = getattr(job, "updated_at", created_at)
                if isinstance(updated_at, datetime):
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)
                    age_seconds = (now_utc - updated_at).total_seconds()
                    if age_seconds > self.reaper._claim_timeout_seconds:
                        if self.backend.update_status(job.job_id, JobStatus.FAILED.value):
                            summary["stuck_recovered"] += 1
                            delivery_id = (job.payload or {}).get("delivery_id")
                            self._emit_job_audit(
                                "job.admin.stuck_recovery",
                                "success",
                                job_id=job.job_id,
                                delivery_id=int(delivery_id) if delivery_id is not None else None,
                                details={"age_seconds": int(age_seconds)},
                            )
                        continue

            # TTL expiry
            if job_status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
                if (now_utc - created_at).total_seconds() > ttl_seconds:
                    if self.backend.update_status(job.job_id, JobStatus.TTL_EXPIRED.value):
                        summary["ttl_expired"] += 1
                        delivery_id = (job.payload or {}).get("delivery_id")
                        self._emit_job_audit(
                            "job.ttl_expired",
                            "success",
                            job_id=job.job_id,
                            delivery_id=int(delivery_id) if delivery_id is not None else None,
                        )
        return summary

    # ------------------------------------------------------------------
    # Cooperative cancellation (PS-75 JQ8.4)
    # ------------------------------------------------------------------

    def is_delivery_cancelled(self, delivery_id: int) -> bool:
        """Check if a delivery job has been cancelled (cooperative cancellation)."""
        job = self.get_delivery_job(int(delivery_id))
        if job is None:
            return False
        return _job_status_value(job.status) == JobStatus.CANCELLED.value

    # ------------------------------------------------------------------
    # Heartbeat (PS-75 JQ8.1)
    # ------------------------------------------------------------------

    def heartbeat_delivery(self, delivery_id: int) -> bool:
        """Update heartbeat timestamp for a running delivery job."""
        job_id = self.get_delivery_job_id(int(delivery_id))
        if not job_id:
            return False
        return self.backend.heartbeat(job_id)

    def can_dispatch(self, job_type: str, *, scope_id: str = "default", user_id: str = "default") -> bool:
        return self.concurrency.can_acquire(job_type, scope_id, user_id)

    def acquire_dispatch(self, job_type: str, *, scope_id: str = "default", user_id: str = "default") -> bool:
        return self.concurrency.acquire(job_type, scope_id, user_id)

    def release_dispatch(self, job_type: str, *, scope_id: str = "default", user_id: str = "default") -> None:
        self.concurrency.release(job_type, scope_id, user_id)


_RUNTIME: JobsRuntime | None = None


def _build_runtime(*, database_url_override: str | None = None) -> JobsRuntime:
    config = get_config()
    backend_name = str(config.get("queue.backend", "sql") or "sql").strip().lower()
    server_id = str(config.get("app.server_id") or socket.gethostname() or "notification-agent").strip()
    database_url = ""
    if backend_name == "redis":
        redis_url = str(config.get("queue.redis_url") or "").strip()
        if not redis_url:
            raise RuntimeError("Missing required configuration: queue.redis_url")
        redis_prefix = str(config.get("queue.redis_key_prefix") or "cloud_dog_notify_jobs").strip()
        backend = RedisQueueBackend(redis_url=redis_url, key_prefix=redis_prefix)
        database_url = redis_url
    else:
        backend_name = "sql"
        sql_database_url = str(
            database_url_override or config.get("queue.sql_database_url") or config.get("db.uri") or ""
        ).strip()
        if not sql_database_url:
            raise RuntimeError("Missing required configuration: queue.sql_database_url or db.uri")
        database_url = _normalise_backend_db_url(sql_database_url)
        backend = SQLQueueBackend(database_url=database_url)
    # Read timeout/dead-letter configuration from config
    claim_timeout_seconds = int(config.get("queue.claim_timeout_seconds") or 120)
    run_timeout_ms = int(config.get("queue.run_timeout_ms") or 900_000)
    dead_letter_queue_name = str(config.get("queue.dead_letter_queue") or "notification_dead_letter").strip()
    queue_name = str(config.get("queue.name") or "notification").strip()

    audit_emitter = _PlatformAuditEmitter()
    queue = JobQueue(backend, audit_emitter=audit_emitter)
    machine = JobStateMachine()
    register_state_extension(
        _DELIVERY_JOB_TYPE,
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

    # Configure dead-letter fallback policy
    fallback_mgr = FallbackPolicyManager(
        policies={
            _DELIVERY_JOB_TYPE: FallbackPolicy(
                action=FallbackAction.DEAD_LETTER,
                dead_letter_queue=dead_letter_queue_name,
            ),
        },
    )

    return JobsRuntime(
        backend=backend,
        queue=queue,
        state_machine=machine,
        reaper=MaintenanceReaper(backend, claim_timeout_seconds=claim_timeout_seconds),
        concurrency=ConcurrencyManager(ConcurrencyLimits()),
        fallback_manager=fallback_mgr,
        server_id=server_id,
        backend_name=backend_name,
        database_url=database_url,
        queue_name=queue_name,
        run_timeout_ms=run_timeout_ms,
        dead_letter_queue=dead_letter_queue_name,
    )


def get_jobs_runtime(*, force_reload: bool = False, database_url_override: str | None = None) -> JobsRuntime:
    global _RUNTIME
    desired_database_url = (
        _normalise_backend_db_url(database_url_override)
        if database_url_override
        else None
    )
    if force_reload and _RUNTIME is not None:
        try:
            close = getattr(_RUNTIME.backend, "close", None)
            if callable(close):
                close()
        except Exception:
            pass
    if (
        _RUNTIME is not None
        and desired_database_url
        and _RUNTIME.backend_name == "sql"
        and _RUNTIME.database_url != desired_database_url
    ):
        force_reload = True
    if _RUNTIME is None or force_reload:
        _RUNTIME = _build_runtime(database_url_override=database_url_override)
    return _RUNTIME
