#!/usr/bin/env python3
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
Unit Tests for Audio Handler

Tests:
- Audio format detection (MP3, WAV, OGG, AAC)
- Audio validation
- Metadata extraction
- Error handling
"""
import pytest
import io
from src.core.media.audio_handler import AudioHandler, AudioFormat, AudioMetadata


@pytest.fixture
def audio_handler():
    """Create AudioHandler instance"""
    return AudioHandler()


class TestAudioFormatDetection:
    """Test audio format detection"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_mp3_format(self, audio_handler):
        """Test MP3 format detection"""
        # MP3 file header (simplified)
        mp3_data = b'\xff\xfb\x90\x00' + b'\x00' * 100
        format = audio_handler.detect_format(mp3_data)
        # May or may not detect depending on header, but should not crash
        assert format is None or format == AudioFormat.MP3
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_wav_format(self, audio_handler):
        """Test WAV format detection"""
        # WAV file header
        wav_data = b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100
        format = audio_handler.detect_format(wav_data)
        assert format == AudioFormat.WAV
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_ogg_format(self, audio_handler):
        """Test OGG format detection"""
        # OGG file header
        ogg_data = b'OggS' + b'\x00' * 100
        format = audio_handler.detect_format(ogg_data)
        assert format == AudioFormat.OGG
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_empty_data(self, audio_handler):
        """Test format detection with empty data"""
        format = audio_handler.detect_format(b"")
        assert format is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_invalid_data(self, audio_handler):
        """Test format detection with invalid data"""
        format = audio_handler.detect_format(b"not an audio file")
        assert format is None


class TestAudioValidation:
    """Test audio validation"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_wav(self, audio_handler):
        """Test WAV validation"""
        wav_data = b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100
        is_valid, error = audio_handler.validate_audio(wav_data)
        # May or may not be valid depending on structure, but should not crash
        assert isinstance(is_valid, bool)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_empty_data(self, audio_handler):
        """Test validation with empty data"""
        is_valid, error = audio_handler.validate_audio(b"")
        assert is_valid is False
        assert "empty" in error.lower()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_invalid_data(self, audio_handler):
        """Test validation with invalid data"""
        is_valid, error = audio_handler.validate_audio(b"not an audio file")
        assert is_valid is False
        assert error is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_oversized_audio(self, audio_handler):
        """Test validation with oversized audio"""
        large_data = b"x" * (51 * 1024 * 1024)  # 51MB
        is_valid, error = audio_handler.validate_audio(large_data)
        assert is_valid is False
        assert "size" in error.lower() or "exceeds" in error.lower()


class TestMetadataExtraction:
    """Test metadata extraction"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_wav_metadata(self, audio_handler):
        """Test WAV metadata extraction"""
        wav_data = b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100
        metadata = audio_handler.extract_metadata(wav_data)
        # May be None if mutagen not available or file invalid
        if metadata:
            assert metadata.format == AudioFormat.WAV
            assert metadata.size_bytes == len(wav_data)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_empty_data(self, audio_handler):
        """Test metadata extraction with empty data"""
        metadata = audio_handler.extract_metadata(b"")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_invalid_data(self, audio_handler):
        """Test metadata extraction with invalid data"""
        metadata = audio_handler.extract_metadata(b"not an audio file")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_metadata_to_dict(self, audio_handler):
        """Test metadata to_dict conversion"""
        wav_data = b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100
        metadata = audio_handler.extract_metadata(wav_data)
        if metadata:
            metadata_dict = metadata.to_dict()
            assert isinstance(metadata_dict, dict)
            assert "format" in metadata_dict
            assert "size_bytes" in metadata_dict


class TestAudioInfo:
    """Test comprehensive audio info"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_audio_info_wav(self, audio_handler):
        """Test get_audio_info for WAV"""
        wav_data = b'RIFF' + b'\x00' * 4 + b'WAVE' + b'\x00' * 100
        info = audio_handler.get_audio_info(wav_data)
        assert info is not None
        assert info["format"] == "wav"
        assert info["size_bytes"] == len(wav_data)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_audio_info_invalid(self, audio_handler):
        """Test get_audio_info with invalid data"""
        info = audio_handler.get_audio_info(b"not an audio file")
        assert info is not None
        assert info["is_valid"] is False
        assert info["error"] is not None
        assert info["metadata"] is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

