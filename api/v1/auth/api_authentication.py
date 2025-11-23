"""
Authentication API Endpoints
Cung cấp API cho login, register, refresh token
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
from configs.environment import get_vietnam_now_naive
import logging
import re

from configs.constant import SERVER_ADDRESS, PARENT_ORG_ID

# Import managers và auth services
from controllers.data.managements import get_mongodb_factory
from controllers.data.init_defaults import get_default_initializer
from controllers.data.limit_service import get_limit_service
from controllers.auth.auth_service import auth_service
from controllers.auth.auth_middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Authentication"])

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password format
    Returns: (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 128:
        return False, "Password must not exceed 128 characters"
    
    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter  
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    # Check for at least one special character
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    return True, ""

# Pydantic Models
class LoginRequest(BaseModel):
    email: str
    password: str
    
class GoogleLoginRequest(BaseModel):
    google_id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    verification_code: str  # Bắt buộc có mã xác thực
    method: str = "email_password"  # email_password, google
    avatar_url: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class SendVerificationEmailRequest(BaseModel):
    email: EmailStr

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    verification_code: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class RateLimitCheckRequest(BaseModel):
    email: EmailStr
    action: str  # "send_verification_email" hoặc "forgot_password"

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: Dict[str, Any]

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str

# Dependency to get management factory
def get_management_factory():
    """Get initialized management factory"""
    try:
        factory = get_mongodb_factory()
        if factory is None:
            raise HTTPException(status_code=503, detail="MongoDB Management Factory not initialized")
        return factory
    except Exception as e:
        logger.error(f"Failed to get management factory: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    factory = Depends(get_management_factory)
):
    """Đăng nhập user với email/username và password"""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(
            factory.user_manager,
            login_data.email,
            login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Incorrect email/username or password"
            )
        
        # Create tokens
        tokens = auth_service.create_user_tokens(user)
        
        # Update user's refresh token in database (optional)
        try:
            await factory.user_manager.update_by_id(
                str(user["_id"]), 
                {"refresh_token": tokens["refresh_token"]}
            )
        except Exception as e:
            logger.warning(f"Failed to update refresh token in database: {e}")
        
        # Get actual limits using limit service
        limit_service = get_limit_service(factory)
        limits_info = await limit_service.get_user_current_limits(str(user["_id"]))
        
        # Remove sensitive data from user response
        user_response = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "method": user.get("method", "email_password"),
            "roles": user.get("roles", []),
            "packages": user.get("current_package"),
            "package_name": user.get("package_name"),
            "package_expires_at": user.get("package_expires_at"),
            "features": user.get("features", {}),
            "limits": limits_info.get("limits", {}),
            "create_at": user.get("create_at"),
            "update_at": user.get("update_at"),
            "email_verified": user.get("email_verified", False)
        }
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            user=user_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/register", response_model=Dict[str, Any])
async def register(
    register_data: RegisterRequest,
    background_tasks: BackgroundTasks,
    factory = Depends(get_management_factory)
):
    """Đăng ký user mới (yêu cầu verification code)"""
    try:
        # Kiểm tra email đã tồn tại chưa
        existing_user = await factory.user_manager.get_by_email(register_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Xác thực email verification code trước khi cho phép đăng ký
        if register_data.method == "email_password":
            # Yêu cầu verification code cho email registration
            is_verified = await factory.email_verification_manager.verify_code(
                register_data.email,
                register_data.verification_code
            )
            
            if not is_verified:
                raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
        # Xử lý password dựa trên method
        hashed_password = None
        if register_data.method == "email_password":
            if not register_data.password:
                raise HTTPException(status_code=400, detail="Password is required for email_password method")
            
            # Validate password format
            is_valid_password, password_error = validate_password(register_data.password)
            if not is_valid_password:
                raise HTTPException(status_code=400, detail=password_error)
            
            hashed_password = auth_service.hash_password(register_data.password)
        # elif register_data.method == "google":
        #     if not register_data.google_id:
        #         raise HTTPException(status_code=400, detail="Google ID is required for google method")
        #     # Kiểm tra google_id đã tồn tại chưa
        #     existing_google_user = await factory.user_manager.get_by_google_id(register_data.google_id)
        #     if existing_google_user:
        #         raise HTTPException(status_code=400, detail="Google account already exists")
        
        features = {
            "dashboard": True,
            "social": True, 
            "bot": True,
            "knowledge": True,
            "company": True,
            "history": True,
            "feedback": True,
            "notification": True,
            "product": True,
            "warehouse": True,
            "order": True,
            "leads": True,
            "settings": True,
            "priority_support": False,
            "advanced_analytics": False
        }
        
        # Tạo user với email_verified = True vì đã xác thực
        user = await factory.user_manager.create_user(
            name=register_data.name,
            email=register_data.email,
            password=hashed_password,
            method=register_data.method,
            avatar_url=register_data.avatar_url,
            roles="user",
            email_verified=True,
            packages="p_free_trial",  # Gán gói Free Trial mặc định
            features=features
        )

        # Tạo cấu trúc phân cấp mặc định cho user mới
        await factory.hierarchy_manager.create_hierarchy(
            user_id=user["_id"],
            parent=PARENT_ORG_ID,
            children=[]
        )

        await factory.hierarchy_manager.add_child(
            user_id=PARENT_ORG_ID,
            child_id=user["_id"]
        )
        
        # Tạo balance mặc định cho user
        await factory.balance_manager.create_balance(user["_id"], 0.0)
        
        # Khởi tạo dữ liệu mặc định cho user mới trong background
        try:
            initializer = await get_default_initializer()
            background_tasks.add_task(initializer.init_user_defaults, str(user["_id"]))
            logger.info(f"Scheduled default data initialization for new user: {user['_id']}")
        except Exception as e:
            logger.warning(f"Failed to schedule user defaults initialization: {str(e)}")
        
        # Create tokens for immediate login
        tokens = auth_service.create_user_tokens(user)
        
        # Update user's refresh token in database
        try:
            await factory.user_manager.update_by_id(
                str(user["_id"]), 
                {"refresh_token": tokens["refresh_token"]}
            )
        except Exception as e:
            logger.warning(f"Failed to update refresh token in database: {e}")
        
        # Remove sensitive data from response
        user_response = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "method": user.get("method", "email_password"),
            "roles": user.get("roles", "user"),
            "packages": user.get("packages"),
            "features": user.get("features", {}),
            "email_verified": True
        }
        
        return {
            "success": True,
            "message": "User registered successfully",
            "user": user_response,
            "tokens": tokens
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-verification-email")
async def send_verification_email(
    email_data: SendVerificationEmailRequest,
    background_tasks: BackgroundTasks,
    factory = Depends(get_management_factory)
):
    """Gửi email xác thực khi đăng ký"""
    try:
        # Kiểm tra rate limit - chỉ cho phép gửi 30s một lần
        can_send = await factory.rate_limit_manager.check_rate_limit(
            identifier=email_data.email,
            action="send_verification_email",
            limit_seconds=30
        )
        
        if not can_send:
            remaining_time = await factory.rate_limit_manager.get_remaining_time(
                identifier=email_data.email,
                action="send_verification_email",
                limit_seconds=30
            )
            raise HTTPException(
                status_code=429, 
                detail=f"Too many verification email requests. Please wait {remaining_time} seconds before trying again."
            )
        
        # Kiểm tra email đã tồn tại chưa
        existing_user = await factory.user_manager.get_by_email(email_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already exists")
        
        # Kiểm tra số lần gửi email trong 1 giờ qua (giới hạn spam)
        attempts = await factory.email_verification_manager.get_verification_attempts(email_data.email)
        if attempts >= 5:  # Giới hạn 5 lần trong 1 giờ
            raise HTTPException(status_code=429, detail="Too many verification attempts. Please try again later.")
        
        # Tạo mã xác thực
        verification_code = auth_service.generate_verification_code()
        
        # Lưu mã xác thực vào database
        await factory.email_verification_manager.store_verification_code(
            email_data.email, 
            verification_code
        )
        
        # Ghi lại hành động thành công
        await factory.rate_limit_manager.record_action(
            identifier=email_data.email,
            action="send_verification_email",
            metadata={"verification_code_sent": True}
        )
        
        # Gửi email trong background
        background_tasks.add_task(
            auth_service.send_verification_email,
            email_data.email,
            verification_code
        )
        
        return {"success": True, "message": "Verification email sent successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send verification email error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    factory = Depends(get_management_factory)
):
    """Refresh access token sử dụng refresh token"""
    try:
        tokens = await auth_service.refresh_access_token(
            refresh_data.refresh_token,
            factory.user_manager
        )
        
        return RefreshResponse(
            access_token=tokens["access_token"],
            token_type=tokens["token_type"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not refresh token")

@router.post("/logout")
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Đăng xuất user (xóa refresh token)"""
    try:
        # Remove refresh token from database
        await factory.user_manager.update_by_id(
            current_user["user_id"],
            {"refresh_token": None}
        )
        
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")

