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
Description: Assemble a well-formed HTML document for the email HTML alternative (W28E-1885 D-013)

The audit found delivered HTML email bodies were not well-formed documents: none carried a
``<!DOCTYPE>``, several had ``<html>`` with no ``<head>``, and 28/64 emitted content *before*
``<html>`` — the branding header and the "View it online" anchor were concatenated ahead of a
producer's ``<html>`` document, so the reader-facing markup had content outside the root element.

``ensure_html_document`` normalises any body — a bare fragment, a headless ``<html>``, or a full
document with content wrapped around it — into a single well-formed document:
``<!DOCTYPE html><html><head>…</head><body>…</body></html>`` with nothing outside ``<html>``. It
preserves an existing ``<head>`` (so producer styles survive) and folds any pre/post content
(branding header/footer, anchor) into ``<body>``. It is idempotent.

Dependency-free (stdlib ``re`` only) so it is importable and unit-testable without the SMTP
adapter or runtime configuration.

Related Requirements: FR-004
Related Tasks: W28E-1885 remediation (D-013)
Related Tests: UT1.75

Recent Changes (max 10):
- W28E-1885 D-013: created; guarantee a well-formed HTML email document

**************************************************
"""

import re

_DEFAULT_HEAD = (
    '<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
)

_HTML_OPEN = re.compile(r"<html\b[^>]*>", re.I)
_HTML_CLOSE = re.compile(r"</html\s*>", re.I)
_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>", re.I)
_HEAD_BLOCK = re.compile(r"<head\b[^>]*>(.*?)</head\s*>", re.I | re.S)
_BODY_BLOCK = re.compile(r"<body\b[^>]*>(.*?)</body\s*>", re.I | re.S)


def ensure_html_document(body: str) -> str:
    """Return ``body`` as a single well-formed HTML document.

    Guarantees a ``<!DOCTYPE html>``, a ``<html>`` root with a ``<head>`` (existing head kept,
    charset/viewport ensured) and a ``<body>``, with no content outside ``<html>``. Idempotent.
    Non-str or empty input is returned unchanged.
    """
    if not isinstance(body, str) or not body.strip():
        return body

    html_open = _HTML_OPEN.search(body)
    if not html_open:
        # A bare fragment: everything becomes the body.
        return _wrap(_DEFAULT_HEAD, body.strip())

    # There is an <html> element. Fold anything outside it back inside so nothing sits outside
    # the root. pre = branding header / anchor prepended ahead of <html>; post = footer after.
    # A leading DOCTYPE is structural, not content, so it must not be folded into the body
    # (folding it would also break idempotency on an already-normalised document).
    pre = _DOCTYPE.sub("", body[: html_open.start()]).strip()
    close = _HTML_CLOSE.search(body, html_open.end())
    if close:
        inner = body[html_open.end(): close.start()]
        post = body[close.end():].strip()
    else:
        inner = body[html_open.end():]
        post = ""

    head_match = _HEAD_BLOCK.search(inner)
    head_content = head_match.group(1).strip() if head_match else ""
    if head_match:
        inner = inner[: head_match.start()] + inner[head_match.end():]

    body_match = _BODY_BLOCK.search(inner)
    if body_match:
        body_inner = body_match.group(1)
    else:
        # No <body>: whatever remains after removing the head is the body content.
        body_inner = inner

    head = _ensure_head_essentials(head_content)
    assembled_body = "\n".join(part for part in (pre, body_inner.strip(), post) if part)
    return _wrap(head, assembled_body)


def _ensure_head_essentials(head_content: str) -> str:
    """Keep an existing head's contents, but guarantee charset and viewport are present."""
    parts = [head_content] if head_content else []
    combined = head_content.lower()
    if "charset" not in combined:
        parts.insert(0, '<meta charset="utf-8">')
    if "viewport" not in combined:
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    return "\n".join(p for p in parts if p).strip() or _DEFAULT_HEAD


def _wrap(head: str, body_inner: str) -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        f"<head>\n{head}\n</head>\n"
        f"<body>\n{body_inner}\n</body>\n"
        "</html>"
    )
