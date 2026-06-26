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
Description: Reliability Module - Rate limiting, circuit breaker, backoff, TTL handling

Related Requirements: FR1.11, BO1.4
Related Tasks: T12
Related Architecture: CP1.1
Related Tests: ST1.2

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from .rate_limiter import RateLimiter
from .circuit_breaker import CircuitBreaker
from .backoff_manager import BackoffManager

__all__ = ["RateLimiter", "CircuitBreaker", "BackoffManager"]
