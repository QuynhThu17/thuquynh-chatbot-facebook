"""
CRM Management Module
Quản lý companies, contacts, products, warehouses, orders, shipments
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from .base_manager import BaseManager
from .product_enhanced_manager import ProductEnhancedManager
from .notification_mixin import CustomerNotificationMixin, OrderNotificationMixin, CRMNotificationMixin
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.ultils.notification_background_tasks import run_in_background

logger = logging.getLogger(__name__)

class CompanyManager(BaseManager, CRMNotificationMixin):
    """Manager cho companies collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "companies")
        self.init_notification_mixin(db_manager)
    
    async def create_company(self, name: str, user_id: str, website: str = None,
                           industry: str = None, address: Union[str, Dict[str, str]] = None, 
                           data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Tạo company mới"""
        company_data = {
            "name": name,
            "website": website,
            "industry": industry,
            "address": address,
            "user_id": user_id,
            "is_default": False,  
        }
        
        # thêm lần lượt các trường trong data nếu có
        if data:
            for key, value in data.items():
                company_data[key] = value
        
        result = await self.create(company_data)
        
        # Gửi notification
        if result:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Tạo công ty thành công",
                content=f"Đã tạo công ty: {name}",
                category="crm",
                notification_type="success",
                action="company_created",
                priority=1,
                metadata={
                    "company_id": str(result["_id"]),
                    "company_name": name,
                    "industry": industry
                }
            )
        
        return result
    
    async def get_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy companies theo user_id"""
        return await self.get_all(filter_query={"user_id": user_id})
    
    async def get_default_company_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy company mặc định của user"""
        companies = await self.get_all(
            filter_query={"user_id": user_id, "is_default": True}, 
            limit=1
        )
        return companies[0] if companies else None
    
    async def get_by_name_and_user(self, name: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Lấy company theo name và user_id"""
        companies = await self.get_all(
            filter_query={"name": name, "user_id": user_id}, 
            limit=1
        )
        return companies[0] if companies else None


class CustomerManager(BaseManager, CustomerNotificationMixin):
    """Manager cho customers collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "customers")
        self.init_notification_mixin(db_manager)
    
    async def create_customer(self, facebook_id: str = None, page_id: str = None,
                            name: str = None, phone: str = None, email: str = None,
                            address: str = None, gender: str = None, 
                            additional_info: str = None, user_id: str = None,
                            auto_reply: bool = True, status: str = "Tương tác",
                            tags: list = None, **kwargs) -> Dict[str, Any]:
        """Tạo customer mới"""
        customer_data = {
            "facebook_id": facebook_id,
            "page_id": page_id,
            "name": name,
            "phone": phone,
            "email": email,
            "address": address,
            "gender": gender,
            "additional_info": additional_info,
            "user_id": user_id,
            "auto_reply": auto_reply if auto_reply is not None else True,
            "status": status if status else "Tương tác",
            "tags": tags if tags is not None else []
        }
        # Merge thêm kwargs nếu có
        customer_data.update(kwargs)
        
        customer = await self.create(customer_data)
        
        # Gửi notification trong background
        if customer and user_id:
            run_in_background(
                self.notify_customer_created,
                user_id=user_id,
                customer_name=name or "Khách hàng mới",
                customer_id=str(customer.get("_id"))
            )
        
        return customer
    
    async def update_customer(self, customer_id: Union[str, ObjectId], 
                            update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật thông tin customer"""
        customer = await self.update_by_id(customer_id, update_data)
        
        # Gửi notification trong background
        if customer:
            user_id = customer.get("user_id")
            customer_name = customer.get("name", "Khách hàng")
            if user_id:
                # Tạo chuỗi mô tả các thay đổi
                changes = ", ".join([f"{k}: {v}" for k, v in update_data.items() if k not in ["updated_at", "_id"]])
                if not changes:
                    changes = "Cập nhật thông tin khách hàng"
                
                run_in_background(
                    self.notify_customer_updated,
                    user_id=user_id,
                    customer_name=customer_name,
                    customer_id=str(customer_id),
                    changes=changes
                )
        
        return customer
    
    async def delete_customer(self, customer_id: Union[str, ObjectId]) -> bool:
        """Xóa customer"""
        customer = await self.get_by_id(customer_id)
        result = await self.delete_by_id(customer_id)
        
        # Gửi notification trong background
        if result and customer:
            user_id = customer.get("user_id")
            customer_name = customer.get("name", "Khách hàng")
            if user_id:
                run_in_background(
                    self.notify_customer_deleted,
                    user_id=user_id,
                    customer_name=customer_name,
                    customer_id=str(customer_id)
                )
        
        return result
    
    async def get_by_facebook_id(self, facebook_id: str) -> Optional[Dict[str, Any]]:
        """Lấy customer theo Facebook ID"""
        customers = await self.get_all(filter_query={"facebook_id": facebook_id}, limit=1)
        return customers[0] if customers else None
    
    async def get_by_customer_id_and_page(self, customer_id: str, social_page_id: str) -> Optional[Dict[str, Any]]:
        """Lấy customer theo customer_id và social_page_id"""
        customers = await self.get_all(
            filter_query={
                "customer_id": customer_id,
                "social_page_id": social_page_id
            }, 
            limit=1
        )
        return customers[0] if customers else None
    
    async def get_by_user_id(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy customers theo user_id"""
        return await self.get_all(filter_query={"user_id": user_id})


class ContactManager(BaseManager):
    """Manager cho contacts collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "contacts")
    
    async def create_contact(self, user_id: str, name: str, contact_type: str = "customer_info",
                           email: str = None, phone_number: str = None, address: str = None,
                           company_id: str = None, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo contact mới
        
        Args:
            user_id: ID user
            name: Tên contact
            contact_type: customer_info, business_human_resource, etc.
            email: Email
            phone_number: Số điện thoại
            address: Địa chỉ
            company_id: ID company
            data: Dữ liệu bổ sung
        """
        contact_data = {
            "user_id": user_id,
            "type": contact_type,
            "name": name,
            "email": email,
            "phone_number": phone_number,
            "address": address,
            "company_id": company_id,
            "data": data or {}
        }
        return await self.create(contact_data)
    
    async def get_by_user_id(self, user_id: str, contact_type: str = None, 
                           company_id: str = None) -> List[Dict[str, Any]]:
        """Lấy contacts theo user_id"""
        filter_query = {"user_id": user_id}
        if contact_type:
            filter_query["type"] = contact_type
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_email(self, email: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy contact theo email"""
        filter_query = {"email": email}
        if user_id:
            filter_query["user_id"] = user_id
        
        contacts = await self.get_all(filter_query=filter_query, limit=1)
        return contacts[0] if contacts else None
    
    async def get_by_phone(self, phone_number: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy contact theo phone"""
        filter_query = {"phone_number": phone_number}
        if user_id:
            filter_query["user_id"] = user_id
        
        contacts = await self.get_all(filter_query=filter_query, limit=1)
        return contacts[0] if contacts else None
    
    async def search_contacts(self, user_id: str, search_term: str) -> List[Dict[str, Any]]:
        """Tìm kiếm contacts"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$match": {
                    "$or": [
                        {"name": {"$regex": search_term, "$options": "i"}},
                        {"email": {"$regex": search_term, "$options": "i"}},
                        {"phone_number": {"$regex": search_term, "$options": "i"}}
                    ]
                }
            }
        ]
        
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            return [self._serialize_object_id(result) for result in results]
        except Exception as e:
            logger.error(f"Error searching contacts: {str(e)}")
            return []


class ProductManager(BaseManager):
    """Manager cho products collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "products")
    
    async def create_product(self, name: str, user_id: str, sku: str, pricing: Dict[str, Any],
                           media: List[Dict[str, Any]] = None, company_id: str = None,
                           data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo product mới
        
        Args:
            name: Tên sản phẩm
            user_id: ID user
            sku: Mã sản phẩm
            pricing: Thông tin giá (có thể có nhiều variant)
            media: List media (images, videos)
            company_id: ID company
            data: Dữ liệu bổ sung
        """
        product_data = {
            "name": name,
            "sku": sku,
            "pricing": pricing,
            "media": media or [],
            "data": data or {},
            "user_id": user_id,
            "company_id": company_id
        }
        return await self.create(product_data)
    
    async def get_by_user_id(self, user_id: str, company_id: str = None) -> List[Dict[str, Any]]:
        """Lấy products theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_sku(self, sku: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy product theo SKU"""
        filter_query = {"sku": sku}
        if user_id:
            filter_query["user_id"] = user_id
        
        products = await self.get_all(filter_query=filter_query, limit=1)
        return products[0] if products else None
    
    async def search_products(self, user_id: str, search_term: str) -> List[Dict[str, Any]]:
        """Tìm kiếm products"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$match": {
                    "$or": [
                        {"name": {"$regex": search_term, "$options": "i"}},
                        {"sku": {"$regex": search_term, "$options": "i"}},
                        {"data.description": {"$regex": search_term, "$options": "i"}}
                    ]
                }
            }
        ]
        
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            return [self._serialize_object_id(result) for result in results]
        except Exception as e:
            logger.error(f"Error searching products: {str(e)}")
            return []
    
    async def update_pricing(self, product_id: Union[str, ObjectId], 
                           new_pricing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật pricing"""
        return await self.update_by_id(product_id, {"pricing": new_pricing})
    
    async def add_media(self, product_id: Union[str, ObjectId], 
                       media_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Thêm media vào product"""
        product = await self.get_by_id(product_id)
        if product:
            current_media = product.get("media", [])
            current_media.append(media_item)
            return await self.update_by_id(product_id, {"media": current_media})
        return None


class WarehouseManager(BaseManager):
    """Manager cho warehouses collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "warehouses")
    
    async def create_warehouse(self, name: str, user_id: str, address: str = None,
                             company_id: str = None, inventory: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Tạo warehouse mới
        
        Args:
            name: Tên kho
            user_id: ID user
            address: Địa chỉ kho
            company_id: ID company
            inventory: List inventory [{product_id, quantity, location_in_warehouse}]
        """
        warehouse_data = {
            "name": name,
            "address": address,
            "inventory": inventory or [],
            "user_id": user_id,
            "company_id": company_id
        }
        return await self.create(warehouse_data)
    
    async def get_by_user_id(self, user_id: str, company_id: str = None) -> List[Dict[str, Any]]:
        """Lấy warehouses theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def update_inventory(self, warehouse_id: Union[str, ObjectId], product_id: str,
                             quantity: int, location_in_warehouse: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật inventory trong warehouse"""
        warehouse = await self.get_by_id(warehouse_id)
        if warehouse:
            inventory = warehouse.get("inventory", [])
            
            # Tìm product trong inventory
            product_found = False
            for item in inventory:
                if item["product_id"] == product_id:
                    item["quantity"] = quantity
                    if location_in_warehouse:
                        item["location_in_warehouse"] = location_in_warehouse
                    product_found = True
                    break
            
            # Nếu chưa có, thêm mới
            if not product_found:
                inventory.append({
                    "product_id": product_id,
                    "quantity": quantity,
                    "location_in_warehouse": location_in_warehouse
                })
            
            return await self.update_by_id(warehouse_id, {"inventory": inventory})
        return None
    
    async def get_product_inventory(self, product_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy inventory của product từ tất cả warehouses"""
        pipeline = [
            {"$unwind": "$inventory"},
            {"$match": {"inventory.product_id": product_id}},
            {
                "$project": {
                    "warehouse_name": "$name",
                    "warehouse_address": "$address",
                    "quantity": "$inventory.quantity",
                    "location": "$inventory.location_in_warehouse"
                }
            }
        ]
        
        if user_id:
            pipeline.insert(1, {"$match": {"user_id": user_id}})
        
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            return [self._serialize_object_id(result) for result in results]
        except Exception as e:
            logger.error(f"Error getting product inventory: {str(e)}")
            return []


class OrderManager(BaseManager, OrderNotificationMixin):
    """Manager cho orders collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "orders")
        self.init_notification_mixin(db_manager)
    
    async def create_order(self, code: str, contact_id: str, line_items: List[Dict[str, Any]],
                         total_price: float, user_id: str, company_id: str = None,
                         shipping_address: str = None, payment_method: str = None,
                         status: str = "new") -> Dict[str, Any]:
        """
        Tạo order mới
        
        Args:
            code: Mã đơn hàng
            contact_id: ID contact
            line_items: List sản phẩm [{product_id, quantity, price}]
            total_price: Tổng tiền
            user_id: ID user
            company_id: ID company
            shipping_address: Địa chỉ giao hàng
            payment_method: Phương thức thanh toán
            status: Trạng thái đơn hàng
        """
        order_data = {
            "code": code,
            "contact_id": contact_id,
            "line_items": line_items,
            "total_price": total_price,
            "shipping_address": shipping_address,
            "payment_method": payment_method,
            "status": status,
            "user_id": user_id,
            "company_id": company_id
        }
        order = await self.create(order_data)
        
        # Gửi notification trong background
        if order and user_id:
            run_in_background(
                self.notify_order_created,
                user_id=user_id,
                order_code=code,
                order_id=str(order.get("_id")),
                total_price=total_price
            )
        
        return order
    
    async def update_status(self, order_id: Union[str, ObjectId], new_status: str) -> Optional[Dict[str, Any]]:
        """Cập nhật trạng thái order"""
        order = await self.update_by_id(order_id, {"status": new_status})
        
        # Gửi notification trong background
        if order:
            user_id = order.get("user_id")
            order_code = order.get("code", "")
            if user_id:
                run_in_background(
                    self.notify_order_status_changed,
                    user_id=user_id,
                    order_id=str(order_id),
                    order_code=order_code,
                    new_status=new_status
                )
        
        return order
    
    async def update_order(self, order_id: Union[str, ObjectId], 
                         update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cập nhật thông tin order"""
        order = await self.update_by_id(order_id, update_data)
        
        # Gửi notification trong background nếu có thay đổi quan trọng
        if order and update_data:
            user_id = order.get("user_id")
            order_code = order.get("code", "")
            
            # Chỉ gửi notification cho những thay đổi quan trọng
            important_fields = ["total_price", "shipping_address", "payment_method", "line_items"]
            if user_id and any(field in update_data for field in important_fields):
                run_in_background(
                    self.notify_order_updated,
                    user_id=user_id,
                    order_id=str(order_id),
                    order_code=order_code
                )
        
        return order
    
    async def delete_order(self, order_id: Union[str, ObjectId]) -> bool:
        """Xóa order"""
        order = await self.get_by_id(order_id)
        result = await self.delete_by_id(order_id)
        
        # Gửi notification trong background
        if result and order:
            user_id = order.get("user_id")
            order_code = order.get("code", "Đơn hàng")
            if user_id:
                run_in_background(
                    self.notify_order_cancelled,
                    user_id=user_id,
                    order_code=order_code,
                    order_id=str(order_id)
                )
        
        return result
    
    async def get_by_user_id(self, user_id: str, status: str = None,
                           company_id: str = None, contact_id: str = None) -> List[Dict[str, Any]]:
        """Lấy orders theo user_id"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        if company_id:
            filter_query["company_id"] = company_id
        if contact_id:
            filter_query["contact_id"] = contact_id
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def get_by_code(self, code: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy order theo code"""
        filter_query = {"code": code}
        if user_id:
            filter_query["user_id"] = user_id
        
        orders = await self.get_all(filter_query=filter_query, limit=1)
        return orders[0] if orders else None
    
    async def get_order_with_contact(self, order_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Lấy order với thông tin contact"""
        try:
            if isinstance(order_id, str):
                order_id = ObjectId(order_id)
            
            pipeline = [
                {"$match": {"_id": order_id}},
                {
                    "$lookup": {
                        "from": "contacts",
                        "localField": "contact_id",
                        "foreignField": "_id",
                        "as": "contact"
                    }
                },
                {
                    "$unwind": {
                        "path": "$contact",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                return self._serialize_object_id(result[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting order with contact: {str(e)}")
            return None


class ShipmentManager(BaseManager):
    """Manager cho shipments collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "shipments")
    
    async def create_shipment(self, code: str, order_id: str, user_id: str,
                            carrier: str = None, tracking_number: str = None,
                            status: str = "preparing", company_id: str = None,
                            history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Tạo shipment mới
        
        Args:
            code: Mã vận chuyển
            order_id: ID order
            user_id: ID user
            carrier: Đơn vị vận chuyển
            tracking_number: Mã tracking
            status: Trạng thái vận chuyển
            company_id: ID company
            history: Lịch sử vận chuyển
        """
        shipment_data = {
            "code": code,
            "order_id": order_id,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "status": status,
            "history": history or [],
            "user_id": user_id,
            "company_id": company_id
        }
        return await self.create(shipment_data)
    
    async def get_by_user_id(self, user_id: str, status: str = None,
                           company_id: str = None) -> List[Dict[str, Any]]:
        """Lấy shipments theo user_id"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def get_by_order_id(self, order_id: str) -> List[Dict[str, Any]]:
        """Lấy shipments theo order_id"""
        return await self.get_all(filter_query={"order_id": order_id})
    
    async def get_by_tracking_number(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        """Lấy shipment theo tracking number"""
        shipments = await self.get_all(filter_query={"tracking_number": tracking_number}, limit=1)
        return shipments[0] if shipments else None
    
    async def update_status(self, shipment_id: Union[str, ObjectId], new_status: str,
                          update_note: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật trạng thái shipment"""
        shipment = await self.get_by_id(shipment_id)
        if shipment:
            # Thêm vào history
            history = shipment.get("history", [])
            history_item = {
                "status": new_status,
                "timestamp": get_vietnam_now_naive(),
                "note": update_note
            }
            history.append(history_item)
            
            update_data = {
                "status": new_status,
                "history": history
            }
            
            return await self.update_by_id(shipment_id, update_data)
        return None


# Factory class để tạo tất cả CRM managers
class CRMManagementFactory:
    """Factory để tạo tất cả CRM Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._company_manager = None
        self._contact_manager = None
        self._customer_manager = None
        self._product_manager = None
        self._product_enhanced_manager = None
        self._warehouse_manager = None
        self._order_manager = None
        self._shipment_manager = None
    
    @property
    def company_manager(self) -> CompanyManager:
        if self._company_manager is None:
            self._company_manager = CompanyManager(self.db_manager)
        return self._company_manager
    
    @property
    def contact_manager(self) -> ContactManager:
        if self._contact_manager is None:
            self._contact_manager = ContactManager(self.db_manager)
        return self._contact_manager
    
    @property
    def customer_manager(self) -> CustomerManager:
        if self._customer_manager is None:
            self._customer_manager = CustomerManager(self.db_manager)
        return self._customer_manager
    
    @property
    def product_manager(self) -> ProductManager:
        """Basic product manager (legacy)"""
        if self._product_manager is None:
            self._product_manager = ProductManager(self.db_manager)
        return self._product_manager
    
    @property
    def product_enhanced_manager(self) -> ProductEnhancedManager:
        """Enhanced product manager với image embedding (recommended)"""
        if self._product_enhanced_manager is None:
            self._product_enhanced_manager = ProductEnhancedManager(self.db_manager)
        return self._product_enhanced_manager
    
    @property
    def warehouse_manager(self) -> WarehouseManager:
        if self._warehouse_manager is None:
            self._warehouse_manager = WarehouseManager(self.db_manager)
        return self._warehouse_manager
    
    @property
    def order_manager(self) -> OrderManager:
        if self._order_manager is None:
            self._order_manager = OrderManager(self.db_manager)
        return self._order_manager
    
    @property
    def shipment_manager(self) -> ShipmentManager:
        if self._shipment_manager is None:
            self._shipment_manager = ShipmentManager(self.db_manager)
        return self._shipment_manager
