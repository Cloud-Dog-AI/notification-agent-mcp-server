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
REAL Integration Tests for Slack Webhook Adapter

These tests use the REAL Slack webhook to verify actual Slack integration works.
Tests send real messages to the configured Slack channel via the API server.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import httpx
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.slack_helpers import (
    assert_slack_mrkdwn_contains,
    require_slack_api_config,
    wait_for_slack_message,
)
from tests.utils.test_helpers import check_test_dependencies


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


def _require_number(test_config: Any, key: str, *, number_type: str):
    value = test_config.get(key)
    if value is None or value == "":
        pytest.fail(f"Missing required configuration: {key}")
    try:
        return float(value) if number_type == "float" else int(value)
    except Exception as e:
        pytest.fail(f"{key} must be a {number_type}: {e}")


def _get_api_timeout(test_config: Any) -> httpx.Timeout:
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


def _get_slack_timeouts(test_config: Any) -> Tuple[float, float, float]:
    wait_timeout = test_config.get("test.slack.wait_timeout") or test_config.get("api.timeout")
    poll_interval = (
        test_config.get("test.slack.poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    request_timeout = (
        test_config.get("test.slack.request_timeout")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if wait_timeout is None or wait_timeout == "":
        pytest.fail(
            "Missing Slack wait timeout. Configure test.slack.wait_timeout or api.timeout in env file."
        )
    if poll_interval is None or poll_interval == "":
        pytest.fail(
            "Missing Slack poll interval. Configure test.slack.poll_interval, api.connect_timeout, or api.timeout in env file."
        )
    if request_timeout is None or request_timeout == "":
        pytest.fail(
            "Missing Slack request timeout. Configure test.slack.request_timeout, api.connect_timeout, or api.timeout in env file."
        )
    return float(wait_timeout), float(poll_interval), float(request_timeout)


def _get_delivery_timeouts(test_config: Any) -> Tuple[float, float]:
    delivery_timeout = (
        test_config.get("test.slack.delivery_timeout")
        or test_config.get("api.timeout")
    )
    delivery_poll_interval = (
        test_config.get("test.slack.delivery_poll_interval")
        or test_config.get("api.connect_timeout")
        or test_config.get("api.timeout")
    )
    if delivery_timeout is None or delivery_timeout == "":
        pytest.fail(
            "Missing delivery timeout. Configure test.slack.delivery_timeout or api.timeout in env file."
        )
    if delivery_poll_interval is None or delivery_poll_interval == "":
        pytest.fail(
            "Missing delivery poll interval. Configure test.slack.delivery_poll_interval, api.connect_timeout, or api.timeout."
        )
    return float(delivery_timeout), float(delivery_poll_interval)


async def _create_message(
    api_base_url: str,
    api_key: str,
    payload: Dict[str, Any],
    api_timeout: httpx.Timeout,
) -> int:
    async with httpx.AsyncClient(timeout=api_timeout) as client:
        response = await client.post(
            f"{api_base_url}/messages",
            json=payload,
            headers={"X-API-Key": api_key},
        )
    assert response.status_code == 201, f"Failed to create message: {response.status_code} - {response.text}"
    message_data = response.json()
    message_id = message_data.get("message_id") or message_data.get("id")
    assert message_id is not None, f"Missing message_id in response: {message_data}"
    return int(message_id)


async def _delete_message(api_base_url: str, api_key: str, message_id: int, api_timeout: httpx.Timeout) -> None:
    async with httpx.AsyncClient(timeout=api_timeout) as client:
        await client.delete(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key},
        )


async def _wait_for_delivery(
    api_base_url: str,
    api_key: str,
    message_id: int,
    *,
    api_timeout: httpx.Timeout,
    max_wait: float,
    poll_interval: float,
    expect_failure: bool = False,
) -> Dict[str, Any]:
    start = time.time()
    async with httpx.AsyncClient(timeout=api_timeout) as client:
        while time.time() - start < max_wait:
            response = await client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key},
            )
            if response.status_code == 200:
                items = response.json().get("items", [])
                if items:
                    delivery = items[0]
                    state = (delivery.get("state") or "").lower()
                    if state in ("sent", "delivered"):
                        return delivery
                    if state in (
                        "failed",
                        "soft_failed",
                        "hard_failed",
                        "ttl_expired",
                        "cancelled",
                        "canceled",
                    ):
                        if expect_failure:
                            return delivery
                        pytest.fail(f"Slack delivery failed: {delivery.get('last_error')}")
            await asyncio.sleep(poll_interval)
    pytest.fail("Timed out waiting for Slack delivery")


