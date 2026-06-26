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

"""Real integration tests for LLM functionality."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.core.formatters.format_converter import FormatConverter
from src.core.formatters.llm_formatter import LLMFormatter
from src.core.llm.runtime_client import LLMManager
from src.database.db_manager import DatabaseManager
from src.database.repositories import ChannelRepository, UserRepository


@pytest.fixture
def db(tmp_path):
    """Create test database."""
    test_db_path = tmp_path / "it15_llm_real.db"
    if test_db_path.exists():
        test_db_path.unlink()

    db = DatabaseManager(f"sqlite3:///{test_db_path}")
    db.connect()

    migrations = [
        "001_initial_schema.sql",
        "002_user_management_personalization.sql",
        "002_add_message_guid.sql",
    ]
    for migration_name in migrations:
        migration_path = project_root / "database" / "migrations" / migration_name
        if migration_path.exists():
            db.apply_migration_file(migration_path)

    yield db

    db.disconnect()
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def real_llm_manager():
    """Create real LLM manager (no mocks)."""
    manager = LLMManager(get_config())
    if not manager.connect() or not manager.get_llm():
        pytest.fail("LLM not available - skipping real integration test")
    return manager
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.integration
@pytest.mark.llm_real
def test_real_llm_connection(real_llm_manager):
    """Verify LLM connection and basic response."""
    test_prompt = "Say OK if you can hear me. Respond with exactly OK."

    start_time = time.time()
    response = real_llm_manager.invoke(test_prompt, timeout=300)
    elapsed = time.time() - start_time

    print(f"LLM response in {elapsed:.2f}s: {response[:120]}")
    assert response is not None
    assert len(response) > 0
    assert "OK" in response.upper() or len(response) > 3
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.integration
@pytest.mark.llm_real
def test_real_llm_format_conversion(real_llm_manager):
    """Verify LLM format conversion works."""
    converter = FormatConverter(real_llm_manager)

    markdown_content = """# Title
## Subtitle
- Item 1
- Item 2
**Bold text** and *italic text*
"""

    start_time = time.time()
    result = converter.convert(
        content=markdown_content,
        source_format="markdown",
        target_format="html",
    )
    elapsed = time.time() - start_time

    print(f"LLM conversion in {elapsed:.2f}s")
    assert result is not None
    assert len(result) > 0
    assert "<" in result and ">" in result
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.integration
@pytest.mark.llm_real
def test_real_llm_message_formatting(db, real_llm_manager, test_email):
    """Verify LLM message formatting path works."""
    user_repo = UserRepository(db)
    user_id = user_repo.create(
        username="it15_real_user",
        email=test_email,
        password_hash="hash",
        language="en",
        content_style="html",
    )

    channel_repo = ChannelRepository(db)
    channel_repo.create(
        name=f"it15_email_{int(time.time())}",
        channel_type="smtp",
        enabled=True,
    )

    formatter = LLMFormatter(db, get_config())
    formatter.llm_manager = real_llm_manager
    formatter.format_converter.llm_manager = real_llm_manager

    content = [{"type": "text", "body": "This is a test message for real LLM formatting."}]
    result = formatter.format_message(
        content=content,
        channel_type="smtp",
        user_id=user_id,
    )

    assert result is not None
    assert "formatted_content" in result
    assert len(result["formatted_content"]) > 0

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.db, pytest.mark.smtp, pytest.mark.heavy]

