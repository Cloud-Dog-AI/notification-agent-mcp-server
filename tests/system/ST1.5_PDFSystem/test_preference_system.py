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

"""System Tests for PDF Preference System"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
from src.core.formatters.pdf_preferences import PDFPreferenceResolver, PDFPreference

class TestPreferenceSystem:
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    def test_preference_enum_values(self):
        """Test PDFPreference enum values"""
        assert PDFPreference.ATTACH.value == "attach"
        assert PDFPreference.LINK.value == "link"
        assert PDFPreference.NONE.value == "none"
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_resolver_default_initialization(self):
        """Test resolver initialization with defaults"""
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_resolver_default_initialization"
        )

        resolver = PDFPreferenceResolver()
        assert resolver.default_preference == "link"
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-025")
    
    def test_preference_resolution_priority(self):
        """Test preference resolution priority"""
        resolver = PDFPreferenceResolver()
        
        # User > Channel > Default
        pref = resolver.resolve_preference(user_preference="attach", channel_preference="link")
        assert pref == PDFPreference.ATTACH
        
        pref = resolver.resolve_preference(channel_preference="link")
        assert pref == PDFPreference.LINK
        
        pref = resolver.resolve_preference()
        assert pref == PDFPreference.LINK  # Default

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

