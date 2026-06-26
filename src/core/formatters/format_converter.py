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
Description: Generic Format Converter - Converts content between different formats using LLM (PDF→HTML, DOC→text, Markdown→HTML, Markdown→text, etc.)

Related Requirements: FR1.10, FR1.11
Related Tasks: T8
Related Architecture: CC3.1
Related Tests: ST1.3

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from typing import Optional, Dict, Any

from src.core.llm.runtime_client import LLMManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FormatConverter:
    """Generic format converter using LLM"""
    
    # Supported format conversions
    SUPPORTED_CONVERSIONS = {
        'pdf': ['html', 'text', 'markdown'],
        'doc': ['text', 'html', 'markdown'],
        'docx': ['text', 'html', 'markdown'],
        'markdown': ['html', 'text', 'pdf'],
        'html': ['text', 'markdown'],
        'text': ['html', 'markdown'],
    }
    
    def __init__(self, llm_manager: LLMManager):
        """
        Initialize format converter
        
        Args:
            llm_manager: LLMManager instance
        """
        self.llm_manager = llm_manager
    
    def convert(
        self,
        content: str,
        source_format: str,
        target_format: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Convert content from source format to target format
        
        Args:
            content: Content to convert
            source_format: Source format (pdf, doc, markdown, html, text)
            target_format: Target format (html, text, markdown)
            options: Optional conversion options (preserve_structure, include_metadata, etc.)
            
        Returns:
            Converted content
        """
        source_format = source_format.lower()
        target_format = target_format.lower()
        
        # Check if conversion is supported
        if source_format not in self.SUPPORTED_CONVERSIONS:
            logger.warning(f"Unsupported source format: {source_format}, using text")
            source_format = 'text'
        
        if target_format not in self.SUPPORTED_CONVERSIONS.get(source_format, []):
            logger.warning(f"Unsupported conversion: {source_format}→{target_format}, using text")
            target_format = 'text'
        
        # Build conversion prompt
        prompt = self._build_conversion_prompt(
            content=content,
            source_format=source_format,
            target_format=target_format,
            options=options or {},
        )
        
        try:
            logger.info(f"⏳ Waiting for LLM to convert {source_format}→{target_format}...")
            converted = self.llm_manager.invoke(prompt, timeout=300)
            logger.info(f"✅ LLM conversion completed: {source_format}→{target_format}")
            return converted.strip()
        except Exception as e:
            logger.warning(f"⚠️ Format conversion failed: {e}, using fallback")
            return self._convert_fallback(content, source_format, target_format)
    
    def _build_conversion_prompt(
        self,
        content: str,
        source_format: str,
        target_format: str,
        options: Dict[str, Any],
    ) -> str:
        """Build LLM prompt for format conversion"""
        
        format_instructions = {
            'html': 'Convert to well-formed HTML with proper structure, semantic tags (<h1>, <h2>, <p>, <ul>, <li>, etc.), and clean formatting.',
            'text': 'Convert to plain text with preserved structure. Use underlines for headers, bullets (•) for lists, and proper indentation.',
            'markdown': 'Convert to Markdown format with proper syntax (headers, lists, links, etc.).',
        }
        
        target_instruction = format_instructions.get(target_format, f'Convert to {target_format} format.')
        
        preserve_structure = options.get('preserve_structure', True)
        include_metadata = options.get('include_metadata', False)
        
        prompt = f"""Convert the following {source_format.upper()} content to {target_format.upper()} format.

{target_instruction}

"""
        
        if preserve_structure:
            prompt += "IMPORTANT: Preserve the original structure, hierarchy, and formatting as much as possible.\n\n"
        
        if include_metadata:
            prompt += "Include any metadata, headers, footers, or document properties if present.\n\n"
        
        prompt += f"""Source content ({source_format.upper()}):
{content}

Converted content ({target_format.upper()}):"""
        
        return prompt
    
    def _convert_fallback(
        self,
        content: str,
        source_format: str,
        target_format: str,
    ) -> str:
        """Fallback conversion when LLM is unavailable"""
        # Basic fallback conversions
        if source_format == 'markdown' and target_format == 'html':
            # Use existing markdown_to_html logic
            # Create a temporary formatter just for the conversion method
            # This is a workaround - ideally we'd extract the conversion logic
            import re
            # Basic markdown to HTML conversion
            text = content
            text = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
            text = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
            text = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
            return text
        
        elif source_format == 'markdown' and target_format == 'text':
            # Use existing markdown_to_text logic
            # Similar workaround
            import re
            text = content
            # Remove markdown headers (keep text)
            text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
            # Remove bold/italic markers
            text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
            text = re.sub(r'\*(.+?)\*', r'\1', text)
            # Convert links to text
            text = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', text)
            return text
        
        # Default: return as-is
        return content
