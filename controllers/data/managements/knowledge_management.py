"""
Knowledge Management Module
Quản lý knowledge_chunks, documents, histories, feedback
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from .base_manager import BaseManager
from .notification_mixin import KnowledgeNotificationMixin
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.ultils.notification_background_tasks import run_in_background

logger = logging.getLogger(__name__)

class KnowledgeChunkManager(BaseManager):
    """Manager cho knowledge_chunks collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "knowledge_chunks")
    
    async def create_knowledge_chunk(self, content: str, content_embedding: List[float],
                                   source_info: Dict[str, Any], user_id: str,
                                   company_id: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo knowledge chunk mới
        
        Args:
            content: Nội dung text
            content_embedding: Vector embedding
            source_info: {"type": "", "source_id": "", "title": ""}
            user_id: ID user
            company_id: ID company
            metadata: {page_number, document_author, tags}
        """
        chunk_data = {
            "content": content,
            "content_embedding": content_embedding,
            "source_info": source_info,
            "metadata": metadata or {},
            "user_id": user_id,
            "company_id": company_id
        }
        return await self.create(chunk_data)
    
    async def create_knowledge_chunk_with_type(self, content: str, content_embedding_text: str,
                                             content_embedding: List[float], chunk_type: str,
                                             source_info: Dict[str, Any], user_id: str,
                                             company_id: str = None, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo knowledge chunk mới với type và embedding text riêng biệt
        
        Args:
            content: Nội dung đầy đủ (bao gồm image tags)
            content_embedding_text: Text được dùng để tạo embedding (không có image tags)
            content_embedding: Vector embedding
            chunk_type: Loại chunk ("text", "page", "image")
            source_info: {"type": "", "source_id": "", "title": ""}
            user_id: ID user
            company_id: ID company
            metadata: {page_number, chunk_type, etc.}
        """
        chunk_data = {
            "content": content,
            "content_embedding_text": content_embedding_text,
            "content_embedding": content_embedding,
            "chunk_type": chunk_type,
            "source_info": source_info,
            "metadata": metadata or {},
            "user_id": user_id,
            "company_id": company_id
        }
        return await self.create(chunk_data)
    
    async def get_by_user_id(self, user_id: str, company_id: str = None,
                           source_type: str = None) -> List[Dict[str, Any]]:
        """Lấy knowledge chunks theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        if source_type:
            filter_query["source_info.type"] = source_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_source_id(self, source_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy knowledge chunks theo source_id"""
        filter_query = {"source_info.source_id": source_id}
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def search_by_content(self, search_term: str, user_id: str = None,
                              company_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Tìm kiếm knowledge chunks theo nội dung"""
        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id
        if company_id:
            filter_query["company_id"] = company_id
        
        # Text search
        filter_query["content"] = {"$regex": search_term, "$options": "i"}
        
        return await self.get_all(filter_query=filter_query, limit=limit)
    
    async def vector_search(self, query_embedding: List[float], user_id: str = None,
                          company_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Vector similarity search (cần MongoDB Atlas với vector search index)
        """
        # Placeholder implementation - cần vector search index
        # Hiện tại trả về theo user_id/company_id
        filter_query = {}
        if user_id:
            filter_query["user_id"] = user_id
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query, limit=limit)
    
    async def get_by_chunk_type(self, chunk_type: str, user_id: str = None,
                               company_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy knowledge chunks theo chunk type"""
        filter_query = {"chunk_type": chunk_type}
        if user_id:
            filter_query["user_id"] = user_id
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query, limit=limit)
    
    async def get_page_chunks_by_document(self, source_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy tất cả page chunks của một document"""
        filter_query = {
            "source_info.source_id": source_id,
            "chunk_type": "page"
        }
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_image_chunks_by_document(self, source_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy tất cả image chunks của một document"""
        filter_query = {
            "source_info.source_id": source_id,
            "chunk_type": "image"
        }
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def delete_by_source_id(self, source_id: str, user_id: str = None) -> int:
        """Xóa tất cả chunks của một source"""
        filter_query = {"source_info.source_id": source_id}
        if user_id:
            filter_query["user_id"] = user_id
        
        try:
            result = await self.collection.delete_many(filter_query)
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting chunks by source_id {source_id}: {str(e)}")
            return 0

    async def bulk_create_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Tạo nhiều knowledge chunks cùng lúc để cải thiện hiệu suất
        
        Args:
            chunks_data: List các chunk data
            
        Returns:
            List các chunks đã tạo
        """
        try:
            if not chunks_data:
                return []
            
            # Sử dụng bulk_create từ base manager
            result = await self.bulk_create(chunks_data)
            logger.info(f"Bulk created {len(result)} knowledge chunks")
            return result
            
        except Exception as e:
            logger.error(f"Error bulk creating chunks: {str(e)}")
            raise


class DocumentManager(BaseManager, KnowledgeNotificationMixin):
    """Manager cho documents collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "documents")
        self.init_notification_mixin(db_manager)

    async def create_document(self, document_name: str, file_name: str, file_type: str, storage_type: str,
                            storage_url: str, user_id: str, title: str = None,
                            content: str = None, status: str = "uploaded",
                            company_id: str = None) -> Dict[str, Any]:
        """
        Tạo document mới
        
        Args:
            file_name: Tên file
            file_type: Loại file (pdf, doc, txt, etc.)
            storage_type: Loại storage (local, s3, etc.)
            storage_url: URL storage
            user_id: ID user
            title: Tiêu đề document
            content: Nội dung text (nếu đã extract)
            status: Trạng thái (uploaded, processing, processed, error)
            company_id: ID company
        """
        doc_data = {
            "document_name": document_name,
            "file_name": file_name,
            "file_type": file_type,
            "storage_type": storage_type,
            "storage_url": storage_url,
            "title": title or file_name,
            "content": content,
            "status": status,
            "user_id": user_id,
            "company_id": company_id
        }
        result = await self.create(doc_data)
        
        # Gửi notification upload thành công
        if result:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Upload tài liệu thành công",
                content=f"Đã tải lên tài liệu: {title or file_name}",
                category="knowledge",
                notification_type="success",
                action="document_uploaded",
                priority=1,
                metadata={
                    "document_id": str(result["_id"]),
                    "file_name": file_name,
                    "file_type": file_type
                }
            )
        
        return result
    
    async def get_by_user_id(self, user_id: str, company_id: str = None,
                           status: str = None) -> List[Dict[str, Any]]:
        """Lấy documents theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        if status:
            filter_query["status"] = status
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def update_content(self, doc_id: Union[str, ObjectId], content: str,
                           status: str = "processed") -> Optional[Dict[str, Any]]:
        """Cập nhật content và status của document"""
        return await self.update_by_id(doc_id, {"content": content, "status": status})
    
    async def update_status(self, doc_id: Union[str, ObjectId], status: str) -> Optional[Dict[str, Any]]:
        """Cập nhật status của document"""
        return await self.update_by_id(doc_id, {"status": status})
    
    async def search_documents(self, user_id: str, search_term: str,
                             company_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm documents"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$match": {
                    "$or": [
                        {"title": {"$regex": search_term, "$options": "i"}},
                        {"file_name": {"$regex": search_term, "$options": "i"}},
                        {"content": {"$regex": search_term, "$options": "i"}}
                    ]
                }
            }
        ]
        
        if company_id:
            pipeline[0]["$match"]["company_id"] = company_id
        
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            return [self._serialize_object_id(result) for result in results]
        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return []


class HistoryManager(BaseManager):
    """Manager cho histories collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "histories")
    
    async def create_history(self, session_id: str, query: str, answer: str,
                           user_id: str, bot_id: str = None, company_id: str = None,
                           media: List[Dict[str, Any]] = None, status: str = "completed") -> Dict[str, Any]:
        """
        Tạo history record mới
        
        Args:
            session_id: ID session
            query: Câu hỏi
            answer: Câu trả lời
            user_id: ID user
            bot_id: ID bot (nếu từ bot)
            company_id: ID company
            media: List media files
            status: Trạng thái
        """
        history_data = {
            "session_id": session_id,
            "query": query,
            "answer": answer,
            "media": media or [],
            "status": status,
            "user_id": user_id,
            "company_id": company_id,
            "bot_id": bot_id
        }
        return await self.create(history_data)
    
    async def get_by_session_id(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy conversation history theo session_id"""
        return await self.get_all(
            filter_query={"session_id": session_id},
            limit=limit,
            sort_by="create_at",
            sort_order=1  # Ascending để có thứ tự conversation
        )
    
    async def get_by_user_id(self, user_id: str, company_id: str = None,
                           bot_id: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """Lấy histories theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        if bot_id:
            filter_query["bot_id"] = bot_id
        
        # Lọc theo ngày nếu cần
        if days:
            start_date = get_vietnam_now_naive() - timedelta(days=days)
            filter_query["create_at"] = {"$gte": start_date}
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1,
            limit=1000
        )
    
    async def get_by_bot_id(self, bot_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Lấy histories theo bot_id"""
        filter_query = {"bot_id": bot_id}
        
        if days:
            start_date = get_vietnam_now_naive() - timedelta(days=days)
            filter_query["create_at"] = {"$gte": start_date}
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def search_conversations(self, user_id: str, search_term: str,
                                 company_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm trong conversations"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$match": {
                    "$or": [
                        {"query": {"$regex": search_term, "$options": "i"}},
                        {"answer": {"$regex": search_term, "$options": "i"}}
                    ]
                }
            }
        ]
        
        if company_id:
            pipeline[0]["$match"]["company_id"] = company_id
        
        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            return [self._serialize_object_id(result) for result in results]
        except Exception as e:
            logger.error(f"Error searching conversations: {str(e)}")
            return []
    
    async def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Lấy thống kê của session"""
        try:
            pipeline = [
                {"$match": {"session_id": session_id}},
                {
                    "$group": {
                        "_id": None,
                        "total_messages": {"$sum": 1},
                        "first_message": {"$min": "$create_at"},
                        "last_message": {"$max": "$create_at"}
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                stats = result[0]
                # Calculate duration
                if stats["first_message"] and stats["last_message"]:
                    duration = stats["last_message"] - stats["first_message"]
                    stats["duration_minutes"] = duration.total_seconds() / 60
                
                return self._serialize_object_id(stats)
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting session stats: {str(e)}")
            return {}


class FeedbackManager(BaseManager):
    """Manager cho feedback collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "feedback")
    
    async def create_feedback(self, user_id: str, social_id: str, 
                            social_identification: Dict[str, Any], content: str,
                            status: str = "new") -> Dict[str, Any]:
        """
        Tạo feedback mới
        
        Args:
            user_id: ID user
            social_id: ID social platform
            social_identification: {fb_page_id, sender_id, session_id}
            content: Nội dung feedback
            status: Trạng thái (new, reviewed, resolved)
        """
        feedback_data = {
            "user_id": user_id,
            "social_id": social_id,
            "social_identification": social_identification,
            "content": content,
            "status": status
        }
        return await self.create(feedback_data)
    
    async def get_by_user_id(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Lấy feedback theo user_id"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def get_by_social_platform(self, social_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Lấy feedback theo social platform"""
        filter_query = {"social_id": social_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="create_at",
            sort_order=-1
        )
    
    async def update_status(self, feedback_id: Union[str, ObjectId], new_status: str) -> Optional[Dict[str, Any]]:
        """Cập nhật status feedback"""
        return await self.update_by_id(feedback_id, {"status": new_status})
    
    async def search_feedback(self, search_term: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm feedback"""
        filter_query = {"content": {"$regex": search_term, "$options": "i"}}
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query, limit=100)


# Factory class để tạo tất cả knowledge management managers
class KnowledgeManagementFactory:
    """Factory để tạo tất cả Knowledge Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._knowledge_chunk_manager = None
        self._document_manager = None
        self._history_manager = None
        self._feedback_manager = None
    
    @property
    def knowledge_chunk_manager(self) -> KnowledgeChunkManager:
        if self._knowledge_chunk_manager is None:
            self._knowledge_chunk_manager = KnowledgeChunkManager(self.db_manager)
        return self._knowledge_chunk_manager
    
    @property
    def document_manager(self) -> DocumentManager:
        if self._document_manager is None:
            self._document_manager = DocumentManager(self.db_manager)
        return self._document_manager
    
    @property
    def history_manager(self) -> HistoryManager:
        if self._history_manager is None:
            self._history_manager = HistoryManager(self.db_manager)
        return self._history_manager
    
    @property
    def feedback_manager(self) -> FeedbackManager:
        if self._feedback_manager is None:
            self._feedback_manager = FeedbackManager(self.db_manager)
        return self._feedback_manager
