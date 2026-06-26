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

"""System Tests for Media Rendering System"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import io
from PIL import Image
from src.core.media.media_renderer import MediaRenderer

@pytest.fixture
def media_renderer():
    return MediaRenderer()

class TestRenderingSystem:
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    def test_rendering_multiple_formats(self, media_renderer, test_config):
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=True,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_rendering_multiple_formats"
        )

        formats = ["markdown", "text", "pdf"]
        image_url = test_config.get("test.media.image_url")
        if not image_url:
            pytest.fail("test.media.image_url not configured. Check your env file.")
        for fmt in formats:
            result = media_renderer.render_image_for_markdown(image_url) if fmt == "markdown" else media_renderer.render_image_for_text(image_url)
            assert result is not None

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

