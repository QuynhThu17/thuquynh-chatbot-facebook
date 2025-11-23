"""
MekongAI SuperAdmin Management API - COMPLETE VERSION
======================================================
🚀 HỆ THỐNG QUẢN LÝ ĐA TẦNG HOÀN CHỈNH

Chức năng:
1. 👥 User Management - Quản lý tất cả users (CRUD, roles, hierarchy)
2. 🏢 White Label Management - Quản lý đối tác White Label
3. 📦 Package Management - Quản lý gói dịch vụ
4. 💳 Subscription Management - Quản lý subscriptions
5. 🔑 API Key Management - Quản lý API keys cho White Label
6. 📊 Analytics & Statistics - Thống kê toàn hệ thống
7. 🔗 Webhook Management - Nhận dữ liệu từ White Label systems
8. ⚙️ Settings Management - Quản lý settings

🔒 Bảo mật:
- JWT Authentication
- Role-based access control (RBAC)
- Hierarchy-based permissions
- API Key authentication cho webhooks
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Header, status
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

from configs.environment import get_vietnam_now_naive
from configs import environment
from bson import ObjectId
from bson.errors import InvalidId

# Import models
from .models import (
    # Request models
    CreateUserRequest, UpdateUserRequest, CreateWhiteLabelRequest,
    CreatePackageRequest, UpdatePackageRequest, CreateAPIKeyRequest,
    AssignRoleRequest, UpdateSubscriptionRequest, WebhookEventRequest,
    # Response models
    UserResponse, HierarchyInfoResponse, PackageResponse, APIKeyResponse,
    SystemStatsResponse, WhiteLabelStatsResponse, ErrorResponse,
    # Enums
    UserRole, LicenseType, SubscriptionStatus
)

# Import managers and middlewares
from controllers.data.managements import get_mongodb_factory
from controllers.data.init_defaults import get_default_initializer
from controllers.auth.superadmin_middleware import (
    require_super_admin,
    require_white_label_or_super,
    get_current_user_permissions,
    verify_api_key,
    check_user_permission,
    PermissionChecker
)
from controllers.auth.auth_service import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/super-admin", tags=["🔒 MekongAI SuperAdmin"])

def _normalize_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(environment.vietnam_tz).replace(tzinfo=None)
    return dt

def _safe_object_id(value: Optional[str]) -> Optional[ObjectId]:
    if not value:
        return None
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None

# ================================
# 👥 USER MANAGEMENT
# ================================

@router.get("/users", summary="Lấy danh sách users")
async def get_all_users(
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua (pagination)"),
    limit: int = Query(50, ge=1, le=1000, description="Số lượng users tối đa trả về (max 1000)"),
    role: Optional[str] = Query(None, description="Lọc theo role: super_admin, white_label_admin, partner_admin, user"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên hoặc email (case-insensitive regex)"),
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    📋 **Lấy danh sách users với filtering và pagination**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Xem TẤT CẢ users trong toàn bộ hệ thống (không giới hạn)
    - 🏢 **White Label Admin**: Xem TẤT CẢ users trong hệ thống của họ (bao gồm Partner Admins và End Users)
    
    **Query Parameters:**
    - `skip`: Số lượng bản ghi bỏ qua (dùng cho pagination)
    - `limit`: Số lượng users tối đa trả về (1-1000, mặc định 50)
    - `role`: Lọc theo role cụ thể (super_admin, white_label_admin, partner_admin, user)
    - `search`: Tìm kiếm theo tên hoặc email (regex không phân biệt hoa thường)
    
    **Response:**
    - Danh sách users với thông tin đầy đủ (bao gồm hierarchy info)
    - Mỗi user có: _id, name, email, roles, create_at, hierarchy
    
    **Business Logic:**
    - White Label Admin = Super Admin trong hệ thống của họ (full access)
    - Kết quả được filter theo hierarchy tree (recursive children)
    - Sort theo thời gian tạo (mới nhất trước)
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        filter_query = {}
        if role:
            filter_query["roles"] = role
        if search:
            filter_query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        
        # CHỈ MekongAI Super Admin mới xem tất cả
        # White Label Admin chỉ xem hệ thống của họ
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            # White Label: Lấy TẤT CẢ users trong hierarchy của họ
            children = await factory.super_hierarchy_manager.get_children_recursive(current_user_id)
            allowed_user_ids = [current_user_id] + [child["user_id"] for child in children]
            filter_query["_id"] = {"$in": allowed_user_ids}
        # Super Admin: Không filter gì cả -> xem tất cả
        
        users = await factory.user_manager.get_all(
            filter_query=filter_query,
            skip=skip,
            limit=limit,
            sort_by="create_at",
            sort_order=-1
        )
        
        for user in users:
            user["_id"] = str(user["_id"])
            hierarchy = await factory.hierarchy_manager.get_by_user_id(str(user["_id"]))
            user["hierarchy"] = hierarchy if hierarchy else None
        
        return users
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}", summary="Lấy chi tiết user")
async def get_user_detail(
    user_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    🔍 **Lấy thông tin đầy đủ của user cụ thể**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Xem bất kỳ user nào trong hệ thống
    - 🏢 **White Label Admin**: Chỉ xem users trong hierarchy của mình (bao gồm chính họ)
    
    **Path Parameters:**
    - `user_id`: ID của user cần lấy thông tin
    
    **Response:**
    - `user`: Thông tin user đầy đủ (name, email, roles, avatar, is_active, create_at)
    - `hierarchy`: Thông tin hierarchy (parent, children, level, license_type)
    - `subscriptions`: Danh sách subscriptions đang active
    - `balance`: Số dư tài khoản hiện tại
    - `statistics`: Thống kê (total_bots, total_social_accounts)
    
    **Business Logic:**
    - White Label Admin phải check hierarchy trước khi truy cập
    - Return 403 nếu user_id không nằm trong hierarchy
    - Super Admin bypass tất cả các kiểm tra
    
    **Errors:**
    - `404`: User not found
    - `403`: Không có quyền xem user này (ngoài hierarchy)
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # KIỂM TRA HIERARCHY: Nếu KHÔNG phải Super Admin
        if not permissions.get("is_super_admin"):
            # Kiểm tra user_id có trong hierarchy không
            if user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, user_id, factory
                )
                if not has_access:
                    raise HTTPException(
                        status_code=403, 
                        detail="You don't have permission to view this user"
                    )
        
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user["_id"] = str(user["_id"])
        hierarchy = await factory.hierarchy_manager.get_by_user_id(user_id)
        subscriptions = await factory.subscription_manager.get_by_user_id(user_id, status="active")
        balance = await factory.balance_manager.get_by_user_id(user_id)
        bots = await factory.bot_manager.get_by_user_id(user_id)
        social_accounts = await factory.social_account_manager.get_by_user_id(user_id)
        
        return {
            "user": user,
            "hierarchy": hierarchy,
            "subscriptions": subscriptions,
            "balance": balance,
            "statistics": {
                "total_bots": len(bots) if bots else 0,
                "total_social_accounts": len(social_accounts) if social_accounts else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Tạo user mới")
async def create_user(
    request: CreateUserRequest,
    background_tasks: BackgroundTasks,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    ➕ **Tạo user mới với hierarchy và khởi tạo dữ liệu mặc định**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Tạo bất kỳ user nào với bất kỳ role nào (không giới hạn)
    - 🏢 **White Label Admin**: FULL quyền tạo users trong hệ thống của họ:
      - ✅ Tạo Partner Admins
      - ✅ Tạo End Users
      - ❌ KHÔNG tạo Super Admin
      - ❌ KHÔNG tạo White Label Admin khác
    
    **Request Body:**
    - `name`: Tên đầy đủ của user
    - `email`: Email (unique, sẽ được validate)
    - `password`: Mật khẩu (sẽ được hash)
    - `roles`: Array các roles (super_admin, white_label_admin, partner_admin, user)
    - `parent_id`: (Optional) ID của parent trong hierarchy, mặc định là current user
    - `package_id`: (Optional) ID của package để gán cho user ngay khi tạo
    - `subscription_months`: (Optional) Số tháng subscription (1-120), mặc định dùng duration của package
    
    **Response:**
    - `message`: Thông báo thành công
    - `user`: Thông tin user vừa tạo (_id, name, email, roles)
    - `subscription`: (Nếu có package_id) Thông tin subscription vừa tạo
    
    **Background Tasks:**
    - Khởi tạo defaults: packages, balances, limits, settings
    - Tạo hierarchy relationship với parent
    - Tạo subscription nếu có package_id
    - Gửi email verification (nếu cấu hình)
    
    **Business Logic:**
    - Email phải unique trong toàn hệ thống
    - Password được hash bằng bcrypt
    - White Label Admin bị chặn tạo super_admin và white_label_admin roles
    - Parent_id phải nằm trong hierarchy của White Label (nếu không phải Super Admin)
    
    **Errors:**
    - `400`: Email already exists
    - `403`: White Label cannot create super_admin or white_label_admin
    - `403`: Parent_id ngoài hierarchy của White Label
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Xác định parent_id
        if request.parent_id:
            parent_id = request.parent_id
            # White Label phải kiểm tra parent trong hierarchy của họ
            if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, parent_id, factory
                )
                if not has_access and parent_id != current_user_id:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only create users under your hierarchy"
                    )
        else:
            # Nếu không chỉ định parent -> parent = current user
            parent_id = current_user_id
            if not parent_id:
                parent_id = "68ca1ed879de6857964de65f"
        
        # KIỂM TRA ROLES: 
        # - Super Admin: Tạo bất kỳ role nào
        # - White Label Admin: FULL quyền NGOẠI TRỪ super_admin và white_label_admin
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            forbidden_roles = ["super_admin", "white_label_admin"]
            if any(role in request.roles for role in forbidden_roles):
                raise HTTPException(
                    status_code=403,
                    detail="White Label Admin cannot create super_admin or other white_label_admin. You can create: partner_admin, user"
                )
        
        existing_user = await factory.user_manager.get_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Validate package nếu có
        subscription_data = None
        if request.package_id:
            package = await factory.package_manager.get_by_id(request.package_id)
            if not package:
                raise HTTPException(status_code=404, detail="Package not found")
            
            # Kiểm tra quyền truy cập package
            if not permissions.get("is_super_admin"):
                # White Label chỉ assign packages của họ hoặc global packages
                if package.get("created_by") != current_user_id and package.get("owner_type") != "super_admin":
                    raise HTTPException(status_code=403, detail="You cannot assign this package")
                
                # Kiểm tra target_users nếu có
                target_users = package.get("target_users")
                if target_users and len(target_users) > 0:
                    # Package có target_users cụ thể -> chỉ Super Admin hoặc creator mới assign được
                    if package.get("created_by") != current_user_id:
                        raise HTTPException(status_code=403, detail="This package is restricted to specific users")
        
        hashed_password = auth_service.hash_password(request.password)
        user = await factory.user_manager.create_user(
            name=request.name,
            email=request.email,
            password=hashed_password,
            roles=request.roles,
            email_verified=True
        )
        
        user_id = str(user["_id"])
        
        # Tạo subscription nếu có package_id VÀ subscription_months > 0
        subscription_data = None
        if request.package_id and request.subscription_months and request.subscription_months > 0:
            months = request.subscription_months
            
            subscription = await factory.subscription_manager.create_subscription(
                user_id=user_id,
                package_id=request.package_id,
                start_day=get_vietnam_now_naive(),
                duration_months=months,
                is_auto_renew=False
            )
            subscription_data = subscription
            
            # Khởi tạo limits từ package
            package_limits = package.get("limits", {})
            user_limits = {}
            for limit_key, limit_value in package_limits.items():
                user_limits[limit_key] = {
                    "total": limit_value,
                    "used": 0,
                    "remaining": limit_value if limit_value != -1 else -1
                }
            
            # Cập nhật current_package, features VÀ limits cho user
            await factory.user_manager.update_by_id(user_id, {
                "packages": request.package_id,
                "current_package": request.package_id,
                "package_name": package.get("name", ""),
                "package_expires_at": subscription["end_day"],
                "features": package.get("features", {}),  # Copy features từ package
                "limits": user_limits  # Copy limits từ package
            })
            
            # ✅ Nếu là custom package, thêm user_id vào target_users của package
            package_type = package.get("type", "default")
            target_users = package.get("target_users", [])
            
            # Danh sách default system packages (không track target_users)
            system_packages = ["p_free_trial", "p_basic", "p_professional", "p_enterprise"]
            is_system_package = request.package_id in system_packages
            
            logger.info(f"Package: {request.package_id}, type: {package_type}, target_users: {target_users}, is_system: {is_system_package}")
            
            # Chỉ track target_users cho NON-SYSTEM packages (custom packages)
            if not is_system_package:
                # Đây là custom package -> Thêm user_id vào target_users nếu chưa có
                if user_id not in target_users:
                    target_users.append(user_id)
                    # ✅ Update bằng _id của package (có thể là ObjectId hoặc string)
                    package_object_id = package.get("_id")
                    await factory.package_manager.collection.update_one(
                        {"_id": package_object_id},
                        {"$set": {
                            "target_users": target_users,
                            "type": "custom",
                            "update_at": get_vietnam_now_naive()
                        }}
                    )
                    logger.info(f"✅ Added user {user_id} to custom package {request.package_id} (ID: {package_object_id}) target_users")
                else:
                    logger.info(f"⚠️ User {user_id} already in target_users of package {request.package_id}")
            else:
                logger.info(f"⏭️ Skipping target_users update for system package {request.package_id}")

            
            logger.info(f"✅ Created subscription for user {user_id}: package={request.package_id}, months={months}")
        elif request.package_id:
            # Chỉ có package_id nhưng không có subscription_months hoặc = 0
            # => Gán package nhưng không tạo subscription (user có thể thấy package trong list)
            
            # Khởi tạo limits từ package
            package_limits = package.get("limits", {})
            user_limits = {}
            for limit_key, limit_value in package_limits.items():
                user_limits[limit_key] = {
                    "total": limit_value,
                    "used": 0,
                    "remaining": limit_value if limit_value != -1 else -1
                }
            
            await factory.user_manager.update_by_id(user_id, {
                "packages": request.package_id,
                "current_package": request.package_id,
                "package_name": package.get("name", ""),
                "features": package.get("features", {}),  # Copy features từ package
                "limits": user_limits  # Copy limits từ package
            })
            
            # ✅ Nếu là custom package, thêm user_id vào target_users của package
            package_type = package.get("type", "default")
            target_users = package.get("target_users", [])
            
            # Danh sách default system packages (không track target_users)
            system_packages = ["p_free_trial", "p_basic", "p_professional", "p_enterprise"]
            is_system_package = request.package_id in system_packages
            
            # Chỉ track target_users cho NON-SYSTEM packages (custom packages)
            if not is_system_package:
                # Đây là custom package -> Thêm user_id vào target_users nếu chưa có
                if user_id not in target_users:
                    target_users.append(user_id)
                    # ✅ Update bằng _id của package (có thể là ObjectId hoặc string)
                    package_object_id = package.get("_id")
                    await factory.package_manager.collection.update_one(
                        {"_id": package_object_id},
                        {"$set": {
                            "target_users": target_users,
                            "type": "custom",
                            "update_at": get_vietnam_now_naive()
                        }}
                    )
                    logger.info(f"✅ Added user {user_id} to custom package {request.package_id} (ID: {package_object_id}) target_users")
            
            logger.info(f"✅ Assigned package {request.package_id} to user {user_id} without subscription")
        
        # QUAN TRỌNG: Gọi initialize_user_data SAU KHI đã set package
        # Để tránh bị ghi đè bởi p_free_trial
        background_tasks.add_task(initialize_user_data, user_id=user_id, parent_id=parent_id)
        
        response = {
            "message": "User created successfully",
            "user": {
                "_id": user_id,
                "name": user["name"],
                "email": user["email"],
                "roles": user["roles"]
            }
        }
        
        if subscription_data:
            response["subscription"] = {
                "_id": str(subscription_data["_id"]),
                "package_id": str(subscription_data["package_id"]),
                "start_day": subscription_data["start_day"].isoformat(),
                "end_day": subscription_data["end_day"].isoformat()
            }
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/{user_id}", summary="Cập nhật user")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    ✏️ **Cập nhật thông tin user (partial update)**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Update bất kỳ user nào trong hệ thống
    - 🏢 **White Label Admin**: Chỉ update users trong hierarchy của mình
    
    **Path Parameters:**
    - `user_id`: ID của user cần cập nhật
    
    **Request Body (tất cả optional):**
    - `name`: Tên mới của user
    - `email`: Email mới (phải unique)
    - `roles`: Array roles mới (có giới hạn với White Label)
    - `avatar_url`: URL avatar mới
    - `is_active`: Trạng thái active (true/false)
    - `package_id`: Gán package mới hoặc thay đổi package hiện tại
    - `extend_subscription_months`: Gia hạn thêm số tháng (1-120)
    
    **Response:**
    - `message`: Thông báo thành công
    - `user`: Thông tin user sau khi update
    - `subscription`: (Nếu có thay đổi package/gia hạn) Thông tin subscription mới
    
    **Business Logic:**
    - Chỉ update các fields được gửi lên (partial update)
    - Email mới phải unique (trừ chính user đó)
    - White Label Admin KHÔNG thể assign super_admin hoặc white_label_admin roles
    - White Label Admin phải check hierarchy trước khi update
    - Nếu có package_id: Tạo subscription mới hoặc update subscription hiện tại
    - Nếu có extend_subscription_months: Gia hạn subscription active (cộng thêm tháng)
    
    **Errors:**
    - `404`: User not found
    - `400`: Email already exists (duplicate)
    - `403`: Không có quyền update user này (ngoài hierarchy)
    - `403`: White Label cannot assign super_admin or white_label_admin roles
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # KIỂM TRA HIERARCHY: Nếu KHÔNG phải Super Admin
        if not permissions.get("is_super_admin"):
            if user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, user_id, factory
                )
                if not has_access:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only update users in your hierarchy"
                    )
            
            # KIỂM TRA ROLES: White Label không được gán super_admin hoặc white_label_admin
            if request.roles:
                forbidden_roles = ["super_admin", "white_label_admin"]
                if any(role in request.roles for role in forbidden_roles):
                    raise HTTPException(
                        status_code=403,
                        detail="You cannot assign super_admin or white_label_admin roles"
                    )
        
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        update_data = {}
        if request.name is not None:
            update_data["name"] = request.name
        if request.email is not None:
            existing = await factory.user_manager.get_by_email(request.email)
            if existing and str(existing["_id"]) != user_id:
                raise HTTPException(status_code=400, detail="Email already exists")
            update_data["email"] = request.email
        if request.roles is not None:
            update_data["roles"] = request.roles
        if request.avatar_url is not None:
            update_data["avatar_url"] = request.avatar_url
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        
        updated_user = await factory.user_manager.update_by_id(user_id, update_data)
        
        # Xử lý package và subscription
        subscription_data = None
        
        # Nếu có package_id: Tạo/update subscription
        if request.package_id:
            package = await factory.package_manager.get_by_id(request.package_id)
            if not package:
                raise HTTPException(status_code=404, detail="Package not found")
            
            # Kiểm tra quyền truy cập package
            if not permissions.get("is_super_admin"):
                if package.get("created_by") != current_user_id and package.get("owner_type") != "super_admin":
                    raise HTTPException(status_code=403, detail="You cannot assign this package")
                
                target_users = package.get("target_users")
                if target_users and len(target_users) > 0:
                    if package.get("created_by") != current_user_id:
                        raise HTTPException(status_code=403, detail="This package is restricted to specific users")
            
            # Lấy active subscription hiện tại
            active_subs = await factory.subscription_manager.get_by_user_id(user_id, status="active")
            
            if active_subs and len(active_subs) > 0:
                # Cancel subscriptions cũ
                for sub in active_subs:
                    await factory.subscription_manager.update_by_id(
                        str(sub["_id"]),
                        {"status": "cancelled"}
                    )
            
            # Tạo subscription mới
            months = package.get("duration_months", 1)
            
            subscription = await factory.subscription_manager.create_subscription(
                user_id=user_id,
                package_id=request.package_id,
                start_day=get_vietnam_now_naive(),
                duration_months=months,
                is_auto_renew=False
            )
            subscription_data = subscription
            
            # ✅ Cập nhật package, features và limits cho user
            package_limits = package.get("limits", {})
            user_limits = {}
            for limit_key, limit_value in package_limits.items():
                user_limits[limit_key] = {
                    "total": limit_value,
                    "used": 0,
                    "remaining": limit_value if limit_value != -1 else -1
                }
            
            await factory.user_manager.update_by_id(user_id, {
                "packages": request.package_id,
                "current_package": request.package_id,
                "package_name": package.get("name", ""),
                "package_expires_at": subscription["end_day"],
                "features": package.get("features", {}),
                "limits": user_limits
            })
            
            # ✅ Nếu là custom package, thêm user_id vào target_users của package
            package_type = package.get("type", "default")
            target_users = package.get("target_users", [])
            
            # Danh sách default system packages (không track target_users)
            system_packages = ["p_free_trial", "p_basic", "p_professional", "p_enterprise"]
            is_system_package = request.package_id in system_packages
            
            # Chỉ track target_users cho NON-SYSTEM packages (custom packages)
            if not is_system_package:
                if user_id not in target_users:
                    target_users.append(user_id)
                    # ✅ Update bằng _id của package (có thể là ObjectId hoặc string)
                    package_object_id = package.get("_id")
                    await factory.package_manager.collection.update_one(
                        {"_id": package_object_id},
                        {"$set": {
                            "target_users": target_users,
                            "type": "custom",
                            "update_at": get_vietnam_now_naive()
                        }}
                    )
                    logger.info(f"✅ Added user {user_id} to custom package {request.package_id} (ID: {package_object_id}) target_users")
            
            logger.info(f"✅ Updated user {user_id} with package {request.package_id}, subscription created")
        
        # Nếu có extend_subscription_months: Gia hạn subscription active
        elif request.extend_subscription_months:
            active_subs = await factory.subscription_manager.get_by_user_id(user_id, status="active")
            
            if not active_subs or len(active_subs) == 0:
                raise HTTPException(status_code=400, detail="No active subscription to extend")
            
            # Gia hạn subscription đầu tiên (hoặc có thể gia hạn tất cả)
            sub = active_subs[0]
            current_end_day = sub.get("end_day")
            
            # ✅ FIX: Tính đúng số tháng (không phải 30 ngày mà là cộng tháng thực)
            # Nếu end_day đã qua, tính từ now, nếu chưa qua thì cộng thêm
            now = get_vietnam_now_naive()
            base_date = max(current_end_day, now) if current_end_day else now
            
            # Cộng tháng đúng (30 hoặc 31 ngày tùy tháng)
            new_end_day = base_date + relativedelta(months=request.extend_subscription_months)
            
            updated_sub = await factory.subscription_manager.update_by_id(
                str(sub["_id"]),
                {
                    "end_day": new_end_day,
                    "status": "active"  # Kích hoạt lại nếu đã expired
                }
            )
            subscription_data = updated_sub
            
            # ✅ Cập nhật package_expires_at cho user
            await factory.user_manager.update_by_id(user_id, {
                "package_expires_at": new_end_day
            })
        
        # ✅ FIX: Fetch lại user từ DB để có dữ liệu mới nhất (sau khi update subscription/package)
        updated_user = await factory.user_manager.get_by_id(user_id)
        
        response = {"message": "User updated successfully", "user": updated_user}
        
        if subscription_data:
            response["subscription"] = {
                "_id": str(subscription_data["_id"]),
                "package_id": str(subscription_data["package_id"]),
                "status": subscription_data["status"],
                "start_day": subscription_data["start_day"].isoformat() if subscription_data.get("start_day") else None,
                "end_day": subscription_data["end_day"].isoformat() if subscription_data.get("end_day") else None
            }
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa user")
async def delete_user(
    user_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    🗑️ **Xóa user (soft delete - đánh dấu inactive)**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Xóa bất kỳ user nào (trừ chính mình)
    - 🏢 **White Label Admin**: Chỉ xóa users trong hierarchy của mình (trừ chính mình)
    
    **Path Parameters:**
    - `user_id`: ID của user cần xóa
    
    **Response:**
    - HTTP 204 No Content (thành công)
    
    **Business Logic:**
    - Soft delete: Chỉ set `is_active = false`, KHÔNG xóa vật lý khỏi database
    - KHÔNG CHO PHÉP user tự xóa chính mình (self-protection)
    - White Label Admin phải check hierarchy trước khi xóa
    - Dữ liệu liên quan (bots, subscriptions) vẫn giữ nguyên
    
    **Errors:**
    - `404`: User not found
    - `400`: You cannot delete yourself (self-protection)
    - `403`: Không có quyền xóa user này (ngoài hierarchy)
    
    **Note:**
    - User bị xóa vẫn tồn tại trong database với `is_active = false`
    - Có thể khôi phục bằng cách set `is_active = true`
    - Để xóa vĩnh viễn cần dùng admin tools khác
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # KHÔNG CHO PHÉP tự xóa mình
        if user_id == current_user_id:
            raise HTTPException(
                status_code=400,
                detail="You cannot delete yourself"
            )
        
        # KIỂM TRA HIERARCHY: Nếu KHÔNG phải Super Admin
        if not permissions.get("is_super_admin"):
            has_access = await PermissionChecker.check_hierarchy(
                current_user_id, user_id, factory
            )
            if not has_access:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete users in your hierarchy"
                )
        
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        await factory.user_manager.update_by_id(user_id, {"is_active": False})
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 🏢 WHITE LABEL MANAGEMENT
# ================================

# @router.post("/white-labels", status_code=status.HTTP_201_CREATED, summary="Tạo White Label partner")
# async def create_white_label_partner(
#     request: CreateWhiteLabelRequest,
#     background_tasks: BackgroundTasks,
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     🏢 **Tạo White Label partner mới với tài khoản admin và API key**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể tạo White Label partners
#     - White Label Admin KHÔNG thể tạo White Label khác
    
#     **Request Body:**
#     - `company_name`: Tên công ty White Label
#     - `domain`: Domain chính của White Label (vd: partner.com)
#     - `contact_name`: Tên người liên hệ
#     - `contact_email`: Email liên hệ (sẽ là tài khoản admin)
#     - `password`: Mật khẩu cho tài khoản admin
#     - `license_config`: Cấu hình license (limits, features, expiry)
    
#     **Response:**
#     - `user`: Thông tin tài khoản admin mới tạo
#     - `hierarchy`: Thông tin hierarchy (license_type: WHITE_LABEL)
#     - `license`: Thông tin license với config
#     - `api_key`: API key cho webhook integration (CHỈ HIỂN THỊ 1 LẦN!)
    
#     **Auto-created:**
#     - Tài khoản admin với role: `white_label_admin`
#     - Hierarchy entry với parent là Super Admin
#     - License với type: WHITE_LABEL
#     - API Key production với permissions: [read, write, webhook]
#     - Default packages, balances, limits (background task)
    
#     **Business Logic:**
#     - White Label Admin = Super Admin trong hệ thống của họ
#     - API key có rate limits cao: 120/min, 5000/hour, 50000/day
#     - Email phải unique trong toàn hệ thống
    
#     **Errors:**
#     - `400`: Email already exists
#     - `403`: Only Super Admin can create White Label partners
#     """
#     try:
#         factory = get_mongodb_factory()
#         existing = await factory.user_manager.get_by_email(request.contact_email)
#         if existing:
#             raise HTTPException(status_code=400, detail="Email already exists")
        
