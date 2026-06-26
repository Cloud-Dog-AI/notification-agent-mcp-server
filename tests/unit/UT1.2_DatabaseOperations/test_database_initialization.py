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
Test Database Initialization

V23.1: Verify that deleting the database and restarting the server
properly populates the database and enables initial channels/users.
"""

import pytest
import sqlite3
import asyncio
from pathlib import Path


@pytest.fixture
def db_path(tmp_path):
    """Use a temp sqlite database for init tests."""
    return tmp_path / "ut_init.db"
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_v23_1_database_initialization_on_startup(db_path, test_config):
    """
    V23.1: Initialize database and verify schema + initial channels
    """
    # Step 1: Verify database is deleted
    assert not db_path.exists(), "Database should be deleted before test"

    from src.database.db_manager import DatabaseManager
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    resolved_db_path = Path(db_manager.db_path)

    # Step 2: Verify database was created
    assert resolved_db_path.exists(), "Database should be created on initialization"

    # Step 3: Verify database has tables
    conn = sqlite3.connect(str(resolved_db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    required_tables = ['users', 'channels', 'messages', 'deliveries', 'groups']
    for table in required_tables:
        assert table in tables, f"Table {table} should exist after initialization"

    # Step 4: Verify initial channels are created
    cursor.execute("SELECT name, enabled FROM channels")
    channels = cursor.fetchall()
    assert len(channels) > 0, "At least one channel should be created"

    default_channel = test_config.get("default_channel")
    if default_channel:
        names = [ch[0] for ch in channels]
        assert default_channel in names, "Default channel should exist after initialization"

    conn.close()
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
async def test_v23_1_verify_initial_users(db_path):
    """
    V23.1 (Extended): Verify users table is created and accessible
    """
    from src.database.db_manager import DatabaseManager
    db_uri = f"sqlite3://{db_path}"
    db_manager = DatabaseManager(db_uri)
    db_manager.connect()
    db_manager.initialize_schema()
    resolved_db_path = Path(db_manager.db_path)

    conn = sqlite3.connect(str(resolved_db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    assert user_count >= 0, "User count should be non-negative"

    conn.close()


if __name__ == "__main__":
    import asyncio
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.unit,
    pytest.mark.db,
    pytest.mark.fast,
    pytest.mark.no_runtime_dependency,
    pytest.mark.no_llm_dependency,
]
