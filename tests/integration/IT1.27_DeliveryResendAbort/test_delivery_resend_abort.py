# @pytest.mark.req("UC-007")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
IT1.27: Delivery resend/abort API coverage.

Validates:
- POST /deliveries/{id}/abort
- POST /deliveries/{id}/resend
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.api_tracking import build_tracked_client
from tests.utils.test_helpers import check_test_dependencies
from tests.conftest import process_deliveries
from src.database.db_manager import DatabaseManager
from src.core.job_manager import JobManager
from src.config import get_config


TERMINAL_STATES = {"sent", "delivered", "read", "hard_failed", "cancelled", "ttl_expired"}


def _is_external_runtime_mode() -> bool:
    return str(os.environ.get("TEST_USE_EXTERNAL_RUNTIME", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _resolve_host_db_uri(db_uri: str) -> str:
    if not db_uri:
        return db_uri
    if db_uri.startswith("sqlite3:///app/"):
        rel_path = db_uri.replace("sqlite3:///app/", "", 1)
        host_path = (project_root / rel_path).resolve()
        return f"sqlite3:///{host_path}"
    return db_uri


def _open_test_db() -> DatabaseManager:
    config = get_config()
    db_uri = str(config.get("db.uri") or "")
    db = DatabaseManager(_resolve_host_db_uri(db_uri))
    db.connect()
    return db


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=30.0,
        registry=api_cleanup_registry,
    ) as client:
        yield client


def _create_message(api_client, channel_name: str, destination: str, body: str) -> int:
    payload = {
        "audience_type": "personalised",
        "destinations": [
            {
                "channel": channel_name,
                "address": destination,
                "preferences": {"language": "fr", "content_style": "html"},
            }
        ],
        "content": [{"type": "text", "body": body}],
        "options": {"subject": "IT1.27 Delivery Resend/Abort"},
    }
    response = api_client.post("/messages", json=payload)
    assert response.status_code == 201, f"Message creation failed: {response.status_code} {response.text[:200]}"
    message_id = response.json().get("message_id")
    assert isinstance(message_id, int), f"Missing message_id in response: {response.text[:200]}"
    return message_id


def _wait_for_delivery(api_client, message_id: int, timeout_seconds: float = 20.0) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload = {}
    while time.time() < deadline:
        response = api_client.get(f"/messages/{message_id}/deliveries")
        assert response.status_code == 200, f"Failed to get deliveries: {response.status_code} {response.text[:200]}"
        payload = response.json()
        last_payload = payload
        items = payload.get("items") or []
        if items:
            return items[0]
        time.sleep(0.5)
    pytest.fail(f"No delivery created for message {message_id} within {timeout_seconds}s. Last payload: {last_payload}")


def _create_non_terminal_delivery(api_client, channel_name: str, destination: str, body: str) -> tuple[int, int, str]:
    # Delivery state can race quickly to terminal. Try a few times to get one
    # that is still queued/formatting/sending for abort semantics.
    for _ in range(4):
        message_id = _create_message(api_client, channel_name, destination, body)
        delivery = _wait_for_delivery(api_client, message_id, timeout_seconds=30.0)
        delivery_id = int(delivery["id"])
        state = str(delivery.get("state") or "")
        if state and state not in TERMINAL_STATES:
            return message_id, delivery_id, state
        time.sleep(1.0)
    pytest.fail("Could not create a non-terminal delivery for abort test after 4 attempts")


def _wait_for_state_change_from(api_client, delivery_id: int, previous_state: str, timeout_seconds: float = 120.0) -> str:
    deadline = time.time() + timeout_seconds
    last_state = previous_state
    db = None
    job_manager = None
    if not _is_external_runtime_mode():
        db = _open_test_db()
        job_manager = JobManager(db)
    while time.time() < deadline:
        if db is not None and job_manager is not None:
            message_id = None
            try:
                delivery_resp = api_client.get(f"/deliveries/{delivery_id}")
                if delivery_resp.status_code == 200:
                    message_id = delivery_resp.json().get("message_id")
            except Exception:
                message_id = None
            if message_id is not None:
                import asyncio
                asyncio.run(
                    process_deliveries(
                        db,
                        job_manager,
                        message_id=int(message_id),
                        max_cycles=10,
                        timeout=5.0,
                    )
                )
        response = api_client.get(f"/deliveries/{delivery_id}")
        assert response.status_code == 200, f"GET /deliveries/{delivery_id} failed: {response.status_code} {response.text[:200]}"
        payload = response.json()
        state = str(payload.get("state") or "")
        last_state = state
        if state and state != previous_state:
            if db is not None:
                db.disconnect()
            return state
        time.sleep(1.0)
    if db is not None:
        db.disconnect()
    pytest.fail(
        f"Delivery {delivery_id} did not transition from '{previous_state}' within {timeout_seconds}s "
        f"(last_state='{last_state}')"
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_abort_delivery_cancels_in_progress(api_client, default_channel, test_email):
    body = "Please summarise in French. " + ("A" * 2500)
    _, delivery_id, initial_state = _create_non_terminal_delivery(api_client, default_channel, test_email, body)

    response = api_client.post(f"/deliveries/{delivery_id}/abort")
    assert response.status_code == 200, f"Abort failed: {response.status_code} {response.text[:200]}"
    payload = response.json()
    assert payload.get("delivery_id") == delivery_id
    assert payload.get("new_state") == "cancelled"
    assert payload.get("previous_state") == initial_state

    delivery_response = api_client.get(f"/deliveries/{delivery_id}")
    assert delivery_response.status_code == 200
    delivery_payload = delivery_response.json()
    assert delivery_payload.get("state") == "cancelled"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_resend_delivery_requeues_and_reexecutes(api_client, default_channel, test_email):
    body = "Please summarise in French. " + ("B" * 2500)
    _, delivery_id, _ = _create_non_terminal_delivery(api_client, default_channel, test_email, body)

    abort_response = api_client.post(f"/deliveries/{delivery_id}/abort")
    assert abort_response.status_code == 200, f"Abort prerequisite failed: {abort_response.status_code} {abort_response.text[:200]}"
    assert abort_response.json().get("new_state") == "cancelled"

    resend_response = api_client.post(f"/deliveries/{delivery_id}/resend")
    assert resend_response.status_code == 200, f"Resend failed: {resend_response.status_code} {resend_response.text[:200]}"
    resend_payload = resend_response.json()
    assert resend_payload.get("delivery_id") == delivery_id
    # The worker may observe the cancellation request while already processing
    # and terminally fail before the resend call reads the delivery. Both states
    # are explicitly resendable; the resend behavior under test is the requeue.
    assert resend_payload.get("previous_state") in {"cancelled", "hard_failed"}
    assert resend_payload.get("new_state") == "queued"

    post_resend = api_client.get(f"/deliveries/{delivery_id}")
    assert post_resend.status_code == 200
    post_payload = post_resend.json()
    assert post_payload.get("state") in {"queued", "formatting", "sending", "sent", "soft_failed", "hard_failed"}
    assert post_payload.get("state") != "cancelled"

    final_state = _wait_for_state_change_from(api_client, delivery_id, previous_state="queued", timeout_seconds=180.0)
    assert final_state in {"formatting", "sending", "sent", "soft_failed", "hard_failed"}

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.smtp, pytest.mark.heavy]
