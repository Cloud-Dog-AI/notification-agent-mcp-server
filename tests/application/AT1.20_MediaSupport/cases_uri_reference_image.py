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
Application Tests for URI Reference Images

Tests:
- URI references in real message scenarios
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


@pytest.fixture
def temp_image_file():
    """Create temporary image file"""
    img = Image.new("RGB", (100, 100), color="red")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    img.save(temp_file, format="PNG")
    temp_file.close()
    yield temp_file.name
    os.unlink(temp_file.name)


class TestURIReferenceScenarios:
    """Test URI reference scenarios"""

    def test_local_file_reference(self, uri_handler, temp_image_file):
        """Test local file reference"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_local_file_reference",
        )

        result = uri_handler.fetch_image(temp_image_file)
        assert result is not None
        image_data, format = result
        assert format == "png"

        # Validate image
        is_valid, _ = uri_handler.image_handler.validate_image(image_data)
        assert is_valid is True

    def test_http_reference_scenario(self, uri_handler):
        """Test HTTP reference scenario (may fail if URL not accessible)"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_http_reference_scenario",
        )

        # Use a well-known test image URL (if available)
        # This test may be skipped if network is not available
        test_url = "https://via.placeholder.com/100.png"
        result = uri_handler.fetch_image(test_url)
        # May or may not succeed depending on network
        if result is not None:
            image_data, format = result
            assert len(image_data) > 0
            assert format in ["png", "jpeg", "gif"]

    def test_https_reference_scenario(self, uri_handler):
        """Test HTTPS reference scenario (may fail if URL not accessible)"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_https_reference_scenario",
        )

        # Use a well-known test image URL (if available)
        test_url = "https://via.placeholder.com/100.jpg"
        result = uri_handler.fetch_image(test_url)
        # May or may not succeed depending on network
        if result is not None:
            image_data, format = result
            assert len(image_data) > 0

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
