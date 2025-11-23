"""
Bot Messenger Agent V2
Xây dựng bot agent với đầy đủ tính năng:
- Lấy thông tin bot từ page_id
- RAG với knowledge_chunks
- Quản lý lịch sử trò chuyện
- Tools cho customer và order management
"""

import logging
import json
import re
import asyncio
import requests
from PIL import Image
import threading
import io
import torch
import traceback
from datetime import datetime
import urllib3
import os  # ✅ ADD: Missing import

# ✅ Disable SSL warnings khi download ảnh từ Facebook CDN
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool, tool
from langchain_community.callbacks import get_openai_callback

# Import bot models
from bot.models import BotResponse, CustomerInfo, OrderInfo

# LangChain changed its agents exports in newer versions.
# Try importing the older names; if not available, provide a small
# compatibility shim that maps the expected symbols to the new API.
try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
except Exception:  # pragma: no cover - compatibility shim for different langchain versions
    from langchain.agents import create_agent

    def create_openai_tools_agent(llm, tools, prompt, **kwargs):
        """
        Compatibility wrapper that attempts to call the newer create_agent API
        while keeping the older call signature used by this codebase.
        """
        # Try common call variations for create_agent
        try:
            return create_agent(llm, tools=tools, prompt=prompt)
        except TypeError:
            try:
                return create_agent(model=llm, tools=tools, prompt=prompt)
            except Exception:
                # Last-resort: return a simple object that exposes run/arun
                class _SimpleAgent:
                    def __init__(self, llm, tools, prompt):
                        self.llm = llm
                        self.tools = tools
                        self.prompt = prompt

                    def run(self, input_text: str):
                        # Try several common method names on the model
                        if hasattr(self.llm, "predict"):
                            return self.llm.predict(input_text)
                        if hasattr(self.llm, "generate"):
                            return self.llm.generate([input_text])
                        if hasattr(self.llm, "__call__"):
                            return self.llm(input_text)
                        raise RuntimeError("No compatible call method found on llm")

                return _SimpleAgent(llm, tools, prompt)

    class AgentExecutor:  # pragma: no cover - lightweight compatibility executor
        """Small compatibility Executor exposing a .run/.arun that delegates to
        the created agent. This is intentionally minimal to avoid deep
        coupling with langchain internals.
        """

        def __init__(self, agent, tools=None, **kwargs):
            self.agent = agent
            self.tools = tools or []

        def run(self, input_text: str):
            # Prefer agent.run, then agent.arun (async), then call the agent
            if hasattr(self.agent, "run"):
                return self.agent.run(input_text)
            if hasattr(self.agent, "arun"):
                import asyncio

                return asyncio.get_event_loop().run_until_complete(self.agent.arun(input_text))
            # If the agent is a Runnable or callable, try calling it
            if callable(self.agent):
                try:
                    return self.agent(input_text)
                except TypeError:
                    # maybe expects keyword 'input'
                    return self.agent(input=input_text)
            raise RuntimeError("Agent is not runnable")
                
# Calculate cosine similarity with each image chunk
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
                
# Import configs and environments
from configs import environment, constant
from controllers.data.managements import get_mongodb_factory
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.databases.mongodb.ensure_indexes import ensure_product_indexes
from controllers.rag.retrieval_service import RAGRetrievalService
from controllers.data.managements import MongoDBManagementFactory

from configs.environment import get_image_embedding_model
from configs.prompts import prompt_facebook_messenger
from controllers.socials.facebook.facebook_send_messenger import send_facebook_messenger, send_typing_action
from controllers.socials.facebook.facebook_connect import get_sender_id_info
from bot.tools.facebook_messenger_tools import FacebookMessengerTools

logger = logging.getLogger(__name__)

# Delay loading image embedding model until needed to avoid startup failures

# ⚡ SPEED OPTIMIZATION: Pre-compiled regex patterns (compile 1 lần thay vì mỗi lần dùng)
COMPILED_REGEX = {
    'url': re.compile(r"\b(?:https?://|www\.)\S+\b", flags=re.UNICODE),
    'multiple_asterisks': re.compile(r"\*\*+", flags=re.UNICODE),
    'sentence_split': re.compile(r'(?<=[.!?])\s+(?=[A-ZĐÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ])', flags=re.UNICODE),
    'list_item': re.compile(r'^\s*(\d+\.|[\-\+\*])\s+', flags=re.UNICODE | re.MULTILINE),
    'end_punctuation': re.compile(r'[.!?…]+$', flags=re.UNICODE),
    'image_url_simple': re.compile(r'(https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp))', flags=re.IGNORECASE),
    # ✅ FIX: Mở rộng regex để match nhiều domain Facebook CDN hơn
    'image_url_fb': re.compile(r'(https?://(?:scontent|platform-lookaside|scontent-[a-z0-9-]+)\.(?:fbsbx\.com|fbcdn\.net|xx\.fbcdn\.net)[^\s]+)', flags=re.IGNORECASE),
    'markdown_image': re.compile(r'!\[.*?\]\((https?://[^\s]+)\)', flags=re.IGNORECASE),
    # ✅ NEW: Match bất kỳ URL nào có chứa "fbcdn" hoặc "fbsbx" (Facebook CDN)
    'image_url_fb_cdn': re.compile(r'(https?://[^\s]*(?:fbcdn|fbsbx)[^\s]+)', flags=re.IGNORECASE)
}

# Message Buffer để gom nhóm tin nhắn liên tiếp
class MessageBuffer:
    """Buffer để gom nhóm các tin nhắn liên tiếp từ cùng user trong khoảng thời gian ngắn"""
    
    def __init__(self, buffer_time: float = 2.0):
        """
        Args:
            buffer_time: Thời gian chờ (giây) để gom nhóm tin nhắn. Mặc định 2 giây.
        """
        self.buffer_time = buffer_time
        self.buffers = {}  # {session_key: {"messages": [], "task": Task, "timestamp": float, "is_processing": bool, "response_sent": bool}}
        self.lock = asyncio.Lock()
    
    def _get_session_key(self, sender_id: str, page_id: str) -> str:
        """Tạo key duy nhất cho mỗi conversation session"""
        return f"{page_id}_{sender_id}"

    async def add_message(self, sender_id: str, page_id: str, bot_id: str, message: str, send_facebook: bool, processor_func, company_id: str = None) -> None:
        """
        Thêm tin nhắn vào buffer và schedule xử lý
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID
            bot_id: Bot ID
            message: Tin nhắn từ user
            send_facebook: Có gửi response về Facebook hay không
            processor_func: Hàm xử lý tin nhắn (async function)
            company_id: ID của company
        """
        session_key = self._get_session_key(sender_id, page_id)
        
        async with self.lock:
            current_time = asyncio.get_event_loop().time()
            
            # Nếu đã có buffer cho session này
            if session_key in self.buffers:
                buffer_data = self.buffers[session_key]
                
                # ✅ CHỈ CANCEL nếu bot CHƯA GỬI RESPONSE về Messenger
                # Nếu đã gửi rồi thì tạo buffer mới
                if buffer_data.get("response_sent", False):
                    # Bot đã gửi response → tạo buffer mới cho tin nhắn này
                    logger.info(f"🔄 Previous response sent, creating new buffer for session {session_key}")
                    self.buffers[session_key] = {
                        "messages": [message],
                        "task": None,
                        "timestamp": current_time,
                        "sender_id": sender_id,
                        "page_id": page_id,
                        "bot_id": bot_id,
                        "send_facebook": send_facebook,
                        "company_id": company_id,
                        "is_processing": False,
                        "response_sent": False
                    }
                else:
                    # Bot chưa gửi response → cancel và gộp tin nhắn
                    if buffer_data["task"] and not buffer_data["task"].done():
                        buffer_data["task"].cancel()
                        logger.info(f"⏸️ Cancelled previous task, buffering message #{len(buffer_data['messages']) + 1} for session {session_key}")
                    
                    # Thêm message mới vào buffer
                    buffer_data["messages"].append(message)
                    buffer_data["timestamp"] = current_time
                    # Update send_facebook flag (use the latest value)
                    buffer_data["send_facebook"] = send_facebook
                    # Update company_id if provided
                    if company_id:
                        buffer_data["company_id"] = company_id
            else:
                # Tạo buffer mới
                self.buffers[session_key] = {
                    "messages": [message],
                    "task": None,
                    "timestamp": current_time,
                    "sender_id": sender_id,
                    "page_id": page_id,
                    "bot_id": bot_id,
                    "send_facebook": send_facebook,
                    "company_id": company_id,
                    "is_processing": False,
                    "response_sent": False
                }
                logger.info(f"📨 Created new buffer for session {session_key}")
            
            # Schedule task mới để xử lý sau buffer_time
            task = asyncio.create_task(
                self._process_after_delay(session_key, processor_func)
            )
            self.buffers[session_key]["task"] = task
    
    async def _process_after_delay(self, session_key: str, processor_func) -> None:
        """
        Đợi buffer_time rồi xử lý tất cả tin nhắn trong buffer
        """
        try:
            # Đợi buffer_time
            await asyncio.sleep(self.buffer_time)
            
            async with self.lock:
                if session_key not in self.buffers:
                    return
                
                buffer_data = self.buffers[session_key]
                
                # ✅ Đánh dấu đang xử lý
                buffer_data["is_processing"] = True
                
                messages = buffer_data["messages"]
                sender_id = buffer_data["sender_id"]
                page_id = buffer_data["page_id"]
                bot_id = buffer_data["bot_id"]
                send_facebook = buffer_data["send_facebook"]
                company_id = buffer_data.get("company_id")
                
                # Gộp tất cả tin nhắn thành một
                combined_message = "\n".join(messages)
                
                logger.info(f"🚀 Processing {len(messages)} buffered messages for session {session_key}: '{combined_message[:100]}...'")
            
            # Xử lý tin nhắn đã gộp (ngoài lock để tránh block)
            await processor_func(sender_id, page_id, bot_id, combined_message, send_facebook, company_id)
            
            # ✅ Đánh dấu đã gửi response
            async with self.lock:
                if session_key in self.buffers:
                    self.buffers[session_key]["response_sent"] = True
                    self.buffers[session_key]["is_processing"] = False
                    # ✅ Xóa buffer sau 5 giây để tránh memory leak (chỉ xóa nếu không có tin nhắn mới)
                    async def cleanup_buffer():
                        await asyncio.sleep(5.0)
                        async with self.lock:
                            if session_key in self.buffers and self.buffers[session_key].get("response_sent"):
                                del self.buffers[session_key]
                                logger.debug(f"🧹 Cleaned up buffer for session {session_key}")
                    
                    asyncio.create_task(cleanup_buffer())
            
        except asyncio.CancelledError:
            # Task bị cancel do có tin nhắn mới - không làm gì
            logger.debug(f"⏸️ Processing cancelled for session {session_key} (new message arrived)")
        except Exception as e:
            logger.error(f"❌ Error processing buffered messages for {session_key}: {e}")
            # ✅ Reset trạng thái khi có lỗi
            async with self.lock:
                if session_key in self.buffers:
                    del self.buffers[session_key]

