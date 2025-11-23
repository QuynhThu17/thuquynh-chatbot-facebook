# MekongAI SuperAdmin & White Label System

## Tổng Quan

Hệ thống MekongAI Social được thiết kế để phục vụ **2 mục đích chính**:

1. **Sử dụng trực tiếp**: MekongAI cung cấp dịch vụ cho khách hàng end-user
2. **White Label**: Chuyển giao hoàn toàn cho đối tác để họ tự vận hành

### Kiến Trúc Hierarchy

```
MekongAI SuperAdmin (Level 0)
├── White Label Partner A (Level 1)
│   ├── Partner A1 (Level 2) 
│   │   ├── User A1-1 (Level 3)
│   │   └── User A1-2 (Level 3)
│   └── User A-1 (Level 2)
├── White Label Partner B (Level 1)
│   └── Partner B1 (Level 2)
│       └── User B1-1 (Level 3)
└── Direct Customer (Level 1)
    └── Direct User (Level 2)
```

## Các Vai Trò (Roles)

### 1. SuperAdmin (MekongAI)
- **Quyền hạn**: Toàn quyền kiểm soát hệ thống
- **Chức năng**: 
  - Tạo và quản lý White Label partners
  - Theo dõi tất cả dữ liệu trong hệ thống
  - Quản lý licenses và billing
  - System monitoring và analytics
- **API riêng**: `/mekongai-internal-api/super-admin/`

### 2. White Label Admin
- **Quyền hạn**: Toàn quyền trong hệ thống con được chuyển giao
- **Chức năng**:
  - Tự quản lý branding và customization
  - Tạo partners con và users
  - Quản lý billing cho khách hàng
  - Truy cập full features
- **Hạn chế**: Phải báo cáo dữ liệu về MekongAI

### 3. Partner Admin (Reseller)
- **Quyền hạn**: Quản lý customers và bán packages
- **Chức năng**:
  - Tạo và quản lý end-users
  - Bán packages cho customers
  - Theo dõi doanh thu và commission
  - Một số features bị hạn chế
- **Hạn chế**: Không thể custom branding, phải báo cáo về parent

### 4. System Admin
- **Quyền hạn**: Admin trong tổ chức của mình
- **Chức năng**: Quản lý users và settings trong tổ chức
- **Hạn chế**: Không có quyền tạo partners

### 5. Enterprise/Professional/Starter Users
- **Quyền hạn**: Dựa theo gói đã mua
- **Chức năng**: Sử dụng bot, CRM, v.v. theo giới hạn gói

## Hệ thống Database

### Collections Mới

#### hierarchy (Mở rộng)
```javascript
{
  hierarchy_id: ObjectId,
  user_id: "user_id",
  parent: "parent_user_id",
  children: ["child1_id", "child2_id"],
  hierarchy_type: "super_admin|white_label_admin|partner_admin|system_admin|user",
  license_type: "white_label|reseller|trial",
  partner_info: {
    contact_person: "string",
    phone: "string", 
    company_info: {},
    max_users: number,
    max_revenue_share: number,
    custom_branding: boolean,
    allowed_features: [],
    restricted_features: [],
    status: "active|inactive|suspended",
    setup_completed: boolean
  },
  revenue_tracking: {
    total_revenue: number,
    this_month: number,
    last_month: number,
    currency: "VND"
  },
  usage_stats: {
    total_users: number,
    active_bots: number,
    total_messages: number,
    storage_used_mb: number
  },
  create_at: Date,
  update_at: Date
}
```

#### partner_licenses
```javascript
{
  license_id: ObjectId,
  partner_id: "user_id",
  license_type: "white_label|reseller|trial",
  status: "active|expired|suspended",
  config: {},
  usage_limits: {
    max_users: number,
    max_monthly_revenue: number,
    allowed_features: [],
    restricted_features: []
  },
  billing: {
    revenue_share_percentage: number,
    monthly_fee: number,
    setup_fee: number
  },
  created_at: Date,
  expires_at: Date
}
```

#### system_monitoring
```javascript
{
  event_id: ObjectId,
  event_type: "string",
  source: "string",
  data: {},
  timestamp: Date,
  severity: "info|warning|error|critical"
}
```

## SuperAdmin API

### Authentication
- **Header**: `X-MekongAI-SuperAdmin-Key: mekongai_super_2024_prod_key_v1`
- **Base URL**: `/mekongai-internal-api/super-admin/`

