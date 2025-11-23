# Hướng dẫn Test Dashboard API

## Endpoint
```
GET /api/v1/dashboard/overview
```

## ✨ Chart Context Feature

**Quan trọng**: Biểu đồ giờ luôn hiển thị thêm context (dữ liệu trước đó) để dễ so sánh:

- **period=today**: Chart hiển thị 7 ngày (6 ngày trước + hôm nay)
- **period=week**: Chart hiển thị 4 tuần (3 tuần trước + tuần này)
- **period=month**: Chart hiển thị 3 tháng (2 tháng trước + tháng này)
- **period=year/all**: Giữ nguyên range

### Field mới: `is_current_period`
Mỗi data point trong chart có thêm field `is_current_period` (boolean):
- `true`: Data trong period user chọn
- `false`: Context data (dữ liệu trước đó)

## Test Cases

### 1. Test với period="today"
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview?period=today" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**: Trả về dữ liệu từ 00:00:00 đến 23:59:59.999999 của ngày hôm nay

### 2. Test với period="week"
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview?period=week" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**: Trả về dữ liệu từ đầu tuần (Thứ 2) đến cuối tuần (Chủ nhật)

### 3. Test với period="month"
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview?period=month" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**: Trả về dữ liệu từ ngày 1 đến ngày cuối tháng hiện tại

### 4. Test với custom date range
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview?start_date=2025-10-01&end_date=2025-10-13" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected**: Trả về dữ liệu từ 2025-10-01 00:00:00 đến 2025-10-13 23:59:59.999999

### 5. Test với company_id filter
```bash
curl -X GET "http://localhost:8000/api/v1/dashboard/overview?period=today&company_id=COMPANY_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Kiểm tra Response Structure

Response phải giữ nguyên cấu trúc:

```json
{
  "success": true,
  "data": {
    "summary": {
      "bots": {
        "total_bots": {...},
        "new_bots": {...},
        "messages": {...},
        "performance": {...}
      },
      "social": {...},
      "customers": {...},
      "orders": {...},
      "knowledge": {...},
      "activities": {...}
    },
    "charts": {...},
    "recent_customer_messages": {
      "title": "Tin nhắn mới nhất từ khách hàng",
      "data": [...],
      "total_customers": 7
    },
    "recent_activity": {
      "title": "Hoạt động gần đây",
      "data": [...],
      "total_activities": 15
    },
    "notifications_summary": {...},
    "metadata": {
      "period": "today",
      "start_date": "2025-10-13T00:00:00",
      "end_date": "2025-10-13T23:59:59.999999",
      "user_id": "...",
      "company_id": null,
      "generated_at": "2025-10-13T10:55:02.565817"
    }
  }
}
```

## Các điểm cần kiểm tra

✅ **Date Range**: 
- Check `metadata.start_date` và `metadata.end_date` có đúng không
- Với period="today", end_date phải là 23:59:59.999999 của ngày hôm nay

✅ **Data Count**:
- `summary.bots.new_bots.current` phải > 0 nếu có bot mới trong period
- `summary.customers.new_customers.current` phải > 0 nếu có khách hàng mới
- Tương tự với các metrics khác

✅ **Growth Rate**:
- Các field `growth_rate` và `growth_direction` phải có
- `growth_direction` là "increase", "decrease" hoặc "stable"

✅ **Recent Messages**:
- `recent_customer_messages.data` phải là array (có thể empty)
- Mỗi message phải có: session_id, query, answer, created_at, etc.

✅ **Recent Activity**:
- `recent_activity.data` phải là array (có thể empty)
- Mỗi activity phải có: type, title, content, timestamp, etc.

## Logs để check

Trong logs, bạn sẽ thấy:

```
INFO: 🎯 Dashboard overview request - user_id: xxx, period: today
INFO: 📅 Date range: 2025-10-13 00:00:00 -> 2025-10-13 23:59:59.999999
DEBUG: Count histories with created_at from 2025-10-13 00:00:00 to 2025-10-13 23:59:59.999999: 123
DEBUG: Growth for bots: current=5, previous=3, rate=66.67
...
```

## Troubleshooting

### Không có dữ liệu trả về?
1. Check logs xem date range có đúng không
2. Check trong MongoDB có dữ liệu với user_id đó không
3. Check các field datetime trong MongoDB có đúng format không (phải là DateTime, không phải string)

### Dữ liệu không đúng?
1. Check timezone của datetime trong MongoDB
2. Verify query MongoDB bằng cách test trực tiếp trong MongoDB shell
3. Check logs để xem count có đúng không

### Growth rate = 0?
- Có thể không có dữ liệu trong period trước đó
- Hoặc số lượng giữa 2 period bằng nhau
