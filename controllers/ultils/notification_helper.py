"""
Notification Helper
Các hàm tiện ích để tạo notifications dễ dàng từ bất kỳ đâu trong ứng dụng
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from controllers.data.managements import get_mongodb_factory
from controllers.data.managements.system_management import (
    NotificationCategory,
    NotificationType,
    NotificationAction
)

logger = logging.getLogger(__name__)


class NotificationHelper:
    """Helper class để tạo notifications dễ dàng"""
    
    @staticmethod
    async def notify(
        user_id: str,
        title: str,
        content: str,
        notification_type: str = NotificationType.INFO,
        category: str = NotificationCategory.SYSTEM,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Tạo notification cơ bản
        
        Example:
            await NotificationHelper.notify(
                user_id="user123",
                title="Thành công",
                content="Bạn đã kết nối Facebook thành công",
                notification_type=NotificationType.SUCCESS,
                category=NotificationCategory.SOCIAL
            )
        """
        try:
            factory = get_mongodb_factory()
            return await factory.notification_manager.create_quick_notification(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                category=category,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    @staticmethod
    async def notify_with_link(
        user_id: str,
        title: str,
        content: str,
        link_type: str,
        link_url: str,
        resource_id: str,
        notification_type: str = NotificationType.INFO,
        category: str = NotificationCategory.SYSTEM,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Tạo notification với link để navigate
        
        Example:
            await NotificationHelper.notify_with_link(
                user_id="user123",
                title="Facebook Page mới",
                content="Page 'My Shop' đã được thêm vào",
                link_type="facebook_page",
                link_url="/socials/facebook/pages/123456",
                resource_id="123456",
                notification_type=NotificationType.SUCCESS,
                category=NotificationCategory.SOCIAL
            )
        """
        try:
            factory = get_mongodb_factory()
            return await factory.notification_manager.create_notification(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                category=category,
                link={
                    "type": link_type,
                    "url": link_url,
                    "resource_id": resource_id
                },
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to create notification with link: {str(e)}")
            return None
    
    # ===== SOCIAL MEDIA NOTIFICATIONS =====
    
    @staticmethod
    async def notify_social_connected(
        user_id: str,
        platform: str,
        account_name: str,
        account_id: str
    ):
        """Thông báo kết nối social platform thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title=f"Kết nối {platform} thành công",
            content=f"Bạn đã kết nối tài khoản {platform}: {account_name}",
            link_type="social_account",
            link_url=f"/socials/{platform.lower()}/accounts/{account_id}",
            resource_id=account_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.SOCIAL,
            action=NotificationAction.CONNECTED,
            priority=3,
            metadata={
                "platform": platform.lower(),
                "account_name": account_name,
                "account_id": account_id
            }
        )
    
    @staticmethod
    async def notify_social_disconnected(
        user_id: str,
        platform: str,
        account_name: str
    ):
        """Thông báo ngắt kết nối social platform"""
        return await NotificationHelper.notify(
            user_id=user_id,
            title=f"Đã ngắt kết nối {platform}",
            content=f"Tài khoản {platform}: {account_name} đã được ngắt kết nối",
            notification_type=NotificationType.WARNING,
            category=NotificationCategory.SOCIAL,
            action=NotificationAction.DISCONNECTED,
            priority=2,
            metadata={
                "platform": platform.lower(),
                "account_name": account_name
            }
        )
    
    @staticmethod
    async def notify_page_added(
        user_id: str,
        platform: str,
        page_name: str,
        page_id: str
    ):
        """Thông báo thêm page/channel thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title=f"Page {platform} mới",
            content=f"Page '{page_name}' đã được thêm vào",
            link_type=f"{platform.lower()}_page",
            link_url=f"/socials/{platform.lower()}/pages/{page_id}",
            resource_id=page_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.SOCIAL,
            action=NotificationAction.PAGE_ADDED,
            priority=3,
            metadata={
                "platform": platform.lower(),
                "page_name": page_name,
                "page_id": page_id
            }
        )
    
    # ===== BOT NOTIFICATIONS =====
    
    @staticmethod
    async def notify_bot_created(
        user_id: str,
        bot_name: str,
        bot_id: str
    ):
        """Thông báo tạo bot thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Bot mới được tạo",
            content=f"Bot '{bot_name}' đã được tạo thành công",
            link_type="bot",
            link_url=f"/bots/{bot_id}",
            resource_id=bot_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.BOT,
            action=NotificationAction.BOT_CREATED,
            priority=3,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            }
        )
    
    @staticmethod
    async def notify_bot_updated(
        user_id: str,
        bot_name: str,
        bot_id: str,
        changes: str
    ):
        """Thông báo cập nhật bot"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title=f"Bot '{bot_name}' đã được cập nhật",
            content=changes,
            link_type="bot",
            link_url=f"/bots/{bot_id}",
            resource_id=bot_id,
            notification_type=NotificationType.INFO,
            category=NotificationCategory.BOT,
            action=NotificationAction.BOT_UPDATED,
            priority=2,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            }
        )
    
    # ===== MESSAGE/CONVERSATION NOTIFICATIONS =====
    
    @staticmethod
    async def notify_new_message(
        user_id: str,
        sender_name: str,
        message_preview: str,
        conversation_id: str,
        platform: str = "messenger"
    ):
        """Thông báo tin nhắn mới"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title=f"Tin nhắn mới từ {sender_name}",
            content=message_preview[:100] + ("..." if len(message_preview) > 100 else ""),
            link_type="conversation",
            link_url=f"/conversations/{conversation_id}",
            resource_id=conversation_id,
            notification_type=NotificationType.INFO,
            category=NotificationCategory.CONVERSATION,
            action=NotificationAction.MESSAGE_RECEIVED,
            priority=4,
            metadata={
                "sender_name": sender_name,
                "conversation_id": conversation_id,
                "platform": platform
            }
        )
    
    @staticmethod
    async def notify_message_failed(
        user_id: str,
        recipient_name: str,
        error_message: str,
        conversation_id: str
    ):
        """Thông báo gửi tin nhắn thất bại"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Gửi tin nhắn thất bại",
            content=f"Không thể gửi tin nhắn đến {recipient_name}: {error_message}",
            link_type="conversation",
            link_url=f"/conversations/{conversation_id}",
            resource_id=conversation_id,
            notification_type=NotificationType.ERROR,
            category=NotificationCategory.CONVERSATION,
            action=NotificationAction.MESSAGE_FAILED,
            priority=4,
            metadata={
                "recipient_name": recipient_name,
                "error_message": error_message,
                "conversation_id": conversation_id
            }
        )
    
    # ===== CRM NOTIFICATIONS =====
    
    @staticmethod
    async def notify_lead_created(
        user_id: str,
        lead_name: str,
        lead_id: str,
        source: str = "unknown"
    ):
        """Thông báo lead mới"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Lead mới",
            content=f"Lead '{lead_name}' đã được tạo từ {source}",
            link_type="lead",
            link_url=f"/crm/leads/{lead_id}",
            resource_id=lead_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.CRM,
            action=NotificationAction.LEAD_CREATED,
            priority=3,
            metadata={
                "lead_name": lead_name,
                "lead_id": lead_id,
                "source": source
            }
        )
    
    # ===== BUSINESS NOTIFICATIONS =====
    
    @staticmethod
    async def notify_business_created(
        user_id: str,
        business_name: str,
        business_id: str
    ):
        """Thông báo tạo business thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Tổ chức mới",
            content=f"Tổ chức '{business_name}' đã được tạo",
            link_type="business",
            link_url=f"/business/{business_id}",
            resource_id=business_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.BUSINESS,
            action=NotificationAction.BUSINESS_CREATED,
            priority=3,
            metadata={
                "business_name": business_name,
                "business_id": business_id
            }
        )
    
    # ===== KNOWLEDGE NOTIFICATIONS =====
    
    @staticmethod
    async def notify_document_uploaded(
        user_id: str,
        document_name: str,
        document_id: str,
        file_size: int
    ):
        """Thông báo tải document thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Document đã được tải lên",
            content=f"Document '{document_name}' ({file_size} bytes) đã được tải lên",
            link_type="document",
            link_url=f"/knowledge/documents/{document_id}",
            resource_id=document_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.KNOWLEDGE,
            action=NotificationAction.DOCUMENT_UPLOADED,
            priority=2,
            metadata={
                "document_name": document_name,
                "document_id": document_id,
                "file_size": file_size
            }
        )
    
    @staticmethod
    async def notify_document_processed(
        user_id: str,
        document_name: str,
        document_id: str,
        chunks_count: int
    ):
        """Thông báo xử lý document hoàn tất"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Document đã được xử lý",
            content=f"Document '{document_name}' đã được xử lý thành {chunks_count} chunks",
            link_type="document",
            link_url=f"/knowledge/documents/{document_id}",
            resource_id=document_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.KNOWLEDGE,
            action=NotificationAction.DOCUMENT_PROCESSED,
            priority=2,
            metadata={
                "document_name": document_name,
                "document_id": document_id,
                "chunks_count": chunks_count
            }
        )
    
    # ===== SYSTEM NOTIFICATIONS =====
    
    @staticmethod
    async def notify_system_update(
        user_ids: List[str],
        title: str,
        content: str,
        priority: int = 3
    ):
        """Thông báo cập nhật hệ thống cho nhiều users"""
        factory = get_mongodb_factory()
        return await factory.notification_manager.notify_multiple_users(
            user_ids=user_ids,
            title=title,
            content=content,
            notification_type=NotificationType.INFO,
            category=NotificationCategory.SYSTEM,
            action=NotificationAction.SYSTEM_UPDATE,
            priority=priority
        )
    
    @staticmethod
    async def notify_maintenance(
        user_ids: List[str],
        start_time: datetime,
        duration_minutes: int
    ):
        """Thông báo bảo trì hệ thống"""
        factory = get_mongodb_factory()
        return await factory.notification_manager.notify_multiple_users(
            user_ids=user_ids,
            title="Bảo trì hệ thống",
            content=f"Hệ thống sẽ bảo trì vào {start_time.strftime('%H:%M %d/%m/%Y')}, "
                   f"dự kiến {duration_minutes} phút",
            notification_type=NotificationType.WARNING,
            category=NotificationCategory.SYSTEM,
            action=NotificationAction.MAINTENANCE,
            priority=5,
            expires_at=start_time + timedelta(minutes=duration_minutes)
        )
    
    # ===== AUTH NOTIFICATIONS =====
    
    @staticmethod
    async def notify_login(
        user_id: str,
        ip_address: str,
        device: str,
        location: str = "Unknown"
    ):
        """Thông báo đăng nhập mới"""
        return await NotificationHelper.notify(
            user_id=user_id,
            title="Đăng nhập mới",
            content=f"Tài khoản của bạn vừa đăng nhập từ {device} tại {location}",
            notification_type=NotificationType.INFO,
            category=NotificationCategory.AUTH,
            action=NotificationAction.LOGIN,
            priority=2,
            metadata={
                "ip_address": ip_address,
                "device": device,
                "location": location
            }
        )
    
    @staticmethod
    async def notify_password_reset(
        user_id: str
    ):
        """Thông báo reset mật khẩu"""
        return await NotificationHelper.notify(
            user_id=user_id,
            title="Mật khẩu đã được đặt lại",
            content="Mật khẩu của bạn đã được thay đổi thành công",
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.AUTH,
            action=NotificationAction.PASSWORD_RESET,
            priority=4
        )
    
    # ===== PAYMENT NOTIFICATIONS =====
    
    @staticmethod
    async def notify_payment_success(
        user_id: str,
        amount: float,
        currency: str,
        transaction_id: str
    ):
        """Thông báo thanh toán thành công"""
        return await NotificationHelper.notify_with_link(
            user_id=user_id,
            title="Thanh toán thành công",
            content=f"Bạn đã thanh toán thành công {amount} {currency}",
            link_type="transaction",
            link_url=f"/payments/transactions/{transaction_id}",
            resource_id=transaction_id,
            notification_type=NotificationType.SUCCESS,
            category=NotificationCategory.PAYMENT,
            action=NotificationAction.PAYMENT_SUCCESS,
            priority=3,
            metadata={
                "amount": amount,
                "currency": currency,
                "transaction_id": transaction_id
            }
        )
    
    @staticmethod
    async def notify_payment_failed(
        user_id: str,
        amount: float,
        currency: str,
        reason: str
    ):
        """Thông báo thanh toán thất bại"""
        return await NotificationHelper.notify(
            user_id=user_id,
            title="Thanh toán thất bại",
            content=f"Không thể thanh toán {amount} {currency}. Lý do: {reason}",
            notification_type=NotificationType.ERROR,
            category=NotificationCategory.PAYMENT,
            action=NotificationAction.PAYMENT_FAILED,
            priority=4,
            metadata={
                "amount": amount,
                "currency": currency,
                "reason": reason
            }
        )


# Singleton instance
_notification_helper = NotificationHelper()


# Shorthand functions để gọi nhanh hơn
async def notify(user_id: str, title: str, content: str, **kwargs):
    """Shorthand function để tạo notification nhanh"""
    return await _notification_helper.notify(user_id, title, content, **kwargs)


async def notify_with_link(user_id: str, title: str, content: str, 
                          link_type: str, link_url: str, resource_id: str, **kwargs):
    """Shorthand function để tạo notification với link"""
    return await _notification_helper.notify_with_link(
        user_id, title, content, link_type, link_url, resource_id, **kwargs
    )


# Email notification helpers
async def notify_new_order(
    user_id: str,
    order_data: Dict[str, Any],
    user_name: str = None,
    user_email: str = None
):
    """
    Thông báo khi có đơn hàng mới
    
    Args:
        user_id: ID của user
        order_data: Dữ liệu đơn hàng
        user_name: Tên user
        user_email: Email user
    """
    try:
        from controllers.ultils.email_service import EmailService
        
        factory = get_mongodb_factory()
        
        # Tạo notification
        await factory.notification_manager.create_notification(
            user_id=user_id,
            title="Đơn hàng mới",
            content=f"Bạn có đơn hàng mới #{order_data.get('order_id', 'N/A')} với giá trị {order_data.get('total', 0):,}đ",
            notification_type="success",
            category="business",
            action="new_order",
            priority=3,
            metadata=order_data
        )
        
        # Kiểm tra setting để gửi email
        email_enabled = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "enable_email_notifications", False
        )
        new_order_notifications = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "new_order_notifications", False
        )
        
        if email_enabled and new_order_notifications and user_email:
            await EmailService.send_notification_email(
                user_email,
                user_name or "User",
                "Đơn hàng mới",
                f"Bạn có đơn hàng mới #{order_data.get('order_id', 'N/A')} với giá trị {order_data.get('total', 0):,}đ",
                "business",
                "new_order",
                order_data
            )
            
    except Exception as e:
        logger.error(f"Error notifying new order: {str(e)}")


async def notify_new_customer(
    user_id: str,
    customer_data: Dict[str, Any],
    user_name: str = None,
    user_email: str = None
):
    """
    Thông báo khi có khách hàng mới
    """
    try:
        from controllers.ultils.email_service import EmailService
        
        factory = get_mongodb_factory()
        
        # Tạo notification
        await factory.notification_manager.create_notification(
            user_id=user_id,
            title="Khách hàng mới",
            content=f"Bạn có khách hàng mới: {customer_data.get('name', 'N/A')} ({customer_data.get('email', 'N/A')})",
            notification_type="info",
            category="crm",
            action="new_customer",
            priority=2,
            metadata=customer_data
        )
        
        # Kiểm tra setting để gửi email
        email_enabled = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "enable_email_notifications", False
        )
        new_customer_notifications = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "new_customer_notifications", False
        )
        
        if email_enabled and new_customer_notifications and user_email:
            await EmailService.send_notification_email(
                user_email,
                user_name or "User",
                "Khách hàng mới",
                f"Bạn có khách hàng mới: {customer_data.get('name', 'N/A')} ({customer_data.get('email', 'N/A')})",
                "crm",
                "new_customer",
                customer_data
            )
            
    except Exception as e:
        logger.error(f"Error notifying new customer: {str(e)}")


async def notify_new_message(
    user_id: str,
    message_data: Dict[str, Any],
    user_name: str = None,
    user_email: str = None
):
    """
    Thông báo khi có tin nhắn mới
    """
    try:
        from controllers.ultils.email_service import EmailService
        
        factory = get_mongodb_factory()
        
        # Tạo notification
        await factory.notification_manager.create_notification(
            user_id=user_id,
            title="Tin nhắn mới", 
            content=f"Bạn có tin nhắn mới từ {message_data.get('sender_name', 'N/A')}: {message_data.get('message', '')[:50]}...",
            notification_type="info",
            category="conversation",
            action="new_message",
            priority=2,
            metadata=message_data
        )
        
        # Kiểm tra setting để gửi email
        email_enabled = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "enable_email_notifications", False
        )
        new_message_notifications = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "new_message_notifications", False
        )
        
        if email_enabled and new_message_notifications and user_email:
            await EmailService.send_notification_email(
                user_email,
                user_name or "User",
                "Tin nhắn mới",
                f"Bạn có tin nhắn mới từ {message_data.get('sender_name', 'N/A')}: {message_data.get('message', '')}",
                "conversation",
                "new_message",
                message_data
            )
            
    except Exception as e:
        logger.error(f"Error notifying new message: {str(e)}")


async def check_and_send_email_notification(
    user_id: str,
    setting_key: str,
    email: str,
    name: str,
    title: str,
    content: str,
    category: str = "system",
    action: str = None,
    metadata: Dict[str, Any] = None
):
    """
    Kiểm tra setting và gửi email notification nếu được bật
    
    Args:
        user_id: ID user
        setting_key: Key setting để check (VD: "new_order_notifications")
        email: Email để gửi
        name: Tên user
        title: Tiêu đề email
        content: Nội dung email
        category: Category notification
        action: Action notification
        metadata: Dữ liệu bổ sung
        
    Returns:
        bool: True nếu đã gửi email
    """
    try:
        from controllers.ultils.email_service import EmailService
        
        factory = get_mongodb_factory()
        
        # Kiểm tra email notifications có được bật không
        email_enabled = await factory.user_settings_manager.get_setting_value(
            user_id, "email", "enable_email_notifications", False
        )
        
        # Kiểm tra setting cụ thể có được bật không
        specific_enabled = await factory.user_settings_manager.get_setting_value(
            user_id, "email", setting_key, False
        )
        
        if email_enabled and specific_enabled:
            await EmailService.send_notification_email(
                email,
                name,
                title,
                content,
                category,
                action,
                metadata
            )
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error checking and sending email notification: {str(e)}")
        return False
