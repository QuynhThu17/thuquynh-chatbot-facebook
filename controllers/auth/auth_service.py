"""
JWT Authentication Service
Quản lý authentication, JWT token creation và validation
"""

import jwt
import bcrypt
import random
import smtplib
from datetime import datetime, timedelta, timezone
from configs.environment import get_vietnam_now_naive
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from fastapi import HTTPException
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import logging
logger = logging.getLogger(__name__)

from configs.constant import (
    SECRET_KEY, JWT_REFRESH_KEY, ALGORITHM, 
    ACCESS_TOKEN_EXPIRE_MINUTES, ACCESS_REFRESH_TOKEN_EXPIRE_DAY,
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, VERIFICATION_TIMEOUT
)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.refresh_key = JWT_REFRESH_KEY
        self.algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = ACCESS_REFRESH_TOKEN_EXPIRE_DAY

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        vietnam_timezone = timezone(timedelta(hours=7))
        
        if expires_delta:
            expire = datetime.now(vietnam_timezone) + expires_delta
        else:
            expire = datetime.now(vietnam_timezone) + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        vietnam_timezone = timezone(timedelta(hours=7))
        
        if expires_delta:
            expire = datetime.now(vietnam_timezone) + expires_delta
        else:
            expire = datetime.now(vietnam_timezone) + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.refresh_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str, use_refresh_key: bool = False) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            key = self.refresh_key if use_refresh_key else self.secret_key
            payload = jwt.decode(token, key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    async def authenticate_user(self, user_manager, email_or_username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email/username and password"""
        try:
            # Try to get user by email first
            user = await user_manager.get_by_email(email_or_username)
            
            # If not found by email, try by username (if user_manager supports it)
            if not user:
                # Try to get by other field if available
                users = await user_manager.get_all(limit=1000)  # Get all and filter
                for u in users:
                    if u.get("name") == email_or_username:
                        user = u
                        break
            
            if not user:
                return None

            # Verify password
            if not self.verify_password(password, user.get("password", "")):
                return None

            return user
        except Exception as e:
            logger.info(f"Authentication error: {e}")
            return None

    def create_user_tokens(self, user: Dict[str, Any]) -> Dict[str, str]:
        """Create both access and refresh tokens for user"""
        # Create token data
        # user_id trong JWT = str(user["_id"]) từ MongoDB
        token_data = {
            "user_id": str(user["_id"]),  # Convert MongoDB ObjectId to string
            "email": user["email"],
            "name": user["name"],
            "roles": user.get("roles", [])
        }

        # Create tokens
        access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
        refresh_token_expires = timedelta(days=self.refresh_token_expire_days)

        access_token = self.create_access_token(
            data=token_data, 
            expires_delta=access_token_expires
        )
        
        refresh_token = self.create_refresh_token(
            data=token_data, 
            expires_delta=refresh_token_expires
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def refresh_access_token(self, refresh_token: str, user_manager) -> Dict[str, str]:
        """Refresh access token using refresh token"""
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, use_refresh_key=True)
            user_id = payload.get("user_id")
            
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid refresh token")

            # Get user from database
            user = await user_manager.get_by_id(user_id)
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            # Create new access token
            access_token_expires = timedelta(minutes=self.access_token_expire_minutes)
            token_data = {
                "user_id": str(user["_id"]),
                "email": user["email"],
                "name": user["name"],
                "roles": user.get("roles", [])
            }

            access_token = self.create_access_token(
                data=token_data,
                expires_delta=access_token_expires
            )

            return {
                "access_token": access_token,
                "token_type": "bearer"
            }

        except Exception as e:
            raise HTTPException(status_code=401, detail="Could not refresh token")

    def create_reset_password_token(self, user_id: str, email: str) -> str:
        """Tạo token cho reset password"""
        # Sử dụng UTC time để tương thích với MongoDB
        expire = get_vietnam_now_naive() + timedelta(hours=1)  # Token hết hạn trong 1 giờ
        
        token_data = {
            "user_id": user_id,
            "email": email,
            "purpose": "reset_password",
            "exp": expire
        }
        
        reset_token = jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created reset token with expiry (UTC): {expire}")
        return reset_token

    def verify_reset_password_token(self, token: str) -> tuple[str, str]:
        """Verify reset password token và trả về user_id, email"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("purpose") != "reset_password":
                raise HTTPException(status_code=400, detail="Invalid token purpose")
            
            user_id = payload.get("user_id")
            email = payload.get("email")
            exp = payload.get("exp")
            logger.info(f"Token verified - user_id: {user_id}, email: {email}, exp: {exp}")
            
            if not user_id or not email:
                raise HTTPException(status_code=400, detail="Invalid token data")
            
            return user_id, email
            
        except jwt.ExpiredSignatureError:
            logger.error("JWT token has expired during verification")
            raise HTTPException(status_code=400, detail="Reset token has expired")
        except jwt.InvalidTokenError:
            logger.error("JWT token is invalid during verification")
            raise HTTPException(status_code=400, detail="Invalid reset token")

    def get_reset_token_expiry(self) -> datetime:
        """Lấy thời gian hết hạn cho reset token - Sử dụng UTC time"""
        expiry = get_vietnam_now_naive() + timedelta(hours=1)
        logger.info(f"Generated expiry time (UTC): {expiry}")
        return expiry

    def is_reset_token_valid(self, expiry_time: Optional[datetime]) -> bool:
        """Kiểm tra reset token còn hạn không"""
        if not expiry_time:
            logger.warning("No expiry time provided")
            return False
        
        # Sử dụng UTC time để so sánh
        current_time = get_vietnam_now_naive()
        
        # MongoDB lưu datetime mà không có timezone info, coi như UTC
        if expiry_time.tzinfo is not None:
            # Nếu có timezone info, convert về UTC
            expiry_time = expiry_time.utctimetuple()
            expiry_time = datetime(*expiry_time[:6])
        
        logger.info(f"Token validity check (UTC) - current: {current_time}, expiry: {expiry_time}, valid: {current_time < expiry_time}")
        return current_time < expiry_time

    def _build_email_html(self, title: str, content: str, subtitle: Optional[str] = None) -> str:
        """Compose a shared HTML wrapper for transactional emails."""
        current_year = datetime.now(timezone.utc).year
        subtitle_section = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
        return f"""
        <html>
        <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <style>
                body {{ background-color: #f3f4f6; margin: 0; padding: 24px; font-family: 'Inter', Arial, sans-serif; color: #111827; }}
                .wrapper {{ max-width: 620px; margin: 0 auto; }}
                .card {{ background-color: #ffffff; border-radius: 14px; padding: 28px; box-shadow: 0 12px 32px rgba(15, 23, 42, 0.08); border: 1px solid #e5e7eb; }}
                .header {{ display: flex; align-items: center; gap: 12px; font-size: 14px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #111827; }}
                .logo-dot {{ width: 10px; height: 10px; background-color: #2563eb; border-radius: 999px; display: inline-block; }}
                .title {{ font-size: 18px; margin: 24px 0 12px; font-weight: 600; color: #111827; }}
                .subtitle {{ margin: 0 0 20px; font-size: 14px; color: #4b5563; }}
                .content {{ font-size: 14px; line-height: 1.6; color: #111827; }}
                .content p {{ margin: 0 0 14px; }}
                .greeting {{ margin-bottom: 16px; }}
                .highlight {{ color: #2563eb; font-weight: 600; }}
                .muted {{ color: #6b7280; }}
                .action {{ margin: 28px 0; text-align: center; }}
                .button {{ background-color: #2563eb; color: #ffffff; padding: 12px 28px; border-radius: 999px; text-decoration: none; font-weight: 600; display: inline-block; }}
                .button:hover {{ background-color: #1d4ed8; }}
                .link-box {{ word-break: break-word; padding: 14px; background-color: #f9fafb; border-radius: 12px; border: 1px dashed #d1d5db; font-size: 13px; color: #1f2937; }}
                .code-wrapper {{ margin: 24px 0; padding: 18px 24px; background-color: #f9fafb; border: 1px solid #dbeafe; border-radius: 12px; text-align: center; }}
                .code-label {{ display: block; font-size: 12px; letter-spacing: 0.08em; color: #6b7280; text-transform: uppercase; margin-bottom: 8px; }}
                .code {{ font-size: 18px; letter-spacing: 0.35em; font-weight: 700; color: #2563eb; }}
                .footer {{ margin-top: 32px; font-size: 12px; color: #9ca3af; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="card">
                    <div class="header">
                        <span class="logo-dot"></span>
                        <span>MekongAI</span>
                    </div>
                    <h1 class="title">{title}</h1>
                    {subtitle_section}
                    <div class="content">
                        {content}
                    </div>
                    <p class="footer">&copy; {current_year} MekongAI. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """.strip()

    async def send_reset_password_email(self, email: str, name: str, reset_token: str) -> bool:
        """Send reset password email with a modern HTML template."""
        try:
            reset_link = f"https://api-mesale.mekongai.com/api/v1/auth/reset-password?token={reset_token}"
            subject = "Reset Your Password - HueAI"
            text_body = (
                f"Hi {name},\n\n"
                "We received a request to reset the password for your HueAI account.\n\n"
                f"Reset link: {reset_link}\n\n"
                "The link expires in 1 hour. If you didn't request this, you can ignore the email.\n\n"
                "Best regards,\n"
                "HueAI Team"
            )

            content_html = f"""
<p class="greeting">Hi <span class="highlight">{name}</span>,</p>
<p>We received a request to reset the password for your HueAI account.</p>
<p>If this was you, use the button below to set a new password right away.</p>
<div class="action">
    <a class="button" href="{reset_link}">Reset password</a>
</div>
<p class="muted">If the button does not work, copy and paste the link below into your browser:</p>
<p class="link-box">{reset_link}</p>
<p class="muted">This link stays active for 1 hour.</p>
<p class="muted">If you didn't make this request, you can safely ignore this message.</p>
""".strip()

            html_body = self._build_email_html(
                title="Reset Your Password",
                subtitle="Securely update your credentials in just a minute.",
                content=content_html,
            )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Reset password email sent successfully to {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send reset password email: {e}")
            return False

    def generate_verification_code(self) -> str:
        """Tạo mã xác thực email 6 số"""
        return str(random.randint(100000, 999999))

    async def send_verification_email(self, email: str, verification_code: str) -> bool:
        """Send verification email with HTML styling and fallback text."""
        try:
            subject = "Verify Your Email - MekongAI"
            expiry_minutes = max(1, (VERIFICATION_TIMEOUT + 59) // 60)
            minute_suffix = "s" if expiry_minutes != 1 else ""

            text_body = (
                "Hello,\n\n"
                "Thank you for signing up with MekongAI!\n\n"
                f"Your email verification code is: {verification_code}\n\n"
                f"The code expires in {expiry_minutes} minute{minute_suffix}.\n\n"
                "If you didn't create an account with us, please ignore this email.\n\n"
                "Best regards,\n"
                "MekongAI Team"
            )

            content_html = f"""
<p class="greeting">Hello,</p>
<p>Thanks for joining MekongAI. Use the code below to verify your email address.</p>
<div class="code-wrapper">
    <span class="code-label">Verification Code</span>
    <div class="code">{verification_code}</div>
</div>
<p class="muted">The code expires in {expiry_minutes} minute{minute_suffix}.</p>
<p class="muted">Didn't create this account? You can safely ignore this message.</p>
""".strip()

            html_body = self._build_email_html(
                title="Verify Your Email",
                subtitle="Confirm your address to activate your MekongAI account.",
                content=content_html,
            )

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = email
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Verification email sent to {email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send verification email: {e}")
            return False

    def create_verification_token(self, email: str, verification_code: str) -> str:
        """Tạo token tạm thời cho verification"""
        vietnam_timezone = timezone(timedelta(hours=7))
        expire = datetime.now(vietnam_timezone) + timedelta(seconds=VERIFICATION_TIMEOUT)
        
        token_data = {
            "email": email,
            "verification_code": verification_code,
            "purpose": "email_verification",
            "exp": expire
        }
        
        return jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)

    def verify_verification_token(self, token: str) -> tuple[str, str]:
        """Verify email verification token và trả về email, verification_code"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("purpose") != "email_verification":
                raise HTTPException(status_code=400, detail="Invalid token purpose")
            
            email = payload.get("email")
            verification_code = payload.get("verification_code")
            
            if not email or not verification_code:
                raise HTTPException(status_code=400, detail="Invalid token data")
            
            return email, verification_code
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Verification code has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Invalid verification token")

# Global auth service instance
auth_service = AuthService()
