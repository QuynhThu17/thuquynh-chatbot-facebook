# Hệ Thống Notification - Hướng Dẫn Sử Dụng

## Tổng Quan

Hệ thống notification được thiết kế để gửi thông báo cho users về tất cả các hoạt động quan trọng trong ứng dụng. Hệ thống hỗ trợ:

- ✅ Nhiều loại notification (info, success, warning, error, alert)
- ✅ Phân loại theo category (system, auth, bot, social, conversation, business, crm, knowledge, payment, etc.)
- ✅ Độ ưu tiên (1-5, 5 là cao nhất)
- ✅ Link reference để navigate tới resource liên quan
- ✅ Metadata bổ sung
- ✅ Expiration time
- ✅ Filter và search mạnh mẽ

## Notification Categories

```python
class NotificationCategory(str, Enum):
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
```

## Notification Types

```python
class NotificationType(str, Enum):
    INFO = "info"        # Thông tin
    SUCCESS = "success"  # Thành công
    WARNING = "warning"  # Cảnh báo
    ERROR = "error"      # Lỗi
    ALERT = "alert"      # Cảnh báo quan trọng
```

## Cách Sử Dụng

### 1. Sử Dụng NotificationHelper (Khuyến Nghị)

NotificationHelper cung cấp các hàm tiện ích để tạo notifications dễ dàng.

#### Import

```python
from controllers.ultils.notification_helper import NotificationHelper, notify, notify_with_link
```

#### Tạo notification đơn giản

```python
# Cách 1: Sử dụng class
await NotificationHelper.notify(
    user_id="user123",
    title="Thành công",
    content="Bạn đã kết nối Facebook thành công",
    notification_type=NotificationType.SUCCESS,
    category=NotificationCategory.SOCIAL
)

# Cách 2: Sử dụng shorthand function
await notify(
    user_id="user123",
    title="Thành công",
    content="Bạn đã kết nối Facebook thành công"
)
```

#### Tạo notification với link

```python
await notify_with_link(
    user_id="user123",
    title="Facebook Page mới",
    content="Page 'My Shop' đã được thêm vào",
    link_type="facebook_page",
    link_url="/socials/facebook/pages/123456",
    resource_id="123456",
    notification_type=NotificationType.SUCCESS,
    category=NotificationCategory.SOCIAL
)
```

### 2. Sử Dụng Pre-built Functions

NotificationHelper cung cấp nhiều hàm đã được tạo sẵn cho các use cases phổ biến:

#### Social Media Notifications

```python
# Kết nối social platform
await NotificationHelper.notify_social_connected(
    user_id="user123",
    platform="Facebook",
    account_name="John Doe",
    account_id="fb_acc_123"
)

# Ngắt kết nối
await NotificationHelper.notify_social_disconnected(
    user_id="user123",
    platform="Facebook",
    account_name="John Doe"
)

# Thêm page
await NotificationHelper.notify_page_added(
    user_id="user123",
    platform="Facebook",
    page_name="My Shop",
    page_id="fb_page_456"
)
```

#### Bot Notifications

```python
# Bot được tạo
await NotificationHelper.notify_bot_created(
    user_id="user123",
    bot_name="Customer Support Bot",
    bot_id="bot_789"
)

# Bot được cập nhật
await NotificationHelper.notify_bot_updated(
    user_id="user123",
    bot_name="Customer Support Bot",
    bot_id="bot_789",
    changes="Đã cập nhật prompt và tăng temperature lên 0.8"
)
```

#### Message/Conversation Notifications

```python
# Tin nhắn mới
await NotificationHelper.notify_new_message(
    user_id="user123",
    sender_name="Nguyễn Văn A",
    message_preview="Chào bạn, tôi muốn hỏi về sản phẩm...",
    conversation_id="conv_456",
    platform="messenger"
)

# Gửi tin nhắn thất bại
await NotificationHelper.notify_message_failed(
    user_id="user123",
    recipient_name="Nguyễn Văn A",
    error_message="Page access token expired",
    conversation_id="conv_456"
)
```

#### CRM Notifications

```python
# Lead mới
await NotificationHelper.notify_lead_created(
    user_id="user123",
    lead_name="Potential Customer",
    lead_id="lead_789",
    source="Facebook Messenger"
)
```

#### Knowledge Notifications

```python
# Document được tải lên
await NotificationHelper.notify_document_uploaded(
    user_id="user123",
    document_name="product_catalog.pdf",
    document_id="doc_123",
    file_size=2048576
)

# Document được xử lý
await NotificationHelper.notify_document_processed(
    user_id="user123",
    document_name="product_catalog.pdf",
    document_id="doc_123",
    chunks_count=45
)
```

#### System Notifications

