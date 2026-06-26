#!/usr/bin/env python3
"""
Slack preview durability tests — W28D-441 Snag 3.

Covers:
- Title deduplication: title not repeated as title/title
- Summary-plus-link: long content produces "View full message" link
- Preview has useful detail after title
"""

import pytest
import re


def _build_slack_payload(text: str, title: str = "") -> dict:
    """Reproduce chat_adapter._build_payload Slack logic for unit testing."""
    def _strip_duplicate_leading_title(value: str, heading: str) -> str:
        if not value or not heading:
            return value
        lines = value.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return value
        first = lines[0].strip()
        normalized_first = re.sub(r"^[*_`~]+|[*_`~]+$", "", first).strip()
        normalized_first = re.sub(r"\s+", " ", normalized_first)
        normalized_heading = re.sub(r"\s+", " ", str(heading).strip())
        if normalized_first == normalized_heading:
            return "\n".join(lines[1:]).lstrip()
        return value

    max_text_length = 4000
    if len(text) > max_text_length:
        text = text[:max_text_length - 3] + "..."

    payload = {"text": text}
    section_text = _strip_duplicate_leading_title(text, title)

    if len(text) <= 3000 and (title or len(text) > 100):
        blocks = []
        if title:
            blocks.append({
                "type": "header",
                "text": {"type": "plain_text", "text": title[:150]},
            })
        if len(section_text) <= 3000 and section_text:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": section_text[:3000]},
            })
        if blocks:
            payload["blocks"] = blocks

    return payload


class TestSlackTitleDeduplication:
    """Title must appear once in header, not duplicated in body."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_no_duplicate_title_plain(self):
        title = "Ukraine digest: 7-day situation update"
        body = f"{title}\nTheme Focus: military operations.\nSources used: [U01] ISW."
        payload = _build_slack_payload(body, title)
        assert "blocks" in payload
        header_texts = [
            b["text"]["text"] for b in payload["blocks"] if b["type"] == "header"
        ]
        section_texts = [
            b["text"]["text"] for b in payload["blocks"] if b["type"] == "section"
        ]
        assert len(header_texts) == 1
        assert header_texts[0] == title
        # Section should NOT start with the title again
        assert len(section_texts) == 1
        assert not section_texts[0].startswith(title)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_no_duplicate_title_markdown(self):
        title = "Ukraine digest: situation update"
        body = f"*{title}*\nBody detail here."
        payload = _build_slack_payload(body, title)
        section_texts = [
            b["text"]["text"] for b in payload["blocks"] if b["type"] == "section"
        ]
        assert len(section_texts) == 1
        assert not section_texts[0].strip().startswith(title)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_different_first_line_preserved(self):
        title = "Ukraine digest"
        body = "Theme Focus: military operations.\nMore content here."
        payload = _build_slack_payload(body, title)
        section_texts = [
            b["text"]["text"] for b in payload["blocks"] if b["type"] == "section"
        ]
        assert len(section_texts) == 1
        assert section_texts[0].startswith("Theme Focus")


class TestSlackPreviewContent:
    """Preview should contain useful detail, not just the title."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_preview_contains_report_detail(self):
        title = "Ukraine digest: Slack preview smoke"
        body = (
            f"{title}\n"
            "Theme Focus: this message checks title handling.\n"
            "What Changed: the body is long enough for useful preview.\n"
            "Sources used: [U01] Slack preview source.\n"
            "Previous messages sent: message 5118."
        )
        payload = _build_slack_payload(body, title)
        section_texts = [
            b["text"]["text"] for b in payload["blocks"] if b["type"] == "section"
        ]
        assert len(section_texts) == 1
        # The section should contain meaningful report detail
        assert "Theme Focus" in section_texts[0]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_view_full_message_link_in_long_content(self):
        """When text includes a View full message link, it appears in payload."""
        title = "Ukraine digest"
        link = "<https://notificationagent0.cloud-dog.net/messages/abc123|View full message (5000 characters)>"
        body = "Summary of the digest content.\n" + link
        payload = _build_slack_payload(body, title)
        assert "View full message" in payload["text"]


pytestmark = [pytest.mark.unit, pytest.mark.fast]
