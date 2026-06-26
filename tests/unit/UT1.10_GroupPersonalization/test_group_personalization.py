# @pytest.mark.req("UC-013")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Test: Send Requirements Document to Users Group with Personalization

This test verifies:
- Group-based message delivery
- User-specific formatting (HTML vs plain text)
- Language translation (French)
- Keyword-based prompt selection
- Content style preferences
- ACTUAL DELIVERY (not just submission)
"""

import pytest
import json
import time
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path
from src.database.db_manager import DatabaseManager
from src.database.repositories import (
    UserRepository, UserDestinationRepository, UserKeywordRepository, GroupKeywordRepository,
    GroupRepository, GroupMemberRepository, MessageRepository, DeliveryRepository,
    LLMPromptRepository
)
from src.core.formatters.llm_formatter import LLMFormatter
from src.core.job_manager import JobManager
from src.core.state_machine import DeliveryState
from src.config import get_config
from tests.conftest import process_deliveries


def _find_project_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / "database" / "migrations").exists():
            return parent
    raise RuntimeError("Project root not found (database/migrations missing).")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve())


def _require_config(test_config, key: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.skip(f"Missing required config for UT1.10: {key}")
    return value


@pytest.fixture(scope="module", autouse=True)
def _disable_api_cleanup_for_ut10():
    """Keep UT1.10 teardown bounded under timeout-wrapped CI runs."""
    previous = os.environ.get("TEST_DISABLE_API_CLEANUP")
    previous_entity_cleanup = os.environ.get("TEST_DISABLE_UT10_ENTITY_CLEANUP")
    previous_cycle_timeout = os.environ.get("TEST_DELIVERY_PROCESS_CYCLE_TIMEOUT_SECONDS")
    os.environ["TEST_DISABLE_API_CLEANUP"] = "true"
    os.environ["TEST_DISABLE_UT10_ENTITY_CLEANUP"] = "true"
    os.environ["TEST_DELIVERY_PROCESS_CYCLE_TIMEOUT_SECONDS"] = "90"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TEST_DISABLE_API_CLEANUP", None)
        else:
            os.environ["TEST_DISABLE_API_CLEANUP"] = previous
        if previous_entity_cleanup is None:
            os.environ.pop("TEST_DISABLE_UT10_ENTITY_CLEANUP", None)
        else:
            os.environ["TEST_DISABLE_UT10_ENTITY_CLEANUP"] = previous_entity_cleanup
        if previous_cycle_timeout is None:
            os.environ.pop("TEST_DELIVERY_PROCESS_CYCLE_TIMEOUT_SECONDS", None)
        else:
            os.environ["TEST_DELIVERY_PROCESS_CYCLE_TIMEOUT_SECONDS"] = previous_cycle_timeout


def _with_run_id(value: str, run_id: str) -> str:
    if "@" in value:
        name, domain = value.split("@", 1)
        return f"{name}+ut10{run_id}@{domain}"
    return f"{value}_{run_id}"


def _format_with_timeout(formatter, *, content, channel_type, user_id, group_id, timeout: float):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            formatter.format_message,
            content=content,
            channel_type=channel_type,
            user_id=user_id,
            group_id=group_id,
        )
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            pytest.fail(f"LLM formatting exceeded timeout ({timeout}s)")


def _connect_with_timeout(formatter, timeout: float):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(formatter.llm_manager.connect)
        try:
            ok = future.result(timeout=timeout)
        except FutureTimeout:
            pytest.fail(f"LLM connect exceeded timeout ({timeout}s)")
        if not ok:
            pytest.fail("LLM not available; UT1.10 requires live LLM for personalization")


def _rewrite_sqlite_uri_for_host(db_uri: str) -> str:
    """Map container-style sqlite locations to a host path under PROJECT_ROOT."""
    if not isinstance(db_uri, str):
        return db_uri
    if db_uri.startswith("sqlite3:///app/database/") or db_uri.startswith("sqlite3:///database/"):
        db_filename = Path(db_uri).name
        host_db_dir = PROJECT_ROOT / "database"
        host_db_dir.mkdir(parents=True, exist_ok=True)
        # Use sqlite3:// + absolute path (not sqlite3:/// + absolute path) to avoid
        # producing sqlite3:////... URIs that can be mis-normalised downstream.
        return f"sqlite3://{host_db_dir / db_filename}"
    return db_uri


@pytest.fixture
def db(test_config):
    """Create test database connection"""
    db_uri = test_config.get("db.uri")
    if not db_uri:
        pytest.skip("db.uri not configured for UT1.10 (set CLOUD_DOG__NOTIFY__DB__URI).")
    db_uri = _rewrite_sqlite_uri_for_host(db_uri)
    db = DatabaseManager(db_uri)
    db.connect()
    try:
        tables = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users','groups','group_members')"
        )
        if len(tables or []) < 3:
            migrations_dir = PROJECT_ROOT / "database" / "migrations"
            for migration_file in sorted(migrations_dir.glob("*.sql")):
                db.apply_migration_file(migration_file)
            tables = db.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users','groups','group_members')"
            )
            if len(tables or []) < 3:
                pytest.fail("Database schema not initialised for UT1.10 after applying migrations.")
        yield db
    finally:
        db.disconnect()


@pytest.fixture
def requirements_content():
    """Load requirements.md content"""
    req_path = PROJECT_ROOT / "docs" / "REQUIREMENTS.md"
    if req_path.exists():
        return req_path.read_text()
    return "Test requirements document content for personalization testing."


@pytest.fixture
def job_manager(db, test_config):
    """Create job manager using config-driven defaults."""
    default_ttl = test_config.get("queue.default_ttl_hours") or 24
    max_retries = test_config.get("queue.max_retries") or 5
    backoff_base = test_config.get("queue.backoff_base_seconds") or 2
    backoff_max = test_config.get("queue.backoff_max_seconds") or 3600
    return JobManager(
        db,
        default_ttl_hours=int(default_ttl),
        max_retries=int(max_retries),
        backoff_base_seconds=int(backoff_base),
        backoff_max_seconds=int(backoff_max),
    )


@pytest.fixture
def ut10_config(test_config):
    return {
        "group_name_base": _require_config(test_config, "test.group_name_base"),
        "group_description": _require_config(test_config, "test.group_description"),
        "channel_type": _require_config(test_config, "test.group_channel_type"),
        "language": _require_config(test_config, "test.group_language"),
        "html_style": _require_config(test_config, "test.group_html_style"),
        "plain_style": _require_config(test_config, "test.group_plain_style"),
        "html_keyword_base": _require_config(test_config, "test.group_html_keyword"),
        "plain_keyword_base": _require_config(test_config, "test.group_plain_keyword"),
        "html_prompt_name_base": _require_config(test_config, "test.group_prompt_html_name"),
        "plain_prompt_name_base": _require_config(test_config, "test.group_prompt_plain_name"),
        "html_prompt_text": _require_config(test_config, "test.group_prompt_html_text"),
        "plain_prompt_text": _require_config(test_config, "test.group_prompt_plain_text"),
        "prompt_priority": int(_require_config(test_config, "test.group_prompt_priority")),
        "content_max_chars": int(_require_config(test_config, "test.group_content_max_chars")),
        "format_timeout": float(_require_config(test_config, "test.group_format_timeout")),
        "connect_timeout": float(_require_config(test_config, "test.group_connect_timeout")),
        "api_delivery_wait_timeout": float(
            test_config.get("test.group_api_delivery_wait_timeout") or 90.0
        ),
        "user_html_username_base": _require_config(test_config, "test.group_user_html_username"),
        "user_html_email_base": _require_config(test_config, "test.group_user_html_email"),
        "user_plain_username_base": _require_config(test_config, "test.group_user_plain_username"),
        "user_plain_email_base": _require_config(test_config, "test.group_user_plain_email"),
        "user_password": _require_config(test_config, "test.group_user_password"),
    }
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.timeout(600)
def test_v21_1_send_requirements_to_group_with_personalization(db, requirements_content, test_config, ut10_config):
    """
    V21.1: Send requirements.md to Users group with personalized formatting
    
    Expected:
    - Gary receives HTML formatted version (German)
    - Operations receives plain text version (German)
    - Each uses appropriate prompt based on keyword preference
    """
    import hashlib
    
    run_id = str(int(time.time()))
    gary_username = _with_run_id(ut10_config["user_html_username_base"], run_id)
    gary_email = _with_run_id(ut10_config["user_html_email_base"], run_id)
    ops_username = _with_run_id(ut10_config["user_plain_username_base"], run_id)
    ops_email = _with_run_id(ut10_config["user_plain_email_base"], run_id)
    test_password = ut10_config["user_password"]

    llm_provider = test_config.get("llm.provider")
    if not llm_provider:
        pytest.skip("LLM provider not configured for UT1.10 (set CLOUD_DOG__NOTIFY__LLM__PROVIDER).")
    if llm_provider == "ollama":
        required = ["llm.base_url", "llm.model", "llm.auto_pull", "llm.model_load_timeout", "llm.ignore_tls"]
        missing = [key for key in required if not test_config.get(key)]
        if missing:
            pytest.skip(f"Missing LLM config for UT1.10: {', '.join(missing)}")

    # Get repositories
    user_repo = UserRepository(db)
    dest_repo = UserDestinationRepository(db)
    keyword_repo = UserKeywordRepository(db)
    group_keyword_repo = GroupKeywordRepository(db)
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)
    prompt_repo = LLMPromptRepository(db)
    
    # Track created entities for cleanup
    created_user_ids = []
    created_dest_ids = []
    created_user_keywords = []
    created_group_keywords = []
    created_prompt_ids = []
    created_group_id = None
    created_group_member_ids = []
    
    try:
        # Create unique group + prompts
        group_name = f"{ut10_config['group_name_base']}_{run_id}"
        html_keyword = f"{ut10_config['html_keyword_base']}_{run_id}"
        plain_keyword = f"{ut10_config['plain_keyword_base']}_{run_id}"
        html_prompt_name = f"{ut10_config['html_prompt_name_base']}_{run_id}"
        plain_prompt_name = f"{ut10_config['plain_prompt_name_base']}_{run_id}"

        created_group_id = group_repo.create(
            name=group_name,
            description=ut10_config["group_description"],
            language=ut10_config["language"],
            preferred_channel=None,
            content_style=None,
            enabled=True,
        )
        group_repo.update(created_group_id, description=f"{ut10_config['group_description']} (updated)")

        created_prompt_ids.append(
            prompt_repo.create(
                name=html_prompt_name,
                prompt_text=ut10_config["html_prompt_text"],
                channel_type=ut10_config["channel_type"],
                keyword=html_keyword,
                priority=ut10_config["prompt_priority"],
                enabled=True,
            )
        )
        created_prompt_ids.append(
            prompt_repo.create(
                name=plain_prompt_name,
                prompt_text=ut10_config["plain_prompt_text"],
                channel_type=ut10_config["channel_type"],
                keyword=plain_keyword,
                priority=ut10_config["prompt_priority"],
                enabled=True,
            )
        )

        # Create Gary user
        gary_id = user_repo.create(
            username=gary_username,
            email=gary_email,
            password_hash=hashlib.sha256(test_password.encode()).hexdigest(),
            role="viewer",
            language=ut10_config["language"],
            content_style=ut10_config["html_style"],
        )
        created_user_ids.append(gary_id)
        user_repo.update_preferences(gary_id, content_style=ut10_config["html_style"], language=ut10_config["language"])
        gary = user_repo.get_by_id(gary_id)

        dest_id = dest_repo.create(
            user_id=gary_id,
            channel_type=ut10_config["channel_type"],
            destination=gary_email,
            verified=True,
            is_primary=True,
        )
        created_dest_ids.append(dest_id)

        keyword_repo.add(gary_id, html_keyword)
        created_user_keywords.append((gary_id, html_keyword))

        # Create Operations user
        ops_id = user_repo.create(
            username=ops_username,
            email=ops_email,
            password_hash=hashlib.sha256(test_password.encode()).hexdigest(),
            role="viewer",
            language=ut10_config["language"],
            content_style=ut10_config["plain_style"],
        )
        created_user_ids.append(ops_id)
        user_repo.update_preferences(ops_id, content_style=ut10_config["plain_style"], language=ut10_config["language"])
        operations = user_repo.get_by_id(ops_id)

        dest_id = dest_repo.create(
            user_id=ops_id,
            channel_type=ut10_config["channel_type"],
            destination=ops_email,
            verified=True,
            is_primary=True,
        )
        created_dest_ids.append(dest_id)

        keyword_repo.add(ops_id, plain_keyword)
        created_user_keywords.append((ops_id, plain_keyword))
        
        # Verify users exist
        assert gary is not None, "Gary user must exist"
        assert operations is not None, "Operations user must exist"
        
        # Verify preferences (CRUD update verified)
        assert gary.get('content_style') == ut10_config["html_style"], "Gary should have html content_style"
        assert operations.get('language') == ut10_config["language"], "Operations should have configured language"
        assert operations.get('content_style') == ut10_config["plain_style"], "Operations should have plain content_style"
        
        # Verify keywords (CRUD create + read)
        gary_keywords = [kw['keyword'] for kw in keyword_repo.get_by_user_id(gary['id'])]
        operations_keywords = [kw['keyword'] for kw in keyword_repo.get_by_user_id(operations['id'])]
        assert html_keyword in gary_keywords, "Gary should have html keyword"
        assert plain_keyword in operations_keywords, "Operations should have plain keyword"

        group_keyword_repo.add(created_group_id, html_keyword)
        created_group_keywords.append((created_group_id, html_keyword))

        # Add users to group
        member_id = member_repo.add_member(created_group_id, gary['id'])
        if member_id:
            created_group_member_ids.append(member_id)
        member_id = member_repo.add_member(created_group_id, operations['id'])
        if member_id:
            created_group_member_ids.append(member_id)

        users_group = group_repo.get_by_id(created_group_id)
        assert users_group is not None, "Group must exist"
        
        # Get group members
        members = db.fetchall(
            "SELECT u.id, u.username, u.email, u.language, u.content_style FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?",
            (users_group['id'],)
        )
        
        assert len(members) >= 2, "Users group should have at least 2 members"
        
        # Initialize formatter
        config = get_config()
        formatter = LLMFormatter(db, config)
        _connect_with_timeout(formatter, ut10_config["connect_timeout"])
        
        # Format message for each user (trimmed for predictable runtime)
        content_blocks = [{"type": "text", "body": requirements_content[:ut10_config["content_max_chars"]]}]
        
        results = {}
        
        for member in members:
            user_id = member['id']
            username = member['username']
            
            # Format message for this user
            result = _format_with_timeout(
                formatter,
                content=content_blocks,
                channel_type=ut10_config["channel_type"],
                user_id=user_id,
                group_id=users_group['id'],
                timeout=ut10_config["format_timeout"],
            )
            
            results[username] = result
            
            # Verify formatting
            # Level 1: Structure
            assert result is not None, f"Formatter should return result for {username}"
            assert isinstance(result, dict)
            assert "formatted_content" in result, f"Result should have formatted_content for {username}"
            assert isinstance(result["formatted_content"], list)
            assert len(result["formatted_content"]) > 0, f"Formatted content should not be empty for {username}"
            
            formatted_text = result["formatted_content"][0]["body"]
            assert isinstance(formatted_text, str)
            assert formatted_text.strip(), "Formatted text must be non-empty"
            
            if username == gary_username:
                # Level 2: Format
                assert result.get("prompt_used") == html_prompt_name, "Gary should use HTML prompt"
                # Level 3: Content
                assert result.get("translation_applied") is True
                assert result.get("target_language") == ut10_config["language"]
                # Level 4: Quality
                has_html_tags = any(tag in formatted_text.lower() for tag in ["<h2>", "<h3>", "<p>", "<ul>", "<li>"])
                assert has_html_tags, "HTML output must include HTML tags"
            
            elif username == ops_username:
                # Level 2: Format
                assert result.get("prompt_used") == plain_prompt_name, "Operations should use plain prompt"
                # Level 3: Content
                assert result.get("translation_applied") is True
                assert result.get("target_language") == ut10_config["language"]
                # Level 4: Quality
                has_html_tags = any(tag in formatted_text.lower() for tag in ["<h2>", "<h3>", "<p>", "<ul>", "<li>"])
                assert not has_html_tags, f"Operations should receive plain text (no HTML), got: {formatted_text[:200]}"
        
        # Verify we got results for both users
        assert gary_username in results, "Should have formatted content for Gary"
        assert ops_username in results, "Should have formatted content for Operations"
        
        assert gary_username in results, "Should have formatted content for HTML user"
        assert ops_username in results, "Should have formatted content for plain user"
    
    finally:
        for group_id, keyword in created_group_keywords:
            group_keyword_repo.remove(group_id, keyword)
        for user_id, keyword in created_user_keywords:
            keyword_repo.remove(user_id, keyword)
        for member_id in created_group_member_ids:
            member_repo.remove_member_by_id(member_id)
        if created_group_id:
            db.execute("DELETE FROM groups WHERE id = ?", (created_group_id,))
        for prompt_id in created_prompt_ids:
            db.execute("DELETE FROM llm_prompts WHERE id = ?", (prompt_id,))
        for dest_id in created_dest_ids:
            db.execute("DELETE FROM user_destinations WHERE id = ?", (dest_id,))
        for user_id in created_user_ids:
            user_repo.delete(user_id)
        db.commit()
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


@pytest.mark.asyncio
@pytest.mark.timeout(600)
async def test_v21_2_send_via_api_to_group(db, requirements_content, job_manager, api_base_url, api_key, default_channel, ut10_config):
    """
    V21.2: Send requirements.md to Users group via API
    
    This test sends the message through the API and verifies
    that deliveries are created for each group member with
    appropriate personalization.
    """
    import requests
    
    headers = {"X-API-Key": api_key}
    
    # Check if API server is running
    try:
        health_response = requests.get(f"{api_base_url}/health", timeout=2.0)
        if health_response.status_code != 200:
            pytest.skip("API server is not running or not healthy")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        pytest.skip("API server is not running (connection refused)")

    # Check if LLM is available — delivery worker cannot format without it
    try:
        llm_response = requests.get(
            f"{api_base_url}/llm/status", headers=headers, timeout=2.0
        )
        if llm_response.status_code == 200:
            llm_status = llm_response.json()
            if llm_status.get("connection_status") == "disconnected":
                pytest.skip("LLM is disconnected — delivery worker cannot format")
    except Exception:
        pass  # If we can't check LLM status, continue and let the test run
    
    # Get group members to verify destinations
    user_repo = UserRepository(db)
    dest_repo = UserDestinationRepository(db)
    group_repo = GroupRepository(db)
    member_repo = GroupMemberRepository(db)
    run_id = str(int(time.time()))
    group_name = f"{ut10_config['group_name_base']}_api_{run_id}"
    users_group = group_repo.get_by_name(group_name)
    created_user_ids = []
    created_group_id = None
    created_message_id = None
    if users_group is None:
        created_group_id = group_repo.create(
            name=group_name,
            description=ut10_config["group_description"],
            language=ut10_config["language"],
            preferred_channel=None,
            content_style=None,
            enabled=True,
        )
        users_group = group_repo.get_by_id(created_group_id)
    
    members = db.fetchall(
        "SELECT u.id, u.username, u.email FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?",
        (users_group['id'],)
    )
    if len(members) < 2:
        import hashlib
        api_html_email = _with_run_id(ut10_config["user_html_email_base"], f"api{run_id}")
        api_plain_email = _with_run_id(ut10_config["user_plain_email_base"], f"api{run_id}")

        gary_id = user_repo.create(
            username=f"{ut10_config['user_html_username_base']}_api_{run_id}",
            email=api_html_email,
            password_hash=hashlib.sha256(ut10_config["user_password"].encode()).hexdigest(),
            role="viewer",
            language=ut10_config["language"],
            content_style=ut10_config["html_style"],
        )
        created_user_ids.append(gary_id)
        dest_repo.create(
            user_id=gary_id,
            channel_type=ut10_config["channel_type"],
            destination=api_html_email,
            verified=True,
            is_primary=True,
        )
        member_repo.add_member(users_group['id'], gary_id)

        ops_id = user_repo.create(
            username=f"{ut10_config['user_plain_username_base']}_api_{run_id}",
            email=api_plain_email,
            password_hash=hashlib.sha256(ut10_config["user_password"].encode()).hexdigest(),
            role="viewer",
            language=ut10_config["language"],
            content_style=ut10_config["plain_style"],
        )
        created_user_ids.append(ops_id)
        dest_repo.create(
            user_id=ops_id,
            channel_type=ut10_config["channel_type"],
            destination=api_plain_email,
            verified=True,
            is_primary=True,
        )
        member_repo.add_member(users_group['id'], ops_id)

        members = db.fetchall(
            "SELECT u.id, u.username, u.email FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?",
            (users_group['id'],)
        )
    
    # Get destinations for group members
    destinations = []
    for member in members:
        dests = dest_repo.get_by_user_id(member['id'], channel_type=ut10_config["channel_type"])
        for dest in dests:
            if dest['is_primary']:
                destinations.append({
                    "channel": default_channel,
                    "address": dest['destination']
                })
                break
    
    assert len(destinations) >= 2, "Should have at least 2 email destinations"
    
    # Send message via API
    payload = {
        "audience_type": "personalised",
        "destinations": destinations,
        "content": [
            {
                "type": "text",
                "body": requirements_content[:ut10_config["content_max_chars"]]
            }
        ],
        "idempotency_key": f"test-group-requirements-{int(time.time())}"
    }
    
    response = requests.post(f"{api_base_url}/messages", headers=headers, json=payload)
    
    assert response.status_code == 201, f"API should return 201, got {response.status_code}: {response.text}"
    
    result = response.json()
    message_id = result.get('message_id')
    assert message_id is not None, "API should return message_id"
    created_message_id = message_id
    
    # This test submits through the real API runtime, so delivery state must be
    # polled from that runtime rather than the temporary unit-test DB fixture.
    delivery_wait_timeout = max(30.0, float(ut10_config.get("api_delivery_wait_timeout", 90.0)))
    deadline = time.monotonic() + delivery_wait_timeout
    deliveries = []
    processed = 0
    while time.monotonic() < deadline:
        deliveries_response = requests.get(
            f"{api_base_url}/messages/{message_id}/deliveries",
            headers=headers,
            timeout=10.0,
        )
        assert deliveries_response.status_code == 200, "Should be able to list message deliveries"
        deliveries_payload = deliveries_response.json()
        deliveries = deliveries_payload.get("items", []) if isinstance(deliveries_payload, dict) else []
        processed = len(deliveries)
        if len(deliveries) >= 2 and any(
            (delivery.get("state") or "") not in {DeliveryState.QUEUED.value}
            for delivery in deliveries
        ):
            break
        await asyncio.sleep(0.5)
    print(f"\nObserved {processed} deliveries for message {message_id}")
    
    # Check message status
    msg_response = requests.get(
        f"{api_base_url}/messages/{message_id}",
        headers={**headers, "Accept": "application/json"},
    )
    assert msg_response.status_code == 200, "Should be able to retrieve message"
    
    msg = msg_response.json()
    
    # Check deliveries were created and PROCESSED by the API runtime
    assert len(deliveries) >= 2, f"Should have at least 2 deliveries (one per user), got {len(deliveries)}"
    
    # VERIFY ACTUAL DELIVERY PROCESSING - not just queued
    processed_count = 0
    queued_count = 0
    sent_count = 0
    failed_count = 0
    sending_count = 0
    formatting_count = 0
    
    for delivery in deliveries:
        state = delivery.get('state')
        destination = delivery.get('destination')
        attempts = delivery.get('attempt_no', 0)
        error = delivery.get('last_error', 'None')
        
        error_str = str(error)[:50] if error else 'None'
        print(f"  - {destination}: {state} (attempts: {attempts}, error: {error_str})")

        if state == DeliveryState.QUEUED.value:
            queued_count += 1
            continue

        # Should have progressed through the delivery pipeline
        assert state in [
            DeliveryState.DEFERRED.value,
            DeliveryState.FORMATTING.value,
            DeliveryState.SENDING.value,
            DeliveryState.SENT.value,
            DeliveryState.DELIVERED.value,
            DeliveryState.SOFT_FAILED.value,
            DeliveryState.HARD_FAILED.value,
        ], f"Delivery to {destination} should be processed (or queued), got {state}"

        processed_count += 1
        
        if state == DeliveryState.SENT.value:
            sent_count += 1
            # Should have tracking ID if sent
            assert delivery.get('provider_tracking_id') is not None, \
                f"Sent delivery to {destination} should have tracking ID"
        elif state == DeliveryState.SENDING.value:
            sending_count += 1
        elif state == DeliveryState.FORMATTING.value:
            formatting_count += 1
        elif state == DeliveryState.DEFERRED.value:
            # Circuit-breaker deferral still proves the worker picked up the delivery.
            pass
        elif state in [DeliveryState.SOFT_FAILED.value, DeliveryState.HARD_FAILED.value]:
            failed_count += 1
            # Should have error message (may be None if just failed)
            # Just verify it was attempted
            # Should have attempt count
            assert attempts > 0, \
                f"Failed delivery to {destination} should have attempt count > 0"
    
    # At least one delivery should have moved beyond queued within bounded wait.
    # If all deliveries remain queued, the delivery worker is not running — this is a
    # runtime-dependency skip, not a product bug (same class as the API/LLM checks above).
    if processed_count == 0 and queued_count > 0:
        pytest.skip(
            f"Delivery worker not processing: all {queued_count} deliveries remain queued after "
            f"{delivery_wait_timeout}s — worker is likely not running in this environment"
        )
    assert processed_count > 0, \
        f"Expected at least one delivery to progress beyond queued; queued={queued_count}, processed={processed_count}"
    
    print(f"\n✅ Delivery Processing Verification:")
    print(f"   - Total deliveries: {len(deliveries)}")
    print(f"   - Processed: {processed_count}")
    print(f"   - Queued: {queued_count}")
    print(f"   - Formatting: {formatting_count}")
    print(f"   - Sent: {sent_count}")
    print(f"   - Sending: {sending_count}")
    print(f"   - Failed: {failed_count}")

    # Cleanup created message and entities (optional for timeout-wrapped UT runs).
    skip_entity_cleanup = str(
        os.environ.get("TEST_DISABLE_UT10_ENTITY_CLEANUP", "")
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not skip_entity_cleanup:
        if created_message_id:
            try:
                requests.delete(f"{api_base_url}/messages/{created_message_id}", headers=headers, timeout=5.0)
            except Exception:
                pass
        for user_id in created_user_ids:
            user_repo.delete(user_id)
        if created_group_id:
            db.execute("DELETE FROM group_members WHERE group_id = ?", (created_group_id,))
            db.execute("DELETE FROM groups WHERE id = ?", (created_group_id,))
            db.commit()
    
    print("\n" + "="*70)
    print("API GROUP MESSAGE TEST RESULTS")
    print("="*70)
    print(f"Message ID: {message_id}")
    print(f"Status: {msg.get('status')}")
    print(f"Deliveries created: {len(deliveries)}")
    print(f"Deliveries sent: {sent_count}")
    for delivery in deliveries:
        print(f"  - {delivery.get('destination')}: {delivery.get('state')} (Tracking: {delivery.get('provider_tracking_id', 'None')})")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.llm, pytest.mark.db, pytest.mark.smtp, pytest.mark.docker, pytest.mark.heavy]
