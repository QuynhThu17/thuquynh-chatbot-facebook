"""
Test script cho search_products tool
"""
import asyncio
import logging
from bot.bot_facebook_messenger import bot_facebook_messenger
from bot.tools.facebook_messenger_tools import FacebookMessengerTools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_search_products():
    """Test các trường hợp sử dụng search_products tool"""
    
    # Initialize bot
    await bot_facebook_messenger.initialize()
    
    # Tạo tools instance
    fb_tools = FacebookMessengerTools(bot_facebook_messenger)
    search_tool = fb_tools.create_search_products_tool()
    
    # Mock bot info với company_id
    bot_facebook_messenger.current_bot_info = {
        "company_id": "test_company_123"  # Thay bằng company_id thật trong DB
    }
    
    logger.info("=" * 80)
    logger.info("TEST 1: Tìm kiếm chung - 'iphone'")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "search_query": "iphone",
        "limit": 5
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Tìm theo khoảng giá - sản phẩm dưới 500k")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "max_price": 500000,
        "limit": 5
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Tìm theo SKU - 'IP15PM'")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "sku": "IP15PM",
        "limit": 3
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Tìm theo category - 'Smartphones'")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "category": "Smartphones",
        "limit": 5
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Kiểm tra tồn kho")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "search_query": "iphone",
        "check_inventory": True,
        "limit": 3
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 6: Kết hợp nhiều điều kiện")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "search_query": "iphone",
        "min_price": 20000000,
        "max_price": 30000000,
        "check_inventory": True,
        "limit": 5
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 7: Tìm không dấu - 'dien thoai'")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "search_query": "dien thoai",
        "limit": 5
    })
    print(result)
    
    logger.info("\n" + "=" * 80)
    logger.info("TEST 8: Đếm tất cả sản phẩm")
    logger.info("=" * 80)
    result = search_tool.invoke({
        "limit": 50
    })
    print(result)
    
    logger.info("\n✅ Hoàn thành test!")

if __name__ == "__main__":
    asyncio.run(test_search_products())
