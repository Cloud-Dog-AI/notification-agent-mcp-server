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
Description: Local filesystem storage backend for notification files

Related Requirements: FR1.18, FR1.19, FR1.20
Related Tasks: T29, T30, T31
Related Architecture: CC6.1.3
Related Tests: UT1.13, ST1.4, IT1.16, AT1.22

Recent Changes (max 10):
- Migrated to cloud_dog_storage.LocalStorage delegate

**************************************************
"""

from typing import Optional, Dict, Any

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

from src.utils.logger import get_logger
from .storage_manager import StorageBackend

logger = get_logger(__name__)


class LocalStorage(StorageBackend):
    """Local filesystem storage backend (delegates to cloud_dog_storage)."""

    def __init__(self, base_path: str):
        """
        Initialize local storage backend

        Args:
            base_path: Base directory path for storage (e.g., "storage/" or "/var/notify/storage")
        """
        self._storage = _PlatformLocalStorage(root_path=base_path)
        self.base_path = self._storage._root
        logger.info(f"LocalStorage initialized with base_path: {self.base_path}")

    def _abs(self, file_path: str) -> str:
        """Return the absolute path for *file_path* relative to base."""
        return str(self.base_path / file_path)

    def store_file(
        self,
        file_content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Store a file in local filesystem

        Args:
            file_content: File content as bytes
            file_path: Path where file should be stored (relative to base_path)
            metadata: Optional metadata

        Returns:
            Dict with storage_path, storage_uri, file_size, mime_type
        """
        abs_path = self._abs(file_path)

        try:
            self._storage.write_bytes(abs_path, file_content)

            file_size = len(file_content)
            storage_uri = self._storage.get_url(abs_path)

            result = {
                "storage_path": file_path,
                "storage_uri": storage_uri,
                "file_size": file_size,
                "mime_type": metadata.get("mime_type") if metadata else None,
            }

            logger.info(f"Stored file: {file_path} ({file_size} bytes)")
            return result

        except Exception as e:
            logger.error(f"Failed to store file {file_path}: {e}")
            raise

    def retrieve_file(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve a file from local filesystem

        Args:
            file_path: Path to file (relative to base_path)

        Returns:
            File content as bytes, or None if not found
        """
        abs_path = self._abs(file_path)

        if not self._storage.exists(abs_path):
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            content = self._storage.read_bytes(abs_path)
            logger.debug(f"Retrieved file: {file_path} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_path}: {e}")
            return None

    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from local filesystem

        Args:
            file_path: Path to file (relative to base_path)

        Returns:
            True if deleted, False otherwise
        """
        abs_path = self._abs(file_path)

        if not self._storage.exists(abs_path):
            logger.warning(f"File not found for deletion: {file_path}")
            return False

        try:
            self._storage.delete_path(abs_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in local filesystem

        Args:
            file_path: Path to file (relative to base_path)

        Returns:
            True if file exists, False otherwise
        """
        abs_path = self._abs(file_path)
        stat = self._storage.stat(abs_path)
        return stat is not None and not stat.is_dir

    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get file size in bytes

        Args:
            file_path: Path to file (relative to base_path)

        Returns:
            File size in bytes, or None if not found
        """
        abs_path = self._abs(file_path)
        stat = self._storage.stat(abs_path)
        if stat is None:
            return None

        try:
            return stat.size
        except Exception as e:
            logger.error(f"Failed to get file size for {file_path}: {e}")
            return None
