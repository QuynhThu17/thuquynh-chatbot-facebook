"""
Image Upload API Endpoints
Cung cấp API cho upload nhiều hình ảnh và trả về link
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import logging
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parents[3]  # Go up 3 levels to reach project root
sys.path.append(str(project_root))

# Import managers và services
from controllers.auth.auth_middleware import get_current_user
from controllers.rag.load_documents.storage.s3_service import S3Service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Image Upload"])

# Pydantic Models
class ImageUploadResult(BaseModel):
    """Kết quả upload cho một hình ảnh"""
    success: bool
    filename: str
    image_url: str | None = None
    error: str | None = None

class MultiImageUploadResponse(BaseModel):
    """Response cho việc upload nhiều hình ảnh"""
    success: bool
    message: str
    total_files: int
    successful_uploads: int
    failed_uploads: int
    results: List[ImageUploadResult]

# Dependency to get S3 service
def get_s3_service():
    """Get S3 service instance"""
    try:
        return S3Service()
    except Exception as e:
        logger.error(f"Failed to initialize S3 service: {str(e)}")
        raise HTTPException(status_code=503, detail="S3 service unavailable")

def validate_image_file(file: UploadFile) -> tuple[bool, str | None]:
    """
    Validate uploaded file is an image
    
    Args:
        file: UploadFile object
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check file size (max 10MB)
    if hasattr(file, 'size') and file.size and file.size > 10 * 1024 * 1024:
        return False, "File size too large. Maximum 10MB allowed."
    
    # Check content type
    allowed_types = [
        "image/jpeg", "image/jpg", "image/png", 
        "image/gif", "image/bmp", "image/webp"
    ]
    
    if file.content_type not in allowed_types:
        return False, f"Invalid file type: {file.content_type}. Allowed types: {', '.join(allowed_types)}"
    
    # Additional validation based on filename extension
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        if ext not in allowed_extensions:
            return False, f"Invalid file extension: {ext}. Allowed extensions: {', '.join(allowed_extensions)}"
    
    return True, None

async def upload_single_image(
    file: UploadFile,
    user_id: str,
    s3_service: S3Service,
    image_index: int
) -> ImageUploadResult:
    """
    Upload một hình ảnh lên S3
    
    Args:
        file: UploadFile object
        user_id: ID của user
        s3_service: S3 service instance
        image_index: Index của ảnh trong batch
        
    Returns:
        ImageUploadResult: Kết quả upload
    """
    filename = file.filename or f"image_{image_index}"
    
    try:
        # Validate file
        is_valid, error_msg = validate_image_file(file)
        if not is_valid:
            return ImageUploadResult(
                success=False,
                filename=filename,
                error=error_msg
            )
        
        # Read file data
        file_data = await file.read()
        
        if not file_data:
            return ImageUploadResult(
                success=False,
                filename=filename,
                error="Empty file"
            )
        
        # Validate file size after reading
        if len(file_data) > 10 * 1024 * 1024:  # 10MB
            return ImageUploadResult(
                success=False,
                filename=filename,
                error="File size too large. Maximum 10MB allowed."
            )
        
        # Upload to S3
        image_url = await s3_service.upload_image(
            image_data=file_data,
            file_name=filename,
            user_id=user_id,
            document_id="general_upload",  # Document ID chung cho upload ảnh
            image_index=image_index,
            content_type=file.content_type or "image/jpeg"
        )
        
        if not image_url:
            return ImageUploadResult(
                success=False,
                filename=filename,
                error="Failed to upload to S3"
            )
        
        logger.info(f"Successfully uploaded image {filename} for user {user_id}: {image_url}")
        
        return ImageUploadResult(
            success=True,
            filename=filename,
            image_url=image_url
        )
        
    except Exception as e:
        logger.error(f"Error uploading image {filename}: {str(e)}")
        return ImageUploadResult(
            success=False,
            filename=filename,
            error=str(e)
        )

@router.post("/upload-images", response_model=MultiImageUploadResponse)
async def upload_images(
    files: List[UploadFile] = File(..., description="Danh sách các file hình ảnh cần upload (tối đa 10 files)"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Upload nhiều hình ảnh cùng lúc và trả về danh sách link
    
    - **files**: Danh sách các file hình ảnh (hỗ trợ: jpg, jpeg, png, gif, bmp, webp)
    - **Giới hạn**: Tối đa 10 files, mỗi file tối đa 10MB
    
    Returns:
        MultiImageUploadResponse: Response với thông tin về từng file đã upload
    """
    try:
        # Kiểm tra số lượng files
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if len(files) > 10:
            raise HTTPException(
                status_code=400, 
                detail="Too many files. Maximum 10 files allowed per request"
            )
        
        user_id = current_user["user_id"]
        
        # Upload tất cả các files song song để tối ưu thời gian
        upload_tasks = [
            upload_single_image(file, user_id, s3_service, idx)
            for idx, file in enumerate(files)
        ]
        
        # Chờ tất cả tasks hoàn thành
        results = await asyncio.gather(*upload_tasks)
        
        # Đếm số lượng thành công và thất bại
        successful_uploads = sum(1 for r in results if r.success)
        failed_uploads = len(results) - successful_uploads
        
        # Xác định overall success (ít nhất 1 file upload thành công)
        overall_success = successful_uploads > 0
        
        # Tạo message tương ứng
        if successful_uploads == len(results):
            message = "All images uploaded successfully"
        elif successful_uploads > 0:
            message = f"Uploaded {successful_uploads} out of {len(results)} images successfully"
        else:
            message = "Failed to upload all images"
        
        logger.info(
            f"Multi-image upload for user {user_id}: "
            f"{successful_uploads}/{len(results)} successful"
        )
        
        return MultiImageUploadResponse(
            success=overall_success,
            message=message,
            total_files=len(results),
            successful_uploads=successful_uploads,
            failed_uploads=failed_uploads,
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-image upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process image upload request")

@router.post("/upload-image", response_model=ImageUploadResult)
async def upload_image(
    file: UploadFile = File(..., description="File hình ảnh cần upload"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Upload một hình ảnh và trả về link
    
    - **file**: File hình ảnh (hỗ trợ: jpg, jpeg, png, gif, bmp, webp)
    - **Giới hạn**: File tối đa 10MB
    
    Returns:
        ImageUploadResult: Response với link ảnh đã upload
    """
    try:
        user_id = current_user["user_id"]
        
        # Upload file
        result = await upload_single_image(file, user_id, s3_service, 0)
        
        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single image upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload image")
