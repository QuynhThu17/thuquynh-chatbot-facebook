"""
Example: Cách áp dụng Notification Mixins vào các Managers
"""

from controllers.data.managements.base_manager import BaseManager
from controllers.data.managements.notification_mixin import (
    CustomerNotificationMixin,
    OrderNotificationMixin,
    ConversationNotificationMixin,
    BotNotificationMixin,
    CRMNotificationMixin,
    KnowledgeNotificationMixin,
    HistoryNotificationMixin,
    SocialNotificationMixin,
    BusinessNotificationMixin
)
from controllers.databases.mongodb.mongodb import MongoDBManager
from typing import Dict, Any


# ===== EXAMPLE 1: Customer Manager với Notification =====
class CustomerManager(BaseManager, CustomerNotificationMixin):
    """Manager cho customers collection với notification support"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "customers")
        # QUAN TRỌNG: Phải gọi init_notification_mixin
        self.init_notification_mixin(db_manager)
    
    async def create_customer(
        self,
        user_id: str,
        name: str,
        email: str,
        phone: str,
        source: str = "manual",
        **kwargs
    ) -> Dict[str, Any]:
        """Tạo customer mới và gửi notification"""
        
        # 1. Tạo customer
        customer_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "source": source,
            "user_id": user_id,
            **kwargs
        }
        customer = await self.create(customer_data)
        
        # 2. Gửi notification
        await self.notify_customer_created(
            user_id=user_id,
            customer_name=name,
            customer_id=str(customer["_id"]),
            source=source
        )
        
        return customer
    
    async def update_customer(
        self,
        customer_id: str,
        user_id: str,
        update_data: Dict[str, Any],
        changes_description: str
    ) -> Dict[str, Any]:
        """Cập nhật customer và gửi notification"""
        
        # 1. Cập nhật customer
        customer = await self.update_by_id(customer_id, update_data)
        
        if customer:
            # 2. Gửi notification
            await self.notify_customer_updated(
                user_id=user_id,
                customer_name=customer.get("name", "Unknown"),
                customer_id=customer_id,
                changes=changes_description
            )
        
        return customer


# ===== EXAMPLE 2: Order Manager với Notification =====
class OrderManager(BaseManager, OrderNotificationMixin):
    """Manager cho orders collection với notification support"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "orders")
        self.init_notification_mixin(db_manager)
    
    async def create_order(
        self,
        user_id: str,
        customer_name: str,
        items: list,
        total_amount: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Tạo order mới và gửi notification"""
        
        # 1. Tạo order
        order_data = {
            "user_id": user_id,
            "customer_name": customer_name,
            "items": items,
            "total_amount": total_amount,
            "status": "pending",
            **kwargs
        }
        order = await self.create(order_data)
        order_id = str(order["_id"])
        
        # 2. Gửi notification
        await self.notify_order_created(
            user_id=user_id,
            order_id=order_id,
            customer_name=customer_name,
            total_amount=total_amount
        )
        
        return order
    
    async def update_order_status(
        self,
        order_id: str,
        user_id: str,
        new_status: str
    ) -> Dict[str, Any]:
        """Cập nhật trạng thái order và gửi notification"""
        
        # 1. Lấy order hiện tại
        order = await self.get_by_id(order_id)
        if not order:
            return None
        
        old_status = order.get("status", "unknown")
        
        # 2. Cập nhật status
        updated_order = await self.update_by_id(order_id, {"status": new_status})
        
        # 3. Gửi notification
        await self.notify_order_status_changed(
            user_id=user_id,
            order_id=order_id,
            old_status=old_status,
            new_status=new_status
        )
        
        return updated_order


# ===== EXAMPLE 3: Conversation Manager với Notification =====
class ConversationManager(BaseManager, ConversationNotificationMixin):
    """Manager cho conversations với notification support"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "conversations")
        self.init_notification_mixin(db_manager)
    
    async def handle_new_message(
        self,
        page_owner_id: str,
        sender_name: str,
        message_content: str,
        conversation_id: str,
        platform: str = "messenger"
    ):
        """Xử lý tin nhắn mới và gửi notification"""
        
        # 1. Lưu message vào database
        # ... your logic ...
        
        # 2. Gửi notification cho page owner
        await self.notify_new_message(
            user_id=page_owner_id,
            sender_name=sender_name,
            message_preview=message_content,
            conversation_id=conversation_id,
            platform=platform
        )


# ===== EXAMPLE 4: History Manager với Notification =====
class HistoryManager(BaseManager, HistoryNotificationMixin):
    """Manager cho history/activity tracking với notification support"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "histories")
        self.init_notification_mixin(db_manager)
    
    async def log_activity(
        self,
        user_id: str,
        activity_type: str,
        description: str,
        related_resource_type: str = None,
        related_resource_id: str = None,
        should_notify: bool = True,
        **metadata
    ) -> Dict[str, Any]:
        """
        Ghi log hoạt động và tùy chọn gửi notification
        
        Args:
            user_id: User thực hiện hoạt động
            activity_type: Loại hoạt động (VD: "created_order", "updated_customer")
            description: Mô tả hoạt động
            related_resource_type: Loại resource liên quan (VD: "order", "customer")
            related_resource_id: ID của resource
            should_notify: Có gửi notification không
            **metadata: Dữ liệu bổ sung
        """
        
        # 1. Tạo history record
        history_data = {
            "user_id": user_id,
            "activity_type": activity_type,
            "description": description,
            "related_resource_type": related_resource_type,
            "related_resource_id": related_resource_id,
            "metadata": metadata
        }
        history = await self.create(history_data)
        history_id = str(history["_id"])
        
        # 2. Gửi notification nếu cần
        if should_notify:
            await self.notify_history_created(
                user_id=user_id,
                activity_type=activity_type,
                description=description,
                history_id=history_id,
                related_resource_type=related_resource_type,
                related_resource_id=related_resource_id
            )
        
        return history


# ===== EXAMPLE 5: CRM Manager với Multiple Notification Methods =====
class CRMManager(BaseManager, CRMNotificationMixin):
    """Manager cho CRM với notification support"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "crm_leads")
        self.init_notification_mixin(db_manager)
    
    async def create_lead(
        self,
        user_id: str,
        name: str,
        email: str,
        source: str,
        lead_score: int = 0,
        **kwargs
    ) -> Dict[str, Any]:
        """Tạo lead mới và gửi notification"""
        
        # 1. Tạo lead
        lead_data = {
            "name": name,
            "email": email,
            "source": source,
            "lead_score": lead_score,
            "user_id": user_id,
            **kwargs
        }
        lead = await self.create(lead_data)
        
        # 2. Gửi notification (priority cao nếu lead score >= 70)
        await self.notify_lead_created(
            user_id=user_id,
            lead_name=name,
            lead_id=str(lead["_id"]),
            source=source,
            lead_score=lead_score
        )
        
        return lead


# ===== EXAMPLE 6: Sử dụng trong API Endpoint =====
"""
# Trong file api/v1/customers/api_customer_management.py

from fastapi import APIRouter, HTTPException, Depends
from controllers.data.managements import get_mongodb_factory

@router.post("/customers")
async def create_customer_endpoint(
    customer_data: CustomerCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_mongodb_factory)
):
    try:
        user_id = current_user.get("user_id")
        
        # CustomerManager đã có notification mixin
        customer = await factory.customer_manager.create_customer(
            user_id=user_id,
            name=customer_data.name,
            email=customer_data.email,
            phone=customer_data.phone,
            source="api"
        )
        
        # Notification đã được gửi tự động!
        
        return {"success": True, "data": customer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
"""


# ===== EXAMPLE 7: Multiple Mixins trong một Manager =====
class UnifiedManager(
    BaseManager,
    CustomerNotificationMixin,
    OrderNotificationMixin,
    HistoryNotificationMixin
):
    """
    Manager có thể sử dụng nhiều notification mixins
    Hữu ích khi một manager xử lý nhiều loại resources
    """
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "unified_collection")
        self.init_notification_mixin(db_manager)
    
    async def process_customer_order(
        self,
        user_id: str,
        customer_name: str,
        order_data: dict
    ):
        """Xử lý đơn hàng và log history"""
        
        # 1. Xử lý order
        order = await self.create(order_data)
        order_id = str(order["_id"])
        
        # 2. Notify về order
        await self.notify_order_created(
            user_id=user_id,
            order_id=order_id,
            customer_name=customer_name,
            total_amount=order_data["total_amount"]
        )
        
        # 3. Log history
        await self.notify_history_created(
            user_id=user_id,
            activity_type="order_created",
            description=f"Tạo đơn hàng #{order_id} cho khách hàng {customer_name}",
            history_id=order_id,
            related_resource_type="order",
            related_resource_id=order_id
        )
        
        return order


