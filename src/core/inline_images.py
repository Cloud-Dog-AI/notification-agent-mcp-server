#!/usr/bin/env python3
# Copyright 2026 Cloud-Dog, Viewdeck Engineering Limited
# SPDX-License-Identifier: Apache-2.0

"""Inline CID image reference validation and resolution."""

from __future__ import annotations

from typing import Any, Callable

from cloud_dog_storage import build_storage_backend, detect_content_type, encode_base64, fetch_uri
from cloud_dog_storage.config import S3Config, StorageConfig


INLINE_IMAGE_REFERENCE_FIELDS = ("data", "storage_path", "url")
DEFAULT_MAX_INLINE_IMAGE_BYTES = 10 * 1024 * 1024


def normalise_inline_images(value: Any) -> list[dict[str, Any]]:
    """Validate inline_images[] and require exactly one data/storage_path/url field."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError("inline_images must be an array")

    images: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"inline_images[{index}] must be an object")

        content_id = str(item.get("content_id") or "").strip()
        if not content_id:
            raise ValueError(f"inline_images[{index}].content_id is required")

        present = [
            field for field in INLINE_IMAGE_REFERENCE_FIELDS
            if item.get(field) not in (None, "")
        ]
        if len(present) != 1:
            raise ValueError(
                f"inline_images[{index}] must include exactly one of data, storage_path, or url"
            )

        image: dict[str, Any] = {"content_id": content_id}
        field = present[0]
        image[field] = str(item[field]).strip() if field != "data" else str(item[field])
        if field == "url" and image[field].lower().startswith("data:"):
            raise ValueError(f"inline_images[{index}].url must not be a data: URL")

        content_type = item.get("content_type")
        if content_type:
            image["content_type"] = str(content_type).strip().lower()
        filename = item.get("filename")
        if filename:
            image["filename"] = str(filename).strip()
        images.append(image)
    return images


def resolve_inline_image_references(
    inline_images: Any,
    *,
    config: Any = None,
    storage_backend: Any = None,
    fetcher: Callable[[str], bytes] = fetch_uri,
    max_bytes: int | None = None,
) -> list[dict[str, Any]]:
    """Resolve storage_path/url inline images to the legacy {data: base64} shape."""
    images = normalise_inline_images(inline_images)
    if not images:
        return []

    limit = _max_inline_image_bytes(config, max_bytes)
    backend = storage_backend
    resolved: list[dict[str, Any]] = []
    for index, image in enumerate(images):
        if image.get("data") is not None:
            resolved.append(dict(image))
            continue

        if image.get("storage_path") is not None:
            if backend is None:
                backend = _build_storage_backend(config)
            payload = backend.read_bytes(image["storage_path"])
            source_name = image.get("filename") or image["storage_path"]
        else:
            payload = fetcher(image["url"])
            source_name = image.get("filename") or image["url"]

        if len(payload) > limit:
            raise ValueError(
                f"inline_images[{index}] exceeds max inline image size of {limit} bytes"
            )

        content_type = image.get("content_type") or detect_content_type(str(source_name), payload)
        if not str(content_type).lower().startswith("image/"):
            raise ValueError(f"inline_images[{index}] content_type must be image/*")

        item = {
            "content_id": image["content_id"],
            "content_type": str(content_type).lower(),
            "data": encode_base64(payload),
        }
        if image.get("filename"):
            item["filename"] = image["filename"]
        resolved.append(item)
    return resolved


def _max_inline_image_bytes(config: Any, explicit: int | None) -> int:
    if explicit is not None:
        return int(explicit)
    if config is not None and hasattr(config, "get"):
        for key in (
            "notification.inline_images.max_bytes",
            "media.inline_images.max_bytes",
            "media.max_inline_image_bytes",
        ):
            value = config.get(key)
            if value not in (None, ""):
                return int(value)
    return DEFAULT_MAX_INLINE_IMAGE_BYTES


def _build_storage_backend(config: Any):
    backend_name = "local"
    root_path = ""
    s3_options: dict[str, Any] = {}
    if config is not None and hasattr(config, "get"):
        backend_name = str(config.get("storage.backend", "local") or "local")
        root_path = str(
            config.get("storage.root_path")
            or config.get("storage.path")
            or config.get(f"storage.{backend_name}.root_path")
            or config.get(f"storage.{backend_name}.path")
            or ""
        )
        raw_s3 = config.get("storage.s3", {}) or {}
        if isinstance(raw_s3, dict):
            s3_options.update(raw_s3)
        for key in ("endpoint", "bucket", "region", "access_key", "secret_key", "prefix"):
            value = config.get(f"storage.s3.{key}")
            if value not in (None, ""):
                s3_options[key] = value

    return build_storage_backend(
        StorageConfig(
            backend=backend_name,
            root_path=root_path,
            s3=S3Config(**s3_options),
        )
    )
