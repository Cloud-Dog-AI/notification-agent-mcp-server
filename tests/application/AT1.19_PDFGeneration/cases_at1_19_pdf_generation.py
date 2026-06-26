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
AT1.19: PDF Output & Generation Test

API-only validations:
- Request PDF generation via destination preferences (generate_pdf + pdf_preference)
- Wait for delivery to reach sent
- Extract PDF via attachment content or PDF URL
- Validate PDF bytes (magic bytes + size) and (optionally) language indicators
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx
import pytest

from tests.utils.test_helpers import check_test_dependencies

# Reuse the proven PDF validator from AT1.4 suite (parses text and checks language corruption etc.)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "AT1.4_Comprehensive"))
from helpers import load_test_message, validate_pdf  # noqa: E402


def _wait_for_delivery_sent(
    api_client,
    message_id: int,
    *,
    max_wait: float,
    poll_interval: float,
) -> Dict[str, Any]:
    t0 = time.time()
    last_state: str | None = None
    while time.time() - t0 < max_wait:
        r = api_client.get(f"/messages/{message_id}/deliveries")
        assert r.status_code == 200, f"GET /messages/{{id}}/deliveries failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        deliveries = data.get("items") if isinstance(data, dict) else data
        if isinstance(deliveries, list) and deliveries:
            d0 = deliveries[0]
            if isinstance(d0, dict):
                last_state = str(d0.get("state") or "").lower()
                elapsed = time.time() - t0
                if int(elapsed) % max(1, int(poll_interval * 5)) == 0:
                    print(f"[{elapsed:6.1f}s] message {message_id}: delivery_state={last_state}")
                if last_state == "sent":
                    return d0
                if last_state in ("hard_failed", "failed", "cancelled", "canceled"):
                    pytest.fail(f"❌ Delivery failed: state={last_state} last_error={d0.get('last_error')}")
        time.sleep(poll_interval)
    pytest.fail(f"❌ Timed out waiting for delivery to reach sent (last_state={last_state!r})")


def _extract_pdf_candidates(payload: Any) -> Tuple[List[bytes], List[str]]:
    """
    Extract PDFs from:
    - attachments: base64 content or url
    - links: url
    Returns: (pdf_bytes_candidates, pdf_url_candidates)
    """
    pdf_bytes: List[bytes] = []
    pdf_urls: List[str] = []

    if payload is None:
        return pdf_bytes, pdf_urls

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"text": payload}

    blocks: List[Dict[str, Any]]
    if isinstance(payload, dict):
        blocks = [payload]
    elif isinstance(payload, list):
        blocks = [b for b in payload if isinstance(b, dict)]
    else:
        return pdf_bytes, pdf_urls

    for b in blocks:
        for att in (b.get("attachments") or []):
            if not isinstance(att, dict):
                continue
            filename = str(att.get("filename", "")).lower()
            ctype = str(att.get("content_type", "")).lower()
            atype = str(att.get("type", "")).lower()
            if "pdf" in (ctype + atype) or filename.endswith(".pdf"):
                if att.get("content"):
                    try:
                        raw = att["content"]
                        pdf_bytes.append(base64.b64decode(raw) if isinstance(raw, str) else raw)
                    except Exception:
                        pass
                if att.get("url"):
                    pdf_urls.append(str(att["url"]))

        for link in (b.get("links") or []):
            if not isinstance(link, dict):
                continue
            url = link.get("url")
            label = str(link.get("label", "")).lower()
            if url and (str(url).lower().endswith(".pdf") or "pdf" in label):
                pdf_urls.append(str(url))

    # de-dupe
    pdf_urls = list(dict.fromkeys(pdf_urls))
    return pdf_bytes, pdf_urls


