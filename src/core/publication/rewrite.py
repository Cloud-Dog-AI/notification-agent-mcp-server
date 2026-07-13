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

"""Delivery-payload link rewriter (EPE §5.1/§5.5).

This is the single point at which a delivery's asset references are changed from
internal (``cid:`` MIME parts, internal storage URLs, ``file://``) to external public
URLs. It is mode-gated by the caller: ``internal`` deliveries are returned untouched;
``external`` deliveries are rewritten and their inline ``cid:`` images dropped (they
become ``<img src="https://<public>/...">``).

Pure text transforms + detectors so the isolation invariant is fully unit-testable:
  * ``rewrite_html`` — internal -> external.
  * ``find_internal_refs`` / ``find_external_refs`` — assertions for the isolation tests
    (internal delivery has zero external refs; external delivery has zero internal refs).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

# A cid reference inside an attribute, e.g. src="cid:candidatemap" or src='cid:logo'.
_CID_SRC_RE = re.compile(r"""(?P<pre>src\s*=\s*["'])cid:(?P<cid>[^"']+)(?P<post>["'])""", re.IGNORECASE)
# A bare cid: token (defensive — any residual cid: reference).
_CID_ANY_RE = re.compile(r"cid:[A-Za-z0-9._%+\-@]+")
_FILE_URI_RE = re.compile(r"file://[^\s\"'<>)]+", re.IGNORECASE)


def rewrite_html(
    html: str,
    *,
    cid_url_map: Optional[Dict[str, str]] = None,
    url_replacements: Optional[Dict[str, str]] = None,
) -> str:
    """Rewrite internal references in ``html`` to external public URLs.

    ``cid_url_map``: ``{content_id -> public_url}`` — every ``src="cid:<id>"`` becomes the
      mapped public URL.
    ``url_replacements``: ``{internal_url -> public_url}`` — exact-substring replacement for
      internal storage/absolute URLs (longest keys first so a prefix does not shadow a
      longer match).
    Defensive: on any error returns the input unchanged.
    """
    if not html:
        return html
    try:
        cid_url_map = cid_url_map or {}
        url_replacements = url_replacements or {}

        def _sub_cid(m: "re.Match[str]") -> str:
            target = cid_url_map.get(m.group("cid"))
            if not target:
                return m.group(0)  # no mapping -> leave (detector will flag it)
            return f"{m.group('pre')}{target}{m.group('post')}"

        out = _CID_SRC_RE.sub(_sub_cid, html)

        for internal in sorted(url_replacements, key=len, reverse=True):
            out = out.replace(internal, url_replacements[internal])
        return out
    except Exception:  # noqa: BLE001 — never break delivery on a rewrite error
        return html


def find_internal_refs(text: str, *, internal_hosts: Sequence[str] = ()) -> List[str]:
    """Return every internal reference in ``text`` (``cid:``, ``file://``, internal host URLs).

    Used by the isolation tests (IT-EPE-11): an ``external`` delivery MUST return ``[]``.
    """
    if not text:
        return []
    hits: List[str] = []
    hits += _CID_ANY_RE.findall(text)
    hits += _FILE_URI_RE.findall(text)
    for host in internal_hosts:
        if not host:
            continue
        # any absolute URL that contains the internal host
        hits += re.findall(r"https?://[^\s\"'<>)]*" + re.escape(host) + r"[^\s\"'<>)]*", text, re.IGNORECASE)
    return hits


def find_external_refs(text: str, public_base_url: str) -> List[str]:
    """Return every reference to ``public_base_url`` in ``text``.

    Used by the isolation tests (IT-EPE-10): an ``internal`` delivery MUST return ``[]``.
    """
    if not text or not public_base_url:
        return []
    base = public_base_url.rstrip("/")
    return re.findall(re.escape(base) + r"[^\s\"'<>)]*", text)


def rewrite_delivery_payload(
    payload: dict,
    inline_images: Optional[Sequence[dict]],
    *,
    cid_url_map: Dict[str, str],
    url_replacements: Optional[Dict[str, str]] = None,
) -> Tuple[dict, List[dict]]:
    """Rewrite a built ``personalised_payload`` for an EXTERNAL delivery.

    Rewrites the ``body`` (and any string fields carrying markup) internal->external and
    DROPS the inline_images (they are now external ``<img src="https://...">``). The caller
    only invokes this when the route resolved to ``external``; ``internal`` deliveries are
    never passed here, guaranteeing internal payloads are never touched.
    """
    new_payload = dict(payload or {})
    body = new_payload.get("body")
    if isinstance(body, str):
        new_payload["body"] = rewrite_html(body, cid_url_map=cid_url_map, url_replacements=url_replacements)
    # inline images are now hosted externally; do not attach them as CID parts
    return new_payload, []
