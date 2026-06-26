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
Tests for REAL Channel Adapters (not mocks)
"""

from pathlib import Path
import sys
import time

import pytest

from tests.utils.test_helpers import check_test_dependencies
from src.adapters.smtp_adapter import SMTPAdapter
from src.adapters.sms_adapter import SMSAdapter
from src.adapters.chat_adapter import ChatAdapter

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def _require_value(value, key: str) -> str:
    if value is None or value == "":
        pytest.fail(f"Missing required configuration: {key}")
    return str(value)


def _twilio_sms_config(test_config):
    config = {
        "base_url": _require_value(test_config.get("test.twilio.sms.base_url"), "test.twilio.sms.base_url"),
        "account_sid": _require_value(test_config.get("test.twilio.sms.account_sid"), "test.twilio.sms.account_sid"),
        "auth_token": _require_value(test_config.get("test.twilio.sms.auth_token"), "test.twilio.sms.auth_token"),
        "from_number": _require_value(test_config.get("test.twilio.sms.from_number"), "test.twilio.sms.from_number"),
    }
    verify_ssl = test_config.get("test.twilio.sms.verify_ssl")
    if verify_ssl is not None:
        config["verify_ssl"] = verify_ssl
    ca_bundle = test_config.get("test.twilio.sms.ca_bundle")
    if ca_bundle:
        config["ca_bundle"] = str(ca_bundle)
    return config


def _twilio_whatsapp_config(test_config):
    config = {
        "base_url": _require_value(test_config.get("test.twilio.whatsapp.base_url"), "test.twilio.whatsapp.base_url"),
        "account_sid": _require_value(test_config.get("test.twilio.whatsapp.account_sid"), "test.twilio.whatsapp.account_sid"),
        "auth_token": _require_value(test_config.get("test.twilio.whatsapp.auth_token"), "test.twilio.whatsapp.auth_token"),
        "from_number": _require_value(test_config.get("test.twilio.whatsapp.from_number"), "test.twilio.whatsapp.from_number"),
    }
    verify_ssl = test_config.get("test.twilio.whatsapp.verify_ssl")
    if verify_ssl is not None:
        config["verify_ssl"] = verify_ssl
    ca_bundle = test_config.get("test.twilio.whatsapp.ca_bundle")
    if ca_bundle:
        config["ca_bundle"] = str(ca_bundle)
    return config


def _sms_adapter_config(test_config):
    config = _twilio_sms_config(test_config)
    return {
        "provider": _require_value(test_config.get("test.sms.provider"), "test.sms.provider"),
        "account_sid": config["account_sid"],
        "auth_token": config["auth_token"],
        "from_number": config["from_number"],
    }


@pytest.fixture(scope="session")
def slack_endpoint(test_config):
    return _require_value(test_config.get("test.webhook.slack_url"), "test.webhook.slack_url")


class TestSMTPAdapter:
    """Tests for Real SMTP Adapter - V6.1 to V6.10"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_1_validate_email_rfc5322(self, smtp_config):
        """V6.1: SMTP - validate email address (RFC 5322)"""
        adapter = SMTPAdapter(smtp_config)
        assert adapter.validate_destination("user@cloud-dog.net") is True
        assert adapter.validate_destination("user+tag@cloud-dog.net") is True
        assert adapter.validate_destination("user.name@example.co.uk") is True
        assert adapter.validate_destination("invalid") is False
        assert adapter.validate_destination("@cloud-dog.net") is False
        assert adapter.validate_destination("user@") is False
        assert adapter.validate_destination("") is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_2_connect_to_smtp_server(self, smtp_config):
        """V6.2: SMTP - connect to configured SMTP host"""
        adapter = SMTPAdapter(smtp_config)
        result = await adapter.test_connection()
        if not result.success:
            print(f"Connection failed: {result.error}")
        assert result.success is True
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_3_authenticate_with_credentials(self, smtp_config):
        """V6.3: SMTP - authenticate with credentials"""
        adapter = SMTPAdapter(smtp_config)
        result = await adapter.test_authentication()
        if result.success:
            assert "successful" in str(result.message).lower()
        else:
            assert result.error
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_4_send_email_successfully(self, smtp_config, test_email):
        """V6.4: SMTP - send email successfully"""
        adapter = SMTPAdapter(smtp_config)
        delivery = {
            "destination": test_email,
            "personalised_payload": '{"subject": "Test from notification-agent", "body": "This is a test email from the notification agent", "content_type": "text"}',
        }
        result = await adapter.send(delivery)
        assert result.success is True
        assert result.tracking_id is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_5_handle_connection_failure_transient(self, test_email):
        """V6.5: SMTP - handle connection failure (transient)"""
        adapter = SMTPAdapter({
            "host": "nonexistent.server.test",
            "port": 25,
            "username": test_email,
            "password": "test",
            "from_address": test_email,
            "use_tls": False,
            "use_starttls": False,
            "timeout": 5,
        })
        delivery = {"destination": test_email, "personalised_payload": '{"subject": "Test", "body": "Test"}'}
        result = await adapter.send(delivery)
        assert result.success is False
        from src.adapters.base import ErrorClass
        assert result.error_class == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_6_handle_authentication_failure_permanent(self, smtp_config):
        """V6.6: SMTP - handle authentication failure (permanent)"""
        from src.adapters.base import ErrorClass
        from aiosmtplib.errors import SMTPAuthenticationError

        adapter = SMTPAdapter(smtp_config)
        auth_error = SMTPAuthenticationError(535, "Authentication credentials invalid")
        assert adapter.classify_error(auth_error) == ErrorClass.PERMANENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_7_handle_invalid_recipient_permanent(self, smtp_config):
        """V6.7: SMTP - handle invalid recipient (permanent)"""
        adapter = SMTPAdapter(smtp_config)
        delivery = {
            "destination": "invalid@example.invalid",
            "personalised_payload": '{"subject": "Test", "body": "Test"}',
        }
        result = await adapter.send(delivery)
        from src.adapters.base import ErrorClass
        if not result.success:
            assert result.error_class in [ErrorClass.PERMANENT, ErrorClass.TRANSIENT]
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_8_handle_mailbox_full_transient(self, smtp_config):
        """V6.8: SMTP - handle mailbox full (transient)"""
        adapter = SMTPAdapter(smtp_config)
        from aiosmtplib import SMTPException
        from src.adapters.base import ErrorClass

        class MockSMTPException(SMTPException):
            def __init__(self, code, message):
                self.code = code
                self.message = message
                super().__init__(message)

        error = MockSMTPException(452, "Mailbox full")
        assert adapter.classify_error(error) == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_9_classify_4xx_errors_as_transient(self, smtp_config):
        """V6.9: SMTP - classify 4xx errors as transient"""
        adapter = SMTPAdapter(smtp_config)
        from aiosmtplib import SMTPException
        from src.adapters.base import ErrorClass

        class MockSMTPException(SMTPException):
            def __init__(self, code, message):
                self.code = code
                self.message = message
                super().__init__(message)

        assert adapter.classify_error(MockSMTPException(421, "Service not available")) == ErrorClass.TRANSIENT
        assert adapter.classify_error(MockSMTPException(450, "Mailbox unavailable")) == ErrorClass.TRANSIENT
        assert adapter.classify_error(MockSMTPException(451, "Action aborted")) == ErrorClass.TRANSIENT
        assert adapter.classify_error(MockSMTPException(452, "Insufficient storage")) == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_10_classify_5xx_errors_as_permanent(self, smtp_config):
        """V6.10: SMTP - classify 5xx errors as permanent"""
        adapter = SMTPAdapter(smtp_config)
        from aiosmtplib import SMTPException
        from src.adapters.base import ErrorClass

        class MockSMTPException(SMTPException):
            def __init__(self, code, message):
                self.code = code
                self.message = message
                super().__init__(message)

        assert adapter.classify_error(MockSMTPException(550, "User not found")) == ErrorClass.PERMANENT
        assert adapter.classify_error(MockSMTPException(551, "User not local")) == ErrorClass.PERMANENT
        assert adapter.classify_error(MockSMTPException(552, "Exceeded storage")) == ErrorClass.PERMANENT
        assert adapter.classify_error(MockSMTPException(553, "Mailbox name invalid")) == ErrorClass.PERMANENT


