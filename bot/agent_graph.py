"""
Optimized Agent Graph sử dụng LangGraph cho Facebook Messenger Bot
Tối ưu tốc độ và độ thông minh khi gọi tools

Features:
1. Query Routing: Phân loại intent để gọi đúng tool ngay từ đầu
2. Parallel Execution: Chạy nhiều tools song song khi có thể
3. ReAct Pattern: Reasoning -> Action -> Observation loop
4. Smart Caching: Cache tool results với TTL
5. Retry Logic: Tự động retry với fallback
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, TypedDict, Annotated
from datetime import datetime
import operator
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

from bot.bot_facebook_messenger import bot_facebook_messenger


# ==================== STATE DEFINITION ====================
class AgentState(TypedDict):
    """State cho Agent Graph"""
    # Input
    user_message: str
    sender_id: str
    page_id: str
    bot_id: str
    company_id: Optional[str]
    
    # Context
    bot_info: Optional[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]
    sender_info: Optional[Dict[str, Any]]
    image_context: str
    qa_pairs_context: str  # ✅ Q&A pairs context from knowledge base
    history_text: str
    current_time_str: str
    
    # Agent working memory
    messages: Annotated[List, operator.add]  # Lưu messages của agent
    intent: Optional[str]  # Phân loại intent: product_search, knowledge_query, customer_info, order, general
    tools_to_call: List[str]  # Danh sách tools cần gọi
    tool_results: Dict[str, Any]  # Kết quả từ tools
    
    # Output
    response: str
    segments: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    
    # Control flow
    step_count: int
    max_steps: int
    should_continue: bool


# ==================== QUERY ROUTING ====================
class QueryRouter:
    """
    Phân loại intent của user query để routing đến đúng tools
    Sử dụng LLM nhẹ để classify nhanh
    """
    
    def __init__(self):
        # LLM cho classification và query processing
        self.classifier_llm = ChatOpenAI(
            model="gpt-4.1-mini",  # ✅ Sử dụng model đúng
            temperature=0,
            max_tokens=500  # ✅ Tăng để có thể xử lý nhiều output hơn
        )
        
        # ✅ NEW: Prompt tích hợp cả classification + keyword extraction + query rewriting
        self.processing_prompt = ChatPromptTemplate.from_messages([
            ("system", """Bạn là query processor thông minh. 
             
### [ Nhiệm vụ ]:
1. PHÂN LOẠI INTENT vào 1 trong các category:
   - product_search: Tìm kiếm sản phẩm / dịch vụ, hỏi về giá, SKU, còn hàng không, xem ảnh
   - knowledge_query: Hỏi về chính sách, quy định, thanh toán, vận chuyển, hoặc các thông tin khác,...
   - customer_info: Tìm thông tin cá nhân (tên, SĐT, địa chỉ), Khi cần dùng tới thông tin khách hàng (trước khi đặt hàng, giao hàng, vận chuyển, hỗ trợ,...)
   - order_management: Đặt hàng, xem đơn hàng, cập nhật đơn
   - general: Chào hỏi, cảm ơn, tạm biệt

2. REWRITE QUERY dựa trên lịch sử hội thoại:
   - Nếu query mơ hồ ("nó", "cái này", "bao nhiêu tiền") → thay thế bằng thông tin cụ thể từ history
   - Nếu query thiếu context → bổ sung context từ những câu hỏi trước
   - Ví dụ: 
     * History: "Có túi Maggie không?" → Bot: "Có ạ..."
     * Query: "bao nhiêu tiền" → Rewrite: "giá túi Maggie"
     * Query: "tìm nó" → Rewrite: "túi Maggie"

3. EXTRACT KEYWORDS cho search:
   - Product search: Tách tên sản phẩm, SKU (nếu có), từ khóa chính
   - Knowledge search: Lấy keywords quan trọng, bỏ stop words

---

HISTORY (3 câu gần nhất, Link all chat history to create a more seamless conversation.):
{history}

---

USER QUERY: {query}

---

