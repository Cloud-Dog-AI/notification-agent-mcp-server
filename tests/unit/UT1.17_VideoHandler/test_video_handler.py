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
Unit Tests for Video Handler

Tests:
- Video format detection (MP4, WebM, OGV, AVI)
- Video validation
- Metadata extraction
- Error handling
"""
import pytest
from src.core.media.video_handler import VideoHandler, VideoFormat, VideoMetadata


@pytest.fixture
def video_handler():
    """Create VideoHandler instance"""
    return VideoHandler()


class TestVideoFormatDetection:
    """Test video format detection"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_mp4_format(self, video_handler):
        """Test MP4 format detection"""
        # MP4 file header
        mp4_data = b'\x00\x00\x00\x20ftypmp4' + b'\x00' * 100
        format = video_handler.detect_format(mp4_data)
        assert format == VideoFormat.MP4
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_webm_format(self, video_handler):
        """Test WebM format detection"""
        # WebM file header
        webm_data = b'\x1a\x45\xdf\xa3' + b'\x00' * 100
        format = video_handler.detect_format(webm_data)
        assert format == VideoFormat.WEBM
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_ogv_format(self, video_handler):
        """Test OGV format detection"""
        # OGV file header
        ogv_data = b'OggS' + b'\x00' * 100
        format = video_handler.detect_format(ogv_data)
        assert format == VideoFormat.OGV
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_avi_format(self, video_handler):
        """Test AVI format detection"""
        # AVI file header
        avi_data = b'RIFF' + b'\x00' * 4 + b'AVI ' + b'\x00' * 100
        format = video_handler.detect_format(avi_data)
        assert format == VideoFormat.AVI
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_empty_data(self, video_handler):
        """Test format detection with empty data"""
        format = video_handler.detect_format(b"")
        assert format is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_detect_format_invalid_data(self, video_handler):
        """Test format detection with invalid data"""
        format = video_handler.detect_format(b"not a video file")
        assert format is None


class TestVideoValidation:
    """Test video validation"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_mp4(self, video_handler):
        """Test MP4 validation"""
        mp4_data = b'\x00\x00\x00\x20ftypmp4' + b'\x00' * 100
        is_valid, error = video_handler.validate_video(mp4_data)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_webm(self, video_handler):
        """Test WebM validation"""
        webm_data = b'\x1a\x45\xdf\xa3' + b'\x00' * 100
        is_valid, error = video_handler.validate_video(webm_data)
        assert is_valid is True
        assert error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_empty_data(self, video_handler):
        """Test validation with empty data"""
        is_valid, error = video_handler.validate_video(b"")
        assert is_valid is False
        assert "empty" in error.lower()
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_invalid_data(self, video_handler):
        """Test validation with invalid data"""
        is_valid, error = video_handler.validate_video(b"not a video file")
        assert is_valid is False
        assert error is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_validate_oversized_video(self, video_handler):
        """Test validation with oversized video"""
        large_data = b"x" * (501 * 1024 * 1024)  # 501MB
        is_valid, error = video_handler.validate_video(large_data)
        assert is_valid is False
        assert "size" in error.lower() or "exceeds" in error.lower()


class TestMetadataExtraction:
    """Test metadata extraction"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_mp4_metadata(self, video_handler):
        """Test MP4 metadata extraction"""
        mp4_data = b'\x00\x00\x00\x20ftypmp4' + b'\x00' * 100
        metadata = video_handler.extract_metadata(mp4_data)
        assert metadata is not None
        assert metadata.format == VideoFormat.MP4
        assert metadata.size_bytes == len(mp4_data)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_empty_data(self, video_handler):
        """Test metadata extraction with empty data"""
        metadata = video_handler.extract_metadata(b"")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_extract_metadata_invalid_data(self, video_handler):
        """Test metadata extraction with invalid data"""
        metadata = video_handler.extract_metadata(b"not a video file")
        assert metadata is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_metadata_to_dict(self, video_handler):
        """Test metadata to_dict conversion"""
        mp4_data = b'\x00\x00\x00\x20ftypmp4' + b'\x00' * 100
        metadata = video_handler.extract_metadata(mp4_data)
        assert metadata is not None
        metadata_dict = metadata.to_dict()
        assert isinstance(metadata_dict, dict)
        assert "format" in metadata_dict
        assert "size_bytes" in metadata_dict


class TestVideoInfo:
    """Test comprehensive video info"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_video_info_mp4(self, video_handler):
        """Test get_video_info for MP4"""
        mp4_data = b'\x00\x00\x00\x20ftypmp4' + b'\x00' * 100
        info = video_handler.get_video_info(mp4_data)
        assert info is not None
        assert info["format"] == "mp4"
        assert info["size_bytes"] == len(mp4_data)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_get_video_info_invalid(self, video_handler):
        """Test get_video_info with invalid data"""
        info = video_handler.get_video_info(b"not a video file")
        assert info is not None
        assert info["is_valid"] is False
        assert info["error"] is not None
        assert info["metadata"] is None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.pure, pytest.mark.fast]

