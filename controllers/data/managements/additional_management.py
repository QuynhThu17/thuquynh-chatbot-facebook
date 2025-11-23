"""
Additional Management Modules
Quản lý usage_tokens, automation_messenger, webhooks, templates, analytics_data, 
conversation_contexts, languages, translations
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from .base_manager import BaseManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

class UsageTokenManager(BaseManager):
    """Manager cho usage_tokens collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "usage_tokens")
    
    async def create_usage_token(self, user_id: str, model: str, input_token: int,
                               output_token: int, total_cost: float, message: str = None) -> Dict[str, Any]:
        """
        Tạo usage token record
        
        Args:
            user_id: ID user
            model: Tên model (gpt-4, claude-3, etc.)
            input_token: Số input tokens
            output_token: Số output tokens
            total_cost: Tổng chi phí
            message: Message context
        """
        total_token = input_token + output_token
        usage_data = {
            "user_id": user_id,
            "model": model,
            "input_token": input_token,
            "output_token": output_token,
            "total_token": total_token,
            "total_cost": total_cost,
            "message": message,
            "timestamp": get_vietnam_now_naive()
        }
        return await self.create(usage_data)
    
    async def get_user_usage(self, user_id: str, days: int = 30,
                           model: str = None) -> List[Dict[str, Any]]:
        """Lấy usage của user trong N ngày"""
        start_date = get_vietnam_now_naive() - timedelta(days=days)
        filter_query = {
            "user_id": user_id,
            "timestamp": {"$gte": start_date}
        }
        if model:
            filter_query["model"] = model
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="timestamp",
            sort_order=-1
        )
    
    async def get_usage_stats(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Lấy thống kê usage của user"""
        try:
            start_date = get_vietnam_now_naive() - timedelta(days=days)
            
            pipeline = [
                {
                    "$match": {
                        "user_id": user_id,
                        "timestamp": {"$gte": start_date}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_tokens": {"$sum": "$total_token"},
                        "total_cost": {"$sum": "$total_cost"},
                        "total_requests": {"$sum": 1},
                        "by_model": {
                            "$push": {
                                "model": "$model",
                                "tokens": "$total_token",
                                "cost": "$total_cost"
                            }
                        }
                    }
                }
            ]
            
            cursor = self.collection.aggregate(pipeline)
            result = await cursor.to_list(length=1)
            
            if result:
                stats = result[0]
                
                # Group by model
                model_stats = {}
                for item in stats.get("by_model", []):
                    model = item["model"]
                    if model not in model_stats:
                        model_stats[model] = {"tokens": 0, "cost": 0.0, "requests": 0}
                    
                    model_stats[model]["tokens"] += item["tokens"]
                    model_stats[model]["cost"] += item["cost"]
                    model_stats[model]["requests"] += 1
                
                stats["by_model"] = model_stats
                return self._serialize_object_id(stats)
            
            return {
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_requests": 0,
                "by_model": {}
            }
            
        except Exception as e:
            logger.error(f"Error getting usage stats: {str(e)}")
            return {}


class TokenLogManager(BaseManager):
    """Manager cho tokens collection (LLM usage logs)"""

    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "tokens")

    async def aggregate_tokens_by_users(
        self,
        user_ids: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Tổng hợp token usage theo danh sách user_id.
        """
        if not user_ids:
            return {}

        match_stage: Dict[str, Any] = {"user_id": {"$in": user_ids}}

        if start_time or end_time:
            time_filter: Dict[str, Any] = {}
            if start_time:
                time_filter["$gte"] = start_time
            if end_time:
                time_filter["$lte"] = end_time
            match_stage["timestamp"] = time_filter

        pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$user_id",
                    "prompt_tokens": {"$sum": "$prompt_tokens"},
                    "completion_tokens": {"$sum": "$completion_tokens"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "total_cost": {"$sum": "$total_cost"},
                    "successful_requests": {"$sum": "$successful_requests"},
                    "request_count": {"$sum": 1},
                    "last_activity": {"$max": "$timestamp"},
                }
            },
        ]

        try:
            cursor = self.collection.aggregate(pipeline)
            docs = await cursor.to_list(length=len(user_ids) + 100)

            return {
                doc["_id"]: {
                    "prompt_tokens": doc.get("prompt_tokens", 0),
                    "completion_tokens": doc.get("completion_tokens", 0),
                    "total_tokens": doc.get("total_tokens", 0),
                    "total_cost": doc.get("total_cost", 0.0),
                    "successful_requests": doc.get("successful_requests", 0),
                    "request_count": doc.get("request_count", 0),
                    "last_activity": doc.get("last_activity"),
                }
                for doc in docs
            }
        except Exception as e:
            logger.error(f"Error aggregating token logs: {str(e)}")
            return {}

    async def get_tokens(
        self,
        user_id: Optional[str] = None,
        company_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        page_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
        status: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "timestamp",
        sort_order: int = -1,
    ) -> Dict[str, Any]:
        """
        Lấy danh sách token logs với các điều kiện lọc.
        """
        try:
            filter_query: Dict[str, Any] = {}
            field_map = {
                "user_id": user_id,
                "company_id": company_id,
                "bot_id": bot_id,
                "page_id": page_id,
                "sender_id": sender_id,
                "session_id": session_id,
                "model": model,
                "status": status,
            }

            for field, value in field_map.items():
                if value is not None and value != "":
                    filter_query[field] = value

            if start_time or end_time:
                time_filter: Dict[str, Any] = {}
                if start_time:
                    time_filter["$gte"] = start_time
                if end_time:
                    time_filter["$lte"] = end_time
                filter_query["timestamp"] = time_filter

            total = await self.count(filter_query)
            tokens = await self.get_all(
                filter_query=filter_query,
                skip=skip,
                limit=limit,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            return {
                "items": tokens,
                "total": total,
            }
        except Exception as e:
            logger.error(f"Error getting token logs: {str(e)}")
            return {
                "items": [],
                "total": 0,
                "error": str(e),
            }


class AutomationMessengerManager(BaseManager):
    """Manager cho automation_messenger collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "automation_messenger")
    
    async def create_automation(self, automation_type: str, social_id: str,
                              social_identification: Dict[str, Any], content: str,
                              datetime_scheduled: datetime, status: str = "scheduled") -> Dict[str, Any]:
        """
        Tạo automation messenger
        
        Args:
            automation_type: Loại automation
            social_id: ID social platform
            social_identification: Thông tin identify
            content: Nội dung message
            datetime_scheduled: Thời gian schedule
            status: Trạng thái (scheduled, sent, failed)
        """
        automation_data = {
            "type": automation_type,
            "social_id": social_id,
            "social_identification": social_identification,
            "content": content,
            "datetime": datetime_scheduled,
            "status": status
        }
        return await self.create(automation_data)
    
    async def get_scheduled_automations(self, before_datetime: datetime = None) -> List[Dict[str, Any]]:
        """Lấy các automations đã scheduled"""
        if before_datetime is None:
            before_datetime = get_vietnam_now_naive()
        
        return await self.get_all(
            filter_query={
                "status": "scheduled",
                "datetime": {"$lte": before_datetime}
            },
            sort_by="datetime",
            sort_order=1
        )
    
    async def mark_as_sent(self, automation_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """Đánh dấu đã gửi"""
        return await self.update_by_id(automation_id, {"status": "sent"})
    
    async def mark_as_failed(self, automation_id: Union[str, ObjectId], error_message: str = None) -> Optional[Dict[str, Any]]:
        """Đánh dấu thất bại"""
        update_data = {"status": "failed"}
        if error_message:
            update_data["error_message"] = error_message
        
        return await self.update_by_id(automation_id, update_data)


class WebhookManager(BaseManager):
    """Manager cho webhooks collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "webhooks")
    
    async def create_webhook(self, user_id: str, name: str, url: str, events: List[str],
                           secret_key: str = None, is_active: bool = True) -> Dict[str, Any]:
        """
        Tạo webhook mới
        
        Args:
            user_id: ID user
            name: Tên webhook
            url: URL webhook
            events: List events để listen
            secret_key: Secret key để verify
            is_active: Trạng thái active
        """
        webhook_data = {
            "user_id": user_id,
            "name": name,
            "url": url,
            "events": events,
            "is_active": is_active,
            "secret_key": secret_key,
            "retry_count": 0,
            "last_response": None
        }
        return await self.create(webhook_data)
    
    async def get_by_user_id(self, user_id: str, is_active: bool = None) -> List[Dict[str, Any]]:
        """Lấy webhooks của user"""
        filter_query = {"user_id": user_id}
        if is_active is not None:
            filter_query["is_active"] = is_active
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_webhooks_for_event(self, event_name: str, user_id: str = None) -> List[Dict[str, Any]]:
        """Lấy webhooks listen event cụ thể"""
        filter_query = {
            "is_active": True,
            "events": {"$in": [event_name]}
        }
        if user_id:
            filter_query["user_id"] = user_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def update_last_response(self, webhook_id: Union[str, ObjectId], 
                                 response_code: int, response_body: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật last response"""
        last_response = {
            "timestamp": get_vietnam_now_naive(),
            "status_code": response_code,
            "body": response_body
        }
        return await self.update_by_id(webhook_id, {"last_response": last_response})


class TemplateManager(BaseManager):
    """Manager cho templates collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "templates")
    
    async def create_template(self, user_id: str, name: str, template_type: str, content: str,
                            variables: List[str] = None, language: str = "vi",
                            is_default: bool = False) -> Dict[str, Any]:
        """
        Tạo template mới
        
        Args:
            user_id: ID user
            name: Tên template
            template_type: message, email, notification
            content: Nội dung template
            variables: List biến dynamic
            language: Ngôn ngữ
            is_default: Có phải template mặc định
        """
        template_data = {
            "user_id": user_id,
            "name": name,
            "type": template_type,
            "content": content,
            "variables": variables or [],
            "language": language,
            "is_default": is_default
        }
        return await self.create(template_data)
    
    async def get_by_user_id(self, user_id: str, template_type: str = None,
                           language: str = None) -> List[Dict[str, Any]]:
        """Lấy templates của user"""
        filter_query = {"user_id": user_id}
        if template_type:
            filter_query["type"] = template_type
        if language:
            filter_query["language"] = language
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_default_templates(self, template_type: str = None,
                                  language: str = "vi") -> List[Dict[str, Any]]:
        """Lấy default templates"""
        filter_query = {"is_default": True, "language": language}
        if template_type:
            filter_query["type"] = template_type
        
        return await self.get_all(filter_query=filter_query)
    
    async def render_template(self, template_id: Union[str, ObjectId], 
                            variables: Dict[str, str]) -> Optional[str]:
        """Render template với variables"""
        template = await self.get_by_id(template_id)
        if template:
            content = template.get("content", "")
            
            # Simple template rendering - replace {{variable}}
            for var_name, var_value in variables.items():
                placeholder = f"{{{{{var_name}}}}}"
                content = content.replace(placeholder, str(var_value))
            
            return content
        
        return None


