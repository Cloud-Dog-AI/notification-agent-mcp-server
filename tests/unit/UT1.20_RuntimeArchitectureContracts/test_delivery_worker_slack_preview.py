#!/usr/bin/env python3

from src.core.delivery_worker import (
    DeliveryProcessorLoop,
    SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS,
    _slack_summary_link_preview_floor,
)
import pytest


class _Config:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


class _Formatter:
    def _apply_restrictions(self, text, restrictions, user_prefs=None):
        return text
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_slack_summary_link_preview_floor_rejects_tiny_config() -> None:
    assert (
        _slack_summary_link_preview_floor(
            _Config({"slack.summary_link_min_preview_chars": 200})
        )
        == SLACK_SUMMARY_LINK_MIN_PREVIEW_CHARS
    )
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_slack_summary_link_preview_floor_honours_larger_config() -> None:
    assert (
        _slack_summary_link_preview_floor(
            _Config({"slack.summary_link_min_preview_chars": 1400})
        )
        == 1400
    )
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_slack_summary_link_preview_preserves_news_formatting() -> None:
    worker = DeliveryProcessorLoop.__new__(DeliveryProcessorLoop)
    worker.config = _Config({"slack.summary_link_min_preview_chars": 1200})
    worker.formatter = _Formatter()

    payload = worker._format_content_for_slack(
        [
            {
                "type": "html",
                "body": """
                <h1>Transparent Borders Research: Global Risk Digest</h1>
                <p><strong>This is the latest digest.</strong></p>
                <h2>Theme Focus</h2>
                <ul>
                  <li><strong>Health Surveillance</strong> - anchored in [G01]; supporting context: Today&#x27;s top news.</li>
                  <li><strong>Humanitarian Access</strong> - anchored in [G04].</li>
                </ul>
                <h2>What Changed</h2>
                <p>Current reporting points to public-health surveillance and humanitarian pressure.</p>
                """,
            }
        ],
        {
            "variables_json": '{"subject": "Transparent Borders Research: Global Risk Digest - 29 May 2026, 07:57 UTC"}',
            "content_json": "[]",
            "guid": "abc",
            "id": 1,
        },
        {},
        "<https://notificationagent0.cloud-dog.net/messages/abc|View full message (1234 characters)>",
        restrictions={"link_strategy": "summary+link", "max_length": 900},
        user_prefs={"language": "en"},
    )

    text = payload["text"]
    assert "*Transparent Borders Research: Global Risk Digest - 29 May 2026, 07:57 UTC*" in text
    assert "\n\n*Theme Focus*" in text
    assert "\n- *Health Surveillance* - anchored in [G01]; supporting context: Today's top news." in text
    assert "\n- *Humanitarian Access* - anchored in [G04]." in text
    assert "\n\n*What Changed*" in text
    assert "Today&#x27;s" not in text
    assert "View full message" in text
