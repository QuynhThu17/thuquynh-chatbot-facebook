"""
Rate limiter implementation
Chống spam và abuse từ users
"""

import time
import logging
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration cho rate limiter"""
    max_requests: int = 10  # Số requests tối đa
    window_seconds: int = 60  # Trong khoảng thời gian (seconds)
    block_duration_seconds: int = 300  # Thời gian block khi vượt limit (5 phút)


class RateLimiter:
    """
    Token bucket rate limiter
    Cho phép giới hạn số requests per user trong time window
    """
    
    def __init__(self, config: RateLimitConfig = None):
        """
        Args:
            config: RateLimitConfig object
        """
        self.config = config or RateLimitConfig()
        
        # {user_id: deque[timestamp]}
        self.requests: Dict[str, deque[float]] = defaultdict(lambda: deque())
        
        # {user_id: block_until_timestamp}
        self.blocked_users: Dict[str, float] = {}
        
        # Stats
        self.total_allowed = 0
        self.total_blocked = 0
    
    def is_allowed(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check xem user có được phép request không
        
        Args:
            user_id: User ID
            
        Returns:
            (allowed, message): 
                - allowed: True nếu được phép, False nếu bị block
                - message: Message giải thích (nếu bị block)
        """
        current_time = time.time()
        
        # Check nếu user đang bị block
        if user_id in self.blocked_users:
            block_until = self.blocked_users[user_id]
            if current_time < block_until:
                remaining = int(block_until - current_time)
                self.total_blocked += 1
                return False, f"⛔ Bạn đang bị giới hạn. Vui lòng thử lại sau {remaining} giây."
            else:
                # Hết thời gian block
                del self.blocked_users[user_id]
                self.requests[user_id].clear()
                logger.info(f"🔓 User {user_id} unblocked")
        
        # Remove old timestamps (ngoài window)
        cutoff_time = current_time - self.config.window_seconds
        user_requests = self.requests[user_id]
        
        while user_requests and user_requests[0] < cutoff_time:
            user_requests.popleft()
        
        # Check limit
        if len(user_requests) >= self.config.max_requests:
            # Vượt limit, block user
            block_until = current_time + self.config.block_duration_seconds
            self.blocked_users[user_id] = block_until
            self.total_blocked += 1
            
            logger.warning(
                f"🚫 User {user_id} exceeded rate limit "
                f"({len(user_requests)}/{self.config.max_requests} in {self.config.window_seconds}s). "
                f"Blocked for {self.config.block_duration_seconds}s"
            )
            
            return False, (
                f"⛔ Bạn đã gửi quá nhiều tin nhắn "
                f"({self.config.max_requests} tin trong {self.config.window_seconds} giây). "
                f"Vui lòng chờ {self.config.block_duration_seconds} giây trước khi thử lại."
            )
        
        # Cho phép request
        user_requests.append(current_time)
        self.total_allowed += 1
        return True, None
    
    def get_remaining_requests(self, user_id: str) -> int:
        """
        Lấy số requests còn lại cho user
        
        Args:
            user_id: User ID
            
        Returns:
            Số requests còn lại
        """
        current_time = time.time()
        cutoff_time = current_time - self.config.window_seconds
        
        user_requests = self.requests[user_id]
        
        # Count requests trong window
        valid_requests = sum(1 for ts in user_requests if ts >= cutoff_time)
        
        return max(0, self.config.max_requests - valid_requests)
    
    def reset_user(self, user_id: str):
        """
        Reset rate limit cho user (dùng cho admin)
        
        Args:
            user_id: User ID
        """
        if user_id in self.requests:
            self.requests[user_id].clear()
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
        logger.info(f"🔄 Reset rate limit for user {user_id}")
    
    def get_stats(self) -> dict:
        """Lấy statistics"""
        return {
            'total_allowed': self.total_allowed,
            'total_blocked': self.total_blocked,
            'currently_blocked_users': len(self.blocked_users),
            'total_tracked_users': len(self.requests),
            'block_rate': self.total_blocked / (self.total_allowed + self.total_blocked) 
                         if (self.total_allowed + self.total_blocked) > 0 else 0
        }
    
    def cleanup_old_data(self):
        """Cleanup old data để tránh memory leak"""
        current_time = time.time()
        cutoff_time = current_time - (self.config.window_seconds * 2)
        
        # Cleanup old requests
        users_to_remove = []
        for user_id, requests in self.requests.items():
            # Remove old timestamps
            while requests and requests[0] < cutoff_time:
                requests.popleft()
            
            # Remove user nếu không còn requests
            if not requests and user_id not in self.blocked_users:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.requests[user_id]
        
        # Cleanup expired blocks
        expired_blocks = [
            user_id for user_id, block_until in self.blocked_users.items()
            if current_time > block_until
        ]
        for user_id in expired_blocks:
            del self.blocked_users[user_id]
        
        if users_to_remove or expired_blocks:
            logger.debug(
                f"🧹 Cleaned up {len(users_to_remove)} inactive users "
                f"and {len(expired_blocks)} expired blocks"
            )


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter với tiers khác nhau
    VIP users có limit cao hơn, spam users có limit thấp hơn
    """
    
    def __init__(self):
        # Default tiers
        self.tiers = {
            'premium': RateLimitConfig(max_requests=50, window_seconds=60, block_duration_seconds=60),
            'standard': RateLimitConfig(max_requests=20, window_seconds=60, block_duration_seconds=180),
            'free': RateLimitConfig(max_requests=10, window_seconds=60, block_duration_seconds=300),
            'suspicious': RateLimitConfig(max_requests=5, window_seconds=60, block_duration_seconds=600)
        }
        
        # User tier mapping
        self.user_tiers: Dict[str, str] = defaultdict(lambda: 'free')
        
        # Rate limiters per tier
        self.limiters: Dict[str, RateLimiter] = {
            tier: RateLimiter(config) for tier, config in self.tiers.items()
        }
    
    def set_user_tier(self, user_id: str, tier: str):
        """
        Set tier cho user
        
        Args:
            user_id: User ID
            tier: Tier name ('premium', 'standard', 'free', 'suspicious')
        """
        if tier not in self.tiers:
            logger.warning(f"Invalid tier: {tier}. Using 'free'")
            tier = 'free'
        
        self.user_tiers[user_id] = tier
        logger.info(f"👤 Set user {user_id} tier to {tier}")
    
    def is_allowed(self, user_id: str) -> Tuple[bool, Optional[str]]:
        """
        Check rate limit cho user
        
        Args:
            user_id: User ID
            
        Returns:
            (allowed, message)
        """
        tier = self.user_tiers[user_id]
        limiter = self.limiters[tier]
        return limiter.is_allowed(user_id)
    
    def get_user_info(self, user_id: str) -> dict:
        """Lấy thông tin về user's rate limit"""
        tier = self.user_tiers[user_id]
        limiter = self.limiters[tier]
        remaining = limiter.get_remaining_requests(user_id)
        
        return {
            'user_id': user_id,
            'tier': tier,
            'remaining_requests': remaining,
            'max_requests': self.tiers[tier].max_requests,
            'window_seconds': self.tiers[tier].window_seconds
        }


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter (singleton)"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter


# Example usage
if __name__ == "__main__":
    # Basic rate limiter
    limiter = RateLimiter(RateLimitConfig(max_requests=5, window_seconds=10))
    
    user_id = "test_user"
    
    # Simulate requests
    for i in range(10):
        allowed, message = limiter.is_allowed(user_id)
        if allowed:
            print(f"✅ Request {i+1} allowed. Remaining: {limiter.get_remaining_requests(user_id)}")
        else:
            print(f"❌ Request {i+1} blocked: {message}")
        time.sleep(0.5)
    
    print(f"\n📊 Stats: {limiter.get_stats()}")
    
    # Adaptive rate limiter
    print("\n" + "="*60)
    print("Testing Adaptive Rate Limiter")
    print("="*60)
    
    adaptive = AdaptiveRateLimiter()
    adaptive.set_user_tier("vip_user", "premium")
    adaptive.set_user_tier("normal_user", "standard")
    adaptive.set_user_tier("spam_user", "suspicious")
    
    for user in ["vip_user", "normal_user", "spam_user"]:
        info = adaptive.get_user_info(user)
        print(f"\n👤 {user}: Tier={info['tier']}, Max={info['max_requests']}, Remaining={info['remaining_requests']}")
