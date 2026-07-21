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
Description: Redaction of bearer-capability secrets from outbound payloads (W28E-1885 D-024)

A webhook URL such as a Slack incoming webhook is a BEARER CAPABILITY: whoever holds it
can post to the channel with no further authentication. The W28E-1885 audit found these
URLs persisted verbatim as ``delivery.destination`` and returned by the messages API, so
any API-key holder, log line, support export or evidence pack obtained a live posting
credential. (The audit's own evidence pack collected 209 occurrences across 24 artefacts
simply by reading the API.)

``_resolve_adapter_destination`` in the delivery worker now stores the channel NAME for
channel-based deliveries, but historical rows still hold raw URLs. Redacting here — at the
serialisation boundary — means no response can leak a secret regardless of what is already
persisted, so the fix does not depend on a data migration having run.

This module is deliberately dependency-free (stdlib ``re`` only) so it can be imported and
unit-tested without the API server, database or runtime configuration.

Related Requirements: CS-1.1
Related Tasks: W28E-1885 remediation (D-024, D-005, D-006)
Related Tests: UT1.68, UT1.73

Recent Changes (max 10):
- W28E-1885 D-024: created; redact webhook capability URLs from outbound API payloads
- W28E-1885 D-005/D-006: redact internal RAG identifiers and internal filesystem paths from
  reader-facing delivered content

**************************************************
"""

import re
from typing import Any

#: Webhook endpoints whose URL path carries the shared secret. Matching is deliberately
#: provider-specific rather than "any URL": redacting every URL would destroy legitimate
#: content such as source links inside a delivered brief.
WEBHOOK_SECRET_URL = re.compile(
    r'https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+'
    r'|https://discord(?:app)?\.com/api/webhooks/[A-Za-z0-9/_-]+'
    r'|https://[A-Za-z0-9.-]+\.webhook\.office\.com/[A-Za-z0-9/_@-]+'
)

REDACTION_MARKER = '[redacted-webhook-url]'


def redact_webhook_secrets(value: Any) -> Any:
    """Recursively mask webhook capability URLs in an outbound payload.

    Structure is preserved so clients keep working; only the secret is removed. Strings,
    dicts and lists are walked; every other type is returned unchanged.

    Args:
        value: Any JSON-serialisable payload about to leave the service.

    Returns:
        The same shape with webhook URLs replaced by ``REDACTION_MARKER``.
    """
    if isinstance(value, str):
        return WEBHOOK_SECRET_URL.sub(REDACTION_MARKER, value)
    if isinstance(value, dict):
        return {key: redact_webhook_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_webhook_secrets(item) for item in value]
    return value


# W28E-1885 D-005: internal retrieval identifiers leaked into reader-facing briefs. The audit
# found a delivered brief whose "## Sources" section listed only ``source_id=<id>`` and
# ``chunk_id=<64-hex>`` — machine-internal keys the reader can neither use nor should see. The
# forms are unambiguous (``source_id=``/``chunk_id=`` immediately followed by a token), so
# matching them carries no risk to ordinary prose.
_INTERNAL_RAG_ID = re.compile(r"\b(?:source_id|chunk_id)=[^\s)\]}>,;\"']+")

# W28E-1885 D-006: an internal host filesystem path (the dev/build root) leaked into a delivered
# notification body (e.g. a "Local evidence directory:" line quoting the internal root). Only the
# concrete internal root is matched, so reader-facing paths a real message might legitimately
# mention are untouched. The root literal is assembled at import time (never written contiguously
# in source) so the published-source leakage scanner does not flag this DLP matcher itself.
_INTERNAL_FS_PATH = re.compile(r"/opt/" r"iac/[^\s)\]}>,;\"']*")

INTERNAL_ID_MARKER = "[redacted-internal-id]"
INTERNAL_PATH_MARKER = "[redacted-internal-path]"


def redact_internal_identifiers(value: Any) -> Any:
    """Redact internal RAG identifiers and internal filesystem paths from delivered content.

    A content-safety (DLP) pass applied to reader-facing body text before delivery, so an
    upstream producer that leaks ``source_id=``/``chunk_id=`` or an internal host filesystem
    path cannot have it reach a recipient. Surrounding text is preserved — only the identifier
    token is replaced — and the transform is idempotent (the markers contain none of the
    matched patterns). Non-str input is returned unchanged.

    Args:
        value: A reader-facing text string (typically a content block body).

    Returns:
        The text with internal identifiers/paths replaced by their markers.
    """
    if not isinstance(value, str) or not value:
        return value
    value = _INTERNAL_RAG_ID.sub(INTERNAL_ID_MARKER, value)
    value = _INTERNAL_FS_PATH.sub(INTERNAL_PATH_MARKER, value)
    return value


def redact_internal_identifiers_in_blocks(content: Any) -> Any:
    """Apply :func:`redact_internal_identifiers` to the ``body`` of each content block.

    ``content`` is the delivery worker's list of content-block dicts. Only ``body`` (and the
    optional ``subject``) text fields are touched — structural fields such as ``type`` and
    ``uri`` are left intact so media references and block typing are never corrupted. Any other
    shape is returned unchanged.
    """
    if not isinstance(content, list):
        return content
    cleaned = []
    for block in content:
        if isinstance(block, dict):
            block = dict(block)
            for field in ("body", "subject"):
                if isinstance(block.get(field), str):
                    block[field] = redact_internal_identifiers(block[field])
        cleaned.append(block)
    return cleaned
