"""
AWS S3 Service
Dịch vụ upload và quản lý files trên AWS S3
"""

import asyncio
import boto3
import logging
import unicodedata
import re
import base64
from typing import Optional, Dict, Any
from io import BytesIO
from datetime import datetime
import uuid
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parents[4]  # Go up 4 levels to reach project root
sys.path.append(str(project_root))

from botocore.exceptions import ClientError, NoCredentialsError

from configs.constant import (
    AWS_BUCKET_NAME,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_DEFAULT_REGION
)

logger = logging.getLogger(__name__)

class S3Service:
    """
    Service để tương tác với AWS S3
    """
    
    def __init__(self):
        """Khởi tạo S3 client"""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                region_name=AWS_DEFAULT_REGION
            )
            self.bucket_name = AWS_BUCKET_NAME
            self._validate_credentials()
            
        except Exception as e:
            logger.error(f"Error initializing S3 client: {str(e)}")
            raise
    
    def _validate_credentials(self):
        """Validate AWS credentials"""
        try:
            self.s3_client.list_buckets()
            logger.info("AWS S3 credentials validated successfully")
        except NoCredentialsError:
            logger.error("AWS credentials not found")
            raise
        except ClientError as e:
            logger.error(f"AWS credentials invalid: {str(e)}")
            raise
    
    def _sanitize_filename_for_ascii(self, filename: str) -> str:
        """
        Chuyển đổi filename có ký tự đặc biệt thành ASCII-only cho S3 metadata
        
        Args:
            filename: Tên file gốc có thể chứa ký tự unicode
            
        Returns:
            str: Tên file chỉ chứa ký tự ASCII
        """
        # Chuyển đổi unicode thành ASCII gần nhất
        # VD: "ĐỐI TÁC" -> "DOI TAC" 
        ascii_filename = unicodedata.normalize('NFD', filename)
        ascii_filename = ''.join(c for c in ascii_filename if unicodedata.category(c) != 'Mn')
        
        # Loại bỏ các ký tự không phải ASCII
        ascii_filename = ascii_filename.encode('ascii', 'ignore').decode('ascii')
        
        # Thay thế các ký tự đặc biệt còn lại bằng underscore
        ascii_filename = re.sub(r'[^\w\s.-]', '_', ascii_filename)
        
        # Loại bỏ multiple spaces/underscores liên tiếp
        ascii_filename = re.sub(r'[\s_]+', '_', ascii_filename)
        
        return ascii_filename.strip('_')

    def _encode_filename_for_metadata(self, filename: str) -> str:
        """
        Encode filename với UTF-8 characters thành ASCII-safe string cho S3 metadata
        
        Args:
            filename: Tên file gốc có thể chứa ký tự unicode
            
        Returns:
            str: Base64 encoded filename (ASCII-safe)
        """
        try:
            # Encode filename to UTF-8 bytes then base64 encode to ASCII
            utf8_bytes = filename.encode('utf-8')
            base64_encoded = base64.b64encode(utf8_bytes).decode('ascii')
            return base64_encoded
        except Exception as e:
            logger.warning(f"Error encoding filename {filename}: {str(e)}")
            # Fallback to sanitized ASCII version
            return self._sanitize_filename_for_ascii(filename)
    
    def _decode_filename_from_metadata(self, encoded_filename: str) -> str:
        """
        Decode filename từ base64 encoded string
        
        Args:
            encoded_filename: Base64 encoded filename
            
        Returns:
            str: Original filename
        """
        try:
            decoded_bytes = base64.b64decode(encoded_filename.encode('ascii'))
            return decoded_bytes.decode('utf-8')
        except Exception as e:
            logger.warning(f"Error decoding filename {encoded_filename}: {str(e)}")
            # Return as-is if can't decode
            return encoded_filename

    async def upload_image(self, image_data: bytes, file_name: str, 
                          user_id: str, document_id: str, 
                          image_index: int, content_type: str = "image/jpeg") -> Optional[str]:
        """
        Upload ảnh lên S3
        
        Args:
            image_data: Dữ liệu ảnh dạng bytes
            file_name: Tên file gốc
            user_id: ID người dùng
            document_id: ID document
            image_index: Thứ tự ảnh trong document
            content_type: MIME type của ảnh
            
        Returns:
            str: URL của ảnh trên S3, None nếu fail
        """
        try:
            # Tạo unique file name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            file_extension = self._get_extension_from_content_type(content_type)
            
            s3_key = f"documents/{user_id}/{document_id}/images/{timestamp}_{unique_id}_{image_index}{file_extension}"
            
            # Sanitize filename for ASCII-only metadata
            ascii_filename = self._sanitize_filename_for_ascii(file_name)
            
            # Encode original UTF-8 filename for metadata storage
            encoded_original_filename = self._encode_filename_for_metadata(file_name)
            
            # Upload file (public access via bucket policy)
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                ContentType=content_type,
                ServerSideEncryption='AES256',  # Mã hóa
                Metadata={
                    'user_id': user_id,
                    'document_id': document_id,
                    'image_index': str(image_index),
                    'original_filename': ascii_filename,  # ASCII-only version
                    'original_filename_encoded': encoded_original_filename,  # Base64 encoded UTF-8 version
                    'uploaded_at': datetime.now().isoformat()
                }
            )
            
            # Tạo URL với format đúng (virtual-hosted style)
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded image to S3: {url}")
            
            return url
            
        except Exception as e:
            logger.error(f"Error uploading image to S3: {str(e)}")
            return None
    
    async def upload_document(self, file_data: bytes, file_name: str,
                            user_id: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        Upload document gốc lên S3
        
        Args:
            file_data: Dữ liệu file
            file_name: Tên file
            user_id: ID người dùng
            content_type: MIME type
            
        Returns:
            str: URL của file trên S3
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            _, file_extension = os.path.splitext(file_name)
            
            s3_key = f"documents/{user_id}/originals/{timestamp}_{unique_id}_{file_name}"
            
            # Sanitize filename for ASCII-only metadata
            ascii_filename = self._sanitize_filename_for_ascii(file_name)
            
            # Encode original UTF-8 filename for metadata storage
            encoded_original_filename = self._encode_filename_for_metadata(file_name)
            
            await asyncio.to_thread(
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType=content_type,
                ServerSideEncryption='AES256',
                Metadata={
                    'user_id': user_id,
                    'original_filename': ascii_filename,  # ASCII-only version
                    'original_filename_encoded': encoded_original_filename,  # Base64 encoded UTF-8 version
                    'uploaded_at': datetime.now().isoformat()
                }
            )
            
            # Tạo URL với format đúng (virtual-hosted style)
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            
            logger.info(f"Successfully uploaded document to S3: {url}")
            
            return url
            
        except Exception as e:
            logger.error(f"Error uploading document to S3: {str(e)}")
            return None
    
    def _get_extension_from_content_type(self, content_type: str) -> str:
        """
        Lấy extension từ content type
        
        Args:
            content_type: MIME type
            
        Returns:
            str: File extension
        """
        content_type_map = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg", 
            "image/png": ".png",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
            "image/tiff": ".tiff",
            "image/webp": ".webp"
        }
        
        return content_type_map.get(content_type.lower(), ".jpg")
    
    async def delete_file(self, s3_url: str) -> bool:
        """
        Xóa file từ S3
        
        Args:
            s3_url: URL của file trên S3
            
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            # Extract S3 key from URL - handle virtual-hosted style
            if f"https://{self.bucket_name}.s3.amazonaws.com/" in s3_url:
                s3_key = s3_url.replace(f"https://{self.bucket_name}.s3.amazonaws.com/", "")
            elif f"https://{self.bucket_name}.s3" in s3_url:
                # Handle other formats as fallback
                s3_key = s3_url.split(f"{self.bucket_name}/")[-1] if f"{self.bucket_name}/" in s3_url else s3_url.split('/')[-1]
            else:
                # Extract key from path-style URL
                s3_key = s3_url.split(f"{self.bucket_name}/")[-1] if f"{self.bucket_name}/" in s3_url else s3_url.split('/')[-1]
            
            await asyncio.to_thread(
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Successfully deleted file from S3: {s3_url}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting file from S3: {str(e)}")
            return False
    
    async def get_file_info(self, s3_url: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin file từ S3
        
        Args:
            s3_url: URL của file
            
        Returns:
            Dict: Thông tin file
        """
        try:
            # Extract S3 key from URL - handle virtual-hosted style
            if f"https://{self.bucket_name}.s3.amazonaws.com/" in s3_url:
                s3_key = s3_url.replace(f"https://{self.bucket_name}.s3.amazonaws.com/", "")
            elif f"https://{self.bucket_name}.s3" in s3_url:
                # Handle other formats as fallback
                s3_key = s3_url.split(f"{self.bucket_name}/")[-1] if f"{self.bucket_name}/" in s3_url else s3_url.split('/')[-1]
            else:
                # Extract key from path-style URL
                s3_key = s3_url.split(f"{self.bucket_name}/")[-1] if f"{self.bucket_name}/" in s3_url else s3_url.split('/')[-1]
            
            response = await asyncio.to_thread(
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            return {
                "size": response.get('ContentLength'),
                "last_modified": response.get('LastModified'),
                "content_type": response.get('ContentType'),
                "metadata": response.get('Metadata', {})
            }
            
        except Exception as e:
            logger.error(f"Error getting file info from S3: {str(e)}")
            return None

    def setup_bucket_for_public_access(self):
        """
        Cấu hình bucket để cho phép public access
        Chỉ cần chạy 1 lần khi setup bucket
        """
        try:
            # 1. Disable Block Public Access
            self.s3_client.delete_public_access_block(Bucket=self.bucket_name)
            logger.info("Disabled public access block")
            
            # 2. Apply bucket policy
            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/*"
                    }
                ]
            }
            
            import json
            self.s3_client.put_bucket_policy(
                Bucket=self.bucket_name,
                Policy=json.dumps(bucket_policy)
            )
            logger.info("Applied bucket policy for public read access")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting up bucket for public access: {str(e)}")
            return False

    async def test_public_access(self, s3_url: str) -> bool:
        """
        Test xem file có thể truy cập public không
        
        Args:
            s3_url: URL của file trên S3
            
        Returns:
            bool: True nếu file accessible public
        """
        try:
            import requests
            response = await asyncio.to_thread(requests.head, s3_url, timeout=10)
            accessible = response.status_code == 200
            
            if accessible:
                logger.info(f"File is publicly accessible: {s3_url}")
            else:
                logger.warning(f"File not publicly accessible: {s3_url} (Status: {response.status_code})")
                
            return accessible
            
        except Exception as e:
            logger.error(f"Error testing public access for {s3_url}: {str(e)}")
            return False

    def get_original_filename_from_metadata(self, metadata: Dict[str, str]) -> str:
        """
        Lấy original filename từ S3 metadata
        
        Args:
            metadata: S3 metadata dictionary
            
        Returns:
            str: Original filename
        """
        # Try to get encoded filename first
        if 'original_filename_encoded' in metadata:
            return self._decode_filename_from_metadata(metadata['original_filename_encoded'])
        
        # Fallback to ASCII version
        if 'original_filename' in metadata:
            return metadata['original_filename']
            
        # Last fallback
        return "unknown_filename"
