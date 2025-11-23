"""
SuperAdmin Authorization Middleware
====================================
Middleware để kiểm tra quyền truy cập SuperAdmin, White Label, và User permissions
"""

from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
import logging
from controllers.data.managements import get_mongodb_factory
from controllers.auth.auth_service import auth_service
from configs.constant import IS_WHITE_LABEL_SYSTEM, WHITE_LABEL_API_KEY

logger = logging.getLogger(__name__)
security = HTTPBearer()

class PermissionChecker:
    """Helper class để kiểm tra permissions"""
    
    @staticmethod
    async def check_role(user_roles: List[str], required_roles: List[str]) -> bool:
        """
        Kiểm tra user có role cần thiết không
        
        Args:
            user_roles: Danh sách roles của user
            required_roles: Danh sách roles yêu cầu (OR logic)
        """
        return any(role in user_roles for role in required_roles)
    
    @staticmethod
    async def check_hierarchy(
        user_id: str,
        target_user_id: str,
        factory
    ) -> bool:
        """
        Kiểm tra user có quyền quản lý target_user không (theo hierarchy)
        
        Returns:
            True nếu user_id là parent/ancestor của target_user_id
        """
        # Lấy hierarchy của cả hai users
        user_hierarchy = await factory.hierarchy_manager.get_by_user_id(user_id)
        target_hierarchy = await factory.hierarchy_manager.get_by_user_id(target_user_id)
        
        if not user_hierarchy or not target_hierarchy:
            return False
        
        # Kiểm tra xem user có phải là ancestor của target không
        current_parent = target_hierarchy.get("parent")
        max_depth = 50  # Tránh vòng lặp vô tận
        depth = 0
        
        while current_parent and depth < max_depth:
            if current_parent == user_id:
                return True
            
            # Lấy hierarchy của parent
            parent_hierarchy = await factory.hierarchy_manager.get_by_user_id(current_parent)
            if not parent_hierarchy:
                break
            
            current_parent = parent_hierarchy.get("parent")
            depth += 1
        
        return False
    
    @staticmethod
    async def get_user_permissions(
        user_id: str,
        factory
    ) -> Dict[str, Any]:
        """
        Lấy tất cả permissions của user
        
        Returns:
            Dictionary chứa roles, features, limits, hierarchy_info
        """
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            return {}
        
        roles = user.get("roles", [])
        # Normalize roles to list if it's a string
        if isinstance(roles, str):
            roles = [roles]
        
        features = user.get("features", {})
        
        # Lấy hierarchy info
        hierarchy = await factory.hierarchy_manager.get_by_user_id(user_id)
        
        # Lấy subscription info
        subscriptions = await factory.subscription_manager.get_by_user_id(user_id, status="active")
        
        # Lấy limits
        limits = {}
        if subscriptions:
            subscription = subscriptions[0]
            package_id = subscription.get("package_id")
            if package_id:
                package = await factory.package_manager.get_by_id(package_id)
                if package:
                    limits = package.get("limits", {})
        
        is_super_admin = "super_admin" in roles
        is_white_label = "white_label_admin" in roles
        
        return {
            "user_id": user_id,
            "roles": roles,
            "features": features,
            "limits": limits,
            "hierarchy": hierarchy,
            "is_super_admin": is_super_admin,
            "is_white_label": is_white_label,
            "is_partner": "partner_admin" in roles,
            # White Label Admin = Super Admin trong hệ thống của họ
            "is_system_admin": is_super_admin or is_white_label
        }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Dependency để lấy current user từ JWT token
    
    Returns:
        Dictionary chứa user info
    """
    try:
        token = credentials.credentials
        payload = auth_service.verify_token(token)
        
        factory = get_mongodb_factory()
        user_id = payload.get("user_id")
        
        if not user_id:
            logger.error("No user_id in token payload")
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=401, detail="User not found")
        
        # Normalize roles to list if it's a string
        if "roles" in user and isinstance(user["roles"], str):
            user["roles"] = [user["roles"]]
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


async def get_current_user_permissions(
    user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency để lấy permissions của current user
    
    Returns:
        Dictionary chứa đầy đủ permissions info
    """
    factory = get_mongodb_factory()
    user_id = str(user["_id"])
    
    permissions = await PermissionChecker.get_user_permissions(user_id, factory)
    permissions["user"] = user
    
    return permissions


def require_roles(required_roles: List[str]):
    """
    Decorator để yêu cầu user phải có một trong các roles
    
    Args:
        required_roles: List các roles (OR logic)
    
    Example:
        @router.get("/admin/users")
        @require_roles(["super_admin", "white_label_admin"])
        async def get_users(permissions: Dict = Depends(get_current_user_permissions)):
            ...
    """
    async def role_checker(
        permissions: Dict[str, Any] = Depends(get_current_user_permissions)
    ):
        user_roles = permissions.get("roles", [])
        
        if not await PermissionChecker.check_role(user_roles, required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {', '.join(required_roles)}"
            )
        
        return permissions
    
    return role_checker


async def require_super_admin(
    permissions: Dict[str, Any] = Depends(get_current_user_permissions)
):
    """
    Dependency yêu cầu Super Admin role
    """
    if not permissions.get("is_super_admin"):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Super Admin role required."
        )
    return permissions


