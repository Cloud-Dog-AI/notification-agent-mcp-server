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
Description: Circuit Breaker - Soft/hard error thresholds, degraded/unavailable states

Related Requirements: FR1.11
Related Tasks: T12
Related Architecture: CP1.1.2
Related Tests: ST1.2

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import time
from enum import Enum
from typing import Callable, Any, Optional, Dict
from threading import Lock

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        success_threshold: int = 2,
        name: str = "circuit"
    ):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening
            timeout_seconds: Time before attempting half-open
            success_threshold: Successes needed to close from half-open
            name: Circuit name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = Lock()
        
        logger.info(f"CircuitBreaker '{name}' initialized: threshold={failure_threshold}, timeout={timeout_seconds}s")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function with circuit breaker protection
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: If circuit is open or function fails
        """
        with self.lock:
            # Check if we should transition to half-open
            if self.state == CircuitState.OPEN:
                if self.last_failure_time and (time.time() - self.last_failure_time) >= self.timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"CircuitBreaker '{self.name}' transitioning to HALF_OPEN")
                else:
                    raise Exception(f"CircuitBreaker '{self.name}' is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise
    
    def _record_success(self):
        """Record successful call"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"CircuitBreaker '{self.name}' closed after {self.success_count} successes")
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    def _record_failure(self):
        """Record failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed during half-open, go back to open
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.warning(f"CircuitBreaker '{self.name}' opened after failure in HALF_OPEN")
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(f"CircuitBreaker '{self.name}' opened after {self.failure_count} failures")
    
    def reset(self):
        """Manually reset circuit breaker to closed state"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"CircuitBreaker '{self.name}' manually reset")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "failure_threshold": self.failure_threshold,
                "timeout_seconds": self.timeout_seconds
            }
