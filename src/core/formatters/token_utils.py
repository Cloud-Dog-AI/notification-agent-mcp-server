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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: Enhanced LLM Formatter for Notification Agent MCP Server - Formats messages using LLM with prompt selection, automatic translation, channel restriction enforcement, and user preference application

Related Requirements: FR1.10, FR1.11
Covers: BR1.3
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: UT1.5, IT1.15, AT1.2

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import ast
import json
import math
import re
import time
from typing import Optional, Dict, Any, List

from src.core.cache_integration import (
    build_context_hash,
    build_model_config_hash,
    build_prompt_hash,
    cached_message_format,
    cached_prompt_render,
    cached_summary_generation,
    cached_translation,
    run_sync,
)
from src.core.prompts.prompt_manager import PromptManager
from src.core.llm.runtime_client import LLMManager
from src.core.users.user_manager import UserManager
from src.core.groups.group_manager import GroupManager
from src.core.formatters.format_converter import FormatConverter
from src.database.repositories import ChannelRepository
from src.database.db_manager import DatabaseManager
from src.config import get_config
from src.utils.logger import get_logger, get_context_logger

logger = get_logger(__name__)


"""Helpers extracted from llm_formatter for W28A-93.06."""

def _get_int_config(self, key: str) -> Optional[int]:
    value = self.config.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Invalid configuration: {key} must be an int ({exc})")

def _get_token_limits(self) -> Dict[str, int]:
    max_context = self._get_int_config("llm.num_ctx")
    if not max_context:
        raise RuntimeError("Missing required configuration: llm.num_ctx")
    max_output = self._get_int_config("llm.max_tokens") or self._get_int_config("llm.num_predict")
    if not max_output:
        raise RuntimeError("Missing required configuration: llm.max_tokens or llm.num_predict")
    if max_output >= max_context:
        adjusted_max_output = max_context // 2
        logger.warning(
            "Invalid token budget: num_ctx=%s, max_output=%s. "
            "Clamping max_output to %s to preserve input budget.",
            max_context,
            max_output,
            adjusted_max_output,
        )
        max_output = adjusted_max_output
    max_input = max_context - max_output
    if max_input <= 0:
        raise RuntimeError(
            f"Invalid token budget: num_ctx={max_context}, max_output={max_output}"
        )
    return {
        "max_context": max_context,
        "max_input": max_input,
        "max_output": max_output,
    }

def _get_chars_per_token(self) -> float:
    value = self.config.get("llm.token_estimate_chars_per_token")
    if value is None or value == "":
        raise RuntimeError("Missing required configuration: llm.token_estimate_chars_per_token")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid configuration: llm.token_estimate_chars_per_token must be a float ({exc})"
        )
    if parsed <= 0:
        raise RuntimeError("Invalid configuration: llm.token_estimate_chars_per_token must be > 0")
    return parsed

def _estimate_tokens(self, text: str) -> int:
    if not text:
        return 0
    chars_per_token = self._get_chars_per_token()
    return int(math.ceil(len(text) / chars_per_token))

def _chunk_text_by_tokens(self, text: str, max_tokens: int) -> List[str]:
    if not text:
        return [""]
    if max_tokens <= 0:
        raise RuntimeError("Chunking error: max_tokens must be > 0")
    chars_per_token = self._get_chars_per_token()
    max_chars = int(max_tokens * chars_per_token)
    if max_chars <= 0:
        raise RuntimeError("Chunking error: max_chars must be > 0")
    if len(text) <= max_chars:
        return [text]

    parts = re.split(r"(\n\s*\n)", text)
    chunks: List[str] = []
    current = ""
    for part in parts:
        if len(current) + len(part) > max_chars and current:
            chunks.append(current.strip())
            current = part
        else:
            current += part
    if current.strip():
        chunks.append(current.strip())

    final_chunks: List[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            for idx in range(0, len(chunk), max_chars):
                final_chunks.append(chunk[idx:idx + max_chars].strip())
    return [c for c in final_chunks if c]

__all__ = [
    "_get_int_config",
    "_get_token_limits",
    "_get_chars_per_token",
    "_estimate_tokens",
    "_chunk_text_by_tokens",
]
