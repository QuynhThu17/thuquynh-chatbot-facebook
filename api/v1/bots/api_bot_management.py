"""
Bot Management API Endpoints
Cung cấp API cho identities, procedures, bots
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import logging
import json
import requests

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.data.limit_service import get_limit_service
from controllers.auth.auth_middleware import get_current_user

from bot.bot_facebook_messenger import process_facebook_message

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Bot Management"])

# Helper function for Facebook subscribed apps
def subscribed_apps(page_id, page_access_token, type="on"):
    """Cập nhật subscribed fields cho Facebook page"""
    url = f"https://graph.facebook.com/{page_id}/subscribed_apps"
    
    if type == "on":
        subscribed_fields = "messages,messaging_postbacks"
    else:
        subscribed_fields = ""

    payload = {
        "subscribed_fields": subscribed_fields,
        "access_token": page_access_token,
    }

    try:
        response = requests.post(url, data=payload, timeout=120)

        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json()
    except Exception as e:
        return False, str(e)

# Pydantic Models
class ConversationExample(BaseModel):
    """
    Model cho một cặp hội thoại user-bot
    """
    user: str = Field(..., description="Tin nhắn từ phía người dùng", json_schema_extra={"example": "Xin chào, bạn có thể giúp tôi không?"})
    you: str = Field(..., description="Tin nhắn phản hồi từ phía bot", json_schema_extra={"example": "Chào bạn! Tôi sẵn sàng hỗ trợ bạn."})

class IdentityCreate(BaseModel):
    """
    Model để tạo identity mới cho bot
    
    **Conversation Example có thể sử dụng 2 format:**
    
    1. **Array format**: `[{"user": "...", "you": "..."}, {"user": "...", "you": "..."}]`
    2. **Object format**: `[{"user": "...", "you": "...", "user": "...", "you": "..."}]`
    
    Cả 2 format đều được hỗ trợ và sẽ tự động chuẩn hóa.
    """
    name: str = Field(..., description="Tên của identity", json_schema_extra={"example": "Trợ lý AI thân thiện"})
    info: str = Field(..., description="Thông tin mô tả về identity", 
                     json_schema_extra={"example": "Một trợ lý AI thân thiện, luôn sẵn sàng giúp đỡ khách hàng"})
    style: str = Field(..., description="Phong cách giao tiếp của identity", 
                      json_schema_extra={"example": "Thân thiện, nhiệt tình, chuyên nghiệp"})
    conversation_style: str = Field(..., description="Cách thức giao tiếp cụ thể", 
                                   json_schema_extra={"example": "Nói chuyện tự nhiên như bạn bè, sử dụng emoji phù hợp"})
    conversation_example: Union[List[ConversationExample], List[Dict[str, str]]] = Field(
        ..., 
        description="Ví dụ về cách bot giao tiếp. Hỗ trợ nhiều format khác nhau.",
        json_schema_extra={
            "example": [
                {"user": "Xin chào", "you": "Chào bạn! Tôi có thể giúp gì cho bạn?"},
                {"user": "Cảm ơn", "you": "Không có gì! Luôn sẵn sàng hỗ trợ bạn! 😊"}
            ]
        }
    )
    
    @field_validator('conversation_example')
    @classmethod
    def normalize_conversation_example(cls, v):
        """
        Normalize conversation_example để luôn trả về List[Dict[str, str]]
        Hỗ trợ cả 2 format:
        1. [{"user": "...", "you": "..."}, {"user": "...", "you": "..."}]
        2. [{"user": "...", "you": "...", "user": "...", "you": "..."}]
        """
        if not v:
            return []
            
        result = []
        
        for item in v:
            if isinstance(item, dict):
                # Trường hợp 1: Object có nhiều cặp user-you
                # Ví dụ: {"user": "a", "you": "b", "user": "c", "you": "d"}
                keys = list(item.keys())
                values = list(item.values())
                
                # Tìm các cặp user-you
                i = 0
                while i < len(keys) - 1:
                    if keys[i] == "user" and i + 1 < len(keys) and keys[i + 1] == "you":
                        result.append({
                            "user": values[i],
                            "you": values[i + 1]
                        })
                        i += 2
                    else:
                        i += 1
                
                # Nếu không tìm thấy cặp user-you nào, thử cách khác
                if not result and "user" in item and "you" in item:
                    result.append({
                        "user": item["user"],
                        "you": item["you"]
                    })
                        
            elif hasattr(item, 'user') and hasattr(item, 'you'):
                # Trường hợp ConversationExample object
                result.append({
                    "user": item.user,
                    "you": item.you
                })
        
        return result

class IdentityUpdate(BaseModel):
    """
    Model để cập nhật identity
    
    **Lưu ý về Conversation Example:**
    - Hỗ trợ cùng các format như IdentityCreate
    - Chỉ truyền các field muốn cập nhật (tất cả đều optional)
    - `conversation_example` sẽ thay thế hoàn toàn dữ liệu cũ
    """
    name: Optional[str] = Field(None, description="Tên mới của identity", 
                               json_schema_extra={"example": "Trợ lý AI cập nhật"})
    info: Optional[str] = Field(None, description="Thông tin mô tả mới", 
                               json_schema_extra={"example": "Mô tả đã được cập nhật"})
    style: Optional[str] = Field(None, description="Phong cách giao tiếp mới", 
                                json_schema_extra={"example": "Phong cách chuyên nghiệp hơn"})
    conversation_style: Optional[str] = Field(None, description="Cách thức giao tiếp mới", 
                                             json_schema_extra={"example": "Giao tiếp formal và lịch sự"})
    conversation_example: Optional[Union[List[ConversationExample], List[Dict[str, str]]]] = Field(
        None, 
        description="Ví dụ hội thoại mới (sẽ thay thế hoàn toàn dữ liệu cũ)",
        json_schema_extra={
            "example": [
                {"user": "Câu hỏi mới", "you": "Câu trả lời mới"},
                {"user": "Thắc mắc khác", "you": "Giải đáp chi tiết"}
            ]
        }
    )
    
    @field_validator('conversation_example')
    @classmethod
    def normalize_conversation_example(cls, v):
        """Normalize conversation_example tương tự như IdentityCreate"""
        if v is None:
            return None
            
        if not v:
            return []
            
        result = []
        
        for item in v:
            if isinstance(item, dict):
                keys = list(item.keys())
                values = list(item.values())
                
                i = 0
                while i < len(keys) - 1:
                    if keys[i] == "user" and i + 1 < len(keys) and keys[i + 1] == "you":
                        result.append({
                            "user": values[i],
                            "you": values[i + 1]
                        })
                        i += 2
                    else:
                        i += 1
                
                if not result and "user" in item and "you" in item:
                    result.append({
                        "user": item["user"],
                        "you": item["you"]
                    })
                        
            elif hasattr(item, 'user') and hasattr(item, 'you'):
                result.append({
                    "user": item.user,
                    "you": item.you
                })
        
        return result

class ProcedureCreate(BaseModel):
    name: str
    procedure: str
    type: str = "custom"  # default, custom

class ProcedureUpdate(BaseModel):
    name: Optional[str] = None
    procedure: Optional[str] = None

class BotCreate(BaseModel):
    name: str
    language_code: str
    identity_id: str
    procedure_id: str
    role: str
    target: str
    mission: str
    type: str = "message"  # message, comment, post
    note: Optional[str] = None
    knowledge: Optional[List[str]] = None  # Mảng document_id
    status: str = "off"  # on, off
    connect: Optional[List[Dict[str, Any]]] = None  # Mảng connection objects  

class BotUpdate(BaseModel):
    name: Optional[str] = None
    language_code: str
    identity_id: Optional[str] = None
    procedure_id: Optional[str] = None
    role: Optional[str] = None
    target: Optional[str] = None
    mission: Optional[str] = None
    note: Optional[str] = None
    knowledge: Optional[List[str]] = None  # Mảng document_id
    type: Optional[str] = None
    connect: Optional[List[Dict[str, Any]]] = None  # Mảng connection objects

class LanguageCreate(BaseModel):
    code: str
    name: str
    native_name: Optional[str] = None
    flag: Optional[str] = None
    is_active: bool = True

class LanguageUpdate(BaseModel):
    name: Optional[str] = None
    native_name: Optional[str] = None
    flag: Optional[str] = None
    is_active: Optional[bool] = None

class BotConnectionCreate(BaseModel):
    social_id: str
    social_page_id: str  # ID của page trong bảng social_facebook_pages

class BotKnowledgeUpdate(BaseModel):
    knowledge: List[str]  # Mảng document_id

# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()


# Language Endpoints
@router.get("/languages", response_model=Dict[str, Any])
async def get_languages(
    active_only: bool = Query(False, description="Chỉ lấy các ngôn ngữ đang active"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory)
):
    """Lấy danh sách ngôn ngữ"""
    try:
        if active_only:
            languages = await factory.additional_factory.language_manager.get_active_languages()
        else:
            # Lấy tất cả languages trước, sau đó áp dụng skip và limit
            all_languages = await factory.additional_factory.language_manager.get_all()
            total = len(all_languages)
            languages = all_languages[skip:skip + limit]
        
        # Sắp xếp languages theo thứ tự: vi -> en -> các ngôn ngữ khác (theo code)
        def sort_languages(lang):
            code = lang.get('code', '')
            if code == 'vi':
                return (0, code)  # vi đứng đầu
            elif code == 'en':
                return (1, code)  # en đứng thứ 2
            else:
                return (2, code)  # các ngôn ngữ khác sắp xếp theo code
        
        languages.sort(key=sort_languages)
        
        # Nếu active_only thì không có total
        if active_only:
            return {"success": True, "data": languages}
        else:
            return {"success": True, "data": languages, "total": total}
        
    except Exception as e:
        logger.error(f"Error getting languages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Identity Endpoints
@router.post("/identities", response_model=Dict[str, Any])
async def create_identity(identity_data: IdentityCreate, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """
    Tạo identity mới
    
    **Conversation Example Format:**
    
    API hỗ trợ 2 định dạng cho field `conversation_example`:
    
    **Format 1: Array of separate objects (Khuyến nghị)**
    ```json
    {
      "conversation_example": [
        {"user": "Xin chào", "you": "Chào bạn!"},
        {"user": "Bạn có khỏe không?", "you": "Tôi khỏe, cảm ơn!"},
        {"user": "Tạm biệt", "you": "Hẹn gặp lại!"}
      ]
    }
    ```
    
    **Format 2: Single object with multiple user-you pairs**
    ```json
    {
      "conversation_example": [
        {
          "user": "Xin chào",
          "you": "Chào bạn!",
          "user": "Bạn có khỏe không?", 
          "you": "Tôi khỏe, cảm ơn!"
        }
      ]
    }
    ```
    
    **Format 3: Mixed format (Kết hợp cả 2)**
    ```json
    {
      "conversation_example": [
        {"user": "Xin chào", "you": "Chào bạn!"},
        {
          "user": "Bạn có khỏe không?",
          "you": "Tôi khỏe, cảm ơn!",
          "user": "Tuyệt vời!",
          "you": "Cảm ơn bạn!"
        }
      ]
    }
    ```
    
    Tất cả các format trên sẽ được tự động chuẩn hóa thành format 1 trong database.
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo identity
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "identities")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more identities due to package limits")
            )
        
        # conversation_example đã được normalize bởi validator
        # Nó luôn là List[Dict[str, str]] sau khi qua validator
        conversation_example_data = identity_data.conversation_example
        
        identity = await factory.identity_manager.create_identity(
            name=identity_data.name,
            info=identity_data.info,
            style=identity_data.style,
            conversation_style=identity_data.conversation_style,
            conversation_example=conversation_example_data,
            identity_type="custom",
            user_id=user_id
        )
        
        return {"success": True, "data": identity}
        
    except Exception as e:
        logger.error(f"Error creating identity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/identities", response_model=Dict[str, Any])
