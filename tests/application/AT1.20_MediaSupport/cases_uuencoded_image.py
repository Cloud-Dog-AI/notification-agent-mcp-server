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
Application Tests for UUEncoded Images

Tests:
- UUEncoded images in real message scenarios
"""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.media.uuencoding import UUEncoding
from src.core.media.image_handler import ImageHandler


@pytest.fixture
def image_handler():
    """Create ImageHandler instance"""
    return ImageHandler()


class TestUUEncodedImageScenarios:
    """Test UUEncoded image scenarios"""

    def test_uuencoded_png_in_message(self, image_handler):
        """Test UUEncoded PNG in message"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_uuencoded_png_in_message",
        )

        img = Image.new("RGB", (100, 100), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_data = buffer.getvalue()

        # UUEncode
        encoded = UUEncoding.encode(image_data, "png")

        # Decode and validate
        result = UUEncoding.decode(encoded)
        assert result is not None
        decoded_data, format = result

        # Validate image
        is_valid, _ = image_handler.validate_image(decoded_data)
        assert is_valid is True

        # Extract metadata
        metadata = image_handler.extract_metadata(decoded_data)
        assert metadata is not None
        assert metadata.format.value == "png"

    def test_uuencoded_jpeg_in_message(self, image_handler):
        """Test UUEncoded JPEG in message"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_uuencoded_jpeg_in_message",
        )

        img = Image.new("RGB", (100, 100), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        image_data = buffer.getvalue()

        # UUEncode
        encoded = UUEncoding.encode(image_data, "jpeg")

        # Decode and validate
        result = UUEncoding.decode(encoded)
        assert result is not None
        decoded_data, format = result

        # Validate image
        is_valid, _ = image_handler.validate_image(decoded_data)
        assert is_valid is True

    def test_uuencoded_gif_in_message(self, image_handler):
        """Test UUEncoded GIF in message"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_uuencoded_gif_in_message",
        )

        img = Image.new("RGB", (100, 100), color="green")
        buffer = io.BytesIO()
        img.save(buffer, format="GIF")
        image_data = buffer.getvalue()

        # UUEncode
        encoded = UUEncoding.encode(image_data, "gif")

        # Decode and validate
        result = UUEncoding.decode(encoded)
        assert result is not None
        decoded_data, format = result

        # Validate image
        is_valid, _ = image_handler.validate_image(decoded_data)
        assert is_valid is True

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