#         hashed_password = auth_service.hash_password(request.password)
#         user = await factory.user_manager.create_user(
#             name=request.contact_name,
#             email=request.contact_email,
#             password=hashed_password,
#             roles=["white_label_admin"],
#             email_verified=True
#         )
        
#         user_id = str(user["_id"])
#         hierarchy = await factory.super_hierarchy_manager.create_hierarchy(
#             user_id=user_id,
#             parent=str(permissions["user"]["_id"]),
#             hierarchy_type="white_label",
#             license_type=LicenseType.WHITE_LABEL.value,
#             partner_info={
#                 "company_name": request.company_name,
#                 "domain": request.domain,
#                 "contact_name": request.contact_name,
#                 "contact_email": request.contact_email
#             }
#         )
        
#         license = await factory.partner_license_manager.create_license(
#             partner_id=user_id,
#             license_type=LicenseType.WHITE_LABEL.value,
#             config=request.license_config
#         )
        
#         api_key = await factory.api_key_manager_v2.create_api_key(
#             owner_id=user_id,
#             owner_type="white_label",
#             name=f"{request.company_name} - Production API Key",
#             permissions=["read", "write", "webhook"],
#             rate_limits={
#                 "requests_per_minute": 120,
#                 "requests_per_hour": 5000,
#                 "requests_per_day": 50000
#             }
#         )
        
