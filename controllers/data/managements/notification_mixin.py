"""
Notification Mixin for Managers
Cung cấp các methods để dễ dàng tạo notifications từ bất kỳ manager nào

IMPORTANT NOTES:
- Các notification methods là async và phải được await trong async context
- Khi gọi từ background tasks với event loop riêng, notifications có thể bị skip
  để tránh conflict (đây là hành vi mong muốn, không phải lỗi)
- Nếu cần đảm bảo notification được tạo, hãy gọi trong main event loop context
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class NotificationMixin:
    """
    Mixin class cung cấp notification methods cho các managers
    
    Usage:
        class YourManager(BaseManager, NotificationMixin):
            def __init__(self, db_manager):
                super().__init__(db_manager, "your_collection")
                self.init_notification_mixin(db_manager)
    """
    
    def init_notification_mixin(self, db_manager):
        """Initialize notification manager and related services"""
        # Kiểm tra xem đã khởi tạo chưa để tránh circular dependency
        if hasattr(self, '_notification_mixin_initialized') and self._notification_mixin_initialized:
            return
        
        self._notification_mixin_initialized = True
        
        from controllers.data.managements.system_management import NotificationManager, UserSettingsManager
        # Lưu db_manager để lazy-load UserManager khi cần (tránh circular dependency)
        self._db_manager_for_notification = db_manager
        self._notification_manager = NotificationManager(db_manager)
        self._user_settings_manager = UserSettingsManager(db_manager)
        self._user_manager = None  # Lazy load để tránh circular dependency
    
    def _get_user_manager(self):
        """Lazy load UserManager để tránh circular dependency"""
        if self._user_manager is None:
            from controllers.data.managements.user_management import UserManager
            # CRITICAL: Không gọi __init__ với NotificationMixin để tránh vòng lặp
            # Sử dụng BaseManager thay vì
            self._user_manager = UserManager.__new__(UserManager)
            BaseManager.__init__(self._user_manager, self._db_manager_for_notification, "users")
            # Không gọi init_notification_mixin ở đây!
        return self._user_manager
    
    async def _create_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: str = "info",
        category: str = "system",
        action: Optional[str] = None,
        priority: int = 2,
        metadata: Optional[Dict[str, Any]] = None,
        link: Optional[Dict[str, str]] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Internal method để tạo notification và tự động gửi email nếu user bật setting
        
        Returns:
            Notification object hoặc None nếu có lỗi
        """
        try:
            # Kiểm tra xem có đang chạy trong đúng event loop không
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                logger.warning("No running event loop. Cannot create notification.")
                return None
            
            # Tạo notification trực tiếp trong event loop hiện tại
            notification = await self._notification_manager.create_notification(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                category=category,
                action=action,
                priority=priority,
                metadata=metadata or {},
                link=link,
                expires_at=expires_at
            )
            
            # Nếu tạo notification thành công, kiểm tra và gửi email
            if notification:
                await self._check_and_send_email_notification(
                    user_id=user_id,
                    title=title,
                    content=content,
                    category=category,
                    action=action,
                    metadata=metadata
                )
            
            return notification
        except RuntimeError as e:
            # Nếu gặp lỗi event loop, log warning và return None (không phải error)
            error_msg = str(e)
            if "attached to a different loop" in error_msg or "different loop" in error_msg:
                logger.debug(f"Event loop conflict when creating notification - notification skipped (this is expected in background tasks)")
                return None
            logger.error(f"Failed to create notification: {error_msg}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}", exc_info=True)
            return None
    
    async def _check_and_send_email_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        category: str,
        action: Optional[str],
        metadata: Optional[Dict[str, Any]]
    ):
        """
        Kiểm tra user settings và gửi email notification nếu được bật
        
        Args:
            user_id: ID user
            title: Tiêu đề notification
            content: Nội dung notification
            category: Category notification
            action: Action notification
            metadata: Dữ liệu bổ sung
        """
        try:
            from controllers.ultils.email_service import EmailService
            
            # Kiểm tra enable_email_notifications
            email_enabled = await self._user_settings_manager.get_setting_value(
                user_id, "email", "enable_email_notifications", False
            )
            
            if not email_enabled:
                return
            
            # Mapping category/action -> setting key để kiểm tra
            setting_key_map = {
                ("order", "created"): "new_order_notifications",
                ("order", "new_order"): "new_order_notifications",
                ("business", "new_order"): "new_order_notifications",
                ("customer", "created"): "new_customer_notifications",
                ("crm", "new_customer"): "new_customer_notifications",
                ("conversation", "message_received"): "new_message_notifications",
                ("conversation", "new_message"): "new_message_notifications",
                ("system", None): "system_notifications",
                ("auth", None): "system_notifications",
                ("bot", None): "system_notifications",
            }
            
            # Tìm setting key tương ứng
            setting_key = setting_key_map.get((category, action))
            if not setting_key:
                # Nếu không tìm thấy mapping cụ thể, dùng system_notifications
                setting_key = "system_notifications"
            
            # Kiểm tra setting cụ thể
            specific_enabled = await self._user_settings_manager.get_setting_value(
                user_id, "email", setting_key, False
            )
            
            if not specific_enabled:
                return
            
            # Lấy thông tin user để gửi email
            user_manager = self._get_user_manager()
            user = await user_manager.get_by_id(user_id)
            if not user or not user.get("email"):
                return
            
            # Gửi email
            await EmailService.send_notification_email(
                email=user.get("email"),
                name=user.get("name", "User"),
                title=title,
                content=content,
                category=category,
                action=action,
                metadata=metadata
            )
            
            logger.info(f"Email notification sent to {user.get('email')} for {category}/{action}")
            
        except Exception as e:
            # Log error nhưng không raise để không ảnh hưởng đến notification
            logger.error(f"Failed to send email notification: {str(e)}", exc_info=True)
    
    async def _notify_multiple_users(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Internal method để gửi notification cho nhiều users
        
        Returns:
            List of created notifications
        """
        try:
            return await self._notification_manager.notify_multiple_users(
                user_ids=user_ids,
                title=title,
                content=content,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Failed to notify multiple users: {str(e)}")
            return []


class SystemNotificationMixin(NotificationMixin):
    """Notification methods cho System events"""
    
    async def notify_system_update(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        priority: int = 3
    ):
        """Thông báo cập nhật hệ thống"""
        return await self._notify_multiple_users(
            user_ids=user_ids,
            title=title,
            content=content,
            notification_type="info",
            category="system",
            action="system_update",
            priority=priority
        )
    
    async def notify_maintenance(
        self,
        user_ids: List[str],
        start_time: datetime,
        duration_minutes: int
    ):
        """Thông báo bảo trì"""
        return await self._notify_multiple_users(
            user_ids=user_ids,
            title="Bảo trì hệ thống",
            content=f"Hệ thống sẽ bảo trì vào {start_time.strftime('%H:%M %d/%m/%Y')}, "
                   f"dự kiến {duration_minutes} phút",
            notification_type="warning",
            category="system",
            action="maintenance",
            priority=5,
            expires_at=start_time + timedelta(minutes=duration_minutes)
        )


class AuthNotificationMixin(NotificationMixin):
    """Notification methods cho Authentication events"""
    
    async def notify_login(
        self,
        user_id: str,
        ip_address: str,
        device: str,
        location: str = "Unknown"
    ):
        """Thông báo đăng nhập mới"""
        return await self._create_notification(
            user_id=user_id,
            title="Đăng nhập mới",
            content=f"Tài khoản của bạn vừa đăng nhập từ {device} tại {location}",
            notification_type="info",
            category="auth",
            action="login",
            priority=2,
            metadata={
                "ip_address": ip_address,
                "device": device,
                "location": location
            }
        )
    
    async def notify_password_changed(self, user_id: str):
        """Thông báo đổi mật khẩu"""
        return await self._create_notification(
            user_id=user_id,
            title="Mật khẩu đã được thay đổi",
            content="Mật khẩu của bạn đã được thay đổi thành công",
            notification_type="success",
            category="auth",
            action="password_reset",
            priority=4
        )
    
    async def notify_security_alert(
        self,
        user_id: str,
        alert_type: str,
        description: str
    ):
        """Thông báo cảnh báo bảo mật"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Cảnh báo bảo mật: {alert_type}",
            content=description,
            notification_type="alert",
            category="security",
            action="security_alert",
            priority=5,
            metadata={"alert_type": alert_type}
        )


