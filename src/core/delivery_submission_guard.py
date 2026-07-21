"""Dependency-free outbound submission safety checks.

These checks intentionally live outside the API module so they can be verified
without starting the service or loading its runtime configuration.
"""

from __future__ import annotations

import re
from typing import Any

UNRESOLVED_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}|\$\{|\{\{")
SUBJECT_BEARING_CHANNEL_TYPES = frozenset({"smtp", "email"})


def find_unresolved_placeholder(text: Any) -> str | None:
    """Return the first unsubstituted template token, or ``None``."""
    if not isinstance(text, str) or not text:
        return None
    match = UNRESOLVED_PLACEHOLDER_RE.search(text)
    return match.group(0) if match else None
