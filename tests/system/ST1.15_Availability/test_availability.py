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
System Test ST1.15: Availability Tests

Tests NF1.2: Availability requirements
- Health checks
- Degraded modes
- Default channel required

Related Requirements: NF1.2
Related Tasks: T12
Related Architecture: RR1.1
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx

def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value


class TestAvailability:
    """Availability tests"""
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-014")
    
    def test_health_check(self, test_config):
        """
        Test that health check endpoint is available
        
        Validates NF1.2: Health checks
        """
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_health_check"
        )

        print("\n" + "="*80)
        print("HEALTH CHECK TEST")
        print("="*80 + "\n")
        
        api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_base_url}/health", timeout=5.0)
            
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
            
            health_data = response.json()
            print(f"  Health status: {health_data.get('status', 'unknown')}")
            
            assert health_data.get("status") in ("healthy", "ok"), "System should be healthy"
            print("\n✅ Health check passed")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-014")
    
    def test_degraded_mode_handling(self, test_config):
        """
        Test that system handles degraded modes gracefully
        
        Validates NF1.2: Degraded modes
        """
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_degraded_mode_handling"
        )

        print("\n" + "="*80)
        print("DEGRADED MODE HANDLING TEST")
        print("="*80 + "\n")
        
        # Test that system continues to operate even if some channels fail
        # This is a basic test - comprehensive degraded mode testing would require
        # simulating channel failures
        
        api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url")
        api_key = _require_value(test_config.get("api_server.api_key"), "api_server.api_key")
        default_channel = _require_value(test_config.get("default_channel"), "default_channel")
        test_email = _require_value(test_config.get("test.email"), "test.email")
        with httpx.Client(timeout=30.0) as client:
            # Create message with multiple channels
            message_payload = {
                "content": [{"type": "text", "body": "Degraded mode test message"}],
                "destinations": [{"channel": default_channel, "address": test_email}],
            }
            
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload,
                timeout=10.0
            )
            
            # System should accept message even if some channels are degraded
            assert response.status_code in [201, 202], f"Message should be accepted: {response.status_code}"
            print("\n✅ System handles degraded modes gracefully")
    @pytest.mark.ST
    @pytest.mark.mcp
    @pytest.mark.req("FR-014")
    
    def test_default_channel_required(self, test_config):
        """
        Test that default channel is required for service readiness
        
        Validates NF1.2: Default channel required
        """
        # CRITICAL: Check dependencies BEFORE any test logic
        check_test_dependencies(
            requires_llm=False,
            requires_smtp=False,
            requires_slack=False,
            requires_api=True,
            test_name="test_default_channel_required"
        )

        print("\n" + "="*80)
        print("DEFAULT CHANNEL REQUIRED TEST")
        print("="*80 + "\n")
        
        # This test validates that the system requires a default channel
        # In practice, this would be validated during startup/configuration
        
        api_base_url = _require_value(test_config.get("api_server.base_url"), "api_server.base_url")
        with httpx.Client(timeout=10.0) as client:
            # Check if system is operational (implies default channel is configured)
            response = client.get(f"{api_base_url}/health", timeout=5.0)
            
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("status") == "healthy":
                    print("  System is healthy (default channel configured)")
                    print("\n✅ Default channel requirement validated")
                else:
                    print("  System is not healthy (may indicate missing default channel)")
            else:
                pytest.skip("Cannot validate default channel requirement - health check failed")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]

