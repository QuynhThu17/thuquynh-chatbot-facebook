"""
Test script để kiểm tra tính năng tự động gửi email notification
"""

import asyncio
import logging
from controllers.databases.mongodb.mongodb import get_mongodb_manager
from controllers.data.managements.system_management import NotificationManager, UserSettingsManager
from controllers.data.managements.user_management import UserManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_email_notification():
    """
    Test case: Tạo notification và kiểm tra email có được gửi tự động không
    
    Prerequisites:
    1. User phải có email settings với enable_email_notifications = True
    2. User phải có setting cụ thể (ví dụ: new_order_notifications = True)
    3. User phải có email trong profile
    """
    
    # Khởi tạo managers
    db_manager = await get_mongodb_manager()
    user_manager = UserManager(db_manager)
    user_settings_manager = UserSettingsManager(db_manager)
    
    # Tìm một user để test
    users = await user_manager.get_all(limit=1)
    if not users:
        logger.error("Không tìm thấy user nào để test")
        return
    
    test_user = users[0]
    user_id = str(test_user["_id"])
    
    logger.info(f"Testing with user: {test_user.get('name')} ({test_user.get('email')})")
    
    # Kiểm tra email settings hiện tại
    email_enabled = await user_settings_manager.get_setting_value(
        user_id, "email", "enable_email_notifications", False
    )
    logger.info(f"Email notifications enabled: {email_enabled}")
    
    new_order_enabled = await user_settings_manager.get_setting_value(
        user_id, "email", "new_order_notifications", False
    )
    logger.info(f"New order notifications enabled: {new_order_enabled}")
    
    # Nếu chưa bật, bật lên để test
    if not email_enabled:
        logger.info("Enabling email notifications...")
        await user_settings_manager.create_setting(
            user_id, "email", "enable_email_notifications", True
        )
    
    if not new_order_enabled:
        logger.info("Enabling new order notifications...")
        await user_settings_manager.create_setting(
            user_id, "email", "new_order_notifications", True
        )
    
    # Test với OrderNotificationMixin
    from controllers.data.managements.notification_mixin import OrderNotificationMixin
    
    # Tạo một test manager với OrderNotificationMixin
    class TestManager(OrderNotificationMixin):
        def __init__(self, db_manager):
            self.init_notification_mixin(db_manager)
    
    test_manager = TestManager(db_manager)
    
    # Gửi notification cho order mới
    logger.info("Creating new order notification...")
    notification = await test_manager.notify_order_created(
        user_id=user_id,
        order_code="TEST001",
        order_id="test_order_123",
        total_price=1000000,
        customer_name="Test Customer",
        currency="VND"
    )
    
    if notification:
        logger.info(f"✅ Notification created successfully: {notification.get('_id')}")
        logger.info("✅ Email should be sent automatically if settings are enabled")
        logger.info("   Check your email inbox!")
    else:
        logger.error("❌ Failed to create notification")


if __name__ == "__main__":
    asyncio.run(test_email_notification())
