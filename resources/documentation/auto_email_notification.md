# Auto Email Notification Feature

## Tổng quan

Tính năng tự động gửi email notification khi tạo notification trong hệ thống. Tính năng này được tích hợp vào `NotificationMixin` và tự động kiểm tra user settings trước khi gửi email.

## Cách hoạt động

1. Khi một notification được tạo thông qua các mixin methods (ví dụ: `notify_order_created()`, `notify_customer_created()`, etc.)
2. Hệ thống tự động:
   - Kiểm tra user có bật `enable_email_notifications` không
   - Kiểm tra setting cụ thể cho loại notification đó (ví dụ: `new_order_notifications`)
   - Lấy thông tin email từ user profile
   - Gửi email thông báo nếu tất cả điều kiện đều thỏa mãn

## User Settings Required

User cần có các settings sau trong collection `user_settings`:

### 1. Enable Email Notifications (Bắt buộc)
```json
{
  "user_id": "user_id",
  "category": "email",
  "setting_key": "enable_email_notifications",
  "setting_value": true
}
```

### 2. Specific Notification Settings
Tùy theo loại notification, user cần bật setting tương ứng:

#### New Order Notifications
```json
{
  "user_id": "user_id",
  "category": "email",
  "setting_key": "new_order_notifications",
  "setting_value": true
}
```

#### New Customer Notifications
```json
{
  "user_id": "user_id",
  "category": "email",
  "setting_key": "new_customer_notifications",
  "setting_value": true
}
```

#### New Message Notifications
```json
{
  "user_id": "user_id",
  "category": "email",
  "setting_key": "new_message_notifications",
  "setting_value": true
}
```

#### System Notifications
```json
{
  "user_id": "user_id",
  "category": "email",
  "setting_key": "system_notifications",
  "setting_value": true
}
```

## Category/Action Mapping

Hệ thống tự động map category và action của notification sang setting key tương ứng:

| Category | Action | Setting Key |
|----------|--------|-------------|
| `order` | `created`, `new_order` | `new_order_notifications` |
| `business` | `new_order` | `new_order_notifications` |
| `customer` | `created` | `new_customer_notifications` |
| `crm` | `new_customer` | `new_customer_notifications` |
| `conversation` | `message_received`, `new_message` | `new_message_notifications` |
| `system` | any | `system_notifications` |
| `auth` | any | `system_notifications` |
| `bot` | any | `system_notifications` |

## Sử dụng trong Code

Không cần thay đổi gì! Chỉ cần sử dụng các notification mixin như bình thường:

```python
# Ví dụ: Thông báo order mới
class YourManager(BaseManager, OrderNotificationMixin):
    def __init__(self, db_manager):
        super().__init__(db_manager, "your_collection")
        self.init_notification_mixin(db_manager)
    
    async def create_order(self, ...):
        # Tạo order logic...
        
        # Gửi notification (email sẽ được gửi tự động nếu user bật setting)
        await self.notify_order_created(
            user_id=user_id,
            order_code=order_code,
            order_id=order_id,
            total_price=total_price,
            customer_name=customer_name
        )
```

## API Endpoints để quản lý Email Settings

### Lấy Email Settings
```http
GET /api/v1/system/email-settings
Authorization: Bearer <token>
```

### Cập nhật Email Settings
```http
PUT /api/v1/system/email-settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "enable_email_notifications": true,
  "new_order_notifications": true,
  "new_customer_notifications": true,
  "new_message_notifications": false,
  "system_notifications": true
}
```

## Testing

Sử dụng test script để kiểm tra tính năng:

```bash
python tests/test_email_notification.py
```

Script sẽ:
1. Tìm một user để test
2. Bật email settings nếu chưa bật
3. Tạo một notification test
4. Kiểm tra xem email có được gửi không

## Lưu ý

- Email chỉ được gửi khi cả 2 settings (`enable_email_notifications` và setting cụ thể) đều được bật
- User phải có email trong profile
- Nếu có lỗi khi gửi email, notification vẫn được tạo thành công (email error không ảnh hưởng notification)
- Email được gửi trong event loop hiện tại, không chặn notification creation

## Troubleshooting

### Email không được gửi?

Kiểm tra:
1. ✅ User có bật `enable_email_notifications` = true?
2. ✅ User có bật setting cụ thể (ví dụ: `new_order_notifications`) = true?
3. ✅ User có email trong profile?
4. ✅ SMTP settings đã được cấu hình đúng? (check `configs/constant.py`)
5. ✅ Check logs để xem có error gì không

### Làm sao biết email đã được gửi?

Check logs, sẽ thấy dòng:
```
Email notification sent to user@example.com for order/created
```
