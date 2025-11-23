"""
Email Service
Cung cấp các chức năng gửi email thông báo cho hệ thống
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from configs.constant import (
    SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
)

logger = logging.getLogger(__name__)

class EmailService:
    """Service để gửi các loại email thông báo"""
    
    @staticmethod
    async def send_notification_email(
        email: str,
        name: str,
        title: str,
        content: str,
        category: str = "system",
        action: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Gửi email thông báo cho user
        
        Args:
            email: Email người nhận 
            name: Tên người nhận
            title: Tiêu đề notification
            content: Nội dung notification
            category: Loại thông báo (social, crm, conversation, etc.)
            action: Hành động (new_order, new_customer, new_message, etc.)
            metadata: Dữ liệu bổ sung
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            # Tạo subject phù hợp với category
            subject_prefix = {
                "social": "📱 Social Media",
                "crm": "👥 CRM",
                "conversation": "💬 Tin nhắn",
                "business": "🏢 Business", 
                "system": "⚙️ Hệ thống",
                "auth": "🔐 Bảo mật",
                "bot": "🤖 Bot",
                "payment": "💳 Thanh toán",
                "subscription": "📋 Đăng ký"
            }.get(category, "📢")
            
            subject = f"{subject_prefix} - {title}"
            
            # Tạo nội dung email
            body = f"""
            Xin chào {name},
            
            {content}
            
            {"" if not metadata else f"Chi tiết: {metadata}"}
            
            Đây là email thông báo tự động từ hệ thống MekongAI.
            
            Trân trọng,
            Đội ngũ MekongAI
            """
            
            # Tạo email
            msg = MIMEMultipart()
            msg['From'] = SMTP_USER
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Gửi email
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            text = msg.as_string()
            server.sendmail(SMTP_USER, email, text)
            server.quit()
            
            logger.info(f"Notification email sent to {email} - {title}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification email to {email}: {e}")
            return False

    @staticmethod
    async def send_support_notification_email(
        email: str,
        name: str,
        support_type: str,
        message: str,
        user_id: str = None
    ) -> bool:
        """
        Gửi email thông báo cho admin khi có yêu cầu hỗ trợ
        
        Args:
            email: Email admin
            name: Tên user cần hỗ trợ
            support_type: Loại hỗ trợ (live_chat, feedback, bug_report)
            message: Nội dung yêu cầu
            user_id: ID của user
            
        Returns:
            bool: True nếu gửi thành công
        """
        try:
            support_labels = {
                "live_chat": "💬 Yêu cầu Chat Trực Tiếp",
                "feedback": "📝 Feedback",
                "bug_report": "🐛 Báo Lỗi",
                "feature_request": "✨ Yêu cầu Tính Năng"
            }
            
            subject = f"{support_labels.get(support_type, '❓ Hỗ Trợ')} - {name}"
            
            body = f"""
            Yêu cầu hỗ trợ mới từ khách hàng:
            
            👤 Khách hàng: {name}
            📧 Email: {email if not user_id else 'Đã đăng nhập'}
            🆔 User ID: {user_id or 'Guest'}
            📋 Loại: {support_type}
            
            💬 Nội dung:
            {message}
            
            ---
            Thông báo tự động từ hệ thống MekongAI
            """
            
            # Gửi tới email admin (có thể config trong settings)
            admin_email = SMTP_USER  # Tạm thời dùng SMTP_USER, sau này có thể config
            
            msg = MIMEMultipart()
            msg['From'] = SMTP_USER
            msg['To'] = admin_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            text = msg.as_string()
            server.sendmail(SMTP_USER, admin_email, text)
            server.quit()
            
            logger.info(f"Support notification sent to admin - {support_type} from {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send support notification: {e}")
            return False