@pytest.fixture(scope="session")
def slack_endpoint(slack_config):
    endpoint = slack_config.get("endpoint")
    if not endpoint:
        pytest.fail("Slack webhook endpoint not configured. Check your env file.")
    return endpoint


@pytest.fixture(scope="session")
def slack_channel_name(slack_config):
    channel_name = slack_config.get("channel_name")
    if not channel_name:
        pytest.fail("test.slack_channel_name not configured. Check your env file.")
    return channel_name


@pytest.fixture(scope="session")
def api_base_url(test_config):
    return _require_value(test_config.get("api_server.base_url"), "api_server.base_url")


@pytest.fixture(scope="session")
def api_key(test_config):
    return _require_value(test_config.get("api_server.api_key"), "api_server.api_key")
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_real_slack_webhook_simple_message(
    api_base_url,
    api_key,
    slack_endpoint,
    slack_channel_name,
    test_config,
):
    marker = f"IT1.13 Simple {int(time.time())}"
    api_timeout = _get_api_timeout(test_config)
    delivery_timeout, delivery_poll_interval = _get_delivery_timeouts(test_config)
    wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)

    message_payload = {
        "audience_type": "broadcast",
        "destinations": [{"channel": slack_channel_name, "address": slack_endpoint}],
        "content": [{"type": "markdown", "body": f"REAL TEST: **{marker}**"}],
        "options": {"subject": f"IT1.13 Slack {marker}"},
    }

    message_id = await _create_message(api_base_url, api_key, message_payload, api_timeout)
    try:
        await _wait_for_delivery(
            api_base_url,
            api_key,
            message_id,
            api_timeout=api_timeout,
            max_wait=delivery_timeout,
            poll_interval=delivery_poll_interval,
        )

        token, channel_id = require_slack_api_config(test_config)
        slack_message = wait_for_slack_message(
            token,
            channel_id,
            marker,
            timeout=wait_timeout,
            poll_interval=poll_interval,
            request_timeout=request_timeout,
        )
        assert_slack_mrkdwn_contains(slack_message, f"*{marker}*")
    finally:
        await _delete_message(api_base_url, api_key, message_id, api_timeout)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_real_slack_webhook_with_blocks(
    api_base_url,
    api_key,
    slack_endpoint,
    slack_channel_name,
    test_config,
):
    marker = f"IT1.13 Blocks {int(time.time())}"
    api_timeout = _get_api_timeout(test_config)
    delivery_timeout, delivery_poll_interval = _get_delivery_timeouts(test_config)

    message_payload = {
        "audience_type": "broadcast",
        "destinations": [{"channel": slack_channel_name, "address": slack_endpoint}],
        "content": [
            {
                "type": "markdown",
                "body": f"# REAL TEST\n\n**{marker}**\n\nThis is a formatted block message.",
            }
        ],
        "options": {"subject": f"IT1.13 Slack Blocks {marker}"},
    }

    message_id = await _create_message(api_base_url, api_key, message_payload, api_timeout)
    try:
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            deliveries_response = await client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key},
            )
        assert deliveries_response.status_code == 200
        payload = deliveries_response.json()
        assert payload.get("total", 0) >= 1
    finally:
        await _delete_message(api_base_url, api_key, message_id, api_timeout)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_real_slack_webhook_long_message(
    api_base_url,
    api_key,
    slack_endpoint,
    slack_channel_name,
    test_config,
):
    api_timeout = _get_api_timeout(test_config)
    delivery_timeout, delivery_poll_interval = _get_delivery_timeouts(test_config)
    long_length = (
        test_config.get("test.slack.long_message_length")
        or test_config.get("test.slack_max_length")
    )
    if long_length is None or long_length == "":
        pytest.fail(
            "Missing long message length. Configure test.slack.long_message_length or test.slack_max_length in env file."
        )
    long_length = int(long_length)

    marker = f"IT1.13 Long {int(time.time())}"
    long_text = f"REAL TEST: **{marker}** - " + ("A" * long_length)

    message_payload = {
        "audience_type": "broadcast",
        "destinations": [{"channel": slack_channel_name, "address": slack_endpoint}],
        "content": [{"type": "markdown", "body": long_text}],
        "options": {"subject": f"IT1.13 Slack Long {marker}"},
    }

    message_id = await _create_message(api_base_url, api_key, message_payload, api_timeout)
    try:
        async with httpx.AsyncClient(timeout=api_timeout) as client:
            deliveries_response = await client.get(
                f"{api_base_url}/messages/{message_id}/deliveries",
                headers={"X-API-Key": api_key},
            )
        assert deliveries_response.status_code == 200
        payload = deliveries_response.json()
        assert payload.get("total", 0) >= 1
    finally:
        await _delete_message(api_base_url, api_key, message_id, api_timeout)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_real_slack_webhook_error_handling(
    api_base_url,
    api_key,
    slack_channel_name,
    test_config,
):
    invalid_url = _require_value(test_config.get("test.webhook.invalid_url"), "test.webhook.invalid_url")
    api_timeout = _get_api_timeout(test_config)
    delivery_timeout, delivery_poll_interval = _get_delivery_timeouts(test_config)

    marker = f"IT1.13 Error {int(time.time())}"
    message_payload = {
        "audience_type": "broadcast",
        "destinations": [{"channel": slack_channel_name, "address": invalid_url}],
        "content": [{"type": "markdown", "body": f"REAL TEST: **{marker}**"}],
        "options": {"subject": f"IT1.13 Slack Error {marker}"},
    }

    message_id = await _create_message(api_base_url, api_key, message_payload, api_timeout)
    try:
        delivery = await _wait_for_delivery(
            api_base_url,
            api_key,
            message_id,
            api_timeout=api_timeout,
            max_wait=delivery_timeout,
            poll_interval=delivery_poll_interval,
            expect_failure=True,
        )
        state = (delivery.get("state") or "").lower()
        assert state in (
            "failed",
            "soft_failed",
            "hard_failed",
            "ttl_expired",
            "cancelled",
            "canceled",
        ), f"Unexpected state: {state}"
    finally:
        await _delete_message(api_base_url, api_key, message_id, api_timeout)
