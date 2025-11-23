"""
CRM Management API Endpoints
Cung cấp API cho companies, contacts, products, warehouses, orders, shipments, customers
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
from configs.environment import get_vietnam_now_naive
import logging
import uuid
import asyncio

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.auth.auth_middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["CRM Management"])

def get_management_factory():
    return get_mongodb_factory()

# Pydantic Models
class HistoryCreate(BaseModel):
    session_id: str
    question: str
    answer: str
    context: Optional[Dict[str, Any]] = {}
    sources: Optional[List[str]] = []
    feedback_score: Optional[int] = None
    media: Optional[Dict[str, Any]] = {}
    status: str = "active"
    company_id: Optional[str] = None
    customer_id: Optional[str] = None
    bot_id: Optional[str] = None
    social_id: Optional[str] = None
    social_page_id: Optional[str] = None

class FeedbackCreate(BaseModel):
    social_id: str = "s_facebook"
    social_identification: Dict[str, Any]  # {fb_page_id, sender_id, session_id}
    content: str
    status: str = "new"  # new, reviewed, resolved

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    threshold: Optional[float] = 0.5

class CustomerCreate(BaseModel):
    social_id: str = "s_facebook"
    social_page_id: str
    customer_id: str
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = {}
    auto_reply: Optional[bool] = True
    status: Optional[str] = "Tương tác"
    tags: Optional[List[str]] = []

class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None
    auto_reply: Optional[bool] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    
class OrderCreate(BaseModel):
    social_id: str = "s_facebook"
    social_page_id: str
    customer_id: str
    product_name: str
    unit_price: float
    quantity: int
    total_price: float
    customer_note: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: str = "pending"
    status: str = "pending"

class OrderUpdate(BaseModel):
    product_name: Optional[str] = None
    unit_price: Optional[float] = None
    quantity: Optional[int] = None
    total_price: Optional[float] = None
    customer_note: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    status: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str
    
    
# Conversation History Endpoints
# @router.post("/histories", response_model=Dict[str, Any])
# async def create_history(
#     history_data: HistoryCreate,
#     current_user: dict = Depends(get_current_user),
#     factory = Depends(get_management_factory)
# ):
#     """Tạo conversation history mới"""
#     try:
#         history_doc = {
#             "history_id": f"hist_{get_vietnam_now_naive().strftime('%Y%m%d_%H%M%S')}_{current_user.get('user_id', 'unknown')}",
#             "session_id": history_data.session_id,
#             "query": history_data.question,
#             "answer": history_data.answer,
#             "media": history_data.media,
#             "status": history_data.status,
#             "user_id": current_user.get("user_id", "unknown"),
#             "company_id": history_data.company_id,
#             "customer_id": history_data.customer_id,
#             "bot_id": history_data.bot_id,
#             "social_id": history_data.social_id,
#             "social_page_id": history_data.social_page_id,
#             "created_at": get_vietnam_now_naive(),
#             "updated_at": get_vietnam_now_naive()
#         }
        
#         history = await factory.history_manager.create_history(**history_doc)
#         return {"success": True, "data": history}
        
#     except Exception as e:
#         logger.error(f"Error creating history: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/histories", response_model=Dict[str, Any])
async def get_histories(
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy lịch sử conversation của user
    
    **Query Parameters:**
    - session_id: str (optional) - Lọc theo session cụ thể
    - customer_id: str (optional) - Lọc theo khách hàng
    - bot_id: str (optional) - Lọc theo bot
    - social_id: str (optional) - Lọc theo nền tảng xã hội
    - social_page_id: str (optional) - Lọc theo trang social
    - skip: int - Số bản ghi bỏ qua (mặc định: 0)
    - limit: int - Số bản ghi trả về (mặc định: 50, max: 100)
    
    **Authentication:** Required (Bearer Token)
    
    **Response fields:**
    - _id: ObjectId - ID của history
    - history_id: str - Mã history
    - session_id: str - ID phiên
    - user_id: str - ID user
    - query: str - Câu hỏi của khách hàng
    - answer: str - Câu trả lời của bot
    - media: Dict - Media kèm theo (images, videos, ...)
    - status: str - Trạng thái
    - customer_id: str - ID khách hàng từ social platform (Facebook sender ID)
    - bot_id: str - ID bot
    - social_id: str - ID nền tảng xã hội
    - social_page_id: str - ID trang social
    - page_info: Dict - Thông tin page (nếu có)
        + _id: ObjectId - ID của page
        + fb_page_id: str - Facebook page ID
        + fb_page_name: str - Tên page
        + social_account_id: str - ID tài khoản social
    - customer_info: Dict - Thông tin khách hàng đầy đủ (nếu có)
        + _id: str - ID document của customer (dùng để gọi GET /api/v1/crm/customers/{customer_id})
        + customer_id: str - ID từ social platform (Facebook sender ID)
        + name: str - Tên khách hàng
        + phone: str - Số điện thoại
        + email: str - Email
        + address: str - Địa chỉ
        + gender: str - Giới tính
        + status: str - Trạng thái
        + tags: List[str] - Tags
        + auto_reply: bool - Trạng thái auto reply
        + additional_info: Dict - Thông tin bổ sung
        + social_id: str - ID nền tảng xã hội
        + social_page_id: str - ID trang social
        + user_id: str - ID user
        + created_at: datetime - Ngày tạo customer
        + updated_at: datetime - Ngày cập nhật customer
    - created_at: datetime - Ngày tạo
    - updated_at: datetime - Ngày cập nhật
    - pagination: Dict - Thông tin phân trang
    
    **Example:** GET /api/v1/crm/histories?session_id=sess_123&limit=20
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        histories = await factory.history_manager.get_by_user_id(user_id, session_id)
        
        # Apply additional filters if needed
        if customer_id or bot_id or social_id or social_page_id:
            filtered_histories = []
            for history in histories:
                if customer_id and history.get("customer_id") != customer_id:
                    continue
                if bot_id and history.get("bot_id") != bot_id:
                    continue
                if social_id and history.get("social_id") != social_id:
                    continue
                if social_page_id and history.get("social_page_id") != social_page_id:
                    continue
                filtered_histories.append(history)
            histories = filtered_histories
        
        # Simple pagination
        total = len(histories)
        paginated_histories = histories[skip:skip+limit]
        
        # Tối ưu: Lấy tất cả page_ids và customer_ids unique để batch query
        unique_page_ids = {}  # key: (social_id, social_page_id)
        unique_customer_keys = {}  # key: (customer_id, social_page_id)
        
        for history in paginated_histories:
            social_id = history.get("social_id")
            social_page_id = history.get("social_page_id")
            customer_id = history.get("customer_id")
            
            if social_id and social_page_id:
                unique_page_ids[(social_id, social_page_id)] = None
            
            if customer_id and social_page_id:
                unique_customer_keys[(customer_id, social_page_id)] = None
        
        # Batch fetch pages và customers song song
        async def fetch_all_pages():
            pages_dict = {}
            tasks = []
            keys = []
            
            for (social_id, social_page_id) in unique_page_ids.keys():
                if social_id == "s_facebook":
                    keys.append((social_id, social_page_id))
                    tasks.append(factory.facebook_page_manager.get_by_fb_page_id(social_page_id))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if not isinstance(result, Exception) and result:
                        social_id, social_page_id = keys[i]
                        pages_dict[(social_id, social_page_id)] = {
                            "_id": result.get("_id"),
                            "fb_page_id": result.get("fb_page_id"),
                            "fb_page_name": result.get("fb_page_name"),
                            "social_account_id": result.get("social_account_id")
                        }
            
            return pages_dict
        
        async def fetch_all_customers():
            customers_dict = {}
            tasks = []
            keys = []
            
            for (customer_id, social_page_id) in unique_customer_keys.keys():
                keys.append((customer_id, social_page_id))
                tasks.append(factory.customer_manager.get_by_customer_id_and_page(customer_id, social_page_id))
            
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if not isinstance(result, Exception) and result:
                        customer_id, social_page_id = keys[i]
                        customers_dict[(customer_id, social_page_id)] = {
                            "_id": str(result.get("_id")),
                            "customer_id": result.get("customer_id"),
                            "name": result.get("name"),
                            "phone": result.get("phone"),
                            "email": result.get("email"),
                            "address": result.get("address"),
                            "gender": result.get("gender"),
                            "status": result.get("status"),
                            "tags": result.get("tags", []),
                            "auto_reply": result.get("auto_reply", True),
                            "additional_info": result.get("additional_info", {}),
                            "social_id": result.get("social_id"),
                            "social_page_id": result.get("social_page_id"),
                            "user_id": result.get("user_id"),
                            "created_at": result.get("created_at"),
                            "updated_at": result.get("updated_at")
                        }
            
            return customers_dict
        
        # Chạy song song cả 2 batch queries
        pages_dict, customers_dict = await asyncio.gather(
            fetch_all_pages(),
            fetch_all_customers()
        )
        
        # Enrich histories với data đã fetch
        enriched_histories = []
        for history in paginated_histories:
            social_id = history.get("social_id")
            social_page_id = history.get("social_page_id")
            customer_id = history.get("customer_id")
            
            # Add page_info từ cache
            if social_id and social_page_id:
                page_info = pages_dict.get((social_id, social_page_id))
                if page_info:
                    history["page_info"] = page_info
            
            # Add customer_info từ cache
            if customer_id and social_page_id:
                customer_info = customers_dict.get((customer_id, social_page_id))
                if customer_info:
                    history["customer_info"] = customer_info
            
            enriched_histories.append(history)
        
        return {
            "success": True,
            "data": enriched_histories,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting histories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/histories/sessions", response_model=Dict[str, Any])
async def get_user_sessions(
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy all sessions của user"""
    try:
        user_id = current_user.get("user_id", "unknown")
        sessions = await factory.history_manager.get_user_sessions(user_id)
        return {"success": True, "data": sessions}
        
    except Exception as e:
        logger.error(f"Error getting user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/histories/sessions/{session_id}", response_model=Dict[str, Any])
