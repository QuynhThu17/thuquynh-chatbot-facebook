"""
Integration module để sử dụng Optimized Agent trong bot hiện tại
"""

import logging
from typing import Dict, Any, Optional
from bot.models import BotResponse

from controllers.socials.facebook.facebook_send_messenger import send_facebook_messenger
from controllers.socials.facebook.facebook_connect import get_sender_id_info

from bot.optimized_processor import optimized_processor
from datetime import datetime
from configs import environment
import asyncio

logger = logging.getLogger(__name__)


async def process_message_with_optimized_agent(
    bot_agent,
    sender_id: str,
    page_id: str,
    bot_id: str,
    message: str,
    company_id: Optional[str] = None
) -> BotResponse:
    """
    Process message sử dụng Optimized LangGraph Agent
    
    Args:
        bot_agent: Instance của BotMessengerAgentV2
        sender_id: Facebook sender ID
        page_id: Facebook page ID
        bot_id: Bot ID
        message: User message
        company_id: Company ID
        
    Returns:
        BotResponse
    """
    try:
        # ✅ Store sender_id and main event loop in bot_agent for tools to access
        bot_agent._current_sender_id = sender_id
        bot_agent._main_event_loop = asyncio.get_running_loop()  # Save loop reference for async operations in tools
        
        # 1. Load context song song (giống code hiện tại)
        async def get_bot_info_task():
            if bot_id is None:
                return await bot_agent.preload_bot_info(page_id=page_id)
            else:
                return await bot_agent.preload_bot_info(bot_id=bot_id)
        
        async def get_conversation_history_task():
            return await bot_agent.get_conversation_history(sender_id, page_id, limit=20)
        
        async def get_page_token_task():
            return await bot_agent.get_page_access_token_cached(page_id)
        
        async def get_sender_info_task():
            try:                
                # Check cache
                current_time = asyncio.get_event_loop().time()
                if sender_id in bot_agent.sender_info_cache:
                    cached_data = bot_agent.sender_info_cache[sender_id]
                    if current_time - cached_data['timestamp'] < bot_agent.cache_ttl['sender_info']:
                        return cached_data['info']
                
                token = await bot_agent.get_page_access_token_cached(page_id)
                if token:
                    sender_info = await asyncio.to_thread(get_sender_id_info, sender_id, token)
                    bot_agent.sender_info_cache[sender_id] = {
                        'info': sender_info,
                        'timestamp': current_time
                    }
                    return sender_info
                return None
            except Exception as e:
                logger.error(f"Error getting sender info: {e}")
                return None
        
        # Load tất cả song song
        bot_info, conversation_history, page_access_token, sender_info = await asyncio.gather(
            get_bot_info_task(),
            get_conversation_history_task(),
            get_page_token_task(),
            get_sender_info_task(),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(bot_info, Exception) or not bot_info:
            error_msg = "❌ Không tìm thấy cấu hình bot cho trang này."
            return BotResponse(
                response=error_msg,
                segments=[{"type": "text", "data": error_msg}],
                metadata={"error": "bot_not_found"}
            )
        
        if isinstance(conversation_history, Exception):
            conversation_history = []
        if isinstance(page_access_token, Exception):
            page_access_token = ""
        if isinstance(sender_info, Exception):
            sender_info = None
        
        # Save page token
        bot_agent.page_access_token = page_access_token
        
        # 2. Format history
        current_time = datetime.now(environment.vietnam_tz)
        history_text = bot_agent.format_history_with_smart_window(conversation_history, current_time)
        
        # 3. Extract image context
        image_context = ""
        image_urls = bot_agent.extract_image_urls_from_message(message)
        
        # ✅ Check if we have local image paths for this sender (from webhook download)
        local_image_paths = bot_agent.local_image_paths_cache.get(sender_id, [])
        
        if (image_urls or local_image_paths) and bot_info.get("knowledge_document_ids"):
            document_ids = bot_info["knowledge_document_ids"]
            logger.info(f"🖼️ Found {len(image_urls)} image URLs and {len(local_image_paths)} local paths in message")
            
            # ✅ PRIORITY: Use local paths first (faster, no expiration issues)
            if local_image_paths:
                for local_path in local_image_paths:
                    image_info = await bot_agent.search_image_in_knowledge(
                        local_path=local_path,
                        document_ids=document_ids
                    )
                    if image_info:
                        image_context += f"\n{image_info}\n"
                        logger.info(f"✅ Found image context from local path: {local_path}")
                    else:
                        logger.info(f"❌ No context found for local image: {local_path}")
                
                # ⚠️ DON'T clean up cache yet - tools may need it later!
                # Cache will be cleaned up at the end of message processing
                
            # ⚠️ FALLBACK: Use URLs nếu không có local paths
            elif image_urls:
                for image_url in image_urls:
                    image_info = await bot_agent.search_image_in_knowledge(
                        image_url=image_url,
                        document_ids=document_ids
                    )
                    if image_info:
                        image_context += f"\n{image_info}\n"
                        logger.info(f"✅ Found image context for URL: {image_url[:80]}...")
                    else:
                        logger.info(f"❌ No context found for image URL: {image_url[:80]}...")
        
        # 4. Search Q&A pairs với keyword extraction
        qa_pairs_context = ""
        try:
            bot_dict = bot_info.get("bot", {})
            effective_company_id = company_id or bot_dict.get("company_id")
            
            # ✅ Extract keywords để search tốt hơn
            import re
            search_query = message.lower().strip()
            
            # ✅ NEW: Remove URLs from search query (ảnh URLs làm nhiễu kết quả)
            # Remove any URLs (http/https)
            search_query = re.sub(r'https?://[^\s]+', '', search_query)
            search_query = search_query.strip()
            
            # Remove stop words
            stop_words = {'có', 'không', 'là', 'của', 'thì', 'cho', 'với', 'bán', 'shop', 'em', 'anh', 'chị', 'ạ', 'vậy', 'nhé', 'nha', 'này'}
            words = search_query.split()
            keywords = [w for w in words if w not in stop_words and len(w) > 1]
            search_query = ' '.join(keywords) if keywords else message
            
            logger.info(f"🔍 Searching Q&A pairs with company_id: {effective_company_id}")
            logger.info(f"🔍 Search keywords: '{search_query}' (original: '{message}')")
            
            qa_pairs = await bot_agent.search_qa_pairs(search_query, limit=2, company_id=effective_company_id)
            
            if qa_pairs:
                qa_lines = []
                for idx, qa in enumerate(qa_pairs, 1):
                    question = str(qa.get("content", "") or "").strip()
                    metadata = qa.get("metadata", {}) or {}
                    answer = ""
                    if isinstance(metadata, dict):
                        answer = str(metadata.get("answer", "") or "").strip()
                    entry = f"{idx}. Q: {question}" if question else f"{idx}. Q:"
                    if answer:
                        entry += f"\n   A: {answer}"
                    qa_lines.append(entry)
                qa_pairs_context = "\n".join(qa_lines)
                logger.info(f"✅ Found {len(qa_pairs)} relevant Q&A pairs")
                logger.debug(f"📝 Q&A Context:\n{qa_pairs_context}")
            else:
                logger.info("ℹ️ No relevant Q&A pairs found")
                
        except Exception as e:
            logger.error(f"❌ Error searching Q&A pairs: {e}")
        
        # 5. Prepare tools dictionary
        tools_dict = {}
        all_tools = bot_agent.fb_tools.get_all_tools()
        for tool in all_tools:
            tools_dict[tool.name] = tool.func
        logger.info(f"🔧 Prepared {len(tools_dict)} tools: {list(tools_dict.keys())}")
        
        # 6. Process với optimized agent
        current_time_str = current_time.isoformat()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 Starting optimized agent processing")
        logger.info(f"  - Message: '{message[:50]}...'")
        logger.info(f"  - QA context to pass: {len(qa_pairs_context) if qa_pairs_context else 0} chars")
        logger.info(f"  - QA context preview: {qa_pairs_context[:200] if qa_pairs_context else 'EMPTY'}")
        logger.info(f"{'='*80}\n")
        
        result = await optimized_processor.process_with_graph(
            user_message=message,
            sender_id=sender_id,
            page_id=page_id,
            bot_id=bot_id,
            bot_info=bot_info,
            conversation_history=conversation_history,
            sender_info=sender_info,
            image_context=image_context,
            qa_pairs_context=qa_pairs_context,  # ✅ Thêm Q&A context
            history_text=history_text,
            current_time_str=current_time_str,
            tools_dict=tools_dict,
            company_id=company_id,
            use_cache=True  # Enable caching
        )
        
        logger.info(f"✅ Agent completed - Response: '{result['response']}'...")
        
        # 7. Send message to Facebook Messenger
        segments = result.get("segments", [])
        try:
            import re
            def _has_image_segment(seg_list):
                for s in seg_list:
                    t = s.get("type")
                    if t == "image":
                        return True
                    if t == "images" and isinstance(s.get("data"), list) and s.get("data"):
                        return True
                return False

            def _contains_facility_intent(text: str) -> bool:
                if not text:
                    return False
                txt = text.lower()
                kws_any = [
                    "cơ sở vật chất",
                    "co so vat chat",
                    "khuôn viên",
                    "khuôn viên trường",
                    "khuôn viên của trường",
                    "khuon vien",
                    "khuon vien truong",
                    "hình ảnh",
                    "ảnh",
                    "phòng học",
                    "thư viện",
                    "ký túc",
                    "kí túc",
                    "ky tuc",
                    "phòng thí nghiệm",
                    "phong thi nghiem",
                    "laboratory",
                    "campus"
                ]
                for k in kws_any:
                    if k in txt:
                        return True
                return False

            async def _retrieve_facility_images(limit: int = 3):
                try:
                    user_id = bot_info.get("user_id")
                    company_id_local = company_id or bot_info.get("company_id")
                    km = bot_agent.factory.knowledge_chunk_manager
                    chunks = await km.get_by_chunk_type("image", user_id=user_id, company_id=company_id_local, limit=200)
                    urls = []
                    patterns = [
                        "cơ sở vật chất",
                        "co so vat chat",
                        "khuôn viên",
                        "khuôn viên trường",
                        "khuon vien",
                        "khuon vien truong",
                        "phòng học",
                        "thư viện",
                        "ký túc",
                        "kí túc",
                        "ky tuc",
                        "phòng thí nghiệm",
                        "phong thi nghiem",
                        "laboratory",
                        "campus"
                    ]
                    for ch in chunks:
                        content = str(ch.get("content", ""))
                        score = 0
                        lc = content.lower()
                        for p in patterns:
                            if p in lc:
                                score += 1
                        if score == 0:
                            continue
                        found = re.findall(r"<image:([^>]+)>", content)
                        for u in found:
                            if u not in urls:
                                urls.append(u)
                                if len(urls) >= limit:
                                    return urls
                    return urls[:limit]
                except Exception:
                    return []

            async def _retrieve_facility_images_from_documents(limit: int = 3):
                try:
                    user_id = bot_info.get("user_id")
                    company_id_local = company_id or bot_info.get("company_id")
                    dm = bot_agent.factory.document_manager
                    docs = await dm.get_by_user_id(user_id=user_id, company_id=company_id_local)
                    urls = []
                    patterns = [
                        "cơ sở vật chất",
                        "co so vat chat",
                        "khuôn viên",
                        "khuôn viên trường",
                        "khuon vien",
                        "khuon vien truong",
                        "phòng học",
                        "thư viện",
                        "ký túc",
                        "kí túc",
                        "ky tuc",
                        "phòng thí nghiệm",
                        "phong thi nghiem",
                        "laboratory",
                        "campus"
                    ]
                    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
                    for d in docs:
                        ft = str(d.get("file_type", "")).lower()
                        if ft not in image_exts:
                            continue
                        name_text = " ".join([
                            str(d.get("file_name", "")),
                            str(d.get("document_name", "")),
                            str(d.get("title", ""))
                        ]).lower()
                        score = 0
                        for p in patterns:
                            if p in name_text:
                                score += 1
                        if score == 0:
                            continue
                        u = d.get("storage_url")
                        if u and u not in urls:
                            urls.append(u)
                            if len(urls) >= limit:
                                return urls
                    if urls:
                        return urls[:limit]
                    for d in docs:
                        ft = str(d.get("file_type", "")).lower()
                        if ft in image_exts:
                            u = d.get("storage_url")
                            if u and u not in urls:
                                urls.append(u)
                                if len(urls) >= limit:
                                    return urls
                    return urls[:limit]
                except Exception:
                    return []

            need_images = False
            if not _has_image_segment(segments):
                if _contains_facility_intent(message) or _contains_facility_intent(result.get("response", "")):
                    need_images = True
            if need_images:
                default_imgs = []
                try:
                    bot_obj = bot_info.get("bot", {}) if isinstance(bot_info, dict) else {}
                    v = bot_obj.get("default_facility_images")
                    if isinstance(v, list):
                        default_imgs = [u for u in v if isinstance(u, str) and u]
                except Exception:
                    default_imgs = []

                image_urls = default_imgs[:4] if default_imgs else await _retrieve_facility_images_from_documents(limit=4)
                if not image_urls:
                    image_urls = await _retrieve_facility_images(limit=4)
                if image_urls:
                    segments.append({"type": "images", "data": image_urls})
        except Exception:
            pass
        
        if segments:
            try:
                logger.info(f"📤 Sending {len(segments)} segments to Facebook Messenger...")
                await send_facebook_messenger(page_id, sender_id, segments)
                logger.info(f"✅ Message sent to Facebook successfully")
            except Exception as e:
                logger.error(f"❌ Failed to send message to Facebook: {e}", exc_info=True)
        else:
            logger.warning("⚠️ No segments to send to Facebook")
        
        # 8. Save conversation
        await bot_agent.save_conversation_message(
            sender_id=sender_id,
            page_id=page_id,
            user_message=message,
            bot_response=result["response"],
            bot_id=bot_id,
            response_segments=result.get("segments"),
            sender_info=sender_info,
            company_id=company_id
        )
        
        # 9. Log performance
        performance = result.get("performance", {})
        logger.info(f"📊 Performance: {performance.get('processing_time', 0):.2f}s | "
                   f"Cache hit rate: {performance.get('cache_stats', {}).get('hit_rate', 0):.2%}")
        
        # 10. ✅ Clean up image cache after all processing complete
        if sender_id in bot_agent.local_image_paths_cache:
            bot_agent.local_image_paths_cache.pop(sender_id, None)
            logger.info(f"🧹 Cleaned up image cache for sender {sender_id}")
        
        return BotResponse(
            response=result["response"],
            segments=result.get("segments", []),
            metadata={
                **result.get("metadata", {}),
                "performance": performance
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in optimized agent processing: {e}")
        
        # ✅ Clean up cache even on error
        if sender_id in bot_agent.local_image_paths_cache:
            bot_agent.local_image_paths_cache.pop(sender_id, None)
        
        # Fallback to original processing
        logger.info("⚠️ Falling back to original processing...")
        return await bot_agent.process_message_immediate(
            sender_id=sender_id,
            page_id=page_id,
            bot_id=bot_id,
            message=message,
            send_facebook=False,
            company_id=company_id
        )
