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
Description: HTML/markdown -> readable text/plain conversion for the email MIME alternative (D-010)

Every HTML email carries a ``text/plain`` alternative for clients that do not render HTML. The
audit (W28E-1885 D-010) found this alternative was produced by ``re.sub(r'<[^>]+>', '', body)``:
a naive tag strip that (a) mashes an HTML ``<table>`` into a run of unaligned cell text and
(b) leaves any residual markdown pipe row (``| a | b |``) verbatim. Either way the reader of the
plain part gets an unreadable or raw-markup body.

This converter renders tables — both HTML ``<table>`` and markdown pipe tables — into an aligned
plain-text grid, strips the remaining HTML, and decodes entities, so the plain alternative
contains no raw HTML tag and no raw markdown table row.

Dependency-free (stdlib ``re``/``html`` only) so it is importable and unit-testable without the
SMTP adapter or runtime configuration.

Related Requirements: FR-004
Related Tasks: W28E-1885 remediation (D-010)
Related Tests: UT1.75

Recent Changes (max 10):
- W28E-1885 D-010: created; render tables into a readable text/plain alternative

**************************************************
"""

import html
import re

_NON_CONTENT_BLOCK = re.compile(r"<(head|style|script)\b[^>]*>.*?</\1\s*>", re.I | re.S)
_HTML_TABLE = re.compile(r"<table\b[^>]*>(.*?)</table>", re.I | re.S)
_HTML_ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_HTML_CELL = re.compile(r"<t[hd]\b[^>]*>(.*?)</t[hd]>", re.I | re.S)
_ANY_TAG = re.compile(r"<[^>]+>")
_MD_SEPARATOR_ROW = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _clean_cell(text: str) -> str:
    """Reduce a table cell's inner HTML/markup to a single clean line of text."""
    text = _ANY_TAG.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("|", "/")  # a literal pipe inside a cell must not look like a column edge
    return re.sub(r"\s+", " ", text).strip()


def _render_grid(rows: list[list[str]]) -> str:
    """Render a list of cell-rows as an aligned plain-text table."""
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    col_widths = [max(len(rows[r][c]) for r in range(len(rows))) for c in range(width)]
    lines = []
    for r_index, row in enumerate(rows):
        lines.append("  ".join(cell.ljust(col_widths[c]) for c, cell in enumerate(row)).rstrip())
        if r_index == 0 and len(rows) > 1:
            # A rule under the header makes the grid readable in a monospace client.
            lines.append("  ".join("-" * col_widths[c] for c in range(width)).rstrip())
    return "\n".join(lines)


def _html_table_to_text(match: "re.Match[str]") -> str:
    rows = []
    for row_html in _HTML_ROW.findall(match.group(1)):
        cells = [_clean_cell(cell) for cell in _HTML_CELL.findall(row_html)]
        if cells:
            rows.append(cells)
    grid = _render_grid(rows)
    return f"\n{grid}\n" if grid else "\n"


def _convert_markdown_pipe_tables(text: str) -> str:
    """Convert contiguous blocks of markdown pipe rows into aligned grids."""
    lines = text.split("\n")
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        rows = []
        for line in block:
            if _MD_SEPARATOR_ROW.match(line):
                continue  # drop the |---|---| separator row
            cells = [_clean_cell(c) for c in line.strip().strip("|").split("|")]
            rows.append(cells)
        grid = _render_grid(rows)
        if grid:
            out.append(grid)
        block.clear()

    for line in lines:
        # A pipe row has a leading/trailing pipe or at least two internal pipes.
        stripped = line.strip()
        is_pipe_row = stripped.startswith("|") or (stripped.count("|") >= 2 and stripped.endswith("|"))
        if is_pipe_row:
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "\n".join(out)


def html_to_plaintext(body: str) -> str:
    """Convert an HTML (or HTML+markdown) email body to a readable text/plain alternative.

    Tables — HTML ``<table>`` and markdown pipe tables — become aligned text grids; all other
    HTML tags are removed and entities decoded. The result contains no raw HTML tag and no raw
    markdown table row (W28E-1885 D-010).
    """
    if not isinstance(body, str) or not body:
        return body if isinstance(body, str) else ""

    # 0) Drop non-content blocks entirely (head/style/script) so CSS or metadata never leaks
    #    into the reader's plain text.
    text = _NON_CONTENT_BLOCK.sub("", body)

    # 1) HTML tables -> aligned text (before the generic tag strip removes their structure).
    text = _HTML_TABLE.sub(_html_table_to_text, text)

    # 2) Block-level HTML -> line breaks so content does not run together.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|h[1-6]|li|tr|ul|ol|table|blockquote)>", "\n", text, flags=re.I)
    text = re.sub(r"<li\b[^>]*>", "- ", text, flags=re.I)

    # 3) Remove every remaining tag and decode entities.
    text = _ANY_TAG.sub("", text)
    text = html.unescape(text)

    # 4) Any markdown pipe tables that were never converted to HTML -> aligned text.
    text = _convert_markdown_pipe_tables(text)

    # 5) Tidy whitespace.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
