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
WebDAV storage backend for remote file storage.

Supports WebDAV-compatible servers like:
- Nextcloud
- ownCloud  
- Apache mod_dav
- Microsoft SharePoint

Uses the platform-storage WebDAV backend for protocol operations.
"""

import asyncio
from typing import Dict, Any, Optional
from urllib.parse import urljoin, quote, urlparse
from cloud_dog_storage.backends.webdav import WebDavStorage
from cloud_dog_storage.config.models import TlsConfig, WebDavConfig

from src.utils.logger import get_logger

from .base import StorageBackend, StoredFile, StorageError, ConfigurationError, FileNotFoundError as StorageFileNotFoundError

logger = get_logger(__name__)


class WebDAVBackend(StorageBackend):
    """
    WebDAV storage backend.
    
    Stores files on WebDAV-compatible servers with support for:
    - Basic authentication
    - HTTPS/TLS
    - Directory creation
    - Custom file paths
    """
    
    def validate_config(self) -> None:
        """Validate WebDAV configuration"""
        required_fields = ["url", "username", "password"]
        
        for field in required_fields:
            if field not in self.config:
                raise ConfigurationError(f"Missing required field: {field}")
        
        url = self.config["url"]
        
        if not url:
            raise ConfigurationError("url cannot be empty")
        
        if not url.startswith(("http://", "https://")):
            raise ConfigurationError("url must start with http:// or https://")
        
        # Ensure URL ends with /
        if not url.endswith("/"):
            self.config["url"] = url + "/"
        
        self._backend = WebDavStorage(
            WebDavConfig(
                base_url=self.config["url"],
                username=self.config["username"],
                password=self.config["password"],
                move_retry_count=int(self.config.get("delete_retry_attempts", 3)),
                move_retry_backoff_s=float(self.config.get("delete_retry_delay_seconds", 0.5)),
            ),
            tls=TlsConfig(insecure_skip_verify=not bool(self.config.get("verify_ssl", True))),
            timeout_s=30,
        )
    
    def _get_full_url(self, filename: str) -> str:
        """
        Get full WebDAV URL for filename.
        
        Args:
            filename: Filename (path-safe)
            
        Returns:
            Full WebDAV URL
        """
        base_url = self.config["url"]
        
        # URL-encode filename
        encoded_filename = quote(filename, safe="/")
        
        return urljoin(base_url, encoded_filename)

    def _relative_path(self, path: str) -> str:
        """Convert a returned WebDAV URL back to the backend-relative path."""
        if not path.startswith(("http://", "https://")):
            return path

        base_path = urlparse(self.config["url"]).path.rstrip("/")
        file_path = urlparse(path).path
        if base_path and file_path.startswith(base_path):
            file_path = file_path[len(base_path):]
        return file_path.lstrip("/")
    
    async def _create_directory(self, dir_path: str) -> None:
        """
        Create directory on WebDAV server.
        
        Args:
            dir_path: Directory path
        """
        try:
            await asyncio.to_thread(self._backend.create_dir, dir_path, parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create directory {dir_path}: {e}")
            # Don't fail - directory might already exist
    
    async def store_file(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredFile:
        """Store file to WebDAV server"""
        
        # Create parent directory if needed
        if "/" in filename:
            dir_path = "/".join(filename.split("/")[:-1])
            await self._create_directory(dir_path)
        
        file_url = self._get_full_url(filename)
        
        try:
            await asyncio.to_thread(self._backend.write_bytes, filename, content, overwrite=True)
            
            logger.info(f"Stored file to WebDAV: {file_url} ({len(content)} bytes)")
            
            # Extract format from filename
            file_format = filename.rsplit('.', 1)[-1] if '.' in filename else 'unknown'
            
            return StoredFile(
                path=file_url,
                format=file_format,
                size_bytes=len(content),
                storage_type="webdav",
                metadata=metadata or {}
            )
            
        except Exception as e:
            raise StorageError(f"Failed to store file to WebDAV: {e}")
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from WebDAV server"""
        
        # Path might be full URL or relative path
        file_url = path if path.startswith(("http://", "https://")) else self._get_full_url(path)
        backend_path = self._relative_path(path)
        
        try:
            await asyncio.to_thread(self._backend.delete_path, backend_path, missing_ok=True)
            logger.info(f"Deleted file from WebDAV: {file_url}")
            return True
        except Exception as e:
            raise StorageError(f"Failed to delete file from WebDAV: {e}")
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists on WebDAV server"""
        
        try:
            return await asyncio.to_thread(self._backend.stat, self._relative_path(path)) is not None
        except Exception:
            return False
    
    async def exists(self, path: str) -> bool:
        """Alias for file_exists() for compatibility"""
        return await self.file_exists(path)
    
    async def get_file_url(self, path: str) -> str:
        """Get WebDAV URL for file"""
        
        if path.startswith(("http://", "https://")):
            return path
        else:
            return self._backend.get_url(path)
    
    async def get_file_content(self, path: str) -> bytes:
        """Retrieve file content from WebDAV server"""
        
        try:
            return await asyncio.to_thread(self._backend.read_bytes, self._relative_path(path))
            
        except StorageFileNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve file from WebDAV: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client"""
        return None
