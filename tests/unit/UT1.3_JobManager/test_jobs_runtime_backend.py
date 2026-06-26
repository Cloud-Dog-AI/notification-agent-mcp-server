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
Unit tests for persistent jobs runtime backend selection and logging context.

Tests:
- SQL backend is selected by default for the runtime
- Delivery jobs survive runtime reload via SQL persistence
- server_id is injected into emitted log records
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from cloud_dog_jobs.domain.enums import JobStatus

from src.config import get_config
from src.core.job_manager import JobManager as LegacyJobManager
from src.core.jobs import JobManager, QueueCoordinator
from src.core.jobs.runtime import get_jobs_runtime
from src.utils import logger as logger_module
from src.utils.logger import get_logger


def _write_runtime_env(path: Path, db_path: Path) -> None:
    """Write the minimal env overlay required for jobs runtime tests."""
    path.write_text(
        "\n".join(
            [
                f"CLOUD_DOG__NOTIFY__DB__URI=sqlite3://{db_path}",
                "CLOUD_DOG__NOTIFY__QUEUE__BACKEND=sql",
                "CLOUD_DOG__NOTIFY__APP__SERVER_ID=ut-jobs-runtime",
                "CLOUD_DOG__NOTIFY__API_SERVER__API_KEY=test-key",
                "CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL=http://127.0.0.1:8020",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _restore_global_config_after_test():
    """Restore the active runtime config after each jobs-runtime unit test."""
    original = get_config()
    defaults_yaml = str(original.defaults_yaml)
    config_yaml = str(original.config_yaml)
    env_file = str(original.env_file)
    yield
    get_config(
        defaults_yaml=defaults_yaml,
        config_yaml=config_yaml,
        env_file=env_file,
        force_reload=True,
    )
    get_jobs_runtime(force_reload=True)
    logger_module._SERVER_ID_CACHE = None
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_sql_backend_selected_by_default(tmp_path):
    """Runtime should use SQLQueueBackend when queue.backend is sql/default."""
    env_path = tmp_path / "jobs-runtime.env"
    db_path = tmp_path / "jobs-runtime.db"
    _write_runtime_env(env_path, db_path)

    get_config(env_file=str(env_path), force_reload=True)
    runtime = get_jobs_runtime(force_reload=True)

    assert runtime.backend_name == "sql"
    assert type(runtime.backend).__name__ == "SQLQueueBackend"
    assert runtime.server_id == "ut-jobs-runtime"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_job_manager_exports_use_jobs_queue_coordinator():
    """Legacy imports should resolve to the cloud_dog_jobs-backed coordinator."""
    assert JobManager is QueueCoordinator
    assert LegacyJobManager is JobManager
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_delivery_jobs_persist_across_runtime_reload(tmp_path):
    """A queued delivery job should remain addressable after runtime reload."""
    env_path = tmp_path / "jobs-runtime.env"
    db_path = tmp_path / "jobs-runtime.db"
    _write_runtime_env(env_path, db_path)

    get_config(env_file=str(env_path), force_reload=True)
    runtime = get_jobs_runtime(force_reload=True)
    job_id = runtime.enqueue_delivery_job(
        delivery_id=42,
        message_id=7,
        channel_id=3,
        destination="persist@cloud-dog.net",
    )
    assert runtime.mark_delivery_status(42, JobStatus.RETRY_WAIT.value) is True

    get_config(env_file=str(env_path), force_reload=True)
    reloaded_runtime = get_jobs_runtime(force_reload=True)
    job = reloaded_runtime.get_delivery_job(42)

    assert job is not None
    assert job.job_id == job_id
    assert getattr(job.status, "value", str(job.status)).lower() == JobStatus.RETRY_WAIT.value
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_server_id_is_injected_into_log_records(tmp_path):
    """Every emitted log record should include the configured server_id."""
    env_path = tmp_path / "jobs-runtime.env"
    db_path = tmp_path / "jobs-runtime.db"
    _write_runtime_env(env_path, db_path)

    get_config(env_file=str(env_path), force_reload=True)
    logger_module._SERVER_ID_CACHE = None

    logger = get_logger("w28a281.test")
    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _ListHandler()
    logger.addHandler(handler)
    try:
        logger.warning("server id test")
    finally:
        logger.removeHandler(handler)

    assert records
    assert getattr(records[-1], "server_id", "") == "ut-jobs-runtime"
