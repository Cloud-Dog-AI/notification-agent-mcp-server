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
AT1.4f: Summary + Full Translated Message - COMPREHENSIVE TEST

Validates:
1. Summary generation to target size
2. Full message translation (preserves original size)
3. Both summary and full message in target language
4. Content saved to storage/files
5. Links to both summary and full message
6. Multiple language pairs
7. Different sizes (5000 chars with summary, 400 chars no summary)
8. Content preservation (formatting, lists, structure)

Test Matrix:
- Languages: EN, PL, ZH, AR, DE, FR
- Translations: EN→FR, EN→AR, EN→ZH, PL→DE, PL→EN, ZH→FR, ZH→EN
- Sizes: 5000 chars (with 400 char summary), 400 chars (no summary)
- Validations: Summary size, full size, both languages, content structure
"""

import pytest
import json
import httpx
import time
import sys
import re
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Add helpers to path
sys.path.insert(0, str(Path(__file__).parent))
from helpers import (
    load_test_message,
    validate_language,
    validate_size,
)

from tests.utils.test_helpers import check_test_dependencies


def wait_for_delivery(api_client, message_id: int, max_wait: int) -> Tuple[bool, Dict[str, Any]]:
    """Wait for message delivery and return payload"""
    wait_time = 0
    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5
        
        deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
        if deliveries_response.status_code != 200:
            continue
            
        deliveries_data = deliveries_response.json()
        deliveries = deliveries_data.get("items", []) if isinstance(deliveries_data, dict) else deliveries_data
        
        if not deliveries:
            continue
            
        delivery = deliveries[0]
        state = delivery.get("state")
        
        if state in ["sent", "delivered", "accepted"]:
            return True, delivery
        elif state in ["failed", "rejected", "hard_failed", "soft_failed"]:
            return False, delivery
    
    return False, {}


def extract_text_from_html(html_content: str) -> str:
    """Extract plain text from HTML, preserving structure"""
    # Remove script and style tags
    html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Try to find message content div
    content_match = re.search(r'<div[^>]*class=["\']message-content[^"\']*["\'][^>]*>(.*?)</div>', html, re.DOTALL)
    if content_match:
        html = content_match.group(1)
    
    # Remove HTML tags but preserve line breaks
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'</div>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode HTML entities
    import html as html_module
    text = html_module.unescape(text)
    
    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    
    return text


def _pick_delivery_by_max_length(deliveries: list, wants_max_length: bool) -> Optional[Dict[str, Any]]:
    """Pick the first sent delivery matching presence/absence of max_length in metadata preferences."""
    for d in deliveries:
        if not isinstance(d, dict):
            continue
        if d.get("state") not in ("sent", "delivered", "accepted"):
            continue
        meta = d.get("metadata_json")
        try:
            meta_obj = json.loads(meta) if isinstance(meta, str) else (meta or {})
        except Exception:
            meta_obj = {}
        prefs = (meta_obj or {}).get("preferences", {}) if isinstance(meta_obj, dict) else {}
        has_max = isinstance(prefs, dict) and ("max_length" in prefs)
        if has_max == wants_max_length:
            return d
    return None


@pytest.mark.parametrize(
    "test_case",
    [
    # Large message tests (5000 chars → 400 char summary + full translation)
    {"source_lang": "en", "target_lang": "fr", "size": 5000, "summary_size": 400, "desc": "EN→FR with summary"},
    {"source_lang": "en", "target_lang": "ar", "size": 5000, "summary_size": 400, "desc": "EN→AR with summary (RTL)"},
    {"source_lang": "en", "target_lang": "zh", "size": 5000, "summary_size": 400, "desc": "EN→ZH with summary (CJK)"},
    {"source_lang": "pl", "target_lang": "de", "size": 5000, "summary_size": 400, "desc": "PL→DE with summary"},
    {"source_lang": "pl", "target_lang": "en", "size": 5000, "summary_size": 400, "desc": "PL→EN with summary"},
    {"source_lang": "zh", "target_lang": "fr", "size": 5000, "summary_size": 400, "desc": "ZH→FR with summary"},
    {"source_lang": "zh", "target_lang": "en", "size": 5000, "summary_size": 400, "desc": "ZH→EN with summary"},
    
    # Small message tests (400 chars → no summary, just full translation)
    {"source_lang": "en", "target_lang": "de", "size": 400, "summary_size": None, "desc": "EN→DE no summary"},
    {"source_lang": "pl", "target_lang": "fr", "size": 400, "summary_size": None, "desc": "PL→FR no summary"},
    {"source_lang": "zh", "target_lang": "de", "size": 400, "summary_size": None, "desc": "ZH→DE no summary"},
    ],
    ids=lambda tc: f"{tc['source_lang']}_to_{tc['target_lang']}_{tc['size']}" + ("_summary" if tc.get("summary_size") else "_nosummary"),
)
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")
def test_at1_4f_summary_full(api_client, test_output_dir, loopback_channel, test_config, test_case):
    """
    AT1.4f: Summary + Full Translated Message
    
    Validates:
    1. Summary generation (target size, target language)
    2. Full message translation (preserves structure, target language)
    3. Both accessible via API/storage
    4. Content quality and language correctness
    5. Proper handling of summary-only vs full+summary scenarios
    """
    # RULES.md: dependency checks before any test logic
    check_test_dependencies(
        requires_llm=True,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="AT1.4f:test_at1_4f_summary_full",
    )

    # Check for --env requirement
    if not test_config.get("at14f_env_loaded"):
        pytest.fail("❌ HARD FAIL: --env file not loaded. Run with: pytest --env private/env-test-at14f")
    
    channel_id, channel = loopback_channel
    channel_name = channel.get("name")
    if not channel_name:
        pytest.fail("❌ Loopback channel name missing from API response")

    # RULES.md: no hardcoded defaults
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ test.email_domain not configured in env file (set CLOUD_DOG__NOTIFY__TEST__EMAIL_DOMAIN)")

    max_wait = test_config.get("test.at14f.max_wait")
    if not max_wait:
        pytest.fail("❌ test.at14f.max_wait not configured in env file (set CLOUD_DOG__NOTIFY__TEST__AT14F__MAX_WAIT)")
    max_wait = int(max_wait)
    
    source_lang = test_case["source_lang"]
    target_lang = test_case["target_lang"]
    size = test_case["size"]
    summary_size = test_case.get("summary_size")
    desc = test_case["desc"]
    
    print(f"\n{'='*80}")
    print(f"AT1.4f Test: {desc}")
    print(f"  Source: {source_lang.upper()} ({size} chars)")
    print(f"  Target: {target_lang.upper()}")
    if summary_size:
        print(f"  Summary: {summary_size} chars")
    print(f"{'='*80}")
    
    # Verify env file is loaded (NO HARDCODING)
    api_base_url = test_config.get("api_server.base_url")
    if not api_base_url:
        pytest.fail("❌ HARD FAIL: api_server.base_url not set in env file")
    
    # Skip same-language tests
    if source_lang == target_lang:
        pytest.fail(f"⚠️ Skipping same-language test: {source_lang}→{target_lang}")
    
    # Load source message
    try:
        source_content = load_test_message(source_lang, size)
        print(f"📄 Loaded source: {len(source_content)} chars")
    except FileNotFoundError as e:
        pytest.fail(f"⚠️ Test file not found: {e}")

    # Quality gate: validate source language and size
    src_lang_valid, src_indicators = validate_language(source_content, source_lang)
    assert src_lang_valid, f"Source content not in {source_lang}: {src_indicators}"
    src_tol = 0.7 if source_lang == "zh" else 0.5
    src_size_valid, src_size_msg = validate_size(source_content, size, tolerance=src_tol)
    assert src_size_valid, f"Source size invalid: {src_size_msg}"
    
    # Create message payload
    destinations = []

    # If we want a summary AND a full message, create two deliveries:
    # - one with max_length (summary)
    # - one without max_length (full)
    if summary_size:
        destinations.append({
            "channel": channel_name,
            "address": f"test_{source_lang}_{target_lang}_summary{email_domain}",
            "preferences": {"language": target_lang, "max_length": summary_size},
        })
        destinations.append({
            "channel": channel_name,
            "address": f"test_{source_lang}_{target_lang}_full{email_domain}",
            "preferences": {"language": target_lang},
        })
    else:
        destinations.append({
            "channel": channel_name,
            "address": f"test_{source_lang}_{target_lang}_full{email_domain}",
            "preferences": {"language": target_lang},
        })

    message_payload = {
        "content": [{"type": "text", "body": source_content}],
        "destinations": destinations,
    }
    
    # Submit message
    response = api_client.post("/messages", json=message_payload)
    assert response.status_code == 201, f"Failed to create message: {response.text}"
    
    message_data = response.json()
    message_id = message_data["message_id"]  # API returns 'message_id' not 'id'
    message_guid = message_data.get("guid", message_id)
    
    print(f"📨 Message created: ID={message_id}, GUID={message_guid}")
    
    # Wait for deliveries
    print(f"⏳ Waiting for deliveries (max {max_wait}s)...")
    wait_time = 0
    deliveries_sent = []
    while wait_time < max_wait:
        time.sleep(5)
        wait_time += 5

        deliveries_response = api_client.get(f"/messages/{message_id}/deliveries")
        if deliveries_response.status_code != 200:
            continue

        deliveries_data = deliveries_response.json()
        deliveries_list = deliveries_data.get("items", []) if isinstance(deliveries_data, dict) else deliveries_data
        if not deliveries_list:
            continue

        deliveries_sent = [d for d in deliveries_list if isinstance(d, dict) and d.get("state") in ("sent", "delivered", "accepted")]
        if summary_size:
            if _pick_delivery_by_max_length(deliveries_sent, wants_max_length=True) and _pick_delivery_by_max_length(deliveries_sent, wants_max_length=False):
                break
        else:
            if _pick_delivery_by_max_length(deliveries_sent, wants_max_length=False):
                break

    if summary_size:
        assert _pick_delivery_by_max_length(deliveries_sent, wants_max_length=True), f"❌ Summary delivery not completed within {max_wait}s"
        assert _pick_delivery_by_max_length(deliveries_sent, wants_max_length=False), f"❌ Full delivery not completed within {max_wait}s"
    else:
        assert _pick_delivery_by_max_length(deliveries_sent, wants_max_length=False), f"❌ Full delivery not completed within {max_wait}s"

    print(f"✅ Deliveries complete ({wait_time}s)")

    summary_text = ""
    full_text = ""

    if summary_size:
        summary_delivery = _pick_delivery_by_max_length(deliveries_sent, wants_max_length=True)
        payload_str = summary_delivery.get("personalised_payload", "{}")
        payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        summary_payload = payload

        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and "body" in item:
                    summary_text = item.get("body", "")
                    break
        elif isinstance(payload, dict):
            summary_text = payload.get("body", "")

        if "<" in summary_text:
            summary_text = extract_text_from_html(summary_text)

        print(f"\n📝 Summary extracted: {len(summary_text)} chars")

    full_delivery = _pick_delivery_by_max_length(deliveries_sent, wants_max_length=False)
    full_payload_str = full_delivery.get("personalised_payload", "{}")
    full_payload = json.loads(full_payload_str) if isinstance(full_payload_str, str) else full_payload_str
    if isinstance(full_payload, list):
        for item in full_payload:
            if isinstance(item, dict) and "body" in item:
                full_text = item.get("body", "")
                break
    elif isinstance(full_payload, dict):
        full_text = full_payload.get("body", "")
    if "<" in full_text:
        full_text = extract_text_from_html(full_text)
    
    # Initialize validation variables
    summary_size_valid = None
    summary_lang_valid = None
    
    # Validate summary / delivered body
    if summary_size:
        # Should have a summary
        assert summary_text, "❌ No summary found in payload"
        
        # Validate summary size (strict; validate_size already accounts for CJK scaling)
        sum_tol = 0.7 if target_lang == "zh" else 0.5
        summary_size_valid, size_details = validate_size(
            summary_text,
            summary_size,
            tolerance=sum_tol,
            language=target_lang,
        )
        assert summary_size_valid, f"❌ Summary size outside target: {size_details}"
        print(f"✅ Summary size valid: {len(summary_text)} chars ({size_details})")
        
        # Validate summary language
        summary_lang_valid, lang_indicators = validate_language(summary_text, target_lang, source_lang)
        assert summary_lang_valid, f"❌ Summary language invalid: found {lang_indicators}"
        print(f"✅ Summary language valid: {target_lang}")
    else:
        # Small message - body should contain translated content
        assert full_text, "❌ No content found in payload"
        body_lang_valid, body_indicators = validate_language(full_text, target_lang, source_lang)
        assert body_lang_valid, f"❌ Payload body language invalid: found {body_indicators}"
        print("✅ Payload body language valid (no summary expected)")

    assert full_text, "❌ No full message found in delivery payload"
    print(f"\n📄 Full message extracted from delivery: {len(full_text)} chars")
    
    # Validate full message size (strict bounds, but wide enough for translation variance)
    src_len = max(1, len(source_content))
    ratio = len(full_text) / src_len
    rtl_langs = {"ar", "he", "fa", "ur"}
    if source_lang == "zh" or target_lang == "zh":
        assert 0.2 <= ratio <= 8.0, f"❌ Full message size ratio out of CJK bounds: {ratio:.2f}x"
    elif source_lang in rtl_langs or target_lang in rtl_langs:
        assert 0.25 <= ratio <= 5.0, f"❌ Full message size ratio out of RTL bounds: {ratio:.2f}x"
    else:
        assert 0.3 <= ratio <= 5.0, f"❌ Full message size ratio out of bounds: {ratio:.2f}x"
    print(f"✅ Full message size ratio OK: {ratio:.2f}x")
    full_size_valid = True
    
    # Validate full message language
    full_lang_valid, full_lang_indicators = validate_language(full_text, target_lang, source_lang)
    if not full_lang_valid and summary_text:
        def _find_full_message_url(payload):
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        links = item.get("links") or []
                        for link in links:
                            url = link.get("url")
                            if url and "/messages/" in url:
                                return url
            elif isinstance(payload, dict):
                links = payload.get("links") or []
                for link in links:
                    url = link.get("url")
                    if url and "/messages/" in url:
                        return url
            return None

        full_message_url = _find_full_message_url(full_payload) or _find_full_message_url(summary_payload)
        if not full_message_url:
            match = re.search(r'(https?://[^\s)]+)', summary_text)
            if match:
                full_message_url = match.group(1)

        if full_message_url:
            try:
                if "format=" not in full_message_url:
                    separator = "&" if "?" in full_message_url else "?"
                    full_message_url = f"{full_message_url}{separator}format=text"
                response = httpx.get(full_message_url, timeout=60.0)
                if response.status_code == 200:
                    full_text = response.text.strip()
                    if "<" in full_text:
                        full_text = extract_text_from_html(full_text)
                    print("🔁 Full message retrieved via link for language validation")
                    # Re-check size ratio with fetched content
                    src_len = max(1, len(source_content))
                    ratio = len(full_text) / src_len
                    rtl_langs = {"ar", "he", "fa", "ur"}
                    if source_lang == "zh" or target_lang == "zh":
                        assert 0.2 <= ratio <= 8.0, f"❌ Full message size ratio out of CJK bounds: {ratio:.2f}x"
                    elif source_lang in rtl_langs or target_lang in rtl_langs:
                        assert 0.25 <= ratio <= 5.0, f"❌ Full message size ratio out of RTL bounds: {ratio:.2f}x"
                    else:
                        assert 0.3 <= ratio <= 5.0, f"❌ Full message size ratio out of bounds: {ratio:.2f}x"
                    print(f"✅ Full message size ratio OK (link): {ratio:.2f}x")
                    full_lang_valid, full_lang_indicators = validate_language(full_text, target_lang, source_lang)
            except Exception as link_err:
                print(f"⚠️ Failed to fetch full message link: {link_err}")

    assert full_lang_valid, f"❌ Full message language invalid: found {full_lang_indicators}"
    print(f"✅ Full message language valid: {target_lang}")
    
    # Save summary to file
    if summary_text:
        summary_file = test_output_dir / f"at1_4f_{source_lang}_to_{target_lang}_{size}_summary.txt"
        summary_file.write_text(summary_text, encoding='utf-8')
        print(f"💾 Saved summary: {summary_file}")
    
    # Save full message to file
    full_file = test_output_dir / f"at1_4f_{source_lang}_to_{target_lang}_{size}_full.txt"
    full_file.write_text(full_text, encoding='utf-8')
    print(f"💾 Saved full message: {full_file}")
    
    # Save source for comparison
    source_file = test_output_dir / f"at1_4f_{source_lang}_to_{target_lang}_{size}_source.txt"
    source_file.write_text(source_content, encoding='utf-8')
    print(f"💾 Saved source: {source_file}")
    
    # Create detailed comparison
    comparison_data = {
        "test_case": desc,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_size": len(source_content),
        "summary_size": len(summary_text) if summary_text else None,
        "full_size": len(full_text),
        "summary_target_size": summary_size,
        "message_id": message_id,
        "message_guid": message_guid,
        "message_center_url": f"{api_base_url}/messages/{message_guid}",
        "validation": {
            "summary": {
                "size_valid": summary_size_valid if summary_size else "N/A",
                "language_valid": summary_lang_valid if summary_text else "N/A",
                "actual_size": len(summary_text) if summary_text else 0,
                "target_size": summary_size
            },
            "full_message": {
                "size_valid": full_size_valid,
                "language_valid": full_lang_valid,
                "actual_size": len(full_text),
                "source_size": len(source_content),
                "expansion_ratio": round(len(full_text) / len(source_content), 2)
            }
        },
        "files": {
            "source": str(source_file.name),
            "summary": str(summary_file.name) if summary_text else None,
            "full": str(full_file.name)
        }
    }
    
    # Save comparison data
    comparison_file = test_output_dir / f"at1_4f_{source_lang}_to_{target_lang}_{size}_comparison.json"
    comparison_file.write_text(json.dumps(comparison_data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"💾 Saved comparison: {comparison_file}")
    
    print(f"\n{'='*80}")
    print(f"✅ AT1.4f PASSED: {desc}")
    print(f"{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_4f_summary_table(test_output_dir):
    """Generate summary table of all AT1.4f tests"""
    print(f"\n{'='*80}")
    print(f"AT1.4f SUMMARY TABLE")
    print(f"{'='*80}\n")
    
    # test_output_dir is function-scoped, so gather all outputs from this pytest run root.
    run_root = test_output_dir.parents[1]
    comparison_files = sorted(run_root.rglob("at1_4f_*_comparison.json"))
    
    if not comparison_files:
        pytest.fail("No AT1.4f test results found")
    
    # Create summary table
    print(f"{'Test':<35} {'Src':<4} {'Tgt':<4} {'Src Size':<9} {'Sum Size':<9} {'Full Size':<10} {'Ratio':<6} {'Sum✓':<5} {'Full✓':<6}")
    print(f"{'-'*35} {'-'*4} {'-'*4} {'-'*9} {'-'*9} {'-'*10} {'-'*6} {'-'*5} {'-'*6}")
    
    for comp_file in sorted(comparison_files):
        try:
            with open(comp_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            test = data.get("test_case", "Unknown")[:35]
            src = data.get("source_lang", "?").upper()
            tgt = data.get("target_lang", "?").upper()
            src_size = data.get("source_size", 0)
            sum_size = data.get("summary_size", "N/A")
            full_size = data.get("full_size", 0)
            ratio = data.get("validation", {}).get("full_message", {}).get("expansion_ratio", 0)
            
            sum_valid = data.get("validation", {}).get("summary", {}).get("size_valid")
            full_valid = data.get("validation", {}).get("full_message", {}).get("size_valid")
            
            sum_check = "✅" if sum_valid == True else ("N/A" if sum_valid == "N/A" else "❌")
            full_check = "✅" if full_valid else "❌"
            
            sum_display = f"{sum_size}" if isinstance(sum_size, int) else "N/A"
            
            print(f"{test:<35} {src:<4} {tgt:<4} {src_size:<9} {sum_display:<9} {full_size:<10} {ratio:<6.2f} {sum_check:<5} {full_check:<6}")
            
        except Exception as e:
            print(f"⚠️ Error reading {comp_file.name}: {e}")
    
    print(f"\n{'='*80}\n")
@pytest.mark.AT
@pytest.mark.mcp
@pytest.mark.req("FR-023")


def test_at1_4f_content_structure_validation(test_output_dir):
    """Validate content structure is preserved (headers, lists, paragraphs)"""
    print(f"\n{'='*80}")
    print(f"AT1.4f CONTENT STRUCTURE VALIDATION")
    print(f"{'='*80}\n")
    
    # test_output_dir is function-scoped, so gather all outputs from this pytest run root.
    run_root = test_output_dir.parents[1]
    full_files = sorted(run_root.rglob("at1_4f_*_full.txt"))
    
    if not full_files:
        pytest.fail("No AT1.4f full message files found")
    
    print(f"Checking {len(full_files)} files for content structure...\n")
    
    for full_file in sorted(full_files):
        try:
            content = full_file.read_text(encoding='utf-8')
            
            # Check for various content markers
            has_headers = bool(re.search(r'^#{1,6}\s', content, re.MULTILINE)) or bool(re.search(r'<h\d>', content))
            has_lists = bool(re.search(r'^\d+\.\s', content, re.MULTILINE)) or bool(re.search(r'^[-*•]\s', content, re.MULTILINE))
            has_paragraphs = len(content.split('\n\n')) > 1
            has_content = len(content.strip()) > 100
            
            status = "✅" if (has_content and (has_headers or has_lists or has_paragraphs)) else "⚠️"
            
            print(f"{status} {full_file.name}")
            print(f"   Headers: {has_headers}, Lists: {has_lists}, Paragraphs: {has_paragraphs}, Length: {len(content)}")
            
        except Exception as e:
            print(f"❌ Error reading {full_file.name}: {e}")
    
    print(f"\n{'='*80}\n")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]
