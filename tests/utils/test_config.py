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
Test configuration utilities

Provides helper functions for tests to access configuration
following the hierarchy: os.environ -> env file -> config.yaml -> defaults.yaml
"""

from pathlib import Path
from typing import Optional, Dict, Any

def get_test_config(env_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get test configuration using config hierarchy.
    
    Args:
        env_file: Path to env file (required)
    
    Returns:
        RuntimeConfig instance
    
    Raises:
        ValueError: If required settings are missing
    """
    from src.config import RuntimeConfig
    
    if not env_file:
        raise ValueError(
            "Environment file is required. Use: pytest --env <env-file>"
        )
    
    env_path = Path(env_file)
    if not env_path.exists():
        raise ValueError(
            f"Environment file not found: {env_file}\n"
            f"Specify with: pytest --env <env-file>"
        )
    
    config = RuntimeConfig(env_file=str(env_path), load_env_file=True)
    
    # Verify critical settings
    missing = []
    if not config.get("api_server.api_key"):
        missing.append("api_server.api_key")
    if not config.get("api_server.base_url"):
        missing.append("api_server.base_url")
    
    if missing:
        raise ValueError(
            f"Missing required settings: {', '.join(missing)}\n"
            f"Check your env file: {env_file}"
        )
    
    return config