class AnalyticsDataManager(BaseManager):
    """Manager cho analytics_data collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "analytics_data")
    
    async def create_analytics_data(self, user_id: str, bot_id: str, date: datetime,
                                  metric_type: str, value: float, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo analytics data
        
        Args:
            user_id: ID user
            bot_id: ID bot
            date: Ngày
            metric_type: messages_sent, conversations_started, orders_created
            value: Giá trị metric
            metadata: Metadata bổ sung
        """
        analytics_data = {
            "user_id": user_id,
            "bot_id": bot_id,
            "date": date,
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {}
        }
        return await self.create(analytics_data)
    
    async def get_analytics_data(self, user_id: str, metric_type: str = None,
                               bot_id: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """Lấy analytics data"""
        start_date = get_vietnam_now_naive() - timedelta(days=days)
        filter_query = {
            "user_id": user_id,
            "date": {"$gte": start_date}
        }
        if metric_type:
            filter_query["metric_type"] = metric_type
        if bot_id:
            filter_query["bot_id"] = bot_id
        
        return await self.get_all(
            filter_query=filter_query,
            sort_by="date",
            sort_order=-1
        )
    
    async def aggregate_metrics(self, user_id: str, metric_type: str,
                              days: int = 30, bot_id: str = None) -> Dict[str, Any]:
        """Tổng hợp metrics theo ngày"""
        try:
            start_date = get_vietnam_now_naive() - timedelta(days=days)
            
            match_filter = {
                "user_id": user_id,
                "metric_type": metric_type,
                "date": {"$gte": start_date}
            }
            if bot_id:
                match_filter["bot_id"] = bot_id
            
            pipeline = [
                {"$match": match_filter},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": "$date"
                            }
                        },
                        "total_value": {"$sum": "$value"},
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=days)
            
            return {
                "metric_type": metric_type,
                "period_days": days,
                "data": [self._serialize_object_id(result) for result in results]
            }
            
        except Exception as e:
            logger.error(f"Error aggregating metrics: {str(e)}")
            return {"metric_type": metric_type, "period_days": days, "data": []}


