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
LLM Provider Comparison Test
Compares llm2/qwen3:14b vs llm1/ibm/granite4:tiny-h on quality and performance
for notification-agent workloads: formatting, translation, summarization.

Usage:
    python tests/llm_test/test_llm_comparison.py

Both providers use Ollama. No env file needed — endpoints are hardcoded
to the known infrastructure.
"""

import json
import time
import sys
import os
import statistics
import urllib3

# Suppress TLS warnings for internal Ollama endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

PROVIDERS = {
    "llm2/qwen3:14b": {
        "base_url": "https://llm.example.com",
        "model": "qwen3:14b",
    },
    "llm1/granite4:tiny-h": {
        "base_url": "https://llm2.example.com",
        "model": "granite4:tiny-h",
    },
}

# ---------------------------------------------------------------------------
# Test prompts — each tests a different notification-agent capability
# ---------------------------------------------------------------------------

TESTS = [
    {
        "id": "T1_FORMAT_EN",
        "name": "Format English content (markdown)",
        "prompt": (
            "Format the following notification content as clean Markdown with "
            "headers, bullet points, and bold key facts. Output ONLY the formatted "
            "content, nothing else.\n\n"
            "Content:\n"
            "The quarterly security audit found 3 critical vulnerabilities in the "
            "payment gateway. CVE-2026-1234 affects TLS handshake, CVE-2026-1235 "
            "is an SQL injection in the reporting module, and CVE-2026-1236 is a "
            "privilege escalation in the admin panel. All must be patched within 72 "
            "hours per SLA. Contact security@cloud-dog.net for details."
        ),
        "quality_checks": [
            ("has_markdown_headers", lambda r: "#" in r),
            ("has_bullet_points", lambda r: "- " in r or "* " in r or "•" in r),
            ("has_cve_numbers", lambda r: "CVE-2026-1234" in r and "CVE-2026-1235" in r),
            ("no_thinking_tags", lambda r: "<think>" not in r),
        ],
    },
    {
        "id": "T2_TRANSLATE_FR",
        "name": "Translate to French",
        "prompt": (
            "Translate the following text to French. Output ONLY the French "
            "translation, nothing else. Do NOT include the original English.\n\n"
            "Text:\n"
            "Your monthly invoice #INV-2026-0842 for Cloud Dog Platform services "
            "is now available. Total amount: €2,450.00. Payment is due by March 15, "
            "2026. Please log in to your dashboard to review and download the PDF."
        ),
        "quality_checks": [
            ("is_french", lambda r: any(w in r.lower() for w in ["facture", "paiement", "montant", "disponible", "connectez"])),
            ("has_amount", lambda r: "2 450" in r or "2,450" in r or "2450" in r),
            ("no_english_leak", lambda r: "your monthly" not in r.lower()),
            ("no_thinking_tags", lambda r: "<think>" not in r),
        ],
    },
    {
        "id": "T3_TRANSLATE_AR",
        "name": "Translate to Arabic (RTL)",
        "prompt": (
            "Translate the following text to Arabic. Output ONLY the Arabic "
            "translation using Arabic script characters. Do NOT transliterate.\n\n"
            "Text:\n"
            "Security alert: Unusual login detected from IP 203.0.113.42 at 14:30 UTC. "
            "If this was not you, please change your password immediately."
        ),
        "quality_checks": [
            ("has_arabic_chars", lambda r: sum(1 for c in r if "\u0600" <= c <= "\u06FF") > 20),
            ("no_latin_heavy", lambda r: sum(1 for c in r if c.isascii() and c.isalpha()) < len(r) * 0.3),
            ("no_thinking_tags", lambda r: "<think>" not in r),
        ],
    },
    {
        "id": "T4_TRANSLATE_ZH",
        "name": "Translate to Chinese (CJK)",
        "prompt": (
            "Translate the following text to Simplified Chinese. Output ONLY the "
            "Chinese translation. Do NOT include English.\n\n"
            "Text:\n"
            "Your deployment to production was successful. 47 services updated, "
            "0 failures. Average response time improved by 12% compared to the "
            "previous release. Monitoring dashboards have been updated."
        ),
        "quality_checks": [
            ("has_cjk_chars", lambda r: sum(1 for c in r if "\u4e00" <= c <= "\u9fff") > 15),
            ("no_english_leak", lambda r: "your deployment" not in r.lower()),
            ("no_thinking_tags", lambda r: "<think>" not in r),
        ],
    },
    {
        "id": "T5_SUMMARIZE",
        "name": "Summarize to 100 words",
        "prompt": (
            "Summarize the following text in approximately 100 words. Output ONLY "
            "the summary, nothing else.\n\n"
            "Text:\n"
            "The 2026 Q1 platform reliability report shows an overall uptime of "
            "99.97% across all Cloud Dog services. The primary database cluster "
            "experienced a 23-minute outage on January 14th due to a failed "
            "automatic failover triggered by network partition between availability "
            "zones. The incident was resolved by manual promotion of the standby "
            "node. Post-incident review identified three root causes: insufficient "
            "heartbeat timeout configuration, a race condition in the failover "
            "controller, and missing alerts for cross-AZ latency spikes. All three "
            "have been remediated. The API gateway maintained 100% uptime. CDN "
            "cache hit ratio improved from 94.2% to 96.8%. P95 latency for the "
            "notification service decreased from 340ms to 210ms after the LLM "
            "provider migration from GPT-4 to a self-hosted Ollama cluster. Cost "
            "per notification dropped 78% as a result. Mobile push delivery "
            "success rate held steady at 99.1%. Email deliverability improved to "
            "97.3% following DKIM alignment fixes."
        ),
        "quality_checks": [
            ("reasonable_length", lambda r: 40 < len(r.split()) < 200),
            ("mentions_uptime", lambda r: "99.97" in r or "uptime" in r.lower()),
            ("no_thinking_tags", lambda r: "<think>" not in r),
        ],
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def invoke_llm(base_url: str, model: str, prompt: str, timeout: int = 120) -> tuple:
    """Call Ollama via OpenAI-compatible /v1/chat/completions endpoint.
    Returns (response_text, latency_seconds).
    """
    import httpx

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": 2048,
        "temperature": 0.5,
        "seed": 1234,
    }
    t0 = time.monotonic()
    with httpx.Client(verify=False, timeout=timeout) as client:
        resp = client.post(f"{base_url}/v1/chat/completions", json=payload)
        resp.raise_for_status()
    elapsed = time.monotonic() - t0
    data = resp.json()
    text = ""
    choices = data.get("choices", [])
    if choices:
        text = choices[0].get("message", {}).get("content", "").strip()
    # Strip <think>...</think> blocks (qwen3 thinking mode)
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return text, elapsed


def run_comparison():
    results = {}  # provider -> list of test results

    for provider_name, cfg in PROVIDERS.items():
        print(f"\n{'=' * 80}")
        print(f"  PROVIDER: {provider_name}")
        print(f"  Endpoint: {cfg['base_url']}  Model: {cfg['model']}")
        print(f"{'=' * 80}")

        provider_results = []
        for test in TESTS:
            print(f"\n  [{test['id']}] {test['name']}...", end=" ", flush=True)
            try:
                text, elapsed = invoke_llm(cfg["base_url"], cfg["model"], test["prompt"])
                # Run quality checks
                checks = {}
                for check_name, check_fn in test["quality_checks"]:
                    checks[check_name] = check_fn(text)
                quality_pass = all(checks.values())
                quality_score = sum(checks.values()) / len(checks)

                result = {
                    "test_id": test["id"],
                    "test_name": test["name"],
                    "latency_s": round(elapsed, 2),
                    "response_chars": len(text),
                    "quality_pass": quality_pass,
                    "quality_score": quality_score,
                    "checks": checks,
                    "response_preview": text[:200],
                    "error": None,
                }
                status = "✅" if quality_pass else "⚠️"
                print(f"{status} {elapsed:.1f}s  ({len(text)} chars)  quality={quality_score:.0%}")
                if not quality_pass:
                    for ck, cv in checks.items():
                        if not cv:
                            print(f"      FAIL: {ck}")
            except Exception as e:
                result = {
                    "test_id": test["id"],
                    "test_name": test["name"],
                    "latency_s": None,
                    "response_chars": 0,
                    "quality_pass": False,
                    "quality_score": 0.0,
                    "checks": {},
                    "response_preview": "",
                    "error": str(e),
                }
                print(f"❌ ERROR: {e}")
            provider_results.append(result)
        results[provider_name] = provider_results

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print(f"\n\n{'=' * 80}")
    print("  COMPARISON SUMMARY")
    print(f"{'=' * 80}\n")

    # Header
    providers = list(PROVIDERS.keys())
    print(f"{'Test':<25s}", end="")
    for p in providers:
        short = p.split("/", 1)[1] if "/" in p else p
        print(f"  {short:>20s}", end="")
    print()
    print("-" * (25 + 22 * len(providers)))

    # Per-test comparison
    for i, test in enumerate(TESTS):
        print(f"{test['id']:<25s}", end="")
        for p in providers:
            r = results[p][i]
            if r["error"]:
                print(f"  {'ERROR':>20s}", end="")
            else:
                status = "✓" if r["quality_pass"] else "✗"
                print(f"  {r['latency_s']:>6.1f}s {status} q={r['quality_score']:.0%}", end="")
                # pad
                cell = f"{r['latency_s']:>6.1f}s {status} q={r['quality_score']:.0%}"
                print(" " * max(0, 20 - len(cell)), end="")
        print()

    # Aggregates
    print("-" * (25 + 22 * len(providers)))
    print(f"{'TOTALS':<25s}", end="")
    for p in providers:
        pr = results[p]
        latencies = [r["latency_s"] for r in pr if r["latency_s"] is not None]
        quality_scores = [r["quality_score"] for r in pr]
        passes = sum(1 for r in pr if r["quality_pass"])
        avg_lat = statistics.mean(latencies) if latencies else 0
        avg_q = statistics.mean(quality_scores) if quality_scores else 0
        cell = f"{avg_lat:.1f}s avg  {passes}/{len(pr)} pass"
        print(f"  {cell:>20s}", end="")
    print()

    print(f"\n{'LATENCY':<25s}", end="")
    for p in providers:
        pr = results[p]
        latencies = [r["latency_s"] for r in pr if r["latency_s"] is not None]
        if latencies:
            total = sum(latencies)
            print(f"  {total:>6.1f}s total         ", end="")
        else:
            print(f"  {'N/A':>20s}", end="")
    print()

    # Write JSON report
    report_dir = os.path.join(os.path.dirname(__file__), "..", "..", "working")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "llm-comparison-results.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results: {os.path.abspath(report_path)}")


if __name__ == "__main__":
    run_comparison()
