"""
Authentication Middleware
Cung cấp dependencies cho FastAPI để xác thực JWT tokens
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any

from .auth_service import auth_service

# HTTP Bearer scheme for token authentication
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency để lấy thông tin user hiện tại từ JWT token
    Bắt buộc phải có token
    
    Returns:
        Dict với user_id (string của MongoDB _id), email, name, roles
    """
    try:
        # Extract token from Bearer authorization header
        token = credentials.credentials
        
        # Decode JWT token
        payload = auth_service.verify_token(token)
        
        # Extract user info from payload
        # user_id trong JWT token chính là str(user["_id"]) từ MongoDB
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return {
            "user_id": user_id,  # string của MongoDB _id
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "roles": payload.get("roles", []),
            "full_payload": payload
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )

def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency để lấy thông tin user hiện tại từ JWT token
    Token không bắt buộc, trả về None nếu không có
    
    Returns:
        Dict với user_id (string của MongoDB _id) hoặc None
    """
    if not credentials:
        return None
    
    try:
        # Extract token from Bearer authorization header
        token = credentials.credentials
        
        # Decode JWT token
        payload = auth_service.verify_token(token)
        
        # Extract user info from payload
        # user_id trong JWT token chính là str(user["_id"]) từ MongoDB
        user_id = payload.get("user_id")
        if user_id is None:
            return None
        
        return {
            "user_id": user_id,  # string của MongoDB _id
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "roles": payload.get("roles", []),
            "full_payload": payload
        }
    except:
        return None

def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    FastAPI dependency để kiểm tra user có quyền admin không
    """
    roles = current_user.get("roles", [])
    if "admin" not in roles and "super_admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def get_super_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    FastAPI dependency để kiểm tra user có quyền super admin không
    """
    roles = current_user.get("roles", [])
    if "super_admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user

def check_user_access(target_user_id: str, current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    FastAPI dependency để kiểm tra user có quyền truy cập tài nguyên của user khác không
    Chỉ admin hoặc chính user đó mới được phép
    """
    roles = current_user.get("roles", [])
    is_admin = "admin" in roles or "super_admin" in roles
    is_same_user = current_user.get("user_id") == target_user_id
    
    if not (is_admin or is_same_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return current_user