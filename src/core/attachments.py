#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
# SPDX-License-Identifier: Apache-2.0

"""Validation helpers for explicit notification attachments."""

from __future__ import annotations

import base64
import hashlib
from typing import Any


def normalise_attachments(value: Any) -> list[dict[str, Any]]:
    """Validate and normalise explicit attachment descriptors.

    Explicit binary attachments must be supplied as base64 text and may include
    an expected ``sha256``. Text attachments may keep the legacy utf-8 encoding.
    """
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("attachments must be an array")

    attachments: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"attachments[{index}] must be an object")

        filename = str(item.get("filename") or item.get("name") or "").strip()
        if not filename:
            raise ValueError(f"attachments[{index}].filename is required")

        content_type = str(
            item.get("content_type") or item.get("mime_type") or "application/octet-stream"
        ).strip() or "application/octet-stream"
        content = item.get("content")
        data = item.get("data")
        has_content = content not in (None, "")
        has_data = data not in (None, "")
        if has_content == has_data:
            raise ValueError(f"attachments[{index}] must include exactly one of content or data")

        content_value = str(data if has_data else content)
        default_encoding = "utf-8" if content_type.lower().startswith("text/") else "base64"
        encoding = str(item.get("encoding") or default_encoding).strip().lower()
        if encoding == "utf8":
            encoding = "utf-8"

        expected_sha256 = str(item.get("sha256") or "").strip().lower()
        normalised: dict[str, Any] = {
            "filename": filename,
            "content": content_value,
            "content_type": content_type,
        }

        if encoding == "base64":
            try:
                decoded = base64.b64decode(content_value.encode("ascii"), validate=True)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(f"attachments[{index}].content must be valid base64") from exc
            actual_sha256 = hashlib.sha256(decoded).hexdigest()
            if expected_sha256 and expected_sha256 != actual_sha256:
                raise ValueError(
                    f"attachments[{index}].sha256 does not match attachment content"
                )
            normalised["encoding"] = "base64"
            if expected_sha256:
                normalised["sha256"] = expected_sha256
        elif encoding in {"utf-8", "text"}:
            actual_sha256 = hashlib.sha256(content_value.encode("utf-8")).hexdigest()
            if expected_sha256 and expected_sha256 != actual_sha256:
                raise ValueError(
                    f"attachments[{index}].sha256 does not match attachment content"
                )
            normalised["encoding"] = "utf-8"
            if expected_sha256:
                normalised["sha256"] = expected_sha256
        else:
            raise ValueError(f"attachments[{index}].encoding must be base64 or utf-8")

        attachments.append(normalised)

    return attachments
