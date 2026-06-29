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
Storage backend factory.

Creates appropriate storage backend instances based on configuration.
"""

from typing import Dict, Any, Type
from src.utils.logger import get_logger

from .base import StorageBackend, ConfigurationError
from .filesystem import FilesystemBackend
from .webdav import WebDAVBackend
from .s3 import S3Backend
from .ftp import FTPBackend

logger = get_logger(__name__)


class StorageFactory:
    """
    Factory to create storage backend instances.
    
    Maintains a registry of available storage backends and creates
    instances based on configuration.
    """
    
    # Registry of available backends
    _backends: Dict[str, Type[StorageBackend]] = {
        "filesystem": FilesystemBackend,
        "local": FilesystemBackend,
        "webdav": WebDAVBackend,
        "s3": S3Backend,
        "ftp": FTPBackend
    }
    
    @classmethod
    def create(cls, config: Dict[str, Any]) -> StorageBackend:
        """
        Create storage backend from configuration.
        
        Args:
            config: Storage backend configuration with 'storage_type' field
            
        Returns:
            Configured storage backend instance
            
        Raises:
            ConfigurationError: If storage_type is missing or unknown
        """
        if not config:
            raise ConfigurationError("Storage configuration cannot be empty")
        
        storage_type = config.get("storage_type")
        
        if not storage_type:
            raise ConfigurationError("Missing 'storage_type' in configuration")
        
        if storage_type not in cls._backends:
            available = ", ".join(cls._backends.keys())
            raise ConfigurationError(
                f"Unknown storage type: {storage_type}. Available: {available}"
            )
        
        backend_class = cls._backends[storage_type]
        
        try:
            backend = backend_class(config)
            logger.info(f"Created {storage_type} storage backend")
            return backend
        except Exception as e:
            raise ConfigurationError(f"Failed to create {storage_type} backend: {e}")
    
    @classmethod
    def register_backend(cls, name: str, backend_class: Type[StorageBackend]) -> None:
        """
        Register a custom storage backend.
        
        Args:
            name: Backend name (used in storage_type field)
            backend_class: Backend class (must inherit from StorageBackend)
        """
        if not issubclass(backend_class, StorageBackend):
            raise ValueError(f"{backend_class} must inherit from StorageBackend")
        
        cls._backends[name] = backend_class
        logger.info(f"Registered custom storage backend: {name}")
    
    @classmethod
    def get_available_backends(cls) -> list:
        """
        Get list of available backend types.
        
        Returns:
            List of backend type names
        """
        return list(cls._backends.keys())
    
    @classmethod
    def is_backend_available(cls, storage_type: str) -> bool:
        """
        Check if a backend type is available.
        
        Args:
            storage_type: Backend type name
            
        Returns:
            True if backend is registered, False otherwise
        """
        return storage_type in cls._backends
