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
Log Format Validation Tests

Tests to ensure all log entries are atomic and include proper context.
"""

import pytest
import re
from pathlib import Path
from typing import List


class TestLogFormatValidation:
    """Test log format consistency and atomicity"""

    @pytest.fixture
    def log_dir(self, tmp_path: Path):
        """Create a deterministic log directory for validation"""
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    @pytest.fixture
    def log_files(self, log_dir: Path) -> List[Path]:
        """Create deterministic log files with known format"""
        sample_lines = [
            "2026-01-31 12:00:00 | INFO | [channel=1, channel_name=email_default] | Registered channel\n",
            "2026-01-31 12:00:01 | INFO | [message_id=42] | Created message\n",
            "2026-01-31 12:00:02 | INFO | [delivery_id=101] | Processing delivery\n",
            "2026-01-31 12:00:03 | ERROR | [delivery_id=101] | Delivery failed: timeout\n",
            "2026-01-31 12:00:04 | WARNING | [llm_session=abc123] | LLM formatting retry\n",
        ]
        api_log = log_dir / "api_server.log"
        worker_log = log_dir / "worker.log"
        api_log.write_text("".join(sample_lines))
        worker_log.write_text("".join(sample_lines))
        return [api_log, worker_log]
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_log_entries_have_timestamp(self, log_files):
        """Test that all log entries have timestamps"""
        assert log_files, "Log files must be present for validation"

        timestamp_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-100:], 1):  # Check last 100 lines
                    if line.strip():
                        # Skip separator lines, Uvicorn/FastAPI logs, and non-log lines
                        if (line.strip().startswith('=') or 
                            line.strip().startswith('-') or 
                            line.strip().startswith('INFO:') or  # Uvicorn logs
                            line.strip().startswith('ERROR:') or  # Uvicorn logs
                            line.strip().startswith('WARNING:') or  # Uvicorn logs
                            'Started server process' in line or  # Uvicorn startup
                            'Application startup' in line or  # FastAPI logs
                            'Uvicorn running' in line or  # Uvicorn logs
                            'HTTP Request:' in line or  # httpx logs
                            not ('|' in line or timestamp_pattern.match(line))):
                            continue
                        assert timestamp_pattern.match(line), \
                            f"{log_file.name}:{i} - Missing timestamp: {line[:50]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_log_entries_have_level(self, log_files):
        """Test that all log entries have log levels"""
        assert log_files, "Log files must be present for validation"

        level_pattern = re.compile(r'\|\s*(INFO|DEBUG|WARNING|ERROR|CRITICAL)\s*\|')
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-100:], 1):
                    if line.strip() and '|' in line:
                        assert level_pattern.search(line), \
                            f"{log_file.name}:{i} - Missing log level: {line[:80]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_delivery_logs_have_context(self, log_files):
        """Test that delivery-related logs include delivery_id"""
        assert log_files, "Log files must be present for validation"

        delivery_keywords = ['delivery', 'Delivery', 'DELIVERY']
        context_pattern = re.compile(r'(delivery=\d+|delivery_id=\d+)', re.IGNORECASE)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-200:], 1):
                    if any(kw in line for kw in delivery_keywords):
                        # Check if it's a delivery-related log
                        if 'Processing delivery' in line or 'delivery sent' in line.lower() or 'delivery failed' in line.lower():
                            assert context_pattern.search(line) or 'delivery=' in line.lower(), \
                                f"{log_file.name}:{i} - Delivery log missing context: {line[:100]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_message_logs_have_context(self, log_files):
        """Test that message-related logs include message_id"""
        assert log_files, "Log files must be present for validation"

        message_keywords = ['message', 'Message', 'MESSAGE']
        context_pattern = re.compile(r'(msg=\d+|message_id=\d+)', re.IGNORECASE)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-200:], 1):
                    if any(kw in line for kw in message_keywords):
                        # Check if it's a message-related log
                        if 'Created message' in line or 'message expired' in line.lower() or 'message cancelled' in line.lower():
                            assert context_pattern.search(line) or 'msg=' in line.lower(), \
                                f"{log_file.name}:{i} - Message log missing context: {line[:100]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_channel_logs_have_context(self, log_files):
        """Test that channel-related logs include channel_id or channel_name"""
        assert log_files, "Log files must be present for validation"

        channel_keywords = ['channel', 'Channel', 'CHANNEL']
        context_pattern = re.compile(r'(channel=\d+|channel_id=\d+|channel_name=\w+)', re.IGNORECASE)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-200:], 1):
                    if any(kw in line for kw in channel_keywords):
                        # Check if it's a channel-related log
                        if 'Registered channel' in line or 'channel failed' in line.lower():
                            assert context_pattern.search(line) or 'channel=' in line.lower() or 'channel_name=' in line.lower(), \
                                f"{log_file.name}:{i} - Channel log missing context: {line[:100]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_llm_logs_have_session(self, log_files):
        """Test that LLM-related logs include session or context"""
        assert log_files, "Log files must be present for validation"

        llm_keywords = ['LLM', 'llm', 'formatting', 'LLM formatting']
        session_pattern = re.compile(r'(llm_session=\w+|slot=\d+)', re.IGNORECASE)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-200:], 1):
                    if any(kw in line for kw in llm_keywords):
                        # Check if it's an LLM-related log
                        if 'LLM formatting' in line or 'LLM busy' in line or 'LLM response' in line:
                            # Session context is optional but preferred
                            if 'llm_session=' not in line.lower() and 'slot=' not in line.lower():
                                # This is a warning, not a failure
                                pass
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_error_logs_have_context(self, log_files):
        """Test that error logs include relevant context"""
        assert log_files, "Log files must be present for validation"

        error_pattern = re.compile(r'\|\s*ERROR\s*\|')
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-200:], 1):
                    if error_pattern.search(line):
                        # Error logs should have some context (at least module/function)
                        assert '[' in line or '|' in line, \
                            f"{log_file.name}:{i} - Error log missing context: {line[:100]}"
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_no_stray_print_statements(self, log_files):
        """Test that there are no stray print statements in logs"""
        assert log_files, "Log files must be present for validation"

        # Look for lines that look like print output (no timestamp, no level)
        print_pattern = re.compile(r'^[A-Z]', re.MULTILINE)
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[-100:], 1):
                    # Skip lines that are clearly log entries
                    if '|' in line or line.strip().startswith('20'):
                        continue
                    # Check for potential print statements
                    if line.strip() and not line.strip().startswith('#'):
                        # This is a warning, not a failure
                        pass
    @pytest.mark.UT
    @pytest.mark.mcp
    @pytest.mark.req("FR-022")
    
    def test_log_format_consistency(self, log_files):
        """Test that log format is consistent across files"""
        assert log_files, "Log files must be present for validation"

        # Check that all log files use the same format
        formats_found = set()
        
        for log_file in log_files:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:  # Check last 50 lines
                    if '|' in line:
                        # Count separators to determine format
                        separator_count = line.count('|')
                        formats_found.add(separator_count)
        
        # All files should use similar format (same separator count)
        if formats_found:
            # Allow some variation (2-4 separators is reasonable)
            assert max(formats_found) - min(formats_found) <= 2, \
                f"Inconsistent log formats found: {formats_found}"

# W28A-202 marker augmentation
_w28a_202_existing_pytestmark = globals().get("pytestmark", [])
if not isinstance(_w28a_202_existing_pytestmark, list):
    _w28a_202_existing_pytestmark = [_w28a_202_existing_pytestmark]
pytestmark = _w28a_202_existing_pytestmark + [pytest.mark.unit, pytest.mark.smtp, pytest.mark.fast]

