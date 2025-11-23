"""
SuperAdmin Management Module
==========================
Quản lý các chức năng đặc biệt cho SuperAdmin của MekongAI:
- Hierarchy đa cấp
- Partner management
- White label licensing
- System monitoring
- Data aggregation
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from bson import ObjectId
from .base_manager import BaseManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

class SuperHierarchyManager(BaseManager):
    """
    Manager mở rộng cho SuperAdmin hierarchy management
    Quản lý cây hierarchy đa cấp: SuperAdmin -> WhiteLabel -> Partners -> Users
    """
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "hierarchy")
    
    async def create_hierarchy(self, user_id: str, parent: str = None, 
                              children: List[str] = None, **kwargs) -> Dict[str, Any]:
        """Tạo hierarchy mới với thông tin mở rộng"""
        hierarchy_data = {
            "user_id": user_id,
            "parent": parent,
            "children": children or [],
            # Thêm các trường mở rộng
            "hierarchy_type": kwargs.get("hierarchy_type", "user"),
            "license_type": kwargs.get("license_type", "trial"),
            "partner_info": kwargs.get("partner_info", {}),
            "system_config": kwargs.get("system_config", {}),
            "revenue_tracking": {
                "total_revenue": 0.0,
                "this_month": 0.0,
                "last_month": 0.0,
                "currency": "VND"
            },
            "usage_stats": {
                "total_users": 0,
                "active_bots": 0,
                "total_messages": 0,
                "storage_used_mb": 0.0
            }
        }
        return await self.create(hierarchy_data)
    
    async def get_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy hierarchy theo user_id"""
        hierarchies = await self.get_all(filter_query={"user_id": user_id}, limit=1)
        return hierarchies[0] if hierarchies else None
    
    async def get_children_recursive(self, user_id: str, max_depth: int = 10) -> List[Dict[str, Any]]:
        """Lấy tất cả children theo đệ quy"""
        async def _get_recursive(uid: str, current_depth: int) -> List[Dict[str, Any]]:
            if current_depth >= max_depth:
                return []
            
            hierarchy = await self.get_by_user_id(uid)
            if not hierarchy:
                return []
            
            result = []
            children_ids = hierarchy.get("children", [])
            
            for child_id in children_ids:
                child_hierarchy = await self.get_by_user_id(child_id)
                if child_hierarchy:
                    result.append(child_hierarchy)
                    # Đệ quy lấy children của child
                    sub_children = await _get_recursive(child_id, current_depth + 1)
                    result.extend(sub_children)
            
            return result
        
        return await _get_recursive(user_id, 0)
    
    async def get_path_to_root(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy đường dẫn từ user lên root (SuperAdmin)"""
        path = []
        current_id = user_id
        
        while current_id:
            hierarchy = await self.get_by_user_id(current_id)
            if not hierarchy:
                break
            
            path.append(hierarchy)
            current_id = hierarchy.get("parent")
            
            # Tránh vòng lặp vô tận
            if len(path) > 50:
                break
        
        return path
    
    async def update_partner_info(self, user_id: str, partner_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật thông tin partner"""
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_info = hierarchy.get("partner_info", {})
            current_info.update(partner_info)
            return await self.update_by_id(hierarchy["_id"], {"partner_info": current_info})
        return None
    
    async def update_revenue_stats(self, user_id: str, revenue_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật thống kê doanh thu"""
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_revenue = hierarchy.get("revenue_tracking", {})
            current_revenue.update(revenue_data)
            return await self.update_by_id(hierarchy["_id"], {"revenue_tracking": current_revenue})
        return None
    
    async def update_usage_stats(self, user_id: str, usage_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật thống kê sử dụng"""
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_usage = hierarchy.get("usage_stats", {})
            current_usage.update(usage_data)
            return await self.update_by_id(hierarchy["_id"], {"usage_stats": current_usage})
        return None
    
    async def add_child(self, user_id: str, child_id: str) -> Optional[Dict[str, Any]]:
        """Thêm child và cập nhật parent của child"""
        # Cập nhật parent
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_children = hierarchy.get("children", [])
            if child_id not in current_children:
                current_children.append(child_id)
                await self.update_by_id(hierarchy["_id"], {"children": current_children})
        
        # Cập nhật child's parent
        child_hierarchy = await self.get_by_user_id(child_id)
        if child_hierarchy:
            await self.update_by_id(child_hierarchy["_id"], {"parent": user_id})
        
        return hierarchy
    
    async def remove_child(self, user_id: str, child_id: str) -> Optional[Dict[str, Any]]:
        """Xóa child và cập nhật parent của child"""
        # Cập nhật parent
        hierarchy = await self.get_by_user_id(user_id)
        if hierarchy:
            current_children = hierarchy.get("children", [])
            if child_id in current_children:
                current_children.remove(child_id)
                await self.update_by_id(hierarchy["_id"], {"children": current_children})
        
        # Xóa parent của child
        child_hierarchy = await self.get_by_user_id(child_id)
        if child_hierarchy:
            await self.update_by_id(child_hierarchy["_id"], {"parent": None})
        
        return hierarchy
    
    async def get_hierarchy_stats(self, user_id: str) -> Dict[str, Any]:
        """Tính toán thống kê hierarchy cho user"""
        hierarchy = await self.get_by_user_id(user_id)
        if not hierarchy:
            return {}
        
        # Đếm số lượng children đệ quy
        all_children = await self.get_children_recursive(user_id)
        
        # Tính tổng stats từ tất cả children
        total_users = 0
        total_revenue = 0.0
        total_bots = 0
        total_messages = 0
        
        for child in all_children:
            usage = child.get("usage_stats", {})
            revenue = child.get("revenue_tracking", {})
            
            total_users += usage.get("total_users", 0)
            total_bots += usage.get("active_bots", 0)
            total_messages += usage.get("total_messages", 0)
            total_revenue += revenue.get("total_revenue", 0.0)
        
        return {
            "direct_children": len(hierarchy.get("children", [])),
            "total_descendants": len(all_children),
            "hierarchy_depth": len(await self.get_path_to_root(user_id)),
            "aggregate_stats": {
                "total_users": total_users,
                "total_revenue": total_revenue,
                "total_bots": total_bots,
                "total_messages": total_messages
            }
        }

class PartnerLicenseManager(BaseManager):
    """Quản lý licenses cho các đối tác"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "partner_licenses")
    
    async def create_license(self, partner_id: str, license_type: str, 
                           config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Tạo license mới cho đối tác"""
        license_data = {
            "partner_id": partner_id,
            "license_type": license_type,  # white_label, reseller, trial
            "status": "active",
            "config": config or {},
            "created_at": datetime.now(),
            "expires_at": None,  # None = không hết hạn
            "usage_limits": {
                "max_users": config.get("max_users", -1) if config else -1,
                "max_monthly_revenue": config.get("max_monthly_revenue", -1) if config else -1,
                "allowed_features": config.get("allowed_features", []) if config else [],
                "restricted_features": config.get("restricted_features", []) if config else []
            },
            "billing": {
                "revenue_share_percentage": config.get("revenue_share_percentage", 0.0) if config else 0.0,
                "monthly_fee": config.get("monthly_fee", 0.0) if config else 0.0,
                "setup_fee": config.get("setup_fee", 0.0) if config else 0.0
            }
        }
        return await self.create(license_data)
    
    async def get_by_partner_id(self, partner_id: str) -> Optional[Dict[str, Any]]:
        """Lấy license theo partner ID"""
        licenses = await self.get_all(filter_query={"partner_id": partner_id}, limit=1)
        return licenses[0] if licenses else None
    
    async def update_usage_limits(self, partner_id: str, limits: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật giới hạn sử dụng"""
        license = await self.get_by_partner_id(partner_id)
        if license:
            current_limits = license.get("usage_limits", {})
            current_limits.update(limits)
            return await self.update_by_id(license["_id"], {"usage_limits": current_limits})
        return None
    
    async def check_license_valid(self, partner_id: str) -> bool:
        """Kiểm tra license có hợp lệ không"""
        license = await self.get_by_partner_id(partner_id)
        if not license:
            return False
        
        # Kiểm tra status
        if license.get("status") != "active":
            return False
        
        # Kiểm tra expiry
        expires_at = license.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            return False
        
        return True

class SystemMonitoringManager(BaseManager):
    """Monitoring hệ thống cho SuperAdmin"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "system_monitoring")
    
    async def log_system_event(self, event_type: str, data: Dict[str, Any], 
                              source: str = "system") -> Dict[str, Any]:
        """Log system event"""
        event_data = {
            "event_type": event_type,
            "source": source,
            "data": data,
            "timestamp": datetime.now(),
            "severity": data.get("severity", "info")
        }
        return await self.create(event_data)
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Lấy tình trạng sức khỏe hệ thống"""
        # TODO: Implement real system health check
        return {
            "status": "healthy",
            "uptime_percentage": 99.9,
            "avg_response_time": 250.5,
            "total_requests_today": 45000,
            "error_rate": 0.1,
            "last_check": datetime.now()
        }
    
    async def get_usage_trends(self, days: int = 30) -> Dict[str, Any]:
        """Lấy xu hướng sử dụng"""
        # TODO: Implement usage trend analysis
        return {
            "period_days": days,
            "total_new_users": 150,
            "total_new_bots": 45,
            "message_growth_rate": 15.5,
            "revenue_growth_rate": 25.2
        }

class DataAggregationManager(BaseManager):
    """Tập hợp và đồng bộ dữ liệu từ các đối tác"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "data_aggregation")
    
    async def aggregate_partner_data(self, partner_id: str) -> Dict[str, Any]:
        """Tập hợp dữ liệu từ đối tác"""
        # TODO: Implement data aggregation logic
        return {
            "partner_id": partner_id,
            "last_sync": datetime.now(),
            "data_sources": ["users", "bots", "messages", "revenue"],
            "sync_status": "completed"
        }
    
    async def sync_all_partners(self) -> Dict[str, Any]:
        """Đồng bộ dữ liệu từ tất cả đối tác"""
        # TODO: Implement bulk sync
        return {
            "total_partners": 25,
            "successful_syncs": 24,
            "failed_syncs": 1,
            "sync_time": datetime.now()
        }

class SuperAdminManagementFactory:
    """Factory cho tất cả SuperAdmin managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._super_hierarchy_manager = None
        self._partner_license_manager = None
        self._system_monitoring_manager = None
        self._data_aggregation_manager = None
    
    @property
    def super_hierarchy_manager(self) -> SuperHierarchyManager:
        if self._super_hierarchy_manager is None:
            self._super_hierarchy_manager = SuperHierarchyManager(self.db_manager)
        return self._super_hierarchy_manager
    
    @property
    def partner_license_manager(self) -> PartnerLicenseManager:
        if self._partner_license_manager is None:
            self._partner_license_manager = PartnerLicenseManager(self.db_manager)
        return self._partner_license_manager
    
    @property
    def system_monitoring_manager(self) -> SystemMonitoringManager:
        if self._system_monitoring_manager is None:
            self._system_monitoring_manager = SystemMonitoringManager(self.db_manager)
        return self._system_monitoring_manager
    
    @property
    def data_aggregation_manager(self) -> DataAggregationManager:
        if self._data_aggregation_manager is None:
            self._data_aggregation_manager = DataAggregationManager(self.db_manager)
        return self._data_aggregation_manager
