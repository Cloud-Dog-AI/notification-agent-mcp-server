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
Description: Audio Handler for Notification Agent MCP Server - Provides audio format detection, validation, metadata extraction for MP3, WAV, OGG, and AAC formats.

Related Requirements: FR1.21
Related Tasks: T32
Related Architecture: CC5.3.4
Related Tests: UT1.16, ST1.7, IT1.20, AT1.22

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented audio format detection, validation, and metadata extraction.

**************************************************
"""
import io
from src.utils.logger import get_logger
from enum import Enum
from typing import Optional, Dict, Any

try:
    from mutagen import File as MutagenFile
    from mutagen.mp3 import MP3
    from mutagen.wave import WAVE
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MutagenFile = None
    MP3 = None
    WAVE = None
    OggVorbis = None
    MP4 = None

logger = get_logger(__name__)


class AudioFormat(str, Enum):
    """Supported audio formats"""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    AAC = "aac"
    M4A = "m4a"  # AAC in MP4 container


class AudioMetadata:
    """Audio metadata container"""
    
    def __init__(
        self,
        format: AudioFormat,
        duration: Optional[float] = None,
        bitrate: Optional[int] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        size_bytes: int = 0,
        mime_type: str = "audio/mpeg",
        title: Optional[str] = None,
        artist: Optional[str] = None,
    ):
        self.format = format
        self.duration = duration
        self.bitrate = bitrate
        self.sample_rate = sample_rate
        self.channels = channels
        self.size_bytes = size_bytes
        self.mime_type = mime_type
        self.title = title
        self.artist = artist
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            "format": self.format.value,
            "duration": self.duration,
            "bitrate": self.bitrate,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "size_bytes": self.size_bytes,
            "mime_type": self.mime_type,
            "title": self.title,
            "artist": self.artist,
        }


class AudioHandler:
    """
    Handles audio format detection, validation, and metadata extraction.
    Supports MP3, WAV, OGG, and AAC formats.
    """
    
    # Maximum audio file size (configurable)
    MAX_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
    
    # Supported formats
    SUPPORTED_FORMATS = {AudioFormat.MP3, AudioFormat.WAV, AudioFormat.OGG, AudioFormat.AAC, AudioFormat.M4A}
    
    def __init__(self, max_size_bytes: Optional[int] = None):
        """
        Initialize audio handler
        
        Args:
            max_size_bytes: Maximum audio file size in bytes (default: 50MB)
        """
        if not MUTAGEN_AVAILABLE:
            logger.debug("mutagen not available. Audio metadata extraction will be limited.")
        
        self.max_size_bytes = max_size_bytes or self.MAX_SIZE_BYTES
        logger.info(f"AudioHandler initialized: max_size_bytes={self.max_size_bytes}")
    
    def detect_format(self, audio_data: bytes) -> Optional[AudioFormat]:
        """
        Detect audio format from audio data
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            AudioFormat enum or None if format not supported
        """
        if not audio_data:
            return None
        
        # Check file headers
        if audio_data.startswith(b'ID3') or audio_data.startswith(b'\xff\xfb') or audio_data.startswith(b'\xff\xf3'):
            return AudioFormat.MP3
        elif audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
            return AudioFormat.WAV
        elif audio_data.startswith(b'OggS'):
            return AudioFormat.OGG
        elif audio_data.startswith(b'\x00\x00\x00\x20ftyp') or audio_data.startswith(b'\x00\x00\x00\x18ftyp'):
            # MP4/M4A container (AAC)
            if b'mp4' in audio_data[:20] or b'M4A' in audio_data[:20]:
                return AudioFormat.M4A
            return AudioFormat.AAC
        
        # Try mutagen if available
        if MUTAGEN_AVAILABLE:
            try:
                audio_file = MutagenFile(io.BytesIO(audio_data))
                if audio_file:
                    mime_type = audio_file.mime[0] if hasattr(audio_file, 'mime') and audio_file.mime else None
                    if mime_type == 'audio/mpeg':
                        return AudioFormat.MP3
                    elif mime_type == 'audio/wav' or mime_type == 'audio/x-wav':
                        return AudioFormat.WAV
                    elif mime_type == 'audio/ogg' or mime_type == 'audio/vorbis':
                        return AudioFormat.OGG
                    elif mime_type == 'audio/mp4' or mime_type == 'audio/x-m4a':
                        return AudioFormat.M4A
            except Exception as e:
                logger.debug(f"mutagen format detection failed: {e}")
        
        return None
    
    def validate_audio(self, audio_data: bytes) -> tuple[bool, Optional[str]]:
        """
        Validate audio data
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not audio_data:
            return False, "Audio data is empty"
        
        # Check size
        if len(audio_data) > self.max_size_bytes:
            return False, f"Audio size ({len(audio_data)} bytes) exceeds maximum ({self.max_size_bytes} bytes)"
        
        # Check format
        format = self.detect_format(audio_data)
        if not format:
            return False, "Unsupported audio format"
        
        # Try to load with mutagen for validation
        if MUTAGEN_AVAILABLE:
            try:
                audio_file = MutagenFile(io.BytesIO(audio_data))
                if not audio_file:
                    return False, "Invalid audio file structure"
            except Exception as e:
                logger.warning(f"Audio validation warning: {e}")
                # Don't fail validation if mutagen can't parse, might be valid but unsupported metadata
        
        return True, None
    
    def extract_metadata(self, audio_data: bytes) -> Optional[AudioMetadata]:
        """
        Extract metadata from audio file
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            AudioMetadata object or None if extraction fails
        """
        if not audio_data:
            return None
        
        format = self.detect_format(audio_data)
        if not format:
            return None
        
        # Map format to MIME type
        mime_map = {
            AudioFormat.MP3: "audio/mpeg",
            AudioFormat.WAV: "audio/wav",
            AudioFormat.OGG: "audio/ogg",
            AudioFormat.AAC: "audio/aac",
            AudioFormat.M4A: "audio/mp4",
        }
        mime_type = mime_map.get(format, "audio/mpeg")
        
        duration = None
        bitrate = None
        sample_rate = None
        channels = None
        title = None
        artist = None
        
        # Extract metadata using mutagen if available
        if MUTAGEN_AVAILABLE:
            try:
                audio_file = MutagenFile(io.BytesIO(audio_data))
                if audio_file:
                    # Duration
                    if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                        duration = audio_file.info.length
                    
                    # Bitrate
                    if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'bitrate'):
                        bitrate = audio_file.info.bitrate
                    
                    # Sample rate
                    if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'sample_rate'):
                        sample_rate = audio_file.info.sample_rate
                    
                    # Channels
                    if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'channels'):
                        channels = audio_file.info.channels
                    
                    # Title
                    if hasattr(audio_file, 'tags'):
                        if 'TIT2' in audio_file.tags or 'TITLE' in audio_file.tags:
                            title = str(audio_file.tags.get('TIT2', audio_file.tags.get('TITLE', [''])[0]))
                    
                    # Artist
                    if hasattr(audio_file, 'tags'):
                        if 'TPE1' in audio_file.tags or 'ARTIST' in audio_file.tags:
                            artist = str(audio_file.tags.get('TPE1', audio_file.tags.get('ARTIST', [''])[0]))
            except Exception as e:
                logger.warning(f"Failed to extract audio metadata with mutagen: {e}")
        
        return AudioMetadata(
            format=format,
            duration=duration,
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
            size_bytes=len(audio_data),
            mime_type=mime_type,
            title=title,
            artist=artist,
        )
    
    def get_audio_info(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive audio information (format, validation, metadata)
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Dictionary with audio info or None if processing fails
        """
        if not audio_data:
            return None
        
        format = self.detect_format(audio_data)
        is_valid, error = self.validate_audio(audio_data)
        metadata = self.extract_metadata(audio_data) if is_valid else None
        
        return {
            "format": format.value if format else None,
            "is_valid": is_valid,
            "error": error,
            "metadata": metadata.to_dict() if metadata else None,
            "size_bytes": len(audio_data),
        }
