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
Base storage backend interface for file channel delivery.

Defines the abstract interface that all storage backends must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class StoredFile:
    """Represents a successfully stored file"""
    path: str                           # Full path/URL to file
    format: str                         # File format (md, txt, pdf)
    size_bytes: int                     # File size
    storage_type: str                   # Backend type (filesystem, webdav, s3, ftp)
    stored_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "path": self.path,
            "format": self.format,
            "size_bytes": self.size_bytes,
            "storage_type": self.storage_type,
            "stored_at": self.stored_at.isoformat(),
            "metadata": self.metadata
        }


class StorageBackend(ABC):
    """
    Base interface for all storage backends.
    
    Each backend must implement methods to:
    - Store files
    - Delete files
    - Check file existence
    - Get file URLs/paths
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage backend with configuration.
        
        Args:
            config: Backend-specific configuration dictionary
        """
        self.config = config
        self.validate_config()
    
    @abstractmethod
    def validate_config(self) -> None:
        """
        Validate backend configuration.
        
        Raises:
            ValueError: If configuration is invalid or missing required fields
        """
        pass
    
    @abstractmethod
    async def store_file(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredFile:
        """
        Store a file and return metadata.
        
        Args:
            content: File content as bytes
            filename: Desired filename (may include subdirectory path)
            content_type: MIME type (e.g., 'text/markdown', 'application/pdf')
            metadata: Optional additional metadata
        
        Returns:
            StoredFile object with path, size, and metadata
        
        Raises:
            StorageError: If file cannot be stored
        """
        pass
    
    @abstractmethod
    async def delete_file(self, path: str) -> bool:
        """
        Delete a file.
        
        Args:
            path: Path to file (as returned by store_file)
        
        Returns:
            True if file was deleted, False if file didn't exist
        
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            path: Path to file
        
        Returns:
            True if file exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_file_url(self, path: str) -> str:
        """
        Get URL/path to access file.
        
        Args:
            path: Path to file
        
        Returns:
            URL or file:// path that can be used to access the file
        """
        pass
    
    @abstractmethod
    async def get_file_content(self, path: str) -> bytes:
        """
        Retrieve file content.
        
        Args:
            path: Path to file
        
        Returns:
            File content as bytes
        
        Raises:
            StorageError: If file cannot be retrieved
        """
        pass


class StorageError(Exception):
    """Base exception for storage backend errors"""
    pass


class ConfigurationError(StorageError):
    """Configuration validation error"""
    pass


class FileNotFoundError(StorageError):
    """File not found in storage"""
    pass


class PermissionError(StorageError):
    """Insufficient permissions for storage operation"""
    pass


class QuotaExceededError(StorageError):
    """Storage quota exceeded"""
    pass
