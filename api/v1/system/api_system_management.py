"""
System Management API Endpoints
Cung cấp API cho notifications, settings, api_keys, sessions, audit_logs, và các chức năng system admin
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.auth.auth_middleware import get_current_user
from controllers.ultils.email_service import EmailService
from controllers.ultils.bot_chat_service import BotChatService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System Management"])

# Pydantic Models
class NotificationCreate(BaseModel):
    """Model để tạo notification mới"""
    title: str
    content: str
    type: str = "info"  # info, success, warning, error, alert
    category: str = "system"  # system, auth, bot, social, conversation, business, customer, order, crm, knowledge, history, etc.
    action: Optional[str] = None  # login, created, updated, deleted, connected, etc.
    priority: int = 1  # 1-5, 5 is highest
    metadata: Optional[Dict[str, Any]] = {}
    link: Optional[Dict[str, str]] = None  # {"type": "page", "url": "/...", "resource_id": "..."}
    expires_at: Optional[datetime] = None

class NotificationQuickCreate(BaseModel):
    """Model để tạo notification nhanh với ít tham số"""
    title: str
    content: str
    type: str = "info"
    category: str = "system"

class NotificationFilter(BaseModel):
    """Model để filter notifications"""
    is_read: Optional[bool] = None
    category: Optional[str] = None
    type: Optional[str] = None
    action: Optional[str] = None
    priority: Optional[int] = None

class SettingUpdate(BaseModel):
    value: Any
    description: Optional[str] = None

class APIKeyCreate(BaseModel):
    user_id: str
    name: str
    permissions: List[str] = []
    expires_at: Optional[datetime] = None

class SessionUpdate(BaseModel):
    data: Dict[str, Any]

class AuditLogQuery(BaseModel):
    user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

# Email Settings Models
class EmailSettingsUpdate(BaseModel):
    """Model để cập nhật cài đặt email"""
    email: Optional[EmailStr] = None
    enable_email_notifications: Optional[bool] = None
    new_order_notifications: Optional[bool] = None
    new_customer_notifications: Optional[bool] = None
    new_message_notifications: Optional[bool] = None
    system_notifications: Optional[bool] = None
    marketing_notifications: Optional[bool] = None

# Help & Support Models
class HelpDocumentCreate(BaseModel):
    """Model để tạo tài liệu hướng dẫn"""
    title: str
    content: Optional[str] = None
    doc_type: str = "guide"  # guide, video, faq, tutorial, api_doc
    category: Optional[str] = None  # getting_started, advanced, troubleshooting, api
    url: Optional[str] = None  # Link cho video hoặc external docs
    language: str = "vi"
    is_public: bool = True
    tags: Optional[List[str]] = []

class FeedbackCreate(BaseModel):
    """Model để tạo feedback"""
    name: Optional[str] = None  # Nếu guest
    email: Optional[EmailStr] = None  # Nếu guest
    feedback_type: str = "general"  # general, bug_report, feature_request, complaint, compliment
    subject: Optional[str] = None
    message: str
    rating: Optional[int] = None  # 1-5 stars
    metadata: Optional[Dict[str, Any]] = {}

# Live Chat Models
class LiveChatSessionCreate(BaseModel):
    """Model để tạo session chat"""
    name: Optional[str] = None  # Nếu guest
    email: Optional[EmailStr] = None  # Nếu guest
    chat_type: str = "bot"  # bot, human
    initial_message: Optional[str] = None

class ChatMessageSend(BaseModel):
    """Model để gửi tin nhắn chat"""
    message: str
    session_id: str

# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()

# Notification Endpoints
# @router.post("/notifications", response_model=Dict[str, Any])
# async def create_notification(
#     notification_data: NotificationCreate,
#     current_user: dict = Depends(get_current_user),
#     factory = Depends(get_management_factory)
# ):
#     """
#     Tạo notification mới cho user hiện tại
    
#     Parameters:
#     - **title** (required): Tiêu đề notification (VD: "Kết nối Facebook thành công")
#     - **content** (required): Nội dung chi tiết (VD: "Bạn đã kết nối với tài khoản Facebook: John Doe")
#     - **type**: Loại notification - info/success/warning/error/alert (default: "info")
#     - **category**: Phân loại - system, auth, bot, social, conversation, business, customer, order, crm, knowledge, history, etc. (default: "system")
#     - **action**: Hành động tạo notification (VD: "connected", "created", "updated", "deleted")
#     - **priority**: Độ ưu tiên 1-5, 5 là cao nhất (default: 1)
#     - **metadata**: Dữ liệu bổ sung dạng JSON object (VD: {"platform": "facebook", "page_id": "123"})
#     - **link**: Link reference để navigate {"type": "page", "url": "/path", "resource_id": "id"}
#     - **expires_at**: Thời gian hết hạn notification (ISO datetime format)
    
