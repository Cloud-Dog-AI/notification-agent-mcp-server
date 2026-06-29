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
Storage backends for file channel delivery.

Provides multiple storage backend implementations:
- Filesystem: Local directory storage
- WebDAV: WebDAV-compatible servers (Nextcloud, ownCloud, etc.)
- S3: S3-compatible object storage (AWS S3, MinIO, etc.)
- FTP: FTP/FTPS servers
"""

from .base import (
    StorageBackend,
    StoredFile,
    StorageError,
    ConfigurationError,
    FileNotFoundError,
    PermissionError,
    QuotaExceededError
)
from .filesystem import FilesystemBackend
from .webdav import WebDAVBackend
from .s3 import S3Backend
from .ftp import FTPBackend
from .factory import StorageFactory

__all__ = [
    "StorageBackend",
    "StoredFile",
    "StorageError",
    "ConfigurationError",
    "FileNotFoundError",
    "PermissionError",
    "QuotaExceededError",
    "FilesystemBackend",
    "WebDAVBackend",
    "S3Backend",
    "FTPBackend",
    "StorageFactory"
]
