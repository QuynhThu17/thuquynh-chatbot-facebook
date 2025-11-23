# Mô Tả Hệ Thống Social Media Bot - MekongAI

## MÔ TẢ LUỒNG CHỨC NĂNG CHO KHÁCH HÀNG

### A. LUỒNG ĐĂNG KÝ VÀ KHỞI TẠO TÀI KHOẢN

#### Bước 1: Đăng ký tài khoản
- Khách hàng truy cập website và chọn "Đăng ký"
- Có 2 tùy chọn: Đăng ký bằng Email/Password hoặc Google
- Điền thông tin cơ bản: Tên, email, mật khẩu
- Xác thực email (nếu dùng email)
- Chọn gói dịch vụ ban đầu (có thể có gói miễn phí trial)

#### Bước 2: Thiết lập profile
- Upload avatar
- Điền thông tin chi tiết: Công ty, ngành nghề, mục tiêu sử dụng
- Chọn múi giờ và ngôn ngữ

---

### B. LUỒNG SỬ DỤNG DASHBOARD

#### Trang Dashboard chính bao gồm:
- **Tổng quan hệ thống**: 
  - Số lượng bot đang hoạt động
  - Số tin nhắn đã xử lý hôm nay/tuần/tháng
  - Số đơn hàng mới từ bot
  - Tỷ lệ chuyển đổi khách hàng
- **Biểu đồ thống kê**:
  - Biểu đồ tương tác theo thời gian
  - Top sản phẩm được hỏi nhiều nhất
  - Thống kê hiệu suất bot
- **Hoạt động gần đây**:
  - Tin nhắn mới
  - Đơn hàng mới
  - Feedback từ khách hàng
- **Cảnh báo và thông báo**:
  - Token sắp hết
  - Bot offline
  - Đơn hàng cần xử lý
- **Quick Actions**:
  - Tạo bot mới
  - Kết nối social account
  - Xem báo cáo chi tiết

---

### C. LUỒNG QUẢN LÝ SOCIAL MEDIA

#### Bước 1: Kết nối Social Platform
- Vào "Quản lý Socials" từ sidebar
- Hiển thị danh sách platforms: Facebook, Instagram, Twitter, LinkedIn
- Chọn Facebook → Hiển thị danh sách tài khoản đã kết nối
- Nhấn "Kết nối tài khoản mới":
  - Chuyển hướng đến Facebook OAuth
  - Cấp quyền truy cập
  - Lưu access token và thông tin tài khoản

#### Bước 2: Quản lý Facebook Pages
- Nhấn vào tài khoản đã kết nối
- Hiển thị grid/list tất cả pages mà tài khoản sở hữu
- Mỗi page hiển thị: Avatar, tên, số follower, trạng thái kết nối
- Chọn pages muốn sử dụng cho bot

---

### D. LUỒNG TẠO VÀ QUẢN LÝ BOT (Chi tiết)

#### Bước 1: Vào quản lý bot
- Sidebar → "Quản lý Bot"
- Mặc định hiển thị tab "Quản lý Bot" với danh sách bot hiện có
- Mỗi bot hiển thị: Tên, trạng thái, platform kết nối, số tin nhắn đã xử lý

#### Bước 2: Tạo bot mới - Quy trình từng bước
**Bước 2.1: Thông tin cơ bản**
- Nhấn "Tạo Bot Mới"
- Màn hình hướng dẫn từng bước:
  - Bước 1/7: Đặt tên cho bot
  - Bước 2/7: Chọn loại bot (Message/Comment/Post)
  - Bước 3/7: Chọn ngôn ngữ chính

**Bước 2.2: Chọn/Tạo Nhân dạng**
- Bước 4/7: Hiển thị danh sách nhân dạng có sẵn:
  - Nhân dạng mặc định: "Tư vấn viên chuyên nghiệp", "Bạn thân thiện", "Chuyên gia kỹ thuật"
  - Nhân dạng tùy chỉnh của user
- Tùy chọn "Tạo nhân dạng mới":
  - Popup/Modal với form:
    - Tên nhân dạng
    - Mô tả tính cách
    - Phong cách giao tiếp (formal/informal/friendly)
    - Mẫu hội thoại (ít nhất 3 mẫu)
    - Preview conversation với nhân dạng đã tạo

**Bước 2.3: Chọn/Tạo Quy trình**
- Bước 5/7: Danh sách quy trình:
  - Quy trình mặc định: "Tư vấn bán hàng", "Hỗ trợ khách hàng", "Thu thập thông tin"
  - Quy trình tùy chỉnh
- Tùy chọn "Tạo quy trình mới":
  - Drag-drop workflow builder
  - Các node: Start, Message, Condition, Action, End
  - Thiết lập điều kiện và hành động cho từng bước

**Bước 2.4: Cấu hình Bot**
- Bước 6/7: Nhập thông tin chi tiết:
  - Vai trò (Role): "Tư vấn viên bán hàng điện thoại"
  - Mục tiêu (Target): "Bán được 100 điện thoại/tháng"
  - Nhiệm vụ (Mission): "Tư vấn sản phẩm, báo giá, xử lý đơn hàng"
  - Ghi chú (Note): Thông tin bổ sung

