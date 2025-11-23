"""
Rate Limit Management
Quản lý giới hạn tần suất gọi API để tránh spam
"""

from datetime import datetime, timedelta, timezone
from configs.environment import get_vietnam_now_naive
from typing import Optional, Dict, Any
from bson import ObjectId
import logging

from .base_manager import BaseManager

logger = logging.getLogger(__name__)

class RateLimitManager(BaseManager):
    def __init__(self, db):
        super().__init__(db, "rate_limits")

    async def check_rate_limit(self, identifier: str, action: str, limit_seconds: int = 30) -> bool:
        """
        Kiểm tra rate limit cho một hành động cụ thể
        
        Args:
            identifier: Định danh (email, IP, user_id, etc.)
            action: Loại hành động (send_verification_email, forgot_password, etc.)
            limit_seconds: Số giây giữa các lần gọi
            
        Returns:
            True nếu cho phép thực hiện, False nếu đã vượt quá giới hạn
        """
        try:
            # Sử dụng UTC để tránh timezone issues
            current_time = get_vietnam_now_naive()
            limit_time = current_time - timedelta(seconds=limit_seconds)
            
            logger.info(f"Checking rate limit for {identifier} - {action}, current_time: {current_time}, limit_time: {limit_time}")

            # Tìm lần thực hiện gần nhất của action này
            last_action = await self.collection.find_one({
                "identifier": identifier,
                "action": action,
                "created_at": {"$gte": limit_time}
            }, sort=[("created_at", -1)])

            if last_action:
                # Đảm bảo last_action["created_at"] cũng là UTC
                last_action_time = last_action["created_at"]
                if hasattr(last_action_time, 'tzinfo') and last_action_time.tzinfo is not None:
                    last_action_time = last_action_time.replace(tzinfo=None)
                
                logger.info(f"Found last action at: {last_action_time}")
                
                # Tính thời gian còn lại phải chờ
                time_diff = (current_time - last_action_time).total_seconds()
                remaining_time = limit_seconds - time_diff
                
                logger.info(f"Time diff: {time_diff}s, remaining: {remaining_time}s")
                
                if remaining_time > 0:
                    logger.warning(f"Rate limit exceeded for {identifier} - {action}. Remaining time: {remaining_time:.0f}s")
                    return False
                else:
                    logger.info(f"Rate limit passed for {identifier} - {action}")

            logger.info(f"No recent action found for {identifier} - {action}")
            return True

        except Exception as e:
            logger.error(f"Failed to check rate limit for {identifier} - {action}: {str(e)}")
            # Trong trường hợp lỗi, cho phép thực hiện để không block user
            return True

    async def record_action(self, identifier: str, action: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Ghi lại một hành động đã thực hiện
        
        Args:
            identifier: Định danh (email, IP, user_id, etc.)
            action: Loại hành động
            metadata: Thông tin bổ sung (optional)
        """
        try:
            # Sử dụng UTC để tránh timezone issues
            current_time = get_vietnam_now_naive()

            action_data = {
                "identifier": identifier,
                "action": action,
                "created_at": current_time,
                "metadata": metadata or {}
            }

            await self.collection.insert_one(action_data)
            logger.info(f"Recorded action: {identifier} - {action}")

        except Exception as e:
            logger.error(f"Failed to record action for {identifier} - {action}: {str(e)}")

    async def get_remaining_time(self, identifier: str, action: str, limit_seconds: int = 30) -> int:
        """
        Lấy thời gian còn lại phải chờ (tính bằng giây)
        
        Returns:
            Số giây còn lại phải chờ, 0 nếu có thể thực hiện ngay
        """
        try:
            # Sử dụng UTC để tránh timezone issues
            current_time = get_vietnam_now_naive()
            limit_time = current_time - timedelta(seconds=limit_seconds)

            # Tìm lần thực hiện gần nhất
            last_action = await self.collection.find_one({
                "identifier": identifier,
                "action": action,
                "created_at": {"$gte": limit_time}
            }, sort=[("created_at", -1)])

            if last_action:
                # Đảm bảo last_action["created_at"] cũng là UTC
                last_action_time = last_action["created_at"]
                if hasattr(last_action_time, 'tzinfo') and last_action_time.tzinfo is not None:
                    last_action_time = last_action_time.replace(tzinfo=None)
                    
                time_diff = (current_time - last_action_time).total_seconds()
                remaining_time = limit_seconds - time_diff
                return max(0, int(remaining_time))

            return 0

        except Exception as e:
            logger.error(f"Failed to get remaining time for {identifier} - {action}: {str(e)}")
            return 0

    async def cleanup_old_records(self, days: int = 7):
        """
        Xóa các bản ghi cũ để tránh database quá lớn
        
        Args:
            days: Xóa bản ghi cũ hơn số ngày này
        """
        try:
            # Sử dụng UTC để tránh timezone issues
            cutoff_time = get_vietnam_now_naive() - timedelta(days=days)

            result = await self.collection.delete_many({
                "created_at": {"$lt": cutoff_time}
            })

            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} old rate limit records")

        except Exception as e:
            logger.error(f"Failed to cleanup old rate limit records: {str(e)}")

    async def get_action_count(self, identifier: str, action: str, hours: int = 24) -> int:
        """
        Đếm số lần thực hiện action trong khoảng thời gian
        
        Args:
            identifier: Định danh
            action: Loại hành động
            hours: Số giờ tính từ hiện tại
            
        Returns:
            Số lần thực hiện
        """
        try:
            # Sử dụng UTC để tránh timezone issues
            start_time = get_vietnam_now_naive() - timedelta(hours=hours)

            count = await self.collection.count_documents({
                "identifier": identifier,
                "action": action,
                "created_at": {"$gte": start_time}
            })

            return count

        except Exception as e:
            logger.error(f"Failed to get action count for {identifier} - {action}: {str(e)}")
            return 0
