"""
Background tasks cho Authentication
Xử lý các task background như cleanup verification codes, etc.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from controllers.data.managements import get_mongodb_factory

logger = logging.getLogger(__name__)

class AuthBackgroundTasks:
    def __init__(self):
        self.is_running = False
    
    async def start_cleanup_task(self):
        """Bắt đầu task dọn dẹp tự động"""
        if self.is_running:
            logger.warning("Cleanup task is already running")
            return
        
        self.is_running = True
        logger.info("Starting email verification cleanup task")
        
        while self.is_running:
            try:
                await self.cleanup_expired_verification_codes()
                # Chạy mỗi 30 phút
                await asyncio.sleep(1800)
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
                await asyncio.sleep(300)  # Thử lại sau 5 phút nếu có lỗi
    
    async def cleanup_expired_verification_codes(self):
        """Dọn dẹp các verification codes đã hết hạn"""
        try:
            factory = get_mongodb_factory()
            if factory:
                await factory.email_verification_manager.cleanup_expired_codes()
                logger.info("Cleaned up expired verification codes")
        except Exception as e:
            logger.error(f"Failed to cleanup expired verification codes: {str(e)}")
    
    def stop_cleanup_task(self):
        """Dừng task dọn dẹp"""
        self.is_running = False
        logger.info("Stopped email verification cleanup task")

# Global instance
auth_background_tasks = AuthBackgroundTasks()

async def start_auth_background_tasks():
    """Khởi động các background tasks cho authentication"""
    try:
        await auth_background_tasks.start_cleanup_task()
    except Exception as e:
        logger.error(f"Failed to start auth background tasks: {str(e)}")

def stop_auth_background_tasks():
    """Dừng các background tasks cho authentication"""
    auth_background_tasks.stop_cleanup_task()
