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
Description: Media Processor for Notification Agent MCP Server - Processes media references in content, handles duplication, and prepares media for delivery

Related Requirements: FR1.19, FR1.21, FR1.23
Related Tasks: T30, T32
Related Architecture: CC5.3.6
Related Tests: IT1.19, IT1.20, IT1.21, AT1.22, AT1.23, AT1.24

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented media processing, duplication, and delivery preparation.

**************************************************
"""
from typing import Optional, Dict, Any, List
import re

from .image_handler import ImageHandler
from .audio_handler import AudioHandler
from .video_handler import VideoHandler
from .media_fetcher import URIHandler
from .uuencoding import UUEncoding
from ..storage.storage_manager import StorageManager
from ...utils.logger import get_logger

logger = get_logger(__name__)


class MediaProcessor:
    """
    Processes media references in content, handles duplication based on channel settings,
    and prepares media for delivery (PDF links, HTML embedding, etc.)
    """
    
    def __init__(
        self,
        storage_manager: Optional[StorageManager] = None,
        image_handler: Optional[ImageHandler] = None,
        audio_handler: Optional[AudioHandler] = None,
        video_handler: Optional[VideoHandler] = None,
        uri_handler: Optional[URIHandler] = None,
    ):
        """
        Initialize media processor
        
        Args:
            storage_manager: StorageManager instance for storing duplicated media
            image_handler: ImageHandler instance
            audio_handler: AudioHandler instance
            video_handler: VideoHandler instance
            uri_handler: URIHandler instance
        """
        self.storage_manager = storage_manager
        self.image_handler = image_handler or ImageHandler()
        self.audio_handler = audio_handler or AudioHandler()
        self.video_handler = video_handler or VideoHandler()
        self.uri_handler = uri_handler or URIHandler(
            image_handler=self.image_handler,
            audio_handler=self.audio_handler,
            video_handler=self.video_handler
        )
        self.uuencoding = UUEncoding()
        logger.info("MediaProcessor initialized")
    
    def extract_media_references(self, content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract media references from content blocks
        
        Args:
            content: List of content blocks
            
        Returns:
            List of media reference dicts with 'type', 'uri', 'format', 'method' (uuencoded/uri)
        """
        media_refs = []
        
        for block in content:
            if not isinstance(block, dict):
                continue
            
            block_type = block.get("type", "text")
            body = block.get("body", "")
            uri = block.get("uri")  # Check uri field for image/audio/video blocks
            
            # Check if this is an explicit media block with uri field
            if block_type in ["image", "audio", "video"] and uri:
                # Check if it's a data URI
                if UUEncoding.is_uuencoded(uri):
                    format = UUEncoding.extract_format_from_uri(uri)
                    if format:
                        media_refs.append({
                            "type": block_type,
                            "uri": uri,
                            "format": format,
                            "method": "uuencoded",
                            "alt_text": block.get("alt_text"),
                            "metadata": block.get("metadata", {})
                        })
                else:
                    # Regular URI
                    format = uri.split(".")[-1].lower() if "." in uri else None
                    media_refs.append({
                        "type": block_type,
                        "uri": uri,
                        "format": format,
                        "method": "uri",
                        "alt_text": block.get("alt_text"),
                        "metadata": block.get("metadata", {})
                    })
                continue  # Skip body processing for explicit media blocks
            
            # Check for UUEncoded media (data URIs) in body
            if UUEncoding.is_uuencoded(body):
                format = UUEncoding.extract_format_from_uri(body)
                if format:
                    # Determine media type from format
                    if format in ["png", "jpeg", "jpg", "gif"]:
                        media_refs.append({
                            "type": "image",
                            "uri": body,
                            "format": format,
                            "method": "uuencoded"
                        })
                    elif format in ["mp3", "wav", "ogg", "aac", "m4a"]:
                        media_refs.append({
                            "type": "audio",
                            "uri": body,
                            "format": format,
                            "method": "uuencoded"
                        })
                    elif format in ["mp4", "webm", "ogv", "avi"]:
                        media_refs.append({
                            "type": "video",
                            "uri": body,
                            "format": format,
                            "method": "uuencoded"
                        })
            
            # Check for URI references in markdown/image tags
            # Markdown: ![alt](url) or [text](url)
            # HTML: <img src="url">, <audio src="url">, <video src="url">
            uri_patterns = [
                (r'!\[.*?\]\((https?://[^\)]+)\)', "image"),  # Markdown image
                (r'<img[^>]+src=["\']([^"\']+)["\']', "image"),  # HTML img
                (r'<audio[^>]+src=["\']([^"\']+)["\']', "audio"),  # HTML audio
                (r'<video[^>]+src=["\']([^"\']+)["\']', "video"),  # HTML video
                (r'https?://[^\s<>"\']+\.(png|jpg|jpeg|gif|mp3|wav|ogg|mp4|webm|ogv|avi)', "auto"),  # Direct URL
            ]
            
            for pattern, media_type in uri_patterns:
                matches = re.finditer(pattern, body, re.IGNORECASE)
                for match in matches:
                    uri = match.group(1) if match.groups() else match.group(0)
                    if media_type == "auto":
                        # Detect from extension
                        ext = uri.split(".")[-1].lower()
                        if ext in ["png", "jpg", "jpeg", "gif"]:
                            media_type = "image"
                        elif ext in ["mp3", "wav", "ogg", "aac", "m4a"]:
                            media_type = "audio"
                        elif ext in ["mp4", "webm", "ogv", "avi"]:
                            media_type = "video"
                        else:
                            continue
                    
                    media_refs.append({
                        "type": media_type,
                        "uri": uri,
                        "format": uri.split(".")[-1].lower() if "." in uri else None,
                        "method": "uri"
                    })
        
        return media_refs
    
    def process_media(
        self,
        media_refs: List[Dict[str, Any]],
        channel_config: Dict[str, Any],
        message_id: Optional[int] = None,
        delivery_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Process media references: fetch, validate, duplicate if needed
        
        Args:
            media_refs: List of media reference dicts
            channel_config: Channel configuration with duplication settings
            message_id: Message ID for storage
            delivery_id: Delivery ID for storage
            
        Returns:
            List of processed media dicts with 'type', 'url', 'format', 'metadata', 'storage_info'
        """
        processed_media = []
        
        # Get duplication settings from channel config
        duplicate_all = channel_config.get("duplicate_external_media", False)
        duplicate_images = channel_config.get("duplicate_images", duplicate_all)
        duplicate_audio = channel_config.get("duplicate_audio", duplicate_all)
        duplicate_video = channel_config.get("duplicate_video", duplicate_all)
        
        for ref in media_refs:
            media_type = ref.get("type")
            uri = ref.get("uri")
            method = ref.get("method")
            format = ref.get("format")
            
            if not uri:
                continue
            
            processed = {
                "type": media_type,
                "format": format,
                "original_uri": uri,
                "alt_text": ref.get("alt_text"),  # Preserve alt_text from original block
            }
            
            # Check if should duplicate
            should_duplicate = False
            if media_type == "image":
                should_duplicate = duplicate_images
            elif media_type == "audio":
                should_duplicate = duplicate_audio
            elif media_type == "video":
                should_duplicate = duplicate_video
            
            # Process based on method
            if method == "uuencoded":
                # Decode and store if duplication enabled
                decoded = UUEncoding.decode(uri)
                if decoded:
                    media_data, detected_format = decoded
                    processed["format"] = detected_format
                    
                    if should_duplicate and self.storage_manager:
                        # Store in local storage
                        try:
                            storage_info = self.storage_manager.store_file(
                                file_content=media_data,
                                file_type=media_type,
                                message_id=message_id,
                                delivery_id=delivery_id,
                                metadata={"format": detected_format}
                            )
                            processed["storage_info"] = storage_info
                            processed["url"] = storage_info.get("access_url") or storage_info.get("storage_uri")
                            processed["is_local"] = True
                        except Exception as e:
                            logger.warning(f"Failed to store {media_type} media: {e}")
                            processed["url"] = uri  # Fallback to original
                            processed["is_local"] = False
                    else:
                        processed["url"] = uri
                        processed["is_local"] = False
                    
                    # Extract metadata
                    if media_type == "image":
                        metadata = self.image_handler.extract_metadata(media_data)
                        if metadata:
                            processed["metadata"] = metadata.to_dict()
                    elif media_type == "audio":
                        metadata = self.audio_handler.extract_metadata(media_data)
                        if metadata:
                            processed["metadata"] = metadata.to_dict()
                    elif media_type == "video":
                        metadata = self.video_handler.extract_metadata(media_data)
                        if metadata:
                            processed["metadata"] = metadata.to_dict()
            
            elif method == "uri":
                # Fetch from URI and store if duplication enabled
                if should_duplicate and self.storage_manager:
                    try:
                        fetched = self.uri_handler.fetch_media(uri, media_type)
                        if fetched:
                            media_data, detected_format = fetched
                            processed["format"] = detected_format
                            
                            # Store in local storage
                            storage_info = self.storage_manager.store_file(
                                file_content=media_data,
                                file_type=media_type,
                                message_id=message_id,
                                delivery_id=delivery_id,
                                metadata={"format": detected_format}
                            )
                            processed["storage_info"] = storage_info
                            processed["url"] = storage_info.get("access_url") or storage_info.get("storage_uri")
                            processed["is_local"] = True
                            
                            # Extract metadata
                            if media_type == "image":
                                metadata = self.image_handler.extract_metadata(media_data)
                                if metadata:
                                    processed["metadata"] = metadata.to_dict()
                            elif media_type == "audio":
                                metadata = self.audio_handler.extract_metadata(media_data)
                                if metadata:
                                    processed["metadata"] = metadata.to_dict()
                            elif media_type == "video":
                                metadata = self.video_handler.extract_metadata(media_data)
                                if metadata:
                                    processed["metadata"] = metadata.to_dict()
                        else:
                            processed["url"] = uri
                            processed["is_local"] = False
                    except Exception as e:
                        logger.warning(f"Failed to fetch and store {media_type} media from {uri}: {e}")
                        processed["url"] = uri
                        processed["is_local"] = False
                else:
                    # Use original URI
                    processed["url"] = uri
                    processed["is_local"] = False
            
            processed_media.append(processed)
        
        return processed_media
    
    def prepare_media_for_pdf(self, processed_media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare media links for PDF generation
        
        Args:
            processed_media: List of processed media dicts
            
        Returns:
            List of media link dicts for PDF generator
        """
        pdf_links = []
        
        for media in processed_media:
            media_type = media.get("type")
            url = media.get("url")
            format = media.get("format")
            metadata = media.get("metadata", {})
            
            if url:
                pdf_links.append({
                    "type": media_type,
                    "url": url,
                    "format": format,
                    "metadata": metadata
                })
        
        return pdf_links
    
    def prepare_media_for_html(self, processed_media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prepare media for HTML embedding
        
        Args:
            processed_media: List of processed media dicts
            
        Returns:
            List of media dicts for HTML generator
        """
        return processed_media  # HTML generator can use processed_media directly
