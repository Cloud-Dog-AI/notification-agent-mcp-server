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

"""External Publication Endpoint asset publisher (EPE §5.1/§5.3).

Uploads a delivery's assets (inline CID images, PDF, HTML) to the public object store and
returns the public URL map used by ``rewrite`` to rewrite the payload internal->external.

Key scheme (EPE §5.3): ``<group>/<message-guid>/<sha256-prefix>.<ext>`` under the per-server
public bucket. Content-addressed => idempotent re-publish + per-group asset reuse (the same
bytes referenced by N recipients in a group upload once). Reuses the existing ``S3Backend``.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from src.utils.logger import get_logger

try:
    import aioboto3
    HAS_AIOBOTO3 = True
except Exception:  # pragma: no cover
    HAS_AIOBOTO3 = False

logger = get_logger(__name__)

_EXT_BY_CT = {
    "image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/gif": "gif",
    "image/svg+xml": "svg", "application/pdf": "pdf", "text/html": "html",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", (value or "").strip().lower()).strip("-") or "default"


class AssetPublisher:
    """Publishes assets for one message/group to the External Publication Endpoint."""

    def __init__(self, config: Dict[str, Any]):
        """``config`` = the ``publication`` block (bucket/endpoint/keys/region/public_base_url).

        ``public_base_url`` is used for the rewritten links. If it is a not-yet-resolvable custom
        domain, set it (in config/env) to the S3 website endpoint so links work; the value here is
        used verbatim.
        """
        self.public_base_url = str(config.get("public_base_url") or "").rstrip("/")
        self._bucket = config.get("bucket")
        self._endpoint = config.get("endpoint")
        self._access_key = config.get("access_key") or config.get("access_key_id")
        self._secret_key = config.get("secret_key") or config.get("secret_access_key")
        self._region = config.get("region", "us-east-1")
        self._seen: Dict[str, str] = {}  # sha256 -> public_url (per-instance dedup)

    def _public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    async def _put(self, group: str, guid: str, content: bytes, content_type: str) -> str:
        """Upload ``content`` (dedup by sha256) and return its public URL.

        Uploads WITHOUT an object ACL — the public bucket grants read via its bucket policy and
        the service IAM identity is not authorised for ``s3:PutObjectAcl``.
        """
        digest = hashlib.sha256(content).hexdigest()[:16]
        if digest in self._seen:
            return self._seen[digest]
        ext = _EXT_BY_CT.get((content_type or "").lower().split(";")[0], "bin")
        key = f"{_slug(group)}/{guid}/{digest}.{ext}"
        session = aioboto3.Session(aws_access_key_id=self._access_key,
                                   aws_secret_access_key=self._secret_key, region_name=self._region)
        async with session.client("s3", endpoint_url=self._endpoint) as s3:
            await s3.put_object(Bucket=self._bucket, Key=key, Body=content,
                                ContentType=content_type or "application/octet-stream",
                                Metadata={"group": _slug(group), "message": guid})
        url = self._public_url(key)
        self._seen[digest] = url
        logger.info("EPE: published %s (%d bytes) -> %s", content_type, len(content), url)
        return url

    async def publish(
        self,
        *,
        group: str,
        message_guid: str,
        inline_images: Optional[List[Dict[str, Any]]] = None,
        pdf_bytes: Optional[bytes] = None,
        internal_url_map: Optional[Dict[str, bytes]] = None,
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Publish all assets. Returns ``(cid_url_map, url_replacements)`` for ``rewrite``.

        * ``inline_images``: ``[{content_id, data(base64), content_type}]`` -> cid_url_map.
        * ``pdf_bytes``: optional generated PDF -> included in url_replacements under a stable key.
        * ``internal_url_map``: ``{internal_url -> raw bytes}`` for internal storage URLs to publish.
        """
        cid_url_map: Dict[str, str] = {}
        url_replacements: Dict[str, str] = {}
        for img in inline_images or []:
            if not isinstance(img, dict):
                continue
            cid = img.get("content_id") or img.get("cid")
            data = img.get("data") or img.get("content")
            ct = img.get("content_type") or "image/png"
            if not (cid and isinstance(data, str) and data):
                continue
            try:
                raw = base64.b64decode(data)
            except Exception:  # noqa: BLE001
                continue
            cid_url_map[str(cid)] = await self._put(group, message_guid, raw, ct)
        for internal_url, raw in (internal_url_map or {}).items():
            if isinstance(raw, (bytes, bytearray)) and raw:
                url_replacements[internal_url] = await self._put(group, message_guid, bytes(raw), "application/octet-stream")
        if pdf_bytes:
            url_replacements["__pdf__"] = await self._put(group, message_guid, pdf_bytes, "application/pdf")
        return cid_url_map, url_replacements
