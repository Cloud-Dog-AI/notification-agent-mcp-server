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
Test Message Loader Utility

Loads test messages from tests/Examples/ folder for use in all tests.
All tests MUST use these example messages, not hardcoded content.
"""

from pathlib import Path
from typing import Optional

# Base path to test Examples directory
EXAMPLES_DIR = Path(__file__).parent.parent / "Examples"

# Available test messages
TEST_MESSAGES = {
    "simple": "Test-Simple.md",
    "brief_news": "Test-Brief-News.md",
    "large_text": "Test-Large-Text.md",
    "multimedia_image": "Test-Multimedia-Image.md",
    "multimedia_audio": "Test-Multimedia-Audio.md",
}


def load_test_message(message_type: str, max_length: Optional[int] = None) -> str:
    """
    Load a test message from the Examples directory.
    
    Args:
        message_type: One of: 'simple', 'brief_news', 'large_text', 
                     'multimedia_image', 'multimedia_audio'
        max_length: Optional maximum length to truncate content
        
    Returns:
        Message content as string
        
    Raises:
        FileNotFoundError: If message file doesn't exist
        ValueError: If message_type is invalid
    """
    if message_type not in TEST_MESSAGES:
        raise ValueError(
            f"Invalid message_type '{message_type}'. "
            f"Must be one of: {list(TEST_MESSAGES.keys())}"
        )
    
    message_file = EXAMPLES_DIR / TEST_MESSAGES[message_type]
    
    if not message_file.exists():
        raise FileNotFoundError(
            f"Test message file not found: {message_file}\n"
            f"Expected location: {EXAMPLES_DIR}"
        )
    
    with open(message_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if max_length and len(content) > max_length:
        content = content[:max_length]
    
    return content


def get_test_message_path(message_type: str) -> Path:
    """
    Get the Path object for a test message file.
    
    Args:
        message_type: One of the available message types
        
    Returns:
        Path object to the message file
    """
    if message_type not in TEST_MESSAGES:
        raise ValueError(
            f"Invalid message_type '{message_type}'. "
            f"Must be one of: {list(TEST_MESSAGES.keys())}"
        )
    
    return EXAMPLES_DIR / TEST_MESSAGES[message_type]


def list_available_messages() -> list:
    """Return list of available message types."""
    return list(TEST_MESSAGES.keys())

