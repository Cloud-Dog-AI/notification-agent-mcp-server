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
Test helper utilities for multimedia tests

Provides:
- Server health checks
- Delivery status polling with better diagnostics
- Test artifact collection
- Performance metrics
"""

import os
import time
import httpx
import sys
import pytest
from typing import Optional, Dict, Any, List
from pathlib import Path

# Add project root to path for config access
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config


# NO hardcoded values - all functions accept api_base_url and api_key as parameters

def get_headers(api_key: str) -> Dict[str, str]:
    """Get standard API headers"""
    return {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def check_server_health(api_base_url: str, timeout: float = 5.0) -> bool:
    """
    Check if API server is running and healthy
    
    Args:
        api_base_url: API server base URL
        timeout: Request timeout
    
    Returns:
        True if server is healthy, False otherwise
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{api_base_url}/health", timeout=timeout)
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def check_delivery_worker_status(api_base_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Check delivery worker status via LLM status endpoint
    
    Args:
        api_base_url: API server base URL
        api_key: API key
    
    Returns:
        Dict with worker status or None if unavailable
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{api_base_url}/llm/status",
                headers=get_headers(api_key),
                timeout=5.0
            )
            if response.status_code == 200:
                return response.json()
    except Exception:
        pass
    return None


def wait_for_llm_ready(
    config,
    *,
    grace_period_seconds: float,
    retry_delay_seconds: float,
    llm_base_url: str,
    llm_model: str,
    verbose: bool = True,
) -> Optional[str]:
    """
    Wait for LLM to become available, handling resets/timeouts.
    
    Returns an error string if LLM is still unavailable after grace period.
    """
    if verbose:
        print(
            f"[LLM Wait] grace_period={grace_period_seconds}s, "
            f"retry_delay={retry_delay_seconds}s, model={llm_model}"
        )
    deadline = time.monotonic() + grace_period_seconds
    last_error = None
    
    while time.monotonic() < deadline:
        try:
            from src.core.llm.runtime_client import LLMManager
            llm_mgr = LLMManager(config)
            llm_mgr.connect()
            if llm_mgr.get_llm():
                return None
            last_error = f"LLM not available at {llm_base_url} (model {llm_model})"
        except Exception as e:
            last_error = str(e)
        
        time.sleep(retry_delay_seconds)
    
    return last_error or f"LLM not available at {llm_base_url} (model {llm_model})"


