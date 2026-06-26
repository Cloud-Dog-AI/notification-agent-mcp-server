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
UT1.20: Runtime architecture contract tests.

Covers runtime guardrails that complement static boundary tests:
- Manager-layer DB access must flow through repositories.
- Media processing duplication must flow through storage service interface.
"""

from __future__ import annotations
import pytest

import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List

from src.core.groups.group_manager import GroupManager
from src.core.media.media_processor import MediaProcessor
from src.core.prompts.prompt_manager import PromptManager
from src.core.users.user_manager import UserManager
from src.database.db_manager import DatabaseManager


def _build_temp_db(tmp_path: Path) -> DatabaseManager:
    db_uri = f"sqlite3:///{tmp_path / 'ut120_runtime_contracts.db'}"
    db = DatabaseManager(db_uri)
    assert db.connect(), "Failed to connect temp DB"
    db.initialize_schema()
    return db


def _attach_db_call_guard(
    db: DatabaseManager,
    *,
    allowed_path_fragments: List[str],
) -> tuple[Dict[str, Callable[..., Any]], List[str]]:
    originals: Dict[str, Callable[..., Any]] = {}
    violations: List[str] = []

    def _guard(method_name: str):
        original = getattr(db, method_name)
        originals[method_name] = original

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            caller_frame = inspect.stack()[1]
            caller = caller_frame.filename.replace("\\", "/")
            if not any(fragment in caller for fragment in allowed_path_fragments):
                violations.append(f"{method_name} called from disallowed module: {caller}")
            return original(*args, **kwargs)

        setattr(db, method_name, wrapped)

    for name in ("execute", "execute_many", "fetchone", "fetchall"):
        _guard(name)

    return originals, violations


def _detach_db_call_guard(db: DatabaseManager, originals: Dict[str, Callable[..., Any]]) -> None:
    for name, original in originals.items():
        setattr(db, name, original)
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_ut120_runtime_db_access_contracts_use_repositories(tmp_path: Path, test_email_domain: str) -> None:
    """
    Runtime contract: manager-layer DB calls must be delegated via repositories.
    """
    db = _build_temp_db(tmp_path)
    user_manager = UserManager(db)
    group_manager = GroupManager(db)
    prompt_manager = PromptManager(db)

    originals, violations = _attach_db_call_guard(
        db,
        allowed_path_fragments=["/src/database/repositories.py"],
    )
    try:
        user_id = user_manager.user_repo.create(
            username="ut120_user",
            email=f"ut120_user{test_email_domain}",
            password_hash="hash",
            role="viewer",
            display_name="UT120 User",
            user_type="real",
            language="en",
            preferred_channel="email",
            content_style="plain",
            timezone="UTC",
        )
        assert user_id > 0

        assert user_manager.lookup_user("ut120_user", by="username") is not None
        assert isinstance(user_manager.search_users("ut120"), list)
        user_manager.update_preferences(user_id, language="fr", preferred_channel="email", content_style="html")
        assert user_manager.add_keyword(user_id, "ops") is True
        assert "ops" in user_manager.get_user_keywords(user_id)

        group_id = group_manager.create_group(
            name="ut120_group",
            description="runtime contract group",
            language="en",
            preferred_channel="email",
            content_style="plain",
        )
        assert group_id > 0
        assert group_manager.add_member(group_id, user_id, role="member") is True
        assert group_manager.add_keyword(group_id, "alerts") is True
        group = group_manager.get_group(group_id)
        assert group is not None and group.get("id") == group_id

        prompt_id = prompt_manager.create_prompt(
            name="ut120_prompt",
            prompt_text="Format in plain English.",
            channel_type="email",
            priority=1,
        )
        assert prompt_id > 0
        prompt = prompt_manager.get_prompt(channel_type="email")
        assert prompt is not None
    finally:
        _detach_db_call_guard(db, originals)
        db.disconnect()

    assert not violations, "Runtime DB contract violations:\n" + "\n".join(violations)


class _DummyStorageManager:
    def __init__(self) -> None:
        self.calls = 0

    def store_file(
        self,
        file_content: bytes,
        file_type: str,
        message_id: int | None = None,
        delivery_id: int | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        self.calls += 1
        return {
            "storage_path": f"{file_type}/dummy.png",
            "storage_uri": "file:///tmp/dummy.png",
            "access_url": "http://localhost:8004/storage/filesystem/dummy.png",
            "file_size": len(file_content),
            "mime_type": "image/png",
        }


class _DummyURIHandler:
    def fetch_media(self, uri: str, media_type: str):  # noqa: ANN201
        if media_type == "image":
            return b"fake_png_bytes", "png"
        return None
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_ut120_runtime_storage_contract_media_processor_uses_storage_service() -> None:
    """
    Runtime contract: media duplication must route through storage manager interface.
    """
    storage = _DummyStorageManager()
    media_processor = MediaProcessor(storage_manager=storage, uri_handler=_DummyURIHandler())

    media_refs = [
        {
            "type": "image",
            "uri": "https://example.com/image.png",
            "format": "png",
            "method": "uri",
        }
    ]

    duplicated = media_processor.process_media(
        media_refs,
        {"duplicate_images": True},
        message_id=10,
        delivery_id=20,
    )
    assert storage.calls == 1
    assert duplicated and duplicated[0].get("is_local") is True
    assert duplicated[0].get("url") == "http://localhost:8004/storage/filesystem/dummy.png"

    storage.calls = 0
    not_duplicated = media_processor.process_media(
        media_refs,
        {"duplicate_images": False},
        message_id=11,
        delivery_id=21,
    )
    assert storage.calls == 0
    assert not_duplicated and not_duplicated[0].get("is_local") is False

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.db, pytest.mark.smtp, pytest.mark.fast]
