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
Description: Channel adapters for notification delivery - exports base adapter, mock adapters, and registry

Related Requirements: FR1.6, FR1.7, FR1.8, FR1.9
Related Tasks: T6, T17, T18, T19, T20
Related Architecture: CC5.1
Related Tests: UT1.4, IT1.12

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""

from .base import BaseChannelAdapter, SendResult, ErrorClass
from .mock_email import MockEmailAdapter
from .mock_sms import MockSMSAdapter
from .mock_chat import MockChatAdapter
from .registry import AdapterRegistry, get_adapter_registry

__all__ = [
    "BaseChannelAdapter",
    "SendResult",
    "ErrorClass",
    "MockEmailAdapter",
    "MockSMSAdapter",
    "MockChatAdapter",
    "AdapterRegistry",
    "get_adapter_registry",
]