#     Example Request:
#     ```json
#     {
#         "title": "Facebook Page mới",
#         "content": "Page 'My Shop' đã được thêm vào",
#         "type": "success",
#         "category": "social",
#         "action": "page_added",
#         "priority": 3,
#         "metadata": {"platform": "facebook", "page_name": "My Shop"},
#         "link": {"type": "facebook_page", "url": "/socials/facebook/pages/123", "resource_id": "123"}
#     }
#     ```
#     """
#     try:
#         user_id = current_user.get("user_id")
#         notification = await factory.notification_manager.create_notification(
#             user_id=user_id,
#             title=notification_data.title,
#             content=notification_data.content,
#             notification_type=notification_data.type,
#             category=notification_data.category,
#             action=notification_data.action,
#             priority=notification_data.priority,
#             metadata=notification_data.metadata,
#             link=notification_data.link,
#             expires_at=notification_data.expires_at
#         )
        
#         return {"success": True, "data": notification}
        
#     except Exception as e:
#         logger.error(f"Error creating notification: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/notifications/quick", response_model=Dict[str, Any])
# async def create_quick_notification(
#     notification_data: NotificationQuickCreate,
#     current_user: dict = Depends(get_current_user),
#     factory = Depends(get_management_factory)
# ):
#     """
#     Tạo notification nhanh với ít tham số (phiên bản đơn giản)
    
#     Parameters:
#     - **title** (required): Tiêu đề notification
#     - **content** (required): Nội dung notification
#     - **type**: Loại - info/success/warning/error/alert (default: "info")
#     - **category**: Phân loại - system, auth, bot, social, conversation, business, customer, order, crm, knowledge, history, etc. (default: "system")
    
#     Example Request:
#     ```json
#     {
#         "title": "Thao tác thành công",
#         "content": "Dữ liệu đã được lưu",
#         "type": "success",
#         "category": "system"
#     }
#     ```
#     """
#     try:
#         user_id = current_user.get("user_id")
#         notification = await factory.notification_manager.create_quick_notification(
#             user_id=user_id,
#             title=notification_data.title,
#             content=notification_data.content,
#             notification_type=notification_data.type,
#             category=notification_data.category
#         )
        
#         return {"success": True, "data": notification}
        
