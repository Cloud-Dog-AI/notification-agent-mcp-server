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
Description: UUEncoding utilities for Notification Agent MCP Server - Provides encoding and decoding of images using UUEncoding for embedding in messages.

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3.1
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented UUEncoding encoding/decoding for images.

**************************************************
"""
import base64
from src.utils.logger import get_logger
from typing import Optional, Tuple

logger = get_logger(__name__)


class UUEncoding:
    """
    UUEncoding utilities for encoding and decoding image data.
    UUEncoding is used to embed images directly in messages.
    """
    
    @staticmethod
    def encode(image_data: bytes, image_format: str = "png") -> str:
        """
        Encode image data using UUEncoding (base64)
        
        Args:
            image_data: Raw image bytes
            image_format: Image format (png, jpeg, gif)
            
        Returns:
            UUEncoded string (data URI format: data:image/{format};base64,{data})
        """
        if not image_data:
            raise ValueError("Image data cannot be empty")
        
        # Encode to base64
        encoded_data = base64.b64encode(image_data).decode('utf-8')
        
        # Create data URI
        mime_type = f"image/{image_format.lower()}"
        data_uri = f"data:{mime_type};base64,{encoded_data}"
        
        logger.debug(f"UUEncoded image: format={image_format}, size={len(image_data)} bytes, encoded_size={len(encoded_data)} chars")
        return data_uri
    
    @staticmethod
    def encode_audio(audio_data: bytes, audio_format: str = "mp3") -> str:
        """
        Encode audio data using UUEncoding (base64)
        
        Args:
            audio_data: Raw audio bytes
            audio_format: Audio format (mp3, wav, ogg, aac)
            
        Returns:
            UUEncoded string (data URI format: data:audio/{format};base64,{data})
        """
        if not audio_data:
            raise ValueError("Audio data cannot be empty")
        
        # Encode to base64
        encoded_data = base64.b64encode(audio_data).decode('utf-8')
        
        # Create data URI
        mime_type = f"audio/{audio_format.lower()}"
        data_uri = f"data:{mime_type};base64,{encoded_data}"
        
        logger.debug(f"UUEncoded audio: format={audio_format}, size={len(audio_data)} bytes, encoded_size={len(encoded_data)} chars")
        return data_uri
    
    @staticmethod
    def encode_video(video_data: bytes, video_format: str = "mp4") -> str:
        """
        Encode video data using UUEncoding (base64)
        
        Args:
            video_data: Raw video bytes
            video_format: Video format (mp4, webm, ogv, avi)
            
        Returns:
            UUEncoded string (data URI format: data:video/{format};base64,{data})
        """
        if not video_data:
            raise ValueError("Video data cannot be empty")
        
        # Encode to base64
        encoded_data = base64.b64encode(video_data).decode('utf-8')
        
        # Create data URI
        mime_type = f"video/{video_format.lower()}"
        data_uri = f"data:{mime_type};base64,{encoded_data}"
        
        logger.debug(f"UUEncoded video: format={video_format}, size={len(video_data)} bytes, encoded_size={len(encoded_data)} chars")
        return data_uri
    
    @staticmethod
    def decode(data_uri: str) -> Optional[Tuple[bytes, str]]:
        """
        Decode UUEncoded media data (image, audio, or video)
        
        Args:
            data_uri: Data URI string (data:{type}/{format};base64,{data})
            
        Returns:
            Tuple of (media_bytes, format) or None if decoding fails
        """
        if not data_uri or not data_uri.startswith("data:"):
            logger.warning("Invalid data URI format")
            return None
        
        try:
            # Parse data URI: data:{type}/{format};base64,{data}
            parts = data_uri.split(",", 1)
            if len(parts) != 2:
                logger.warning("Invalid data URI format: missing comma separator")
                return None
            
            header = parts[0]  # data:{type}/{format};base64
            encoded_data = parts[1]  # base64 encoded data
            
            # Extract format from header (supports image/, audio/, video/)
            media_format = None
            if "image/" in header:
                format_part = header.split("image/")[1].split(";")[0]
                media_format = format_part.lower()
            elif "audio/" in header:
                format_part = header.split("audio/")[1].split(";")[0]
                media_format = format_part.lower()
            elif "video/" in header:
                format_part = header.split("video/")[1].split(";")[0]
                media_format = format_part.lower()
            else:
                logger.warning("Could not extract media format from data URI")
                return None
            
            # Decode base64
            media_data = base64.b64decode(encoded_data)
            
            logger.debug(f"UUDecoded media: format={media_format}, size={len(media_data)} bytes")
            return (media_data, media_format)
        except Exception as e:
            logger.error(f"Failed to decode UUEncoded data: {e}")
            return None
    
    @staticmethod
    def is_uuencoded(data: str) -> bool:
        """
        Check if a string is UUEncoded (data URI format)
        
        Args:
            data: String to check
            
        Returns:
            True if string appears to be UUEncoded
        """
        return isinstance(data, str) and (
            data.startswith("data:image/") or 
            data.startswith("data:audio/") or 
            data.startswith("data:video/")
        ) and ";base64," in data
    
    @staticmethod
    def extract_format_from_uri(data_uri: str) -> Optional[str]:
        """
        Extract media format from data URI without decoding
        
        Args:
            data_uri: Data URI string
            
        Returns:
            Media format (png, jpeg, gif, mp3, wav, mp4, webm, etc.) or None
        """
        if not UUEncoding.is_uuencoded(data_uri):
            return None
        
        try:
            header = data_uri.split(",", 1)[0]
            if "image/" in header:
                format_part = header.split("image/")[1].split(";")[0]
                return format_part.lower()
            elif "audio/" in header:
                format_part = header.split("audio/")[1].split(";")[0]
                return format_part.lower()
            elif "video/" in header:
                format_part = header.split("video/")[1].split(";")[0]
                return format_part.lower()
        except Exception:
            pass
        
        return None
