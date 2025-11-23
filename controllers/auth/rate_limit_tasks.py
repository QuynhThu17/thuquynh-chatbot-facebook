"""
Background Tasks for Rate Limiting
Các task chạy nền để dọn dẹp dữ liệu rate limiting
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class RateLimitBackgroundTasks:
    def __init__(self, rate_limit_manager):
        self.rate_limit_manager = rate_limit_manager
        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start_cleanup_task(self, interval_hours: int = 24):
        """
        Bắt đầu task dọn dẹp định kỳ
        
        Args:
            interval_hours: Khoảng thời gian giữa các lần dọn dẹp (giờ)
        """
        if self._is_running:
            logger.warning("Rate limit cleanup task is already running")
            return
            
        self._is_running = True
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(interval_hours)
        )
        logger.info(f"Started rate limit cleanup task with {interval_hours}h interval")

    async def stop_cleanup_task(self):
        """Dừng task dọn dẹp"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self._is_running = False
        logger.info("Stopped rate limit cleanup task")

    async def _cleanup_loop(self, interval_hours: int):
        """Loop chính cho việc dọn dẹp định kỳ"""
        while self._is_running:
            try:
                # Dọn dẹp bản ghi cũ hơn 7 ngày
                await self.rate_limit_manager.cleanup_old_records(days=7)
                
                # Chờ đến lần dọn dẹp tiếp theo
                await asyncio.sleep(interval_hours * 3600)  # Convert to seconds
                
            except asyncio.CancelledError:
                logger.info("Rate limit cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in rate limit cleanup task: {str(e)}")
                # Chờ 1 giờ trước khi thử lại nếu có lỗi
                await asyncio.sleep(3600)

    async def manual_cleanup(self, days: int = 7):
        """Thực hiện dọn dẹp thủ công"""
        try:
            await self.rate_limit_manager.cleanup_old_records(days=days)
            logger.info(f"Manual cleanup completed for records older than {days} days")
        except Exception as e:
            logger.error(f"Manual cleanup failed: {str(e)}")
            raise

# Global instance
_rate_limit_bg_tasks: Optional[RateLimitBackgroundTasks] = None

def get_rate_limit_background_tasks(rate_limit_manager) -> RateLimitBackgroundTasks:
    """Get hoặc tạo mới instance của RateLimitBackgroundTasks"""
    global _rate_limit_bg_tasks
    
    if _rate_limit_bg_tasks is None:
        _rate_limit_bg_tasks = RateLimitBackgroundTasks(rate_limit_manager)
    
    return _rate_limit_bg_tasks

async def init_rate_limit_cleanup(rate_limit_manager, interval_hours: int = 24):
    """Khởi tạo background task cho rate limit cleanup"""
    bg_tasks = get_rate_limit_background_tasks(rate_limit_manager)
    await bg_tasks.start_cleanup_task(interval_hours)
    return bg_tasks
