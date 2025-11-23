"""
Retry logic với exponential backoff và circuit breaker
Tăng reliability cho external API calls
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, TypeVar, Optional, Type, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator cho retry logic với exponential backoff
    
    Args:
        max_retries: Số lần retry tối đa
        base_delay: Delay ban đầu (seconds)
        max_delay: Delay tối đa (seconds)
        exponential_base: Base cho exponential backoff (2.0 = double mỗi lần)
        exceptions: Tuple các exceptions cần retry
        
    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        async def my_api_call():
            # ... code có thể fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Failed after {max_retries} retries: {func.__name__}")
                        raise
                    
                    # Calculate delay với exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"⚠️ Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )
                    
                    await asyncio.sleep(delay)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            import time
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ Failed after {max_retries} retries: {func.__name__}")
                        raise
                    
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"⚠️ Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s. Error: {e}"
                    )
                    
                    time.sleep(delay)
        
        # Detect async vs sync function
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern để protect system khỏi cascading failures
    
    States:
        - CLOSED: Normal operation, requests go through
        - OPEN: Too many failures, reject all requests immediately
        - HALF_OPEN: Testing if service recovered, allow limited requests
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Args:
            failure_threshold: Số failures trước khi open circuit
            timeout_seconds: Thời gian chờ trước khi thử lại (half-open)
            expected_exception: Exception type để count failures
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = 'closed'  # closed, open, half_open
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function với circuit breaker protection
        
        Args:
            func: Function cần execute
            *args, **kwargs: Arguments cho function
            
        Returns:
            Result của function
            
        Raises:
            CircuitBreakerOpenException: Nếu circuit đang open
        """
        if self.state == 'open':
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout_seconds):
                self.state = 'half_open'
                logger.info(f"🔄 Circuit breaker HALF_OPEN: {func.__name__}")
            else:
                logger.warning(f"⛔ Circuit breaker OPEN, rejecting call: {func.__name__}")
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is OPEN for {func.__name__}. "
                    f"Will retry after {self.timeout_seconds}s"
                )
        
        try:
            result = func(*args, **kwargs)
            
            # Success
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"✅ Circuit breaker CLOSED: {func.__name__}")
            
            return result
            
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(
                f"⚠️ Circuit breaker failure {self.failure_count}/{self.failure_threshold}: "
                f"{func.__name__} - {e}"
            )
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"🔴 Circuit breaker OPEN: {func.__name__}")
            
            raise
    
    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Async version của call()"""
        if self.state == 'open':
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout_seconds):
                self.state = 'half_open'
                logger.info(f"🔄 Circuit breaker HALF_OPEN: {func.__name__}")
            else:
                logger.warning(f"⛔ Circuit breaker OPEN, rejecting call: {func.__name__}")
                raise CircuitBreakerOpenException(
                    f"Circuit breaker is OPEN for {func.__name__}. "
                    f"Will retry after {self.timeout_seconds}s"
                )
        
        try:
            result = await func(*args, **kwargs)
            
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"✅ Circuit breaker CLOSED: {func.__name__}")
            
            return result
            
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(
                f"⚠️ Circuit breaker failure {self.failure_count}/{self.failure_threshold}: "
                f"{func.__name__} - {e}"
            )
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.error(f"🔴 Circuit breaker OPEN: {func.__name__}")
            
            raise
    
    def reset(self):
        """Reset circuit breaker về trạng thái closed"""
        self.state = 'closed'
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("🔄 Circuit breaker manually reset")
    
    def get_state(self) -> dict:
        """Lấy trạng thái hiện tại"""
        return {
            'state': self.state,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'failure_threshold': self.failure_threshold,
            'timeout_seconds': self.timeout_seconds
        }


class CircuitBreakerOpenException(Exception):
    """Exception raised khi circuit breaker đang OPEN"""
    pass


# Example usage:
if __name__ == "__main__":
    # Retry decorator
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    async def flaky_api_call():
        # Simulate 50% failure rate
        import random
        if random.random() < 0.5:
            raise Exception("API call failed")
        return "Success"
    
    # Circuit breaker
    cb = CircuitBreaker(failure_threshold=3, timeout_seconds=10)
    
    async def protected_call():
        try:
            result = await cb.call_async(flaky_api_call)
            print(f"✅ Result: {result}")
        except CircuitBreakerOpenException as e:
            print(f"⛔ {e}")
    
    # Run
    # asyncio.run(protected_call())
