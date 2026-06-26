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
Description: Media module for Notification Agent MCP Server - provides image processing, UUEncoding, URI handling, and media rendering.

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""
from .image_handler import ImageHandler, ImageFormat, ImageMetadata
from .audio_handler import AudioHandler, AudioFormat, AudioMetadata
from .video_handler import VideoHandler, VideoFormat, VideoMetadata
from .uuencoding import UUEncoding
from .media_fetcher import URIHandler
from .image_cache import ImageCacheManager
from .media_renderer import MediaRenderer

__all__ = [
    "ImageHandler", "ImageFormat", "ImageMetadata",
    "AudioHandler", "AudioFormat", "AudioMetadata",
    "VideoHandler", "VideoFormat", "VideoMetadata",
    "UUEncoding", "URIHandler", "ImageCacheManager", "MediaRenderer"
]
