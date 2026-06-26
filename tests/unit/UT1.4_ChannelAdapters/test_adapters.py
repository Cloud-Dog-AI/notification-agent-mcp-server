# @pytest.mark.req("UC-001")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
# @pytest.mark.req("UC-002")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Unit tests for Channel Adapters

Tests: BR1.1

Tests:
- Destination validation
- Mock sending
- Error classification
- Adapter registry
"""

import pytest
import asyncio

from src.adapters.mock_email import MockEmailAdapter
from src.adapters.mock_sms import MockSMSAdapter
from src.adapters.mock_chat import MockChatAdapter
from src.adapters.registry import AdapterRegistry
from src.adapters.base import ErrorClass, BaseChannelAdapter

# Import real adapters if available
try:
    from src.adapters.smtp_adapter import SMTPAdapter
except ImportError:
    SMTPAdapter = None

try:
    from src.adapters.twilio_sms_adapter import TwilioSMSAdapter
except ImportError:
    TwilioSMSAdapter = None

try:
    from src.adapters.chat_adapter import ChatAdapter
except ImportError:
    ChatAdapter = None

try:
    from src.adapters.whatsapp_adapter import WhatsAppAdapter
except ImportError:
    WhatsAppAdapter = None


class TestMockEmailAdapter:
    """Test MockEmailAdapter"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_email_valid(self):
        """Test validating valid email addresses"""
        adapter = MockEmailAdapter({})
        
        assert adapter.validate_destination("test@cloud-dog.net") == True
        assert adapter.validate_destination("user.name@domain.co.uk") == True
        assert adapter.validate_destination("test123@cloud-dog.net") == True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_email_invalid(self):
        """Test validating invalid email addresses"""
        adapter = MockEmailAdapter({})
        
        assert adapter.validate_destination("invalid") == False
        assert adapter.validate_destination("@cloud-dog.net") == False
        assert adapter.validate_destination("test@") == False
        assert adapter.validate_destination("test @cloud-dog.net") == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_send_email_success(self, test_email_domain):
        """Test sending email successfully"""
        adapter = MockEmailAdapter({})
        
        delivery = {
            "destination": f"test{test_email_domain}",
            "personalised_payload": "Test message"
        }
        
        result = await adapter.send(delivery)
        
        assert result.success == True
        assert result.tracking_id is not None
        assert result.tracking_id.startswith("mock-email-")
        assert result.error is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_send_email_invalid_destination(self):
        """Test sending to invalid email"""
        adapter = MockEmailAdapter({})
        
        delivery = {
            "destination": "invalid-email",
            "personalised_payload": "Test"
        }
        
        result = await adapter.send(delivery)
        
        assert result.success == False
        assert result.error == "Invalid email address"
        assert result.error_class == ErrorClass.PERMANENT
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_confirm_email(self):
        """Test email confirmation"""
        adapter = MockEmailAdapter({})
        
        result = await adapter.confirm("mock-tracking-id")
        
        assert result.status == "delivered"
        assert result.timestamp is not None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_classify_error_transient(self):
        """Test classifying transient errors"""
        adapter = MockEmailAdapter({})
        
        assert adapter.classify_error(TimeoutError()) == ErrorClass.TRANSIENT
        assert adapter.classify_error(ConnectionError()) == ErrorClass.TRANSIENT
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_classify_error_permanent(self):
        """Test classifying permanent errors"""
        adapter = MockEmailAdapter({})
        
        assert adapter.classify_error(ValueError()) == ErrorClass.PERMANENT