def wait_for_delivery_with_diagnostics(
    api_client: httpx.Client,
    message_id: int,
    api_base_url: str,
    api_key: str,
    max_wait: float = 120.0,
    poll_interval: float = 2.0,
    verbose: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Wait for delivery to complete with detailed diagnostics
    
    Args:
        api_client: HTTP client
        message_id: Message ID to check
        api_base_url: API server base URL
        api_key: API key
        max_wait: Maximum time to wait (seconds)
        poll_interval: Time between polls (seconds)
        verbose: Print diagnostic information
    
    Returns:
        Delivery dict if complete, None if timeout
    """
    start_time = time.time()
    last_state = None
    state_changes = []
    
    if verbose:
        print(f"\n[Delivery Wait] Message {message_id}, max_wait={max_wait}s")

    def _cancel_stale_queued_messages() -> None:
        try:
            list_resp = api_client.get(
                f"{api_base_url}/messages",
                headers=get_headers(api_key),
                params={"status": "queued", "limit": 200},
                timeout=10.0,
            )
            if list_resp.status_code != 200:
                return
            payload = list_resp.json()
            items = payload if isinstance(payload, list) else payload.get("items", [])
            for item in items:
                stale_id = item.get("id") if isinstance(item, dict) else None
                if stale_id is None or int(stale_id) == int(message_id):
                    continue
                try:
                    api_client.post(
                        f"{api_base_url}/messages/{int(stale_id)}/cancel",
                        headers=get_headers(api_key),
                        timeout=10.0,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Full integration runs share the runtime queue across suites. Cancel
    # stale queued messages first so the target message can make progress.
    _cancel_stale_queued_messages()
    
    while time.time() - start_time < max_wait:
        try:
            # Get message with deliveries
            response = api_client.get(
                f"{api_base_url}/messages/{message_id}",
                headers=get_headers(api_key),
                timeout=10.0
            )
            
            if response.status_code == 200:
                message_data = response.json()
                deliveries = message_data.get("deliveries", [])
                if isinstance(deliveries, dict):
                    # Some endpoints return delivery summaries; fetch full items.
                    deliveries_resp = api_client.get(
                        f"{api_base_url}/messages/{message_id}/deliveries",
                        headers=get_headers(api_key),
                        timeout=10.0,
                    )
                    if deliveries_resp.status_code == 200:
                        payload = deliveries_resp.json()
                        deliveries = payload.get("items", [])
                    else:
                        deliveries = []
                
                if deliveries:
                    # Check all delivery states
                    states = [d.get("state", "unknown") for d in deliveries]
                    current_state = ", ".join(set(states))
                    
                    # Track state changes
                    if current_state != last_state:
                        state_changes.append((time.time() - start_time, current_state))
                        last_state = current_state
                        if verbose:
                            print(f"  [{time.time() - start_time:.1f}s] State: {current_state}")
                    
                    # Check if all deliveries are complete
                    terminal_states = {"sent", "delivered", "failed", "hard_failed", "ttl_expired", "cancelled"}
                    all_complete = all(
                        d.get("state", "").lower() in terminal_states or 
                        d.get("state", "").lower() in [s.lower() for s in terminal_states]
                        for d in deliveries
                    )
                    
                    if all_complete:
                        if verbose:
                            print(f"  [✓] All deliveries complete in {time.time() - start_time:.1f}s")
                        return deliveries[0] if deliveries else None
                    
                    # Check for stuck deliveries
                    queued_count = sum(1 for d in deliveries if d.get("state", "").lower() == "queued")
                    if queued_count > 0 and time.time() - start_time > 30:
                        if verbose:
                            print(f"  [⚠] {queued_count} delivery(ies) still queued after {time.time() - start_time:.1f}s")
                        _cancel_stale_queued_messages()
            
            time.sleep(poll_interval)
            
        except Exception as e:
            if verbose:
                print(f"  [✗] Error checking delivery: {e}")
            time.sleep(poll_interval)
    
    if verbose:
        print(f"  [✗] Timeout after {max_wait}s")
        if state_changes:
            print(f"  State changes: {state_changes}")
    
    return None


def collect_test_artifacts(
    message_id: int,
    api_base_url: str,
    api_key: str,
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Collect test artifacts (PDFs, HTML pages, etc.) for manual inspection
    
    Args:
        message_id: Message ID
        api_base_url: API server base URL
        api_key: API key
        output_dir: Directory to save artifacts (default: test_artifacts/)
    
    Returns:
        Dict with artifact paths and metadata
    """
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "test_artifacts" / f"message_{message_id}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    artifacts = {
        "message_id": message_id,
        "output_dir": str(output_dir),
        "files": []
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            # Get message details
            response = client.get(
                f"{api_base_url}/messages/{message_id}",
                headers=get_headers(api_key),
                timeout=10.0
            )
            
            if response.status_code == 200:
                message_data = response.json()
                
                # Save message JSON
                message_file = output_dir / "message.json"
                import json
                with open(message_file, "w") as f:
                    json.dump(message_data, f, indent=2)
                artifacts["files"].append(str(message_file))
                
                # Get deliveries
                deliveries = message_data.get("deliveries", [])
                for delivery in deliveries:
                    delivery_id = delivery.get("id")
                    
                    # Get delivery details
                    deliv_response = client.get(
                        f"{api_base_url}/deliveries/{delivery_id}",
                        headers=get_headers(api_key),
                        timeout=10.0
                    )
                    
                    if deliv_response.status_code == 200:
                        delivery_data = deliv_response.json()
                        
                        # Save delivery JSON
                        delivery_file = output_dir / f"delivery_{delivery_id}.json"
                        with open(delivery_file, "w") as f:
                            json.dump(delivery_data, f, indent=2)
                        artifacts["files"].append(str(delivery_file))
                        
                        # Extract PDFs from attachments
                        payload_str = delivery_data.get("personalised_payload", "{}")
                        if isinstance(payload_str, str):
                            payload = json.loads(payload_str)
                        else:
                            payload = payload_str
                        
                        attachments = payload.get("attachments", [])
                        for i, att in enumerate(attachments):
                            if att.get("content_type") == "application/pdf" or att.get("filename", "").endswith(".pdf"):
                                content = att.get("content")
                                if isinstance(content, str):
                                    import base64
                                    pdf_data = base64.b64decode(content)
                                    pdf_file = output_dir / f"delivery_{delivery_id}_attachment_{i}.pdf"
                                    with open(pdf_file, "wb") as f:
                                        f.write(pdf_data)
                                    artifacts["files"].append(str(pdf_file))
    
    except Exception as e:
        artifacts["error"] = str(e)
    
    return artifacts


def get_performance_metrics(message_id: int, api_base_url: str, api_key: str) -> Dict[str, Any]:
    """
    Get performance metrics for a message
    
    Args:
        message_id: Message ID
        api_base_url: API server base URL
        api_key: API key
    
    Returns:
        Dict with timing information
    """
    metrics = {
        "message_id": message_id,
        "timings": {}
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(
                f"{api_base_url}/messages/{message_id}",
                headers=get_headers(api_key),
                timeout=10.0
            )
            
            if response.status_code == 200:
                message_data = response.json()
                
                # Extract timing from message metadata
                created_at = message_data.get("created_at")
                updated_at = message_data.get("updated_at")
                
                if created_at and updated_at:
                    from datetime import datetime
                    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    duration = (updated - created).total_seconds()
                    metrics["timings"]["total_duration"] = duration
                
                # Get delivery timings
                deliveries = message_data.get("deliveries", [])
                delivery_timings = []
                for delivery in deliveries:
                    deliv_created = delivery.get("created_at")
                    deliv_updated = delivery.get("updated_at")
                    if deliv_created and deliv_updated:
                        from datetime import datetime
                        created = datetime.fromisoformat(deliv_created.replace("Z", "+00:00"))
                        updated = datetime.fromisoformat(deliv_updated.replace("Z", "+00:00"))
                        duration = (updated - created).total_seconds()
                        delivery_timings.append({
                            "delivery_id": delivery.get("id"),
                            "state": delivery.get("state"),
                            "duration": duration
                        })
                
                metrics["timings"]["deliveries"] = delivery_timings
    
    except Exception as e:
        metrics["error"] = str(e)
    
    return metrics


def check_test_dependencies(
    requires_llm: bool = False,
    requires_smtp: bool = False,
    requires_slack: bool = False,
    requires_api: bool = True,
    test_name: str = "test"
) -> None:
    """
    CRITICAL: Check all dependencies for a test BEFORE running test logic.
    This MUST be called at the start of EVERY test function.
    
    Args:
        requires_llm: Test requires LLM (for formatting/translation)
        requires_smtp: Test requires SMTP (for email delivery)
        requires_slack: Test requires Slack (for Slack delivery)
        requires_api: Test requires API server (default: True)
        test_name: Name of the test (for error messages)
    
    Raises:
        pytest.fail: If any required dependency is missing
    """
    config = get_config()
    missing = []
    
    # Check API server (required by default)
    if requires_api:
        api_key = config.get("api_server.api_key")
        api_base_url = config.get("api_server.base_url")
        if not api_key:
            missing.append("API Server API Key (api_server.api_key)")
        if not api_base_url:
            missing.append("API Server Base URL (api_server.base_url)")
    
    # Check LLM (if required) - CRITICAL: LLM must be available and working
    if requires_llm:
        llm_provider = config.get("llm.provider")
        llm_base_url = config.get("llm.base_url")
        llm_model = config.get("llm.model")
        if not llm_provider:
            missing.append("LLM Provider (llm.provider)")
        if not llm_base_url:
            missing.append("LLM Base URL (llm.base_url)")
        if not llm_model:
            missing.append("LLM Model (llm.model)")
        
        # CRITICAL: Verify LLM is actually available and working
        if llm_provider and llm_base_url and llm_model:
            try:
                llm_grace = config.get("llm.model_load_timeout")
                retry_delay = config.get("api.connect_timeout") or config.get("api.read_timeout")
                if not llm_grace:
                    missing.append("LLM Model Load Timeout (llm.model_load_timeout)")
                if not retry_delay:
                    missing.append("API Connect Timeout (api.connect_timeout) or API Read Timeout (api.read_timeout)")
                
                if not missing:
                    llm_error = wait_for_llm_ready(
                        config,
                        grace_period_seconds=float(llm_grace),
                        retry_delay_seconds=float(retry_delay),
                        llm_base_url=llm_base_url,
                        llm_model=llm_model,
                    )
                    if llm_error:
                        missing.append(f"LLM Connection Failed: {llm_error}")
            except Exception as e:
                missing.append(f"LLM Connection Failed: {str(e)}")
    
    # Check SMTP (if required)
    if requires_smtp:
        smtp_config = config.get("channels.smtp.default", {})
        if not smtp_config.get("enabled"):
            missing.append("SMTP Channel Enabled (channels.smtp.default.enabled)")
        if not smtp_config.get("host"):
            missing.append("SMTP Host (channels.smtp.default.host)")
        if not smtp_config.get("from_address"):
            missing.append("SMTP From Address (channels.smtp.default.from_address)")
    
    # Check Slack (if required)
    if requires_slack:
        slack_config = config.get("channels.chat_rest.transparentbordes", {})
        if not slack_config.get("enabled"):
            missing.append("Slack Channel Enabled (channels.chat_rest.transparentbordes.enabled)")
        if not slack_config.get("endpoint"):
            missing.append("Slack Webhook Endpoint (channels.chat_rest.transparentbordes.endpoint)")
    
    # Fail immediately if dependencies are missing
    if missing:
        pytest.fail(
            f"❌ {test_name}: MISSING REQUIRED DEPENDENCIES:\n"
            f"{chr(10).join('  - ' + m for m in missing)}\n"
            f"Configure in env file (e.g., private/env-test) with:\n"
            f"  CLOUD_DOG__NOTIFY__<SETTING>=...\n"
            f"Test will NOT run until all dependencies are configured."
        )