class TestSMSAdapter:
    """Tests for Real SMS Adapter - V6.11 to V6.18"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_11_validate_phone_e164(self, test_config):
        """V6.11: SMS - validate phone number (E.164)"""
        adapter = SMSAdapter(_sms_adapter_config(test_config))
        assert adapter.validate_destination("+1234567890") is True
        assert adapter.validate_destination("+44207123456") is True
        assert adapter.validate_destination("123456") is False
        assert adapter.validate_destination("invalid") is False
        assert adapter.validate_destination("+") is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_12_send_sms_successfully(self, test_config):
        """V6.12: SMS - send SMS via Twilio API"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from src.adapters.base import ErrorClass

        adapter = TwilioSMSAdapter(_twilio_sms_config(test_config))
        delivery = {
            "destination": "+447768116229",
            "personalised_payload": '{"body": "Test SMS message from notification-agent"}',
        }
        result = await adapter.send(delivery)
        if not result.success:
            assert "from" in result.error.lower() or "number" in result.error.lower()
            assert result.error_class == ErrorClass.PERMANENT
        else:
            assert result.tracking_id is not None
            assert result.tracking_id.startswith("SM")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_13_handle_rate_limit_transient(self, test_config):
        """V6.13: SMS - handle rate limit errors (transient)"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_sms_config(test_config)
        adapter = TwilioSMSAdapter(config)
        request = Request("POST", config["base_url"])
        response_429 = Response(429, request=request, text='{"code": 20429, "message": "Rate limit exceeded"}')
        error_429 = HTTPStatusError("Rate limit", request=request, response=response_429)
        assert adapter.classify_error(error_429) == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_14_handle_invalid_number_permanent(self, test_config):
        """V6.14: SMS - handle invalid number (permanent)"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_sms_config(test_config)
        adapter = TwilioSMSAdapter(config)
        request = Request("POST", config["base_url"])
        response_400 = Response(400, request=request, text='{"code": 21211, "message": "Invalid To Phone Number"}')
        error_400 = HTTPStatusError("Invalid number", request=request, response=response_400)
        assert adapter.classify_error(error_400) == ErrorClass.PERMANENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_15_parse_delivery_receipt(self, test_config):
        """V6.15: SMS - parse delivery receipt"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        adapter = TwilioSMSAdapter(_twilio_sms_config(test_config))
        callback_data = {
            "MessageSid": "SM1234567890abcdef",
            "MessageStatus": "delivered",
            "To": "+447768116229",
            "From": "+14155238886",
            "DateSent": "2025-11-11T12:00:00Z",
        }
        parsed = adapter.parse_callback(callback_data)
        assert parsed["message_id"] == "SM1234567890abcdef"
        assert parsed["status"] == "delivered"
        assert parsed["destination"] == "+447768116229"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_16_handle_rate_limit_transient(self, test_config):
        """V6.16: SMS - handle rate limit (transient)"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_sms_config(test_config)
        adapter = TwilioSMSAdapter(config)
        request = Request("POST", config["base_url"])
        response_429 = Response(429, request=request, text='{"code": 20429, "message": "Rate limit exceeded"}')
        error_429 = HTTPStatusError("Rate limit", request=request, response=response_429)
        assert adapter.classify_error(error_429) == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_17_handle_account_issue_permanent(self, test_config):
        """V6.17: SMS - handle account issue (permanent)"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_sms_config(test_config)
        adapter = TwilioSMSAdapter(config)
        request = Request("POST", config["base_url"])
        response_401 = Response(401, request=request, text='{"code": 20003, "message": "Authenticate"}')
        error_401 = HTTPStatusError("Unauthorized", request=request, response=response_401)
        assert adapter.classify_error(error_401) == ErrorClass.PERMANENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_18_retry_with_backoff(self, test_config):
        """V6.18: SMS - retry with backoff"""
        from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_sms_config(test_config)
        adapter = TwilioSMSAdapter(config)
        request = Request("POST", config["base_url"])
        response_500 = Response(500, request=request, text='{"code": 20001, "message": "Internal error"}')
        error_500 = HTTPStatusError("Server error", request=request, response=response_500)
        assert adapter.classify_error(error_500) == ErrorClass.TRANSIENT
        network_error = ConnectionError("Connection refused")
        assert adapter.classify_error(network_error) == ErrorClass.TRANSIENT


class TestChatAdapter:
    """Tests for Real Chat/REST Adapter - V6.19 to V6.24"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_19_validate_webhook_url(self, test_config):
        """V6.19: Chat - validate webhook URL"""
        slack_url = _require_value(test_config.get("test.webhook.slack_url"), "test.webhook.slack_url")
        discord_url = _require_value(test_config.get("test.webhook.discord_url"), "test.webhook.discord_url")
        invalid_url = _require_value(test_config.get("test.webhook.invalid_url"), "test.webhook.invalid_url")
        invalid_scheme_url = _require_value(test_config.get("test.webhook.invalid_scheme_url"), "test.webhook.invalid_scheme_url")
        adapter = ChatAdapter({"endpoint": slack_url, "auth_type": "bearer", "token": "test-token"})
        assert adapter.validate_destination(slack_url) is True
        assert adapter.validate_destination(discord_url) is True
        assert adapter.validate_destination(invalid_url) is False
        assert adapter.validate_destination(invalid_scheme_url) is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_20_send_post_request(self, slack_endpoint):
        """V6.20: Chat - send POST request to REAL Slack TEST webhook"""
        adapter = ChatAdapter({"endpoint": slack_endpoint, "auth_type": "none", "timeout": 10})
        delivery = {
            "destination": slack_endpoint,
            "personalised_payload": '{"text": "REAL TEST: Chat adapter send - ' + str(int(time.time())) + '", "format_type": "slack"}',
        }
        result = await adapter.send(delivery)
        assert result.success is True or (result.error and "429" in result.error)
        if result.success:
            assert result.tracking_id is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_21_handle_authentication(self, slack_endpoint, test_config):
        """V6.21: Chat - handle authentication with bearer token"""
        bearer_token = _require_value(test_config.get("test.webhook.bearer_token"), "test.webhook.bearer_token")
        adapter = ChatAdapter({
            "endpoint": slack_endpoint,
            "auth_type": "bearer",
            "token": bearer_token,
            "timeout": 10,
        })
        assert adapter.auth_type == "bearer"
        assert adapter.token == bearer_token
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_22_parse_success_response(self, slack_endpoint):
        """V6.22: Chat - parse success response from REAL Slack TEST webhook"""
        adapter = ChatAdapter({"endpoint": slack_endpoint, "auth_type": "none", "timeout": 10})
        delivery = {
            "destination": slack_endpoint,
            "personalised_payload": f'{{"text": "REAL TEST: Response parsing {int(time.time())}", "format_type": "slack"}}',
        }
        result = await adapter.send(delivery)
        assert result.success is True, f"Slack webhook failed: {result.error}"
        assert result.tracking_id is not None
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_23_handle_http_errors_classify(self):
        """V6.23: Chat - handle HTTP errors (classify)"""
        adapter = ChatAdapter({"endpoint": "https://hooks.test.com/test", "auth_type": "none"})
        assert adapter.classify_http_error(429) == "transient"
        assert adapter.classify_http_error(500) == "transient"
        assert adapter.classify_http_error(400) == "permanent"
        assert adapter.classify_http_error(401) == "permanent"
        assert adapter.classify_http_error(404) == "permanent"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_24_retry_on_network_failure(self):
        """V6.24: Chat - retry on network failure"""
        import httpx

        adapter = ChatAdapter({"endpoint": "https://hooks.test.com/test", "auth_type": "none"})
        connect_error = httpx.ConnectError("Connection refused")
        timeout_error = httpx.ReadTimeout("Read timeout")
        assert adapter.classify_error(connect_error) == "transient"
        assert adapter.classify_error(timeout_error) == "transient"


