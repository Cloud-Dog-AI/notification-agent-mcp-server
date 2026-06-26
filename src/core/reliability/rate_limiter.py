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
Description: Rate Limiter - Per-channel and per-destination rate limiting

Related Requirements: FR1.11
Related Tasks: T12
Related Architecture: CP1.1.1
Related Tests: ST1.2

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import time
from typing import Dict, Any, Optional, Tuple
from threading import Lock
from collections import defaultdict
from cloud_dog_jobs.scheduler.concurrency import ConcurrencyLimits

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for per-channel and per-destination rate limits"""
    
    def __init__(
        self,
        default_limit: int = 100,
        window_seconds: int = 60,
        per_channel_limits: Optional[Dict[str, int]] = None,
        per_destination_limits: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize rate limiter
        
        Args:
            default_limit: Default requests per window
            window_seconds: Time window in seconds
            per_channel_limits: Per-channel limits (channel_name -> limit)
            per_destination_limits: Per-destination limits (destination -> limit)
        """
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self.per_channel_limits = per_channel_limits or {}
        self.per_destination_limits = per_destination_limits or {}
        max_channel_limit = max(self.per_channel_limits.values(), default=default_limit)
        max_destination_limit = max(self.per_destination_limits.values(), default=default_limit)
        self._limits = ConcurrencyLimits(
            global_max=int(default_limit),
            per_type_max=int(max_channel_limit),
            per_tenant_max=int(max_destination_limit),
            per_user_max=int(default_limit),
        )
        
        # Track requests: identifier -> list of timestamps
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = Lock()
        
        logger.info(f"RateLimiter initialized: default={default_limit}/{window_seconds}s")
    
    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if request is allowed
        
        Args:
            identifier: Identifier (channel_name or destination)
            limit: Override limit (optional)
            window_seconds: Override window (optional)
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        with self.lock:
            # Determine limit and window
            effective_limit = limit or self._get_limit(identifier)
            effective_window = window_seconds or self.window_seconds
            
            # Get request history for this identifier
            request_times = self.requests[identifier]
            now = time.time()
            
            # Remove old requests outside window
            cutoff = now - effective_window
            while request_times and request_times[0] < cutoff:
                request_times.pop(0)
            
            # Check if limit exceeded
            if len(request_times) >= effective_limit:
                # Calculate retry after
                oldest_request = request_times[0]
                retry_after = effective_window - (now - oldest_request)
                return False, max(0, retry_after)
            
            # Add current request
            request_times.append(now)
            return True, None
    
    def _get_limit(self, identifier: str) -> int:
        """Get limit for identifier"""
        # Check per-destination first
        if identifier in self.per_destination_limits:
            return self.per_destination_limits[identifier]
        
        # Check per-channel
        if identifier in self.per_channel_limits:
            return self.per_channel_limits[identifier]
        
        # Default
        return int(self._limits.global_max)
    
    def reset(self, identifier: Optional[str] = None):
        """Reset rate limit for identifier (or all if None)"""
        with self.lock:
            if identifier:
                if identifier in self.requests:
                    del self.requests[identifier]
            else:
                self.requests.clear()
    
    def get_stats(self, identifier: str) -> Dict[str, Any]:
        """Get rate limit statistics for identifier"""
        with self.lock:
            request_times = self.requests.get(identifier, [])
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Count requests in window
            count = sum(1 for t in request_times if t >= cutoff)
            limit = self._get_limit(identifier)
            
            return {
                "identifier": identifier,
                "count": count,
                "limit": limit,
                "remaining": max(0, limit - count),
                "window_seconds": self.window_seconds
            }
