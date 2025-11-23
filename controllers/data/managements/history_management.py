"""
History Management Factory
Quản lý lịch sử chat trong MongoDB
"""

import logging
import uuid
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from typing import Dict, List, Any, Optional, Union
from controllers.databases.mongodb.mongodb import MongoDBManager
from .notification_mixin import ConversationNotificationMixin
from controllers.ultils.notification_background_tasks import run_in_background

logger = logging.getLogger(__name__)

class HistoryManagementFactory(ConversationNotificationMixin):
    """
    Factory để quản lý lịch sử chat trong MongoDB
    """
    
    def __init__(self, db_manager: MongoDBManager):
        """
        Khởi tạo History Management Factory
        
        Args:
            db_manager: MongoDB manager instance
        """
        self.db_manager = db_manager
        self.collection_name = "histories"
        self.init_notification_mixin(db_manager)
    
    @property
    def history_manager(self):
        """Get history manager (for compatibility)"""
        return self
    
    async def save_history(self, user_id: str, session_id: str = None, customer_id: str = None, query: str = "", 
                          answer: str = "", media: Dict[str, Any] = None, status: str = "active", 
                          company_id: str = None, bot_id: str = None, history_id: str = None, social_id: str = None, social_page_id: str = None, response_segments: List[Dict[str, Any]] = None, sender_info: Dict[str, Any] = None, tags: List[str] = None) -> Optional[str]:
        """
        Lưu lịch sử chat vào MongoDB
        
        Args:
            user_id: ID người dùng
            session_id: ID phiên chat
            query: Câu hỏi của người dùng
            answer: Câu trả lời của bot
            media: Media data {type: "image", url: "..."}
            status: Trạng thái history
            company_id: ID công ty
            bot_id: ID bot
            history_id: ID history (tự tạo nếu không có)
            social: Nền tảng social (ví dụ: "s_facebook")
            social_page_id: ID trang social (ví dụ: Facebook Page ID)
            response_segments: Segments của câu trả lời bot [{"type": "text|image", "data": "..."}]
            sender_info: Thông tin người gửi (nếu có)
            
        Returns:
            str: ID của history vừa tạo
        """
        try:
            # Tạo IDs nếu không có
            if not history_id:
                history_id = str(uuid.uuid4())
            if not session_id:
                session_id = str(uuid.uuid4())
            
            
            
            # Chuẩn bị document
            history_doc = {
                "history_id": history_id,
                "session_id": session_id,
                "query": query,
                "answer": answer,
                "answer_segments": response_segments or [],
                "media": media or {},
                "status": status,
                "user_id": user_id,
                "company_id": company_id,
                "customer_id": customer_id,
                "sender_info": sender_info or {},
                "bot_id": bot_id,
                "social_id": social_id,
                "social_page_id": social_page_id,
                "social_access_link": f"https://business.facebook.com/latest/inbox/all/?nav_ref=manage_page_ap_plus_inbox_message_button&asset_id={social_page_id}&business_id=&mailbox_id=&selected_item_id={sender_info.get('id')}&thread_type=FB_MESSAGE" if sender_info else None,
                "created_at": get_vietnam_now_naive(),
                "updated_at": get_vietnam_now_naive()
            }
            
            # Lưu vào MongoDB
            result_id = await self.db_manager.insert_one(self.collection_name, history_doc)
            
            # Auto-create customer nếu chưa tồn tại
            if customer_id and social_page_id:
                try:
                    from controllers.data.managements import get_mongodb_factory
                    factory = get_mongodb_factory()
                    
                    # Kiểm tra customer đã tồn tại chưa
                    existing_customer = await factory.customer_manager.get_by_customer_id_and_page(
                        customer_id=customer_id,
                        social_page_id=social_page_id
                    )
                    
                    # Nếu chưa có thì tạo mới
                    if not existing_customer:
                        customer_name = sender_info.get("name") if sender_info else None
                        customer_data = {
                            "user_id": user_id,
                            "social_id": social_id or "s_facebook",
                            "social_page_id": social_page_id,
                            "customer_id": customer_id,
                            "name": customer_name or f"Customer {customer_id[:8]}",
                            "phone": None,
                            "email": None,
                            "address": None,
                            "gender": None,
                            "additional_info": sender_info or {},
                            "auto_reply": True,
                            "status": "Tương tác",
                            "tags": [],
                            "created_at": get_vietnam_now_naive(),
                            "updated_at": get_vietnam_now_naive()
                        }
                        
                        await factory.customer_manager.create_customer(**customer_data)
                        logger.info(f"✅ Tự động tạo customer mới: {customer_id}")
                    
                except Exception as e:
                    # Không block việc lưu history nếu tạo customer thất bại
                    logger.warning(f"⚠️ Không thể tự động tạo customer: {e}")
            
            if result_id:
                logger.info(f"✅ Lưu history thành công. ID: {history_id}")
                
                # Gửi notification trong background (chỉ với message từ customer)
                if user_id and query:  # Có query mới từ customer
                    # Lấy sender name từ sender_info nếu có
                    sender_name = "Khách hàng"
                    if sender_info and "name" in sender_info:
                        sender_name = sender_info["name"]
                    elif customer_id:
                        sender_name = f"Customer {customer_id[:8]}"
                    
                    run_in_background(
                        self.notify_new_message,
                        user_id=user_id,
                        sender_name=sender_name,
                        message_preview=query[:100] if len(query) > 100 else query,
                        conversation_id=session_id,
                        platform="messenger"  # hoặc lấy từ social_id nếu có
                    )
                
                return history_id
            else:
                logger.error("❌ Lỗi lưu history vào MongoDB")
                return None
                
        except Exception as e:
            logger.error(f"❌ Lỗi lưu history: {e}")
            return None
    
    async def get_history(self, user_id: str, session_id: str = None, 
                         history_id: str = None, limit: int = None, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử chat từ MongoDB
        
        Args:
            user_id: ID người dùng
            session_id: ID phiên chat
            history_id: ID history cụ thể
            limit: Giới hạn số lượng kết quả
            include_deleted: bool - Bao gồm histories đã xóa (mặc định: False)
            
        Returns:
            List[Dict]: Danh sách lịch sử
        """
        try:
            # Tạo filter
            filter_dict = {"user_id": user_id}

            if not include_deleted:
                filter_dict["status"] = {"$ne": "deleted"}

            if history_id:
                filter_dict["history_id"] = history_id
            elif session_id:
                filter_dict["session_id"] = session_id
            
            # Sắp xếp theo thời gian tạo
            sort = [("created_at", 1)]
            
            # Lấy dữ liệu từ MongoDB
            histories = await self.db_manager.find_many(
                self.collection_name, 
                filter_dict, 
                sort=sort, 
                limit=limit
            )
            
            logger.info(f"✅ Lấy {len(histories)} histories cho user {user_id}")
            return histories
            
        except Exception as e:
            logger.error(f"❌ Lỗi lấy history: {e}")
            return []
    
    async def get_all_history_user(self, user_id: str, company_id: str = None, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        Lấy tất cả lịch sử của người dùng
        
        Args:
            user_id: ID người dùng
            company_id: ID công ty (optional)
            include_deleted: bool - Bao gồm histories đã xóa (mặc định: False)
            
        Returns:
            List[Dict]: Danh sách tất cả lịch sử
        """
        try:
            filter_dict = {"user_id": user_id}

            if not include_deleted:
                filter_dict["status"] = {"$ne": "deleted"}

            if company_id:
                filter_dict["company_id"] = company_id
            
            # Sắp xếp theo thời gian tạo
            sort = [("created_at", -1)]
            
            histories = await self.db_manager.find_many(
                self.collection_name, 
                filter_dict, 
                sort=sort
            )
            
            logger.info(f"✅ Lấy tất cả {len(histories)} histories cho user {user_id}")
            return histories
            
        except Exception as e:
            logger.error(f"❌ Lỗi lấy tất cả history: {e}")
            return []
    
    async def update_feedback(self, history_id: str, new_feedback: str = None, 
                             new_feedback_status: str = None) -> bool:
        """
        Cập nhật feedback cho history
        
        Args:
            history_id: ID history
            new_feedback: Feedback mới
            new_feedback_status: Trạng thái feedback mới
            
        Returns:
            bool: True nếu cập nhật thành công
        """
        try:
            filter_dict = {"history_id": history_id}
            update_dict = {}
            
            if new_feedback is not None:
                update_dict["feedback"] = new_feedback
            if new_feedback_status is not None:
                update_dict["feedback_status"] = new_feedback_status
            
            if not update_dict:
                logger.warning("⚠️ Không có dữ liệu để cập nhật")
                return False
            
            success = await self.db_manager.update_one(
                self.collection_name, 
                filter_dict, 
                update_dict
            )
            
            if success:
                logger.info(f"✅ Cập nhật feedback cho history {history_id} thành công")
            else:
                logger.warning(f"⚠️ Không tìm thấy history {history_id} để cập nhật")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Lỗi cập nhật feedback: {e}")
            return False
    
    async def delete_history(self, user_id: str, session_id: str = None, 
                            history_id: str = None) -> int:
        """
        Xóa lịch sử chat
        
        Args:
            user_id: ID người dùng
            session_id: ID phiên chat (xóa toàn bộ session)
            history_id: ID history cụ thể (xóa 1 history)
            
        Returns:
            int: Number of histories deleted (0 if none)
        """
        try:
            filter_dict = {"user_id": user_id}
            
            if history_id:
                filter_dict["history_id"] = history_id
            elif session_id:
                filter_dict["session_id"] = session_id
            else:
                logger.error("❌ Cần cung cấp session_id hoặc history_id để xóa")
                return 0

            filter_dict["status"] = {"$ne": "deleted"}
            
            # Sử dụng soft delete bằng cách update status
            update_dict = {"status": "deleted"}
            
            deleted_count = await self.db_manager.update_many(
                self.collection_name, 
                filter_dict, 
                update_dict
            )
            
            if deleted_count > 0:
                logger.info(f"✅ Xóa {deleted_count} histories thành công")
                
                # Gửi notification trong background khi xóa session
                if session_id and user_id:
                    run_in_background(
                        self.notify_conversation_ended,
                        user_id=user_id,
                        conversation_id=session_id,
                        message_count=deleted_count
                    )
                
                return deleted_count
            else:
                logger.warning("⚠️ Không tìm thấy history để xóa")
                return 0
                
        except Exception as e:
            logger.error(f"❌ Lỗi xóa history: {e}")
            return 0
    
    async def get_session_list(self, user_id: str, company_id: str = None) -> List[Dict[str, Any]]:
        """
        Lấy danh sách sessions của user
        
        Args:
            user_id: ID người dùng
            company_id: ID công ty (optional)
            
        Returns:
            List[Dict]: Danh sách sessions với thông tin summary
        """
        try:
            filter_dict = {"user_id": user_id, "status": {"$ne": "deleted"}}
            
            if company_id:
                filter_dict["company_id"] = company_id
            
            # Aggregate để group theo session_id và lấy thông tin summary
            pipeline = [
                {"$match": filter_dict},
                {
                    "$group": {
                        "_id": "$session_id",
                        "session_id": {"$first": "$session_id"},
                        "first_query": {"$first": "$query"},
                        "last_message": {"$last": "$answer"},
                        "message_count": {"$sum": 1},
                        "created_at": {"$first": "$created_at"},
                        "updated_at": {"$last": "$updated_at"},
                        "company_id": {"$first": "$company_id"},
                        "bot_id": {"$first": "$bot_id"}
                    }
                },
                {"$sort": {"updated_at": -1}}
            ]
            
            collection = self.db_manager.get_collection(self.collection_name)
            cursor = collection.aggregate(pipeline)
            sessions = await cursor.to_list(length=None)
            
            logger.info(f"✅ Lấy {len(sessions)} sessions cho user {user_id}")
            return sessions
            
        except Exception as e:
            logger.error(f"❌ Lỗi lấy session list: {e}")
            return []
    
    async def get_by_user_id(self, user_id: str, session_id: str = None) -> List[Dict[str, Any]]:
        """
        Lấy histories theo user_id (alias cho get_history để tương thích với API)
        
        Args:
            user_id: ID người dùng
            session_id: ID phiên chat (optional)
            
        Returns:
            List[Dict]: Danh sách lịch sử
        """
        try:
            return await self.get_history(user_id=user_id, session_id=session_id)
        except Exception as e:
            logger.error(f"❌ Lỗi lấy history by user_id: {e}")
            return []
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Lấy all sessions của user (alias cho get_session_list để tương thích với API)
        
        Args:
            user_id: ID người dùng
            
        Returns:
            List[Dict]: Danh sách sessions
        """
        try:
            return await self.get_session_list(user_id=user_id)
        except Exception as e:
            logger.error(f"❌ Lỗi lấy user sessions: {e}")
            return []
    
    async def search_conversations(self, user_id: str, query: str) -> List[Dict[str, Any]]:
        """
        Tìm kiếm trong conversation histories
        
        Args:
            user_id: ID người dùng
            query: Từ khóa tìm kiếm
            
        Returns:
            List[Dict]: Danh sách histories khớp với tìm kiếm
        """
        try:
            # Tìm kiếm trong query và answer
            filter_dict = {
                "user_id": user_id,
                "status": {"$ne": "deleted"},
                "$or": [
                    {"query": {"$regex": query, "$options": "i"}},
                    {"answer": {"$regex": query, "$options": "i"}}
                ]
            }
            
            # Sắp xếp theo thời gian tạo giảm dần
            sort = [("created_at", -1)]
            
            # Lấy dữ liệu từ MongoDB
            histories = await self.db_manager.find_many(
                self.collection_name,
                filter_dict,
                sort=sort,
                limit=100  # Giới hạn 100 kết quả
            )
            
            logger.info(f"✅ Tìm thấy {len(histories)} histories cho query '{query}' của user {user_id}")
            return histories
            
        except Exception as e:
            logger.error(f"❌ Lỗi tìm kiếm conversations: {e}")
            return []