#         background_tasks.add_task(initialize_user_data, user_id=user_id, parent_id=str(permissions["user"]["_id"]))
        
#         return {
#             "message": "White Label partner created successfully",
#             "user": {
#                 "_id": user_id,
#                 "name": user["name"],
#                 "email": user["email"],
#                 "roles": user["roles"]
#             },
#             "hierarchy": hierarchy,
#             "license": license,
#             "api_key": {
#                 "_id": str(api_key["_id"]),
#                 "api_key": api_key.get("api_key"),
#                 "permissions": api_key["permissions"]
#             }
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error creating white label: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/white-labels", summary="Lấy danh sách White Label partners")
# async def get_white_label_partners(
#     skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua (pagination)"),
#     limit: int = Query(50, ge=1, le=1000, description="Số lượng tối đa trả về (max 1000)"),
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     📋 **Lấy danh sách tất cả White Label partners với thống kê**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể xem danh sách White Label
#     - White Label Admin KHÔNG xem được White Label khác (isolation)
    
#     **Query Parameters:**
#     - `skip`: Số lượng bản ghi bỏ qua (pagination)
#     - `limit`: Số lượng tối đa trả về (1-1000)
    
#     **Response:**
#     - Array các White Label partners, mỗi item gồm:
#       - `user`: Thông tin tài khoản admin (_id, name, email, roles)
#       - `hierarchy`: Hierarchy info (parent, license_type, partner_info)
#       - `total_users`: Tổng số users trong hệ thống của họ (recursive)
#       - `stats`: Thống kê tổng hợp (messages, bots, revenue, etc.)
    
