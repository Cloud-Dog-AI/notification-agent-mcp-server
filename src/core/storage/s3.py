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
S3 storage backend for object storage.

Supports S3-compatible storage services:
- Amazon S3
- MinIO
- DigitalOcean Spaces
- Wasabi
- Backblaze B2

Uses aioboto3 for async S3 operations.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

# Lazy import to avoid startup errors if aioboto3 not installed
try:
    import aioboto3
    from botocore.exceptions import ClientError
    HAS_AIOBOTO3 = True
except ImportError:
    HAS_AIOBOTO3 = False
    aioboto3 = None
    ClientError = Exception

from .base import StorageBackend, StoredFile, StorageError, ConfigurationError, FileNotFoundError as StorageFileNotFoundError

logger = get_logger(__name__)


class S3Backend(StorageBackend):
    """
    S3-compatible object storage backend.
    
    Stores files in S3 buckets with support for:
    - Custom endpoints (non-AWS S3)
    - Access key authentication
    - Public/private ACLs
    - Pre-signed URLs
    """
    
    def validate_config(self) -> None:
        """Validate S3 configuration"""
        if not HAS_AIOBOTO3:
            raise ConfigurationError("aioboto3 library not installed. Install with: pip install aioboto3")

        def _is_missing(value: Any) -> bool:
            return value is None or str(value).strip() == ""

        alias_map = {
            "endpoint": ("url", "base_url"),
            "bucket": ("bucket_name",),
            "access_key": ("access_key_id", "aws_access_key_id"),
            "secret_key": ("secret_access_key", "aws_secret_access_key"),
        }

        for canonical_key, aliases in alias_map.items():
            canonical_value = self.config.get(canonical_key)
            if _is_missing(canonical_value):
                for alias_key in aliases:
                    alias_value = self.config.get(alias_key)
                    if not _is_missing(alias_value):
                        self.config[canonical_key] = alias_value
                        canonical_value = alias_value
                        break
            if not _is_missing(canonical_value):
                for alias_key in aliases:
                    if _is_missing(self.config.get(alias_key)):
                        self.config[alias_key] = canonical_value
        
        required_fields = ["endpoint", "bucket", "access_key", "secret_key"]
        
        for field in required_fields:
            if field not in self.config:
                raise ConfigurationError(f"Missing required field: {field}")
        
        endpoint = self.config["endpoint"]
        bucket = self.config["bucket"]
        
        if not endpoint:
            raise ConfigurationError("endpoint cannot be empty")
        
        if not bucket:
            raise ConfigurationError("bucket cannot be empty")
        
        if not endpoint.startswith(("http://", "https://")):
            raise ConfigurationError("endpoint must start with http:// or https://")
        
        # Initialize session
        self._session = None
    
    def _get_session(self):
        """Get or create aioboto3 session"""
        if self._session is None:
            self._session = aioboto3.Session(
                aws_access_key_id=self.config["access_key"],
                aws_secret_access_key=self.config["secret_key"],
                region_name=self.config.get("region", "us-east-1")
            )
        
        return self._session
    
    def _get_s3_key(self, filename: str) -> str:
        """
        Get S3 object key from filename.
        
        Args:
            filename: Filename (may include path)
            
        Returns:
            S3 object key
        """
        # Remove leading slashes
        return filename.lstrip("/")
    
    async def store_file(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StoredFile:
        """Store file to S3 bucket"""
        
        session = self._get_session()
        bucket = self.config["bucket"]
        key = self._get_s3_key(filename)
        acl = self.config.get("acl", "private")
        
        try:
            async with session.client(
                's3',
                endpoint_url=self.config["endpoint"]
            ) as s3:
                # Upload file
                await s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=content,
                    ContentType=content_type,
                    ACL=acl,
                    Metadata=metadata or {}
                )
                
                logger.info(f"Stored file to S3: s3://{bucket}/{key} ({len(content)} bytes)")
                
                # Get object URL
                if acl == "public-read":
                    # Public URL
                    endpoint = self.config["endpoint"].rstrip("/")
                    file_url = f"{endpoint}/{bucket}/{key}"
                else:
                    # Private - use s3:// scheme
                    file_url = f"s3://{bucket}/{key}"
                
                # Extract format from filename
                file_format = filename.rsplit('.', 1)[-1] if '.' in filename else 'unknown'
                
                return StoredFile(
                    path=file_url,
                    format=file_format,
                    size_bytes=len(content),
                    storage_type="s3",
                    metadata=metadata or {}
                )
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise StorageError(f"S3 upload failed ({error_code}): {e}")
        except Exception as e:
            raise StorageError(f"Failed to store file to S3: {e}")
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from S3 bucket"""
        
        session = self._get_session()
        bucket = self.config["bucket"]
        
        # Extract key from path
        if path.startswith("s3://"):
            # s3://bucket/key format
            path_parts = path.replace("s3://", "").split("/", 1)
            if len(path_parts) == 2:
                key = path_parts[1]
            else:
                key = path_parts[0]
        elif path.startswith(("http://", "https://")):
            # HTTP URL format
            key = path.split(f"/{bucket}/", 1)[1] if f"/{bucket}/" in path else path.split("/")[-1]
        else:
            # Direct key
            key = self._get_s3_key(path)
        
        try:
            async with session.client(
                's3',
                endpoint_url=self.config["endpoint"]
            ) as s3:
                # Check if file exists first
                try:
                    await s3.head_object(Bucket=bucket, Key=key)
                except ClientError as e:
                    if e.response['Error']['Code'] == '404':
                        return False
                    raise
                
                # Delete file
                await s3.delete_object(Bucket=bucket, Key=key)
                
                logger.info(f"Deleted file from S3: s3://{bucket}/{key}")
                return True
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise StorageError(f"S3 delete failed ({error_code}): {e}")
        except Exception as e:
            raise StorageError(f"Failed to delete file from S3: {e}")
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists in S3 bucket"""
        
        session = self._get_session()
        bucket = self.config["bucket"]
        
        # Extract key from path
        if path.startswith("s3://"):
            path_parts = path.replace("s3://", "").split("/", 1)
            key = path_parts[1] if len(path_parts) == 2 else path_parts[0]
        elif path.startswith(("http://", "https://")):
            key = path.split(f"/{bucket}/", 1)[1] if f"/{bucket}/" in path else path.split("/")[-1]
        else:
            key = self._get_s3_key(path)
        
        try:
            async with session.client(
                's3',
                endpoint_url=self.config["endpoint"]
            ) as s3:
                await s3.head_object(Bucket=bucket, Key=key)
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
        except Exception:
            return False
    
    async def exists(self, path: str) -> bool:
        """Alias for file_exists() for compatibility"""
        return await self.file_exists(path)
    
    async def get_file_url(self, path: str) -> str:
        """Get URL for S3 object"""
        
        # If already a URL, return it
        if path.startswith(("http://", "https://", "s3://")):
            return path
        
        bucket = self.config["bucket"]
        key = self._get_s3_key(path)
        acl = self.config.get("acl", "private")
        
        if acl == "public-read":
            # Public URL
            endpoint = self.config["endpoint"].rstrip("/")
            return f"{endpoint}/{bucket}/{key}"
        else:
            # Private - return s3:// scheme (or generate pre-signed URL)
            return f"s3://{bucket}/{key}"
    
    async def get_file_content(self, path: str) -> bytes:
        """Retrieve file content from S3 bucket"""
        
        session = self._get_session()
        bucket = self.config["bucket"]
        
        # Extract key from path
        if path.startswith("s3://"):
            path_parts = path.replace("s3://", "").split("/", 1)
            key = path_parts[1] if len(path_parts) == 2 else path_parts[0]
        elif path.startswith(("http://", "https://")):
            key = path.split(f"/{bucket}/", 1)[1] if f"/{bucket}/" in path else path.split("/")[-1]
        else:
            key = self._get_s3_key(path)
        
        try:
            async with session.client(
                's3',
                endpoint_url=self.config["endpoint"]
            ) as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)
                
                # Read content
                async with response['Body'] as stream:
                    return await stream.read()
                    
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchKey' or error_code == '404':
                raise StorageFileNotFoundError(f"File not found: {path}")
            raise StorageError(f"S3 download failed ({error_code}): {e}")
        except Exception as e:
            raise StorageError(f"Failed to retrieve file from S3: {e}")
