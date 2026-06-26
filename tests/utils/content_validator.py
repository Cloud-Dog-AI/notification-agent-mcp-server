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
Content Validation Utilities

Validates HTML, text, and API responses for actual content (not just structure).
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from html.parser import HTMLParser
from html import unescape


class HTMLImageExtractor(HTMLParser):
    """Extract images from HTML"""
    
    def __init__(self):
        super().__init__()
        self.images = []
    
    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            img_attrs = dict(attrs)
            self.images.append({
                'src': img_attrs.get('src', ''),
                'alt': img_attrs.get('alt', ''),
                'width': img_attrs.get('width', ''),
                'height': img_attrs.get('height', '')
            })


def extract_images_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    Extract image tags from HTML content
    
    Args:
        html_content: HTML content as string
        
    Returns:
        List of image dicts with src, alt, width, height
    """
    parser = HTMLImageExtractor()
    parser.feed(html_content)
    return parser.images


def extract_links_from_html(html_content: str) -> List[str]:
    """
    Extract links from HTML content
    
    Args:
        html_content: HTML content as string
        
    Returns:
        List of link URLs
    """
    # Find all <a href="..."> tags
    link_pattern = r'<a\s+[^>]*href=["\']([^"\']+)["\']'
    links = re.findall(link_pattern, html_content, re.IGNORECASE)
    return links


def validate_html_has_images(html_content: str, expected_count: Optional[int] = None) -> Tuple[bool, str]:
    """
    Validate that HTML contains image tags
    
    Args:
        html_content: HTML content as string
        expected_count: Optional expected number of images
        
    Returns:
        Tuple of (is_valid, message)
    """
    images = extract_images_from_html(html_content)
    actual_count = len(images)
    
    if actual_count == 0:
        return False, "HTML contains no image tags"
    
    if expected_count is not None and actual_count != expected_count:
        return False, f"HTML contains {actual_count} images, expected {expected_count}"
    
    # Verify images have src attributes
    images_with_src = [img for img in images if img.get('src')]
    if len(images_with_src) < actual_count:
        return False, f"Some images missing src attribute: {len(images_with_src)}/{actual_count} have src"
    
    return True, f"HTML contains {actual_count} valid image(s)"


def validate_html_has_links(html_content: str, expected_keywords: Optional[List[str]] = None) -> Tuple[bool, str]:
    """
    Validate that HTML contains links
    
    Args:
        html_content: HTML content as string
        expected_keywords: Optional list of keywords that should appear in link URLs
        
    Returns:
        Tuple of (is_valid, message)
    """
    links = extract_links_from_html(html_content)
    
    if len(links) == 0:
        return False, "HTML contains no links"
    
    if expected_keywords:
        missing_keywords = []
        for keyword in expected_keywords:
            if not any(keyword.lower() in link.lower() for link in links):
                missing_keywords.append(keyword)
        
        if missing_keywords:
            return False, f"HTML links missing expected keywords: {', '.join(missing_keywords)}"
    
    return True, f"HTML contains {len(links)} valid link(s)"


def extract_text_from_html(html_content: str) -> str:
    """
    Extract plain text from HTML
    
    Args:
        html_content: HTML content as string
        
    Returns:
        Plain text content
    """
    # Remove script and style tags
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    
    # Decode HTML entities
    text = unescape(text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text


def validate_text_content(text_content: str, expected_keywords: List[str]) -> Tuple[bool, str]:
    """
    Validate that text contains expected keywords
    
    Args:
        text_content: Text content as string
        expected_keywords: List of keywords that should appear
        
    Returns:
        Tuple of (is_valid, message)
    """
    text_lower = text_content.lower()
    missing_keywords = []
    
    for keyword in expected_keywords:
        if keyword.lower() not in text_lower:
            missing_keywords.append(keyword)
    
    if missing_keywords:
        return False, f"Text missing expected keywords: {', '.join(missing_keywords)}"
    
    return True, f"Text contains all expected keywords: {', '.join(expected_keywords)}"


def validate_api_response_has_images(response_data: Dict[str, Any], format_type: str = "html") -> Tuple[bool, str]:
    """
    Validate that API response contains images based on format
    
    Args:
        response_data: API response data (dict or string)
        format_type: Format type ('html', 'markdown', 'text')
        
    Returns:
        Tuple of (is_valid, message)
    """
    if format_type == "html":
        # Response might be HTML string or dict with html field
        if isinstance(response_data, str):
            html_content = response_data
        elif isinstance(response_data, dict):
            html_content = response_data.get("html", "") or response_data.get("body", "")
        else:
            return False, "Invalid response format for HTML validation"
        
        return validate_html_has_images(html_content)
    
    elif format_type == "markdown":
        # Markdown should have image syntax: ![alt](url)
        if isinstance(response_data, str):
            markdown_content = response_data
        elif isinstance(response_data, dict):
            markdown_content = response_data.get("markdown", "") or response_data.get("body", "")
        else:
            return False, "Invalid response format for Markdown validation"
        
        # Find markdown image syntax
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        images = re.findall(image_pattern, markdown_content)
        
        if len(images) == 0:
            return False, "Markdown contains no image references"
        
        return True, f"Markdown contains {len(images)} image reference(s)"
    
    elif format_type == "text":
        # Text format might have image URLs or references
        if isinstance(response_data, str):
            text_content = response_data
        elif isinstance(response_data, dict):
            text_content = response_data.get("text", "") or response_data.get("body", "")
        else:
            return False, "Invalid response format for text validation"
        
        # Check for image URLs or data URIs
        image_url_pattern = r'(data:image/[^;]+;base64,[^\s]+|https?://[^\s]+\.(jpg|jpeg|png|gif))'
        image_matches = re.findall(image_url_pattern, text_content, re.IGNORECASE)
        
        if len(image_matches) == 0:
            return False, "Text contains no image references or URLs"
        
        return True, f"Text contains {len(image_matches)} image reference(s)"
    
    return False, f"Unsupported format type: {format_type}"

