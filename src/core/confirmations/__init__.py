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
Description: Confirmation management for delivery tracking - exports CallbackProcessor and ConfirmationPoller

Related Requirements: FR1.2
Related Tasks: T7
Related Architecture: CC2.1.4
Related Tests: IT1.10

Recent Changes (max 10):
- (Initial header added)

**************************************************
"""
from .processor import CallbackProcessor
from .poller import ConfirmationPoller

__all__ = ["CallbackProcessor", "ConfirmationPoller"]