class SocialNotificationMixin(NotificationMixin):
    """Notification methods cho Social Media events"""
    
    async def notify_social_connected(
        self,
        user_id: str,
        platform: str,
        account_name: str,
        account_id: str
    ):
        """Thông báo kết nối social platform"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Kết nối {platform} thành công",
            content=f"Bạn đã kết nối tài khoản {platform}: {account_name}",
            notification_type="success",
            category="social",
            action="connected",
            priority=3,
            metadata={
                "platform": platform.lower(),
                "account_name": account_name,
                "account_id": account_id
            },
            link={
                "type": "social_account",
                "url": f"/socials/{platform.lower()}/accounts/{account_id}",
                "resource_id": account_id
            }
        )
    
    async def notify_page_added(
        self,
        user_id: str,
        platform: str,
        page_name: str,
        page_id: str
    ):
        """Thông báo thêm page/channel"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Page {platform} mới",
            content=f"Page '{page_name}' đã được thêm vào",
            notification_type="success",
            category="social",
            action="page_added",
            priority=3,
            metadata={
                "platform": platform.lower(),
                "page_name": page_name,
                "page_id": page_id
            },
            link={
                "type": f"{platform.lower()}_page",
                "url": f"/socials/{platform.lower()}/pages/{page_id}",
                "resource_id": page_id
            }
        )


