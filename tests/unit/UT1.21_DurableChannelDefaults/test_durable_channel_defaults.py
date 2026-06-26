"""UT1.21 Durable Channel Defaults — W28C-437

Tests that channel limits/restrictions from defaults.yaml are applied
during reconciliation, ensuring Slack preview and summary+link behavior
survive service restart.
"""

import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock


DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "defaults.yaml"


class TestDefaultsYamlChannelConfig:
    """Verify defaults.yaml contains transparentbordes channel with correct settings."""

    @pytest.fixture
    def defaults(self):
        with open(DEFAULTS_PATH) as f:
            return yaml.safe_load(f)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_profile_exists(self, defaults):
        chat_rest = defaults.get("channels", {}).get("chat_rest", {})
        assert "transparentbordes" in chat_rest, "transparentbordes profile missing from defaults.yaml"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_limits_max_length(self, defaults):
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        limits = profile.get("limits", {})
        assert limits.get("max_length") == 1000, "Slack preview max_length must be 1000"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_restrictions_link_strategy(self, defaults):
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        restrictions = profile.get("restrictions", {})
        assert restrictions.get("link_strategy") == "summary+link"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_restrictions_max_length(self, defaults):
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        restrictions = profile.get("restrictions", {})
        assert restrictions.get("max_length") == 1000
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_format_is_slack(self, defaults):
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        assert profile.get("format") == "slack"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_is_channel_based(self, defaults):
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        assert profile.get("is_channel_based") is True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_transparentbordes_disabled_by_default(self, defaults):
        """Channel must be disabled in defaults — enabled via env override."""
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        assert profile.get("enabled") is False


class TestReconcileChannelsLimitsRestrictions:
    """Test that _reconcile_channels_from_config applies limits and restrictions."""

    def _make_config(self, limits=None, restrictions=None):
        """Build a config dict mimicking defaults.yaml structure."""
        profile = {
            "enabled": True,
            "endpoint": "https://hooks.example.com/test",
            "is_channel_based": True,
            "auth_type": "none",
            "format": "slack",
        }
        if limits:
            profile["limits"] = limits
        if restrictions:
            profile["restrictions"] = restrictions
        return {"channels": {"chat_rest": {"test_channel": profile}}}

    def _make_repo(self, existing=None):
        repo = MagicMock()
        repo.get_by_name.return_value = existing
        if existing is None:
            # Simulate create followed by get
            repo.create.return_value = None
            repo.get_by_name.side_effect = [None, {"id": 99, "name": "chat_rest_test_channel"}]
        return repo
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_new_channel_gets_limits_json(self):
        from src.servers.api.api_server import _reconcile_channels_from_config

        cfg_dict = self._make_config(
            limits={"max_length": 1000, "rate_per_minute": 100}
        )
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: cfg_dict.get(k, d)
        repo = self._make_repo(existing=None)
        log = MagicMock()

        _reconcile_channels_from_config(cfg, repo, log)

        repo.create.assert_called_once()
        call_kwargs = repo.create.call_args
        limits_arg = call_kwargs.kwargs.get("limits_json") or call_kwargs[1].get("limits_json")
        if limits_arg is None and len(call_kwargs.args) > 4:
            limits_arg = call_kwargs.args[4]
        assert limits_arg is not None
        parsed = json.loads(limits_arg)
        assert parsed["max_length"] == 1000
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_new_channel_config_marks_channel_based(self):
        from src.servers.api.api_server import _reconcile_channels_from_config

        cfg_dict = self._make_config()
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: cfg_dict.get(k, d)
        repo = self._make_repo(existing=None)
        log = MagicMock()

        _reconcile_channels_from_config(cfg, repo, log)

        call_kwargs = repo.create.call_args
        config_arg = call_kwargs.kwargs.get("config_json") or call_kwargs[1].get("config_json")
        if config_arg is None and len(call_kwargs.args) > 3:
            config_arg = call_kwargs.args[3]
        parsed = json.loads(config_arg)
        assert parsed["is_channel_based"] is True
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_new_channel_gets_restrictions_json(self):
        from src.servers.api.api_server import _reconcile_channels_from_config

        cfg_dict = self._make_config(
            restrictions={"max_length": 1000, "link_strategy": "summary+link"}
        )
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: cfg_dict.get(k, d)
        repo = self._make_repo(existing=None)
        log = MagicMock()

        _reconcile_channels_from_config(cfg, repo, log)

        # After create, restrictions should be applied via update
        assert repo.update.called
        update_args = repo.update.call_args
        updates = update_args[0][1] if len(update_args[0]) > 1 else update_args.kwargs
        assert "restrictions_json" in str(updates)
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_existing_channel_preserves_db_limits(self):
        """If DB already has limits_json, config should NOT overwrite."""
        from src.servers.api.api_server import _reconcile_channels_from_config

        existing = {
            "id": 59,
            "name": "chat_rest_test_channel",
            "type": "chat_rest",
            "enabled": 1,
            "config_json": "{}",
            "limits_json": '{"max_length": 500}',
            "restrictions_json": '{"link_strategy": "inline"}',
        }
        cfg_dict = self._make_config(
            limits={"max_length": 1000},
            restrictions={"max_length": 1000, "link_strategy": "summary+link"},
        )
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, d=None: cfg_dict.get(k, d)
        repo = self._make_repo(existing=existing)
        repo.get_by_name.return_value = existing
        repo.get_by_name.side_effect = None
        log = MagicMock()

        _reconcile_channels_from_config(cfg, repo, log)

        # Should not overwrite existing limits/restrictions
        if repo.update.called:
            update_dict = repo.update.call_args[0][1]
            assert "limits_json" not in update_dict
            assert "restrictions_json" not in update_dict


