## MÔ TẢ TẤT CẢ CÁC CHỨC NĂNG CỦA HỆ THỐNG

```
Social Media Bot là hệ thống hoàn thiện được tạo bởi công ty công nghệ MekongAI 

Luồng chức năng khách hàng:

- Khách hàng đăng ký tài khoản -> Vào trang có sidebar gồm các chức năng (dashboard, Quản lý Socials, quản lý bot, CRM, Upgrade plan, Settings, Help), mặc định mở trang dashboard

- Dashboard gồm ...

- Quản lý Socials: hiển thị danh sách Socials (socials), ví dụ nhấn vào Facebook, sẽ hiển thị tất cả tài khoản facebook đã được kết nối dạng grid/list (social_accounts), có nút kết nối tài khoản mới, khi nhấn vào tài khoản đã kết nối thì hiển thị vào social_facebook_pages với tất cả pages mà tài khoản đó sở hữu 

- Quản lý bot (bots) gồm 3 Tab con: Quản lý Bot, Quản lý Nhân dạng, Quản lý Quy trình, Quản lý kiến thức
+ Khi vào trang quản lý bot, ban đầu sẽ là trang Quản lý Bot hiển thị danh sách tất cả các bot (grid/list)
+ Có nút tạo bot mới
+ Khi vào giao diện tạo bot mới, đầu tiên là trang hướng dẫn / các bước setup dạng list từng bước 1 để thực hiện
+ Đầu tiên là đặt tên cho Bot, sau đó chọn Nhân dạng (list nhân dạng đã có hoặc nút tạo mới link sang phần Quản lý Nhân dạng / show model popup), sau đó chọn Quy trình (list quy trình đã có hoặc nút tạo mới link sang phần Quản lý Quy trình / show model popup), sau đó nhập Vai trò, Mục tiêu, Nhiệm vụ, Note, sau đó chọn Kiến thức Bot (đến trang Quản lý kiến thức, phần này sẽ liên quan đến CRM), sau đó sẽ có phần switch status on/off để bật, tắt bot
+ Kết nối Socials:
Model / Cửa sổ chọn Socials -> Facebook -> List Account / Kết nối Tài khoản -> List Page -> Chọn
+ Bot có thể update bot / copy bot / delete bot

- Phần quản lý nhân dạng (identities) và quy trình (procedures) có thêm sửa xóa

- Phần CRM:
+ Quản lý Công ty (companies) phân chia công ty ra để dễ quản lý (mặc định sẽ có một công ty default)
+ Quản lý liên hệ (contacts) quản lý thông tin nhân viên, khách hàng
+ Quản lý thông tin công ty (documents): Thêm thông tin trực tiếp, hoặc upload file (.pdf, .doc, .docx, excel, .txt)
+ Quản lý sản phẩm (products): upload file (.sql, excel), nhập tay tự thêm các trường - thêm sửa xóa, có 1 hình ảnh sp chính, và các hình ảnh khác của sp như các góc khác (mô tả cho từng ảnh)
+ Quản lý Kho (warehouses) - thêm sửa xóa
+ Quản lý Order (orders) được lấy tự động khi khách hàng nhắn tin với bot (có thể thêm sửa xóa)
+ Quản lý Shipment (Quản lý vận đơn, đơn vị vận chuyển)
```

### 1. HỆ THỐNG NGƯỜI DÙNG VÀ PHÂN QUYỀN
- **Đăng ký/Đăng nhập**: Email/Password, Google OAuth
- **Phân quyền**: Role-based với features và permissions
- **Hierarchy**: Hệ thống cấp bậc người dùng (parent-children)
- **Profile Management**: Quản lý thông tin cá nhân, avatar

### 2. HỆ THỐNG THANH TOÁN VÀ GÓI DỊCH VỤ
- **Quản lý Balance**: Theo dõi số dư tài khoản
- **Packages**: Các gói dịch vụ với thời hạn và giá cả
- **Subscriptions**: Đăng ký gói, gia hạn tự động
- **Transactions**: Lịch sử giao dịch (mua gói, sử dụng, hoàn tiền)
- **Usage Tracking**: Theo dõi token sử dụng theo model

### 3. HỆ THỐNG QUẢN LÝ SOCIAL MEDIA
- **Multi-platform Support**: Facebook, Instagram, Twitter, LinkedIn...
- **Account Connection**: Kết nối nhiều tài khoản social
- **Facebook Pages Management**: Quản lý pages Facebook
- **Access Token Management**: Quản lý token truy cập
- **Social Account Sync**: Đồng bộ thông tin từ social platforms

### 4. HỆ THỐNG BOT VÀ TỰ ĐỘNG HOÁ
#### 4.1 Bot Management
- **Bot Creation/Configuration**: Tạo và cấu hình bot
- **Multi-type Bots**: Message bot, Comment bot, Post bot
- **Bot Status Control**: Bật/tắt bot
- **Bot Connection**: Kết nối bot với social accounts/pages

