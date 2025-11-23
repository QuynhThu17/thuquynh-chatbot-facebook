"""
Background Notification Tasks Utility
Cung cấp các hàm để chạy notification trong background/threading
để không ảnh hưởng performance của main process
"""

import asyncio
import threading
import logging
from typing import Callable, Any, Dict
from functools import wraps

logger = logging.getLogger(__name__)


def run_in_background(func: Callable, *args, **kwargs):
    """
    Chạy async function trong background thread
    
    Args:
        func: Async function cần chạy
        *args: Positional arguments
        **kwargs: Keyword arguments
    """
    def _run():
        try:
            # Tạo event loop mới cho thread này
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Chạy coroutine trực tiếp trong loop này
                result = loop.run_until_complete(func(*args, **kwargs))
                return result
            finally:
                # Đảm bảo đóng loop sau khi hoàn thành
                try:
                    # Cancel tất cả pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    # Chờ tất cả tasks bị cancel
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.debug(f"Error cancelling tasks: {str(e)}")
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Background task error: {str(e)}", exc_info=True)
    
    # Chạy trong thread riêng
    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def add_notification_task(background_tasks, notification_func: Callable, **kwargs):
    """
    Thêm notification task vào FastAPI BackgroundTasks
    
    Args:
        background_tasks: FastAPI BackgroundTasks instance
        notification_func: Async notification function
        **kwargs: Arguments cho notification function
    """
    def _wrapper():
        run_in_background(notification_func, **kwargs)
    
    background_tasks.add_task(_wrapper)


def background_notify(func: Callable):
    """
    Decorator để tự động chạy notification function trong background
    
    Usage:
        @background_notify
        async def notify_something(self, user_id, message):
            await self.notification_manager.create_notification(...)
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        run_in_background(func, *args, **kwargs)
    
    return wrapper


class NotificationQueue:
    """
    Queue-based notification system để xử lý notifications hàng loạt
    Sử dụng khi có nhiều notifications cần gửi cùng lúc
    """
    
    def __init__(self, batch_size: int = 10, flush_interval: float = 5.0):
        """
        Args:
            batch_size: Số notifications tối đa trong một batch
            flush_interval: Thời gian (giây) để tự động flush queue
        """
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.queue = []
        self.lock = threading.Lock()
        self._start_flush_timer()
    
    def add(self, notification_func: Callable, **kwargs):
        """Thêm notification vào queue"""
        with self.lock:
            self.queue.append((notification_func, kwargs))
            
            if len(self.queue) >= self.batch_size:
                self._flush()
    
    def _flush(self):
        """Xử lý tất cả notifications trong queue"""
        if not self.queue:
            return
        
        notifications = self.queue.copy()
        self.queue.clear()
        
        def _process():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Chạy tất cả notifications song song
                tasks = [func(**kwargs) for func, kwargs in notifications]
                loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                
                loop.close()
                logger.info(f"Flushed {len(notifications)} notifications")
            except Exception as e:
                logger.error(f"Error flushing notification queue: {str(e)}")
        
        thread = threading.Thread(target=_process, daemon=True)
        thread.start()
    
    def _start_flush_timer(self):
        """Bắt đầu timer để tự động flush"""
        def _timer():
            with self.lock:
                if self.queue:
                    self._flush()
            
            # Lặp lại timer
            threading.Timer(self.flush_interval, _timer).start()
        
        threading.Timer(self.flush_interval, _timer).start()


# Global notification queue instance
notification_queue = NotificationQueue(batch_size=10, flush_interval=5.0)