```python
# Thông báo cho nhiều users
await NotificationHelper.notify_system_update(
    user_ids=["user1", "user2", "user3"],
    title="Cập nhật hệ thống",
    content="Hệ thống đã được cập nhật phiên bản mới với nhiều tính năng",
    priority=3
)

# Thông báo bảo trì
from datetime import datetime, timedelta
await NotificationHelper.notify_maintenance(
    user_ids=["user1", "user2", "user3"],
    start_time=datetime(2025, 10, 3, 2, 0),  # 2:00 AM ngày 3/10/2025
    duration_minutes=30
)
```

#### Auth Notifications

```python
# Đăng nhập mới
await NotificationHelper.notify_login(
    user_id="user123",
    ip_address="192.168.1.1",
    device="Chrome on Windows",
    location="Ho Chi Minh City, Vietnam"
)

# Reset password
await NotificationHelper.notify_password_reset(
    user_id="user123"
)
```

#### Payment Notifications

```python
# Thanh toán thành công
await NotificationHelper.notify_payment_success(
    user_id="user123",
    amount=199000,
    currency="VND",
    transaction_id="txn_456"
)

# Thanh toán thất bại
await NotificationHelper.notify_payment_failed(
    user_id="user123",
    amount=199000,
    currency="VND",
    reason="Insufficient balance"
)
```

### 3. Sử Dụng NotificationManager Trực Tiếp

Nếu bạn cần control chi tiết hơn:

```python
from controllers.data.managements import get_mongodb_factory

factory = get_mongodb_factory()

# Tạo notification
notification = await factory.notification_manager.create_notification(
    user_id="user123",
    title="Custom Notification",
    content="This is a custom notification",
    notification_type=NotificationType.INFO,
    category=NotificationCategory.SYSTEM,
    action=NotificationAction.CREATED,
    priority=3,
    metadata={
        "custom_field": "custom_value",
        "another_field": 123
    },
    link={
        "type": "custom_page",
        "url": "/custom/page",
        "resource_id": "resource_123"
    },
    expires_at=get_vietnam_now_naive() + timedelta(days=7)
)
```

## API Endpoints

### 1. Tạo Notification

```http
POST /api/v1/system/notifications
Authorization: Bearer <token>

{
    "title": "Notification Title",
    "content": "Notification content here",
    "type": "success",
    "category": "social",
    "action": "connected",
    "priority": 3,
    "metadata": {
        "platform": "facebook"
    },
    "link": {
        "type": "social_page",
        "url": "/socials/facebook/pages/123",
        "resource_id": "123"
    }
}
```

### 2. Tạo Notification Nhanh

```http
POST /api/v1/system/notifications/quick
Authorization: Bearer <token>

{
    "title": "Quick Notification",
    "content": "Simple notification",
    "type": "info",
    "category": "system"
}
```

### 3. Lấy Danh Sách Notifications

```http
GET /api/v1/system/notifications?is_read=false&category=social&skip=0&limit=20
Authorization: Bearer <token>
```

Query Parameters:
- `is_read`: true/false - Lọc theo trạng thái đã đọc
- `category`: string - Lọc theo category
- `type`: string - Lọc theo type (info, success, warning, error, alert)
- `action`: string - Lọc theo action
- `priority`: int (1-5) - Lọc theo priority
- `skip`: int - Pagination skip
- `limit`: int (1-100) - Pagination limit

### 4. Đánh Dấu Đã Đọc

```http
PUT /api/v1/system/notifications/{notification_id}/read
Authorization: Bearer <token>
```

### 5. Đánh Dấu Chưa Đọc

```http
PUT /api/v1/system/notifications/{notification_id}/unread
Authorization: Bearer <token>
```

### 6. Đánh Dấu Tất Cả Đã Đọc

```http
PUT /api/v1/system/notifications/mark-all-read?category=social
Authorization: Bearer <token>
```

### 7. Đếm Số Notifications Chưa Đọc

```http
GET /api/v1/system/notifications/unread-count?category=social&priority=3
Authorization: Bearer <token>
```

### 8. Đếm Theo Category

```http
GET /api/v1/system/notifications/unread-count-by-category
Authorization: Bearer <token>
```

Response:
```json
{
    "success": true,
    "data": {
        "system": 5,
        "social": 3,
        "conversation": 12,
        "bot": 2
    },
    "total": 22
}
```

### 9. Xóa Notification

```http
DELETE /api/v1/system/notifications/{notification_id}
Authorization: Bearer <token>
```

## Best Practices

### 1. Sử Dụng Priority Hợp Lý

- **Priority 5**: Urgent, cần attention ngay lập tức (payment failed, security alert)
- **Priority 4**: Important, cần xem sớm (new message, login from new device)
- **Priority 3**: Normal, thông báo quan trọng (resource created, connection success)
- **Priority 2**: Low, thông tin bổ sung (minor updates)
- **Priority 1**: Very low, thông tin không quan trọng

