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
File Channel Adapter for delivering notifications to file storage.

Handles:
- Format conversion (Markdown, Plain Text, PDF)
- Filename pattern processing
- Multi-file delivery
- Storage backend coordination
"""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, List, Tuple
from src.utils.logger import get_logger

from ..storage.factory import StorageFactory
from ..storage.base import StoredFile, StorageError

logger = get_logger(__name__)
_pdf_executor: ThreadPoolExecutor | None = None


def _get_file_pdf_executor() -> ThreadPoolExecutor:
    """Lazy PDF executor used by file-channel PDF generation."""
    global _pdf_executor
    if _pdf_executor is None:
        _pdf_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="file-pdf")
    return _pdf_executor


class FileChannelAdapter:
    """
    File channel adapter for file-based notification delivery.
    
    Delivers notifications by writing them to various storage backends
    in multiple formats (Markdown, Plain Text, PDF).
    """
    
    def __init__(self, channel_config: Dict[str, Any]):
        """
        Initialize file channel adapter.
        
        Args:
            channel_config: Channel configuration including storage backend config
        """
        self.config = channel_config
        
        # Create storage backend
        self.storage = StorageFactory.create(channel_config)
        
        logger.info(f"Initialized file channel adapter with {channel_config.get('storage_type')} backend")
    
    def _process_filename_pattern(
        self,
        pattern: str,
        message_id: str,
        language: str,
        file_format: str
    ) -> str:
        """
        Process filename pattern with token replacement.
        
        Tokens:
        - {message_id}: Message ID
        - {timestamp}: Unix timestamp
        - {datetime}: ISO datetime
        - {year}: Current year (YYYY)
        - {month}: Current month (01-12)
        - {day}: Current day (01-31)
        - {lang}: Target language
        - {format}: File format (md, txt, pdf)
        
        Args:
            pattern: Filename pattern
            message_id: Message ID
            language: Target language
            file_format: File format
            
        Returns:
            Processed filename
        """
        now = datetime.now()
        
        replacements = {
            "{message_id}": message_id,
            "{timestamp}": str(int(now.timestamp())),
            "{datetime}": now.isoformat(),
            "{year}": now.strftime("%Y"),
            "{month}": now.strftime("%m"),
            "{day}": now.strftime("%d"),
            "{lang}": language,
            "{format}": file_format
        }
        
        filename = pattern
        for token, value in replacements.items():
            filename = filename.replace(token, value)
        
        return filename
    
    def _convert_markdown_to_text(self, markdown: str) -> str:
        """
        Convert Markdown to plain text by stripping markdown syntax.
        
        Args:
            markdown: Markdown content
            
        Returns:
            Plain text content
        """
        text = markdown
        
        # Remove headers (#, ##, ###)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove bold (**text** or __text__)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        
        # Remove italic (*text* or _text_)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        
        # Remove links [text](url)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    def _convert_markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to basic HTML."""
        if not markdown:
            return ""

        text = markdown

        # Headers
        text = re.sub(r'^###\s+(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^##\s+(.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^#\s+(.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)

        # Bold / italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)

        # Links
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)

        # Lists (very basic)
        lines = text.split("\n")
        html_lines: List[str] = []
        in_ul = False
        in_ol = False

        for line in lines:
            if re.match(r'^\s*[-*+]\s+', line):
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                if not in_ul:
                    html_lines.append("<ul>")
                    in_ul = True
                item = re.sub(r'^\s*[-*+]\s+', '', line).strip()
                html_lines.append(f"<li>{item}</li>")
                continue

            if re.match(r'^\s*\d+\.\s+', line):
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if not in_ol:
                    html_lines.append("<ol>")
                    in_ol = True
                item = re.sub(r'^\s*\d+\.\s+', '', line).strip()
                html_lines.append(f"<li>{item}</li>")
                continue

            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False

            if line.strip():
                html_lines.append(f"<p>{line}</p>")

        if in_ul:
            html_lines.append("</ul>")
        if in_ol:
            html_lines.append("</ol>")

        return "\n".join(html_lines)

    def _infer_pdf_content_type(self, content: str) -> Tuple[str, str]:
        """
        Infer the correct PDF content type for the stored file payload.

        The file-channel path receives already-formatted translated text. Forcing
        markdown- or HTML-like payloads through the plain-text PDF converter can
        distort list/RTL structure and inflate extracted text size. Keep the
        original semantics whenever we can infer them safely.
        """
        text = str(content or "").strip()
        if not text:
            return "", "text"

        def _strip_markdown_headers(value: str) -> str:
            return re.sub(r"(?m)^\s*#{2,6}\s+", "", value or "").strip()

        text_lower = text.lower()
        if any(tag in text_lower for tag in ("<html", "<body", "<p", "<div", "<h1", "<h2", "<h3", "<ul", "<ol", "<li", "<img", "<video", "<audio")):
            return _strip_markdown_headers(text), "html"

        has_markdown_structure = (
            "```" in text
            or re.search(r"(?m)^\s*#{1,6}\s+\S", text) is not None
            or re.search(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+\S", text) is not None
            or re.search(r"\*\*.+?\*\*", text) is not None
            or re.search(r"\[(.+?)\]\((.+?)\)", text) is not None
        )
        if has_markdown_structure:
            # Render markdown-like payloads to HTML before WeasyPrint so PDF text
            # extraction does not retain raw heading markers such as ## / ###.
            return self._convert_markdown_to_html(_strip_markdown_headers(text)), "html"

        return _strip_markdown_headers(text), "text"
    
    async def _generate_pdf(self, content: str, language: str) -> bytes:
        """
        Generate PDF from markdown content.
        
        Args:
            content: Markdown content
            language: Target language
            
        Returns:
            PDF bytes
        """
        # Import PDF generator
        try:
            from ..formatters.pdf_generator_weasyprint import PDFGeneratorWeasyPrint
            import asyncio
            generator = PDFGeneratorWeasyPrint()
            normalized_content, content_type = self._infer_pdf_content_type(content)

            # Run synchronous PDF generation in shared lazy-init thread pool (W28A-93b)
            loop = asyncio.get_event_loop()
            pdf_bytes = await loop.run_in_executor(
                _get_file_pdf_executor(),
                generator.generate_pdf,
                normalized_content,
                content_type,
                language,
                "Notification"
            )
            
            return pdf_bytes
            
        except ImportError as e:
            logger.error(f"PDF generator not available: {e}")
            raise StorageError(f"PDF generation not available: {e}")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            raise StorageError(f"PDF generation failed: {e}")
    
    async def deliver(
        self,
        message_id: str,
        content: str,
        language: str,
        user_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deliver notification to file storage.
        
        Args:
            message_id: Message ID
            content: Translated content (Markdown)
            language: Target language
            user_preferences: User preferences including:
                - output_formats: List of formats (md, txt, pdf)
                - generate_pdf: Boolean for PDF generation
            
        Returns:
            Delivery result with stored file metadata
        """
        stored_files: List[StoredFile] = []
        errors: List[str] = []
        
        # Get requested formats
        output_formats = user_preferences.get("output_formats", [])
        generate_pdf = user_preferences.get("generate_pdf", False)
        
        # Get filename pattern
        filename_pattern = self.config.get(
            "file_name_pattern",
            "{message_id}_{timestamp}_{lang}.{format}"
        )
        
        logger.info(f"Delivering message {message_id} to file storage")
        logger.info(f"Formats: {output_formats}, PDF: {generate_pdf}")
        logger.info(f"DEBUG: content length={len(content) if content else 0}")
        
        try:
            # Generate and store Markdown file
            if "md" in output_formats:
                try:
                    filename = self._process_filename_pattern(
                        filename_pattern,
                        message_id,
                        language,
                        "md"
                    )
                    
                    stored_file = await self.storage.store_file(
                        content=content.encode('utf-8'),
                        filename=filename,
                        content_type="text/markdown",
                        metadata={"message_id": message_id, "language": language}
                    )
                    
                    stored_files.append(stored_file)
                    logger.info(f"Stored Markdown file: {filename}")
                    
                except Exception as e:
                    error_msg = f"Failed to store Markdown file: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Generate and store HTML file
            if "html" in output_formats:
                try:
                    filename = self._process_filename_pattern(
                        filename_pattern,
                        message_id,
                        language,
                        "html"
                    )

                    html_body = self._convert_markdown_to_html(content)
                    html_page = (
                        "<!DOCTYPE html>\n"
                        f"<html lang=\"{language}\">\n"
                        "<head><meta charset=\"UTF-8\"></head>\n"
                        f"<body>\n{html_body}\n</body>\n"
                        "</html>\n"
                    )

                    stored_file = await self.storage.store_file(
                        content=html_page.encode('utf-8'),
                        filename=filename,
                        content_type="text/html",
                        metadata={"message_id": message_id, "language": language}
                    )

                    stored_files.append(stored_file)
                    logger.info(f"Stored HTML file: {filename}")

                except Exception as e:
                    error_msg = f"Failed to store HTML file: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Generate and store Plain Text file
            if "txt" in output_formats:
                try:
                    filename = self._process_filename_pattern(
                        filename_pattern,
                        message_id,
                        language,
                        "txt"
                    )
                    
                    text_content = self._convert_markdown_to_text(content)
                    
                    stored_file = await self.storage.store_file(
                        content=text_content.encode('utf-8'),
                        filename=filename,
                        content_type="text/plain",
                        metadata={"message_id": message_id, "language": language}
                    )
                    
                    stored_files.append(stored_file)
                    logger.info(f"Stored text file: {filename}")
                    
                except Exception as e:
                    error_msg = f"Failed to store text file: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Generate and store PDF file
            if generate_pdf:
                try:
                    filename = self._process_filename_pattern(
                        filename_pattern,
                        message_id,
                        language,
                        "pdf"
                    )
                    
                    pdf_bytes = await self._generate_pdf(content, language)
                    
                    stored_file = await self.storage.store_file(
                        content=pdf_bytes,
                        filename=filename,
                        content_type="application/pdf",
                        metadata={"message_id": message_id, "language": language}
                    )
                    
                    stored_files.append(stored_file)
                    logger.info(f"Stored PDF file: {filename}")
                    
                except Exception as e:
                    error_msg = f"Failed to store PDF file: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Build result
            result = {
                "success": len(stored_files) > 0,
                "files_stored": len(stored_files),
                "stored_files": [f.to_dict() for f in stored_files],
                "errors": errors
            }
            
            if not stored_files:
                result["error_message"] = "No files were stored"
                logger.warning(f"No files stored for message {message_id}")
            else:
                logger.info(f"Successfully stored {len(stored_files)} files for message {message_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"File delivery failed: {e}")
            return {
                "success": False,
                "files_stored": 0,
                "stored_files": [],
                "errors": [str(e)],
                "error_message": f"File delivery failed: {e}"
            }
    
    async def delete_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Delete files from storage.
        
        Args:
            file_paths: List of file paths to delete
            
        Returns:
            Deletion result
        """
        deleted = []
        failed = []
        
        for path in file_paths:
            try:
                success = await self.storage.delete_file(path)
                if success:
                    deleted.append(path)
                else:
                    failed.append({"path": path, "error": "File not found"})
            except Exception as e:
                failed.append({"path": path, "error": str(e)})
        
        return {
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted": deleted,
            "failed": failed
        }
    
    async def close(self):
        """Close storage backend connections"""
        if hasattr(self.storage, '__aexit__'):
            await self.storage.__aexit__(None, None, None)