**Bước 2.5: Chọn Kiến thức**
- Bước 7/7: Chuyển đến trang Quản lý Kiến thức:
  - Chọn documents đã upload
  - Chọn sản phẩm từ CRM
  - Chọn company information
  - Thiết lập mức độ ưu tiên thông tin

#### Bước 3: Kết nối Social Platform
- Sau khi tạo bot, hiển thị modal "Kết nối Platform"
- Chọn Facebook → Chọn tài khoản → Chọn page
- Thiết lập trigger conditions:
  - Keywords để bot phản hồi
  - Thời gian hoạt động
  - Blacklist users

#### Bước 4: Test và Deploy
- Chế độ test: Chat trực tiếp với bot
- Xem preview responses
- Adjust settings nếu cần
- Bật bot (switch On/Off)

---

### E. LUỒNG CRM

#### E.1: Thiết lập Company
- Vào "CRM" → Tab "Quản lý Công ty"
- Mặc định có 1 company "Default Company"
- Tạo company mới:
  - Thông tin cơ bản: Tên, website, địa chỉ, ngành nghề
  - Logo và hình ảnh
  - Thông tin liên hệ
  - Cấu trúc tổ chức

#### E.2: Quản lý Contacts
- Tab "Quản lý Liên hệ"
- Phân loại: Customers, Employees, Suppliers, Partners
- Import contacts:
  - Từ CSV/Excel
  - Từ Google Contacts
  - Từ social media
- Thông tin chi tiết:
  - Basic info: Tên, email, SĐT, địa chỉ
  - Company association
  - Tags và notes
  - Communication history
  - Custom fields

#### E.3: Quản lý Sản phẩm
- Tab "Quản lý Sản phẩm"
- Tạo sản phẩm:
  - Thông tin cơ bản: Tên, SKU, giá
  - Mô tả chi tiết
  - Hình ảnh chính và gallery
  - Categories và tags
  - Specifications (custom fields)
- Import products:
  - Từ Excel với template
  - Từ SQL database
  - Từ CSV file
- Product variants:
  - Size, color, material
  - Different pricing
  - Separate inventory

#### E.4: Quản lý Kho
- Tab "Quản lý Kho"
- Tạo warehouse:
  - Tên và địa chỉ kho
  - Layout map (optional)
  - Storage zones
- Inventory management:
  - Stock levels
  - Location trong kho
  - Minimum stock alerts
  - Stock movement history

#### E.5: Quản lý Đơn hàng
- Tab "Orders"
- Order sources:
  - Tự động từ bot conversations
  - Thủ công tạo đơn
  - Import từ external systems
- Order workflow:
  - New → Confirmed → Processing → Shipped → Delivered → Completed
  - Cancelled/Refunded states
- Order details:
  - Customer information
  - Line items với quantity và pricing
  - Shipping address
  - Payment method và status
  - Order notes

#### E.6: Quản lý Vận chuyển
- Tab "Shipments"
- Integration với đơn vị vận chuyển:
  - Giao Hàng Nhanh, Giao Hàng Tiết Kiệm
  - ViettelPost, VNPost
  - International: DHL, FedEx
- Shipment tracking:
  - Real-time status updates
  - Delivery notifications
  - Customer tracking portal
- Shipping cost calculation:
  - Weight-based
  - Distance-based
  - Zone-based pricing

---

### F. LUỒNG QUẢN LÝ TÀI LIỆU VÀ KIẾN THỨC

#### Upload và xử lý tài liệu:
- Tab "Quản lý Thông tin Công ty"
- Upload options:
  - Drag & drop files
  - Browse và select multiple files
  - URL import
- Supported formats: PDF, DOC, DOCX, Excel, TXT, Markdown
- Document processing:
  - Extract text content
  - Generate embeddings
  - Create searchable chunks
  - OCR for scanned documents

#### Knowledge base management:
- Organize documents trong folders
- Tagging và categorization
- Search và filter
- Version control
- Access permissions

---

### G. LUỒNG SETTINGS VÀ HỖ TRỢ

#### G.1: Settings
- **Account Settings**: 
  - Profile information
  - Change password
  - Two-factor authentication
  - Delete account
- **Notification Settings**:
  - Email notifications
  - Browser notifications
  - Mobile push notifications
  - Notification frequency
- **API Settings**:
  - Generate API keys
  - Webhook URLs
  - Rate limits
- **Integration Settings**:
  - Third-party connections
  - OAuth applications
  - Custom integrations

#### G.2: Help & Support
- **Documentation**: Comprehensive user guides
- **Video Tutorials**: Step-by-step video guides
- **FAQ**: Frequently asked questions
- **Contact Support**: 
  - Live chat
  - Email tickets
  - Phone support (for premium users)
- **Community Forum**: User community discussions
- **Feature Requests**: Suggest new features

---

### H. LUỒNG UPGRADE PLAN

#### Current plan overview:
- Display current plan details
- Usage statistics và limits
- Remaining quota

#### Available plans:
- Feature comparison table
- Pricing information
- User testimonials

#### Upgrade process:
- Select new plan
- Payment method selection
- Billing information
- Confirmation và activation
