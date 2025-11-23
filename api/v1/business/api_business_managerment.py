"""
Business Management API Endpoints
Cung cấp API cho companies, contacts, products, warehouses, orders, shipments
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging
import json
import base64
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
import uuid

from controllers.ultils.product_description_cleaner import cleaner

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.data.limit_service import get_limit_service
from controllers.auth.auth_middleware import get_current_user
from .convert_sql_to_mongo import (
    open_connection, fetch_products, fetch_meta, fetch_all_meta,
    fetch_taxonomy_terms, fetch_product_meta_lookup, fetch_media_posts,
    fetch_media_alt_text, fetch_default_currency, select_price, select_cost,
    resolve_currency, select_quantity, build_media_list, extract_attributes,
    coalesce_meta, Product, Pricing
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Business Management"])

# Pydantic Models
class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    description: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    logo_url: Optional[str] = ""
    social_links: Optional[Dict[str, str]] = {
        "facebook": "",
        "instagram": "",
        "twitter": "",
        "linkedin": "",
        "youtube": "",
        "tiktok": "",
        "github": ""
    }
    business_info: Optional[Dict[str, Any]] = {
        "tax_id": "",
        "business_license": "",
        "established_date": None,
        "employee_count": 0,
        "annual_revenue": 0
    }
    banking_info: Optional[Dict[str, str]] = {
        "bank_name": "",
        "account_number": "",
        "account_holder": "",
        "swift_code": ""
    }
    status: Optional[str] = "active"

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[Dict[str, str]] = None
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    business_info: Optional[Dict[str, Any]] = None
    banking_info: Optional[Dict[str, str]] = None
    status: Optional[str] = None

class ContactCreate(BaseModel):
    name: str
    type: str = "customer_info"  # customer_info, business_human_resource, etc.
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    company_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = {}

class ContactUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    company_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class ProductCreate(BaseModel):
    name: str
    sku: str
    pricing: Dict[str, Any]
    media: Optional[List[Dict[str, Any]]] = []
    company_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = {}

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    pricing: Optional[Dict[str, Any]] = None
    media: Optional[List[Dict[str, Any]]] = None
    data: Optional[Dict[str, Any]] = None

class ProductSearchByImage(BaseModel):
    query_image: str  # Base64 encoded image
    category: Optional[str] = None
    price_range: Optional[Dict[str, float]] = None
    limit: int = 20

class WarehouseCreate(BaseModel):
    name: str
    address: Optional[str] = None
    company_id: Optional[str] = None
    inventory: Optional[List[Dict[str, Any]]] = []

class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    company_id: Optional[str] = None

class InventoryUpdate(BaseModel):
    product_id: str
    quantity: int
    location_in_warehouse: Optional[str] = None

class OrderCreate(BaseModel):
    code: str
    contact_id: str
    line_items: List[Dict[str, Any]]  # [{product_id, quantity, price}, ...]
    total_price: float
    company_id: Optional[str] = None
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None
    status: str = "new"

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    shipping_address: Optional[str] = None
    payment_method: Optional[str] = None

class ShipmentCreate(BaseModel):
    code: str
    order_id: str
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    status: str = "preparing"
    company_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []

class ShipmentStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None

# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()

# Thread pool cho xử lý song song
executor = ThreadPoolExecutor(max_workers=10)

async def create_single_product_core(
    user_id: str,
    name: str,
    sku: str,
    pricing: Dict[str, Any],
    media: List[Dict[str, Any]],
    company_id: Optional[str],
    data: Dict[str, Any],
    factory
) -> Dict[str, Any]:
    """
    Core logic để tạo 1 product - được dùng chung bởi cả create_product và convert_sql_to_mongo
    """
    # Kiểm tra limit trước khi tạo product
    #limit_service = get_limit_service(factory)
    #limit_check = await limit_service.check_limit_before_create(user_id, "product")
    
    # if not limit_check.get("can_create", False):
    #     raise HTTPException(
    #         status_code=403, 
    #         detail=limit_check.get("message", "Cannot create more products due to package limits")
    #     )
    
    # Kiểm tra SKU đã tồn tại chưa
    existing = await factory.product_manager.get_by_sku(sku, user_id)
    if existing:
        raise HTTPException(status_code=400, detail=f"SKU {sku} already exists")
    
    # Xử lý company_id
    if company_id:
        # Kiểm tra company có tồn tại và thuộc về user không
        company = await factory.company_manager.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        if company.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Company access denied")
    else:
        # Lấy company mặc định của user
        default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
        if default_company:
            company_id = str(default_company["_id"])
    
    # Tạo product trong MongoDB
    product = await factory.product_manager.create_product(
        name=name,
        user_id=user_id,
        sku=sku,
        pricing=pricing,
        media=media,
        company_id=company_id,
        data=data
    )
    
    # TỰ ĐỘNG: Nếu có media type="image" → Generate embedding và lưu vào knowledge_chunks
    if media:
        image_medias = [m for m in media if m.get("type") == "image" and m.get("url")]
        if image_medias:
            try:
                # Get enhanced manager
                product_enhanced = factory.crm_factory.product_enhanced_manager
                product_enhanced.set_dependencies(
                    knowledge_chunk_manager=factory.knowledge_chunk_manager,
                    s3_manager=None  # URLs already exist, no S3 upload needed
                )
                
                # Process images để tạo embeddings
                await product_enhanced.process_product_images_from_urls(
                    product_id=str(product["_id"]),
                    user_id=user_id,
                    product_info=product,
                    image_urls=[(m.get("url"), m.get("alt_text", "")) for m in image_medias]
                )
                logger.info(f"Generated embeddings for {len(image_medias)} images of product {sku}")
            except Exception as e:
                logger.warning(f"Failed to generate image embeddings for {sku}: {str(e)}")
                # Không fail request, chỉ log warning
    
    return product

# Company Endpoints
@router.post("/companies", response_model=Dict[str, Any])
async def create_company(company_data: CompanyCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Tạo company mới
    
    **Required fields:**
    - name: str - Tên công ty (bắt buộc)
    
    **Optional fields:**
    - website: str - Website công ty
    - industry: str - Ngành nghề
    - address: Dict[str, str] - Địa chỉ công ty với các trường:
        + street: str - Địa chỉ đường
        + city: str - Thành phố
        + state: str - Tỉnh/thành
        + postal_code: str - Mã bưu điện
        + country: str - Quốc gia (mặc định: Vietnam)
    - description: str - Mô tả công ty
    - phone: str - Số điện thoại
    - email: str - Email liên hệ
    - logo_url: str - URL logo công ty
    - social_links: Dict[str, str] - Các liên kết mạng xã hội (facebook, instagram, twitter, linkedin, youtube, tiktok, github)
    - business_info: Dict[str, Any] - Thông tin kinh doanh:
        + tax_id: str - Mã số thuế
        + business_license: str - Giấy phép kinh doanh
        + established_date: datetime - Ngày thành lập
        + employee_count: int - Số lượng nhân viên
        + annual_revenue: float - Doanh thu hàng năm
    - banking_info: Dict[str, str] - Thông tin ngân hàng:
        + bank_name: str - Tên ngân hàng
        + account_number: str - Số tài khoản
        + account_holder: str - Chủ tài khoản
        + swift_code: str - Mã SWIFT
    - status: str - Trạng thái (mặc định: active)
    
    **Example Request:**
    ```json
    {
        "name": "MekongAI",
        "website": "https://mekongai.com",
        "industry": "Technology",
        "address": {
            "street": "38 Dương Thị Xuấn Quý",
            "city": "Da Nang",
            "state": "Da Nang",
            "postal_code": "550000",
            "country": "Vietnam"
        },
        "phone": "+84 236 123 4567",
        "email": "contact@mekongai.com"
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo company
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "company")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more companies due to package limits")
            )
        
        # Chuẩn bị data đầy đủ từ CompanyCreate model
        company_dict = company_data.model_dump()
        
        # Tạo data object với các thông tin bổ sung
        additional_data = {
            "description": company_dict.get("description", ""),
            "phone": company_dict.get("phone", ""),
            "email": company_dict.get("email", ""),
            "logo_url": company_dict.get("logo_url", ""),
            "social_links": company_dict.get("social_links", {
                "facebook": "",
                "instagram": "",
                "twitter": "",
                "linkedin": "",
                "youtube": "",
                "tiktok": "",
                "github": ""
            }),
            "business_info": company_dict.get("business_info", {
                "tax_id": "",
                "business_license": "",
                "established_date": None,
                "employee_count": 0,
                "annual_revenue": 0
            }),
            "banking_info": company_dict.get("banking_info", {
                "bank_name": "",
                "account_number": "",
                "account_holder": "",
                "swift_code": ""
            }),
            "status": company_dict.get("status", "active")
        }
        
        # Chuẩn hóa address - đảm bảo address luôn là object
        address = company_data.address
        if address is None:
            address = {
                "street": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "Vietnam"
            }
        elif isinstance(address, str):
            # Nếu address là string, chuyển thành object
            address = {
                "street": address,
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "Vietnam"
            }
        
        company = await factory.company_manager.create_company(
            name=company_data.name,
            user_id=user_id,
            website=company_data.website,
            industry=company_data.industry,
            address=address,
            data=additional_data
        )
        
        return {"success": True, "data": company}
        
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/companies", response_model=Dict[str, Any])
async def get_companies(current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Lấy danh sách companies của user hiện tại
    
    **Authentication:** Required (Bearer Token)
    
    **Response fields:**
    - _id: ObjectId - ID của company
    - name: str - Tên công ty
    - user_id: str - ID của user sở hữu
    - website: str - Website
    - industry: str - Ngành nghề
    - address: Dict hoặc str - Địa chỉ
    - description: str - Mô tả
    - phone: str - Số điện thoại
    - email: str - Email
    - logo_url: str - URL logo
    - social_links: Dict - Các mạng xã hội
    - business_info: Dict - Thông tin kinh doanh
    - banking_info: Dict - Thông tin ngân hàng
    - status: str - Trạng thái
    - is_default: bool - Company mặc định hay không
    - created_at/create_at: datetime - Ngày tạo
    - updated_at/update_at: datetime - Ngày cập nhật
    """
    try:
        user_id = current_user.get("user_id")
        companies = await factory.company_manager.get_by_user_id(user_id)
        return {"success": True, "data": companies}
        
    except Exception as e:
        logger.error(f"Error getting companies: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/companies/{company_id}", response_model=Dict[str, Any])