class BotMessengerAgentV2:
    """Bot Agent V2 với đầy đủ tính năng RAG, conversation history, customer & order management"""
    
    def __init__(self, buffer_time: float = 2.0):
        """
        Args:
            buffer_time: Thời gian chờ (giây) để gom nhóm tin nhắn liên tiếp. Mặc định 2 giây.
        """
        self.factory = None
        self.db_manager = None
        self.current_bot_info = None
        self.current_user_id = None
        self.rag_retrieval_service = None
        self.page_access_token = None
        self.current_page_id = None
        self.current_sender_id = None
        
        # Message buffer để gom nhóm tin nhắn liên tiếp
        self.message_buffer = MessageBuffer(buffer_time=buffer_time)
        
        # Facebook Messenger Tools
        self.fb_tools = FacebookMessengerTools(self)
        
        # Theo dõi tools đã thực hiện thành công - giới hạn mỗi tool chỉ gọi 1 lần
        self.completed_tools = set()
        self.tool_call_count = {}
        
        # ⚡ SPEED OPTIMIZATION: Cache với TTL khác nhau dựa trên tần suất thay đổi
        self.bot_info_cache = {}  # Cache bot info theo page_id hoặc bot_id
        self.page_token_cache = {}  # Cache page access token theo page_id
        self.sender_info_cache = {}  # Cache sender info theo sender_id
        
        # TTL khác nhau cho từng loại cache
        self.cache_ttl = {
            'bot_info': 600,      # 10 phút - ít thay đổi
            'page_token': 1800,   # 30 phút - rất ít thay đổi
            'sender_info': 3600,  # 60 phút - hầu như không đổi
        }
        self.default_cache_ttl = 300  # 5 phút cho các cache khác
        
        # ✅ Store local image paths for current request (keyed by sender_id)
        self.local_image_paths_cache = {}
        
    def reset_tool_usage(self):
        """Reset trạng thái sử dụng tools cho cuộc hội thoại mới"""
        self.completed_tools.clear()
        self.tool_call_count.clear()
        # logger.info("🔄 Đã reset trạng thái sử dụng tools")
        
    async def preload_bot_info(self, page_id: str = None, bot_id: str = None):
        """Preload và cache bot info để tối ưu tốc độ"""
        try:
            cache_key = page_id or bot_id
            current_time = asyncio.get_event_loop().time()
            
            # Kiểm tra cache với TTL 10 phút
            if cache_key in self.bot_info_cache:
                cached_data = self.bot_info_cache[cache_key]
                if current_time - cached_data['timestamp'] < self.cache_ttl['bot_info']:
                    logger.debug(f"✅ Cache hit: bot_info for {cache_key}")
                    self.current_bot_info = cached_data['data']
                    return cached_data['data']
            
            # Load bot info
            if page_id:
                bot_info = await self.get_bot_info_from_page_id(page_id)
            else:
                bot_info = await self.get_bot_info_from_bot_id(bot_id)
            
            # Cache kết quả
            if bot_info:
                self.bot_info_cache[cache_key] = {
                    'data': bot_info,
                    'timestamp': current_time
                }
                # logger.debug(f"💾 Cached bot_info for {cache_key} (TTL: {self.cache_ttl['bot_info']}s)")
            
            return bot_info
        except Exception as e:
            logger.error(f"❌ Error preloading bot info: {e}")
            return None
    
    async def get_page_access_token_cached(self, page_id: str) -> str:
        """Lấy page access token với cache (TTL 30 phút)"""
        try:
            current_time = asyncio.get_event_loop().time()
            
            # Kiểm tra cache với TTL 30 phút
            if page_id in self.page_token_cache:
                cached_data = self.page_token_cache[page_id]
                if current_time - cached_data['timestamp'] < self.cache_ttl['page_token']:
                    logger.debug(f"✅ Cache hit: page_token for {page_id}")
                    return cached_data['token']
            
            # Load từ database
            if not self.factory:
                return ""
                
            facebook_page = await self.factory.facebook_page_manager.get_by_fb_page_id(page_id)
            if not facebook_page:
                return ""
            
            token = facebook_page.get("fb_page_access_token", "")
            
            # Cache kết quả
            self.page_token_cache[page_id] = {
                'token': token,
                'timestamp': current_time
            }
            
            return token
        except Exception as e:
            logger.error(f"❌ Error getting cached page token: {e}")
            return ""
    
    async def warm_up_cache(self, page_ids: List[str] = None, bot_ids: List[str] = None):
        """
        Warm up cache cho các page_ids và bot_ids thường xuyên sử dụng
        Gọi method này khi khởi động application để preload data
        """
        try:
            # logger.info("🔥 Starting cache warm-up...")
            
            tasks = []
            
            # Warm up bot info
            if page_ids:
                for page_id in page_ids:
                    tasks.append(self.preload_bot_info(page_id=page_id))
                    
            if bot_ids:
                for bot_id in bot_ids:
                    tasks.append(self.preload_bot_info(bot_id=bot_id))
            
            # Warm up page tokens
            if page_ids:
                for page_id in page_ids:
                    tasks.append(self.get_page_access_token_cached(page_id))
            
            # Chạy tất cả tasks song song
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"❌ Error during cache warm-up: {e}")
    
    def clear_cache(self):
        """Xóa toàn bộ cache"""
        self.bot_info_cache.clear()
        self.page_token_cache.clear()
        self.sender_info_cache.clear()
        
    async def initialize(self):
        """Khởi tạo kết nối MongoDB và factory"""
        try:
            # Khởi tạo MongoDB manager
            self.db_manager = MongoDBManager()
            await self.db_manager.connect()
            
            # 🔧 Ensure product indexes exist (tự động tạo nếu chưa có)
            try:
                await ensure_product_indexes(self.db_manager.database)
            except Exception as e:
                logger.warning(f"⚠️ Could not ensure product indexes: {e}")
            
            # Khởi tạo factory với db_manager
            self.factory = MongoDBManagementFactory(self.db_manager)
            
            # Khởi tạo RAG retrieval service
            self.rag_retrieval_service = RAGRetrievalService(self.db_manager)
            
            # Tạo enhanced prompt template với better context
            prompt_template = prompt_facebook_messenger.FACEBOOK_MESSENGER
            
            # Create prompt
            prompt = ChatPromptTemplate.from_template(prompt_template)
            
            # Agent tools
            raw_tools = self.fb_tools.get_all_tools()
            
            # Wrap tools để giới hạn mỗi tool chỉ gọi 1 lần
            tools = [self._create_tool_wrapper(tool) for tool in raw_tools]
            
            # Create agent với tối ưu để gọi nhiều tools song song
            agent = create_openai_tools_agent(environment.llm, tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=12,  
                return_intermediate_steps=False, 
                max_execution_time=90, 
                early_stopping_method="generate" 
            )
            
        except Exception as e:
            logger.error(f"❌ Error initializing Bot Agent V2: {e}")
            raise

    def _create_tool_wrapper(self, original_tool: BaseTool) -> BaseTool:
        """
        Tạo wrapper cho tool với logic tối ưu hóa
        
        Args:
            original_tool: Tool gốc cần wrap
            
        Returns:
            Tool đã được wrap với logic kiểm tra
        """
        @tool(original_tool.name)
        def wrapped_tool(*args, **kwargs) -> str:
            """Wrapped tool với tối ưu hóa"""
            tool_name = original_tool.name
            
            # Một số tools quan trọng có thể gọi nhiều lần với query khác nhau
            multi_call_allowed = tool_name in ['search_knowledge', 'search_products', 'get_customer_info', 'get_order_info']
            
            if not multi_call_allowed:
                # Kiểm tra số lần gọi cho tools chỉ gọi 1 lần
                if tool_name in self.tool_call_count or tool_name in self.completed_tools:
                    logger.warning(f"⚠️ Tool '{tool_name}' đã được gọi rồi, bỏ qua lần gọi này")
                    return f"❌ Tool '{tool_name}' đã được sử dụng rồi. Mỗi tool chỉ được gọi tối đa 1 lần trong một phiên hội thoại. Vui lòng sử dụng thông tin đã có hoặc hỏi người dùng trực tiếp.\n\n"
                
                # Đánh dấu tool đã được gọi
                self.tool_call_count[tool_name] = 1
                self.completed_tools.add(tool_name)
            else:
                # Cho phép gọi nhiều lần với giới hạn hợp lý
                call_count = self.tool_call_count.get(tool_name, 0)
                max_calls = 1  # Giới hạn tối đa 1 lần cho search_knowledge và search_products
                
                if call_count >= max_calls:
                    logger.error(f"❌ CRITICAL: Tool '{tool_name}' loop detected! Already called {call_count} times")
                    # Đánh dấu tool này vào completed để block hoàn toàn
                    self.completed_tools.add(tool_name)
                    # Trả về message FORCE STOP
                    return (
                        f"⛔ TOOL LIMIT REACHED ⛔\n\n"
                        f"Tool '{tool_name}' has been called {max_calls} times (maximum limit).\n\n"
                        f"🛑 YOU MUST STOP calling this tool immediately!\n\n"
                        f"✅ Action Required:\n"
                        f"1. DO NOT call '{tool_name}' again\n"
                        f"2. Use the information already gathered\n"
                        f"3. Provide a response to the customer NOW\n"
                        f"4. If no information found, politely tell the customer you don't have that information\n\n"
                        f"Please respond to the customer immediately with what you have.\n"
                    )
                
                self.tool_call_count[tool_name] = call_count + 1
            
            logger.info(f"✅ Executing tool: {tool_name} (lần {self.tool_call_count.get(tool_name, 1)})")
            
            # Gọi tool gốc
            try:
                result = original_tool.func(*args, **kwargs)
                return result
            except Exception as e:
                logger.error(f"❌ Error in tool {tool_name}: {e}")
                return f"❌ Lỗi khi thực thi tool {tool_name}: {e}"
        
        # Copy metadata từ tool gốc
        if original_tool.name in ['search_knowledge', 'search_products']:
            wrapped_tool.description = f"{original_tool.description}\n\n💡 Tool này có thể được gọi tối đa 2 lần với query khác nhau để tìm kiếm thông tin tốt hơn."
        elif original_tool.name in ['get_customer_info', 'get_order_info']:
            wrapped_tool.description = f"{original_tool.description}\n\n💡 Tool này có thể được gọi nhiều lần nếu cần."
        else:
            wrapped_tool.description = f"{original_tool.description}\n\n⚠️ QUAN TRỌNG: Tool này chỉ được gọi MỘT LẦN duy nhất trong toàn bộ cuộc hội thoại."
        wrapped_tool.args_schema = original_tool.args_schema
        
        return wrapped_tool

    async def get_bot_info_from_page_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin bot từ page_id
        
        Args:
            page_id: Facebook page ID
            
        Returns:
            Dict chứa thông tin bot, identity, procedure, knowledge
        """
        try:
            # 1. Lấy thông tin page từ social_facebook_pages
            facebook_page = await self.factory.social_media_factory.facebook_page_manager.get_by_fb_page_id(page_id)
            if not facebook_page:
                logger.warning(f"❌ Không tìm thấy Facebook page với ID: {page_id}")
                return None
            
            # 2. Lấy social_account_id từ page
            social_account_id = facebook_page.get("social_account_id")
            if not social_account_id:
                logger.warning(f"❌ Không tìm thấy social_account_id cho page: {page_id}")
                return None
            
            # 3. Lấy user_id từ social_accounts
            social_account = await self.factory.social_media_factory.social_account_manager.get_social_account_by_id(social_account_id)
            if not social_account:
                logger.warning(f"❌ Không tìm thấy social account với ID: {social_account_id}")
                return None
            
            user_id = social_account.get("user_id")
            if not user_id:
                logger.warning(f"❌ Không tìm thấy user_id cho social account: {social_account_id}")
                return None
            
            self.current_user_id = user_id
            
            # 4. Tìm bot có connect chứa page_id này
            # Bot connect có thể là string hoặc list of dicts
            all_bots = await self.factory.bot_factory.bot_manager.get_by_user_id(user_id, status="on")
            # logger.info(f"🔍 Found {len(all_bots)} active bots for user {user_id}")
            
            bot_info = None
            for bot in all_bots:
                connect_data = bot.get("connect")
                # logger.info(f"🔍 Checking bot {bot.get('name')} with connect: {connect_data}")
                if connect_data:
                    # Parse connect data if it's a string
                    if isinstance(connect_data, str):
                        try:
                            connect_data = json.loads(connect_data)
                        except:
                            continue
                    
                    # Check if connect contains this page_id
                    if isinstance(connect_data, list):
                        for conn in connect_data:
                            if isinstance(conn, dict):
                                fb_page_id = conn.get("fb_page_id")
                                # logger.info(f"🔍 Comparing fb_page_id: {fb_page_id} with page_id: {page_id}")
                                if fb_page_id == page_id:
                                    bot_info = bot
                                    break
                    elif isinstance(connect_data, dict):
                        fb_page_id = connect_data.get("fb_page_id")
                        # logger.info(f"🔍 Comparing fb_page_id: {fb_page_id} with page_id: {page_id}")
                        if fb_page_id == page_id:
                            bot_info = bot
                            break
                
                if bot_info:
                    break
            
            if not bot_info:
                logger.warning(f"❌ Không tìm thấy bot được kết nối với page: {page_id}")
                return None
            
            # 5. Lấy thông tin identity
            identity_id = bot_info.get("identity_id")
            identity_info = None
            if identity_id:
                identity_info = await self.factory.bot_factory.identity_manager.get_by_id(identity_id)
            
            # 6. Lấy thông tin procedure
            procedure_id = bot_info.get("procedure_id")
            procedure_info = None
            if procedure_id:
                procedure_info = await self.factory.bot_factory.procedure_manager.get_by_id(procedure_id)
            
            # ⚡ SPEED: Lazy load knowledge documents - chỉ lưu IDs, fetch content khi cần
            # Thay vì load full documents (chậm), chỉ lưu document_ids
            knowledge = bot_info.get("knowledge")
            knowledge_document_ids = []
            company_id = None
            
            if knowledge:
                if isinstance(knowledge, str):
                    try:
                        knowledge = json.loads(knowledge)
                    except:
                        knowledge = [knowledge]
                
                if isinstance(knowledge, list):
                    knowledge_document_ids = knowledge
                    
                    # Chỉ fetch 1 document đầu để lấy company_id (thay vì fetch tất cả)
                    if knowledge_document_ids:
                        first_doc = await self.factory.knowledge_factory.document_manager.get_by_id(
                            knowledge_document_ids[0]
                        )
                        if first_doc:
                            company_id = first_doc.get("company_id")
            
            result = {
                "bot": bot_info,
                "identity": identity_info,
                "procedure": procedure_info,
                "knowledge_document_ids": knowledge_document_ids,  # Chỉ lưu IDs thay vì full docs
                "user_id": user_id,
                "facebook_page": facebook_page,
                "social_account": social_account,
                "company_id": company_id
            }
            
            self.current_bot_info = result
            # logger.info(f"✅ Successfully loaded bot info for page: {page_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting bot info from page_id {page_id}: {e}")
            return None
        
    async def get_bot_info_from_bot_id(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin bot từ bot_id
        
        Args:
            bot_id: Bot ID
            
        Returns:
            Dict chứa thông tin bot, identity, procedure, knowledge
        """
        try:
            # 1. Lấy thông tin bot từ bot_id
            bot_info = await self.factory.bot_factory.bot_manager.get_by_id(bot_id)
            if not bot_info:
                logger.warning(f"❌ Không tìm thấy bot với ID: {bot_id}")
                return None
            
            user_id = bot_info.get("user_id")
            if not user_id:
                logger.warning(f"❌ Không tìm thấy user_id cho bot: {bot_id}")
                return None
            
            self.current_user_id = user_id
            
            # 2. Lấy thông tin identity
            identity_id = bot_info.get("identity_id")
            identity_info = None
            if identity_id:
                identity_info = await self.factory.bot_factory.identity_manager.get_by_id(identity_id)
            
            # 3. Lấy thông tin procedure
            procedure_id = bot_info.get("procedure_id")
            procedure_info = None
            if procedure_id:
                procedure_info = await self.factory.bot_factory.procedure_manager.get_by_id(procedure_id)
            
            # ⚡ SPEED: Lazy load knowledge documents - chỉ lưu IDs
            knowledge = bot_info.get("knowledge")
            knowledge_document_ids = []
            company_id = None
            
            if knowledge:
                if isinstance(knowledge, str):
                    try:
                        knowledge = json.loads(knowledge)
                    except:
                        knowledge = [knowledge]
                
                if isinstance(knowledge, list):
                    knowledge_document_ids = knowledge
                    
                    # Chỉ fetch 1 document để lấy company_id
                    if knowledge_document_ids:
                        first_doc = await self.factory.knowledge_factory.document_manager.get_by_id(
                            knowledge_document_ids[0]
                        )
                        if first_doc:
                            company_id = first_doc.get("company_id")
            
            result = {
                "bot": bot_info,
                "identity": identity_info,
                "procedure": procedure_info,
                "knowledge_document_ids": knowledge_document_ids,
                "user_id": user_id,
                "company_id": company_id
            }
            
            self.current_bot_info = result
            # logger.info(f"✅ Successfully loaded bot info for bot ID: {bot_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting bot info from bot_id {bot_id}: {e}")
            return None

    async def search_knowledge_chunks(self, query: str, document_ids: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Tìm kiếm knowledge chunks liên quan đến query với enhanced RAG
        
        Args:
            query: Câu hỏi tìm kiếm
            document_ids: Danh sách document IDs
            limit: Số lượng chunks tối đa
            
        Returns:
            List of relevant knowledge chunks
        """
        try:
            if not self.rag_retrieval_service:
                logger.error("❌ RAG retrieval service not initialized")
                return []
            
            # Sử dụng enhanced retrieval service
            relevant_chunks = await self.rag_retrieval_service.search_relevant_chunks(
                query=query,
                document_ids=document_ids,
                user_id=self.current_user_id,
                limit=limit,
                similarity_threshold=0.5,
                use_hybrid=True
            )
            
            # logger.info(f"🔍 Enhanced search found {len(relevant_chunks)} relevant chunks")
            return relevant_chunks
            
        except Exception as e:
            logger.error(f"❌ Error in enhanced search_knowledge_chunks: {e}")
            return []

    async def search_knowledge_with_context(self, query: str, document_ids: List[str], limit: int = 5) -> Dict[str, Any]:
        """
        Tìm kiếm knowledge với context window để có thông tin đầy đủ hơn
        
        Args:
            query: Câu hỏi tìm kiếm
            document_ids: Danh sách document IDs
            limit: Số lượng chunks tối đa
            
        Returns:
            Dict chứa chunks chính và context chunks
        """
        try:
            if not self.rag_retrieval_service:
                logger.error("❌ RAG retrieval service not initialized")
                return {'chunks': [], 'context_chunks': [], 'total_found': 0}
            
            result = await self.rag_retrieval_service.search_with_context(
                query=query,
                document_ids=document_ids,
                user_id=self.current_user_id,
                context_window=2,
                limit=limit
            )
            
            # logger.info(f"🔍 Context search found {result['total_found']} main + {result.get('context_found', 0)} context chunks")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in search_knowledge_with_context: {e}")
            return {'chunks': [], 'context_chunks': [], 'total_found': 0}

    async def search_qa_pairs(self, query: str, limit: int = 3, company_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tìm kiếm các Q&A pairs liên quan đến query"""
        try:
            if not self.rag_retrieval_service:
                logger.error("❌ RAG retrieval service not initialized")
                return []

            user_id = self.current_user_id
            if not user_id and self.current_bot_info:
                user_id = self.current_bot_info.get("user_id")

            if not user_id:
                logger.warning("⚠️ Không có user_id để tìm kiếm Q&A pairs")
                return []

            results = await self.rag_retrieval_service.search_relevant_chunks(
                query=query,
                document_ids=None,
                user_id=user_id,
                limit=limit,
                chunk_types=["qa_pair"],
                source_types=["qa_pair"],
                company_id=company_id
            )

            # logger.info(f"🔍 QA search found {len(results)} chunks for query")
            return results

        except Exception as e:
            logger.error(f"❌ Error in search_qa_pairs: {e}")
            return []

    async def search_image_in_knowledge(self, image_url: str = None, document_ids: List[str] = None, local_path: str = None) -> Optional[str]:
        """
        Tìm kiếm ảnh trong knowledge base bằng vector similarity và trả về content tương ứng
        Sử dụng SigLIP model để tạo embedding cho ảnh và so sánh với image chunks trong database
        
        Args:
            image_url: URL của ảnh cần tìm (optional nếu có local_path)
            document_ids: Danh sách document IDs để tìm kiếm
            local_path: Local file path của ảnh đã download (optional, ưu tiên hơn image_url)
            
        Returns:
            Content mô tả ảnh nếu tìm thấy, None nếu không tìm thấy
        """
        try:
            # ✅ Khai báo global để sử dụng image model và processor
            global image_model, image_processor
            
            # logger.info(f"🔍 Searching for image in knowledge base using vector similarity: {image_url}")
            
            if not self.factory:
                logger.error("❌ Factory not initialized")
                return None
            
            # Step 1: Load image and create embedding
            try:         
                # Load image from local path or download from URL
                if local_path and os.path.exists(local_path):
                    # ✅ PREFERRED: Load from local file (faster, no network issues)
                    logger.info(f"📁 Loading image from local path: {local_path}")
                    with open(local_path, 'rb') as f:
                        image_data = f.read()
                    logger.info(f"✅ Loaded image from local file: {len(image_data)} bytes")
                    
                elif image_url:
                    # ⚠️ FALLBACK: Download from URL (may fail if URL expired)
                    logger.info(f"📥 Downloading image from URL: {image_url[:80]}...")
                    # ✅ FIX: Thêm User-Agent và headers để tránh 403 Forbidden từ Facebook CDN
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.facebook.com/',
                    }
                    
                    # ✅ IMPROVED: Disable SSL verification for Facebook CDN (workaround for SSL issues)
                    response = await asyncio.to_thread(
                        requests.get, 
                        image_url, 
                        headers=headers, 
                        timeout=15,  # Tăng timeout
                        verify=False,  # Disable SSL verification
                        allow_redirects=True  # Follow redirects
                    )
                    response.raise_for_status()
                    image_data = response.content
                    logger.info(f"✅ Downloaded image: {len(image_data)} bytes")
                else:
                    logger.error("❌ Neither local_path nor image_url provided")
                    return None
                
                # Load and process image
                image = Image.open(io.BytesIO(image_data))
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                # Generate embedding for query image
                # Lazy-load image embedding tools only when needed
                image_model, image_processor = get_image_embedding_model()
                inputs = image_processor(images=image, return_tensors="pt")
                with torch.no_grad():
                    outputs = image_model.get_image_features(**inputs)
                    # Normalize embedding
                    query_embedding = outputs / outputs.norm(dim=-1, keepdim=True)
                    query_embedding_list = query_embedding.squeeze().cpu().numpy().tolist()
                
                logger.info(f"✅ Generated image embedding with dimension: {len(query_embedding_list)}")
                logger.info(f"🔢 Embedding preview (first 10 dims): {query_embedding_list[:10]}")
                
            except Exception as e:
                logger.error(f"❌ Error generating image embedding: {e}")
                # Fallback to text-based search
                return await self._search_image_by_url_fallback(image_url, document_ids)
            
            # Step 2: Search for similar image chunks using vector similarity
            try:
                # Collect all image chunks from specified documents
                all_image_chunks = []
                for document_id in document_ids:
                    image_chunks = await self.factory.knowledge_chunk_manager.get_image_chunks_by_document(
                        source_id=document_id,
                        user_id=self.current_user_id
                    )
                    logger.info(f"📄 Document {document_id}: Found {len(image_chunks)} image chunks")
                    all_image_chunks.extend(image_chunks)
                
                logger.info(f"🔍 Total: {len(all_image_chunks)} image chunks to compare across {len(document_ids)} documents")
                
                if not all_image_chunks:
                    logger.info(f"❌ No image chunks found in documents")
                    return None

                query_vec = np.array(query_embedding_list).reshape(1, -1)
                similarities = []
                
                logger.info(f"🔢 Query vector shape: {query_vec.shape}, norm: {np.linalg.norm(query_vec):.4f}")
                
                for chunk in all_image_chunks:
                    chunk_embedding = chunk.get('content_embedding')
                    if chunk_embedding and len(chunk_embedding) == len(query_embedding_list):
                        chunk_vec = np.array(chunk_embedding).reshape(1, -1)
                        # ✅ IMPORTANT: Cả 2 vectors phải được normalize trước khi tính cosine
                        # Query đã normalized trong model output, nhưng chunk embedding có thể chưa
                        chunk_vec_normalized = chunk_vec / np.linalg.norm(chunk_vec)
                        query_vec_normalized = query_vec / np.linalg.norm(query_vec)
                        
                        similarity = cosine_similarity(query_vec_normalized, chunk_vec_normalized)[0][0]
                        similarities.append({
                            'chunk': chunk,
                            'similarity': float(similarity),
                            'chunk_name': chunk.get('chunk_name', 'Unknown'),
                            'document_id': chunk.get('source_id', 'Unknown')
                        })
                
                logger.info(f"✅ Calculated {len(similarities)} similarity scores")
                
                if not similarities:
                    logger.info(f"❌ No valid embeddings found to compare")
                    return None
                
                # Sort by similarity (highest first)
                similarities.sort(key=lambda x: x['similarity'], reverse=True)
                
                # ✅ DEBUG: Log top 5 matches để debug
                logger.info(f"🎯 Top 5 similarity scores:")
                for i, match in enumerate(similarities[:5], 1):
                    chunk_name = match['chunk'].get('chunk_name', 'Unknown')
                    logger.info(f"  {i}. {chunk_name}: {match['similarity']:.4f} ({match['similarity']:.2%})")
                
                # Get top match
                top_match = similarities[0]
                similarity_score = top_match['similarity']
                matched_chunk = top_match['chunk']
                
                logger.info(f"🎯 Selected top match similarity score: {similarity_score:.4f}")
                
                # ✅ LOWERED: Giảm threshold từ 0.7 → 0.5 (50%) để dễ match hơn
                # Lý do: Image similarity thường thấp hơn text similarity
                # Ảnh cùng loại sản phẩm có thể chỉ đạt 50-70% similarity
                SIMILARITY_THRESHOLD = 0.5  # 50% similarity (was 0.7)
                
                if similarity_score >= SIMILARITY_THRESHOLD:
                    # logger.info(f"✅ Found similar image in knowledge base (similarity: {similarity_score:.2%})")
                    
                    # Extract content description
                    content = matched_chunk.get('content', '')
                    # Remove image tags to extract description
                    # description = re.sub(r'<image:[^>]+>', '', content).strip()
                    
                    if content:
                        return f"📸 Thông tin về ảnh đính kèm (độ tương đồng: {similarity_score:.2%}): {content}"
                    else:
                        return f"📸 Tìm thấy ảnh tương tự trong cơ sở dữ liệu (độ tương đồng: {similarity_score:.2%}) nhưng chưa có mô tả chi tiết."
                else:
                    logger.info(f"⚠️ No sufficiently similar image found (best match: {similarity_score:.2%})")
                    # Try fallback text-based search
                    fallback_result = await self._search_image_by_url_fallback(image_url, document_ids)
                    if fallback_result:
                        return fallback_result
                    return f"📸 Không tìm thấy ảnh tương tự trong cơ sở dữ liệu (độ tương đồng cao nhất: {similarity_score:.2%})"
                    
            except Exception as e:
                logger.error(f"❌ Error in vector similarity search: {e}")
                traceback.print_exc()
                return None
            
        except Exception as e:
            logger.error(f"❌ Error searching image in knowledge: {e}")
            traceback.print_exc()
            return None
    
    async def _search_image_by_url_fallback(self, image_url: str, document_ids: List[str]) -> Optional[str]:
        """
        Fallback method: Tìm kiếm ảnh dựa trên URL matching (phương pháp cũ)
        
        Args:
            image_url: URL của ảnh cần tìm
            document_ids: Danh sách document IDs để tìm kiếm
            
        Returns:
            Content mô tả ảnh nếu tìm thấy, None nếu không tìm thấy
        """
        try:
            # logger.info(f"🔄 Fallback to URL-based search for image: {image_url}")
            
            # Lặp qua từng document để tìm image chunks
            for document_id in document_ids:
                # Lấy tất cả image chunks của document này
                image_chunks = await self.factory.knowledge_chunk_manager.get_image_chunks_by_document(
                    source_id=document_id,
                    user_id=self.current_user_id
                )
                
                # Tìm kiếm URL trong content của các image chunks
                for chunk in image_chunks:
                    content = chunk.get('content', '')
                    
                    # Tìm kiếm exact match với URL
                    if image_url in content:
                        # logger.info(f"✅ Found matching image by URL in knowledge base")
                        description = re.sub(r'<image:[^>]+>', '', content).strip()
                        
                        if description:
                            return f"📸 Thông tin về ảnh này: {description}"
                        else:
                            return "📸 Ảnh này có trong cơ sở dữ liệu nhưng chưa có mô tả chi tiết."
                    
                    # Tìm kiếm partial match (tên file)
                    image_filename = image_url.split('/')[-1] if '/' in image_url else image_url
                    if image_filename in content:
                        # logger.info(f"✅ Found partial matching image by filename in knowledge base")
                        description = re.sub(r'<image:[^>]+>', '', content).strip()
                        
                        if description:
                            return f"📸 Thông tin về ảnh tương tự: {description}"
                        else:
                            return "📸 Tìm thấy ảnh tương tự trong cơ sở dữ liệu nhưng chưa có mô tả chi tiết."
            
            logger.info(f"❌ Image not found by URL in knowledge base")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in fallback URL search: {e}")
            return None

    def extract_image_urls_from_message(self, message: str) -> List[str]:
        """
        Trích xuất các URL ảnh từ tin nhắn
        ⚡ OPTIMIZED: Sử dụng pre-compiled regex
        
        Args:
            message: Tin nhắn từ user
            
        Returns:
            List các URL ảnh được tìm thấy
        """
        try:
            image_urls = []
            
            # Sử dụng compiled patterns
            urls = COMPILED_REGEX['image_url_simple'].findall(message)
            image_urls.extend(urls)
            
            urls = COMPILED_REGEX['image_url_fb'].findall(message)
            image_urls.extend(urls)
            
            # ✅ NEW: Sử dụng regex match Facebook CDN
            urls = COMPILED_REGEX['image_url_fb_cdn'].findall(message)
            image_urls.extend(urls)
            
            urls = COMPILED_REGEX['markdown_image'].findall(message)
            image_urls.extend(urls)
            
            # Loại bỏ trùng lặp
            unique_urls = list(set(image_urls))
            
            # Clean URLs (remove trailing punctuation)
            cleaned_urls = []
            for url in unique_urls:
                cleaned_url = COMPILED_REGEX['end_punctuation'].sub('', url.rstrip('.,;!?'))
                cleaned_urls.append(cleaned_url)
            
            if cleaned_urls:
                logger.info(f"🖼️ Extracted {len(cleaned_urls)} image URLs from message")
                for idx, url in enumerate(cleaned_urls, 1):
                    logger.debug(f"  {idx}. {url[:80]}...")
            
            return cleaned_urls
            
        except Exception as e:
            logger.error(f"❌ Error extracting image URLs: {e}")
            return []

    def format_history_with_smart_window(self, conversation_history: List[Dict[str, Any]], current_time: datetime) -> str:
        """
        Format lịch sử hội thoại với sliding window thông minh:
        - 5 tin nhắn gần nhất: Hiển thị đầy đủ (User + You) với timestamp
        - 10 tin nhắn tiếp theo: Chỉ hiển thị User với timestamp
        - Các tin nhắn cũ hơn: Tóm tắt ngắn gọn
        
        Args:
            conversation_history: Danh sách lịch sử hội thoại
            current_time: Thời gian hiện tại
            
        Returns:
            str: History text đã được format
        """
        try:
            if not conversation_history:
                return ""
            
            total_messages = len(conversation_history)
            history_text = ""
            
            # Xác định các vùng sliding window
            # Window 1: 5 tin nhắn gần nhất - Hiển thị đầy đủ với timestamp
            recent_window_size = 5
            # Window 2: 10 tin nhắn tiếp theo - Chỉ User với timestamp  
            medium_window_size = 10
            
            recent_start_idx = max(0, total_messages - recent_window_size)
            medium_start_idx = max(0, recent_start_idx - medium_window_size)
            old_messages_count = medium_start_idx
            
            # Phần 1: Tóm tắt các tin nhắn cũ (nếu có)
            if old_messages_count > 0:
                old_user_queries = []
                for i in range(old_messages_count):
                    hist = conversation_history[i]
                    user_query = hist.get('query', '').strip()
                    if user_query and len(user_query) > 10:  # Chỉ lấy câu hỏi có ý nghĩa
                        # Rút gọn câu hỏi nếu quá dài
                        if len(user_query) > 100:
                            user_query = user_query[:97] + "..."
                        old_user_queries.append(user_query)
                
                if old_user_queries:
                    # Lấy tối đa 3 câu đại diện
                    sample_queries = old_user_queries[:3]
                    if len(old_user_queries) > 3:
                        sample_queries.append(f"... và {len(old_user_queries) - 3} câu hỏi khác")
                    
                    history_text += f"📋 Lịch sử cũ ({old_messages_count} tin nhắn):\n"
                    for query in sample_queries:
                        history_text += f"  - {query}\n"
                    history_text += "\n"
            
            # Phần 2: Window 2 - 10 tin nhắn trung bình (chỉ User với timestamp)
            if medium_start_idx < recent_start_idx:
                history_text += "📝 Ngữ cảnh gần đây:\n"
                for i in range(medium_start_idx, recent_start_idx):
                    hist = conversation_history[i]
                    user_query = hist.get('query', '').strip()
                    created_at = hist.get('created_at')
                    
                    if user_query:
                        # Format thời gian
                        time_str = self._format_relative_time(created_at, current_time)
                        history_text += f"User ({time_str}): {user_query}\n"
                
                history_text += "\n"
            
            # Phần 3: Window 1 - 5 tin nhắn gần nhất (đầy đủ User + You với timestamp)
            history_text += "💬 Hội thoại gần đây:\n"
            for i in range(recent_start_idx, total_messages):
                hist = conversation_history[i]
                user_query = hist.get('query', '').strip()
                bot_answer = hist.get('answer', '').strip()
                created_at = hist.get('created_at')
                
                # Format thời gian
                time_str = self._format_relative_time(created_at, current_time)
                
                # Thêm phần User
                if user_query:
                    history_text += f"User ({time_str}): {user_query}\n"
                
                # Thêm phần You
                if bot_answer:
                    # Rút gọn câu trả lời quá dài
                    if len(bot_answer) > 500:
                        bot_answer = bot_answer[:497] + "..."
                    history_text += f"You: {bot_answer}\n"
                
                history_text += "\n"
            
            logger.info(f"📊 Formatted history: {old_messages_count} old + {recent_start_idx - medium_start_idx} medium + {total_messages - recent_start_idx} recent")
            return history_text
            
        except Exception as e:
            logger.error(f"❌ Error formatting history with smart window: {e}")
            # Fallback to simple format
            return self._format_history_simple(conversation_history)
    
    def _format_relative_time(self, created_at, current_time: datetime) -> str:
        """
        Format thời gian tương đối (vừa xong, 5 phút trước, 2 giờ trước, hôm qua, v.v.)
        
        Args:
            created_at: Thời gian tạo tin nhắn (datetime hoặc string)
            current_time: Thời gian hiện tại
            
        Returns:
            str: Chuỗi thời gian tương đối
        """
        try:
            # Convert created_at to datetime if needed
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            if not created_at:
                return "N/A"
            
            # Remove timezone info for comparison
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
            if current_time.tzinfo:
                current_time = current_time.replace(tzinfo=None)
            
            # Tính khoảng cách thời gian
            delta = current_time - created_at
            
            # Định dạng theo khoảng cách
            total_seconds = delta.total_seconds()
            
            if total_seconds < 60:  # Dưới 1 phút
                return "vừa xong"
            elif total_seconds < 3600:  # Dưới 1 giờ
                minutes = int(total_seconds / 60)
                return f"{minutes} phút trước"
            elif total_seconds < 86400:  # Dưới 1 ngày
                hours = int(total_seconds / 3600)
                return f"{hours} giờ trước"
            elif total_seconds < 172800:  # Dưới 2 ngày
                return "hôm qua"
            elif total_seconds < 604800:  # Dưới 1 tuần
                days = int(total_seconds / 86400)
                return f"{days} ngày trước"
            else:
                # Hiển thị ngày tháng cụ thể
                return created_at.strftime("%d/%m %H:%M")
                
        except Exception as e:
            logger.error(f"❌ Error formatting relative time: {e}")
            return "N/A"
    
    def _format_history_simple(self, conversation_history: List[Dict[str, Any]]) -> str:
        """
        Fallback: Format history đơn giản khi có lỗi
        
        Args:
            conversation_history: Danh sách lịch sử hội thoại
            
        Returns:
            str: History text đơn giản
        """
        try:
            history_text = ""
            total_messages = len(conversation_history)
            
            # Chỉ lấy 5 tin nhắn cuối
            for i in range(max(0, total_messages - 5), total_messages):
                hist = conversation_history[i]
                user_query = hist.get('query', '').strip()
                bot_answer = hist.get('answer', '').strip()
                
                if user_query:
                    history_text += f"User: {user_query}\n"
                if bot_answer:
                    history_text += f"You: {bot_answer}\n"
                history_text += "\n"
            
            return history_text
            
        except Exception as e:
            logger.error(f"❌ Error in simple history format: {e}")
            return ""

    async def get_conversation_history(self, sender_id: str, page_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử trò chuyện với context window thông minh
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID
            limit: Số lượng tin nhắn tối đa (mặc định 20 để có context đủ)
            
        Returns:
            List of conversation messages
        """
        try:
            session_id = f"{page_id}_{sender_id}"
            
            # Tìm conversation history - lấy nhiều hơn để có context đầy đủ
            histories = await self.factory.history_factory.get_history(
                user_id=self.current_user_id or "unknown",
                session_id=session_id,
                limit=limit
            )
            
            return histories
            
        except Exception as e:
            logger.error(f"❌ Error getting conversation history: {e}")
            return []

    async def save_conversation_message(self, sender_id: str, page_id: str, user_message: str, bot_response: str, bot_id: str = None, social_id: str = None, response_segments: List[Dict[str, Any]] = None, sender_info: Dict[str, Any] = None, company_id: str = None):
        """
        Lưu tin nhắn vào lịch sử trò chuyện
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID  
            user_message: Tin nhắn của user
            bot_response: Phản hồi của bot
            bot_id: ID của bot (nếu có)
            social_id: Nguồn gốc của tin nhắn (nếu có)
            response_segments: Các segments của phản hồi bot (nếu có)
            sender_info: Thông tin người gửi (nếu có)
        """
        try:
            session_id = f"{page_id}_{sender_id}"
            
            # Lưu tin nhắn
            await self.factory.history_factory.save_history(
                user_id=self.current_user_id or "unknown",
                session_id=session_id,
                customer_id=sender_id,
                query=user_message,
                answer=bot_response,
                status="active",
                bot_id=bot_id,
                social_id=social_id,
                social_page_id=page_id,
                response_segments=response_segments,
                sender_info=sender_info,
                company_id=company_id
            )
            
            logger.info(f"✅ Saved conversation message for {session_id}")
            
        except Exception as e:
            logger.error(f"❌ Error saving conversation message: {e}")

    async def log_llm_token_usage(
        self,
        *,
        user_id: Optional[str],
        company_id: Optional[Any],
        bot_id: Optional[Any],
        page_id: Optional[str],
        sender_id: Optional[str],
        session_id: str,
        message: str,
        response: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        total_cost: float,
        successful_requests: int,
        status: str,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Ghi log số lượng token sử dụng bởi LLM vào MongoDB.
        """
        try:
            try:
                if self.db_manager is None or self.db_manager.database is None:
                    logger.warning("Token usage log skipped: MongoDB manager is not available")
                    return

                # Tạo collection nếu chưa tồn tại
                if "tokens" not in await self.db_manager.database.list_collection_names():
                    await self.db_manager.database.create_collection("tokens")
                    # logger.info("✅ Created 'tokens' collection for LLM token usage logging")

                    # Tạo index cho collection để tối ưu query
                    await self.db_manager.database["tokens"].create_index([("timestamp", -1)])
                    await self.db_manager.database["tokens"].create_index([("user_id", 1)])
                    await self.db_manager.database["tokens"].create_index([("session_id", 1)])
                    # logger.info("✅ Created indexes for 'tokens' collection")

                tokens_collection = self.db_manager.database["tokens"]

                def _normalize(value: Optional[Any]) -> Optional[Any]:
                    if value is None:
                        return None
                    if isinstance(value, (dict, list)):
                        return value
                    return str(value)

                record: Dict[str, Any] = {
                    "user_id": _normalize(user_id),
                    "company_id": _normalize(company_id),
                    "bot_id": _normalize(bot_id),
                    "page_id": _normalize(page_id),
                    "sender_id": _normalize(sender_id),
                    "session_id": session_id,
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "total_cost": total_cost,
                    "successful_requests": successful_requests,
                    "status": status,
                    "error": error,
                    "message": message,
                    "response": response,
                    "timestamp": environment.get_vietnam_now_naive(),
                }

                if extra:
                    record["extra"] = extra

                await tokens_collection.insert_one(record)
                logger.debug(
                    f"Logged LLM token usage for session {session_id}: "
                    f"{prompt_tokens}/{completion_tokens} (total {total_tokens})"
                )
            except Exception as e:
                logger.error(f"❌ Error logging LLM token usage: {str(e)}")

        except Exception as log_error:
            logger.error(f"Error logging LLM token usage: {log_error}")

    def split_sentences(self, text: str) -> List[str]:
        """
        Tách câu từ văn bản cho trước, đồng thời bảo vệ các liên kết (URL) không bị tách riêng.
        ⚡ OPTIMIZED: Sử dụng pre-compiled regex patterns
        """
        # Bước 0: Bảo vệ các URL bằng cách thay thế tạm thời bằng placeholder
        placeholders = {}

        def replacer(match):
            placeholder = f"__URL_PLACEHOLDER_{len(placeholders)}__"
            placeholders[placeholder] = match.group(0)
            return placeholder

        text = COMPILED_REGEX['url'].sub(replacer, text)

        # Bước 1: Thay thế nhiều dấu '*' liên tiếp thành 1 dấu '*'
        text = COMPILED_REGEX['multiple_asterisks'].sub("*", text)

        # Bước 1.5: Tách câu dựa trên xuống dòng nếu câu đủ dài
        # Nếu có xuống dòng và mỗi dòng đủ dài (>20 ký tự), coi như câu riêng
        lines = text.split('\n')
        processed_lines = []
        for line in lines:
            line = line.strip()
            if line:
                processed_lines.append(line)
        
        # Nếu có nhiều dòng và mỗi dòng đủ dài, xử lý từng dòng như câu riêng
        if len(processed_lines) > 1 and all(len(line) > 20 for line in processed_lines):
            all_sentences = []
            for line in processed_lines:
                # Tách thêm theo dấu câu trong mỗi dòng
                pattern = re.compile(r"(?<!\b\d)\.(?=\s|$)|(?<=[!?])\s*", flags=re.UNICODE)
                line_sentences = pattern.split(line)
                line_sentences = [s.strip() for s in line_sentences if s.strip()]
                all_sentences.extend(line_sentences)
            sentences = all_sentences
        else:
            # Ghép lại và tách theo dấu câu như cũ
            text = ' '.join(processed_lines)
            # Bước 2: Sử dụng regex để tách câu dựa trên dấu chấm, dấu chấm than, dấu chấm hỏi.
            # Chú ý: Không tách khi dấu chấm nằm sau chữ số (ví dụ: số thứ tự)
            pattern = re.compile(r"(?<!\b\d)\.(?=\s|$)|(?<=[!?])\s*", flags=re.UNICODE)
            sentences = pattern.split(text)

        # Loại bỏ khoảng trắng thừa và các câu rỗng
        cleaned_sentences = [
            sentence.strip() for sentence in sentences if sentence.strip()
        ]

        # Nếu phần tử cuối cùng chỉ chứa ký tự không phải chữ hoặc số, gộp vào câu trước
        if len(cleaned_sentences) > 1:
            last_part = cleaned_sentences[-1]
            if re.match(r"^[^\w\s]+$", last_part, flags=re.UNICODE):
                cleaned_sentences[-2] += f" {last_part}"
                cleaned_sentences.pop()

        # Nếu câu có chứa danh sách (số thứ tự hoặc dấu '-' dùng trong liệt kê) thì tách riêng theo dòng
        final_sentences = []
        for sentence in cleaned_sentences:
            if re.search(r"^\d+\.\s|-\s", sentence, flags=re.MULTILINE):
                items = sentence.split("\n")
                final_sentences.extend([item.strip() for item in items if item.strip()])
            else:
                final_sentences.append(sentence)

        # Gộp lại các dòng bắt đầu bằng '-' hoặc '+' với câu phía trên
        processed_sentences = []
        for sentence in final_sentences:
            if processed_sentences and (
                sentence.startswith("-") or sentence.startswith("+")
            ):
                processed_sentences[-1] += "\n" + sentence
            else:
                processed_sentences.append(sentence)

        # Cuối cùng, khôi phục lại các URL từ placeholder
        def restore_placeholders(sentence):
            for placeholder, url in placeholders.items():
                sentence = sentence.replace(placeholder, url)
            return sentence

        processed_sentences = [
            restore_placeholders(sentence) for sentence in processed_sentences
        ]

        return processed_sentences

    def parse_response_to_segments(self, response_text: str) -> List[Dict[str, str]]:
        """
        Tách response text thành các segments có type 'text', 'image', hoặc 'images'
        
        Args:
            response_text: Chuỗi response từ bot
            
        Returns:
            List[Dict]: Danh sách segments với format [{"type": "text|image|images", "data": "content|array"}]
        """
        try:
            segments = []
            
            # Tìm tất cả các image tags trong text
            image_pattern = r'<image:(https?://[^\s>]+)>'
            images = re.findall(image_pattern, response_text)
            
            # Tách text dựa trên vị trí của image tags
            parts = re.split(image_pattern, response_text)
            
            i = 0
            while i < len(parts):
                part = parts[i].strip()
                
                # Nếu part là URL (từ image tag), thêm như image segment
                if part.startswith('http') and any(part == img for img in images):
                    segments.append({
                        "type": "image",
                        "data": part
                    })
                    i += 1
                    continue
                
                # Nếu part là text và không rỗng
                if part:
                    # Tách theo các đoạn lớn trước (dựa trên 2 xuống dòng liên tiếp)
                    paragraphs = re.split(r'\n\s*\n', part)
                    
                    for paragraph in paragraphs:
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                            
                        # Kiểm tra xem đoạn có chứa danh sách số không (1. 2. 3.)
                        if re.search(r'^\s*\d+\.\s+', paragraph, re.MULTILINE):
                            # Tách phần text mở đầu (nếu có) và phần danh sách
                            # Ví dụ: "Dưới đây là thông tin:\n1. Item 1\n2. Item 2"
                            match = re.search(r'^(.*?)(\n\s*\d+\.\s+)', paragraph, re.DOTALL)
                            if match and match.group(1).strip():
                                # Có text mở đầu, tách riêng
                                intro_text = match.group(1).strip()
                                segments.append({
                                    "type": "text",
                                    "data": intro_text
                                })
                                # Phần còn lại là danh sách
                                list_part = paragraph[len(match.group(1)):].strip()
                            else:
                                list_part = paragraph
                            
                            # Tách từng item trong danh sách
                            items = re.split(r'(?=^\s*\d+\.\s+)', list_part, flags=re.MULTILINE)
                            for item in items:
                                item = item.strip()
                                if item:
                                    segments.append({
                                        "type": "text",
                                        "data": item
                                    })
                        
                        # Kiểm tra xem đoạn có chứa danh sách bullet (•, -, +) không
                        elif re.search(r'^\s*[•\-+]\s+', paragraph, re.MULTILINE):
                            # Tách phần text mở đầu (nếu có) và phần danh sách
                            match = re.search(r'^(.*?)(\n\s*[•\-+]\s+)', paragraph, re.DOTALL)
                            if match and match.group(1).strip():
                                intro_text = match.group(1).strip()
                                segments.append({
                                    "type": "text",
                                    "data": intro_text
                                })
                                list_part = paragraph[len(match.group(1)):].strip()
                            else:
                                list_part = paragraph
                            
                            # Tách từng item trong danh sách bullet
                            items = re.split(r'(?=^\s*[•\-+]\s+)', list_part, flags=re.MULTILINE)
                            for item in items:
                                item = item.strip()
                                if item:
                                    segments.append({
                                        "type": "text",
                                        "data": item
                                    })
                        
                        else:
                            # Không phải danh sách, xử lý như text thông thường
                            # Tách theo câu dựa trên dấu câu (. ! ?)
                            sentences = self.split_sentences(paragraph)
                            for sentence in sentences:
                                sentence = sentence.strip()
                                if sentence:
                                    segments.append({
                                        "type": "text",
                                        "data": sentence
                                    })
                
                i += 1
            
            # Bước 1: Loại bỏ segments rỗng và merge text segments ngắn liên tiếp (có điều kiện)
            filtered_segments = []
            for segment in segments:
                if segment["data"].strip():
                    # Kiểm tra xem có nên merge với segment trước không
                    should_merge = False
                    if (filtered_segments and 
                        filtered_segments[-1]["type"] == "text" and 
                        segment["type"] == "text"):
                        
                        prev_data = filtered_segments[-1]["data"]
                        curr_data = segment["data"]
                        
                        # Không merge nếu:
                        # 1. Bất kỳ segment nào là danh sách (có số thứ tự hoặc bullet)
                        # 2. Câu hiện tại kết thúc bằng dấu câu mạnh (. ! ?)
                        # 3. Câu hiện tại bắt đầu bằng chữ hoa (câu mới)
                        is_list = (re.match(r'^\s*\d+\.\s+', curr_data) or 
                                  re.match(r'^\s*[•\-+]\s+', curr_data) or
                                  re.match(r'^\s*\d+\.\s+', prev_data) or
                                  re.match(r'^\s*[•\-+]\s+', prev_data))
                        
                        ends_with_punctuation = re.search(r'[.!?]\s*$', prev_data)
                        starts_with_capital = re.match(r'^[A-ZĐÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ]', curr_data)
                        
                        # Chỉ merge nếu cả 2 câu đều ngắn (<40 ký tự) và không vi phạm các điều kiện trên
                        if (len(prev_data) < 40 and 
                            len(curr_data) < 40 and
                            not is_list and
                            not (ends_with_punctuation and starts_with_capital)):
                            should_merge = True
                    
                    if should_merge:
                        filtered_segments[-1]["data"] += " " + segment["data"]
                    else:
                        filtered_segments.append(segment)
            
            # Bước 2: Gộp các image segments liên tiếp thành images segments
            final_segments = []
            i = 0
            while i < len(filtered_segments):
                current_segment = filtered_segments[i]
                
                if current_segment["type"] == "image":
                    # Tìm tất cả image segments liên tiếp
                    consecutive_images = [current_segment["data"]]
                    j = i + 1
                    
                    while j < len(filtered_segments) and filtered_segments[j]["type"] == "image":
                        consecutive_images.append(filtered_segments[j]["data"])
                        j += 1
                    
                    # Nếu có 2+ hình ảnh liên tiếp, gộp thành "images"
                    if len(consecutive_images) >= 2:
                        final_segments.append({
                            "type": "images",
                            "data": consecutive_images
                        })
                    else:
                        # Chỉ có 1 hình ảnh, giữ nguyên type "image"
                        final_segments.append({
                            "type": "image",
                            "data": consecutive_images[0]
                        })
                    
                    i = j  # Bỏ qua các image đã được xử lý
                else:
                    # Không phải image segment, thêm bình thường
                    final_segments.append(current_segment)
                    i += 1
            
            return final_segments
            
        except Exception as e:
            logger.error(f"❌ Error parsing response to segments: {e}")
            # Fallback: trả về toàn bộ text như một segment
            return [{"type": "text", "data": response_text}]


    async def process_message_buffered(self, sender_id: str, page_id: str, bot_id: str, message: str, send_facebook: bool = False, company_id: str = None) -> None:
        """
        Thêm tin nhắn vào buffer để gom nhóm với các tin nhắn liên tiếp
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID
            bot_id: Bot ID
            message: Tin nhắn người dùng
            send_facebook: Có gửi response về Facebook hay không
            company_id: ID của company
        """
        await self.message_buffer.add_message(
            sender_id=sender_id,
            page_id=page_id,
            bot_id=bot_id,
            message=message,
            send_facebook=send_facebook,
            processor_func=self._process_and_send_response,
            company_id=company_id,
        )

    async def _process_and_send_response(self, sender_id: str, page_id: str, bot_id: str, message: str, send_facebook: bool, company_id: str = None) -> None:
        """
        Xử lý tin nhắn và gửi response (được gọi bởi message buffer)
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID
            bot_id: Bot ID
            message: Tin nhắn đã được gom nhóm
            send_facebook: Có gửi response về Facebook hay không
            company_id: ID của company
        """
        try:
            await self.process_message_immediate(sender_id, page_id, bot_id, message, send_facebook, company_id=company_id)
            
        except Exception as e:
            logger.error(f"❌ Error in _process_and_send_response: {e}")

    async def process_message_immediate(self, sender_id: str, page_id: str, bot_id: str, message: str, send_facebook: bool = False, company_id: str = None) -> BotResponse:
        """
        Xử lý tin nhắn ngay lập tức với OPTIMIZED AGENT (LangGraph)
        
        Args:
            sender_id: Facebook sender ID
            page_id: Facebook page ID
            bot_id: Bot ID
            message: Tin nhắn người dùng
            send_facebook: Có gửi response về Facebook hay không
            company_id: ID của company
            
        Returns:
            BotResponse: Phản hồi của bot
        """
        try:
            # Import here to avoid circular import
            from bot.integration import process_message_with_optimized_agent
            
            response = await process_message_with_optimized_agent(
                bot_agent=self,
                sender_id=sender_id,
                page_id=page_id,
                bot_id=bot_id,
                message=message,
                company_id=company_id
            )
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error processing message: {e}")
            error_msg = "Xin lỗi, Hệ thống đang gặp chút sự cố nhỏ trong việc xử lý yêu cầu của bạn. Bạn vui lòng thử lại hoặc diễn đạt khác đi một chút nhé!"
            return BotResponse(
                response=error_msg,
                segments=[{"type": "text", "data": error_msg}],
                metadata={"error": str(e)}
            )

# Global instance
bot_facebook_messenger = BotMessengerAgentV2()

async def process_facebook_message(sender_id: str, page_id: str, bot_id: str = None, message: str = "", use_buffer: bool = True, send_facebook: bool = False, type: str = "", company_id: str = None, local_image_paths: Optional[List[str]] = None) -> Optional[BotResponse]:
    """
    Main function để xử lý tin nhắn Facebook với tối ưu hóa tốc độ
    
    Args:
        sender_id: Facebook sender ID  
        page_id: Facebook page ID
        bot_id: ID của bot (nếu có)
        message: Tin nhắn người dùng
        use_buffer: Có sử dụng message buffering hay không (mặc định True)
        send_facebook: Có gửi response về Facebook hay không
        type: Loại tin nhắn (text, sticker, etc.)
        company_id: ID của company (nếu không có sẽ lấy company mặc định)
        local_image_paths: Local file paths của ảnh đã download (nếu có)
        
    Returns:
        BotResponse hoặc None nếu sử dụng buffer (response sẽ được gửi sau khi buffer xử lý)
    """
    
    try:
        # Initialize agent if needed
        if not bot_facebook_messenger.factory:
            await bot_facebook_messenger.initialize()
            
            # ✅ OPTIMIZATION: Warm up cache cho page này ngay sau khi initialize
            await bot_facebook_messenger.warm_up_cache(page_ids=[page_id])
        
        # ✅ OPTIMIZATION: Sử dụng cached token thay vì query mỗi lần
        if not bot_facebook_messenger.page_access_token:
            bot_facebook_messenger.page_access_token = await bot_facebook_messenger.get_page_access_token_cached(page_id)
        
        # Lấy company_id: nếu không có thì lấy default company từ user_id của bot
        if not company_id:
            try:
                # Lấy bot info để có user_id
                bot_info = None
                if bot_id:
                    bot_info = await bot_facebook_messenger.get_bot_info_from_bot_id(bot_id)
                else:
                    bot_info = await bot_facebook_messenger.get_bot_info_from_page_id(page_id)
                
                if bot_info and bot_info.get('user_id'):
                    user_id = bot_info['user_id']
                    # Lấy default company của user
                    default_company = await bot_facebook_messenger.factory.crm_factory.company_manager.get_default_company_by_user_id(user_id)
                    if default_company:
                        company_id = str(default_company.get('_id'))
                        logger.debug(f"✅ Using default company: {company_id} for user: {user_id}")
                    else:
                        logger.debug(f"⚠️ No default company found for user: {user_id}")
                else:
                    logger.debug(f"⚠️ Could not get bot info for page_id: {page_id}, bot_id: {bot_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to get default company: {e}")
        
        # ⚡ SPEED OPTIMIZATION: Fire-and-forget typing indicators (không đợi)
        # Chạy async task trong background, không block main flow
        async def send_typing_indicators_async():
            try:
                await asyncio.to_thread(
                    send_typing_action,
                    page_id,
                    bot_facebook_messenger.page_access_token,
                    sender_id,
                    typing="mark_seen",
                )
                await asyncio.to_thread(
                    send_typing_action,
                    page_id,
                    bot_facebook_messenger.page_access_token,
                    sender_id,
                )
            except Exception as e:
                logger.debug(f"Typing indicator failed (non-critical): {e}")
        
        # Fire and forget - không await
        asyncio.create_task(send_typing_indicators_async())
        
        # ✅ Store local_image_paths in cache nếu có
        if local_image_paths:
            bot_facebook_messenger.local_image_paths_cache[sender_id] = local_image_paths
            logger.info(f"✅ Stored {len(local_image_paths)} local image paths for sender {sender_id}")
    
        if type != "sticker":
            if use_buffer:
                # Thêm vào buffer, không trả về response ngay
                await bot_facebook_messenger.process_message_buffered(sender_id, page_id, bot_id, message, send_facebook=send_facebook, company_id=company_id)
                # logger.info(f"📨 Message added to buffer for {sender_id}")
                return None
            else:
                # Xử lý ngay lập tức
                response = await bot_facebook_messenger.process_message_immediate(sender_id, page_id, bot_id, message, send_facebook=send_facebook, company_id=company_id)
            
            # Send response back via Facebook API
            # if send_facebook and response.segments:
            #     await send_facebook_messenger(page_id, sender_id, response.segments)
                
        elif type == "sticker" and send_facebook:
            # Gửi sticker response trong background
            asyncio.create_task(
                send_facebook_messenger(page_id, sender_id, [{"type": "text", "data": "🥰"}])
            )
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error in process_facebook_message: {e}")
        error_msg = "Xin lỗi, Hệ thống đang gặp chút sự cố nhỏ trong việc xử lý yêu cầu của bạn. Bạn vui lòng thử lại hoặc diễn đạt khác đi một chút nhé!"
        return BotResponse(
            response=error_msg,
            segments=[{"type": "text", "data": error_msg}],
            metadata={"error": str(e)}
        )

async def send_typing_indicators_async_public(page_id, page_access_token, sender_id):
    try:
        await asyncio.to_thread(
            send_typing_action,
            page_id,
            page_access_token,
            sender_id,
        )
    except Exception as e:
        logger.debug(f"Typing indicator failed (non-critical): {e}")
                
                
