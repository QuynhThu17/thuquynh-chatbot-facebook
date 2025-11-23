"""
Social Media Management Module
Quản lý socials, social_accounts và các platform accounts (Facebook, Instagram, Twitter, LinkedIn)
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from bson import ObjectId
from .base_manager import BaseManager
from .notification_mixin import SocialNotificationMixin
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.ultils.notification_background_tasks import run_in_background

logger = logging.getLogger(__name__)

class SocialManager(BaseManager):
    """Manager cho socials collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "socials")
    
    async def create_social(self, name: str, logo_url: str = None) -> Dict[str, Any]:
        """Tạo social platform mới"""
        social_data = {
            "name": name,
            "logo_url": logo_url
        }
        return await self.create(social_data)
    
    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Lấy social theo name"""
        socials = await self.get_all(filter_query={"name": name}, limit=1)
        return socials[0] if socials else None
    
    async def get_social_by_id(self, social_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Lấy social theo ID"""
        return await self.get_by_id(social_id)


class SocialAccountManager(BaseManager, SocialNotificationMixin):
    """Manager cho social_accounts collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "social_accounts")
        self.init_notification_mixin(db_manager)
    
    async def create_social_account(self, social_id: str, user_id: str, 
                                  social_account_user_id: str, social_account_name: str,
                                  social_account_avatar_url: str = None, 
                                  social_account_access_token: str = None) -> Dict[str, Any]:
        """Tạo social account mới"""
        account_data = {
            "social_id": social_id,
            "user_id": user_id,
            "social_account_user_id": social_account_user_id,
            "social_account_name": social_account_name,
            "social_account_avatar_url": social_account_avatar_url,
            "social_account_access_token": social_account_access_token
        }
        result = await self.create(account_data)
        
        # Gửi notification kết nối thành công
        if result:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Kết nối tài khoản mạng xã hội thành công",
                content=f"Bạn đã kết nối tài khoản {social_account_name}",
                category="social",
                notification_type="success",
                action="account_connected",
                priority=1,
                metadata={
                    "social_id": str(social_id),
                    "account_id": str(result["_id"]),
                    "account_name": social_account_name
                }
            )
        
        return result
    
    async def get_by_user_id(self, user_id: str, social_id: str = None) -> List[Dict[str, Any]]:
        """Lấy social accounts theo user_id"""
        filter_query = {"user_id": user_id}
        if social_id:
            filter_query["social_id"] = social_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_social_user_id(self, social_account_user_id: str, social_id: str) -> Optional[Dict[str, Any]]:
        """Lấy social account theo social_account_user_id và social_id"""
        accounts = await self.get_all(
            filter_query={
                "social_account_user_id": social_account_user_id,
                "social_id": social_id
            }, 
            limit=1
        )
        return accounts[0] if accounts else None
    
    async def update_access_token(self, account_id: Union[str, ObjectId], 
                                access_token: str) -> Optional[Dict[str, Any]]:
        """Cập nhật access token"""
        return await self.update_by_id(account_id, {"social_account_access_token": access_token})
    
    async def get_social_account_by_id(self, account_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Lấy social account theo ID"""
        return await self.get_by_id(account_id)


class FacebookPageManager(BaseManager):
    """Manager cho social_facebook_pages collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "social_facebook_pages")
    
    async def create_facebook_page(self, fb_page_id: str, fb_page_name: str, 
                                 social_account_id: str, fb_page_avatar: str = None,
                                 fb_page_access_token: str = None, is_connected: bool = False,
                                 webhook_verified: bool = False) -> Dict[str, Any]:
        """Tạo Facebook page mới"""
        page_data = {
            "fb_page_id": fb_page_id,
            "fb_page_name": fb_page_name,
            "fb_page_avatar": fb_page_avatar,
            "fb_page_access_token": fb_page_access_token,
            "social_account_id": social_account_id,
            "is_connected": is_connected,
            "webhook_verified": webhook_verified
        }
        return await self.create(page_data)
    
    async def get_by_social_account_id(self, social_account_id: str) -> List[Dict[str, Any]]:
        """Lấy FB pages theo social_account_id"""
        return await self.get_all(filter_query={"social_account_id": social_account_id})
    
    async def get_by_fb_page_id(self, fb_page_id: str) -> Optional[Dict[str, Any]]:
        """Lấy FB page theo fb_page_id"""
        pages = await self.get_all(filter_query={"fb_page_id": fb_page_id}, limit=1)
        return pages[0] if pages else None
    
    async def delete_by_fb_page_id(self, fb_page_id: str) -> bool:
        """Xóa FB page theo fb_page_id"""
        page = await self.get_by_fb_page_id(fb_page_id)
        if page:
            return await self.delete_by_id(page["_id"])
        return False
    
    async def connect_page(self, page_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Kết nối page với bot"""
        return await self.update_by_id(page_id, {"is_connected": True})
    
    async def disconnect_page(self, page_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Ngắt kết nối page với bot"""
        return await self.update_by_id(page_id, {"is_connected": False})
    
    async def verify_webhook(self, page_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Verify webhook cho page"""
        return await self.update_by_id(page_id, {"webhook_verified": True})
    
    async def get_connected_pages(self, social_account_id: str = None) -> List[Dict[str, Any]]:
        """Lấy tất cả pages đã kết nối"""
        filter_query = {"is_connected": True}
        if social_account_id:
            filter_query["social_account_id"] = social_account_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_facebook_page_by_id(self, page_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Lấy Facebook page theo ID"""
        return await self.get_by_id(page_id)


# Factory class để tạo tất cả social media managers
class SocialMediaManagementFactory:
    """Factory để tạo tất cả Social Media Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._social_manager = None
        self._social_account_manager = None
        self._facebook_page_manager = None
        self._instagram_account_manager = None
        self._twitter_account_manager = None
        self._linkedin_account_manager = None
    
    @property
    def social_manager(self) -> SocialManager:
        if self._social_manager is None:
            self._social_manager = SocialManager(self.db_manager)
        return self._social_manager
    
    @property
    def social_account_manager(self) -> SocialAccountManager:
        if self._social_account_manager is None:
            self._social_account_manager = SocialAccountManager(self.db_manager)
        return self._social_account_manager
    
    @property
    def facebook_page_manager(self) -> FacebookPageManager:
        if self._facebook_page_manager is None:
            self._facebook_page_manager = FacebookPageManager(self.db_manager)
        return self._facebook_page_manager
