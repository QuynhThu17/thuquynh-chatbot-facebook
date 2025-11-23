import requests
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
    page_id, page_access_token, sender_id, image_urls = []
):
    """
    Hàm gửi tin nhắn hình ảnh đến Facebook Messenger.
    """

    url = f"https://graph.facebook.com/v20.0/{page_id}/messages"

    headers = {
        "Authorization": f"Bearer {page_access_token}",
    }

    attachments = []

    for image_url in image_urls:
        try:
            attachments.append({
                "type": "image",
                "payload": {"is_reusable": True, "url": image_url},
            })
                
        except Exception as e:
            pass

    try:
        if attachments:
            send_typing_action(
                page_id, page_access_token, sender_id
            )

            # Gửi tin nhắn chứa ảnh lên Facebook Messenger
            data = {
                "recipient": {"id": sender_id},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachments": attachments
                },
            }

            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code == 200:
                pass
            else:
                logger.error(
                    f"Failed to send image. Status code: {response.status_code}, Response: {response.text}"
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
                    await asyncio.to_thread(
                        send_images,
                        page_id,
                        page_access_token,
                        sender_id,
                        msg,
                    )
            else:
                pass
    except Exception as e:
        logger.error(f"An exception occurred message: {str(e)}")
        return









