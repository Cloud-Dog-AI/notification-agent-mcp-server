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
Shared pytest fixtures for AT1.4 Comprehensive Test Suite
"""

import pytest
import json
import httpx
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any
from uuid import uuid4
import sys
from tests.utils.api_tracking import build_tracked_client

# Import test_config from root conftest
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from tests.conftest import (
    _ensure_api_ready_for_test,
    _overlay_env_values,
    _raw_env_args,
    _resolve_env_paths,
    _restart_local_service,
    _wait_for_health,
    test_config,
)

# Get project root
project_root = Path(__file__).parent.parent.parent.parent


def _resolve_sqlite_db_path(env: Dict[str, str]) -> Path | None:
    db_uri = str(env.get("CLOUD_DOG__NOTIFY__DB__URI") or "").strip()
    if not db_uri.startswith("sqlite3:///"):
        return None
    raw_path = db_uri.replace("sqlite3:///", "", 1).strip()
    if not raw_path:
        return None
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = project_root / db_path
    return db_path


def _restart_external_api(env_file: str, env_overrides: Dict[str, str]) -> None:
    child_env = os.environ.copy()
    child_env.update({key: str(value) for key, value in (env_overrides or {}).items()})
    child_env["CLOUD_DOG__DELIVERY_WORKER__STARTUP_DEFER_SECONDS"] = "0"
    child_env["CLOUD_DOG__NOTIFY__DELIVERY_WORKER__STARTUP_DEFER_SECONDS"] = "0"
    runtime_python = project_root / ".venv" / "bin" / "python"
    python_executable = str(runtime_python) if runtime_python.exists() else sys.executable

    subprocess.run(
        ["bash", "-lc", "for pid in $(lsof -ti tcp:8020 2>/dev/null); do kill $pid; done"],
        cwd=str(project_root),
        env=child_env,
        text=True,
        capture_output=True,
        check=False,
    )

    for _ in range(50):
        probe = subprocess.run(
            ["bash", "-lc", "lsof -ti tcp:8020"],
            cwd=str(project_root),
            env=child_env,
            text=True,
            capture_output=True,
            check=False,
        )
        if not probe.stdout.strip():
            break
        time.sleep(0.2)

    db_path = _resolve_sqlite_db_path(child_env)
    if db_path:
        for suffix in ("", "-shm", "-wal"):
            transient_db = Path(f"{db_path}{suffix}")
            if transient_db.exists():
                transient_db.unlink()

    log_path = Path("/tmp/notification-api-at14.out")
    with open(log_path, "ab") as log_handle:
        subprocess.Popen(
            [python_executable, "-u", "start_api_server.py", "--env", env_file],
            cwd=str(project_root),
            env=child_env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


@pytest.fixture(scope="session")
def api_base_url(test_config):
    """API base URL from config - NO HARDCODED FALLBACK"""
    url = test_config.get("api_server.base_url")
    if not url:
        pytest.fail(
            "❌ api_server.base_url not configured in env file\n"
            "Add: CLOUD_DOG__NOTIFY__API_SERVER__BASE_URL=<API_BASE_URL>"
        )
    return url


@pytest.fixture(scope="session")
def api_key(test_config):
    """API key from config - NO HARDCODED FALLBACK"""
    key = test_config.get("api_server.api_key")
    if not key:
        pytest.fail(
            "❌ api_server.api_key not configured in env file\n"
            "Add: CLOUD_DOG__NOTIFY__API_SERVER__API_KEY=your-api-key"
        )
    return key


@pytest.fixture(scope="function")
def restart_api_per_test(test_config, request, api_base_url, api_key):
    """
    AT1.4 exercises heavy PDF/storage paths, but the state boundary it needs is
    a healthy API plus an empty queued backlog. Use that lighter-weight
    isolation step instead of a full API restart for local-server runs.
    """
    env_args = _raw_env_args(request.config.getoption("--env"))
    env_paths = _resolve_env_paths(env_args)
    primary_env_file = str(env_paths[0].resolve())
    env_overrides = _overlay_env_values(env_paths)
    use_external_runtime = str(
        env_overrides.get("TEST_USE_EXTERNAL_RUNTIME", os.environ.get("TEST_USE_EXTERNAL_RUNTIME", "false"))
    ).strip().lower() in {"1", "true", "yes", "on"}
    if use_external_runtime:
        _restart_external_api(primary_env_file, env_overrides)
        time.sleep(2.0)
        health = _wait_for_health(api_base_url, timeout_seconds=60.0)
        if health is None:
            pytest.fail("❌ API not ready after per-test restart in AT1.4")
    else:
        _, cancelled = _ensure_api_ready_for_test(
            api_base_url,
            api_key,
            timeout_seconds=60.0,
            context_label="AT1.4 test execution",
        )
        if cancelled:
            print(f"✅ AT1.4 cancelled {cancelled} stale queued message(s) before test")


@pytest.fixture(scope="function")
def api_client(api_base_url, api_key, test_config, api_cleanup_registry, restart_api_per_test):
    """HTTP client for API calls"""
    # Read timeout from config
    timeout_total = test_config.get("api.timeout", 300)
    timeout_connect = test_config.get("api.connect_timeout", 60)
    timeout_read = test_config.get("api.read_timeout", 300)
    
    api_timeout = httpx.Timeout(
        timeout=timeout_total,
        connect=timeout_connect,
        read=timeout_read
    )
    
    with build_tracked_client(
        base_url=api_base_url,
        api_key=api_key,
        timeout=api_timeout,
        registry=api_cleanup_registry,
    ) as client:
        yield client


@pytest.fixture(scope="function")
def loopback_channel(api_client, test_config, request):
    """
    Create or get loop-back channel for testing
    
    Returns:
        Channel ID and channel dict
    """
    # Check if loop-back channel already exists
    messages_base_url = test_config.get("messages.base_url")
    if not messages_base_url:
        pytest.fail("❌ messages.base_url not configured in env file")

    desired_name = test_config.get("test.loopback_channel_name")
    message_path_template = test_config.get("test.loopback_message_path_template")
    desired_config = {"base_url": messages_base_url}
    if message_path_template:
        desired_config["message_path_template"] = message_path_template

    response = api_client.get("/channels")
    assert response.status_code == 200
    channels = response.json()

    created_channel_id = None
    existing_channel_id = None
    restore_enabled = None
    restore_config = None

    def _cleanup():
        if created_channel_id:
            resp = api_client.delete(f"/channels/{created_channel_id}")
            assert resp.status_code in (200, 204), (
                f"Failed to delete channel: {resp.status_code} {resp.text[:200]}"
            )
            return
        if existing_channel_id is not None:
            updates = {}
            if restore_enabled is False:
                updates["enabled"] = False
            if restore_config is not None:
                updates["config_json"] = restore_config
            if updates:
                resp = api_client.patch(f"/channels/{existing_channel_id}", json=updates)
                assert resp.status_code == 200, (
                    f"Failed to restore loop-back channel {existing_channel_id}: "
                    f"{resp.status_code} {resp.text[:200]}"
                )

    request.addfinalizer(_cleanup)

    selected_channel = None
    if desired_name:
        selected_channel = next((ch for ch in channels if ch.get("name") == desired_name), None)
    if not selected_channel:
        selected_channel = next((ch for ch in channels if ch.get("type") == "loopback"), None)

    if selected_channel:
        channel_id = selected_channel["id"]
        existing_channel_id = channel_id
        updates = {}
        if not bool(selected_channel.get("enabled")):
            updates["enabled"] = True
            restore_enabled = False
        current_config = selected_channel.get("config") if "config" in selected_channel else None
        restore_config = current_config if current_config is not None else None
        current_config = current_config or {}
        if any(current_config.get(k) != v for k, v in desired_config.items()):
            merged_config = dict(current_config)
            merged_config.update(desired_config)
            updates["config_json"] = merged_config
        if updates:
            update = api_client.patch(f"/channels/{channel_id}", json=updates)
            assert update.status_code == 200, (
                f"Failed to update loop-back channel {channel_id}: "
                f"{update.status_code} {update.text}"
            )
            selected_channel = api_client.get(f"/channels/{channel_id}").json()
        print(f"✅ Using existing loop-back channel: {channel_id}")
        return channel_id, selected_channel

    # Create loop-back channel
    channel_name = desired_name or f"loopback_{uuid4().hex}"
    channel_config = {
        "name": channel_name,
        "type": "loopback",
        "enabled": True,
        "config": desired_config,
    }

    response = api_client.post("/channels", json=channel_config)
    assert response.status_code == 201, f"Failed to create loop-back channel: {response.text}"

    channel_id = response.json()["id"]
    created_channel_id = channel_id
    print(f"✅ Created loop-back channel: {channel_id}")

    return channel_id, response.json()


@pytest.fixture
def cleanup_channels(api_client):
    """Cleanup helper - can be used to remove test channels if needed"""
    yield
    # Cleanup can be added here if needed
    pass


@pytest.fixture
def test_output_dir(tmp_path):
    """Temporary directory for test outputs"""
    output_dir = tmp_path / "test_outputs"
    output_dir.mkdir()
    return output_dir