class ConversationNotificationMixin(NotificationMixin):
    """Notification methods cho Conversation/Message events"""
    
    async def notify_new_message(
        self,
        user_id: str,
        sender_name: str,
        message_preview: str,
        conversation_id: str,
        platform: str = "messenger"
    ):
        """Thông báo tin nhắn mới"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Tin nhắn mới từ {sender_name}",
            content=message_preview[:100] + ("..." if len(message_preview) > 100 else ""),
            notification_type="info",
            category="conversation",
            action="message_received",
            priority=4,
            metadata={
                "sender_name": sender_name,
                "conversation_id": conversation_id,
                "platform": platform
            },
            link={
                "type": "conversation",
                "url": f"/conversations/{conversation_id}",
                "resource_id": conversation_id
            }
        )
    
    async def notify_message_failed(
        self,
        user_id: str,
        recipient_name: str,
        error_message: str,
        conversation_id: str
    ):
        """Thông báo gửi tin nhắn thất bại"""
        return await self._create_notification(
            user_id=user_id,
            title="Gửi tin nhắn thất bại",
            content=f"Không thể gửi tin nhắn đến {recipient_name}: {error_message}",
            notification_type="error",
            category="conversation",
            action="message_failed",
            priority=4,
            metadata={
                "recipient_name": recipient_name,
                "error_message": error_message,
                "conversation_id": conversation_id
            },
            link={
                "type": "conversation",
                "url": f"/conversations/{conversation_id}",
                "resource_id": conversation_id
            }
        )
    
    async def notify_conversation_ended(
        self,
        user_id: str,
        conversation_id: str,
        message_count: int = 0
    ):
        """Thông báo cuộc hội thoại kết thúc"""
        return await self._create_notification(
            user_id=user_id,
            title="Cuộc hội thoại đã kết thúc",
            content=f"Cuộc hội thoại {conversation_id[:8]}... đã được đóng ({message_count} tin nhắn)",
            notification_type="info",
            category="conversation",
            action="conversation_ended",
            priority=5,
            metadata={
                "conversation_id": conversation_id,
                "message_count": message_count
            },
            link={
                "type": "conversation",
                "url": f"/conversations/{conversation_id}",
                "resource_id": conversation_id
            }
        )


class BotNotificationMixin(NotificationMixin):
    """Notification methods cho Bot events"""
    
    async def notify_bot_created(
        self,
        user_id: str,
        bot_name: str,
        bot_id: str
    ):
        """Thông báo tạo bot"""
        return await self._create_notification(
            user_id=user_id,
            title="Bot mới được tạo",
            content=f"Bot '{bot_name}' đã được tạo thành công",
            notification_type="success",
            category="bot",
            action="bot_created",
            priority=3,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            },
            link={
                "type": "bot",
                "url": f"/bots/{bot_id}",
                "resource_id": bot_id
            }
        )
    
    async def notify_bot_activated(
        self,
        user_id: str,
        bot_name: str,
        bot_id: str
    ):
        """Thông báo bot được bật"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Bot '{bot_name}' đã được bật",
            content=f"Bot '{bot_name}' đang hoạt động trở lại và sẵn sàng hỗ trợ khách hàng.",
            notification_type="success",
            category="bot",
            action="bot_activated",
            priority=3,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            },
            link={
                "type": "bot",
                "url": f"/bots/{bot_id}",
                "resource_id": bot_id
            }
        )
    
    async def notify_bot_deactivated(
        self,
        user_id: str,
        bot_name: str,
        bot_id: str
    ):
        """Thông báo bot bị tắt"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Bot '{bot_name}' đã bị tắt",
            content=f"Bot '{bot_name}' đã được tạm dừng hoạt động. Bật lại bot khi bạn sẵn sàng phục vụ khách hàng.",
            notification_type="warning",
            category="bot",
            action="bot_deactivated",
            priority=4,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            },
            link={
                "type": "bot",
                "url": f"/bots/{bot_id}",
                "resource_id": bot_id
            }
        )
    
    async def notify_bot_updated(
        self,
        user_id: str,
        bot_name: str,
        bot_id: str,
        changes: str
    ):
        """Thông báo cập nhật bot"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Bot '{bot_name}' đã được cập nhật",
            content=changes,
            notification_type="info",
            category="bot",
            action="bot_updated",
            priority=2,
            metadata={
                "bot_name": bot_name,
                "bot_id": bot_id
            },
            link={
                "type": "bot",
                "url": f"/bots/{bot_id}",
                "resource_id": bot_id
            }
        )


