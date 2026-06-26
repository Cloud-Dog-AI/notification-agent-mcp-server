# @pytest.mark.req("UC-018")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Test: Async Message Submission (Non-Blocking)

Tests that message creation returns immediately even when LLM formatting is required.
This verifies the asynchronous LLM processing implementation.

Tests:
- V25.21: Message submission returns immediately (< configured threshold)
- V25.22: Message created even when LLM unavailable
- V25.23: Multiple messages queued correctly
- V25.24: estimated_delivery_time included when LLM busy
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _require_number(test_config, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"❌ HARD FAIL: {key} not configured in env/config")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: {key} must be a {number_type}: {e}")


def _get_api_timeout(test_config) -> httpx.Timeout:
    total = _require_number(test_config, "api.timeout", number_type="float")
    connect = test_config.get("api.connect_timeout")
    if connect is None or connect == "":
        connect = total
    else:
        connect = _require_number(test_config, "api.connect_timeout", number_type="float")
    read = test_config.get("api.read_timeout")
    if read is None or read == "":
        read = total
    else:
        read = _require_number(test_config, "api.read_timeout", number_type="float")
    return httpx.Timeout(timeout=total, connect=connect, read=read)


def _get_max_submit_seconds(test_config) -> float:
    max_submit = (
        test_config.get("test.it13.max_submit_seconds")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if max_submit is None or max_submit == "":
        pytest.fail(
            "❌ HARD FAIL: Configure test.it13.max_submit_seconds, api.connect_timeout, or api.timeout"
        )
    return float(max_submit)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.fixture(scope="session")
def test_message_path(test_config):
    filename = _require_value(test_config.get("test.message_file"), "test.message_file")
    candidate = Path(filename)
    project_root = Path(__file__).resolve().parents[3]
    if candidate.is_absolute():
        return candidate
    if candidate.parts and candidate.parts[0] in {"test", "tests"}:
        return project_root / candidate
    return project_root / "tests" / "Examples" / candidate


@pytest.fixture
def api_client(api_base_url, api_key, test_config):
    """Create API client with config-driven timeouts."""
    api_timeout = _get_api_timeout(test_config)
    return httpx.Client(
        base_url=api_base_url,
        headers={"X-API-Key": api_key},
        timeout=api_timeout,
    )


def read_test_message(test_message_path: Path) -> str:
    """Read the test message file."""
    if not test_message_path.exists():
        pytest.fail(f"Test message file not found: {test_message_path}")
    return test_message_path.read_text(encoding="utf-8")


def _wait_for_runtime_health(
    base_url: str,
    api_key: str,
    timeout: httpx.Timeout,
    *,
    max_wait_seconds: float,
) -> None:
    deadline = time.monotonic() + max_wait_seconds
    last_error = ""
    while time.monotonic() < deadline:
        try:
            response = httpx.get(
                f"{base_url.rstrip('/')}/health",
                headers={"X-API-Key": api_key},
                timeout=timeout,
            )
            if response.status_code == 200:
                return
            last_error = f"{response.status_code} {response.text[:200]}"
        except Exception as exc:
            last_error = repr(exc)
        time.sleep(1)

    pytest.fail(f"Runtime API did not become healthy within {max_wait_seconds}s: {last_error}")


def _restart_runtime_service(
    env_file: str,
    service: str,
    overrides: dict[str, str] | None = None,
    *,
    base_url: str,
    api_key: str,
    timeout: httpx.Timeout,
    max_wait_seconds: float,
) -> None:
    target = "all" if service in {"api", "web", "mcp", "a2a", "worker"} else service
    # The selected env file declares startup-critical secrets (auth.jwt_secret,
    # api_server.api_key, mcp keys) as ${vault.*} references. server_control
    # reloads the env file on restart, but the local runtime cannot resolve
    # vault refs (no approle creds), so the unified app would crash at import on
    # a missing auth.jwt_secret. Resolve the notify vars here (the test session
    # already has vault read access) and pass the literals through, so the
    # restarted runtime boots with exactly the resolved config the tests use.
    from tests.conftest import _resolve_env_value

    child_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CLOUD_DOG__NOTIFY__")
    }
    for key, value in os.environ.items():
        if key.startswith("CLOUD_DOG__NOTIFY__"):
            child_env[key] = _resolve_env_value(value)
    if overrides:
        child_env.update({key: str(value) for key, value in overrides.items()})
    commands = [
        ["./server_control.sh", "--env", env_file, "stop", target],
        ["./server_control.sh", "--env", env_file, "start", target],
    ]
    outputs = []
    for command in commands:
        result = subprocess.run(
            command,
            cwd=str(project_root),
            env=child_env,
            text=True,
            capture_output=True,
            check=False,
        )
        outputs.append((command, result))
        if result.returncode != 0:
            break
    assert outputs[-1][1].returncode == 0, "\n".join(
        f"Command failed: {' '.join(command)}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        for command, result in outputs
    )
    _wait_for_runtime_health(
        base_url,
        api_key,
        timeout,
        max_wait_seconds=max_wait_seconds,
    )
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_message_submission_returns_immediately(api_client, test_email, test_message_path, default_channel, test_config):
    """V25.21: Message submission returns immediately (< configured threshold)."""

    print("\n" + "=" * 80)
    print("TEST: Message Submission Returns Immediately")
    print("=" * 80)

    max_submit_seconds = _get_max_submit_seconds(test_config)

    # Read test message
    news_content = read_test_message(test_message_path)

    # Create message with LLM formatting requirement (French translation)
    message_payload = {
        "audience_type": "personalised",
        "destinations": [
            {
                "channel": default_channel,
                "address": test_email,
                "preferences": {"language": "fr", "content_style": "html"},
            }
        ],
        "content": [
            {
                "type": "text",
                "body": f"Please provide a summary in French of the following content:\n\n{news_content[:2000]}",
            }
        ],
        "options": {"subject": "Test - Immediate Submission"},
    }

    print(f"📧 Sending to: {test_email}")
    print(f"📄 Content length: {len(news_content[:2000])} characters")
    print(f"⏳ Submitting message (should return in < {max_submit_seconds}s)...")

    # Measure submission time
    start_time = time.time()
    response = api_client.post("/messages", json=message_payload)
    submission_time = time.time() - start_time

    print(f"⏱️  Submission time: {submission_time:.2f} seconds")

    # Should return 201 in < threshold seconds
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    assert submission_time < max_submit_seconds, (
        f"Submission took {submission_time:.2f}s, should be < {max_submit_seconds}s"
    )

    result = response.json()
    message_id = result.get("message_id")
    message_guid = result.get("guid")
    status = result.get("status", "unknown")

    print(f"✅ Message created: ID={message_id}, GUID={message_guid}, Status={status}")
    print(f"✅ Submission completed in {submission_time:.2f} seconds (non-blocking)")

    # Verify message is queued
    assert status == "queued", f"Expected status 'queued', got '{status}'"
    assert message_id is not None, "Message ID should be returned"
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_message_created_when_llm_unavailable(api_client, test_email, default_channel, test_config):
    """V25.22: Message created even when LLM unavailable."""

    print("\n" + "=" * 80)
    print("TEST: Message Created When LLM Unavailable")
    print("=" * 80)

    max_submit_seconds = _get_max_submit_seconds(test_config)

    # Check LLM status first
    llm_status = api_client.get("/llm/status")
    if llm_status.status_code == 200:
        status_data = llm_status.json()
        print(
            f"📊 LLM Status: available={status_data.get('available')}, "
            f"queue={status_data.get('queue_length')}"
        )

    # Create message (should work regardless of LLM availability)
    message_payload = {
        "audience_type": "personalised",
        "destinations": [
            {"channel": default_channel, "address": test_email, "preferences": {"language": "fr"}}
        ],
        "content": [{"type": "text", "body": "Test message for LLM unavailable scenario"}],
    }

    print("⏳ Creating message (LLM may be busy)...")
    start_time = time.time()
    response = api_client.post("/messages", json=message_payload)
    submission_time = time.time() - start_time

    assert response.status_code == 201, f"Message should be created even if LLM is busy: {response.status_code}"
    assert submission_time < max_submit_seconds, (
        f"Submission should be fast: {submission_time:.2f}s (limit {max_submit_seconds}s)"
    )

    result = response.json()
    message_id = result.get("message_id")

    print(f"✅ Message created: ID={message_id} (submission time: {submission_time:.2f}s)")
    print("✅ Message will be processed when LLM becomes available")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_multiple_messages_queued_correctly(api_client, test_email, default_channel, test_config):
    """V25.23: Multiple messages queued correctly."""

    print("\n" + "=" * 80)
    print("TEST: Multiple Messages Queued Correctly")
    print("=" * 80)

    max_submit_seconds = _get_max_submit_seconds(test_config)
    message_ids = []

    # Create 3 messages quickly
    for i in range(3):
        message_payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": default_channel, "address": test_email, "preferences": {"language": "fr"}}
            ],
            "content": [{"type": "text", "body": f"Test message {i+1} for queue test"}],
            "options": {"subject": f"Queue Test Message {i+1}"},
        }

        start_time = time.time()
        response = api_client.post("/messages", json=message_payload)
        submission_time = time.time() - start_time

        assert response.status_code == 201, f"Message {i+1} creation failed: {response.status_code}"
        assert submission_time < max_submit_seconds, (
            f"Message {i+1} submission too slow: {submission_time:.2f}s (limit {max_submit_seconds}s)"
        )

        result = response.json()
        message_id = result.get("message_id")
        message_ids.append(message_id)

        print(f"✅ Message {i+1}: ID={message_id} (submission: {submission_time:.2f}s)")

    # Check LLM queue status
    llm_status = api_client.get("/llm/status")
    if llm_status.status_code == 200:
        status_data = llm_status.json()
        queue_length = status_data.get("queue_length", 0)
        print(f"📊 LLM Queue: {queue_length} messages waiting")
        print(f"✅ All {len(message_ids)} messages created successfully")
        print(f"✅ Messages will be processed in order: {message_ids}")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_estimated_delivery_time_included(api_client, test_email, default_channel, test_config):
    """V25.24: estimated_delivery_time included when LLM busy."""

    print("\n" + "=" * 80)
    print("TEST: Estimated Delivery Time Included")
    print("=" * 80)

    # Check LLM status
    llm_status = api_client.get("/llm/status")
    assert llm_status.status_code == 200, "Failed to get LLM status"
    status_data = llm_status.json()

    print(f"📊 LLM Status: available={status_data.get('available')}, queue={status_data.get('queue_length')}")

    # Create message
    message_payload = {
        "audience_type": "personalised",
        "destinations": [
            {"channel": default_channel, "address": test_email, "preferences": {"language": "fr"}}
        ],
        "content": [{"type": "text", "body": "Test message for estimated delivery time"}],
    }

    response = api_client.post("/messages", json=message_payload)
    assert response.status_code == 201, f"Message creation failed: {response.status_code}"

    result = response.json()

    # If LLM is busy, estimated_delivery_time should be included
    if not status_data.get("available") and status_data.get("queue_length", 0) > 0:
        assert "estimated_delivery_time" in result, "estimated_delivery_time should be included when LLM is busy"
        estimated_time = result.get("estimated_delivery_time")
        print(f"✅ Estimated delivery time included: {estimated_time}")
    else:
        print("ℹ️  LLM is available, estimated_delivery_time may not be included")
        if "estimated_delivery_time" in result:
            print(f"   (But it was included: {result.get('estimated_delivery_time')})")

    message_id = result.get("message_id")
    print(f"✅ Message created: ID={message_id}")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


