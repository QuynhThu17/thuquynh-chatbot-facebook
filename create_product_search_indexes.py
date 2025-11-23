"""
Script tạo indexes cho MongoDB để tối ưu tìm kiếm sản phẩm
Chạy script này một lần để tạo indexes
"""
import logging
from pymongo import MongoClient, ASCENDING, TEXT
from configs import constant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_product_indexes():
    """Tạo indexes cho collection products"""
    try:
        # Kết nối trực tiếp MongoDB
        client = MongoClient(constant.MONGODB_URI)
        db = client["mekongai_social"]
        products_collection = db["products"]
        
        logger.info("🔨 Bắt đầu tạo indexes cho products collection...")
        
        # 1. Index cho company_id (thường xuyên query)
        products_collection.create_index([("company_id", ASCENDING)], name="idx_company_id")
        logger.info("✅ Created index: idx_company_id")
        
        # 2. Text index cho tìm kiếm full-text (name, description, tags)
        products_collection.create_index([
            ("name", TEXT),
            ("data.description", TEXT),
            ("data.tags", TEXT)
        ], name="idx_fulltext_search", default_language="english")
        logger.info("✅ Created index: idx_fulltext_search")
        
        # 3. Index cho SKU (tìm kiếm chính xác)
        products_collection.create_index([("sku", ASCENDING)], name="idx_sku")
        logger.info("✅ Created index: idx_sku")
        
        # 4. Index cho category
        products_collection.create_index([("data.category", ASCENDING)], name="idx_category")
        logger.info("✅ Created index: idx_category")
        
        # 5. Index cho price (lọc theo giá)
        products_collection.create_index([("pricing.price", ASCENDING)], name="idx_price")
        logger.info("✅ Created index: idx_price")
        
        # 6. Compound index cho company + price (query thường gặp)
        products_collection.create_index([
            ("company_id", ASCENDING),
            ("pricing.price", ASCENDING)
        ], name="idx_company_price")
        logger.info("✅ Created index: idx_company_price")
        
        # 7. Compound index cho company + category
        products_collection.create_index([
            ("company_id", ASCENDING),
            ("data.category", ASCENDING)
        ], name="idx_company_category")
        logger.info("✅ Created index: idx_company_category")
        
        # Hiển thị tất cả indexes
        logger.info("\n📋 Danh sách indexes hiện tại:")
        for index in products_collection.list_indexes():
            logger.info(f"   - {index['name']}: {index['key']}")
        
        logger.info("\n🎉 Hoàn thành tạo indexes cho products!")
        
        client.close()
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi tạo indexes: {e}")
        raise

if __name__ == "__main__":
    create_product_indexes()
