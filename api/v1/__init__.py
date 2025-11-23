"""
Main API Router
Kết nối tất cả các API modules
"""

from fastapi import APIRouter
from api.v1.users.api_user_management import router as user_router
from api.v1.users.api_avatar_management import router as avatar_router
from api.v1.users.api_image_upload import router as image_upload_router
from api.v1.socials.api_social_media import router as social_router
from api.v1.bots.api_bot_management import router as bot_router
from api.v1.crm.api_crm import router as crm_router
from api.v1.knowledge.api_knowledge_management import router as knowledge_router
from api.v1.system.api_system_management import router as system_router
from api.v1.additional_features.api_additional_features import router as additional_router
from api.v1.dashboard.api_dashboard import router as dashboard_router
from api.v1.auth.api_authentication import router as auth_router
from api.v1.business.api_business_managerment import router as business_router

# Main V1 API Router
v1_router = APIRouter(prefix="/v1")

# Include all routers
v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(user_router)
v1_router.include_router(avatar_router, prefix="/avatar", tags=["Avatar Management"])
v1_router.include_router(image_upload_router, prefix="/images", tags=["Image Upload"])
v1_router.include_router(social_router)
v1_router.include_router(knowledge_router)
v1_router.include_router(bot_router)
v1_router.include_router(business_router)  # Đã bao gồm Product Enhanced endpoints
v1_router.include_router(crm_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(system_router)
# v1_router.include_router(additional_router)

# Health check endpoint
@v1_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "API is running"}

# API Info endpoint
@v1_router.get("/info")
async def api_info():
    """API information endpoint"""
    return {
        "api_version": "v1",
        "modules": [
            {
                "name": "Authentication",
                "prefix": "/auth",
                "description": "Email xác thực, đăng nhập, đăng ký, đặt lại mật khẩu"
            },
            {
                "name": "User Management",
                "prefix": "/users",
                "description": "Quản lý users, roles, balances, subscriptions, transactions"
            },
            {
                "name": "Avatar Management",
                "prefix": "/avatar",
                "description": "Quản lý avatar của user: upload, update, delete avatar"
            },
            {
                "name": "Image Upload",
                "prefix": "/images",
                "description": "Upload nhiều hình ảnh cùng lúc và lấy link ảnh"
            },
            {
                "name": "Social Media",
                "prefix": "/social",
                "description": "Quản lý social media accounts và integrations"
            },
            {
                "name": "Bot Management",
                "prefix": "/bots",
                "description": "Quản lý bot identities, procedures, và bot instances"
            },
            {
                "name": "CRM",
                "prefix": "/crm",
                "description": "Quản lý companies, contacts, products, warehouses, orders, shipments"
            },
            {
                "name": "Knowledge Management", 
                "prefix": "/knowledge",
                "description": "Quản lý documents, knowledge chunks, conversation histories, feedback với advanced document processing (PDF, Word, Excel)"
            },
            {
                "name": "System Management",
                "prefix": "/system", 
                "description": "Quản lý notifications, settings, API keys, sessions, audit logs"
            },
            {
                "name": "Additional Features",
                "prefix": "/additional",
                "description": "Usage tracking, automation, webhooks, templates, analytics"
            },
            {
                "name": "Dashboard",
                "prefix": "/dashboard", 
                "description": "Tổng quan dashboard với metrics, charts, activities"
            },
            {
                "name": "System Analytics",
                "prefix": "/system-analytics",
                "description": "System monitoring, health check, performance metrics"
            }
        ]
    }
