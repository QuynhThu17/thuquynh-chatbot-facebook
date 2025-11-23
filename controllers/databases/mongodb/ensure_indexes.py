"""
Auto-ensure MongoDB indexes on application startup
Tự động kiểm tra và tạo indexes khi app khởi động
"""
import logging
from pymongo import ASCENDING, TEXT, DESCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)

class MongoDBIndexEnsurer:
    """Class để đảm bảo indexes tồn tại trong MongoDB (Async-compatible)"""
    
    def __init__(self, database):
        """
        Args:
            database: MongoDB database instance (Motor AsyncIOMotorDatabase hoặc PyMongo Database)
        """
        self.database = database
        self.is_async = hasattr(database, 'command')  # Check if it's Motor async
        self.indexes_config = {
            "products": [
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_fulltext_search",
                    "keys": [
                        ("name", TEXT),
                        ("data.description", TEXT),
                        ("data.tags", TEXT)
                    ],
                    "unique": False,
                    "default_language": "english"
                },
                {
                    "name": "idx_sku",
                    "keys": [("sku", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_category",
                    "keys": [("data.category", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_price",
                    "keys": [("pricing.price", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_company_price",
                    "keys": [
                        ("company_id", ASCENDING),
                        ("pricing.price", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_company_category",
                    "keys": [
                        ("company_id", ASCENDING),
                        ("data.category", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_user_created",
                    "keys": [
                        ("user_id", ASCENDING),
                        ("created_at", DESCENDING)
                    ],
                    "unique": False
                }
            ],
            "customers": [
                {
                    "name": "idx_social_customer",
                    "keys": [
                        ("social_id", ASCENDING),
                        ("social_page_id", ASCENDING),
                        ("customer_id", ASCENDING)
                    ],
                    "unique": True
                },
                {
                    "name": "idx_customer_lookup",
                    "keys": [
                        ("social_page_id", ASCENDING),
                        ("customer_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_phone",
                    "keys": [("phone", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_email",
                    "keys": [("email", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_created_at",
                    "keys": [("created_at", DESCENDING)],
                    "unique": False
                }
            ],
            "orders": [
                {
                    "name": "idx_social_order",
                    "keys": [
                        ("social_id", ASCENDING),
                        ("social_page_id", ASCENDING),
                        ("customer_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_page_customer",
                    "keys": [
                        ("social_page_id", ASCENDING),
                        ("customer_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_order_lookup_sorted",
                    "keys": [
                        ("social_page_id", ASCENDING),
                        ("customer_id", ASCENDING),
                        ("created_at", DESCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_status",
                    "keys": [("status", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_created",
                    "keys": [("created_at", DESCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_status_created",
                    "keys": [
                        ("status", ASCENDING),
                        ("created_at", DESCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_payment_status",
                    "keys": [("payment_status", ASCENDING)],
                    "unique": False
                }
            ],
            "warehouses": [
                {
                    "name": "idx_company",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_product_inventory",
                    "keys": [("inventory.product_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_company_inventory",
                    "keys": [
                        ("company_id", ASCENDING),
                        ("inventory.product_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_warehouse_name",
                    "keys": [("name", ASCENDING)],
                    "unique": False
                }
            ],
            "knowledge_chunks": [
                {
                    "name": "idx_user_source",
                    "keys": [
                        ("user_id", ASCENDING),
                        ("source_info.source_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_chunk_type",
                    "keys": [("chunk_type", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_source_type",
                    "keys": [("source_info.type", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_embedding_exists",
                    "keys": [("content_embedding", ASCENDING)],
                    "unique": False,
                    "sparse": True
                }
            ],
            "bots": [
                {
                    "name": "idx_user_id",
                    "keys": [("user_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_social_page",
                    "keys": [
                        ("social_id", ASCENDING),
                        ("social_page_id", ASCENDING)
                    ],
                    "unique": True,
                    "sparse": True  # Chỉ index documents có cả 2 fields (tránh lỗi với null values)
                },
                {
                    "name": "idx_status",
                    "keys": [("status", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_created_at",
                    "keys": [("created_at", DESCENDING)],
                    "unique": False
                }
            ],
            "conversations": [
                {
                    "name": "idx_bot_sender",
                    "keys": [
                        ("bot_id", ASCENDING),
                        ("sender_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_page_sender",
                    "keys": [
                        ("page_id", ASCENDING),
                        ("sender_id", ASCENDING)
                    ],
                    "unique": False
                },
                {
                    "name": "idx_updated_at",
                    "keys": [("updated_at", DESCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_status",
                    "keys": [("status", ASCENDING)],
                    "unique": False
                }
            ],
            "users": [
                {
                    "name": "idx_email",
                    "keys": [("email", ASCENDING)],
                    "unique": True
                },
                {
                    "name": "idx_username",
                    "keys": [("username", ASCENDING)],
                    "unique": True,
                    "sparse": True
                },
                {
                    "name": "idx_company_id",
                    "keys": [("company_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_role",
                    "keys": [("role", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_status",
                    "keys": [("status", ASCENDING)],
                    "unique": False
                }
            ],
            "companies": [
                {
                    "name": "idx_owner_id",
                    "keys": [("owner_id", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_name",
                    "keys": [("name", ASCENDING)],
                    "unique": False
                },
                {
                    "name": "idx_status",
                    "keys": [("status", ASCENDING)],
                    "unique": False
                }
            ]
        }
    
    async def ensure_all_indexes(self):
        """Đảm bảo tất cả indexes tồn tại cho tất cả collections (Async)"""
        try:
            logger.info("🔍 Kiểm tra và tạo indexes cho MongoDB...")
            
            total_created = 0
            total_existing = 0
            
            for collection_name, indexes in self.indexes_config.items():
                created, existing = await self._ensure_collection_indexes(collection_name, indexes)
                total_created += created
                total_existing += existing
            
            if total_created > 0:
                logger.info(f"✅ Đã tạo {total_created} indexes mới")
            if total_existing > 0:
                logger.info(f"ℹ️  {total_existing} indexes đã tồn tại")
            
            logger.info("🎉 Hoàn thành kiểm tra indexes!")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi ensure indexes: {e}")
    
    async def _ensure_collection_indexes(self, collection_name: str, indexes: list) -> tuple:
        """
        Đảm bảo indexes cho một collection (Async)
        
        Returns:
            (created_count, existing_count): Số lượng indexes được tạo mới và đã tồn tại
        """
        try:
            collection = self.database[collection_name]
            
            # Get existing indexes (async)
            existing_indexes_cursor = collection.list_indexes()
            existing_indexes = set()
            async for idx in existing_indexes_cursor:
                existing_indexes.add(idx['name'])
            
            created_count = 0
            existing_count = 0
            
            for index_config in indexes:
                index_name = index_config["name"]
                
                # Kiểm tra xem index đã tồn tại chưa
                if index_name in existing_indexes:
                    existing_count += 1
                    logger.debug(f"✓ Index '{index_name}' đã tồn tại trong '{collection_name}'")
                    continue
                
                # Tạo index mới
                try:
                    keys = index_config["keys"]
                    options = {
                        "name": index_name,
                        "background": True  # Tạo index trong background
                    }
                    
                    # Thêm các options khác nếu có
                    if "unique" in index_config and index_config["unique"]:
                        options["unique"] = True
                    
                    if "sparse" in index_config and index_config["sparse"]:
                        options["sparse"] = True
                    
                    if "default_language" in index_config:
                        options["default_language"] = index_config["default_language"]
                    
                    await collection.create_index(keys, **options)
                    created_count += 1
                    logger.info(f"✅ Đã tạo index '{index_name}' cho '{collection_name}'")
                    
                except OperationFailure as e:
                    if "already exists" in str(e).lower():
                        existing_count += 1
                        logger.debug(f"✓ Index '{index_name}' đã tồn tại")
                    else:
                        logger.error(f"❌ Lỗi tạo index '{index_name}': {e}")
            
            return created_count, existing_count
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi ensure indexes cho '{collection_name}': {e}")
            return 0, 0
    
    async def check_index_exists(self, collection_name: str, index_name: str) -> bool:
        """
        Kiểm tra xem index có tồn tại không (Async)
        
        Args:
            collection_name: Tên collection
            index_name: Tên index
            
        Returns:
            bool: True nếu index tồn tại
        """
        try:
            collection = self.database[collection_name]
            existing_indexes_cursor = collection.list_indexes()
            existing_indexes = set()
            async for idx in existing_indexes_cursor:
                existing_indexes.add(idx['name'])
            return index_name in existing_indexes
        except Exception as e:
            logger.error(f"❌ Lỗi khi kiểm tra index: {e}")
            return False
    
    async def drop_index(self, collection_name: str, index_name: str) -> bool:
        """
        Xóa một index (Async)
        
        Args:
            collection_name: Tên collection
            index_name: Tên index
            
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            collection = self.database[collection_name]
            await collection.drop_index(index_name)
            logger.info(f"🗑️  Đã xóa index '{index_name}' từ '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"❌ Lỗi khi xóa index: {e}")
            return False
    
    async def list_all_indexes(self):
        """Liệt kê tất cả indexes trong các collections (Async)"""
        try:
            logger.info("\n📋 Danh sách tất cả indexes:")
            
            for collection_name in self.indexes_config.keys():
                collection = self.database[collection_name]
                indexes_cursor = collection.list_indexes()
                
                logger.info(f"\n📦 Collection: {collection_name}")
                async for idx in indexes_cursor:
                    logger.info(f"   • {idx['name']}: {idx['key']}")
                    
        except Exception as e:
            logger.error(f"❌ Lỗi khi liệt kê indexes: {e}")


async def ensure_mongodb_indexes(database):
    """
    Helper function để ensure indexes (Async)
    
    Args:
        database: MongoDB database instance (Motor AsyncIOMotorDatabase)
    """
    ensurer = MongoDBIndexEnsurer(database)
    await ensurer.ensure_all_indexes()


async def ensure_product_indexes(database):
    """
    Helper function để chỉ ensure indexes cho products (Async)
    
    Args:
        database: MongoDB database instance (Motor AsyncIOMotorDatabase)
    """
    ensurer = MongoDBIndexEnsurer(database)
    created, existing = await ensurer._ensure_collection_indexes("products", ensurer.indexes_config["products"])
    
    if created > 0:
        logger.info(f"✅ Đã tạo {created} indexes mới cho products")
    if existing > 0:
        logger.info(f"ℹ️  {existing} indexes đã tồn tại cho products")
