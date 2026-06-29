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
Description: FTP storage backend for notification files

Related Requirements: FR1.20
Related Tasks: T31.4
Related Architecture: CC6.1.2, CC6.1.3
Related Tests: AT1.21

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
from typing import Optional, Dict, Any
from ftplib import FTP, FTP_TLS
from io import BytesIO

from .storage_manager import StorageBackend

logger = get_logger(__name__)


class FTPStorage(StorageBackend):
    """FTP storage backend"""
    
    def __init__(self, host: str, port: int = 21, username: str = "", password: str = "", passive_mode: bool = True, use_tls: bool = False):
        """
        Initialize FTP storage backend
        
        Args:
            host: FTP server hostname
            port: FTP server port (default 21)
            username: FTP username
            password: FTP password
            passive_mode: Use passive mode (default True)
            use_tls: Use FTPS (FTP over TLS) (default False)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.passive_mode = passive_mode
        self.use_tls = use_tls
        logger.info(f"FTPStorage initialized: {host}:{port}")
    
    def _get_connection(self):
        """Get FTP connection"""
        if self.use_tls:
            ftp = FTP_TLS()
            ftp.connect(self.host, self.port)
            if self.username:
                ftp.login(self.username, self.password)
            ftp.prot_p()  # Switch to secure data connection
        else:
            ftp = FTP()
            ftp.connect(self.host, self.port)
            if self.username:
                ftp.login(self.username, self.password)
        
        if self.passive_mode:
            ftp.set_pasv(True)
        
        return ftp
    
    def store_file(
        self,
        file_content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a file via FTP
        
        Args:
            file_content: File content as bytes
            file_path: Path where file should be stored (relative to FTP root)
            metadata: Optional metadata
            
        Returns:
            Dict with storage_path, storage_uri, file_size, mime_type
        """
        # Ensure parent directory exists
        parent_path = '/'.join(file_path.split('/')[:-1])
        if parent_path:
            self._ensure_directory(parent_path)
        
        ftp = None
        try:
            ftp = self._get_connection()
            
            # Change to directory if needed
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                filename = file_path.split('/')[-1]
                if dir_path:
                    self._ensure_directory_on_ftp(ftp, dir_path)
                    ftp.cwd(dir_path)
                    file_path = filename
            else:
                filename = file_path
            
            # Store file
            file_obj = BytesIO(file_content)
            ftp.storbinary(f'STOR {filename}', file_obj)
            
            file_size = len(file_content)
            storage_uri = f"ftp://{self.host}:{self.port}/{file_path}"
            
            result = {
                "storage_path": file_path,
                "storage_uri": storage_uri,
                "file_size": file_size,
                "mime_type": metadata.get("mime_type") if metadata else None
            }
            
            logger.info(f"Stored file via FTP: {file_path} ({file_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to store file via FTP {file_path}: {e}")
            raise
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
    
    def retrieve_file(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve a file from FTP
        
        Args:
            file_path: Path to file (relative to FTP root)
            
        Returns:
            File content as bytes, or None if not found
        """
        ftp = None
        try:
            ftp = self._get_connection()
            
            # Change to directory if needed
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                filename = file_path.split('/')[-1]
                if dir_path:
                    try:
                        ftp.cwd(dir_path)
                    except Exception:
                        logger.warning(f"Directory not found via FTP: {dir_path}")
                        return None
                file_path = filename
            
            # Retrieve file
            file_obj = BytesIO()
            try:
                ftp.retrbinary(f'RETR {file_path}', file_obj.write)
                content = file_obj.getvalue()
                logger.debug(f"Retrieved file via FTP: {file_path} ({len(content)} bytes)")
                return content
            except Exception as e:
                logger.warning(f"File not found via FTP: {file_path} - {e}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve file via FTP {file_path}: {e}")
            return None
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from FTP
        
        Args:
            file_path: Path to file (relative to FTP root)
            
        Returns:
            True if deleted, False otherwise
        """
        ftp = None
        try:
            ftp = self._get_connection()
            
            # Change to directory if needed
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                filename = file_path.split('/')[-1]
                if dir_path:
                    try:
                        ftp.cwd(dir_path)
                    except Exception:
                        logger.warning(f"Directory not found via FTP: {dir_path}")
                        return False
                file_path = filename
            
            # Delete file
            ftp.delete(file_path)
            logger.info(f"Deleted file via FTP: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file via FTP {file_path}: {e}")
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in FTP
        
        Args:
            file_path: Path to file (relative to FTP root)
            
        Returns:
            True if file exists, False otherwise
        """
        ftp = None
        try:
            ftp = self._get_connection()
            
            # Change to directory if needed
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                filename = file_path.split('/')[-1]
                if dir_path:
                    try:
                        ftp.cwd(dir_path)
                    except Exception:
                        return False
                file_path = filename
            
            # List files and check if our file exists
            files = ftp.nlst()
            return file_path in files
            
        except Exception:
            return False
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get file size in bytes from FTP
        
        Args:
            file_path: Path to file (relative to FTP root)
            
        Returns:
            File size in bytes, or None if not found
        """
        ftp = None
        try:
            ftp = self._get_connection()
            
            # Change to directory if needed
            if '/' in file_path:
                dir_path = '/'.join(file_path.split('/')[:-1])
                filename = file_path.split('/')[-1]
                if dir_path:
                    try:
                        ftp.cwd(dir_path)
                    except Exception:
                        return None
                file_path = filename
            
            # Get file size
            size = ftp.size(file_path)
            return size if size else None
            
        except Exception as e:
            logger.error(f"Failed to get file size via FTP for {file_path}: {e}")
            return None
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    ftp.close()
    
    def _ensure_directory(self, directory_path: str):
        """Ensure directory exists (wrapper for backward compatibility)"""
        # This is called before connection, so we'll create it during store_file
        pass
    
    def _ensure_directory_on_ftp(self, ftp: FTP, directory_path: str):
        """Ensure directory exists on FTP server"""
        if not directory_path:
            return
        
        parts = directory_path.strip('/').split('/')
        for part in parts:
            if part:
                try:
                    ftp.cwd(part)
                except Exception:
                    # Directory doesn't exist, create it
                    ftp.mkd(part)
                    ftp.cwd(part)
