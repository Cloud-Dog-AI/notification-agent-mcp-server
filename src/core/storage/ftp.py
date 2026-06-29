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
FTP storage backend for FTP/FTPS servers.

Supports:
- Standard FTP
- FTPS (FTP over TLS)
- Passive mode
- Directory creation

Uses aioftp for async FTP operations.
"""

from pathlib import PurePosixPath
from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

# Lazy import to avoid startup errors if aioftp not installed
try:
    import aioftp
    HAS_AIOFTP = True
except ImportError:
    HAS_AIOFTP = False
    aioftp = None

from .base import StorageBackend, StoredFile, StorageError, ConfigurationError, FileNotFoundError as StorageFileNotFoundError

logger = get_logger(__name__)


class FTPBackend(StorageBackend):
    """
    FTP/FTPS storage backend.
    
    Stores files on FTP servers with support for:
    - FTP and FTPS (TLS)
    - Passive mode
    - Directory creation
    - Custom base paths
    """
    
    def validate_config(self) -> None:
        """Validate FTP configuration"""
        if not HAS_AIOFTP:
            raise ConfigurationError("aioftp library not installed. Install with: pip install aioftp")
        
        required_fields = ["host", "username", "password"]
        
        for field in required_fields:
            if field not in self.config:
                raise ConfigurationError(f"Missing required field: {field}")
        
        host = self.config["host"]
        
        if not host:
            raise ConfigurationError("host cannot be empty")
        
        # Validate port
        port = self.config.get("port", 21)
        try:
            port = int(port)
            if port < 1 or port > 65535:
                raise ValueError()
            self.config["port"] = port
        except (ValueError, TypeError):
            raise ConfigurationError(f"Invalid port: {port}")
        
        # Set defaults
        if "passive_mode" not in self.config:
            self.config["passive_mode"] = True
        
        if "use_tls" not in self.config:
            self.config["use_tls"] = False
    
    def _get_full_path(self, filename: str) -> str:
        """
        Get full FTP path for filename.
        
        Args:
            filename: Filename (may include subdirectory)
            
        Returns:
            Full FTP path
        """
        base_path = self.config.get("base_path", "")
        
        # Combine base path and filename
        if base_path:
            base_path = base_path.strip("/")
            filename = filename.lstrip("/")
            full_path = f"{base_path}/{filename}"
        else:
            full_path = filename.lstrip("/")
        
        return full_path
    
    async def _connect(self):
        """Create and return FTP client connection"""
        host = self.config["host"]
        port = self.config["port"]
        user = self.config["username"]
        password = self.config["password"]
        use_tls = self.config["use_tls"]
        
        try:
            if use_tls:
                client = aioftp.Client.context()
            else:
                client = aioftp.Client()
            
            await client.connect(host, port)
            await client.login(user, password)
            
            return client
            
        except Exception as e:
            raise StorageError(f"FTP connection failed: {e}")
    
    async def _ensure_directory(self, client, dir_path: str) -> None:
        """
        Ensure directory exists, creating if necessary.
        
        Args:
            client: FTP client
            dir_path: Directory path
        """
        if not dir_path or dir_path == "/":
            return
        
        # Split path into parts
        parts = dir_path.strip("/").split("/")
        current_path = ""
        
        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                # Check if directory exists
                await client.stat(current_path)
            except aioftp.StatusCodeError:
                # Directory doesn't exist, create it
                try:
                    await client.make_directory(current_path)
                    logger.debug(f"Created FTP directory: {current_path}")
                except Exception as e:
                    logger.warning(f"Failed to create directory {current_path}: {e}")
    
    async def store_file(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredFile:
        """Store file to FTP server"""
        
        full_path = self._get_full_path(filename)
        
        # Extract directory path
        path_parts = full_path.rsplit("/", 1)
        if len(path_parts) == 2:
            dir_path, file_name = path_parts
        else:
            dir_path = ""
            file_name = path_parts[0]
        
        client = None
        
        try:
            client = await self._connect()
            
            # Ensure directory exists
            if dir_path:
                await self._ensure_directory(client, dir_path)
            
            # Upload file using STOR command
            async with client.upload_stream(full_path) as stream:
                await stream.write(content)
            
            logger.info(f"Stored file to FTP: {full_path} ({len(content)} bytes)")
            
            # Extract format from filename
            file_format = filename.rsplit('.', 1)[-1] if '.' in filename else 'unknown'
            
            # Construct FTP URL
            host = self.config["host"]
            port = self.config["port"]
            ftp_url = f"ftp://{host}:{port}/{full_path}"
            
            return StoredFile(
                path=ftp_url,
                format=file_format,
                size_bytes=len(content),
                storage_type="ftp",
                metadata=metadata or {}
            )
            
        except Exception as e:
            raise StorageError(f"FTP upload failed: {e}")
        finally:
            if client:
                await client.quit()
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from FTP server"""
        
        # Extract path from FTP URL if necessary
        if path.startswith("ftp://"):
            # ftp://host:port/path format
            path = path.split("/", 3)[3] if "/" in path.split("//")[1] else ""
        
        full_path = self._get_full_path(path) if not path.startswith("/") else path.lstrip("/")
        
        client = None
        
        try:
            client = await self._connect()
            
            # Check if file exists
            try:
                await client.stat(full_path)
            except aioftp.StatusCodeError:
                return False
            
            # Delete file
            await client.remove(full_path)
            
            logger.info(f"Deleted file from FTP: {full_path}")
            return True
            
        except Exception as e:
            raise StorageError(f"FTP delete failed: {e}")
        finally:
            if client:
                await client.quit()
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists on FTP server"""
        
        if path.startswith("ftp://"):
            path = path.split("/", 3)[3] if "/" in path.split("//")[1] else ""
        
        full_path = self._get_full_path(path) if not path.startswith("/") else path.lstrip("/")
        
        client = None
        
        try:
            client = await self._connect()
            await client.stat(full_path)
            return True
            
        except aioftp.StatusCodeError:
            return False
        except Exception:
            return False
        finally:
            if client:
                try:
                    await client.quit()
                except Exception:
                    pass

    async def exists(self, path: str) -> bool:
        """Compatibility alias used by storage API routes."""
        return await self.file_exists(path)
    
    async def get_file_url(self, path: str) -> str:
        """Get FTP URL for file"""
        
        if path.startswith("ftp://"):
            return path
        
        full_path = self._get_full_path(path)
        host = self.config["host"]
        port = self.config["port"]
        
        return f"ftp://{host}:{port}/{full_path}"
    
    async def get_file_content(self, path: str) -> bytes:
        """Retrieve file content from FTP server"""
        
        if path.startswith("ftp://"):
            path = path.split("/", 3)[3] if "/" in path.split("//")[1] else ""
        
        full_path = self._get_full_path(path) if not path.startswith("/") else path.lstrip("/")
        
        client = None
        
        try:
            client = await self._connect()
            
            # Check if file exists
            try:
                await client.stat(full_path)
            except aioftp.StatusCodeError:
                raise StorageFileNotFoundError(f"File not found: {path}")
            
            # Download file
            content = bytearray()
            async with client.download_stream(full_path) as stream:
                async for chunk in stream.iter_by_block():
                    content.extend(chunk)
            
            return bytes(content)
            
        except StorageFileNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"FTP download failed: {e}")
        finally:
            if client:
                await client.quit()
