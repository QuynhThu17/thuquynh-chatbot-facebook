"""
Bot Management Module
Quản lý identities, procedures, bots
"""

import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from .base_manager import BaseManager
from .notification_mixin import BotNotificationMixin, CRMNotificationMixin
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.ultils.notification_background_tasks import run_in_background

logger = logging.getLogger(__name__)

class IdentityManager(BaseManager, CRMNotificationMixin):
    """Manager cho identities collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "identities")
        self.init_notification_mixin(db_manager)
    
    async def create_identity(self, name: str, info: str, style: str,
                            conversation_style: str, conversation_example: List[Dict[str, str]],
                            identity_type: str = "custom", user_id: str = None) -> Dict[str, Any]:
        """
        Tạo identity mới
        
        Args:
            name: Tên identity
            info: Thông tin về identity
            style: Style của identity
            conversation_style: Phong cách giao tiếp
            conversation_example: Ví dụ hội thoại dạng array [{"user": "...", "you": "..."}]
            identity_type: "default" hoặc "custom"
            user_id: ID user tạo (null nếu là default)
        """
        identity_data = {
            "name": name,
            "info": info,
            "style": style,
            "conversation_style": conversation_style,
            "conversation_example": conversation_example,
            "type": identity_type,
            "user_id": user_id
        }
        result = await self.create(identity_data)
        
        # Gửi notification
        if result and user_id:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Tạo Identity thành công",
                content=f"Đã tạo identity mới: {name}",
                notification_type="success",
                category="crm",
                action="identity_created",
                priority=1,
                metadata={
                    "identity_id": str(result["_id"]),
                    "identity_name": name,
                    "identity_type": identity_type
                }
            )
        
        return result
    
    async def get_by_user_id(self, user_id: str, identity_type: str = None) -> List[Dict[str, Any]]:
        """Lấy identities theo user_id"""
        filter_query = {"user_id": user_id}
        if identity_type:
            filter_query["type"] = identity_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_default_identities(self) -> List[Dict[str, Any]]:
        """Lấy tất cả default identities"""
        return await self.get_all(filter_query={"type": "default"})
    
    async def get_by_name_and_user(self, name: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy identity theo name và user_id"""
        filter_query = {"name": name}
        if user_id:
            filter_query["user_id"] = user_id
        else:
            filter_query["type"] = "default"
        
        identities = await self.get_all(filter_query=filter_query, limit=1)
        return identities[0] if identities else None
    
    async def update_conversation_example(self, identity_id: Union[str, ObjectId], 
                                        new_example: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """Cập nhật conversation example"""
        return await self.update_by_id(identity_id, {"conversation_example": new_example})


class ProcedureManager(BaseManager, CRMNotificationMixin):
    """Manager cho procedures collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "procedures")
        self.init_notification_mixin(db_manager)
    
    async def create_procedure(self, name: str, procedure: str, procedure_type: str = "custom",
                             user_id: str = None) -> Dict[str, Any]:
        """
        Tạo procedure mới
        
        Args:
            name: Tên procedure
            procedure: Nội dung procedure (có thể là JSON workflow)
            procedure_type: "default" hoặc "custom"
            user_id: ID user tạo (null nếu là default)
        """
        procedure_data = {
            "name": name,
            "procedure": procedure,
            "type": procedure_type,
            "user_id": user_id
        }
        result = await self.create(procedure_data)
        
        # Gửi notification
        if result and user_id:
            run_in_background(
                self._create_notification,
                user_id=str(user_id),
                title="Tạo Procedure thành công",
                content=f"Đã tạo procedure mới: {name}",
                notification_type="success",
                category="crm",
                action="procedure_created",
                priority=1,
                metadata={
                    "procedure_id": str(result["_id"]),
                    "procedure_name": name,
                    "procedure_type": procedure_type
                }
            )
        
        return result
    
    async def get_by_user_id(self, user_id: str, procedure_type: str = None) -> List[Dict[str, Any]]:
        """Lấy procedures theo user_id"""
        filter_query = {"user_id": user_id}
        if procedure_type:
            filter_query["type"] = procedure_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_default_procedures(self) -> List[Dict[str, Any]]:
        """Lấy tất cả default procedures"""
        return await self.get_all(filter_query={"type": "default"})
    
    async def get_by_name_and_user(self, name: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy procedure theo name và user_id"""
        filter_query = {"name": name}
        if user_id:
            filter_query["user_id"] = user_id
        else:
            filter_query["type"] = "default"
        
        procedures = await self.get_all(filter_query=filter_query, limit=1)
        return procedures[0] if procedures else None
    
    async def update_procedure_content(self, procedure_id: Union[str, ObjectId], 
                                     new_procedure: str) -> Optional[Dict[str, Any]]:
        """Cập nhật nội dung procedure"""
        return await self.update_by_id(procedure_id, {"procedure": new_procedure})


class BotManager(BaseManager, BotNotificationMixin):
    """Manager cho bots collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "bots")
        self.init_notification_mixin(db_manager)
    
    async def create_bot(self, user_id: str, name: str, identity_id: str, procedure_id: str,
                         role: str, target: str, mission: str, bot_type: str = "message",
                         note: str = None, knowledge: str = None, status: str = "off",
                         connect: str = None, language_code: str = None) -> Dict[str, Any]:
        """
        Tạo bot mới
        
        Args:
            user_id: ID user tạo bot
            name: Tên bot
            identity_id: ID identity
            procedure_id: ID procedure
            role: Vai trò của bot
            target: Mục tiêu
            mission: Nhiệm vụ
            bot_type: Loại bot (message, comment, post)
            note: Ghi chú
            knowledge: Kiến thức bot
            status: Trạng thái (on, off)
            connect: Kết nối (fb_page_id, instagram_id, etc.)
            language_code: Mã ngôn ngữ (ví dụ: "en", "vi")
        """
        bot_data = {
            "user_id": user_id,
            "name": name,
            "language_code": language_code,
            "identity_id": identity_id,
            "procedure_id": procedure_id,
            "role": role,
            "target": target,
            "mission": mission,
            "note": note,
            "knowledge": knowledge,
            "type": bot_type,
            "bot_type": "message",
            "status": status,
            "connect": connect
        }
        bot = await self.create(bot_data)
        
        # Gửi notification trong background
        if bot and user_id:
            run_in_background(
                self.notify_bot_created,
                user_id=user_id,
                bot_name=name,
                bot_id=str(bot.get("_id"))
            )
        
        return bot
    
    async def get_by_user_id(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Lấy bots theo user_id"""
        filter_query = {"user_id": user_id}
        if status:
            filter_query["status"] = status
        
        return await self.get_all(filter_query=filter_query, sort_by="create_at", sort_order=-1)
    
    async def get_active_bots(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy tất cả bots đang hoạt động"""
        filter_query = {"status": "on"}
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_connection(self, connect_id: str, bot_type: str = None) -> List[Dict[str, Any]]:
        """Lấy bots theo connection ID"""
        filter_query = {"connect": connect_id}
        if bot_type:
            filter_query["type"] = bot_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def activate_bot(self, bot_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Bật bot"""
        bot = await self.update_by_id(bot_id, {"status": "on"})
        
        # Gửi notification trong background
        if bot:
            user_id = bot.get("user_id")
            bot_name = bot.get("name", "Bot")
            if user_id:
                run_in_background(
                    self.notify_bot_activated,
                    user_id=user_id,
                    bot_name=bot_name,
                    bot_id=str(bot_id)
                )
        
        return bot
    
    async def deactivate_bot(self, bot_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Tắt bot"""
        bot = await self.update_by_id(bot_id, {"status": "off"})
        
        # Gửi notification trong background
        if bot:
            user_id = bot.get("user_id")
            bot_name = bot.get("name", "Bot")
            if user_id:
                run_in_background(
                    self.notify_bot_deactivated,
                    user_id=user_id,
                    bot_name=bot_name
                )
        
        return bot
    
    async def update_bot_connection(self, bot_id: Union[str, ObjectId], 
                                  connect_id: str) -> Optional[Dict[str, Any]]:
        """Cập nhật kết nối bot (legacy method, sử dụng cho single connection)"""
        return await self.update_by_id(bot_id, {"connect": connect_id})
    
    async def add_bot_connection(self, bot_id: Union[str, ObjectId], 
                               connection_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Thêm connection mới cho bot"""        
        # Lấy bot hiện tại
        bot = await self.get_by_id(bot_id)
        if not bot:
            return None
        
        # Parse connections hiện tại
        current_connections = []
        if bot.get('connect'):
            try:
                current_connections = json.loads(bot['connect']) if isinstance(bot['connect'], str) else bot['connect']
                if not isinstance(current_connections, list):
                    current_connections = []
            except:
                current_connections = []
        
        # Thêm connection mới
        connection_data['connected_at'] = datetime.now().isoformat()
        current_connections.append(connection_data)
        
        # Cập nhật bot
        connect_json = json.dumps(current_connections)
        return await self.update_by_id(bot_id, {"connect": connect_json})
    
    async def remove_bot_connection(self, bot_id: Union[str, ObjectId], 
                                  social_page_id: str) -> Optional[Dict[str, Any]]:
        """Xóa connection của bot"""        
        # Lấy bot hiện tại
        bot = await self.get_by_id(bot_id)
        if not bot:
            return None
        
        # Parse connections hiện tại
        current_connections = []
        if bot.get('connect'):
            try:
                current_connections = json.loads(bot['connect']) if isinstance(bot['connect'], str) else bot['connect']
                if not isinstance(current_connections, list):
                    current_connections = []
            except:
                current_connections = []
        
        # Xóa connection
        updated_connections = [conn for conn in current_connections if conn.get('social_page_id') != social_page_id]
        
        # Cập nhật bot
        connect_json = json.dumps(updated_connections)
        return await self.update_by_id(bot_id, {"connect": connect_json})
    
    async def get_bot_connections(self, bot_id: Union[str, ObjectId]) -> List[Dict[str, Any]]:
        """Lấy danh sách connections của bot"""        
        bot = await self.get_by_id(bot_id)
        if not bot or not bot.get('connect'):
            return []
        
        try:
            connections = json.loads(bot['connect']) if isinstance(bot['connect'], str) else bot['connect']
            return connections if isinstance(connections, list) else []
        except:
            return []
    
    async def update_bot_knowledge(self, bot_id: Union[str, ObjectId], 
                                 knowledge: str) -> Optional[Dict[str, Any]]:
        """Cập nhật kiến thức bot"""
        return await self.update_by_id(bot_id, {"knowledge": knowledge})
    
    async def get_bot_with_details(self, bot_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """
        Lấy bot với thông tin chi tiết (join identity và procedure)
        """
        try:
            if isinstance(bot_id, str):
                bot_id = ObjectId(bot_id)
            
            pipeline = [
                {"$match": {"_id": bot_id}},
                {
                    "$lookup": {
                        "from": "identities",
                        "localField": "identity_id",
                        "foreignField": "_id",
                        "as": "identity"
                    }
                },
                {
                    "$lookup": {
                        "from": "procedures",
                        "localField": "procedure_id",
                        "foreignField": "_id",
                        "as": "procedure"
                    }
                },
                {
                    "$unwind": {
                        "path": "$identity",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                {
                    "$unwind": {
                        "path": "$procedure",
                        "preserveNullAndEmptyArrays": True
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                return self._serialize_object_id(result[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting bot with details: {str(e)}")
            return None
    
    async def get_user_bots_with_stats(self, user_id: str) -> List[Dict[str, Any]]:
        """Lấy bots của user với thống kê"""
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {
                    "$lookup": {
                        "from": "histories",
                        "localField": "_id",
                        "foreignField": "bot_id",
                        "as": "conversations"
                    }
                },
                {
                    "$addFields": {
                        "total_conversations": {"$size": "$conversations"},
                        "today_conversations": {
                            "$size": {
                                "$filter": {
                                    "input": "$conversations",
                                    "cond": {
                                        "$gte": [
                                            "$$this.create_at",
                                            get_vietnam_now_naive().replace(hour=0, minute=0, second=0, microsecond=0)
                                        ]
                                    }
                                }
                            }
                        }
                    }
                },
                {"$project": {"conversations": 0}},  # Remove conversations array từ result
                {"$sort": {"create_at": -1}}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=100)
            
            return [self._serialize_object_id(result) for result in results]
            
        except Exception as e:
            logger.error(f"Error getting user bots with stats: {str(e)}")
            return []


# Factory class để tạo tất cả bot management managers
class BotManagementFactory:
    """Factory để tạo tất cả Bot Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._identity_manager = None
        self._procedure_manager = None
        self._bot_manager = None
    
    @property
    def identity_manager(self) -> IdentityManager:
        if self._identity_manager is None:
            self._identity_manager = IdentityManager(self.db_manager)
        return self._identity_manager
    
    @property
    def procedure_manager(self) -> ProcedureManager:
        if self._procedure_manager is None:
            self._procedure_manager = ProcedureManager(self.db_manager)
        return self._procedure_manager
    
    @property
    def bot_manager(self) -> BotManager:
        if self._bot_manager is None:
            self._bot_manager = BotManager(self.db_manager)
        return self._bot_manager
