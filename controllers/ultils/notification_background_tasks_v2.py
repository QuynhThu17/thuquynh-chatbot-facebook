"""
Background Notification Tasks Utility V2
Sử dụng approach an toàn hơn với asyncio.create_task() thay vì threading
"""

import asyncio
import logging
from typing import Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


def run_in_background_v2(func: Callable, *args, **kwargs):
    """
    Chạy async function trong background sử dụng asyncio.create_task()
    Approach này an toàn hơn với event loop
    
    Args:
        func: Async function cần chạy
        *args: Positional arguments
        **kwargs: Keyword arguments
    """
    async def _execute():
        try:
            await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Background task error: {str(e)}", exc_info=True)
    
    try:
        # Lấy current event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Nếu loop đang chạy, tạo task
            asyncio.create_task(_execute())
        else:
            # Nếu loop chưa chạy, schedule coroutine
            loop.run_until_complete(_execute())
    except RuntimeError:
        # Không có event loop, tạo mới (fallback)
        logger.warning("No event loop available, creating new one")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_execute())
        finally:
            loop.close()


def schedule_notification(func: Callable, *args, **kwargs):
    """
    Schedule notification để chạy sau khi response hiện tại đã được gửi
    
    Args:
        func: Async function cần chạy
        *args: Positional arguments
        **kwargs: Keyword arguments
    """
    async def _delayed_execute():
        # Đợi một chút để đảm bảo response đã được gửi
        await asyncio.sleep(0.1)
        try:
            await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Scheduled notification error: {str(e)}", exc_info=True)
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_delayed_execute())
        else:
            logger.warning("Cannot schedule notification: no running event loop")
    except Exception as e:
        logger.error(f"Failed to schedule notification: {str(e)}", exc_info=True)