class ConversationContextManager(BaseManager):
    """Manager cho conversation_contexts collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "conversation_contexts")
    
    async def create_context(self, session_id: str, user_id: str, bot_id: str,
                           current_step: str = None, context_data: Dict[str, Any] = None,
                           last_message_id: str = None) -> Dict[str, Any]:
        """
        Tạo conversation context
        
        Args:
            session_id: ID session
            user_id: ID user
            bot_id: ID bot
            current_step: Bước hiện tại trong conversation
            context_data: Dữ liệu context
            last_message_id: ID message cuối
        """
        context = {
            "session_id": session_id,
            "user_id": user_id,
            "bot_id": bot_id,
            "current_step": current_step,
            "context_data": context_data or {},
            "last_message_id": last_message_id,
            "is_active": True
        }
        return await self.create(context)
    
    async def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy context theo session_id"""
        contexts = await self.get_all(filter_query={"session_id": session_id}, limit=1)
        return contexts[0] if contexts else None
    
    async def update_context(self, session_id: str, current_step: str = None,
                           context_data: Dict[str, Any] = None, last_message_id: str = None) -> Optional[Dict[str, Any]]:
        """Cập nhật context"""
        update_data = {}
        if current_step is not None:
            update_data["current_step"] = current_step
        if context_data is not None:
            update_data["context_data"] = context_data
        if last_message_id is not None:
            update_data["last_message_id"] = last_message_id
        
        if update_data:
            contexts = await self.get_all(filter_query={"session_id": session_id}, limit=1)
            if contexts:
                return await self.update_by_id(contexts[0]["_id"], update_data)
        
        return None
    
    async def end_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Kết thúc context"""
        contexts = await self.get_all(filter_query={"session_id": session_id}, limit=1)
        if contexts:
            return await self.update_by_id(contexts[0]["_id"], {"is_active": False})
        return None


class LanguageManager(BaseManager):
    """Manager cho languages collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "languages")
    
    async def create_language(self, code: str, name: str, is_active: bool = True) -> Dict[str, Any]:
        """Tạo language mới"""
        language_data = {
            "code": code,  # vi, en, zh, etc.
            "name": name,
            "is_active": is_active
        }
        return await self.create(language_data)
    
    async def get_active_languages(self) -> List[Dict[str, Any]]:
        """Lấy các ngôn ngữ đang active"""
        return await self.get_all(filter_query={"is_active": True})
    
    async def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Lấy language theo code"""
        languages = await self.get_all(filter_query={"code": code}, limit=1)
        return languages[0] if languages else None


class TranslationManager(BaseManager):
    """Manager cho translations collection"""
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "translations")
    
    async def create_translation(self, language_id: str, key_name: str, translated_text: str,
                               category: str = "ui") -> Dict[str, Any]:
        """
        Tạo translation mới
        
        Args:
            language_id: ID language
            key_name: Key cần translate
            translated_text: Text đã translate
            category: ui, bot, notification
        """
        translation_data = {
            "language_id": language_id,
            "key_name": key_name,
            "translated_text": translated_text,
            "category": category
        }
        return await self.create(translation_data)
    
    async def get_translations(self, language_id: str, category: str = None) -> List[Dict[str, Any]]:
        """Lấy translations theo language"""
        filter_query = {"language_id": language_id}
        if category:
            filter_query["category"] = category
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_translation_dict(self, language_id: str, category: str = None) -> Dict[str, str]:
        """Lấy translations dưới dạng dictionary"""
        translations = await self.get_translations(language_id, category)
        return {
            t["key_name"]: t["translated_text"] 
            for t in translations
        }
    
    async def translate_key(self, language_id: str, key_name: str, 
                          default_text: str = None) -> str:
        """Translate một key cụ thể"""
        translations = await self.get_all(
            filter_query={"language_id": language_id, "key_name": key_name},
            limit=1
        )
        
        if translations:
            return translations[0].get("translated_text", default_text or key_name)
        
        return default_text or key_name


# Factory class
class AdditionalManagementFactory:
    """Factory để tạo tất cả Additional Management managers"""
    
    def __init__(self, db_manager: MongoDBManager):
        self.db_manager = db_manager
        self._usage_token_manager = None
        self._token_log_manager = None
        self._automation_messenger_manager = None
        self._webhook_manager = None
        self._template_manager = None
        self._analytics_data_manager = None
        self._conversation_context_manager = None
        self._language_manager = None
        self._translation_manager = None
    
    @property
    def usage_token_manager(self) -> UsageTokenManager:
        if self._usage_token_manager is None:
            self._usage_token_manager = UsageTokenManager(self.db_manager)
        return self._usage_token_manager
    
    @property
    def token_log_manager(self) -> TokenLogManager:
        if self._token_log_manager is None:
            self._token_log_manager = TokenLogManager(self.db_manager)
        return self._token_log_manager
    
    @property
    def automation_messenger_manager(self) -> AutomationMessengerManager:
        if self._automation_messenger_manager is None:
            self._automation_messenger_manager = AutomationMessengerManager(self.db_manager)
        return self._automation_messenger_manager
    
    @property
    def webhook_manager(self) -> WebhookManager:
        if self._webhook_manager is None:
            self._webhook_manager = WebhookManager(self.db_manager)
        return self._webhook_manager
    
    @property
    def template_manager(self) -> TemplateManager:
        if self._template_manager is None:
            self._template_manager = TemplateManager(self.db_manager)
        return self._template_manager
    
    @property
    def analytics_data_manager(self) -> AnalyticsDataManager:
        if self._analytics_data_manager is None:
            self._analytics_data_manager = AnalyticsDataManager(self.db_manager)
        return self._analytics_data_manager
    
    @property
    def conversation_context_manager(self) -> ConversationContextManager:
        if self._conversation_context_manager is None:
            self._conversation_context_manager = ConversationContextManager(self.db_manager)
        return self._conversation_context_manager
    
    @property
    def language_manager(self) -> LanguageManager:
        if self._language_manager is None:
            self._language_manager = LanguageManager(self.db_manager)
        return self._language_manager
    
    @property
    def translation_manager(self) -> TranslationManager:
        if self._translation_manager is None:
            self._translation_manager = TranslationManager(self.db_manager)
        return self._translation_manager
