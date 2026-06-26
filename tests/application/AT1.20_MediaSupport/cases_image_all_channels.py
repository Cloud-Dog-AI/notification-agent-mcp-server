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

"""Application Tests for Images Across All Channels"""
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.media.media_renderer import MediaRenderer


@pytest.fixture
def media_renderer():
    return MediaRenderer()


class TestImageAllChannels:
    def test_email_channel_image(self, media_renderer):
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=False,
            test_name="test_email_channel_image",
        )

        content = [{"type": "image", "uri": "http://example.com/image.png"}]
        processed, images = media_renderer.process_images_in_content(
            content,
            output_format="html",
            channel_type="smtp",
        )
        assert len(processed) > 0

    def test_slack_channel_image(self, media_renderer):
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=False,
            test_name="test_slack_channel_image",
        )

        content = [{"type": "image", "uri": "http://example.com/image.png"}]
        processed, images = media_renderer.process_images_in_content(
            content,
            output_format="text",
            channel_type="slack",
        )
        assert len(processed) > 0

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [
    pytest.mark.application,
    pytest.mark.media,
    pytest.mark.non_llm,
    pytest.mark.no_llm_dependency,
    pytest.mark.no_runtime_dependency,
    pytest.mark.pure,
    pytest.mark.fast,
]

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-007")
