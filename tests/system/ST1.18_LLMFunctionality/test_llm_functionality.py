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
System Test: LLM Functionality Verification

Tests that the LLM can:
1. Summarize content
2. Translate content to different languages
3. Format content (Markdown/HTML)

Uses:
- Env settings from --env flag (e.g., private/env-test)
- Prompt file path from env: CLOUD_DOG__NOTIFY__TEST__LLM_PROMPT_FILE
- Test content file path from env: CLOUD_DOG__NOTIFY__TEST__LLM_CONTENT_FILE
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
# From tests/system/ST1.18_LLMFunctionality/test_llm_functionality.py
# We need to go up 4 levels: ST1.18_LLMFunctionality -> system -> test -> project_root
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config, RuntimeConfig
from src.core.llm.runtime_client import LLMManager
from tests.utils.test_helpers import check_test_dependencies


def _get_timeout(test_config, key: str, fallback_key: str, default: int) -> int:
    value = test_config.get(key)
    if value is None or value == "":
        value = test_config.get(fallback_key)
    if value is None or value == "":
        return default
    return int(value)


@pytest.fixture(scope="session")
def llm_config(test_config):
    """Get LLM configuration from test config - supports all LLM parameters"""
    config = {
        "provider": test_config.get("llm.provider"),
        "base_url": test_config.get("llm.base_url"),
        "model": test_config.get("llm.model"),
        "temperature": test_config.get("llm.temperature", 0.1),
        "max_tokens": test_config.get("llm.max_tokens", 32768),
        "query_timeout": test_config.get("llm.query_timeout", 480),
        "auto_pull": test_config.get("llm.auto_pull", True),
        "model_load_timeout": test_config.get("llm.model_load_timeout", 600),
    }
    
    # Ollama-specific parameters
    if config["provider"].lower() == "ollama":
        config["num_ctx"] = test_config.get("llm.num_ctx") or test_config.get("llm.context_window", 32768)
        config["num_predict"] = test_config.get("llm.num_predict") or config["max_tokens"]
        config["top_p"] = test_config.get("llm.top_p")
        config["top_k"] = test_config.get("llm.top_k")
        config["repeat_penalty"] = test_config.get("llm.repeat_penalty")
        config["mirostat"] = test_config.get("llm.mirostat", 0)
        config["mirostat_tau"] = test_config.get("llm.mirostat_tau", 5.0)
        config["mirostat_eta"] = test_config.get("llm.mirostat_eta", 0.1)
        config["seed"] = test_config.get("llm.seed")
        config["stop"] = test_config.get("llm.stop")
        config["ignore_tls"] = test_config.get("llm.ignore_tls", False)
    
    # OpenAI-compatible parameters
    if config["provider"].lower() in ["openai", "azure"]:
        config["api_key"] = test_config.get("llm.openai_api_key") or test_config.get("llm.key")
        if config["provider"].lower() == "azure":
            config["azure_openai_endpoint"] = test_config.get("llm.azure_openai_endpoint") or config["base_url"]
            config["azure_openai_api_version"] = test_config.get("llm.azure_openai_api_version", "2024-02-15-preview")
    
    return config


@pytest.fixture(scope="session")
def prompt_file_path(test_config):
    """Get prompt file path from config"""
    prompt_file = test_config.get("test.llm_prompt_file")
    if not prompt_file:
        pytest.skip("LLM prompt file not configured (test.llm_prompt_file)")
    
    prompt_path = Path(prompt_file)
    if not prompt_path.is_absolute():
        # Relative to project root
        prompt_path = project_root / prompt_path
    
    if not prompt_path.exists():
        pytest.fail(f"LLM prompt file not found: {prompt_path}")
    
    return prompt_path


@pytest.fixture(scope="session")
def content_file_path(test_config):
    """Get test content file path from config"""
    content_file = test_config.get("test.llm_content_file")
    if not content_file:
        pytest.skip("LLM content file not configured (test.llm_content_file)")
    
    content_path = Path(content_file)
    if not content_path.is_absolute():
        # Relative to project root
        content_path = project_root / content_path
    
    if not content_path.exists():
        pytest.fail(f"LLM content file not found: {content_path}")
    
    return content_path


