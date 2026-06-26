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

"""Notification-agent cache integration helpers built on cloud_dog_cache."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Awaitable, Callable, Dict, Optional

from cloud_dog_cache import cached, hash_config, hash_text


def build_context_hash(payload: Any) -> str:
    """Return a stable hash for request/content payloads."""
    return hash_text(_stable_text(payload))


def build_model_config_hash(config: Dict[str, Any]) -> str:
    """Return a stable hash for LLM/runtime configuration."""
    return hash_config(config)


def build_prompt_hash(prompt: Optional[str]) -> str:
    """Return a stable hash for rendered prompt text."""
    return hash_text(str(prompt or ""))


def run_sync(awaitable: Awaitable[Any]) -> Any:
    """Execute an awaitable from sync code, even if a loop already exists in this thread."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def _runner() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except BaseException as exc:  # noqa: BLE001
            error["exc"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "exc" in error:
        raise error["exc"]
    return result.get("value")


def _stable_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


@cached(
    ttl=3600,
    invalidate_on=("prompt_change",),
    key_params=("channel_type", "target_language", "context_hash", "prompt_hash"),
    context_hash_param="context_hash",
    prompt_hash_param="prompt_hash",
)
async def cached_prompt_render(
    *,
    channel_type: str,
    target_language: str,
    context_hash: str,
    prompt_hash: str,
    render_fn: Callable[[], str],
) -> str:
    """Cache rendered prompt templates."""
    return render_fn()


@cached(
    ttl=3600,
    invalidate_on=("config_change",),
    key_params=(
        "target_language",
        "allow_pivot",
        "enforce_target_output",
        "context_hash",
        "model_config_hash",
    ),
    context_hash_param="context_hash",
    model_config_hash_param="model_config_hash",
)
async def cached_translation(
    *,
    target_language: str,
    allow_pivot: bool,
    enforce_target_output: bool,
    context_hash: str,
    model_config_hash: str,
    translate_fn: Callable[[], str],
) -> str:
    """Cache translated output for identical text/language/config inputs."""
    return translate_fn()


@cached(
    ttl=3600,
    invalidate_on=("config_change", "prompt_change"),
    key_params=(
        "channel_type",
        "target_language",
        "max_length",
        "context_hash",
        "model_config_hash",
        "prompt_hash",
    ),
    context_hash_param="context_hash",
    model_config_hash_param="model_config_hash",
    prompt_hash_param="prompt_hash",
)
async def cached_message_format(
    *,
    channel_type: str,
    target_language: str,
    max_length: int,
    context_hash: str,
    model_config_hash: str,
    prompt_hash: str,
    format_fn: Callable[[], str],
) -> str:
    """Cache formatted LLM output for identical inputs."""
    return format_fn()


@cached(
    ttl=3600,
    invalidate_on=("config_change", "prompt_change"),
    key_params=(
        "channel_type",
        "target_language",
        "max_length",
        "context_hash",
        "model_config_hash",
    ),
    context_hash_param="context_hash",
    model_config_hash_param="model_config_hash",
)
async def cached_summary_generation(
    *,
    channel_type: str,
    target_language: str,
    max_length: int,
    context_hash: str,
    model_config_hash: str,
    summarize_fn: Callable[[], str],
) -> str:
    """Cache summarization results for identical content/config inputs."""
    return summarize_fn()
