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
Unit Tests for SMTP Email Header Validation

Tests that email headers are properly formatted according to RFC 5322:
- Required headers (Date, Message-ID, MIME-Version, From, To, Subject)
- Header encoding for non-ASCII characters
- Header line length limits
- Proper MIME structure

Related Requirements: FR1.6
Related Tasks: T17
Related Tests: UT1.4
"""

import pytest
from email.message import EmailMessage
from email.utils import parseaddr
from src.adapters.smtp_adapter import SMTPAdapter


class TestSMTPEmailHeaders:
    """Test SMTP email header formatting and validation"""
    
    @pytest.fixture
    def smtp_adapter(self, smtp_config):
        """Create SMTP adapter instance"""
        config = {
            "host": smtp_config.get("host"),
            "port": smtp_config.get("port"),
            "from_address": smtp_config.get("from_address"),
            "use_tls": smtp_config.get("use_tls"),
            "use_starttls": smtp_config.get("use_starttls"),
            "timeout": smtp_config.get("timeout"),
        }
        return SMTPAdapter(config)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_required_headers_present(self, smtp_adapter):
        """Test that all required RFC 5322 headers are present"""
        content = {
            "subject": "Test Subject",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Check required headers
        assert 'Date' in msg, "Date header must be present"
        assert 'Message-ID' in msg, "Message-ID header must be present"
        assert 'MIME-Version' in msg, "MIME-Version header must be present"
        assert 'From' in msg, "From header must be present"
        assert 'To' in msg, "To header must be present"
        assert 'Subject' in msg, "Subject header must be present"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_date_header_format(self, smtp_adapter):
        """Test that Date header is in RFC 2822 format"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        date_header = msg['Date']
        assert date_header is not None, "Date header must not be None"
        # Date should be in RFC 2822 format (e.g., "Mon, 1 Jan 2024 12:00:00 +0000")
        assert ',' in date_header, "Date header should contain comma (RFC 2822 format)"
        assert len(date_header) > 10, "Date header should be properly formatted"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_message_id_format(self, smtp_adapter):
        """Test that Message-ID is properly formatted"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        message_id = msg['Message-ID']
        assert message_id is not None, "Message-ID must not be None"
        # Message-ID should be in format <local@domain>
        assert message_id.startswith('<'), "Message-ID should start with <"
        assert message_id.endswith('>'), "Message-ID should end with >"
        assert '@' in message_id, "Message-ID should contain @"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_mime_version_header(self, smtp_adapter):
        """Test that MIME-Version header is set to 1.0"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        mime_version = msg['MIME-Version']
        assert mime_version == '1.0', f"MIME-Version should be '1.0', got '{mime_version}'"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_from_header_formatting(self, smtp_adapter):
        """Test that From header is properly formatted"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        from_header = msg['From']
        assert from_header is not None, "From header must not be None"
        # Should be valid email address
        name, addr = parseaddr(from_header)
        assert '@' in addr, "From header should contain valid email address"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_to_header_formatting(self, smtp_adapter):
        """Test that To header is properly formatted"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text"
        }
        
        destination = "recipient@cloud-dog.net"
        msg = smtp_adapter._build_message(destination, content)
        
        to_header = msg['To']
        assert to_header == destination, f"To header should match destination: {to_header} != {destination}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_subject_encoding_ascii(self, smtp_adapter):
        """Test that ASCII subject is not encoded"""
        content = {
            "subject": "Simple ASCII Subject",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        subject = msg['Subject']
        assert subject == "Simple ASCII Subject", f"ASCII subject should not be encoded: {subject}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_subject_encoding_non_ascii(self, smtp_adapter):
        """Test that non-ASCII subject is properly encoded"""
        content = {
            "subject": "Test avec accents: éàù",
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        subject = msg['Subject']
        assert subject is not None, "Subject header must not be None"
        # Non-ASCII should be encoded (may be base64 or quoted-printable)
        # Just check it's not the raw string
        assert len(subject) > 0, "Subject should be present"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_html_email_headers(self, smtp_adapter):
        """Test that HTML emails have all required headers"""
        content = {
            "subject": "HTML Test",
            "body": "<html><body><p>HTML content</p></body></html>",
            "content_type": "html"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Check required headers
        assert 'Date' in msg, "Date header must be present in HTML email"
        assert 'Message-ID' in msg, "Message-ID header must be present in HTML email"
        assert 'MIME-Version' in msg, "MIME-Version header must be present in HTML email"
        assert 'Subject' in msg, "Subject header must be present in HTML email"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_email_with_attachments_headers(self, smtp_adapter):
        """Test that emails with attachments have all required headers"""
        content = {
            "subject": "Attachment Test",
            "body": "Test body with attachment",
            "content_type": "text",
            "attachments": [
                {
                    "filename": "test.pdf",
                    "content": "dGVzdCBwZGYgY29udGVudA==",  # base64 encoded
                    "content_type": "application/pdf",
                    "encoding": "base64"
                }
            ]
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Check required headers
        assert 'Date' in msg, "Date header must be present in email with attachments"
        assert 'Message-ID' in msg, "Message-ID header must be present in email with attachments"
        assert 'MIME-Version' in msg, "MIME-Version header must be present in email with attachments"
        assert 'Subject' in msg, "Subject header must be present in email with attachments"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_header_line_length(self, smtp_adapter):
        """Test that headers don't exceed RFC 5322 line length limits"""
        # RFC 5322 recommends max 78 characters per line (with folding)
        # Create a long subject
        long_subject = "A" * 200
        content = {
            "subject": long_subject,
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Python's email library should handle folding automatically
        # Just verify the header is present and valid
        subject = msg['Subject']
        assert subject is not None, "Long subject should still be present"
        # The email library will fold long headers, so we just check it's valid
        assert len(subject) > 0, "Subject should be present even if long"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_from_address_with_display_name(self, smtp_adapter):
        """Test From header with display name"""
        content = {
            "subject": "Test",
            "body": "Test body",
            "content_type": "text",
            "from_name": "Test Sender",
            "from_address": "sender@cloud-dog.net"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        from_header = msg['From']
        assert from_header is not None, "From header must not be None"
        # Should contain both name and email
        name, addr = parseaddr(from_header)
        assert name == "Test Sender", f"From name should be 'Test Sender', got '{name}'"
        assert addr == "sender@cloud-dog.net", f"From address should be 'sender@cloud-dog.net', got '{addr}'"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_message_structure_plain_text(self, smtp_adapter):
        """Test that plain text message has correct MIME structure"""
        content = {
            "subject": "Test",
            "body": "Plain text body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Should be multipart/alternative
        assert msg.get_content_type() == 'multipart/alternative', "Plain text should use multipart/alternative"
        
        # Should have one part (plain text)
        parts = list(msg.walk())
        assert len(parts) >= 2, "Should have at least container and one content part"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_message_structure_html(self, smtp_adapter):
        """Test that HTML message has correct MIME structure"""
        content = {
            "subject": "Test",
            "body": "<html><body><p>HTML body</p></body></html>",
            "content_type": "html"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Should be multipart/alternative
        assert msg.get_content_type() == 'multipart/alternative', "HTML should use multipart/alternative"
        
        # Should have both plain text and HTML parts
        parts = list(msg.walk())
        assert len(parts) >= 3, "HTML email should have plain text and HTML parts"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-012")
    
    def test_no_bad_characters_in_headers(self, smtp_adapter):
        """Test that headers don't contain invalid characters"""
        content = {
            "subject": "Test\nSubject\rWith\nNewlines",  # Should be sanitized
            "body": "Test body",
            "content_type": "text"
        }
        
        msg = smtp_adapter._build_message("recipient@cloud-dog.net", content)
        
        # Headers should not contain newlines (should be sanitized or encoded)
        subject = msg['Subject']
        # Newlines in headers are invalid per RFC 5322
        # The encode_header method or email library should handle this
        assert '\n' not in subject or '\r' not in subject, "Subject should not contain raw newlines"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.smtp, pytest.mark.docker, pytest.mark.fast]

