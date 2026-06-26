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
IT1.28: Multi-dialect database validation (R-DB-08 / R-DB-10).

Checks:
- Engine initialisation for the active dialect overlay.
- Basic CRUD round-trip with a real DB connection.
- Migration asset presence for the active dialect.
- Health probe exposes database dialect metadata.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import text

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from cloud_dog_db import DatabaseSettings, build_sync_engine
from tests.utils.api_tracking import build_tracked_client
from tests.utils.test_helpers import check_test_dependencies


def _rewrite_sqlite_uri_for_host(db_uri: str) -> str:
    """Map container sqlite locations to the mounted host preprod database path."""
    if not isinstance(db_uri, str):
        return db_uri
    if db_uri.startswith("sqlite3:///app/database/data/") or db_uri.startswith("sqlite:///app/database/data/"):
        db_filename = Path(db_uri).name
        host_path = Path("/opt/docker/notificationagent0/database") / db_filename
        if host_path.exists():
            return f"sqlite:///{host_path}"
    return db_uri


def _database_settings_from_env(test_config) -> tuple[DatabaseSettings, str]:
    cfg_dialect = str(test_config.get("cloud_dog_db.dialect") or "").strip().lower()
    env_dialect = str(os.getenv("CLOUD_DOG_DB__DIALECT") or "").strip().lower()
    dialect = cfg_dialect or env_dialect
    if dialect in {"mysql", "postgresql"}:
        host = str(test_config.get("cloud_dog_db.host") or os.getenv("CLOUD_DOG_DB__HOST") or "").strip()
        port_raw = str(test_config.get("cloud_dog_db.port") or os.getenv("CLOUD_DOG_DB__PORT") or "").strip()
        username = str(test_config.get("cloud_dog_db.username") or os.getenv("CLOUD_DOG_DB__USERNAME") or "").strip()
        password = str(test_config.get("cloud_dog_db.password") or os.getenv("CLOUD_DOG_DB__PASSWORD") or "").strip()
        database = str(test_config.get("cloud_dog_db.database") or os.getenv("CLOUD_DOG_DB__DATABASE") or "").strip()
        missing = [
            key
            for key, value in (
                ("CLOUD_DOG_DB__HOST", host),
                ("CLOUD_DOG_DB__PORT", port_raw),
                ("CLOUD_DOG_DB__USERNAME", username),
                ("CLOUD_DOG_DB__PASSWORD", password),
                ("CLOUD_DOG_DB__DATABASE", database),
            )
            if not value
        ]
        if missing:
            pytest.fail(f"Missing DB overlay settings for {dialect}: {', '.join(missing)}")
        settings = DatabaseSettings(
            dialect=dialect,
            host=host,
            port=int(port_raw),
            username=username,
            password=password,
            database=database,
        )
        return settings, dialect

    db_uri = str(test_config.get("db.uri") or "").strip()
    if not db_uri:
        pytest.fail("Missing db.uri in runtime configuration")
    db_uri = _rewrite_sqlite_uri_for_host(db_uri)
    if db_uri.startswith("sqlite3://"):
        db_uri = "sqlite://" + db_uri[len("sqlite3://") :]
    settings = DatabaseSettings(url=db_uri)
    expected = "sqlite" if db_uri.startswith("sqlite") else ""
    return settings, expected


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, api_cleanup_registry):
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=30.0,
        registry=api_cleanup_registry,
    ) as client:
        yield client
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_db_engine_initialisation_and_basic_crud(test_config):
    settings, expected_dialect = _database_settings_from_env(test_config)
    engine = build_sync_engine(settings)

    table_name = f"it128_db_probe_{int(time.time())}"
    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY, value VARCHAR(64))"))
            conn.execute(text(f"DELETE FROM {table_name}"))
            conn.execute(
                text(f"INSERT INTO {table_name} (id, value) VALUES (:id, :value)"),
                {"id": 1, "value": "ok"},
            )
            row = conn.execute(text(f"SELECT value FROM {table_name} WHERE id = :id"), {"id": 1}).first()
            assert row is not None, "Expected row not returned"
            assert row[0] == "ok"
            conn.execute(text(f"DELETE FROM {table_name} WHERE id = :id"), {"id": 1})
            remaining = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one()
            assert int(remaining) == 0

        actual = str(engine.dialect.name or "").lower()
        if expected_dialect:
            # Accept "postgres" as equivalent to "postgresql".
            if expected_dialect == "postgresql":
                assert actual in {"postgresql", "postgres"}
            else:
                assert actual == expected_dialect
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        engine.dispose()
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_db_migration_assets_present_for_active_dialect(test_config):
    _, expected_dialect = _database_settings_from_env(test_config)
    migrations_root = project_root / "database" / "migrations"

    if expected_dialect in {"mysql", "mariadb"}:
        migrations_dir = migrations_root / "mysql"
    elif expected_dialect in {"postgresql", "postgres"}:
        migrations_dir = migrations_root / "postgres"
    else:
        migrations_dir = migrations_root

    assert migrations_dir.exists(), f"Migration directory missing: {migrations_dir}"
    sql_files = list(migrations_dir.glob("*.sql"))
    assert sql_files, f"No SQL migration files found in {migrations_dir}"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_health_probe_reports_database_dialect(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.status_code} {response.text[:200]}"
    payload = response.json()

    checks = payload.get("checks")
    assert isinstance(checks, dict), f"Expected health checks in /health payload: {payload}"
    database = checks.get("database")
    assert isinstance(database, dict), f"Expected database check in /health payload: {payload}"
    assert database.get("status") in {"ok", "error"}
    if database.get("status") == "ok":
        assert str(database.get("dialect") or "").strip(), "Connected DB must report dialect"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.heavy]