@pytest.fixture(scope="session")
def llm_manager(test_config, llm_config):
    """Initialize and connect LLM manager using test_config (reuses existing LLMManager code)"""
    # Check dependencies first
    check_test_dependencies(
        requires_llm=True,
        requires_api=False,
        requires_smtp=False,
        test_name="test_llm_functionality"
    )
    # Use test_config directly - LLMManager will read all parameters from it
    # This ensures we're using the exact same code path as the application
    manager = LLMManager(test_config)
    
    # Connect to LLM
    if not manager.connect():
        pytest.fail(f"Failed to connect to LLM provider: {llm_config['provider']}")
    
    if not manager.llm:
        pytest.fail("LLM manager initialized but llm instance is None")
    
    # Log LLM configuration for debugging
    print(f"\n📋 LLM Configuration:")
    print(f"   Provider: {llm_config['provider']}")
    print(f"   Model: {llm_config['model']}")
    print(f"   Base URL: {llm_config['base_url']}")
    print(f"   Temperature: {llm_config['temperature']}")
    print(f"   Max Tokens: {llm_config['max_tokens']}")
    if llm_config["provider"].lower() == "ollama":
        print(f"   Num Ctx: {llm_config.get('num_ctx', 'default')}")
        print(f"   Num Predict: {llm_config.get('num_predict', 'default')}")
        if llm_config.get("top_p"):
            print(f"   Top P: {llm_config['top_p']}")
        if llm_config.get("top_k"):
            print(f"   Top K: {llm_config['top_k']}")
        if llm_config.get("repeat_penalty"):
            print(f"   Repeat Penalty: {llm_config['repeat_penalty']}")
    
    return manager
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


@pytest.fixture(scope="session")
def test_content(content_file_path):
    """Load test content from file"""
    with open(content_file_path, 'r', encoding='utf-8') as f:
        return f.read()
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


