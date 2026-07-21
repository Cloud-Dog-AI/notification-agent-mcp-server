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
Description: Slack mrkdwn sanitisers applied at the chat-adapter payload boundary (W28E-1885)

Slack's mrkdwn is NOT CommonMark: bold is a single asterisk (``*bold*``), there is no heading
syntax, and HTML is shown verbatim. The delivery worker's smart path already converts most
content, but several truncation/passthrough branches build ``{"text": <raw body>}`` directly,
so raw ``**bold**``, ``# heading`` and ``<h1>..</h1><p>..`` reach the Slack API. The audit
(W28E-1885) observed 115/1200 messages leaking ``**text**`` into blocks (D-015), heading lines
rendered literally (D-016) and raw HTML in the notification fallback text (D-017).

This module is the LAST gate — the chat adapter applies it to every Slack payload regardless
of which upstream path produced it — so it must be **idempotent**: running it on text the smart
path already converted must be a no-op. That is why it deliberately does NOT convert a lone
``*word*`` to ``_word_`` italic: a single asterisk is ambiguous (raw CommonMark italic vs
already-converted mrkdwn bold), and clobbering it would corrupt bold the smart path produced.
The defect is ``**double**`` surviving, and that is what is fixed. Slack link syntax
``<url|label>`` is protected before any tag stripping so a link is never mistaken for HTML.

Dependency-free (stdlib ``re``/``html`` only) so it is importable and unit-testable without the
API server, database or runtime configuration.

Related Requirements: FR-023
Related Tasks: W28E-1885 remediation (D-015, D-016, D-017)
Related Tests: UT1.71

Recent Changes (max 10):
- W28E-1885 D-015/016/017: created; idempotent CommonMark->mrkdwn + fallback markup strip

**************************************************
"""

import html
import re
from typing import Any

#: Slack link/entity forms that must survive tag stripping: <url|label>, <url>, <@U…>, <#C…>.
#: Distinguished from HTML by containing a scheme (``://``), a ``|`` separator, or a Slack
#: mention sigil — none of which appear in a real HTML tag name.
_SLACK_ENTITY = re.compile(r"<((?:https?|mailto):[^>]+|[@#!][^>]+)>")

#: Markdown heading lines (``# H`` .. ``###### H``) -> Slack bold. Idempotent: after conversion
#: the line starts with ``*`` not ``#`` so a re-run matches nothing.
_MD_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s*(.+?)\s*$")

#: CommonMark bold -> Slack bold. ``**x**``/``__x__`` -> ``*x*``. Idempotent (no ``**``/``__``
#: remains afterwards). A lone ``*x*`` is intentionally left untouched (see module docstring).
_MD_BOLD_STARS = re.compile(r"\*\*(.+?)\*\*", re.S)
_MD_BOLD_UNDERSCORES = re.compile(r"__(.+?)__", re.S)

#: Markdown link ``[label](url)`` -> Slack link ``<url|label>``. Idempotent: the Slack form has
#: no ``](`` so a re-run matches nothing.
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")

#: A generic HTML tag. Slack entities are masked out first, so this never eats ``<url|label>``.
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_BLOCK_CLOSE = re.compile(r"</(h[1-6]|p|li|div|tr|ul|ol|table|blockquote)>", re.I)
_BR = re.compile(r"<br\s*/?>", re.I)


def sanitize_slack_mrkdwn(text: Any) -> Any:
    """Make text safe for a Slack ``mrkdwn`` block, idempotently.

    Converts CommonMark bold and headings to Slack mrkdwn and markdown links to Slack links.
    Leaves lone ``*word*`` alone so already-converted bold is never turned into italic. Non-str
    input is returned unchanged.
    """
    if not isinstance(text, str) or not text:
        return text
    value = _MD_LINK.sub(r"<\2|\1>", text)
    value = _MD_HEADING.sub(r"*\1*", value)
    value = _MD_BOLD_STARS.sub(r"*\1*", value)
    value = _MD_BOLD_UNDERSCORES.sub(r"*\1*", value)
    return value


def strip_markup_for_fallback(text: Any) -> Any:
    """Produce a plain-text Slack notification-fallback string, idempotently.

    Removes HTML tags and decodes entities so no ``<h1>``/``<p>`` markup reaches the fallback
    ``text`` field, while preserving Slack link/mention syntax (``<url|label>``, ``<@U…>``).
    Non-str input is returned unchanged.
    """
    if not isinstance(text, str) or not text:
        return text

    # Protect Slack entities from the tag stripper.
    protected: list[str] = []

    def _mask(match: "re.Match[str]") -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    value = _SLACK_ENTITY.sub(_mask, text)

    # Turn block-level markup into line breaks before removing the rest, so words don't run
    # together, then strip every remaining tag.
    value = _BR.sub("\n", value)
    value = _BLOCK_CLOSE.sub("\n", value)
    value = _HTML_TAG.sub("", value)
    value = html.unescape(value)

    # Restore protected Slack entities.
    def _unmask(match: "re.Match[str]") -> str:
        return protected[int(match.group(1))]

    value = re.sub(r"\x00(\d+)\x00", _unmask, value)

    # Collapse the runs of blank lines the block-close substitution can create.
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value
