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
Application Tests for Local File Images

Tests:
- Local file images in real scenarios
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.media.media_fetcher import URIHandler
from src.core.media.image_handler import ImageHandler


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


@pytest.fixture
def uri_handler(image_handler):
    """Create URIHandler instance"""
    return URIHandler(image_handler=image_handler)


class TestLocalFileImageScenarios:
    """Test local file image scenarios"""

    def test_local_png_file(self, uri_handler):
        """Test local PNG file"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_local_png_file",
        )

        img = Image.new("RGB", (100, 100), color="red")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(temp_file, format="PNG")
        temp_file.close()

        try:
            result = uri_handler.fetch_image(temp_file.name)
            assert result is not None
            image_data, format = result
            assert format == "png"
        finally:
            os.unlink(temp_file.name)

    def test_local_jpeg_file(self, uri_handler):
        """Test local JPEG file"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_local_jpeg_file",
        )

        img = Image.new("RGB", (100, 100), color="blue")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        img.save(temp_file, format="JPEG")
        temp_file.close()

        try:
            result = uri_handler.fetch_image(temp_file.name)
            assert result is not None
            image_data, format = result
            assert format == "jpeg"
        finally:
            os.unlink(temp_file.name)

    def test_local_gif_file(self, uri_handler):
        """Test local GIF file"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_local_gif_file",
        )

        img = Image.new("RGB", (100, 100), color="green")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".gif")
        img.save(temp_file, format="GIF")
        temp_file.close()

        try:
            result = uri_handler.fetch_image(temp_file.name)
            assert result is not None
            image_data, format = result
            assert format == "gif"
        finally:
            os.unlink(temp_file.name)

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.application, pytest.mark.smtp, pytest.mark.heavy]

# --- PS-REQ-TEST-TRACE binding (W28E-1807B) ----------------------------------
# This AT case-suite drives notification output via the API surface; it is an
# executable AT-tier test (run under tests/env-AT) bound to its canonical
# functional requirement so the conftest PS-REQ-TEST-TRACE marker gate collects
# it. Comment-anchor marker form is sanctioned by tests/conftest.py.
# @pytest.mark.AT
# @pytest.mark.api
# @pytest.mark.req("FR-007")
