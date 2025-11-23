"""
Script để tạo MongoDB indexes cho Facebook Messenger Tools
Chạy script này để tối ưu tốc độ query
"""

import pymongo
from configs import constant
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_facebook_messenger_indexes():
    """Tạo tất cả indexes cần thiết cho Facebook Messenger Tools"""
    
    try:
        # Kết nối MongoDB
        client = pymongo.MongoClient(constant.MONGODB_URI)
        db = client["mekongai_social"]
        
        logger.info("🔍 Bắt đầu tạo indexes...")
        
        # 1. Customers collection indexes
        logger.info("📝 Tạo indexes cho customers collection...")
        customers = db["customers"]
        
        # Compound index cho find_customer query
        try:
            customers.create_index(
                [("social_page_id", 1), ("customer_id", 1)],
                name="idx_customer_lookup",
                background=True
            )
            logger.info("✅ Created index: customers.idx_customer_lookup")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Index cho social_id filter
        try:
            customers.create_index(
                [("social_id", 1), ("social_page_id", 1), ("customer_id", 1)],
                name="idx_customer_social_lookup",
                background=True
            )
            logger.info("✅ Created index: customers.idx_customer_social_lookup")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # 2. Orders collection indexes
        logger.info("📝 Tạo indexes cho orders collection...")
        orders = db["orders"]
        
        # Compound index cho find_orders query (với sort by created_at)
        try:
            orders.create_index(
                [("social_page_id", 1), ("customer_id", 1), ("created_at", -1)],
                name="idx_order_lookup_sorted",
                background=True
            )
            logger.info("✅ Created index: orders.idx_order_lookup_sorted")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Index cho social_id filter
        try:
            orders.create_index(
                [("social_id", 1), ("social_page_id", 1), ("customer_id", 1)],
                name="idx_order_social_lookup",
                background=True
            )
            logger.info("✅ Created index: orders.idx_order_social_lookup")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Index cho status filter
        try:
            orders.create_index(
                [("status", 1), ("created_at", -1)],
                name="idx_order_status",
                background=True
            )
            logger.info("✅ Created index: orders.idx_order_status")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # 3. Products collection indexes
        logger.info("📝 Tạo indexes cho products collection...")
        products = db["products"]
        
        # Index cho company_id filter
        try:
            products.create_index(
                [("company_id", 1)],
                name="idx_product_company",
                background=True
            )
            logger.info("✅ Created index: products.idx_product_company")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Index cho SKU lookup
        try:
            products.create_index(
                [("sku", 1)],
                name="idx_product_sku",
                background=True
            )
            logger.info("✅ Created index: products.idx_product_sku")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Compound index cho company + category
        try:
            products.create_index(
                [("company_id", 1), ("data.category", 1)],
                name="idx_product_company_category",
                background=True
            )
            logger.info("✅ Created index: products.idx_product_company_category")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Compound index cho company + price range
        try:
            products.create_index(
                [("company_id", 1), ("pricing.price", 1)],
                name="idx_product_company_price",
                background=True
            )
            logger.info("✅ Created index: products.idx_product_company_price")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Text index cho search
        try:
            products.create_index(
                [("name", "text"), ("sku", "text"), ("data.description", "text"), ("data.tags", "text")],
                name="idx_product_text_search",
                weights={
                    "name": 10,      # Tên quan trọng nhất
                    "sku": 8,        # SKU quan trọng thứ 2
                    "data.tags": 5,  # Tags quan trọng thứ 3
                    "data.description": 3  # Mô tả ít quan trọng nhất
                },
                background=True
            )
            logger.info("✅ Created index: products.idx_product_text_search")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # 4. Warehouses collection indexes
        logger.info("📝 Tạo indexes cho warehouses collection...")
        warehouses = db["warehouses"]
        
        # Index cho company_id filter
        try:
            warehouses.create_index(
                [("company_id", 1)],
                name="idx_warehouse_company",
                background=True
            )
            logger.info("✅ Created index: warehouses.idx_warehouse_company")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Index cho inventory product lookup
        try:
            warehouses.create_index(
                [("inventory.product_id", 1)],
                name="idx_warehouse_inventory_product",
                background=True
            )
            logger.info("✅ Created index: warehouses.idx_warehouse_inventory_product")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        # Compound index cho company + inventory
        try:
            warehouses.create_index(
                [("company_id", 1), ("inventory.product_id", 1)],
                name="idx_warehouse_company_inventory",
                background=True
            )
            logger.info("✅ Created index: warehouses.idx_warehouse_company_inventory")
        except Exception as e:
            logger.warning(f"⚠️ Index already exists or error: {e}")
        
        logger.info("\n✅ Hoàn thành tạo indexes!")
        
        # Hiển thị thống kê indexes
        logger.info("\n📊 Thống kê indexes:")
        for collection_name in ["customers", "orders", "products", "warehouses"]:
            collection = db[collection_name]
            indexes = list(collection.list_indexes())
            logger.info(f"\n{collection_name}: {len(indexes)} indexes")
            for idx in indexes:
                logger.info(f"  - {idx['name']}: {idx.get('key', {})}")
        
        client.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi tạo indexes: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Facebook Messenger Tools - Index Creation Script")
    logger.info("=" * 60)
    logger.info("")
    
    success = create_facebook_messenger_indexes()
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("✅ Indexes đã được tạo thành công!")
        logger.info("🚀 Hệ thống sẵn sàng với hiệu năng tối ưu!")
        logger.info("=" * 60)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ Có lỗi xảy ra khi tạo indexes!")
        logger.error("=" * 60)
