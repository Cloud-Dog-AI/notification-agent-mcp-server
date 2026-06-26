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
Description: Metrics Collection - send_rate, delivery_rate, error_rate, retry_count, ttl_drops, queue_depth

Related Requirements: FR1.12
Related Tasks: T33
Related Architecture: MO1.2
Related Tests: ST1.3

Recent Changes (max 10):
- (Initial implementation)
**************************************************
"""

from src.utils.logger import get_logger
import time
from typing import Dict, Any, Optional
from threading import Lock
from collections import defaultdict, deque

logger = get_logger(__name__)


class MetricsCollector:
    """Metrics collector for notification system"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self.lock = Lock()
        
        # Counters
        self.send_count = 0
        self.delivery_count = 0
        self.error_count = 0
        self.retry_count = 0
        self.ttl_drops = 0
        
        # Rate tracking (requests per minute)
        self.send_times: deque = deque()
        self.delivery_times: deque = deque()
        self.error_times: deque = deque()
        
        # Queue depth tracking
        self.queue_depths: deque = deque()
        
        # Adapter latency tracking
        self.adapter_latencies: Dict[str, deque] = defaultdict(lambda: deque())
        
        logger.info("MetricsCollector initialized")
    
    def record_send(self):
        """Record a message send"""
        with self.lock:
            self.send_count += 1
            self.send_times.append(time.time())
            # Keep only last hour of timestamps
            cutoff = time.time() - 3600
            while self.send_times and self.send_times[0] < cutoff:
                self.send_times.popleft()
    
    def record_delivery(self):
        """Record a delivery"""
        with self.lock:
            self.delivery_count += 1
            self.delivery_times.append(time.time())
            cutoff = time.time() - 3600
            while self.delivery_times and self.delivery_times[0] < cutoff:
                self.delivery_times.popleft()
    
    def record_error(self):
        """Record an error"""
        with self.lock:
            self.error_count += 1
            self.error_times.append(time.time())
            cutoff = time.time() - 3600
            while self.error_times and self.error_times[0] < cutoff:
                self.error_times.popleft()
    
    def record_retry(self):
        """Record a retry"""
        with self.lock:
            self.retry_count += 1
    
    def record_ttl_drop(self):
        """Record a TTL expiry"""
        with self.lock:
            self.ttl_drops += 1
    
    def record_queue_depth(self, depth: int):
        """Record queue depth"""
        with self.lock:
            self.queue_depths.append((time.time(), depth))
            # Keep only last hour
            cutoff = time.time() - 3600
            while self.queue_depths and self.queue_depths[0][0] < cutoff:
                self.queue_depths.popleft()
    
    def record_adapter_latency(self, adapter_name: str, latency_ms: float):
        """Record adapter latency"""
        with self.lock:
            self.adapter_latencies[adapter_name].append((time.time(), latency_ms))
            # Keep only last hour
            cutoff = time.time() - 3600
            adapter_times = self.adapter_latencies[adapter_name]
            while adapter_times and adapter_times[0][0] < cutoff:
                adapter_times.popleft()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self.lock:
            now = time.time()
            
            # Calculate rates (per minute)
            send_rate = len([t for t in self.send_times if t > now - 60]) / 60.0 * 60
            delivery_rate = len([t for t in self.delivery_times if t > now - 60]) / 60.0 * 60
            error_rate = len([t for t in self.error_times if t > now - 60]) / 60.0 * 60
            
            # Current queue depth
            current_queue_depth = self.queue_depths[-1][1] if self.queue_depths else 0
            
            # Average queue depth (last hour)
            if self.queue_depths:
                avg_queue_depth = sum(d for _, d in self.queue_depths) / len(self.queue_depths)
            else:
                avg_queue_depth = 0
            
            # Adapter latencies
            adapter_stats = {}
            for adapter_name, latencies in self.adapter_latencies.items():
                if latencies:
                    recent_latencies = [latency for ts, latency in latencies if ts > now - 60]
                    if recent_latencies:
                        adapter_stats[adapter_name] = {
                            "avg_latency_ms": sum(recent_latencies) / len(recent_latencies),
                            "min_latency_ms": min(recent_latencies),
                            "max_latency_ms": max(recent_latencies),
                            "p95_latency_ms": sorted(recent_latencies)[int(len(recent_latencies) * 0.95)] if recent_latencies else 0
                        }
            
            return {
                "send_rate": send_rate,
                "delivery_rate": delivery_rate,
                "error_rate": error_rate,
                "retry_count": self.retry_count,
                "ttl_drops": self.ttl_drops,
                "queue_depth": current_queue_depth,
                "avg_queue_depth": avg_queue_depth,
                "total_sends": self.send_count,
                "total_deliveries": self.delivery_count,
                "total_errors": self.error_count,
                "adapter_latencies": adapter_stats
            }
    
    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.send_count = 0
            self.delivery_count = 0
            self.error_count = 0
            self.retry_count = 0
            self.ttl_drops = 0
            self.send_times.clear()
            self.delivery_times.clear()
            self.error_times.clear()
            self.queue_depths.clear()
            self.adapter_latencies.clear()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def setup_metrics() -> MetricsCollector:
    """Setup and return global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
