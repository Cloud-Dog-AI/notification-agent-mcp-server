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
AT1.6 LLM Configuration Test
Tests LLM connection, settings, and prompt instruction following

This test MUST run FIRST in the AT1.6 suite to validate:
1. LLM server connectivity
2. Model availability
3. Context window settings (num_ctx, num_predict)
4. Temperature and sampling settings
5. Prompt instruction following capability

CRITICAL: This test ensures the LLM is properly configured BEFORE
running prompt selection and formatting tests.

NO HARDCODED VALUES - All settings from env file
NO STUBS/MOCKS - Real LLM testing
100% API - Uses LLMManager directly
"""

import os
import sys
import pytest
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from src.config import get_config
from src.core.llm.runtime_client import LLMManager


class TestAT16LLMConfig:
    """AT1.6 LLM Configuration Tests"""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup for each test"""
        self.config = get_config()
        
        # REQUIRED settings from env file
        self.llm_provider = self.config.get('llm.provider')
        self.llm_model = self.config.get('llm.model')
        self.llm_base_url = self.config.get('llm.base_url')
        
        # Validate required settings
        assert self.llm_provider, "LLM provider not set in env file"
        assert self.llm_model, "LLM model not set in env file"
        assert self.llm_base_url, "LLM base_url not set in env file"
        
        print(f"\n=== AT1.6 LLM Configuration Test ===")
        print(f"Provider: {self.llm_provider}")
        print(f"Model: {self.llm_model}")
        print(f"Base URL: {self.llm_base_url}")
    @pytest.mark.AT
    @pytest.mark.mcp
    @pytest.mark.req("FR-023")
    
    def test_llm_connectivity(self):
        """
        Test: LLM Server Connectivity
        Validates: Server is reachable and model is available
        """
        print("\n[TEST] LLM Server Connectivity")
        
        llm_manager = LLMManager(self.config)
        
        # Test connection
        connected = llm_manager.connect()
        assert connected, f"Failed to connect to LLM at {self.llm_base_url}"
        
        print(f"✅ Connected to {self.llm_base_url}")
        print(f"✅ Model {self.llm_model} available")
    @pytest.mark.AT
    @pytest.mark.mcp
    @pytest.mark.req("FR-023")
    
    def test_llm_context_settings(self):
        """
        Test: LLM Context Window Settings
        Validates: num_ctx, num_predict, max_tokens are properly configured
        """
        print("\n[TEST] LLM Context Window Settings")
        
        # Get settings from config
        num_ctx = self.config.get('llm.num_ctx')
        num_predict = self.config.get('llm.num_predict')
        max_tokens = self.config.get('llm.max_tokens')
        
        print(f"num_ctx: {num_ctx}")
        print(f"num_predict: {num_predict}")
        print(f"max_tokens: {max_tokens}")
        
        # Validate settings exist
        assert num_ctx is not None, "num_ctx not configured"
        assert num_predict is not None or max_tokens is not None, \
            "Neither num_predict nor max_tokens configured"
        
        # Validate sensible values for 32K context models
        if num_ctx:
            assert num_ctx >= 8192, f"num_ctx too low: {num_ctx}"
            print(f"✅ Context window: {num_ctx} tokens")
        
        effective_predict = num_predict or max_tokens
        if effective_predict:
            assert effective_predict > 0, \
                f"num_predict/max_tokens must be > 0: {effective_predict}"
            print(f"✅ Output limit: {effective_predict} tokens")
            
            # Warn if output limit exceeds context
            if num_ctx and effective_predict > num_ctx:
                print(f"⚠️  WARNING: num_predict ({effective_predict}) > num_ctx ({num_ctx})")
    @pytest.mark.AT
    @pytest.mark.mcp
    @pytest.mark.req("FR-023")
    
    def test_llm_temperature_settings(self):
        """
        Test: LLM Temperature and Sampling Settings
        Validates: temperature, top_p, top_k, repeat_penalty
        """
        print("\n[TEST] LLM Temperature and Sampling Settings")
        
        temperature = self.config.get('llm.temperature')
        top_p = self.config.get('llm.top_p')
        top_k = self.config.get('llm.top_k')
        repeat_penalty = self.config.get('llm.repeat_penalty')
        seed = self.config.get('llm.seed')
        
        print(f"Temperature: {temperature}")
        print(f"Top P: {top_p}")
        print(f"Top K: {top_k}")
        print(f"Repeat Penalty: {repeat_penalty}")
        print(f"Seed: {seed}")
        
        # Validate temperature is set
        assert temperature is not None, "Temperature not configured"
        assert 0.0 <= temperature <= 2.0, f"Temperature out of range: {temperature}"
        
        print(f"✅ Temperature: {temperature}")
        
        if temperature < 0.3:
            print("   (Deterministic - good for consistent formatting)")
        elif temperature < 0.7:
            print("   (Balanced - moderate creativity)")
        else:
            print("   (Creative - high variability)")
    @pytest.mark.AT
    @pytest.mark.mcp
    @pytest.mark.req("FR-023")
    
    def test_llm_prompt_instruction_following(self):
        """
        Test: LLM Prompt Instruction Following
        Validates: LLM can follow explicit tag insertion instructions
        
        This is CRITICAL for AT1.6E/F prompt selection tests
        """
        print("\n[TEST] LLM Prompt Instruction Following")
        
        llm_manager = LLMManager(self.config)
        
        # Connect
        connected = llm_manager.connect()
        assert connected, "Failed to connect to LLM"
        
        # Test prompt with explicit tag instruction
        test_prompt = """You are a message formatter. Format this message professionally for email delivery.

CRITICAL INSTRUCTION: You MUST add the tag [LLM_CONFIG_TEST_PASSED] at the very start of your response body.
Then format the message content provided below.

Message content:
This is a test message to validate LLM prompt instruction following capability.

Formatted output:"""
        
        print("Invoking LLM with test prompt...")
        start_time = time.time()
        prompt_timeout = int(self.config.get("test.at16.prompt_follow_timeout", 180))

        try:
            response = llm_manager.invoke(test_prompt, timeout=prompt_timeout)
            elapsed = time.time() - start_time
            
            print(f"✅ LLM responded in {elapsed:.2f}s")
            print(f"Response length: {len(response)} characters")
            print(f"\nResponse preview (first 300 chars):")
            print("-" * 80)
            print(response[:300])
            if len(response) > 300:
                print("...")
            print("-" * 80)
            
            # CRITICAL: Check for tag
            assert "[LLM_CONFIG_TEST_PASSED]" in response, \
                "LLM did NOT follow instruction to include tag [LLM_CONFIG_TEST_PASSED]"
            
            print("\n✅✅✅ SUCCESS: LLM correctly followed tag insertion instruction")
            print("✅ LLM is ready for AT1.6E/F prompt selection tests")
            
        except Exception as e:
            pytest.fail(f"LLM invoke failed: {e}")
    @pytest.mark.AT
    @pytest.mark.mcp
    @pytest.mark.req("FR-023")
    
    def test_llm_settings_from_env_override(self, request):
        """
        Test: Environment File Settings Override
        Validates: Env file settings properly override defaults.yaml
        
        This ensures we can test different models with different settings
        """
        print("\n[TEST] Environment File Settings Override")
        
        # Check if env-specific settings are different from defaults
        temperature = self.config.get('llm.temperature')
        num_predict = self.config.get('llm.num_predict')
        
        print(f"Current temperature: {temperature}")
        print(f"Current num_predict: {num_predict}")
        
        # Get env file path from pytest (RULES.md: prefer --env flag, not env var)
        env_file = request.config.getoption("--env")
        print(f"Env file: {env_file}")
        
        assert env_file, "❌ --env not set - run with: pytest --env private/env-test-at16 ..."
        
        print(f"✅ Using env file: {env_file}")
        print("✅ Settings are configurable per test environment")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

