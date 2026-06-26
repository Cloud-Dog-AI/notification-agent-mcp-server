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
Tests for LLM Manager (T18 - LLM Integration)

V18.11-V18.15: LLM Manager tests against runtime client migration.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from src.config import RuntimeConfig
from src.core.llm.runtime_client import LLMManager


@pytest.fixture
def mock_config(test_config):
    """Mock config for LLM using env-driven values."""
    config = Mock(spec=RuntimeConfig)
    config.get = lambda key, default=None: test_config.get(key, default)
    return config


class TestLLMManager:
    """V18.11-V18.15: LLM Manager tests."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_v18_11_llm_manager_initialization(self, mock_config, test_config):
        """V18.11: LLM Manager initialization."""
        manager = LLMManager(mock_config)
        assert manager.provider == test_config.get("llm.provider")
        assert manager.llm is None
        assert manager.client is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    @patch("src.core.llm.runtime_client.get_llm_client")
    def test_v18_12_ollama_connection(self, mock_get_client, mock_config):
        """V18.12: Runtime client connection and health check."""
        mock_client = Mock()
        mock_client.health = AsyncMock(return_value=True)
        mock_get_client.return_value = mock_client

        manager = LLMManager(mock_config)
        result = manager.connect()

        assert result is True
        assert manager.client is mock_client
        assert manager.llm is manager
        mock_get_client.assert_called_once()
        mock_client.health.assert_awaited_once()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    @patch("src.core.llm.runtime_client.get_llm_client")
    def test_v18_13_ollama_with_parameters(self, mock_get_client, mock_config, test_config):
        """V18.13: Provider config mapping passed to client factory."""
        mock_client = Mock()
        mock_client.health = AsyncMock(return_value=True)
        mock_get_client.return_value = mock_client

        manager = LLMManager(mock_config)
        assert manager.connect() is True

        call_config = mock_get_client.call_args.args[0]
        provider = test_config.get("llm.provider")
        model = test_config.get("llm.model")
        base_url = test_config.get("llm.base_url")

        assert call_config["llm"]["default_provider"] in (provider, "openai_compat")
        provider_cfg = call_config["providers"][call_config["llm"]["default_provider"]]
        assert provider_cfg["model"] == model
        assert provider_cfg["base_url"] == base_url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    @patch("src.core.llm.runtime_client.get_llm_client")
    def test_v18_14_llm_invoke(self, mock_get_client, mock_config):
        """V18.14: LLM invoke method."""
        mock_client = Mock()
        mock_client.health = AsyncMock(return_value=True)
        mock_client.chat = AsyncMock(return_value=SimpleNamespace(content="Test response"))
        mock_get_client.return_value = mock_client

        manager = LLMManager(mock_config)
        assert manager.connect() is True

        result = manager.invoke("Test prompt", timeout=30)

        assert result == "Test response"
        mock_client.chat.assert_awaited_once()
        request_arg = mock_client.chat.call_args.args[0]
        assert request_arg.messages[0].content == "Test prompt"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    @patch("src.core.llm.runtime_client.get_llm_client")
    def test_v18_15_unsupported_provider(self, mock_get_client, mock_config):
        """V18.15: Unsupported provider handling."""
        mock_config.get = lambda key, default=None: {
            "llm.provider": "unsupported",
            "llm.base_url": "http://localhost:11434",
            "llm.model": "dummy",
        }.get(key, default)

        manager = LLMManager(mock_config)
        result = manager.connect()

        assert result is False
        assert manager.llm is None
        assert manager.client is None
        mock_get_client.assert_not_called()

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.llm, pytest.mark.fast]

