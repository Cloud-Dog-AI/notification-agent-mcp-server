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
Simple LLM Test Script
Tests different settings against qwen3:14b to find optimal configuration
"""

import pytest

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.config import get_config
from src.core.llm.runtime_client import LLMManager
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-024")

def test_llm_with_settings(test_name, prompt, content, settings_override=None):
    """Test LLM with specific settings"""
    
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)
    
    # Get config
    config = get_config()
    
    # Apply settings override
    if settings_override:
        print("\nSettings Override:")
        for key, value in settings_override.items():
            full_key = f"llm.{key}"
            print(f"  {key}: {value}")
            config.config[full_key] = value
    
    # Show current settings
    print("\nCurrent LLM Settings:")
    print(f"  Model: {config.get('llm.model')}")
    print(f"  Temperature: {config.get('llm.temperature')}")
    print(f"  Num Predict: {config.get('llm.num_predict', config.get('llm.max_tokens'))}")
    print(f"  Top P: {config.get('llm.top_p')}")
    print(f"  Top K: {config.get('llm.top_k')}")
    print(f"  Repeat Penalty: {config.get('llm.repeat_penalty')}")
    print(f"  Seed: {config.get('llm.seed')}")
    
    # Initialize LLM
    print("\nInitializing LLM...")
    llm_manager = LLMManager(config)
    if not llm_manager.connect():
        print("❌ Failed to connect to LLM")
        return None
    
    print("✅ LLM connected")
    
    # Build full prompt
    full_prompt = f"{prompt}\n\nContent to format:\n{content}\n\nFormatted output:"
    
    print(f"\nPrompt (first 200 chars):\n{full_prompt[:200]}...")
    
    # Invoke LLM
    print("\nInvoking LLM...")
    try:
        response = llm_manager.invoke(full_prompt, timeout=60)
        print(f"\n✅ LLM Response ({len(response)} chars):")
        print("-" * 80)
        print(response)
        print("-" * 80)
        
        # Check for tag
        if "[TEST_TAG_FOUND]" in response:
            print("\n✅✅✅ SUCCESS: Tag [TEST_TAG_FOUND] found in response!")
            return True
        else:
            print("\n❌ FAIL: Tag [TEST_TAG_FOUND] NOT found in response")
            return False
            
    except Exception as e:
        print(f"\n❌ LLM invoke failed: {e}")
        return None


def main():
    """Run LLM tests with different settings"""
    
    # Load environment
    env_file = os.path.join(os.path.dirname(__file__), 'env-llm-test')
    if os.path.exists(env_file):
        print(f"Loading environment from: {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes
                    value = value.strip('"').strip("'")
                    os.environ[key] = value
    
    # Get test prompt and content from env
    prompt = os.environ.get('LLM_TEST_PROMPT', 'Format this message professionally.')
    content = os.environ.get('LLM_TEST_CONTENT', 'Test message')
    
    results = {}
    
    # Test 1: Baseline (current settings from env)
    results['baseline'] = test_llm_with_settings(
        "Baseline (env settings)",
        prompt,
        content
    )
    
    # Test 2: Higher temperature
    results['temp_0.5'] = test_llm_with_settings(
        "Temperature 0.5",
        prompt,
        content,
        {'temperature': 0.5}
    )
    
    # Test 3: Higher num_predict
    results['predict_4096'] = test_llm_with_settings(
        "Num Predict 4096",
        prompt,
        content,
        {'num_predict': 4096, 'max_tokens': 4096}
    )
    
    # Test 4: No repeat penalty
    results['no_repeat_penalty'] = test_llm_with_settings(
        "Repeat Penalty 1.0 (disabled)",
        prompt,
        content,
        {'repeat_penalty': 1.0}
    )
    
    # Test 5: Top K sampling
    results['top_k_40'] = test_llm_with_settings(
        "Top K = 40",
        prompt,
        content,
        {'top_k': 40}
    )
    
    # Test 6: Combined optimal
    results['combined_optimal'] = test_llm_with_settings(
        "Combined: temp=0.3, predict=4096, repeat=1.0",
        prompt,
        content,
        {
            'temperature': 0.3,
            'num_predict': 4096,
            'max_tokens': 4096,
            'repeat_penalty': 1.0
        }
    )
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in results.items():
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else "⚠️  ERROR"
        print(f"{test_name:30s} {status}")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
