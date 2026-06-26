"""W28A-309: Unit tests for public message URL generation."""
import pytest
from src.core.formatters.message_url import build_public_message_url, sanitise_url_for_payload


class FakeConfig:
    def __init__(self, values):
        self._values = values

    def get(self, key):
        return self._values.get(key)


class TestBuildPublicMessageUrl:
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-013")
    def test_preprod_url_with_guid(self):
        cfg = FakeConfig({"messages.base_url": "https://notificationagent0.cloud-dog.net/messages"})
        url = build_public_message_url(cfg, message_guid="abc-123")
        assert url == "https://notificationagent0.cloud-dog.net/messages/abc-123"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("CS-014")

    def test_preprod_url_with_language(self):
        cfg = FakeConfig({"messages.base_url": "https://notificationagent0.cloud-dog.net/messages"})
        url = build_public_message_url(cfg, message_guid="abc-123", language="fr")
        assert url == "https://notificationagent0.cloud-dog.net/messages/abc-123?language=fr"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_localhost_fallback_when_no_messages_url(self):
        cfg = FakeConfig({"api_server.base_url": "http://localhost:8083"})
        url = build_public_message_url(cfg, message_guid="abc-123")
        assert "localhost" in url  # fallback accepted in dev mode
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_messages_url_takes_precedence(self):
        cfg = FakeConfig({
            "messages.base_url": "https://notificationagent0.cloud-dog.net/messages",
            "api_server.base_url": "http://localhost:8083",
        })
        url = build_public_message_url(cfg, message_guid="abc-123")
        assert "notificationagent0" in url
        assert "localhost" not in url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_normalises_api_prefix(self):
        cfg = FakeConfig({"messages.base_url": "http://localhost:8083/api/messages"})
        url = build_public_message_url(cfg, message_guid="abc-123")
        assert "/api/messages" not in url
        assert "/messages/abc-123" in url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_missing_config_raises(self):
        cfg = FakeConfig({})
        with pytest.raises(RuntimeError, match="Missing required configuration"):
            build_public_message_url(cfg, message_guid="abc-123")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_no_identifier_returns_base(self):
        cfg = FakeConfig({"messages.base_url": "https://example.com/messages"})
        url = build_public_message_url(cfg)
        assert url == "https://example.com/messages"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")


    def test_message_id_fallback(self):
        cfg = FakeConfig({"messages.base_url": "https://notificationagent0.cloud-dog.net/messages"})
        url = build_public_message_url(cfg, message_id="42")
        assert url == "https://notificationagent0.cloud-dog.net/messages/42"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_guid_takes_precedence_over_id(self):
        cfg = FakeConfig({"messages.base_url": "https://notificationagent0.cloud-dog.net/messages"})
        url = build_public_message_url(cfg, message_guid="guid-1", message_id="42")
        assert "guid-1" in url
        assert "42" not in url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_base_url_without_messages_suffix(self):
        cfg = FakeConfig({"messages.base_url": "https://notificationagent0.cloud-dog.net"})
        url = build_public_message_url(cfg, message_guid="abc")
        assert url == "https://notificationagent0.cloud-dog.net/messages/abc"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_no_localhost_in_preprod_url(self):
        """When messages.base_url is set to a real host, no localhost leak."""
        cfg = FakeConfig({
            "messages.base_url": "https://notificationagent0.cloud-dog.net/messages",
            "api_server.base_url": "http://localhost:8083",
        })
        url = build_public_message_url(cfg, message_guid="test-guid", language="en")
        assert "localhost" not in url
        assert "notificationagent0.cloud-dog.net" in url
        assert "?language=en" in url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_slack_url_no_ellipsis(self):
        """Reported W28A-309 defect: Slack URLs must not end with ellipsis."""
        long_url = "https://understandingwar.org/research/russia-ukraine/russian-offensive-campaign-assessment-may-17-2026"
        assert sanitise_url_for_payload(long_url) == long_url
        truncated = long_url[:80] + "..."
        cleaned = sanitise_url_for_payload(truncated)
        assert not cleaned.endswith("...")
        assert not cleaned.endswith("\u2026")
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_email_url_no_api_prefix(self):
        """Email URLs must use /messages/ not /api/messages/."""
        cfg = FakeConfig({"messages.base_url": "http://localhost:8083/api/messages"})
        url = build_public_message_url(cfg, message_guid="email-guid")
        assert "/api/messages/" not in url
        assert "/messages/email-guid" in url


class TestSanitiseUrl:
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    def test_complete_url_unchanged(self):
        url = "https://example.com/article/full-title-here"
        assert sanitise_url_for_payload(url) == url
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_truncated_ellipsis_stripped(self):
        url = "https://understandingwar.org/research/russia-ukraine/russian-offensive-campaign-assessme..."
        result = sanitise_url_for_payload(url)
        assert not result.endswith("...")
        assert "assessme" in result
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_unicode_ellipsis_stripped(self):
        url = "https://example.com/long-path\u2026"
        result = sanitise_url_for_payload(url)
        assert "\u2026" not in result
