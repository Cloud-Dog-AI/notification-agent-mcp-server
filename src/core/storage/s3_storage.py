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
Description: S3-compatible storage backend for notification files

Related Requirements: FR1.20
Related Tasks: T31.5
Related Architecture: CC6.1.2, CC6.1.3
Related Tests: AT1.21

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
from typing import Optional, Dict, Any
from io import BytesIO

from .storage_manager import StorageBackend

logger = get_logger(__name__)

# Try to import boto3, but make it optional
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not available. S3 storage will not work. Install with: pip install boto3")


class S3Storage(StorageBackend):
    """S3-compatible storage backend"""
    
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "us-east-1"
    ):
        """
        Initialize S3 storage backend
        
        Args:
            endpoint: S3 endpoint URL (e.g., "https://s3.amazonaws.com" or "https://s3.wasabisys.com")
            bucket: S3 bucket name
            access_key: S3 access key
            secret_key: S3 secret key
            region: AWS region (default "us-east-1")
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
        
        self.endpoint = endpoint
        self.bucket = bucket
        self.region = region
        
        # Create S3 client
        s3_config = {
            'region_name': region
        }
        
        # If endpoint is provided and not AWS standard, use it
        if endpoint and 'amazonaws.com' not in endpoint:
            s3_config['endpoint_url'] = endpoint
        
        if access_key and secret_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                **s3_config
            )
        else:
            # Use default credentials (environment variables, IAM role, etc.)
            self.s3_client = boto3.client('s3', **s3_config)
        
        logger.info(f"S3Storage initialized: bucket={bucket}, endpoint={endpoint}")
    
    def store_file(
        self,
        file_content: bytes,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a file in S3
        
        Args:
            file_content: File content as bytes
            file_path: Path where file should be stored (S3 key)
            metadata: Optional metadata
            
        Returns:
            Dict with storage_path, storage_uri, file_size, mime_type
        """
        try:
            # Prepare metadata for S3
            s3_metadata = {}
            if metadata:
                # Convert metadata to S3 metadata format
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float)):
                        s3_metadata[f"x-amz-meta-{key}"] = str(value)
            
            # Determine content type
            content_type = metadata.get("mime_type") if metadata else "application/octet-stream"
            
            # Upload file
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=file_path,
                Body=file_content,
                ContentType=content_type,
                Metadata=s3_metadata
            )
            
            file_size = len(file_content)
            storage_uri = f"s3://{self.bucket}/{file_path}"
            
            result = {
                "storage_path": file_path,
                "storage_uri": storage_uri,
                "file_size": file_size,
                "mime_type": content_type
            }
            
            logger.info(f"Stored file in S3: {file_path} ({file_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to store file in S3 {file_path}: {e}")
            raise
    
    def retrieve_file(self, file_path: str) -> Optional[bytes]:
        """
        Retrieve a file from S3
        
        Args:
            file_path: Path to file (S3 key)
            
        Returns:
            File content as bytes, or None if not found
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=file_path
            )
            content = response['Body'].read()
            logger.debug(f"Retrieved file from S3: {file_path} ({len(content)} bytes)")
            return content
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found in S3: {file_path}")
                return None
            logger.error(f"Failed to retrieve file from S3 {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve file from S3 {file_path}: {e}")
            return None
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file from S3
        
        Args:
            file_path: Path to file (S3 key)
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket,
                Key=file_path
            )
            logger.info(f"Deleted file from S3: {file_path}")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == 'NoSuchKey':
                logger.warning(f"File not found for deletion in S3: {file_path}")
                return False
            logger.error(f"Failed to delete file from S3 {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete file from S3 {file_path}: {e}")
            return False
    
    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists in S3
        
        Args:
            file_path: Path to file (S3 key)
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket,
                Key=file_path
            )
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return False
            # Other errors - assume doesn't exist
            return False
        except Exception:
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        Get file size in bytes from S3
        
        Args:
            file_path: Path to file (S3 key)
            
        Returns:
            File size in bytes, or None if not found
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket,
                Key=file_path
            )
            return response.get('ContentLength')
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                return None
            logger.error(f"Failed to get file size from S3 for {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get file size from S3 for {file_path}: {e}")
            return None
