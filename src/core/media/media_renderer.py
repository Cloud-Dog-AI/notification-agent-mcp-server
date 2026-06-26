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
Description: Media Renderer for Notification Agent MCP Server - Renders images into PDF, Markdown, and text formats with channel-specific handling.

Related Requirements: FR1.19
Related Tasks: T30
Related Architecture: CC5.3.3
Related Tests: UT1.15, ST1.6, IT1.19, AT1.20

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented media rendering for PDF, Markdown, and text formats.

**************************************************
"""
import io
from src.utils.logger import get_logger
from typing import List, Dict, Any, Optional, Tuple

try:
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageReader = None

from .image_handler import ImageHandler
from .uuencoding import UUEncoding
from .media_fetcher import URIHandler
logger = get_logger(__name__)


class MediaRenderer:
    """
    Renders images into PDF, Markdown, and text formats.
    Supports UUEncoded images, URI references, and cached images.
    """

    def __init__(
        self,
        image_handler: Optional[ImageHandler] = None,
        uri_handler: Optional[URIHandler] = None,
        cache_manager: Optional[object] = None,
    ):
        """
        Initialize media renderer

        Args:
            image_handler: ImageHandler instance (optional)
            uri_handler: URIHandler instance (optional)
            cache_manager: Deprecated — retained for API compatibility only
        """
        self.image_handler = image_handler or ImageHandler()
        self.uri_handler = uri_handler or URIHandler(image_handler=self.image_handler)
        self.cache_manager = cache_manager
        logger.info("MediaRenderer initialized")
    
    def render_image_for_pdf(
        self,
        image_data: bytes,
        format: str,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> Optional[ImageReader]:
        """
        Render image for PDF using ReportLab ImageReader
        
        Args:
            image_data: Raw image bytes
            format: Image format (png, jpeg, gif)
            width: Optional width in points
            height: Optional height in points
            
        Returns:
            ReportLab ImageReader or None if rendering fails
        """
        if not PIL_AVAILABLE or not ImageReader:
            logger.warning("PIL/ReportLab not available for PDF image rendering")
            return None
        
        try:
            # Create ImageReader from bytes
            image_reader = ImageReader(io.BytesIO(image_data))
            
            # If dimensions specified, they'll be used when adding to PDF
            # ImageReader itself doesn't take dimensions, they're passed to addImage
            return image_reader
        except Exception as e:
            logger.error(f"Failed to create ImageReader for PDF: {e}")
            return None
    
    def render_image_for_markdown(
        self,
        image_uri: str,
        alt_text: Optional[str] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        Render image reference for Markdown
        
        Args:
            image_uri: Image URI (data URI, HTTP URL, or local path)
            alt_text: Alternative text for image
            title: Optional title attribute
            
        Returns:
            Markdown image syntax string
        """
        alt = alt_text or "Image"
        title_attr = f' "{title}"' if title else ""
        return f"![{alt}]({image_uri}{title_attr})"
    
    def render_image_for_text(
        self,
        image_uri: str,
        alt_text: Optional[str] = None,
    ) -> str:
        """
        Render image reference for text format
        
        Args:
            image_uri: Image URI (data URI, HTTP URL, or local path)
            alt_text: Alternative text for image
            
        Returns:
            Text representation of image
        """
        alt = alt_text or "Image"
        return f"[Image: {alt} - {image_uri}]"
    
    def process_images_in_content(
        self,
        content: List[Dict[str, Any]],
        output_format: str = "text",  # 'text', 'markdown', 'pdf', 'html'
        channel_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process images in content blocks and prepare for rendering
        
        Args:
            content: List of content blocks (may contain image references)
            output_format: Target output format
            channel_type: Channel type for channel-specific handling
            
        Returns:
            Tuple of (processed_content, image_data_list)
            - processed_content: Content with image references processed
            - image_data_list: List of image data dicts for rendering
        """
        processed_content = []
        image_data_list = []
        
        for block in content:
            if not isinstance(block, dict):
                processed_content.append(block)
                continue
            
            block_type = block.get("type", "text")
            block.get("body", "")
            
            # Check for image references in block
            if block_type == "image" or "image" in block:
                # Handle image block
                image_info = self._extract_image_info(block)
                if image_info:
                    image_data_list.append(image_info)
                    
                    # Add image reference to content based on format
                    if output_format == "markdown":
                        image_ref = self.render_image_for_markdown(
                            image_info.get("uri", ""),
                            image_info.get("alt_text")
                        )
                        processed_content.append({"type": "text", "body": image_ref})
                    elif output_format == "text":
                        image_ref = self.render_image_for_text(
                            image_info.get("uri", ""),
                            image_info.get("alt_text")
                        )
                        processed_content.append({"type": "text", "body": image_ref})
                    elif output_format == "pdf":
                        # For PDF, image will be rendered separately
                        processed_content.append({"type": "image", "body": "", "image_data": image_info})
                    else:
                        processed_content.append(block)
                else:
                    processed_content.append(block)
            else:
                processed_content.append(block)
        
        return processed_content, image_data_list
    
    def _extract_image_info(self, block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract image information from content block
        
        Args:
            block: Content block with image data
            
        Returns:
            Dict with image info or None
        """
        # Check for UUEncoded image
        if block.get("type") == "image" and "uuencoded" in block:
            data_uri = block.get("uuencoded")
            if UUEncoding.is_uuencoded(data_uri):
                result = UUEncoding.decode(data_uri)
                if result:
                    image_data, format = result
                    return {
                        "type": "uuencoded",
                        "image_data": image_data,
                        "format": format,
                        "uri": data_uri,
                        "alt_text": block.get("alt_text", "Image")
                    }
        
        # Check for URI reference
        if block.get("type") == "image" and "uri" in block:
            uri = block.get("uri")
            # Fetch image if needed
            if self.uri_handler:
                result = self.uri_handler.fetch_image(uri)
                if result:
                    image_data, format = result
                    return {
                        "type": "uri",
                        "image_data": image_data,
                        "format": format,
                        "uri": uri,
                        "alt_text": block.get("alt_text", "Image")
                    }
        
        return None
