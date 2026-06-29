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
Description: WebDAV storage backend for notification files

Related Requirements: FR1.20
Related Tasks: T31.3
Related Architecture: CC6.1.2, CC6.1.3
Related Tests: AT1.21

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
from typing import Optional, Dict, Any
from urllib.parse import urljoin, urlparse
import requests
from requests.auth import HTTPBasicAuth

from .storage_manager import StorageBackend

logger = get_logger(__name__)


class WebDAVStorage(StorageBackend):
    """WebDAV storage backend"""
    
    def __init__(self, url: str, username: str = "", password: str = ""):
        """
        Initialize WebDAV storage backend
        
        Args:
            url: WebDAV server URL (e.g., "https://example.com/webdav/")
            username: WebDAV username
            password: WebDAV password
        """
        self.base_url = url.rstrip('/') + '/'
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password) if username else None
        logger.info(f"WebDAVStorage initialized with URL: {self.base_url}")
    
    def store_file(
        self,
        file_content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a file via WebDAV
        
        Args:
            file_content: File content as bytes
            file_path: Path where file should be stored (relative to WebDAV root)
            metadata: Optional metadata
            
        Returns:
            Dict with storage_path, storage_uri, file_size, mime_type
        """
        full_url = urljoin(self.base_url, file_path)
        
        # Ensure parent directory exists
        parent_path = '/'.join(file_path.split('/')[:-1])
        if parent_path:
            self._ensure_directory(parent_path)
        
        try:
            response = requests.put(
                full_url,
                data=file_content,
                auth=self.auth,
                timeout=30
            )
            response.raise_for_status()
            
            file_size = len(file_content)
            storage_uri = full_url
            
            result = {
                "storage_path": file_path,
                "storage_uri": storage_uri,
                "file_size": file_size,
                "mime_type": metadata.get("mime_type") if metadata else None
            }
            
            logger.info(f"Stored file via WebDAV: {file_path} ({file_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to store file via WebDAV {file_path}: {e}")
            raise
    
    def retrieve_file(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve a file from WebDAV
        
        Args:
            file_path: Path to file (relative to WebDAV root)
            
        Returns:
            File content as bytes, or None if not found
        """
        full_url = urljoin(self.base_url, file_path)
        
        try:
            response = requests.get(
                full_url,
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 404:
                logger.warning(f"File not found via WebDAV: {file_path}")
                return None
            
            response.raise_for_status()
            content = response.content
            logger.debug(f"Retrieved file via WebDAV: {file_path} ({len(content)} bytes)")
            return content
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to retrieve file via WebDAV {file_path}: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from WebDAV
        
        Args:
            file_path: Path to file (relative to WebDAV root)
            
        Returns:
            True if deleted, False otherwise
        """
        full_url = urljoin(self.base_url, file_path)
        
        try:
            response = requests.delete(
                full_url,
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 404:
                logger.warning(f"File not found for deletion via WebDAV: {file_path}")
                return False
            
            response.raise_for_status()
            logger.info(f"Deleted file via WebDAV: {file_path}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete file via WebDAV {file_path}: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in WebDAV
        
        Args:
            file_path: Path to file (relative to WebDAV root)
            
        Returns:
            True if file exists, False otherwise
        """
        full_url = urljoin(self.base_url, file_path)
        
        try:
            response = requests.head(
                full_url,
                auth=self.auth,
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get file size in bytes from WebDAV
        
        Args:
            file_path: Path to file (relative to WebDAV root)
            
        Returns:
            File size in bytes, or None if not found
        """
        full_url = urljoin(self.base_url, file_path)
        
        try:
            response = requests.head(
                full_url,
                auth=self.auth,
                timeout=10
            )
            
            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    return int(content_length)
            return None
        except Exception as e:
            logger.error(f"Failed to get file size via WebDAV for {file_path}: {e}")
            return None
    
    def _ensure_directory(self, directory_path: str):
        """Ensure directory exists in WebDAV (create if needed)"""
        if not directory_path:
            return
        
        # Create directory path recursively
        parts = directory_path.strip('/').split('/')
        current_path = ''
        
        for part in parts:
            if part:
                current_path = f"{current_path}/{part}" if current_path else part
                dir_url = urljoin(self.base_url, current_path + '/')
                
                try:
                    # Try to create directory (MKCOL)
                    response = requests.request(
                        'MKCOL',
                        dir_url,
                        auth=self.auth,
                        timeout=10
                    )
                    # 201 = created, 405 = already exists (method not allowed)
                    if response.status_code not in [201, 405]:
                        response.raise_for_status()
                except requests.exceptions.RequestException:
                    # Directory might already exist, continue
                    pass
