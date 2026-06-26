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
Description: File Storage Adapter - Saves notification content to file storage backends

Related Requirements: FR1.20
Related Tasks: T31
Related Architecture: CC5.1.5, CC6.1.3
Related Tests: AT1.4g, AT1.25

Recent Changes (max 10):
- Updated to use new FileChannelAdapter with multi-backend support (2025-12-21)
- (Initial implementation)
**************************************************
"""

import json
from src.utils.logger import get_logger
from typing import Dict, Any

from .base import BaseChannelAdapter, SendResult, ConfirmResult, ErrorClass
from ..core.adapters.file_channel_adapter import FileChannelAdapter

logger = get_logger(__name__)


class FileAdapter(BaseChannelAdapter):
    """
    File storage adapter - saves notifications to file storage backends.
    
    Wraps the FileChannelAdapter to work with the adapter registry system.
    Supports multiple storage backends: filesystem, WebDAV, S3, FTP.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize file adapter.
        
        Args:
            config: Channel configuration dict with:
                - storage_type: Backend type (filesystem, webdav, s3, ftp)
                - Backend-specific config (base_path, url, endpoint, etc.)
                - file_name_pattern: Filename pattern (optional)
        """
        super().__init__(config)
        self.config = config
        
        # Create file channel adapter
        try:
            self.file_channel = FileChannelAdapter(config)
            logger.info(f"FileAdapter initialized with {config.get('storage_type', 'unknown')} backend")
        except Exception as e:
            logger.error(f"Failed to initialize FileAdapter: {e}")
            raise
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """
        Save notification to file storage.
        
        Args:
            delivery: Delivery dict with:
                - destination: User identifier
                - personalised_payload: Translated content (markdown or JSON)
                - metadata_json: Metadata including language, format preferences
        
        Returns:
            SendResult with success status and stored file information
        """
        try:
            # Parse delivery payload
            payload_str = delivery.get("personalised_payload", "")
            metadata_str = delivery.get("metadata_json", "{}")
            message_id = str(delivery.get("message_id", "unknown"))
            
            # Parse metadata
            if isinstance(metadata_str, str):
                metadata = json.loads(metadata_str) if metadata_str else {}
            else:
                metadata = metadata_str or {}
            
            # Extract content from payload
            if isinstance(payload_str, str):
                try:
                    payload = json.loads(payload_str)
                    # If payload is a list of content blocks, extract body
                    if isinstance(payload, list):
                        content = "\n\n".join(
                            block.get("body", "") for block in payload 
                            if isinstance(block, dict) and block.get("body")
                        )
                    elif isinstance(payload, dict):
                        content = payload.get("body", payload_str)
                    else:
                        # payload is a plain string (happens when formatted_content was json.dumps'ed as a string)
                        content = payload  # Use the parsed payload, not payload_str!
                except json.JSONDecodeError:
                    # Not JSON, treat as raw content
                    content = payload_str
            else:
                content = str(payload_str)

            # ---------------------------------------------------------------------
            # UC1.8 / FR1.20: Ensure stored outputs preserve multimedia references.
            #
            # The file adapter receives `processed_media` in delivery metadata (produced by the
            # delivery worker media processor). The formatted payload may omit rich media, so
            # append a deterministic media section (markdown + raw HTML) before handing off to
            # FileChannelAdapter. This ensures:
            # - Markdown output contains image/video references
            # - HTML output contains <img>/<video> tags (FileChannelAdapter wraps raw HTML)
            # - PDF generation (WeasyPrint) embeds images when data URIs are used
            # ---------------------------------------------------------------------
            processed_media = metadata.get("processed_media") if isinstance(metadata, dict) else None

            def _media_url(item: Dict[str, Any]) -> str:
                url = item.get("url") or item.get("original_uri") or ""
                if not isinstance(url, str):
                    return ""
                url = url.strip()
                if url.startswith(("http://", "https://", "data:")):
                    return url
                return ""

            def _media_alt(item: Dict[str, Any]) -> str:
                alt = item.get("alt_text") or ""
                if not isinstance(alt, str):
                    alt = ""
                alt = alt.strip()
                if alt:
                    return alt
                return str(item.get("type") or "media")

            if isinstance(processed_media, list) and processed_media:
                media_lines: list[str] = []
                for item in processed_media:
                    if not isinstance(item, dict):
                        continue
                    mtype = str(item.get("type") or "").lower()
                    url = _media_url(item)
                    if not url:
                        continue
                    alt = _media_alt(item)

                    if mtype == "image":
                        # Raw HTML + markdown image syntax.
                        media_lines.append(f'<img src="{url}" alt="{alt}">')
                        media_lines.append(f"![{alt}]({url})")
                    elif mtype == "video":
                        media_lines.append(f'<video controls src="{url}"></video>')
                        media_lines.append(f"Video: {url}")
                    elif mtype == "audio":
                        media_lines.append(f'<audio controls src="{url}"></audio>')
                        media_lines.append(f"Audio: {url}")

                if media_lines:
                    # Append without mutating the main body structure too much.
                    content = (content or "").rstrip() + "\n\n---\nEmbedded media\n\n" + "\n\n".join(media_lines) + "\n"
            
            # Get preferences from metadata (preferences are nested under "preferences" key)
            prefs = metadata.get("preferences", {})
            
            # Get language from preferences
            language = prefs.get("language", "en")
            
            # Get format preferences
            user_preferences = {
                "output_formats": prefs.get("output_formats", []),
                "generate_pdf": prefs.get("generate_pdf", False)
            }
            
            logger.info(
                "Delivering to file storage",
                extra={
                    "message_id": message_id,
                    "language": language,
                    "storage_type": self.config.get("storage_type", "unknown"),
                    "output_formats": list(user_preferences.get("output_formats", [])),
                    "generate_pdf": bool(user_preferences.get("generate_pdf", False)),
                    "content_length": len(content or ""),
                    "processed_media_count": len(processed_media) if isinstance(processed_media, list) else 0,
                },
            )
            
            # Deliver using file channel adapter
            result = await self.file_channel.deliver(
                message_id=message_id,
                content=content,
                language=language,
                user_preferences=user_preferences
            )
            
            if result["success"]:
                # Store file info as tracking_id (JSON string)
                stored_files_json = json.dumps(result["stored_files"])
                
                return SendResult(
                    success=True,
                    tracking_id=stored_files_json,
                    error=None,
                    error_class=None
                )
            else:
                error_msg = result.get("error_message", "File delivery failed")
                logger.error(f"File delivery failed: {error_msg}")
                
                return SendResult(
                    success=False,
                    tracking_id=None,
                    error=error_msg,
                    error_class=ErrorClass.TRANSIENT
                )
                
        except Exception as e:
            logger.error(f"File adapter send failed: {e}", exc_info=True)
            return SendResult(
                success=False,
                tracking_id=None,
                error=f"File delivery error: {str(e)}",
                error_class=ErrorClass.TRANSIENT
            )
    
    async def confirm(self, delivery: Dict[str, Any]) -> ConfirmResult:
        """
        Confirm file delivery (not applicable for file storage).
        
        Returns:
            ConfirmResult indicating confirmation not needed
        """
        return ConfirmResult(
            requires_confirmation=False,
            is_confirmed=True
        )
    
    async def close(self):
        """Close file channel adapter connections"""
        if hasattr(self, 'file_channel'):
            await self.file_channel.close()
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate file storage destination.
        
        For file channels, the destination is typically "storage" or a path.
        Always returns True as file storage doesn't require validation.
        """
        return True
    
    def parse_callback(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse callback webhook (not applicable for file storage).
        
        File storage doesn't use webhooks, so this returns empty data.
        """
        return {}
    
    def classify_error(self, error: Exception) -> ErrorClass:
        """
        Classify file storage errors.
        
        Most file storage errors are transient (disk space, permissions, network).
        Permanent errors are rare (invalid configuration).
        """
        error_message = str(error).lower()
        
        # Permanent errors
        if any(x in error_message for x in [
            "invalid configuration",
            "bucket does not exist",
            "authentication failed",
            "access denied permanently",
            "invalid credentials"
        ]):
            return ErrorClass.PERMANENT
        
        # Everything else is transient (disk space, network, temporary permissions)
        return ErrorClass.TRANSIENT
