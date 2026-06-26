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
Description: HTML Page Generator for Notification Agent MCP Server - Generates complete HTML pages with embedded multimedia for personalized content

Related Requirements: FR1.22
Related Tasks: T32
Related Architecture: CC5.3.5
Related Tests: UT1.18, ST1.9, IT1.22, AT1.24

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented HTML page generation with embedded media.

**************************************************
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import html

from src.utils.logger import get_logger

logger = get_logger(__name__)


class HTMLPageGenerator:
    """
    Generates complete HTML pages with embedded multimedia content.
    Supports personalized content, embedded images, audio, and video.
    """
    
    def __init__(self):
        """Initialize HTML page generator"""
        logger.info("HTMLPageGenerator initialized")
    
    def generate_page(
        self,
        content: str,
        title: Optional[str] = None,
        language: Optional[str] = None,
        embedded_media: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate complete HTML page
        
        Args:
            content: Main content (text, markdown converted to HTML, or HTML)
            title: Page title
            language: Language code (e.g., 'en', 'fr', 'de')
            embedded_media: List of media dicts with 'type', 'url', 'format', 'metadata'
            metadata: Optional page metadata
            
        Returns:
            Complete HTML page as string
        """
        lang_attr = f' lang="{language}"' if language else ''
        
        html_parts = [
            '<!DOCTYPE html>',
            f'<html{lang_attr}>',
            '<head>',
            '<meta charset="UTF-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        ]
        
        # Title
        page_title = title or "Notification"
        html_parts.append(f'<title>{html.escape(page_title)}</title>')
        
        # Basic styles
        html_parts.append('<style>')
        html_parts.append('''
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            h1 { color: #0056b3; }
            h2 { color: #0056b3; margin-top: 30px; }
            img { max-width: 100%; height: auto; }
            audio, video { max-width: 100%; }
        ''')
        html_parts.append('</style>')
        html_parts.append('</head>')
        html_parts.append('<body>')
        
        # Main title
        html_parts.append(f'<h1>{html.escape(page_title)}</h1>')
        
        # Main content
        html_parts.append('<div class="content">')
        # Content is already HTML or will be treated as HTML
        html_parts.append(content)
        html_parts.append('</div>')
        
        # Embedded media
        if embedded_media:
            html_parts.append('<div class="media">')
            for media in embedded_media:
                media_html = self._embed_media(media)
                if media_html:
                    html_parts.append(media_html)
            html_parts.append('</div>')
        
        # Footer
        html_parts.append('<footer>')
        html_parts.append(f'<p><small>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</small></p>')
        html_parts.append('</footer>')
        
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)
    
    def _embed_media(self, media: Dict[str, Any]) -> Optional[str]:
        """
        Generate HTML for embedded media
        
        Args:
            media: Media dict with 'type', 'url', 'format', 'metadata'
            
        Returns:
            HTML string for media element or None
        """
        media_type = media.get("type")  # 'image', 'audio', 'video'
        url = media.get("url", "")
        format = media.get("format", "")
        metadata = media.get("metadata", {})
        
        if not url:
            return None
        
        escaped_url = html.escape(url)
        
        if media_type == "image":
            alt_text = metadata.get("alt", "Image")
            width = metadata.get("width")
            height = metadata.get("height")
            width_attr = f' width="{width}"' if width else ''
            height_attr = f' height="{height}"' if height else ''
            return f'<img src="{escaped_url}" alt="{html.escape(alt_text)}"{width_attr}{height_attr}>'
        
        elif media_type == "audio":
            controls = 'controls'
            preload = 'preload="metadata"'
            duration = metadata.get("duration")
            duration_text = f' ({duration:.1f}s)' if duration else ''
            return f'<audio {controls} {preload}><source src="{escaped_url}" type="audio/{format}">Your browser does not support the audio element.</audio><p><small>Audio file{duration_text}</small></p>'
        
        elif media_type == "video":
            controls = 'controls'
            preload = 'preload="metadata"'
            width = metadata.get("width")
            height = metadata.get("height")
            width_attr = f' width="{width}"' if width else ''
            height_attr = f' height="{height}"' if height else ''
            duration = metadata.get("duration")
            duration_text = f' ({duration:.1f}s)' if duration else ''
            return f'<video {controls} {preload}{width_attr}{height_attr}><source src="{escaped_url}" type="video/{format}">Your browser does not support the video element.</video><p><small>Video file{duration_text}</small></p>'
        
        return None
