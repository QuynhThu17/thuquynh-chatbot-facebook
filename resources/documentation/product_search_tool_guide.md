# 🔍 Hướng Dẫn Sử Dụng Tool Tìm Kiếm Sản Phẩm

## Tổng Quan

Tool `search_products` được thiết kế để tìm kiếm sản phẩm một cách thông minh và linh hoạt, hỗ trợ đa dạng các dạng query từ người dùng.

## Tính Năng Chính

### 1. Tìm Kiếm Mờ (Fuzzy Search)
- Không cần gõ chính xác tên sản phẩm
- Không phân biệt hoa thường
- Hỗ trợ bỏ dấu tiếng Việt
- Tìm kiếm trong: tên, mô tả, tags, category, SKU

**Ví dụ:**
```python
# User: "có sản phẩm iphone nào không?"
search_products_tool(search_query="iphone")

# User: "có điện thoại nào không" (gõ sai dấu)
search_products_tool(search_query="điện thoại")

# User: "tim dien thoai" (không dấu)
search_products_tool(search_query="dien thoai")
```

### 2. Tìm Theo Mã SKU
- Tìm chính xác hoặc chứa chuỗi SKU
- Ưu tiên cao hơn search_query

**Ví dụ:**
```python
# User: "tìm sp có mã IP15PM-256-BLK-2"
search_products_tool(sku="IP15PM-256-BLK-2")

# User: "có sản phẩm nào mã IP15PM"
search_products_tool(sku="IP15PM")

# User: "sản phẩm màu đen" (BLK = Black)
search_products_tool(sku="BLK")
```

### 3. Lọc Theo Khoảng Giá
- Hỗ trợ giá min/max
- Đơn vị: VND

**Ví dụ:**
```python
# User: "những sản phẩm có giá dưới 500k"
search_products_tool(max_price=500000)

# User: "sản phẩm giá từ 1 triệu đến 5 triệu"
search_products_tool(min_price=1000000, max_price=5000000)

# User: "sản phẩm trên 10 triệu"
search_products_tool(min_price=10000000)
```

### 4. Tìm Theo Danh Mục
- Tìm kiếm trong field `data.category`

**Ví dụ:**
```python
# User: "có điện thoại nào"
search_products_tool(category="Smartphones")

# User: "laptop nào tốt"
search_products_tool(category="Laptop")
```

### 5. Kiểm Tra Tồn Kho
- Truy vấn warehouse để lấy số lượng tồn kho
- Tổng hợp từ tất cả kho

**Ví dụ:**
```python
# User: "còn bao nhiêu cái trong kho"
search_products_tool(check_inventory=True)

# User: "iphone còn hàng không"
search_products_tool(search_query="iphone", check_inventory=True)
```

### 6. Đếm Số Lượng Sản Phẩm
- Tăng limit để đếm nhiều sản phẩm hơn

**Ví dụ:**
```python
# User: "có bán bao nhiêu sản phẩm"
search_products_tool(limit=50)

# User: "danh sách tất cả sản phẩm"
search_products_tool(limit=50)
```

## Kết Hợp Nhiều Điều Kiện

Tool hỗ trợ kết hợp nhiều điều kiện cùng lúc:

```python
# User: "iphone giá từ 20tr đến 30tr"
search_products_tool(
    search_query="iphone",
    min_price=20000000,
    max_price=30000000
)

# User: "điện thoại samsung còn hàng giá dưới 10tr"
search_products_tool(
    search_query="samsung",
    max_price=10000000,
    check_inventory=True
)

# User: "laptop gaming còn trong kho"
search_products_tool(
    category="Laptop",
    search_query="gaming",
    check_inventory=True
)
```

## Các Trường Hợp Đặc Biệt

### 1. Query Mơ Hồ
Khi user hỏi không rõ ràng, dùng `search_query` cho linh hoạt:

```python
# User: "có gì mới không"
search_products_tool(limit=10)

# User: "sản phẩm nào đẹp"
search_products_tool(limit=10)
```