OUTPUT FORMAT (JSON):
{{
    "intent": "product_search",
    "original_query": "túi Maggie giá bao nhiêu",
    "rewritten_query": "giá túi Maggie",
    "product_keywords": {{
        "search_query": "giá túi Maggie",
        "search_query_keyword": "Maggie", 
        "sku": null
    }},
    "knowledge_keywords": {{
        "query": "giá túi Maggie",
        "original_query": "túi Maggie giá bao nhiêu"
    }}
}}"""),
        ])
        
        # Cache để tránh classify lại các query tương tự
        self.classification_cache = {}
        
    async def process_query(self, query: str, history_text: str = "") -> dict:
        """
        Process query với LLM: classify intent + rewrite query + extract keywords
        
        Args:
            query: User query
            history_text: Lịch sử trò chuyện (3 câu gần nhất)
            
        Returns:
            dict with:
                - intent: Classified intent
                - rewritten_query: Query đã rewrite với context
                - product_keywords: Keywords cho search_products
                - knowledge_keywords: Keywords cho search_knowledge
        """
        try:
            import json
            
            # Normalize query để cache tốt hơn
            query_normalized = query.lower().strip()
            cache_key = f"{query_normalized}_{history_text[:50]}"
            
            # Check cache
            if cache_key in self.classification_cache:
                # logger.debug(f"✅ Query processing cache hit: {query_normalized[:30]}...")
                return self.classification_cache[cache_key]
            
            # ❌ DISABLED Fast path - LUÔN dùng LLM để extract keywords thông minh
            # Lý do: Fast path không extract keywords đúng → search kém hiệu quả
            # VD: "túi maggie giá bao nhiêu" → cần extract thành "maggie" hoặc "túi maggie"
            # Chỉ LLM mới làm được việc này tốt với context từ history
            
            # ✅ LLM processing (cho queries phức tạp hoặc cần context)
            logger.info(f"🤖 Using LLM to process query with history context...")
            
            prompt = self.processing_prompt.format_messages(
                query=query,
                history=history_text if history_text else "Chưa có lịch sử"
            )
            
            response = await self.classifier_llm.ainvoke(prompt)
            response_text = response.content.strip()
            
            # Parse JSON response
            try:
                # Extract JSON từ response (có thể có markdown wrapper)
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                result = json.loads(response_text)
                
                # Validate intent
                valid_intents = ["product_search", "knowledge_query", "customer_info", "order_management", "general"]
                if result.get("intent") not in valid_intents:
                    result["intent"] = "general"
                
                # Ensure all required fields exist
                if "rewritten_query" not in result:
                    result["rewritten_query"] = query
                if "product_keywords" not in result:
                    result["product_keywords"] = {
                        "search_query": result["rewritten_query"],
                        "search_query_keyword": result["rewritten_query"],
                        "sku": None
                    }
                if "knowledge_keywords" not in result:
                    result["knowledge_keywords"] = {
                        "query": result["rewritten_query"],
                        "original_query": query
                    }
                
                # logger.info(f"🎯 LLM processing result:")
                # logger.info(f"  - Intent: {result['intent']}")
                # logger.info(f"  - Original: {query}")
                # logger.info(f"  - Rewritten: {result['rewritten_query']}")
                # logger.info(f"  - Product keywords: {result['product_keywords']}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse LLM JSON response: {e}")
                logger.error(f"   Raw response: {response_text}")
                # Fallback to simple processing
                result = {
                    "intent": "general",
                    "rewritten_query": query,
                    "product_keywords": {
                        "search_query": query,
                        "search_query_keyword": query,
                        "sku": None
                    },
                    "knowledge_keywords": {
                        "query": query,
                        "original_query": query
                    }
                }
            
            # Cache kết quả
            self.classification_cache[cache_key] = result
            
            # Giới hạn cache size
            if len(self.classification_cache) > 500:
                # Remove oldest entries
                keys_to_remove = list(self.classification_cache.keys())[:100]
                for key in keys_to_remove:
                    del self.classification_cache[key]
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error processing query: {e}", exc_info=True)
            return {
                "intent": "general",
                "rewritten_query": query,
                "product_keywords": {
                    "search_query": query,
                    "search_query_keyword": query,
                    "sku": None
                },
                "knowledge_keywords": {
                    "query": query,
                    "original_query": query
                }
            }
    
    async def classify(self, query: str, history_text: str = "") -> str:
        """
        Classify query intent (wrapper for backward compatibility)
        """
        result = await self.process_query(query, history_text)
        return result["intent"]


# ==================== TOOL SELECTOR ====================
class ToolSelector:
    """
    Chọn tools cần gọi dựa trên intent và query
    Hỗ trợ parallel execution khi có thể
    """
    
    # Mapping intent -> tools
    INTENT_TOOL_MAPPING = {
        "product_search": ["search_products", "search_knowledge"],  # Có thể cần cả 2
        "knowledge_query": ["search_knowledge"],
        "customer_info": ["get_customer_info"],  # ✅ CHỈ GET, không hardcode SAVE
        "order_management": ["search_products"],  # ✅ CHỈ SEARCH, không hardcode SAVE ORDER
        "general": []  # Không cần tools
    }
    
    @staticmethod
    def select_tools(intent: str, query: str) -> List[str]:
        """
        Select tools dựa trên intent và query
        
        Args:
            intent: Classified intent
            query: User query
            
        Returns:
            List of tool names to call
        """
        tools = ToolSelector.INTENT_TOOL_MAPPING.get(intent, [])
        
        # Refine tool selection based on query keywords
        query_lower = query.lower()
        
        if intent == "product_search":
            # ✅ LUÔN GỌI CẢ search_products VÀ search_knowledge song song
            # Lý do: search_knowledge chứa Q&A pairs có thể trả lời câu hỏi về sản phẩm
            # VD: "túi Maggie giá bao nhiêu" → search_products có thể không tìm thấy
            #     nhưng Q&A pairs có câu trả lời về giá
            tools = ["search_products", "search_knowledge"]
            
            # logger.info(f"🔧 Product search: Will call both search_products AND search_knowledge in parallel")
        
        elif intent == "customer_info":
            # ✅ CHỈ GET thông tin khách hàng, không hardcode SAVE
            # Lý do: save_customer_info cần nhiều params → để LLM tự quyết định thông qua response
            tools = ["get_customer_info"]
        
        elif intent == "order_management":
            # ✅ CHỈ SEARCH sản phẩm hoặc GET đơn hàng, không hardcode SAVE ORDER
            # Lý do: save_order cần nhiều params → để LLM tự quyết định thông qua response
            if any(kw in query_lower for kw in ['đặt', 'mua', 'order', 'chốt']):
                tools = ["search_products", "get_customer_info"]  # ✅ Lấy info để confirm
            elif any(kw in query_lower for kw in ['xem', 'kiểm tra', 'check']):
                tools = ["get_order_info"]
            elif any(kw in query_lower for kw in ['cập nhật', 'sửa', 'thay đổi']):
                tools = ["get_order_info"]  # ✅ update_order cần manual params
        
        logger.info(f"🔧 Selected tools for intent '{intent}': {tools}")
        return tools


# ==================== GRAPH NODES ====================
async def route_query(state: AgentState) -> AgentState:
    """
    Node 1: Route query để classify intent + rewrite query với history context
    ✅ NEW: Tự động phát hiện ảnh và thêm search_products_by_image tool
    """
    try:
        # logger.info("🎯 [Node: route_query] Processing query with history context...")
        
        router = QueryRouter()
        
        # ✅ Process query với LLM (classify + rewrite + extract keywords)
        processing_result = await router.process_query(
            state["user_message"], 
            state.get("history_text", "")
        )
        
        intent = processing_result["intent"]
        rewritten_query = processing_result["rewritten_query"]
        
        # Select tools dựa trên intent
        tools_to_call = ToolSelector.select_tools(intent, rewritten_query)
        
        # ✅ NEW: Tự động phát hiện ảnh trong message và thêm search_products_by_image
        user_message = state["user_message"]
        import re
        # Regex để detect image URLs (Facebook CDN, http/https images)
        image_url_patterns = [
            r'https?://[^\s]*(?:fbcdn|fbsbx)[^\s]+',  # Facebook CDN
            r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp)',  # Image extensions
        ]
        
        image_urls = []
        for pattern in image_url_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            image_urls.extend(matches)
        
        # Remove duplicates
        image_urls = list(set(image_urls))
        
        if image_urls:
            logger.info(f"🖼️ Detected {len(image_urls)} image URLs in message")
            # Thêm search_products_by_image vào tools_to_call nếu chưa có
            if "search_products_by_image" not in tools_to_call:
                tools_to_call.insert(0, "search_products_by_image")  # Ưu tiên gọi đầu tiên
                logger.info(f"✅ Added search_products_by_image to tools")
            
            # Lưu image URLs vào metadata để dùng cho tool calling
            if "metadata" not in state:
                state["metadata"] = {}
            state["metadata"]["image_urls"] = image_urls
        
        # ✅ Lưu processing result vào state để dùng cho tool calling
        state["intent"] = intent
        state["tools_to_call"] = tools_to_call
        state["metadata"] = {
            **state.get("metadata", {}),
            "rewritten_query": rewritten_query,
            "product_keywords": processing_result["product_keywords"],
            "knowledge_keywords": processing_result["knowledge_keywords"]
        }
        state["step_count"] = state.get("step_count", 0) + 1
        
        # logger.info(f"✅ Intent: {intent}")
        # logger.info(f"✅ Original query: {state['user_message']}")
        # logger.info(f"✅ Rewritten query: {rewritten_query}")
        # logger.info(f"✅ Tools to call: {tools_to_call}")
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error in route_query: {e}", exc_info=True)
        state["intent"] = "general"
        state["tools_to_call"] = []
        state["metadata"] = {}
        return state


async def call_tools_parallel(state: AgentState, tools_dict: Dict[str, Any]) -> AgentState:
    """
    Node 2: Gọi tools song song khi có thể
    """
    try:
        # logger.info("🔧 [Node: call_tools_parallel] Calling tools...")
        
        tools_to_call = state.get("tools_to_call", [])
        if not tools_to_call:
            # logger.info("⏭️ No tools to call, skipping...")
            state["should_continue"] = False
            return state
        
        # logger.info(f"🔧 Tools to call: {tools_to_call}")
        
        # Prepare tool inputs
        sender_id = state["sender_id"]
        page_id = state["page_id"]
        query = state["user_message"]
        
        # ✅ Get keywords từ metadata (đã được LLM extract trong route_query)
        metadata = state.get("metadata", {})
        product_keywords = metadata.get("product_keywords", {
            "search_query": query,
            "search_query_keyword": query,
            "sku": None
        })
        knowledge_keywords = metadata.get("knowledge_keywords", {
            "query": query,
            "original_query": query
        })
        rewritten_query = metadata.get("rewritten_query", query)
        
        # logger.info(f"📝 Tool inputs - Original: '{query[:50]}...'")
        # logger.info(f"📝 Rewritten query: '{rewritten_query[:50]}...'")
        # logger.info(f"🔑 Product keywords: {product_keywords}")
        # logger.info(f"🔑 Knowledge keywords: {knowledge_keywords}")
        
        # Xác định tools có thể chạy parallel
        # Rule: search_products, search_knowledge, và search_products_by_image có thể chạy song song
        parallel_groups = []
        current_group = []
        
        for tool_name in tools_to_call:
            if tool_name in ["search_products", "search_knowledge", "search_products_by_image"]:
                current_group.append(tool_name)
            else:
                if current_group:
                    parallel_groups.append(current_group)
                    current_group = []
                parallel_groups.append([tool_name])
        
        if current_group:
            parallel_groups.append(current_group)
        
        # logger.info(f"🔄 Parallel execution groups: {parallel_groups}")
        
        # Execute tools theo groups
        tool_results = {}
        
        for group_idx, group in enumerate(parallel_groups, 1):
            # logger.info(f"📦 Executing group {group_idx}/{len(parallel_groups)}: {group}")
            
            if len(group) == 1:
                # Execute single tool
                tool_name = group[0]
                tool_func = tools_dict.get(tool_name)
                if tool_func:
                    try:
                        # logger.info(f"🔨 Executing tool: {tool_name}")
                        
                        if tool_name == "search_products":
                            # ✅ Sử dụng extracted keywords
                            result = await asyncio.to_thread(
                                tool_func,
                                search_query=product_keywords['search_query'],
                                search_query_keyword=product_keywords['search_query_keyword'],
                                sku=product_keywords['sku']
                            )
                        elif tool_name == "search_knowledge":
                            # ✅ Sử dụng extracted keywords
                            result = await asyncio.to_thread(
                                tool_func,
                                query=knowledge_keywords['query'],
                                original_query=knowledge_keywords['original_query']
                            )
                        elif tool_name == "search_products_by_image":
                            # ✅ NEW: Gọi search_products_by_image với image URLs
                            image_urls = metadata.get("image_urls", [])
                            if image_urls:
                                # Chỉ search với ảnh đầu tiên
                                result = await asyncio.to_thread(
                                    tool_func,
                                    image_url=image_urls[0]
                                )
                            else:
                                result = "No image URL found"
                        elif tool_name == "get_customer_info":
                            result = await asyncio.to_thread(tool_func, sender_id=sender_id, page_id=page_id)
                        elif tool_name == "get_order_info":
                            result = await asyncio.to_thread(tool_func, sender_id=sender_id, page_id=page_id)
                        else:
                            result = "Tool requires manual parameters"
                        
                        tool_results[tool_name] = result
                        logger.info(f"✅ Tool '{tool_name}' executed successfully - Result length: {len(str(result))} chars")
                        # logger.debug(f"   Result preview: {str(result)[:200]}...")
                    except Exception as e:
                        logger.error(f"❌ Error executing tool '{tool_name}': {e}", exc_info=True)
                        tool_results[tool_name] = f"Error: {str(e)}"
            else:
                # Execute parallel
                # logger.info(f"⚡ Running {len(group)} tools in parallel...")
                
                async def execute_tool(tool_name):
                    tool_func = tools_dict.get(tool_name)
                    if not tool_func:
                        logger.error(f"❌ Tool '{tool_name}' not found in tools_dict")
                        return tool_name, "Tool not found"
                    
                    try:
                        # logger.info(f"  🔨 Starting parallel execution: {tool_name}")
                        
                        if tool_name == "search_products":
                            # ✅ Sử dụng extracted keywords
                            result = await asyncio.to_thread(
                                tool_func,
                                search_query=product_keywords['search_query'],
                                search_query_keyword=product_keywords['search_query_keyword'],
                                sku=product_keywords['sku']
                            )
                        elif tool_name == "search_knowledge":
                            # ✅ Sử dụng extracted keywords
                            result = await asyncio.to_thread(
                                tool_func,
                                query=knowledge_keywords['query'],
                                original_query=knowledge_keywords['original_query']
                            )
                        elif tool_name == "search_products_by_image":
                            # ✅ NEW: Parallel execution for image search
                            image_urls = metadata.get("image_urls", [])
                            if image_urls:
                                result = await asyncio.to_thread(
                                    tool_func,
                                    image_url=image_urls[0]
                                )
                            else:
                                result = "No image URL found"
                        else:
                            result = "Tool requires manual parameters"
                        
                        # logger.info(f"  ✅ {tool_name} completed - {len(str(result))} chars")
                        return tool_name, result
                    except Exception as e:
                        logger.error(f"  ❌ Error in parallel execution of '{tool_name}': {e}", exc_info=True)
                        return tool_name, f"Error: {str(e)}"
                
                # Run parallel
                results = await asyncio.gather(*[execute_tool(tn) for tn in group])
                for tool_name, result in results:
                    tool_results[tool_name] = result
                    # logger.info(f"✅ Parallel tool '{tool_name}' result stored")
        
        state["tool_results"] = tool_results
        state["step_count"] = state.get("step_count", 0) + 1
        
        # logger.info(f"✅ All tools executed successfully!")
        # logger.info(f"📊 Tool results summary:")
        # for tool_name, result in tool_results.items():
        #     logger.info(f"  - {tool_name}: {len(str(result))} chars")
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error in call_tools_parallel: {e}", exc_info=True)
        state["tool_results"] = {}
        return state


async def generate_response(state: AgentState, llm: ChatOpenAI) -> AgentState:
    """
    Node 3: Generate response dựa trên tool results và context
    """
    try:
        # logger.info("💬 [Node: generate_response] Generating final response...")
        
        # Build context từ tool results
        tool_context = ""
        if state.get("tool_results"):
            # logger.info(f"📦 Building tool context from {len(state['tool_results'])} tools")
            for tool_name, result in state["tool_results"].items():
                tool_context += f"\n### Kết quả từ {tool_name}:\n{result}\n"
                logger.debug(f"  - {tool_name}: {len(str(result))} chars")
        
        # Build prompt - SỬ DỤNG PROMPT CHÍNH
        from configs.prompts import prompt_facebook_messenger
        
        bot_info = state.get("bot_info", {}) or {}
        identity = bot_info.get("identity") or {}
        procedure = bot_info.get("procedure") or {}
        bot = bot_info.get("bot") or {}
        
        # Lấy Q&A context từ state
        qa_pairs_context = state.get("qa_pairs_context", "")
        
        # logger.info(f"🔍 Debugging Q&A context:")
        # logger.info(f"  - state keys: {list(state.keys())}")
        # logger.info(f"  - qa_pairs_context value: {qa_pairs_context[:200] if qa_pairs_context else 'EMPTY'}")
        # logger.info(f"  - qa_pairs_context type: {type(qa_pairs_context)}")
        # logger.info(f"  - qa_pairs_context length: {len(qa_pairs_context) if qa_pairs_context else 0}")
        
        if qa_pairs_context:
            # logger.info(f"✅ Using Q&A context: {len(qa_pairs_context)} chars")
            logger.debug(f"📝 Q&A Context preview:\n{qa_pairs_context[:500]}...")
        else:
            logger.warning("⚠️ No Q&A context available in state!")
            logger.warning(f"   Full state dump: {state}")
        
        procedure_content = (procedure.get("procedure", "") if isinstance(procedure, dict) else "") or (
            procedure.get("content", "") if isinstance(procedure, dict) else ""
        )
        if procedure_content:
            logger.info(f"✅ Using procedure: {len(procedure_content)} chars")
        else:
            logger.warning("⚠️ No procedure content available!")
        
        # ✅ Sử dụng RESPONSE_ONLY prompt (không có phần Tools để tránh LLM trả JSON)
        system_prompt = prompt_facebook_messenger.FACEBOOK_MESSENGER_RESPONSE_ONLY.format(
            role=bot.get("role", ""),
            target=bot.get("target", ""),
            mission=bot.get("mission", ""),
            history=state.get('history_text', 'Chưa có lịch sử'),
            user_message=state["user_message"],
            sender_info=state.get('sender_info', 'Chưa có thông tin'),
            identity_info=identity.get("info", ""),
            identity_style=identity.get("style", ""),
            conversation_style=identity.get("conversation_style", ""),
            conversation_example=identity.get("conversation_example", ""),
            time_now=state.get('current_time_str', ''),
            note=bot.get("note", ""),
            image_context=state.get('image_context', ''),
            procedure_content=procedure_content,
            sender_id=state["sender_id"],
            page_id=state["page_id"],
            agent_scratchpad=tool_context,  # Tools results làm scratchpad
            qa_pairs_context=qa_pairs_context  # ✅ Q&A pairs context
        )


        # logging.info(f"📝 Final prompt:\n\n {system_prompt}")
        
        messages = [
            SystemMessage(content=system_prompt)
        ]
        
        # logger.info(f"🤖 Calling LLM with prompt length: {len(system_prompt)} chars")
        
        # Generate response
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        # logger.info(f"✅ LLM response received: {len(response_text)} chars")
        
        # Parse response to segments (reuse existing logic)
        segments = bot_facebook_messenger.parse_response_to_segments(response_text)
        # logger.info(f"📄 Parsed into {len(segments)} segments")
        
        state["response"] = response_text
        state["segments"] = segments
        state["metadata"] = {
            "intent": state.get("intent"),
            "tools_called": list(state.get("tool_results", {}).keys()),
            "step_count": state.get("step_count", 0)
        }
        state["should_continue"] = False
        
        # logger.info(f"✅ Response generation completed")
        return state
        
    except Exception as e:
        logger.error(f"❌ Error in generate_response: {e}", exc_info=True)
        error_msg = "Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn."
        state["response"] = error_msg
        state["segments"] = [{"type": "text", "data": error_msg}]
        state["metadata"] = {"error": str(e)}
        state["should_continue"] = False
        return state


async def auto_save_customer_order_info(state: AgentState, tools_dict: Dict[str, Any]) -> AgentState:
    """
    Node 4: Tự động extract và lưu thông tin khách hàng + đơn hàng từ conversation
    
    Chỉ chạy khi:
    - Intent là customer_info hoặc order_management
    - Response đã được generate
    - Phát hiện có thông tin cần lưu trong conversation
    """
    try:
        intent = state.get("intent")
        
        # Chỉ xử lý khi intent liên quan đến customer hoặc order
        if intent not in ["customer_info", "order_management"]:
            logger.info("⏭️ Intent không cần lưu thông tin, skipping...")
            return state
        
        logger.info(f"💾 [Node: auto_save] Detecting info to save for intent '{intent}'...")
        
        # Lấy context
        user_message = state["user_message"]
        bot_response = state.get("response", "")
        history_text = state.get("history_text", "")
        sender_id = state["sender_id"]
        page_id = state["page_id"]
        
        # ✅ Sử dụng LLM để extract thông tin cần lưu
        extractor_llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0,
            max_tokens=800
        )
        
        extraction_prompt = f"""Bạn là information extractor thông minh.

