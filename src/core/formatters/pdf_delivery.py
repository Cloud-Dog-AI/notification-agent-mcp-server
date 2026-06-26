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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: PDF Delivery Helper for Notification Agent MCP Server - Handles PDF generation, storage, and attachment/link creation for deliveries

Related Requirements: FR1.18
Related Tasks: T29
Related Architecture: CC5.2.4
Related Tests: UT1.4, ST1.5, IT1.18, AT1.19

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import re
from typing import Optional, Dict, Any, List

from src.core.formatters.pdf_generator import PDFGenerator, REPORTLAB_AVAILABLE
from src.core.formatters.pdf_preferences import PDFPreferenceResolver
from src.core.storage.storage_manager import StorageManager
from src.core.media.media_processor import MediaProcessor
from src.utils.logger import get_logger

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

logger = get_logger(__name__)


class PDFDeliveryHelper:
    """Helper class for PDF generation and delivery integration"""
    
    def __init__(
        self,
        pdf_generator: Optional[PDFGenerator] = None,
        preference_resolver: Optional[PDFPreferenceResolver] = None,
        storage_manager: Optional[StorageManager] = None,
        media_processor: Optional[MediaProcessor] = None
    ):
        """
        Initialize PDF delivery helper
        
        Args:
            pdf_generator: PDFGenerator instance (optional)
            preference_resolver: PDFPreferenceResolver instance (optional)
            storage_manager: StorageManager instance (optional)
            media_processor: MediaProcessor instance (optional)
        """
        self.pdf_generator = pdf_generator or (PDFGenerator() if REPORTLAB_AVAILABLE else None)
        self.preference_resolver = preference_resolver or PDFPreferenceResolver()
        self.storage_manager = storage_manager
        self.media_processor = media_processor
        # Get URI handler from media_processor if available
        self.uri_handler = media_processor.uri_handler if media_processor else None
        logger.info("PDFDeliveryHelper initialized")
    
    def generate_and_prepare_pdf(
        self,
        content: List[Dict[str, Any]],
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        message_id: Optional[int] = None,
        delivery_id: Optional[int] = None,
        language: Optional[str] = None,
        content_style: Optional[str] = None,
        user_preference: Optional[str] = None,
        processed_media: Optional[List[Dict[str, Any]]] = None,
        title: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate PDF and prepare for delivery based on preferences
        
        Args:
            content: Formatted content blocks
            user_id: User ID for preference resolution
            channel_id: Channel ID for preference resolution
            message_id: Message ID for storage tracking
            delivery_id: Delivery ID for storage tracking
            language: Language for PDF (optional)
            content_style: Content style (text, markdown, html)
            
        Returns:
            Dict with PDF info (bytes, path, preference) or None if PDF not needed
        """
        # Delivery worker now initializes this helper with the active PDF backend
        # (WeasyPrint in the current runtime). Do not reject generation purely
        # because the legacy ReportLab backend is unavailable.
        if not self.pdf_generator:
            logger.warning("PDF generation not available")
            return None
        
        # Resolve PDF preference (use user_preference parameter if provided, otherwise lookup)
        preference = self.preference_resolver.resolve_preference(
            user_id=user_id,
            channel_id=channel_id,
            user_preference=user_preference  # Pass explicit preference (e.g., from destination preferences)
        )
        
        # Check if PDF should be generated
        if not self.preference_resolver.should_generate_pdf(preference):
            logger.debug("PDF generation not required (preference: none)")
            return None
        
        # Convert content to text/markdown/html for PDF
        pdf_content = self._content_to_text(content, content_style)
        
        # Generate PDF
        try:
            # Extract image data from processed_media for embedding
            processed_images = None
            media_links = None
            
            if processed_media:
                # Extract actual image data (bytes) from processed_media
                processed_images = []
                media_links = []
                
                for media in processed_media:
                    media_type = media.get("type")
                    if media_type != "image":
                        # For non-image media, just add to links
                        url = media.get("url") or media.get("original_uri")
                        if url:
                            media_links.append({
                                "type": media_type,
                                "url": url,
                                "format": media.get("format", "")
                            })
                        continue
                    
                    # For images, extract actual image bytes
                    image_bytes = None
                    image_format = media.get("format", "")
                    alt_text = media.get("alt_text", "")
                    metadata = media.get("metadata", {})
                    
                    # Try to get image bytes from various sources (in priority order)
                    # 1. Check if image_bytes is already in processed_media (from UUEncoded data)
                    if media.get("image_bytes"):
                        image_bytes = media.get("image_bytes")
                        logger.debug("Using image_bytes from processed_media")
                    # 2. Check if URL is a data URI
                    else:
                        url = media.get("url") or media.get("original_uri")
                        
                        if url and url.startswith("data:image/"):
                            # Decode data URI
                            from src.core.media.uuencoding import UUEncoding
                            decoded = UUEncoding.decode(url)
                            if decoded:
                                image_bytes, detected_format = decoded
                                image_format = detected_format or image_format
                                logger.debug(f"Decoded image from data URI: {len(image_bytes)} bytes, format={image_format}")
                        elif url and self.uri_handler:
                            # Fetch from URL (HTTP or local file)
                            try:
                                fetched = self.uri_handler.fetch_image(url)
                                if fetched:
                                    image_bytes, detected_format = fetched
                                    image_format = detected_format or image_format
                                    logger.debug(f"Fetched image from URL: {len(image_bytes)} bytes, format={image_format}")
                            except Exception as e:
                                logger.warning(f"Failed to fetch image from {url}: {e}")
                        elif media.get("storage_info"):
                            # Retrieve from storage
                            storage_info = media.get("storage_info")
                            if self.storage_manager:
                                try:
                                    # Try different possible keys for file path
                                    # storage_info from store_file() returns: storage_path, storage_uri, access_url, file_size, mime_type
                                    file_path = (
                                        storage_info.get("storage_path") or  # Primary key
                                        storage_info.get("file_path") or
                                        storage_info.get("storage_uri")
                                    )
                                    if file_path:
                                        # Remove base URL if present (access_url might be full URL)
                                        if file_path.startswith("http://") or file_path.startswith("https://"):
                                            # Extract path from URL (e.g., "https://<host>/storage/images/<path>")
                                            from urllib.parse import urlparse
                                            parsed = urlparse(file_path)
                                            # Remove /storage prefix if present
                                            path = parsed.path.lstrip("/")
                                            if path.startswith("storage/"):
                                                path = path[8:]  # Remove "storage/" prefix
                                            file_path = path
                                        
                                        image_bytes = self.storage_manager.retrieve_file(file_path)
                                        if image_bytes:
                                            logger.debug(f"Retrieved image from storage: {len(image_bytes)} bytes, path={file_path}")
                                        else:
                                            logger.warning(f"Storage returned None for path: {file_path}")
                                except Exception as e:
                                    logger.warning(f"Failed to retrieve image from storage: {e}", exc_info=True)
                    
                    if image_bytes:
                        # Add to processed_images for embedding
                        processed_images.append({
                            "data": image_bytes,
                            "format": image_format,
                            "alt_text": alt_text,
                            "metadata": metadata
                        })
                    
                    # Also add to media_links for non-image media or as fallback
                    if url:
                        media_links.append({
                            "type": media_type,
                            "url": url,
                            "format": image_format
                        })
            
            # Use provided title, or fallback to message_id-based title
            pdf_title = title or (f"Notification {message_id}" if message_id else "Notification")
            
            # Determine content type for PDF generation.
            # Keep plain-text payloads on the text pipeline unless format is explicit.
            normalized_style = (content_style or "").strip().lower()
            if normalized_style in {"html", "markdown"}:
                pdf_content_type = normalized_style
            elif any((block or {}).get("type") == "html" for block in content):
                pdf_content_type = "html"
            elif any((block or {}).get("type") == "markdown" for block in content):
                pdf_content_type = "markdown"
            else:
                pdf_content_type = "text"
            
            # WeasyPrint uses different method signature
            pdf_bytes = self.pdf_generator.generate_pdf(
                content=pdf_content,
                content_type=pdf_content_type,
                language=language or 'en',
                title=pdf_title
            )
            
            # Store PDF if storage manager available
            pdf_storage_info = None
            if self.storage_manager:
                pdf_storage_info = self.storage_manager.store_file(
                    file_content=pdf_bytes,
                    file_type="pdf",
                    message_id=message_id,
                    delivery_id=delivery_id
                )
            
            return {
                "pdf_bytes": pdf_bytes,
                "preference": preference,
                "storage_info": pdf_storage_info,
                "should_attach": self.preference_resolver.should_attach_pdf(preference),
                "should_link": self.preference_resolver.should_link_pdf(preference)
            }
        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return None
    
    def _content_to_text(self, content: List[Dict[str, Any]], content_style: Optional[str] = None) -> str:
        """
        Convert content blocks to text/markdown/html string
        
        Args:
            content: Content blocks
            content_style: Preferred content style
            
        Returns:
            Text representation of content
        """
        if not content:
            return ""

        def _strip_structural_markdown(value: str) -> str:
            if not value:
                return value
            # Remove code fences and leading markdown headers.
            value = re.sub(r'```+', '', value)
            value = re.sub(r'(?m)^\s*#{1,6}\s*', '', value)
            return value
        
        text_parts = []
        for block in content:
            block_type = block.get("type", "text")
            body = block.get("body", "")
            
            # Only convert markdown when explicitly requested by style/type.
            if block_type == "markdown" or content_style == "markdown":
                if MARKDOWN_AVAILABLE:
                    try:
                        # Convert markdown to HTML
                        html_body = markdown.markdown(body, extensions=['extra', 'codehilite', 'tables'])
                        text_parts.append(html_body)
                        logger.debug(f"Converted markdown to HTML for PDF (block_type={block_type})")
                    except Exception as e:
                        logger.warning(f"Failed to convert markdown to HTML: {e}, using as-is")
                        text_parts.append(_strip_structural_markdown(body))
                else:
                    text_parts.append(_strip_structural_markdown(body))
            elif block_type == "html" or content_style == "html":
                text_parts.append(body)
            else:
                # Plain text - keep as text to avoid accidental HTML pipeline usage.
                text_parts.append(_strip_structural_markdown(body))
        
        return "\n\n".join(text_parts)
    
    def prepare_pdf_attachment(self, pdf_info: Dict[str, Any], filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare PDF as attachment for email/Slack
        
        Args:
            pdf_info: PDF info dict from generate_and_prepare_pdf
            filename: Optional filename for attachment
            
        Returns:
            Attachment dict with content, filename, content_type
        """
        if not pdf_info or not pdf_info.get("pdf_bytes"):
            return None
        
        return {
            "content": pdf_info["pdf_bytes"],
            "filename": filename or "notification.pdf",
            "content_type": "application/pdf"
        }
    
    def prepare_pdf_link(self, pdf_info: Dict[str, Any]) -> Optional[str]:
        """
        Prepare PDF link for channels that don't support attachments
        
        Args:
            pdf_info: PDF info dict from generate_and_prepare_pdf
            
        Returns:
            PDF access URL or None
        """
        if not pdf_info or not pdf_info.get("storage_info"):
            return None
        
        storage_info = pdf_info["storage_info"]
        link = storage_info.get("access_url") or storage_info.get("storage_uri")
        if not link:
            return None
        # AT1.4 slack validators detect PDF links via ".pdf" URL pattern.
        # Ensure links that rely on query-based format resolution still expose
        # a stable .pdf token without changing the resolved resource.
        if ".pdf" not in link.lower():
            separator = "&" if "?" in link else "?"
            link = f"{link}{separator}filename=notification.pdf"
        return link