#### 4.2 Identity Management (Nhân dạng)
- **Personality Definition**: Định nghĩa tính cách bot
- **Conversation Style**: Phong cách giao tiếp
- **Example Conversations**: Mẫu hội thoại
- **Default/Custom Identities**: Nhân dạng mặc định và tùy chỉnh

#### 4.3 Procedure Management (Quy trình)
- **Workflow Definition**: Định nghĩa quy trình xử lý
- **Step-by-step Procedures**: Các bước xử lý tuần tự
- **Conditional Logic**: Logic điều kiện trong quy trình
- **Default/Custom Procedures**: Quy trình mặc định và tùy chỉnh

#### 4.4 Knowledge Management
- **Knowledge Base**: Cơ sở tri thức cho bot
- **Document Integration**: Tích hợp tài liệu
- **Content Embedding**: Vector embedding cho semantic search
- **Knowledge Chunks**: Phân đoạn kiến thức để xử lý

### 5. HỆ THỐNG CRM HOÀN CHỈNH
#### 5.1 Company Management
- **Multi-company Support**: Hỗ trợ nhiều công ty
- **Company Profiles**: Thông tin công ty chi tiết
- **Industry Classification**: Phân loại theo ngành nghề
- **Company Hierarchy**: Cấu trúc tổ chức công ty

#### 5.2 Contact Management
- **Customer Management**: Quản lý khách hàng
- **Employee Management**: Quản lý nhân viên
- **Contact Segmentation**: Phân loại liên hệ
- **Contact Import/Export**: Nhập/xuất danh sách liên hệ
- **Contact History**: Lịch sử tương tác với liên hệ

#### 5.3 Product Management
- **Product Catalog**: Danh mục sản phẩm
- **SKU Management**: Quản lý mã sản phẩm
- **Pricing Management**: Quản lý giá
- **Media Gallery**: Thư viện hình ảnh sản phẩm
- **Product Import**: Import từ Excel/SQL
- **Product Categories**: Phân loại sản phẩm
- **Inventory Tracking**: Theo dõi tồn kho

#### 5.4 Warehouse Management
- **Multi-warehouse**: Hỗ trợ nhiều kho
- **Inventory Management**: Quản lý tồn kho
- **Location Tracking**: Theo dõi vị trí trong kho
- **Stock Movement**: Theo dõi xuất nhập kho
- **Low Stock Alerts**: Cảnh báo hết hàng

#### 5.5 Order Management
- **Order Creation**: Tạo đơn hàng (tự động từ chat + thủ công)
- **Order Processing**: Xử lý đơn hàng
- **Payment Integration**: Tích hợp thanh toán
- **Order Status Tracking**: Theo dõi trạng thái đơn hàng
- **Order History**: Lịch sử đơn hàng
- **Invoice Generation**: Tạo hóa đơn

#### 5.6 Shipment Management
- **Shipping Integration**: Tích hợp đơn vị vận chuyển
- **Tracking Number Management**: Quản lý mã vận đơn
- **Delivery Status**: Theo dõi trạng thái giao hàng
- **Shipping Cost Calculation**: Tính phí vận chuyển
- **Delivery History**: Lịch sử giao hàng

### 6. HỆ THỐNG QUẢN LÝ TÀI LIỆU VÀ KIẾN THỨC
- **Document Upload**: Upload file (PDF, DOC, DOCX, Excel, TXT)
- **Document Processing**: Xử lý và extract content
- **Document Categorization**: Phân loại tài liệu
- **Full-text Search**: Tìm kiếm toàn văn
- **Version Control**: Quản lý phiên bản tài liệu
- **Document Sharing**: Chia sẻ tài liệu

### 7. HỆ THỐNG LỊCH SỬ VÀ PHÂN TÍCH
- **Conversation History**: Lịch sử hội thoại
- **Analytics Dashboard**: Bảng điều khiển phân tích
- **Performance Metrics**: Các chỉ số hiệu suất
- **Usage Reports**: Báo cáo sử dụng
- **Customer Insights**: Thông tin khách hàng
- **Bot Performance**: Hiệu suất bot

### 8. HỆ THỐNG FEEDBACK VÀ HỖ TRỢ
- **User Feedback**: Phản hồi người dùng
- **Rating System**: Hệ thống đánh giá
- **Support Tickets**: Ticket hỗ trợ
- **FAQ Management**: Quản lý câu hỏi thường gặp
- **Help Documentation**: Tài liệu hướng dẫn

### 9. HỆ THỐNG THÔNG BÁO
- **Real-time Notifications**: Thông báo thời gian thực
- **Email Notifications**: Thông báo qua email
- **Push Notifications**: Thông báo đẩy
- **Notification Settings**: Cài đặt thông báo

### 10. HỆ THỐNG CẤU HÌNH VÀ BẢO MẬT
- **System Settings**: Cài đặt hệ thống
- **Security Settings**: Cài đặt bảo mật
- **API Key Management**: Quản lý API key
- **Backup & Restore**: Sao lưu và khôi phục
- **Audit Logs**: Nhật ký kiểm toán
