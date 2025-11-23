"""
Pydantic Models for SuperAdmin API
===================================
"""

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# ================================
# ENUMS
# ================================

class UserRole(str, Enum):
    """User roles trong hệ thống"""
    SUPER_ADMIN = "super_admin"
    WHITE_LABEL_ADMIN = "white_label_admin"
    PARTNER_ADMIN = "partner_admin"
    USER = "user"

class LicenseType(str, Enum):
    """Loại license"""
    WHITE_LABEL = "white_label"
    RESELLER = "reseller"
    TRIAL = "trial"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, Enum):
    """Trạng thái subscription"""
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"

# ================================
# REQUEST MODELS
# ================================

class CreateUserRequest(BaseModel):
    """Request tạo user mới"""
    name: str = Field(..., min_length=1, max_length=200, description="Tên user")
    email: EmailStr = Field(..., description="Email user")
    password: str = Field(..., min_length=6, description="Mật khẩu (tối thiểu 6 ký tự)")
    roles: List[str] = Field(default=["user"], description="Danh sách roles")
    parent_id: Optional[str] = Field(None, description="ID của parent user (để xây dựng hierarchy)")
    package_id: Optional[str] = Field(None, description="ID của package để gán cho user")
    subscription_months: Optional[int] = Field(None, ge=1, le=120, description="Số tháng subscription (1-120)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Nguyễn Văn A",
                "email": "nguyenvana@example.com",
                "password": "securepass123",
                "roles": ["user"],
                "parent_id": None,
                "package_id": "package123",
                "subscription_months": 12
            }
        }
    )