async def get_company(company_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Lấy thông tin company"""
    try:
        user_id = current_user.get("user_id")
        company = await factory.company_manager.get_by_id(company_id)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Kiểm tra quyền truy cập
        if company.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": company}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/companies/{company_id}", response_model=Dict[str, Any])
async def update_company(company_id: str, company_data: CompanyUpdate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Cập nhật company"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company tồn tại và quyền truy cập
        existing_company = await factory.company_manager.get_by_id(company_id)
        if not existing_company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if existing_company.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Chỉ update các field không None
        update_data = {k: v for k, v in company_data.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        company = await factory.company_manager.update_by_id(company_id, update_data)
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return {"success": True, "data": company}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/companies/{company_id}", response_model=Dict[str, Any])
async def delete_company(company_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Xóa company"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company tồn tại và quyền truy cập
        existing_company = await factory.company_manager.get_by_id(company_id)
        if not existing_company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        if existing_company.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await factory.company_manager.delete_by_id(company_id)
        if not success:
            raise HTTPException(status_code=404, detail="Company not found")
        
        return {"success": True, "message": "Company deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Contact Endpoints
@router.post("/contacts", response_model=Dict[str, Any])
async def create_contact(contact_data: ContactCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Tạo contact mới
    
    **Required fields:**
    - name: str - Tên contact (bắt buộc)
    
    **Optional fields:**
    - type: str - Loại contact (mặc định: customer_info)
        + customer_info: Thông tin khách hàng
        + business_human_resource: Nhân sự doanh nghiệp
    - email: EmailStr - Email liên hệ
    - phone_number: str - Số điện thoại
    - address: str - Địa chỉ
    - company_id: str - ID công ty liên kết
    - data: Dict[str, Any] - Dữ liệu bổ sung tùy chỉnh
    
    **Example Request:**
    ```json
    {
        "name": "Nguyen Van A",
        "type": "customer_info",
        "email": "nguyenvana@example.com",
        "phone_number": "+84 912 345 678",
        "address": "123 Le Loi, Da Nang",
        "company_id": "68dc8389dcd6982b375cb811"
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company_id nếu có
        if contact_data.company_id:
            company = await factory.company_manager.get_by_id(contact_data.company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        contact = await factory.contact_manager.create_contact(
            user_id=user_id,
            name=contact_data.name,
            contact_type=contact_data.type,
            email=contact_data.email,
            phone_number=contact_data.phone_number,
            address=contact_data.address,
            company_id=contact_data.company_id,
            data=contact_data.data
        )
        
        return {"success": True, "data": contact}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contacts", response_model=Dict[str, Any])
async def get_contacts(
    type: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy contacts của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company_id nếu có
        if company_id:
            company = await factory.company_manager.get_by_id(company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        contacts = await factory.contact_manager.get_by_user_id(user_id, type, company_id)
        
        # Simple pagination in memory (for better performance, implement in database)
        total = len(contacts)
        paginated_contacts = contacts[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_contacts,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contacts/search", response_model=Dict[str, Any])
async def search_contacts(q: str = Query(...), current_user: dict = Depends(get_current_user),
                        factory = Depends(get_management_factory)):
    """Tìm kiếm contacts của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        contacts = await factory.contact_manager.search_contacts(user_id, q)
        return {"success": True, "data": contacts}
        
    except Exception as e:
        logger.error(f"Error searching contacts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/contacts/{contact_id}", response_model=Dict[str, Any])
async def get_contact(contact_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Lấy thông tin contact"""
    try:
        user_id = current_user.get("user_id")
        contact = await factory.contact_manager.get_by_id(contact_id)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        # Kiểm tra quyền truy cập
        if contact.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": contact}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/contacts/{contact_id}", response_model=Dict[str, Any])
async def update_contact(contact_id: str, contact_data: ContactUpdate, current_user: dict = Depends(get_current_user),
                       factory = Depends(get_management_factory)):
    """Cập nhật contact"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra contact tồn tại và quyền truy cập
        existing_contact = await factory.contact_manager.get_by_id(contact_id)
        if not existing_contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        if existing_contact.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Chỉ update các field không None
        update_data = {k: v for k, v in contact_data.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        # Kiểm tra company_id nếu có trong update
        if 'company_id' in update_data and update_data['company_id']:
            company = await factory.company_manager.get_by_id(update_data['company_id'])
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        contact = await factory.contact_manager.update_by_id(contact_id, update_data)
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return {"success": True, "data": contact}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contacts/{contact_id}/copy", response_model=Dict[str, Any])
async def copy_contact(contact_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Copy contact"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra contact tồn tại và quyền truy cập
        existing_contact = await factory.contact_manager.get_by_id(contact_id)
        if not existing_contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        if existing_contact.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        copy_suffix = str(uuid.uuid4())[:8]
        
        copied_contact = await factory.contact_manager.copy_by_id(contact_id, {
            "name": f"Copy of {existing_contact.get('name', 'Contact')} {copy_suffix}",
            "email": f"copy_{copy_suffix}@example.com" if not existing_contact.get('email') else None
        })
        
        if not copied_contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return {"success": True, "data": copied_contact}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Product Endpoints
@router.post("/products", response_model=Dict[str, Any])
async def create_product(product_data: ProductCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Tạo product mới
    
    **Required fields:**
    - name: str - Tên sản phẩm (bắt buộc)
    - sku: str - Mã SKU duy nhất (bắt buộc)
    - pricing: Dict[str, Any] - Thông tin giá (bắt buộc)
        + cost: float - Giá vốn
        + price: float - Giá bán
        + currency: str - Đơn vị tiền tệ (VND, USD, ...)
    
    **Optional fields:**
    - media: List[Dict[str, Any]] - Danh sách media (ảnh, video)
        + type: str - Loại media (image, video)
        + url: str - URL của media
        + alt_text: str - Mô tả thay thế
    - company_id: str - ID công ty
    - data: Dict[str, Any] - Dữ liệu bổ sung:
        + description: str - Mô tả sản phẩm
        + category: str - Danh mục
        + weight: float - Trọng lượng
        + dimensions: Dict - Kích thước (length, width, height)
        + color: str - Màu sắc
        + size: str - Kích cỡ
        + tags: List[str] - Thẻ
        + attributes: Dict[str, Any] - Thuộc tính tùy chỉnh
    
    **Example Request:**
    ```json
    {
        "name": "iPhone 15 Pro Max",
        "sku": "IP15PM-256-BLK",
        "pricing": {
            "cost": 25000000,
            "price": 30000000,
            "currency": "VND"
        },
        "media": [
            {
                "type": "image",
                "url": "https://example.com/iphone15.jpg",
                "alt_text": "iPhone 15 Pro Max Black"
            }
        ],
        "data": {
            "description": "Latest iPhone model",
            "category": "Smartphones",
            "color": "Black Titanium"
        }
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo product
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "product")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more products due to package limits")
            )
        
        # Kiểm tra SKU đã tồn tại chưa
        existing = await factory.product_manager.get_by_sku(product_data.sku, user_id)
        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")
        
        # Xử lý company_id
        company_id = product_data.company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        else:
            # Lấy company mặc định của user
            default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
            if default_company:
                company_id = str(default_company["_id"])
        
        # Sử dụng core function chung
        product = await create_single_product_core(
            user_id=user_id,
            name=product_data.name,
            sku=product_data.sku,
            pricing=product_data.pricing,
            media=product_data.media,
            company_id=company_id,
            data=product_data.data,
            factory=factory
        )
        
        return {"success": True, "data": product}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_single_sql_product(
    product: Dict[str, Any],
    meta_lookup: Dict,
    taxonomy_lookup: Dict,
    product_meta_lookup: Dict,
    media_lookup: Dict,
    alt_lookup: Dict,
    default_currency: str,
    user_id: str,
    company_id: Optional[str],
    factory
) -> Dict[str, Any]:
    """
    Xử lý 1 product từ SQL - chạy song song
    """
    try:
        product_id = product["ID"]
        meta = meta_lookup.get(product_id, {})
        taxonomies = taxonomy_lookup.get(product_id, {})
        
        raw_sku = meta.get("_sku")
        sku = raw_sku.strip() if raw_sku else str(product_id)
        
        # Parse product data từ SQL
        product_lookup_row = product_meta_lookup.get(product_id)
        pricing = Pricing(
            price=select_price(meta),
            currency=resolve_currency(meta, default_currency),
            cost=select_cost(meta),
        )
        quantity = select_quantity(meta, product_lookup_row)
        media_entries = build_media_list(meta, media_lookup, alt_lookup)
        
        categories = [term["name"] for term in taxonomies.get("product_cat", [])]
        tags = [term["name"] for term in taxonomies.get("product_tag", [])]
        colors = [term["name"] for term in taxonomies.get("pa_color", [])]
        sizes = [term["name"] for term in taxonomies.get("pa_size", [])]
        
        dimensions = {
            "length": meta.get("_length"),
            "width": meta.get("_width"),
            "height": meta.get("_height"),
        }
        dimensions = {k: v for k, v in dimensions.items() if v is not None}
        
        # Build data payload
        data_payload: Dict[str, Any] = {}
        if product.get("post_content"):
            data_payload["description"] = cleaner.clean_description(product["post_content"].strip())
        if categories:
            data_payload["category"] = categories
        if meta.get("_weight") is not None:
            data_payload["weight"] = meta.get("_weight")
        if dimensions:
            data_payload["dimensions"] = dimensions
        if colors:
            data_payload["color"] = ", ".join(colors)
        if sizes:
            data_payload["size"] = ", ".join(sizes)
        if tags:
            data_payload["tags"] = tags
        
        attributes = extract_attributes(meta, taxonomies)
        if attributes:
            data_payload["attributes"] = attributes
        
        if quantity is not None:
            data_payload["quantity"] = quantity
        
        # Prepare pricing dict
        pricing_dict = {
            "price": pricing.price,
            "currency": pricing.currency,
            "cost": pricing.cost
        }
        
        # Prepare media list
        media_list = [
            {
                "type": m.type,
                "url": m.url,
                "alt_text": m.alt_text
            } for m in media_entries
        ]
        
        # Sử dụng core function chung để tạo product
        created_product = await create_single_product_core(
            user_id=user_id,
            name=product["post_title"],
            sku=sku,
            pricing=pricing_dict,
            media=media_list,
            company_id=company_id,
            data=data_payload,
            factory=factory
        )
        
        return {
            "status": "success",
            "product_id": product_id,
            "sku": sku,
            "created_id": str(created_product["_id"])
        }
        
    except HTTPException as e:
        if "already exists" in str(e.detail):
            return {
                "status": "skipped",
                "product_id": product_id,
                "sku": sku,
                "reason": str(e.detail)
            }
        else:
            return {
                "status": "failed",
                "product_id": product_id,
                "sku": sku,
                "error": str(e.detail)
            }
    except Exception as e:
        return {
            "status": "failed",
            "product_id": product_id,
            "sku": sku if 'sku' in locals() else str(product_id),
            "error": str(e)
        }

@router.post("/convert-sql-to-mongo", response_model=Dict[str, Any])
async def convert_sql_to_mongo(
    company_id: Optional[str] = None,
    batch_size: int = Query(50, ge=1, le=100, description="Số lượng products xử lý đồng thời"),
    current_user: dict = Depends(get_current_user), 
    factory = Depends(get_management_factory)
):
    """
    Convert products từ MySQL (WooCommerce) sang MongoDB với xử lý song song
    
    **Parameters:**
    - company_id: ID của company (optional, sẽ dùng default nếu không có)  
    - batch_size: Số lượng products xử lý song song (1-100, default: 50)
    
    **Features:**
    - ✅ Xử lý song song nhiều products cùng lúc
    - ✅ Skip products đã tồn tại (theo SKU)
    - ✅ Tự động generate image embeddings
    - ✅ Detailed progress tracking
    """
    try:
        user_id = current_user.get("user_id")
        # Tạo args object với config từ convert_sql_to_mongo.py
        class Args:
            host = "144.91.113.233"
            port = 3306
            user = "mekongai"
            password = "12345678"
            database = "test_kat"
            table_prefix = "wg_"
            status = ["publish", "draft", "pending", "private"]
        
        args = Args()
        
        # Kết nối MySQL và fetch data
        conn = open_connection(args)
        
        try:
            prefix = args.table_prefix
            statuses = args.status
            
            logger.info(f"🚀 Starting SQL to MongoDB conversion with batch_size={batch_size}")
            
            # Fetch products from SQL
            products = fetch_products(conn, prefix, statuses, limit=None)
            
            if not products:
                return {
                    "success": True,
                    "message": "No products found for the specified criteria",
                    "converted_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0
                }
            
            total_products = len(products)
            logger.info(f"📦 Found {total_products} products to process")
            
            product_ids = [row["ID"] for row in products]
            
            # Fetch metadata (1 lần cho tất cả products)
            logger.info("📊 Fetching metadata from MySQL...")
            meta_keys = [
                "_sku", "_price", "_regular_price", "_sale_price",
                "_wc_cog_cost", "_alg_wc_cog_cost", "_cost", "_purchase_price",
                "_currency", "_thumbnail_id", "_product_image_gallery",
                "_weight", "_length", "_width", "_height",
                "_product_attributes", "_stock", "_manage_stock", "_stock_status",
                "company_id",
            ]
            
            meta_lookup = fetch_meta(conn, prefix, product_ids, meta_keys)
            full_meta_lookup = fetch_all_meta(conn, prefix, product_ids)
            taxonomy_lookup = fetch_taxonomy_terms(conn, prefix, product_ids)
            product_meta_lookup = fetch_product_meta_lookup(conn, prefix, product_ids)
            
            # Fetch media
            media_ids = set()
            for meta in meta_lookup.values():
                thumb = meta.get("_thumbnail_id")
                if thumb and thumb.isdigit():
                    media_ids.add(int(thumb))
                gallery = meta.get("_product_image_gallery")
                if gallery:
                    media_ids.update(int(mid) for mid in gallery.split(",") if mid.strip().isdigit())
            
            media_lookup = fetch_media_posts(conn, prefix, list(media_ids))
            alt_lookup = fetch_media_alt_text(conn, prefix, list(media_ids))
            default_currency = fetch_default_currency(conn, prefix)
            
            logger.info("🔄 Starting parallel processing...")
            
            # Xử lý song song theo batch
            results = []
            for i in range(0, total_products, batch_size):
                batch = products[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_products + batch_size - 1) // batch_size
                
                logger.info(f"⚡ Processing batch {batch_num}/{total_batches} ({len(batch)} products)")
                
                # Tạo tasks cho batch hiện tại
                tasks = []
                for product in batch:
                    task = process_single_sql_product(
                        product=product,
                        meta_lookup=meta_lookup,
                        taxonomy_lookup=taxonomy_lookup,
                        product_meta_lookup=product_meta_lookup,
                        media_lookup=media_lookup,
                        alt_lookup=alt_lookup,
                        default_currency=default_currency,
                        user_id=user_id,
                        company_id=company_id,
                        factory=factory
                    )
                    tasks.append(task)
                
                # Chạy song song batch hiện tại
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Xử lý kết quả của batch
                for result in batch_results:
                    if isinstance(result, Exception):
                        results.append({
                            "status": "failed",
                            "product_id": "unknown",
                            "error": str(result)
                        })
                    else:
                        results.append(result)
                
                logger.info(f"✅ Batch {batch_num} completed")
        
        finally:
            conn.close()
        
        # Tổng hợp kết quả
        converted_count = len([r for r in results if r.get("status") == "success"])
        skipped_count = len([r for r in results if r.get("status") == "skipped"])  
        failed_count = len([r for r in results if r.get("status") == "failed"])
        
        errors = [
            {
                "product_id": r.get("product_id"),
                "sku": r.get("sku", "unknown"),
                "error": r.get("error") or r.get("reason")
            }
            for r in results 
            if r.get("status") in ["failed", "skipped"] and (r.get("error") or r.get("reason"))
        ]
        
        logger.info(f"🎉 Conversion completed: {converted_count} converted, {skipped_count} skipped, {failed_count} failed")
        
        return {
            "success": True,
            "message": f"Parallel conversion completed: {converted_count} converted, {skipped_count} skipped, {failed_count} failed",
            "converted_count": converted_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "total_processed": len(results),
            "batch_size": batch_size,
            "errors": errors[:50] if errors else []  # Giới hạn 50 errors đầu tiên
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in SQL to MongoDB conversion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products", response_model=Dict[str, Any])
async def get_products(
    company_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy products của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        
        # Xử lý company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        else:
            # Lấy company mặc định của user
            default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
            if default_company:
                company_id = str(default_company["_id"])
        
        products = await factory.product_manager.get_by_user_id(user_id, company_id)
        
        # Simple pagination
        total = len(products)
        paginated_products = products[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_products,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products/search", response_model=Dict[str, Any])
async def search_products(q: str = Query(...), current_user: dict = Depends(get_current_user),
                        factory = Depends(get_management_factory)):
    """Tìm kiếm products của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        products = await factory.product_manager.search_products(user_id, q)
        return {"success": True, "data": products}
        
    except Exception as e:
        logger.error(f"Error searching products: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/products/{product_id}", response_model=Dict[str, Any])
async def get_product(product_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Lấy thông tin product"""
    try:
        user_id = current_user.get("user_id")
        product = await factory.product_manager.get_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Kiểm tra quyền truy cập
        if product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": product}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/products/{product_id}", response_model=Dict[str, Any])
async def update_product(product_id: str, product_data: ProductUpdate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Cập nhật product"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra product tồn tại và quyền truy cập
        existing_product = await factory.product_manager.get_by_id(product_id)
        if not existing_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        if existing_product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Chỉ update các field không None
        update_data = {k: v for k, v in product_data.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        # Kiểm tra SKU mới nếu có
        if 'sku' in update_data and update_data['sku'] != existing_product.get('sku'):
            existing_sku = await factory.product_manager.get_by_sku(update_data['sku'], user_id)
            if existing_sku:
                raise HTTPException(status_code=400, detail="SKU already exists")
        
        product = await factory.product_manager.update_by_id(product_id, update_data)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"success": True, "data": product}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/products/{product_id}", response_model=Dict[str, Any])
async def delete_product(product_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Xóa product"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra product tồn tại và quyền truy cập
        existing_product = await factory.product_manager.get_by_id(product_id)
        if not existing_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        if existing_product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await factory.product_manager.delete_by_id(product_id)
        if not success:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"success": True, "message": "Product deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting product: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/products/{product_id}/pricing", response_model=Dict[str, Any])
async def update_product_pricing(product_id: str, pricing: Dict[str, Any], current_user: dict = Depends(get_current_user),
                               factory = Depends(get_management_factory)):
    """Cập nhật pricing của product"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra product tồn tại và quyền truy cập
        existing_product = await factory.product_manager.get_by_id(product_id)
        if not existing_product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        if existing_product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        product = await factory.product_manager.update_pricing(product_id, pricing)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"success": True, "data": product}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating product pricing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/inventory", response_model=Dict[str, Any])
async def get_product_inventory(product_id: str, current_user: dict = Depends(get_current_user),
                              factory = Depends(get_management_factory)):
    """Lấy inventory của product từ tất cả warehouses"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra product có thuộc về user này không
        product = await factory.product_manager.get_by_id(product_id)
        if not product or product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Invalid product_id")
        
        inventory = await factory.warehouse_manager.get_product_inventory(product_id, user_id)
        return {"success": True, "data": inventory}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product inventory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Warehouse Endpoints
@router.post("/warehouses", response_model=Dict[str, Any])
async def create_warehouse(warehouse_data: WarehouseCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Tạo warehouse (kho) mới
    
    **Required fields:**
    - name: str - Tên kho (bắt buộc)
    
    **Optional fields:**
    - address: str - Địa chỉ kho
    - company_id: str - ID công ty
    - inventory: List[Dict[str, Any]] - Danh sách hàng tồn kho:
        + product_id: str - ID sản phẩm
        + quantity: int - Số lượng
        + location_in_warehouse: str - Vị trí trong kho
    
    **Example Request:**
    ```json
    {
        "name": "Kho Trung tâm Đà Nẵng",
        "address": "456 Tran Phu, Da Nang",
        "company_id": "68dc8389dcd6982b375cb811",
        "inventory": [
            {
                "product_id": "prod_123",
                "quantity": 100,
                "location_in_warehouse": "A1-01"
            }
        ]
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo warehouse
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "warehouse")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more warehouses due to package limits")
            )
        
        # Kiểm tra company_id nếu có
        if warehouse_data.company_id:
            company = await factory.company_manager.get_by_id(warehouse_data.company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        warehouse = await factory.warehouse_manager.create_warehouse(
            name=warehouse_data.name,
            user_id=user_id,
            address=warehouse_data.address,
            company_id=warehouse_data.company_id,
            inventory=warehouse_data.inventory
        )
        
        return {"success": True, "data": warehouse}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating warehouse: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/warehouses", response_model=Dict[str, Any])
async def get_warehouses(company_id: Optional[str] = Query(None), current_user: dict = Depends(get_current_user),
                       factory = Depends(get_management_factory)):
    """Lấy warehouses (kho) của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company_id nếu có
        if company_id:
            company = await factory.company_manager.get_by_id(company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        warehouses = await factory.warehouse_manager.get_by_user_id(user_id, company_id)
        return {"success": True, "data": warehouses}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting warehouses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/warehouses/{warehouse_id}", response_model=Dict[str, Any])
async def get_warehouse(warehouse_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Lấy thông tin warehouse"""
    try:
        user_id = current_user.get("user_id")
        warehouse = await factory.warehouse_manager.get_by_id(warehouse_id)
        if not warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        # Kiểm tra quyền truy cập
        if warehouse.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {"success": True, "data": warehouse}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting warehouse: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/warehouses/{warehouse_id}", response_model=Dict[str, Any])
async def update_warehouse(warehouse_id: str, warehouse_data: WarehouseUpdate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Cập nhật warehouse"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra warehouse tồn tại và quyền truy cập
        existing_warehouse = await factory.warehouse_manager.get_by_id(warehouse_id)
        if not existing_warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        if existing_warehouse.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Chỉ update các field không None
        update_data = {k: v for k, v in warehouse_data.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        # Kiểm tra company_id nếu có trong update
        if 'company_id' in update_data and update_data['company_id']:
            company = await factory.company_manager.get_by_id(update_data['company_id'])
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        warehouse = await factory.warehouse_manager.update_by_id(warehouse_id, update_data)
        if not warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        return {"success": True, "data": warehouse}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating warehouse: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/warehouses/{warehouse_id}", response_model=Dict[str, Any])
async def delete_warehouse(warehouse_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Xóa warehouse"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra warehouse tồn tại và quyền truy cập
        existing_warehouse = await factory.warehouse_manager.get_by_id(warehouse_id)
        if not existing_warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        if existing_warehouse.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await factory.warehouse_manager.delete_by_id(warehouse_id)
        if not success:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        return {"success": True, "message": "Warehouse deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting warehouse: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/warehouses/{warehouse_id}/inventory", response_model=Dict[str, Any])
async def update_warehouse_inventory(warehouse_id: str, inventory_data: InventoryUpdate, current_user: dict = Depends(get_current_user),
                                   factory = Depends(get_management_factory)):
    """Cập nhật inventory trong warehouse"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra warehouse tồn tại và quyền truy cập
        existing_warehouse = await factory.warehouse_manager.get_by_id(warehouse_id)
        if not existing_warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        if existing_warehouse.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Kiểm tra product có thuộc về user này không
        product = await factory.product_manager.get_by_id(inventory_data.product_id)
        if not product or product.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Invalid product_id")
        
        warehouse = await factory.warehouse_manager.update_inventory(
            warehouse_id,
            inventory_data.product_id,
            inventory_data.quantity,
            inventory_data.location_in_warehouse
        )
        
        if not warehouse:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        
        return {"success": True, "data": warehouse}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating warehouse inventory: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# # Order Endpoints
# @router.post("/orders", response_model=Dict[str, Any])
# async def create_order(order_data: OrderCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
#     """
#     Tạo order (đơn hàng) mới
    
#     **Required fields:**
#     - code: str - Mã đơn hàng (bắt buộc)
#     - contact_id: str - ID khách hàng (bắt buộc)
#     - line_items: List[Dict[str, Any]] - Danh sách sản phẩm (bắt buộc)
#         + product_id: str - ID sản phẩm
#         + quantity: int - Số lượng
#         + price: float - Giá bán
#     - total_price: float - Tổng giá trị đơn hàng (bắt buộc)
    
#     **Optional fields:**
#     - company_id: str - ID công ty
#     - shipping_address: str - Địa chỉ giao hàng
#     - payment_method: str - Phương thức thanh toán
#     - status: str - Trạng thái (mặc định: new)
    
#     **Example Request:**
#     ```json
#     {
#         "code": "ORD-20251001-001",
#         "contact_id": "contact_123",
#         "line_items": [
#             {
#                 "product_id": "prod_123",
#                 "quantity": 2,
#                 "price": 500000
#             }
#         ],
#         "total_price": 1000000,
#         "shipping_address": "123 Le Loi, Da Nang",
#         "payment_method": "cash"
#     }
#     ```
#     """
#     try:
#         user_id = current_user.get("user_id")
        
#         # Kiểm tra contact có thuộc về user này không
#         contact = await factory.contact_manager.get_by_id(order_data.contact_id)
#         if not contact or contact.get("user_id") != user_id:
#             raise HTTPException(status_code=403, detail="Invalid contact_id")
        
#         # Kiểm tra company_id nếu có
#         if order_data.company_id:
#             company = await factory.company_manager.get_by_id(order_data.company_id)
#             if not company or company.get("user_id") != user_id:
#                 raise HTTPException(status_code=403, detail="Invalid company_id")
        
#         # Kiểm tra tất cả products trong line_items
#         for item in order_data.line_items:
#             if 'product_id' in item:
#                 product = await factory.product_manager.get_by_id(item['product_id'])
#                 if not product or product.get("user_id") != user_id:
#                     raise HTTPException(status_code=403, detail=f"Invalid product_id: {item['product_id']}")
        
#         order = await factory.order_manager.create_order(
#             code=order_data.code,
#             contact_id=order_data.contact_id,
#             line_items=order_data.line_items,
#             total_price=order_data.total_price,
#             user_id=user_id,
#             company_id=order_data.company_id,
#             shipping_address=order_data.shipping_address,
#             payment_method=order_data.payment_method,
#             status=order_data.status
#         )
        
#         return {"success": True, "data": order}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error creating order: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/orders", response_model=Dict[str, Any])
# async def get_orders(
#     status: Optional[str] = Query(None),
#     company_id: Optional[str] = Query(None),
#     contact_id: Optional[str] = Query(None),
#     skip: int = Query(0, ge=0),
#     limit: int = Query(50, ge=1, le=100),
#     current_user: dict = Depends(get_current_user),
#     factory = Depends(get_management_factory)
# ):
#     """Lấy orders của user hiện tại"""
#     try:
#         user_id = current_user.get("user_id")
        
#         # Kiểm tra company_id nếu có
#         if company_id:
#             company = await factory.company_manager.get_by_id(company_id)
#             if not company or company.get("user_id") != user_id:
#                 raise HTTPException(status_code=403, detail="Invalid company_id")
        
#         # Kiểm tra contact_id nếu có
#         if contact_id:
#             contact = await factory.contact_manager.get_by_id(contact_id)
#             if not contact or contact.get("user_id") != user_id:
#                 raise HTTPException(status_code=403, detail="Invalid contact_id")
        
#         orders = await factory.order_manager.get_by_user_id(user_id, status, company_id, contact_id)
        
#         # Simple pagination
#         total = len(orders)
#         paginated_orders = orders[skip:skip+limit]
        
#         return {
#             "success": True,
#             "data": paginated_orders,
#             "pagination": {
#                 "skip": skip,
#                 "limit": limit,
#                 "total": total
#             }
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting orders: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.get("/orders/{order_id}", response_model=Dict[str, Any])
# async def get_order(order_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
#     """Lấy thông tin order"""
#     try:
#         user_id = current_user.get("user_id")
#         order = await factory.order_manager.get_by_id(order_id)
#         if not order:
#             raise HTTPException(status_code=404, detail="Order not found")
        
#         # Kiểm tra quyền truy cập
#         if order.get("user_id") != user_id:
#             raise HTTPException(status_code=403, detail="Access denied")
        
#         return {"success": True, "data": order}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error getting order: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.put("/orders/{order_id}", response_model=Dict[str, Any])
# async def update_order(order_id: str, order_data: OrderUpdate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
#     """Cập nhật order"""
#     try:
#         user_id = current_user.get("user_id")
        
#         # Kiểm tra order tồn tại và quyền truy cập
#         existing_order = await factory.order_manager.get_by_id(order_id)
#         if not existing_order:
#             raise HTTPException(status_code=404, detail="Order not found")
        
#         if existing_order.get("user_id") != user_id:
#             raise HTTPException(status_code=403, detail="Access denied")
        
#         # Chỉ update các field không None
#         update_data = {k: v for k, v in order_data.model_dump().items() if v is not None}
        
#         if not update_data:
#             raise HTTPException(status_code=400, detail="No data to update")
        
#         order = await factory.order_manager.update_by_id(order_id, update_data)
#         if not order:
#             raise HTTPException(status_code=404, detail="Order not found")
        
#         return {"success": True, "data": order}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating order: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.delete("/orders/{order_id}", response_model=Dict[str, Any])
# async def delete_order(order_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
#     """Xóa order"""
#     try:
#         user_id = current_user.get("user_id")
        
#         # Kiểm tra order tồn tại và quyền truy cập
#         existing_order = await factory.order_manager.get_by_id(order_id)
#         if not existing_order:
#             raise HTTPException(status_code=404, detail="Order not found")
        
#         if existing_order.get("user_id") != user_id:
#             raise HTTPException(status_code=403, detail="Access denied")
        
#         success = await factory.order_manager.delete_by_id(order_id)
#         if not success:
#             raise HTTPException(status_code=404, detail="Order not found")
        
#         return {"success": True, "message": "Order deleted successfully"}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting order: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# Shipment Endpoints
@router.post("/shipments", response_model=Dict[str, Any])
async def create_shipment(shipment_data: ShipmentCreate, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """
    Tạo shipment (đơn vận chuyển) mới
    
    **Required fields:**
    - code: str - Mã shipment (bắt buộc)
    - order_id: str - ID đơn hàng (bắt buộc)
    
    **Optional fields:**
    - carrier: str - Đơn vị vận chuyển (VNPost, Giao Hang Nhanh, J&T, ...)
    - tracking_number: str - Mã tracking
    - status: str - Trạng thái (mặc định: preparing)
        + preparing: Đang chuẩn bị
        + in_transit: Đang vận chuyển
        + delivered: Đã giao
        + returned: Đã trả lại
        + cancelled: Đã hủy
    - company_id: str - ID công ty
    - history: List[Dict[str, Any]] - Lịch sử vận chuyển:
        + status: str - Trạng thái
        + note: str - Ghi chú
        + timestamp: datetime - Thời gian
        + location: str - Địa điểm
    
    **Example Request:**
    ```json
    {
        "code": "SHIP-20251001-001",
        "order_id": "order_123",
        "carrier": "Giao Hang Nhanh",
        "tracking_number": "GHN123456789",
        "status": "preparing",
        "history": [
            {
                "status": "preparing",
                "note": "Đơn hàng đang được đóng gói",
                "timestamp": "2025-10-01T10:00:00Z",
                "location": "Da Nang"
            }
        ]
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra order có thuộc về user này không
        order = await factory.order_manager.get_by_id(shipment_data.order_id)
        if not order or order.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Invalid order_id")
        
        # Kiểm tra company_id nếu có
        if shipment_data.company_id:
            company = await factory.company_manager.get_by_id(shipment_data.company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        shipment = await factory.shipment_manager.create_shipment(
            code=shipment_data.code,
            order_id=shipment_data.order_id,
            user_id=user_id,
            carrier=shipment_data.carrier,
            tracking_number=shipment_data.tracking_number,
            status=shipment_data.status,
            company_id=shipment_data.company_id,
            history=shipment_data.history
        )
        
        return {"success": True, "data": shipment}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating shipment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipments", response_model=Dict[str, Any])
async def get_shipments(
    status: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy shipments của user hiện tại"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra company_id nếu có
        if company_id:
            company = await factory.company_manager.get_by_id(company_id)
            if not company or company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Invalid company_id")
        
        shipments = await factory.shipment_manager.get_by_user_id(user_id, status, company_id)
        return {"success": True, "data": shipments}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shipments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders/{order_id}/shipments", response_model=Dict[str, Any])
async def get_order_shipments(order_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Lấy shipments của order"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra order có thuộc về user này không
        order = await factory.order_manager.get_by_id(order_id)
        if not order or order.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Invalid order_id")
        
        shipments = await factory.shipment_manager.get_by_order_id(order_id)
        return {"success": True, "data": shipments}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order shipments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipments/tracking/{tracking_number}", response_model=Dict[str, Any])
async def track_shipment(tracking_number: str, factory = Depends(get_management_factory)):
    """Track shipment theo tracking number"""
    try:
        shipment = await factory.shipment_manager.get_by_tracking_number(tracking_number)
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        return {"success": True, "data": shipment}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking shipment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/shipments/{shipment_id}/status", response_model=Dict[str, Any])
async def update_shipment_status(shipment_id: str, status_data: ShipmentStatusUpdate, current_user: dict = Depends(get_current_user),
                               factory = Depends(get_management_factory)):
    """Cập nhật trạng thái shipment"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra shipment tồn tại và quyền truy cập
        existing_shipment = await factory.shipment_manager.get_by_id(shipment_id)
        if not existing_shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        if existing_shipment.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        shipment = await factory.shipment_manager.update_status(
            shipment_id, 
            status_data.status,
            status_data.note
        )
        
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        return {"success": True, "data": shipment}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shipment status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Bulk Operations
@router.delete("/contacts/{contact_id}", response_model=Dict[str, Any])
async def delete_contact(contact_id: str, current_user: dict = Depends(get_current_user), factory = Depends(get_management_factory)):
    """Xóa contact"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra contact tồn tại và quyền truy cập
        existing_contact = await factory.contact_manager.get_by_id(contact_id)
        if not existing_contact:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        if existing_contact.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await factory.contact_manager.delete_by_id(contact_id)
        if not success:
            raise HTTPException(status_code=404, detail="Contact not found")
        
        return {"success": True, "message": "Contact deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== IMAGE SEARCH FOR PRODUCTS ====================

@router.post("/products/search/by-image", response_model=Dict[str, Any])
async def search_products_by_image(
    search_data: ProductSearchByImage,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tìm kiếm products bằng ảnh (Image Similarity Search)
    Sử dụng embeddings đã được tự động generate khi tạo product
    
    **Example:**
    ```json
    {
        "query_image": "<base64_image>",
        "category": "Smartphones",
        "limit": 10
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        
        # Decode image
        try:
            image_bytes = base64.b64decode(search_data.query_image)
        except:
            raise HTTPException(status_code=400, detail="Invalid base64 image")
        
        # Search using enhanced manager
        product_enhanced = factory.crm_factory.product_enhanced_manager
        product_enhanced.set_dependencies(
            knowledge_chunk_manager=factory.knowledge_chunk_manager,
            s3_manager=None
        )
        
        results = await product_enhanced.search_products_by_image(
            query_image_data=image_bytes,
            user_id=user_id,
            category=search_data.category,
            price_range=search_data.price_range,
            limit=search_data.limit
        )
        
        return {"success": True, "data": results, "total": len(results)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching products by image: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        return {"success": True, "message": "Contact deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

