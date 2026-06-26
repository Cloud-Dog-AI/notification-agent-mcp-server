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
Unit tests for DeliveryWorker startup backlog deferral behavior.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime

import pytest

from src.core.delivery_worker import DeliveryWorker
from src.database.db_manager import DatabaseManager
from src.database.repositories import DeliveryRepository, MessageRepository


def _synthetic_email(local_part: str, test_email_domain: str) -> str:
    return f"{local_part}{test_email_domain}"


@pytest.fixture
def db():
    """Create an isolated sqlite database for startup-backlog tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()

    yield db_manager

    db_manager.disconnect()
    try:
        os.unlink(db_path)
    except OSError:
        pass


def _insert_channel(db: DatabaseManager, name: str) -> int:
    cursor = db.execute(
        """
        INSERT INTO channels (name, type, enabled, config_json)
        VALUES (?, 'loopback', 1, ?)
        """,
        (name, json.dumps({"base_url": "http://127.0.0.1:8004"})),
    )
    db.commit()
    return int(cursor.lastrowid)


def _insert_message(db: DatabaseManager, suffix: str) -> int:
    message_repo = MessageRepository(db)
    return int(
        message_repo.create(
            created_by=f"ut-startup-{suffix}",
            audience_type="personalised",
            content_json=json.dumps([{"type": "text", "body": f"message-{suffix}"}]),
        )
    )


def _build_worker_for_test(
    db: DatabaseManager,
    *,
    startup_backlog_max_id: int,
    startup_mark: datetime | None = None,
) -> DeliveryWorker:
    # Build a lightweight instance to test internal startup-backlog helpers.
    worker = DeliveryWorker.__new__(DeliveryWorker)
    worker.db = db
    worker._startup_mark = startup_mark or datetime.now()
    worker._startup_backlog_deferred = False
    worker._startup_defer_seconds = 300
    worker._startup_backlog_max_id = startup_backlog_max_id
    return worker
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_capture_startup_backlog_max_id_uses_current_delivery_high_watermark(db: DatabaseManager, test_email_domain):
    channel_id = _insert_channel(db, "ut-startup-capture")
    msg_id = _insert_message(db, "capture")
    delivery_repo = DeliveryRepository(db)
    created_id = delivery_repo.create(
        message_id=msg_id,
        channel_id=channel_id,
        destination=_synthetic_email("capture", test_email_domain),
        state="queued",
    )

    worker = _build_worker_for_test(db, startup_backlog_max_id=0)
    captured = worker._capture_startup_backlog_max_id()

    assert captured == created_id
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_defer_startup_backlog_defers_only_pre_start_deliveries_by_id(db: DatabaseManager, test_email_domain):
    channel_id = _insert_channel(db, "ut-startup-defer")
    delivery_repo = DeliveryRepository(db)

    old_msg_id = _insert_message(db, "old")
    old_delivery_id = delivery_repo.create(
        message_id=old_msg_id,
        channel_id=channel_id,
        destination=_synthetic_email("old", test_email_domain),
        state="queued",
    )

    startup_max_id = old_delivery_id
    worker = _build_worker_for_test(db, startup_backlog_max_id=startup_max_id, startup_mark=datetime.now())

    new_msg_id = _insert_message(db, "new")
    new_delivery_id = delivery_repo.create(
        message_id=new_msg_id,
        channel_id=channel_id,
        destination=_synthetic_email("new", test_email_domain),
        state="queued",
    )
    assert new_delivery_id > startup_max_id

    worker._defer_startup_backlog_once()

    old_delivery = delivery_repo.get_by_id(old_delivery_id)
    new_delivery = delivery_repo.get_by_id(new_delivery_id)

    assert old_delivery is not None
    assert old_delivery.get("next_action_at") is not None
    assert new_delivery is not None
    assert new_delivery.get("next_action_at") is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.unit,
    pytest.mark.db,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]
