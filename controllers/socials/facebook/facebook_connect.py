import requests
import asyncio
from configs import constant
from controllers.data.managements import get_mongodb_factory
from controllers.data.limit_service import get_limit_service
from .facebook_s3_utils import download_and_upload_facebook_avatar, download_and_upload_facebook_page_avatar

import logging
logger = logging.getLogger(__name__)

async def connect_facebook(authorization_code, id_user):
    access_token_url = f"https://graph.facebook.com/v20.0/oauth/access_token"
    params = {
        'client_id': constant.CLIENT_ID,
        'redirect_uri': constant.REDIRECT_URI,
        'client_secret': constant.CLIENT_SECRET,
        'code': authorization_code
    }

    try:
        response = requests.get(access_token_url, params=params, timeout=300)
        logger.info(f"Response from Facebook: {response.json()}")

        # 3. Kiểm tra phản hồi từ Facebook
        if response.status_code == 200:
            # Lấy `access_token` từ phản hồi JSON
            access_token = response.json().get('access_token')
            logger.info(f"Access Token: {access_token}")

            # Chạy các hàm async
            try:
                await save_user_account_data(id_user, access_token)
                await save_pages(id_user, access_token)
            except Exception as e:
                logger.error(f"Lỗi khi lưu dữ liệu: {e}")

            # 4. Trả về một trang HTML sử dụng `postMessage` để gửi access_token về trang gốc
            return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Facebook OAuth</title>
                </head>
                <body>
                    <h1>Facebook OAuth Success</h1>
                    <p>Access Token đã nhận được thành công!</p>
                    <script>
                        // Gửi `access_token` về cửa sổ cha qua `postMessage`
                        window.opener.postMessage({{"access_token": "{access_token}"}}, "*");
    
                        // Tự động đóng popup sau khi gửi xong
                        window.close();
                    </script>
                </body>
                </html>
                """
        else:
            # In ra lỗi nếu có
            logger.error(f"Lỗi khi lấy Access Token: {response.json()}")
            return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Facebook OAuth</title>
                </head>
                <body>
                    <h1>Lỗi khi lấy Access Token</h1>
                    <p>Không thể lấy Access Token, vui lòng thử lại.</p>
                    <script>
                        // Gửi thông báo lỗi về cửa sổ cha
                        window.opener.postMessage({{"error": "{response.json()}"}}, "*");
    
                        // Tự động đóng popup sau khi gửi xong
                        window.close();
                    </script>
                </body>
                </html>
                """

    except Exception as e:
        logger.error(f"Lỗi khi lấy Access Token: {e}")
        return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Facebook OAuth</title>
            </head>
            <body>
                <h1>Lỗi khi lấy Access Token</h1>
                <p>Không thể lấy Access Token, vui lòng thử lại.</p>
                <script>
                    // Gửi thông báo lỗi về cửa sổ cha
                    window.opener.postMessage({{"error": "{e}"}}, "*");
    
                    // Tự động đóng popup sau khi gửi xong
                    window.close();
                </script>
            </body>
            </html>
            """

async def save_user_account_data(id_user, access_fb):
    try:
        # Lấy MongoDB factory
        factory = get_mongodb_factory()
        
        # Lấy thông tin user từ Facebook Graph API
        url = "https://graph.facebook.com/v20.0/me"
        params = {
            'access_token': access_fb,
            'fields': 'id,name'
        }
        
        response = requests.get(url, params=params, timeout=300)
        if response.status_code != 200:
            return {
                "name": None,
                "profile_pic": None,
                "gender": None,
                "id": None,
                "status": 400, 
                "message": "Failed to get user info from Facebook"
            }
            
        user_info = response.json()
        fb_user_id = user_info.get('id')
        fb_user_name = user_info.get('name')
        
        # Lấy ảnh đại diện user
        fb_user_avatar = None
        s3_avatar_url = None
        try:
            avatar_url = f"https://graph.facebook.com/v20.0/me/picture?access_token={access_fb}&redirect=false&type=large"
            avatar_response = requests.get(avatar_url, timeout=300)
            if avatar_response.status_code == 200:
                avatar_data = avatar_response.json()
                fb_user_avatar = avatar_data.get('data', {}).get('url')
                
                # Upload avatar lên S3 nếu có URL
                if fb_user_avatar:
                    s3_avatar_url = await download_and_upload_facebook_avatar(
                        fb_user_avatar, id_user, "user"
                    )
        except Exception as e:
            logger.error(f"Error fetching user avatar: {str(e)}")
        
        social_id = "s_facebook"
        
        # Kiểm tra xem social account đã tồn tại chưa
        existing_account = await factory.social_account_manager.get_by_social_user_id(
            fb_user_id, social_id
        )
        
        if existing_account:
            # Cập nhật thông tin account đã tồn tại
            updated_account = await factory.social_account_manager.update_by_id(
                existing_account['_id'],
                {
                    'user_id': id_user,
                    'social_account_name': fb_user_name,
                    'social_account_avatar_url': s3_avatar_url or fb_user_avatar,
                    'social_account_access_token': access_fb
                }
            )
            return updated_account
        else:
            # Kiểm tra limit trước khi tạo social account mới
            limit_service = get_limit_service(factory)
            limit_check = await limit_service.check_limit_before_create(id_user, "social")
            
            if not limit_check.get("can_create", False):
                return {"status": 403, "message": limit_check.get("message", "Cannot connect more social accounts due to package limits")}
            
            # Tạo social account mới
            new_account = await factory.social_account_manager.create_social_account(
                social_id=social_id,
                user_id=id_user,
                social_account_user_id=fb_user_id,
                social_account_name=fb_user_name,
                social_account_avatar_url=s3_avatar_url or fb_user_avatar,
                social_account_access_token=access_fb
            )
            return new_account
            
    except Exception as e:
        return {"status": 500, "message": f"Error: {str(e)}"}


async def save_pages(user_id, access_token_user):  
    try:
        # Lấy MongoDB factory
        factory = get_mongodb_factory()

        list_pages = []

        # Gửi yêu cầu đến Facebook API để lấy danh sách các trang
        page_list_url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={access_token_user}"
        response = requests.get(page_list_url, timeout=300)

        # Kiểm tra nếu phản hồi trả về thành công
        if response.status_code == 200:
            response_page_data = response.json()

            # Lấy social account để lấy social_account_id
            social_id = "s_facebook"
            social_accounts = await factory.social_account_manager.get_by_user_id(user_id, social_id)
            
            if not social_accounts:
                return {"status": 400, "message": "No Facebook social account found for this user"}
            
            # Lấy social_account_id đầu tiên (nếu có nhiều account)
            social_account_id = str(social_accounts[0]['_id'])

            # Lặp qua từng trang trong phản hồi
            for new_page in response_page_data.get("data", []):
                id_page = new_page.get("id")
                name_page = new_page.get("name")
                access_token_page = new_page.get("access_token")

                # Lấy ảnh đại diện page
                fb_page_avatar = None
                s3_page_avatar_url = None
                try:
                    page_avatar_url = f"https://graph.facebook.com/v20.0/{id_page}/picture?redirect=false&type=large"
                    avatar_response = requests.get(page_avatar_url, params={'access_token': access_token_page}, timeout=300)
                    if avatar_response.status_code == 200:
                        avatar_data = avatar_response.json()
                        fb_page_avatar = avatar_data.get('data', {}).get('url')
                        
                        # # Upload page avatar lên S3 nếu có URL
                        # if fb_page_avatar:
                        #     s3_page_avatar_url = await download_and_upload_facebook_page_avatar(
                        #         fb_page_avatar, user_id, id_page
                        #     )
                except Exception as e:
                    logger.error(f"Error fetching page avatar for {id_page}: {str(e)}")

                page = {
                    "page_id": id_page,
                    "page_name": name_page,
                    "page_access_token": access_token_page,
                    "page_avatar": fb_page_avatar or s3_page_avatar_url
                }

                list_pages.append(page)

                # Kiểm tra xem trang này đã tồn tại trong database hay chưa
                existing_page = await factory.facebook_page_manager.get_by_fb_page_id(id_page)

                # Nếu trang chưa tồn tại, lưu vào MongoDB
                if not existing_page:
                    await factory.facebook_page_manager.create_facebook_page(
                        fb_page_id=id_page,
                        fb_page_name=name_page,
                        fb_page_avatar=fb_page_avatar or s3_page_avatar_url,
                        fb_page_access_token=access_token_page,
                        social_account_id=social_account_id,
                        is_connected=False,
                        webhook_verified=False
                    )

            logger.info("Danh sách trang đã được lưu vào MongoDB!")
            logger.info(f"List of pages: {list_pages}")
            return list_pages
        else:
            # Nếu phản hồi không thành công, trả về thông tin lỗi
            return {"status": response.status_code,
                    "message": response.json().get("error", {}).get("message", "Unknown error")}

    except Exception as e:
        return {"status": 500, "message": f"Error: {str(e)}"}


async def reload_facebook_pages(social_account_id=None, user_id=None):
    """
    Reload Facebook pages từ API và cập nhật vào database
    """
    try:
        factory = get_mongodb_factory()
        
        # Nếu có social_account_id thì reload cho account đó
        if social_account_id:
            social_account = await factory.social_account_manager.get_by_id(social_account_id)
            if not social_account:
                return {"status": 404, "message": "Social account not found"}
            
            access_token = social_account.get('social_account_access_token')
            if not access_token:
                return {"status": 400, "message": "No access token found for this account"}
            
            # Reload pages cho account này
            await reload_pages_for_account(social_account_id, access_token)
            
        # Nếu có user_id thì reload cho tất cả accounts của user
        elif user_id:
            social_id = "s_facebook"
            social_accounts = await factory.social_account_manager.get_by_user_id(user_id, social_id)
            
            for account in social_accounts:
                access_token = account.get('social_account_access_token')
                if access_token:
                    await reload_pages_for_account(str(account['_id']), access_token)
        
        return {"status": 200, "message": "Pages reloaded successfully"}
        
    except Exception as e:
        return {"status": 500, "message": f"Error reloading pages: {str(e)}"}


async def reload_pages_for_account(social_account_id, access_token):
    """
    Reload pages cho một social account cụ thể
    """
    try:
        factory = get_mongodb_factory()
        
        # Gọi Facebook API để lấy danh sách pages
        page_list_url = f"https://graph.facebook.com/v20.0/me/accounts?access_token={access_token}"
        response = requests.get(page_list_url, timeout=300)
        
        if response.status_code != 200:
            return {"status": response.status_code, "message": "Failed to fetch pages from Facebook"}
        
        response_data = response.json()
        
        # Lấy danh sách page IDs hiện tại từ Facebook API
        current_page_ids = {page.get('id') for page in response_data.get('data', [])}
        
        # Lấy danh sách pages hiện có trong database cho account này
        existing_pages = await factory.facebook_page_manager.get_by_social_account_id(social_account_id)
        existing_page_ids = {page.get('fb_page_id') for page in existing_pages}
        
        # Xóa các pages không còn tồn tại trên Facebook
        pages_to_remove = existing_page_ids - current_page_ids
        for page_id in pages_to_remove:
            await factory.facebook_page_manager.delete_by_fb_page_id(page_id)
            logger.info(f"Removed page {page_id} from database")
        
        # Thêm hoặc cập nhật các pages từ Facebook
        for page_data in response_data.get('data', []):
            page_id = page_data.get('id')
            page_name = page_data.get('name')
            page_access_token = page_data.get('access_token')
            
            # Lấy ảnh đại diện page
            fb_page_avatar = None
            try:
                page_avatar_url = f"https://graph.facebook.com/v20.0/{page_id}/picture?redirect=false&type=large"
                avatar_response = requests.get(page_avatar_url, params={'access_token': page_access_token}, timeout=300)
                if avatar_response.status_code == 200:
                    avatar_data = avatar_response.json()
                    fb_page_avatar = avatar_data.get('data', {}).get('url')
            except Exception as e:
                logger.error(f"Error fetching page avatar for {page_id}: {str(e)}")
            
            # Kiểm tra xem page đã tồn tại chưa
            existing_page = await factory.facebook_page_manager.get_by_fb_page_id(page_id)
            
            if existing_page:
                # Cập nhật thông tin page
                await factory.facebook_page_manager.update_by_id(
                    existing_page['_id'],
                    {
                        'fb_page_name': page_name,
                        'fb_page_avatar': fb_page_avatar,
                        'fb_page_access_token': page_access_token,
                        'social_account_id': social_account_id
                    }
                )
                logger.info(f"Updated page {page_id}")
            else:
                # Tạo page mới
                await factory.facebook_page_manager.create_facebook_page(
                    fb_page_id=page_id,
                    fb_page_name=page_name,
                    fb_page_avatar=fb_page_avatar,
                    fb_page_access_token=page_access_token,
                    social_account_id=social_account_id,
                    is_connected=False,
                    webhook_verified=False
                )
                logger.info(f"Created new page {page_id}")
        
        return {"status": 200, "message": f"Reloaded pages for account {social_account_id}"}
        
    except Exception as e:
        logger.error(f"Error reloading pages for account {social_account_id}: {str(e)}")
        return {"status": 500, "message": f"Error: {str(e)}"}
        
        
def get_sender_id_info(sender_id: str, page_access_token: str):
    """
    Lấy thông tin user từ sender_id và page_access_token
    """
    try:
        url = f"https://graph.facebook.com/v20.0/{sender_id}"
        params = {
            'access_token': page_access_token,
            'fields': 'name,profile_pic,gender'
        }
        
        response = requests.get(url, params=params, timeout=300)
        if response.status_code != 200:
            return {
                "name": None,
                "profile_pic": None,
                "gender": None,
                "id": sender_id,
                "status": 400, 
                "message": "Failed to get user info from Facebook"
            }
        
        user_info = response.json()
        return user_info
        
    except Exception as e:
        return {
            "name": None,
            "profile_pic": None,
            "gender": None,
            "id": sender_id,
            "status": 500,
            "message": f"Error: {str(e)}"
        }
        