@router.get("/me", response_model=Dict[str, Any])
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy thông tin user hiện tại từ token"""
    try:
        user = await factory.user_manager.get_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get actual limits using limit service
        limit_service = get_limit_service(factory)
        limits_info = await limit_service.get_user_current_limits(current_user["user_id"])
        
        # Remove sensitive data
        user_response = {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "method": user.get("method", "email_password"),
            "roles": user.get("roles", "user"),
            "packages": user.get("current_package"),
            "package_name": user.get("package_name"),
            "package_expires_at": user.get("package_expires_at"),
            "features": user.get("features", {}),
            "limits": limits_info.get("limits", {}),
            "create_at": user.get("create_at"),
            "update_at": user.get("update_at"),
            "email_verified": user.get("email_verified", False)
        }
        
        return {"success": True, "data": user_response}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits", response_model=Dict[str, Any])
async def get_current_user_limits(
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy thông tin limits chi tiết của user hiện tại"""
    try:
        user_id = current_user["user_id"]
        
        # Get actual limits using limit service
        limit_service = get_limit_service(factory)
        limits_info = await limit_service.get_user_current_limits(user_id)
        
        if not limits_info:
            raise HTTPException(status_code=404, detail="Limits information not found")
        
        return {"success": True, "data": limits_info}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user limits error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits/check/{resource_type}")