@pytest.mark.IT
@pytest.mark.mcp
@pytest.mark.req("FR-026")


@pytest.mark.asyncio
async def test_real_slack_webhook_via_api(
    api_base_url,
    api_key,
    slack_endpoint,
    slack_channel_name,
    test_config,
):
    api_timeout = _get_api_timeout(test_config)
    delivery_timeout, delivery_poll_interval = _get_delivery_timeouts(test_config)
    wait_timeout, poll_interval, request_timeout = _get_slack_timeouts(test_config)

    marker = f"IT1.13 API {int(time.time())}"
    message_payload = {
        "audience_type": "broadcast",
        "destinations": [{"channel": slack_channel_name, "address": slack_endpoint}],
        "content": [{"type": "markdown", "body": f"REAL API TEST: **{marker}**"}],
        "options": {"subject": f"IT1.13 Slack API {marker}"},
    }

    message_id = await _create_message(api_base_url, api_key, message_payload, api_timeout)
    try:
        await _wait_for_delivery(
            api_base_url,
            api_key,
            message_id,
            api_timeout=api_timeout,
            max_wait=delivery_timeout,
            poll_interval=delivery_poll_interval,
        )

        token, channel_id = require_slack_api_config(test_config)
        slack_message = wait_for_slack_message(
            token,
            channel_id,
            marker,
            timeout=wait_timeout,
            poll_interval=poll_interval,
            request_timeout=request_timeout,
        )
        assert_slack_mrkdwn_contains(slack_message, f"*{marker}*")
    finally:
        await _delete_message(api_base_url, api_key, message_id, api_timeout)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.integration,
    pytest.mark.live_provider,
    pytest.mark.live_delivery,
    pytest.mark.no_llm_dependency,
    pytest.mark.heavy,
]