#     **Business Logic:**
#     - Filter users có role: `white_label_admin`
#     - Tính toán recursive children để lấy total_users
#     - Lấy aggregate stats từ hierarchy manager
#     - Sort theo thời gian tạo (mới nhất trước)
    
#     **Use Cases:**
#     - Dashboard: Hiển thị danh sách tất cả White Label partners
#     - Analytics: So sánh performance giữa các partners
#     - Management: Quản lý và giám sát tất cả partners
#     """
#     try:
#         factory = get_mongodb_factory()
#         users = await factory.user_manager.get_all(
#             filter_query={"roles": "white_label_admin"},
#             skip=skip,
#             limit=limit,
#             sort_by="create_at",
#             sort_order=-1
#         )
        
#         result = []
#         for user in users:
#             user_id = str(user["_id"])
#             hierarchy = await factory.hierarchy_manager.get_by_user_id(user_id)
#             children = await factory.super_hierarchy_manager.get_children_recursive(user_id)
#             stats = await factory.super_hierarchy_manager.get_hierarchy_stats(user_id)
            
#             result.append({
#                 "user": {
#                     "_id": user_id,
#                     "name": user["name"],
#                     "email": user["email"],
#                     "roles": user.get("roles", [])
#                 },
#                 "hierarchy": hierarchy,
#                 "total_users": len(children),
#                 "stats": stats
#             })
        
#         return result
#     except Exception as e:
#         logger.error(f"Error getting white labels: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.get("/white-labels/{partner_id}", summary="Lấy chi tiết White Label partner")
# async def get_white_label_detail(
#     partner_id: str,
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     🔍 **Lấy thông tin chi tiết của White Label partner**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể xem chi tiết White Label
    
#     **Path Parameters:**
#     - `partner_id`: ID của White Label partner
    
#     **Response:**
#     - `user`: Thông tin đầy đủ của admin account
#     - `hierarchy`: Hierarchy info với partner_info (company_name, domain, contact)
#     - `license`: License details (type, config, limits, expiry)
#     - `total_users`: Tổng số users trong hệ thống (recursive count)
#     - `stats`: Thống kê chi tiết (aggregate_stats, usage_stats)
#     - `api_keys`: Danh sách API keys (KHÔNG bao gồm api_key thật)
    
#     **Business Logic:**
#     - Validate partner_id phải có role: `white_label_admin`
#     - Lấy recursive children để tính total_users
#     - Aggregate stats từ tất cả users trong hierarchy
#     - API keys chỉ hiển thị metadata (không hiển thị key thật)
    
#     **Errors:**
#     - `404`: White Label partner not found
#     - `404`: User không có role white_label_admin
    
#     **Use Cases:**
#     - Chi tiết partner profile
#     - Quản lý license và API keys
#     - Giám sát performance của từng partner
#     """
#     try:
#         factory = get_mongodb_factory()
#         user = await factory.user_manager.get_by_id(partner_id)
#         if not user or "white_label_admin" not in user.get("roles", []):
#             raise HTTPException(status_code=404, detail="White Label partner not found")
        
#         hierarchy = await factory.hierarchy_manager.get_by_user_id(partner_id)
#         children = await factory.super_hierarchy_manager.get_children_recursive(partner_id)
#         stats = await factory.super_hierarchy_manager.get_hierarchy_stats(partner_id)
#         license = await factory.partner_license_manager.get_by_partner_id(partner_id)
#         api_keys = await factory.api_key_manager_v2.get_by_owner(partner_id)
        
#         return {
#             "user": {
#                 "_id": str(user["_id"]),
#                 "name": user["name"],
#                 "email": user["email"],
#                 "roles": user.get("roles", []),
#                 "is_active": user.get("is_active", True),
#                 "create_at": user.get("create_at")
#             },
#             "hierarchy": hierarchy,
#             "license": license,
#             "total_users": len(children),
#             "stats": stats,
#             "api_keys": [{
#                 "_id": str(k["_id"]),
#                 "name": k.get("name"),
#                 "permissions": k.get("permissions", []),
#                 "is_active": k.get("is_active", True),
#                 "last_used": k.get("last_used")
#             } for k in api_keys] if api_keys else []
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting white label detail: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.patch("/white-labels/{partner_id}", summary="Cập nhật White Label partner")
# async def update_white_label_partner(
#     partner_id: str,
#     request: UpdateUserRequest,
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     ✏️ **Cập nhật thông tin White Label partner**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể update White Label
    
#     **Path Parameters:**
#     - `partner_id`: ID của White Label partner
    
#     **Request Body (tất cả optional):**
#     - `name`: Tên mới
#     - `email`: Email mới (phải unique)
#     - `is_active`: Trạng thái active/inactive
    
#     **Response:**
#     - `message`: Thông báo thành công
#     - `user`: Thông tin user sau khi update
    
#     **Business Logic:**
#     - Chỉ update fields được gửi lên (partial update)
#     - Email mới phải unique
#     - Validate partner_id phải có role: white_label_admin
    
#     **Errors:**
#     - `404`: White Label partner not found
#     - `400`: Email already exists
    
#     **Note:**
#     - Để update license config, dùng API khác
#     - Để revoke API keys, dùng API Key Management
#     """
#     try:
#         factory = get_mongodb_factory()
#         user = await factory.user_manager.get_by_id(partner_id)
#         if not user or "white_label_admin" not in user.get("roles", []):
#             raise HTTPException(status_code=404, detail="White Label partner not found")
        
#         update_data = {}
#         if request.name is not None:
#             update_data["name"] = request.name
#         if request.email is not None:
#             existing = await factory.user_manager.get_by_email(request.email)
#             if existing and str(existing["_id"]) != partner_id:
#                 raise HTTPException(status_code=400, detail="Email already exists")
#             update_data["email"] = request.email
#         if request.is_active is not None:
#             update_data["is_active"] = request.is_active
        
#         updated = await factory.user_manager.update_by_id(partner_id, update_data)
#         return {"message": "White Label partner updated successfully", "user": updated}
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating white label: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.delete("/white-labels/{partner_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa White Label partner")
# async def delete_white_label_partner(
#     partner_id: str,
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     🗑️ **Xóa White Label partner (soft delete + revoke API keys)**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể xóa White Label
    
#     **Path Parameters:**
#     - `partner_id`: ID của White Label partner cần xóa
    
#     **Response:**
#     - HTTP 204 No Content (thành công)
    
#     **Business Logic:**
#     - Soft delete: Set `is_active = false`
#     - Revoke tất cả API keys của partner (set is_active = false)
#     - KHÔNG xóa dữ liệu vật lý (giữ lại cho audit)
#     - Users trong hierarchy vẫn tồn tại nhưng không thể login
    
#     **Cascade Actions:**
#     - Revoke tất cả API keys
#     - Đánh dấu tài khoản admin inactive
#     - (Tùy chọn) Disable users trong hierarchy
    
#     **Errors:**
#     - `404`: White Label partner not found
    
#     **Warning:**
#     - Hành động này sẽ làm tất cả hệ thống của White Label ngừng hoạt động
#     - Cân nhắc kỹ trước khi xóa
#     - Có thể khôi phục bằng cách set is_active = true
#     """
#     try:
#         factory = get_mongodb_factory()
#         user = await factory.user_manager.get_by_id(partner_id)
#         if not user or "white_label_admin" not in user.get("roles", []):
#             raise HTTPException(status_code=404, detail="White Label partner not found")
        
#         # Soft delete - chỉ đánh dấu inactive
#         await factory.user_manager.update_by_id(partner_id, {"is_active": False})
        
#         # Revoke tất cả API keys
#         api_keys = await factory.api_key_manager_v2.get_by_owner(partner_id)
#         if api_keys:
#             for key in api_keys:
#                 await factory.api_key_manager_v2.revoke_api_key(str(key["_id"]))
        
#         return None
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting white label: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# ================================
# 📦 PACKAGE MANAGEMENT
# ================================

