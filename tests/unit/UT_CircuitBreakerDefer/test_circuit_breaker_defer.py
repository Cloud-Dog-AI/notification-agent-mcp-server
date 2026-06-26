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

"""Unit coverage for defer-on-breaker-open delivery behavior."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from cloud_dog_jobs.domain.enums import JobStatus

from src.core.delivery_worker import DeliveryWorker
from src.core.llm.llm_availability_manager import LLMAvailabilityManager
from src.core.state_machine import DeliveryState


class _ConfigStub(dict):
    def get(self, key, default=None):  # noqa: A003 - config API contract
        return super().get(key, default)


class _BreakerOpenManager:
    def get_circuit_state(self) -> str:
        return "open"

    def get_connection_status(self) -> str:
        return "breaker_open"

    def is_healthy(self) -> bool:
        return False


class _HalfOpenManager:
    def get_circuit_state(self) -> str:
        return "half_open"

    def get_connection_status(self) -> str:
        return "probing"

    def is_healthy(self) -> bool:
        return True


def _build_worker_for_breaker_open_test() -> tuple[DeliveryWorker, dict[str, str]]:
    worker = DeliveryWorker.__new__(DeliveryWorker)
    worker.config = _ConfigStub(
        {
            "llm.circuit_breaker_recovery_seconds": 7,
            "llm.query_timeout": 1,
            "llm.formatting_timeout": 1,
            "llm.translation_timeout": 1,
            "llm.timeout": 1,
        }
    )
    worker.db = Mock()
    worker.db.fetchone.return_value = None
    worker.db.fetchall.return_value = []
    worker.media_processor = None
    worker.html_page_generator = None
    worker.pdf_helper = None

    delivery_state = {"state": DeliveryState.QUEUED.value}
    delivery_record = {
        "id": 41,
        "message_id": 11,
        "channel_id": 22,
        "destination": "loopback-user",
        "metadata_json": json.dumps({"preferences": {"language": "fr"}}),
    }

    worker.delivery_repo = Mock()

    def _update_state(*args, **kwargs):
        state = kwargs.get("state")
        if state is None and len(args) >= 2:
            state = args[1]
        delivery_state["state"] = str(state)

    worker.delivery_repo.update_state.side_effect = _update_state
    worker.delivery_repo.get_by_id.side_effect = lambda _delivery_id: {
        "id": delivery_record["id"],
        "state": delivery_state["state"],
    }
    worker.delivery_repo.update_metadata = Mock()
    worker.delivery_repo.update_payload = Mock()
    worker.delivery_repo.clear_payload = Mock()
    worker.delivery_repo.set_next_action_at = Mock()

    worker.message_repo = Mock()
    worker.message_repo.get_by_id.return_value = {
        "id": 11,
        "guid": "msg-guid-11",
        "audience_type": "personalised",
        "content_json": json.dumps([{"type": "text", "body": "Hello world"}]),
        "variables_json": json.dumps({}),
    }

    worker.channel_repo = Mock()
    worker.channel_repo.get_by_id.return_value = {
        "id": 22,
        "name": "ut-loopback-breaker",
        "type": "loopback",
        "config_json": json.dumps({"base_url": "http://127.0.0.1:8020"}),
        "restrictions_json": None,
        "limits_json": None,
    }

    worker.adapter_registry = Mock()
    worker.adapter_registry.get_adapter.return_value = object()

    worker.job_manager = Mock()
    worker.job_manager.check_delivery_cancelled.return_value = False
    worker.job_manager.track_delivery_progress = Mock()
    worker.job_manager.heartbeat_delivery = Mock()

    worker.jobs_runtime = Mock()
    worker.jobs_runtime.mark_delivery_status = Mock()
    worker.jobs_runtime._emit_job_audit = Mock()  # noqa: SLF001 - exercised via worker helper

    worker.formatter = Mock()
    worker.formatter.format_message.side_effect = RuntimeError("CircuitBreaker 'llm' is OPEN")
    worker.formatter._translate = Mock(return_value="translated")

    worker.llm_availability = Mock()
    worker.llm_availability.check_availability = AsyncMock(return_value=(True, 0, 0))
    worker.llm_availability.acquire_slot = AsyncMock(return_value="slot-ut-1")
    worker.llm_availability.release_slot = AsyncMock(return_value=None)
    worker.llm_availability.get_connection_status.return_value = "connected"
    worker.llm_availability.llm_manager = _BreakerOpenManager()

    return worker, delivery_record
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_process_delivery_defers_when_breaker_is_open():
    worker, delivery = _build_worker_for_breaker_open_test()

    asyncio.run(worker._process_delivery(delivery, ctx_logger=Mock()))

    update_state_calls = [call.kwargs["state"] for call in worker.delivery_repo.update_state.call_args_list]
    assert update_state_calls[:2] == [DeliveryState.FORMATTING.value, DeliveryState.DEFERRED.value]
    worker.delivery_repo.update_payload.assert_not_called()
    worker.delivery_repo.clear_payload.assert_called_once_with(delivery["id"])

    metadata_payload = worker.delivery_repo.update_metadata.call_args.kwargs["metadata_json"]
    metadata = json.loads(metadata_payload)
    assert metadata["llm_deferred_reason"] == "breaker_open"
    assert metadata["llm_wait_time"] == 7
    assert metadata["llm_retry_count"] == 1
    assert metadata["llm_retry_after"]

    scheduled_at = worker.delivery_repo.set_next_action_at.call_args.args[1]
    assert isinstance(scheduled_at, datetime)
    worker.jobs_runtime.mark_delivery_status.assert_called_once_with(
        delivery["id"],
        JobStatus.RETRY_WAIT.value,
        from_status=DeliveryState.FORMATTING.value,
    )
    worker.job_manager.track_delivery_progress.assert_any_call(
        delivery["id"],
        DeliveryState.DEFERRED.value,
    )


@pytest.mark.parametrize(
    ("manager", "expected_status"),
    [
        (_BreakerOpenManager(), "breaker_open"),
        (_HalfOpenManager(), "probing"),
    ],
)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")
def test_llm_queue_status_surfaces_breaker_state(manager, expected_status):
    availability = LLMAvailabilityManager(
        config=_ConfigStub({"llm.circuit_breaker_recovery_seconds": 7}),
        llm_manager=manager,
    )

    status = asyncio.run(availability.get_queue_status())

    assert status["available"] is False
    assert status["connection_status"] == expected_status
    assert status["estimated_wait_seconds"] >= 1


pytestmark = [
    pytest.mark.unit,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]