### 2. Query Về Giá
Tool tự động hiểu các từ khóa về giá:

```python
# "dưới 500k" -> max_price=500000
# "trên 1 triệu" -> min_price=1000000
# "từ 2tr đến 5tr" -> min_price=2000000, max_price=5000000
```

### 3. Query Về Tồn Kho
Các từ khóa liên quan đến kho:
- "còn hàng", "còn không", "hết hàng"
- "trong kho", "số lượng", "bao nhiêu cái"
→ Set `check_inventory=True`

## Tối Ưu Hóa

### MongoDB Indexes
Tool sử dụng các indexes sau để tối ưu tốc độ:

1. **idx_company_id**: Filter theo company
2. **idx_fulltext_search**: Text search (name, description, tags)
3. **idx_sku**: Tìm theo SKU
4. **idx_category**: Filter theo category
5. **idx_price**: Filter theo giá
6. **idx_company_price**: Compound index (company + price)
7. **idx_company_category**: Compound index (company + category)

### Best Practices

1. **Ưu tiên SKU** nếu user cung cấp mã cụ thể
2. **Sử dụng category** nếu user đề cập danh mục rõ ràng
3. **Kết hợp price filter** khi user đề cập giá
4. **Bật check_inventory** khi user hỏi về tồn kho
5. **Giới hạn limit** hợp lý (mặc định 10, tối đa 50)

## Kết Quả Trả Về

Tool trả về thông tin chi tiết:

```
✅ Tìm thấy 3 sản phẩm:

📦 1. iPhone 15 Pro Max
   • SKU: IP15PM-256-BLK
   • Giá: 30,000,000 VND
   • Danh mục: Smartphones
   • Màu sắc: Black Titanium
   • Mô tả: Latest iPhone model with advanced features...
   • Tồn kho: 15 sản phẩm

📦 2. iPhone 14 Pro
   • SKU: IP14P-128-BLU
   • Giá: 25,000,000 VND
   ...
```

## Xử Lý Lỗi

- ❌ Không tìm thấy company_id → Kiểm tra bot config
- ❌ Không tìm thấy sản phẩm → Trả về message thân thiện
- ❌ Lỗi database → Log error và thông báo user

## Gợi Ý Câu Hỏi Cho User

Agent nên hiểu và xử lý các câu hỏi như:

1. **Tìm kiếm chung:**
   - "có sản phẩm nào không?"
   - "cho xem sản phẩm"
   - "hiển thị danh sách sản phẩm"

2. **Tìm theo tên:**
   - "có iphone không?"
   - "điện thoại samsung"
   - "laptop dell"

3. **Tìm theo giá:**
   - "sản phẩm dưới 500k"
   - "giá từ 1 triệu đến 5 triệu"
   - "có gì rẻ không"

4. **Tìm theo mã:**
   - "tìm sp mã IP15PM"
   - "sản phẩm có SKU..."

5. **Kiểm tra kho:**
   - "còn hàng không"
   - "còn bao nhiêu trong kho"
   - "hết hàng chưa"

6. **Đếm số lượng:**
   - "có bán bao nhiêu sản phẩm"
   - "tổng cộng bao nhiêu"

## Migration & Setup

### ✨ Tự Động (Recommended)
**Indexes tự động được tạo khi app khởi động!**

```bash
# Chỉ cần start app - indexes tự động được ensure
uvicorn app:app

# ✅ Tự động check & create indexes
# ✅ Không cần chạy script thủ công
# ✅ Safe: Không duplicate nếu đã tồn tại
```

### 🔨 Thủ Công (Optional)
Nếu muốn chạy script riêng:
```bash
python create_product_search_indexes.py
```

### 📋 Module Quản Lý
- `controllers/databases/mongodb/ensure_indexes.py` - Auto-ensure logic
- `app.py` - Tích hợp vào FastAPI startup
- `bot_facebook_messenger.py` - Tích hợp vào bot initialization

**Xem thêm**: [Auto-Ensure Indexes Guide](auto_ensure_indexes_guide.md)
