"""
Facebook Messenger Agent Tools
Chứa tất cả các tools được sử dụng bởi bot Facebook Messenger
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from typing import Dict, List, Optional, Any, Tuple
from bson import ObjectId
import pymongo
import urllib3

from langchain_core.tools import BaseTool, tool

# ✅ Disable SSL warnings khi download ảnh từ Facebook CDN
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from configs import constant
from controllers.socials.facebook.facebook_send_messenger import send_typing_action


logger = logging.getLogger(__name__)

_typing_indicator_executor = ThreadPoolExecutor(max_workers=1)


def _schedule_typing_indicator(page_id: str, page_access_token: str, sender_id: str) -> None:
    """Trigger typing indicator without assuming an active asyncio loop."""

    async def _run_async():
        await send_typing_indicators_async_public(page_id, page_access_token, sender_id)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        def _run_in_thread():
            try:
                asyncio.run(_run_async())
            except Exception as exc:
                logger.debug(f"Typing indicator fallback failed: {exc}")

        _typing_indicator_executor.submit(_run_in_thread)
    else:
        loop.create_task(_run_async())


class SyncMongoHelper:
    """Sync MongoDB helper for tools to avoid async issues"""
    
    def __init__(self):
        self.client = None
        self.database = None
        self._connection_string = constant.MONGODB_URI
        # Cache để tối ưu tốc độ - Tăng TTL và thêm cache cho nhiều loại dữ liệu hơn
        self._customer_cache = {}  # {cache_key: (customer_data, timestamp)}
        self._product_cache = {}  # {cache_key: (products, timestamp)}
        self._order_cache = {}  # {cache_key: (orders, timestamp)}
        self._cache_ttl = 300  # Cache TTL 5 phút (tăng từ 60s)
    
    def connect(self, database_name: str = "mekongai_social"):
        """Connect to MongoDB synchronously"""
        try:
            if self.client is None:
                self.client = pymongo.MongoClient(
                    self._connection_string,
                    serverSelectionTimeoutMS=3000,  # Giảm từ 5000ms
                    connectTimeoutMS=5000,  # Giảm từ 10000ms
                    socketTimeoutMS=15000,  # Tăng từ 10000ms
                    maxPoolSize=100,  # Tăng từ 50
                    minPoolSize=10,  # Tăng từ 5
                    maxIdleTimeMS=45000,
                    waitQueueTimeoutMS=5000,
                    retryWrites=True,
                    retryReads=True
                )
                # Test connection
                self.client.admin.command('ping')
                self.database = self.client[database_name]
                logger.info(f"✅ Sync MongoDB connected to: {database_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Sync MongoDB connection error: {e}")
            return False

    def close(self):
        try:
            if self.client:
                self.client.close()
            self.client = None
            self.database = None
        except Exception:
            self.client = None
            self.database = None
    
    def find_customer(self, social_page_id: str, customer_id: str):
        """Find customer synchronously với cache"""
        try:
            # Kiểm tra cache
            cache_key = f"{social_page_id}_{customer_id}"
            current_time = datetime.now().timestamp()
            
            if cache_key in self._customer_cache:
                customer_data, timestamp = self._customer_cache[cache_key]
                if current_time - timestamp < self._cache_ttl:
                    logger.debug(f"✅ Customer cache hit: {cache_key}")
                    return customer_data
            
            if self.database is None:
                self.connect()
            
            collection = self.database["customers"]
            # Projection: chỉ lấy fields cần thiết để giảm data transfer
            projection = {
                "_id": 1, "name": 1, "phone": 1, "address": 1,
                "email": 1, "gender": 1, "additional_info": 1
            }
            
            # Query với hint index (nếu có)
            query = {
                "social_id": "s_facebook",
                "social_page_id": social_page_id,
                "customer_id": customer_id
            }
            
            # Try hint index nếu có
            try:
                # Giả định có compound index trên (social_page_id, customer_id)
                customer = collection.find_one(query, projection).hint([("social_page_id", 1), ("customer_id", 1)])
            except:
                # Fallback nếu không có index
                customer = collection.find_one(query, projection)
            
            # Cache kết quả
            if customer:
                self._customer_cache[cache_key] = (customer, current_time)
            
            return customer
        except Exception as e:
            logger.error(f"Error finding customer: {e}")
            return None
        finally:
            self.close()
    
    def _invalidate_customer_cache(self, social_page_id: str, customer_id: str):
        """Invalidate customer cache"""
        cache_key = f"{social_page_id}_{customer_id}"
        self._customer_cache.pop(cache_key, None)
    
    def _invalidate_order_cache(self, social_page_id: str, customer_id: str):
        """Invalidate tất cả order cache của customer"""
        keys_to_remove = [k for k in self._order_cache.keys() if k.startswith(f"{social_page_id}_{customer_id}_orders")]
        for key in keys_to_remove:
            self._order_cache.pop(key, None)
    
    def invalidate_product_cache(self):
        """Invalidate toàn bộ product cache (gọi khi có thay đổi product)"""
        self._product_cache.clear()
        logger.info("🧹 Product cache invalidated")
    
    def clear_expired_cache(self):
        """Clear expired cache entries để tránh memory leak"""
        current_time = datetime.now().timestamp()
        
        # Clear customer cache
        expired_customer_keys = [
            k for k, (_, ts) in self._customer_cache.items()
            if current_time - ts >= self._cache_ttl
        ]
        for key in expired_customer_keys:
            self._customer_cache.pop(key, None)
        
        # Clear product cache
        expired_product_keys = [
            k for k, (_, ts) in self._product_cache.items()
            if current_time - ts >= self._cache_ttl
        ]
        for key in expired_product_keys:
            self._product_cache.pop(key, None)
        
        # Clear order cache
        expired_order_keys = [
            k for k, (_, ts) in self._order_cache.items()
            if current_time - ts >= self._cache_ttl
        ]
        for key in expired_order_keys:
            self._order_cache.pop(key, None)
        
        if expired_customer_keys or expired_product_keys or expired_order_keys:
            logger.debug(f"🧹 Cleared {len(expired_customer_keys) + len(expired_product_keys) + len(expired_order_keys)} expired cache entries")
                
    def save_customer(self, customer_data: dict):
        """Save/update customer synchronously với merge thông tin cũ"""
        try:
            if self.database is None:
                self.connect()
            
            collection = self.database["customers"]
            
            # Try to find existing customer
            existing = collection.find_one({
                "social_id": customer_data.get("social_id"),
                "social_page_id": customer_data.get("social_page_id"),
                "customer_id": customer_data.get("customer_id")
            })
            
            if existing:
                # Merge thông tin cũ với mới (chỉ cập nhật field có giá trị)
                merged_data = existing.copy()
                for key, value in customer_data.items():
                    if value is not None and str(value).strip():
                        merged_data[key] = value
                merged_data["updated_at"] = get_vietnam_now_naive()
                
                collection.update_one(
                    {"_id": existing["_id"]},
                    {"$set": merged_data}
                )
                # Invalidate cache
                self._invalidate_customer_cache(customer_data.get('social_page_id'), customer_data.get('customer_id'))
                return f"✅ Đã cập nhật thông tin khách hàng. Thông tin khách hàng: {str(merged_data)}\n\n"
            else:
                # Create new
                customer_data["created_at"] = get_vietnam_now_naive()
                customer_data["updated_at"] = get_vietnam_now_naive()
                collection.insert_one(customer_data)
                # Invalidate cache
                self._invalidate_customer_cache(customer_data.get('social_page_id'), customer_data.get('customer_id'))
                return f"✅ Đã lưu thông tin khách hàng mới. Thông tin khách hàng: {str(customer_data)}\n\n"
        except Exception as e:
            logger.error(f"Error saving customer: {e}")
            return f"❌ Lỗi khi lưu thông tin khách hàng: {e}\n\n"
        finally:
            self.close()
    
    def save_order(self, order_data: dict):
        """Save order synchronously"""
        try:
            if self.database is None:
                self.connect()
            
            collection = self.database["orders"]
            order_data["created_at"] = get_vietnam_now_naive()
            order_data["updated_at"] = get_vietnam_now_naive()
            order_data["status"] = "new"  # Đơn hàng mới
            
            result = collection.insert_one(order_data)
            # Invalidate order cache
            self._invalidate_order_cache(order_data.get("social_page_id"), order_data.get("customer_id"))
            return f"✅ Đã lưu đơn hàng thành công! Thông tin đơn hàng: {str(order_data)}\n\n"
        except Exception as e:
            logger.error(f"Error saving order: {e}")
            return f"❌ Lỗi khi lưu đơn hàng: {e}\n\n"
        finally:
            self.close()
    
    def update_order(self, order_id: str, update_data: dict):
        """Update existing order synchronously"""
        try:
            if self.database is None:
                self.connect()
            
            collection = self.database["orders"]
            
            # Validate order_id
            try:
                object_id = ObjectId(order_id)
            except:
                return "❌ Mã đơn hàng không hợp lệ\n\n"
            
            # Find existing order
            existing_order = collection.find_one({"_id": object_id})
            if not existing_order:
                return "❌ Không tìm thấy đơn hàng\n\n"
            
            # Update order
            update_data["updated_at"] = get_vietnam_now_naive()
            result = collection.update_one(
                {"_id": object_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                # Invalidate order cache (lấy thông tin từ existing_order)
                self._invalidate_order_cache(
                    existing_order.get("social_page_id"),
                    existing_order.get("customer_id")
                )
                return f"✅ Đã cập nhật đơn hàng {order_id[:8]} thành công. Thông tin đơn hàng: {str(update_data)}\n\n"
            else:
                return "❌ Không có thay đổi nào được thực hiện\n\n"
                
        except Exception as e:
            logger.error(f"Error updating order: {e}")
            return f"❌ Lỗi khi cập nhật đơn hàng: {e}\n\n"
    
    def find_orders(self, social_page_id: str, customer_id: str, limit: int = 5):
        """Find customer orders synchronously với cache"""
        try:
            # Kiểm tra cache
            cache_key = f"{social_page_id}_{customer_id}_orders_{limit}"
            current_time = datetime.now().timestamp()
            
            if cache_key in self._order_cache:
                orders, timestamp = self._order_cache[cache_key]
                if current_time - timestamp < self._cache_ttl:
                    logger.debug(f"✅ Order cache hit: {cache_key}")
                    return orders
            
            if self.database is None:
                self.connect()
            
            collection = self.database["orders"]
            # Projection: chỉ lấy fields hiển thị
            projection = {
                "_id": 1, "product_name": 1, "quantity": 1,
                "total_price": 1, "status": 1, "created_at": 1
            }
            
            # Query với hint index (nếu có)
            cursor = collection.find(
                {
                    "social_id": "s_facebook",
                    "social_page_id": social_page_id,
                    "customer_id": customer_id
                },
                projection
            ).sort("created_at", -1).limit(limit)
            
            # Try hint index
            try:
                cursor = cursor.hint([("social_page_id", 1), ("customer_id", 1)])
            except:
                pass  # Ignore nếu không có index
            
            orders = list(cursor)
            
            # Cache kết quả
            self._order_cache[cache_key] = (orders, current_time)
            
            return orders
        except Exception as e:
            logger.error(f"Error finding orders: {e}")
            return []


class FacebookMessengerTools:
    """Class chứa tất cả tools cho Facebook Messenger Bot"""
    
    def __init__(self, bot_agent):
        """
        Args:
            bot_agent: Instance của BotMessengerAgentV2
        """
        self.bot_agent = bot_agent
        self.sync_mongo = SyncMongoHelper()
        
        # Auto clear expired cache định kỳ (gọi ngay khi khởi tạo)
        self.sync_mongo.clear_expired_cache()
        
        # Schedule periodic cache cleanup (mỗi 5 phút)
        self._schedule_periodic_cache_cleanup()
    
    def _schedule_periodic_cache_cleanup(self):
        """Schedule định kỳ clear expired cache mỗi 5 phút"""
        import threading
        
        def cleanup_task():
            while True:
                import time
                time.sleep(300)  # 5 phút
                try:
                    self.sync_mongo.clear_expired_cache()
                    logger.info("🧹 Periodic cache cleanup completed")
                except Exception as e:
                    logger.error(f"❌ Error in periodic cache cleanup: {e}")
        
        # Chạy trong background thread
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        logger.info("✅ Periodic cache cleanup scheduled (every 5 minutes)")
    
    def create_customer_info_tool(self):
        @tool("get_customer_info")
        def get_customer_info_tool(sender_id: str, page_id: str) -> str:
            """
            🔍 Lấy thông tin khách hàng
            
            Args:
                sender_id: Facebook sender ID
                page_id: Facebook page ID
                
            Returns:
                str: Thông tin khách hàng hoặc thông báo không tìm thấy
            """
            try:
                customer = self.sync_mongo.find_customer(page_id, sender_id)
                
                if customer:
                    customer_info = []
                    if customer.get("name"):
                        customer_info.append(f"👤 Tên: {customer['name']}")
                    if customer.get("phone"):
                        customer_info.append(f"📞 SĐT: {customer['phone']}")
                    if customer.get("address"):
                        customer_info.append(f"🏠 Địa chỉ: {customer['address']}")
                    if customer.get("email"):
                        customer_info.append(f"📧 Email: {customer['email']}")
                    if customer.get("gender"):
                        customer_info.append(f"👥 Giới tính: {customer['gender']}")
                    if customer.get("additional_info"):
                        customer_info.append(f"ℹ️ Thông tin thêm: {customer['additional_info']}")
                    
                    result = "--- 📋 CUSTOMER INFO: ---\n" + "\n".join(customer_info)
                    result += "\n--- END CUSTOMER INFO ---\n\n"
                    return result
                else:
                    return "❌ Chưa có thông tin khách hàng được lưu trữ.\n\n"

            except Exception as e:
                return f"❌ Lỗi khi lấy thông tin khách hàng: {e}\n\n"
        
        return get_customer_info_tool

    def create_save_customer_tool(self):
        @tool("save_customer_info")
        def save_customer_info_tool(sender_id: str, page_id: str, name: str = None, 
                                   phone: str = None, address: str = None, email: str = None,
                                   gender: str = None, additional_info: str = None) -> str:
            """
            💾 Lưu / Cập nhật thông tin khách hàng khi có bất kỳ thông tin nào mới và có giá trị được cung cấp từ khách hàng)
            
            Sử dụng tool này khi khách hàng:
                ✅ Cung cấp bất kỳ thông tin cá nhân mới (tên, SĐT, địa chỉ)
                ✅ Chia sẻ sở thích, nhu cầu cá nhân
                ✅ Thể hiện quan tâm đến sản phẩm/dịch vụ cụ thể
                ✅ Đưa ra thông tin bổ sung về bản thân
            
            Tool này cần được gọi khi có bất kỳ thông tin mới nào được phát hiện để xây dựng cơ sở dữ liệu khách hàng tiềm năng.
    
            Args:
                sender_id: Facebook sender ID
                page_id: Facebook page ID
                name: Tên khách hàng
                phone: Số điện thoại
                address: Địa chỉ
                email: Email
                gender: Giới tính
                additional_info: Thông tin bổ sung, string dài, có thể bao gồm nhiều thông tin khác nhau như sở thích, nhu cầu, v.v.
                
            Returns:
                str: Kết quả lưu thông tin
            """
            try:
                customer_data = {
                    "social_id": "s_facebook",
                    "social_page_id": page_id,
                    "customer_id": sender_id,
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "email": email,
                    "gender": gender,
                    "additional_info": additional_info
                }
                
                # Remove None values
                customer_data = {k: v for k, v in customer_data.items() if v is not None}
                
                return self.sync_mongo.save_customer(customer_data)
                    
            except Exception as e:
                return f"❌ Lỗi khi lưu thông tin khách hàng: {e}\n\n"
        
        return save_customer_info_tool

    def create_save_order_tool(self):
        @tool("save_order")
        def save_order_tool(sender_id: str, page_id: str, product_name: str, unit_price: float,
                           quantity: int, total_price: float, customer_note: str = "",
                           customer_name: str = None, customer_phone: str = None, 
                           customer_address: str = None, payment_method: str = None, payment_status: str = None) -> str:
            """
            📦 Lưu đơn hàng mới
            
            Args:
                sender_id: Facebook sender ID
                page_id: Facebook page ID
                product_name: Tên sản phẩm
                unit_price: Đơn giá
                quantity: Số lượng
                total_price: Tổng tiền
                customer_note: Ghi chú khách hàng
                customer_name: Tên khách hàng (nếu có)
                customer_phone: SĐT khách hàng (nếu có)
                customer_address: Địa chỉ khách hàng (nếu có)
                payment_method: Phương thức thanh toán
                payment_status: Trạng thái thanh toán
                
            Returns:
                str: Kết quả lưu đơn hàng
            """
            try:
                order_data = {
                    "social_id": "s_facebook",
                    "social_page_id": page_id,
                    "customer_id": sender_id,
                    "product_name": product_name,
                    "unit_price": unit_price,
                    "quantity": quantity,
                    "total_price": total_price,
                    "customer_note": customer_note or "",
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "customer_address": customer_address,
                    "payment_method": payment_method,
                    "payment_status": payment_status or "pending"
                }
                
                return self.sync_mongo.save_order(order_data)
                
            except Exception as e:
                return f"❌ Lỗi khi lưu đơn hàng: {e}\n\n"
        
        return save_order_tool

    def create_update_order_tool(self):
        @tool("update_order")
        def update_order_tool(order_id: str, product_name: str = None, unit_price: float = None,
                            quantity: int = None, total_price: float = None, customer_note: str = None,
                            customer_name: str = None, customer_phone: str = None, 
                            customer_address: str = None, payment_method: str = None, 
                            payment_status: str = None, status: str = None) -> str:
            """
            🔄 Cập nhật đơn hàng hiện có
            
            Args:
                order_id: ID của đơn hàng cần cập nhật
                product_name: Tên sản phẩm mới (nếu có)
                unit_price: Đơn giá mới (nếu có)
                quantity: Số lượng mới (nếu có)
                total_price: Tổng tiền mới (nếu có)
                customer_note: Ghi chú mới (nếu có)
                customer_name: Tên khách hàng mới (nếu có)
                customer_phone: SĐT mới (nếu có)
                customer_address: Địa chỉ mới (nếu có)
                payment_method: Phương thức thanh toán mới (nếu có)
                payment_status: Trạng thái thanh toán mới (nếu có)
                status: Trạng thái đơn hàng mới (nếu có)
                
            Returns:
                str: Kết quả cập nhật đơn hàng
            """
            try:
                update_data = {}
                
                # Chỉ add các field có giá trị
                if product_name is not None:
                    update_data["product_name"] = product_name
                if unit_price is not None:
                    update_data["unit_price"] = unit_price
                if quantity is not None:
                    update_data["quantity"] = quantity
                if total_price is not None:
                    update_data["total_price"] = total_price
                if customer_note is not None:
                    update_data["customer_note"] = customer_note
                if customer_name is not None:
                    update_data["customer_name"] = customer_name
                if customer_phone is not None:
                    update_data["customer_phone"] = customer_phone
                if customer_address is not None:
                    update_data["customer_address"] = customer_address
                if payment_method is not None:
                    update_data["payment_method"] = payment_method
                if payment_status is not None:
                    update_data["payment_status"] = payment_status
                if status is not None:
                    update_data["status"] = status
                
                if not update_data:
                    return "❌ Không có thông tin nào để cập nhật\n\n"
                
                return self.sync_mongo.update_order(order_id, update_data)
                
            except Exception as e:
                return f"❌ Lỗi khi cập nhật đơn hàng: {e}\n\n"
        
        return update_order_tool

    def create_get_order_info_tool(self):
        @tool("get_order_info")
        def get_order_info_tool(sender_id: str, page_id: str, limit: int = 5) -> str:
            """
            📋 Lấy thông tin đơn hàng của khách hàng
            
            Args:
                sender_id: Facebook sender ID
                page_id: Facebook page ID
                limit: Số lượng đơn hàng tối đa (mặc định 5)
                
            Returns:
                str: Danh sách đơn hàng hoặc thông báo không tìm thấy
            """
            try:
                orders = self.sync_mongo.find_orders(page_id, sender_id, limit)
                
                if not orders:
                    return "❌ Không tìm thấy đơn hàng nào.\n\n"
                
                result = f"--- ORDER SEARCH ---\n📋 Tìm thấy danh sách {len(orders)} đơn hàng gần nhất của khách hàng:\n\n"
                
                for i, order in enumerate(orders, 1):
                    order_id = str(order.get("_id", ""))
                    product_name = order.get("product_name", "N/A")
                    quantity = order.get("quantity", 0)
                    total_price = order.get("total_price", 0)
                    status = order.get("status", "N/A")
                    created_at = order.get("created_at", "")
                    
                    if created_at:
                        created_str = created_at.strftime("%d/%m/%Y %H:%M") if hasattr(created_at, 'strftime') else str(created_at)
                    else:
                        created_str = "N/A"
                    
                    result += f"{i}. 🏷️ Mã (order_id): {order_id}\n"
                    result += f"   📦 Sản phẩm: {product_name}\n"
                    result += f"   🔢 Số lượng: {quantity}\n"
                    result += f"   💰 Tổng tiền: {total_price:,.0f} VNĐ\n"
                    result += f"   📊 Trạng thái: {status}\n"
                    result += f"   📅 Ngày tạo: {created_str}\n\n"
                
                result += "--- END ORDER SEARCH ---\n\n"
                
                return result
                
            except Exception as e:
                return f"❌ Lỗi khi lấy thông tin đơn hàng: {e}\n\n"
        
        return get_order_info_tool

    def create_search_products_tool(self):
        @tool("search_products")
        def search_products_tool(
            search_query: str = None,
            search_query_keyword: str = None,
            sku: str = None,
            category: str = None,
            min_price: float = None,
            max_price: float = None,
            check_inventory: bool = False,
            include_description: bool = False,
            limit: int = 3
        ) -> str:
            """
            🔍 Tìm kiếm sản phẩm/dịch vụ trong hệ thống (bất kỳ khi nào cần thiết / khách hàng yêu cầu thông tin chi tiết / xem ảnh / gửi thông tin / gửi ảnh)
            
            ⚠️ QUAN TRỌNG - CẤU TRÚC THAM SỐ:
            - Nếu có MÃ SẢN PHẨM/SKU (số hoặc mã code) → PHẢI TRUYỀN VÀO `sku`
            - Tên sản phẩm / dịch vụ (chữ) → truyền vào `search_query_keyword`, Viết lại query thông minh vào `search_query`
            - VÍ DỤ: "túi Maggie M38301 này chất liệu làm từ gì vậy em" 
              ✅ ĐÚNG: search_query="chất liệu túi Maggie M38301", search_query_keyword="Maggie", sku="M38301"
              ❌ SAI: search_query="Maggie M38301" (không tách SKU riêng)
            
            Tool này hỗ trợ TẤT CẢ các dạng truy vấn về sản phẩm:
            ✅ Tìm theo tên (fuzzy search, không cần chính xác): "iphone", "điện thoại", "dien thoai"
            ✅ Tìm theo mã SKU (chính xác hoặc gần đúng): "IP15PM-256-BLK", "IP15PM", "38301"
            ✅ Tìm theo khoảng giá: "dưới 500k", "từ 1tr đến 5tr", "giá dưới 10 triệu"
            ✅ Tìm theo danh mục: "smartphone", "laptop", "điện thoại", "túi", "giày"
            ✅ Đếm số lượng: "bao nhiêu sản phẩm", "có mấy loại"
            ✅ Kiểm tra tồn kho: "còn hàng không", "còn bao nhiêu trong kho"
            
            Args:
                search_query: Từ khóa tìm kiếm chung - CHỈ TÊN SẢN PHẨM (không bao gồm mã/số). 
                             Hỗ trợ tìm kiếm mờ (fuzzy), không phân biệt hoa thường, bỏ qua dấu.
                             Ví dụ: "túi đi chơi", "giày thể thao", "iphone 15 pro max", "Maggie"
                             ⚠️ KHÔNG truyền mã SKU vào đây, hãy dùng tham số `sku` riêng.
                
                search_query_keyword: Từ khóa quan trọng nhất (chỉ 1 từ hoặc cụm từ ngắn gọn) - CHỈ TÊN.
                                     Dùng làm fallback khi search_query không tìm thấy kết quả.
                                     Ví dụ: "có túi đi chơi không shop" => search_query_keyword="túi"
                                           "shop có bán giày thể thao không" => search_query_keyword="giày"
                                           "tìm túi Maggie cho em" => search_query_keyword="Maggie"
                                     ⚠️ KHÔNG truyền mã SKU vào đây.
                             
                sku: Mã SKU sản phẩm (mã code, số định danh) - PHẢI TÁCH RIÊNG.
                     Ví dụ: "IP15PM-256-BLK-2", "IP15PM", "38301", "KAT-001"
                     ⚠️ Nếu user hỏi về "túi Maggie 38301" thì sku="38301"
                     
                category: Danh mục sản phẩm (tìm chính xác hoặc chứa chuỗi).
                         Ví dụ: "Smartphones", "Laptop", "điện thoại"
                         
                min_price: Giá tối thiểu (VND). Dùng để lọc sản phẩm có giá >= giá trị này.
                          Ví dụ: 500000 (tức >=500k), 1000000 (>=1tr)
                          
                max_price: Giá tối đa (VND). Dùng để lọc sản phẩm có giá <= giá trị này.
                          Ví dụ: 5000000 (<=5tr), 10000000 (<=10tr)
                          
                check_inventory: True nếu cần kiểm tra tồn kho trong warehouse.
                                Khi True, tool sẽ trả về thêm thông tin số lượng tồn kho.
                
                include_description: True nếu cần lấy mô tả chi tiết của sản phẩm.
                                    Mặc định False để tối ưu hiệu suất. Chỉ bật khi người dùng
                                    yêu cầu thông tin chi tiết về sản phẩm.
                                
                limit: Số lượng sản phẩm tối đa trả về (mặc định 3, tối đa 30)
            
            Returns:
                str: Thông tin chi tiết về sản phẩm bao gồm:
                    - Tên, SKU, giá
                    - Danh mục, màu sắc
                    - Mô tả chi tiết (nếu include_description=True)
                    - Tồn kho (nếu check_inventory=True)
                    - Tổng số sản phẩm tìm thấy
            
            Ví dụ sử dụng:
                1. "có sản phẩm iphone nào không?" 
                   -> search_products_tool(search_query="iphone", search_query_keyword="iphone")
                   
                2. "những sản phẩm có giá dưới 500k"
                   -> search_products_tool(max_price=500000)
                   
                3. "tìm túi có mã IP15PM-256-BLK-2"
                   -> search_products_tool(search_query="túi", search_query_keyword="túi", sku="IP15PM-256-BLK-2")
                   
                4. "có điện thoại nào không"
                   -> search_products_tool(search_query="điện thoại", search_query_keyword="phone")
                   
                5. "có bán bao nhiêu sản phẩm"
                   -> search_products_tool(limit=50) để đếm tất cả
                   
                6. "túi maggie còn hàng không"
                   -> search_products_tool(search_query="túi", search_query_keyword="maggie", check_inventory=True)
                   
                7. "iphone giá từ 20tr đến 30tr"
                   -> search_products_tool(search_query="iphone", min_price=20000000, max_price=30000000)
            """
            qa_future = None
            qa_executor: Optional[ThreadPoolExecutor] = None
            try:
                if not self.bot_agent.current_bot_info:
                    return "❌ Chưa có thông tin bot. Vui lòng kiểm tra cấu hình.\n\n"
                
                # logging.info(f"self.bot_agent.current_bot_info: {self.bot_agent.current_bot_info}")
                
                # Lấy company_id từ bot info
                company_id = self.bot_agent.current_bot_info.get("company_id")
                if not company_id:
                    return "❌ Không tìm thấy thông tin công ty.\n\n"
                
                # ✅ OPTIMIZATION: Tự động tách SKU nếu Agent truyền sai (gộp SKU vào search_query)
                # Phát hiện pattern: search_query chứa cả tên + số (VD: "Maggie 38301")
                if search_query and not sku:
                    import re
                    # Tìm số trong search_query (có thể là SKU)
                    numbers = re.findall(r'\b\d+\b', search_query)
                    if numbers:
                        # Lấy số cuối cùng làm SKU (thường là mã sản phẩm)
                        potential_sku = numbers[-1]
                        # Loại bỏ số khỏi search_query
                        search_query_cleaned = re.sub(r'\s*\b' + re.escape(potential_sku) + r'\b\s*', ' ', search_query).strip()
                        
                        if search_query_cleaned:  # Nếu còn lại tên sản phẩm
                            sku = potential_sku
                            search_query = search_query_cleaned
                            search_query_keyword = search_query_cleaned if not search_query_keyword else search_query_keyword
                            logger.info(f"🔄 Auto-split SKU: search_query='{search_query}', sku='{sku}'")
                
                # Giới hạn limit
                limit = min(max(1, limit), 50)
                
                # ✅ OPTIMIZATION: Tạo cache key từ tất cả parameters
                cache_key_parts = [
                    str(company_id),
                    str(search_query or ''),
                    str(search_query_keyword or ''),
                    str(sku or ''),
                    str(category or ''),
                    str(min_price or ''),
                    str(max_price or ''),
                    str(check_inventory),
                    str(include_description),
                    str(limit)
                ]
                cache_key = '_'.join(cache_key_parts)
                
                # ✅ OPTIMIZATION: Kiểm tra cache trước
                current_time = datetime.now().timestamp()
                if cache_key in self.sync_mongo._product_cache:
                    cached_result, timestamp = self.sync_mongo._product_cache[cache_key]
                    if current_time - timestamp < self.sync_mongo._cache_ttl:
                        logger.debug(f"✅ Product cache hit: {cache_key[:50]}...")
                        return cached_result
                
                # Kết nối database
                if not self.sync_mongo.connect():
                    return "❌ Không thể kết nối database.\n\n"
                
                collection = self.sync_mongo.database["products"]
                
                # Xây dựng query tìm kiếm
                query_filter = {"company_id": company_id}
                
                # ✅ ƯU TIÊN 1: Tìm theo SKU (chính xác nhất) - Nếu có SKU thì chỉ tìm theo SKU
                active_search_query = None
                need_fallback_search = False
                
                if sku and sku.strip():
                    logger.info(f"🔍 Priority search by SKU: {sku}")
                    query_filter["sku"] = {"$regex": sku, "$options": "i"}
                    active_search_query = sku
                    need_fallback_search = False
                
                # ✅ ƯU TIÊN 2: Tìm theo search_query (tên, mô tả) - Chỉ khi KHÔNG có SKU
                elif search_query and search_query.strip():
                    # Loại bỏ dấu tiếng Việt để tìm kiếm tốt hơn
                    import unicodedata
                    def remove_accents(text):
                        nfd = unicodedata.normalize('NFD', text)
                        return ''.join([c for c in nfd if not unicodedata.combining(c)])
                    
                    # Thử dùng text search trước (nếu có index)
                    search_clean = search_query.strip()
                    active_search_query = search_clean
                    
                    # Fallback: Regex search cho linh hoạt hơn
                    query_filter["$or"] = [
                        {"name": {"$regex": search_clean, "$options": "i"}},
                        {"sku": {"$regex": search_clean, "$options": "i"}},
                        {"data.tags": {"$regex": search_clean, "$options": "i"}},
                        {"data.category": {"$regex": search_clean, "$options": "i"}},
                        {"data.description": {"$regex": search_clean, "$options": "i"}},
                    ]
                    
                    # Đánh dấu cần fallback nếu có search_query_keyword
                    if search_query_keyword and search_query_keyword.strip():
                        need_fallback_search = True
                else:
                    # Không có cả SKU và search_query
                    if search_query_keyword and search_query_keyword.strip():
                        need_fallback_search = True
                
                # 3. Tìm theo category (không override SKU filter)
                if category and category.strip():
                    # Chỉ thêm category filter, không xóa các filter khác
                    query_filter["data.category"] = {"$regex": category, "$options": "i"}
                
                # 4. Lọc theo khoảng giá (không override SKU filter)
                price_filter = {}
                if min_price is not None and min_price > 0:
                    price_filter["$gte"] = min_price
                if max_price is not None and max_price > 0:
                    price_filter["$lte"] = max_price
                    
                if price_filter:
                    query_filter["pricing.price"] = price_filter
                
                logger.info(f"🔍 Final query filter: {query_filter}")
                
                # Projection: chỉ lấy fields cần thiết
                projection = {
                    "name": 1, "sku": 1, "pricing": 1, "media": 1,
                    "data.category": 1, "data.color": 1
                }
                
                # Chỉ lấy description nếu được yêu cầu
                if include_description:
                    projection["data.description"] = 1
                
                # Thực hiện tìm kiếm với hint index (nếu có)
                cursor = collection.find(query_filter, projection).limit(limit)
                
                # Hint index để tăng tốc (nếu có index trên company_id)
                try:
                    cursor = cursor.hint([("company_id", 1)])
                except:
                    pass  # Ignore nếu không có index
                
                products = list(cursor)
                
                # FALLBACK: Nếu không tìm thấy sản phẩm và có search_query_keyword, thử tìm lại với keyword
                if not products and need_fallback_search and search_query_keyword and search_query_keyword.strip():
                    logger.info(f"🔄 Fallback search với keyword: {search_query_keyword}")
                    
                    # Reset query và tìm lại với keyword đơn giản hơn
                    fallback_query_filter = {"company_id": company_id}
                    keyword_clean = search_query_keyword.strip()
                    
                    fallback_query_filter["$or"] = [
                        {"name": {"$regex": keyword_clean, "$options": "i"}},
                        {"sku": {"$regex": keyword_clean, "$options": "i"}},
                        {"data.description": {"$regex": keyword_clean, "$options": "i"}},
                        {"data.tags": {"$regex": keyword_clean, "$options": "i"}},
                        {"data.category": {"$regex": keyword_clean, "$options": "i"}},
                    ]
                    
                    # Thêm lại các filter khác (category, price) nếu có
                    if category and category.strip():
                        fallback_query_filter["data.category"] = {"$regex": category, "$options": "i"}
                    
                    if price_filter:
                        fallback_query_filter["pricing.price"] = price_filter
                    
                    # Tìm kiếm lại
                    fallback_cursor = collection.find(fallback_query_filter, projection).limit(limit)
                    try:
                        fallback_cursor = fallback_cursor.hint([("company_id", 1)])
                    except:
                        pass
                    
                    products = list(fallback_cursor)
                    active_search_query = keyword_clean  # Cập nhật query đang dùng
                
                # ❌ KHÔNG return sớm nữa - vẫn tiếp tục search Q&A ngay cả khi không tìm thấy product
                # if not products:
                #     return "❌ Không tìm thấy sản phẩm nào phù hợp.\n\n"
                
                qa_lines: list[str] = []
                # Fetch supporting QA pairs from knowledge base filtered by product tags
                rag_service = getattr(self.bot_agent, "rag_retrieval_service", None)
                user_id = None

                if rag_service:
                    try:
                        user_id = getattr(self.bot_agent, "current_user_id", None)
                        if not user_id:
                            maybe_user_id = self.bot_agent.current_bot_info.get("user_id")
                            if maybe_user_id:
                                self.bot_agent.current_user_id = maybe_user_id
                                user_id = maybe_user_id
                    except Exception as user_resolve_error:
                        logger.error(f"Error resolving user_id for product QA search: {user_resolve_error}")
                        user_id = None

                if rag_service and user_id:
                    qa_limit = 3
                    candidate_values: list[str] = []

                    for raw_value in (search_query, search_query_keyword, sku):
                        if raw_value:
                            value_str = str(raw_value).strip()
                            if value_str:
                                candidate_values.append(value_str)

                    for product in products:
                        name_value = str(product.get("name") or "").strip()
                        if name_value:
                            candidate_values.append(name_value)

                    seen_candidates: set[str] = set()
                    qa_candidates: list[str] = []
                    for candidate_value in candidate_values:
                        normalized_candidate = candidate_value.lower()
                        if normalized_candidate in seen_candidates:
                            continue
                        seen_candidates.add(normalized_candidate)
                        qa_candidates.append(candidate_value)
                        if len(qa_candidates) >= 5:
                            break

                    def normalize_text(text: Optional[str]) -> str:
                        if not text:
                            return ""
                        return " ".join(str(text).lower().split())

                    def fetch_product_qa_pairs(candidates: List[str]) -> List[str]:
                        qa_results: list[Dict[str, Any]] = []
                        seen_chunk_ids: set[str] = set()
                        seen_pairs: set[Tuple[str, str]] = set()

                        for candidate in candidates:
                            if len(qa_results) >= qa_limit:
                                break

                            remaining = qa_limit - len(qa_results)
                            if remaining <= 0:
                                break

                            try:
                                chunks = rag_service.search_relevant_chunks_sync(
                                    query=candidate,
                                    document_ids=None,
                                    user_id=user_id,
                                    limit=remaining,
                                    chunk_types=["qa_pair"],
                                    source_types=["qa_pair"],
                                    company_id=company_id,
                                    metadata_tags=["product"]
                                )
                            except Exception as chunk_error:
                                logger.error(f"Error searching QA chunks for '{candidate}': {chunk_error}")
                                continue

                            for chunk in chunks:
                                chunk_id = str(chunk.get("_id") or chunk.get("id") or chunk.get("chunk_id") or "")
                                if chunk_id and chunk_id in seen_chunk_ids:
                                    continue

                                metadata = chunk.get("metadata", {}) or {}
                                question_text = str(chunk.get("content", "") or "")
                                answer_text = ""
                                if isinstance(metadata, dict):
                                    answer_text = str(metadata.get("answer") or metadata.get("content") or "").strip()
                                if not answer_text:
                                    answer_text = str(chunk.get("answer", "") or "").strip()

                                normalized_pair = (
                                    normalize_text(question_text),
                                    normalize_text(answer_text)
                                )
                                if normalized_pair in seen_pairs:
                                    continue

                                if chunk_id:
                                    seen_chunk_ids.add(chunk_id)

                                seen_pairs.add(normalized_pair)
                                qa_results.append((question_text.strip(), answer_text))

                                if len(qa_results) >= qa_limit:
                                    break

                        formatted_lines: list[str] = []
                        for idx, (question_text, answer_text) in enumerate(qa_results, 1):
                            entry = f"{idx}. Q: {question_text}" if question_text else f"{idx}. Q:"
                            if answer_text:
                                entry += f"\n   A: {answer_text}"
                            formatted_lines.append(entry)

                        return formatted_lines

                    if qa_candidates:
                        qa_executor = ThreadPoolExecutor(max_workers=1)
                        qa_future = qa_executor.submit(fetch_product_qa_pairs, qa_candidates)
                elif rag_service and not user_id:
                    logger.debug("No user_id available for product QA search")

                # Lấy thông tin tồn kho nếu cần - OPTIMIZED: Query chỉ các warehouse cần thiết
                inventory_map = {}
                if check_inventory:
                    warehouse_collection = self.sync_mongo.database["warehouses"]
                    product_ids = [str(p.get("_id")) for p in products]
                    
                    # Query với $elemMatch để tìm chính xác các product_id cần thiết
                    warehouses = warehouse_collection.find({
                        "company_id": company_id,
                        "inventory.product_id": {"$in": product_ids}
                    })
                    
                    for warehouse in warehouses:
                        for item in warehouse.get("inventory", []):
                            product_id = str(item.get("product_id"))
                            # Chỉ xử lý các product trong danh sách tìm kiếm
                            if product_id in product_ids:
                                quantity = item.get("quantity")
                                if quantity is not None:
                                    inventory_map[product_id] = inventory_map.get(product_id, 0) + quantity
                
                # Format kết quả
                result = f"--- PRODUCT SEARCH PARAMS ---\n"
                result += f"Search query: {search_query or 'N/A'}\n"
                result += f"Search query keyword: {search_query_keyword or 'N/A'}\n"
                result += f"SKU: {sku or 'N/A'}\n"
                result += f"Category: {category or 'N/A'}\n"
                result += f"Price range: {min_price or 'N/A'} - {max_price or 'N/A'}\n"
                result += f"--- END PARAMS ---\n\n"
                result += f"--- PRODUCT SEARCH: --- \n✅ Tìm thấy {len(products)} sản phẩm / dịch vụ / ảnh liên quan:\n\n"
                
                for i, product in enumerate(products, 1):
                    product_id = str(product.get("_id"))
                    name = product.get("name", "N/A")
                    sku_code = product.get("sku", "N/A")
                    pricing = product.get("pricing", {})
                    price = pricing.get("price", 0)
                    currency = pricing.get("currency", "VND")
                    
                    media = product.get("media", [])
                    
                    # Lấy tất cả URL của ảnh có type "image"
                    images = [item.get("url") for item in media if item.get("type") == "image" and item.get("url")]
                    
                    data = product.get("data", {})
                    category_name = data.get("category", "N/A")
                    description = data.get("description", "")
                    color = data.get("color", "")
                    
                    result += f"📦 {i}. {name}\n"
                    result += f"   • SKU: {sku_code}\n"
                    result += f"   • Giá: {price:,.0f} {currency}\n"
                    result += f"   • Danh mục: {category_name}\n"
                    if images:
                        result += f"   • Ảnh: " + "\n"
                        for img_url in images:
                            result += f"     - <image:{img_url}>\n"
                    
                    if color:
                        result += f"   • Màu sắc: {color}\n"
                    
                    # Hiển thị tồn kho - CHỈ KHI có thông tin
                    if check_inventory:
                        if product_id in inventory_map:
                            stock = inventory_map[product_id]
                            result += f"   • Tồn kho: {stock} sản phẩm\n"
                    
                    # Chỉ hiển thị mô tả khi được yêu cầu
                    if include_description and description:
                        result += f"   • Mô tả: '{description}'\n"

                if qa_future:
                    try:
                        qa_lines = qa_future.result()
                    except Exception as rag_error:
                        logger.error(f"Error retrieving product QA pairs: {rag_error}")
                        qa_lines = []

                result += "\n--- END PRODUCT SEARCH---\n\n"
                
                # Thêm tổng kết
                if len(products) == limit:
                    result += f"ℹ️ (LƯU Ý TRƯỚC KHI TRẢ LỜI) Đây chỉ là kết quả tìm kiếm {limit} sản phẩm đầu tiên trong dữ liệu. Có thể vẫn còn nhiều sản phẩm khác trong dữ liệu (nêu rõ đây là một số trong tổng số sản phẩm).\n"
                
                if qa_lines:
                    result += "\n\n--- RELATED PRODUCT QA ---\n"
                    result += "\n".join(qa_lines)
                    result += "\n--- END RELATED PRODUCT QA ---\n\n"
                else:
                    logger.info("No related product QA pairs found.")
                    
                # ✅ OPTIMIZATION: Cache kết quả
                self.sync_mongo._product_cache[cache_key] = (result, current_time)
                logger.debug(f"💾 Cached product search result: {cache_key[:50]}...")
                
                return result
                
            except Exception as e:
                logger.error(f"Error searching products: {e}")
                return f"❌ Lỗi khi tìm kiếm sản phẩm: {e}\n\n"
            finally:
                if qa_future and not qa_future.done():
                    qa_future.cancel()
                if qa_executor:
                    try:
                        qa_executor.shutdown(wait=False)
                    except Exception as shutdown_error:
                        logger.debug(f"Product QA executor shutdown warning: {shutdown_error}")
        
        return search_products_tool

    def create_search_knowledge_tool(self):
        @tool("search_knowledge")
        def search_knowledge_tool(query: str, original_query: Optional[str] = None) -> str:
            """
            🔍 KHI NGƯỜI DÙNG HỎI bất kỳ thông tin nào / tổng quan doanh nghiệp / tài liệu doanh nghiệp / sứ mệnh / chính sách / thông tin thanh toán / ...

            Args:
                query: Câu hỏi đã được viết lại bởi agent (paraphrased query)
                original_query: Câu hỏi gốc của người dùng (không viết lại)

            Returns:
                str: Thông tin liên quan (tối đa 3 kết quả từ documents + 3 từ Q&A)

            Hướng dẫn sử dụng:
                • Luôn truyền song song cả `query` (đã viết lại) và `original_query` (câu hỏi gốc).
                • Tool sẽ tìm kiếm đồng thời với cả hai biến thể để không bỏ sót thông tin.
            """
            try:
                _schedule_typing_indicator(
                    self.bot_agent.current_page_id,
                    self.bot_agent.page_access_token,
                    self.bot_agent.current_sender_id,
                )
            except Exception as e:
                logger.error(f"Error sending typing indicators: {e}")
                
            try:
                if not self.bot_agent.current_bot_info:
                    return "❌ Không có thông tin bot để tìm kiếm.\n\n"

                # Đảm bảo bot agent có user_id để search
                if not getattr(self.bot_agent, "current_user_id", None):
                    maybe_user_id = self.bot_agent.current_bot_info.get("user_id")
                    if maybe_user_id:
                        self.bot_agent.current_user_id = maybe_user_id

                rag_service = getattr(self.bot_agent, "rag_retrieval_service", None)
                if not rag_service:
                    return "❌ Hệ thống chưa sẵn sàng để tìm kiếm knowledge base.\n\n"

                user_id = self.bot_agent.current_user_id
                if not user_id:
                    return "❌ Không tìm thấy thông tin user để tìm kiếm.\n\n"

                company_id = self.bot_agent.current_bot_info.get("company_id")
                knowledge_documents = self.bot_agent.current_bot_info.get("knowledge_documents") or []
                knowledge_document_ids = self.bot_agent.current_bot_info.get("knowledge_document_ids") or []

                def _extract_document_ids() -> List[str]:
                    collected_ids: List[str] = []
                    sources = knowledge_documents if knowledge_documents else []

                    if sources:
                        for doc in sources:
                            doc_id = None
                            if isinstance(doc, dict):
                                doc_id = (
                                    doc.get("_id")
                                    or doc.get("id")
                                    or doc.get("document_id")
                                    or doc.get("documentId")
                                )
                            elif doc:
                                doc_id = doc

                            if doc_id:
                                collected_ids.append(str(doc_id))

                    if not collected_ids and knowledge_document_ids:
                        for doc_id in knowledge_document_ids:
                            if doc_id:
                                collected_ids.append(str(doc_id))

                    # Preserve order but remove duplicates
                    seen: set[str] = set()
                    unique_ids: List[str] = []
                    for doc_id in collected_ids:
                        if doc_id not in seen:
                            seen.add(doc_id)
                            unique_ids.append(doc_id)
                    return unique_ids

                doc_ids = _extract_document_ids()

                query_variants: List[str] = []
                if original_query and original_query.strip():
                    query_variants.append(original_query.strip())
                if query and query.strip():
                    rewritten = query.strip()
                    if rewritten not in query_variants:
                        query_variants.append(rewritten)

                if not query_variants:
                    return "❌ Không có query hợp lệ để tìm kiếm.\n\n"

                # Tăng max_workers để xử lý song song nhanh hơn
                max_workers = min(len(query_variants) * 3, 12)  # Tăng từ 8 lên 12
                doc_chunks: List[Dict[str, Any]] = []
                qa_chunks: List[Dict[str, Any]] = []

                def normalize_text(text: Optional[str]) -> str:
                    if not text:
                        return ""
                    return " ".join(text.lower().split())

                doc_content_seen: set[str] = set()
                qa_content_seen: set[Tuple[str, str]] = set()

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    doc_futures = []
                    if doc_ids:
                        for q in query_variants:
                            future = executor.submit(
                                rag_service.search_with_context_sync,
                                q,
                                doc_ids,
                                user_id,
                                2,
                                20,
                                None,
                                None,
                                company_id
                            )
                            doc_futures.append(future)

                    qa_futures = []
                    for q in query_variants:
                        future = executor.submit(
                            rag_service.search_relevant_chunks_sync,
                            q,
                            None,
                            user_id,
                            3,
                            0.35,
                            True,
                            ["qa_pair"],
                            ["qa_pair"],
                            company_id
                        )
                        # The code `qa_futures` is a comment in Python. Comments are used to provide
                        # explanations or annotations in the code and are not executed by the Python
                        # interpreter.
                        qa_futures.append(future)

                    doc_seen: set[str] = set()
                    for future in doc_futures:
                        try:
                            result = future.result()
                        except Exception as exc:
                            logger.error(f"Error searching documents: {exc}")
                            continue

                        for chunk in result.get('chunks', []):
                            content = chunk.get('content', '')
                            chunk_id = str(chunk.get('_id') or chunk.get('id') or chunk.get('chunk_id') or "")
                            if not chunk_id:
                                chunk_id = str(hash(content[:200]))

                            if chunk_id in doc_seen:
                                continue

                            doc_seen.add(chunk_id)
                            normalized_content = normalize_text(content)
                            if normalized_content in doc_content_seen:
                                continue

                            doc_content_seen.add(normalized_content)
                            doc_chunks.append(chunk)

                            if len(doc_chunks) >= 5:
                                break

                        if len(doc_chunks) >= 5:
                            break

                    qa_seen: set[str] = set()
                    for future in qa_futures:
                        try:
                            result = future.result()
                        except Exception as exc:
                            logger.error(f"Error searching QA pairs: {exc}")
                            continue

                        for chunk in result:
                            chunk_id = str(chunk.get('_id') or chunk.get('id') or chunk.get('chunk_id') or "")
                            if not chunk_id:
                                chunk_id = str(hash(chunk.get('content', '')[:200]))

                            if chunk_id in qa_seen:
                                continue

                            qa_seen.add(chunk_id)
                            metadata = chunk.get('metadata', {}) or {}
                            question = chunk.get('content', '')
                            answer_content = metadata.get('answer') or chunk.get('answer', '')
                            
                            normalized_pair = (
                                normalize_text(question),
                                normalize_text(answer_content)
                            )
                            if normalized_pair in qa_content_seen:
                                continue

                            qa_content_seen.add(normalized_pair)
                            qa_chunks.append(chunk)

                            if len(qa_chunks) >= 3:
                                break

                        if len(qa_chunks) >= 3:
                            break

                if not doc_chunks and not qa_chunks:
                    return "❌ Không tìm thấy thông tin liên quan đến truy vấn.\n\n"

                response_lines = []
                response_lines.append(f"Query: {original_query}")
                response_lines.append(f"Paraphrased query: {query}\n")
                
                total_results = len(doc_chunks) + len(qa_chunks)
                response_lines.append(f"📚 Tìm thấy {total_results} thông tin liên quan:\n")

                if qa_chunks:
                    response_lines.append("--- 📑 QUESTION & ANSWER PAIRS: (Nếu giống Query, hãy tham khảo thông tin và cách trả lời trong đây để đưa ra câu trả lời phù hợp) ---")
                    for idx, chunk in enumerate(qa_chunks, 1):
                        metadata = chunk.get('metadata', {}) or {}
                        question = chunk.get('content', '')
                        content = metadata.get('answer') or chunk.get('answer', '')

                        response_lines.append(f"{idx}. Query: '{question}'")
                        response_lines.append(f"Answer guide: '{content}'")
                        response_lines.append("")
                        
                    response_lines.append("--- END Q&A PAIRS ---\n")

                if doc_chunks:
                    response_lines.append("--- 📑 REFERENCE CONTENT: ---")
                    for idx, chunk in enumerate(doc_chunks, 1):
                        content = chunk.get('content', '')

                        response_lines.append(f"📑 REFERENCE {idx}:\n{content}")
                        response_lines.append("")
                    response_lines.append("--- END REFERENCE ---\n")

                return "\n".join(response_lines).strip() + "\n\n"

            except Exception as e:
                logger.error(f"Error in search_knowledge_tool: {e}", exc_info=True)
                return f"❌ Lỗi khi tìm kiếm thông tin: {e}\n\n"
        
        return search_knowledge_tool

    def create_search_products_by_image_tool(self):
        @tool("search_products_by_image")
        def search_products_by_image_tool(
            image_url: str,
            category: str = None,
            min_price: float = None,
            max_price: float = None,
            limit: int = 2
        ) -> str:
            """
            🖼️ Tìm kiếm sản phẩm bằng ảnh tương tự (Image-based Product Search)
            
            Tool này tự động được gọi khi user upload/gửi ảnh để tìm sản phẩm tương tự.
            Sử dụng AI vision để so sánh ảnh và tìm sản phẩm có hình ảnh giống nhất.
            
            ⚠️ QUAN TRỌNG:
            - Tool này chỉ dùng khi user GỬI ẢNH (không phải text)
            - Kết quả trả về có thể không giống 100% nhưng tương tự về màu sắc, hình dáng, kiểu dáng
            - Độ tương đồng được tính bằng similarity_score (0-1, càng cao càng giống)
            
            Args:
                image_url: URL của ảnh cần tìm (bắt buộc)
                category: Lọc theo danh mục (tùy chọn)
                min_price: Giá tối thiểu (VND)
                max_price: Giá tối đa (VND)
                limit: Số lượng sản phẩm tối đa trả về (mặc định 5)
            
            Returns:
                str: Danh sách sản phẩm tương tự kèm độ tương đồng và thông tin chi tiết
            
            Ví dụ sử dụng:
                1. User gửi ảnh túi xách
                   -> search_products_by_image_tool(image_url="https://...")
                   
                2. User gửi ảnh và hỏi "có màu khác không?"
                   -> search_products_by_image_tool(image_url="https://...")
                   
                3. User gửi ảnh giày và hỏi "giá bao nhiêu?"
                   -> search_products_by_image_tool(image_url="https://...", limit=3)
            """
            try:
                if not image_url:
                    logger.error("❌ Missing image_url parameter")
                    return "❌ Thiếu URL ảnh để tìm kiếm.\n\n"
                
                # logger.info(f"🖼️ ========================================")
                # logger.info(f"🖼️ SEARCH_PRODUCTS_BY_IMAGE TOOL CALLED")
                # logger.info(f"🖼️ ========================================")
                # logger.info(f"   Image URL: {image_url[:100]}...")
                # logger.info(f"   Category: {category}")
                # logger.info(f"   Price range: {min_price} - {max_price}")
                # logger.info(f"   Limit: {limit}")
                
                if not self.bot_agent.current_bot_info:
                    logger.error("❌ No bot info available")
                    return "❌ Chưa có thông tin bot. Vui lòng kiểm tra cấu hình.\n\n"
                
                # Lấy company_id từ bot info
                company_id = self.bot_agent.current_bot_info.get("company_id")
                if not company_id:
                    return "❌ Không tìm thấy thông tin công ty.\n\n"
                
                logger.info(f"🖼️ Searching products by image: {image_url}...")
                
                # ✅ FIX: Ưu tiên dùng local image cache trước (đã download trong webhook)
                image_data = None
                local_path = None
                
                # Tìm sender_id từ current context
                sender_id = None
                if hasattr(self.bot_agent, '_current_sender_id'):
                    sender_id = self.bot_agent._current_sender_id
                    logger.info(f"🔍 Found sender_id from context: {sender_id}")
                else:
                    logger.warning(f"⚠️ No _current_sender_id attribute in bot_agent")
                
                # Check cache for local image paths
                if sender_id:
                    local_paths = self.bot_agent.local_image_paths_cache.get(sender_id, [])
                    logger.info(f"📦 Cache status: {len(self.bot_agent.local_image_paths_cache)} senders, "
                               f"this sender has {len(local_paths)} local paths")
                    
                    if local_paths:
                        local_path = local_paths[0]  # Use first image
                        logger.info(f"📁 Using cached local image: {local_path}")
                        
                        try:
                            import os
                            if os.path.exists(local_path):
                                with open(local_path, 'rb') as f:
                                    image_data = f.read()
                                logger.info(f"✅ Loaded image from cache: {len(image_data)} bytes")
                            else:
                                logger.warning(f"⚠️ Cached file does not exist: {local_path}")
                                image_data = None
                        except Exception as e:
                            logger.error(f"❌ Failed to load cached image: {e}")
                            image_data = None
                    else:
                        logger.warning(f"⚠️ No cached local paths for sender {sender_id}")
                else:
                    logger.warning(f"⚠️ No sender_id available to check cache")
                
                # Fallback: Download from URL if no cached image
                if not image_data:
                    logger.info(f"📥 No cached image, downloading from URL...")
                    import requests
                    import io
                    
                    try:
                        # ✅ FIX: Thêm User-Agent và headers để tránh 403 Forbidden từ Facebook CDN
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Referer': 'https://www.facebook.com/',
                        }
                        # ✅ IMPROVED: Disable SSL verification and increase timeout
                        response = requests.get(
                            image_url, 
                            headers=headers, 
                            timeout=20,
                            verify=False,  # Disable SSL verification
                            allow_redirects=True
                        )
                        response.raise_for_status()
                        image_data = response.content
                        logger.info(f"✅ Downloaded image: {len(image_data)} bytes")
                    except Exception as e:
                        logger.error(f"❌ Failed to download image: {e}")
                        # ✅ GRACEFUL DEGRADATION: Thay vì fail, return friendly message
                        return ("❌ Hiện tại không thể tìm kiếm bằng ảnh do vấn đề kỹ thuật.\n"
                               "Bạn vui lòng mô tả sản phẩm bằng text hoặc cung cấp tên/mã sản phẩm để em hỗ trợ tốt hơn nhé!\n\n"
                               f"(Lỗi kỹ thuật: {str(e)[:100]})")
                
                # Search products by image using enhanced manager
                try:
                    # logger.info(f"🔍 Starting image search...")
                    # logger.info(f"   Image data size: {len(image_data)} bytes")
                    # logger.info(f"   Company ID: {company_id}")
                    
                    # Build filters
                    price_range = None
                    if min_price or max_price:
                        price_range = {}
                        if min_price:
                            price_range["min"] = min_price
                        if max_price:
                            price_range["max"] = max_price
                        logger.info(f"   Price range filter: {price_range}")
                    
                    # ✅ FIX: Get main event loop from bot_agent and submit coroutine to it
                    # This tool runs in thread pool (via asyncio.to_thread), so we need to
                    # submit async work back to the main loop that owns MongoDB connections
                    import asyncio
                    
                    # Get saved main loop reference
                    if hasattr(self.bot_agent, '_main_event_loop'):
                        main_loop = self.bot_agent._main_event_loop
                        logger.info(f"✅ Using saved main event loop")
                        logger.info(f"🚀 Submitting coroutine to main loop...")
                        
                        # Submit coroutine to main loop and wait for result
                        future = asyncio.run_coroutine_threadsafe(
                            self.bot_agent.factory.product_enhanced_manager.search_products_by_image(
                                query_image_data=image_data,
                                company_id=company_id,
                                category=category,
                                price_range=price_range,
                                limit=limit
                            ),
                            main_loop
                        )
                        
                        logger.info(f"⏳ Waiting for search results (timeout=30s)...")
                        # Wait for result (with timeout)
                        products = future.result(timeout=30)
                        logger.info(f"✅ Search completed! Found {len(products)} products")
                    else:
                        logger.error("❌ No main event loop saved in bot_agent!")
                        return "❌ Lỗi kỹ thuật: Không thể xử lý tìm kiếm bằng ảnh.\n\n"
                    
                    if not products:
                        logger.warning(f"⚠️ No products found matching image")
                        return "❌ Không tìm thấy sản phẩm tương tự với ảnh này.\n\n"
                    
                    logger.info(f"📦 Formatting {len(products)} products into response...")
                    
                    # ✅ Check if we have EXACT match (100% similarity)
                    has_exact_match = products[0].get("similarity_score", 0) >= 0.99 if products else False
                    
                    # Format response header
                    if has_exact_match:
                        # ✅ EXACT MATCH - Đây CHÍNH XÁC là sản phẩm trong ảnh!
                        result = "--- IMAGE SEARCH RESULT ---\n"
                        result += f"✅ TÌM THẤY SẢN PHẨM CHÍNH XÁC TRONG ẢNH!\n\n"
                        result += f"Đây chính xác là thông tin sản phẩm trong ảnh user gửi:\n\n"
                    else:
                        # Similar products - Các sản phẩm tương tự
                        result = "--- IMAGE SEARCH RESULT ---\n"
                        result += f"🖼️ Tìm thấy {len(products)} sản phẩm tương tự:\n\n"
                    
                    # Format each product (similar to search_products_tool)
                    for idx, product in enumerate(products, 1):
                        product_id = str(product.get("_id"))
                        name = product.get("name", "N/A")
                        sku_code = product.get("sku", "N/A")
                        pricing = product.get("pricing", {})
                        price = pricing.get("price", 0)
                        currency = pricing.get("currency", "VND")
                        
                        media = product.get("media", [])
                        # Lấy tất cả URL của ảnh có type "image"
                        images = [item.get("url") for item in media if item.get("type") == "image" and item.get("url")]
                        
                        data = product.get("data", {})
                        category_name = data.get("category", "N/A")
                        description = data.get("description", "")
                        color = data.get("color", "")
                        
                        similarity = product.get("similarity_score", 0)
                        matched_image = product.get("matched_image", "")
                        
                        # ✅ Highlight EXACT match
                        if similarity >= 0.99:
                            result += f"📦 {idx}. **{name}** (CHÍNH XÁC - 100% giống)\n"
                        else:
                            result += f"📦 {idx}. {name}\n"
                        
                        result += f"   • SKU: {sku_code}\n"
                        result += f"   • Giá: {price:,.0f} {currency}\n"
                        result += f"   • Danh mục: {category_name}\n"
                        
                        # Hiển thị độ tương đồng (nếu không phải 100%)
                        if similarity < 0.99:
                            similarity_pct = f"{similarity * 100:.1f}%"
                            result += f"   • Độ tương đồng: {similarity_pct}\n"
                        
                        # Hiển thị tất cả ảnh sản phẩm
                        if images:
                            result += f"   • Ảnh: " + "\n"
                            for img_url in images:
                                result += f"     - <image:{img_url}>\n"
                        
                        if color:
                            result += f"   • Màu sắc: {color}\n"
                        
                        # ✅ LUÔN hiển thị mô tả (nếu có)
                        if description:
                            result += f"   • Mô tả: '{description}'\n"
                        
                        result += "\n"
                    
                    result += "--- END IMAGE SEARCH ---\n\n"
                    
                    # ✅ Different note for exact match vs similar products
                    if has_exact_match:
                        result += f"✅ QUAN TRỌNG: Sản phẩm đầu tiên là KẾT QUẢ CHÍNH XÁC 100%.\n"
                        result += f"   Hãy sử dụng thông tin này để trả lời khách hàng.\n\n"
                    else:
                        result += f"💡 Lưu ý: Độ tương đồng cho biết mức độ giống nhau giữa ảnh gửi và ảnh sản phẩm.\n"
                        result += f"   Sản phẩm đầu tiên có độ tương đồng cao nhất.\n\n"
                    
                    logger.info(f"✅ Response formatted: {len(result)} chars")
                    logger.info(f"🖼️ ========================================\n")
                    return result
                    
                except Exception as e:
                    logger.error(f"❌ Error searching products by image: {e}", exc_info=True)
                    return f"❌ Lỗi khi tìm kiếm sản phẩm bằng ảnh: {e}\n\n"
                
            except Exception as e:
                logger.error(f"Error in search_products_by_image_tool: {e}", exc_info=True)
                return f"❌ Lỗi: {e}\n\n"
        
        return search_products_by_image_tool

    def get_all_tools(self) -> List[BaseTool]:
        """
        Lấy tất cả tools
        
        Returns:
            List[BaseTool]: Danh sách tất cả tools
        """
        return [
            self.create_search_products_tool(), 
            self.create_search_knowledge_tool(),
            self.create_search_products_by_image_tool(),  # ✅ Thêm tool mới
            self.create_customer_info_tool(),
            self.create_save_customer_tool(), 
            self.create_save_order_tool(),
            self.create_update_order_tool(),
            self.create_get_order_info_tool(),
        ]
        
        
async def send_typing_indicators_async_public(page_id, page_access_token, sender_id):
    try:
        await asyncio.to_thread(
            send_typing_action,
            page_id,
            page_access_token,
            sender_id,
        )
    except Exception as e:
        logger.debug(f"Typing indicator failed (non-critical): {e}")
