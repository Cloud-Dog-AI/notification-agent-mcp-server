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
Description: Database management for Notification Agent MCP Server - exports DatabaseManager and all repository classes

Related Requirements: FR1.3, NF1.2
Related Tasks: T4
Related Architecture: CC6.1, DM1.1
Related Tests: UT1.2

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from .db_manager import DatabaseManager, get_db_manager
from .repositories import (
    MessageRepository,
    DeliveryRepository,
    ReceiptRepository,
    ChannelRepository,
    UserRepository,
    TemplateRepository,
    AuditEventRepository,
)

__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "MessageRepository",
    "DeliveryRepository",
    "ReceiptRepository",
    "ChannelRepository",
    "UserRepository",
    "TemplateRepository",
    "AuditEventRepository",
]
