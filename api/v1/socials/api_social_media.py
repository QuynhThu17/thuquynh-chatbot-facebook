"""
Social Media Management API Endpoints
Cung cấp API cho socials, social_accounts, và các platform accounts
"""

import os
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query, Form, Request, BackgroundTasks
from typing import List, Optional, Dict, Any
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from datetime import datetime
import logging
import requests
import httpx
import json
import hashlib
import hmac
import base64
import urllib3
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

# ✅ Suppress SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.data.limit_service import get_limit_service

# Import Facebook modules
from controllers.socials.facebook.facebook_connect import connect_facebook, reload_facebook_pages
from controllers.socials.facebook.facebook_send_messenger import send_facebook_messenger

from controllers.auth.auth_middleware import get_current_user
from configs import constant

from bot.bot_facebook_messenger import process_facebook_message, bot_facebook_messenger

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Social Media Management"])


# Pydantic Models
class SocialCreate(BaseModel):
    name: str
    logo_url: Optional[str] = None

class SocialConnectRequest(BaseModel):
    user_id: str
    access_token: Optional[str] = None
    authorization_code: Optional[str] = None

class SocialDisconnectRequest(BaseModel):
    user_id: str
    account_id: str

class FacebookPageConnectRequest(BaseModel):
    user_id: str
    page_id: str
    is_connected: bool = True

class MessageData(BaseModel):
    type: str = Field(description="Message type (text, image_url, etc.)")
    content: Union[str, List[str]] = Field(description="Message content")
    page_id: str = Field(description="Facebook page ID")
    sender_id: str = Field(description="Sender ID")
    sticker: bool = Field(default=False, description="Indicates if the message is a sticker")
    reply_to: Optional[Dict[str, Any]] = Field(default=None, description="Metadata of the message being replied to")
    local_image_paths: Optional[List[str]] = Field(default=None, description="Local paths of downloaded images")

class SendMessageRequest(BaseModel):
    page_id: str = Field(description="Facebook page ID")
    sender_id: str = Field(description="Người nhận tin nhắn (Facebook User ID)")
    messages: List[Dict[str, Any]] = Field(
        description="Danh sách tin nhắn cần gửi. Format: [{'type': 'text'|'image'|'images', 'data': str|List[str]}]"
    )
    
# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()


@router.get("/socials", response_model=Dict[str, Any])
async def get_socials(factory=Depends(get_management_factory)):
    """Lấy danh sách social platforms"""
    try:
        socials = await factory.social_manager.get_all()
        return {"success": True, "data": socials}

    except Exception as e:
        logger.error(f"Error getting social platforms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/socials/{social_id}", response_model=Dict[str, Any])
async def get_social(social_id: str, factory=Depends(get_management_factory)):
    """Lấy thông tin social platform"""
    try:
        social = await factory.social_manager.get_by_id(social_id)
        if not social:
            raise HTTPException(status_code=404, detail="Social platform not found")

        return {"success": True, "data": social}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social platform: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/socials/{social_id}/connect", response_model=Dict[str, Any])
# async def connect_social(
#     social_id: str, 
#     factory=Depends(get_management_factory),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Kết nối với Social Platform"""
#     try:
#         if social_id != "s_facebook":
#             raise HTTPException(status_code=400, detail="Only Facebook connection is supported currently")
        
