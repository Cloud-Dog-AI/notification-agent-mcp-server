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
Description: PDF Generator for Notification Agent MCP Server - Converts text, Markdown, and HTML content to PDF format with stylesheet support

Related Requirements: FR1.18
Related Tasks: T29
Related Architecture: CC5.2
Related Tests: UT1.14, ST1.5, IT1.17, AT1.19

Recent Changes (max 10):
- (Initial implementation)

**************************************************
"""

import io
import platform
from typing import Optional, Dict, Any, List
from pathlib import Path
import re

from cloud_dog_storage.backends.local import LocalStorage as _PlatformLocalStorage

_fs = _PlatformLocalStorage(root_path="/")

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    from html.parser import HTMLParser
    HTML_PARSER_AVAILABLE = True
except ImportError:
    HTML_PARSER_AVAILABLE = False

from src.utils.logger import get_logger

logger = get_logger(__name__)


class HTMLToPDFParser(HTMLParser):
    """Simple HTML parser to extract text and basic formatting for PDF"""
    
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.current_tag = None
        self.current_attrs = {}
    
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        self.current_attrs = dict(attrs)
    
    def handle_endtag(self, tag):
        if tag in ['p', 'div', 'br']:
            self.text_parts.append('\n')
        self.current_tag = None
        self.current_attrs = {}
    
    def handle_data(self, data):
        self.text_parts.append(data)
    
    def get_text(self):
        return ''.join(self.text_parts)


class PDFGenerator:
    """Generates PDF documents from text, Markdown, or HTML content"""
    
    def __init__(self, stylesheet_path: Optional[str] = None):
        """
        Initialize PDF generator
        
        Args:
            stylesheet_path: Optional path to CSS stylesheet file
        """
        if not REPORTLAB_AVAILABLE:
            raise ImportError("reportlab is required for PDF generation. Install with: pip install reportlab")
        
        self.stylesheet_path = stylesheet_path
        self.styles = getSampleStyleSheet()
        self._register_fonts()
        self._setup_custom_styles()
        logger.info("PDFGenerator initialized")
    
    def _register_fonts(self):
        """Register fonts that support Unicode characters (including Arabic, Chinese, Japanese, Korean)"""
        try:
            # Register multiple fonts for comprehensive language support:
            # 1. NotoSansArabic for Arabic
            # 2. DroidSansFallbackFull for CJK (Chinese, Japanese, Korean)
            # 3. NotoSans for Latin/European languages
            system = platform.system()
            
            # Try common font paths
            font_paths = []
            if system == "Linux":
                # CRITICAL: Use .ttf files, NOT .ttc (ReportLab doesn't support .ttc)
                # DroidSansFallbackFull has excellent CJK support and reasonable coverage for other scripts
                # Note: Arabic rendering may need additional fonts, but CJK takes priority
                font_paths = [
                    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # PRIMARY - Best multi-script support
                    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                ]
            elif system == "Darwin":  # macOS
                font_paths = [
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                    "/Library/Fonts/Arial Unicode.ttf",
                ]
            elif system == "Windows":
                font_paths = [
                    "C:/Windows/Fonts/msyh.ttf",  # Microsoft YaHei (Chinese)
                    "C:/Windows/Fonts/simsun.ttc",  # SimSun (Chinese)
                    "C:/Windows/Fonts/arial.ttf",  # Arial (fallback)
                ]
            
            # Try to register a Unicode-supporting font
            font_registered = False
            for font_path in font_paths:
                if _fs.exists(font_path):
                    try:
                        # Register as 'UnicodeFont' for use in styles
                        pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
                        logger.info(f"Registered Unicode font: {font_path}")
                        font_registered = True
                        self.unicode_font_name = 'UnicodeFont'
                        break
                    except Exception as e:
                        logger.debug(f"Failed to register font {font_path}: {e}")
                        continue
            
            # If no system font found, ReportLab will use default fonts
            # For Chinese characters, we'll need to handle encoding issues
            if not font_registered:
                logger.warning("No Unicode-supporting font found. Chinese characters may not render correctly.")
                logger.warning("Consider installing Noto Sans CJK or similar font for full Unicode support.")
                self.unicode_font_name = None
        except Exception as e:
            logger.warning(f"Error registering fonts: {e}")
            self.unicode_font_name = None
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # CRITICAL: Use Unicode font if available, otherwise use default
        # For CJK (Chinese, Japanese, Korean), we MUST use the Unicode font
        body_font = self.unicode_font_name if self.unicode_font_name else 'Helvetica'
        heading_font = self.unicode_font_name if self.unicode_font_name else 'Helvetica'  # CJK doesn't have bold variant
        
        # Heading styles
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            textColor='#000000',
            fontName=heading_font
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            textColor='#333333',
            fontName=heading_font
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            spaceAfter=6,
            leading=14,
            textColor='#000000',
            fontName=body_font
        ))
        
        # RTL Body text style for Arabic/Hebrew
        self.styles.add(ParagraphStyle(
            name='CustomBodyRTL',
            parent=self.styles['BodyText'],
            fontSize=11,
            spaceAfter=6,
            leading=14,
            textColor='#000000',
            fontName=body_font,
            alignment=TA_RIGHT,  # Right-align for RTL
            wordWrap='RTL'  # Right-to-left text flow
        ))
        
        # RTL Heading styles for Arabic/Hebrew
        self.styles.add(ParagraphStyle(
            name='CustomHeading1RTL',
            parent=self.styles['Heading1'],
            fontSize=18,
            spaceAfter=12,
            textColor='#000000',
            fontName=heading_font,
            alignment=TA_RIGHT
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2RTL',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            textColor='#333333',
            fontName=heading_font,
            alignment=TA_RIGHT
        ))
        
        # Code style (keep Courier for code)
        self.styles.add(ParagraphStyle(
            name='CustomCode',
            parent=self.styles['Code'],
            fontSize=9,
            fontName='Courier',
            backColor='#f5f5f5',
            borderColor='#cccccc',
            borderWidth=1,
            borderPadding=5
        ))
    
    def _apply_stylesheet(self, content: str) -> str:
        """
        Apply CSS stylesheet to content (basic implementation)
        
        Args:
            content: HTML content
            
        Returns:
            Styled HTML content
        """
        if not self.stylesheet_path or not _fs.exists(self.stylesheet_path):
            return content
        
        # For now, return content as-is
        # Full CSS parsing would require additional libraries (cssutils, etc.)
        # This is a placeholder for Phase 2.2 (Stylesheet Management)
        logger.debug(f"Stylesheet path provided: {self.stylesheet_path}, but full CSS parsing not yet implemented")
        return content
    
    def _markdown_to_html(self, markdown_content: str) -> str:
        """
        Convert Markdown to HTML
        
        Args:
            markdown_content: Markdown formatted text
            
        Returns:
            HTML formatted text
        """
        if not MARKDOWN_AVAILABLE:
            logger.warning("markdown library not available, treating as plain text")
            return markdown_content
        
        try:
            html = markdown.markdown(
                markdown_content,
                extensions=['extra', 'codehilite', 'tables']
            )
            return html
        except Exception as e:
            logger.error(f"Error converting Markdown to HTML: {e}")
            return markdown_content
    
    def _html_to_text(self, html_content: str) -> str:
        """
        Convert HTML to plain text for PDF generation
        
        Args:
            html_content: HTML formatted text
            
        Returns:
            Plain text with basic formatting preserved
        """
        parser = HTMLToPDFParser()
        parser.feed(html_content)
        text = parser.get_text()
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()
    
    def _is_rtl_language(self, text: str) -> bool:
        """
        Detect if text contains RTL (Right-to-Left) characters (Arabic, Hebrew, etc.)
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains significant RTL characters
        """
        if not text:
            return False
        
        # Count Arabic and Hebrew characters
        # Arabic: U+0600 to U+06FF, U+0750 to U+077F, U+08A0 to U+08FF, U+FB50 to U+FDFF, U+FE70 to U+FEFF
        # Hebrew: U+0590 to U+05FF
        rtl_count = 0
        total_chars = 0
        
        for char in text:
            code_point = ord(char)
            # Check if it's a letter or digit (ignore whitespace/punctuation)
            if char.isalnum() or code_point > 127:
                total_chars += 1
                # Check for Arabic/Hebrew ranges
                if (0x0600 <= code_point <= 0x06FF or  # Arabic
                    0x0750 <= code_point <= 0x077F or  # Arabic Supplement
                    0x08A0 <= code_point <= 0x08FF or  # Arabic Extended-A
                    0xFB50 <= code_point <= 0xFDFF or  # Arabic Presentation Forms-A
                    0xFE70 <= code_point <= 0xFEFF or  # Arabic Presentation Forms-B
                    0x0590 <= code_point <= 0x05FF):   # Hebrew
                    rtl_count += 1
        
        # If more than 30% of characters are RTL, consider it RTL text
        if total_chars > 0 and rtl_count / total_chars > 0.3:
            logger.info(f"Detected RTL text: {rtl_count}/{total_chars} RTL chars ({100*rtl_count/total_chars:.1f}%)")
            return True
        
        return False
    
    def _text_to_elements(self, text: str) -> List:
        """
        Convert plain text to ReportLab flowable elements with better formatting
        
        Args:
            text: Plain text content
            
        Returns:
            List of ReportLab flowable elements
        """
        
        # Detect if text is RTL (Arabic/Hebrew)
        is_rtl = self._is_rtl_language(text)
        if is_rtl:
            logger.info("Using RTL formatting for PDF content")
        
        # Select appropriate styles based on text direction
        body_style = self.styles['CustomBodyRTL'] if is_rtl else self.styles['CustomBody']
        heading1_style = self.styles['CustomHeading1RTL'] if is_rtl else self.styles['CustomHeading1']
        heading2_style = self.styles['CustomHeading2RTL'] if is_rtl else self.styles['CustomHeading2']
        
        elements = []
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()  # Keep left spacing for bullets
            
            # Empty line = paragraph break
            if not line.strip():
                elements.append(Spacer(1, 0.2 * inch))
                i += 1
                continue
            
            # Detect headings (lines starting with #)
            stripped = line.strip()
            if stripped.startswith('# '):
                heading_text = stripped[2:]
                try:
                    # Escape HTML chars but preserve Unicode
                    safe_text = heading_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    elements.append(Paragraph(safe_text, heading1_style))
                    elements.append(Spacer(1, 0.15 * inch))
                except Exception as e:
                    logger.error(f"Failed to create heading: {e}, text: {heading_text[:50]}")
                i += 1
                continue
            elif stripped.startswith('## '):
                heading_text = stripped[3:]
                try:
                    safe_text = heading_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    elements.append(Paragraph(safe_text, heading2_style))
                    elements.append(Spacer(1, 0.1 * inch))
                except Exception as e:
                    logger.error(f"Failed to create heading: {e}, text: {heading_text[:50]}")
                i += 1
                continue
            
            # Detect numbered lists (1. 2. 3.)
            elif re.match(r'^\d+[\.\)]\s', stripped):
                # Collect all consecutive numbered items
                numbered_items = []
                while i < len(lines):
                    numbered_line = lines[i].strip()
                    match = re.match(r'^(\d+)[\.\)]\s+(.+)', numbered_line)
                    if match:
                        item_number = match.group(1)
                        item_text = match.group(2)
                        numbered_items.append((item_number, item_text))
                        i += 1
                    elif not numbered_line:  # Empty line ends list
                        break
                    else:  # Non-numbered line ends list
                        break
                
                # Create numbered list with proper formatting
                if numbered_items:
                    try:
                        numbered_style = ParagraphStyle(
                            name='NumberedItem',
                            parent=body_style,
                            fontSize=11,
                            leftIndent=25 if not is_rtl else 0,  # No indent for RTL
                            rightIndent=0 if not is_rtl else 25,  # Right indent for RTL
                            firstLineIndent=-15 if not is_rtl else 0,
                            spaceAfter=6,
                            fontName=self.unicode_font_name or 'Helvetica',
                            alignment=TA_RIGHT if is_rtl else TA_LEFT
                        )
                        
                        # Create numbered paragraphs
                        for item_number, item_text in numbered_items:
                            # Escape HTML but preserve Unicode
                            safe_text = item_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            
                            # Add number prefix
                            numbered_para = Paragraph(f'<b>{item_number}.</b> {safe_text}', numbered_style)
                            elements.append(numbered_para)
                        
                        elements.append(Spacer(1, 0.15 * inch))
                        
                    except Exception as e:
                        logger.warning(f"Failed to create numbered list: {e}")
                        # Fallback: simple numbered paragraphs
                        for item_number, item_text in numbered_items:
                            safe_text = item_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            try:
                                elements.append(Paragraph(f'{item_number}. {safe_text}', body_style))
                            except Exception:
                                logger.error(f"Could not render numbered item: {item_text[:50]}")
                        elements.append(Spacer(1, 0.1 * inch))
                continue  # i already advanced
            
            # Detect bullet points (•, -, *)
            elif stripped.startswith(('• ', '- ', '* ')):
                # Collect all consecutive bullet items
                bullet_items = []
                while i < len(lines):
                    bullet_line = lines[i].strip()
                    if bullet_line.startswith(('• ', '- ', '* ')):
                        # Remove bullet marker
                        for marker in ['• ', '- ', '* ']:
                            if bullet_line.startswith(marker):
                                item_text = bullet_line[len(marker):]
                                break
                        bullet_items.append(item_text)
                        i += 1
                    elif not bullet_line:  # Empty line ends list
                        break
                    else:  # Non-bullet line ends list
                        break
                
                # Create bullet list with proper formatting
                if bullet_items:
                    try:
                        # Use ReportLab's bullet paragraph style
                        bullet_style = ParagraphStyle(
                            name='BulletItem',
                            parent=body_style,
                            fontSize=11,
                            leftIndent=20 if not is_rtl else 0,
                            rightIndent=0 if not is_rtl else 20,
                            firstLineIndent=0,
                            spaceAfter=6,
                            bulletIndent=10,
                            bulletFontName=self.unicode_font_name or 'Helvetica',
                            fontName=self.unicode_font_name or 'Helvetica',
                            alignment=TA_RIGHT if is_rtl else TA_LEFT
                        )
                        
                        # Create bullet paragraphs with proper bullet formatting
                        for item_text in bullet_items:
                            # Escape HTML but preserve Unicode
                            safe_text = item_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            
                            # Use <bullet> tag with bulletText parameter for proper rendering
                            # ReportLab's Paragraph supports <bullet> tags when bulletText is set
                            bullet_para = Paragraph(f'<bullet>&bull;</bullet>{safe_text}', bullet_style, bulletText='•')
                            elements.append(bullet_para)
                        
                        elements.append(Spacer(1, 0.15 * inch))
                        
                    except Exception as e:
                        logger.warning(f"Failed to create bullet list with proper formatting: {e}")
                        # Fallback: use simpler approach with indentation
                        for item_text in bullet_items:
                            safe_text = item_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            try:
                                # Create indented paragraph with bullet character
                                bullet_style = ParagraphStyle(
                                    name='SimpleBullet',
                                    parent=body_style,
                                    leftIndent=20 if not is_rtl else 0,
                                    rightIndent=0 if not is_rtl else 20,
                                    bulletIndent=10,
                                    fontName=self.unicode_font_name or 'Helvetica',
                                    alignment=TA_RIGHT if is_rtl else TA_LEFT
                                )
                                elements.append(Paragraph(f'• {safe_text}', bullet_style))
                            except Exception:
                                logger.error(f"Could not render bullet item: {item_text[:50]}")
                        elements.append(Spacer(1, 0.1 * inch))
                continue  # i already advanced
            
            # Regular paragraph
            else:
                try:
                    # Preserve bold (**text**) and italic (*text*)
                    para_text = stripped
                    para_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para_text)  # Bold
                    para_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', para_text)  # Italic
                    
                    # Escape remaining HTML chars
                    para_text = para_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    # Un-escape our formatting tags
                    para_text = para_text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
                    para_text = para_text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
                    
                    elements.append(Paragraph(para_text, body_style))
                    elements.append(Spacer(1, 0.08 * inch))
                except Exception as e:
                    logger.error(f"Failed to create paragraph: {e}, text: {stripped[:50]}")
                i += 1
        
        return elements
    
    def _html_to_elements(self, html_content: str) -> List:
        """
        Convert HTML to ReportLab flowable elements
        
        Args:
            html_content: HTML formatted text
            
        Returns:
            List of ReportLab flowable elements
        """
        elements = []
        
        # ReportLab's Paragraph class supports basic HTML tags natively
        # Clean up HTML content first
        html_content = html_content.strip()
        
        # Remove extra periods and clean up spacing
        html_content = re.sub(r'\.{3,}', '...', html_content)  # Replace multiple periods with ...
        html_content = re.sub(r'\.\s*\.', '.', html_content)  # Remove double periods
        html_content = re.sub(r'\s+', ' ', html_content)  # Normalize whitespace
        
        # Split by paragraph tags or div tags
        # Extract paragraphs
        paragraphs = re.split(r'</?p[^>]*>|</?div[^>]*>', html_content, flags=re.IGNORECASE)
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Remove HTML tags that ReportLab doesn't support, but keep basic formatting
            # ReportLab Paragraph supports: <b>, <i>, <u>, <font>, <br/>, <a>
            # Remove unsupported tags but keep their content
            para = re.sub(r'</?(?:html|body|head|meta|link|script|style)[^>]*>', '', para, flags=re.IGNORECASE)
            
            # Convert markdown-style headings to HTML headings
            para = re.sub(r'^#\s+(.+)$', r'<b><font size="18">\1</font></b>', para, flags=re.MULTILINE)
            para = re.sub(r'^##\s+(.+)$', r'<b><font size="14">\1</font></b>', para, flags=re.MULTILINE)
            
            # Clean up any remaining markdown syntax
            para = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', para)  # Bold
            para = re.sub(r'\*(.+?)\*', r'<i>\1</i>', para)  # Italic
            
            # Use ReportLab's Paragraph which supports HTML
            try:
                elements.append(Paragraph(para, self.styles['CustomBody']))
                elements.append(Spacer(1, 0.1 * inch))
            except Exception as e:
                logger.warning(f"Failed to parse HTML paragraph: {e}, trying fallback")
                # Fallback 1: Try with plain text extraction
                try:
                    text = self._html_to_text(para)
                    if text.strip():
                        # Clean text but preserve Unicode characters (Chinese, Japanese, Korean)
                        # ReportLab should handle Unicode if font is registered
                        text_clean = text  # Don't strip Unicode - let ReportLab handle it
                        try:
                            elements.append(Paragraph(text_clean, self.styles['CustomBody']))
                            elements.append(Spacer(1, 0.1 * inch))
                        except Exception as e2:
                            logger.error(f"Failed to create paragraph even with plain text: {e2}")
                            # Last resort: try with minimal cleaning (only remove problematic HTML entities)
                            text_minimal = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                            try:
                                elements.append(Paragraph(text_minimal, self.styles['CustomBody']))
                                elements.append(Spacer(1, 0.1 * inch))
                            except Exception:
                                logger.error(f"Could not create paragraph: {text[:100]}")
                except Exception as e2:
                    logger.error(f"Fallback also failed: {e2}, skipping paragraph: {para[:100]}")
        
        return elements
    
    def generate_from_text(
        self,
        text_content: str,
        output_path: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processed_images: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generate PDF from plain text content
        
        Args:
            text_content: Plain text content
            output_path: Optional file path to save PDF (if None, returns bytes)
            title: Optional document title
            metadata: Optional PDF metadata (author, subject, keywords)
            
        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer if output_path is None else output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build story (content)
        story = []
        
        # Add title if provided
        if title:
            story.append(Paragraph(title, self.styles['CustomHeading1']))
            story.append(Spacer(1, 0.3 * inch))
        
        # Convert text to elements
        elements = self._text_to_elements(text_content)
        story.extend(elements)
        
        # Embed images if provided
        if processed_images:
            for img in processed_images:
                try:
                    image_data = img.get("data")
                    if image_data:
                        # Create Image from bytes using ImageReader
                        from reportlab.lib.utils import ImageReader
                        img_reader = ImageReader(io.BytesIO(image_data))
                        
                        # Get dimensions from metadata or use defaults
                        width = img.get("metadata", {}).get("width")
                        height = img.get("metadata", {}).get("height")
                        
                        # Set max width/height to fit page (6 inches max)
                        max_width = 6 * inch
                        max_height = 6 * inch
                        
                        if width and height:
                            # Scale to fit if too large
                            scale = min(max_width / width, max_height / height, 1.0)
                            width = width * scale
                            height = height * scale
                        else:
                            # Use default size if dimensions not available
                            width = min(max_width, 4 * inch)
                            height = None  # Let ReportLab maintain aspect ratio
                        
                        # Add spacing before image
                        story.append(Spacer(1, 0.2 * inch))
                        
                        # Add image
                        if height:
                            story.append(Image(img_reader, width=width, height=height))
                        else:
                            story.append(Image(img_reader, width=width))
                        
                        # Add alt text as caption if available
                        alt_text = img.get("alt_text", "")
                        if alt_text:
                            story.append(Spacer(1, 0.1 * inch))
                            story.append(Paragraph(f"<i>{alt_text}</i>", self.styles['CustomBody']))
                        
                        # Add spacing after image
                        story.append(Spacer(1, 0.2 * inch))
                except Exception as e:
                    logger.warning(f"Failed to embed image in PDF: {e}")
        
        # Build PDF
        doc.build(story)
        
        if output_path is None:
            buffer.seek(0)
            return buffer.read()
        else:
            return _fs.read_bytes(output_path)
    
    def generate_from_markdown(
        self,
        markdown_content: str,
        output_path: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processed_images: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generate PDF from Markdown content
        
        Args:
            markdown_content: Markdown formatted text
            output_path: Optional file path to save PDF (if None, returns bytes)
            title: Optional document title
            metadata: Optional PDF metadata
            processed_images: List of image data dicts for embedding
            
        Returns:
            PDF content as bytes
        """
        # Convert Markdown to HTML first
        html_content = self._markdown_to_html(markdown_content)
        
        # Then convert HTML to PDF
        return self.generate_from_html(
            html_content,
            output_path=output_path,
            title=title,
            metadata=metadata,
            processed_images=processed_images
        )
    
    def generate_from_html(
        self,
        html_content: str,
        output_path: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        processed_images: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generate PDF from HTML content
        
        Args:
            html_content: HTML formatted text
            output_path: Optional file path to save PDF (if None, returns bytes)
            title: Optional document title
            metadata: Optional PDF metadata
            
        Returns:
            PDF content as bytes
        """
        # Apply stylesheet if available
        styled_html = self._apply_stylesheet(html_content)
        
        buffer = io.BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(
            buffer if output_path is None else output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build story (content)
        story = []
        
        # Add title if provided
        if title:
            story.append(Paragraph(title, self.styles['CustomHeading1']))
            story.append(Spacer(1, 0.3 * inch))
        
        # Convert HTML to elements
        elements = self._html_to_elements(styled_html)
        story.extend(elements)
        
        # Embed images if provided
        if processed_images:
            for img in processed_images:
                try:
                    image_data = img.get("data")
                    if image_data:
                        # Create Image from bytes using ImageReader
                        from reportlab.lib.utils import ImageReader
                        img_reader = ImageReader(io.BytesIO(image_data))
                        
                        # Get dimensions from metadata or use defaults
                        width = img.get("metadata", {}).get("width")
                        height = img.get("metadata", {}).get("height")
                        
                        # Set max width/height to fit page (6 inches max)
                        max_width = 6 * inch
                        max_height = 6 * inch
                        
                        if width and height:
                            # Scale to fit if too large
                            scale = min(max_width / width, max_height / height, 1.0)
                            width = width * scale
                            height = height * scale
                        else:
                            # Use default size if dimensions not available
                            width = min(max_width, 4 * inch)
                            height = None  # Let ReportLab maintain aspect ratio
                        
                        # Add spacing before image
                        story.append(Spacer(1, 0.2 * inch))
                        
                        # Add image
                        if height:
                            story.append(Image(img_reader, width=width, height=height))
                        else:
                            story.append(Image(img_reader, width=width))
                        
                        # Add alt text as caption if available
                        alt_text = img.get("alt_text", "")
                        if alt_text:
                            story.append(Spacer(1, 0.1 * inch))
                            story.append(Paragraph(f"<i>{alt_text}</i>", self.styles['CustomBody']))
                        
                        # Add spacing after image
                        story.append(Spacer(1, 0.2 * inch))
                except Exception as e:
                    logger.warning(f"Failed to embed image in PDF: {e}")
        
        # Build PDF
        doc.build(story)
        
        if output_path is None:
            buffer.seek(0)
            return buffer.read()
        else:
            return _fs.read_bytes(output_path)
    
    def generate(
        self,
        content: str,
        content_type: str = 'text',
        output_path: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        media_links: Optional[List[Dict[str, Any]]] = None,
        processed_images: Optional[List[Dict[str, Any]]] = None
    ) -> bytes:
        """
        Generate PDF from content (auto-detect or specify type)
        
        Args:
            content: Content to convert (text, markdown, or HTML)
            content_type: Type of content ('text', 'markdown', 'html')
            output_path: Optional file path to save PDF
            title: Optional document title
            metadata: Optional PDF metadata
            
        Returns:
            PDF content as bytes
        """
        # Add media links to content if provided (for non-image media)
        if media_links:
            media_section = self._format_media_links(media_links)
            content = f"{content}\n\n{media_section}"
        
        if content_type == 'markdown':
            return self.generate_from_markdown(
                content,
                output_path=output_path,
                title=title,
                metadata=metadata,
                processed_images=processed_images
            )
        elif content_type == 'html':
            return self.generate_from_html(
                content,
                output_path=output_path,
                title=title,
                metadata=metadata,
                processed_images=processed_images
            )
        else:  # Default to text
            return self.generate_from_text(
                content,
                output_path=output_path,
                title=title,
                metadata=metadata,
                processed_images=processed_images
            )

    def generate_pdf(
        self,
        content: str,
        content_type: str = "text",
        language: Optional[str] = None,
        title: Optional[str] = None,
        output_path: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        media_links: Optional[List[Dict[str, Any]]] = None,
        processed_images: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """
        Backward-compatible wrapper used by older formatter paths.
        The current generator is language-agnostic, so `language` is accepted
        for contract compatibility and ignored.
        """
        return self.generate(
            content=content,
            content_type=content_type,
            output_path=output_path,
            title=title,
            metadata=metadata,
            media_links=media_links,
            processed_images=processed_images,
        )
    
    def _format_media_links(self, media_links: List[Dict[str, Any]]) -> str:
        """
        Format media links for inclusion in PDF
        
        Args:
            media_links: List of media link dicts with 'type', 'url', 'format', 'metadata'
            
        Returns:
            Formatted text with media links
        """
        if not media_links:
            return ""
        
        lines = ["\n---\nMedia Files:"]
        for link in media_links:
            media_type = link.get("type", "unknown")  # 'audio', 'video'
            url = link.get("url", "")
            format = link.get("format", "")
            metadata = link.get("metadata", {})
            
            if media_type == "audio":
                duration = metadata.get("duration")
                duration_str = f" ({duration:.1f}s)" if duration else ""
                lines.append(f"Audio ({format}{duration_str}): {url}")
            elif media_type == "video":
                duration = metadata.get("duration")
                width = metadata.get("width")
                height = metadata.get("height")
                info_parts = []
                if duration:
                    info_parts.append(f"{duration:.1f}s")
                if width and height:
                    info_parts.append(f"{width}x{height}")
                info_str = f" ({', '.join(info_parts)})" if info_parts else ""
                lines.append(f"Video ({format}{info_str}): {url}")
            else:
                lines.append(f"{media_type.title()} ({format}): {url}")
        
        return "\n".join(lines)
