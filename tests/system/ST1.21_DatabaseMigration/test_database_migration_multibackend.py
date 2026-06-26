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

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from cloud_dog_db import DatabaseSettings, MigrationRunner, build_sync_engine
from cloud_dog_db.migrations.runner import MigrationConfig


def _env_value(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def _settings_from_env() -> DatabaseSettings:
    payload: dict[str, str] = {}
    env_map = {
        "dialect": ("CLOUD_DOG_DB__DIALECT", "CLOUD_DOG__DB__DIALECT"),
        "driver": ("CLOUD_DOG_DB__DRIVER", "CLOUD_DOG__DB__DRIVER"),
        "host": ("CLOUD_DOG_DB__HOST", "CLOUD_DOG__DB__HOST"),
        "port": ("CLOUD_DOG_DB__PORT", "CLOUD_DOG__DB__PORT"),
        "username": ("CLOUD_DOG_DB__USERNAME", "CLOUD_DOG__DB__USERNAME"),
        "password": ("CLOUD_DOG_DB__PASSWORD", "CLOUD_DOG__DB__PASSWORD"),
        "database": ("CLOUD_DOG_DB__DATABASE", "CLOUD_DOG__DB__DATABASE"),
        "url": ("CLOUD_DOG_DB__URL", "CLOUD_DOG__DB__URL", "CLOUD_DOG__DB__URI", "CLOUD_DOG__NOTIFY__DB__URI"),
    }
    for field, names in env_map.items():
        value = _env_value(*names)
        if value is not None:
            # Normalise sqlite3:// to sqlite:// for SQLAlchemy compatibility
            if field == "url" and value.startswith("sqlite3://"):
                value = "sqlite://" + value[len("sqlite3://"):]
            payload[field] = value

    if not payload:
        payload = {
            "dialect": "sqlite",
            "database": "./database/notification_agent.db",
        }
    elif not str(payload.get("database") or "").strip() and not str(payload.get("url") or "").strip():
        payload["database"] = "./database/notification_agent.db"

    return DatabaseSettings.model_validate(payload)


def _migration_script_location() -> str:
    return str((Path(__file__).resolve().parents[3] / "database" / "migrations" / "cloud_dog_db").resolve())


def _version_table_ref(cfg: MigrationConfig) -> str:
    if cfg.version_table_schema:
        return f"{cfg.version_table_schema}.{cfg.version_table}"
    return cfg.version_table


def _current_revision(engine, cfg: MigrationConfig) -> str | None:
    table_ref = _version_table_ref(cfg)
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT version_num FROM {table_ref}")).fetchall()
    if not rows:
        return None
    return str(rows[0][0])


def _write_temp_migration(script_location: Path, down_revision: str) -> tuple[str, Path]:
    revision = f"w23a_test_{time.time_ns()}"
    path = script_location / "versions" / f"{revision}_version_check.py"
    path.write_text(
        f'''"""temporary W23A version simulation migration"""
from __future__ import annotations
import pytest
from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = "{down_revision}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "_test_version_check",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("marker", sa.String(length=64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("_test_version_check")
''',
        encoding="utf-8",
    )
    return revision, path


def _build_runtime(tmp_path: Path) -> tuple[MigrationRunner, MigrationConfig, object]:
    settings = _settings_from_env()
    if settings.dialect.value == "sqlite":
        db_path = tmp_path / "notification-agent-st.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Rebuild settings with the temp path so to_sync_url() uses the correct DB.
        # Setting settings.database alone does NOT change the URL returned by to_sync_url().
        settings = DatabaseSettings(dialect="sqlite", database=str(db_path))

    cfg = MigrationConfig(
        script_location=_migration_script_location(),
        sqlalchemy_url=settings.to_sync_url(),
    )
    runner = MigrationRunner(cfg)
    engine = build_sync_engine(settings)
    return runner, cfg, engine
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st_db_01_migration_lifecycle_upgrade_downgrade_upgrade(tmp_path: Path) -> None:
    runner, cfg, engine = _build_runtime(tmp_path)
    try:
        runner.upgrade("head")
        baseline_revision = _current_revision(engine, cfg)
        assert baseline_revision

        runner.downgrade("base")
        assert _current_revision(engine, cfg) is None

        runner.upgrade("head")
        assert _current_revision(engine, cfg) == baseline_revision
    finally:
        engine.dispose()
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_st_db_02_schema_versioning_simulation(tmp_path: Path) -> None:
    runner, cfg, engine = _build_runtime(tmp_path)
    script_location = Path(cfg.script_location)
    try:
        runner.upgrade("head")
        baseline_revision = _current_revision(engine, cfg)
        assert baseline_revision

        _, temp_migration = _write_temp_migration(script_location, baseline_revision)
        try:
            runner.upgrade("head")
            inspector = inspect(engine)
            assert "_test_version_check" in inspector.get_table_names()

            with engine.begin() as conn:
                conn.execute(text("INSERT INTO _test_version_check (marker) VALUES ('ok')"))
                count = conn.execute(text("SELECT COUNT(*) FROM _test_version_check")).scalar_one()
            assert count == 1

            runner.downgrade(baseline_revision)
            inspector = inspect(engine)
            assert "_test_version_check" not in inspector.get_table_names()
        finally:
            if temp_migration.exists():
                temp_migration.unlink()
            runner.upgrade("head")
    finally:
        engine.dispose()

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.db, pytest.mark.slow]