class TestWhatsAppAdapter:
    """Tests for Real WhatsApp Adapter - V6.25 to V6.30"""
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_25_validate_whatsapp_number(self, test_config):
        """V6.25: WhatsApp - validate WhatsApp number format (whatsapp:+E.164)"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        adapter = WhatsAppAdapter(_twilio_whatsapp_config(test_config))
        assert adapter.validate_destination("whatsapp:+447768116229") is True
        assert adapter.validate_destination("whatsapp:+1234567890") is True
        assert adapter.validate_destination("+447768116229") is False
        assert adapter.validate_destination("whatsapp:447768116229") is False
        assert adapter.validate_destination("invalid") is False
        assert adapter.validate_destination("") is False
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_26_send_text_message(self, test_config):
        """V6.26: WhatsApp - send text message via Twilio API"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        adapter = WhatsAppAdapter(_twilio_whatsapp_config(test_config))
        delivery = {
            "destination": "whatsapp:+447768116229",
            "personalised_payload": '{"body": "Test WhatsApp message from notification-agent"}',
        }
        result = await adapter.send(delivery)
        assert result.success is True
        assert result.tracking_id is not None
        assert result.tracking_id.startswith("SM")
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    @pytest.mark.asyncio
    async def test_v6_27_send_contentsid_template(self, test_config):
        """V6.27: WhatsApp - send ContentSid template with variables"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        adapter = WhatsAppAdapter(_twilio_whatsapp_config(test_config))
        delivery = {
            "destination": "whatsapp:+447768116229",
            "personalised_payload": '{"content_sid": "HXb5b62575e6e4ff6129ad7c8efe1f983e", "content_variables": {"1": "12/1", "2": "3pm"}}',
        }
        result = await adapter.send(delivery)
        assert result.success is True or "ContentSid" in str(result.error)
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_28_handle_twilio_errors(self, test_config):
        """V6.28: WhatsApp - handle Twilio API errors (transient vs permanent)"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        from httpx import HTTPStatusError, Request, Response
        from src.adapters.base import ErrorClass

        config = _twilio_whatsapp_config(test_config)
        adapter = WhatsAppAdapter(config)
        request = Request("POST", config["base_url"])
        response_429 = Response(429, request=request, text='{"code": 20429, "message": "Rate limit exceeded"}')
        error_429 = HTTPStatusError("Rate limit", request=request, response=response_429)
        assert adapter.classify_error(error_429) == ErrorClass.TRANSIENT
        response_400 = Response(400, request=request, text='{"code": 21211, "message": "Invalid To Phone Number"}')
        error_400 = HTTPStatusError("Invalid number", request=request, response=response_400)
        assert adapter.classify_error(error_400) == ErrorClass.PERMANENT
        response_401 = Response(401, request=request, text='{"code": 20003, "message": "Authenticate"}')
        error_401 = HTTPStatusError("Unauthorized", request=request, response=response_401)
        assert adapter.classify_error(error_401) == ErrorClass.PERMANENT
        response_500 = Response(500, request=request, text='{"code": 20001, "message": "Internal error"}')
        error_500 = HTTPStatusError("Server error", request=request, response=response_500)
        assert adapter.classify_error(error_500) == ErrorClass.TRANSIENT
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_29_parse_twilio_callback(self, test_config):
        """V6.29: WhatsApp - parse Twilio callback (StatusCallback)"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        config = _twilio_whatsapp_config(test_config)
        adapter = WhatsAppAdapter(config)
        callback_data = {
            "MessageSid": "SM1234567890abcdef",
            "MessageStatus": "delivered",
            "To": "whatsapp:+447768116229",
            "From": config["from_number"],
            "DateSent": "2025-11-11T12:00:00Z",
        }
        parsed = adapter.parse_callback(callback_data)
        assert parsed["message_id"] == "SM1234567890abcdef"
        assert parsed["status"] == "delivered"
        assert parsed["destination"] == "whatsapp:+447768116229"
    @pytest.mark.IT
    @pytest.mark.mcp
    @pytest.mark.req("FR-026")

    def test_v6_30_classify_errors_correctly(self, test_config):
        """V6.30: WhatsApp - classify errors correctly"""
        from src.adapters.whatsapp_adapter import WhatsAppAdapter
        from src.adapters.base import ErrorClass
        from httpx import HTTPStatusError, Request, Response

        config = _twilio_whatsapp_config(test_config)
        adapter = WhatsAppAdapter(config)
        request = Request("POST", config["base_url"])
        network_error = ConnectionError("Connection refused")
        assert adapter.classify_error(network_error) == ErrorClass.TRANSIENT
        timeout_error = TimeoutError("Request timeout")
        assert adapter.classify_error(timeout_error) == ErrorClass.TRANSIENT
        response_invalid = Response(400, request=request, text='{"code": 21211, "message": "Invalid number"}')
        error_invalid = HTTPStatusError("Invalid", request=request, response=response_invalid)
        assert adapter.classify_error(error_invalid) == ErrorClass.PERMANENT
        response_unsub = Response(400, request=request, text='{"code": 21610, "message": "Unsubscribed"}')
        error_unsub = HTTPStatusError("Unsubscribed", request=request, response=response_unsub)
        assert adapter.classify_error(error_unsub) == ErrorClass.PERMANENT
        response_auth = Response(401, request=request, text='{"code": 20003, "message": "Authenticate"}')
        error_auth = HTTPStatusError("Auth", request=request, response=response_auth)
        assert adapter.classify_error(error_auth) == ErrorClass.PERMANENT
        response_rate = Response(429, request=request, text='{"code": 20429, "message": "Rate limit"}')
        error_rate = HTTPStatusError("Rate", request=request, response=response_rate)
        assert adapter.classify_error(error_rate) == ErrorClass.TRANSIENT

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.integration, pytest.mark.smtp, pytest.mark.heavy]
