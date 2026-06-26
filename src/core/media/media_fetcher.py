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
Description: Shared-transfer-backed media fetcher for Notification Agent MCP Server.

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3.1
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20
**************************************************
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple
from urllib.parse import urlparse

from cloud_dog_storage import fetch_uri
from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

from src.utils.logger import get_logger

from .audio_handler import AudioHandler
from .image_handler import ImageHandler
from .video_handler import VideoHandler

logger = get_logger(__name__)
_fs = _PlatformLocalStorage(root_path="/")


class URIHandler:
    """
    Handles fetching images from URIs (HTTP/HTTPS URLs and local file paths).
    """

    def __init__(
        self,
        image_handler: Optional[ImageHandler] = None,
        audio_handler: Optional[AudioHandler] = None,
        video_handler: Optional[VideoHandler] = None,
        timeout: int = 30,
    ):
        self.image_handler = image_handler or ImageHandler()
        self.audio_handler = audio_handler or AudioHandler()
        self.video_handler = video_handler or VideoHandler()
        self.timeout = timeout
        logger.info(f"URIHandler initialized with timeout={timeout}s")

    def parse_uri(self, uri: str) -> dict[str, Any]:
        """Parse URI and determine whether it targets HTTP(S) or a local path."""
        if not uri:
            return {"type": None, "parsed": None, "is_local": False}

        parsed = urlparse(uri)
        if parsed.scheme in ["http", "https"]:
            return {
                "type": parsed.scheme,
                "parsed": parsed,
                "is_local": False,
                "url": uri,
            }

        if parsed.scheme == "file":
            return {
                "type": "file",
                "parsed": parsed,
                "is_local": True,
                "path": uri,
            }

        if _fs.exists(uri) or uri.startswith("/") or uri.startswith("./") or "\\" in uri or ":" in uri:
            return {
                "type": "file",
                "parsed": None,
                "is_local": True,
                "path": uri,
            }

        path = Path(uri)
        if _fs.exists(str(path.resolve())) or path.is_absolute():
            return {
                "type": "file",
                "parsed": None,
                "is_local": True,
                "path": str(path),
            }

        return {"type": None, "parsed": None, "is_local": False}

    def fetch_from_http(self, url: str, media_type: str = "image") -> Optional[Tuple[bytes, str]]:
        """Fetch media from HTTP/HTTPS URL via the shared transfer helper."""
        return self._fetch_from_uri(url, media_type)

    def fetch_from_file(self, file_path: str, media_type: str = "image") -> Optional[Tuple[bytes, str]]:
        """Fetch media from local file via the shared transfer helper."""
        return self._fetch_from_uri(file_path, media_type)

    def fetch_image(self, uri: str) -> Optional[Tuple[bytes, str]]:
        return self.fetch_media(uri, "image")

    def fetch_audio(self, uri: str) -> Optional[Tuple[bytes, str]]:
        return self.fetch_media(uri, "audio")

    def fetch_video(self, uri: str) -> Optional[Tuple[bytes, str]]:
        return self.fetch_media(uri, "video")

    def fetch_media(self, uri: str, media_type: str = "image") -> Optional[Tuple[bytes, str]]:
        if not uri:
            return None

        parsed = self.parse_uri(uri)
        if parsed["type"] in ["http", "https"]:
            return self.fetch_from_http(parsed["url"], media_type)
        if parsed["type"] == "file":
            return self.fetch_from_file(parsed["path"], media_type)

        logger.warning(f"Unsupported URI type: {uri}")
        return None

    def validate_uri(self, uri: str) -> Tuple[bool, Optional[str]]:
        """Validate URI accessibility and media compatibility."""
        if not uri:
            return False, "URI is empty"

        result = self.fetch_image(uri)
        if result is None:
            return False, f"Unsupported URI type or unreadable resource: {uri}"
        return True, None

    def _fetch_from_uri(self, uri: str, media_type: str) -> Optional[Tuple[bytes, str]]:
        if not uri:
            return None

        try:
            parsed = self.parse_uri(uri)
            if parsed["type"] not in {"http", "https", "file"}:
                logger.warning(f"Unsupported URI type for fetch: {uri}")
                return None
            media_data = fetch_uri(uri, timeout_seconds=float(self.timeout))

            format_str = self._validate_media(uri, media_data, media_type)
            if not format_str:
                return None
            logger.info(
                f"Successfully fetched {media_type} from {uri}: {len(media_data)} bytes, format={format_str}"
            )
            return media_data, format_str
        except FileNotFoundError:
            logger.warning(f"File does not exist: {uri}")
            return None
        except OSError as exc:
            logger.error(f"Error fetching {media_type} from {uri}: {exc}")
            return None
        except Exception as exc:
            logger.error(f"Error fetching {media_type} from {uri}: {exc}")
            return None

    def _validate_media(self, uri: str, media_data: bytes, media_type: str) -> Optional[str]:
        if media_type == "image":
            is_valid, error = self.image_handler.validate_image(media_data)
            if not is_valid:
                logger.warning(f"Fetched image is invalid: {error}")
                return None
            format_value = self.image_handler.detect_format(media_data)
        elif media_type == "audio":
            is_valid, error = self.audio_handler.validate_audio(media_data)
            if not is_valid:
                logger.warning(f"Fetched audio is invalid: {error}")
                return None
            format_value = self.audio_handler.detect_format(media_data)
        elif media_type == "video":
            is_valid, error = self.video_handler.validate_video(media_data)
            if not is_valid:
                logger.warning(f"Fetched video is invalid: {error}")
                return None
            format_value = self.video_handler.detect_format(media_data)
        else:
            logger.warning(f"Unsupported media type: {media_type}")
            return None

        if not format_value:
            logger.warning(f"Could not detect {media_type} format from fetched data at {uri}")
            return None

        return format_value.value
