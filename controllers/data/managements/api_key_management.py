"""
API Key Management Module
=========================
Quản lý API Keys cho White Label Partners và external integrations
"""

import logging
import secrets
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bson import ObjectId
from .base_manager import BaseManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

class APIKeyManager(BaseManager):
    """Manager cho API keys collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "api_keys")
    
    def generate_api_key(self, prefix: str = "mk") -> str:
        """
        Generate một API key ngẫu nhiên
        Format: mk_live_xxxxxxxxxxxxxxxxxxxxxxxx
        """
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_live_{random_part}"
    
    def hash_api_key(self, api_key: str) -> str:
        """Hash API key để lưu vào database (bảo mật)"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    async def create_api_key(
        self,
        owner_id: str,
        owner_type: str,  # "white_label", "partner", "user"
        name: str,
        permissions: List[str] = None,
        rate_limits: Dict[str, Any] = None,
        expires_at: datetime = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Tạo API key mới
        
        Args:
            owner_id: ID của owner (user_id hoặc partner_id)
            owner_type: Loại owner
            name: Tên mô tả cho API key
            permissions: List permissions được phép
            rate_limits: Giới hạn rate limiting
            expires_at: Thời gian hết hạn
            metadata: Metadata bổ sung
        
        Returns:
            Dictionary chứa API key info (bao gồm plain API key)
        """
        # Generate API key
        api_key = self.generate_api_key()
        hashed_key = self.hash_api_key(api_key)
        
        # Tạo data
        key_data = {
            "hashed_key": hashed_key,
            "owner_id": owner_id,
            "owner_type": owner_type,
            "name": name,
            "permissions": permissions or ["read"],
            "rate_limits": rate_limits or {
                "requests_per_minute": 60,
                "requests_per_hour": 1000,
                "requests_per_day": 10000
            },
            "status": "active",
            "expires_at": expires_at,
            "last_used_at": None,
            "usage_count": 0,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        result = await self.create(key_data)
        
        # Trả về kèm plain API key (chỉ lần này duy nhất)
        result["api_key"] = api_key
        return result
    
    async def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Verify API key và trả về thông tin nếu hợp lệ
        
        Args:
            api_key: Plain API key cần verify
            
        Returns:
            Dictionary chứa API key info nếu hợp lệ, None nếu không
        """
        hashed_key = self.hash_api_key(api_key)
        
        keys = await self.get_all(
            filter_query={"hashed_key": hashed_key, "status": "active"},
            limit=1
        )
        
        if not keys:
            return None
        
        key_info = keys[0]
        
        # Kiểm tra expiration
        if key_info.get("expires_at"):
            if datetime.now() > key_info["expires_at"]:
                # Key đã hết hạn
                await self.update_by_id(key_info["_id"], {"status": "expired"})
                return None
        
        # Update usage stats
        await self.update_by_id(
            key_info["_id"],
            {
                "last_used_at": datetime.now(),
                "usage_count": key_info.get("usage_count", 0) + 1
            }
        )
        
        return key_info
    
    async def get_by_owner(self, owner_id: str, owner_type: str = None) -> List[Dict[str, Any]]:
        """Lấy tất cả API keys của một owner"""
        filter_query = {"owner_id": owner_id}
        if owner_type:
            filter_query["owner_type"] = owner_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def revoke_api_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Revoke một API key"""
        return await self.update_by_id(
            key_id,
            {
                "status": "revoked",
                "revoked_at": datetime.now()
            }
        )
    
    async def rotate_api_key(self, key_id: str) -> Dict[str, Any]:
        """
        Rotate API key (tạo key mới và revoke key cũ)
        
        Returns:
            Dictionary chứa API key mới
        """
        old_key = await self.get_by_id(key_id)
        if not old_key:
            raise ValueError("API key not found")
        
        # Revoke old key
        await self.revoke_api_key(key_id)
        
        # Create new key với cùng config
        new_key = await self.create_api_key(
            owner_id=old_key["owner_id"],
            owner_type=old_key["owner_type"],
            name=old_key["name"] + " (Rotated)",
            permissions=old_key.get("permissions"),
            rate_limits=old_key.get("rate_limits"),
            expires_at=old_key.get("expires_at"),
            metadata=old_key.get("metadata")
        )
        
        return new_key
    
    async def check_rate_limit(self, key_id: str, window: str = "minute") -> Dict[str, Any]:
        """
        Kiểm tra rate limit cho API key
        
        Args:
            key_id: ID của API key
            window: Cửa sổ thời gian ("minute", "hour", "day")
            
        Returns:
            Dictionary chứa thông tin rate limit
        """
        key_info = await self.get_by_id(key_id)
        if not key_info:
            return {"allowed": False, "reason": "Key not found"}
        
        rate_limits = key_info.get("rate_limits", {})
        limit_key = f"requests_per_{window}"
        max_requests = rate_limits.get(limit_key, 0)
        
        # TODO: Implement actual rate limiting logic with Redis or similar
        # For now, just return the limit info
        
        return {
            "allowed": True,
            "max_requests": max_requests,
            "remaining": max_requests - 1,  # Placeholder
            "window": window
        }
    
    async def get_usage_stats(self, key_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Lấy thống kê sử dụng của API key
        
        Args:
            key_id: ID của API key
            days: Số ngày lấy thống kê
            
        Returns:
            Dictionary chứa thống kê sử dụng
        """
        key_info = await self.get_by_id(key_id)
        if not key_info:
            return {}
        
        # TODO: Implement detailed usage tracking
        # For now, return basic stats
        
        return {
            "key_id": str(key_id),
            "total_usage": key_info.get("usage_count", 0),
            "last_used_at": key_info.get("last_used_at"),
            "created_at": key_info.get("created_at"),
            "status": key_info.get("status")
        }


class WhiteLabelWebhookManager(BaseManager):
    """Manager cho webhook logs từ White Label systems"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "white_label_webhooks")
    
    async def log_webhook(
        self,
        partner_id: str,
        event_type: str,
        payload: Dict[str, Any],
        status: str = "received",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Log webhook event từ White Label system
        
        Args:
            partner_id: ID của White Label partner
            event_type: Loại event (user_created, bot_created, message_sent, etc.)
            payload: Dữ liệu payload
            status: Trạng thái xử lý
            metadata: Metadata bổ sung
        """
        webhook_data = {
            "partner_id": partner_id,
            "event_type": event_type,
            "payload": payload,
            "status": status,
            "metadata": metadata or {},
            "created_at": datetime.now(),
            "processed_at": None
        }
        
        return await self.create(webhook_data)
    
    async def get_by_partner(
        self,
        partner_id: str,
        event_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Lấy webhook logs theo partner"""
        filter_query = {"partner_id": partner_id}
        if event_type:
            filter_query["event_type"] = event_type
        
        return await self.get_all(
            filter_query=filter_query,
            limit=limit,
            sort=[("created_at", -1)]
        )
    
    async def mark_processed(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Đánh dấu webhook đã được xử lý"""
        return await self.update_by_id(
            webhook_id,
            {
                "status": "processed",
                "processed_at": datetime.now()
            }
        )
