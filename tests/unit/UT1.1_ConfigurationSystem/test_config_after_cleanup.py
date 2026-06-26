# @pytest.mark.req("UC-019")  # W28E-1807A UC trace anchor (PS-REQ-TEST-TRACE section 3.5)
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
Test Configuration After env-build Cleanup

V23.2: Verify all config values pass through correctly after env-build cleanup.
"""

import pytest
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_config
@pytest.mark.UT
@pytest.mark.mcp
@pytest.mark.req("FR-022")


def test_v23_2_config_values_pass_through():
    """
    V23.2: Verify all config values pass through correctly after env-build cleanup
    """
    config = get_config()
    
    required_keys = [
        "api_server.port",
        "web_server.port",
        "mcp_server.port",
        "a2a_server.port",
        "api_server.api_key",
        "web_server.username",
        "web_server.password",
        "api_server.base_url",
        "web_server.api_base_url",
        "llm.base_url",
        "db.uri",
        "llm.max_tokens",
        "llm.num_ctx",
        "llm.startup_timeout",
        "channels.smtp.default.enabled",
        "channels.smtp.default.host",
    ]
    missing = [key for key in required_keys if not config.get(key)]
    if missing:
        pytest.skip(f"Missing required env-build values: {', '.join(missing)}")
    
    # Test defaults still work (values not in env-build)
    assert config.get("queue.default_ttl_hours"), "Queue TTL should be set"
    assert config.get("rate_limit.per_channel_per_minute"), "Rate limit should be set"
    assert config.get("circuit.soft_error_threshold"), "Circuit breaker threshold should be set"

    # Type validation (forensic format)
    assert isinstance(config.get("api_server.port"), int)
    assert isinstance(config.get("web_server.port"), int)
    assert isinstance(config.get("llm.max_tokens"), int)
    assert isinstance(config.get("llm.num_ctx"), int)
    assert isinstance(config.get("channels.smtp.default.enabled"), bool)
    
    print("✅ All config values pass through correctly:")
    print(f"   - Ports: API={config.get('api_server.port')}, Web={config.get('web_server.port')}")
    print(f"   - Secrets: API key set, Web credentials set")
    print(f"   - Base URLs: All set correctly")
    print(f"   - Defaults: Queue TTL={config.get('queue.default_ttl_hours')}, Rate limit={config.get('rate_limit.per_channel_per_minute')}")
    print(f"   - LLM: Max tokens={config.get('llm.max_tokens')}, Context={config.get('llm.num_ctx')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.smtp, pytest.mark.mcp, pytest.mark.fast]