### 2. Sử Dụng Link Reference

Luôn cung cấp link để user có thể navigate tới resource liên quan:

```python
link={
    "type": "facebook_page",  # Loại resource
    "url": "/socials/facebook/pages/123456",  # URL để navigate
    "resource_id": "123456"  # ID của resource
}
```

### 3. Sử Dụng Metadata

Lưu thêm thông tin hữu ích trong metadata:

```python
metadata={
    "platform": "facebook",
    "page_name": "My Shop",
    "page_id": "123456",
    "timestamp": get_vietnam_now_naive().isoformat()
}
```

### 4. Set Expiration cho Notifications Tạm Thời

```python
expires_at=get_vietnam_now_naive() + timedelta(days=7)  # Hết hạn sau 7 ngày
```

### 5. Error Handling

```python
try:
    await NotificationHelper.notify_social_connected(...)
except Exception as e:
    logger.error(f"Failed to send notification: {str(e)}")
    # Notification failures should not break the main flow
```

## Maintenance

### Clean Up Old Notifications

```python
from controllers.data.managements import get_mongodb_factory

factory = get_mongodb_factory()

# Xóa notifications đã đọc cũ hơn 30 ngày
deleted_count = await factory.notification_manager.delete_old_notifications(days=30)

# Xóa notifications đã hết hạn
expired_count = await factory.notification_manager.delete_expired_notifications()
```

## Examples trong Context

### Example 1: Sau khi kết nối Facebook

```python
# Trong controllers/socials/facebook/facebook_connect.py

async def connect_facebook(authorization_code: str, user_id: str):
    # ... logic kết nối Facebook ...
    
    # Gửi notification
    await NotificationHelper.notify_social_connected(
        user_id=user_id,
        platform="Facebook",
        account_name=account_data.get("name"),
        account_id=str(social_account["_id"])
    )
    
    return result
```

### Example 2: Sau khi tạo Bot

```python
# Trong api/v1/bots/api_bot_management.py

@router.post("/bots")
async def create_bot(bot_data: BotCreate, current_user: dict = Depends(get_current_user)):
    # ... logic tạo bot ...
    
    # Gửi notification
    await NotificationHelper.notify_bot_created(
        user_id=current_user.get("user_id"),
        bot_name=bot_data.name,
        bot_id=str(bot["_id"])
    )
    
    return {"success": True, "data": bot}
```

### Example 3: Khi nhận tin nhắn mới

```python
# Trong bot/bot_facebook_messenger.py

async def process_facebook_message(sender_id: str, page_id: str, message: str, **kwargs):
    # ... logic xử lý tin nhắn ...
    
    # Lấy thông tin user và conversation
    page = await factory.facebook_page_manager.get_by_fb_page_id(page_id)
    user_id = page.get("user_id")
    
    # Gửi notification cho page owner
    await NotificationHelper.notify_new_message(
        user_id=user_id,
        sender_name=sender_info.get("name", "Unknown"),
        message_preview=message,
        conversation_id=conversation_id,
        platform="messenger"
    )
```

## Notification Structure

```json
{
    "_id": "notif_123",
    "user_id": "user_123",
    "title": "Facebook Page mới",
    "content": "Page 'My Shop' đã được thêm vào",
    "type": "success",
    "category": "social",
    "action": "page_added",
    "priority": 3,
    "is_read": false,
    "read_at": null,
    "metadata": {
        "platform": "facebook",
        "page_name": "My Shop",
        "page_id": "123456"
    },
    "link": {
        "type": "facebook_page",
        "url": "/socials/facebook/pages/123456",
        "resource_id": "123456"
    },
    "expires_at": "2025-10-10T00:00:00Z",
    "create_at": "2025-10-02T10:30:00Z",
    "update_at": "2025-10-02T10:30:00Z"
}
```

## Frontend Integration

### Polling cho Notifications Mới

```javascript
// Poll every 30 seconds
setInterval(async () => {
    const response = await fetch('/api/v1/system/notifications/unread-count', {
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    const data = await response.json();
    updateNotificationBadge(data.unread_count);
}, 30000);
```

### Lấy Notifications theo Category

```javascript
const getNotificationsByCategory = async (category) => {
    const response = await fetch(
        `/api/v1/system/notifications?category=${category}&is_read=false&limit=20`,
        {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        }
    );
    return await response.json();
};
```

### Navigate tới Resource

```javascript
const handleNotificationClick = async (notification) => {
    // Mark as read
    await fetch(`/api/v1/system/notifications/${notification._id}/read`, {
        method: 'PUT',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    });
    
    // Navigate to link
    if (notification.link && notification.link.url) {
        window.location.href = notification.link.url;
    }
};
```

## Support

Nếu có vấn đề hoặc câu hỏi về hệ thống notification, vui lòng liên hệ team development.
