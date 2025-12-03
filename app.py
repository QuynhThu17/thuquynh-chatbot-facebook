from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import warnings
import uvicorn
import asyncio

# Import new comprehensive API router
from api.v1 import v1_router
# Import SuperAdmin API router
from api.super_user_managerment.api_super_user_managerment import router as super_admin_router

# Initialize MongoDB factory at startup
from controllers.data.managements import get_mongodb_factory
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.databases.mongodb.ensure_indexes import ensure_mongodb_indexes
from controllers.data.init_defaults import get_default_initializer
from controllers.auth.background_tasks import start_auth_background_tasks, stop_auth_background_tasks
from controllers.auth.rate_limit_tasks import init_rate_limit_cleanup
from configs.constant import MONGODB_URI, MONGODB_DATABASE
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", message="Api key is used with an insecure connection.")

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)"""
    # Startup
    try:
        # Create and connect MongoDB manager
        mongodb_manager = MongoDBManager(MONGODB_URI)
        connected = await mongodb_manager.connect(MONGODB_DATABASE)
        
        if connected:
            # Initialize the management factory with the connected MongoDB manager
            factory = get_mongodb_factory(mongodb_manager)
            logger.info("✅ Application started successfully with MongoDB factory initialized")
            
            # 🔧 Ensure MongoDB indexes exist (tự động tạo nếu chưa có)
            try:
                await ensure_mongodb_indexes(mongodb_manager.database)
                logger.info("✅ MongoDB indexes ensured")
            except Exception as e:
                logger.error(f"⚠️ Warning: Failed to ensure indexes: {str(e)}")
            
            # Initialize default data if needed
            try:
                initializer = await get_default_initializer(mongodb_manager)
                health_report = await initializer.check_system_health()
                
                # Kiểm tra xem có cần khởi tạo dữ liệu mặc định không
                missing_defaults = any(
                    info["count"] == 0 for info in health_report.values()
                )
                
                if missing_defaults:
                    logger.info("🔄 Some default data is missing, initializing...")
                    await initializer.init_system_defaults()
                    logger.info("✅ Default data initialization completed")
                else:
                    logger.info("✅ All default data is present")
                    
            except Exception as e:
                logger.error(f"⚠️ Warning: Default data initialization failed: {str(e)}")
                # Continue anyway, app can still function without default data
            
            # Start background tasks for email verification cleanup
            try:
                asyncio.create_task(start_auth_background_tasks())
                logger.info("✅ Auth background tasks started successfully")
            except Exception as e:
                logger.error(f"⚠️ Warning: Failed to start auth background tasks: {str(e)}")
            
            # Start rate limiting cleanup background tasks
            try:
                await init_rate_limit_cleanup(
                    rate_limit_manager=factory.rate_limit_manager,
                    interval_hours=24
                )
                logger.info("✅ Rate limiting background tasks started successfully")
            except Exception as e:
                logger.error(f"⚠️ Warning: Failed to start rate limiting background tasks: {str(e)}")
            
        else:
            logger.error("❌ Failed to connect to MongoDB during startup")
    except Exception as e:
        logger.error(f"❌ Failed to initialize MongoDB factory during startup: {str(e)}")
        # You can choose to raise exception here to prevent app from starting
        # raise e
    
    yield
    
    # Shutdown
    try:
        # Stop auth background tasks
        stop_auth_background_tasks()
        logger.info("✅ Auth background tasks stopped")
        
        # Get the factory instance if it exists
        factory = get_mongodb_factory()
        if factory and factory.db_manager:
            await factory.db_manager.disconnect()
            logger.info("✅ MongoDB connection closed successfully")
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")

app = FastAPI(
    title="HueAI - Social Media Management API",
    description="Comprehensive API for managing social media, bots, CRM, knowledge base, and more",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3002",
        "http://127.0.0.1:3002",
        "http://192.168.137.1:3002",
    ],
    allow_origin_regex=r"http://.*:3002$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include new comprehensive API endpoints
app.include_router(v1_router, prefix="/api")

# Include SuperAdmin API (🔒 Secured endpoints for MekongAI internal management)
app.include_router(super_admin_router)

# Add reset-password route directly to app (without API prefix)
from api.v1.auth.api_authentication import get_reset_password_page, get_management_factory
from fastapi import Depends
from fastapi.responses import HTMLResponse

@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(
    token: str,
    factory = Depends(get_management_factory)
):
    """Direct route for reset password page"""
    return await get_reset_password_page(token, factory)


@app.get("/")
async def hello():
    return {"status": 200, "message": "MekongAI API Services - Hello!"}


# ================================================ MAIN API ===================================================
###############################################################################################################
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=1975, timeout_keep_alive=50000)
