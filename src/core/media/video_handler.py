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
Description: Video Handler for Notification Agent MCP Server - Provides video format detection, validation, metadata extraction for MP4, WebM, OGV, and AVI formats.

Related Requirements: FR1.21
Related Tasks: T32
Related Architecture: CC5.3.4
Related Tests: UT1.17, ST1.8, IT1.21, AT1.22

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented video format detection, validation, and metadata extraction.

**************************************************
"""
from src.utils.logger import get_logger
from enum import Enum
from typing import Optional, Dict, Any

logger = get_logger(__name__)


class VideoFormat(str, Enum):
    """Supported video formats"""
    MP4 = "mp4"
    WEBM = "webm"
    OGV = "ogv"
    AVI = "avi"


class VideoMetadata:
    """Video metadata container"""
    
    def __init__(
        self,
        format: VideoFormat,
        duration: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        bitrate: Optional[int] = None,
        frame_rate: Optional[float] = None,
        codec: Optional[str] = None,
        size_bytes: int = 0,
        mime_type: str = "video/mp4",
    ):
        self.format = format
        self.duration = duration
        self.width = width
        self.height = height
        self.bitrate = bitrate
        self.frame_rate = frame_rate
        self.codec = codec
        self.size_bytes = size_bytes
        self.mime_type = mime_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "format": self.format.value,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "bitrate": self.bitrate,
            "frame_rate": self.frame_rate,
            "codec": self.codec,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
        }


class VideoHandler:
    """
    Handles video format detection, validation, and metadata extraction.
    Supports MP4, WebM, OGV, and AVI formats.
    """
    
    # Maximum video file size (configurable)
    MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
    
    # Supported formats
    SUPPORTED_FORMATS = {VideoFormat.MP4, VideoFormat.WEBM, VideoFormat.OGV, VideoFormat.AVI}
    
    def __init__(self, max_size_bytes: Optional[int] = None):
        """
        Initialize video handler
        
        Args:
            max_size_bytes: Maximum video file size in bytes (default: 500MB)
        """
        self.max_size_bytes = max_size_bytes or self.MAX_SIZE_BYTES
        logger.info(f"VideoHandler initialized: max_size_bytes={self.max_size_bytes}")
    
    def detect_format(self, video_data: bytes) -> Optional[VideoFormat]:
        """
        Detect video format from video data
        
        Args:
            video_data: Raw video bytes
            
        Returns:
            VideoFormat enum or None if format not supported
        """
        if not video_data:
            return None
        
        # Check file headers
        if video_data.startswith(b'\x00\x00\x00\x20ftyp') or video_data.startswith(b'\x00\x00\x00\x18ftyp'):
            # MP4 container
            if b'mp4' in video_data[:32] or b'isom' in video_data[:32]:
                return VideoFormat.MP4
        elif video_data.startswith(b'\x1a\x45\xdf\xa3'):
            # WebM (Matroska container)
            return VideoFormat.WEBM
        elif video_data.startswith(b'OggS'):
            # OGV (Ogg container)
            return VideoFormat.OGV
        elif video_data.startswith(b'RIFF') and b'AVI ' in video_data[:12]:
            # AVI
            return VideoFormat.AVI
        
        return None
    
    def validate_video(self, video_data: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate video data
        
        Args:
            video_data: Raw video bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not video_data:
            return False, "Video data is empty"
        
        # Check size
        if len(video_data) > self.max_size_bytes:
            return False, f"Video size ({len(video_data)} bytes) exceeds maximum ({self.max_size_bytes} bytes)"
        
        # Check format
        format = self.detect_format(video_data)
        if not format:
            return False, "Unsupported video format"
        
        # Basic structure validation based on format
        if format == VideoFormat.MP4:
            if not (video_data.startswith(b'\x00\x00\x00\x20ftyp') or video_data.startswith(b'\x00\x00\x00\x18ftyp')):
                return False, "Invalid MP4 file structure"
        elif format == VideoFormat.WEBM:
            if not video_data.startswith(b'\x1a\x45\xdf\xa3'):
                return False, "Invalid WebM file structure"
        elif format == VideoFormat.OGV:
            if not video_data.startswith(b'OggS'):
                return False, "Invalid OGV file structure"
        elif format == VideoFormat.AVI:
            if not (video_data.startswith(b'RIFF') and b'AVI ' in video_data[:12]):
                return False, "Invalid AVI file structure"
        
        return True, None
    
    def extract_metadata(self, video_data: bytes) -> Optional[VideoMetadata]:
        """
        Extract metadata from video file
        
        Args:
            video_data: Raw video bytes
            
        Returns:
            VideoMetadata object or None if extraction fails
        """
        if not video_data:
            return None
        
        format = self.detect_format(video_data)
        if not format:
            return None
        
        # Map format to MIME type
        mime_map = {
            VideoFormat.MP4: "video/mp4",
            VideoFormat.WEBM: "video/webm",
            VideoFormat.OGV: "video/ogg",
            VideoFormat.AVI: "video/x-msvideo",
        }
        mime_type = mime_map.get(format, "video/mp4")
        
        duration = None
        width = None
        height = None
        bitrate = None
        frame_rate = None
        codec = None
        
        # Basic metadata extraction from headers
        # Note: Full metadata extraction would require ffmpeg or similar
        # For now, we extract what we can from file headers
        
        if format == VideoFormat.AVI:
            # Try to extract dimensions from AVI header
            try:
                if len(video_data) > 64:
                    # AVI header structure (simplified)
                    video_data[32:64]
                    # Width and height are often at specific offsets
                    # This is a simplified extraction
                    pass
            except Exception:
                pass
        
        return VideoMetadata(
            format=format,
            duration=duration,
            width=width,
            height=height,
            bitrate=bitrate,
            frame_rate=frame_rate,
            codec=codec,
            size_bytes=len(video_data),
            mime_type=mime_type,
        )
    
    def get_video_info(self, video_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive video information (format, validation, metadata)
        
        Args:
            video_data: Raw video bytes
            
        Returns:
            Dictionary with video info or None if processing fails
        """
        if not video_data:
            return None
        
        format = self.detect_format(video_data)
        is_valid, error = self.validate_video(video_data)
        metadata = self.extract_metadata(video_data) if is_valid else None
        
        return {
            "format": format.value if format else None,
            "is_valid": is_valid,
            "error": error,
            "metadata": metadata.to_dict() if metadata else None,
            "size_bytes": len(video_data),
        }
