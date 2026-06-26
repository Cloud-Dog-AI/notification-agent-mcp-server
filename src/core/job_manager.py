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

"""Compatibility exports for the notification queue coordinator.

New code should import JobManager from ``src.core.jobs``.  This module remains
for existing tests, API servers, and worker entry points that still import the
legacy ``src.core.job_manager`` path.
"""

from .jobs.queue_coordinator import JobManager, QueueCoordinator

__all__ = ["JobManager", "QueueCoordinator"]
