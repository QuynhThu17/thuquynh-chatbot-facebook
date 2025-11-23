"""
Test auto-ensure indexes
"""
import asyncio
import logging
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.databases.mongodb.ensure_indexes import MongoDBIndexEnsurer, ensure_mongodb_indexes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_auto_ensure():
    """Test auto-ensure indexes"""
    try:
        # Connect to MongoDB
        db_manager = MongoDBManager()
        await db_manager.connect()
        
        logger.info("\n" + "="*80)
        logger.info("TEST: Auto-Ensure Indexes")
        logger.info("="*80 + "\n")
        
        # Test ensure all indexes
        logger.info("📋 Testing ensure_mongodb_indexes()...")
        await ensure_mongodb_indexes(db_manager.database)
        
        # List all indexes
        logger.info("\n" + "="*80)
        logger.info("📋 Listing all indexes...")
        logger.info("="*80 + "\n")
        
        ensurer = MongoDBIndexEnsurer(db_manager.database)
        await ensurer.list_all_indexes()
        
        # Check specific index
        logger.info("\n" + "="*80)
        logger.info("🔍 Checking specific indexes...")
        logger.info("="*80 + "\n")
        
        test_cases = [
            ("products", "idx_fulltext_search"),
            ("products", "idx_sku"),
            ("customers", "idx_social_customer"),
            ("orders", "idx_status")
        ]
        
        for collection, index_name in test_cases:
            exists = await ensurer.check_index_exists(collection, index_name)
            status = "✅ EXISTS" if exists else "❌ NOT FOUND"
            logger.info(f"{status}: {collection}.{index_name}")
        
        logger.info("\n✅ Test completed successfully!")
        
        # Close connection
        await db_manager.disconnect()
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(test_auto_ensure())
