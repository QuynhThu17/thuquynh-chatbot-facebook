"""
Script để thêm các trường mặc định cho customers collection
- auto_reply: bool (mặc định True)
- status: str (mặc định "Tương tác")
- tags: list (mặc định [])
"""

import asyncio
from controllers.databases.mongodb.mongodb_manager import MongoDBManager
from configs.environment import env_vars
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def update_customers_defaults():
    """Update customers collection với các trường mặc định"""
    try:
        # Khởi tạo MongoDB manager
        db_manager = MongoDBManager(
            connection_string=env_vars.MONGODB_CONNECTION_STRING,
            database_name=env_vars.MONGODB_DATABASE_NAME
        )
        
        # Kết nối database
        await db_manager.connect()
        collection = db_manager.db["customers"]
        
        # Đếm số lượng documents cần update
        count_missing_auto_reply = await collection.count_documents({"auto_reply": {"$exists": False}})
        count_missing_status = await collection.count_documents({"status": {"$exists": False}})
        count_missing_tags = await collection.count_documents({"tags": {"$exists": False}})
        
        logger.info(f"Tìm thấy {count_missing_auto_reply} customers thiếu trường auto_reply")
        logger.info(f"Tìm thấy {count_missing_status} customers thiếu trường status")
        logger.info(f"Tìm thấy {count_missing_tags} customers thiếu trường tags")
        
        # Update các documents thiếu auto_reply
        if count_missing_auto_reply > 0:
            result_auto_reply = await collection.update_many(
                {"auto_reply": {"$exists": False}},
                {"$set": {"auto_reply": True}}
            )
            logger.info(f"Đã cập nhật auto_reply cho {result_auto_reply.modified_count} customers")
        
        # Update các documents thiếu status
        if count_missing_status > 0:
            result_status = await collection.update_many(
                {"status": {"$exists": False}},
                {"$set": {"status": "Tương tác"}}
            )
            logger.info(f"Đã cập nhật status cho {result_status.modified_count} customers")
        
        # Update các documents thiếu tags
        if count_missing_tags > 0:
            result_tags = await collection.update_many(
                {"tags": {"$exists": False}},
                {"$set": {"tags": []}}
            )
            logger.info(f"Đã cập nhật tags cho {result_tags.modified_count} customers")
        
        logger.info("Hoàn thành việc cập nhật customers!")
        
        # Đóng kết nối
        await db_manager.close()
        
    except Exception as e:
        logger.error(f"Lỗi khi cập nhật customers: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(update_customers_defaults())