async def get_identities(
    type: Optional[str] = Query(None, description="Filter by type: custom or default"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách identities
    
    **Response Format:**
    Dữ liệu trả về sẽ có `conversation_example` ở dạng chuẩn hóa:
    ```json
    {
      "success": true,
      "data": [
        {
          "_id": "...",
          "name": "Tên identity",
          "conversation_example": [
            {"user": "Câu hỏi 1", "you": "Câu trả lời 1"},
            {"user": "Câu hỏi 2", "you": "Câu trả lời 2"}
          ]
        }
      ],
      "total": 10
    }
    ```
    
    **Filter Options:**
    - `type=custom`: Chỉ lấy identities do user tạo
    - `type=default`: Chỉ lấy identities mặc định của hệ thống
    - Không có `type`: Lấy cả custom và default (tùy thuộc user)
    """
    try:
        user_id = current_user.get("user_id")
        
        if user_id:
            identities = await factory.identity_manager.get_by_user_id(user_id, type)
        elif type == "default":
            identities = await factory.identity_manager.get_default_identities()
        else:
            identities = []
        
        # Áp dụng skip và limit
        total = len(identities)
        identities = identities[skip:skip + limit]
        
        return {"success": True, "data": identities, "total": total}
        
    except Exception as e:
        logger.error(f"Error getting identities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/identities/{identity_id}", response_model=Dict[str, Any])
async def get_identity(identity_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """
    Lấy thông tin chi tiết của một identity
    
    **Response Format:**
    ```json
    {
      "success": true,
      "data": {
        "_id": "identity_id",
        "name": "Tên identity",
        "info": "Thông tin mô tả",
        "style": "Phong cách giao tiếp",
        "conversation_style": "Cách thức giao tiếp",
        "conversation_example": [
          {"user": "Câu hỏi người dùng", "you": "Câu trả lời của bot"},
          {"user": "Câu hỏi khác", "you": "Câu trả lời khác"}
        ],
        "type": "custom",
        "user_id": "...",
        "created_at": "2025-09-22T10:00:00Z",
        "updated_at": "2025-09-22T11:00:00Z"
      }
    }
    ```
    
    **Lưu ý:**
    - `conversation_example` luôn được trả về ở dạng chuẩn hóa (array of objects)
    - Chỉ có thể xem identity của chính mình hoặc identity default
    """
    try:
        identity = await factory.identity_manager.get_by_id(identity_id)
        if not identity:
            raise HTTPException(status_code=404, detail="Identity not found")
        
        return {"success": True, "data": identity}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting identity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/identities/{identity_id}", response_model=Dict[str, Any])
async def update_identity(identity_id: str, identity_data: IdentityUpdate, 
                        factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """
    Cập nhật identity
    
    **Conversation Example Format:**
    
    Khi cập nhật field `conversation_example`, API hỗ trợ 2 định dạng tương tự như khi tạo mới:
    
    **Format 1: Array of separate objects (Khuyến nghị)**
    ```json
    {
      "conversation_example": [
        {"user": "Câu hỏi mới", "you": "Câu trả lời mới"},
        {"user": "Câu hỏi khác", "you": "Câu trả lời khác"}
      ]
    }
    ```
    
    **Format 2: Single object with multiple user-you pairs**
    ```json
    {
      "conversation_example": [
        {
          "user": "Câu hỏi 1",
          "you": "Câu trả lời 1",
          "user": "Câu hỏi 2", 
          "you": "Câu trả lời 2"
        }
      ]
    }
    ```
    
    **Lưu ý:**
    - Chỉ cần truyền các field muốn cập nhật
    - `conversation_example` sẽ thay thế hoàn toàn dữ liệu cũ (không merge)
    - Dữ liệu sẽ được tự động chuẩn hóa trước khi lưu vào database
    """
    try:
        # Chỉ update các field không None
        update_data = {}
        for k, v in identity_data.dict().items():
            if v is not None:
                # conversation_example đã được normalize bởi validator
                update_data[k] = v
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        identity = await factory.identity_manager.update_by_id(identity_id, update_data)
        if not identity:
            raise HTTPException(status_code=404, detail="Identity not found")
        
        return {"success": True, "data": identity}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating identity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/identities/{identity_id}", response_model=Dict[str, Any])
async def delete_identity(identity_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Xóa identity"""
    try:
        # Clear references from bots before removing the identity
        bots_using_identity = await factory.bot_manager.count({"identity_id": identity_id})
        if bots_using_identity:
            await factory.bot_manager.bulk_update([
                {
                    "filter": {"identity_id": identity_id},
                    "update": {"identity_id": ""}
                }
            ])

        success = await factory.identity_manager.delete_by_id(identity_id)
        if not success:
            raise HTTPException(status_code=404, detail="Identity not found")

        return {"success": True, "message": "Identity deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting identity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/identities/{identity_id}/copy", response_model=Dict[str, Any])
async def copy_identity(identity_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Copy identity"""
    try:
        # Lấy identity gốc để lấy tên
        original_identity = await factory.identity_manager.get_by_id(identity_id)
        if not original_identity:
            raise HTTPException(status_code=404, detail="Identity not found")
        
        copied_identity = await factory.identity_manager.copy_by_id(identity_id, {
            "name": f"Copy of {original_identity['name']}"
        })
        
        if not copied_identity:
            raise HTTPException(status_code=404, detail="Identity not found")
        
        return {"success": True, "data": copied_identity}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying identity: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Procedure Endpoints
@router.post("/procedures", response_model=Dict[str, Any])
async def create_procedure(procedure_data: ProcedureCreate, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Tạo procedure mới"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo procedure
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "procedures")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more procedures due to package limits")
            )
        
        procedure = await factory.procedure_manager.create_procedure(
            name=procedure_data.name,
            procedure=procedure_data.procedure,
            procedure_type=procedure_data.type,
            user_id=user_id
        )
        
        return {"success": True, "data": procedure}
        
    except Exception as e:
        logger.error(f"Error creating procedure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/procedures", response_model=Dict[str, Any])
async def get_procedures(
    type: Optional[str] = Query(None, description="Filter by type: custom or default"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)
):
    """Lấy danh sách procedures"""
    try:
        user_id = current_user.get("user_id")
        
        if user_id:
            procedures = await factory.procedure_manager.get_by_user_id(user_id, type)
        elif type == "default":
            procedures = await factory.procedure_manager.get_default_procedures()
        else:
            procedures = []
        
        # Áp dụng skip và limit
        total = len(procedures)
        procedures = procedures[skip:skip + limit]
        
        return {"success": True, "data": procedures, "total": total}
        
    except Exception as e:
        logger.error(f"Error getting procedures: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/procedures/{procedure_id}", response_model=Dict[str, Any])
async def get_procedure(procedure_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Lấy thông tin procedure"""
    try:
        procedure = await factory.procedure_manager.get_by_id(procedure_id)
        if not procedure:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        return {"success": True, "data": procedure}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting procedure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/procedures/{procedure_id}", response_model=Dict[str, Any])
async def update_procedure(procedure_id: str, procedure_data: ProcedureUpdate,
                         factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Cập nhật procedure"""
    try:
        # Chỉ update các field không None
        update_data = {k: v for k, v in procedure_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        procedure = await factory.procedure_manager.update_by_id(procedure_id, update_data)
        if not procedure:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        return {"success": True, "data": procedure}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating procedure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/procedures/{procedure_id}", response_model=Dict[str, Any])
async def delete_procedure(procedure_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Xóa procedure"""
    try:
        # Clear references from bots before removing the procedure
        bots_using_procedure = await factory.bot_manager.count({"procedure_id": procedure_id})
        if bots_using_procedure:
            await factory.bot_manager.bulk_update([
                {
                    "filter": {"procedure_id": procedure_id},
                    "update": {"procedure_id": ""}
                }
            ])

        success = await factory.procedure_manager.delete_by_id(procedure_id)
        if not success:
            raise HTTPException(status_code=404, detail="Procedure not found")

        return {"success": True, "message": "Procedure deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting procedure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/procedures/{procedure_id}/copy", response_model=Dict[str, Any])
async def copy_procedure(procedure_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Copy procedure"""
    try:
        # Lấy procedure gốc để lấy tên
        original_procedure = await factory.procedure_manager.get_by_id(procedure_id)
        if not original_procedure:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        copied_procedure = await factory.procedure_manager.copy_by_id(procedure_id, {
            "name": f"Copy of {original_procedure['name']}"
        })
        
        if not copied_procedure:
            raise HTTPException(status_code=404, detail="Procedure not found")
        
        return {"success": True, "data": copied_procedure}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying procedure: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    
# Bot Endpoints
@router.post("/bots", response_model=Dict[str, Any])
async def create_bot(bot_data: BotCreate, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Tạo bot mới"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo bot
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "bot")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot create more bots due to package limits")
            )
        
        # Validate knowledge documents nếu có
        if bot_data.knowledge:
            for doc_id in bot_data.knowledge:
                document = await factory.document_manager.get_by_id(doc_id)
                if not document:
                    raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
                
                # Kiểm tra quyền truy cập
                if document.get("user_id") != user_id:
                    company_id = document.get("company_id")
                    if company_id:
                        company = await factory.company_manager.get_by_id(company_id)
                        if not company or company.get("user_id") != user_id:
                            raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
                    else:
                        raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
        
        bot = await factory.bot_manager.create_bot(
            user_id=user_id,
            name=bot_data.name,
            language_code=bot_data.language_code,
            identity_id=bot_data.identity_id,
            procedure_id=bot_data.procedure_id,
            role=bot_data.role,
            target=bot_data.target,
            mission=bot_data.mission,
            bot_type=bot_data.type,
            note=bot_data.note,
            knowledge=bot_data.knowledge,
            status=bot_data.status,
            connect=bot_data.connect
        )
        
        return {"success": True, "data": bot}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bots", response_model=Dict[str, Any])
async def get_bots(
    status: Optional[str] = Query(None, description="Filter by status: on or off"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)
):
    """Lấy danh sách bots"""
    try:
        user_id = current_user.get("user_id")
        
        if user_id:
            bots = await factory.bot_manager.get_by_user_id(user_id, status)
        elif status == "on":
            bots = await factory.bot_manager.get_active_bots()
        else:
            bots = []
        
        # Áp dụng skip và limit
        total = len(bots)
        bots = bots[skip:skip + limit]
        
        return {"success": True, "data": bots, "total": total}
        
    except Exception as e:
        logger.error(f"Error getting bots: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bots/{bot_id}", response_model=Dict[str, Any])
async def get_bot(bot_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Lấy thông tin bot"""
    try:
        bot = await factory.bot_manager.get_by_id(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {"success": True, "data": bot}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bots/{bot_id}", response_model=Dict[str, Any])
async def update_bot(bot_id: str, bot_data: BotUpdate, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Cập nhật bot"""
    try:
        # Chỉ update các field không None
        update_data = {k: v for k, v in bot_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        bot = await factory.bot_manager.update_by_id(bot_id, update_data)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {"success": True, "data": bot}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bots/{bot_id}/activate", response_model=Dict[str, Any])
async def activate_bot(bot_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Bật bot"""
    try:
        # Lấy thông tin bot trước
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Kiểm tra bot đã connect với page nào chưa
        connections = []
        if current_bot.get('connect'):
            try:
                if isinstance(current_bot['connect'], str):
                    connections = json.loads(current_bot['connect'])
                elif isinstance(current_bot['connect'], list):
                    connections = current_bot['connect']
            except:
                connections = []
        
        # Nếu chưa connect với page nào thì không cho active
        if not connections or len(connections) == 0:
            raise HTTPException(
                status_code=400, 
                detail="Bot chưa được kết nối với bất kỳ Facebook page nào. Vui lòng kết nối bot với page trước khi kích hoạt."
            )
        
        # Cập nhật subscribed apps cho tất cả pages đã connect
        facebook_update_results = []
        for connection in connections:
            if connection.get('social_id') == 's_facebook':
                # Lấy thông tin page để có access token
                page_id = connection.get('social_page_id')
                page = await factory.facebook_page_manager.get_by_id(page_id)
                
                if page and page.get('fb_page_access_token'):
                    fb_page_id = page.get('fb_page_id')
                    access_token = page.get('fb_page_access_token')
                    
                    # Gọi API Facebook để bật subscribed apps
                    success, result = subscribed_apps(fb_page_id, access_token, type="on")
                    
                    facebook_update_results.append({
                        "page_id": page_id,
                        "fb_page_id": fb_page_id,
                        "fb_page_name": page.get('fb_page_name'),
                        "success": success,
                        "result": result
                    })
                    
                    if not success:
                        logger.warning(f"Failed to update subscribed apps for page {fb_page_id}: {result}")
        
        # Kích hoạt bot trong database
        bot = await factory.bot_manager.activate_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {
            "success": True, 
            "data": bot,
            "facebook_updates": facebook_update_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bots/{bot_id}/deactivate", response_model=Dict[str, Any])
async def deactivate_bot(bot_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Tắt bot"""
    try:
        # Lấy thông tin bot trước
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Kiểm tra bot có connect với page nào không
        connections = []
        if current_bot.get('connect'):
            try:
                if isinstance(current_bot['connect'], str):
                    connections = json.loads(current_bot['connect'])
                elif isinstance(current_bot['connect'], list):
                    connections = current_bot['connect']
            except:
                connections = []
        
        # Cập nhật subscribed apps cho tất cả pages đã connect (nếu có)
        facebook_update_results = []
        if connections and len(connections) > 0:
            for connection in connections:
                if connection.get('social_id') == 's_facebook':
                    # Lấy thông tin page để có access token
                    page_id = connection.get('social_page_id')
                    page = await factory.facebook_page_manager.get_by_id(page_id)
                    
                    if page and page.get('fb_page_access_token'):
                        fb_page_id = page.get('fb_page_id')
                        access_token = page.get('fb_page_access_token')
                        
                        # Gọi API Facebook để tắt subscribed apps
                        success, result = subscribed_apps(fb_page_id, access_token, type="off")
                        
                        facebook_update_results.append({
                            "page_id": page_id,
                            "fb_page_id": fb_page_id,
                            "fb_page_name": page.get('fb_page_name'),
                            "success": success,
                            "result": result
                        })
                        
                        if not success:
                            logger.warning(f"Failed to update subscribed apps for page {fb_page_id}: {result}")
        
        # Tắt bot trong database
        bot = await factory.bot_manager.deactivate_bot(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {
            "success": True, 
            "data": bot,
            "facebook_updates": facebook_update_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bots/{bot_id}/connection", response_model=Dict[str, Any])
async def update_bot_connection(
    bot_id: str,
    connection_data: BotConnectionCreate,
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Cập nhật kết nối bot với Facebook page"""
    try:
        # Lấy thông tin social page để validate và lấy thông tin cần thiết
        page = await factory.facebook_page_manager.get_by_id(connection_data.social_page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Facebook page not found")
        
        # Lấy thông tin social account để có social_account_id
        social_account = await factory.social_account_manager.get_by_id(page['social_account_id'])
        if not social_account:
            raise HTTPException(status_code=404, detail="Social account not found")
        
        # Lấy bot hiện tại để kiểm tra connect hiện tại
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Parse connect hiện tại (nếu có) - hỗ trợ cả string JSON và array
        current_connections = []
        if current_bot.get('connect'):
            try:
                if isinstance(current_bot['connect'], str):
                    current_connections = json.loads(current_bot['connect'])
                elif isinstance(current_bot['connect'], list):
                    current_connections = current_bot['connect']
                else:
                    current_connections = []
                    
                if not isinstance(current_connections, list):
                    current_connections = []
            except:
                current_connections = []
        
        # Tạo connection object mới
        new_connection = {
            "social_id": connection_data.social_id,
            "social_account_id": str(social_account['_id']),
            "social_page_id": connection_data.social_page_id,
            "fb_page_id": page['fb_page_id'],
            "fb_page_name": page['fb_page_name'],
            "connected_at": datetime.now().isoformat()
        }
        
        # Kiểm tra xem connection này đã tồn tại chưa
        existing_connection_index = -1
        for i, conn in enumerate(current_connections):
            if conn.get('social_page_id') == connection_data.social_page_id:
                existing_connection_index = i
                break
        
        if existing_connection_index >= 0:
            # Cập nhật connection hiện có
            current_connections[existing_connection_index] = new_connection
        else:
            # Thêm connection mới
            current_connections.append(new_connection)
        
        # Cập nhật bot với danh sách connections mới (lưu dưới dạng array thay vì string)
        bot = await factory.bot_manager.update_by_id(bot_id, {"connect": current_connections})
        
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Nếu social_id là "s_facebook" thì cập nhật is_connected = True trong social_facebook_pages
        if connection_data.social_id == "s_facebook":
            await factory.facebook_page_manager.update_by_id(
                connection_data.social_page_id, 
                {"is_connected": True}
            )
        
        return {"success": True, "data": bot, "connection": new_connection}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bot connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bots/{bot_id}/connections", response_model=Dict[str, Any])
async def get_bot_connections(
    bot_id: str, 
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Lấy danh sách kết nối của bot"""
    try:
        bot = await factory.bot_manager.get_by_id(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        connections = []
        if bot.get('connect'):
            try:
                # Xử lý cả trường hợp connect là string JSON hoặc array 
                if isinstance(bot['connect'], str):
                    connections = json.loads(bot['connect'])
                elif isinstance(bot['connect'], list):
                    connections = bot['connect']
                else:
                    connections = []
                    
                if not isinstance(connections, list):
                    connections = []
            except:
                connections = []
        
        return {"success": True, "data": connections}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot connections: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bots/{bot_id}/connections/{social_page_id}", response_model=Dict[str, Any])
async def remove_bot_connection(
    bot_id: str,
    social_page_id: str,
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Xóa kết nối bot với Facebook page"""
    try:
        # Lấy bot hiện tại
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Parse connect hiện tại - hỗ trợ cả string JSON và array
        current_connections = []
        if current_bot.get('connect'):
            try:
                if isinstance(current_bot['connect'], str):
                    current_connections = json.loads(current_bot['connect'])
                elif isinstance(current_bot['connect'], list):
                    current_connections = current_bot['connect']
                else:
                    current_connections = []
                    
                if not isinstance(current_connections, list):
                    current_connections = []
            except:
                current_connections = []
        
        # Xóa connection có social_page_id tương ứng
        initial_count = len(current_connections)
        current_connections = [conn for conn in current_connections if conn.get('social_page_id') != social_page_id]
        
        if len(current_connections) == initial_count:
            raise HTTPException(status_code=404, detail="Connection not found")
        
        # Cập nhật bot (lưu dưới dạng array thay vì string)
        bot = await factory.bot_manager.update_by_id(bot_id, {"connect": current_connections})
        
        # Tìm connection đã bị xóa để lấy social_id
        removed_connection = None
        for conn in (current_bot.get('connect', []) if isinstance(current_bot.get('connect'), list) else []):
            if conn.get('social_page_id') == social_page_id:
                removed_connection = conn
                break
        
        # Nếu social_id là "s_facebook" thì cập nhật is_connected = False trong social_facebook_pages
        if removed_connection and removed_connection.get('social_id') == "s_facebook":
            await factory.facebook_page_manager.update_by_id(
                social_page_id, 
                {"is_connected": False}
            )
        
        return {"success": True, "data": bot, "message": "Connection removed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing bot connection: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bots/{bot_id}/knowledge", response_model=Dict[str, Any])
async def update_bot_knowledge(
    bot_id: str, 
    knowledge_data: BotKnowledgeUpdate, 
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Cập nhật kiến thức bot với mảng document_id"""
    try:
        # Validate document IDs exist và thuộc về user
        user_id = current_user.get("user_id")
        
        # Kiểm tra từng document_id
        for doc_id in knowledge_data.knowledge:
            document = await factory.document_manager.get_by_id(doc_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
            
            # Kiểm tra document có thuộc về user không (hoặc company của user)
            if document.get("user_id") != user_id:
                # Kiểm tra xem document có thuộc về company của user không
                company_id = document.get("company_id")
                if company_id:
                    company = await factory.company_manager.get_by_id(company_id)
                    if not company or company.get("user_id") != user_id:
                        raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
                else:
                    raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
        
        # Cập nhật bot knowledge
        bot = await factory.bot_manager.update_bot_knowledge(bot_id, knowledge_data.knowledge)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {"success": True, "data": bot}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating bot knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bots/{bot_id}/knowledge", response_model=Dict[str, Any])
async def get_bot_knowledge(
    bot_id: str, 
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Lấy danh sách knowledge (documents) của bot"""
    try:
        # Lấy thông tin bot
        bot = await factory.bot_manager.get_by_id(bot_id)
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Lấy knowledge documents
        knowledge_list = bot.get('knowledge', [])
        if not isinstance(knowledge_list, list):
            knowledge_list = []
        
        # Lấy thông tin chi tiết của các documents
        documents = []
        for doc_id in knowledge_list:
            try:
                document = await factory.document_manager.get_by_id(doc_id)
                if document:
                    documents.append({
                        "document_id": str(document["_id"]),
                        "document_name": document.get("document_name", ""),
                        "file_name": document.get("file_name", ""),
                        "file_type": document.get("file_type", ""),
                        "status": document.get("status", ""),
                        "created_at": document.get("create_at", "")
                    })
            except Exception as e:
                logger.warning(f"Failed to get document {doc_id}: {str(e)}")
                continue
        
        return {
            "success": True, 
            "data": {
                "bot_id": bot_id,
                "bot_name": bot.get("name", ""),
                "knowledge_count": len(documents),
                "documents": documents
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bots/{bot_id}/knowledge/add", response_model=Dict[str, Any])
async def add_bot_knowledge(
    bot_id: str, 
    knowledge_data: BotKnowledgeUpdate, 
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Thêm documents vào knowledge của bot"""
    try:
        user_id = current_user.get("user_id")
        
        # Lấy bot hiện tại
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Lấy knowledge hiện tại
        current_knowledge = current_bot.get('knowledge', [])
        if not isinstance(current_knowledge, list):
            current_knowledge = []
        
        # Validate và thêm document IDs mới
        new_docs = []
        for doc_id in knowledge_data.knowledge:
            if doc_id in current_knowledge:
                continue  # Skip nếu đã tồn tại
                
            document = await factory.document_manager.get_by_id(doc_id)
            if not document:
                raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
            
            # Kiểm tra quyền truy cập
            if document.get("user_id") != user_id:
                company_id = document.get("company_id")
                if company_id:
                    company = await factory.company_manager.get_by_id(company_id)
                    if not company or company.get("user_id") != user_id:
                        raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
                else:
                    raise HTTPException(status_code=403, detail=f"Access denied to document {doc_id}")
            
            new_docs.append(doc_id)
        
        # Cập nhật knowledge
        updated_knowledge = current_knowledge + new_docs
        bot = await factory.bot_manager.update_bot_knowledge(bot_id, updated_knowledge)
        
        return {
            "success": True, 
            "data": bot,
            "added_documents": new_docs,
            "total_documents": len(updated_knowledge)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding bot knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bots/{bot_id}/knowledge/{document_id}", response_model=Dict[str, Any])
async def remove_bot_knowledge(
    bot_id: str,
    document_id: str,
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """Xóa một document khỏi knowledge của bot"""
    try:
        # Lấy bot hiện tại
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Lấy knowledge hiện tại
        current_knowledge = current_bot.get('knowledge', [])
        if not isinstance(current_knowledge, list):
            current_knowledge = []
        
        if document_id not in current_knowledge:
            raise HTTPException(status_code=404, detail="Document not found in bot knowledge")
        
        # Xóa document khỏi knowledge
        updated_knowledge = [doc for doc in current_knowledge if doc != document_id]
        bot = await factory.bot_manager.update_bot_knowledge(bot_id, updated_knowledge)
        
        return {
            "success": True, 
            "data": bot,
            "removed_document": document_id,
            "remaining_documents": len(updated_knowledge)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing bot knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bots/{bot_id}", response_model=Dict[str, Any])
async def delete_bot(bot_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Xóa bot"""
    try:
        # Lấy thông tin bot trước khi xóa để cập nhật is_connected của pages
        current_bot = await factory.bot_manager.get_by_id(bot_id)
        if not current_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        # Lấy danh sách connections
        connections = []
        if current_bot.get('connect'):
            try:
                if isinstance(current_bot['connect'], str):
                    connections = json.loads(current_bot['connect'])
                elif isinstance(current_bot['connect'], list):
                    connections = current_bot['connect']
            except:
                connections = []
        
        # Cập nhật is_connected = False cho tất cả Facebook pages đang connect
        for connection in connections:
            if connection.get('social_id') == 's_facebook' and connection.get('social_page_id'):
                try:
                    await factory.facebook_page_manager.update_by_id(
                        connection['social_page_id'], 
                        {"is_connected": False}
                    )
                    logger.info(f"Updated is_connected=False for page {connection['social_page_id']}")
                except Exception as e:
                    logger.error(f"Error updating is_connected for page {connection['social_page_id']}: {str(e)}")
        
        # Xóa bot
        success = await factory.bot_manager.delete_by_id(bot_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {
            "success": True, 
            "message": "Bot deleted successfully",
            "disconnected_pages": len([c for c in connections if c.get('social_id') == 's_facebook'])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bots/{bot_id}/copy", response_model=Dict[str, Any])
async def copy_bot(bot_id: str, factory = Depends(get_management_factory), current_user: dict = Depends(get_current_user)):
    """Copy bot"""
    try:
        # Lấy bot gốc để lấy tên
        original_bot = await factory.bot_manager.get_by_id(bot_id)
        if not original_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        copied_bot = await factory.bot_manager.copy_by_id(bot_id, {
            "name": f"Copy of {original_bot['name']}",
            "status": "off"  # Copy bot luôn bắt đầu với status off
        })
        
        if not copied_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return {"success": True, "data": copied_bot}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================== TEST BOT API V2 ======================

class TestBotMessage(BaseModel):
    sender_id: str
    page_id: str
    bot_id: Optional[str] = None
    message: str
    company_id: Optional[str] = None

class TestBotBufferedMessage(BaseModel):
    """Model cho test buffering - gửi tin nhắn vào buffer"""
    sender_id: str
    page_id: str
    bot_id: Optional[str] = None
    message: str
    company_id: Optional[str] = None

class TestBotBatchMessages(BaseModel):
    """Model cho test batch - gửi nhiều tin nhắn cùng lúc"""
    sender_id: str
    page_id: str
    bot_id: Optional[str] = None
    messages: List[str] = Field(..., description="Danh sách tin nhắn cần gửi liên tiếp")
    company_id: Optional[str] = None

@router.post("/test-bot", response_model=Dict[str, Any])
async def test_bot_message(
    message_data: TestBotMessage,
    factory = Depends(get_management_factory)
):
    """
    Test Bot Messenger V2 API
    
    Endpoint để test bot messenger với:
    - sender_id: Facebook sender ID
    - page_id: Facebook page ID  
    - message: Tin nhắn test
    - company_id: ID của company (nếu không có sẽ lấy company mặc định)
    """
    try:
        # Xử lý tin nhắn qua Bot Agent V2
        # Tắt buffer cho API test để nhận response ngay lập tức
        response = await process_facebook_message(
            sender_id=message_data.sender_id,
            page_id=message_data.page_id,
            bot_id=message_data.bot_id,
            message=message_data.message,
            use_buffer=False,  # API test không dùng buffer
            company_id=message_data.company_id
        )
        
        return {
            "success": True,
            "data": {
                "sender_id": message_data.sender_id,
                "page_id": message_data.page_id,
                "user_message": message_data.message,
                "bot_response": response.response,
                "bot_response_segments": response.segments,
                "metadata": response.metadata
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing bot message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bot test error: {str(e)}")

@router.post("/test-bot/buffered", response_model=Dict[str, Any])
async def test_bot_buffered_message(
    message_data: TestBotBufferedMessage,
    factory = Depends(get_management_factory)
):
    """
    Test Bot với Message Buffering
    
    Endpoint này sẽ thêm tin nhắn vào buffer (không trả response ngay).
    
    **Cách sử dụng:**
    1. Gọi endpoint này nhiều lần liên tiếp với cùng sender_id + page_id
    2. Các tin nhắn sẽ được gom nhóm trong 2 giây
    3. Sau 2 giây, bot sẽ xử lý tất cả tin nhắn đã gom
    4. Response sẽ được log ra console (hoặc gửi qua webhook nếu có)
    
    **Use case:**
    - Test tính năng gom nhóm tin nhắn liên tiếp
    - Simulate webhook behavior của Facebook
    - Test với nhiều tin nhắn + hình ảnh
    
    **Lưu ý:** API này trả về ngay lập tức, response thực tế sẽ xuất hiện sau buffer_time
    """
    try:
        # Thêm tin nhắn vào buffer (use_buffer=True)
        await process_facebook_message(
            sender_id=message_data.sender_id,
            page_id=message_data.page_id,
            bot_id=message_data.bot_id,
            message=message_data.message,
            use_buffer=True,  # Sử dụng buffer
            company_id=message_data.company_id
        )
        
        return {
            "success": True,
            "message": "Tin nhắn đã được thêm vào buffer. Bot sẽ xử lý sau 2 giây nếu không có tin nhắn mới.",
            "data": {
                "sender_id": message_data.sender_id,
                "page_id": message_data.page_id,
                "user_message": message_data.message,
                "note": "Response thực tế sẽ được xử lý trong background và log ra console"
            }
        }
        
    except Exception as e:
        logger.error(f"Error buffering bot message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bot buffer error: {str(e)}")

@router.post("/test-bot/batch", response_model=Dict[str, Any])
async def test_bot_batch_messages(
    message_data: TestBotBatchMessages,
    factory = Depends(get_management_factory)
):
    """
    Test Bot với nhiều tin nhắn cùng lúc (Batch Mode)
    
    Endpoint này cho phép gửi nhiều tin nhắn cùng lúc và nhận response đã gom nhóm.
    
    **Ví dụ request:**
    ```json
    {
        "sender_id": "test_user_001",
        "page_id": "test_page_001",
        "bot_id": "your_bot_id",
        "messages": [
            "hi",
            "shop có bán sản phẩm này không",
            "https://example.com/image.png"
        ]
    }
    ```
    
    **Kết quả:**
    Bot sẽ xử lý message gộp: "hi\\nshop có bán sản phẩm này không\\nhttps://example.com/image.png"
    
    **Use case:**
    - Test bot với nhiều tin nhắn liên tiếp
    - Simulate user gửi message + hình ảnh
    - Kiểm tra khả năng hiểu context đầy đủ
    """
    try:
        # Gộp tất cả messages thành một
        combined_message = "\n".join(message_data.messages)
        
        # Log combined message đầy đủ
        logger.info(f"📦 Batch processing {len(message_data.messages)} messages")
        logger.info(f"📝 Combined message (full):\n{'='*60}\n{combined_message}\n{'='*60}")
        
        # Xử lý message gộp (không dùng buffer vì đã gộp sẵn)
        response = await process_facebook_message(
            sender_id=message_data.sender_id,
            page_id=message_data.page_id,
            bot_id=message_data.bot_id,
            message=combined_message,
            use_buffer=False,  # Không cần buffer vì đã gộp rồi
            company_id=message_data.company_id
        )
        
        return {
            "success": True,
            "data": {
                "sender_id": message_data.sender_id,
                "page_id": message_data.page_id,
                "original_messages": message_data.messages,
                "combined_message": combined_message,
                "bot_response": response.response,
                "bot_response_segments": response.segments,
                "metadata": response.metadata
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing bot batch messages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bot batch test error: {str(e)}")

@router.get("/test-bot/info/{page_id}", response_model=Dict[str, Any])
async def get_bot_test_info(
    page_id: str,
    factory = Depends(get_management_factory)
):
    """
    Lấy thông tin bot để test
    
    Args:
        page_id: Facebook page ID
    """
    try:
        from bot.bot_facebook_messenger import bot_agent_v2
        
        # Initialize agent if needed
        if not bot_agent_v2.factory:
            await bot_agent_v2.initialize()
        
        # Lấy thông tin bot
        bot_info = await bot_agent_v2.get_bot_info_from_page_id(page_id)
        
        if not bot_info:
            raise HTTPException(status_code=404, detail="Bot configuration not found for this page")
        
        # Format response
        return {
            "success": True,
            "data": {
                "page_id": page_id,
                "bot": {
                    "id": str(bot_info["bot"]["_id"]),
                    "name": bot_info["bot"]["name"],
                    "status": bot_info["bot"]["status"],
                    "type": bot_info["bot"]["type"],
                    "role": bot_info["bot"]["role"],
                    "target": bot_info["bot"]["target"],
                    "mission": bot_info["bot"]["mission"]
                },
                "identity": {
                    "id": str(bot_info["identity"]["_id"]) if bot_info["identity"] else None,
                    "name": bot_info["identity"]["name"] if bot_info["identity"] else None,
                    "style": bot_info["identity"]["style"] if bot_info["identity"] else None
                },
                "procedure": {
                    "id": str(bot_info["procedure"]["_id"]) if bot_info["procedure"] else None,
                    "name": bot_info["procedure"]["name"] if bot_info["procedure"] else None
                },
                "knowledge_documents": [
                    {
                        "id": str(doc["_id"]),
                        "title": doc.get("title", ""),
                        "file_type": doc.get("file_type", "")
                    } for doc in bot_info["knowledge_documents"]
                ],
                "user_id": bot_info["user_id"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting bot test info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-bot/conversation/{page_id}/{sender_id}", response_model=Dict[str, Any])
async def get_conversation_history_test(
    page_id: str,
    sender_id: str,
    limit: int = Query(10, description="Số lượng tin nhắn tối đa"),
    factory = Depends(get_management_factory)
):
    """
    Lấy lịch sử trò chuyện để test
    
    Args:
        page_id: Facebook page ID
        sender_id: Facebook sender ID
        limit: Số lượng tin nhắn
    """
    try:
        from bot.bot_facebook_messenger import bot_agent_v2
        
        # Initialize agent if needed
        if not bot_agent_v2.factory:
            await bot_agent_v2.initialize()
        
        # Lấy lịch sử trò chuyện
        history = await bot_agent_v2.get_conversation_history(sender_id, page_id, limit)
        
        return {
            "success": True,
            "data": {
                "page_id": page_id,
                "sender_id": sender_id,
                "conversation_history": [
                    {
                        "id": str(msg["_id"]),
                        "query": msg.get("query", ""),
                        "response": msg.get("response", ""),
                        "created_at": msg.get("created_at"),
                        "metadata": msg.get("metadata", {})
                    } for msg in history
                ],
                "total_messages": len(history)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-bot/knowledge-search", response_model=Dict[str, Any])
async def test_knowledge_search(
    page_id: str,
    query: str,
    limit: int = Query(5, description="Số lượng chunks tối đa"),
    factory = Depends(get_management_factory)
):
    """
    Test tìm kiếm knowledge chunks
    
    Args:
        page_id: Facebook page ID
        query: Câu hỏi tìm kiếm
        limit: Số lượng chunks
    """
    try:
        from bot.bot_facebook_messenger import bot_agent_v2
        
        # Initialize agent if needed
        if not bot_agent_v2.factory:
            await bot_agent_v2.initialize()
        
        # Lấy bot info
        bot_info = await bot_agent_v2.get_bot_info_from_page_id(page_id)
        if not bot_info:
            raise HTTPException(status_code=404, detail="Bot not found for this page")
        
        # Search knowledge
        document_ids = [str(doc["_id"]) for doc in bot_info["knowledge_documents"]]
        chunks = await bot_agent_v2.search_knowledge_chunks(query, document_ids, limit)
        
        return {
            "success": True,
            "data": {
                "query": query,
                "document_ids": document_ids,
                "found_chunks": [
                    {
                        "id": str(chunk["_id"]),
                        "content": chunk.get("content", ""),
                        "source_info": chunk.get("source_info", {}),
                        "relevance_score": chunk.get("relevance_score", 0),
                        "metadata": chunk.get("metadata", {})
                    } for chunk in chunks
                ],
                "total_chunks": len(chunks)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing knowledge search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ====================== END TEST BOT API V2 ======================

