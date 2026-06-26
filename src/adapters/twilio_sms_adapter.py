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
Description: Real Twilio SMS Adapter for SMS Notifications - Implements the ChannelAdapter interface for actual SMS delivery via Twilio Messages API

Related Requirements: FR1.7
Related Tasks: T18
Related Architecture: CC5.1.2
Related Tests: IT1.12

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

import re
import json
import time
import ssl
from typing import Dict, Any, Optional
from httpx import AsyncClient as SharedAsyncHTTPClient, HTTPStatusError

from .base import BaseChannelAdapter, SendResult, ConfirmResult, ErrorClass


class TwilioSMSAdapter(BaseChannelAdapter):
    """
    Real Twilio SMS Adapter for sending SMS via Twilio Messages API.
    
    Configuration:
        base_url: Twilio Messages API endpoint (full URL)
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        from_number: Sender phone number (E.164 format, no whatsapp: prefix)
        timeout: Request timeout in seconds (default 30)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url")
        self.account_sid = config.get("account_sid")
        # Accept legacy/compat aliases used in existing channel config payloads.
        self.auth_token = config.get("auth_token") or config.get("api_key")
        raw_from_number = config.get("from_number") or config.get("sender")
        self.from_number = None
        if raw_from_number is not None:
            normalised_from = str(raw_from_number).strip()
            if normalised_from and not normalised_from.startswith("+") and normalised_from.isdigit():
                normalised_from = f"+{normalised_from}"
            self.from_number = normalised_from or None
        self.timeout = int(config.get("timeout", 30))
        raw_verify_ssl = config.get("verify_ssl", True)  # Allow disabling SSL verification for testing
        if raw_verify_ssl is None:
            raw_verify_ssl = True
        if isinstance(raw_verify_ssl, str):
            lowered = raw_verify_ssl.strip().lower()
            if lowered in {"false", "0", "no", "off"}:
                raw_verify_ssl = False
            elif lowered in {"true", "1", "yes", "on"}:
                raw_verify_ssl = True

        # Optional custom CA bundle path (preferred over boolean verify toggle).
        ca_bundle = config.get("ca_bundle") or config.get("ca_cert") or config.get("certificate")
        self.verify_ssl = raw_verify_ssl
        if ca_bundle:
            ca_path = str(ca_bundle).strip()
            if ca_path:
                try:
                    self.verify_ssl = ssl.create_default_context(cafile=ca_path)
                except Exception:
                    self.verify_ssl = raw_verify_ssl
        # Shared long-lived HTTP client — avoids per-call creation (W28A-93b, AGENT-LESSONS §2.3)
        self._http_client: SharedAsyncHTTPClient | None = None

    def _get_http_client(self) -> SharedAsyncHTTPClient:
        """Return the shared long-lived HTTP client, creating on first use."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = SharedAsyncHTTPClient(
                timeout=self.timeout, verify=self.verify_ssl
            )
        return self._http_client

    async def close(self) -> None:
        """Close the shared HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    @staticmethod
    def _extract_body_text(payload: Any) -> Optional[str]:
        """Normalise payload variants to a plain SMS body string."""
        if payload is None:
            return None

        if isinstance(payload, str):
            text = payload.strip()
            return text if text else None

        if isinstance(payload, dict):
            for key in ("body", "text", "message"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            if "content" in payload:
                return TwilioSMSAdapter._extract_body_text(payload.get("content"))
            return None

        if isinstance(payload, list):
            parts: list[str] = []
            for item in payload:
                part = TwilioSMSAdapter._extract_body_text(item)
                if part:
                    parts.append(part)
            if parts:
                return "\n\n".join(parts).strip()
            return None

        return None
    
    def validate_destination(self, destination: str) -> bool:
        """
        Validate phone number (E.164 format).
        
        E.164 format: +[country code][number]
        Example: +447768116229
        
        Args:
            destination: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        # E.164 regex: + followed by 1-15 digits
        e164_pattern = r'^\+[1-9]\d{1,14}$'
        return bool(re.match(e164_pattern, destination))
    
    async def send(self, delivery: Dict[str, Any]) -> SendResult:
        """
        Send SMS via Twilio Messages API.
        
        Args:
            delivery: Delivery dict with:
                - destination: Recipient phone number (E.164 format)
                - personalised_payload: JSON string or dict with:
                    - body: SMS message text
                
        Returns:
            SendResult with tracking_id (Twilio SID) or error
        """
        destination = delivery.get("destination")
        if not destination:
            return SendResult(
                success=False,
                error="Missing destination",
                error_class=ErrorClass.PERMANENT
            )
        
        if not self.validate_destination(destination):
            return SendResult(
                success=False,
                error=f"Invalid phone number format: {destination}",
                error_class=ErrorClass.PERMANENT
            )
        
        # Parse personalised_payload
        payload = delivery.get("personalised_payload", "{}")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {"body": payload}  # Fallback to plain text
        
        # Prepare Twilio API request
        start_time = time.time()

        missing_config: list[str] = []
        if not self.base_url:
            missing_config.append("base_url")
        if not self.account_sid:
            missing_config.append("account_sid")
        if not self.auth_token:
            missing_config.append("auth_token/api_key")
        if not self.from_number:
            missing_config.append("from_number/sender")
        if missing_config:
            return SendResult(
                success=False,
                error=f"Missing Twilio SMS configuration: {', '.join(missing_config)}",
                error_class=ErrorClass.PERMANENT,
            )
        
        # Build form data
        form_data = {
            "To": destination,
            "From": self.from_number
        }
        
        # Get message body from either dict payloads or formatted content block lists
        message_body = self._extract_body_text(payload)
        if message_body:
            form_data["Body"] = message_body
        else:
            return SendResult(
                success=False,
                error="Missing 'body' in payload",
                error_class=ErrorClass.PERMANENT
            )
        
        try:
            client = self._get_http_client()
            response = await client.post(
                self.base_url,
                data=form_data,
                auth=(self.account_sid, self.auth_token)
            )
            response.raise_for_status()

            result_data = response.json()
            latency_ms = int((time.time() - start_time) * 1000)

            # Twilio returns SID in 'sid' field
            tracking_id = result_data.get("sid")

            return SendResult(
                success=True,
                tracking_id=tracking_id,
                latency_ms=latency_ms
            )

        except HTTPStatusError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_class = self.classify_error(e)

            # Try to extract error message from response
            error_msg = str(e)
            try:
                if e.response:
                    error_data = e.response.json()
                    error_msg = error_data.get("message", str(e))
            except Exception:
                pass

            return SendResult(
                success=False,
                error=error_msg,
                error_class=error_class,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_class = self.classify_error(e)

            return SendResult(
                success=False,
                error=str(e),
                error_class=error_class,
                latency_ms=latency_ms
            )
    
    async def confirm(self, tracking_id: str) -> ConfirmResult:
        """
        Poll Twilio API for message delivery status.
        
        Args:
            tracking_id: Twilio Message SID
            
        Returns:
            ConfirmResult with current status
        """
        if not tracking_id:
            return ConfirmResult(
                status="unknown",
                error="Missing tracking_id"
            )
        
        # Build Twilio API URL for message status
        # Format: https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages/{MessageSid}.json
        api_url = self.base_url.replace("/Messages.json", f"/Messages/{tracking_id}.json")
        
        try:
            client = self._get_http_client()
            response = await client.get(
                api_url,
                auth=(self.account_sid, self.auth_token)
            )
            response.raise_for_status()

            result_data = response.json()
            twilio_status = result_data.get("status", "unknown")

            # Map Twilio status to our internal status
            status = self._map_twilio_status(twilio_status)

            return ConfirmResult(
                status=status,
                timestamp=result_data.get("date_updated")
            )

        except Exception as e:
            return ConfirmResult(
                status="unknown",
                error=str(e)
            )
    
    def parse_callback(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Twilio StatusCallback webhook data.
        
        Args:
            raw_data: Raw callback data from Twilio
            
        Returns:
            Parsed callback dict with message_id, status, destination, etc.
        """
        return {
            "message_id": raw_data.get("MessageSid"),
            "status": self._map_twilio_status(raw_data.get("MessageStatus", "unknown")),
            "destination": raw_data.get("To"),
            "from": raw_data.get("From"),
            "timestamp": raw_data.get("DateSent") or raw_data.get("Timestamp"),
            "error_code": raw_data.get("ErrorCode"),
            "error_message": raw_data.get("ErrorMessage"),
            "raw_data": raw_data
        }
    
    def classify_error(self, error: Exception) -> ErrorClass:
        """
        Classify Twilio API errors as transient or permanent.
        
        Transient: Rate limits (429, 20429), server errors (5xx), network issues
        Permanent: Invalid numbers (21211), unsubscribed (21610), auth errors (401, 20003)
        
        Args:
            error: Exception that occurred
            
        Returns:
            ErrorClass indicating retry strategy
        """
        # Network/connection errors = transient
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorClass.TRANSIENT
        
        # HTTP errors
        if isinstance(error, HTTPStatusError):
            status_code = error.response.status_code if error.response else 0
            
            # Rate limit (429) = transient
            if status_code == 429:
                return ErrorClass.TRANSIENT
            
            # Server errors (5xx) = transient
            if 500 <= status_code < 600:
                return ErrorClass.TRANSIENT
            
            # Try to extract Twilio error code from response
            try:
                if error.response:
                    error_data = error.response.json()
                    twilio_code = error_data.get("code")
                    
                    # Twilio error codes that are permanent
                    permanent_codes = [
                        21211,  # Invalid 'To' Phone Number
                        21610,  # Unsubscribed recipient
                        20003,  # Authenticate
                        20008,  # Unknown destination number
                        21408,  # Permission to send an SMS has not been enabled
                    ]
                    
                    if twilio_code in permanent_codes:
                        return ErrorClass.PERMANENT
            except Exception:
                pass
            
            # Auth errors (401) = permanent
            if status_code == 401:
                return ErrorClass.PERMANENT
            
            # Client errors (4xx except 429) = permanent
            if 400 <= status_code < 500:
                return ErrorClass.PERMANENT
        
        # Default to transient (can retry)
        return ErrorClass.TRANSIENT
    
    def _map_twilio_status(self, twilio_status: str) -> str:
        """
        Map Twilio message status to our internal delivery states.
        
        Args:
            twilio_status: Twilio status string
            
        Returns:
            Internal status string
        """
        status_map = {
            "queued": "queued",
            "sending": "sending",
            "sent": "sent",
            "delivered": "delivered",
            "undelivered": "hard_failed",
            "failed": "hard_failed"
        }
        return status_map.get(twilio_status.lower(), "unknown")
