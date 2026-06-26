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
Description: Real SMTP Adapter for Email Notifications - Implements the ChannelAdapter interface for actual SMTP email delivery

Related Requirements: FR1.6
Related Tasks: T17
Related Architecture: CC5.1.1
Related Tests: UT1.4, IT1.12, AT1.1

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import asyncio
import imaplib
from datetime import datetime, timezone
from email import message_from_bytes
from typing import Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, parseaddr, formatdate, make_msgid, parsedate_to_datetime
from email.header import Header
import aiosmtplib
from aiosmtplib import SMTPException
from email_validator import validate_email, EmailNotValidError
import socket

from .base import ChannelAdapter, SendResult, ConfirmResult, ErrorClass
from src.config import get_config


class SMTPAdapter(ChannelAdapter):
    """
    Real SMTP Adapter for sending emails via SMTP servers.
    
    Configuration:
        host: SMTP server hostname
        port: SMTP server port (default 25)
        username: SMTP authentication username
        password: SMTP authentication password
        from_address: Default from address (can include display name)
        use_tls: Whether to use TLS (default False)
        use_starttls: Whether to use STARTTLS (default True)
        timeout: Connection timeout in seconds (default 30)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.host = self._require_config(config.get("host"), "channels.smtp.default.host")
        self.port = int(self._require_config(config.get("port"), "channels.smtp.default.port"))
        self.username = config.get("username")
        self.password = config.get("password")
        self.from_address = self._require_config(config.get("from_address"), "channels.smtp.default.from_address")
        self.use_tls = self._parse_bool(self._require_config(config.get("use_tls"), "channels.smtp.default.use_tls"))
        self.use_starttls = self._parse_bool(self._require_config(config.get("use_starttls"), "channels.smtp.default.use_starttls"))
        self.timeout = int(self._require_config(config.get("timeout"), "channels.smtp.default.timeout"))
        runtime_config = get_config()
        self.imap_host = str(config.get("imap_host") or runtime_config.get("email.imap.default.host") or "").strip()
        self.imap_port = int(config.get("imap_port") or runtime_config.get("email.imap.default.port") or 993)
        self.imap_username = str(config.get("imap_username") or runtime_config.get("email.imap.default.username") or "").strip()
        self.imap_password = str(config.get("imap_password") or runtime_config.get("email.imap.default.password") or "").strip()
        self.imap_use_tls = self._parse_bool(
            config.get("imap_use_tls")
            if config.get("imap_use_tls") is not None
            else runtime_config.get("email.imap.default.use_tls", True)
        )
        self.imap_use_starttls = self._parse_bool(
            config.get("imap_use_starttls")
            if config.get("imap_use_starttls") is not None
            else runtime_config.get("email.imap.default.use_starttls", False)
        )
        self.imap_mailbox = str(config.get("imap_mailbox") or runtime_config.get("email.imap.default.mailbox") or "INBOX")
        self.confirmation_timeout = float(
            config.get("confirmation_timeout")
            or runtime_config.get("email.imap.default.poll_timeout_seconds")
            or 60
        )
        self.confirmation_poll_interval = float(
            config.get("confirmation_poll_interval")
            or runtime_config.get("email.imap.default.poll_interval_seconds")
            or 5
        )

    @staticmethod
    def _parse_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        return bool(value)

    @staticmethod
    def _require_config(value, key: str):
        if value is None or value == "":
            raise RuntimeError(f"Missing required configuration: {key}")
        return value
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate email address using RFC 5322 validation.
        
        Args:
            destination: Email address to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Use email-validator library for RFC 5322 compliance
            validate_email(destination, check_deliverability=False)
            return True
        except EmailNotValidError:
            return False
    
    async def test_connection(self) -> Any:
        """
        Test connection to SMTP server.
        
        Returns:
            Result object with success status
        """
        try:
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                timeout=self.timeout,
                use_tls=self.use_tls
            ) as smtp:
                if self.use_starttls and not self.use_tls:
                    await smtp.starttls()
                
                return type('Result', (), {
                    'success': True,
                    'message': 'Connection successful'
                })()
        except Exception as e:
            return type('Result', (), {
                'success': False,
                'error': str(e)
            })()
    
    async def test_authentication(self) -> Any:
        """
        Test authentication with SMTP server.
        
        Returns:
            Result object with success status
        """
        try:
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                timeout=self.timeout,
                use_tls=self.use_tls
            ) as smtp:
                if self.use_starttls and not self.use_tls:
                    await smtp.starttls()
                
                if self.username and self.password:
                    await smtp.login(self.username, self.password)
                
                return type('Result', (), {
                    'success': True,
                    'message': 'Authentication successful'
                })()
        except Exception as e:
            return type('Result', (), {
                'success': False,
                'error': str(e)
            })()
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """
        Send an email via SMTP.
        
        Args:
            delivery: Delivery dict with:
                - destination: Recipient email address
                - personalised_payload: Email content (JSON string or dict)
                - OR subject, body, content_type directly
                
        Returns:
            SendResult with success status and tracking_id (message ID)
        """
        start_time = asyncio.get_event_loop().time()
        
        destination = delivery.get("destination")
        if not destination or not self.validate_destination(destination):
            return SendResult(
                success=False,
                error=f'Invalid email address: {destination}',
                error_class=ErrorClass.PERMANENT,
                latency_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        
        try:
            # Extract content from delivery
            content = self._extract_content(delivery)
            
            # Build email message
            msg = self._build_message(destination, content)
            
            # Connect and send
            async with aiosmtplib.SMTP(
                hostname=self.host,
                port=self.port,
                timeout=self.timeout,
                use_tls=self.use_tls
            ) as smtp:
                # Start TLS if configured
                if self.use_starttls and not self.use_tls:
                    await smtp.starttls()
                
                # Authenticate if credentials provided and supported
                if self.username and self.password:
                    try:
                        await smtp.login(self.username, self.password)
                    except SMTPException as auth_error:
                        # Some servers don't support AUTH, continue without it
                        if "AUTH" not in str(auth_error):
                            raise  # Re-raise if not an AUTH issue
                
                # Send message
                await smtp.send_message(msg)
                
                # Extract message ID from response or headers
                message_id = msg.get('Message-ID', f'smtp-{id(msg)}')
                
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                
                return SendResult(
                    success=True,
                    tracking_id=message_id,
                    latency_ms=latency_ms
                )
                
        except SMTPException as e:
            error_class = ErrorClass.TRANSIENT if self.classify_error(e) == "transient" else ErrorClass.PERMANENT
            return SendResult(
                success=False,
                error=str(e),
                error_class=error_class,
                latency_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
        except Exception as e:
            error_class = ErrorClass.TRANSIENT if self.classify_error(e) == "transient" else ErrorClass.PERMANENT
            return SendResult(
                success=False,
                error=str(e),
                error_class=error_class,
                latency_ms=int((asyncio.get_event_loop().time() - start_time) * 1000)
            )
    
    def _extract_content(self, delivery: Dict[str, Any]) -> Dict[str, Any]:
        """Extract email content from delivery record."""
        import json
        
        # Try to parse personalised_payload if it's a JSON string
        payload = delivery.get("personalised_payload")
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                # Treat as plain text body
                return {"body": payload, "subject": delivery.get("subject", "(No Subject)")}
        elif isinstance(payload, dict):
            return payload
        else:
            # Build from individual fields
            return {
                "subject": delivery.get("subject", "(No Subject)"),
                "body": delivery.get("body", ""),
                "content_type": delivery.get("content_type", "text")
            }
    
    def _build_message(self, destination: str, content: Dict[str, Any]) -> MIMEMultipart:
        """
        Build MIME message from content dict.
        
        Args:
            destination: Recipient email address
            content: Content dictionary
            
        Returns:
            MIMEMultipart message object
        """
        subject = content.get('subject', '(No Subject)')
        body = content.get('body', '')
        content_type = content.get('content_type', 'text')
        from_address = content.get('from_address', self.from_address)
        from_name = content.get('from_name')
        
        # Parse from address to get name and email
        if from_name:
            from_header = formataddr((from_name, from_address))
        else:
            # Try to parse name from from_address if it includes one
            name, addr = parseaddr(from_address)
            from_header = formataddr((name, addr)) if name else addr
        
        # Create message
        # Determine if content is HTML (check content_type or detect HTML tags)
        is_html = content_type == 'html' or (content_type != 'plain' and '<' in body and '>' in body and any(tag in body for tag in ['<p>', '<h', '<ul>', '<li>', '<div>', '<br>']))
        
        # Check if we have attachments
        attachments = content.get('attachments', [])
        
        # If we have attachments, use 'mixed' multipart, otherwise 'alternative'
        if attachments:
            # Mixed multipart for body + attachments
            msg = MIMEMultipart('mixed')
            # Set required RFC 5322 headers with proper encoding
            # Note: MIMEMultipart automatically adds MIME-Version, so don't set it explicitly
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=self._get_domain())
            # Only set MIME-Version if not already present (MIMEMultipart may add it)
            if 'MIME-Version' not in msg:
                msg['MIME-Version'] = '1.0'
            msg['Subject'] = self._encode_header(subject)
            msg['From'] = from_header
            msg['To'] = destination
            
            # Create body part (alternative for HTML/text)
            body_msg = MIMEMultipart('alternative')
            
            if is_html:
                # Create plain text version (strip HTML tags)
                import re
                plain_body = re.sub(r'<[^>]+>', '', body)
                plain_body = re.sub(r'\n\s*\n', '\n\n', plain_body)  # Clean up extra whitespace
                
                # Attach plain text version first
                part1 = MIMEText(plain_body, 'plain', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part1:
                    del part1['MIME-Version']
                body_msg.attach(part1)
                
                # Attach HTML version
                part2 = MIMEText(body, 'html', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part2:
                    del part2['MIME-Version']
                body_msg.attach(part2)
            else:
                part = MIMEText(body, 'plain', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part:
                    del part['MIME-Version']
                body_msg.attach(part)
            
            # Attach body to main message
            msg.attach(body_msg)
            
            # Attach files
            from email.mime.base import MIMEBase
            from email import encoders
            
            for attachment in attachments:
                filename = attachment.get('filename', 'attachment.txt')
                attach_content = attachment.get('content', '')
                attach_content_type = attachment.get('content_type', 'text/plain')
                encoding = attachment.get('encoding', 'utf-8')  # Support base64 encoding for PDFs
                
                # Create attachment
                if encoding == 'base64':
                    # For base64-encoded content (e.g., PDFs)
                    import base64
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(base64.b64decode(attach_content))
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    part.add_header('Content-Type', attach_content_type)
                    msg.attach(part)
                else:
                    # For text content (original behavior)
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attach_content.encode('utf-8'))
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {filename}'
                    )
                    if attach_content_type:
                        part.add_header('Content-Type', attach_content_type)
                    msg.attach(part)
        else:
            # No attachments - use alternative multipart
            if is_html:
                # HTML email - use MIMEMultipart with both HTML and plain text alternatives
                msg = MIMEMultipart('alternative')
                # Set required RFC 5322 headers with proper encoding
                # Note: MIMEMultipart automatically adds MIME-Version, so don't set it explicitly
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid(domain=self._get_domain())
                # Only set MIME-Version if not already present (MIMEMultipart may add it)
                if 'MIME-Version' not in msg:
                    msg['MIME-Version'] = '1.0'
                msg['Subject'] = self._encode_header(subject)
                msg['From'] = from_header
                msg['To'] = destination
                
                # Create plain text version (strip HTML tags)
                import re
                plain_body = re.sub(r'<[^>]+>', '', body)
                plain_body = re.sub(r'\n\s*\n', '\n\n', plain_body)  # Clean up extra whitespace
                
                # Attach plain text version first
                part1 = MIMEText(plain_body, 'plain', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part1:
                    del part1['MIME-Version']
                msg.attach(part1)
                
                # Attach HTML version
                part2 = MIMEText(body, 'html', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part2:
                    del part2['MIME-Version']
                msg.attach(part2)
            else:
                # Plain text email
                msg = MIMEMultipart('alternative')
                # Set required RFC 5322 headers with proper encoding
                # Note: MIMEMultipart automatically adds MIME-Version, so don't set it explicitly
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid(domain=self._get_domain())
                # Only set MIME-Version if not already present (MIMEMultipart may add it)
                if 'MIME-Version' not in msg:
                    msg['MIME-Version'] = '1.0'
                msg['Subject'] = self._encode_header(subject)
                msg['From'] = from_header
                msg['To'] = destination
                
                part = MIMEText(body, 'plain', 'utf-8')
                # Remove MIME-Version from part (already on main message)
                if 'MIME-Version' in part:
                    del part['MIME-Version']
                msg.attach(part)
        
        return msg
    
    def _encode_header(self, value: str) -> str:
        """
        Encode header value according to RFC 2047 if it contains non-ASCII characters.
        Also sanitizes invalid characters (newlines, etc.) per RFC 5322.
        
        Args:
            value: Header value to encode
            
        Returns:
            Encoded header value
        """
        if not value:
            return value
        
        # Sanitize: Remove or replace invalid characters per RFC 5322
        # Headers cannot contain unencoded newlines, carriage returns, or null bytes
        sanitized = value.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ').replace('\0', '')
        # Collapse multiple spaces
        sanitized = ' '.join(sanitized.split())
        
        try:
            # Check if value contains non-ASCII characters
            sanitized.encode('ascii')
            # All ASCII - return sanitized
            return sanitized
        except UnicodeEncodeError:
            # Contains non-ASCII - encode using Header class
            header = Header(sanitized, 'utf-8')
            return str(header)
    
    def _get_domain(self) -> str:
        """
        Get domain name for Message-ID generation.
        
        Returns:
            Domain name (from hostname or config)
        """
        try:
            # Try to get domain from from_address
            if self.from_address:
                _, addr = parseaddr(self.from_address)
                if '@' in addr:
                    return addr.split('@')[1]
        except Exception:
            pass
        
        try:
            # Fallback to hostname
            hostname = socket.getfqdn()
            if hostname:
                return hostname
        except Exception:
            pass
        raise RuntimeError("Missing required configuration: channels.smtp.default.from_address (domain)")
    
    def classify_error(self, error: Exception) -> ErrorClass:
        """
        Classify SMTP errors as transient or permanent.
        
        SMTP error codes:
        - 4xx: Transient failures (temporary, retry possible)
          - 421: Service not available
          - 450: Mailbox unavailable
          - 451: Action aborted (local error)
          - 452: Insufficient storage
        - 5xx: Permanent failures (don't retry)
          - 550: Mailbox not found
          - 551: User not local
          - 552: Exceeded storage allocation
          - 553: Mailbox name not allowed
          - 554: Transaction failed
        
        Args:
            error: Exception or error object
            
        Returns:
            ErrorClass.TRANSIENT or ErrorClass.PERMANENT
        """
        if isinstance(error, SMTPException):
            # Get SMTP status code
            if hasattr(error, 'code'):
                code = error.code
                if isinstance(code, int):
                    # 4xx = transient, 5xx = permanent
                    if 400 <= code < 500:
                        return ErrorClass.TRANSIENT
                    elif 500 <= code < 600:
                        return ErrorClass.PERMANENT
            
            # Check error message for codes
            error_str = str(error)
            if any(code in error_str for code in ['421', '450', '451', '452']):
                return ErrorClass.TRANSIENT
            elif any(code in error_str for code in ['550', '551', '552', '553', '554']):
                return ErrorClass.PERMANENT
        
        # Connection errors, timeouts, etc = transient
        if isinstance(error, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return ErrorClass.TRANSIENT
        
        # Authentication errors = permanent
        error_str = str(error).lower()
        if any(term in error_str for term in ['auth', 'login', 'password', 'credentials']):
            return ErrorClass.PERMANENT
        
        # Default to transient (can retry)
        return ErrorClass.TRANSIENT
    
    async def confirm(self, tracking_id: str) -> ConfirmResult:
        """
        Confirm delivery status by checking the recipient mailbox via IMAP.
        
        Args:
            tracking_id: Message ID from send operation
            
        Returns:
            ConfirmResult with current status
        """
        if not tracking_id:
            return ConfirmResult(status="unknown", error="Missing SMTP tracking ID")
        if not (self.imap_host and self.imap_username and self.imap_password):
            return ConfirmResult(
                status="unknown",
                error="Missing IMAP confirmation configuration for SMTP delivery tracking",
            )

        deadline = asyncio.get_event_loop().time() + max(self.confirmation_timeout, 1.0)
        while True:
            delivered_at = await asyncio.to_thread(self._check_mailbox_for_message, tracking_id)
            if delivered_at:
                return ConfirmResult(status="delivered", timestamp=delivered_at)
            if asyncio.get_event_loop().time() >= deadline:
                return ConfirmResult(
                    status="sent",
                    error=f"Message-ID {tracking_id} not observed in {self.imap_mailbox} within {self.confirmation_timeout:.0f}s",
                )
            await asyncio.sleep(max(self.confirmation_poll_interval, 1.0))

    @staticmethod
    def _normalise_message_id(value: str) -> str:
        return str(value or "").strip().strip("<>")

    def _check_mailbox_for_message(self, tracking_id: str) -> str | None:
        client: imaplib.IMAP4 | imaplib.IMAP4_SSL | None = None
        try:
            if self.imap_use_tls:
                client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            else:
                client = imaplib.IMAP4(self.imap_host, self.imap_port)
                if self.imap_use_starttls and hasattr(client, "starttls"):
                    client.starttls()

            client.login(self.imap_username, self.imap_password)
            status, _ = client.select(self.imap_mailbox, readonly=True)
            if status != "OK":
                return None

            status, data = client.search(None, "HEADER", "Message-ID", tracking_id)
            message_ids = data[0].split() if status == "OK" and data and data[0] else []
            if not message_ids:
                status, data = client.search(None, "ALL")
                all_ids = data[0].split() if status == "OK" and data and data[0] else []
                message_ids = all_ids[-25:]

            wanted = self._normalise_message_id(tracking_id)
            for message_id in reversed(message_ids):
                fetch_status, msg_data = client.fetch(message_id, "(BODY.PEEK[HEADER.FIELDS (DATE MESSAGE-ID)])")
                if fetch_status != "OK" or not msg_data:
                    continue
                header_bytes = None
                for item in msg_data:
                    if isinstance(item, tuple) and len(item) == 2:
                        header_bytes = item[1]
                        break
                if not header_bytes:
                    continue
                msg = message_from_bytes(header_bytes)
                mailbox_message_id = self._normalise_message_id(msg.get("Message-ID"))
                if mailbox_message_id != wanted:
                    continue
                date_header = msg.get("Date")
                if date_header:
                    try:
                        return parsedate_to_datetime(date_header).astimezone(timezone.utc).isoformat()
                    except Exception:
                        pass
                return datetime.now(timezone.utc).isoformat()
            return None
        finally:
            if client is not None:
                try:
                    client.logout()
                except Exception:
                    pass

    def parse_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse delivery callback/webhook data.
        
        For SMTP, this would typically be:
        1. Bounce emails (parse from mailbox)
        2. DSN (Delivery Status Notification) messages
        3. Third-party service webhooks (SendGrid, SES, etc.)
        
        Args:
            callback_data: Raw callback data
            
        Returns:
            Parsed callback dict with status, message_id, etc.
        """
        # Basic DSN parsing
        return {
            "message_id": callback_data.get("message_id"),
            "status": callback_data.get("status", "unknown"),
            "recipient": callback_data.get("recipient"),
            "timestamp": callback_data.get("timestamp"),
            "raw_data": callback_data
        }
