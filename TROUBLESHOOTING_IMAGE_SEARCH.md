# Troubleshooting: Image Search 403 Forbidden

## Vấn đề
Khi user gửi ảnh vào Facebook Messenger, bot không thể download ảnh để search sản phẩm:
```
ERROR: ❌ Failed to download image: 403 Client Error: Forbidden
```

## Nguyên nhân

### 1. **Code chưa được reload**
Server đang chạy code cũ, chưa có fix `verify=False`.

**Giải pháp**: 
```bash
# Restart server để load code mới
# Hoặc reload nếu dùng uvicorn --reload
```

### 2. **Facebook CDN SSL Issues**
Facebook CDN có SSL certificate issues với một số môi trường.

**Đã fix**: Code mới đã disable SSL verification:
```python
response = requests.get(
    image_url, 
    headers=headers, 
    timeout=20,
    verify=False,  # ✅ Disable SSL verification
    allow_redirects=True
)
```

### 3. **Facebook URL Expiration**
URL ảnh từ Facebook có thể expire sau một thời gian.

**Workaround hiện tại**: 
- Tool sẽ return friendly error message
- User có thể describe bằng text thay vì ảnh

## Các bước kiểm tra

### Bước 1: Kiểm tra server đã restart chưa
```bash
# Check server logs
# Xem có log này không:
# "✅ Downloaded image: XXXXX bytes"
```

### Bước 2: Test download ảnh thủ công
```python
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://scontent.xx.fbcdn.net/..."  # URL từ log

headers = {
    'User-Agent': 'Mozilla/5.0...',
    'Referer': 'https://www.facebook.com/'
}

response = requests.get(url, headers=headers, verify=False, timeout=20)
print(f"Status: {response.status_code}")
print(f"Size: {len(response.content)} bytes")
```

### Bước 3: Kiểm tra webhook data
```bash
# Check file webhook trong resources/webhook/
# Xem URL ảnh có đầy đủ query parameters không
```

## Giải pháp dài hạn

### Option 1: Sử dụng Facebook Graph API (RECOMMENDED)
Thay vì download từ CDN, sử dụng Graph API với page_access_token:

```python
# Get attachment từ Graph API
url = f"https://graph.facebook.com/v20.0/{attachment_id}"
params = {
    "fields": "url",
    "access_token": page_access_token
}
response = requests.get(url, params=params)
image_url = response.json()["url"]
```

**Ưu điểm**:
- Không bị 403 Forbidden
- URL luôn valid
- Có authentication proper

### Option 2: Download và cache ảnh ngay khi nhận webhook
```python
# Trong webhook handler
if attachment.type == "image":
    url = attachment.payload.url
    # Download ngay và lưu vào S3/local
    image_data = download_image(url)
    image_id = save_to_s3(image_data)
    # Truyền image_id vào bot thay vì URL
```

### Option 3: Cho phép user upload ảnh qua web interface
Tạo web UI để user upload ảnh trực tiếp → Tránh dependency vào Facebook CDN.

## Current Status

✅ **Fixed:**
- SSL verification disabled
- Headers added
- Timeout increased
- Graceful error handling

⚠️ **Known Issue:**
- Vẫn có thể bị 403 nếu Facebook CDN block request
- Cần restart server để code mới có hiệu lực

🔄 **Workaround:**
- Tool sẽ show friendly error message
- User có thể describe sản phẩm bằng text thay vì ảnh
- Search vẫn hoạt động bình thường với text query

## Testing

Sau khi restart server, test với:
1. Gửi ảnh vào Messenger
2. Check server logs xem có "✅ Downloaded image" không
3. Nếu vẫn lỗi 403 → Cần implement Option 1 (Graph API)

---

**Last updated**: 2025-11-07
**Status**: Partial fix - cần restart server hoặc implement Graph API solution
