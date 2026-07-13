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

"""Publication routing resolver (EPE §4).

Deterministically decides, per delivery (message x recipient x channel), whether the
delivery is published to the External Publication Endpoint (``external``) or kept
``internal``. The precedence is fixed; the first rule that fires decides:

  RG-1  feature off / no channel policy          -> internal
  RG-2  endpoint matches out_of_scope_regex       -> internal   (HARD; always wins)
  RG-3  recipient override in {internal,external} -> that mode
  RG-4  scope_regex set and endpoint NOT in scope  -> internal
  RG-5  channel default                            -> default

RG-2 is the isolation guard: an address on an internal domain can never be forced
external by any per-recipient override (EPE FR-EPE-042). This module is pure logic
(no I/O), so the whole truth table is unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

INTERNAL = "internal"
EXTERNAL = "external"
_VALID_MODES = frozenset({INTERNAL, EXTERNAL})
_OVERRIDE_INHERIT = "inherit"


@dataclass(frozen=True)
class PublicationPolicy:
    """Per-channel publication policy (from ``channel.config_json.publication``)."""

    enabled: bool = False
    default: str = INTERNAL
    scope_regex: Optional[str] = None
    out_of_scope_regex: Optional[str] = None

    @classmethod
    def from_config(cls, channel_publication: Optional[dict], *, feature_enabled: bool) -> "PublicationPolicy":
        """Build a policy from a channel's ``publication`` config block.

        ``feature_enabled`` is the server-wide ``publication.enabled`` flag; when it is
        false, or the channel has no publication block, the policy is disabled (RG-1).
        """
        if not feature_enabled or not isinstance(channel_publication, dict):
            return cls(enabled=False)
        default = str(channel_publication.get("default") or INTERNAL).strip().lower()
        if default not in _VALID_MODES:
            default = INTERNAL
        return cls(
            enabled=True,
            default=default,
            scope_regex=channel_publication.get("scope_regex") or None,
            out_of_scope_regex=channel_publication.get("out_of_scope_regex") or None,
        )


@dataclass(frozen=True)
class RouteDecision:
    """Outcome of :func:`resolve_publication_mode` — carries the audit trail."""

    mode: str            # "internal" | "external"
    rule_id: str         # "RG-1".."RG-5"
    matched_pattern: Optional[str] = None

    @property
    def is_external(self) -> bool:
        return self.mode == EXTERNAL


def _safe_search(pattern: Optional[str], value: str) -> bool:
    """Regex search that never raises: a malformed pattern is treated as 'no match'.

    A malformed ``out_of_scope`` pattern therefore does NOT accidentally force-internal
    (fails open to the rest of the precedence), and a malformed ``scope`` pattern does
    NOT accidentally admit an address to external (RG-4 falls through to no-match ->
    internal). Both malformed cases err toward NOT publishing externally.
    """
    if not pattern:
        return False
    try:
        return re.search(pattern, value or "") is not None
    except re.error:
        return False


def resolve_publication_mode(
    policy: PublicationPolicy,
    endpoint_address: str,
    recipient_override: Optional[str] = None,
) -> RouteDecision:
    """Resolve the publication mode for one delivery (EPE §4).

    ``endpoint_address`` is the recipient's channel address (email, slack id, ...).
    ``recipient_override`` is the recipient ``preferences.publication_mode`` — one of
    ``internal`` / ``external`` / ``inherit`` (or None == inherit).
    """
    # RG-1: feature off or no channel policy.
    if not policy.enabled:
        return RouteDecision(INTERNAL, "RG-1")

    # RG-2: hard deny — an out-of-scope (internal-domain) address is ALWAYS internal.
    if _safe_search(policy.out_of_scope_regex, endpoint_address):
        return RouteDecision(INTERNAL, "RG-2", policy.out_of_scope_regex)

    # RG-3: explicit per-recipient override (already past the RG-2 guard).
    override = (recipient_override or _OVERRIDE_INHERIT).strip().lower()
    if override in _VALID_MODES:
        return RouteDecision(override, "RG-3")

    # RG-4: scope gate — if a scope regex is set, only matching addresses are eligible.
    if policy.scope_regex is not None and not _safe_search(policy.scope_regex, endpoint_address):
        return RouteDecision(INTERNAL, "RG-4", policy.scope_regex)

    # RG-5: channel default.
    return RouteDecision(policy.default, "RG-5")