class TestMockSMSAdapter:
    """Test MockSMSAdapter"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_phone_valid(self):
        """Test validating valid phone numbers"""
        adapter = MockSMSAdapter({})
        
        assert adapter.validate_destination("+447700900123") == True
        assert adapter.validate_destination("+1234567890") == True
        assert adapter.validate_destination("+819012345678") == True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_phone_invalid(self):
        """Test validating invalid phone numbers"""
        adapter = MockSMSAdapter({})
        
        assert adapter.validate_destination("invalid") == False
        assert adapter.validate_destination("+0") == False
        assert adapter.validate_destination("") == False
        assert adapter.validate_destination("+") == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_send_sms_success(self):
        """Test sending SMS successfully"""
        adapter = MockSMSAdapter({})
        
        delivery = {
            "destination": "+447700900123",
            "personalised_payload": "Test SMS message"
        }
        
        result = await adapter.send(delivery)
        
        assert result.success == True
        assert result.tracking_id is not None
        assert result.tracking_id.startswith("mock-sms-")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_send_sms_invalid_phone(self):
        """Test sending to invalid phone"""
        adapter = MockSMSAdapter({})
        
        delivery = {
            "destination": "invalid",
            "personalised_payload": "Test"
        }
        
        result = await adapter.send(delivery)
        
        assert result.success == False
        assert "Invalid phone number" in result.error


class TestRealSMSPayloadNormalisation:
    """Test real adapter payload normalisation paths used by runtime delivery_worker."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")

    def test_twilio_extract_body_from_content_blocks(self):
        """Twilio adapter must accept formatted content blocks, not only {'body': ...} dict payloads."""
        if TwilioSMSAdapter is None:
            pytest.skip("TwilioSMSAdapter import unavailable")

        payload = [
            {"type": "text", "body": "Line one"},
            {"type": "text", "body": "Line two"},
        ]
        assert TwilioSMSAdapter._extract_body_text(payload) == "Line one\n\nLine two"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")

    def test_whatsapp_extract_body_from_content_wrapper(self):
        """WhatsApp adapter must accept payload wrappers containing content lists."""
        if WhatsAppAdapter is None:
            pytest.skip("WhatsAppAdapter import unavailable")

        payload = {"content": [{"type": "text", "body": "Wrapped body"}]}
        assert WhatsAppAdapter._extract_body_text(payload) == "Wrapped body"


class TestMockChatAdapter:
    """Test MockChatAdapter"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_url_valid(self, test_config):
        """Test validating valid URLs"""
        adapter = MockChatAdapter({})
        slack_url = test_config.get("test.webhook.slack_url")
        local_url = test_config.get("test.webhook.local_url")
        example_url = test_config.get("test.webhook.example_url")
        if not slack_url or not local_url or not example_url:
            pytest.fail("test.webhook.* URLs not configured. Check your env file.")
        
        assert adapter.validate_destination(slack_url) is True
        assert adapter.validate_destination(local_url) is True
        assert adapter.validate_destination(example_url) is True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_validate_url_invalid(self):
        """Test validating invalid URLs"""
        adapter = MockChatAdapter({})
        
        assert adapter.validate_destination("invalid") == False
        assert adapter.validate_destination("ftp://example.com") == False
        assert adapter.validate_destination("not-a-url") == False
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    @pytest.mark.asyncio
    async def test_send_chat_success(self, test_config):
        """Test sending chat message successfully"""
        adapter = MockChatAdapter({})
        slack_url = test_config.get("test.webhook.slack_url")
        if not slack_url:
            pytest.fail("test.webhook.slack_url not configured. Check your env file.")
        
        delivery = {
            "destination": slack_url,
            "personalised_payload": "Test chat message"
        }
        
        result = await adapter.send(delivery)
        
        assert result.success == True
        assert result.tracking_id is not None
        assert result.tracking_id.startswith("mock-chat-")


class TestChatAdapterSlackPayload:
    """Test Slack webhook payload shaping."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")

    def test_slack_blocks_do_not_duplicate_title(self):
        """Title-led text plus a Slack header should not show the title twice."""
        if ChatAdapter is None:
            pytest.skip("ChatAdapter import unavailable")

        adapter = ChatAdapter({"endpoint": "https://example.com/webhook"})
        payload = adapter._build_payload(
            {
                "format": "slack",
                "title": "Ukraine digest: 7-day situation update",
                "text": (
                    "*Ukraine digest: 7-day situation update*\n\n"
                    "Recent updates include expanded drone and infrastructure reporting "
                    "with military, political, and strategic context.\n\n"
                    "<https://notificationagent0.cloud-dog.net/messages/example|View full message>"
                ),
            }
        )

        assert payload["text"].startswith("*Ukraine digest: 7-day situation update*")
        assert payload["blocks"][0]["type"] == "header"
        section_text = payload["blocks"][1]["text"]["text"]
        assert "Recent updates include expanded drone" in section_text
        assert not section_text.startswith("*Ukraine digest: 7-day situation update*")


