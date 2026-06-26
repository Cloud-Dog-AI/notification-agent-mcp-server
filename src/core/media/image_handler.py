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
Description: Image Handler for Notification Agent MCP Server - Provides image format detection, validation, metadata extraction, and processing for PNG, GIF, and JPEG formats.

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3.1
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented image format detection, validation, and metadata extraction.

**************************************************
"""
import io
from src.utils.logger import get_logger
from enum import Enum
from typing import Optional, Dict, Any, Tuple

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

logger = get_logger(__name__)


class ImageFormat(str, Enum):
    """Supported image formats"""
    PNG = "png"
    JPEG = "jpeg"
    JPG = "jpg"  # Alias for JPEG
    GIF = "gif"


class ImageMetadata:
    """Image metadata container"""
    
    def __init__(
        self,
        format: ImageFormat,
        width: int,
        height: int,
        size_bytes: int,
        mime_type: str,
        mode: Optional[str] = None,
        has_transparency: bool = False,
    ):
        self.format = format
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self.mime_type = mime_type
        self.mode = mode
        self.has_transparency = has_transparency
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "format": self.format.value,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "mode": self.mode,
            "has_transparency": self.has_transparency,
        }


class ImageHandler:
    """
    Handles image format detection, validation, and metadata extraction.
    Supports PNG, GIF, and JPEG formats.
    """
    
    # Maximum image dimensions (configurable)
    MAX_WIDTH = 10000
    MAX_HEIGHT = 10000
    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
    
    # Supported formats
    SUPPORTED_FORMATS = {ImageFormat.PNG, ImageFormat.JPEG, ImageFormat.JPG, ImageFormat.GIF}
    
    def __init__(self, max_width: Optional[int] = None, max_height: Optional[int] = None, max_size_bytes: Optional[int] = None):
        """
        Initialize image handler
        
        Args:
            max_width: Maximum image width (default: 10000)
            max_height: Maximum image height (default: 10000)
            max_size_bytes: Maximum image size in bytes (default: 10MB)
        """
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow is required for image handling. Install with: pip install Pillow")
        
        self.max_width = max_width or self.MAX_WIDTH
        self.max_height = max_height or self.MAX_HEIGHT
        self.max_size_bytes = max_size_bytes or self.MAX_SIZE_BYTES
        logger.info(f"ImageHandler initialized: max_width={self.max_width}, max_height={self.max_height}, max_size_bytes={self.max_size_bytes}")
    
    def detect_format(self, image_data: bytes) -> Optional[ImageFormat]:
        """
        Detect image format from image data
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            ImageFormat enum or None if format not supported
        """
        if not image_data:
            return None
        
        try:
            # Use PIL to detect format
            image = Image.open(io.BytesIO(image_data))
            format_str = image.format.lower() if image.format else None
            
            if format_str == "png":
                return ImageFormat.PNG
            elif format_str in ["jpeg", "jpg"]:
                return ImageFormat.JPEG
            elif format_str == "gif":
                return ImageFormat.GIF
            else:
                logger.warning(f"Unsupported image format detected: {format_str}")
                return None
        except Exception as e:
            logger.error(f"Failed to detect image format: {e}")
            return None
    
    def validate_image(self, image_data: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate image data
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not image_data:
            return False, "Image data is empty"
        
        # Check size
        if len(image_data) > self.max_size_bytes:
            return False, f"Image size ({len(image_data)} bytes) exceeds maximum ({self.max_size_bytes} bytes)"
        
        # Try to open and validate with PIL
        try:
            image = Image.open(io.BytesIO(image_data))
            image.verify()  # Verify image integrity
            
            # Check dimensions
            width, height = image.size
            if width > self.max_width:
                return False, f"Image width ({width}) exceeds maximum ({self.max_width})"
            if height > self.max_height:
                return False, f"Image height ({height}) exceeds maximum ({self.max_height})"
            
            # Check format
            format_str = image.format.lower() if image.format else None
            if format_str not in ["png", "jpeg", "jpg", "gif"]:
                return False, f"Unsupported image format: {format_str}"
            
            return True, None
        except Exception as e:
            return False, f"Invalid image data: {str(e)}"
    
    def extract_metadata(self, image_data: bytes) -> Optional[ImageMetadata]:
        """
        Extract metadata from image
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            ImageMetadata object or None if extraction fails
        """
        if not image_data:
            return None
        
        try:
            image = Image.open(io.BytesIO(image_data))
            format_str = image.format.lower() if image.format else None
            
            # Map format
            if format_str == "png":
                image_format = ImageFormat.PNG
                mime_type = "image/png"
            elif format_str in ["jpeg", "jpg"]:
                image_format = ImageFormat.JPEG
                mime_type = "image/jpeg"
            elif format_str == "gif":
                image_format = ImageFormat.GIF
                mime_type = "image/gif"
            else:
                logger.warning(f"Unsupported format for metadata extraction: {format_str}")
                return None
            
            width, height = image.size
            mode = image.mode
            
            # Check for transparency
            has_transparency = False
            if image_format == ImageFormat.PNG:
                has_transparency = image.mode in ["RGBA", "LA"] or "transparency" in image.info
            elif image_format == ImageFormat.GIF:
                has_transparency = "transparency" in image.info or image.mode == "P"
            
            return ImageMetadata(
                format=image_format,
                width=width,
                height=height,
                size_bytes=len(image_data),
                mime_type=mime_type,
                mode=mode,
                has_transparency=has_transparency,
            )
        except Exception as e:
            logger.error(f"Failed to extract image metadata: {e}")
            return None
    
    def get_image_info(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive image information (format, validation, metadata)
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary with image info or None if processing fails
        """
        if not image_data:
            return None
        
        format = self.detect_format(image_data)
        is_valid, error = self.validate_image(image_data)
        metadata = self.extract_metadata(image_data) if is_valid else None
        
        return {
            "format": format.value if format else None,
            "is_valid": is_valid,
            "error": error,
            "metadata": metadata.to_dict() if metadata else None,
            "size_bytes": len(image_data),
        }
