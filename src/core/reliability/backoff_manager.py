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
Description: Backoff Manager - Exponential backoff with jitter

Related Requirements: FR1.11
Related Tasks: T12
Related Architecture: CP1.1.3
Related Tests: ST1.2

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import time
from cloud_dog_jobs.scheduler.policies import exponential_backoff_seconds

logger = get_logger(__name__)


class BackoffManager:
    """Exponential backoff with jitter"""
    
    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter_factor: float = 0.1
    ):
        """
        Initialize backoff manager
        
        Args:
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            multiplier: Exponential multiplier
            jitter_factor: Jitter as fraction of delay (0.1 = 10%)
        """
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter_factor = jitter_factor
        
        logger.info(f"BackoffManager initialized: initial={initial_delay}s, max={max_delay}s, multiplier={multiplier}")
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for attempt number
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = exponential_backoff_seconds(
            attempt=max(0, int(attempt)),
            base=float(self.initial_delay),
            maximum=float(self.max_delay),
            jitter=self.jitter_factor > 0,
        )
        return max(0, float(delay))
    
    def wait(self, attempt: int):
        """
        Wait for calculated delay
        
        Args:
            attempt: Attempt number (0-based)
        """
        delay = self.calculate_delay(attempt)
        if delay > 0:
            logger.debug(f"Backoff wait: attempt={attempt}, delay={delay:.2f}s")
            time.sleep(delay)
    
    async def async_wait(self, attempt: int):
        """
        Async wait for calculated delay
        
        Args:
            attempt: Attempt number (0-based)
        """
        import asyncio
        delay = self.calculate_delay(attempt)
        if delay > 0:
            logger.debug(f"Backoff async wait: attempt={attempt}, delay={delay:.2f}s")
            await asyncio.sleep(delay)