class TestAdapterRegistry:
    """Test AdapterRegistry"""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_register_channel(self, test_config):
        """Test registering a channel"""
        registry = AdapterRegistry()
        smtp_config = {
            "host": test_config.get("channels.smtp.default.host"),
            "port": test_config.get("channels.smtp.default.port"),
            "username": test_config.get("channels.smtp.default.username"),
            "password": test_config.get("channels.smtp.default.password"),
            "from_address": test_config.get("channels.smtp.default.from_address"),
            "use_tls": test_config.get("channels.smtp.default.use_tls"),
            "use_starttls": test_config.get("channels.smtp.default.use_starttls"),
            "timeout": test_config.get("channels.smtp.default.timeout"),
        }
        if SMTPAdapter and not smtp_config.get("host"):
            pytest.skip("SMTP config missing for AdapterRegistry test.")
        
        adapter = registry.register_channel(
            channel_id=1,
            channel_type="email",
            config=smtp_config if SMTPAdapter else {}
        )
        
        assert adapter is not None
        # Registry now uses real adapters if available, otherwise mocks
        assert isinstance(adapter, BaseChannelAdapter)
        if SMTPAdapter:
            assert isinstance(adapter, SMTPAdapter)
        else:
            assert isinstance(adapter, MockEmailAdapter)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_get_adapter(self):
        """Test getting registered adapter"""
        registry = AdapterRegistry()
        
        registry.register_channel(
            channel_id=1,
            channel_type="sms",
            config={}
        )
        
        adapter = registry.get_adapter(1)
        assert adapter is not None
        # Registry now uses real adapters if available, otherwise mocks
        assert isinstance(adapter, BaseChannelAdapter)
        if TwilioSMSAdapter:
            assert isinstance(adapter, TwilioSMSAdapter)
        else:
            assert isinstance(adapter, MockSMSAdapter)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_unregister_channel(self, test_config):
        """Test unregistering a channel"""
        registry = AdapterRegistry()
        smtp_config = {
            "host": test_config.get("channels.smtp.default.host"),
            "port": test_config.get("channels.smtp.default.port"),
            "username": test_config.get("channels.smtp.default.username"),
            "password": test_config.get("channels.smtp.default.password"),
            "from_address": test_config.get("channels.smtp.default.from_address"),
            "use_tls": test_config.get("channels.smtp.default.use_tls"),
            "use_starttls": test_config.get("channels.smtp.default.use_starttls"),
            "timeout": test_config.get("channels.smtp.default.timeout"),
        }
        if SMTPAdapter and not smtp_config.get("host"):
            pytest.skip("SMTP config missing for AdapterRegistry test.")
        
        registry.register_channel(
            channel_id=1,
            channel_type="email",
            config=smtp_config if SMTPAdapter else {}
        )
        
        assert registry.get_adapter(1) is not None
        
        registry.unregister_channel(1)
        
        assert registry.get_adapter(1) is None
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_register_unknown_type(self):
        """Test registering unknown channel type"""
        registry = AdapterRegistry()
        
        with pytest.raises(ValueError, match="Unknown channel type"):
            registry.register_channel(
                channel_id=1,
                channel_type="unknown_type",
                config={}
            )
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-003")
    
    def test_multiple_channels(self, test_config):
        """Test registering multiple channels"""
        registry = AdapterRegistry()
        smtp_config = {
            "host": test_config.get("channels.smtp.default.host"),
            "port": test_config.get("channels.smtp.default.port"),
            "username": test_config.get("channels.smtp.default.username"),
            "password": test_config.get("channels.smtp.default.password"),
            "from_address": test_config.get("channels.smtp.default.from_address"),
            "use_tls": test_config.get("channels.smtp.default.use_tls"),
            "use_starttls": test_config.get("channels.smtp.default.use_starttls"),
            "timeout": test_config.get("channels.smtp.default.timeout"),
        }
        if SMTPAdapter and not smtp_config.get("host"):
            pytest.skip("SMTP config missing for AdapterRegistry test.")
        
        registry.register_channel(1, "email", smtp_config if SMTPAdapter else {})
        registry.register_channel(2, "sms", {})
        registry.register_channel(3, "chat", {})
        
        # Registry now uses real adapters if available, otherwise mocks
        adapter1 = registry.get_adapter(1)
        adapter2 = registry.get_adapter(2)
        adapter3 = registry.get_adapter(3)
        
        assert isinstance(adapter1, BaseChannelAdapter)
        assert isinstance(adapter2, BaseChannelAdapter)
        assert isinstance(adapter3, BaseChannelAdapter)
        
        # Check for real adapters if available
        if SMTPAdapter:
            assert isinstance(adapter1, SMTPAdapter)
        else:
            assert isinstance(adapter1, MockEmailAdapter)
        
        if TwilioSMSAdapter:
            assert isinstance(adapter2, TwilioSMSAdapter)
        else:
            assert isinstance(adapter2, MockSMSAdapter)
        
        if ChatAdapter:
            assert isinstance(adapter3, ChatAdapter)
        else:
            assert isinstance(adapter3, MockChatAdapter)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.smtp, pytest.mark.fast]
