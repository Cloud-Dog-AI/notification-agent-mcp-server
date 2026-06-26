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
Description: Tracing - Traces around adapter operations

Related Requirements: FR1.12
Related Tasks: T33
Related Architecture: MO1.3
Related Tests: ST1.3

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import time
import uuid
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from functools import wraps

logger = get_logger(__name__)


class TraceContext:
    """Trace context for distributed tracing"""
    
    def __init__(self, trace_id: Optional[str] = None, span_id: Optional[str] = None):
        """
        Initialize trace context
        
        Args:
            trace_id: Trace ID (generated if not provided)
            span_id: Span ID (generated if not provided)
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.tags: Dict[str, Any] = {}
        self.logs: list = []
    
    def add_tag(self, key: str, value: Any):
        """Add tag to trace"""
        self.tags[key] = value
    
    def add_log(self, message: str, level: str = "INFO", **kwargs):
        """Add log entry to trace"""
        self.logs.append({
            "timestamp": time.time(),
            "message": message,
            "level": level,
            **kwargs
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace context to dictionary"""
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time) * 1000  # milliseconds
        
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": duration,
            "tags": self.tags,
            "logs": self.logs
        }


@contextmanager
def trace_adapter_operation(
    adapter_name: str,
    operation: str,
    message_id: Optional[int] = None,
    delivery_id: Optional[int] = None,
    **tags
):
    """
    Context manager for tracing adapter operations
    
    Args:
        adapter_name: Name of adapter
        operation: Operation name (e.g., "send", "confirm")
        message_id: Optional message ID
        delivery_id: Optional delivery ID
        **tags: Additional tags
    
    Yields:
        TraceContext
    """
    trace = TraceContext()
    trace.add_tag("adapter", adapter_name)
    trace.add_tag("operation", operation)
    
    if message_id:
        trace.add_tag("message_id", message_id)
    if delivery_id:
        trace.add_tag("delivery_id", delivery_id)
    
    for key, value in tags.items():
        trace.add_tag(key, value)
    
    trace.start_time = time.time()
    trace.add_log(f"Starting {operation} on {adapter_name}")
    
    try:
        yield trace
        trace.end_time = time.time()
        trace.add_log(f"Completed {operation} on {adapter_name}", level="INFO")
        
        # Log trace
        logger.info(
            "Adapter operation trace",
            extra={
                "trace_id": trace.trace_id,
                "span_id": trace.span_id,
                "adapter": adapter_name,
                "operation": operation,
                "duration_ms": trace.to_dict().get("duration_ms"),
                **trace.tags
            }
        )
    except Exception as e:
        trace.end_time = time.time()
        trace.add_log(f"Failed {operation} on {adapter_name}: {e}", level="ERROR")
        trace.add_tag("error", str(e))
        
        # Log trace with error
        logger.error(
            "Adapter operation trace (error)",
            extra={
                "trace_id": trace.trace_id,
                "span_id": trace.span_id,
                "adapter": adapter_name,
                "operation": operation,
                "duration_ms": trace.to_dict().get("duration_ms"),
                "error": str(e),
                **trace.tags
            },
            exc_info=True
        )
        raise


def trace_function(operation_name: Optional[str] = None):
    """
    Decorator for tracing function calls
    
    Args:
        operation_name: Optional operation name (defaults to function name)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            with trace_adapter_operation(
                adapter_name=func.__module__,
                operation=op_name,
                **kwargs
            ):
                return func(*args, **kwargs)
        return wrapper
    return decorator
