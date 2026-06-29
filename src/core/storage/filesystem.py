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
Filesystem storage backend for local directory storage.

Thin wrapper around ``cloud_dog_storage.LocalStorage`` that preserves
the original ``StorageBackend`` / ``FilesystemBackend`` API contract
used by the file-channel delivery layer.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage
from cloud_dog_storage import StorageFileNotFoundError as _PlatformFileNotFoundError

from src.utils.logger import get_logger
from .base import (
    StorageBackend,
    StoredFile,
    StorageError,
    ConfigurationError,
    FileNotFoundError as StorageFileNotFoundError,
)

logger = get_logger(__name__)


class FilesystemBackend(StorageBackend):
    """
    Filesystem storage backend.

    Delegates all I/O to ``cloud_dog_storage.LocalStorage`` while
    preserving the existing async API surface expected by callers.
    """

    def validate_config(self) -> None:
        """Validate filesystem configuration"""
        required_fields = ["base_path"]

        for field in required_fields:
            if field not in self.config:
                raise ConfigurationError(f"Missing required field: {field}")

        base_path = self.config["base_path"]

        if not base_path:
            raise ConfigurationError("base_path cannot be empty")

        # Sanitize and expand path
        base_path = os.path.expanduser(base_path)
        base_path = os.path.abspath(base_path)
        self.config["base_path"] = base_path

        # Validate / normalise permissions
        self.config["permissions"] = self._normalise_permissions(
            self.config.get("permissions"), fallback=0o644
        )
        self.config["dir_permissions"] = self._normalise_permissions(
            self.config.get("dir_permissions"), fallback=0o755
        )

        # Build the platform storage backend
        self._storage = _PlatformLocalStorage(
            root_path=base_path,
            file_permissions=oct(self.config["permissions"]),
            dir_permissions=oct(self.config["dir_permissions"]),
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_permissions(perms, *, fallback: int) -> int:
        """Return an integer file-mode from various input formats."""
        if perms is None:
            return fallback
        if isinstance(perms, str):
            try:
                return int(perms, 8)
            except ValueError:
                raise ConfigurationError(f"Invalid permissions: {perms}")
        if isinstance(perms, int):
            if perms <= 0o777:
                return perms
            perms_str = str(perms)
            try:
                return int(perms_str, 8)
            except ValueError:
                raise ConfigurationError(f"Invalid permissions: {perms}")
        return fallback

    def _sanitize_path(self, path: str) -> str:
        """Sanitize path to prevent directory traversal attacks."""
        path = path.replace("..", "")
        path = path.lstrip("/")
        path = path.replace("//", "/")
        return path

    def _create_directory_structure(self, filename: str) -> str:
        """
        Build the logical path (relative to base_path) for *filename*,
        honouring subdirectory patterns when configured.

        Returns the relative POSIX path string (no leading slash).
        """
        filename = self._sanitize_path(filename)
        has_subpath = "/" in filename

        if self.config.get("create_subdirs", False) and not has_subpath:
            subdir_pattern = self.config.get("subdir_pattern", "{year}/{month}/{day}")
            now = datetime.now()
            subdir = subdir_pattern.format(
                year=now.strftime("%Y"),
                month=now.strftime("%m"),
                day=now.strftime("%d"),
            )
            subdir = self._sanitize_path(subdir)
            rel_path = f"{subdir}/{filename}"
        else:
            rel_path = filename

        return rel_path

    def _abs_path(self, rel_path: str) -> str:
        """Return the absolute POSIX path inside the storage root."""
        base = self.config["base_path"].rstrip("/")
        return f"{base}/{rel_path}"

    # ------------------------------------------------------------------
    # public async API (unchanged contract)
    # ------------------------------------------------------------------

    async def store_file(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StoredFile:
        """Store file to filesystem via cloud_dog_storage."""
        rel_path = self._create_directory_structure(filename)
        abs_path = self._abs_path(rel_path)

        try:
            self._storage.write_bytes(abs_path, content)
        except Exception as e:
            raise StorageError(f"Failed to store file {abs_path}: {e}")

        logger.info(f"Stored file: {abs_path} ({len(content)} bytes)")

        file_format = filename.rsplit(".", 1)[-1] if "." in filename else "unknown"

        return StoredFile(
            path=abs_path,
            format=file_format,
            size_bytes=len(content),
            storage_type="filesystem",
            metadata=metadata or {},
        )

    async def exists(self, path: str) -> bool:
        """Check if file exists in filesystem."""
        path = self._sanitize_path(path)
        base_path = Path(self.config["base_path"])
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = base_path / file_path

        abs_str = str(file_path.resolve())
        try:
            file_path.resolve().relative_to(base_path)
        except ValueError:
            return False

        stat = self._storage.stat(abs_str)
        return stat is not None and not stat.is_dir

    async def delete_file(self, path: str) -> bool:
        """Delete file from filesystem."""
        path = self._sanitize_path(path)
        base_path = Path(self.config["base_path"])
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = base_path / file_path

        abs_str = str(file_path.resolve())
        try:
            file_path.resolve().relative_to(base_path)
        except ValueError:
            raise StorageError(f"Path {path} is outside base directory")

        if not self._storage.exists(abs_str):
            return False

        try:
            self._storage.delete_path(abs_str)
            logger.info(f"Deleted file: {abs_str}")
            return True
        except Exception as e:
            raise StorageError(f"Failed to delete file {abs_str}: {e}")

    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        path = self._sanitize_path(path)
        base_path = Path(self.config["base_path"])
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = base_path / file_path

        abs_str = str(file_path.resolve())
        try:
            file_path.resolve().relative_to(base_path)
            return self._storage.exists(abs_str)
        except Exception:
            return False

    async def get_file_url(self, path: str) -> str:
        """Get file:// URL for file."""
        path = self._sanitize_path(path)
        base_path = Path(self.config["base_path"])
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = base_path / file_path

        abs_str = str(file_path.resolve())
        try:
            file_path.resolve().relative_to(base_path)
        except Exception as e:
            raise StorageError(f"Invalid path {path}: {e}")

        return self._storage.get_url(abs_str)

    async def get_file_content(self, path: str) -> bytes:
        """Retrieve file content."""
        path = self._sanitize_path(path)
        base_path = Path(self.config["base_path"])
        file_path = Path(path)

        if not file_path.is_absolute():
            file_path = base_path / file_path

        abs_str = str(file_path.resolve())
        try:
            file_path.resolve().relative_to(base_path)
        except Exception as e:
            raise StorageError(f"Invalid path {path}: {e}")

        try:
            return self._storage.read_bytes(abs_str)
        except _PlatformFileNotFoundError:
            raise StorageFileNotFoundError(f"File not found: {path}")
        except Exception as e:
            raise StorageError(f"Failed to read file {abs_str}: {e}")
