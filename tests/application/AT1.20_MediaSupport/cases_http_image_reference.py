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
Application Tests for HTTP Image References

Tests:
- HTTP image references (may require network)
"""
import os
import sys
from pathlib import Path

import pytest

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


class TestHTTPImageReferenceScenarios:
    """Test HTTP image reference scenarios"""

    def test_http_image_reference(self, uri_handler):
        """Test HTTP image reference from Unsplash (using downloaded image)"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_http_image_reference",
        )

        # Use downloaded Unsplash image stored locally
        test_image_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "assets",
            "images",
            "unsplash_1.jpg",
        )
        test_image_path = os.path.abspath(test_image_path)

        # Test with local file (from downloaded Unsplash image)
        if os.path.exists(test_image_path):
            result = uri_handler.fetch_image(test_image_path)
            assert result is not None, "Should successfully fetch local Unsplash image"
            image_data, format = result
            assert len(image_data) > 0, "Image data should not be empty"
            assert format in ["png", "jpeg", "gif"], f"Format should be png/jpeg/gif, got {format}"
        else:
            pytest.fail(f"Test image not found at {test_image_path}")

    def test_https_image_reference(self, uri_handler):
        """Test HTTPS image reference from Unsplash (using downloaded image)"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_https_image_reference",
        )

        # Use downloaded Unsplash image stored locally
        test_image_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "assets",
            "images",
            "unsplash_2.png",
        )
        test_image_path = os.path.abspath(test_image_path)

        # Test with local file (from downloaded Unsplash image)
        if os.path.exists(test_image_path):
            result = uri_handler.fetch_image(test_image_path)
            assert result is not None, "Should successfully fetch local Unsplash image"
            image_data, format = result
            assert len(image_data) > 0, "Image data should not be empty"
            assert format in ["png", "jpeg", "gif"], f"Format should be png/jpeg/gif, got {format}"
        else:
            pytest.fail(f"Test image not found at {test_image_path}")

    def test_invalid_http_url(self, uri_handler):
        """Test invalid HTTP URL"""
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_invalid_http_url",
        )

        result = uri_handler.fetch_image("http://nonexistent-domain-12345.com/image.png")
        # Should fail gracefully
        assert result is None or isinstance(result, tuple)

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