#     except Exception as e:
#         logger.error(f"Error creating quick notification: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications", response_model=Dict[str, Any])
async def get_notifications(
    is_read: Optional[bool] = Query(None, description="Lọc theo trạng thái đọc: true=đã đọc, false=chưa đọc, null=tất cả"),
    category: Optional[str] = Query(None, description="Lọc theo category: system, crm, knowledge, auth, conversation, bot, customer, order, history, business, social, etc."),
    type: Optional[str] = Query(None, description="Lọc theo type: info, success, warning, error, alert"),
    action: Optional[str] = Query(None, description="Lọc theo action: connected, created, updated, deleted, etc."),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Lọc theo priority: 1-5 (5 là cao nhất)"),
    skip: int = Query(0, ge=0, description="Số lượng bỏ qua (pagination)"),
    limit: int = Query(50, ge=1, le=100, description="Số lượng tối đa trả về (1-100)"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy danh sách notifications của user với nhiều tùy chọn lọc
    
    Query Parameters:
    - **is_read**: Lọc theo trạng thái (true/false/null)
    - **category**: Lọc theo phân loại
    - **type**: Lọc theo loại notification
    - **action**: Lọc theo hành động
    - **priority**: Lọc theo độ ưu tiên (1-5)
    - **skip**: Bỏ qua n records (dùng cho pagination)
    - **limit**: Giới hạn số lượng trả về (max 100)
    
    Example:
    ```
    GET /notifications?is_read=false&category=social&priority=3&skip=0&limit=20
    ```
    
    Response:
    ```json
    {
        "success": true,
        "data": [...notifications...],
        "pagination": {
            "skip": 0,
            "limit": 20,
            "total": 45
        }
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        notifications = await factory.notification_manager.get_by_user_id(
            user_id=user_id,
            is_read=is_read,
            category=category,
            notification_type=type,
            action=action,
            priority=priority,
            limit=limit,
            skip=skip
        )
        
        # Count total for pagination
        total = await factory.notification_manager.count({
            "user_id": user_id,
            **({"is_read": is_read} if is_read is not None else {}),
            **({"category": category} if category else {}),
            **({"type": type} if type else {}),
            **({"action": action} if action else {}),
            **({"priority": priority} if priority else {})
        })
        
        return {
            "success": True,
            "data": notifications,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting notifications: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/notifications/{notification_id}/read", response_model=Dict[str, Any])
async def mark_notification_read(
    notification_id: str,
    factory = Depends(get_management_factory)
):
    """
    Đánh dấu một notification đã đọc
    
    Path Parameters:
    - **notification_id**: ID của notification cần đánh dấu
    
    Example:
    ```
    PUT /notifications/60d5ec49f1a2c3b4d5e6f789/read
    ```
    """
    try:
        notification = await factory.notification_manager.mark_as_read(notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"success": True, "data": notification}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/notifications/{notification_id}/unread", response_model=Dict[str, Any])
async def mark_notification_unread(
    notification_id: str,
    factory = Depends(get_management_factory)
):
    """
    Đánh dấu một notification chưa đọc (unread)
    
    Path Parameters:
    - **notification_id**: ID của notification cần đánh dấu
    
    Example:
    ```
    PUT /notifications/60d5ec49f1a2c3b4d5e6f789/unread
    ```
    """
    try:
        notification = await factory.notification_manager.mark_as_unread(notification_id)
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"success": True, "data": notification}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification as unread: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/notifications/mark-all-read", response_model=Dict[str, Any])
async def mark_all_notifications_read(
    category: Optional[str] = Query(None, description="Chỉ đánh dấu notifications của category này (VD: 'social', 'bot'). Bỏ trống để đánh dấu tất cả"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Đánh dấu tất cả notifications của user đã đọc
    
    Query Parameters:
    - **category** (optional): Chỉ đánh dấu notifications của category cụ thể. Bỏ trống để đánh dấu tất cả.
    
    Examples:
    ```
    PUT /notifications/mark-all-read              (đánh dấu tất cả)
    PUT /notifications/mark-all-read?category=social  (chỉ social)
    ```
    
    Response:
    ```json
    {
        "success": true,
        "message": "Marked 15 notifications as read",
        "updated_count": 15
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        count = await factory.notification_manager.mark_all_as_read(user_id, category)
        
        return {
            "success": True,
            "message": f"Marked {count} notifications as read",
            "updated_count": count
        }
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/unread-count", response_model=Dict[str, Any])
async def get_unread_count(
    category: Optional[str] = Query(None, description="Đếm unread cho category cụ thể (VD: 'social', 'conversation'). Bỏ trống để đếm tất cả"),
    priority: Optional[int] = Query(None, ge=1, le=5, description="Chỉ đếm notifications có priority >= giá trị này (VD: priority=3 sẽ đếm priority 3,4,5)"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Đếm số lượng notifications chưa đọc
    
    Query Parameters:
    - **category** (optional): Đếm cho category cụ thể
    - **priority** (optional): Chỉ đếm notifications có priority >= giá trị này
    
    Examples:
    ```
    GET /notifications/unread-count                    (đếm tất cả)
    GET /notifications/unread-count?category=social    (chỉ social)
    GET /notifications/unread-count?priority=4         (priority >= 4)
    ```
    
    Response:
    ```json
    {
        "success": true,
        "unread_count": 12
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        count = await factory.notification_manager.get_unread_count(
            user_id=user_id,
            category=category,
            priority=priority
        )
        return {"success": True, "unread_count": count}
        
    except Exception as e:
        logger.error(f"Error getting unread count: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notifications/unread-count-by-category", response_model=Dict[str, Any])
async def get_unread_count_by_category(
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Đếm số lượng notifications chưa đọc theo từng category
    
    Không cần parameters. Trả về số lượng unread cho tất cả categories.
    
    Example:
    ```
    GET /notifications/unread-count-by-category
    ```
    
    Response:
    ```json
    {
        "success": true,
        "data": {
            "system": 5,
            "social": 3,
            "conversation": 12,
            "bot": 2,
            "crm": 1
        },
        "total": 23
    }
    ```
    
    Hữu ích để hiển thị badge count cho từng tab/section trong UI.
    """
    try:
        user_id = current_user.get("user_id")
        counts = await factory.notification_manager.get_unread_count_by_category(user_id)
        
        return {
            "success": True,
            "data": counts,
            "total": sum(counts.values())
        }
        
    except Exception as e:
        logger.error(f"Error getting unread count by category: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/notifications/{notification_id}", response_model=Dict[str, Any])
async def delete_notification(
    notification_id: str,
    factory = Depends(get_management_factory)
):
    """
    Xóa một notification khỏi hệ thống
    
    Path Parameters:
    - **notification_id**: ID của notification cần xóa
    
    Example:
    ```
    DELETE /notifications/60d5ec49f1a2c3b4d5e6f789
    ```
    
    Response:
    ```json
    {
        "success": true,
        "message": "Notification deleted successfully"
    }
    ```
    """
    try:
        success = await factory.notification_manager.delete_by_id(notification_id)
        if not success:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"success": True, "message": "Notification deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Settings Endpoints
@router.get("/settings", response_model=Dict[str, Any])
async def get_settings(
    scope: str = Query("user", description="Scope của settings: 'user' (cài đặt cá nhân) hoặc 'global' (cài đặt toàn hệ thống)"),
    category: Optional[str] = Query(None, description="Lọc theo category: notification, privacy, api, integration, etc. Bỏ trống để lấy tất cả"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy settings của user hoặc global settings
    
    Query Parameters:
    - **scope**: 'user' (cài đặt của user hiện tại) hoặc 'global' (cài đặt hệ thống)
    - **category** (optional): Lọc theo category
    
    Examples:
    ```
    GET /settings?scope=user                          (tất cả settings của user)
    GET /settings?scope=user&category=notification    (chỉ notification settings)
    GET /settings?scope=global                        (global settings)
    ```
    
    Response:
    ```json
    {
        "success": true,
        "data": [
            {
                "_id": "...",
                "category": "notification",
                "setting_key": "email_notifications",
                "setting_value": true
            }
        ]
    }
    ```
    """
    try:
        if scope == "user":
            user_id = current_user.get("user_id")
            settings = await factory.user_settings_manager.get_user_settings(user_id, category)
        else:
            # For global settings, we'll implement later or use user_settings with admin scope
            settings = []
        
        return {"success": True, "data": settings}
        
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/settings/{setting_key}", response_model=Dict[str, Any])
async def update_setting(
    setting_key: str,
    setting_data: SettingUpdate,
    scope: str = Query("user", description="Scope của settings: 'user' (cài đặt cá nhân) hoặc 'global' (cài đặt toàn hệ thống)"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Cập nhật hoặc tạo mới một setting
    
    Path Parameters:
    - **setting_key**: Key của setting (VD: "email_notifications", "push_notifications")
    
    Query Parameters:
    - **scope**: 'user' hoặc 'global'
    
    Request Body:
    - **value** (required): Giá trị mới của setting (có thể là string, number, boolean, object, array)
    - **description** (optional): Mô tả về setting
    
    Example:
    ```
    PUT /settings/email_notifications?scope=user
    
    Body:
    {
        "value": true,
        "description": "Bật thông báo qua email"
    }
    ```
    
    Response:
    ```json
    {
        "success": true,
        "data": {
            "_id": "...",
            "setting_key": "email_notifications",
            "setting_value": true,
            "description": "Bật thông báo qua email"
        }
    }
    ```
    """
    try:
        if scope == "user":
            user_id = current_user.get("user_id")
            setting = await factory.user_settings_manager.create_setting(
                user_id, "user", setting_key, setting_data.value
            )
        else:
            # For global settings, we'll implement later or use admin scope
            setting = await factory.user_settings_manager.create_setting(
                "admin", "global", setting_key, setting_data.value
            )
        
        return {"success": True, "data": setting}
        
    except Exception as e:
        logger.error(f"Error updating setting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/settings/{setting_key}", response_model=Dict[str, Any])
async def delete_setting(
    setting_key: str,
    scope: str = Query("user", description="Scope của settings: 'user' (cài đặt cá nhân) hoặc 'global' (cài đặt toàn hệ thống)"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Xóa một setting
    
    Path Parameters:
    - **setting_key**: Key của setting cần xóa
    
    Query Parameters:
    - **scope**: 'user' hoặc 'global'
    
    Example:
    ```
    DELETE /settings/old_setting?scope=user
    ```
    
    Response:
    ```json
    {
        "success": true,
        "message": "Setting deleted successfully"
    }
    ```
    
    Lưu ý: Xóa setting sẽ khôi phục về giá trị mặc định của hệ thống (nếu có).
    """
    try:
        if scope == "user":
            user_id = current_user.get("user_id")
            # Find and delete the setting
            settings = await factory.user_settings_manager.get_user_settings(user_id, "user")
            setting_to_delete = next((s for s in settings if s.get("setting_key") == setting_key), None)
            success = False
            if setting_to_delete:
                success = await factory.user_settings_manager.delete_by_id(setting_to_delete["_id"])
        else:
            # For global settings deletion - implement later
            success = False
        
        if not success:
            raise HTTPException(status_code=404, detail="Setting not found")
        
        return {"success": True, "message": "Setting deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting setting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Email Settings Endpoints
@router.get("/email-settings", response_model=Dict[str, Any])
async def get_email_settings(
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy cài đặt email của user hiện tại
    
    Trả về các cài đặt:
    - **email**: Email để nhận thông báo
    - **enable_email_notifications**: Bật/tắt thông báo email
    - **new_order_notifications**: Thông báo khi có đơn hàng mới
    - **new_customer_notifications**: Thông báo khi có khách hàng mới  
    - **new_message_notifications**: Thông báo khi có tin nhắn mới
    - **system_notifications**: Thông báo hệ thống
    - **marketing_notifications**: Thông báo marketing
    
    Example Response:
    ```json
    {
        "success": true,
        "data": {
            "email": "user@example.com",
            "enable_email_notifications": true,
            "new_order_notifications": true,
            "new_customer_notifications": false,
            "new_message_notifications": true,
            "system_notifications": true,
            "marketing_notifications": false
        }
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Lấy tất cả email settings của user
        email_settings = await factory.user_settings_manager.get_user_settings(
            user_id=user_id, 
            category="email"
        )
        
        # Chuyển đổi sang dict để dễ truy cập
        settings_dict = {}
        for setting in email_settings:
            settings_dict[setting["setting_key"]] = setting["setting_value"]
        
        # Default values nếu chưa có settings
        result = {
            "email": settings_dict.get("email", current_user.get("email", "")),
            "enable_email_notifications": settings_dict.get("enable_email_notifications", False),
            "new_order_notifications": settings_dict.get("new_order_notifications", False),
            "new_customer_notifications": settings_dict.get("new_customer_notifications", False),
            "new_message_notifications": settings_dict.get("new_message_notifications", False),
            "system_notifications": settings_dict.get("system_notifications", True),
            "marketing_notifications": settings_dict.get("marketing_notifications", False)
        }
        
        return {"success": True, "data": result}
        
    except Exception as e:
        logger.error(f"Error getting email settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/email-settings", response_model=Dict[str, Any])
async def update_email_settings(
    settings_data: EmailSettingsUpdate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Cập nhật cài đặt email của user
    
    Request Body:
    - **email** (optional): Email để nhận thông báo
    - **enable_email_notifications** (optional): Bật/tắt thông báo email
    - **new_order_notifications** (optional): Thông báo đơn hàng mới
    - **new_customer_notifications** (optional): Thông báo khách hàng mới
    - **new_message_notifications** (optional): Thông báo tin nhắn mới
    - **system_notifications** (optional): Thông báo hệ thống
    - **marketing_notifications** (optional): Thông báo marketing
    
    Example Request:
    ```json
    {
        "email": "newemail@example.com",
        "enable_email_notifications": true,
        "new_order_notifications": true,
        "new_customer_notifications": true,
        "new_message_notifications": false
    }
    ```
    
    **Lưu ý**: Sau khi cập nhật, hệ thống sẽ tạo notification và gửi email thông báo (nếu đã bật email notifications).
    """
    try:
        user_id = current_user.get("user_id")
        user_name = current_user.get("name", "User")
        updated_settings = {}
        
        # Cập nhật từng setting nếu có trong request
        settings_to_update = settings_data.dict(exclude_unset=True)
        
        for key, value in settings_to_update.items():
            await factory.user_settings_manager.create_setting(
                user_id=user_id,
                category="email",
                setting_key=key,
                setting_value=value
            )
            updated_settings[key] = value
        
        # Tạo notification về việc cập nhật settings
        if updated_settings:
            settings_text = ", ".join([f"{k}: {v}" for k, v in updated_settings.items()])
            
            await factory.notification_manager.create_notification(
                user_id=user_id,
                title="Cài đặt email đã được cập nhật",
                content=f"Các cài đặt email đã được thay đổi: {settings_text}",
                notification_type="success", 
                category="system",
                action="updated",
                priority=2
            )
            
            # Gửi email thông báo nếu user đã bật email notifications
            email_enabled = updated_settings.get("enable_email_notifications")
            if email_enabled is True or (email_enabled is None and 
                await factory.user_settings_manager.get_setting_value(
                    user_id, "email", "enable_email_notifications", False
                )):
                
                user_email = updated_settings.get("email") or current_user.get("email")
                if user_email:
                    background_tasks.add_task(
                        EmailService.send_notification_email,
                        user_email,
                        user_name,
                        "Cài đặt email đã được cập nhật",
                        f"Bạn đã cập nhật thành công các cài đặt email: {settings_text}",
                        "system",
                        "settings_updated"
                    )
        
        return {
            "success": True, 
            "message": "Email settings updated successfully",
            "updated_settings": updated_settings
        }
        
    except Exception as e:
        logger.error(f"Error updating email settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Help & Support Endpoints
@router.get("/help/documents", response_model=Dict[str, Any])
async def get_help_documents(
    category: Optional[str] = Query(None, description="Lọc theo category: getting_started, advanced, troubleshooting, api"),
    doc_type: Optional[str] = Query(None, description="Lọc theo type: guide, video, faq, tutorial, api_doc"),
    language: str = Query("vi", description="Ngôn ngữ tài liệu"),
    factory = Depends(get_management_factory)
):
    """
    Lấy danh sách tài liệu hướng dẫn và hỗ trợ
    
    Query Parameters:
    - **category** (optional): Lọc theo phân loại
    - **doc_type** (optional): Loại tài liệu (guide, video, faq, tutorial, api_doc)
    - **language**: Ngôn ngữ (mặc định "vi")
    
    Examples:
    ```
    GET /help/documents                                    (tất cả tài liệu)
    GET /help/documents?category=getting_started           (tài liệu bắt đầu)
    GET /help/documents?doc_type=video                     (chỉ video)
    GET /help/documents?category=api&doc_type=api_doc      (tài liệu API)
    ```
    
    Response:
    ```json
    {
        "success": true,
        "data": [
            {
                "_id": "...",
                "title": "Hướng dẫn tạo bot",
                "content": "...",
                "doc_type": "guide",
                "category": "getting_started",
                "url": null,
                "view_count": 100,
                "helpful_count": 45
            }
        ]
    }
    ```
    """
    try:
        documents = await factory.help_document_manager.get_public_documents(
            category=category,
            doc_type=doc_type,
            language=language
        )
        
        return {"success": True, "data": documents}
        
    except Exception as e:
        logger.error(f"Error getting help documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/help/documents/search", response_model=Dict[str, Any])
async def search_help_documents(
    q: str = Query(..., description="Từ khóa tìm kiếm"),
    language: str = Query("vi", description="Ngôn ngữ tài liệu"),
    factory = Depends(get_management_factory)
):
    """
    Tìm kiếm tài liệu hướng dẫn
    
    Query Parameters:
    - **q** (required): Từ khóa tìm kiếm
    - **language**: Ngôn ngữ (mặc định "vi")
    
    Example:
    ```
    GET /help/documents/search?q=bot&language=vi
    ```
    
    Tìm kiếm trong title, content và tags của tài liệu.
    """
    try:
        documents = await factory.help_document_manager.search_documents(
            query=q,
            language=language
        )
        
        return {"success": True, "data": documents, "query": q}
        
    except Exception as e:
        logger.error(f"Error searching help documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/help/documents/{doc_id}/view", response_model=Dict[str, Any])
async def increment_document_view(
    doc_id: str,
    factory = Depends(get_management_factory)
):
    """
    Tăng view count cho tài liệu (khi user xem tài liệu)
    
    Path Parameters:
    - **doc_id**: ID của tài liệu
    
    Example:
    ```
    PUT /help/documents/60d5ec49f1a2c3b4d5e6f789/view
    ```
    """
    try:
        document = await factory.help_document_manager.increment_view_count(doc_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"success": True, "data": document}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error incrementing document view: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback", response_model=Dict[str, Any])
async def create_feedback(
    feedback_data: FeedbackCreate,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Gửi feedback cho hệ thống
    
    Request Body:
    - **name** (optional): Tên (nếu guest user)  
    - **email** (optional): Email (nếu guest user)
    - **feedback_type**: Loại feedback - general, bug_report, feature_request, complaint, compliment
    - **subject** (optional): Tiêu đề
    - **message** (required): Nội dung feedback
    - **rating** (optional): Đánh giá 1-5 sao
    - **metadata** (optional): Thông tin bổ sung
    
    Example Request:
    ```json
    {
        "feedback_type": "bug_report",
        "subject": "Lỗi khi tạo bot",
        "message": "Tôi gặp lỗi khi tạo bot mới...",
        "rating": 3,
        "metadata": {
            "page_url": "/bots/create",
            "browser": "Chrome"
        }
    }
    ```
    
    **Lưu ý**: Hệ thống sẽ gửi email thông báo cho admin về feedback mới.
    """
    try:
        # Xác định user info
        user_id = None
        user_name = feedback_data.name
        user_email = feedback_data.email
        
        if current_user:
            user_id = current_user.get("user_id")
            user_name = user_name or current_user.get("name")
            user_email = user_email or current_user.get("email")
        
        # Tạo feedback
        feedback = await factory.feedback_manager.create_feedback(
            user_id=user_id,
            name=user_name,
            email=user_email,
            feedback_type=feedback_data.feedback_type,
            subject=feedback_data.subject,
            message=feedback_data.message,
            rating=feedback_data.rating,
            metadata=feedback_data.metadata
        )
        
        # Tạo notification cho user (nếu đã đăng nhập)
        if user_id:
            await factory.notification_manager.create_notification(
                user_id=user_id,
                title="Feedback đã được gửi",
                content=f"Cảm ơn bạn đã gửi feedback về '{feedback_data.subject or feedback_data.feedback_type}'. Chúng tôi sẽ xem xét và phản hồi sớm nhất có thể.",
                notification_type="success",
                category="system", 
                action="feedback_sent",
                priority=2
            )
        
        # Gửi email thông báo cho admin
        background_tasks.add_task(
            EmailService.send_support_notification_email,
            user_email or "unknown@example.com",
            user_name or "Anonymous User",
            "feedback",
            feedback_data.message,
            user_id
        )
        
        return {
            "success": True, 
            "message": "Feedback submitted successfully",
            "data": feedback
        }
        
    except Exception as e:
        logger.error(f"Error creating feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feedback", response_model=Dict[str, Any])
async def get_my_feedback(
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy danh sách feedback của user hiện tại
    
    Response:
    ```json
    {
        "success": true,
        "data": [
            {
                "_id": "...",
                "feedback_type": "bug_report",
                "subject": "Lỗi khi tạo bot",
                "message": "...",
                "status": "new",
                "admin_response": null,
                "create_at": "..."
            }
        ]
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        feedback_list = await factory.feedback_manager.get_by_user_id(user_id)
        
        return {"success": True, "data": feedback_list}
        
    except Exception as e:
        logger.error(f"Error getting user feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Live Chat Support Endpoints
@router.post("/live-chat/sessions", response_model=Dict[str, Any])
async def create_chat_session(
    session_data: LiveChatSessionCreate,
    background_tasks: BackgroundTasks,
    current_user: Optional[dict] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo session chat hỗ trợ mới
    
    Request Body:
    - **name** (optional): Tên (nếu guest user)
    - **email** (optional): Email (nếu guest user)  
    - **chat_type** (required): "bot" hoặc "human"
    - **initial_message** (optional): Tin nhắn đầu tiên
    
    Example Request:
    ```json
    {
        "chat_type": "bot",
        "initial_message": "Tôi cần hỗ trợ về cách tạo bot"
    }
    ```
    
    **Lưu ý**: 
    - Nếu chọn chat_type="human", hệ thống sẽ tạo notification cho admin và gửi email (nếu user đã cài đặt).
    - Nếu chọn chat_type="bot", hệ thống sẽ tự động phản hồi bằng AI bot.
    """
    try:
        # Xác định user info
        user_id = None
        user_name = session_data.name
        user_email = session_data.email
        
        if current_user:
            user_id = current_user.get("user_id")
            user_name = user_name or current_user.get("name")
            user_email = user_email or current_user.get("email")
        
        # Tạo chat session
        session = await factory.live_chat_manager.create_chat_session(
            user_id=user_id,
            name=user_name,
            email=user_email,
            chat_type=session_data.chat_type,
            initial_message=session_data.initial_message
        )
        
        response_data = {
            "success": True,
            "data": session,
            "bot_response": None
        }
        
        # Xử lý tin nhắn đầu tiên nếu có
        if session_data.initial_message:
            if session_data.chat_type == "bot":
                # Chat với bot - xử lý tin nhắn ngay
                bot_response = await BotChatService.process_bot_message(
                    message=session_data.initial_message,
                    user_id=user_id,
                    session_id=str(session["_id"])
                )
                
                # Lưu tin nhắn user và bot response
                await factory.live_chat_manager.add_message(
                    session["_id"], 
                    "user", 
                    session_data.initial_message,
                    user_id,
                    user_name
                )
                
                await factory.live_chat_manager.add_message(
                    session["_id"],
                    "bot",
                    bot_response["response"],
                    "system",
                    "AI Assistant"
                )
                
                response_data["bot_response"] = bot_response
                
                # Nếu bot suggest chuyển sang human
                if bot_response.get("need_human"):
                    await factory.live_chat_manager.update_status(
                        session["_id"], 
                        "waiting", 
                        None
                    )
                    session_data.chat_type = "human"  # Update để trigger notification
            
            elif session_data.chat_type == "human":
                # Chat với human - lưu tin nhắn và chờ agent
                await factory.live_chat_manager.add_message(
                    session["_id"],
                    "user", 
                    session_data.initial_message,
                    user_id,
                    user_name
                )
                
                await factory.live_chat_manager.update_status(
                    session["_id"],
                    "waiting"
                )
        
        # Nếu yêu cầu chat với human, tạo notification và gửi email
        if session_data.chat_type == "human":
            # Tạo notification cho admin (có thể config admin user_ids)
            # Tạm thời tạo notification chung
            admin_notification = await factory.notification_manager.create_notification(
                user_id="admin",  # TODO: Config admin user ID
                title="Yêu cầu hỗ trợ trực tiếp",
                content=f"Khách hàng {user_name or 'Guest'} yêu cầu chat trực tiếp. Tin nhắn: {session_data.initial_message or 'Không có tin nhắn'}",
                notification_type="alert",
                category="system",
                action="live_chat_request",
                priority=4,
                metadata={
                    "session_id": str(session["_id"]),
                    "user_name": user_name,
                    "user_email": user_email,
                    "user_id": user_id
                }
            )
            
            # Gửi email thông báo cho admin nếu user đã cài đặt email notifications
            if user_id:
                email_enabled = await factory.user_settings_manager.get_setting_value(
                    user_id, "email", "enable_email_notifications", False
                )
                if email_enabled:
                    background_tasks.add_task(
                        EmailService.send_support_notification_email,
                        user_email or "unknown@example.com",
                        user_name or "Guest User",
                        "live_chat",
                        session_data.initial_message or "Yêu cầu chat trực tiếp",
                        user_id
                    )
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error creating chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/live-chat/send-message", response_model=Dict[str, Any])
async def send_chat_message(
    message_data: ChatMessageSend,
    current_user: Optional[dict] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Gửi tin nhắn trong chat session
    
    Request Body:
    - **message** (required): Nội dung tin nhắn
    - **session_id** (required): ID của chat session
    
    Example Request:
    ```json
    {
        "message": "Tôi cần hướng dẫn tạo bot",
        "session_id": "60d5ec49f1a2c3b4d5e6f789"
    }
    ```
    
    **Response**: Trả về tin nhắn đã gửi và phản hồi từ bot (nếu chat với bot).
    """
    try:
        # Lấy thông tin session
        session = await factory.live_chat_manager.get_by_id(message_data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Xác định user info
        user_id = None
        user_name = "Guest"
        
        if current_user:
            user_id = current_user.get("user_id")
            user_name = current_user.get("name")
        elif session.get("name"):
            user_name = session["name"]
        
        # Lưu tin nhắn user
        await factory.live_chat_manager.add_message(
            message_data.session_id,
            "user",
            message_data.message,
            user_id,
            user_name
        )
        
        response_data = {
            "success": True,
            "message": "Message sent successfully",
            "bot_response": None
        }
        
        # Nếu là bot chat, xử lý và trả lời
        if session["chat_type"] == "bot":
            bot_response = await BotChatService.process_bot_message(
                message=message_data.message,
                user_id=user_id,
                session_id=message_data.session_id,
                context=session.get("metadata", {})
            )
            
            # Lưu phản hồi bot
            await factory.live_chat_manager.add_message(
                message_data.session_id,
                "bot",
                bot_response["response"],
                "system",
                "AI Assistant"
            )
            
            response_data["bot_response"] = bot_response
            
            # Nếu bot suggest chuyển sang human
            if bot_response.get("need_human"):
                await factory.live_chat_manager.update_status(
                    message_data.session_id,
                    "waiting"
                )
                response_data["transferred_to_human"] = True
        
        elif session["chat_type"] == "human" and session["status"] == "active":
            # Human chat đang active - tin nhắn sẽ được forward tới agent
            # TODO: Implement real-time notification to agent
            response_data["waiting_for_agent"] = True
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending chat message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/live-chat/sessions", response_model=Dict[str, Any])
async def get_my_chat_sessions(
    status: Optional[str] = Query(None, description="Lọc theo status: active, waiting, closed"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy danh sách chat sessions của user hiện tại
    
    Query Parameters:
    - **status** (optional): Lọc theo trạng thái
    
    Example:
    ```
    GET /live-chat/sessions
    GET /live-chat/sessions?status=active
    ```
    """
    try:
        user_id = current_user.get("user_id")
        sessions = await factory.live_chat_manager.get_by_user_id(user_id, status)
        
        return {"success": True, "data": sessions}
        
    except Exception as e:
        logger.error(f"Error getting chat sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/live-chat/sessions/{session_id}", response_model=Dict[str, Any])
async def get_chat_session_detail(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy chi tiết chat session bao gồm tất cả tin nhắn
    
    Path Parameters:
    - **session_id**: ID của chat session
    
    Example:
    ```
    GET /live-chat/sessions/60d5ec49f1a2c3b4d5e6f789
    ```
    
    Response bao gồm thông tin session và tất cả tin nhắn trong cuộc hội thoại.
    """
    try:
        session = await factory.live_chat_manager.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Kiểm tra quyền truy cập (user chỉ xem được session của mình hoặc admin)
        if current_user:
            user_id = current_user.get("user_id")
            if session.get("user_id") != user_id:
                # TODO: Check if user is admin
                raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": session}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat session detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/live-chat/sessions/{session_id}/close", response_model=Dict[str, Any])
async def close_chat_session(
    session_id: str,
    current_user: Optional[dict] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Đóng chat session
    
    Path Parameters:
    - **session_id**: ID của chat session cần đóng
    
    Example:
    ```
    PUT /live-chat/sessions/60d5ec49f1a2c3b4d5e6f789/close
    ```
    """
    try:
        session = await factory.live_chat_manager.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Kiểm tra quyền (user chỉ đóng được session của mình)
        if current_user:
            user_id = current_user.get("user_id")
            if session.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Cập nhật status
        updated_session = await factory.live_chat_manager.update_status(session_id, "closed")
        
        return {
            "success": True,
            "message": "Chat session closed successfully",
            "data": updated_session
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Utility endpoint to get bot suggestions
@router.get("/live-chat/bot-suggestions", response_model=Dict[str, Any])
async def get_bot_suggestions():
    """
    Lấy các câu hỏi gợi ý để chat với bot
    
    **Public endpoint** - không cần authentication
    
    Response:
    ```json
    {
        "success": true,
        "suggestions": [
            "Làm thế nào để bắt đầu?",
            "Bảng giá dịch vụ như thế nào?",
            "Tôi gặp vấn đề kỹ thuật",
            "Hướng dẫn sử dụng tính năng",
            "Nói chuyện với nhân viên hỗ trợ"
        ]
    }
    ```
    
    Sử dụng để hiển thị quick replies trong chat interface.
    """
    try:
        suggestions = await BotChatService.get_suggested_responses()
        
        return {
            "success": True,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Error getting bot suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
# Admin Endpoints for Help Documents (requires admin role)
@router.post("/admin/help/documents", response_model=Dict[str, Any])
async def create_help_document(
    doc_data: HelpDocumentCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    [ADMIN] Tạo tài liệu hướng dẫn mới
    
    **Chỉ dành cho admin/staff**
    
    Request Body:
    - **title** (required): Tiêu đề tài liệu
    - **content** (optional): Nội dung (cho loại guide/tutorial)
    - **doc_type**: Loại tài liệu - guide, video, faq, tutorial, api_doc
    - **category** (optional): Phân loại - getting_started, advanced, troubleshooting, api
    - **url** (optional): Link cho video hoặc external docs
    - **language**: Ngôn ngữ (mặc định "vi")
    - **is_public**: Công khai hay không (mặc định true)
    - **tags**: Tags để tìm kiếm
    
    Example Request:
    ```json
    {
        "title": "Hướng dẫn tạo bot Facebook",
        "content": "Chi tiết các bước tạo bot...",
        "doc_type": "guide", 
        "category": "getting_started",
        "tags": ["bot", "facebook", "messenger"]
    }
    ```
    
    **Hoặc cho video tutorial:**
    ```json
    {
        "title": "Video: Cách kết nối Facebook Page",
        "doc_type": "video",
        "category": "getting_started", 
        "url": "https://youtube.com/watch?v=...",
        "tags": ["video", "facebook", "page"]
    }
    ```
    """
    try:
        # TODO: Check if user is admin/staff
        # For now, assume all authenticated users can create docs
        
        document = await factory.help_document_manager.create_document(
            title=doc_data.title,
            content=doc_data.content,
            doc_type=doc_data.doc_type,
            category=doc_data.category,
            url=doc_data.url,
            language=doc_data.language,
            is_public=doc_data.is_public,
            tags=doc_data.tags
        )
        
        return {
            "success": True,
            "message": "Help document created successfully",
            "data": document
        }
        
    except Exception as e:
        logger.error(f"Error creating help document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))