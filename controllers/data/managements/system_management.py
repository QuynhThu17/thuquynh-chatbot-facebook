"""
System Management Module
Quản lý các collections hệ thống: notifications, user_settings, api_keys, sessions, 
audit_logs, file_uploads, support_tickets, faqs, feature_requests, webhooks, templates, 
analytics_data, conversation_contexts, languages, translations
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from enum import Enum
from .base_manager import BaseManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

# Notification Categories
class NotificationCategory(str, Enum):
    """Các danh mục notification"""
    SYSTEM = "system"              # Thông báo hệ thống
    AUTH = "auth"                  # Xác thực, đăng nhập
    BOT = "bot"                    # Bot, AI assistant
    SOCIAL = "social"              # Social media
    CONVERSATION = "conversation"  # Hội thoại, tin nhắn
    BUSINESS = "business"          # Business, tổ chức
    USER = "user"                  # User, profile
    CRM = "crm"                    # Khách hàng, leads
    KNOWLEDGE = "knowledge"        # Kiến thức, documents
    PAYMENT = "payment"            # Thanh toán
    SUBSCRIPTION = "subscription"  # Đăng ký dịch vụ
    INTEGRATION = "integration"    # Tích hợp bên thứ 3
    ANALYTICS = "analytics"        # Phân tích, báo cáo
    SECURITY = "security"          # Bảo mật
    ERROR = "error"                # Lỗi hệ thống

# Notification Types
class NotificationType(str, Enum):
    """Các loại notification"""
    INFO = "info"        # Thông tin
    SUCCESS = "success"  # Thành công
    WARNING = "warning"  # Cảnh báo
    ERROR = "error"      # Lỗi
    ALERT = "alert"      # Cảnh báo quan trọng

# Notification Actions - giúp định nghĩa hành động đã xảy ra
class NotificationAction(str, Enum):
    """Các hành động tạo notification"""
    # Auth actions
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_RESET = "password_reset"
    
    # Social actions
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PAGE_ADDED = "page_added"
    PAGE_REMOVED = "page_removed"
    
    # Bot actions
    BOT_CREATED = "bot_created"
    BOT_UPDATED = "bot_updated"
    BOT_DELETED = "bot_deleted"
    
    # Message actions
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    MESSAGE_FAILED = "message_failed"
    
    # CRM actions
    LEAD_CREATED = "lead_created"
    LEAD_UPDATED = "lead_updated"
    CONTACT_CREATED = "contact_created"
    
    # Business actions
    BUSINESS_CREATED = "business_created"
    BUSINESS_UPDATED = "business_updated"
    
    # Knowledge actions
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_PROCESSED = "document_processed"
    
    # System actions
    SYSTEM_UPDATE = "system_update"
    MAINTENANCE = "maintenance"
    BACKUP_COMPLETED = "backup_completed"
    
    # Payment actions
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    SUBSCRIPTION_RENEWED = "subscription_renewed"
    SUBSCRIPTION_EXPIRED = "subscription_expired"
    
    # Generic actions
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    COMPLETED = "completed"
    FAILED = "failed"

class NotificationManager(BaseManager):
    """Manager cho notifications collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "notifications")
    
    async def create_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: str = NotificationType.INFO,
        category: str = NotificationCategory.SYSTEM,
        action: Optional[str] = None,
        priority: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        link: Optional[Dict[str, str]] = None,
        is_read: bool = False,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Tạo notification mới
        
        Args:
            user_id: ID user nhận notification
            title: Tiêu đề ngắn gọn
            content: Nội dung chi tiết
            notification_type: info, success, warning, error, alert
            category: system, auth, bot, social, conversation, business, etc.
            action: Hành động đã xảy ra (login, created, updated, etc.)
            priority: Độ ưu tiên 1-5 (5 là cao nhất)
            metadata: Dữ liệu bổ sung liên quan
            link: Link để navigate tới resource {"type": "page", "url": "/...", "resource_id": "..."}
            is_read: Đã đọc chưa
            expires_at: Thời gian hết hạn notification
            
        Returns:
            Dict chứa notification đã tạo
            
        Example:
            await notification_manager.create_notification(
                user_id="user123",
                title="Kết nối Facebook thành công",
                content="Bạn đã kết nối thành công với Facebook Page: My Page",
                notification_type=NotificationType.SUCCESS,
                category=NotificationCategory.SOCIAL,
                action=NotificationAction.CONNECTED,
                priority=3,
                metadata={"platform": "facebook", "page_id": "123456", "page_name": "My Page"},
                link={"type": "social_page", "url": "/socials/facebook/pages/123456", "resource_id": "123456"}
            )
        """
        notification_data = {
            "user_id": user_id,
            "title": title,
            "content": content,
            "type": notification_type,
            "category": category,
            "action": action,
            "priority": priority,
            "metadata": metadata or {},
            "link": link,
            "is_read": is_read,
            "expires_at": expires_at,
            "read_at": None
        }
        return await self.create(notification_data)
    
    async def create_quick_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: str = NotificationType.INFO,
        category: str = NotificationCategory.SYSTEM,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Tạo notification nhanh với ít tham số hơn
        
        Example:
            await notification_manager.create_quick_notification(
                user_id="user123",
                title="Bot đã được tạo",
                content="Bot 'Customer Support' đã được tạo thành công",
                notification_type=NotificationType.SUCCESS,
                category=NotificationCategory.BOT
            )
        """
        return await self.create_notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            category=category,
            **kwargs
        )
    
    async def notify_multiple_users(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Gửi notification cho nhiều users cùng lúc
        
        Args:
            user_ids: List user IDs
            title: Tiêu đề
            content: Nội dung
            **kwargs: Các tham số khác của create_notification
            
        Returns:
            List notifications đã tạo
        """
        notifications = []
        for user_id in user_ids:
            try:
                notification = await self.create_notification(
                    user_id=user_id,
                    title=title,
                    content=content,
                    **kwargs
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Failed to create notification for user {user_id}: {str(e)}")
        
        return notifications
    
    async def get_by_user_id(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        category: Optional[str] = None,
        notification_type: Optional[str] = None,
        action: Optional[str] = None,
        priority: Optional[int] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lấy notifications theo user_id với nhiều filter options
        
        Args:
            user_id: ID user
            is_read: Lọc theo trạng thái đã đọc/chưa đọc
            category: Lọc theo category
            notification_type: Lọc theo type (info, success, warning, error)
            action: Lọc theo action
            priority: Lọc theo độ ưu tiên
            limit: Giới hạn số lượng
            skip: Bỏ qua số lượng
        """
        filter_query = {"user_id": user_id}
        
        # Lọc theo các điều kiện
        if is_read is not None:
            filter_query["is_read"] = is_read
        if category:
            filter_query["category"] = category
        if notification_type:
            filter_query["type"] = notification_type
        if action:
            filter_query["action"] = action
        if priority:
            filter_query["priority"] = priority
        
        # Lọc notifications chưa hết hạn
        filter_query["$or"] = [
            {"expires_at": None},
            {"expires_at": {"$gt": get_vietnam_now_naive()}}
        ]
        
        return await self.get_all(
            filter_query=filter_query,
            limit=limit,
            skip=skip,
            sort_by="priority",
            sort_order=-1
        )
    
    async def mark_as_read(self, notification_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Đánh dấu đã đọc"""
        return await self.update_by_id(notification_id, {
            "is_read": True,
            "read_at": get_vietnam_now_naive()
        })
    
    async def mark_as_unread(self, notification_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Đánh dấu chưa đọc"""
        return await self.update_by_id(notification_id, {
            "is_read": False,
            "read_at": None
        })
    
    async def mark_all_as_read(self, user_id: str, category: Optional[str] = None) -> int:
        """
        Đánh dấu tất cả notifications của user đã đọc
        
        Args:
            user_id: ID user
            category: Nếu có, chỉ đánh dấu notifications của category này
        """
        filter_query = {"user_id": user_id, "is_read": False}
        if category:
            filter_query["category"] = category
            
        return await self.bulk_update([{
            "filter": filter_query,
            "update": {
                "is_read": True,
                "read_at": get_vietnam_now_naive()
            }
        }])
    
    async def get_unread_count(
        self,
        user_id: str,
        category: Optional[str] = None,
        priority: Optional[int] = None
    ) -> int:
        """
        Đếm số notifications chưa đọc
        
        Args:
            user_id: ID user
            category: Nếu có, chỉ đếm notifications của category này
            priority: Nếu có, chỉ đếm notifications có priority này trở lên
        """
        filter_query = {"user_id": user_id, "is_read": False}
        
        if category:
            filter_query["category"] = category
        if priority:
            filter_query["priority"] = {"$gte": priority}
        
        # Lọc notifications chưa hết hạn
        filter_query["$or"] = [
            {"expires_at": None},
            {"expires_at": {"$gt": get_vietnam_now_naive()}}
        ]
        
        return await self.count(filter_query)
    
    async def get_unread_count_by_category(self, user_id: str) -> Dict[str, int]:
        """
        Lấy số lượng notifications chưa đọc theo từng category
        
        Returns:
            Dict với key là category, value là số lượng unread
            Example: {"system": 5, "bot": 3, "social": 2}
        """
        result = {}
        for category in NotificationCategory:
            count = await self.get_unread_count(user_id, category=category.value)
            if count > 0:
                result[category.value] = count
        return result
    
    async def delete_old_notifications(self, days: int = 30) -> int:
        """
        Xóa notifications cũ đã đọc
        
        Args:
            days: Xóa notifications đã đọc cũ hơn X ngày
            
        Returns:
            Số lượng đã xóa
        """
        cutoff_date = get_vietnam_now_naive() - timedelta(days=days)
        filter_query = {
            "is_read": True,
            "create_at": {"$lt": cutoff_date}
        }
        
        old_notifications = await self.get_all(filter_query=filter_query)
        deleted_count = 0
        
        for notification in old_notifications:
            if await self.delete_by_id(notification["_id"]):
                deleted_count += 1
        
        return deleted_count
    
    async def delete_expired_notifications(self) -> int:
        """Xóa notifications đã hết hạn"""
        filter_query = {
            "expires_at": {"$lte": get_vietnam_now_naive()}
        }
        
        expired_notifications = await self.get_all(filter_query=filter_query)
        deleted_count = 0
        
        for notification in expired_notifications:
            if await self.delete_by_id(notification["_id"]):
                deleted_count += 1
        
        return deleted_count


class UserSettingsManager(BaseManager):
    """Manager cho user_settings collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "user_settings")
    
    async def create_setting(self, user_id: str, category: str, setting_key: str,
                           setting_value: Any) -> Dict[str, Any]:
        """
        Tạo/Cập nhật setting
        
        Args:
            user_id: ID user
            category: notification, privacy, api, integration
            setting_key: Key setting
            setting_value: Giá trị setting
        """
        # Kiểm tra xem setting đã tồn tại chưa
        existing = await self.get_all(
            filter_query={"user_id": user_id, "category": category, "setting_key": setting_key},
            limit=1
        )
        
        if existing:
            # Update existing setting
            return await self.update_by_id(existing[0]["_id"], {"setting_value": setting_value})
        else:
            # Create new setting
            setting_data = {
                "user_id": user_id,
                "category": category,
                "setting_key": setting_key,
                "setting_value": setting_value
            }
            return await self.create(setting_data)
    
    async def get_user_settings(self, user_id: str, category: str = None) -> List[Dict[str, Any]]:
        """Lấy settings của user"""
        filter_query = {"user_id": user_id}
        if category:
            filter_query["category"] = category
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_setting_value(self, user_id: str, category: str, setting_key: str,
                              default_value: Any = None) -> Any:
        """Lấy giá trị setting cụ thể"""
        settings = await self.get_all(
            filter_query={"user_id": user_id, "category": category, "setting_key": setting_key},
            limit=1
        )
        
        if settings:
            return settings[0].get("setting_value", default_value)
        return default_value


class ApiKeyManager(BaseManager):
    """Manager cho api_keys collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "api_keys")
    
    async def create_api_key(self, user_id: str, key_name: str, api_key_hash: str,
                           permissions: List[str] = None, expires_at: datetime = None) -> Dict[str, Any]:
        """
        Tạo API key mới
        
        Args:
            user_id: ID user
            key_name: Tên key
            api_key_hash: Hash của API key
            permissions: List endpoints được phép
            expires_at: Thời gian hết hạn
        """
        key_data = {
            "user_id": user_id,
            "key_name": key_name,
            "api_key_hash": api_key_hash,
            "permissions": permissions or [],
            "is_active": True,
            "last_used": None,
            "usage_count": 0,
            "expires_at": expires_at
        }
        return await self.create(key_data)
    
    async def get_by_user_id(self, user_id: str, is_active: bool = None) -> List[Dict[str, Any]]:
        """Lấy API keys của user"""
        filter_query = {"user_id": user_id}
        if is_active is not None:
            filter_query["is_active"] = is_active
        
        return await self.get_all(filter_query=filter_query, sort_by="create_at", sort_order=-1)
    
    async def get_by_key_hash(self, api_key_hash: str) -> Optional[Dict[str, Any]]:
        """Lấy API key theo hash"""
        keys = await self.get_all(filter_query={"api_key_hash": api_key_hash}, limit=1)
        return keys[0] if keys else None
    
    async def update_usage(self, key_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Cập nhật usage statistics"""
        key = await self.get_by_id(key_id)
        if key:
            new_usage_count = key.get("usage_count", 0) + 1
            return await self.update_by_id(key_id, {
                "last_used": get_vietnam_now_naive(),
                "usage_count": new_usage_count
            })
        return None
    
    async def deactivate_key(self, key_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Vô hiệu hóa API key"""
        return await self.update_by_id(key_id, {"is_active": False})


class SessionManager(BaseManager):
    """Manager cho sessions collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "sessions")
    
    async def create_session(self, user_id: str, token_hash: str, device_info: Dict[str, Any],
                           expires_at: datetime) -> Dict[str, Any]:
        """
        Tạo session mới
        
        Args:
            user_id: ID user
            token_hash: Hash của session token
            device_info: Thông tin device {browser, os, ip}
            expires_at: Thời gian hết hạn
        """
        session_data = {
            "user_id": user_id,
            "token_hash": token_hash,
            "device_info": device_info,
            "is_active": True,
            "last_activity": get_vietnam_now_naive(),
            "expires_at": expires_at
        }
        return await self.create(session_data)
    
    async def get_by_token_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Lấy session theo token hash"""
        sessions = await self.get_all(filter_query={"token_hash": token_hash}, limit=1)
        return sessions[0] if sessions else None
    
    async def get_active_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy các session đang active"""
        return await self.get_all(
            filter_query={"user_id": user_id, "is_active": True},
            sort_by="last_activity",
            sort_order=-1
        )
    
    async def update_activity(self, session_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Cập nhật last activity"""
        return await self.update_by_id(session_id, {"last_activity": get_vietnam_now_naive()})
    
    async def deactivate_session(self, session_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Vô hiệu hóa session"""
        return await self.update_by_id(session_id, {"is_active": False})
    
    async def cleanup_expired_sessions(self) -> int:
        """Xóa các sessions đã hết hạn"""
        current_time = get_vietnam_now_naive()
        return await self.bulk_delete([{"expires_at": {"$lt": current_time}}])


class AuditLogManager(BaseManager):
    """Manager cho audit_logs collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "audit_logs")
    
    async def create_audit_log(self, user_id: str, action: str, resource_type: str,
                             resource_id: str = None, old_data: Dict[str, Any] = None,
                             new_data: Dict[str, Any] = None, ip_address: str = None,
                             user_agent: str = None) -> Dict[str, Any]:
        """
        Tạo audit log mới
        
        Args:
            user_id: ID user thực hiện action
            action: login, logout, create_bot, update_order, etc.
            resource_type: bot, order, contact, etc.
            resource_id: ID của resource
            old_data: Dữ liệu trước thay đổi
            new_data: Dữ liệu sau thay đổi
            ip_address: Địa chỉ IP
            user_agent: User agent
        """
        log_data = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "old_data": old_data,
            "new_data": new_data,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": get_vietnam_now_naive()
        }
        return await self.create(log_data)
    
    async def get_by_user_id(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Lấy audit logs của user"""
        filter_query = {"user_id": user_id}
        if days:
            start_date = get_vietnam_now_naive() - timedelta(days=days)
            filter_query["timestamp"] = {"$gte": start_date}
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="timestamp",
            sort_order=-1
        )
    
    async def get_by_resource(self, resource_type: str, resource_id: str) -> List[Dict[str, Any]]:
        """Lấy audit logs của resource cụ thể"""
        return await self.get_all(
            filter_query={"resource_type": resource_type, "resource_id": resource_id},
            sort_by="timestamp",
            sort_order=-1
        )


class FileUploadManager(BaseManager):
    """Manager cho file_uploads collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "file_uploads")
    
    async def create_file_upload(self, user_id: str, file_name: str, original_name: str,
                               file_type: str, file_size: int, storage_type: str,
                               storage_url: str, upload_purpose: str,
                               is_processed: bool = False, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo file upload record
        
        Args:
            user_id: ID user
            file_name: Tên file (có thể đã rename)
            original_name: Tên file gốc
            file_type: Loại file
            file_size: Size file (bytes)
            storage_type: local, s3, cloudinary
            storage_url: URL để access file
            upload_purpose: avatar, document, product_image, etc.
            is_processed: Đã xử lý chưa
            metadata: Metadata bổ sung (dimensions, duration, etc.)
        """
        upload_data = {
            "user_id": user_id,
            "file_name": file_name,
            "original_name": original_name,
            "file_type": file_type,
            "file_size": file_size,
            "storage_type": storage_type,
            "storage_url": storage_url,
            "upload_purpose": upload_purpose,
            "is_processed": is_processed,
            "metadata": metadata or {}
        }
        return await self.create(upload_data)
    
    async def get_by_user_id(self, user_id: str, upload_purpose: str = None) -> List[Dict[str, Any]]:
        """Lấy files của user"""
        filter_query = {"user_id": user_id}
        if upload_purpose:
            filter_query["upload_purpose"] = upload_purpose
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def mark_as_processed(self, upload_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Đánh dấu file đã được xử lý"""
        return await self.update_by_id(upload_id, {"is_processed": True})


class SupportTicketManager(BaseManager):
    """Manager cho support_tickets collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "support_tickets")
    
    async def create_ticket(self, user_id: str, subject: str, description: str,
                          priority: str = "medium", category: str = "technical",
                          attachments: List[str] = None) -> Dict[str, Any]:
        """
        Tạo support ticket mới
        
        Args:
            user_id: ID user
            subject: Tiêu đề ticket
            description: Mô tả chi tiết
            priority: low, medium, high, urgent
            category: technical, billing, feature_request
            attachments: List upload IDs
        """
        ticket_data = {
            "user_id": user_id,
            "subject": subject,
            "description": description,
            "priority": priority,
            "status": "open",
            "category": category,
            "assigned_to": None,
            "attachments": attachments or []
        }
        return await self.create(ticket_data)
    
    async def get_by_user_id(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Lấy tickets của user"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def update_status(self, ticket_id: Union[str, ObjectId], new_status: str,
                          assigned_to: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật status ticket"""
        update_data = {"status": new_status}
        if assigned_to:
            update_data["assigned_to"] = assigned_to
        
        return await self.update_by_id(ticket_id, update_data)


class FAQManager(BaseManager):
    """Manager cho faqs collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "faqs")
    
    async def create_faq(self, question: str, answer: str, category: str = None,
                       language: str = "vi", is_public: bool = True) -> Dict[str, Any]:
        """Tạo FAQ mới"""
        faq_data = {
            "question": question,
            "answer": answer,
            "category": category,
            "language": language,
            "is_public": is_public,
            "view_count": 0,
            "helpful_count": 0
        }
        return await self.create(faq_data)
    
    async def get_public_faqs(self, category: str = None, language: str = "vi") -> List[Dict[str, Any]]:
        """Lấy FAQs public"""
        filter_query = {"is_public": True, "language": language}
        if category:
            filter_query["category"] = category
        
        return await self.get_all(filter_query=filter_query)
    
    async def increment_view_count(self, faq_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Tăng view count"""
        faq = await self.get_by_id(faq_id)
        if faq:
            new_count = faq.get("view_count", 0) + 1
            return await self.update_by_id(faq_id, {"view_count": new_count})
        return None
    
    async def increment_helpful_count(self, faq_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Tăng helpful count"""
        faq = await self.get_by_id(faq_id)
        if faq:
            new_count = faq.get("helpful_count", 0) + 1
            return await self.update_by_id(faq_id, {"helpful_count": new_count})
        return None


class FeatureRequestManager(BaseManager):
    """Manager cho feature_requests collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "feature_requests")
    
    async def create_feature_request(self, user_id: str, title: str, description: str,
                                   category: str = None, priority: str = "medium") -> Dict[str, Any]:
        """Tạo feature request mới"""
        request_data = {
            "user_id": user_id,
            "title": title,
            "description": description,
            "category": category,
            "priority": priority,
            "status": "submitted",
            "votes_count": 0
        }
        return await self.create(request_data)
    
    async def get_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Lấy feature requests theo status"""
        return await self.get_all(
            filter_query={"status": status},
            sort_by="votes_count",
            sort_order=-1
        )
    
    async def vote_for_request(self, request_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Vote cho feature request"""
        request = await self.get_by_id(request_id)
        if request:
            new_votes = request.get("votes_count", 0) + 1
            return await self.update_by_id(request_id, {"votes_count": new_votes})
        return None


class HelpDocumentManager(BaseManager):
    """Manager cho help_documents collection - tài liệu hướng dẫn"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "help_documents")
    
    async def create_document(self, title: str, content: str = None, doc_type: str = "guide",
                            category: str = None, url: str = None, language: str = "vi",
                            is_public: bool = True, tags: List[str] = None) -> Dict[str, Any]:
        """
        Tạo tài liệu hướng dẫn mới
        
        Args:
            title: Tiêu đề tài liệu
            content: Nội dung (cho loại text)
            doc_type: Loại - guide, video, faq, tutorial, api_doc
            category: Phân loại - getting_started, advanced, troubleshooting, api
            url: Link tài liệu (cho loại video hoặc external)
            language: Ngôn ngữ
            is_public: Công khai hay không
            tags: Tags để tìm kiếm
        """
        doc_data = {
            "title": title,
            "content": content,
            "doc_type": doc_type,
            "category": category,
            "url": url,
            "language": language,
            "is_public": is_public,
            "tags": tags or [],
            "view_count": 0,
            "helpful_count": 0,
            "order_index": 0
        }
        return await self.create(doc_data)
    
    async def get_public_documents(self, category: str = None, doc_type: str = None,
                                 language: str = "vi") -> List[Dict[str, Any]]:
        """Lấy tài liệu công khai"""
        filter_query = {"is_public": True, "language": language}
        if category:
            filter_query["category"] = category
        if doc_type:
            filter_query["doc_type"] = doc_type
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="order_index",
            sort_order=1
        )
    
    async def search_documents(self, query: str, language: str = "vi") -> List[Dict[str, Any]]:
        """Tìm kiếm tài liệu"""
        filter_query = {
            "is_public": True,
            "language": language,
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"content": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [query]}}
            ]
        }
        return await self.get_all(filter_query=filter_query)
    
    async def increment_view_count(self, doc_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Tăng view count"""
        doc = await self.get_by_id(doc_id)
        if doc:
            new_count = doc.get("view_count", 0) + 1
            return await self.update_by_id(doc_id, {"view_count": new_count})
        return None


class FeedbackManager(BaseManager):
    """Manager cho feedback collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "feedback")
    
    async def create_feedback(self, user_id: str = None, name: str = None, email: str = None,
                            feedback_type: str = "general", subject: str = None,
                            message: str = "", rating: int = None, 
                            metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo feedback mới
        
        Args:
            user_id: ID user (nếu đã đăng nhập)
            name: Tên (nếu guest)
            email: Email (nếu guest)  
            feedback_type: Loại - general, bug_report, feature_request, complaint, compliment
            subject: Tiêu đề
            message: Nội dung feedback
            rating: Đánh giá 1-5 sao
            metadata: Thông tin bổ sung (page_url, user_agent, etc.)
        """
        feedback_data = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "feedback_type": feedback_type,
            "subject": subject,
            "message": message,
            "rating": rating,
            "metadata": metadata or {},
            "status": "new",  # new, reviewed, resolved
            "admin_response": None
        }
        return await self.create(feedback_data)
    
    async def get_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy feedback của user"""
        return await self.get_all(
            filter_query={"user_id": user_id},
            sort_by="create_at",
            sort_order=-1
        )
    
    async def get_by_status(self, status: str = "new") -> List[Dict[str, Any]]:
        """Lấy feedback theo status"""
        return await self.get_all(
            filter_query={"status": status},
            sort_by="create_at",
            sort_order=-1
        )
    
    async def update_status(self, feedback_id: Union[str, ObjectId], status: str,
                          admin_response: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật status feedback"""
        update_data = {"status": status}
        if admin_response:
            update_data["admin_response"] = admin_response
        
        return await self.update_by_id(feedback_id, update_data)


class LiveChatManager(BaseManager):
    """Manager cho live_chat_sessions collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "live_chat_sessions")
    
    async def create_chat_session(self, user_id: str = None, name: str = None, 
                                email: str = None, chat_type: str = "bot",
                                initial_message: str = None) -> Dict[str, Any]:
        """
        Tạo session chat mới
        
        Args:
            user_id: ID user (nếu đã đăng nhập)
            name: Tên (nếu guest)
            email: Email (nếu guest)
            chat_type: Loại chat - bot, human
            initial_message: Tin nhắn đầu tiên
        """
        session_data = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "chat_type": chat_type,
            "status": "active",  # active, waiting, closed
            "agent_id": None,  # ID của agent phụ trách (nếu human)
            "messages": [],
            "metadata": {
                "initial_message": initial_message,
                "created_at": get_vietnam_now_naive()
            }
        }
        return await self.create(session_data)
    
    async def add_message(self, session_id: Union[str, ObjectId], sender_type: str,
                        message: str, sender_id: str = None, sender_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Thêm tin nhắn vào session
        
        Args:
            session_id: ID session
            sender_type: user, bot, agent
            message: Nội dung tin nhắn
            sender_id: ID người gửi
            sender_name: Tên người gửi
        """
        session = await self.get_by_id(session_id)
        if not session:
            return None
        
        new_message = {
            "sender_type": sender_type,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "message": message,
            "timestamp": get_vietnam_now_naive()
        }
        
        messages = session.get("messages", [])
        messages.append(new_message)
        
        return await self.update_by_id(session_id, {"messages": messages})
    
    async def get_by_user_id(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Lấy chat sessions của user"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def update_status(self, session_id: Union[str, ObjectId], status: str,
                          agent_id: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật status session"""
        update_data = {"status": status}
        if agent_id:
            update_data["agent_id"] = agent_id
        
        return await self.update_by_id(session_id, update_data)
    
    async def get_waiting_for_human(self) -> List[Dict[str, Any]]:
        """Lấy các session đang chờ agent"""
        return await self.get_all(
            filter_query={"chat_type": "human", "status": "waiting"},
            sort_by="create_at",
            sort_order=1
        )


# Factory class
class SystemManagementFactory:
    """Factory để tạo tất cả System Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._notification_manager = None
        self._user_settings_manager = None
        self._api_key_manager = None
        self._session_manager = None
        self._audit_log_manager = None
        self._file_upload_manager = None
        self._support_ticket_manager = None
        self._faq_manager = None
        self._feature_request_manager = None
        self._help_document_manager = None
        self._feedback_manager = None
        self._live_chat_manager = None
    
    @property
    def notification_manager(self) -> NotificationManager:
        if self._notification_manager is None:
            self._notification_manager = NotificationManager(self.db_manager)
        return self._notification_manager
    
    @property
    def user_settings_manager(self) -> UserSettingsManager:
        if self._user_settings_manager is None:
            self._user_settings_manager = UserSettingsManager(self.db_manager)
        return self._user_settings_manager
    
    @property
    def api_key_manager(self) -> ApiKeyManager:
        if self._api_key_manager is None:
            self._api_key_manager = ApiKeyManager(self.db_manager)
        return self._api_key_manager
    
    @property
    def session_manager(self) -> SessionManager:
        if self._session_manager is None:
            self._session_manager = SessionManager(self.db_manager)
        return self._session_manager
    
    @property
    def audit_log_manager(self) -> AuditLogManager:
        if self._audit_log_manager is None:
            self._audit_log_manager = AuditLogManager(self.db_manager)
        return self._audit_log_manager
    
    @property
    def file_upload_manager(self) -> FileUploadManager:
        if self._file_upload_manager is None:
            self._file_upload_manager = FileUploadManager(self.db_manager)
        return self._file_upload_manager
    
    @property
    def support_ticket_manager(self) -> SupportTicketManager:
        if self._support_ticket_manager is None:
            self._support_ticket_manager = SupportTicketManager(self.db_manager)
        return self._support_ticket_manager
    
    @property
    def faq_manager(self) -> FAQManager:
        if self._faq_manager is None:
            self._faq_manager = FAQManager(self.db_manager)
        return self._faq_manager
    
    @property
    def feature_request_manager(self) -> FeatureRequestManager:
        if self._feature_request_manager is None:
            self._feature_request_manager = FeatureRequestManager(self.db_manager)
        return self._feature_request_manager
    
    @property
    def help_document_manager(self) -> HelpDocumentManager:
        if self._help_document_manager is None:
            self._help_document_manager = HelpDocumentManager(self.db_manager)
        return self._help_document_manager
    
    @property
    def feedback_manager(self) -> FeedbackManager:
        if self._feedback_manager is None:
            self._feedback_manager = FeedbackManager(self.db_manager)
        return self._feedback_manager
    
    @property
    def live_chat_manager(self) -> LiveChatManager:
        if self._live_chat_manager is None:
            self._live_chat_manager = LiveChatManager(self.db_manager)
        return self._live_chat_manager