class CRMNotificationMixin(NotificationMixin):
    """Notification methods cho CRM events"""
    
    async def notify_lead_created(
        self,
        user_id: str,
        lead_name: str,
        lead_id: str,
        source: str = "unknown",
        lead_score: Optional[int] = None
    ):
        """Thông báo lead mới"""
        return await self._create_notification(
            user_id=user_id,
            title="Lead mới",
            content=f"Lead '{lead_name}' đã được tạo từ {source}",
            notification_type="success",
            category="crm",
            action="lead_created",
            priority=3 if not lead_score or lead_score < 70 else 4,
            metadata={
                "lead_name": lead_name,
                "lead_id": lead_id,
                "source": source,
                "lead_score": lead_score
            },
            link={
                "type": "lead",
                "url": f"/crm/leads/{lead_id}",
                "resource_id": lead_id
            }
        )
    
    async def notify_contact_created(
        self,
        user_id: str,
        contact_name: str,
        contact_id: str
    ):
        """Thông báo contact mới"""
        return await self._create_notification(
            user_id=user_id,
            title="Contact mới",
            content=f"Contact '{contact_name}' đã được thêm vào",
            notification_type="success",
            category="crm",
            action="contact_created",
            priority=2,
            metadata={
                "contact_name": contact_name,
                "contact_id": contact_id
            },
            link={
                "type": "contact",
                "url": f"/crm/contacts/{contact_id}",
                "resource_id": contact_id
            }
        )


