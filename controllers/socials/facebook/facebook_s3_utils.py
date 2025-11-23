"""
Facebook S3 utilities
Utilities để tải và upload avatar Facebook lên S3
"""

import requests
import asyncio
import uuid
from datetime import datetime
from typing import Optional
import logging

# Import S3 service
import sys
from pathlib import Path
project_root = Path(__file__).parents[3]
sys.path.append(str(project_root))

from controllers.rag.load_documents.storage.s3_service import S3Service

logger = logging.getLogger(__name__)

async def download_and_upload_facebook_avatar(avatar_url: str, user_id: str, 
                                           avatar_type: str = "user") -> Optional[str]:
    """
    Tải avatar từ Facebook URL và upload lên S3
    
    Args:
        avatar_url: URL avatar từ Facebook
        user_id: ID của user
        avatar_type: Loại avatar ("user" hoặc "page")
        
    Returns:
        str: S3 URL của avatar đã upload, None nếu fail
    """
    try:
        # Tải avatar từ Facebook
        response = requests.get(avatar_url, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to download avatar from Facebook: {response.status_code}")
            return None
            
        avatar_data = response.content
        
        if not avatar_data:
            logger.error("Empty avatar data from Facebook")
            return None
        
        # Khởi tạo S3 service
        s3_service = S3Service()
        
        # Tạo tên file unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Xác định content type từ response header hoặc default
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        # Xác định extension từ content type
        if 'jpeg' in content_type or 'jpg' in content_type:
            extension = '.jpg'
        elif 'png' in content_type:
            extension = '.png'
        elif 'gif' in content_type:
            extension = '.gif'
        elif 'webp' in content_type:
            extension = '.webp'
        else:
            extension = '.jpg'  # default
            
        filename = f"facebook_{avatar_type}_avatar_{timestamp}_{unique_id}{extension}"
        
        # Upload lên S3 với đường dẫn riêng cho Facebook avatars
        s3_key = f"social_avatars/facebook/{avatar_type}s/{user_id}/{filename}"
        
        try:
            s3_service.s3_client.put_object(
                Bucket=s3_service.bucket_name,
                Key=s3_key,
                Body=avatar_data,
                ContentType=content_type,
                ServerSideEncryption='AES256',
                Metadata={
                    'user_id': user_id,
                    'avatar_type': avatar_type,
                    'source': 'facebook',
                    'original_url': avatar_url,
                    'uploaded_at': datetime.now().isoformat()
                }
            )
            
            # Tạo URL với format đúng
            s3_url = f"https://{s3_service.bucket_name}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded Facebook {avatar_type} avatar to S3: {s3_url}")
            
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading avatar to S3: {str(e)}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Error downloading avatar from Facebook: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in download_and_upload_facebook_avatar: {str(e)}")
        return None

async def download_and_upload_facebook_page_avatar(avatar_url: str, user_id: str, 
                                                 page_id: str) -> Optional[str]:
    """
    Tải avatar page từ Facebook URL và upload lên S3
    
    Args:
        avatar_url: URL avatar page từ Facebook
        user_id: ID của user sở hữu page
        page_id: ID của Facebook page
        
    Returns:
        str: S3 URL của avatar đã upload, None nếu fail
    """
    try:
        # Tải avatar từ Facebook
        response = requests.get(avatar_url, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Failed to download page avatar from Facebook: {response.status_code}")
            return None
            
        avatar_data = response.content
        
        if not avatar_data:
            logger.error("Empty page avatar data from Facebook")
            return None
        
        # Khởi tạo S3 service
        s3_service = S3Service()
        
        # Tạo tên file unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Xác định content type từ response header hoặc default
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        # Xác định extension từ content type
        if 'jpeg' in content_type or 'jpg' in content_type:
            extension = '.jpg'
        elif 'png' in content_type:
            extension = '.png'
        elif 'gif' in content_type:
            extension = '.gif'
        elif 'webp' in content_type:
            extension = '.webp'
        else:
            extension = '.jpg'  # default
            
        filename = f"facebook_page_{page_id}_{timestamp}_{unique_id}{extension}"
        
        # Upload lên S3 với đường dẫn riêng cho Facebook page avatars
        s3_key = f"social_avatars/facebook/pages/{user_id}/{page_id}/{filename}"
        
        try:
            s3_service.s3_client.put_object(
                Bucket=s3_service.bucket_name,
                Key=s3_key,
                Body=avatar_data,
                ContentType=content_type,
                ServerSideEncryption='AES256',
                Metadata={
                    'user_id': user_id,
                    'page_id': page_id,
                    'avatar_type': 'page',
                    'source': 'facebook',
                    'original_url': avatar_url,
                    'uploaded_at': datetime.now().isoformat()
                }
            )
            
            # Tạo URL với format đúng
            s3_url = f"https://{s3_service.bucket_name}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded Facebook page avatar to S3: {s3_url}")
            
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading page avatar to S3: {str(e)}")
            return None
            
    except requests.RequestException as e:
        logger.error(f"Error downloading page avatar from Facebook: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in download_and_upload_facebook_page_avatar: {str(e)}")
        return None
