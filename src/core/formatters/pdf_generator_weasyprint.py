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
Description: WeasyPrint-based PDF Generator - Converts HTML/Markdown to PDF with full multi-language support

Related Requirements: FR1.18
Related Tasks: T29
Related Architecture: CC5.2
Related Tests: UT1.14, ST1.5, IT1.17, AT1.19

Recent Changes:
- Replaced ReportLab with WeasyPrint for better Unicode/RTL support
- HTML-based rendering with CSS for numbered lists, RTL, and formatting

**************************************************
"""

from typing import Optional
import re

from src.utils.logger import get_logger

WEASYPRINT_IMPORT_ERROR: Optional[str] = None
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    WEASYPRINT_AVAILABLE = False
    WEASYPRINT_IMPORT_ERROR = str(e)

try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

logger = get_logger(__name__)


class PDFGeneratorWeasyPrint:
    """Generates PDF documents from HTML/Markdown using WeasyPrint"""
    
    def __init__(self, stylesheet_path: Optional[str] = None):
        """
        Initialize PDF generator with WeasyPrint
        
        Args:
            stylesheet_path: Optional path to CSS stylesheet file
        """
        if not WEASYPRINT_AVAILABLE:
            detail = f" ({WEASYPRINT_IMPORT_ERROR})" if WEASYPRINT_IMPORT_ERROR else ""
            raise ImportError(f"weasyprint is required for PDF generation. Install with: pip install weasyprint{detail}")
        
        self.stylesheet_path = stylesheet_path
        self.font_config = FontConfiguration()
        logger.info("PDFGeneratorWeasyPrint initialized")
    
    def _get_default_css(self, language: str = 'en') -> str:
        """
        Get default CSS for PDF generation with language-specific styles
        
        Args:
            language: Target language code (en, ar, zh, etc.)
            
        Returns:
            CSS string
        """
        # Detect RTL languages
        rtl_languages = ['ar', 'he', 'fa', 'ur']
        is_rtl = language in rtl_languages
        
        css = f"""
        @page {{
            size: A4;
            margin: 2cm;
        }}
        
        body {{
            font-family: 'DejaVu Sans', 'Noto Sans', 'Arial Unicode MS', sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #000000;
            direction: {'rtl' if is_rtl else 'ltr'};
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            font-weight: bold;
            margin-top: 1em;
            margin-bottom: 0.5em;
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        h1 {{ font-size: 18pt; }}
        h2 {{ font-size: 14pt; }}
        h3 {{ font-size: 12pt; }}
        
        p {{
            margin: 0.5em 0;
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        /* Numbered lists */
        ol {{
            margin: 0.5em 0;
            padding-{('right' if is_rtl else 'left')}: 2em;
            list-style-position: outside;
        }}
        
        ol li {{
            margin: 0.3em 0;
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        /* Bullet lists */
        ul {{
            margin: 0.5em 0;
            padding-{('right' if is_rtl else 'left')}: 2em;
            list-style-position: outside;
        }}
        
        ul li {{
            margin: 0.3em 0;
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        /* Bold and italic */
        strong, b {{ font-weight: bold; }}
        em, i {{ font-style: italic; }}
        
        /* Code blocks */
        code, pre {{
            font-family: 'DejaVu Sans Mono', 'Courier New', monospace;
            background-color: #f5f5f5;
            padding: 0.2em 0.4em;
            border-radius: 3px;
        }}
        
        pre {{
            display: block;
            padding: 1em;
            margin: 0.5em 0;
            overflow-x: auto;
        }}
        
        /* Links */
        a {{
            color: #0066cc;
            text-decoration: underline;
        }}
        
        /* Tables */
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 0.5em 0;
        }}
        
        th, td {{
            border: 1px solid #ddd;
            padding: 0.5em;
            text-align: {'right' if is_rtl else 'left'};
        }}
        
        th {{
            background-color: #f5f5f5;
            font-weight: bold;
        }}
        """
        
        return css
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Convert Markdown to HTML
        
        Args:
            markdown_text: Markdown formatted text
            
        Returns:
            HTML string
        """
        if not MARKDOWN_AVAILABLE:
            # Fallback: simple conversion
            html = markdown_text.replace('\n\n', '</p><p>')
            html = f'<p>{html}</p>'
            return html
        
        # Use markdown library with extensions
        html = markdown.markdown(
            markdown_text,
            extensions=['extra', 'nl2br', 'sane_lists']
        )
        return html
    
    def _text_to_html(self, text: str) -> str:
        """
        Convert plain text to HTML, preserving formatting
        
        Args:
            text: Plain text content
            
        Returns:
            HTML string
        """
        html_parts = []
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            stripped = line.strip()
            
            # Empty line
            if not stripped:
                i += 1
                continue
            
            # Headings
            if stripped.startswith('# '):
                html_parts.append(f'<h1>{stripped[2:]}</h1>')
                i += 1
                continue
            elif stripped.startswith('## '):
                html_parts.append(f'<h2>{stripped[3:]}</h2>')
                i += 1
                continue
            elif stripped.startswith('### '):
                html_parts.append(f'<h3>{stripped[4:]}</h3>')
                i += 1
                continue
            
            # Numbered lists
            elif re.match(r'^\d+[\.\)]\s', stripped):
                list_items = []
                while i < len(lines):
                    list_line = lines[i].strip()
                    match = re.match(r'^\d+[\.\)]\s+(.+)', list_line)
                    if match:
                        list_items.append(match.group(1))
                        i += 1
                    elif not list_line:
                        break
                    else:
                        break
                
                if list_items:
                    html_parts.append('<ol>')
                    for item in list_items:
                        html_parts.append(f'<li>{item}</li>')
                    html_parts.append('</ol>')
                continue
            
            # Bullet lists
            elif stripped.startswith(('• ', '- ', '* ')):
                list_items = []
                while i < len(lines):
                    list_line = lines[i].strip()
                    if list_line.startswith(('• ', '- ', '* ')):
                        for marker in ['• ', '- ', '* ']:
                            if list_line.startswith(marker):
                                list_items.append(list_line[len(marker):])
                                break
                        i += 1
                    elif not list_line:
                        break
                    else:
                        break
                
                if list_items:
                    html_parts.append('<ul>')
                    for item in list_items:
                        html_parts.append(f'<li>{item}</li>')
                    html_parts.append('</ul>')
                continue
            
            # Regular paragraph
            else:
                # Handle bold and italic
                para_text = stripped
                para_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', para_text)
                para_text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', para_text)
                html_parts.append(f'<p>{para_text}</p>')
                i += 1
        
        return '\n'.join(html_parts)
    
    def generate_pdf(
        self,
        content: str,
        content_type: str = 'text',
        language: str = 'en',
        title: Optional[str] = None,
        custom_css: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF from content
        
        Args:
            content: Content to convert (text, markdown, or HTML)
            content_type: Type of content ('text', 'markdown', 'html')
            language: Target language code
            title: Optional document title
            custom_css: Optional custom CSS
            
        Returns:
            PDF bytes
        """
        logger.info(f"Generating PDF: type={content_type}, language={language}, length={len(content)}")
        
        # Convert content to HTML
        if content_type == 'html':
            html_body = content
        elif content_type == 'markdown':
            html_body = self._markdown_to_html(content)
        else:  # text
            html_body = self._text_to_html(content)
        
        # Build complete HTML document
        html_doc = f"""
<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <title>{title or 'Document'}</title>
</head>
<body>
{html_body}
</body>
</html>
"""
        
        # Get CSS
        css_content = custom_css or self._get_default_css(language)
        
        # Generate PDF
        try:
            html_obj = HTML(string=html_doc)
            css_obj = CSS(string=css_content, font_config=self.font_config)
            
            pdf_bytes = html_obj.write_pdf(
                stylesheets=[css_obj],
                font_config=self.font_config
            )
            
            logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            raise
