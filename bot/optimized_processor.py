"""
Optimized Message Processor
Tích hợp LangGraph Agent vào Facebook Messenger Bot

Features:
1. Tool Results Caching với Redis fallback to in-memory
2. Query Deduplication để tránh xử lý trùng lặp
3. Smart Tool Calling với parallel execution
4. Performance Monitoring
"""

import logging
import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import OrderedDict

logger = logging.getLogger(__name__)


# ==================== CACHING LAYER ====================
class ToolResultCache:
    """
    Cache kết quả từ tools với TTL
    Sử dụng LRU cache in-memory, có thể mở rộng sang Redis
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Args:
            max_size: Số lượng entries tối đa trong cache
            default_ttl: TTL mặc định (seconds)
        """
        self.cache = OrderedDict()  # {cache_key: (result, timestamp)}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.hit_count = 0
        self.miss_count = 0
    
    def _generate_cache_key(self, tool_name: str, **kwargs) -> str:
        """Generate cache key từ tool name và parameters"""
        # Sort kwargs để đảm bảo consistent key
        sorted_params = sorted(kwargs.items())
        params_str = str(sorted_params)
        
        # Hash để tránh key quá dài
        key_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"{tool_name}:{key_hash}"
    
    def get(self, tool_name: str, **kwargs) -> Optional[Any]:
        """
        Lấy kết quả từ cache
        
        Args:
            tool_name: Tên tool
            **kwargs: Parameters của tool call
            
        Returns:
            Cached result hoặc None nếu không có/expired
        """
        try:
            cache_key = self._generate_cache_key(tool_name, **kwargs)
            
            if cache_key in self.cache:
                result, timestamp = self.cache[cache_key]
                
                # Check TTL
                if time.time() - timestamp < self.default_ttl:
                    # Move to end (LRU)
                    self.cache.move_to_end(cache_key)
                    self.hit_count += 1
                    logger.debug(f"✅ Cache HIT: {tool_name} (hit rate: {self.get_hit_rate():.2%})")
                    return result
                else:
                    # Expired, remove
                    del self.cache[cache_key]
            
            self.miss_count += 1
            logger.debug(f"❌ Cache MISS: {tool_name} (hit rate: {self.get_hit_rate():.2%})")
            return None
            
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            return None
    
    def set(self, tool_name: str, result: Any, **kwargs) -> None:
        """
        Lưu kết quả vào cache
        
        Args:
            tool_name: Tên tool
            result: Kết quả cần cache
            **kwargs: Parameters của tool call
        """
        try:
            cache_key = self._generate_cache_key(tool_name, **kwargs)
            
            # Kiểm tra size limit
            if len(self.cache) >= self.max_size:
                # Remove oldest entry
                self.cache.popitem(last=False)
            
            self.cache[cache_key] = (result, time.time())
            logger.debug(f"💾 Cached: {tool_name} (cache size: {len(self.cache)})")
            
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
    
    def get_hit_rate(self) -> float:
        """Tính cache hit rate"""
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total
    
    def clear(self) -> None:
        """Xóa toàn bộ cache"""
        self.cache.clear()
        logger.info("🧹 Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê cache"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": self.get_hit_rate()
        }


