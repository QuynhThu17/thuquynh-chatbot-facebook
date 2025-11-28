"""
Main MongoDB Management Factory
Tích hợp tất cả các factory managers và cung cấp interface thống nhất
"""

import logging
from typing import Dict, Any
from controllers.databases.mongodb.mongodb import MongoDBManager
from .user_management import UserManagementFactory
from .social_media_management import SocialMediaManagementFactory
from .bot_management import BotManagementFactory
from .crm_management import CRMManagementFactory
from .knowledge_management import KnowledgeManagementFactory
from .system_management import SystemManagementFactory
from .additional_management import AdditionalManagementFactory
from .super_admin_management import SuperAdminManagementFactory
from .history_management import HistoryManagementFactory
from .email_verification_management import EmailVerificationManager
from .rate_limit_management import RateLimitManager
from .api_key_management import APIKeyManager, WhiteLabelWebhookManager

logger = logging.getLogger(__name__)

class MongoDBManagementFactory:
    """
    Main factory để access tất cả MongoDB managers
    Singleton pattern để đảm bảo chỉ có một instance
    """
    
    _instance = None
    _db_manager = None
    
    def __new__(cls, db_manager: MongoDBManager = None):
        if cls._instance is None:
            cls._instance = super(MongoDBManagementFactory, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_manager: MongoDBManager = None):
        if self._initialized:
            return
            
        if db_manager is None:
            raise ValueError("MongoDBManager instance is required for first initialization")
        
        self._db_manager = db_manager
        self._initialized = True
        
        # Initialize all factories
        self._user_factory = None
        self._social_media_factory = None
        self._bot_factory = None
        self._crm_factory = None
        self._knowledge_factory = None
        self._system_factory = None
        self._additional_factory = None
        self._super_admin_factory = None
        self._history_factory = None
        
        # Authentication-related managers
        self._email_verification_manager = None
        self._rate_limit_manager = None
        
        # API Key & White Label managers
        self._api_key_manager_v2 = None
        self._white_label_webhook_manager = None
        
        logger.info("MongoDBManagementFactory initialized successfully")
    
    @property
    def db_manager(self) -> MongoDBManager:
        """Get MongoDB manager instance"""
        return self._db_manager
    
    # User Management Properties
    @property
    def user_factory(self) -> UserManagementFactory:
        if self._user_factory is None:
            self._user_factory = UserManagementFactory(self._db_manager)
        return self._user_factory
    
    @property
    def user_manager(self):
        return self.user_factory.user_manager
    
    @property
    def hierarchy_manager(self):
        return self.user_factory.hierarchy_manager
    
    @property
    def feature_manager(self):
        return self.user_factory.feature_manager
    
    @property
    def role_manager(self):
        return self.user_factory.role_manager
    
    @property
    def balance_manager(self):
        return self.user_factory.balance_manager
    
    @property
    def package_manager(self):
        return self.user_factory.package_manager
    
    @property
    def subscription_manager(self):
        return self.user_factory.subscription_manager
    
    @property
    def transaction_manager(self):
        return self.user_factory.transaction_manager
    
    # Authentication Management Properties
    @property
    def email_verification_manager(self):
        if self._email_verification_manager is None:
            self._email_verification_manager = EmailVerificationManager(self._db_manager.database)
        return self._email_verification_manager
    
    @property
    def rate_limit_manager(self):
        if self._rate_limit_manager is None:
            self._rate_limit_manager = RateLimitManager(self._db_manager.database)
        return self._rate_limit_manager
    
    # Social Media Management Properties
    @property
    def social_media_factory(self) -> SocialMediaManagementFactory:
        if self._social_media_factory is None:
            self._social_media_factory = SocialMediaManagementFactory(self._db_manager)
        return self._social_media_factory
    
    @property
    def social_manager(self):
        return self.social_media_factory.social_manager
    
    @property
    def social_account_manager(self):
        return self.social_media_factory.social_account_manager
    
    @property
    def facebook_page_manager(self):
        return self.social_media_factory.facebook_page_manager
    
    # Bot Management Properties
    @property
    def bot_factory(self) -> BotManagementFactory:
        if self._bot_factory is None:
            self._bot_factory = BotManagementFactory(self._db_manager)
        return self._bot_factory
    
    @property
    def identity_manager(self):
        return self.bot_factory.identity_manager
    
    @property
    def procedure_manager(self):
        return self.bot_factory.procedure_manager
    
    @property
    def bot_manager(self):
        return self.bot_factory.bot_manager
    
    # CRM Management Properties
    @property
    def crm_factory(self) -> CRMManagementFactory:
        if self._crm_factory is None:
            self._crm_factory = CRMManagementFactory(self._db_manager)
        return self._crm_factory
    
    @property
    def company_manager(self):
        return self.crm_factory.company_manager
    
    @property
    def contact_manager(self):
        return self.crm_factory.contact_manager
    
    @property
    def customer_manager(self):
        return self.crm_factory.customer_manager
    
    @property
    def product_manager(self):
        return self.crm_factory.product_manager
    
    @property
    def warehouse_manager(self):
        return self.crm_factory.warehouse_manager
    
    @property
    def order_manager(self):
        return self.crm_factory.order_manager
    
    @property
    def shipment_manager(self):
        return self.crm_factory.shipment_manager
    
    @property
    def product_enhanced_manager(self):
        """Enhanced product manager với image embedding - inject dependencies"""
        manager = self.crm_factory.product_enhanced_manager
        # ✅ Inject dependencies nếu chưa có
        if manager.knowledge_chunk_manager is None:
            manager.set_dependencies(
                knowledge_chunk_manager=self.knowledge_chunk_manager,
                s3_manager=None  # TODO: Add S3Manager khi cần
            )
        return manager
    
    # Knowledge Management Properties
    @property
    def knowledge_factory(self) -> KnowledgeManagementFactory:
        if self._knowledge_factory is None:
            self._knowledge_factory = KnowledgeManagementFactory(self._db_manager)
        return self._knowledge_factory
    
    @property
    def knowledge_chunk_manager(self):
        return self.knowledge_factory.knowledge_chunk_manager
    
    @property
    def document_manager(self):
        return self.knowledge_factory.document_manager
    
    @property
    def feedback_manager(self):
        return self.knowledge_factory.feedback_manager
    
    # History Management Properties
    @property
    def history_factory(self) -> HistoryManagementFactory:
        if self._history_factory is None:
            self._history_factory = HistoryManagementFactory(self._db_manager)
        return self._history_factory
    
    @property
    def history_manager(self):
        return self.history_factory.history_manager
    
    # System Management Properties
    @property
    def system_factory(self) -> SystemManagementFactory:
        if self._system_factory is None:
            self._system_factory = SystemManagementFactory(self._db_manager)
        return self._system_factory
    
    @property
    def notification_manager(self):
        return self.system_factory.notification_manager
    
    @property
    def user_settings_manager(self):
        return self.system_factory.user_settings_manager
    
    @property
    def api_key_manager(self):
        return self.system_factory.api_key_manager
    
    @property
    def session_manager(self):
        return self.system_factory.session_manager
    
    @property
    def audit_log_manager(self):
        return self.system_factory.audit_log_manager
    
    @property
    def file_upload_manager(self):
        return self.system_factory.file_upload_manager
    
    @property
    def support_ticket_manager(self):
        return self.system_factory.support_ticket_manager
    
    @property
    def faq_manager(self):
        return self.system_factory.faq_manager
    
    @property
    def feature_request_manager(self):
        return self.system_factory.feature_request_manager
    
    @property
    def help_document_manager(self):
        return self.system_factory.help_document_manager
    
    @property
    def feedback_manager(self):
        return self.system_factory.feedback_manager
    
    @property
    def live_chat_manager(self):
        return self.system_factory.live_chat_manager
    
    # Additional Management Properties
    @property
    def additional_factory(self) -> AdditionalManagementFactory:
        if self._additional_factory is None:
            self._additional_factory = AdditionalManagementFactory(self._db_manager)
        return self._additional_factory
    
    @property
    def usage_token_manager(self):
        return self.additional_factory.usage_token_manager
    
    @property
    def token_log_manager(self):
        return self.additional_factory.token_log_manager
    
    @property
    def automation_messenger_manager(self):
        return self.additional_factory.automation_messenger_manager
    
    @property
    def webhook_manager(self):
        return self.additional_factory.webhook_manager
    
    @property
    def template_manager(self):
        return self.additional_factory.template_manager
    
    @property
    def analytics_data_manager(self):
        return self.additional_factory.analytics_data_manager
    
    @property
    def conversation_context_manager(self):
        return self.additional_factory.conversation_context_manager
    
    @property
    def language_manager(self):
        return self.additional_factory.language_manager
    
    @property
    def translation_manager(self):
        return self.additional_factory.translation_manager

    @property
    def major_statistic_manager(self):
        return self.additional_factory.major_statistic_manager
    
    # SuperAdmin Management Properties
    @property
    def super_admin_factory(self) -> SuperAdminManagementFactory:
        if self._super_admin_factory is None:
            self._super_admin_factory = SuperAdminManagementFactory(self._db_manager)
        return self._super_admin_factory
    
    @property
    def super_hierarchy_manager(self):
        return self.super_admin_factory.super_hierarchy_manager
    
    @property
    def partner_license_manager(self):
        return self.super_admin_factory.partner_license_manager
    
    @property
    def system_monitoring_manager(self):
        return self.super_admin_factory.system_monitoring_manager
    
    @property
    def data_aggregation_manager(self):
        return self.super_admin_factory.data_aggregation_manager
    
    # API Key Management V2 (for White Label & Partners)
    @property
    def api_key_manager_v2(self) -> APIKeyManager:
        """New API Key Manager with full features for White Label partners"""
        if self._api_key_manager_v2 is None:
            self._api_key_manager_v2 = APIKeyManager(self._db_manager)
        return self._api_key_manager_v2
    
    @property
    def white_label_webhook_manager(self) -> WhiteLabelWebhookManager:
        """Manager for White Label webhook logs"""
        if self._white_label_webhook_manager is None:
            self._white_label_webhook_manager = WhiteLabelWebhookManager(self._db_manager)
        return self._white_label_webhook_manager
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check cho tất cả managers"""
        health_status = {
            "db_connection": False,
            "collections": {},
            "total_documents": 0
        }
        
        try:
            # Check database connection
            await self._db_manager.database.command("ismaster")
            health_status["db_connection"] = True
            
            # Check each collection
            collection_names = [
                "users", "hierarchy", "features", "roles", "balances", "packages", 
                "subscriptions", "transactions", "socials", "social_accounts", 
                "social_facebook_pages", "social_instagram_accounts", "social_twitter_accounts",
                "social_linkedin_accounts", "identities", "procedures", "bots",
                "companies", "contacts", "products", "warehouses", "orders", "shipments",
                "knowledge_chunks", "documents", "histories", "feedback",
                "notifications", "user_settings", "api_keys", "sessions", "audit_logs",
                "file_uploads", "support_tickets", "faqs", "feature_requests",
                "webhooks", "templates", "analytics_data", "conversation_contexts",
                "languages", "translations", "usage_tokens", "automation_messenger"
            ]
            
            total_docs = 0
            for collection_name in collection_names:
                try:
                    collection = self._db_manager.database[collection_name]
                    count = await collection.count_documents({})
                    health_status["collections"][collection_name] = count
                    total_docs += count
                except Exception as e:
                    health_status["collections"][collection_name] = f"Error: {str(e)}"
            
            health_status["total_documents"] = total_docs
            
        except Exception as e:
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {str(e)}")
        
        return health_status
    
    def get_all_managers(self) -> Dict[str, Any]:
        """Get dictionary of all managers"""
        return {
            # User Management
            "user_manager": self.user_manager,
            "hierarchy_manager": self.hierarchy_manager,
            "feature_manager": self.feature_manager,
            "role_manager": self.role_manager,
            "balance_manager": self.balance_manager,
            "package_manager": self.package_manager,
            "subscription_manager": self.subscription_manager,
            "transaction_manager": self.transaction_manager,
            
            # Social Media Management
            "social_manager": self.social_manager,
            "social_account_manager": self.social_account_manager,
            "facebook_page_manager": self.facebook_page_manager,
            "instagram_account_manager": self.instagram_account_manager,
            "twitter_account_manager": self.twitter_account_manager,
            "linkedin_account_manager": self.linkedin_account_manager,
            
            # Bot Management
            "identity_manager": self.identity_manager,
            "procedure_manager": self.procedure_manager,
            "bot_manager": self.bot_manager,
            
            # CRM Management
            "company_manager": self.company_manager,
            "contact_manager": self.contact_manager,
            "product_manager": self.product_manager,
            "warehouse_manager": self.warehouse_manager,
            "order_manager": self.order_manager,
            "shipment_manager": self.shipment_manager,
            
            # Knowledge Management
            "knowledge_chunk_manager": self.knowledge_chunk_manager,
            "document_manager": self.document_manager,
            "history_manager": self.history_manager,
            "feedback_manager": self.feedback_manager,
            
            # System Management
            "notification_manager": self.notification_manager,
            "user_settings_manager": self.user_settings_manager,
            "api_key_manager": self.api_key_manager,
            "session_manager": self.session_manager,
            "audit_log_manager": self.audit_log_manager,
            "file_upload_manager": self.file_upload_manager,
            "support_ticket_manager": self.support_ticket_manager,
            "faq_manager": self.faq_manager,
            "feature_request_manager": self.feature_request_manager,
            
            # Additional Management
            "usage_token_manager": self.usage_token_manager,
            "automation_messenger_manager": self.automation_messenger_manager,
            "webhook_manager": self.webhook_manager,
            "template_manager": self.template_manager,
            "analytics_data_manager": self.analytics_data_manager,
            "conversation_context_manager": self.conversation_context_manager,
            "language_manager": self.language_manager,
            "translation_manager": self.translation_manager,
            "token_log_manager": self.token_log_manager,
            
            # SuperAdmin Management
            "super_hierarchy_manager": self.super_hierarchy_manager,
            "partner_license_manager": self.partner_license_manager,
            "system_monitoring_manager": self.system_monitoring_manager,
            "data_aggregation_manager": self.data_aggregation_manager
        }


# Global instance
_management_factory = None

def get_mongodb_factory(db_manager: MongoDBManager = None) -> MongoDBManagementFactory:
    """
    Get global MongoDB Management Factory instance
    """
    global _management_factory
    if _management_factory is None:
        if db_manager is None:
            raise ValueError("MongoDBManager is required for first initialization")
        _management_factory = MongoDBManagementFactory(db_manager)
    return _management_factory