@pytest.fixture(scope="session")
def test_prompt(prompt_file_path):
    """Load test prompt from file"""
    with open(prompt_file_path, 'r', encoding='utf-8') as f:
        return f.read()
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_connection(llm_manager, test_config):
    """Test 1: Verify LLM connection and basic response"""
    print("\n" + "="*80)
    print("TEST 1: LLM Connection and Basic Response")
    print("="*80)
    
    test_prompt = "Say 'OK' if you can hear me. Respond with exactly: OK"
    timeout = _get_timeout(test_config, "test.llm_connection_timeout", "llm.query_timeout", 120)
    response = llm_manager.invoke(test_prompt, timeout=timeout)
    
    print(f"✅ LLM Response: {response[:200]}")
    assert response is not None, "LLM returned None"
    assert len(response) > 0, "LLM returned empty response"
    assert "OK" in response.upper(), f"LLM did not respond with OK. Got: {response[:100]}"
    
    print("✅ TEST 1 PASSED: LLM connection working")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_translation(llm_manager, test_content, test_prompt, test_config):
    """Test 2: Verify LLM can translate content to French"""
    print("\n" + "="*80)
    print("TEST 2: LLM Translation (English to French)")
    print("="*80)
    
    # Build prompt with translation instruction at BEGINNING (more effective)
    translation_instruction = """
═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENT - MUST FOLLOW EXACTLY  ⚠️
═══════════════════════════════════════════════════════════

1. LANGUAGE: You MUST write the ENTIRE response in French (NOT English)
   - All text MUST be in French
   - Subject line MUST be in French
   - Body content MUST be in French
   - Do NOT use any English words or phrases
   - Translate EVERYTHING to French

═══════════════════════════════════════════════════════════
"""
    
    # Put instructions at BEGINNING for better LLM attention
    full_prompt = f"{translation_instruction}\n\n{test_prompt}\n\nContent to translate:\n{test_content[:500]}"
    
    print(f"📝 Sending translation request (first 200 chars of prompt)...")
    print(f"   {full_prompt[:200]}...")
    
    timeout = _get_timeout(test_config, "test.llm_translation_timeout", "llm.translation_timeout", 240)
    response = llm_manager.invoke(full_prompt, timeout=timeout)
    
    print(f"✅ LLM Response (first 300 chars): {response[:300]}")
    
    # Check for French indicators - look for common French words and patterns
    french_indicators = [
        "ceci", "c'est", "pour", "système", "notification", "contenu", "message",
        "test", "paragraphes", "capacité", "traiter", "formater", "doit",
        "traduction", "formatage", "synthèse", "français", "langue", "texte"
    ]
    english_indicators = ["this is", "system", "notification", "content", "message", "test", "paragraphs"]
    
    response_lower = response.lower()
    # Count French indicators
    french_count = sum(1 for word in french_indicators if word in response_lower)
    # Check for common French patterns (articles, prepositions)
    has_french_patterns = any(pattern in response_lower for pattern in ["de ", "du ", "des ", "le ", "la ", "les ", "un ", "une "])
    
    # Response is in French if it has French indicators or patterns
    is_french = french_count >= 3 or (has_french_patterns and french_count >= 1)
    
    assert is_french, f"Response does not appear to be in French. Found {french_count} French indicators. Response: {response[:300]}"
    
    print("✅ TEST 2 PASSED: LLM translation working")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_formatting(llm_manager, test_content, test_prompt, test_config):
    """Test 3: Verify LLM can format content as Markdown"""
    print("\n" + "="*80)
    print("TEST 3: LLM Formatting (Markdown)")
    print("="*80)
    
    # Build prompt with formatting instruction at BEGINNING
    format_instruction = """
═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENT - MUST FOLLOW EXACTLY  ⚠️
═══════════════════════════════════════════════════════════

2. FORMAT: You MUST format the output as Markdown
   - Use markdown syntax: # headers, ## subheaders, - lists, **bold**, *italic*
   - Use blank lines between paragraphs
   - The system will convert Markdown to HTML automatically
   - Do NOT output HTML directly - use Markdown only

═══════════════════════════════════════════════════════════
"""
    
    # Put instructions at BEGINNING for better LLM attention
    full_prompt = f"{format_instruction}\n\n{test_prompt}\n\nContent to format:\n{test_content[:500]}"
    
    print(f"📝 Sending formatting request (first 200 chars of prompt)...")
    print(f"   {full_prompt[:200]}...")
    
    timeout = _get_timeout(test_config, "test.llm_formatting_timeout", "llm.formatting_timeout", 240)
    response = llm_manager.invoke(full_prompt, timeout=timeout)
    
    print(f"✅ LLM Response (first 300 chars): {response[:300]}")
    
    # Check for Markdown indicators
    markdown_indicators = ["#", "##", "###", "**", "*", "- ", "1. ", "2. "]

    def _has_markdown(text: str) -> bool:
        return any(indicator in text for indicator in markdown_indicators)

    has_markdown = _has_markdown(response)
    if not has_markdown:
        # Retry once with stricter structural requirements to reduce
        # model variance while preserving real-runtime validation.
        retry_prompt = (
            "RETRY - STRICT FORMAT REQUIREMENT:\n"
            "- Output MUST be Markdown.\n"
            "- Include at least one heading starting with '# '.\n"
            "- Include at least one bullet line starting with '- '.\n"
            "- Output ONLY the final markdown content.\n\n"
            f"{full_prompt}"
        )
        response = llm_manager.invoke(retry_prompt, timeout=timeout)
        print(f"✅ LLM Retry Response (first 300 chars): {response[:300]}")
        has_markdown = _has_markdown(response)

    assert has_markdown, f"Response does not appear to be in Markdown format. Response: {response[:200]}"
    
    print("✅ TEST 3 PASSED: LLM formatting working")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_summarization(llm_manager, test_content, test_prompt, test_config):
    """Test 4: Verify LLM can summarize content with max_length constraint (using actual formatter prompt)"""
    print("\n" + "="*80)
    print("TEST 4: LLM Summarization with max_length constraint")
    print("="*80)
    
    # Use max_length=1000 (200 words) - same as channel restriction
    max_length = 1000
    target_words = max_length // 5  # 200 words
    
    # Get summarization prompt template from config (same as used in llm_formatter)
    from src.config import get_config
    
    config = get_config()
    prompt_template = config.get("llm.summarization_prompt_template")
    
    if not prompt_template:
        # Fallback to hardcoded template if not in config
        prompt_template = """═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENT - MUST FOLLOW EXACTLY  ⚠️
═══════════════════════════════════════════════════════════════

TASK: Create a concise summary of the content below

CRITICAL REQUIREMENTS:
- Maximum length: {max_length} characters (approximately {target_words} words)
- The summary MUST be written in {target_lang_name} (NOT English)
- Preserve the most important information and key facts
- Maintain critical details, numbers, and actionable points
- Extract and condense key points - DO NOT just truncate the text
- Format appropriately for {channel_type} channel: {channel_format_hint}
- DO NOT exceed {max_length} characters under any circumstances
- DO NOT include reasoning, thinking, or meta-commentary
- Output ONLY the summary, nothing else

═══════════════════════════════════════════════════════════════

Content to summarize:
{content}

Summary (in {target_lang_name}, maximum {max_length} characters / {target_words} words):"""
    
    # Format the prompt template (same way llm_formatter does)
    full_prompt = prompt_template.format(
        max_length=max_length,
        target_words=target_words,
        target_lang_name="English",
        channel_type="slack",
        channel_format_hint="Use clear, concise formatting.",
        content=test_content
    )
    
    print(f"📝 Sending summarization request:")
    print(f"   Original content: {len(test_content)} chars")
    print(f"   Max length: {max_length} chars ({target_words} words)")
    print(f"   Prompt length: {len(full_prompt)} chars")
    print(f"   Prompt preview (first 500 chars):\n{full_prompt[:500]}...")
    
    timeout = _get_timeout(test_config, "test.llm_summarization_timeout", "llm.summarization_timeout", 240)
    response = llm_manager.invoke(full_prompt, timeout=timeout)
    
    print(f"\n✅ LLM Response:")
    print(f"   Length: {len(response)} chars, {len(response.split())} words")
    print(f"   First 300 chars: {response[:300]}")
    
    # Remove any reasoning/thinking blocks that LLM might include
    import re
    cleaned_response = response
    # Remove XML-style thinking blocks
    cleaned_response = re.sub(r'<[^>]*thinking[^>]*>.*?</[^>]*>', '', cleaned_response, flags=re.DOTALL | re.IGNORECASE)
    cleaned_response = re.sub(r'<[^>]*reasoning[^>]*>.*?</[^>]*>', '', cleaned_response, flags=re.DOTALL | re.IGNORECASE)
    # Remove hidden blocks
    cleaned_response = re.sub(r'hidden<[^>]*>.*?</[^>]*>', '', cleaned_response, flags=re.DOTALL | re.IGNORECASE)
    # Remove prompt text if LLM echoed it
    cleaned_response = re.sub(r'^Please provide a summary.*?:\s*', '', cleaned_response, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    cleaned_response = re.sub(r'^Create a concise summary.*?:\s*', '', cleaned_response, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    cleaned_response = cleaned_response.strip()
    
    print(f"\n📊 After cleaning:")
    print(f"   Length: {len(cleaned_response)} chars, {len(cleaned_response.split())} words")
    
    # CRITICAL: Check that summary respects max_length
    assert len(cleaned_response) <= max_length, \
        f"❌ CRITICAL: Summary ({len(cleaned_response)} chars) exceeds max_length ({max_length} chars). " \
        f"Response: {cleaned_response[:500]}"
    
    # Check that summary is shorter than original
    assert len(cleaned_response) < len(test_content), \
        f"Summary is not shorter than original. Summary: {len(cleaned_response)} chars (raw: {len(response)}), Original: {len(test_content)} chars"
    
    # Check that summary contains some content
    assert len(cleaned_response) > 50, f"Summary is too short: {len(cleaned_response)} chars"
    
    print(f"✅ TEST 4 PASSED: LLM summarization working (summary: {len(cleaned_response)} chars <= {max_length} chars)")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-025")


def test_llm_combined_instructions(llm_manager, test_content, test_prompt, test_config):
    """Test 5: Verify LLM can handle combined instructions (translate + format)"""
    print("\n" + "="*80)
    print("TEST 5: LLM Combined Instructions (Translate + Format)")
    print("="*80)
    
    # Build prompt with both translation and formatting instructions at BEGINNING
    combined_instruction = """
═══════════════════════════════════════════════════════════
⚠️  CRITICAL REQUIREMENTS - MUST FOLLOW EXACTLY  ⚠️
═══════════════════════════════════════════════════════════

1. LANGUAGE: You MUST write the ENTIRE response in French (NOT English)
   - All text MUST be in French
   - Subject line MUST be in French
   - Body content MUST be in French
   - Do NOT use any English words or phrases
   - Translate EVERYTHING to French

2. FORMAT: You MUST format the output as Markdown
   - Use markdown syntax: # headers, ## subheaders, - lists, **bold**, *italic*
   - Use blank lines between paragraphs
   - The system will convert Markdown to HTML automatically
   - Do NOT output HTML directly - use Markdown only

═══════════════════════════════════════════════════════════
"""
    
    # Put instructions at BEGINNING for better LLM attention
    full_prompt = f"{combined_instruction}\n\n{test_prompt}\n\nContent to translate and format:\n{test_content[:500]}"
    
    print(f"📝 Sending combined request (translate + format)...")
    
    timeout = _get_timeout(test_config, "test.llm_instruction_timeout", "llm.query_timeout", 240)
    response = llm_manager.invoke(full_prompt, timeout=timeout)
    
    print(f"✅ LLM Response (first 300 chars): {response[:300]}")
    
    # Check for French - use same improved detection as test_llm_translation
    french_indicators = [
        "ceci", "c'est", "pour", "système", "notification", "contenu", "message",
        "test", "paragraphes", "capacité", "traiter", "formater", "doit",
        "traduction", "formatage", "synthèse", "français", "langue", "texte"
    ]
    response_lower = response.lower()
    french_count = sum(1 for word in french_indicators if word in response_lower)
    has_french_patterns = any(pattern in response_lower for pattern in ["de ", "du ", "des ", "le ", "la ", "les ", "un ", "une "])
    is_french = french_count >= 3 or (has_french_patterns and french_count >= 1)
    
    # Check for Markdown
    markdown_indicators = ["#", "##", "**", "*", "- "]
    has_markdown = any(indicator in response for indicator in markdown_indicators)
    
    assert is_french, f"Response does not appear to be in French. Found {french_count} French indicators. Response: {response[:300]}"
    assert has_markdown, f"Response does not appear to be in Markdown format. Response: {response[:200]}"
    
    print("✅ TEST 5 PASSED: LLM combined instructions working")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.llm, pytest.mark.smtp, pytest.mark.slow]

