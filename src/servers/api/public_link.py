#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
#
# Licensed under the Apache License, Version 2.0

"""Pure path checks for anonymous message capability URLs."""

from __future__ import annotations


def is_public_message_read_path(path: str, api_base_path: str) -> bool:
    """Return whether path is exactly one message read under a supported API prefix."""
    prefixes = ["/messages/"]
    normalised_base = str(api_base_path or "").strip().rstrip("/")
    if normalised_base and normalised_base != "/":
        if not normalised_base.startswith("/"):
            normalised_base = f"/{normalised_base}"
        prefixes.append(f"{normalised_base}/messages/")

    for prefix in prefixes:
        if not path.startswith(prefix):
            continue
        message_identifier = path[len(prefix):]
        return bool(message_identifier) and "/" not in message_identifier
    return False