### [ NHIỆM VỤ ]:
Phân tích cuộc hội thoại và extract thông tin khách hàng + đơn hàng (nếu có).

---
HISTORY (3 câu gần nhất):
{history_text if history_text else "Chưa có"}

USER: {user_message}

BOT: {bot_response}
---

### [ OUTPUT FORMAT (JSON) ]:

Nếu có thông tin khách hàng mới:
{{
    "has_customer_info": true,
    "customer_info": {{
        "name": "Nguyễn Văn A",
        "phone": "0901234567",
        "address": "123 Đường ABC, Quận 1, TP.HCM",
        "email": null,
        "additional_info": "Khách quan tâm đến túi xách"
    }}
}}

Nếu khách chốt đơn (xác nhận mua/đặt hàng):
{{
    "has_order": true,
    "order_info": {{
        "product_name": "Túi Maggie",
        "unit_price": 500000,
        "quantity": 2,
        "total_price": 1000000,
        "customer_note": "Giao buổi chiều",
        "customer_name": "Nguyễn Văn A",
        "customer_phone": "0901234567",
        "customer_address": "123 Đường ABC",
        "payment_method": "COD",
        "payment_status": "pending"
    }}
}}

Nếu KHÔNG có thông tin gì:
{{
    "has_customer_info": false,
    "has_order": false
}}

