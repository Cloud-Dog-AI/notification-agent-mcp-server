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
Description: Real Chat/REST Adapter for Webhook Notifications - Implements the ChannelAdapter interface for generic webhook/REST notifications (Slack, Discord, Teams, custom webhooks)

Related Requirements: FR1.8
Related Tasks: T19
Related Architecture: CC5.1.3
Related Tests: UT1.4, IT1.12, IT1.13

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import asyncio
import re
from typing import Dict, Any
from urllib.parse import urlparse
from httpx import (
    AsyncClient as SharedAsyncHTTPClient,
    ConnectError as HTTPConnectError,
    HTTPStatusError,
    TimeoutException as HTTPTimeoutException,
)

from .base import ChannelAdapter, SendResult


class ChatAdapter(ChannelAdapter):
    """
    Real Chat/REST Adapter for sending notifications via webhooks.
    
    Configuration:
        endpoint: Webhook URL
        auth_type: Authentication type ('none', 'bearer', 'api_key', 'basic')
        token: Bearer token or API key
        api_key_header: Header name for API key (default: 'X-API-Key')
        username: Basic auth username
        password: Basic auth password
        timeout: Request timeout in seconds (default: 30)
        retry_count: Number of retries (default: 3)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.endpoint = config.get("endpoint")
        self.auth_type = config.get("auth_type", "none")
        self.token = config.get("token")
        self.api_key_header = config.get("api_key_header", "X-API-Key")
        self.username = config.get("username")
        self.password = config.get("password")
        self.timeout = int(config.get("timeout", 30))
        self.retry_count = int(config.get("retry_count", 3))
        # Shared long-lived HTTP client — avoids per-call creation (W28A-93b, AGENT-LESSONS §2.3)
        self._http_client: SharedAsyncHTTPClient | None = None

    def _get_http_client(self) -> SharedAsyncHTTPClient:
        """Return the shared long-lived HTTP client, creating on first use."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = SharedAsyncHTTPClient(timeout=self.timeout)
        return self._http_client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate webhook URL.
        
        Args:
            destination: Webhook URL to validate
            
        Returns:
            True if valid HTTPS URL, False otherwise
        """
        try:
            parsed = urlparse(destination)
            # Webhook destinations must be HTTPS with a host.
            return parsed.scheme == "https" and bool(parsed.netloc)
        except Exception:
            return False
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """
        Send notification via webhook POST request.
        
        Args:
            delivery: Delivery dict with:
                - destination: Webhook URL
                - personalised_payload: JSON string or dict with content
                - OR text, format, title, fields directly
                
        Returns:
            SendResult with success status and tracking_id
        """
        from .base import SendResult, ErrorClass
        import time
        
        start_time = time.time()
        
        destination = delivery.get("destination")
        if not destination or not self.validate_destination(destination):
            return SendResult(
                success=False,
                error=f'Invalid webhook URL: {destination}',
                error_class=ErrorClass.PERMANENT,
                latency_ms=int((time.time() - start_time) * 1000)
            )
        
        try:
            # Extract content from delivery
            content = self._extract_content(delivery)
            
            # Build payload based on format
            payload = self._build_payload(content)
            
            # Build headers
            headers = self._build_headers()
            
            # Send with retries using shared long-lived client
            client = self._get_http_client()
            for attempt in range(self.retry_count):
                try:
                    response = await client.post(
                        destination,
                        json=payload,
                        headers=headers
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if response.status_code < 400:
                        tracking_id = response.headers.get('X-Request-Id', f'webhook-{id(response)}')
                        return SendResult(
                            success=True,
                            tracking_id=tracking_id,
                            latency_ms=latency_ms
                        )
                    else:
                        # HTTP error
                        error_class = self.classify_http_error(response.status_code)
                        error_class_enum = ErrorClass.PERMANENT if error_class == "permanent" else ErrorClass.TRANSIENT

                        if error_class == "permanent":
                            # Don't retry permanent errors
                            return SendResult(
                                success=False,
                                error=f'HTTP {response.status_code}: {response.text}',
                                error_class=error_class_enum,
                                latency_ms=latency_ms
                            )
                        # Else retry transient errors
                        if attempt == self.retry_count - 1:
                            # Last attempt failed
                            return SendResult(
                                success=False,
                                error=f'HTTP {response.status_code}: {response.text}',
                                error_class=error_class_enum,
                                latency_ms=latency_ms
                            )

                except (HTTPConnectError, HTTPTimeoutException) as e:
                    # Network errors - retry
                    if attempt == self.retry_count - 1:
                        # Last attempt failed
                        latency_ms = int((time.time() - start_time) * 1000)
                        return SendResult(
                            success=False,
                            error=f'Network error after {self.retry_count} attempts: {e}',
                            error_class=ErrorClass.TRANSIENT,
                            latency_ms=latency_ms
                        )
                    # Wait before retry
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

            # All retries exhausted
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error=f'Failed after {self.retry_count} attempts',
                error_class=ErrorClass.TRANSIENT,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error=str(e),
                error_class=ErrorClass.TRANSIENT,
                latency_ms=latency_ms
            )
    
    def _extract_content(self, delivery: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content from delivery dict"""
        import json
        import html
        import re
        
        # Try to get from personalised_payload
        payload_str = delivery.get("personalised_payload")
        if payload_str:
            try:
                if isinstance(payload_str, str):
                    payload_data = json.loads(payload_str)
                else:
                    payload_data = payload_str
                
                # Check if it's already in the right format (dict with text/format)
                if isinstance(payload_data, dict):
                    if "text" in payload_data:
                        return {
                            "text": payload_data["text"],
                            "format": payload_data.get("format", "slack"),
                            "title": payload_data.get("title", ""),
                        }
                
                # Check if it's content blocks format (list of dicts)
                if isinstance(payload_data, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in payload_data:
                        if isinstance(block, dict):
                            block_type = block.get('type', 'text')
                            block_body = block.get('body', '')
                            
                            if block_type in ['text', 'markdown', 'html']:
                                # Convert HTML to plain text for Slack
                                if block_type == 'html':
                                    block_body = re.sub(r'<!doctype[^>]*>', '', block_body, flags=re.I)
                                    block_body = re.sub(r'<(script|style|head)\b[^>]*>.*?</\1>', '', block_body, flags=re.I | re.S)
                                    block_body = re.sub(r'<br\s*/?>', '\n', block_body, flags=re.I)
                                    block_body = re.sub(r'</(h1|h2|h3|h4|p|li|div)>', '\n', block_body, flags=re.I)
                                    block_body = re.sub(r'<(h1|h2|h3|h4|p|li|div)\b[^>]*>', '\n', block_body, flags=re.I)
                                    block_body = re.sub(r'<[^>]+>', '', block_body)
                                block_body = html.unescape(block_body)
                                text_parts.append(block_body)
                    
                    text = '\n'.join(text_parts).strip()
                    if text:
                        return {
                            "text": text,
                            "format": "slack",
                        }
            
            except (json.JSONDecodeError, TypeError):
                # If parsing fails, try to use as plain text
                if payload_str and isinstance(payload_str, str):
                    return {
                        "text": payload_str,
                        "format": "slack",
                    }
        
        # Fallback: use delivery dict directly
        return {
            "text": delivery.get("text", ""),
            "title": delivery.get("title", ""),
            "format": delivery.get("format", "slack"),
            "fields": delivery.get("fields", {}),
        }
    
    def _build_payload(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Build webhook payload based on format."""
        format_type = content.get('format', 'slack')  # Default to slack
        text = content.get('text', '')
        title = content.get('title', '')
        fields = content.get('fields', {})

        def _strip_duplicate_leading_title(value: str, heading: str) -> str:
            if not value or not heading:
                return value
            lines = value.splitlines()
            while lines and not lines[0].strip():
                lines.pop(0)
            if not lines:
                return value
            first = lines[0].strip()
            normalized_first = re.sub(r"^[*_`~]+|[*_`~]+$", "", first).strip()
            normalized_first = re.sub(r"\s+", " ", normalized_first)
            normalized_heading = re.sub(r"\s+", " ", str(heading).strip())
            if normalized_first == normalized_heading:
                return "\n".join(lines[1:]).lstrip()
            return value
        
        if format_type == 'slack':
            # Slack webhook format - simple text payload
            # Slack webhooks accept simple {"text": "message"} format
            # Slack has a 4000 character limit for the text field
            # If text is too long, truncate it
            max_text_length = 4000
            if len(text) > max_text_length:
                text = text[:max_text_length - 3] + "..."
            
            payload = {
                "text": text
            }
            section_text = _strip_duplicate_leading_title(text, title)
            
            # Only add blocks if text is reasonable length (blocks have their own limits)
            # For very long text, just use simple text format (no blocks)
            if len(text) <= 3000 and (title or len(text) > 100):
                blocks = []
                if title:
                    blocks.append({
                        "type": "header",
                        "text": {"type": "plain_text", "text": title[:150]}  # Header text limit
                    })
                # Only add section block if text fits
                if len(section_text) <= 3000 and section_text:
                    blocks.append({
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": section_text[:3000]}  # Section text limit
                    })
                if blocks:
                    payload["blocks"] = blocks
            
            return payload
        elif format_type == 'discord':
            return {
                "content": text,
                "embeds": [
                    {
                        "title": title,
                        "description": text,
                        "fields": [{"name": k, "value": v} for k, v in fields.items()]
                    }
                ] if title else []
            }
        elif format_type == 'teams':
            return {
                "@type": "MessageCard",
                "title": title,
                "text": text
            }
        else:  # generic
            return {
                "title": title,
                "message": text,
                "fields": fields
            }
    
    def _build_headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        
        if self.auth_type == "bearer" and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.auth_type == "api_key" and self.token:
            headers[self.api_key_header] = self.token
        # Basic auth handled by the shared HTTP client.
        
        return headers
    
    def classify_error(self, error: Any) -> str:
        """
        Classify webhook errors as transient or permanent.
        
        Args:
            error: Exception or error object
            
        Returns:
            'transient' or 'permanent'
        """
        if isinstance(error, HTTPStatusError):
            return self.classify_http_error(error.response.status_code)
        
        # Network errors = transient
        if isinstance(error, (HTTPConnectError, HTTPTimeoutException)):
            return "transient"
        
        # Default to transient
        return "transient"
    
    def classify_http_error(self, status_code: int) -> str:
        """
        Classify HTTP status codes.
        
        Transient:
        - 429 (Too Many Requests)
        - 5xx (Server errors)
        - 408 (Request Timeout)
        
        Permanent:
        - 4xx (Client errors) except 429 and 408
        
        Args:
            status_code: HTTP status code
            
        Returns:
            'transient' or 'permanent'
        """
        if status_code in [429, 408]:
            return "transient"
        elif 500 <= status_code < 600:
            return "transient"
        elif 400 <= status_code < 500:
            return "permanent"
        else:
            return "transient"
    
    async def confirm(self, provider_id: str) -> Dict[str, Any]:
        """
        Webhooks don't provide delivery confirmation.
        
        Args:
            provider_id: Request ID from send operation
            
        Returns:
            Status dict (always unknown)
        """
        return {
            "status": "unknown",
            "note": "Webhooks do not provide delivery confirmation"
        }
    
    def parse_callback(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse webhook callback (if the service supports it).
        
        Args:
            callback_data: Raw callback data
            
        Returns:
            Parsed callback dict
        """
        return {
            "message_id": callback_data.get("message_id"),
            "status": callback_data.get("status", "unknown"),
            "timestamp": callback_data.get("timestamp"),
            "raw_data": callback_data
        }