#         user_id = current_user.get("user_id")
#         url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id={constant.CLIENT_ID}&redirect_uri={constant.REDIRECT_URI}&client_secret={constant.CLIENT_SECRET}&scope=pages_show_list,pages_messaging,public_profile,pages_manage_metadata&response_type=code&state={user_id}"
#         return RedirectResponse(url=url, status_code=302)

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error connecting to social platform: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.post("/socials/{social_id}/connect", response_model=Dict[str, Any])
async def connect_social(
    social_id: str, 
    factory=Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Kết nối với Social Platform"""
    try:
        if social_id != "s_facebook":
            raise HTTPException(status_code=400, detail="Only Facebook connection is supported currently")
        
        user_id = current_user.get("user_id")
        auth_url = f"https://www.facebook.com/v20.0/dialog/oauth?client_id={constant.CLIENT_ID}&redirect_uri={constant.REDIRECT_URI}&client_secret={constant.CLIENT_SECRET}&scope=pages_show_list,pages_messaging,public_profile,pages_manage_metadata&response_type=code&state={user_id}"
        
        return {
            "success": True,
            "data": {
                "auth_url": auth_url,
                "message": "Please open the auth_url to connect with Facebook"
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to social platform: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/socials/{social_id}/accounts", response_model=Dict[str, Any])
async def get_social_accounts(
    social_id: str, 
    current_user: dict = Depends(get_current_user),
    factory=Depends(get_management_factory)
):
    """Lấy danh sách accounts đã kết nối theo social platform"""
    try:
        # Kiểm tra social platform có tồn tại không
        social = await factory.social_manager.get_by_id(social_id)
        if not social:
            raise HTTPException(status_code=404, detail="Social platform not found")
        
        # Lấy danh sách social accounts
        user_id = current_user.get("user_id")
        accounts = await factory.social_account_manager.get_by_user_id(user_id, social_id)
        
        # bỏ phần social_account_access_token trong accounts trả về
        for account in accounts:
            if "social_account_access_token" in account:
                del account["social_account_access_token"]

        return {"success": True, "data": accounts}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/socials/{social_id}/pages", response_model=Dict[str, Any])
async def get_social_pages(
    social_id: str,
    social_accounts_id: str = Query(description="ID của social account để lấy pages"),
    reload: bool = Query(False, description="Nếu true thì sẽ cập nhật lại danh sách pages từ account social platform"),
    current_user: dict = Depends(get_current_user),
    factory=Depends(get_management_factory)
):
    """Lấy danh sách pages/accounts theo social platform"""
    try:
        # Kiểm tra social platform có tồn tại không
        social = await factory.social_manager.get_by_id(social_id)
        if not social:
            raise HTTPException(status_code=404, detail="Social platform not found")
        
        social_name = social.get("name", "").lower()
        user_id = current_user.get("user_id")
        
        all_pages = []
        
        if social_name == "facebook" or social_id == "s_facebook":
            # Nếu có reload=True, reload pages từ Facebook API trước
            if reload:
                if social_accounts_id:
                    # Reload cho account cụ thể
                    reload_result = await reload_facebook_pages(social_account_id=social_accounts_id)
                else:
                    # Reload cho tất cả accounts của user
                    reload_result = await reload_facebook_pages(user_id=user_id)
                
                if reload_result.get("status") != 200:
                    logger.warning(f"Reload pages failed: {reload_result.get('message')}")
            
            if social_accounts_id:
                pages = await factory.facebook_page_manager.get_by_social_account_id(social_accounts_id)
                all_pages.extend(pages)
            else: 
                # Lấy social accounts của user cho Facebook
                social_accounts = await factory.social_account_manager.get_by_user_id(user_id, social_id)
                
                for account in social_accounts:
                    # Lấy Facebook pages cho mỗi social account
                    pages = await factory.facebook_page_manager.get_by_social_account_id(str(account["_id"]))
                    all_pages.extend(pages)
            
            # bỏ phần fb_page_access_token trong all_pages trả về
            for page in all_pages:
                if "fb_page_access_token" in page:
                    del page["fb_page_access_token"]

            return {"success": True, "data": all_pages}
        
        else:
            raise HTTPException(status_code=400, detail=f"Pages not supported for {social_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social pages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/socials/{social_id}/pages/{social_page_id}", response_model=Dict[str, Any])
async def get_social_page_info(
    social_id: str,
    social_page_id: str,
    current_user: dict = Depends(get_current_user),
    factory=Depends(get_management_factory)
):
    """Lấy thông tin chi tiết của page theo social_id và social_page_id"""
    try:
        # Kiểm tra social platform có tồn tại không
        social = await factory.social_manager.get_by_id(social_id)
        if not social:
            raise HTTPException(status_code=404, detail="Social platform not found")
        
        social_name = social.get("name", "").lower()
        user_id = current_user.get("user_id")
        
        if social_name == "facebook" or social_id == "s_facebook":
            # Lấy thông tin Facebook page
            page = await factory.facebook_page_manager.get_by_fb_page_id(social_page_id)
            
            if not page:
                raise HTTPException(status_code=404, detail="Facebook page not found")
            
            # Kiểm tra page có thuộc về user không
            social_account_id = page.get("social_account_id")
            if social_account_id:
                social_account = await factory.social_account_manager.get_by_id(social_account_id)
                if not social_account or social_account.get("user_id") != user_id:
                    raise HTTPException(status_code=403, detail="You don't have permission to access this page")
            else:
                raise HTTPException(status_code=400, detail="Invalid page configuration")
            
            # Bỏ fb_page_access_token trước khi trả về
            if "fb_page_access_token" in page:
                del page["fb_page_access_token"]
            
            return {"success": True, "data": page}
        
        else:
            raise HTTPException(status_code=400, detail=f"Page info not supported for {social_name}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting social page info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Handler cho callback Facebook
@router.get("/socials/facebook/connect", response_class=HTMLResponse)
async def facebook_connect(request: Request):
    """FE không sử dụng - Hàm callback sau khi người dùng xác thực Facebook"""
    try:
        authorization_code = request.query_params.get('code')
        id_user = request.query_params.get('state')

        if not authorization_code:
            return HTMLResponse(content="<html><body><h1>Error: Not found code in URL!</h1></body></html>")

        user_access_token = await connect_facebook(authorization_code, id_user)

        return HTMLResponse(content=user_access_token)
    except Exception as e:
        return HTMLResponse(content=f"<html><body><h1>Error: {str(e)}</h1></body></html>")
    
    
@router.get("/socials/facebook/webhook")
async def verify_token(request: Request):
    """
    Xác thực webhook với Facebook Messenger Platform.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == constant.VERIFY_TOKEN:
        return int(challenge)
    else:
        raise HTTPException(status_code=403, detail="Token không hợp lệ")


def save_webhook_data(body_json: dict):
    """
    Lưu webhook data vào file JSON
    Tạo folder theo ngày và file theo timestamp
    """
    try:
        # Lấy thời gian hiện tại
        now = datetime.now()
        
        # Tạo đường dẫn folder theo ngày (YYYY-MM-DD)
        date_folder = now.strftime("%Y-%m-%d")
        webhook_folder = Path("resources/webhook") / date_folder
        
        # Tạo folder nếu chưa tồn tại
        webhook_folder.mkdir(parents=True, exist_ok=True)
        
        # Tạo tên file theo timestamp (YYYY-MM-DD_HH-MM-SS.json)
        filename = now.strftime("%Y-%m-%d_%H-%M-%S.json")
        filepath = webhook_folder / filename
        
        # Lưu data vào file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(body_json, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Webhook data saved to: {filepath}")
        
    except Exception as e:
        logger.error(f"Error saving webhook data: {str(e)}")


async def download_facebook_image(image_url: str) -> Optional[Dict[str, Any]]:
    """
    Download ảnh từ Facebook CDN ngay lập tức khi nhận được webhook.
    Lưu vào local file và tùy chọn encode base64.
    
    Args:
        image_url: URL ảnh từ Facebook CDN
        
    Returns:
        Dict chứa local_path, base64_data, size hoặc None nếu thất bại
    """
    try:
        # Tạo thư mục lưu ảnh nếu chưa có
        images_dir = Path("resources/images")
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # Tạo tên file unique dựa trên timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        local_filename = f"fb_image_{timestamp}.png"
        local_path = images_dir / local_filename
        
        # Headers giống như user gợi ý
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.facebook.com/",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        
        # Download ảnh với httpx async client
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.get(image_url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            # Lưu vào file
            with open(local_path, "wb") as f:
                f.write(response.content)
            
            # Tùy chọn: encode base64 để lưu vào DB nếu cần
            base64_data = base64.b64encode(response.content).decode('utf-8')
            
            logger.info(f"✅ Downloaded Facebook image: {local_path} ({len(response.content)} bytes)")
            
            return {
                "local_path": str(local_path),
                "base64_data": base64_data,
                "size": len(response.content),
                "original_url": image_url
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP error downloading image: {e.response.status_code} - {image_url[:100]}")
        return None
    except Exception as e:
        logger.error(f"❌ Error downloading Facebook image: {str(e)} - {image_url[:100]}")
        return None


@router.post("/socials/facebook/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    factory=Depends(get_management_factory),
):
    body = await request.body()
    x_hub_signature = request.headers.get("x-hub-signature-256")

    if not verify_signature(x_hub_signature, body):
        raise HTTPException(status_code=403, detail="Request không hợp lệ")

    body_json = await request.json()

    # Lưu webhook data vào file trong thread riêng để không chặn request loop
    async def _save_webhook_data_async(payload: Dict[str, Any]) -> None:
        try:
            await asyncio.to_thread(save_webhook_data, payload)
        except Exception as exc:
            logger.error(f"Error saving webhook data in background: {exc}")

    asyncio.create_task(_save_webhook_data_async(body_json))

    webhook_data = await extract_facebook_webhook_data(body_json)

    if not webhook_data:
        return "EVENT_RECEIVED"

    # Determine user dựa trên Facebook page ID
    user_id = None
    if factory and webhook_data.page_id:
        try:
            facebook_page = await factory.facebook_page_manager.get_by_fb_page_id(webhook_data.page_id)
            if facebook_page:
                social_account_id = facebook_page.get("social_account_id")
                if social_account_id:
                    social_account = await factory.social_account_manager.get_by_id(social_account_id)
                    if social_account:
                        user_id = social_account.get("user_id")
        except Exception as exc:
            logger.error(f"Error resolving user for page {webhook_data.page_id}: {exc}")

    can_process_message = True
    should_increment_usage = False
    limit_service = None

    if user_id:
        try:
            limit_service = get_limit_service(factory)
            limits_info = await limit_service.get_user_current_limits(str(user_id))
            message_limit = (limits_info or {}).get("limits", {}).get("messages_per_month")

            if message_limit:
                limit_value = message_limit.get("limit")
                is_unlimited = message_limit.get("is_unlimited") or (isinstance(limit_value, int) and limit_value == -1)

                if not is_unlimited:
                    remaining = message_limit.get("remaining")
                    if isinstance(remaining, str):
                        try:
                            remaining = int(remaining)
                        except (TypeError, ValueError):
                            logger.warning(f"Unexpected remaining value for user {user_id}: {remaining}")
                            remaining = 0

                    if remaining is None or remaining <= 0:
                        can_process_message = False
                        logger.warning(f"Facebook webhook blocked for user {user_id}: messages_per_month limit reached")
                    else:
                        should_increment_usage = True
        except Exception as exc:
            logger.error(f"Error checking message limit for user {user_id}: {exc}")

    if webhook_data.content and can_process_message:
        async def process_message_and_track_usage():
            try:
                await process_facebook_message(
                    webhook_data.sender_id,
                    webhook_data.page_id,
                    message=webhook_data.content,
                    use_buffer=True,
                    send_facebook=True,
                    type=webhook_data.type,
                    local_image_paths=webhook_data.local_image_paths,
                )
                if should_increment_usage and limit_service:
                    await limit_service.increment_usage(str(user_id), "messages_per_month")
            except Exception as exc:
                logger.error(f"Error processing Facebook webhook message for page {webhook_data.page_id}: {exc}")

        background_tasks.add_task(process_message_and_track_usage)

    return "EVENT_RECEIVED"


def verify_signature(x_hub_signature, body):
    """
    Hàm xác thực chữ ký request đến từ Facebook.
    """
    if not x_hub_signature:
        return False

    signature = x_hub_signature.split("=")[1]
    mac = hmac.new(constant.CLIENT_SECRET.encode(), body, hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)


async def _fetch_reply_message_from_graph(page_id: str, message_id: str) -> Optional[Dict[str, Any]]:
    if not message_id:
        return None
    try:
        if not bot_facebook_messenger.factory:
            await bot_facebook_messenger.initialize()
        access_token = await bot_facebook_messenger.get_page_access_token_cached(page_id)
        if not access_token:
            logger.warning(f"Bot Messenger WARN || Missing page access token when fetching reply message {message_id}")
            return None
        url = f"https://graph.facebook.com/v20.0/{message_id}"
        params = {
            "fields": "id,message,attachments{type,media_type,media,url,filename,description,subattachments,payload},sticker"
        }
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await asyncio.to_thread(
            requests.get,
            url,
            params=params,
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            logger.error(
                f"Bot Messenger ERR || Failed to fetch reply message {message_id}: {response.status_code} - {response.text}"
            )
            return None
        return response.json()
    except Exception as exc:
        logger.error(f"Bot Messenger ERR || Exception fetching reply message {message_id}: {exc}")
        return None


def _summarize_reply_message(reply_data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(reply_data, dict):
        return None

    parts = []

    message_text = reply_data.get("message")
    if message_text:
        parts.append(str(message_text))

    attachments_container = reply_data.get("attachments") or {}
    attachments = attachments_container.get("data") if isinstance(attachments_container, dict) else []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue

        attachment_type = attachment.get("type") or attachment.get("media_type")
        payload = attachment.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        url = (
            attachment.get("url")
            or payload.get("url")
            or payload.get("href")
            or payload.get("src")
            or payload.get("source")
        )
        title = attachment.get("title") or payload.get("title")
        description = attachment.get("description") or payload.get("description")

        segments = []
        if attachment_type:
            segments.append(str(attachment_type).upper())
        if title:
            segments.append(str(title))
        if url:
            segments.append(str(url))
        elif description:
            segments.append(str(description))

        if segments:
            parts.append(" - ".join(segments))

    sticker = reply_data.get("sticker")
    if isinstance(sticker, dict):
        sticker_url = sticker.get("url") or sticker.get("link")
        if sticker_url:
            parts.append(f"STICKER - {sticker_url}")

    return "\n".join(parts) if parts else None


async def _build_reply_metadata(page_id: str, reply_payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(reply_payload, dict):
        return None

    message_id = reply_payload.get("mid") or reply_payload.get("id")
    if not message_id:
        return None

    metadata: Dict[str, Any] = {
        "mid": message_id,
        "payload": reply_payload,
    }

    reply_data = await _fetch_reply_message_from_graph(page_id, message_id)
    if reply_data:
        metadata["message"] = reply_data.get("message")

    return metadata


async def extract_facebook_webhook_data(json_data: Dict) -> Optional[MessageData]:
    """Extract message data from Facebook webhook payload."""
    try:
        entry = json_data.get("entry", [])
        if not entry or not isinstance(entry, list):
            logger.error("Bot Messenger ERR || Missing or invalid 'entry' field")
            return None

        entry_item = entry[0]
        page_id = entry_item.get("id")

        messaging = entry_item.get("messaging", [])
        if not messaging or not isinstance(messaging, list):
            logger.warning("Bot Messenger WARN || No 'messaging' field found")
            return None

        messaging_item = messaging[0]
        sender = messaging_item.get("sender", {})
        sender_id = sender.get("id")

        message = messaging_item.get("message", {})

        if not message:
            postback = messaging_item.get("postback", {})
            message_text = postback.get("title")
            if message_text:
                message_text = (
                    message_text.encode("latin1").decode("utf-8")
                    if isinstance(message_text, str)
                    else message_text
                )
                return MessageData(
                    type="text",
                    content=message_text,
                    page_id=page_id,
                    sender_id=sender_id,
                )
            return None

        reply_payload = message.get("reply_to")
        reply_metadata = (
            await _build_reply_metadata(page_id, reply_payload)
            if isinstance(reply_payload, dict)
            else None
        )

        message_text = message.get("text")
        if message_text:
            try:
                message_text = (
                    message_text.encode("latin1").decode("utf-8")
                    if isinstance(message_text, str)
                    else message_text
                )
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass

            if reply_metadata and isinstance(message_text, str):
                summary = reply_metadata.get("message")
                if summary:
                    message_text = f"{message_text}\n\n[Replied to message]:\n{summary}"

            return MessageData(
                type="text",
                content=message_text,
                page_id=page_id,
                sender_id=sender_id,
                reply_to=reply_metadata,
            )

        attachments = message.get("attachments", [])
        if attachments:
            urls = []
            local_image_paths = []
            
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    continue
                if attachment.get("type") == "image":
                    payload = attachment.get("payload", {})
                    sticker_id = payload.get("sticker_id")
                    if not sticker_id:
                        url = payload.get("url")
                        if url:
                            urls.append(url)
                            logger.info(f"Found image URL: {url}")
                            
                            # Download ảnh ngay lập tức để tránh URL expire
                            download_result = await download_facebook_image(url)
                            if download_result:
                                local_image_paths.append(download_result["local_path"])
                                logger.info(f"✅ Image downloaded to: {download_result['local_path']}")
                            else:
                                logger.warning(f"⚠️ Failed to download image from: {url[:100]}")
                    else:
                        if len(attachments) == 1:
                            return MessageData(
                                type="sticker",
                                content=payload.get("url") or str(sticker_id),
                                page_id=page_id,
                                sender_id=sender_id,
                                sticker=True,
                                reply_to=reply_metadata,
                            )

            if len(urls) == 1:
                return MessageData(
                    type="image_url",
                    content=urls[0],
                    page_id=page_id,
                    sender_id=sender_id,
                    reply_to=reply_metadata,
                    local_image_paths=local_image_paths if local_image_paths else None,
                )
            elif len(urls) > 1:
                return MessageData(
                    type="multiple_images",
                    content=urls,
                    page_id=page_id,
                    sender_id=sender_id,
                    reply_to=reply_metadata,
                    local_image_paths=local_image_paths if local_image_paths else None,
                )

        return None
    except Exception as e:
        logger.error(f"Bot Messenger ERR || Error in extract_message_data: {e}")
        return None

@router.post("/socials/facebook/send-message", response_model=Dict[str, Any])
async def send_message_to_facebook(
    request: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
    factory=Depends(get_management_factory)
):
    """
    Gửi tin nhắn tới Facebook Messenger
    
    Args:
        page_id: ID của Facebook page
        sender_id: ID của người nhận (Facebook User ID)
        messages: Danh sách tin nhắn cần gửi
            Format: [
                {"type": "text", "data": "Nội dung tin nhắn"},
                {"type": "image", "data": "https://example.com/image.jpg"},
                {"type": "images", "data": ["url1", "url2"]}
            ]
    
    Returns:
        Dict với success status và message
    """
    try:
        user_id = current_user.get("user_id")
        page_id = request.page_id
        sender_id = request.sender_id
        messages = request.messages
        
        # Validate page_id thuộc về user
        facebook_page = await factory.facebook_page_manager.get_by_fb_page_id(page_id)
        
        if not facebook_page:
            raise HTTPException(status_code=404, detail="Facebook page not found")
        
        # Kiểm tra page có thuộc về user không
        social_account_id = facebook_page.get("social_account_id")
        if not social_account_id:
            raise HTTPException(status_code=400, detail="Invalid Facebook page configuration")
        
        social_account = await factory.social_account_manager.get_by_id(social_account_id)
        if not social_account or social_account.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to send messages from this page")
        
        # Validate messages format
        if not messages or not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="Messages must be a non-empty list")
        
        for msg in messages:
            if not isinstance(msg, dict):
                raise HTTPException(status_code=400, detail="Each message must be a dictionary")
            if "type" not in msg or "data" not in msg:
                raise HTTPException(status_code=400, detail="Each message must have 'type' and 'data' fields")
            if msg["type"] not in ["text", "image", "images"]:
                raise HTTPException(status_code=400, detail="Message type must be 'text', 'image', or 'images'")
        
        # Gửi tin nhắn qua Facebook Messenger và lưu history trong background
        # để không chờ và trả về response nhanh hơn
        async def send_and_save_background():
            try:
                await send_facebook_messenger(page_id, sender_id, messages)
                
                # Lưu lịch sử tin nhắn
                session_id = f"{page_id}_{sender_id}"
                
                # Format messages để lưu vào history
                message_text = []
                for msg in messages:
                    msg_type = msg.get("type", "")
                    msg_data = msg.get("data", "")
                    
                    if msg_type == "text":
                        message_text.append(f"[Text]: {msg_data}")
                    elif msg_type == "image":
                        message_text.append(f"[Image]: {msg_data}")
                    elif msg_type == "images":
                        if isinstance(msg_data, list):
                            message_text.append(f"[Images]: {', '.join(msg_data)}")
                        else:
                            message_text.append(f"[Images]: {msg_data}")
                
                formatted_message = "\n".join(message_text)
                
                # Lưu vào history
                await factory.history_factory.save_history(
                    user_id=user_id,
                    session_id=session_id,
                    customer_id=sender_id,
                    query="",  # User không gửi query trong trường hợp này
                    answer=formatted_message,
                    status="active",
                    bot_id=None,
                    social_id="s_facebook",
                    social_page_id=page_id,
                    response_segments=messages,
                    sender_info={
                        "name": "",
                        "profile_pic": "",
                        "gender": "",
                        "id": sender_id,
                    }
                )
                
                logger.info(f"✅ Message sent and saved to history for session: {session_id}")
                
            except Exception as e:
                logger.error(f"❌ Error in background send_and_save: {str(e)}")
        
        # Chạy background task mà không chờ để response nhanh hơn
        asyncio.create_task(send_and_save_background())
        
        return {
            "success": True,
            "message": "Message sent successfully",
            "data": {
                "page_id": page_id,
                "sender_id": sender_id,
                "message_count": len(messages)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error sending Facebook message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    
