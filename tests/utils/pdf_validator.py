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
PDF Content Validation Utilities

Extracts and validates actual content from PDFs:
- Image streams with JPEG/PNG markers
- Text content
- Image count and dimensions
"""

import re
import io
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

PYPDF_AVAILABLE = False
PdfReader = None

try:
    from pypdf import PdfReader as _PdfReader  # type: ignore
    PdfReader = _PdfReader
    PYPDF_AVAILABLE = True
except Exception:
    PYPDF_AVAILABLE = False

try:
    from reportlab.lib.utils import ImageReader
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class PDFValidator:
    """Validates PDF content including embedded images and text"""
    
    def __init__(self):
        self.pypdf_available = PYPDF_AVAILABLE
        if not PYPDF_AVAILABLE:
            raise RuntimeError("pypdf is required for PDF validation but is not installed.")
    
    def extract_image_streams(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract image streams from PDF and verify they contain actual image data
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            List of dicts with image info: {'stream_index': int, 'has_jpeg_marker': bool, 
                                           'has_png_marker': bool, 'size': int, 'format': str}
        """
        image_streams = []
        
        # Convert PDF to string for pattern matching
        pdf_text = pdf_bytes[:500000].decode('latin-1', errors='ignore')  # First 500KB
        
        # Find all stream objects
        # Pattern: /Length N\nstream\n...data...\nendstream
        stream_pattern = r'/Length\s+(\d+).*?stream\s+([\x00-\xFF]{100,}?)endstream'
        streams = re.finditer(stream_pattern, pdf_text, re.DOTALL)
        
        stream_index = 0
        for match in streams:
            stream_index += 1
            length = int(match.group(1))
            stream_data = match.group(2)
            
            # Check for JPEG markers (FF D8 FF)
            has_jpeg = b'\xFF\xD8\xFF' in stream_data.encode('latin-1', errors='ignore')[:100]
            
            # Check for PNG markers (89 50 4E 47)
            has_png = b'\x89PNG' in stream_data.encode('latin-1', errors='ignore')[:100]
            
            # Determine format
            format_type = None
            if has_jpeg:
                format_type = "jpeg"
            elif has_png:
                format_type = "png"
            
            if has_jpeg or has_png:
                image_streams.append({
                    'stream_index': stream_index,
                    'has_jpeg_marker': has_jpeg,
                    'has_png_marker': has_png,
                    'size': length,
                    'format': format_type,
                    'data_preview': stream_data[:200]  # First 200 chars for debugging
                })
        
        return image_streams

    def _count_images_pypdf(self, pdf_bytes: bytes) -> Optional[int]:
        """
        Count embedded images using pypdf XObject inspection.

        This is more reliable than scanning for raw JPEG/PNG signatures because
        many PDF generators (e.g., WeasyPrint) store images as FlateDecode streams
        without embedding the original file signatures.
        """
        if not self.pypdf_available:
            return None

        def _deref(obj):
            try:
                if hasattr(obj, "get_object"):
                    return obj.get_object()
                if hasattr(obj, "getObject"):
                    return obj.getObject()
            except Exception:
                return obj
            return obj

        try:
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))  # type: ignore[misc]
        except Exception:
            return None

        def _count_xobject_images(xobj) -> int:
            count = 0
            try:
                xobj = _deref(xobj)
                # xobj behaves like a dict mapping names -> IndirectObject
                for name in xobj:
                    obj = _deref(xobj[name])
                    subtype = obj.get("/Subtype") if hasattr(obj, "get") else None
                    subtype_str = str(subtype) if subtype is not None else ""
                    if subtype_str == "/Image":
                        count += 1
                    elif subtype_str == "/Form":
                        # Recurse into nested form XObjects
                        try:
                            res = obj.get("/Resources") or {}
                            res = _deref(res)
                            nested = res.get("/XObject") if hasattr(res, "get") else None
                            if nested:
                                count += _count_xobject_images(nested)
                        except Exception:
                            pass
            except Exception:
                return count
            return count

        try:
            pages = list(pdf_reader.pages)
        except Exception:
            return None

        total = 0
        try:
            for page in pages:
                res = page.get("/Resources") or {}
                res = _deref(res)
                xobj = res.get("/XObject") if hasattr(res, "get") else None
                if xobj:
                    xobj = _deref(xobj)
                    total += _count_xobject_images(xobj)
        except Exception:
            return None

        return total
    
    def extract_text_content(self, pdf_bytes: bytes) -> str:
        """
        Extract text content from PDF
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            Extracted text content
        """
        if not self.pypdf_available:
            # Fallback: simple text extraction from PDF structure
            pdf_text = pdf_bytes[:100000].decode('latin-1', errors='ignore')
            # Extract text between parentheses (PDF text objects)
            text_matches = re.findall(r'\(([^)]+)\)', pdf_text)
            return ' '.join(text_matches)
        
        try:
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))  # type: ignore[misc]
            text_parts = []
            pages = list(pdf_reader.pages)
            for page in pages:
                text_parts.append(page.extract_text() or "")
            return '\n'.join([t for t in text_parts if t])
        except Exception as e:
            # Fallback if pypdf fails
            pdf_text = pdf_bytes[:100000].decode('latin-1', errors='ignore')
            text_matches = re.findall(r'\(([^)]+)\)', pdf_text)
            return ' '.join(text_matches)
    
    def count_embedded_images(self, pdf_bytes: bytes) -> int:
        """
        Count number of embedded images in PDF
        
        Args:
            pdf_bytes: PDF content as bytes
            
        Returns:
            Number of embedded images
        """
        pypdf_count = self._count_images_pypdf(pdf_bytes)
        if isinstance(pypdf_count, int):
            return pypdf_count

        image_streams = self.extract_image_streams(pdf_bytes)
        return len(image_streams)
    
    def validate_pdf_has_images(self, pdf_bytes: bytes, expected_count: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate that PDF contains embedded images
        
        Args:
            pdf_bytes: PDF content as bytes
            expected_count: Optional expected number of images
            
        Returns:
            Tuple of (is_valid, message)
        """
        actual_count = self.count_embedded_images(pdf_bytes)
        
        if actual_count == 0:
            return False, "PDF contains no embedded images (only text references)"
        
        if expected_count is not None and actual_count != expected_count:
            return False, f"PDF contains {actual_count} images, expected {expected_count}"
        
        return True, f"PDF contains {actual_count} embedded image(s)"
    
    def validate_pdf_text_content(self, pdf_bytes: bytes, expected_keywords: List[str]) -> Tuple[bool, str]:
        """
        Validate that PDF contains expected text content
        
        Args:
            pdf_bytes: PDF content as bytes
            expected_keywords: List of keywords that should appear in PDF
            
        Returns:
            Tuple of (is_valid, message)
        """
        text_content = self.extract_text_content(pdf_bytes).lower()
        
        missing_keywords = []
        for keyword in expected_keywords:
            if keyword.lower() not in text_content:
                missing_keywords.append(keyword)
        
        if missing_keywords:
            return False, f"PDF missing expected keywords: {', '.join(missing_keywords)}"
        
        return True, f"PDF contains all expected keywords: {', '.join(expected_keywords)}"
    
    def validate_pdf_complete(
        self, 
        pdf_bytes: bytes, 
        expected_image_count: Optional[int] = None,
        expected_keywords: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Complete PDF validation
        
        Args:
            pdf_bytes: PDF content as bytes
            expected_image_count: Optional expected number of images
            expected_keywords: Optional list of keywords that should appear
            
        Returns:
            Dict with validation results
        """
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'image_count': 0,
            'text_content': '',
            'image_streams': []
        }
        
        # Validate images
        # Use the robust image counter (pypdf XObject inspection) where available.
        results['image_count'] = self.count_embedded_images(pdf_bytes)
        # Keep legacy stream extraction for debugging only.
        results['image_streams'] = self.extract_image_streams(pdf_bytes)
        
        if expected_image_count is not None:
            img_valid, img_msg = self.validate_pdf_has_images(pdf_bytes, expected_image_count)
            if not img_valid:
                results['is_valid'] = False
                results['errors'].append(f"Image validation failed: {img_msg}")
        else:
            img_valid, img_msg = self.validate_pdf_has_images(pdf_bytes)
            if not img_valid:
                results['warnings'].append(f"Image validation: {img_msg}")
        
        # Validate text content
        text_content = self.extract_text_content(pdf_bytes)
        results['text_content'] = text_content
        
        if expected_keywords:
            text_valid, text_msg = self.validate_pdf_text_content(pdf_bytes, expected_keywords)
            if not text_valid:
                results['is_valid'] = False
                results['errors'].append(f"Text validation failed: {text_msg}")
        
        return results


def validate_pdf_file(pdf_path: Path, **kwargs) -> Dict[str, Any]:
    """
    Validate a PDF file
    
    Args:
        pdf_path: Path to PDF file
        **kwargs: Arguments to pass to validate_pdf_complete
        
    Returns:
        Validation results dict
    """
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    validator = PDFValidator()
    return validator.validate_pdf_complete(pdf_bytes, **kwargs)


def validate_pdf_bytes(pdf_bytes: bytes, **kwargs) -> Dict[str, Any]:
    """
    Validate PDF bytes
    
    Args:
        pdf_bytes: PDF content as bytes
        **kwargs: Arguments to pass to validate_pdf_complete
        
    Returns:
        Validation results dict
    """
    validator = PDFValidator()
    return validator.validate_pdf_complete(pdf_bytes, **kwargs)

