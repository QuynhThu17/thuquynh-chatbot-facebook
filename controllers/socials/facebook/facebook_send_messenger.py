import requests
from urllib.parse import urlsplit, urlunsplit, quote
import asyncio
from controllers.data.managements import get_mongodb_factory

import logging
logger = logging.getLogger(__name__)


def send_typing_action(page_id, page_access_token, sender_id, typing = "on"):
    """
    Hàm gửi trạng thái gõ tin nhắn Facebook.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    if typing == "on":
        action = "typing_on"
    elif typing == "off":
        action = "typing_off"
    else:
        action = "mark_seen"

    data = {"recipient": {"id": sender_id}, "sender_action": action}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None
    
    

def send_images(
    page_id, page_access_token, sender_id, image_urls = [], mode: str = "single", aspect: str = "horizontal"
):
    """
    Hàm gửi tin nhắn hình ảnh đến Facebook Messenger.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    def _encode_public_url(u: str) -> str:
        try:
            parts = urlsplit(u)
            encoded_path = quote(parts.path, safe="/")
            return urlunsplit((parts.scheme, parts.netloc, encoded_path, parts.query, parts.fragment))
        except Exception:
            return u

    try:
        encoded_urls = []
        for u in image_urls:
            if not u:
                continue
            eu = _encode_public_url(u)
            encoded_urls.append(eu)

        if not encoded_urls:
            return

        if mode == "carousel" and len(encoded_urls) >= 2:
            send_typing_action(page_id, page_access_token, sender_id)
            elements = [{"title": " ", "image_url": eu} for eu in encoded_urls[:10]]
            data = {
                "recipient": {"id": sender_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "template",
                        "payload": {
                            "template_type": "generic",
                            "elements": elements,
                            "image_aspect_ratio": (aspect if aspect in ("square", "horizontal") else "horizontal")
                        }
                    }
                },
            }
            resp = requests.post(url, headers=headers, json=data, timeout=120)
            if resp.status_code != 200:
                logger.error(
                    f"Failed to send carousel. Status: {resp.status_code}, Resp: {resp.text}"
                )
            return

        for eu in encoded_urls:
            send_typing_action(page_id, page_access_token, sender_id)
            data = {
                "recipient": {"id": sender_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "image",
                        "payload": {"is_reusable": True, "url": eu}
                    }
                },
            }
            resp = requests.post(url, headers=headers, json=data, timeout=120)
            if resp.status_code != 200:
                logger.error(
                    f"Failed to send image. Status: {resp.status_code}, Resp: {resp.text}"
                )

    except Exception as e:
        logger.error(f"An exception occurred while sending image: {str(e)}")

    finally:
        send_typing_action(
            page_id, page_access_token, sender_id, typing="off"
        )
        return

def send_text_message(
    page_id, page_access_token, sender_id, message
):
    """
    Hàm gửi tin nhắn đến Facebook Messenger.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    send_typing_action(page_id, page_access_token, sender_id)

    data = {
        "recipient": {"id": sender_id},
        "messaging_type": "RESPONSE",
        "message": {"text": message},
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=120)
        if response.status_code != 200:
            logger.error(
                f"Failed to send message. Status code: {response.status_code}, Response: {response.text}"
            )
    except Exception as e:
        logger.error(f"An exception occurred message: {str(e)}")
    finally:
        send_typing_action(page_id, page_access_token, sender_id, typing="off")
        return


async def send_facebook_messenger(
    page_id, sender_id, messages
):
    """
    Hàm gửi tin nhắn đến Facebook Messenger.
    """
    
    # Lấy access token của page từ database
    try:
        factory = get_mongodb_factory()
        facebook_page = await factory.facebook_page_manager.get_by_fb_page_id(page_id)
        
        if not facebook_page:
            logger.warning(f"Không tìm thấy Facebook page với ID: {page_id}")
            return
        
        page_access_token = facebook_page.get("fb_page_access_token", "")
        
        if not page_access_token:
            logger.warning(f"Không tìm thấy access token cho page: {page_id}")
            return
            
    except Exception as e:
        logger.error(f"Lỗi khi lấy page access token: {str(e)}")
        return

    try:
        if not messages:
            return
        
        # Gửi từng câu nhỏ
        for message in messages:
            type = message.get("type", "")
            msg = message.get("data", "")
            
            if not msg:
                continue

            if type == "text":
                await asyncio.to_thread(
                    send_text_message,
                    page_id,
                    page_access_token,
                    sender_id,
                    msg,
                )
            elif type == "image":
                await asyncio.to_thread(
                    send_images,
                    page_id,
                    page_access_token,
                    sender_id,
                    [msg],
                )
            elif type == "images":
                if isinstance(msg, list):
                    layout = message.get("layout") or message.get("mode") or message.get("display")
                    use_mode = "carousel" if (layout == "carousel" or len(msg) >= 2) else "single"
                    aspect = message.get("aspect") or message.get("image_aspect_ratio") or "square"
                    await asyncio.to_thread(
                        send_images,
                        page_id,
                        page_access_token,
                        sender_id,
                        msg,
                        use_mode,
                        aspect,
                    )
            else:
                pass
    except Exception as e:
        logger.error(f"An exception occurred message: {str(e)}")
        return









