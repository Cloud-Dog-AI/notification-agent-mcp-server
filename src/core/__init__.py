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
Description: Core functionality for Notification Agent MCP Server - Job Manager, State Machine, and core components

Related Requirements: FR1.1, FR1.2
Related Tasks: T5
Related Architecture: CC2.1
Related Tests: UT1.3

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from .jobs import JobManager
from .state_machine import DeliveryState, MessageStatus

__all__ = ["JobManager", "DeliveryState", "MessageStatus"]