async def require_white_label_or_super(
    permissions: Dict[str, Any] = Depends(get_current_user_permissions)
):
    """
    Dependency yêu cầu White Label Admin hoặc Super Admin
    White Label Admin = Super Admin trong hệ thống của họ
    """
    if not permissions.get("is_system_admin"):
        raise HTTPException(
            status_code=403,
            detail="Access denied. System Admin role required."
        )
    return permissions


async def require_partner_or_above(
    permissions: Dict[str, Any] = Depends(get_current_user_permissions)
):
    """
    Dependency yêu cầu Partner Admin trở lên
    (Partner, White Label, Super Admin)
    """
    if not (permissions.get("is_system_admin") or permissions.get("is_partner")):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Partner Admin or above required."
        )
    return permissions


async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Dict[str, Any]:
    """
    Dependency để verify API Key (cho White Label webhooks)
    
    Args:
        x_api_key: API Key từ header
    
    Returns:
        Dictionary chứa API key info
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API Key is required"
        )
    
    factory = get_mongodb_factory()
    key_info = await factory.api_key_manager_v2.verify_api_key(x_api_key)
    
    if not key_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API Key"
        )
    
    return key_info


async def verify_hierarchy_access(
    target_user_id: str,
    permissions: Dict[str, Any] = Depends(get_current_user_permissions)
):
    """
    Dependency để verify user có quyền access target_user theo hierarchy
    
    Args:
        target_user_id: ID của user cần access
        permissions: Permissions của current user
    """
    # Super admin có quyền access tất cả
    if permissions.get("is_super_admin"):
        return permissions
    
    # Kiểm tra hierarchy
    factory = get_mongodb_factory()
    user_id = str(permissions["user"]["_id"])
    
    has_access = await PermissionChecker.check_hierarchy(
        user_id,
        target_user_id,
        factory
    )
    
    if not has_access and user_id != target_user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied. You don't have permission to access this user."
        )
    
    return permissions


def check_feature_access(feature_name: str):
    """
    Decorator để kiểm tra user có access feature không
    
    Args:
        feature_name: Tên feature cần kiểm tra
    
    Example:
        @router.get("/dashboard")
        @check_feature_access("dashboard")
        async def get_dashboard(permissions: Dict = Depends(get_current_user_permissions)):
            ...
    """
    async def feature_checker(
        permissions: Dict[str, Any] = Depends(get_current_user_permissions)
    ):
        features = permissions.get("features", {})
        
        if not features.get(feature_name, False):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Feature '{feature_name}' is not available in your plan."
            )
        
        return permissions
    
    return feature_checker


def check_limit(limit_type: str, required_count: int = 1):
    """
    Decorator để kiểm tra user có đủ limit không
    
    Args:
        limit_type: Loại limit (messages_per_month, bot, social, etc.)
        required_count: Số lượng cần thiết
    
    Example:
        @router.post("/bots")
        @check_limit("bot", 1)
        async def create_bot(permissions: Dict = Depends(get_current_user_permissions)):
            ...
    """
    async def limit_checker(
        permissions: Dict[str, Any] = Depends(get_current_user_permissions)
    ):
        limits = permissions.get("limits", {})
        max_allowed = limits.get(limit_type, 0)
        
        # -1 nghĩa là unlimited
        if max_allowed != -1:
            # TODO: Kiểm tra usage hiện tại
            # For now, just check if limit exists
            if max_allowed == 0:
                raise HTTPException(
                    status_code=403,
                    detail=f"Limit exceeded for '{limit_type}'. Please upgrade your plan."
                )
        
        return permissions
    
    return limit_checker


class RateLimiter:
    """Rate limiting cho API"""
    
    @staticmethod
    async def check_rate_limit(
        user_id: str,
        endpoint: str,
        max_requests: int = 60,
        window_seconds: int = 60
    ) -> bool:
        """
        Kiểm tra rate limit
        
        Args:
            user_id: ID user
            endpoint: Endpoint name
            max_requests: Số requests tối đa
            window_seconds: Cửa sổ thời gian (giây)
        
        Returns:
            True nếu còn trong limit
        """
        # TODO: Implement with Redis
        # For now, always return True
        return True


# Convenience function để kiểm tra quyền trong code
async def check_user_permission(
    user_id: str,
    required_roles: List[str] = None,
    required_features: List[str] = None,
    target_user_id: str = None
) -> bool:
    """
    Kiểm tra quyền của user trong code
    
    Args:
        user_id: ID user cần kiểm tra
        required_roles: Roles yêu cầu
        required_features: Features yêu cầu
        target_user_id: ID user mục tiêu (để kiểm tra hierarchy)
    
    Returns:
        True nếu có quyền
    """
    factory = get_mongodb_factory()
    permissions = await PermissionChecker.get_user_permissions(user_id, factory)
    
    # Kiểm tra roles
    if required_roles:
        user_roles = permissions.get("roles", [])
        if not await PermissionChecker.check_role(user_roles, required_roles):
            return False
    
    # Kiểm tra features
    if required_features:
        features = permissions.get("features", {})
        if not all(features.get(f, False) for f in required_features):
            return False
    
    # Kiểm tra hierarchy
    if target_user_id:
        # Super admin luôn có quyền
        if permissions.get("is_super_admin"):
            return True
        
        # Kiểm tra hierarchy relationship
        has_access = await PermissionChecker.check_hierarchy(
            user_id,
            target_user_id,
            factory
        )
        if not has_access and user_id != target_user_id:
            return False
    
    return True