async def delete_session_histories(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Xóa tất cả histories của một session"""
    try:
        user_id = current_user.get("user_id", "unknown")
        count = await factory.history_manager.delete_history(user_id, session_id=session_id)
        if count == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "success": True,
            "message": f"Deleted {count} conversation histories",
            "deleted_count": count
        }
        
    except Exception as e:
        logger.error(f"Error deleting session histories: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Feedback Endpoints
@router.post("/feedback", response_model=Dict[str, Any])
async def create_feedback(
    feedback_data: FeedbackCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo feedback mới từ khách hàng
    
    **Required fields:**
    - content: str - Nội dung feedback (bắt buộc)
    - social_identification: Dict[str, Any] - Thông tin nhận dạng (bắt buộc)
        + fb_page_id: str - ID trang Facebook
        + sender_id: str - ID người gửi
        + session_id: str - ID phiên
    
    **Optional fields:**
    - social_id: str - ID nền tảng xã hội (mặc định: s_facebook)
    - status: str - Trạng thái (mặc định: new)
        + new: Mới
        + reviewed: Đã xem xét
        + resolved: Đã giải quyết
    
    **Example Request:**
    ```json
    {
        "social_id": "s_facebook",
        "social_identification": {
            "fb_page_id": "123456789",
            "sender_id": "987654321",
            "session_id": "684930451376580_68db410c4fe460df83431855"
        },
        "content": "Sản phẩm rất tốt, giao hàng nhanh!",
        "status": "new"
    }
    ```
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        feedback = await factory.feedback_manager.create_feedback(
            user_id=user_id,
            social_id=feedback_data.social_id,
            social_identification=feedback_data.social_identification,
            content=feedback_data.content,
            status=feedback_data.status
        )
        
        return {"success": True, "data": feedback}
        
    except Exception as e:
        logger.error(f"Error creating feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/feedback", response_model=Dict[str, Any])
async def get_feedback(
    status: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy danh sách feedback của user hiện tại
    
    **Query Parameters:**
    - status: str (optional) - Lọc theo trạng thái
        + new: Feedback mới
        + reviewed: Đã xem xét
        + resolved: Đã giải quyết
    
    **Authentication:** Required (Bearer Token)
    
    **Response fields:**
    - _id: ObjectId - ID của feedback
    - user_id: str - ID user
    - social_id: str - ID nền tảng xã hội
    - social_identification: Dict - Thông tin nhận dạng
    - content: str - Nội dung feedback
    - status: str - Trạng thái
    - create_at: datetime - Ngày tạo
    - update_at: datetime - Ngày cập nhật
    
    **Example:** GET /api/v1/crm/feedback?status=new
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        feedback_list = await factory.feedback_manager.get_by_user_id(user_id, status)
        return {"success": True, "data": feedback_list}
        
    except Exception as e:
        logger.error(f"Error getting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Customer Endpoints
@router.post("/customers", response_model=Dict[str, Any])
async def create_customer(
    customer_data: CustomerCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo customer mới
    
    **Required fields:**
    - social_page_id: str - ID trang social (bắt buộc)
    - customer_id: str - ID khách hàng (bắt buộc)
    - name: str - Tên khách hàng (bắt buộc)
    
    **Optional fields:**
    - social_id: str - ID nền tảng xã hội (mặc định: s_facebook)
    - phone: str - Số điện thoại
    - email: str - Email
    - address: str - Địa chỉ
    - gender: str - Giới tính (male, female, other)
    - additional_info: Dict[str, Any] - Thông tin bổ sung
        + birthday: str - Ngày sinh
        + notes: str - Ghi chú
        + tags: List[str] - Thẻ tag
    
    **Example Request:**
    ```json
    {
        "social_id": "s_facebook",
        "social_page_id": "123456789",
        "customer_id": "987654321",
        "name": "Nguyen Van A",
        "phone": "+84 912 345 678",
        "email": "nguyenvana@example.com",
        "address": "123 Le Loi, Da Nang",
        "gender": "male",
        "additional_info": {
            "birthday": "1990-01-15",
            "notes": "Khách hàng thân thiết",
            "tags": ["VIP", "Regular"]
        }
    }
    ```
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        customer_doc = {
            "user_id": user_id,
            "social_id": customer_data.social_id,
            "social_page_id": customer_data.social_page_id,
            "customer_id": customer_data.customer_id,
            "name": customer_data.name,
            "phone": customer_data.phone,
            "email": customer_data.email,
            "address": customer_data.address,
            "gender": customer_data.gender,
            "additional_info": customer_data.additional_info,
            "auto_reply": customer_data.auto_reply if customer_data.auto_reply is not None else True,
            "status": customer_data.status if customer_data.status else "Tương tác",
            "tags": customer_data.tags if customer_data.tags is not None else [],
            "created_at": get_vietnam_now_naive(),
            "updated_at": get_vietnam_now_naive()
        }
        
        customer = await factory.customer_manager.create_customer(**customer_doc)
        return {"success": True, "data": customer}
        
    except Exception as e:
        logger.error(f"Error creating customer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customers", response_model=Dict[str, Any])
async def get_customers(
    customer_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy customers của user"""
    try:
        user_id = current_user.get("user_id", "unknown")
        customers = await factory.customer_manager.get_by_user_id(user_id)
        
        # Apply additional filters if needed
        if customer_id or social_id or social_page_id:
            filtered_customers = []
            for customer in customers:
                if customer_id and customer.get("customer_id") != customer_id:
                    continue
                if social_id and customer.get("social_id") != social_id:
                    continue
                if social_page_id and customer.get("social_page_id") != social_page_id:
                    continue
                filtered_customers.append(customer)
            customers = filtered_customers
        
        # Simple pagination
        total = len(customers)
        paginated_customers = customers[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_customers,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting customers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/customers/{customer_id}", response_model=Dict[str, Any])
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy thông tin customer theo _id hoặc customer_id
    
    API này có thể tìm customer theo 2 cách:
    - Theo _id (document ID): GET /api/v1/crm/customers/67321abc...
    - Theo customer_id (social platform ID): GET /api/v1/crm/customers/684930451376580
    
    Chỉ cần match 1 trong 2 trường là được
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        
        # Thử tìm theo _id trước
        customer = await factory.customer_manager.get_by_id(customer_id)
        
        # Nếu không tìm thấy, thử tìm theo customer_id (social platform ID)
        if not customer:
            customers = await factory.customer_manager.get_by_user_id(user_id)
            for c in customers:
                if c.get("customer_id") == customer_id:
                    customer = c
                    break
        
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Verify customer belongs to current user
        if customer.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": customer}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting customer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/customers/{customer_id}", response_model=Dict[str, Any])
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Cập nhật thông tin customer"""
    try:
        update_data = {k: v for k, v in customer_data.model_dump().items() if v is not None}
        update_data["updated_at"] = get_vietnam_now_naive()
        
        customer = await factory.customer_manager.update_customer(customer_id, update_data)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        return {"success": True, "data": customer}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/customers/{customer_id}", response_model=Dict[str, Any])
async def delete_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Xóa customer"""
    try:
        success = await factory.customer_manager.delete_customer(customer_id)
        if not success:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        return {"success": True, "message": "Customer deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting customer: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/customers/{customer_id}/auto-reply", response_model=Dict[str, Any])
async def toggle_auto_reply(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Toggle (bật/tắt) trạng thái auto_reply của customer
    
    **Cách dùng đơn giản:** Chỉ cần gọi API này, nó sẽ tự động toggle trạng thái
    - Nếu đang bật (True) → tắt (False)
    - Nếu đang tắt (False) → bật (True)
    
    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "customer_id": "...",
            "auto_reply": false,
            "name": "Nguyen Van A",
            "status": "Tương tác"
        },
        "message": "Đã tắt auto reply"
    }
    ```
    
    **Example:** 
    ```
    PATCH /api/v1/crm/customers/{customer_id}/auto-reply
    ```
    """
    try:
        customer = await factory.customer_manager.get_by_id(customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Toggle trạng thái
        current_auto_reply = customer.get("auto_reply", True)
        new_auto_reply = not current_auto_reply
        
        # Cập nhật
        update_data = {
            "auto_reply": new_auto_reply,
            "updated_at": get_vietnam_now_naive()
        }
        
        updated_customer = await factory.customer_manager.update_customer(customer_id, update_data)
        
        return {
            "success": True,
            "data": {
                "customer_id": str(customer_id),
                "auto_reply": new_auto_reply,
                "name": updated_customer.get("name", ""),
                "status": updated_customer.get("status", "Tương tác"),
                "tags": updated_customer.get("tags", [])
            },
            "message": "Đã bật auto reply" if new_auto_reply else "Đã tắt auto reply"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling auto_reply: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/customers/batch/auto-reply", response_model=Dict[str, Any])
async def batch_toggle_auto_reply(
    customer_ids: List[str],
    enable: Optional[bool] = None,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Toggle auto_reply cho nhiều customers cùng lúc
    
    **Request Body:**
    ```json
    {
        "customer_ids": ["id1", "id2", "id3"],
        "enable": true  // Optional: true=bật, false=tắt, null=toggle
    }
    ```
    
    **Tham số:**
    - customer_ids: List[str] - Danh sách customer IDs cần thay đổi
    - enable: bool (optional) - 
        + true: Bật auto_reply cho tất cả
        + false: Tắt auto_reply cho tất cả
        + null/không truyền: Toggle (đảo ngược) trạng thái của từng customer
    
    **Response:**
    ```json
    {
        "success": true,
        "data": {
            "updated_count": 3,
            "failed_count": 0,
            "results": [...]
        },
        "message": "Đã cập nhật 3 customers"
    }
    ```
    """
    try:
        results = []
        updated_count = 0
        failed_count = 0
        
        for customer_id in customer_ids:
            try:
                customer = await factory.customer_manager.get_by_id(customer_id)
                if not customer:
                    results.append({
                        "customer_id": customer_id,
                        "success": False,
                        "error": "Customer not found"
                    })
                    failed_count += 1
                    continue
                
                # Xác định trạng thái mới
                if enable is not None:
                    new_auto_reply = enable
                else:
                    # Toggle nếu không truyền enable
                    current_auto_reply = customer.get("auto_reply", True)
                    new_auto_reply = not current_auto_reply
                
                # Cập nhật
                update_data = {
                    "auto_reply": new_auto_reply,
                    "updated_at": get_vietnam_now_naive()
                }
                
                updated_customer = await factory.customer_manager.update_customer(customer_id, update_data)
                
                results.append({
                    "customer_id": customer_id,
                    "success": True,
                    "auto_reply": new_auto_reply,
                    "name": updated_customer.get("name", "")
                })
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error updating customer {customer_id}: {str(e)}")
                results.append({
                    "customer_id": customer_id,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        action = "bật" if enable == True else "tắt" if enable == False else "cập nhật"
        
        return {
            "success": True,
            "data": {
                "updated_count": updated_count,
                "failed_count": failed_count,
                "total": len(customer_ids),
                "results": results
            },
            "message": f"Đã {action} auto reply cho {updated_count}/{len(customer_ids)} customers"
        }
        
    except Exception as e:
        logger.error(f"Error batch toggling auto_reply: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Order Endpoints
@router.post("/orders", response_model=Dict[str, Any])
async def create_order(
    order_data: OrderCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo order (đơn hàng) mới
    
    **Required fields:**
    - social_page_id: str - ID trang social (bắt buộc)
    - customer_id: str - ID khách hàng (bắt buộc)
    - product_name: str - Tên sản phẩm (bắt buộc)
    - unit_price: float - Giá đơn vị (bắt buộc)
    - quantity: int - Số lượng (bắt buộc)
    - total_price: float - Tổng giá (bắt buộc)
    
    **Optional fields:**
    - social_id: str - ID nền tảng xã hội (mặc định: s_facebook)
    - customer_note: str - Ghi chú của khách hàng
    - customer_name: str - Tên người nhận
    - customer_phone: str - Số điện thoại người nhận
    - customer_address: str - Địa chỉ giao hàng
    - payment_method: str - Phương thức thanh toán (COD, Bank Transfer, E-wallet, ...)
    - payment_status: str - Trạng thái thanh toán (mặc định: pending)
        + pending: Chờ thanh toán
        + paid: Đã thanh toán
        + failed: Thanh toán thất bại
    - status: str - Trạng thái đơn hàng (mặc định: pending)
        + pending: Chờ xử lý
        + confirmed: Đã xác nhận
        + processing: Đang xử lý
        + shipping: Đang giao hàng
        + completed: Hoàn thành
        + cancelled: Đã hủy
    
    **Example Request:**
    ```json
    {
        "social_id": "s_facebook",
        "social_page_id": "123456789",
        "customer_id": "987654321",
        "product_name": "iPhone 15 Pro Max",
        "unit_price": 30000000,
        "quantity": 1,
        "total_price": 30000000,
        "customer_note": "Giao giờ hành chính",
        "customer_name": "Nguyen Van A",
        "customer_phone": "+84 912 345 678",
        "customer_address": "123 Le Loi, Da Nang",
        "payment_method": "COD",
        "payment_status": "pending",
        "status": "pending"
    }
    ```
    """
    try:
        user_id = current_user.get("user_id", "unknown")
        
        # Tạo mã order (có thể random hoặc theo format khác)
        order_code = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        
        # Tạo line_items từ thông tin sản phẩm
        line_items = [{
            "product_name": order_data.product_name,
            "quantity": order_data.quantity,
            "unit_price": order_data.unit_price,
            "total_price": order_data.unit_price * order_data.quantity
        }]
        
        # Gọi OrderManager.create_order với đúng signature
        order = await factory.order_manager.create_order(
            code=order_code,
            contact_id=order_data.customer_id,  # customer_id được map sang contact_id
            line_items=line_items,
            total_price=order_data.total_price,
            user_id=user_id,
            company_id=None,  # Có thể lấy từ current_user nếu cần
            shipping_address=order_data.customer_address,
            payment_method=order_data.payment_method,
            status=order_data.status
        )
        
        # Bổ sung thêm thông tin khác vào order document nếu cần
        if order:
            additional_data = {
                "social_id": order_data.social_id,
                "social_page_id": order_data.social_page_id,
                "customer_note": order_data.customer_note,
                "customer_name": order_data.customer_name,
                "customer_phone": order_data.customer_phone,
                "payment_status": order_data.payment_status
            }
            # Update order với các thông tin bổ sung
            await factory.order_manager.update_by_id(order["_id"], additional_data)
            order.update(additional_data)
        
        return {"success": True, "data": order}
        
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders", response_model=Dict[str, Any])
async def get_orders(
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy orders của user"""
    try:
        user_id = current_user.get("user_id", "unknown")
        orders = await factory.order_manager.get_by_user_id(user_id, status)
        
        # Apply additional filters if needed
        if customer_id or social_id or social_page_id:
            filtered_orders = []
            for order in orders:
                if customer_id and order.get("customer_id") != customer_id:
                    continue
                if social_id and order.get("social_id") != social_id:
                    continue
                if social_page_id and order.get("social_page_id") != social_page_id:
                    continue
                filtered_orders.append(order)
            orders = filtered_orders
        
        # Simple pagination
        total = len(orders)
        paginated_orders = orders[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_orders,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting orders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{order_id}", response_model=Dict[str, Any])
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy thông tin order"""
    try:
        order = await factory.order_manager.get_by_id(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"success": True, "data": order}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/orders/{order_id}", response_model=Dict[str, Any])
async def update_order(
    order_id: str,
    order_data: OrderUpdate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Cập nhật thông tin order"""
    try:
        update_data = {k: v for k, v in order_data.dict().items() if v is not None}
        update_data["updated_at"] = get_vietnam_now_naive()
        
        order = await factory.order_manager.update_order(order_id, update_data)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"success": True, "data": order}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/orders/{order_id}/status", response_model=Dict[str, Any])
async def update_order_status(
    order_id: str,
    status_data: StatusUpdate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Cập nhật trạng thái order"""
    try:
        order = await factory.order_manager.update_status(order_id, status_data.status)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"success": True, "data": order}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating order status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/orders/{order_id}", response_model=Dict[str, Any])
async def delete_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Xóa order"""
    try:
        success = await factory.order_manager.delete_order(order_id)
        if not success:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"success": True, "message": "Order deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting order: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))