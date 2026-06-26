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
Description: HTML Page Generator for Notification Agent MCP Server - Generates personalized HTML pages with embedded multimedia content

Related Requirements: FR1.22
Related Tasks: T32
Related Architecture: CC5.3.5
Related Tests: IT1.21, AT1.24

Recent Changes (max 10):
- (Initial header added)
- 2025-12-03: Implemented HTML page generation with embedded media.

**************************************************
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from ...utils.logger import get_logger

logger = get_logger(__name__)


class HTMLPageGenerator:
    """
    Generates personalized HTML pages with embedded multimedia content
    """
    
    def __init__(self):
        """Initialize HTML page generator"""
        logger.info("HTMLPageGenerator initialized")
    
    def generate_page(
        self,
        content: List[Dict[str, Any]],
        user_name: Optional[str] = None,
        message_title: Optional[str] = None,
        processed_media: Optional[List[Dict[str, Any]]] = None,
        language: Optional[str] = None,
        stylesheet_url: Optional[str] = None,
    ) -> str:
        """
        Generate personalized HTML page with embedded media
        
        Args:
            content: List of content blocks (text, markdown, html)
            user_name: User's name for personalization
            message_title: Message title
            processed_media: List of processed media dicts (from MediaProcessor)
            language: Language code for HTML lang attribute
            stylesheet_url: Optional URL to external stylesheet
            
        Returns:
            Complete HTML page as string
        """
        html_parts = []
        
        # HTML header
        html_parts.append("<!DOCTYPE html>")
        html_parts.append(f'<html lang="{language or "en"}">')
        html_parts.append("<head>")
        html_parts.append('<meta charset="UTF-8">')
        html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        
        if message_title:
            html_parts.append(f'<title>{self._escape_html(message_title)}</title>')
        else:
            html_parts.append("<title>Notification</title>")
        
        # Add stylesheet if provided
        if stylesheet_url:
            html_parts.append(f'<link rel="stylesheet" href="{self._escape_html(stylesheet_url)}">')
        else:
            # Default inline styles
            html_parts.append("<style>")
            html_parts.append(self._get_default_styles())
            html_parts.append("</style>")
        
        html_parts.append("</head>")
        html_parts.append("<body>")
        
        # Page container
        html_parts.append('<div class="notification-page">')
        
        # Header with personalization
        if user_name:
            html_parts.append(f'<div class="header"><h1>Hello, {self._escape_html(user_name)}!</h1></div>')
        elif message_title:
            html_parts.append(f'<div class="header"><h1>{self._escape_html(message_title)}</h1></div>')
        
        # Content blocks
        html_parts.append('<div class="content">')
        for block in content:
            block_type = block.get("type", "text")
            body = block.get("body", "")
            
            if block_type == "html":
                html_parts.append(body)
            elif block_type == "markdown":
                # Convert markdown to HTML (simplified - would use markdown library in production)
                html_parts.append(f'<div class="markdown-content">{self._markdown_to_html(body)}</div>')
            else:
                # Plain text
                html_parts.append(f'<div class="text-content"><p>{self._escape_html(body)}</p></div>')
        
        html_parts.append("</div>")
        
        # Media section
        if processed_media:
            html_parts.append('<div class="media-section">')
            html_parts.append("<h2>Media Files</h2>")
            
            for media in processed_media:
                media_type = media.get("type")
                url = media.get("url") or media.get("original_uri")
                format = media.get("format", "")
                metadata = media.get("metadata", {})
                
                if not url:
                    continue
                
                if media_type == "image":
                    # Embed image - support both data URIs and regular URLs
                    # Get alt_text from metadata or original block
                    alt_text = metadata.get("alt") or media.get("alt_text") or f"Image ({format})"
                    width = metadata.get("width")
                    height = metadata.get("height")
                    width_attr = f' width="{width}"' if width else ""
                    height_attr = f' height="{height}"' if height else ""
                    html_parts.append('<div class="media-item image">')
                    # Data URIs can be used directly in img src
                    html_parts.append(f'<img src="{self._escape_html(url)}" alt="{self._escape_html(alt_text)}"{width_attr}{height_attr}>')
                    html_parts.append("</div>")
                
                elif media_type == "audio":
                    # Embed audio player
                    duration = metadata.get("duration")
                    duration_str = f" ({duration:.1f}s)" if duration else ""
                    html_parts.append('<div class="media-item audio">')
                    html_parts.append(f'<p><strong>Audio</strong> ({format}{duration_str})</p>')
                    html_parts.append(f'<audio controls><source src="{self._escape_html(url)}" type="audio/{format}">')
                    html_parts.append('Your browser does not support the audio element.</audio>')
                    html_parts.append("</div>")
                
                elif media_type == "video":
                    # Embed video player
                    duration = metadata.get("duration")
                    width = metadata.get("width")
                    height = metadata.get("height")
                    info_parts = []
                    if duration:
                        info_parts.append(f"{duration:.1f}s")
                    if width and height:
                        info_parts.append(f"{width}x{height}")
                    info_str = f" ({', '.join(info_parts)})" if info_parts else ""
                    html_parts.append('<div class="media-item video">')
                    html_parts.append(f'<p><strong>Video</strong> ({format}{info_str})</p>')
                    html_parts.append(f'<video controls width="{width or 640}" height="{height or 360}">')
                    html_parts.append(f'<source src="{self._escape_html(url)}" type="video/{format}">')
                    html_parts.append('Your browser does not support the video element.</video>')
                    html_parts.append("</div>")
                
                else:
                    # Generic media link
                    html_parts.append('<div class="media-item generic">')
                    html_parts.append(f'<p><a href="{self._escape_html(url)}">{media_type.title()} ({format})</a></p>')
                    html_parts.append("</div>")
            
            html_parts.append("</div>")
        
        # Footer
        html_parts.append('<div class="footer">')
        html_parts.append(f'<p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')
        html_parts.append("</div>")
        
        html_parts.append("</div>")  # Close notification-page
        html_parts.append("</body>")
        html_parts.append("</html>")
        
        html_content = "\n".join(html_parts)
        logger.debug(f"Generated HTML page: {len(html_content)} characters")
        return html_content
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        if not isinstance(text, str):
            text = str(text)
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert markdown to HTML (simplified version)
        In production, would use a proper markdown library
        """
        # Very basic markdown conversion
        html = markdown_text
        # Headers
        html = html.replace("\n# ", "\n<h1>").replace("\n## ", "\n<h2>")
        html = html.replace("\n### ", "\n<h3>")
        # Bold
        html = html.replace("**", "<strong>").replace("**", "</strong>")
        # Italic
        html = html.replace("*", "<em>").replace("*", "</em>")
        # Links (basic)
        import re
        html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
        # Line breaks
        html = html.replace("\n\n", "</p><p>")
        html = f"<p>{html}</p>"
        return html
    
    def _get_default_styles(self) -> str:
        """Get default CSS styles for HTML page"""
        return """
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #333;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
    background-color: #f5f5f5;
}
.notification-page {
    background-color: white;
    padding: 30px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.header {
    border-bottom: 2px solid #0056b3;
    padding-bottom: 10px;
    margin-bottom: 20px;
}
.header h1 {
    color: #0056b3;
    margin: 0;
}
.content {
    margin-bottom: 30px;
}
.text-content, .markdown-content {
    margin-bottom: 15px;
}
.media-section {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
}
.media-section h2 {
    color: #0056b3;
    margin-bottom: 15px;
}
.media-item {
    margin-bottom: 20px;
    padding: 15px;
    background-color: #f9f9f9;
    border-radius: 4px;
}
.media-item img {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
}
.media-item audio, .media-item video {
    width: 100%;
    margin-top: 10px;
}
.footer {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    text-align: center;
    color: #777;
    font-size: 0.9em;
}
"""
