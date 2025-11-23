# 🔧 Auto-Ensure MongoDB Indexes

## Tổng Quan

Hệ thống đã được cấu hình để **tự động kiểm tra và tạo indexes** khi application khởi động. Bạn không cần chạy script thủ công nữa!

## Cách Hoạt Động

### 1. Auto-Ensure trong `app.py`
Khi FastAPI app khởi động:
```python
@app.on_event("startup")
async def startup_event():
    # ...
    ensure_mongodb_indexes(mongodb_manager.database)
    # ✅ Tự động kiểm tra và tạo TẤT CẢ indexes
```

### 2. Auto-Ensure trong Bot
Khi bot khởi động:
```python
async def initialize(self):
    # ...
    ensure_product_indexes(self.db_manager.database)
    # ✅ Tự động kiểm tra và tạo indexes cho products
```

## Module: `ensure_indexes.py`

### Class: `MongoDBIndexEnsurer`

Quản lý việc đảm bảo indexes tồn tại trong MongoDB.

#### Tính Năng

1. **Auto-Detection**: Kiểm tra index đã tồn tại chưa
2. **Auto-Creation**: Tự động tạo nếu chưa có
3. **Background Mode**: Tạo index trong background (không block)
4. **Safe**: Không ảnh hưởng đến indexes đã tồn tại
5. **Multi-Collection**: Hỗ trợ nhiều collections

#### Collections Được Quản Lý

```python
indexes_config = {
    "products": [
        # 8 indexes cho product search
    ],
    "customers": [
        # 3 indexes cho customer lookup
    ],
    "orders": [
        # 3 indexes cho order queries
    ],
    "warehouses": [
        # 2 indexes cho inventory
    ]
}
```

### Functions

#### `ensure_mongodb_indexes(database)`
Ensure tất cả indexes cho tất cả collections.

**Sử dụng trong:**
- `app.py` startup event

**Ví dụ:**
```python
from controllers.databases.mongodb.ensure_indexes import ensure_mongodb_indexes

# Trong startup
ensure_mongodb_indexes(mongodb_manager.database)
```

#### `ensure_product_indexes(database)`
Chỉ ensure indexes cho products collection.

**Sử dụng trong:**
- `bot_facebook_messenger.py` initialization

**Ví dụ:**
```python
from controllers.databases.mongodb.ensure_indexes import ensure_product_indexes

# Trong bot init
ensure_product_indexes(self.db_manager.database)
```

## Indexes Được Tạo Tự Động

### Products Collection (8 indexes)

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_company_id` | company_id | Filter by company |
| `idx_fulltext_search` | name, description, tags | Full-text search |
| `idx_sku` | sku | SKU lookup |
| `idx_category` | data.category | Category filter |
| `idx_price` | pricing.price | Price range filter |
| `idx_company_price` | company_id + price | Compound query |
| `idx_company_category` | company_id + category | Compound query |
| `idx_user_created` | user_id + created_at | User's products |

### Customers Collection (3 indexes)

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_social_customer` | social_id + social_page_id + customer_id | Unique customer lookup |
| `idx_phone` | phone | Phone lookup |
| `idx_email` | email | Email lookup |

### Orders Collection (3 indexes)

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_social_order` | social_id + social_page_id + customer_id | Customer orders |
| `idx_status` | status | Status filter |
| `idx_created` | created_at | Sort by date |

### Warehouses Collection (2 indexes)

| Index Name | Fields | Purpose |
|------------|--------|---------|
| `idx_company` | company_id | Company warehouses |
| `idx_product_inventory` | inventory.product_id | Product inventory |

## Logging

Hệ thống log chi tiết:

```
🔍 Kiểm tra và tạo indexes cho MongoDB...
✅ Đã tạo index 'idx_company_id' cho 'products'
✓ Index 'idx_fulltext_search' đã tồn tại trong 'products'
✅ Đã tạo index 'idx_sku' cho 'products'
...
✅ Đã tạo 5 indexes mới
ℹ️  3 indexes đã tồn tại
🎉 Hoàn thành kiểm tra indexes!
```

## Khi Nào Indexes Được Tạo?

### Tự Động
- ✅ Khi start FastAPI app (`uvicorn app:app`)
- ✅ Khi khởi tạo bot (`bot_facebook_messenger.initialize()`)

### Thủ Công (Nếu Cần)
```bash
# Chạy script độc lập
python create_product_search_indexes.py
```

## Performance Impact

### Startup Time
- **First time**: +2-5 giây (tạo indexes mới)
- **Subsequent**: +50-200ms (chỉ check tồn tại)

### Runtime Impact
- **Zero**: Indexes được tạo trong background mode
- **No blocking**: Application vẫn hoạt động bình thường

## Best Practices

### 1. Development
```python
# Indexes tự động tạo khi start app
uvicorn app:app --reload
```

### 2. Production
```python
# Indexes tự động tạo lần đầu deploy
# Các lần sau chỉ verify
uvicorn app:app
```

### 3. Testing
```python
# Có thể test riêng
from controllers.databases.mongodb.ensure_indexes import MongoDBIndexEnsurer

ensurer = MongoDBIndexEnsurer(database)
ensurer.ensure_all_indexes()
ensurer.list_all_indexes()
```

## Quản Lý Indexes

### Kiểm Tra Indexes Hiện Tại
```python
from controllers.databases.mongodb.ensure_indexes import MongoDBIndexEnsurer

ensurer = MongoDBIndexEnsurer(database)
ensurer.list_all_indexes()
```

### Kiểm Tra Index Cụ Thể
```python
exists = ensurer.check_index_exists("products", "idx_fulltext_search")
print(f"Index exists: {exists}")
```

### Xóa Index (Nếu Cần)
```python
ensurer.drop_index("products", "idx_old_index")
```

## Troubleshooting

### Lỗi: "Index already exists"
✅ **Bình thường** - Hệ thống tự động bỏ qua

### Lỗi: "Cannot create index"
❌ **Kiểm tra:**
- MongoDB có đủ quyền tạo index?
- Disk space còn đủ không?
- Collection có data conflict không?

### Lỗi: "Connection failed"
❌ **Kiểm tra:**
- MongoDB có đang chạy?
- Connection string đúng?
- Network có vấn đề?

## Migration từ Manual Script

### Trước Đây (Manual)
```bash
# Phải chạy thủ công mỗi lần
python create_product_search_indexes.py
```

### Bây Giờ (Auto)
```bash
# Chỉ cần start app
uvicorn app:app
# ✅ Indexes tự động ensure
```

### Script Cũ Vẫn Hoạt Động
Script `create_product_search_indexes.py` vẫn có thể dùng nếu muốn chạy riêng.

## Thêm Index Mới

### Bước 1: Cập nhật `indexes_config`
```python
# Trong ensure_indexes.py
self.indexes_config = {
    "products": [
        # ... existing indexes
        {
            "name": "idx_new_field",
            "keys": [("new_field", ASCENDING)],
            "unique": False
        }
    ]
}
```

### Bước 2: Restart App
```bash
# Index mới tự động được tạo
uvicorn app:app --reload
```

## Summary

| Feature | Status |
|---------|--------|
| Auto-creation on app startup | ✅ |
| Auto-creation on bot init | ✅ |
| Background mode | ✅ |
| Safe (no duplicates) | ✅ |
| Multi-collection support | ✅ |
| Detailed logging | ✅ |
| Manual script still works | ✅ |

---

**Result**: Bạn không cần lo về indexes nữa! Hệ thống tự động đảm bảo chúng luôn tồn tại. 🎉
