"""
Metrics tracking cho bot performance monitoring
Thu thập và phân tích performance metrics
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class BotMetrics:
    """Metrics cho bot performance"""
    total_messages: int = 0
    total_errors: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    tool_call_counts: Dict[str, int] = field(default_factory=dict)
    cache_hit_rate: float = 0.0
    messages_per_minute: float = 0.0
    error_rate: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'total_messages': self.total_messages,
            'total_errors': self.total_errors,
            'avg_response_time': round(self.avg_response_time, 3),
            'min_response_time': round(self.min_response_time, 3) if self.min_response_time != float('inf') else 0,
            'max_response_time': round(self.max_response_time, 3),
            'tool_call_counts': self.tool_call_counts,
            'cache_hit_rate': round(self.cache_hit_rate, 3),
            'messages_per_minute': round(self.messages_per_minute, 2),
            'error_rate': round(self.error_rate, 3)
        }


class MetricsCollector:
    """
    Thu thập và tính toán metrics
    Thread-safe và memory-efficient
    """
    
    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: Số lượng measurements giữ lại để tính toán (sliding window)
        """
        self.window_size = window_size
        
        # Sliding window cho response times (memory efficient)
        self.response_times: deque[float] = deque(maxlen=window_size)
        
        # Message timestamps cho tính messages_per_minute
        self.message_timestamps: deque[float] = deque(maxlen=window_size)
        
        # Counters
        self.total_messages = 0
        self.total_errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Tool call tracking
        self.tool_call_counts: Dict[str, int] = defaultdict(int)
        
        # Min/Max tracking
        self.min_response_time = float('inf')
        self.max_response_time = 0.0
        
        # Start time
        self.start_time = time.time()
    
    def record_message(self, duration: float, success: bool = True):
        """
        Record message processing
        
        Args:
            duration: Response time (seconds)
            success: True nếu không có error
        """
        self.total_messages += 1
        self.response_times.append(duration)
        self.message_timestamps.append(time.time())
        
        if not success:
            self.total_errors += 1
        
        # Update min/max
        self.min_response_time = min(self.min_response_time, duration)
        self.max_response_time = max(self.max_response_time, duration)
    
    def record_error(self):
        """Record error occurrence"""
        self.total_errors += 1
    
    def record_cache_access(self, hit: bool):
        """
        Record cache access
        
        Args:
            hit: True nếu cache hit, False nếu cache miss
        """
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def record_tool_call(self, tool_name: str):
        """
        Record tool call
        
        Args:
            tool_name: Tên của tool được gọi
        """
        self.tool_call_counts[tool_name] += 1
    
    def get_metrics(self) -> BotMetrics:
        """
        Get current metrics snapshot
        
        Returns:
            BotMetrics object với các metrics hiện tại
        """
        metrics = BotMetrics()
        
        # Basic counters
        metrics.total_messages = self.total_messages
        metrics.total_errors = self.total_errors
        
        # Response times
        if self.response_times:
            metrics.avg_response_time = sum(self.response_times) / len(self.response_times)
            metrics.min_response_time = self.min_response_time
            metrics.max_response_time = self.max_response_time
        
        # Cache hit rate
        total_cache_access = self.cache_hits + self.cache_misses
        if total_cache_access > 0:
            metrics.cache_hit_rate = self.cache_hits / total_cache_access
        
        # Error rate
        if self.total_messages > 0:
            metrics.error_rate = self.total_errors / self.total_messages
        
        # Messages per minute (based on sliding window)
        if len(self.message_timestamps) >= 2:
            time_span = self.message_timestamps[-1] - self.message_timestamps[0]
            if time_span > 0:
                metrics.messages_per_minute = (len(self.message_timestamps) / time_span) * 60
        
        # Tool call counts
        metrics.tool_call_counts = dict(self.tool_call_counts)
        
        return metrics
    
    def get_report(self) -> str:
        """
        Get formatted metrics report
        
        Returns:
            Formatted string report
        """
        metrics = self.get_metrics()
        uptime = time.time() - self.start_time
        
        report = f"""
{'='*60}
📊 BOT METRICS REPORT
{'='*60}
⏱️  Uptime: {uptime/3600:.2f} hours

📨 Messages:
   • Total: {metrics.total_messages}
   • Per minute: {metrics.messages_per_minute:.2f}
   • Errors: {metrics.total_errors} ({metrics.error_rate:.1%})

⚡ Response Time:
   • Average: {metrics.avg_response_time:.3f}s
   • Min: {metrics.min_response_time:.3f}s
   • Max: {metrics.max_response_time:.3f}s

💾 Cache:
   • Hit rate: {metrics.cache_hit_rate:.1%}
   • Hits: {self.cache_hits}
   • Misses: {self.cache_misses}

🔧 Tool Calls:
"""
        for tool_name, count in sorted(metrics.tool_call_counts.items(), key=lambda x: x[1], reverse=True):
            report += f"   • {tool_name}: {count}\n"
        
        report += f"{'='*60}\n"
        
        return report
    
    def reset(self):
        """Reset tất cả metrics"""
        self.response_times.clear()
        self.message_timestamps.clear()
        self.total_messages = 0
        self.total_errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.tool_call_counts.clear()
        self.min_response_time = float('inf')
        self.max_response_time = 0.0
        self.start_time = time.time()
        logger.info("🔄 Metrics reset")
    
    def get_percentiles(self, percentiles: List[float] = [50, 90, 95, 99]) -> Dict[str, float]:
        """
        Calculate response time percentiles
        
        Args:
            percentiles: List of percentiles to calculate (e.g., [50, 90, 95, 99])
            
        Returns:
            Dict mapping percentile to value
        """
        if not self.response_times:
            return {f"p{p}": 0.0 for p in percentiles}
        
        sorted_times = sorted(self.response_times)
        n = len(sorted_times)
        
        result = {}
        for p in percentiles:
            index = int(n * p / 100)
            if index >= n:
                index = n - 1
            result[f"p{p}"] = sorted_times[index]
        
        return result


class PerformanceTimer:
    """
    Context manager để measure execution time
    
    Usage:
        with PerformanceTimer() as timer:
            # ... code to measure
        
        print(f"Execution time: {timer.duration}s")
    """
    
    def __init__(self, name: str = "Operation"):
        """
        Args:
            name: Tên operation để log
        """
        self.name = name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        
        if exc_type is None:
            logger.debug(f"⏱️  {self.name} completed in {self.duration:.3f}s")
        else:
            logger.warning(f"⏱️  {self.name} failed after {self.duration:.3f}s: {exc_val}")
        
        return False  # Don't suppress exceptions


# Global metrics collector instance
_global_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector (singleton)"""
    global _global_metrics_collector
    if _global_metrics_collector is None:
        _global_metrics_collector = MetricsCollector()
    return _global_metrics_collector


# Example usage
if __name__ == "__main__":
    collector = MetricsCollector()
    
    # Simulate some messages
    import random
    for i in range(100):
        duration = random.uniform(0.1, 2.0)
        success = random.random() > 0.1  # 90% success rate
        collector.record_message(duration, success)
        
        # Simulate cache access
        collector.record_cache_access(hit=random.random() > 0.3)
        
        # Simulate tool calls
        if random.random() > 0.5:
            tool = random.choice(['search_knowledge', 'search_products', 'get_customer_info'])
            collector.record_tool_call(tool)
    
    # Print report
    print(collector.get_report())
    
    # Get percentiles
    percentiles = collector.get_percentiles([50, 90, 95, 99])
    print("\n📊 Response Time Percentiles:")
    for p, value in percentiles.items():
        print(f"   {p}: {value:.3f}s")
