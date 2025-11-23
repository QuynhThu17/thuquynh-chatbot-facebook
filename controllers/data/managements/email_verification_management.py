"""
Email Verification Management
Quản lý việc lưu trữ và xác thực email verification codes
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from bson import ObjectId
import logging

from .base_manager import BaseManager

logger = logging.getLogger(__name__)

class EmailVerificationManager(BaseManager):
    def __init__(self, db):
        super().__init__(db, "email_verifications")

    async def store_verification_code(self, email: str, verification_code: str) -> Dict[str, Any]:
        """Lưu trữ mã xác thực email tạm thời"""
        try:
            vietnam_timezone = timezone(timedelta(hours=7))
            created_at = datetime.now(vietnam_timezone)
            expires_at = created_at + timedelta(minutes=5)  # Hết hạn sau 5 phút

            # Xóa verification codes cũ của email này
            await self.collection.delete_many({"email": email})

            verification_data = {
                "email": email,
                "verification_code": verification_code,
                "created_at": created_at,
                "expires_at": expires_at,
                "verified": False
            }

            result = await self.collection.insert_one(verification_data)
            verification_data["_id"] = result.inserted_id

            logger.info(f"Stored verification code for email: {email}")
            return verification_data

        except Exception as e:
            logger.error(f"Failed to store verification code for {email}: {str(e)}")
            raise

    async def verify_code(self, email: str, verification_code: str) -> bool:
        """Xác thực mã verification code"""
        try:
            vietnam_timezone = timezone(timedelta(hours=7))
            current_time = datetime.now(vietnam_timezone)

            # Tìm verification record
            verification = await self.collection.find_one({
                "email": email,
                "verification_code": verification_code,
                "verified": False,
                "expires_at": {"$gt": current_time}
            })

            if not verification:
                logger.warning(f"Invalid or expired verification code for email: {email}")
                return False

            # Đánh dấu đã verified
            await self.collection.update_one(
                {"_id": verification["_id"]},
                {"$set": {"verified": True}}
            )

            logger.info(f"Email verified successfully: {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to verify code for {email}: {str(e)}")
            return False

    async def is_email_verified(self, email: str) -> bool:
        """Kiểm tra email đã được xác thực chưa"""
        try:
            verification = await self.collection.find_one({
                "email": email,
                "verified": True
            })
            return verification is not None

        except Exception as e:
            logger.error(f"Failed to check email verification status for {email}: {str(e)}")
            return False

    async def cleanup_expired_codes(self):
        """Xóa các mã xác thực đã hết hạn"""
        try:
            vietnam_timezone = timezone(timedelta(hours=7))
            current_time = datetime.now(vietnam_timezone)

            result = await self.collection.delete_many({
                "expires_at": {"$lt": current_time}
            })

            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} expired verification codes")

        except Exception as e:
            logger.error(f"Failed to cleanup expired verification codes: {str(e)}")

    async def resend_verification_code(self, email: str, new_verification_code: str) -> Dict[str, Any]:
        """Gửi lại mã xác thực mới"""
        try:
            # Xóa tất cả mã cũ của email này
            await self.collection.delete_many({"email": email})

            # Tạo mã mới
            return await self.store_verification_code(email, new_verification_code)

        except Exception as e:
            logger.error(f"Failed to resend verification code for {email}: {str(e)}")
            raise

    async def get_verification_attempts(self, email: str) -> int:
        """Đếm số lần thử xác thực trong 1 giờ qua"""
        try:
            vietnam_timezone = timezone(timedelta(hours=7))
            one_hour_ago = datetime.now(vietnam_timezone) - timedelta(hours=1)

            count = await self.collection.count_documents({
                "email": email,
                "created_at": {"$gte": one_hour_ago}
            })

            return count

        except Exception as e:
            logger.error(f"Failed to get verification attempts for {email}: {str(e)}")
            return 0