class CustomerNotificationMixin(NotificationMixin):
    """Notification methods cho Customer events"""
    
    async def notify_customer_created(
        self,
        user_id: str,
        customer_name: str,
        customer_id: str,
        source: str = "manual"
    ):
        """Thông báo khách hàng mới"""
        return await self._create_notification(
            user_id=user_id,
            title="Khách hàng mới",
            content=f"Khách hàng '{customer_name}' đã được thêm vào hệ thống",
            notification_type="success",
            category="customer",
            action="created",
            priority=3,
            metadata={
                "customer_name": customer_name,
                "customer_id": customer_id,
                "source": source
            },
            link={
                "type": "customer",
                "url": f"/customers/{customer_id}",
                "resource_id": customer_id
            }
        )
    
    async def notify_customer_updated(
        self,
        user_id: str,
        customer_name: str,
        customer_id: str,
        changes: str
    ):
        """Thông báo cập nhật khách hàng"""
        return await self._create_notification(
            user_id=user_id,
            title=f"Khách hàng '{customer_name}' đã được cập nhật",
            content=changes,
            notification_type="info",
            category="customer",
            action="updated",
            priority=2,
            metadata={
                "customer_name": customer_name,
                "customer_id": customer_id
            },
            link={
                "type": "customer",
                "url": f"/customers/{customer_id}",
                "resource_id": customer_id
            }
        )
    
    async def notify_customer_deleted(
        self,
        user_id: str,
        customer_name: str,
        customer_id: str,
        reason: Optional[str] = None
    ):
        """Thông báo xóa khách hàng"""
        content = f"Khách hàng '{customer_name}' đã bị xóa khỏi hệ thống"
        if reason:
            content += f": {reason}"
        
        return await self._create_notification(
            user_id=user_id,
            title="Khách hàng đã bị xóa",
            content=content,
            notification_type="warning",
            category="customer",
            action="deleted",
            priority=3,
            metadata={
                "customer_name": customer_name,
                "customer_id": customer_id,
                "reason": reason
            }
        )


