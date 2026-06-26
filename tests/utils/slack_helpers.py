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

import time
from typing import Any, Dict, Iterable, List

import httpx
import pytest


def require_slack_api_config(test_config: Any) -> tuple[str, str]:
    """Require Slack bot token + channel id for verification."""
    token = test_config.get("test.slack.bot_token")
    channel_id = test_config.get("test.slack.channel_id")
    if not token:
        pytest.fail(
            "Slack bot token missing. Add CLOUD_DOG__NOTIFY__TEST__SLACK__BOT_TOKEN=... to env file."
        )
    if not channel_id:
        pytest.fail(
            "Slack channel id missing. Add CLOUD_DOG__NOTIFY__TEST__SLACK__CHANNEL_ID=... to env file."
        )
    return str(token), str(channel_id)


def _extract_message_texts(message: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    if message.get("text"):
        texts.append(str(message["text"]))

    blocks = message.get("blocks") or []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") in ("section", "header"):
            text = (block.get("text") or {}).get("text")
            if text:
                texts.append(str(text))
        if block.get("type") == "context":
            for element in block.get("elements", []):
                if isinstance(element, dict) and element.get("type") in ("mrkdwn", "plain_text"):
                    text = element.get("text")
                    if text:
                        texts.append(str(text))
    return texts


def _slack_history(
    token: str,
    channel_id: str,
    *,
    oldest: float | None = None,
    limit: int = 200,
    request_timeout: float,
) -> Iterable[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    params: Dict[str, Any] = {"channel": channel_id, "limit": limit}
    if oldest is not None:
        params["oldest"] = str(oldest)
    messages: List[Dict[str, Any]] = []
    cursor = None
    pages = 0
    while True:
        if cursor:
            params["cursor"] = cursor
        resp = httpx.get(
            "https://slack.com/api/conversations.history",
            params=params,
            headers=headers,
            timeout=request_timeout,
        )
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "2"))
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            pytest.fail(f"Slack API error: {data.get('error')}")
        messages.extend(data.get("messages", []))
        pages += 1
        cursor = (data.get("response_metadata") or {}).get("next_cursor")
        if not data.get("has_more") or not cursor or pages >= 5:
            break
    return messages


def wait_for_slack_message(
    token: str,
    channel_id: str,
    marker: str,
    *,
    timeout: float = 360.0,
    poll_interval: float = 2.0,
    request_timeout: float,
    start_time: float | None = None,
) -> Dict[str, Any]:
    """Poll Slack history until a message containing marker is found."""
    start = time.time()
    # Avoid using "oldest" because local clock can drift from Slack.
    oldest = None
    while time.time() - start < timeout:
        for message in _slack_history(
            token,
            channel_id,
            oldest=oldest,
            request_timeout=request_timeout,
        ):
            texts = _extract_message_texts(message)
            if any(marker in t for t in texts):
                return message
        time.sleep(poll_interval)
    pytest.fail(f"Slack message with marker not found within {timeout}s: {marker}")


def assert_slack_mrkdwn_contains(message: Dict[str, Any], expected: str) -> None:
    texts = _extract_message_texts(message)
    combined = "\n".join(texts)
    assert expected in combined, f"Expected Slack message to contain: {expected}"