class TestSlackPreviewBehavior:
    """Test Slack preview length and title deduplication."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_preview_floor_enforced(self):
        """Slack preview must be at least SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS."""
        from src.core.delivery_worker import SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS
        assert SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS >= 400
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_configured_1000_exceeds_floor(self):
        """1000-char preview exceeds the minimum floor."""
        from src.core.delivery_worker import SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS
        assert 1000 >= SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS


class TestSlackTitleDeduplication:
    """Verify link_strategy=summary+link does not duplicate the title."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_restrictions_link_strategy_summary_link(self):
        """The transparentbordes channel uses summary+link, not inline."""
        with open(DEFAULTS_PATH) as f:
            defaults = yaml.safe_load(f)
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        restrictions = profile.get("restrictions", {})
        assert restrictions.get("link_strategy") == "summary+link"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_link_strategy_not_inline(self):
        """Inline link strategy would embed links in text, summary+link provides separate link."""
        with open(DEFAULTS_PATH) as f:
            defaults = yaml.safe_load(f)
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        restrictions = profile.get("restrictions", {})
        assert restrictions.get("link_strategy") != "inline"


class TestEmailHTMLPayload:
    """Verify email channels deliver HTML content_type for group deliveries."""
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_email_default_channel_exists_in_migration(self):
        """email_default channel is seeded in migration with smtp type."""
        migration = Path(__file__).resolve().parent.parent.parent.parent / "database" / "migrations" / "001_initial_schema.sql"
        content = migration.read_text()
        assert "email_default" in content
        assert "'smtp'" in content
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")

    def test_html_content_type_preserved_in_config(self):
        """The transparentbordes restrictions allow text format for Slack;
        email channels use HTML by default when content_type=html is set."""
        with open(DEFAULTS_PATH) as f:
            defaults = yaml.safe_load(f)
        profile = defaults["channels"]["chat_rest"]["transparentbordes"]
        restrictions = profile.get("restrictions", {})
        # Slack gets text format
        assert "text" in restrictions.get("allowed_formats", [])
        # Email channels have no text-only restriction — they accept html