class OrderNotificationMixin(NotificationMixin):
    """Notification methods cho Order events"""
    
    async def notify_order_created(
        self,
        user_id: str,
        order_code: str,
        order_id: str,
        total_price: float,
        customer_name: Optional[str] = None,
        currency: str = "VND"
    ):
        """Thông báo đơn hàng mới"""
        content = f"Đơn hàng #{order_code}"
        if customer_name:
            content += f" từ {customer_name}"
        content += f" - {total_price:,.0f} {currency}"
        
        return await self._create_notification(
            user_id=user_id,
            title="Đơn hàng mới",
            content=content,
            notification_type="success",
            category="order",
            action="created",
            priority=4,
            metadata={
                "order_code": order_code,
                "order_id": order_id,
                "customer_name": customer_name,
                "total_price": total_price,
                "currency": currency
            },
            link={
                "type": "order",
                "url": f"/orders/{order_id}",
                "resource_id": order_id
            }
        )
    
    async def notify_order_status_changed(
        self,
        user_id: str,
        order_id: str,
        order_code: str,
        new_status: str,
        old_status: Optional[str] = None
    ):
        """Thông báo thay đổi trạng thái đơn hàng"""
        if old_status:
            content = f"Trạng thái đã thay đổi: {old_status} → {new_status}"
        else:
            content = f"Trạng thái mới: {new_status}"
        
        return await self._create_notification(
            user_id=user_id,
            title=f"Đơn hàng #{order_code} - Cập nhật trạng thái",
            content=content,
            notification_type="info",
            category="order",
            action="updated",
            priority=3,
            metadata={
                "order_id": order_id,
                "order_code": order_code,
                "old_status": old_status,
                "new_status": new_status
            },
            link={
                "type": "order",
                "url": f"/orders/{order_id}",
                "resource_id": order_id
            }
        )
    
    async def notify_order_updated(
        self,
        user_id: str,
        order_id: str,
        order_code: str,
        changes: Optional[str] = None
    ):
        """Thông báo cập nhật đơn hàng"""
        content = changes if changes else f"Đơn hàng #{order_code} đã được cập nhật"
        
        return await self._create_notification(
            user_id=user_id,
            title=f"Đơn hàng #{order_code} đã được cập nhật",
            content=content,
            notification_type="info",
            category="order",
            action="updated",
            priority=3,
            metadata={
                "order_id": order_id,
                "order_code": order_code
            },
            link={
                "type": "order",
                "url": f"/orders/{order_id}",
                "resource_id": order_id
            }
        )
    
    async def notify_order_cancelled(
        self,
        user_id: str,
        order_code: str,
        order_id: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Thông báo hủy đơn hàng"""
        content = f"Đơn hàng #{order_code} đã được hủy"
        if reason:
            content += f": {reason}"
        
        metadata = {
            "order_code": order_code,
            "reason": reason
        }
        
        link = None
        if order_id:
            metadata["order_id"] = order_id
            link = {
                "type": "order",
                "url": f"/orders/{order_id}",
                "resource_id": order_id
            }
        
        return await self._create_notification(
            user_id=user_id,
            title=f"Đơn hàng #{order_code} - Đã hủy",
            content=content,
            notification_type="warning",
            category="order",
            action="cancelled",
            priority=4,
            metadata=metadata,
            link=link
        )


class KnowledgeNotificationMixin(NotificationMixin):
    """Notification methods cho Knowledge/Document events"""
    
    async def notify_document_uploaded(
        self,
        user_id: str,
        document_name: str,
        document_id: str,
        file_size: int
    ):
        """Thông báo upload document"""
        return await self._create_notification(
            user_id=user_id,
            title="Document đã được tải lên",
            content=f"Document '{document_name}' ({file_size} bytes) đã được tải lên",
            notification_type="success",
            category="knowledge",
            action="document_uploaded",
            priority=2,
            metadata={
                "document_name": document_name,
                "document_id": document_id,
                "file_size": file_size
            },
            link={
                "type": "document",
                "url": f"/knowledge/documents/{document_id}",
                "resource_id": document_id
            }
        )
    
    async def notify_document_processed(
        self,
        user_id: str,
        document_name: str,
        document_id: str,
        chunks_count: int
    ):
        """Thông báo xử lý document hoàn tất"""
        return await self._create_notification(
            user_id=user_id,
            title="Document đã được xử lý",
            content=f"Document '{document_name}' đã được xử lý thành {chunks_count} chunks",
            notification_type="success",
            category="knowledge",
            action="document_processed",
            priority=2,
            metadata={
                "document_name": document_name,
                "document_id": document_id,
                "chunks_count": chunks_count
            },
            link={
                "type": "document",
                "url": f"/knowledge/documents/{document_id}",
                "resource_id": document_id
            }
        )


class HistoryNotificationMixin(NotificationMixin):
    """Notification methods cho History/Activity events"""
    
    async def notify_history_created(
        self,
        user_id: str,
        activity_type: str,
        description: str,
        history_id: str,
        related_resource_type: Optional[str] = None,
        related_resource_id: Optional[str] = None
    ):
        """Thông báo hoạt động mới"""
        metadata = {
            "activity_type": activity_type,
            "history_id": history_id
        }
        
        link = None
        if related_resource_type and related_resource_id:
            metadata["related_resource_type"] = related_resource_type
            metadata["related_resource_id"] = related_resource_id
            link = {
                "type": related_resource_type,
                "url": f"/{related_resource_type}s/{related_resource_id}",
                "resource_id": related_resource_id
            }
        
        return await self._create_notification(
            user_id=user_id,
            title=f"Hoạt động mới: {activity_type}",
            content=description,
            notification_type="info",
            category="history",
            action="created",
            priority=1,
            metadata=metadata,
            link=link
        )


class BusinessNotificationMixin(NotificationMixin):
    """Notification methods cho Business events"""
    
    async def notify_business_created(
        self,
        user_id: str,
        business_name: str,
        business_id: str
    ):
        """Thông báo tạo business"""
        return await self._create_notification(
            user_id=user_id,
            title="Tổ chức mới",
            content=f"Tổ chức '{business_name}' đã được tạo",
            notification_type="success",
            category="business",
            action="business_created",
            priority=3,
            metadata={
                "business_name": business_name,
                "business_id": business_id
            },
            link={
                "type": "business",
                "url": f"/business/{business_id}",
                "resource_id": business_id
            }
        )
    
    async def notify_member_invited(
        self,
        user_id: str,
        business_name: str,
        inviter_name: str,
        role: str
    ):
        """Thông báo được mời vào business"""
        return await self._create_notification(
            user_id=user_id,
            title="Lời mời tham gia tổ chức",
            content=f"{inviter_name} đã mời bạn tham gia '{business_name}' với vai trò {role}",
            notification_type="info",
            category="business",
            action="member_invited",
            priority=4,
            metadata={
                "business_name": business_name,
                "inviter_name": inviter_name,
                "role": role
            }
        )