class UpdateUserRequest(BaseModel):
    """Request cập nhật user"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    avatar_url: Optional[str] = None
    package_id: Optional[str] = Field(None, description="ID của package để gán/thay đổi")
    extend_subscription_months: Optional[int] = Field(None, ge=1, le=120, description="Số tháng gia hạn thêm (1-120)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Nguyễn Văn A (Updated)",
                "roles": ["user", "partner_admin"],
                "package_id": "package456",
                "extend_subscription_months": 6
            }
        }
    )

class CreateWhiteLabelRequest(BaseModel):
    """Request tạo White Label partner"""
    company_name: str = Field(..., description="Tên công ty")
    contact_name: str = Field(..., description="Tên người liên hệ")
    contact_email: EmailStr = Field(..., description="Email liên hệ")
    password: str = Field(..., min_length=6)
    domain: Optional[str] = Field(None, description="Domain của công ty")
    license_config: Optional[Dict[str, Any]] = Field(default={}, description="Cấu hình license")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "company_name": "ABC Technology",
                "contact_name": "Trần Văn B",
                "contact_email": "tran.b@abc.com",
                "password": "securepass123",
                "domain": "abc.com",
                "license_config": {
                    "max_users": 100,
                    "revenue_share_percentage": 20.0
                }
            }
        }
    )

class CreatePackageRequest(BaseModel):
    """Request tạo package mới"""
    name: str = Field(..., description="Tên package")
    price: float = Field(..., ge=0, description="Giá (VND)")
    description: Optional[str] = Field(None, description="Mô tả package")
    features: Dict[str, bool] = Field(..., description="Features enabled")
    limits: Dict[str, Any] = Field(..., description="Giới hạn sử dụng")
    duration_months: int = Field(default=1, ge=1, description="Thời hạn (tháng)")
    target_users: Optional[List[str]] = Field(None, description="Danh sách user_ids được phép thấy package này (None = tất cả users trong hierarchy)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Premium",
                "price": 999000,
                "description": "Gói Premium với nhiều tính năng",
                "features": {
                    "dashboard": True,
                    "bot": True,
                    "knowledge": True
                },
                "limits": {
                    "messages_per_month": 10000,
                    "bot": 50,
                    "social": 5
                },
                "duration_months": 1,
                "target_users": ["user123", "user456"]
            }
        }
    )

class UpdatePackageRequest(BaseModel):
    """Request cập nhật package"""
    name: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None
    features: Optional[Dict[str, bool]] = None
    limits: Optional[Dict[str, Any]] = None
    duration_months: Optional[int] = Field(None, ge=1)
    target_users: Optional[List[str]] = Field(None, description="Danh sách user_ids được phép thấy package (None = reset về mặc định)")

class CreateAPIKeyRequest(BaseModel):
    """Request tạo API Key"""
    owner_id: str = Field(..., description="ID của owner (user hoặc partner)")
    owner_type: str = Field(..., description="Loại owner: white_label, partner, user")
    name: str = Field(..., description="Tên mô tả cho API key")
    permissions: List[str] = Field(default=["read"], description="Danh sách permissions")
    expires_at: Optional[datetime] = Field(None, description="Thời gian hết hạn (None = không hết hạn)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "owner_id": "user123",
                "owner_type": "white_label",
                "name": "Production API Key",
                "permissions": ["read", "write", "webhook"],
                "expires_at": None
            }
        }
    )

class AssignRoleRequest(BaseModel):
    """Request gán role cho user"""
    user_id: str = Field(..., description="ID user")
    role: str = Field(..., description="Role cần gán")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user123",
                "role": "partner_admin"
            }
        }
    )

class UpdateSubscriptionRequest(BaseModel):
    """Request cập nhật subscription"""
    status: Optional[str] = Field(None, description="Trạng thái mới: active, expired, cancelled")
    expiry_date: Optional[datetime] = Field(None, description="Ngày hết hạn mới")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "active",
                "expiry_date": "2025-12-31T23:59:59"
            }
        }
    )

class WebhookEventRequest(BaseModel):
    """Request từ White Label system gửi webhook"""
    event_type: str = Field(..., description="Loại event: user_created, bot_created, message_sent, etc.")
    payload: Dict[str, Any] = Field(..., description="Dữ liệu payload")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "user_created",
                "payload": {
                    "user_id": "wl_user_123",
                    "email": "user@example.com",
                    "name": "New User",
                    "created_at": "2025-01-07T10:00:00Z"
                }
            }
        }
    )

# ================================
# RESPONSE MODELS
# ================================

class UserResponse(BaseModel):
    """Response user info"""
    id: str = Field(..., alias="_id")
    name: str
    email: str
    roles: List[str]
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    email_verified: bool = False
    
    model_config = ConfigDict(populate_by_name=True)

class HierarchyInfoResponse(BaseModel):
    """Response hierarchy info"""
    user_id: str
    parent: Optional[str] = None
    children: List[str] = []
    hierarchy_type: str = "user"
    depth: int = 0
    total_descendants: int = 0

class PackageResponse(BaseModel):
    """Response package info"""
    id: str = Field(..., alias="_id")
    name: str
    price: float
    description: Optional[str] = None
    features: Dict[str, bool]
    limits: Dict[str, Any]
    duration_months: int
    created_at: datetime
    
    model_config = ConfigDict(populate_by_name=True)

class APIKeyResponse(BaseModel):
    """Response API Key info"""
    id: str = Field(..., alias="_id")
    owner_id: str
    owner_type: str
    name: str
    permissions: List[str]
    status: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    api_key: Optional[str] = None  # Chỉ hiển thị khi tạo mới
    
    model_config = ConfigDict(populate_by_name=True)

class SystemStatsResponse(BaseModel):
    """Response thống kê hệ thống"""
    total_users: int
    total_white_labels: int
    total_partners: int
    total_active_bots: int
    total_messages_today: int
    total_revenue_month: float
    active_subscriptions: int

class WhiteLabelStatsResponse(BaseModel):
    """Response thống kê White Label"""
    partner_id: str
    company_name: str
    total_users: int
    active_users: int
    total_revenue: float
    total_messages: int
    created_at: datetime

class ErrorResponse(BaseModel):
    """Response lỗi"""
    error: str
    detail: Optional[str] = None
    status_code: int
