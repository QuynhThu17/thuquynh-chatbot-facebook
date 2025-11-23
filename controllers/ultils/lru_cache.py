"""
LRU Cache Implementation
Tránh memory leak khi cache grow không giới hạn
"""

from collections import OrderedDict
from typing import TypeVar, Generic, Optional
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class LRUCache(Generic[T]):
    """
    LRU (Least Recently Used) Cache với size limit
    Tự động evict entries cũ nhất khi đạt max_size
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Args:
            max_size: Số lượng items tối đa trong cache
        """
        self.cache: OrderedDict[str, T] = OrderedDict()
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[T]:
        """
        Lấy value từ cache
        
        Args:
            key: Cache key
            
        Returns:
            Value nếu tồn tại, None nếu không
        """
        if key not in self.cache:
            self._misses += 1
            return None
        
        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self._hits += 1
        return self.cache[key]
    
    def set(self, key: str, value: T):
        """
        Set value vào cache
        
        Args:
            key: Cache key
            value: Value cần cache
        """
        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
        
        self.cache[key] = value
        
        # Evict oldest if over limit
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            evicted_value = self.cache.pop(oldest_key)
            logger.debug(f"🗑️ LRU evicted: {oldest_key}")
    
    def delete(self, key: str) -> bool:
        """
        Xóa key khỏi cache
        
        Args:
            key: Cache key
            
        Returns:
            True nếu xóa thành công, False nếu key không tồn tại
        """
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self):
        """Xóa toàn bộ cache"""
        self.cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("🧹 LRU cache cleared")
    
    def size(self) -> int:
        """Số lượng items hiện tại trong cache"""
        return len(self.cache)
    
    def hit_rate(self) -> float:
        """Tính cache hit rate"""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total
    
    def stats(self) -> dict:
        """Lấy statistics của cache"""
        return {
            'size': self.size(),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': self.hit_rate()
        }


class TTLCache(Generic[T]):
    """
    Cache với TTL (Time To Live) và lazy expiration
    Chỉ check expiration khi access, không cần periodic cleanup
    """
    
    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000):
        """
        Args:
            ttl_seconds: Time to live (seconds)
            max_size: Số lượng items tối đa
        """
        self.ttl_seconds = ttl_seconds
        self.lru_cache: LRUCache[tuple[T, float]] = LRUCache(max_size)
    
    def get(self, key: str, current_time: float) -> Optional[T]:
        """
        Lấy value từ cache với lazy expiration
        
        Args:
            key: Cache key
            current_time: Current timestamp
            
        Returns:
            Value nếu còn valid, None nếu expired hoặc không tồn tại
        """
        cached = self.lru_cache.get(key)
        if cached is None:
            return None
        
        value, timestamp = cached
        
        # Check expiration
        if current_time - timestamp >= self.ttl_seconds:
            # Expired, remove
            self.lru_cache.delete(key)
            logger.debug(f"⏱️ Cache expired: {key}")
            return None
        
        return value
    
    def set(self, key: str, value: T, current_time: float):
        """
        Set value với timestamp
        
        Args:
            key: Cache key
            value: Value cần cache
            current_time: Current timestamp
        """
        self.lru_cache.set(key, (value, current_time))
    
    def delete(self, key: str) -> bool:
        """Xóa key khỏi cache"""
        return self.lru_cache.delete(key)
    
    def clear(self):
        """Xóa toàn bộ cache"""
        self.lru_cache.clear()
    
    def stats(self) -> dict:
        """Lấy statistics"""
        base_stats = self.lru_cache.stats()
        base_stats['ttl_seconds'] = self.ttl_seconds
        return base_stats