def test_message_submission_rejects_when_delivery_queue_is_full(
    test_email,
    default_channel,
    test_config,
):
    """Queue saturation should return 503 with Retry-After once the configured backlog limit is exceeded."""

    runtime_env_file = (
        str(test_config.get("app.env_file") or "").strip()
        or os.environ.get("CLOUD_DOG__NOTIFY__APP__ENV_FILE", "").strip()
        or str(getattr(test_config, "env_file", "")).strip()
    )
    if not runtime_env_file:
        pytest.fail("❌ HARD FAIL: app.env_file unavailable for runtime restart test")

    override_env = {
        "CLOUD_DOG__NOTIFY__DELIVERY__MAX_QUEUED": "1",
        "CLOUD_DOG__NOTIFY__DELIVERY_WORKER__ENABLED": "false",
    }
    api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url")
    api_key = _require_value(test_config.get("api_server.api_key"), "api_server.api_key")
    api_timeout = _get_api_timeout(test_config)
    runtime_wait_seconds = _require_number(test_config, "api.timeout", number_type="float")
    created_message_ids: list[int] = []

    try:
        _restart_runtime_service(
            runtime_env_file,
            "api",
            override_env,
            base_url=api_base_url,
            api_key=api_key,
            timeout=api_timeout,
            max_wait_seconds=runtime_wait_seconds,
        )
        saturation_client = httpx.Client(
            base_url=api_base_url,
            headers={"X-API-Key": api_key},
            timeout=api_timeout,
        )

        payload = {
            "audience_type": "personalised",
            "destinations": [
                {"channel": default_channel, "address": test_email, "preferences": {"language": "en"}}
            ],
            "content": [{"type": "text", "body": "Queue limit saturation test"}],
        }

        try:
            first_response = saturation_client.post("/messages", json=payload)
            assert first_response.status_code == 201, (
                f"Expected first submission to queue successfully: {first_response.status_code} {first_response.text}"
            )
            first_message_id = first_response.json().get("message_id")
            if first_message_id is not None:
                created_message_ids.append(int(first_message_id))

            second_response = saturation_client.post("/messages", json=payload)
            assert second_response.status_code == 503, (
                f"Expected queue saturation 503, got {second_response.status_code}: {second_response.text}"
            )
            assert second_response.headers.get("Retry-After"), "Retry-After header missing on queue saturation response"
        finally:
            saturation_client.close()
    finally:
        _restart_runtime_service(
            runtime_env_file,
            "api",
            base_url=api_base_url,
            api_key=api_key,
            timeout=api_timeout,
            max_wait_seconds=runtime_wait_seconds,
        )
        restore_client = httpx.Client(
            base_url=api_base_url,
            headers={"X-API-Key": api_key},
            timeout=api_timeout,
        )
        try:
            for message_id in created_message_ids:
                try:
                    restore_client.post(f"/messages/{message_id}/cancel")
                except Exception:
                    pass
        finally:
            restore_client.close()

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.integration,
    pytest.mark.worker,
    pytest.mark.forensic,
    pytest.mark.no_llm_dependency,
    pytest.mark.smtp,
    pytest.mark.heavy,
]
