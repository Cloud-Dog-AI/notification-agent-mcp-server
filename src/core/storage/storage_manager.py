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
Description: Storage Manager - Abstract storage interface for notification files (PDFs, images, media)

Related Requirements: FR1.18, FR1.19, FR1.20
Related Tasks: T29, T30, T31
Related Architecture: CC6.1.3
Related Tests: UT1.13, ST1.4, IT1.16, AT1.22

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

from src.utils.logger import get_logger
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, BinaryIO
from pathlib import Path
from datetime import datetime

logger = get_logger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends"""
    
    @abstractmethod
    def store_file(
        self,
        file_content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a file in the storage backend
        
        Args:
            file_content: File content as bytes
            file_path: Path where file should be stored (relative to storage root)
            metadata: Optional metadata (file_type, mime_type, etc.)
            
        Returns:
            Dict with storage_path, storage_uri, file_size, etc.
        """
        pass
    
    @abstractmethod
    def retrieve_file(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve a file from storage
        
        Args:
            file_path: Path to file (relative to storage root)
            
        Returns:
            File content as bytes, or None if not found
        """
        pass
    
    @abstractmethod
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from storage
        
        Args:
            file_path: Path to file (relative to storage root)
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in storage
        
        Args:
            file_path: Path to file (relative to storage root)
            
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get file size in bytes
        
        Args:
            file_path: Path to file (relative to storage root)
            
        Returns:
            File size in bytes, or None if not found
        """
        pass


class StorageManager:
    """Manages storage for notification files (PDFs, images, media)"""
    
    def __init__(self, backend: StorageBackend, base_url: Optional[str] = None):
        """
        Initialize storage manager
        
        Args:
            backend: Storage backend implementation
            base_url: Base URL for generating access links (e.g., "https://example.com/storage")
        """
        self.backend = backend
        self.base_url = base_url or ""
        logger.info(f"StorageManager initialized with backend: {type(backend).__name__}")
    
    def store_file(
        self,
        file_content: bytes,
        file_type: str,
        message_id: Optional[int] = None,
        delivery_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a file with organized path structure
        
        Args:
            file_content: File content as bytes
            file_type: Type of file ('pdf', 'image', etc.)
            message_id: Optional message ID for organization
            delivery_id: Optional delivery ID for organization
            metadata: Optional additional metadata
            
        Returns:
            Dict with:
                - storage_path: Relative path in storage
                - storage_uri: Full URI (file:// or http://)
                - access_url: Public access URL (if base_url configured)
                - file_size: Size in bytes
                - mime_type: MIME type
        """
        # Generate organized path: {file_type}/{year}/{month}/{day}/{message_id}_{delivery_id}_{timestamp}_{filename}
        now = datetime.now()
        date_path = f"{file_type}/{now.year:04d}/{now.month:02d}/{now.day:02d}"
        
        # Generate filename
        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
        if message_id and delivery_id:
            filename = f"{message_id}_{delivery_id}_{timestamp}"
        elif message_id:
            filename = f"{message_id}_{timestamp}"
        else:
            filename = timestamp
        
        # Add extension based on file_type or metadata
        extension = self._get_extension(file_type, metadata)
        if extension:
            filename = f"{filename}.{extension}"
        
        file_path = f"{date_path}/{filename}"
        
        # Prepare metadata
        storage_metadata = {
            "file_type": file_type,
            "message_id": message_id,
            "delivery_id": delivery_id,
            **(metadata or {})
        }
        
        # Store file
        result = self.backend.store_file(file_content, file_path, storage_metadata)
        
        # Generate access URL if base_url is configured
        access_url = None
        if self.base_url:
            access_url = f"{self.base_url.rstrip('/')}/{file_path}"
        
        # Get MIME type (prefer from result, then metadata, then default)
        mime_type = result.get("mime_type")
        if not mime_type:
            mime_type = self._get_mime_type(file_type, storage_metadata)
        
        return {
            "storage_path": file_path,
            "storage_uri": result.get("storage_uri", file_path),
            "access_url": access_url,
            "file_size": result.get("file_size", len(file_content)),
            "mime_type": mime_type,
            **{k: v for k, v in result.items() if k not in ["storage_path", "storage_uri", "file_size", "mime_type"]}
        }
    
    def retrieve_file(self, storage_path: str) -> Optional[bytes]:
        """
        Retrieve a file from storage
        
        Args:
            storage_path: Path to file (relative to storage root)
            
        Returns:
            File content as bytes, or None if not found
        """
        return self.backend.retrieve_file(storage_path)
    
    def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage
        
        Args:
            storage_path: Path to file (relative to storage root)
            
        Returns:
            True if deleted, False otherwise
        """
        return self.backend.delete_file(storage_path)
    
    def file_exists(self, storage_path: str) -> bool:
        """
        Check if a file exists in storage
        
        Args:
            storage_path: Path to file (relative to storage root)
            
        Returns:
            True if file exists, False otherwise
        """
        return self.backend.file_exists(storage_path)
    
    def get_file_info(self, storage_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file information
        
        Args:
            storage_path: Path to file (relative to storage root)
            
        Returns:
            Dict with file info (size, exists, etc.) or None if not found
        """
        if not self.backend.file_exists(storage_path):
            return None
        
        file_size = self.backend.get_file_size(storage_path)
        access_url = None
        if self.base_url:
            access_url = f"{self.base_url.rstrip('/')}/{storage_path}"
        
        return {
            "storage_path": storage_path,
            "file_size": file_size,
            "exists": True,
            "access_url": access_url
        }
    
    def _get_extension(self, file_type: str, metadata: Optional[Dict[str, Any]]) -> Optional[str]:
        """Get file extension based on file_type and metadata"""
        if metadata and "extension" in metadata:
            return metadata["extension"]
        
        extension_map = {
            "pdf": "pdf",
            "image": metadata.get("format", "png") if metadata else "png",
            "audio": metadata.get("format", "mp3") if metadata else "mp3",
            "video": metadata.get("format", "mp4") if metadata else "mp4",
            "text": "txt",
            "markdown": "md",
            "html": "html"
        }
        return extension_map.get(file_type)
    
    def _get_mime_type(self, file_type: str, metadata: Optional[Dict[str, Any]]) -> str:
        """Get MIME type based on file_type and metadata"""
        if metadata and "mime_type" in metadata:
            return metadata["mime_type"]
        
        mime_type_map = {
            "pdf": "application/pdf",
            "image": f"image/{metadata.get('format', 'png')}" if metadata else "image/png",
            "audio": f"audio/{metadata.get('format', 'mp3')}" if metadata else "audio/mpeg",
            "video": f"video/{metadata.get('format', 'mp4')}" if metadata else "video/mp4",
            "text": "text/plain",
            "markdown": "text/markdown",
            "html": "text/html"
        }
        return mime_type_map.get(file_type, "application/octet-stream")


# Global storage manager instance
_storage_manager_instance: Optional['StorageManager'] = None


def get_storage_manager(backend_type: Optional[str] = None, backend_config: Optional[Dict[str, Any]] = None) -> 'StorageManager':
    """
    Get or create the global storage manager instance.
    Uses configured backend (local, webdav, ftp, s3) from config.

    Args:
        backend_type: Override backend type (optional)
        backend_config: Override backend configuration (optional)

    Returns:
        StorageManager instance
    """
    global _storage_manager_instance

    if _storage_manager_instance is None or backend_type or backend_config:
        from .local_storage import LocalStorage
        from ...config import get_config

        config = get_config()

        storage_backend_type = backend_type or config.get("storage.backend", "local")
        if not storage_backend_type:
            storage_backend_type = "local"

        backend_cfg = backend_config or config.get(f"storage.{storage_backend_type}", {}) or {}
        if not isinstance(backend_cfg, dict):
            backend_cfg = {}

        local_base_path = (
            backend_cfg.get("base_path")
            or config.get("storage.local.base_path")
            or config.get("storage.path")
            or "storage/"
        )

        if storage_backend_type in ("local", "filesystem"):
            backend = LocalStorage(base_path=local_base_path)

        elif storage_backend_type == "webdav":
            try:
                from .webdav_storage import WebDAVStorage

                url = backend_cfg.get("url") or config.get("storage.webdav.url", "")
                username = backend_cfg.get("username") or config.get("storage.webdav.username", "")
                password = backend_cfg.get("password") or config.get("storage.webdav.password", "")
                if not url:
                    raise ValueError("WebDAV URL is required")
                backend = WebDAVStorage(url=url, username=username, password=password)
            except ImportError:
                logger.warning("WebDAV storage not available, falling back to local")
                backend = LocalStorage(base_path=local_base_path)

        elif storage_backend_type == "ftp":
            try:
                from .ftp_storage import FTPStorage

                host = backend_cfg.get("host") or config.get("storage.ftp.host", "")
                port = backend_cfg.get("port") or config.get("storage.ftp.port", 21)
                username = backend_cfg.get("username") or config.get("storage.ftp.username", "")
                password = backend_cfg.get("password") or config.get("storage.ftp.password", "")
                passive_mode = backend_cfg.get("passive_mode")
                if passive_mode is None:
                    passive_mode = config.get("storage.ftp.passive_mode", True)
                use_tls = backend_cfg.get("use_tls")
                if use_tls is None:
                    use_tls = config.get("storage.ftp.use_tls", False)
                if not host:
                    raise ValueError("FTP host is required")
                backend = FTPStorage(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    passive_mode=passive_mode,
                    use_tls=use_tls,
                )
            except ImportError:
                logger.warning("FTP storage not available, falling back to local")
                backend = LocalStorage(base_path=local_base_path)

        elif storage_backend_type == "s3":
            try:
                from .s3_storage import S3Storage

                endpoint = backend_cfg.get("endpoint") or config.get("storage.s3.endpoint", "")
                bucket = backend_cfg.get("bucket") or config.get("storage.s3.bucket", "")
                access_key = (
                    backend_cfg.get("access_key")
                    or backend_cfg.get("access_key_id")
                    or config.get("storage.s3.access_key")
                    or config.get("storage.s3.access_key_id", "")
                )
                secret_key = (
                    backend_cfg.get("secret_key")
                    or backend_cfg.get("secret_access_key")
                    or config.get("storage.s3.secret_key")
                    or config.get("storage.s3.secret_access_key", "")
                )
                region = backend_cfg.get("region") or config.get("storage.s3.region", "us-east-1")
                if not endpoint or not bucket:
                    raise ValueError("S3 endpoint and bucket are required")
                backend = S3Storage(
                    endpoint=endpoint,
                    bucket=bucket,
                    access_key=access_key,
                    secret_key=secret_key,
                    region=region,
                )
            except ImportError:
                logger.warning("S3 storage not available, falling back to local")
                backend = LocalStorage(base_path=local_base_path)

        else:
            logger.warning(f"Unknown storage backend type: {storage_backend_type}, using local")
            backend = LocalStorage(base_path=local_base_path)

        base_url = config.get("storage.base_url") or config.get("storage.local.base_url")
        if not base_url:
            api_port = config.get("api_server.port", 8080)
            base_url = f"http://localhost:{api_port}/storage"

        if backend_type or backend_config:
            return StorageManager(backend=backend, base_url=base_url)

        _storage_manager_instance = StorageManager(backend=backend, base_url=base_url)
        logger.info(f"Global StorageManager created: backend={storage_backend_type}, base_url={base_url}")

    return _storage_manager_instance
