"""
Bot Chat Service
Xử lý chat với bot AI cho live support
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class BotChatService:
    """Service để xử lý chat với bot AI"""
    
    @staticmethod
    async def process_bot_message(
        message: str,
        user_id: str = None,
        session_id: str = None,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Xử lý tin nhắn từ user và trả về response từ bot
        
        Args:
            message: Tin nhắn từ user
            user_id: ID user (nếu đã đăng nhập)
            session_id: ID session chat
            context: Context của cuộc hội thoại
            
        Returns:
            Dict chứa response từ bot
            {
                "response": "Bot response text",
                "actions": [...],  # Các action bot có thể thực hiện
                "suggestions": [...],  # Gợi ý câu hỏi tiếp theo
                "need_human": False  # Có cần chuyển sang human không
            }
        """
        try:
            # TODO: Tích hợp với AI model/LLM để xử lý tin nhắn
            # Hiện tại tạm thời trả về response cố định
            
            # Phân tích intent từ tin nhắn
            message_lower = message.lower()
            
            # Các câu hỏi thường gặp
            if any(word in message_lower for word in ["giá", "price", "cost", "phí"]):
                return {
                    "response": "Hiện tại chúng tôi có các gói dịch vụ với mức giá khác nhau. Bạn có muốn tôi cung cấp thông tin chi tiết về bảng giá không?",
                    "actions": ["show_pricing"],
                    "suggestions": [
                        "Chi tiết bảng giá",
                        "Gói dịch vụ nào phù hợp với tôi?",
                        "Có khuyến mãi không?"
                    ],
                    "need_human": False
                }
            
            elif any(word in message_lower for word in ["hướng dẫn", "guide", "tutorial", "cách"]):
                return {
                    "response": "Tôi có thể hướng dẫn bạn sử dụng các tính năng của hệ thống. Bạn muốn tìm hiểu về tính năng nào?",
                    "actions": ["show_guides"],
                    "suggestions": [
                        "Cách tạo bot",
                        "Kết nối Facebook",
                        "Quản lý khách hàng",
                        "Xem tài liệu hướng dẫn"
                    ],
                    "need_human": False
                }
            
            elif any(word in message_lower for word in ["lỗi", "error", "bug", "không hoạt động"]):
                return {
                    "response": "Tôi hiểu bạn đang gặp vấn đề kỹ thuật. Tôi sẽ cố gắng hỗ trợ bạn giải quyết. Bạn có thể mô tả chi tiết hơn về lỗi bạn gặp phải không?",
                    "actions": ["troubleshoot"],
                    "suggestions": [
                        "Lỗi kết nối Facebook",
                        "Bot không phản hồi",
                        "Không thể đăng nhập",
                        "Nói chuyện với nhân viên hỗ trợ"
                    ],
                    "need_human": False
                }
            
            elif any(word in message_lower for word in ["nhân viên", "người thật", "human", "support"]):
                return {
                    "response": "Tôi hiểu bạn muốn nói chuyện trực tiếp với nhân viên hỗ trợ. Tôi sẽ chuyển cuộc hội thoại cho đội ngũ hỗ trợ của chúng tôi.",
                    "actions": ["transfer_to_human"],
                    "suggestions": [],
                    "need_human": True
                }
            
            else:
                # Response chung cho các tin nhắn khác
                return {
                    "response": f"Cảm ơn bạn đã liên hệ! Tôi đã nhận được tin nhắn: '{message}'. Tôi là trợ lý AI và sẽ cố gắng hỗ trợ bạn tốt nhất. Bạn có thể hỏi tôi về:",
                    "actions": ["show_menu"],
                    "suggestions": [
                        "Bảng giá dịch vụ",
                        "Hướng dẫn sử dụng",
                        "Báo cáo lỗi",
                        "Nói chuyện với nhân viên"
                    ],
                    "need_human": False
                }
                
        except Exception as e:
            logger.error(f"Error processing bot message: {str(e)}")
            return {
                "response": "Xin lỗi, tôi gặp sự cố kỹ thuật. Bạn có muốn nói chuyện trực tiếp với nhân viên hỗ trợ không?",
                "actions": ["transfer_to_human"],
                "suggestions": ["Nói chuyện với nhân viên hỗ trợ"],
                "need_human": True
            }
    
    @staticmethod
    async def get_suggested_responses(context: Dict[str, Any] = None) -> List[str]:
        """
        Lấy các câu hỏi gợi ý dựa trên context
        
        Returns:
            List các câu hỏi gợi ý
        """
        try:
            # TODO: Có thể dựa vào context để đưa ra gợi ý phù hợp hơn
            
            default_suggestions = [
                "Làm thế nào để bắt đầu?",
                "Bảng giá dịch vụ như thế nào?",
                "Tôi gặp vấn đề kỹ thuật",
                "Hướng dẫn sử dụng tính năng",
                "Nói chuyện với nhân viên hỗ trợ"
            ]
            
            return default_suggestions
            
        except Exception as e:
            logger.error(f"Error getting suggested responses: {str(e)}")
            return []
    
    @staticmethod
    def should_transfer_to_human(message: str, previous_messages: List[str] = None) -> bool:
        """
        Kiểm tra xem có nên chuyển sang chat với human không
        
        Args:
            message: Tin nhắn hiện tại
            previous_messages: Các tin nhắn trước đó
            
        Returns:
            bool: True nếu nên transfer sang human
        """
        try:
            message_lower = message.lower()
            
            # Các từ khóa yêu cầu human support
            human_keywords = [
                "nhân viên", "người thật", "human", "staff",
                "phức tạp", "không hiểu", "không thể giải quyết",
                "khiếu nại", "complaint", "không hài lòng"
            ]
            
            if any(keyword in message_lower for keyword in human_keywords):
                return True
            
            # Nếu user hỏi lại nhiều lần về cùng một vấn đề
            if previous_messages and len(previous_messages) > 3:
                # Logic phức tạp hơn để detect frustrated user
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking transfer to human: {str(e)}")
            return False