# ===== EXAMPLE 8: Conditional Notification =====
class SmartOrderManager(BaseManager, OrderNotificationMixin):
    """Manager với logic notification thông minh"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "smart_orders")
        self.init_notification_mixin(db_manager)
    
    async def create_order_smart(
        self,
        user_id: str,
        customer_name: str,
        total_amount: float,
        notify_threshold: float = 1000000  # Chỉ notify nếu order >= 1M
    ) -> Dict[str, Any]:
        """Tạo order và chỉ notify nếu đơn hàng đủ lớn"""
        
        order_data = {
            "user_id": user_id,
            "customer_name": customer_name,
            "total_amount": total_amount,
            "status": "pending"
        }
        order = await self.create(order_data)
        order_id = str(order["_id"])
        
        # Chỉ notify nếu order >= threshold
        if total_amount >= notify_threshold:
            await self.notify_order_created(
                user_id=user_id,
                order_id=order_id,
                customer_name=customer_name,
                total_amount=total_amount
            )
        
        return order


# ===== EXAMPLE 9: Background Notification =====
"""
# Trong API với BackgroundTasks

from fastapi import BackgroundTasks

@router.post("/customers/bulk")
async def create_bulk_customers(
    customers: List[CustomerCreate],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_mongodb_factory)
):
    user_id = current_user.get("user_id")
    created_customers = []
    
    for customer_data in customers:
        customer = await factory.customer_manager.create(customer_data.dict())
        created_customers.append(customer)
        
        # Gửi notification trong background
        background_tasks.add_task(
            factory.customer_manager.notify_customer_created,
            user_id=user_id,
            customer_name=customer_data.name,
            customer_id=str(customer["_id"]),
            source="bulk_import"
        )
    
    return {"success": True, "count": len(created_customers)}
"""


# ===== SUMMARY =====
"""
## Cách sử dụng Notification Mixins:

### 1. Import Mixin phù hợp:
from controllers.data.managements.notification_mixin import CustomerNotificationMixin

### 2. Kế thừa trong Manager:
class YourManager(BaseManager, CustomerNotificationMixin):
    def __init__(self, db_manager):
        super().__init__(db_manager, "collection_name")
        self.init_notification_mixin(db_manager)  # QUAN TRỌNG!

### 3. Gọi notification methods:
await self.notify_customer_created(...)

### 4. Available Mixins:
- CustomerNotificationMixin
- OrderNotificationMixin
- ConversationNotificationMixin
- BotNotificationMixin
- CRMNotificationMixin
- KnowledgeNotificationMixin
- HistoryNotificationMixin
- SocialNotificationMixin
- BusinessNotificationMixin
- SystemNotificationMixin
- AuthNotificationMixin

### 5. Benefits:
✅ Tự động tạo notification khi có sự kiện
✅ Consistent notification format
✅ Dễ maintain và extend
✅ Tích hợp sẵn với Recent Activity
✅ Support link reference để navigate
"""
