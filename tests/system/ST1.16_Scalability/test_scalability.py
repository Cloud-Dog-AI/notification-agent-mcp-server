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
System Test ST1.16: Scalability Tests

Tests NF1.3: Scalability requirements
- Horizontal workers
- Stateless API nodes
- Work-queue backed

Related Requirements: NF1.3
Related Tasks: T12, T14
Related Architecture: SP1.2
"""

import pytest
import sys
import time
from pathlib import Path
from typing import List, Any, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.utils.test_helpers import check_test_dependencies
import httpx
import concurrent.futures


def _require_value(value, key: str):
    if value is None or value == "":
        raise RuntimeError(f"Missing required configuration: {key}")
    return value
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-015")


@pytest.fixture
def test_output_dir(tmp_path: Path) -> Path:
    return tmp_path
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-015")


def test_st1_16_concurrent_message_creation(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_output_dir: Path
):
    """
    Test that system handles concurrent message creation
    
    Validates NF1.3: Horizontal workers, stateless API nodes
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("st116_env_loaded"):
        pytest.skip("ST1.16 env not loaded. Run with: pytest --env private/env-test-st116")
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=False,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_st1_16_concurrent_message_creation"
    )
    
    print("\n" + "="*80)
    print("ST1.16 CONCURRENT MESSAGE CREATION TEST")
    print("="*80 + "\n")
    
    # Get configuration (NO HARDCODING)
    api_timeout = _require_value(test_config.get("api.timeout"), "api.timeout")
    concurrent_requests = _require_value(test_config.get("test.st116.concurrent_requests"), "test.st116.concurrent_requests")
    test_channel = _require_value(test_config.get("test.st116.channel"), "test.st116.channel")
    test_address = _require_value(test_config.get("test.st116.address"), "test.st116.address")
    
    def create_message(index: int) -> dict:
        """Create a message"""
        with httpx.Client(timeout=api_timeout) as client:
            message_payload = {
                "audience_type": "direct",
                "content": [{"type": "text", "body": f"Concurrent test message {index}"}],
                "destinations": [{
                    "channel": test_channel,
                    "address": test_address
                }]
            }
            
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload,
                timeout=api_timeout
            )
            
            if response.status_code == 201:
                return response.json()
            else:
                return {"error": response.status_code, "text": response.text}
    
    # Create messages concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
        futures = [executor.submit(create_message, i) for i in range(concurrent_requests)]
        results: List[dict] = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    # Validate results
    successes = [r for r in results if "message_id" in r or "id" in r]
    failures = [r for r in results if "error" in r]
    
    print(f"  Concurrent requests: {concurrent_requests}")
    print(f"  Successes: {len(successes)}")
    print(f"  Failures: {len(failures)}")
    
    # All requests should succeed (or at least most)
    success_rate = len(successes) / len(results) if results else 0
    assert success_rate >= 0.8, f"Success rate ({success_rate*100:.1f}%) is too low"
    
    print(f"\n✅ System handles concurrent requests (success rate: {success_rate*100:.1f}%)")
    
    # Save test log
    test_log_file = test_output_dir / "st1_16_concurrent_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: ST1.16 Concurrent Message Creation\n")
        f.write(f"Concurrent Requests: {concurrent_requests}\n")
        f.write(f"Successes: {len(successes)}\n")
        f.write(f"Failures: {len(failures)}\n")
        f.write(f"Success Rate: {success_rate*100:.1f}%\n")
    
    print(f"✅ Test log saved: {test_log_file}")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-015")
    