def _download_pdf(
    *,
    api_client,
    api_base_url: str,
    api_key: str,
    pdf_url: str,
) -> bytes:
    api_base = str(api_base_url).rstrip("/")
    api_parts = urlsplit(api_base)
    pdf_parts = urlsplit(str(pdf_url))

    def _is_local_host(hostname: str) -> bool:
        return hostname in {"localhost", "127.0.0.1", "0.0.0.0"}

    same_origin = False
    local_alias_same_scheme = False
    if pdf_parts.scheme and pdf_parts.netloc:
        same_scheme = (pdf_parts.scheme or "").lower() == (api_parts.scheme or "").lower()
        api_host = (api_parts.hostname or "").lower()
        pdf_host = (pdf_parts.hostname or "").lower()
        same_port = (pdf_parts.port or (443 if pdf_parts.scheme == "https" else 80)) == (
            api_parts.port or (443 if api_parts.scheme == "https" else 80)
        )
        same_host = api_host == pdf_host or (_is_local_host(api_host) and _is_local_host(pdf_host))
        same_origin = same_scheme and same_host and same_port
        local_alias_same_scheme = same_scheme and _is_local_host(api_host) and _is_local_host(pdf_host)

    if str(pdf_url).startswith("/"):
        rel = str(pdf_url)
        r = api_client.get(rel)
        assert r.status_code == 200, f"PDF download via API failed: {r.status_code} {r.text[:200]}"
        assert "application/pdf" in (r.headers.get("content-type") or ""), f"Unexpected content-type: {r.headers.get('content-type')}"
        return r.content

    if same_origin:
        rel = pdf_parts.path or "/"
        if pdf_parts.query:
            rel = f"{rel}?{pdf_parts.query}"
        r = api_client.get(rel)
        assert r.status_code == 200, f"PDF download via API failed: {r.status_code} {r.text[:200]}"
        assert "application/pdf" in (r.headers.get("content-type") or ""), f"Unexpected content-type: {r.headers.get('content-type')}"
        return r.content

    if local_alias_same_scheme:
        r_local = httpx.get(pdf_url, timeout=30.0, headers={"X-API-Key": api_key} if api_key else None)
        assert r_local.status_code == 200, f"PDF download failed: {r_local.status_code} {r_local.text[:200]}"
        assert "application/pdf" in (r_local.headers.get("content-type") or ""), f"Unexpected content-type: {r_local.headers.get('content-type')}"
        return r_local.content

    # External or non-API URL: fetch directly.
    r2 = httpx.get(pdf_url, timeout=30.0)
    assert r2.status_code == 200, f"PDF download failed: {r2.status_code} {r2.text[:200]}"
    assert "application/pdf" in (r2.headers.get("content-type") or ""), f"Unexpected content-type: {r2.headers.get('content-type')}"
    return r2.content


def _create_message(
    api_client,
    *,
    channel_name: str,
    address: str,
    subject: str,
    body: str,
    preferences: Dict[str, Any],
) -> int:
    r = api_client.post(
        "/messages",
        json={
            "audience_type": "personalised",
            "destinations": [{"channel": channel_name, "address": address, "preferences": preferences}],
            "content": [{"type": "text", "body": body}],
            "options": {"subject": subject},
        },
    )
    assert r.status_code == 201, f"POST /messages failed: {r.status_code} {r.text[:200]}"
    mid = r.json().get("message_id")
    assert mid, f"No message_id in response: {r.json()}"
    return int(mid)


def test_at1_19a_pdf_link_via_loopback_channel(
    api_client,
    api_base_url: str,
    api_key: str,
    test_config: Any,
    request,
    loopback_channel_name: str,
    at119_max_wait: float,
    at119_poll_interval: float,
    pdf_language: str,
    pdf_output_formats: List[str],
    at119_source_lang: str,
    at119_source_size: int,
    test_output_dir: Path,
):
    check_test_dependencies(requires_llm=True, requires_smtp=False, requires_slack=False, requires_api=True, test_name="AT1.19A")

    subject = test_config.get("test.at119.subject")
    if not subject:
        pytest.fail("❌ HARD FAIL: test.at119.subject not configured in env file")
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ HARD FAIL: test.email_domain not configured in env file")

    run_id = str(int(time.time()))
    address = f"at119_pdf_loopback_{run_id}{email_domain}"
    message_id: Optional[int] = None

    def _cleanup() -> None:
        if message_id is not None:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    try:
        source_content = load_test_message(at119_source_lang, at119_source_size)
    except FileNotFoundError as e:
        pytest.fail(f"❌ Missing test source content: {e}")

    message_id = _create_message(
        api_client,
        channel_name=loopback_channel_name,
        address=address,
        subject=f"{subject} (loopback {run_id})",
        body=source_content,
        preferences={
            "language": pdf_language,
            "content_style": "html",
            "generate_pdf": True,
            "pdf_preference": "link",
            "output_formats": pdf_output_formats,
        },
    )

    delivery = _wait_for_delivery_sent(api_client, message_id, max_wait=at119_max_wait, poll_interval=at119_poll_interval)
    payload = delivery.get("personalised_payload")
    pdf_bytes_list, pdf_urls = _extract_pdf_candidates(payload)
    assert pdf_urls or pdf_bytes_list, "❌ PDF requested but no PDF attachment/link found in personalised_payload"

    if pdf_bytes_list:
        pdf_bytes = pdf_bytes_list[0]
    else:
        pdf_bytes = _download_pdf(api_client=api_client, api_base_url=api_base_url, api_key=api_key, pdf_url=pdf_urls[0])

    assert pdf_bytes[:4] == b"%PDF", f"PDF magic bytes incorrect: {pdf_bytes[:4]}"
    assert len(pdf_bytes) > 1000, f"PDF too small: {len(pdf_bytes)} bytes"

    pdf_ok, pdf_info = validate_pdf(pdf_bytes, pdf_language, expected_min_size=len(source_content), source_content=source_content)
    assert pdf_ok, f"❌ PDF validation failed: {pdf_info}"

    out = test_output_dir / f"at1_19a_loopback_{run_id}.pdf"
    out.write_bytes(pdf_bytes)
    print(f"✅ Saved PDF: {out}")