### Main Endpoints

#### Partner Management
```http
POST /partners                          # Tạo đối tác mới
GET  /partners                          # Danh sách đối tác
GET  /partners/{partner_id}             # Chi tiết đối tác  
PUT  /partners/{partner_id}             # Cập nhật đối tác
```

#### Hierarchy Management  
```http
GET  /hierarchy/tree                    # Cây hierarchy đầy đủ
GET  /hierarchy/tree?root_id={id}       # Từ node cụ thể
```

#### Analytics & Monitoring
```http
GET  /analytics/system                  # Thống kê tổng hệ thống
GET  /analytics/partners/{partner_id}   # Thống kê đối tác
```

#### Data Synchronization
```http
POST /sync/partner-data                 # Sync dữ liệu từ đối tác
```

## Quy Trình Chuyển Giao White Label

### 1. Tạo White Label Partner
```python
# Sử dụng SuperAdmin API
POST /mekongai-internal-api/super-admin/partners
{
  "name": "ABC Technology",
  "email": "admin@abc-tech.com",
  "contact_person": "John Doe",
  "hierarchy_type": "white_label_admin",
  "license_type": "white_label",
  "custom_branding": true,
  "max_users": -1
}
```

### 2. Setup Partner
- Partner nhận email với thông tin login
- Đổi password và setup profile
- Cấu hình branding và domain
- Test API integration
- Go live

### 3. Data Sync Requirements
Partner **PHẢI** implement các API để sync dữ liệu về MekongAI:

```http
# Partner phải gọi định kỳ
POST /mekongai-internal-api/super-admin/sync/partner-data
{
  "partner_id": "xxx",
  "data_type": "user_data|billing_data|usage_data",
  "data": {...}
}
```

## Initialization & Setup

### 1. Khởi tạo hệ thống
```bash
# Khởi tạo toàn bộ hệ thống (chỉ chạy lần đầu)
python init_super_admin_cli.py init-system
```

### 2. Tạo đối tác mới
```bash  
# Interactive partner creation
python init_super_admin_cli.py create-partner
```

### 3. Xem hierarchy
```bash
# Hiển thị cây hierarchy
python init_super_admin_cli.py show-hierarchy
```

### 4. Reset hệ thống
```bash
# NGUY HIỂM: Xóa toàn bộ dữ liệu
python init_super_admin_cli.py reset-system
```

## Security & Best Practices

### SuperAdmin Security
- [ ] Đổi password mặc định ngay lập tức
- [ ] Enable 2FA cho SuperAdmin account
- [ ] Hạn chế truy cập SuperAdmin API theo IP
- [ ] Monitor tất cả SuperAdmin activities
- [ ] Regular backup toàn bộ database

### API Key Management
- [ ] Rotate SuperAdmin API keys định kỳ
- [ ] Sử dụng HTTPS cho tất cả API calls
- [ ] Implement rate limiting
- [ ] Log tất cả API requests

### Data Privacy & Compliance
- [ ] Encrypt sensitive data
- [ ] Implement data retention policies
- [ ] GDPR compliance cho EU customers
- [ ] Regular security audits

## Monitoring & Analytics

### System Health
- Uptime monitoring
- Performance metrics
- Error rates
- Resource usage

### Business Metrics
- Total partners & users
- Revenue tracking
- Growth rates
- Feature usage

### Alerts & Notifications
- System downtime
- High error rates
- Unusual activity patterns
- Revenue anomalies

## Development Workflow

### 1. Local Development
```bash
# Start development server
python app.py

# Initialize development data
python init_super_admin_cli.py init-system
```

### 2. Testing
```bash
# Test SuperAdmin APIs
curl -H "X-MekongAI-SuperAdmin-Key: mekongai_super_2024_dev_key_v1" \
     http://localhost:1945/mekongai-internal-api/super-admin/health
```

### 3. Production Deployment
- [ ] Update SuperAdmin credentials
- [ ] Configure production MongoDB
- [ ] Setup SSL certificates
- [ ] Configure monitoring
- [ ] Deploy with proper security

---

## 🚨 Important Notes

1. **SuperAdmin API không được expose ra public**
2. **Tất cả đối tác PHẢI báo cáo dữ liệu về MekongAI**
3. **Regular backup và disaster recovery plan**
4. **Monitor security logs thường xuyên**
5. **Tuân thủ data protection regulations**
