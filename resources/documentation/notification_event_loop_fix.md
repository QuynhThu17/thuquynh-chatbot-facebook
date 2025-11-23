# Notification Mixin - Event Loop Best Practices

## Vấn đề Event Loop Conflict

Khi tạo notifications từ các background tasks hoặc threads khác, có thể gặp lỗi:
```
RuntimeError: Task got Future attached to a different loop
```

### Nguyên nhân

- Motor (MongoDB async driver) được khởi tạo với một event loop cụ thể
- Khi tạo event loop mới trong background thread, motor vẫn reference đến loop cũ
- Gọi async MongoDB operations trong loop khác → conflict

## Giải pháp đã implement

### 1. Graceful Degradation
```python
async def _create_notification(...):
    try:
        # Kiểm tra running loop
        current_loop = asyncio.get_running_loop()
        
        # Tạo notification
        notification = await self._notification_manager.create_notification(...)
        return notification
    except RuntimeError as e:
        if "different loop" in str(e):
            # Skip notification nếu có conflict (expected behavior)
            logger.debug("Event loop conflict - notification skipped")
            return None
```

### 2. Fire-and-Forget Alternative
Nếu muốn tạo notification mà không chờ kết quả:
```python
async def some_operation(self):
    # Tạo notification trong background (không await)
    asyncio.create_task(
        self._create_notification(
            user_id="user123",
            title="Operation completed",
            content="..."
        )
    )
```

## Best Practices

### ✅ DO - Gọi trong async context
```python
class YourManager(BaseManager, NotificationMixin):
    async def create_customer(self, data):
        # Tạo customer
        customer = await self.create(data)
        
        # Gửi notification (await để đảm bảo success)
        await self.notify_customer_created(
            user_id=customer["user_id"],
            customer_name=customer["name"],
            customer_id=str(customer["_id"])
        )
        
        return customer
```

### ✅ DO - Fire-and-forget trong cùng event loop
```python
async def some_operation(self):
    # Tạo task mà không chờ
    asyncio.create_task(
        self._create_notification(...)
    )
    
    # Tiếp tục logic khác
    return result
```

### ❌ DON'T - Gọi từ background thread với event loop riêng
```python
# WRONG - Sẽ gây event loop conflict
def run_in_background(func):
    def wrapper():
        loop = asyncio.new_event_loop()  # ❌ Loop mới
        asyncio.set_event_loop(loop)
        loop.run_until_complete(func())  # ❌ Conflict
    
    thread = threading.Thread(target=wrapper)
    thread.start()
```

### ✅ DO - Sử dụng NotificationHelper cho background tasks
```python
from controllers.ultils.notification_helper import NotificationHelper

# Trong background task
async def background_process():
    # NotificationHelper xử lý event loop conflicts tốt hơn
    await NotificationHelper.notify_social_connected(
        user_id="user123",
        platform="Facebook",
        account_name="My Page",
        account_id="page123"
    )
```

## Khi nào notification bị skip?

Notification sẽ bị skip (return None) khi:
1. Không có running event loop
2. Event loop conflict (gọi từ loop khác với loop của MongoDB connection)
3. Lỗi exception khác

**Đây là hành vi mong muốn** để tránh crash ứng dụng. Notifications không nên làm gián đoạn business logic.

## Logging

- **DEBUG level**: Event loop conflict (expected, không phải lỗi)
- **ERROR level**: Lỗi thực sự (network, database, validation, etc.)

## Migration Notes

Nếu đang gặp lỗi event loop với code cũ:

1. **Cách 1**: Đảm bảo gọi notifications trong async context đúng event loop
2. **Cách 2**: Sử dụng `NotificationHelper` thay vì mixin
3. **Cách 3**: Bọc notification calls trong try-except và ignore errors

```python
# Cách 3 example
try:
    await self.notify_something(...)
except Exception as e:
    logger.debug(f"Notification failed (non-critical): {e}")
    pass  # Continue với business logic
```
