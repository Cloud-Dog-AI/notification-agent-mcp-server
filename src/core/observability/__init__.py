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
Description: Observability Module - Metrics, tracing, and structured logging

Related Requirements: FR1.12
Related Tasks: T33
Related Architecture: MO1.1, MO1.2, MO1.3
Related Tests: ST1.3

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from .metrics import MetricsCollector, setup_metrics
from .tracing import TraceContext, trace_adapter_operation

__all__ = ["MetricsCollector", "setup_metrics", "TraceContext", "trace_adapter_operation"]
