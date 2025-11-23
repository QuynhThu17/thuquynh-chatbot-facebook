"""
Limit Service Module
Quản lý tính toán và kiểm tra limits dựa trên gói hiện tại của user
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from configs.environment import get_vietnam_now_naive
from bson import ObjectId

logger = logging.getLogger(__name__)

class LimitService:
    """Service để tính toán và kiểm tra limits của user"""
    
    def __init__(self, factory):
        self.factory = factory
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = 60  # Cache TTL in seconds
    
    async def get_user_current_limits(self, user_id: str) -> Dict[str, Any]:
        """
        Lấy limits hiện tại của user dựa trên gói đang sử dụng
        
        Returns:
            Dict chứa thông tin limits và usage hiện tại
        """
        try:
            # Check cache first
            cache_key = f"limits_{user_id}"
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # Chạy song song việc lấy user info và tính usage để tối ưu thời gian
            user_task = self.factory.user_manager.get_by_id(user_id)
            usage_task = self._calculate_current_usage(user_id)
            
            user, current_usage = await asyncio.gather(user_task, usage_task, return_exceptions=True)
            
            # Handle exceptions
            if isinstance(user, Exception):
                logger.error(f"Error getting user {user_id}: {str(user)}")
                return {}
            if isinstance(current_usage, Exception):
                logger.error(f"Error calculating usage for {user_id}: {str(current_usage)}")
                current_usage = {}
            
            if not user:
                return {}
            
            # Lấy thông tin package hiện tại
            current_package_id = user.get("current_package", "p_free_trial")
            package = await self.factory.package_manager.get_by_id(current_package_id)
            
            if not package:
                # Fallback to free trial package
                package = await self.factory.package_manager.get_by_id("p_free_trial")
                if not package:
                    return {}
            
            package_limits = package.get("limits", {})
            
            # Tạo response với limits và usage hiện tại
            limits_info = {}
            for limit_key, limit_value in package_limits.items():
                current_used = current_usage.get(limit_key, 0)
                
                # Kiểm tra nếu limit là -1 (unlimited)
                is_unlimited = (isinstance(limit_value, int) and limit_value == -1)
                
                limits_info[limit_key] = {
                    "limit": limit_value,
                    "used": current_used,
                    "remaining": "unlimited" if is_unlimited else self._calculate_remaining(limit_value, current_used),
                    "usage_percentage": 0.0 if is_unlimited else self._calculate_usage_percentage(limit_value, current_used),
                    "is_unlimited": is_unlimited
                }
            
            result = {
                "package_id": current_package_id,
                "package_name": package.get("name", "Unknown"),
                "package_expires_at": user.get("package_expires_at"),
                "limits": limits_info
            }
            
            # Cache the result
            self._set_cache(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting user limits for {user_id}: {str(e)}")
            return {}
    
    async def _calculate_current_usage(self, user_id: str) -> Dict[str, int]:
        """Tính toán usage hiện tại của user cho tất cả các loại limits - Tối ưu với count queries và asyncio.gather"""
        usage = {}
        
        try:
            # Tạo start_of_month cho messages query
            start_of_month = get_vietnam_now_naive().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            # Sử dụng count_documents thay vì find_many để tối ưu hiệu suất
            results = await asyncio.gather(
                self._count_documents("social_accounts", {"user_id": user_id}),
                self._count_documents("bots", {"user_id": user_id}),
                self._count_documents("identities", {"user_id": user_id}),
                self._count_documents("procedures", {"user_id": user_id}),
                self._count_documents("documents", {"user_id": user_id}),
                self._count_documents("companies", {"user_id": user_id}),
                self._count_documents("products", {"user_id": user_id}),
                self._count_documents("warehouses", {"user_id": user_id}),
                self._count_documents("histories", {
                    "user_id": user_id,
                    "created_at": {"$gte": start_of_month}
                }),
                return_exceptions=True
            )
            
            # Collection names để mapping với results
            collection_names = ["social_accounts", "bots", "identities", "procedures", "documents", "companies", "products", "warehouses", "messages"]
            usage_keys = ["social", "bot", "identities", "procedures", "knowledge", "company", "product", "warehouse", "messages_per_month"]
            
            # Assign results to usage dict, handle exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error counting {collection_names[i]} for user {user_id}: {str(result)}")
                    usage[usage_keys[i]] = 0
                else:
                    usage[usage_keys[i]] = result
            
            # Storage usage (tính theo bytes, convert về string với đơn vị)
            # TODO: Implement storage calculation khi có file management
            usage["storage"] = "0MB"
            
        except Exception as e:
            logger.error(f"Error calculating usage for user {user_id}: {str(e)}")
        
        return usage
    
    async def _count_documents(self, collection: str, filter_query: Dict) -> int:
        """Helper method để count documents với error handling"""
        try:
            # Kiểm tra xem db_manager có method count_documents không
            if hasattr(self.factory.db_manager, 'count_documents'):
                return await self.factory.db_manager.count_documents(collection, filter_query)
            else:
                # Fallback to find_many if count_documents not available
                documents = await self.factory.db_manager.find_many(collection, filter_query)
                return len(documents) if documents else 0
        except Exception as e:
            logger.error(f"Error counting documents in {collection}: {str(e)}")
            return 0
    
    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Lấy data từ cache nếu còn valid"""
        if key in self._cache:
            cached_data, timestamp = self._cache[key]
            if get_vietnam_now_naive().timestamp() - timestamp < self._cache_ttl:
                logger.debug(f"Cache hit for key: {key}")
                return cached_data
            else:
                # Cache expired, remove it
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Dict[str, Any]):
        """Lưu data vào cache"""
        self._cache[key] = (data, get_vietnam_now_naive().timestamp())
        logger.debug(f"Cached data for key: {key}")
    
    def _calculate_remaining(self, limit_value: Union[int, str], current_used: Union[int, str]) -> Union[int, str]:
        """Tính toán remaining dựa trên loại limit"""
        # Nếu limit là -1 thì unlimited
        if isinstance(limit_value, int):
            if limit_value == -1:
                return "unlimited"
            if isinstance(current_used, int):
                return max(0, limit_value - current_used)
        elif isinstance(limit_value, str) and any(unit in limit_value for unit in ["GB", "MB", "TB"]):
            # Handle storage limits - extract number from string
            try:
                if "GB" in limit_value:
                    limit_gb = float(limit_value.replace("GB", "").strip())
                    # Assume current_used is in format like "100MB" or "1GB"
                    if isinstance(current_used, str):
                        if "MB" in current_used:
                            used_gb = float(current_used.replace("MB", "").strip()) / 1024
                        elif "GB" in current_used:
                            used_gb = float(current_used.replace("GB", "").strip())
                        elif "TB" in current_used:
                            used_gb = float(current_used.replace("TB", "").strip()) * 1024
                        else:
                            used_gb = 0
                    else:
                        used_gb = 0
                    remaining_gb = max(0, limit_gb - used_gb)
                    return f"{remaining_gb:.1f}GB"
                else:
                    return limit_value
            except:
                return limit_value
        else:
            return limit_value
    
    def _calculate_usage_percentage(self, limit_value: Union[int, str], current_used: Union[int, str]) -> float:
        """Tính toán phần trăm đã sử dụng"""
        if isinstance(limit_value, int) and isinstance(current_used, int):
            # Nếu limit là -1 (unlimited) thì usage_percentage là 0
            if limit_value == -1:
                return 0.0
            if limit_value == 0:
                return 0.0
            return min(100.0, (current_used / limit_value) * 100)
        elif isinstance(limit_value, str) and any(unit in limit_value for unit in ["GB", "MB", "TB"]):
            try:
                if "GB" in limit_value:
                    limit_gb = float(limit_value.replace("GB", "").strip())
                    if isinstance(current_used, str):
                        if "MB" in current_used:
                            used_gb = float(current_used.replace("MB", "").strip()) / 1024
                        elif "GB" in current_used:
                            used_gb = float(current_used.replace("GB", "").strip())
                        elif "TB" in current_used:
                            used_gb = float(current_used.replace("TB", "").strip()) * 1024
                        else:
                            used_gb = 0
                    else:
                        used_gb = 0
                    
                    if limit_gb == 0:
                        return 0.0
                    return min(100.0, (used_gb / limit_gb) * 100)
                else:
                    return 0.0
            except:
                return 0.0
        else:
            return 0.0
    
    async def check_limit_before_create(self, user_id: str, resource_type: str) -> Dict[str, Any]:
        """
        Kiểm tra xem user có thể tạo thêm resource không
        
        Args:
            user_id: ID của user
            resource_type: Loại resource muốn tạo (social, bot, knowledge, etc.)
        
        Returns:
            Dict với thông tin can_create và thông báo
        """
        try:
            # Sử dụng cached limits để tối ưu thời gian response
            limits_info = await self.get_user_current_limits(user_id)
            
            if not limits_info or "limits" not in limits_info:
                return {
                    "can_create": False,
                    "message": "Unable to verify limits. Please contact support.",
                    "error_code": "LIMITS_UNAVAILABLE"
                }
            
            resource_limit_info = limits_info["limits"].get(resource_type)
            
            if not resource_limit_info:
                # Nếu không có limit cho resource này, cho phép tạo
                return {
                    "can_create": True,
                    "message": "No limit restriction for this resource type."
                }
            
            limit = resource_limit_info["limit"]
            used = resource_limit_info["used"]
            remaining = resource_limit_info["remaining"]
            is_unlimited = resource_limit_info.get("is_unlimited", False)
            
            # Nếu limit là unlimited (-1), cho phép tạo
            if is_unlimited or (isinstance(limit, int) and limit == -1):
                return {
                    "can_create": True,
                    "message": f"You have unlimited {resource_type}.",
                    "remaining": "unlimited",
                    "current_usage": used,
                    "limit": -1,
                    "is_unlimited": True
                }
            
            if isinstance(limit, int) and isinstance(used, int):
                if used >= limit:
                    package_name = limits_info.get("package_name", "current package")
                    return {
                        "can_create": False,
                        "message": f"You have reached the limit for {resource_type} ({used}/{limit}) in your {package_name}. Please upgrade your package to create more.",
                        "error_code": "LIMIT_EXCEEDED",
                        "current_usage": used,
                        "limit": limit,
                        "package_name": package_name
                    }
                
                return {
                    "can_create": True,
                    "message": f"You can create {remaining} more {resource_type}(s).",
                    "remaining": remaining,
                    "current_usage": used,
                    "limit": limit
                }
            
            # For non-numeric limits, allow creation for now
            return {
                "can_create": True,
                "message": "Limit check passed."
            }
            
        except Exception as e:
            logger.error(f"Error checking limit for user {user_id}, resource {resource_type}: {str(e)}")
            return {
                "can_create": False,
                "message": "Unable to verify limits. Please try again.",
                "error_code": "LIMIT_CHECK_ERROR"
            }
    
    async def increment_usage(self, user_id: str, resource_type: str, amount: int = 1):
        """
        Tăng usage counter cho một resource type
        Chỉ cần thiết cho một số resource types như messages
        Phần lớn resources sẽ được tính trực tiếp từ database
        """
        try:
            if resource_type == "messages_per_month":
                # Lưu message record để tracking
                await self.factory.db_manager.create("message_usage", {
                    "user_id": user_id,
                    "count": amount,
                    "created_at": get_vietnam_now_naive()
                })
                logger.info(f"Incremented {resource_type} usage for user {user_id} by {amount}")
            
            # Clear cache để đảm bảo data mới nhất
            self._clear_user_cache(user_id)
                
        except Exception as e:
            logger.error(f"Error incrementing usage for user {user_id}, resource {resource_type}: {str(e)}")
    
    def _clear_user_cache(self, user_id: str):
        """Clear cache cho một user cụ thể"""
        cache_key = f"limits_{user_id}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.debug(f"Cleared cache for user: {user_id}")
    
    def clear_all_cache(self):
        """Clear toàn bộ cache - có thể gọi định kỳ hoặc khi cần"""
        self._cache.clear()
        logger.info("Cleared all limit service cache")

# Singleton instance
_limit_service = None

def get_limit_service(factory):
    """Get or create limit service instance"""
    global _limit_service
    if _limit_service is None:
        _limit_service = LimitService(factory)
    return _limit_service