@router.get("/packages", summary="Lấy tất cả packages")
async def get_packages(
    user_id: Optional[str] = Query(None, description="Lọc packages cho user cụ thể (bao gồm global, hierarchy, và custom)"),
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    📦 **Lấy tất cả packages (gói dịch vụ) với filtering thông minh**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Xem tất cả packages (global + tất cả White Label + custom)
    - 🏢 **White Label Admin**: Xem packages (global + của họ + custom trong hierarchy)
    
    **Query Parameters:**
    - `user_id`: (Optional) Lọc packages mà user cụ thể được phép thấy
    
    **Response:**
    - Array các packages, mỗi package gồm:
      - `_id`: Package ID
      - `name`: Tên gói
      - `price`: Giá (VND)
      - `description`: Mô tả
      - `features`: Object các features (chatbot, social_accounts, etc.)
      - `limits`: Object các giới hạn (max_bots, max_messages, etc.)
      - `duration_months`: Thời hạn (tháng)
      - `type`: Loại package (default, custom)
      - `created_by`: User ID người tạo
      - `owner_type`: super_admin hoặc white_label
      - `target_users`: Array user_ids (nếu là custom package)
    
    **Business Logic:**
    - **Global packages** (owner_type = super_admin): Hiển thị cho TẤT CẢ
    - **Hierarchy packages** (owner_type = white_label, target_users = null/empty): Hiển thị cho users trong hierarchy
    - **Custom packages** (target_users có giá trị): CHỈ hiển thị cho users trong target_users
    - Nếu có user_id: Filter packages mà user đó được phép thấy
    - Sort theo create_at (mới nhất trước)
    
    **Use Cases:**
    - Hiển thị pricing page cho user cụ thể
    - Admin quản lý tất cả packages
    - Chọn package khi tạo subscription
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        all_packages = await factory.package_manager.get_all()
        
        # Nếu có user_id: Filter packages cho user đó
        if user_id:
            # Kiểm tra quyền truy cập user_id
            if not permissions.get("is_super_admin"):
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, user_id, factory
                )
                if not has_access:
                    raise HTTPException(status_code=403, detail="Cannot access this user's packages")
            
            # Lấy hierarchy của user để check owner
            user_hierarchy = await factory.hierarchy_manager.get_by_user_id(user_id)
            user_parent = user_hierarchy.get("parent") if user_hierarchy else None
            
            # Filter packages
            filtered_packages = []
            for pkg in all_packages:
                # Global packages: Tất cả đều thấy
                if pkg.get("owner_type") == "super_admin":
                    filtered_packages.append(pkg)
                    continue
                
                # Custom packages: Chỉ users trong target_users
                target_users = pkg.get("target_users")
                if target_users and len(target_users) > 0:
                    if user_id in target_users:
                        filtered_packages.append(pkg)
                    continue
                
                # Hierarchy packages: Check hierarchy
                pkg_creator = pkg.get("created_by")
                if pkg_creator:
                    # Nếu creator là parent của user hoặc trong cùng hierarchy tree
                    if pkg_creator == user_parent or pkg_creator == user_id:
                        filtered_packages.append(pkg)
                        continue
                    
                    # Check recursive hierarchy
                    has_hierarchy_access = await PermissionChecker.check_hierarchy(
                        pkg_creator, user_id, factory
                    )
                    if has_hierarchy_access:
                        filtered_packages.append(pkg)
            
            packages = filtered_packages
        else:
            # Không có user_id: Trả về packages theo quyền admin
            if permissions.get("is_super_admin"):
                packages = all_packages
            else:
                # White Label: Chỉ packages global + của họ
                packages = []
                for pkg in all_packages:
                    if pkg.get("owner_type") == "super_admin":
                        packages.append(pkg)
                    elif pkg.get("created_by") == current_user_id:
                        packages.append(pkg)
                    elif pkg.get("created_by"):
                        # Check nếu trong hierarchy
                        has_access = await PermissionChecker.check_hierarchy(
                            current_user_id, pkg.get("created_by"), factory
                        )
                        if has_access:
                            packages.append(pkg)
        
        for pkg in packages:
            pkg["_id"] = str(pkg["_id"])
        
        return packages
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting packages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages/{package_id}", summary="Lấy thông tin package theo ID")
async def get_package_by_id(
    package_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    📦 **Lấy thông tin chi tiết của một package theo ID**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Xem tất cả packages
    - 🏢 **White Label Admin**: Chỉ xem packages (global + của họ + trong hierarchy)
    
    **Path Parameters:**
    - `package_id`: ID của package cần lấy thông tin
    
    **Response:**
    - Package object với đầy đủ thông tin:
      - `_id`: Package ID
      - `name`: Tên gói
      - `price`: Giá (VND)
      - `description`: Mô tả
      - `features`: Object các features (chatbot, social_accounts, etc.)
      - `limits`: Object các giới hạn (max_bots, max_messages, etc.)
      - `duration_months`: Thời hạn (tháng)
      - `type`: Loại package (default, custom)
      - `created_by`: User ID người tạo
      - `owner_type`: super_admin hoặc white_label
      - `target_users`: Array user_ids (nếu là custom package)
      - `create_at`: Thời gian tạo
      - `update_at`: Thời gian cập nhật
    
    **Business Logic:**
    - Super Admin: Có thể xem tất cả packages
    - White Label Admin: Chỉ xem được packages họ được phép truy cập
      - Global packages (owner_type = super_admin)
      - Packages do họ tạo
      - Packages trong hierarchy tree của họ
    
    **Error Codes:**
    - 404: Package không tồn tại
    - 403: Không có quyền truy cập package này
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Lấy package
        package = await factory.package_manager.get_by_id(package_id)
        if not package:
            raise HTTPException(
                status_code=404,
                detail=f"Package with ID {package_id} not found"
            )
        
        # Kiểm tra quyền truy cập
        if not permissions.get("is_super_admin"):
            # White Label Admin: Kiểm tra quyền
            can_access = False
            
            # Global package: Tất cả đều truy cập được
            if package.get("owner_type") == "super_admin":
                can_access = True
            # Package do họ tạo
            elif package.get("created_by") == current_user_id:
                can_access = True
            # Package trong hierarchy
            elif package.get("created_by"):
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, package.get("created_by"), factory
                )
                if has_access:
                    can_access = True
            
            if not can_access:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to access this package"
                )
        
        # Convert ObjectId to string
        package["_id"] = str(package["_id"])
        if package.get("created_by"):
            package["created_by"] = str(package["created_by"])
        
        return package
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting package by ID: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/packages", status_code=status.HTTP_201_CREATED, summary="Tạo package")
async def create_package(request: CreatePackageRequest, permissions: Dict = Depends(require_white_label_or_super)):
    """
    ➕ **Tạo package mới (gói dịch vụ) với target users**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Tạo global packages (cho toàn hệ thống)
    - 🏢 **White Label Admin**: Tạo packages cho hệ thống của họ
    
    **Request Body:**
    - `name`: Tên gói (vd: "Starter", "Professional", "Enterprise")
    - `price`: Giá (VND)
    - `description`: Mô tả chi tiết
    - `features`: Object các tính năng {"chatbot": true, "analytics": true, ...}
    - `limits`: Object giới hạn {"max_bots": 10, "max_messages": 10000, ...}
    - `duration_months`: Thời hạn (tháng), vd: 1, 3, 6, 12
    - `target_users`: (Optional) Array user_ids để tạo custom package cho users cụ thể
    
    **Response:**
    - `message`: Thông báo thành công
    - `package`: Thông tin package vừa tạo
    
    **Business Logic:**
    - Super Admin tạo: `owner_type = "super_admin"` (global package nếu không có target_users)
    - White Label tạo: `owner_type = "white_label"` (chỉ trong hệ thống của họ)
    - Nếu có `target_users`: Tạo custom package CHỈ cho users đó
    - Nếu không có `target_users`: Tạo package cho tất cả users trong hierarchy
    - `type` tự động set = "custom"
    - `created_by` = current_user_id
    
    **Use Cases:**
    - Tạo package VIP cho khách hàng cao cấp (target_users = ["user123"])
    - Tạo package đặc biệt cho đối tác chiến lược
    - Tạo global package cho toàn hệ thống (Super Admin, không có target_users)
    - White Label tạo packages riêng cho khách hàng của họ
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Validate target_users nếu có
        if request.target_users and len(request.target_users) > 0:
            # Kiểm tra quyền truy cập các users
            if not permissions.get("is_super_admin"):
                for target_user_id in request.target_users:
                    has_access = await PermissionChecker.check_hierarchy(
                        current_user_id, target_user_id, factory
                    )
                    if not has_access:
                        raise HTTPException(
                            status_code=403,
                            detail=f"You cannot create package for user {target_user_id} (outside your hierarchy)"
                        )
        
        package_data = {
            "name": request.name,
            "price": request.price,
            "description": request.description,
            "features": request.features,
            "limits": request.limits,
            "duration_months": request.duration_months,
            "type": "custom",
            "created_by": current_user_id,
            "owner_type": "super_admin" if permissions.get("is_super_admin") else "white_label",
            "target_users": request.target_users if request.target_users else []
        }
        package = await factory.package_manager.create(package_data)
        package["_id"] = str(package["_id"])
        return {"message": "Package created successfully", "package": package}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/packages/{package_id}", summary="Cập nhật package")
async def update_package(package_id: str, request: UpdatePackageRequest, permissions: Dict = Depends(require_white_label_or_super)):
    """
    ✏️ **Cập nhật package (partial update)**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Update bất kỳ package nào
    - 🏢 **White Label Admin**: Chỉ update packages của họ (created_by = user_id)
    
    **Path Parameters:**
    - `package_id`: ID của package cần update
    
    **Request Body (tất cả optional):**
    - `name`: Tên mới
    - `price`: Giá mới
    - `description`: Mô tả mới
    - `features`: Features mới (object)
    - `limits`: Limits mới (object)
    - `duration_months`: Thời hạn mới
    
    **Response:**
    - `message`: Thông báo thành công
    - `package`: Thông tin package sau khi update
    
    **Business Logic:**
    - Chỉ update fields được gửi lên (partial update)
    - White Label chỉ update packages của họ (check created_by)
    - Super Admin có thể update bất kỳ package nào
    - Có thể update target_users để thêm/bớt users được phép thấy package
    
    **Errors:**
    - `404`: Package not found
    - `403`: White Label cannot update packages created by others
    - `403`: Cannot set target_users outside your hierarchy
    
    **Warning:**
    - Update package sẽ ảnh hưởng đến active subscriptions
    - Nên thông báo cho users trước khi thay đổi giá hoặc limits
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        package = await factory.package_manager.get_by_id(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        # White Label chỉ update packages của họ
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            if package.get("created_by") != current_user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only update packages created by you"
                )
        
        # Validate target_users nếu có
        if request.target_users is not None:
            if len(request.target_users) > 0 and not permissions.get("is_super_admin"):
                for target_user_id in request.target_users:
                    has_access = await PermissionChecker.check_hierarchy(
                        current_user_id, target_user_id, factory
                    )
                    if not has_access:
                        raise HTTPException(
                            status_code=403,
                            detail=f"You cannot set target_users for user {target_user_id} (outside your hierarchy)"
                        )
        
        update_data = {}
        if request.name is not None: update_data["name"] = request.name
        if request.price is not None: update_data["price"] = request.price
        if request.description is not None: update_data["description"] = request.description
        if request.features is not None: update_data["features"] = request.features
        if request.limits is not None: update_data["limits"] = request.limits
        if request.duration_months is not None: update_data["duration_months"] = request.duration_months
        if request.target_users is not None: update_data["target_users"] = request.target_users
        
        updated = await factory.package_manager.update_by_id(package_id, update_data)
        return {"message": "Package updated successfully", "package": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/packages/{package_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Xóa package")
async def delete_package(package_id: str, permissions: Dict = Depends(require_white_label_or_super)):
    """
    🗑️ **Xóa package (hard delete)**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Xóa bất kỳ package nào
    - 🏢 **White Label Admin**: Chỉ xóa packages của họ (created_by = user_id)
    
    **Path Parameters:**
    - `package_id`: ID của package cần xóa
    
    **Response:**
    - HTTP 204 No Content (thành công)
    
    **Business Logic:**
    - Hard delete: Xóa vật lý khỏi database
    - White Label chỉ xóa packages của họ (check created_by)
    - KHÔNG cho phép xóa nếu có active subscriptions
    
    **Validation:**
    - Kiểm tra active subscriptions trước khi xóa
    - Nếu có subscriptions đang active -> Return 400 error
    - Phải cancel/expire tất cả subscriptions trước
    
    **Errors:**
    - `404`: Package not found
    - `403`: White Label cannot delete packages created by others
    - `400`: Cannot delete - active subscriptions exist (số lượng subscriptions)
    
    **Warning:**
    - Hành động này KHÔNG thể khôi phục
    - Nên cân nhắc kỹ trước khi xóa
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        package = await factory.package_manager.get_by_id(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        # White Label chỉ xóa packages của họ
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            if package.get("created_by") != current_user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete packages created by you"
                )
        
        subscriptions = await factory.subscription_manager.get_all(
            filter_query={"package_id": package_id, "status": "active"}
        )
        if subscriptions:
            raise HTTPException(status_code=400, detail=f"Cannot delete. {len(subscriptions)} active subscriptions exist")
        
        await factory.package_manager.delete_by_id(package_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 💳 SUBSCRIPTION MANAGEMENT
# ================================

@router.get("/subscriptions", summary="Lấy danh sách subscriptions")
async def get_subscriptions(
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua (pagination)"),
    limit: int = Query(50, ge=1, le=1000, description="Số lượng tối đa trả về (max 1000)"),
    user_id: Optional[str] = Query(None, description="Lọc theo user_id cụ thể"),
    status: Optional[str] = Query(None, description="Lọc theo status: active, expired, cancelled"),
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    💳 **Lấy danh sách subscriptions với filtering**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Xem tất cả subscriptions trong toàn hệ thống
    - 🏢 **White Label Admin**: Chỉ xem subscriptions của users trong hierarchy
    
    **Query Parameters:**
    - `skip`: Số lượng bản ghi bỏ qua (pagination)
    - `limit`: Số lượng tối đa trả về (1-1000, mặc định 50)
    - `user_id`: Lọc subscriptions của user cụ thể
    - `status`: Lọc theo trạng thái (active, expired, cancelled)
    
    **Response:**
    - Array các subscriptions, mỗi item gồm:
      - `_id`: Subscription ID
      - `user_id`: ID của user
      - `package_id`: ID của package
      - `status`: Trạng thái (active, expired, cancelled)
      - `start_date`: Ngày bắt đầu
      - `expiry_date`: Ngày hết hạn
      - `features`: Features được kích hoạt
      - `limits`: Giới hạn sử dụng
      - `user_info`: Thông tin user (name, email)
      - `package_info`: Thông tin package (name, price)
    
    **Business Logic:**
    - White Label Admin: Filter theo hierarchy tree (recursive)
    - Super Admin: Không filter (xem tất cả)
    - Enrich với user_info và package_info
    - Sort theo create_at (mới nhất trước)
    
    **Use Cases:**
    - Quản lý subscriptions
    - Theo dõi doanh thu
    - Kiểm tra subscriptions sắp hết hạn
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        filter_query = {}
        if status:
            filter_query["status"] = status
        
        # Nếu KHÔNG phải Super Admin -> chỉ lấy subscriptions trong hierarchy
        if not permissions.get("is_super_admin"):
            children = await factory.super_hierarchy_manager.get_children_recursive(current_user_id)
            allowed_user_ids = [current_user_id] + [child["user_id"] for child in children]
            
            if user_id:
                if user_id not in allowed_user_ids:
                    raise HTTPException(status_code=403, detail="Access denied")
                filter_query["user_id"] = user_id
            else:
                filter_query["user_id"] = {"$in": allowed_user_ids}
        elif user_id:
            filter_query["user_id"] = user_id
        
        subscriptions = await factory.subscription_manager.get_all(
            filter_query=filter_query,
            skip=skip,
            limit=limit,
            sort_by="create_at",
            sort_order=-1
        )
        
        # Enrich với thông tin user và package
        for sub in subscriptions:
            sub["_id"] = str(sub["_id"])
            user = await factory.user_manager.get_by_id(sub["user_id"])
            package = await factory.package_manager.get_by_id(sub["package_id"])
            sub["user_info"] = {
                "name": user.get("name"),
                "email": user.get("email")
            } if user else None
            sub["package_info"] = {
                "name": package.get("name"),
                "price": package.get("price")
            } if package else None
        
        return subscriptions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions/{subscription_id}", summary="Lấy chi tiết subscription")
async def get_subscription_detail(
    subscription_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    🔍 **Lấy thông tin chi tiết của subscription**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Xem bất kỳ subscription nào
    - 🏢 **White Label Admin**: Chỉ xem subscriptions trong hierarchy
    
    **Path Parameters:**
    - `subscription_id`: ID của subscription
    
    **Response:**
    - `subscription`: Thông tin đầy đủ của subscription
    - `user`: Thông tin user sở hữu subscription
    - `package`: Thông tin package của subscription
    
    **Business Logic:**
    - White Label Admin phải check hierarchy trước khi truy cập
    - Return 403 nếu subscription nằm ngoài hierarchy
    - Enrich với full user và package info
    
    **Errors:**
    - `404`: Subscription not found
    - `403`: Không có quyền xem subscription này
    
    **Use Cases:**
    - Xem chi tiết subscription của khách hàng
    - Kiểm tra trạng thái và ngày hết hạn
    - Hỗ trợ khách hàng
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        subscription = await factory.subscription_manager.get_by_id(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Kiểm tra hierarchy nếu không phải Super Admin
        if not permissions.get("is_super_admin"):
            sub_user_id = subscription.get("user_id")
            if sub_user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, sub_user_id, factory
                )
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied")
        
        subscription["_id"] = str(subscription["_id"])
        user = await factory.user_manager.get_by_id(subscription["user_id"])
        package = await factory.package_manager.get_by_id(subscription["package_id"])
        
        return {
            "subscription": subscription,
            "user": user,
            "package": package
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions", status_code=status.HTTP_201_CREATED, summary="Tạo subscription")
async def create_subscription(
    user_id: str = Query(..., description="ID của user nhận subscription"),
    package_id: str = Query(..., description="ID của package đăng ký"),
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    ➕ **Tạo subscription mới cho user**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Tạo cho bất kỳ user nào
    - 🏢 **White Label Admin**: Chỉ tạo cho users trong hierarchy
    
    **Query Parameters:**
    - `user_id`: ID của user sẽ nhận subscription (required)
    - `package_id`: ID của package muốn đăng ký (required)
    
    **Response:**
    - `message`: Thông báo thành công
    - `subscription`: Thông tin subscription vừa tạo
    
    **Business Logic:**
    - White Label phải check hierarchy trước khi tạo
    - Validate user và package tồn tại
    - Tự động tính expiry_date = start_date + duration_months
    - Status mặc định = "active"
    - Copy features và limits từ package
    - Lưu payment_info (amount, currency, created_by)
    
    **Auto-calculated:**
    - `start_date`: Thời điểm hiện tại
    - `expiry_date`: start_date + package.duration_months
    - `status`: "active"
    - `features`: Copy từ package
    - `limits`: Copy từ package
    
    **Errors:**
    - `404`: User not found
    - `404`: Package not found
    - `403`: Không có quyền tạo subscription cho user này
    
    **Use Cases:**
    - Khách hàng mua package
    - Admin tạo subscription cho user
    - Upgrade/downgrade package
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Kiểm tra hierarchy nếu không phải Super Admin
        if not permissions.get("is_super_admin"):
            if user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, user_id, factory
                )
                if not has_access:
                    raise HTTPException(
                        status_code=403,
                        detail="You can only create subscriptions for users in your hierarchy"
                    )
        
        # Kiểm tra user tồn tại
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Kiểm tra package tồn tại
        package = await factory.package_manager.get_by_id(package_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        # Tạo subscription
        duration_months = package.get("duration_months", 1)
        expiry_date = datetime.now() + timedelta(days=duration_months * 30)
        
        subscription_data = {
            "user_id": user_id,
            "package_id": package_id,
            "status": "active",
            "start_date": datetime.now(),
            "expiry_date": expiry_date,
            "features": package.get("features", {}),
            "limits": package.get("limits", {}),
            "payment_info": {
                "amount": package.get("price", 0),
                "currency": "VND",
                "created_by": current_user_id
            }
        }
        
        subscription = await factory.subscription_manager.create(subscription_data)
        subscription["_id"] = str(subscription["_id"])
        
        return {
            "message": "Subscription created successfully",
            "subscription": subscription
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/subscriptions/{subscription_id}", summary="Cập nhật subscription")
async def update_subscription(
    subscription_id: str,
    request: UpdateSubscriptionRequest,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    ✏️ **Cập nhật subscription (status, expiry)**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Update bất kỳ subscription nào
    - 🏢 **White Label Admin**: Chỉ update subscriptions trong hierarchy
    
    **Path Parameters:**
    - `subscription_id`: ID của subscription cần update
    
    **Request Body (tất cả optional):**
    - `status`: Trạng thái mới (active, expired, cancelled)
    - `expiry_date`: Ngày hết hạn mới (datetime)
    
    **Response:**
    - `message`: Thông báo thành công
    - `subscription`: Thông tin subscription sau khi update
    
    **Business Logic:**
    - White Label phải check hierarchy trước khi update
    - Chỉ update fields được gửi lên (partial update)
    - Có thể gia hạn bằng cách update expiry_date
    - Có thể cancel bằng cách set status = "cancelled"
    
    **Errors:**
    - `404`: Subscription not found
    - `403`: Không có quyền update subscription này
    
    **Use Cases:**
    - Gia hạn subscription (update expiry_date)
    - Tạm dừng subscription (set status = "expired")
    - Kích hoạt lại (set status = "active")
    - Cancel subscription (set status = "cancelled")
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        subscription = await factory.subscription_manager.get_by_id(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Kiểm tra hierarchy nếu không phải Super Admin
        if not permissions.get("is_super_admin"):
            sub_user_id = subscription.get("user_id")
            if sub_user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, sub_user_id, factory
                )
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied")
        
        update_data = {}
        if request.status is not None:
            update_data["status"] = request.status
        if request.expiry_date is not None:
            update_data["expiry_date"] = request.expiry_date
        
        updated = await factory.subscription_manager.update_by_id(subscription_id, update_data)
        return {"message": "Subscription updated successfully", "subscription": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Hủy subscription")
async def cancel_subscription(
    subscription_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    ❌ **Hủy subscription (set status = cancelled)**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Hủy bất kỳ subscription nào
    - 🏢 **White Label Admin**: Chỉ hủy subscriptions trong hierarchy
    
    **Path Parameters:**
    - `subscription_id`: ID của subscription cần hủy
    
    **Response:**
    - HTTP 204 No Content (thành công)
    
    **Business Logic:**
    - White Label phải check hierarchy trước khi hủy
    - Set status = "cancelled" (KHÔNG xóa vật lý)
    - Giữ lại dữ liệu cho audit và báo cáo
    - User sẽ mất quyền truy cập features
    
    **Cascade Actions:**
    - Set subscription status = "cancelled"
    - Revoke các quyền truy cập liên quan
    - Giữ lại lịch sử thanh toán
    
    **Errors:**
    - `404`: Subscription not found
    - `403`: Không có quyền hủy subscription này
    
    **Note:**
    - User có thể đăng ký lại package khác
    - Không hoàn tiền tự động (cần xử lý riêng)
    - Có thể kích hoạt lại bằng API PATCH
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        subscription = await factory.subscription_manager.get_by_id(subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        # Kiểm tra hierarchy nếu không phải Super Admin
        if not permissions.get("is_super_admin"):
            sub_user_id = subscription.get("user_id")
            if sub_user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, sub_user_id, factory
                )
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied")
        
        await factory.subscription_manager.update_by_id(subscription_id, {"status": "cancelled"})
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# �📊 STATISTICS
# ================================

@router.get("/statistics/overview", summary="Thống kê tổng quan")
async def get_system_statistics(permissions: Dict = Depends(require_white_label_or_super)):
    """
    📊 **Thống kê tổng quan hệ thống (FULL statistics)**
    
    **Phân quyền:**
    - 🔑 **MekongAI Super Admin**: Thống kê TOÀN BỘ hệ thống (global scope)
    - 🏢 **White Label Admin**: Thống kê HỆ THỐNG CỦA HỌ (full statistics trong hierarchy)
    
    **Response:**
    - `scope`: "White Label System" hoặc "Global System" (để phân biệt)
    - `users`: Thống kê users
      - `total`: Tổng số users
      - `white_labels`: Số lượng White Label admins
      - `partners`: Số lượng Partner admins
      - `regular_users`: Số lượng end users
    - `subscriptions`: Thống kê subscriptions
      - `active`: Số lượng subscriptions đang active
    - `system`: Thống kê hệ thống
      - `total_bots`: Tổng số chatbots
      - `total_social_accounts`: Tổng số social accounts
      - `messages_today`: Số messages hôm nay
    - `revenue`: Thống kê doanh thu
      - `this_month`: Doanh thu tháng này (VND)
      - `currency`: Đơn vị tiền tệ
    
    **Business Logic:**
    - White Label Admin: Tính toán recursive trong hierarchy của họ
    - Super Admin: Tính toán toàn bộ hệ thống
    - Messages today: Filter theo ngày hiện tại (00:00 - 23:59)
    - Revenue: Tính từ đầu tháng đến hiện tại
    
    **Scope Filtering:**
    - White Label scope: users, bots, messages trong hierarchy tree
    - Global scope: Tất cả dữ liệu trong hệ thống
    
    **Use Cases:**
    - Dashboard overview
    - Business intelligence
    - Performance monitoring
    - White Label sẽ thấy FULL statistics của hệ thống họ (như Super Admin)
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Xác định scope
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            # White Label: Thống kê hệ thống của họ
            children = await factory.super_hierarchy_manager.get_children_recursive(current_user_id)
            user_ids = [current_user_id] + [child["user_id"] for child in children]
            filter_users = {"_id": {"$in": user_ids}}
        else:
            # Super Admin: Toàn bộ hệ thống
            filter_users = {}
        
        total_users = await factory.user_manager.count(filter_users)
        white_labels = await factory.user_manager.count({**filter_users, "roles": "white_label_admin"})
        partners = await factory.user_manager.count({**filter_users, "roles": "partner_admin"})
        regular_users = await factory.user_manager.count({**filter_users, "roles": "user"})
        
        # Subscriptions trong scope
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            subscription_filter = {"user_id": {"$in": user_ids}, "status": "active"}
        else:
            subscription_filter = {"status": "active"}
        active_subscriptions = await factory.subscription_manager.count(subscription_filter)
        
        # Bots và Social Accounts
        total_bots = 0
        total_social_accounts = 0
        if permissions.get("is_white_label") and not permissions.get("is_super_admin"):
            for uid in user_ids:
                bots = await factory.bot_manager.get_by_user_id(uid)
                social_accounts = await factory.social_account_manager.get_by_user_id(uid)
                total_bots += len(bots) if bots else 0
                total_social_accounts += len(social_accounts) if social_accounts else 0
        else:
            # Lấy tất cả bots và social accounts
            all_bots = await factory.bot_manager.get_all()
            all_social_accounts = await factory.social_account_manager.get_all()
            total_bots = len(all_bots) if all_bots else 0
            total_social_accounts = len(all_social_accounts) if all_social_accounts else 0
        
        # Messages today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Lấy history today và đếm
        try:
            histories_today = await factory.history_manager.get_all(
                filter_query={"create_at": {"$gte": today_start}}
            )
            messages_today = len(histories_today) if histories_today else 0
        except Exception:
            messages_today = 0
        
        # Revenue this month
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        transactions = await factory.transaction_manager.get_all(
            filter_query={"status": "success", "create_at": {"$gte": month_start}}
        )
        revenue_month = sum(t.get("amount", 0) for t in transactions)
        
        return {
            "scope": "White Label System" if (permissions.get("is_white_label") and not permissions.get("is_super_admin")) else "Global System",
            "users": {
                "total": total_users,
                "white_labels": white_labels,
                "partners": partners,
                "regular_users": regular_users
            },
            "subscriptions": {"active": active_subscriptions},
            "system": {
                "total_bots": total_bots,
                "total_social_accounts": total_social_accounts,
                "messages_today": messages_today
            },
            "revenue": {"this_month": revenue_month, "currency": "VND"}
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# @router.get("/statistics/white-labels/{partner_id}", summary="Thống kê White Label cụ thể")
# async def get_white_label_statistics(
#     partner_id: str,
#     permissions: Dict = Depends(require_super_admin)
# ):
#     """
#     📈 **Thống kê chi tiết của White Label partner cụ thể**
    
#     **Phân quyền:**
#     - ⚠️ **CHỈ MekongAI Super Admin** có thể xem thống kê White Label
    
#     **Path Parameters:**
#     - `partner_id`: ID của White Label partner
    
#     **Response:**
#     - `partner_id`: ID của partner
#     - `partner_name`: Tên partner
#     - `users`: Thống kê users trong hệ thống của partner
#       - `total`: Tổng số users (bao gồm partner)
#       - `partners`: Số lượng Partner Admins
#       - `regular_users`: Số lượng End Users
#     - `subscriptions`: Thống kê subscriptions
#       - `active`: Subscriptions đang active
#       - `expired`: Subscriptions đã hết hạn
#     - `api_keys`: Thống kê API keys
#       - `total`: Tổng số API keys
#       - `active`: API keys đang active
#     - `hierarchy_stats`: Aggregate stats từ hierarchy manager
#       - Usage stats, performance metrics, etc.
    
#     **Business Logic:**
#     - Tính toán recursive trong hierarchy tree của partner
#     - Count users theo roles (partner_admin vs user)
#     - Aggregate subscriptions theo status
#     - Lấy hierarchy stats từ hierarchy manager
    
#     **Errors:**
#     - `404`: White Label partner not found
#     - `404`: User không có role white_label_admin
    
#     **Use Cases:**
#     - So sánh performance giữa các White Label partners
#     - Monitoring health của từng partner
#     - Business analytics cho MekongAI
#     - Identify top-performing partners
#     """
#     try:
#         factory = get_mongodb_factory()
        
#         # Kiểm tra partner tồn tại
#         user = await factory.user_manager.get_by_id(partner_id)
#         if not user or "white_label_admin" not in user.get("roles", []):
#             raise HTTPException(status_code=404, detail="White Label partner not found")
        
#         # Thống kê hierarchy
#         children = await factory.super_hierarchy_manager.get_children_recursive(partner_id)
#         stats = await factory.super_hierarchy_manager.get_hierarchy_stats(partner_id)
        
#         # Thống kê users theo role
#         user_ids = [partner_id] + [child["user_id"] for child in children]
#         partners_count = 0
#         users_count = 0
#         for uid in user_ids:
#             u = await factory.user_manager.get_by_id(uid)
#             if u:
#                 roles = u.get("roles", [])
#                 if "partner_admin" in roles:
#                     partners_count += 1
#                 elif "user" in roles:
#                     users_count += 1
        
#         # Thống kê subscriptions
#         active_subs = 0
#         expired_subs = 0
#         for uid in user_ids:
#             subs = await factory.subscription_manager.get_all(
#                 filter_query={"user_id": uid}
#             )
#             for sub in subs:
#                 if sub.get("status") == "active":
#                     active_subs += 1
#                 else:
#                     expired_subs += 1
        
#         # Thống kê API keys
#         api_keys = await factory.api_key_manager_v2.get_by_owner(partner_id)
#         active_api_keys = len([k for k in api_keys if k.get("is_active", True)])
        
#         return {
#             "partner_id": partner_id,
#             "partner_name": user.get("name"),
#             "users": {
#                 "total": len(user_ids),
#                 "partners": partners_count,
#                 "regular_users": users_count
#             },
#             "subscriptions": {
#                 "active": active_subs,
#                 "expired": expired_subs
#             },
#             "api_keys": {
#                 "total": len(api_keys),
#                 "active": active_api_keys
#             },
#             "hierarchy_stats": stats
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting white label statistics: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/token-usage", summary="Thống kê token usage theo cây hierarchy")
async def get_hierarchy_token_usage(
    root_user_id: Optional[str] = Query(
        None,
        description="User gốc để thống kê. Mặc định là user hiện tại.",
    ),
    start_time: Optional[datetime] = Query(
        None, description="Thời gian bắt đầu (Asia/Ho_Chi_Minh)"
    ),
    end_time: Optional[datetime] = Query(
        None, description="Thời gian kết thúc (Asia/Ho_Chi_Minh)"
    ),
    permissions: Dict = Depends(require_white_label_or_super),
):
    """
    📊 **Thống kê token usage theo hierarchy**

    **Phân quyền:**
    - 🔐 **Super Admin**: thống kê toàn bộ hệ thống (mọi user).
    - 🏢 **White Label Admin**: thống kê trong cây hierarchy của chính mình.

    **Query Parameters:**
    - `root_user_id`: User làm gốc thống kê (tùy chọn).
    - `start_time`, `end_time`: Khoảng thời gian lọc (tùy chọn).

    **Response:**
    - `root_user_id`: User gốc của cây.
    - `time_range`: Khoảng thời gian áp dụng filter.
    - `totals`: Tổng tokens/cost/requests trong toàn cây.
    - `users`: Danh sách từng user trong cây kèm metrics & thông tin hierarchy.
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        target_user_id = root_user_id or current_user_id

        # Kiểm tra quyền truy cập
        if target_user_id != current_user_id and not permissions.get("is_super_admin"):
            has_access = await PermissionChecker.check_hierarchy(
                current_user_id, target_user_id, factory
            )
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied")

        # Kiểm tra user tồn tại
        target_user = await factory.user_manager.get_by_id(target_user_id)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")

        root_hierarchy = await factory.super_hierarchy_manager.get_by_user_id(
            target_user_id
        )
        if not root_hierarchy:
            raise HTTPException(status_code=404, detail="Hierarchy not found for user")

        children_hierarchies = await factory.super_hierarchy_manager.get_children_recursive(
            target_user_id
        )
        hierarchy_docs = [root_hierarchy] + children_hierarchies

        user_ids: List[str] = []
        for doc in hierarchy_docs:
            uid = doc.get("user_id")
            if uid and uid not in user_ids:
                user_ids.append(uid)

        normalized_start = _normalize_datetime(start_time)
        normalized_end = _normalize_datetime(end_time)

        if (
            normalized_start
            and normalized_end
            and normalized_start > normalized_end
        ):
            raise HTTPException(
                status_code=400, detail="start_time must be before end_time"
            )

        aggregate_map = await factory.token_log_manager.aggregate_tokens_by_users(
            user_ids=user_ids,
            start_time=normalized_start,
            end_time=normalized_end,
        )

        hierarchy_map = {
            doc["user_id"]: doc for doc in hierarchy_docs if doc.get("user_id")
        }
        children_map = {
            uid: hierarchy_map[uid].get("children", [])
            for uid in hierarchy_map.keys()
        }

        depth_map: Dict[str, int] = {target_user_id: 0}
        queue: List[str] = [target_user_id]
        while queue:
            current = queue.pop(0)
            for child_id in children_map.get(current, []):
                if child_id not in depth_map:
                    depth_map[child_id] = depth_map[current] + 1
                    queue.append(child_id)

        object_ids = [
            oid
            for uid in user_ids
            for oid in [_safe_object_id(uid)]
            if oid is not None
        ]
        user_info_map: Dict[str, Dict[str, Any]] = {}
        if object_ids:
            users = await factory.user_manager.get_all(
                filter_query={"_id": {"$in": object_ids}},
                limit=0,
            )
            for user in users:
                roles = user.get("roles", [])
                if isinstance(roles, str):
                    roles = [roles]
                user_info_map[user["_id"]] = {
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "roles": roles,
                    "company_id": user.get("company_id"),
                }

        user_details: List[Dict[str, Any]] = []
        for uid in user_ids:
            metrics = aggregate_map.get(uid, {})
            info = user_info_map.get(uid, {})
            hierarchy_info = hierarchy_map.get(uid, {})

            last_activity = metrics.get("last_activity")
            if last_activity and hasattr(last_activity, "isoformat"):
                last_activity = last_activity.isoformat()

            user_details.append(
                {
                    "user_id": uid,
                    "name": info.get("name"),
                    "email": info.get("email"),
                    "roles": info.get("roles", []),
                    "company_id": info.get("company_id"),
                    "parent_id": hierarchy_info.get("parent"),
                    "depth": depth_map.get(uid, 0),
                    "children_count": len(hierarchy_info.get("children", []))
                    if hierarchy_info
                    else 0,
                    "prompt_tokens": metrics.get("prompt_tokens", 0),
                    "completion_tokens": metrics.get("completion_tokens", 0),
                    "total_tokens": metrics.get("total_tokens", 0),
                    "total_cost": metrics.get("total_cost", 0.0),
                    "successful_requests": metrics.get("successful_requests", 0),
                    "request_count": metrics.get("request_count", 0),
                    "last_activity": last_activity,
                }
            )

        totals = {
            "prompt_tokens": sum(item["prompt_tokens"] for item in user_details),
            "completion_tokens": sum(item["completion_tokens"] for item in user_details),
            "total_tokens": sum(item["total_tokens"] for item in user_details),
            "total_cost": sum(item["total_cost"] for item in user_details),
            "successful_requests": sum(
                item["successful_requests"] for item in user_details
            ),
            "request_count": sum(item["request_count"] for item in user_details),
            "users": len(user_details),
        }

        return {
            "success": True,
            "data": {
                "root_user_id": target_user_id,
                "time_range": {
                    "start": normalized_start.isoformat() if normalized_start else None,
                    "end": normalized_end.isoformat() if normalized_end else None,
                },
                "totals": totals,
                "users": user_details,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating token usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics/users/{user_id}", summary="Thống kê user cụ thể")
async def get_user_statistics(
    user_id: str,
    permissions: Dict = Depends(require_white_label_or_super)
):
    """
    👤 **Thống kê chi tiết của user cụ thể**
    
    **Phân quyền:**
    - 🔑 **Super Admin**: Xem bất kỳ user nào
    - 🏢 **White Label Admin**: Chỉ xem users trong hierarchy
    
    **Path Parameters:**
    - `user_id`: ID của user cần thống kê
    
    **Response:**
    - `user_id`: ID của user
    - `user_name`: Tên user
    - `user_email`: Email user
    - `bots`: Thống kê chatbots
      - `total`: Tổng số bots
      - `active`: Số bots đang active
    - `social_accounts`: Thống kê social accounts
      - `total`: Tổng số accounts
    - `subscriptions`: Thống kê subscriptions
      - `total`: Tổng số subscriptions
      - `active`: Subscriptions đang active
    - `balance`: Số dư tài khoản hiện tại (VND)
    - `messages`: Thống kê messages
      - `today`: Số messages hôm nay
    
    **Business Logic:**
    - White Label phải check hierarchy trước khi xem
    - Count bots theo is_active status
    - Count subscriptions theo status
    - Messages today: Filter theo ngày hiện tại
    - Balance: Lấy từ balance_manager
    
    **Errors:**
    - `404`: User not found
    - `403`: Không có quyền xem user này (ngoài hierarchy)
    
    **Use Cases:**
    - User profile dashboard
    - Customer support
    - Usage monitoring
    - Billing và invoicing
    - Identify power users
    """
    try:
        factory = get_mongodb_factory()
        current_user_id = str(permissions["user"]["_id"])
        
        # Kiểm tra hierarchy nếu không phải Super Admin
        if not permissions.get("is_super_admin"):
            if user_id != current_user_id:
                has_access = await PermissionChecker.check_hierarchy(
                    current_user_id, user_id, factory
                )
                if not has_access:
                    raise HTTPException(status_code=403, detail="Access denied")
        
        # Kiểm tra user tồn tại
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Thống kê
        bots = await factory.bot_manager.get_by_user_id(user_id)
        social_accounts = await factory.social_account_manager.get_by_user_id(user_id)
        subscriptions = await factory.subscription_manager.get_all(
            filter_query={"user_id": user_id}
        )
        balance = await factory.balance_manager.get_by_user_id(user_id)
        
        # Thống kê messages
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_today = 0
        if bots:
            for bot in bots:
                bot_id = str(bot["_id"])
                try:
                    histories = await factory.history_manager.get_all(
                        filter_query={
                            "bot_id": bot_id,
                            "create_at": {"$gte": today_start}
                        }
                    )
                    messages_today += len(histories) if histories else 0
                except Exception:
                    pass
        
        return {
            "user_id": user_id,
            "user_name": user.get("name"),
            "user_email": user.get("email"),
            "bots": {
                "total": len(bots) if bots else 0,
                "active": len([b for b in bots if b.get("is_active", True)]) if bots else 0
            },
            "social_accounts": {
                "total": len(social_accounts) if social_accounts else 0
            },
            "subscriptions": {
                "total": len(subscriptions),
                "active": len([s for s in subscriptions if s.get("status") == "active"])
            },
            "balance": balance.get("amount", 0) if balance else 0,
            "messages": {
                "today": messages_today
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================
# 🛠️ HELPER FUNCTIONS
# ================================

async def initialize_user_data(user_id: str, parent_id: Optional[str] = None):
    """
    Helper function để khởi tạo dữ liệu mặc định cho user mới
    
    Args:
        user_id: ID của user cần khởi tạo
        parent_id: ID của parent trong hierarchy
    """
    try:
        initializer = await get_default_initializer()
        await initializer.init_user_defaults(user_id, parent_id)
        logger.info(f"✅ Initialized default data for user: {user_id}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize user data for {user_id}: {str(e)}")