### [ LƯU Ý ]:
- CHỈ extract khi khách CUNG CẤP thông tin mới
- CHỈ has_order=true khi khách XÁC NHẬN CHỐT ĐƠN (đặt, mua, xác nhận)
- Không tự bịa thông tin
- Giá tiền phải lấy từ tool results hoặc history
"""
        
        messages = [SystemMessage(content=extraction_prompt)]
        response = await extractor_llm.ainvoke(messages)
        response_text = response.content.strip()
        
        # Parse JSON
        try:
            import json
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            extracted = json.loads(response_text)
            
            logger.info(f"📊 Extraction result: {extracted}")
            
            # ✅ Lưu thông tin khách hàng nếu có
            if extracted.get("has_customer_info") and extracted.get("customer_info"):
                customer_info = extracted["customer_info"]
                save_customer_tool = tools_dict.get("save_customer_info")
                
                if save_customer_tool:
                    logger.info(f"💾 Saving customer info: {customer_info}")
                    result = await asyncio.to_thread(
                        save_customer_tool,
                        sender_id=sender_id,
                        page_id=page_id,
                        name=customer_info.get("name"),
                        phone=customer_info.get("phone"),
                        address=customer_info.get("address"),
                        email=customer_info.get("email"),
                        additional_info=customer_info.get("additional_info")
                    )
                    logger.info(f"✅ Customer info saved: {result}")
                    
                    # Thêm vào metadata
                    state["metadata"]["customer_saved"] = True
            
            # ✅ Lưu đơn hàng nếu có
            if extracted.get("has_order") and extracted.get("order_info"):
                order_info = extracted["order_info"]
                save_order_tool = tools_dict.get("save_order")
                
                if save_order_tool:
                    logger.info(f"📦 Saving order: {order_info}")
                    result = await asyncio.to_thread(
                        save_order_tool,
                        sender_id=sender_id,
                        page_id=page_id,
                        product_name=order_info.get("product_name"),
                        unit_price=order_info.get("unit_price"),
                        quantity=order_info.get("quantity"),
                        total_price=order_info.get("total_price"),
                        customer_note=order_info.get("customer_note", ""),
                        customer_name=order_info.get("customer_name"),
                        customer_phone=order_info.get("customer_phone"),
                        customer_address=order_info.get("customer_address"),
                        payment_method=order_info.get("payment_method"),
                        payment_status=order_info.get("payment_status", "pending")
                    )
                    logger.info(f"✅ Order saved: {result}")
                    
                    # Thêm vào metadata
                    state["metadata"]["order_saved"] = True
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse extraction JSON: {e}")
            logger.error(f"   Raw response: {response_text}")
        
        return state
        
    except Exception as e:
        logger.error(f"❌ Error in auto_save_customer_order_info: {e}", exc_info=True)
        return state


def should_continue_routing(state: AgentState) -> str:
    """
    Conditional edge: Quyết định có tiếp tục hay không
    """
    # Check max steps
    if state.get("step_count", 0) >= state.get("max_steps", 5):
        logger.info("⏹️ Max steps reached, ending...")
        return "generate"
    
    # Check if we need to call tools
    if state.get("tools_to_call") and not state.get("tool_results"):
        logger.info("🔄 Need to call tools...")
        return "tools"
    
    # Otherwise generate response
    # logger.info("💬 Moving to response generation...")
    return "generate"


# ==================== BUILD GRAPH ====================
def create_optimized_agent_graph(tools_dict: Dict[str, Any]) -> StateGraph:
    """
    Tạo optimized agent graph với LangGraph
    
    Args:
        tools_dict: Dictionary mapping tool name -> tool function
        
    Returns:
        Compiled StateGraph
    """
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4.1",  # ✅ Fixed: Đúng model name
        temperature=0.1,  # ✅ Fixed: Temperature thấp hơn cho consistent output
        streaming=False
    )
    
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes - IMPORTANT: Wrap async functions properly
    async def tools_node(state):
        return await call_tools_parallel(state, tools_dict)
    
    async def generate_node(state):
        return await generate_response(state, llm)
    
    async def auto_save_node(state):
        return await auto_save_customer_order_info(state, tools_dict)
    
    workflow.add_node("route", route_query)
    workflow.add_node("tools", tools_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("auto_save", auto_save_node)  # ✅ Thêm node mới
    
    # Add edges
    workflow.set_entry_point("route")
    
    workflow.add_conditional_edges(
        "route",
        should_continue_routing,
        {
            "tools": "tools",
            "generate": "generate"
        }
    )
    
    workflow.add_edge("tools", "generate")
    workflow.add_edge("generate", "auto_save")  # ✅ Sau generate → auto save
    workflow.add_edge("auto_save", END)  # ✅ Sau auto save → kết thúc
    
    # Compile
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    
    logger.info("✅ Optimized Agent Graph created successfully")
    return app


# ==================== USAGE EXAMPLE ====================
async def run_optimized_agent(
    user_message: str,
    sender_id: str,
    page_id: str,
    bot_id: str,
    bot_info: Dict[str, Any],
    conversation_history: List[Dict[str, Any]],
    sender_info: Optional[Dict[str, Any]],
    image_context: str,
    qa_pairs_context: str,  # ✅ Thêm Q&A context
    history_text: str,
    current_time_str: str,
    tools_dict: Dict[str, Any],
    company_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run optimized agent với LangGraph
    
    Returns:
        Dict with 'response', 'segments', 'metadata'
    """
    try:
        # logger.info(f"\n{'='*80}")
        # logger.info(f"🚀 run_optimized_agent called")
        # logger.info(f"  - Query: '{user_message[:50]}...'")
        # logger.info(f"  - QA context received: {len(qa_pairs_context) if qa_pairs_context else 0} chars")
        # logger.info(f"  - QA context preview: {qa_pairs_context[:200] if qa_pairs_context else 'EMPTY'}")
        # logger.info(f"{'='*80}\n")
        
        # Create graph
        app = create_optimized_agent_graph(tools_dict)
        # logger.info("✅ Graph created successfully")
        
        # Initial state
        initial_state = {
            "user_message": user_message,
            "sender_id": sender_id,
            "page_id": page_id,
            "bot_id": bot_id,
            "company_id": company_id,
            "bot_info": bot_info,
            "conversation_history": conversation_history,
            "sender_info": sender_info,
            "image_context": image_context,
            "qa_pairs_context": qa_pairs_context,  # ✅ Thêm vào state
            "history_text": history_text,
            "current_time_str": current_time_str,
            "messages": [],
            "intent": None,
            "tools_to_call": [],
            "tool_results": {},
            "response": "",
            "segments": [],
            "metadata": {},
            "step_count": 0,
            "max_steps": 5,
            "should_continue": True
        }
        
        # logger.info(f"� Initial state prepared:")
        # logger.info(f"  - qa_pairs_context in state: {bool(initial_state.get('qa_pairs_context'))}")
        # logger.info(f"  - qa_pairs_context length: {len(initial_state.get('qa_pairs_context', ''))}")
        # logger.info(f"  - State keys: {list(initial_state.keys())}")
        # logger.debug(f"  - Full qa_pairs_context: {initial_state.get('qa_pairs_context')}")
        
        # logger.info(f"📋 Tools available: {len(tools_dict)}")
        
        # Run graph
        config = {"configurable": {"thread_id": f"{sender_id}_{page_id}"}}
        # logger.info("🚀 Starting graph execution...")
        
        final_state = await app.ainvoke(initial_state, config=config)
        
        # logger.info(f"✅ Graph execution completed | Steps: {final_state.get('step_count')} | "
        #            f"Intent: {final_state.get('intent')} | Tools called: {list(final_state.get('tool_results', {}).keys())}")
        
        return {
            "response": final_state.get("response", ""),
            "segments": final_state.get("segments", []),
            "metadata": final_state.get("metadata", {})
        }
        
    except Exception as e:
        logger.error(f"❌ Error in run_optimized_agent: {e}", exc_info=True)
        error_msg = "Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn."
        return {
            "response": error_msg,
            "segments": [{"type": "text", "data": error_msg}],
            "metadata": {"error": str(e)}
        }