# ==================== QUERY DEDUPLICATION ====================
class QueryDeduplicator:
    """
    Tránh xử lý trùng lặp các query giống nhau trong thời gian ngắn
    """
    
    def __init__(self, window_seconds: int = 5):
        """
        Args:
            window_seconds: Thời gian window để coi là duplicate (seconds)
        """
        self.window_seconds = window_seconds
        self.recent_queries = {}  # {query_hash: (timestamp, future)}
    
    def _generate_query_hash(self, sender_id: str, page_id: str, message: str) -> str:
        """Generate hash cho query"""
        combined = f"{sender_id}:{page_id}:{message.lower().strip()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def process_or_wait(self, sender_id: str, page_id: str, message: str, processor_func) -> Any:
        """
        Xử lý query hoặc đợi nếu đang được xử lý
        
        Args:
            sender_id: Sender ID
            page_id: Page ID
            message: User message
            processor_func: Async function to process message
            
        Returns:
            Kết quả xử lý
        """
        try:
            query_hash = self._generate_query_hash(sender_id, page_id, message)
            current_time = time.time()
            
            # Clean expired entries
            expired_keys = [
                key for key, (ts, _) in self.recent_queries.items()
                if current_time - ts > self.window_seconds
            ]
            for key in expired_keys:
                self.recent_queries.pop(key, None)
            
            # Check if query is being processed
            if query_hash in self.recent_queries:
                timestamp, existing_future = self.recent_queries[query_hash]
                
                # Nếu trong window time, đợi kết quả từ request trước
                if current_time - timestamp < self.window_seconds:
                    logger.info(f"⏳ Duplicate query detected, waiting for existing processing...")
                    result = await existing_future
                    logger.info(f"✅ Got result from duplicate query processing")
                    return result
            
            # Create new processing future
            future = asyncio.Future()
            self.recent_queries[query_hash] = (current_time, future)
            
            try:
                # Process query
                result = await processor_func()
                
                # Set result for waiting requests
                if not future.done():
                    future.set_result(result)
                
                return result
                
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
                raise
            
        except Exception as e:
            logger.error(f"Error in query deduplication: {e}")
            # Fallback to direct processing
            return await processor_func()


# ==================== PERFORMANCE MONITOR ====================
class PerformanceMonitor:
    """
    Monitor performance của agent
    """
    
    def __init__(self):
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "tool_call_counts": {},
            "intent_distribution": {},
            "avg_response_time": 0.0
        }
    
    def record_request(self, success: bool, processing_time: float, 
                      tools_called: List[str], intent: str) -> None:
        """
        Ghi nhận metrics cho 1 request
        """
        try:
            self.metrics["total_requests"] += 1
            
            if success:
                self.metrics["successful_requests"] += 1
            else:
                self.metrics["failed_requests"] += 1
            
            self.metrics["total_processing_time"] += processing_time
            self.metrics["avg_response_time"] = (
                self.metrics["total_processing_time"] / self.metrics["total_requests"]
            )
            
            # Tool call counts
            for tool in tools_called:
                self.metrics["tool_call_counts"][tool] = \
                    self.metrics["tool_call_counts"].get(tool, 0) + 1
            
            # Intent distribution
            self.metrics["intent_distribution"][intent] = \
                self.metrics["intent_distribution"].get(intent, 0) + 1
                
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Lấy metrics"""
        return self.metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset metrics"""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "tool_call_counts": {},
            "intent_distribution": {},
            "avg_response_time": 0.0
        }
        logger.info("📊 Metrics reset")


