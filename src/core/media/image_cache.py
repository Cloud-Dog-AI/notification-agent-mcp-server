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
Description: Image cache backed by cloud_dog_cache — replaces bespoke ImageCacheManager (W28A-93b §1.4 compliance)

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3.2
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20

Recent Changes (max 10):
- 2026-05-07: Replaced bespoke ImageCacheManager with cloud_dog_cache-backed implementation (W28A-93b)

**************************************************
"""
from typing import Optional, Dict, Any, Tuple
import asyncio
import hashlib
import inspect

from cloud_dog_cache import get_cache_manager, init_cache

from src.utils.logger import get_logger
from .image_handler import ImageHandler
from .media_fetcher import URIHandler
from ..storage.storage_manager import StorageManager

logger = get_logger(__name__)

_DEFAULT_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days


class ImageCacheManager:
    """Image cache backed by cloud_dog_cache.

    Retains the same public API as the previous bespoke implementation
    so existing callers and tests continue to work.
    """

    def __init__(
        self,
        storage_manager: StorageManager,
        image_handler: Optional[ImageHandler] = None,
        uri_handler: Optional[URIHandler] = None,
        max_cache_size_mb: int = 100,
        cache_ttl_days: int = 30,
    ):
        self.storage_manager = storage_manager
        self.image_handler = image_handler or ImageHandler()
        self.uri_handler = uri_handler or URIHandler(image_handler=self.image_handler)
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
        self._cache_ttl_seconds = cache_ttl_days * 24 * 3600
        self._cache = get_cache_manager() or init_cache()
        logger.info(
            "ImageCacheManager initialized (cloud_dog_cache): "
            f"max_size={max_cache_size_mb}MB, ttl={cache_ttl_days} days"
        )

    @staticmethod
    def _generate_cache_key(uri: str) -> str:
        return hashlib.sha256(uri.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata_cache_key(cache_key: str) -> str:
        return f"image-cache:metadata:{cache_key}"

    def _get_cache_path(self, cache_key: str, fmt: str) -> str:
        return f"cache/images/{cache_key[:2]}/{cache_key}.{fmt}"

    def _cache_call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        try:
            asyncio.get_running_loop()
            return None
        except RuntimeError:
            result = getattr(self._cache, method_name)(*args, **kwargs)
            if inspect.isawaitable(result):
                return asyncio.run(result)
            return result

    def cache_image(self, uri: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        if not uri:
            return None

        if not force_refresh:
            existing = self.get_cached_image(uri)
            if existing:
                logger.debug(f"Image already cached: {uri}")
                return existing

        result = self.uri_handler.fetch_image(uri)
        if not result:
            logger.warning(f"Failed to fetch image from URI: {uri}")
            return None

        image_data, fmt = result
        cache_key = self._generate_cache_key(uri)
        cache_path = self._get_cache_path(cache_key, fmt)

        try:
            self.storage_manager.backend.store_file(
                file_content=image_data,
                file_path=cache_path,
                metadata={"mime_type": f"image/{fmt}"},
            )
            access_url = (
                f"{self.storage_manager.base_url}/{cache_path}"
                if self.storage_manager.base_url
                else None
            )
            from datetime import datetime

            info: Dict[str, Any] = {
                "cache_key": cache_key,
                "cache_path": cache_path,
                "access_url": access_url,
                "original_uri": uri,
                "format": fmt,
                "size_bytes": len(image_data),
                "cached_at": datetime.now().isoformat(),
            }
            self._cache_call(
                "set",
                self._metadata_cache_key(cache_key),
                info,
                ttl=self._cache_ttl_seconds,
                tags=("images",),
            )
            logger.info(f"Cached image: {uri} -> {cache_path}")
            return info
        except Exception as e:
            logger.error(f"Failed to store image in cache: {uri}, error: {e}")
            return None

    def get_cached_image(self, uri: str) -> Optional[Dict[str, Any]]:
        cache_key = self._generate_cache_key(uri)
        cached_info = self._cache_call("get", self._metadata_cache_key(cache_key))
        if isinstance(cached_info, dict):
            cache_path = cached_info.get("cache_path")
            if cache_path and self.storage_manager.file_exists(cache_path):
                return cached_info
            self._cache_call("delete", self._metadata_cache_key(cache_key))

        for fmt in ("png", "jpeg", "jpg", "gif"):
            cache_path = self._get_cache_path(cache_key, fmt)
            if self.storage_manager.file_exists(cache_path):
                file_info = self.storage_manager.get_file_info(cache_path)
                if file_info:
                    access_url = (
                        f"{self.storage_manager.base_url}/{cache_path}"
                        if self.storage_manager.base_url
                        else None
                    )
                    return {
                        "cache_key": cache_key,
                        "cache_path": cache_path,
                        "access_url": access_url,
                        "original_uri": uri,
                        "format": fmt,
                        "size_bytes": file_info.get("file_size", 0),
                        "cached_at": file_info.get("created_at"),
                    }
        return None

    def get_image(
        self,
        uri: str,
        use_cache: bool = True,
        serve_from_cache: bool = False,
    ) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
        if use_cache:
            cached_info = self.get_cached_image(uri)
            if cached_info:
                image_data = self.storage_manager.retrieve_file(cached_info["cache_path"])
                if image_data:
                    logger.debug(f"Serving image from cache: {uri}")
                    return (image_data, cached_info["format"], cached_info)
            if serve_from_cache:
                logger.debug(f"Image not in cache and serve_from_cache=True: {uri}")
                return None

        cache_info = self.cache_image(uri)
        if cache_info:
            image_data = self.storage_manager.retrieve_file(cache_info["cache_path"])
            if image_data:
                return (image_data, cache_info["format"], cache_info)
        return None

    def cleanup_cache(self, max_age_days: Optional[int] = None) -> int:
        """Clean up old cache metadata via cloud_dog_cache flush."""
        try:
            self._cache_call("flush")
        except Exception:
            pass
        return 0
