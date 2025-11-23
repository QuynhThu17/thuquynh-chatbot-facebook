"""
Avatar Management API Endpoints
Cung cấp API cho upload, update, delete avatar của user
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Optional, Dict, Any
from pydantic import BaseModel
import logging
import mimetypes
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parents[3]  # Go up 3 levels to reach project root
sys.path.append(str(project_root))

# Import managers và services
from controllers.data.managements import get_mongodb_factory
from controllers.auth.auth_middleware import get_current_user
from controllers.rag.load_documents.storage.s3_service import S3Service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Avatar Management"])

# Pydantic Models
class AvatarUploadResponse(BaseModel):
    success: bool
    message: str
    avatar_url: Optional[str] = None
    
class AvatarDeleteResponse(BaseModel):
    success: bool
    message: str

# Dependency to get management factory
def get_management_factory():
    """Get initialized management factory"""
    try:
        factory = get_mongodb_factory()
        if factory is None:
            raise HTTPException(status_code=503, detail="MongoDB Management Factory not initialized")
        return factory
    except Exception as e:
        logger.error(f"Failed to get management factory: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")

# Dependency to get S3 service
def get_s3_service():
    """Get S3 service instance"""
    try:
        return S3Service()
    except Exception as e:
        logger.error(f"Failed to initialize S3 service: {str(e)}")
        raise HTTPException(status_code=503, detail="S3 service unavailable")

def validate_image_file(file: UploadFile) -> None:
    """
    Validate uploaded file is an image
    
    Args:
        file: UploadFile object
        
    Raises:
        HTTPException: If file is not valid image
    """
    # Check file size (max 5MB)
    if hasattr(file, 'size') and file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size too large. Maximum 5MB allowed.")
    
    # Check content type
    allowed_types = [
        "image/jpeg", "image/jpg", "image/png", 
        "image/gif", "image/bmp", "image/webp"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Additional validation based on filename extension
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file extension. Allowed extensions: {', '.join(allowed_extensions)}"
            )

@router.post("/upload-avatar", response_model=AvatarUploadResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Upload avatar cho user hiện tại
    
    Args:
        file: Image file to upload
        current_user: Current authenticated user
        factory: MongoDB factory
        s3_service: S3 service instance
        
    Returns:
        AvatarUploadResponse: Response with success status and avatar URL
    """
    try:
        # Validate file
        validate_image_file(file)
        
        # Read file data
        file_data = await file.read()
        
        if not file_data:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Validate file size after reading
        if len(file_data) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size too large. Maximum 5MB allowed.")
        
        user_id = current_user["user_id"]
        
        # Get current user info to check for existing avatar
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete old avatar if exists
        old_avatar_url = user.get("avatar_url")
        if old_avatar_url:
            try:
                await s3_service.delete_file(old_avatar_url)
                logger.info(f"Deleted old avatar for user {user_id}: {old_avatar_url}")
            except Exception as e:
                logger.warning(f"Failed to delete old avatar {old_avatar_url}: {str(e)}")
        
        # Upload new avatar to S3
        avatar_url = await s3_service.upload_image(
            image_data=file_data,
            file_name=file.filename or "avatar",
            user_id=user_id,
            document_id="avatar",  # Special document ID for avatars
            image_index=0,
            content_type=file.content_type or "image/jpeg"
        )
        
        if not avatar_url:
            raise HTTPException(status_code=500, detail="Failed to upload avatar to S3")
        
        # Update user's avatar_url in database
        await factory.user_manager.update_by_id(
            user_id,
            {"avatar_url": avatar_url}
        )
        
        logger.info(f"Successfully uploaded avatar for user {user_id}: {avatar_url}")
        
        return AvatarUploadResponse(
            success=True,
            message="Avatar uploaded successfully",
            avatar_url=avatar_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to upload avatar")

@router.put("/update-avatar", response_model=AvatarUploadResponse)
async def update_avatar(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Update avatar cho user hiện tại (tương tự upload nhưng explicitly cho update)
    
    Args:
        file: New image file to upload
        current_user: Current authenticated user
        factory: MongoDB factory
        s3_service: S3 service instance
        
    Returns:
        AvatarUploadResponse: Response with success status and new avatar URL
    """
    try:
        # Validate file
        validate_image_file(file)
        
        # Read file data
        file_data = await file.read()
        
        if not file_data:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Validate file size after reading
        if len(file_data) > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size too large. Maximum 5MB allowed.")
        
        user_id = current_user["user_id"]
        
        # Get current user info
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete old avatar if exists
        old_avatar_url = user.get("avatar_url")
        if old_avatar_url:
            try:
                await s3_service.delete_file(old_avatar_url)
                logger.info(f"Deleted old avatar for user {user_id}: {old_avatar_url}")
            except Exception as e:
                logger.warning(f"Failed to delete old avatar {old_avatar_url}: {str(e)}")
        
        # Upload new avatar to S3
        new_avatar_url = await s3_service.upload_image(
            image_data=file_data,
            file_name=file.filename or "avatar",
            user_id=user_id,
            document_id="avatar",  # Special document ID for avatars
            image_index=0,
            content_type=file.content_type or "image/jpeg"
        )
        
        if not new_avatar_url:
            raise HTTPException(status_code=500, detail="Failed to upload new avatar to S3")
        
        # Update user's avatar_url in database
        await factory.user_manager.update_by_id(
            user_id,
            {"avatar_url": new_avatar_url}
        )
        
        logger.info(f"Successfully updated avatar for user {user_id}: {new_avatar_url}")
        
        return AvatarUploadResponse(
            success=True,
            message="Avatar updated successfully",
            avatar_url=new_avatar_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar update error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update avatar")

@router.delete("/delete-avatar", response_model=AvatarDeleteResponse)
async def delete_avatar(
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Delete avatar của user hiện tại
    
    Args:
        current_user: Current authenticated user
        factory: MongoDB factory
        s3_service: S3 service instance
        
    Returns:
        AvatarDeleteResponse: Response with success status
    """
    try:
        user_id = current_user["user_id"]
        
        # Get current user info
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has avatar
        avatar_url = user.get("avatar_url")
        if not avatar_url:
            return AvatarDeleteResponse(
                success=True,
                message="No avatar to delete"
            )
        
        # Delete avatar from S3
        deleted = await s3_service.delete_file(avatar_url)
        
        if not deleted:
            logger.warning(f"Failed to delete avatar from S3: {avatar_url}")
            # Continue to remove from database anyway
        
        # Remove avatar_url from user in database
        await factory.user_manager.update_by_id(
            user_id,
            {"avatar_url": None}
        )
        
        logger.info(f"Successfully deleted avatar for user {user_id}: {avatar_url}")
        
        return AvatarDeleteResponse(
            success=True,
            message="Avatar deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Avatar delete error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete avatar")

@router.get("/avatar-info")
async def get_avatar_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy thông tin avatar hiện tại của user
    
    Args:
        current_user: Current authenticated user
        factory: MongoDB factory
        
    Returns:
        Dict: Avatar information
    """
    try:
        user_id = current_user["user_id"]
        
        # Get current user info
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        avatar_url = user.get("avatar_url")
        
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "avatar_url": avatar_url,
                "has_avatar": avatar_url is not None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get avatar info error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get avatar info")