# ==================== OPTIMIZED PROCESSOR ====================
class OptimizedMessageProcessor:
    """
    Main processor tích hợp tất cả optimizations
    """
    
    def __init__(self):
        self.tool_cache = ToolResultCache(max_size=1000, default_ttl=300)
        self.deduplicator = QueryDeduplicator(window_seconds=5)
        self.performance_monitor = PerformanceMonitor()
    
    async def process_with_graph(
        self,
        user_message: str,
        sender_id: str,
        page_id: str,
        bot_id: str,
        bot_info: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        sender_info: Optional[Dict[str, Any]],
        image_context: str,
        qa_pairs_context: str,  # ✅ Thêm Q&A context
        history_text: str,
        current_time_str: str,
        tools_dict: Dict[str, Any],
        company_id: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Process message với optimized graph
        
        Args:
            use_cache: Có sử dụng cache cho tool results hay không
            
        Returns:
            Dict with 'response', 'segments', 'metadata', 'performance'
        """
        start_time = time.time()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🎯 OptimizedMessageProcessor.process_with_graph")
        logger.info(f"  - Query: '{user_message[:50]}...'")
        logger.info(f"  - Cache enabled: {use_cache}")
        logger.info(f"  - QA context received: {len(qa_pairs_context) if qa_pairs_context else 0} chars")
        logger.info(f"  - QA context preview: {qa_pairs_context[:200] if qa_pairs_context else 'EMPTY'}")
        logger.info(f"{'='*80}\n")
        
        async def processor():
            try:
                # Wrap tools với caching nếu enabled
                if use_cache:
                    cached_tools_dict = self._wrap_tools_with_cache(tools_dict)
                    logger.info(f"💾 Enabled caching for {len(cached_tools_dict)} tools")
                else:
                    cached_tools_dict = tools_dict
                    logger.info(f"🔧 Using {len(cached_tools_dict)} tools without cache")
                
                # Import và run agent graph
                from bot.agent_graph import run_optimized_agent
                
                logger.info("🚀 Starting optimized agent execution...")
                logger.info(f"📤 Passing qa_pairs_context to run_optimized_agent: {len(qa_pairs_context) if qa_pairs_context else 0} chars")
                
                result = await run_optimized_agent(
                    user_message=user_message,
                    sender_id=sender_id,
                    page_id=page_id,
                    bot_id=bot_id,
                    bot_info=bot_info,
                    conversation_history=conversation_history,
                    sender_info=sender_info,
                    image_context=image_context,
                    qa_pairs_context=qa_pairs_context,  # ✅ Pass Q&A context
                    history_text=history_text,
                    current_time_str=current_time_str,
                    tools_dict=cached_tools_dict,
                    company_id=company_id
                )
                
                # Add performance info
                processing_time = time.time() - start_time
                cache_stats = self.tool_cache.get_stats()
                
                result["performance"] = {
                    "processing_time": processing_time,
                    "cache_stats": cache_stats
                }
                
                # Record metrics
                self.performance_monitor.record_request(
                    success=True,
                    processing_time=processing_time,
                    tools_called=result.get("metadata", {}).get("tools_called", []),
                    intent=result.get("metadata", {}).get("intent", "unknown")
                )
                
                logger.info(f"✅ Processing completed in {processing_time:.2f}s | "
                          f"Cache hit rate: {cache_stats.get('hit_rate', 0):.2%}")
                return result
                
            except Exception as e:
                logger.error(f"❌ Error in optimized processing: {e}", exc_info=True)
                processing_time = time.time() - start_time
                
                self.performance_monitor.record_request(
                    success=False,
                    processing_time=processing_time,
                    tools_called=[],
                    intent="error"
                )
                
                error_msg = "Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn."
                return {
                    "response": error_msg,
                    "segments": [{"type": "text", "data": error_msg}],
                    "metadata": {"error": str(e)},
                    "performance": {
                        "processing_time": processing_time,
                        "cache_stats": self.tool_cache.get_stats()
                    }
                }
        
        # Use deduplicator to avoid processing duplicate queries
        result = await self.deduplicator.process_or_wait(
            sender_id, page_id, user_message, processor
        )
        
        return result
    
    def _wrap_tools_with_cache(self, tools_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrap tools với caching layer
        
        Args:
            tools_dict: Original tools dictionary
            
        Returns:
            Wrapped tools dictionary
        """
        wrapped_tools = {}
        
        for tool_name, tool_func in tools_dict.items():
            # Chỉ cache các tools read-only (không cache save/update)
            if tool_name in ["search_products", "search_knowledge", "get_customer_info", "get_order_info"]:
                wrapped_tools[tool_name] = self._create_cached_tool(tool_name, tool_func)
            else:
                wrapped_tools[tool_name] = tool_func
        
        return wrapped_tools
    
    def _create_cached_tool(self, tool_name: str, tool_func):
        """
        Tạo cached version của tool
        """
        def cached_tool(*args, **kwargs):
            # Try cache first
            cached_result = self.tool_cache.get(tool_name, **kwargs)
            if cached_result is not None:
                return cached_result
            
            # Cache miss, execute tool
            result = tool_func(*args, **kwargs)
            
            # Cache result
            self.tool_cache.set(tool_name, result, **kwargs)
            
            return result
        
        return cached_tool
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Lấy performance metrics"""
        return self.performance_monitor.get_metrics()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Lấy cache statistics"""
        return self.tool_cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear tool cache"""
        self.tool_cache.clear()


# Global instance
optimized_processor = OptimizedMessageProcessor()
