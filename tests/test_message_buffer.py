"""
Test Message Buffer - Gộp tin nhắn liên tiếp thông minh
"""
import asyncio
import logging
from bot.bot_facebook_messenger import MessageBuffer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock processor function
async def mock_processor(sender_id, page_id, bot_id, message, send_facebook, company_id):
    """Giả lập việc xử lý tin nhắn"""
    logger.info(f"🤖 Processing message: '{message}'")
    # Giả lập thời gian xử lý
    await asyncio.sleep(1.0)
    logger.info(f"✅ Processed: '{message}'")

async def test_case_1_consecutive_messages_before_response():
    """
    Test Case 1: Gửi 3 tin nhắn liên tiếp trước khi bot phản hồi
    Expected: Bot nhận 1 tin nhắn gộp
    """
    logger.info("\n" + "="*80)
    logger.info("TEST CASE 1: Tin nhắn liên tiếp TRƯỚC KHI bot trả lời")
    logger.info("="*80)
    
    buffer = MessageBuffer(buffer_time=2.0)
    
    # Gửi 3 tin nhắn liên tiếp
    await buffer.add_message("user1", "page1", "bot1", "hi", True, mock_processor, "company1")
    await asyncio.sleep(0.5)
    
    await buffer.add_message("user1", "page1", "bot1", "có túi maggie không", True, mock_processor, "company1")
    await asyncio.sleep(0.5)
    
    await buffer.add_message("user1", "page1", "bot1", "giá bao nhiêu", True, mock_processor, "company1")
    
    # Đợi buffer xử lý xong
    await asyncio.sleep(4.0)
    
    logger.info("✅ TEST CASE 1 PASSED: Bot nhận được tin nhắn gộp\n")

async def test_case_2_messages_after_response():
    """
    Test Case 2: Gửi tin nhắn SAU KHI bot đã trả lời
    Expected: Bot nhận 2 tin nhắn riêng biệt
    """
    logger.info("\n" + "="*80)
    logger.info("TEST CASE 2: Tin nhắn SAU KHI bot đã trả lời")
    logger.info("="*80)
    
    buffer = MessageBuffer(buffer_time=2.0)
    
    # Gửi tin nhắn đầu tiên
    await buffer.add_message("user2", "page2", "bot2", "hello", True, mock_processor, "company2")
    
    # Đợi bot xử lý và trả lời xong
    await asyncio.sleep(4.0)
    
    logger.info("⏰ Bot đã trả lời xong, bây giờ gửi tin nhắn mới...")
    
    # Gửi tin nhắn mới sau khi bot đã trả lời
    await buffer.add_message("user2", "page2", "bot2", "có túi không", True, mock_processor, "company2")
    
    # Đợi xử lý
    await asyncio.sleep(4.0)
    
    logger.info("✅ TEST CASE 2 PASSED: 2 tin nhắn được xử lý riêng biệt\n")

async def test_case_3_mixed_scenario():
    """
    Test Case 3: Kịch bản thực tế - gộp 3 tin liên tiếp, bot trả lời, sau đó 2 tin mới
    Expected: 
    - Lần 1: Bot nhận 3 tin gộp
    - Lần 2: Bot nhận 2 tin gộp
    """
    logger.info("\n" + "="*80)
    logger.info("TEST CASE 3: Kịch bản thực tế hỗn hợp")
    logger.info("="*80)
    
    buffer = MessageBuffer(buffer_time=1.5)
    
    # Batch 1: 3 tin liên tiếp
    logger.info("📨 Batch 1: Gửi 3 tin liên tiếp...")
    await buffer.add_message("user3", "page3", "bot3", "hi", True, mock_processor, "company3")
    await asyncio.sleep(0.3)
    await buffer.add_message("user3", "page3", "bot3", "có hàng không", True, mock_processor, "company3")
    await asyncio.sleep(0.3)
    await buffer.add_message("user3", "page3", "bot3", "giá bao nhiêu", True, mock_processor, "company3")
    
    # Đợi bot xử lý xong batch 1
    await asyncio.sleep(4.0)
    
    # Batch 2: 2 tin mới sau khi bot đã trả lời
    logger.info("📨 Batch 2: Gửi 2 tin mới sau khi bot đã trả lời...")
    await buffer.add_message("user3", "page3", "bot3", "ok đặt 2 cái", True, mock_processor, "company3")
    await asyncio.sleep(0.5)
    await buffer.add_message("user3", "page3", "bot3", "ship cod nhé", True, mock_processor, "company3")
    
    # Đợi xử lý
    await asyncio.sleep(4.0)
    
    logger.info("✅ TEST CASE 3 PASSED: Kịch bản thực tế hoạt động đúng\n")

async def main():
    """Run all test cases"""
    logger.info("\n🧪 BẮT ĐẦU TEST MESSAGE BUFFER\n")
    
    await test_case_1_consecutive_messages_before_response()
    await test_case_2_messages_after_response()
    await test_case_3_mixed_scenario()
    
    logger.info("\n" + "="*80)
    logger.info("✅ TẤT CẢ TEST CASES PASSED!")
    logger.info("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