def test_at1_19b_pdf_attachment_via_smtp_channel(
    api_client,
    test_config: Any,
    request,
    smtp_channel_name: str,
    at119_max_wait: float,
    at119_poll_interval: float,
    pdf_language: str,
    pdf_output_formats: List[str],
    at119_source_lang: str,
    at119_source_size: int,
):
    check_test_dependencies(requires_llm=True, requires_smtp=True, requires_slack=False, requires_api=True, test_name="AT1.19B")

    to_email = test_config.get("test.at119.recipient_email")
    if not to_email:
        pytest.fail("❌ HARD FAIL: test.at119.recipient_email not configured in env file")
    subject = test_config.get("test.at119.subject")
    if not subject:
        pytest.fail("❌ HARD FAIL: test.at119.subject not configured in env file")

    run_id = str(int(time.time()))
    message_id: Optional[int] = None

    def _cleanup() -> None:
        if message_id is not None:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    try:
        source_content = load_test_message(at119_source_lang, at119_source_size)
    except FileNotFoundError as e:
        pytest.fail(f"❌ Missing test source content: {e}")

    message_id = _create_message(
        api_client,
        channel_name=smtp_channel_name,
        address=to_email,
        subject=f"{subject} (smtp attach {run_id})",
        body=source_content,
        preferences={
            "language": pdf_language,
            "content_style": "html",
            "generate_pdf": True,
            "pdf_preference": "attach",
            "output_formats": pdf_output_formats,
        },
    )

    delivery = _wait_for_delivery_sent(api_client, message_id, max_wait=at119_max_wait, poll_interval=at119_poll_interval)
    payload = delivery.get("personalised_payload")
    pdf_bytes_list, pdf_urls = _extract_pdf_candidates(payload)
    assert pdf_bytes_list or pdf_urls, "❌ PDF requested but no PDF attachment/link found in personalised_payload"

    # Prefer embedded attachment bytes (stronger validation than URL presence)
    if pdf_bytes_list:
        pdf_bytes = pdf_bytes_list[0]
    else:
        # Some SMTP payloads store only a URL in attachment metadata
        api_base_url = str(api_client.base_url)
        api_key = api_client.headers.get("X-API-Key", "")
        pdf_bytes = _download_pdf(api_client=api_client, api_base_url=api_base_url, api_key=api_key, pdf_url=pdf_urls[0])

    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 1000
    pdf_ok, pdf_info = validate_pdf(pdf_bytes, pdf_language, expected_min_size=len(source_content), source_content=source_content)
    assert pdf_ok, f"❌ PDF validation failed: {pdf_info}"


def test_at1_19c_pdf_output_formats_include_pdf(
    api_client,
    test_config: Any,
    request,
    loopback_channel_name: str,
    at119_max_wait: float,
    at119_poll_interval: float,
    pdf_language: str,
    at119_source_lang: str,
    at119_source_size: int,
):
    check_test_dependencies(requires_llm=True, requires_smtp=False, requires_slack=False, requires_api=True, test_name="AT1.19C")

    subject = test_config.get("test.at119.subject")
    if not subject:
        pytest.fail("❌ HARD FAIL: test.at119.subject not configured in env file")
    email_domain = test_config.get("test.email_domain")
    if not email_domain:
        pytest.fail("❌ HARD FAIL: test.email_domain not configured in env file")

    output_formats = test_config.get("test.at119.output_formats_pdf_only")
    if not output_formats:
        pytest.fail("❌ HARD FAIL: test.at119.output_formats_pdf_only not configured (JSON list)")
    try:
        if isinstance(output_formats, str):
            of = json.loads(output_formats)
        elif isinstance(output_formats, (list, tuple)):
            of = list(output_formats)
        else:
            raise TypeError(f"unsupported type: {type(output_formats).__name__}")
    except Exception as e:
        pytest.fail(f"❌ HARD FAIL: test.at119.output_formats_pdf_only invalid JSON/list: {e}")
    assert "pdf" in [str(x).lower() for x in of], "Expected output_formats_pdf_only to include 'pdf'"

    run_id = str(int(time.time()))
    address = f"at119_formats_{run_id}{email_domain}"
    message_id: Optional[int] = None

    def _cleanup() -> None:
        if message_id is not None:
            try:
                api_client.delete(f"/messages/{message_id}")
            except Exception:
                pass

    request.addfinalizer(_cleanup)

    try:
        source_content = load_test_message(at119_source_lang, at119_source_size)
    except FileNotFoundError as e:
        pytest.fail(f"❌ Missing test source content: {e}")

    message_id = _create_message(
        api_client,
        channel_name=loopback_channel_name,
        address=address,
        subject=f"{subject} (formats {run_id})",
        body=source_content,
        preferences={
            "language": pdf_language,
            "content_style": "text",
            "generate_pdf": True,
            "pdf_preference": "link",
            "output_formats": of,
        },
    )

    delivery = _wait_for_delivery_sent(api_client, message_id, max_wait=at119_max_wait, poll_interval=at119_poll_interval)
    payload = delivery.get("personalised_payload")
    pdf_bytes_list, pdf_urls = _extract_pdf_candidates(payload)
    assert pdf_urls or pdf_bytes_list, "❌ Expected at least one PDF link/attachment when output_formats includes pdf"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]


# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-020")
