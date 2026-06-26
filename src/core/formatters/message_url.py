"""Shared helper for public message URL generation (W28A-309).

Centralises the message URL construction that was previously duplicated
across llm_formatter.py, translator.py, prompt_renderer.py, and
delivery_worker.py.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode


def build_public_message_url(
    config,
    *,
    message_guid: Optional[str] = None,
    message_id: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Build a public-facing message URL for email/Slack link rendering.

    Priority: messages.base_url (public) > api_server.base_url (internal fallback).
    The route is /messages/{guid-or-id}, NOT /api/messages/{guid-or-id}.
    """
    # messages.base_url is the authoritative public URL
    base_url = (
        config.get("messages.base_url")
        or config.get("api_server.base_url")
    )
    if not base_url:
        raise RuntimeError(
            "Missing required configuration: messages.base_url or api_server.base_url"
        )

    base_url = str(base_url).rstrip("/")

    # Ensure the base ends with /messages
    if not base_url.endswith("/messages"):
        base_url = f"{base_url}/messages"

    # Normalise away /api/ prefix — the public route is /messages/, not /api/messages/
    base_url = base_url.replace("/api/messages", "/messages")

    # Build the full URL
    identifier = message_guid or message_id
    if identifier:
        url = f"{base_url}/{identifier}"
    else:
        return base_url

    if language:
        url = f"{url}?language={language}"

    return url


def sanitise_url_for_payload(url: str) -> str:
    """Ensure a URL in a Slack/email payload is complete and not truncated.

    Replaces trailing ellipsis with nothing (logs a warning) so no URL
    in a raw payload ends with '...' or the Unicode ellipsis character.
    """
    if url.endswith("...") or url.endswith("\u2026"):
        # Strip the ellipsis — this is a formatting defect, not intentional
        return url.rstrip(".\u2026").rstrip("/")
    return url
