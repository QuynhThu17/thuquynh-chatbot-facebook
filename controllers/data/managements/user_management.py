"""
User Management Module
Quản lý users, hierarchy, features, roles, balances, packages, subscriptions, transactions
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from bson import ObjectId
from .base_manager import BaseManager
from .notification_mixin import AuthNotificationMixin, BusinessNotificationMixin
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.ultils.notification_background_tasks import run_in_background
from configs.environment import get_vietnam_now_naive

logger = logging.getLogger(__name__)

class UserManager(BaseManager, AuthNotificationMixin):
    """Manager cho users collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "users")
        self.init_notification_mixin(db_manager)
    
    async def create_user(self, name: str, email: str, password: str = None, 
                         method: str = "email_password", google_id: str = None,
                         avatar_url: str = None, roles: str = ["user"],
                         email_verified: bool = False, packages: str = None, features: Dict = None, _id: str = None, current_package: str = None, package_name: str = None, limits: Dict = None, package_expires_at: datetime = None) -> Dict[str, Any]:
        """
        Tạo user mới
        
        Args:
            name: Tên user
            email: Email user
            password: Mật khẩu (nếu method = email_password)
            method: Phương thức đăng ký (email_password, google)
            google_id: Google ID (nếu method = google)
            avatar_url: URL avatar
            roles: List các role IDs
            email_verified: Trạng thái xác thực email
            packages: Danh sách các gói (packages) của user
            features: Danh sách các tính năng (features) của user
            current_package: Gói hiện tại của user
            package_name: Tên gói của user
            limits: Giới hạn của user
            package_expires_at: Thời gian hết hạn gói của user
            _id: ID user (nếu có, để tạo với ID cụ thể)
        """
        user_data = {
            "name": name,
            "method": method,
            "email": email,
            "password": password,
            "google_id": google_id,
            "avatar_url": avatar_url,
            "roles": roles,
            "email_verified": email_verified,
            "packages": packages,
            "features": features,
            "current_package": current_package,
            "package_name": package_name,
            "limits": limits,
            "package_expires_at": package_expires_at
        }

        if _id:
            user_data["_id"] = _id

        return await self.create(user_data)
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Lấy user theo email"""
        users = await self.get_all(filter_query={"email": email}, limit=1)
        return users[0] if users else None
    
    async def get_by_google_id(self, google_id: str) -> Optional[Dict[str, Any]]:
        """Lấy user theo Google ID"""
        users = await self.get_all(filter_query={"google_id": google_id}, limit=1)
        return users[0] if users else None
    
    async def update_avatar(self, user_id: Union[str, ObjectId], avatar_url: str) -> Optional[Dict[str, Any]]:
        """Cập nhật avatar user"""
        result = await self.update_by_id(user_id, {"avatar_url": avatar_url})
        
        # Gửi notification
        if result:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Avatar đã được cập nhật",
                content="Avatar của bạn đã được thay đổi thành công",
                category="auth",
                notification_type="info",
                action="avatar_updated",
                priority=1
            )
        
        return result
    
    async def add_role(self, user_id: Union[str, ObjectId], role_id: str) -> Optional[Dict[str, Any]]:
        """Thêm role cho user"""
        user = await self.get_by_id(user_id)
        if user:
            current_roles = user.get("roles", [])
            if role_id not in current_roles:
                current_roles.append(role_id)
                return await self.update_by_id(user_id, {"roles": current_roles})
        return None
    
    async def remove_role(self, user_id: Union[str, ObjectId], role_id: str) -> Optional[Dict[str, Any]]:
        """Xóa role khỏi user"""
        user = await self.get_by_id(user_id)
        if user:
            current_roles = user.get("roles", [])
            if role_id in current_roles:
                current_roles.remove(role_id)
                return await self.update_by_id(user_id, {"roles": current_roles})
        return None


class HierarchyManager(BaseManager):
    """Manager cho hierarchy collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "hierarchy")
    
    async def create_hierarchy(self, user_id: str, parent: str = None, 
                              children: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Tạo hierarchy mới với support cho additional fields"""
        hierarchy_data = {
            "user_id": user_id,
            "parent": parent,
            "children": children or []
        }
        # Thêm tất cả kwargs vào hierarchy_data
        hierarchy_data.update(kwargs)
        return await self.create(hierarchy_data)
    
    async def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy hierarchy theo user_id"""
        hierarchies = await self.get_all(filter_query={"user_id": user_id}, limit=1)
        return hierarchies[0] if hierarchies else None
    
    async def add_child(self, user_id: str, child_id: str) -> Optional[Dict[str, Any]]:
        """Thêm child vào hierarchy"""
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_children = hierarchy.get("children", [])
            if child_id not in current_children:
                current_children.append(child_id)
                return await self.update_by_id(hierarchy["_id"], {"children": current_children})
        return None
    
    async def remove_child(self, user_id: str, child_id: str) -> Optional[Dict[str, Any]]:
        """Xóa child khỏi hierarchy"""
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_children = hierarchy.get("children", [])
            if child_id in current_children:
                current_children.remove(child_id)
                return await self.update_by_id(hierarchy["_id"], {"children": current_children})
        return None


class FeatureManager(BaseManager):
    """Manager cho features collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "features")
    
    async def create_feature(self, name: str, description: str = None) -> Dict[str, Any]:
        """Tạo feature mới"""
        feature_data = {
            "name": name,
            "description": description
        }
        return await self.create(feature_data)
    
    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Lấy feature theo name"""
        features = await self.get_all(filter_query={"name": name}, limit=1)
        return features[0] if features else None


class RoleManager(BaseManager):
    """Manager cho roles collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "roles")
    
    async def create_role(self, name: str, permissions: List[str] = None) -> Dict[str, Any]:
        """Tạo role mới"""
        role_data = {
            "name": name,
            "permissions": permissions or []
        }
        return await self.create(role_data)
    
    async def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Lấy role theo name"""
        roles = await self.get_all(filter_query={"name": name}, limit=1)
        return roles[0] if roles else None
    
    async def add_permission(self, role_id: Union[str, ObjectId], feature_id: str) -> Optional[Dict[str, Any]]:
        """Thêm permission vào role"""
        role = await self.get_by_id(role_id)
        if role:
            current_permissions = role.get("permissions", [])
            if feature_id not in current_permissions:
                current_permissions.append(feature_id)
                return await self.update_by_id(role_id, {"permissions": current_permissions})
        return None


class BalanceManager(BaseManager):
    """Manager cho balances collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "balances")
    
    async def create_balance(self, user_id: str, current_balance: float = 0.0) -> Dict[str, Any]:
        """Tạo balance mới cho user"""
        balance_data = {
            "user_id": user_id,
            "current_balance": current_balance
        }
        return await self.create(balance_data)
    
    async def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy balance theo user_id"""
        balances = await self.get_all(filter_query={"user_id": user_id}, limit=1)
        return balances[0] if balances else None
    
    async def update_balance(self, user_id: str, amount: float, operation: str = "add") -> Optional[Dict[str, Any]]:
        """
        Cập nhật balance
        
        Args:
            user_id: ID user
            amount: Số tiền
            operation: "add" hoặc "subtract"
        """
        balance = await self.get_by_user_id(user_id)
        if balance:
            current = balance.get("current_balance", 0.0)
            if operation == "add":
                new_balance = current + amount
            elif operation == "subtract":
                new_balance = max(0, current - amount)  # Không cho phép âm
            else:
                raise ValueError("Operation must be 'add' or 'subtract'")
            
            return await self.update_by_id(balance["_id"], {"current_balance": new_balance})
        return None


class PackageManager(BaseManager, BusinessNotificationMixin):
    """Manager cho packages collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "packages")
        self.init_notification_mixin(db_manager)
    
    async def create_package(self, name: str, price: float, duration_months: int,
                           description: str = None) -> Dict[str, Any]:
        """Tạo package mới"""
        package_data = {
            "name": name,
            "price": price,
            "duration_months": duration_months,
            "description": description
        }
        return await self.create(package_data)
    
    async def get_active_packages(self) -> List[Dict[str, Any]]:
        """Lấy tất cả packages active"""
        return await self.get_all()


class SubscriptionManager(BaseManager):
    """Manager cho subscriptions collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "subscriptions")
    
    async def create_subscription(self, user_id: str, package_id: str, start_day: datetime = None,
                                duration_months: int = 1, is_auto_renew: bool = False) -> Dict[str, Any]:
        """Tạo subscription mới"""
        if start_day is None:
            start_day = get_vietnam_now_naive()
        
        end_day = start_day + timedelta(days=duration_months * 30)  # Approximation
        
        subscription_data = {
            "user_id": user_id,
            "package_id": package_id,
            "start_day": start_day,
            "end_day": end_day,
            "status": "active",
            "is_auto_renew": is_auto_renew
        }
        return await self.create(subscription_data)
    
    async def get_by_user_id(self, user_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """Lấy subscriptions theo user_id"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(filter_query=filter_query)
    
    async def expire_subscription(self, subscription_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Hết hạn subscription"""
        return await self.update_by_id(subscription_id, {"status": "expired"})
    
    async def cancel_subscription(self, subscription_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Hủy subscription"""
        return await self.update_by_id(subscription_id, {"status": "canceled", "is_auto_renew": False})


class TransactionManager(BaseManager):
    """Manager cho transactions collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "transactions")
    
    async def create_transaction(self, user_id: str, transaction_type: str, amount: float,
                               description: str = None) -> Dict[str, Any]:
        """
        Tạo transaction mới
        
        Args:
            user_id: ID user
            transaction_type: purchase_package, usage, refund
            amount: Số tiền
            description: Mô tả transaction
        """
        transaction_data = {
            "user_id": user_id,
            "type": transaction_type,
            "amount": amount,
            "timestamp": get_vietnam_now_naive(),
            "description": description
        }
        return await self.create(transaction_data)
    
    async def get_by_user_id(self, user_id: str, transaction_type: str = None) -> List[Dict[str, Any]]:
        """Lấy transactions theo user_id"""
        filter_query = {"user_id": user_id}
        if transaction_type:
            filter_query["type"] = transaction_type
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="timestamp",
            sort_order=-1
        )
    
    async def get_user_balance_history(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Lấy lịch sử balance trong N ngày"""
        start_date = get_vietnam_now_naive() - timedelta(days=days)
        filter_query = {
            "user_id": user_id,
            "timestamp": {"$gte": start_date}
        }
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="timestamp",
            sort_order=-1
        )


# Factory class để tạo tất cả managers
class UserManagementFactory:
    """Factory để tạo tất cả User Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._user_manager = None
        self._hierarchy_manager = None
        self._feature_manager = None
        self._role_manager = None
        self._balance_manager = None
        self._package_manager = None
        self._subscription_manager = None
        self._transaction_manager = None
    
    @property
    def user_manager(self) -> UserManager:
        if self._user_manager is None:
            self._user_manager = UserManager(self.db_manager)
        return self._user_manager
    
    @property
    def hierarchy_manager(self) -> HierarchyManager:
        if self._hierarchy_manager is None:
            self._hierarchy_manager = HierarchyManager(self.db_manager)
        return self._hierarchy_manager
    
    @property
    def feature_manager(self) -> FeatureManager:
        if self._feature_manager is None:
            self._feature_manager = FeatureManager(self.db_manager)
        return self._feature_manager
    
    @property
    def role_manager(self) -> RoleManager:
        if self._role_manager is None:
            self._role_manager = RoleManager(self.db_manager)
        return self._role_manager
    
    @property
    def balance_manager(self) -> BalanceManager:
        if self._balance_manager is None:
            self._balance_manager = BalanceManager(self.db_manager)
        return self._balance_manager
    
    @property
    def package_manager(self) -> PackageManager:
        if self._package_manager is None:
            self._package_manager = PackageManager(self.db_manager)
        return self._package_manager
    
    @property
    def subscription_manager(self) -> SubscriptionManager:
        if self._subscription_manager is None:
            self._subscription_manager = SubscriptionManager(self.db_manager)
        return self._subscription_manager
    
    @property
    def transaction_manager(self) -> TransactionManager:
        if self._transaction_manager is None:
            self._transaction_manager = TransactionManager(self.db_manager)
        return self._transaction_manager