async def check_resource_limit(
    resource_type: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Kiểm tra xem user có thể tạo thêm resource không"""
    try:
        user_id = current_user["user_id"]
        
        # Validate resource type
        valid_resources = ["social", "bot", "identities", "procedures", "knowledge", "company", "product", "warehouse"]
        if resource_type not in valid_resources:
            raise HTTPException(status_code=400, detail=f"Invalid resource type. Valid types: {valid_resources}")
        
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, resource_type)
        
        return {"success": True, "data": limit_check}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check resource limit error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Đổi password (yêu cầu đăng nhập)"""
    try:
        # Lấy thông tin user
        user = await factory.user_manager.get_by_id(current_user["user_id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Kiểm tra password hiện tại
        if not user.get("password") or not auth_service.verify_password(password_data.current_password, user["password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Validate new password format
        is_valid_password, password_error = validate_password(password_data.new_password)
        if not is_valid_password:
            raise HTTPException(status_code=400, detail=password_error)
        
        # Hash password mới
        new_password_hash = auth_service.hash_password(password_data.new_password)
        
        # Cập nhật password
        await factory.user_manager.update_by_id(
            current_user["user_id"],
            {
                "password": new_password_hash,
                "refresh_token": None  # Logout từ tất cả devices khác
            }
        )
        
        return {"success": True, "message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    
@router.post("/forgot-password")
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    factory = Depends(get_management_factory)
):
    """Gửi email reset password"""
    try:
        # Kiểm tra rate limit - chỉ cho phép gửi 30s một lần
        can_send = await factory.rate_limit_manager.check_rate_limit(
            identifier=forgot_data.email,
            action="forgot_password",
            limit_seconds=30
        )
        
        if not can_send:
            remaining_time = await factory.rate_limit_manager.get_remaining_time(
                identifier=forgot_data.email,
                action="forgot_password",
                limit_seconds=30
            )
            raise HTTPException(
                status_code=429, 
                detail=f"Too many password reset requests. Please wait {remaining_time} seconds before trying again."
            )
        
        # Tìm user bằng email
        user = await factory.user_manager.get_by_email(forgot_data.email)
        
        # Luôn ghi lại hành động bất kể user có tồn tại hay không (để tránh spam)
        await factory.rate_limit_manager.record_action(
            identifier=forgot_data.email,
            action="forgot_password",
            metadata={"user_found": user is not None, "user_id": str(user["_id"]) if user else None}
        )
        
        if not user:
            # Không trả về lỗi để tránh enumerate users
            return {"success": True, "message": "If email exists, reset instructions have been sent"}
        
        # Tạo reset token
        reset_token = auth_service.create_reset_password_token(str(user["_id"]), forgot_data.email)
        logger.info(f"Generated reset token for user {user['_id']}: {reset_token[:50]}...")
        
        # Lấy thời gian hết hạn
        expiry_time = auth_service.get_reset_token_expiry()
        logger.info(f"Generated expiry time (UTC): {expiry_time}")
        
        # Lưu reset token vào database
        await factory.user_manager.update_by_id(
            str(user["_id"]),
            {
                "reset_password_token": reset_token,
                "reset_password_expires": expiry_time
            }
        )
        logger.info(f"Saved reset token to database for user {user['_id']}")
        
        # Gửi email trong background
        background_tasks.add_task(
            auth_service.send_reset_password_email,
            forgot_data.email,
            user["name"],
            reset_token
        )
        
        return {"success": True, "message": "If email exists, reset instructions have been sent"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/reset-password", response_class=HTMLResponse)
async def get_reset_password_page(
    token: str,
    factory = Depends(get_management_factory)
):
    """FE không sử dụng (/forgot-password sẽ gửi email đến user => nhấp vào link trong email sẽ được điều hướng đến API này để nhập Password mới)"""
    try:
        # Verify reset token để kiểm tra tính hợp lệ
        logger.info(f"Verifying reset token: {token[:50]}...")
        user_id, email = auth_service.verify_reset_password_token(token)
        logger.info(f"Token verified successfully for user_id: {user_id}, email: {email}")
        
        # Tìm user và kiểm tra token
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            logger.error(f"User not found for user_id: {user_id}")
            return f"""
            <html>
            <head><title>Reset Password - Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>Reset Password</h2>
                <p style="color: red;">Invalid reset token. Please request a new password reset.</p>
                <a href="https://api-mesale.mekongai.com/api/v1/auth/forgot-password" style="color: #007bff;">Request New Reset</a>
            </body>
            </html>
            """
        
        # Log thông tin debug
        db_token = user.get("reset_password_token")
        db_expires = user.get("reset_password_expires")
        logger.info(f"Database token: {db_token[:50] if db_token else 'None'}...")
        logger.info(f"Database expires: {db_expires}")
        logger.info(f"Current time (UTC): {get_vietnam_now_naive()}")
        logger.info(f"Tokens match: {db_token == token}")
        
        # Kiểm tra token trong database
        token_valid = auth_service.is_reset_token_valid(user.get("reset_password_expires"))
        logger.info(f"Token valid check result: {token_valid}")
        
        if (user.get("reset_password_token") != token or not token_valid):
            logger.warning(f"Token validation failed - token match: {user.get('reset_password_token') == token}, token valid: {token_valid}")
            return f"""
            <html>
            <head><title>Reset Password - Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>Reset Password</h2>
                <p style="color: red;">Your reset token has expired. Please request a new password reset.</p>
                <a href="https://api-mesale.mekongai.com/api/v1/auth/forgot-password" style="color: #007bff;">Request New Reset</a>
            </body>
            </html>
            """
        
        # Token hợp lệ, hiển thị form reset password
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Reset Password - MekongAI</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 400px;
                    margin: 50px auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h2 {{
                    text-align: center;
                    color: #333;
                    margin-bottom: 30px;
                }}
                .form-group {{
                    margin-bottom: 20px;
                }}
                label {{
                    display: block;
                    margin-bottom: 5px;
                    color: #555;
                }}
                input[type="password"] {{
                    width: 100%;
                    padding: 12px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    font-size: 16px;
                    box-sizing: border-box;
                }}
                button {{
                    width: 100%;
                    padding: 12px;
                    background-color: #007bff;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 16px;
                    cursor: pointer;
                }}
                button:hover {{
                    background-color: #0056b3;
                }}
                .message {{
                    margin-top: 15px;
                    padding: 10px;
                    border-radius: 4px;
                    text-align: center;
                }}
                .success {{
                    background-color: #d4edda;
                    color: #155724;
                    border: 1px solid #c3e6cb;
                }}
                .error {{
                    background-color: #f8d7da;
                    color: #721c24;
                    border: 1px solid #f5c6cb;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Reset Your Password</h2>
                <p>Enter your new password for: <strong>{email}</strong></p>
                
                <form id="resetForm">
                    <div class="form-group">
                        <label for="newPassword">New Password:</label>
                        <input type="password" id="newPassword" name="newPassword" required minlength="8" 
                               placeholder="At least 8 characters with uppercase, lowercase, number & special char">
                    </div>
                    
                    <div class="form-group">
                        <label for="confirmPassword">Confirm Password:</label>
                        <input type="password" id="confirmPassword" name="confirmPassword" required minlength="8">
                    </div>
                    
                    <button type="submit">Reset Password</button>
                </form>
                
                <div id="message"></div>
            </div>

            <script>
                document.getElementById('resetForm').addEventListener('submit', async function(e) {{
                    e.preventDefault();
                    
                    const newPassword = document.getElementById('newPassword').value;
                    const confirmPassword = document.getElementById('confirmPassword').value;
                    const messageDiv = document.getElementById('message');
                    
                    // Validate passwords match
                    if (newPassword !== confirmPassword) {{
                        messageDiv.innerHTML = '<div class="message error">Passwords do not match!</div>';
                        return;
                    }}
                    
                    // Validate password length
                    if (newPassword.length < 8) {{
                        messageDiv.innerHTML = '<div class="message error">Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character!</div>';
                        return;
                    }}
                    
                    try {{
                        const response = await fetch('/api/v1/auth/reset-password', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                            body: JSON.stringify({{
                                token: '{token}',
                                new_password: newPassword
                            }})
                        }});
                        
                        const result = await response.json();
                        
                        if (response.ok && result.success) {{
                            messageDiv.innerHTML = '<div class="message success">Password reset successfully! You can now login with your new password.</div>';
                            document.getElementById('resetForm').style.display = 'none';
                        }} else {{
                            messageDiv.innerHTML = '<div class="message error">' + (result.detail || 'An error occurred') + '</div>';
                        }}
                    }} catch (error) {{
                        messageDiv.innerHTML = '<div class="message error">Network error. Please try again.</div>';
                    }}
                }});
            </script>
        </body>
        </html>
        """
        
        return html_content
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reset password page error: {str(e)}")
        return """
        <html>
        <head><title>Reset Password - Error</title></head>
        <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
            <h2>Reset Password</h2>
            <p style="color: red;">An error occurred. Please try again later.</p>
        </body>
        </html>
        """


@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPasswordRequest,
    factory = Depends(get_management_factory)
):
    """FE không sử dụng - Reset password using reset token"""
    try:
        # Verify reset token
        logger.info(f"Verifying reset token for password reset: {reset_data.token[:50]}...")
        user_id, email = auth_service.verify_reset_password_token(reset_data.token)
        logger.info(f"Token verified - user_id: {user_id}, email: {email}")
        
        # Get user and verify token in database
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            logger.error(f"User not found for user_id: {user_id}")
            raise HTTPException(status_code=400, detail="Invalid reset token")
        
        # Log database token info
        db_token = user.get("reset_password_token")
        db_expires = user.get("reset_password_expires")
        logger.info(f"Database token: {db_token[:50] if db_token else 'None'}...")
        logger.info(f"Database expires: {db_expires}")
        logger.info(f"Current time (UTC): {get_vietnam_now_naive()}")
        logger.info(f"Tokens match: {db_token == reset_data.token}")
        
        # Check token in database
        token_valid = auth_service.is_reset_token_valid(user.get("reset_password_expires"))
        logger.info(f"Token validity check: {token_valid}")
        
        if (user.get("reset_password_token") != reset_data.token or not token_valid):
            logger.warning(f"Token validation failed - match: {user.get('reset_password_token') == reset_data.token}, valid: {token_valid}")
            raise HTTPException(status_code=400, detail="Reset token has expired")
        
        # Validate new password format
        is_valid_password, password_error = validate_password(reset_data.new_password)
        if not is_valid_password:
            raise HTTPException(status_code=400, detail=password_error)
        
        # Hash new password
        new_password_hash = auth_service.hash_password(reset_data.new_password)
        
        # Update password and clear reset token
        await factory.user_manager.update_by_id(
            user_id,
            {
                "password": new_password_hash,
                "reset_password_token": None,
                "reset_password_expires": None,
                "refresh_token": None  # Logout from all devices
            }
        )
        
        return {"success": True, "message": "Password reset successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# @router.post("/check-rate-limit")
# async def check_rate_limit(
#     rate_limit_data: RateLimitCheckRequest,
#     factory = Depends(get_management_factory)
# ):
#     """Kiểm tra rate limit cho một action cụ thể"""
#     try:
#         # Kiểm tra các action hợp lệ
#         valid_actions = ["send_verification_email", "forgot_password"]
#         if rate_limit_data.action not in valid_actions:
#             raise HTTPException(status_code=400, detail=f"Invalid action. Valid actions: {valid_actions}")
        
#         # Kiểm tra rate limit
#         can_perform = await factory.rate_limit_manager.check_rate_limit(
#             identifier=rate_limit_data.email,
#             action=rate_limit_data.action,
#             limit_seconds=30
#         )
        
#         remaining_time = 0
#         if not can_perform:
#             remaining_time = await factory.rate_limit_manager.get_remaining_time(
#                 identifier=rate_limit_data.email,
#                 action=rate_limit_data.action,
#                 limit_seconds=30
#             )
        
#         # Đếm số lần thực hiện trong 24h qua
#         action_count_24h = await factory.rate_limit_manager.get_action_count(
#             identifier=rate_limit_data.email,
#             action=rate_limit_data.action,
#             hours=24
#         )
        
#         return {
#             "success": True,
#             "data": {
#                 "can_perform": can_perform,
#                 "remaining_time": remaining_time,
#                 "action_count_24h": action_count_24h,
#                 "rate_limit_seconds": 30
#             }
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Check rate limit error: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error")