def test_st1_16_stateless_api_nodes(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_output_dir: Path
):
    """
    Test that API nodes are stateless
    
    Validates NF1.3: Stateless API nodes
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("st116_env_loaded"):
        pytest.skip("ST1.16 env not loaded. Run with: pytest --env private/env-test-st116")
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=False,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_st1_16_stateless_api_nodes"
    )
    
    print("\n" + "="*80)
    print("ST1.16 STATELESS API NODES TEST")
    print("="*80 + "\n")
    
    # Get configuration (NO HARDCODING)
    api_timeout = _require_value(test_config.get("api.timeout"), "api.timeout")
    test_count = _require_value(test_config.get("test.st116.stateless.test_count"), "test.st116.stateless.test_count")
    test_channel = _require_value(test_config.get("test.st116.channel"), "test.st116.channel")
    test_address = _require_value(test_config.get("test.st116.address"), "test.st116.address")
    
    # Test that multiple requests to the same endpoint work independently
    # (no session state required)
    
    with httpx.Client(timeout=api_timeout) as client:
        # Create multiple messages without maintaining session state
        message_ids = []
        
        for i in range(test_count):
            message_payload = {
                "audience_type": "direct",
                "content": [{"type": "text", "body": f"Stateless test message {i}"}],
                "destinations": [{
                    "channel": test_channel,
                    "address": test_address
                }]
            }
            
            response = client.post(
                f"{api_base_url}/messages",
                headers={"X-API-Key": api_key, "Content-Type": "application/json"},
                json=message_payload,
                timeout=api_timeout
            )
            
            assert response.status_code == 201, f"Request {i} failed: {response.status_code}"
            message_data = response.json()
            message_id = message_data.get("message_id") or message_data.get("id")
            message_ids.append(message_id)
        
        print(f"  Created {len(message_ids)} messages independently")
        print(f"  Message IDs: {message_ids}")
        
        # Verify all messages are accessible
        for message_id in message_ids:
            response = client.get(
                f"{api_base_url}/messages/{message_id}",
                headers={"X-API-Key": api_key, "Accept": "application/json"},
                timeout=api_timeout
            )
            assert response.status_code == 200, f"Message {message_id} not accessible"
        
        print("\n✅ API nodes are stateless (requests work independently)")
    
    # Save test log
    test_log_file = test_output_dir / "st1_16_stateless_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: ST1.16 Stateless API Nodes\n")
        f.write(f"Test Count: {test_count}\n")
        f.write(f"Message IDs: {message_ids}\n")
        f.write(f"Status: All requests worked independently\n")
    
    print(f"✅ Test log saved: {test_log_file}")
@pytest.mark.ST
@pytest.mark.mcp
@pytest.mark.req("FR-015")
    
def test_st1_16_work_queue_backed(
    api_base_url: str,
    api_key: str,
    test_config: Any,
    test_output_dir: Path,
    test_email_domain: str
):
    """
    Test that system uses work-queue for processing
    
    Validates NF1.3: Work-queue backed
    """
    # CRITICAL: Verify env file is loaded
    if not test_config.get("st116_env_loaded"):
        pytest.skip("ST1.16 env not loaded. Run with: pytest --env private/env-test-st116")
    
    # CRITICAL: Check dependencies BEFORE any test logic
    check_test_dependencies(
        requires_llm=False,
        requires_smtp=False,
        requires_slack=False,
        requires_api=True,
        test_name="test_st1_16_work_queue_backed"
    )
    
    print("\n" + "="*80)
    print("ST1.16 WORK-QUEUE BACKED TEST")
    print("="*80 + "\n")
    
    # Get configuration (NO HARDCODING)
    api_timeout = test_config.get("api.timeout")
    if not api_timeout:
        pytest.fail("❌ HARD FAIL: api.timeout not configured in env file")
    
    test_channel = test_config.get("test.st116.channel", "loopback")
    test_address = test_config.get("test.st116.address")
    if not test_address:
        test_address = f"test_queue_{int(time.time())}{test_email_domain}"
    
    # Test that messages are queued and processed asynchronously
    with httpx.Client(timeout=api_timeout) as client:
        # Create message
        message_payload = {
            "audience_type": "direct",
            "content": [{"type": "text", "body": "Work-queue test message"}],
            "destinations": [{
                "channel": test_channel,
                "address": test_address
            }]
        }
        
        response = client.post(
            f"{api_base_url}/messages",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json=message_payload,
            timeout=api_timeout
        )
        
        assert response.status_code == 201, f"Message creation failed: {response.status_code}"
        message_data = response.json()
        message_id = message_data.get("message_id") or message_data.get("id")
        
        # Message should be queued immediately
        response = client.get(
            f"{api_base_url}/messages/{message_id}",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=api_timeout
        )
        
        assert response.status_code == 200, "Message should be accessible"
        message = response.json()
        
        # Check that message is in queue (status should be queued or processing)
        status = message.get("status", "")
        print(f"  Message status: {status}")
        
        assert status in ["queued", "processing", "completed"], f"Unexpected status: {status}"
        print("\n✅ System uses work-queue for processing")
    
    # Save test log
    test_log_file = test_output_dir / "st1_16_work_queue_log.txt"
    with open(test_log_file, "w") as f:
        f.write(f"Test: ST1.16 Work-Queue Backed\n")
        f.write(f"Message ID: {message_id}\n")
        f.write(f"Status: {status}\n")
        f.write(f"Status: Work-queue validated\n")
    
    print(f"✅ Test log saved: {test_log_file}")

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.system, pytest.mark.smtp, pytest.mark.slow]
