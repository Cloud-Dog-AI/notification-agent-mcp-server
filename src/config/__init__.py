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
**************************************************
License: Apache 2.0
Ownership: Cloud Dog
Description: Configuration bridge exports for Notification Agent MCP Server

Related Requirements: NF1.5
Related Tasks: T3
Related Architecture: CM1.1
Related Tests: UT1.1

Recent Changes (max 10):
- 2026-02-24: Export RuntimeConfig and get_config from cloud_dog_config bridge

**************************************************
"""

from .runtime_config import RuntimeConfig, get_config

__all__ = ["RuntimeConfig", "get_config"]
