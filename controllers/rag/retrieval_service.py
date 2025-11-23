"""
Enhanced RAG Retrieval Service với MongoDB Vector Search
Service tối ưu cho việc tìm kiếm thông tin từ knowledge chunks với MongoDB native vector search
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

# Import configurations 
from configs.environment import get_embedding, get_query_embedding
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.data.managements.knowledge_management import KnowledgeChunkManager

logger = logging.getLogger(__name__)

from pymongo import MongoClient
from configs.constant import MONGODB_URI, MONGODB_DATABASE
            
class RAGRetrievalService:
    """
    Enhanced RAG Retrieval Service với MongoDB Vector Search
    - Sử dụng MongoDB native vector search với aggregation pipeline
    - Tìm kiếm trong knowledge_chunks theo document_ids
    - Hỗ trợ hybrid search (semantic + keyword) native trong MongoDB
    - Tối ưu performance với MongoDB indexing
    """
    
    def __init__(self, db_manager: MongoDBManager):
        """
        Initialize RAG Retrieval Service
        
        Args:
            db_manager: MongoDB manager instance
        """
        self.db_manager = db_manager
        self.knowledge_chunk_manager = KnowledgeChunkManager(db_manager)
        
        # Cache cho embeddings
        self.query_cache = {}
        
        logger.info("🚀 RAG Retrieval Service initialized với MongoDB Vector Search")
    
    async def search_relevant_chunks(
        self,
        query: str,
        document_ids: Optional[List[str]],
        user_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.5,  # Giảm threshold để capture được results
        use_hybrid: bool = True,
        chunk_types: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        company_id: Optional[str] = None,
        metadata_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm chunks liên quan với MongoDB vector search
        
        Args:
            query: Câu hỏi/query để tìm kiếm
            document_ids: Danh sách document IDs để tìm kiếm
            user_id: User ID
            limit: Số lượng chunks tối đa
            similarity_threshold: Ngưỡng similarity tối thiểu
            use_hybrid: Có sử dụng hybrid search không
            metadata_tags: Danh sách tags trong metadata.tags để lọc kết quả (phải bao gồm toàn bộ tags yêu cầu)
            
        Returns:
            List of relevant chunks với similarity scores
        """
        try:
            # 1. Tạo embedding cho query
            query_embedding = await self._get_query_embedding(query)
            
            # 2. Build filter query cho documents, chunk types và user
            filter_query: Dict[str, Any] = {"user_id": user_id}

            if document_ids:
                filter_query["source_info.source_id"] = {"$in": document_ids}

            if chunk_types:
                if len(chunk_types) == 1:
                    filter_query["chunk_type"] = chunk_types[0]
                else:
                    filter_query["chunk_type"] = {"$in": chunk_types}

            if source_types:
                if len(source_types) == 1:
                    filter_query["source_info.type"] = source_types[0]
                else:
                    filter_query["source_info.type"] = {"$in": source_types}

            if company_id:
                filter_query["company_id"] = company_id

            if metadata_tags:
                filter_query["metadata.tags"] = {"$all": metadata_tags}
            
            # 3. Sử dụng MongoDB vector search hoặc hybrid search
            if use_hybrid:
                results = await self.db_manager.hybrid_search(
                    collection_name="knowledge_chunks",
                    query_text=query,
                    query_vector=query_embedding,
                    text_fields=["content"],
                    vector_field="content_embedding",
                    filter_query=filter_query,
                    limit=limit,
                    semantic_weight=0.5,
                    keyword_weight=0.3,
                    similarity_threshold=similarity_threshold
                )
            else:
                results = await self.db_manager.vector_search(
                    collection_name="knowledge_chunks",
                    query_vector=query_embedding,
                    vector_field="content_embedding",
                    filter_query=filter_query,
                    limit=limit,
                    similarity_threshold=similarity_threshold
                )
            
            logger.info(f"✅ Found {len(results)} relevant chunks for query: '{query}'")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in search_relevant_chunks: {str(e)}")
            return []
    
    async def _get_query_embedding(self, query: str) -> List[float]:
        """Tạo embedding cho query với cache"""
        try:
            # Kiểm tra cache
            cache_key = f"query_{hash(query)}"
            if cache_key in self.query_cache:
                return self.query_cache[cache_key]
            
            # Tạo embedding bằng function từ environment
            query_embedding = get_query_embedding(query)
            
            # Cache kết quả (giới hạn cache size)
            if len(self.query_cache) > 100:
                # Xóa cache cũ nhất
                oldest_key = next(iter(self.query_cache))
                del self.query_cache[oldest_key]
            
            self.query_cache[cache_key] = query_embedding
            
            return query_embedding
            
        except Exception as e:
            logger.error(f"❌ Error creating query embedding: {str(e)}")
            raise
    
    async def search_with_context(
        self,
        query: str,
        document_ids: List[str],
        user_id: str,
        context_window: int = 2,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Tìm kiếm với context window (lấy thêm chunks xung quanh)
        
        Args:
            query: Query string
            document_ids: Document IDs
            user_id: User ID
            context_window: Số chunks xung quanh để lấy thêm
            limit: Limit kết quả
            metadata_tags: Danh sách tags trong metadata.tags để lọc kết quả
            
        Returns:
            Dict with chunks và context information
        """
        try:
            # 1. Tìm kiếm chunks chính
            main_chunks = await self.search_relevant_chunks(
                query=query,
                document_ids=document_ids,
                user_id=user_id,
                limit=limit
            )
            
            if not main_chunks:
                return {
                    'chunks': [],
                    'context_chunks': [],
                    'total_found': 0
                }
            
            # 2. Lấy context chunks xung quanh
            context_chunks = []
            for chunk in main_chunks:
                try:
                    chunk_position = chunk.get('chunk_index', 0)
                    source_id = chunk.get('source_info', {}).get('source_id') or chunk.get('source_id')
                    
                    if source_id:
                        # Lấy chunks xung quanh
                        nearby_chunks = await self._get_nearby_chunks(
                            source_id=source_id,
                            user_id=user_id,
                            center_position=chunk_position,
                            window=context_window
                        )
                        context_chunks.extend(nearby_chunks)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error getting context for chunk {chunk.get('_id')}: {str(e)}")
                    continue
            
            # 3. Deduplicate context chunks
            seen_ids = {str(chunk['_id']) for chunk in main_chunks}
            unique_context = [
                chunk for chunk in context_chunks 
                if str(chunk['_id']) not in seen_ids
            ]
            
            result = {
                'chunks': main_chunks,
                'context_chunks': unique_context,
                'total_found': len(main_chunks),
                'context_found': len(unique_context)
            }
            
            logger.info(f"🔍 Search with context: {len(main_chunks)} main + {len(unique_context)} context chunks")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in search_with_context: {str(e)}")
            return {'chunks': [], 'context_chunks': [], 'total_found': 0}
    
    async def _get_nearby_chunks(
        self,
        source_id: str,
        user_id: str,
        center_position: int,
        window: int
    ) -> List[Dict[str, Any]]:
        """Lấy chunks xung quanh vị trí center_position"""
        try:
            # Tính range cần lấy
            start_pos = max(0, center_position - window)
            end_pos = center_position + window + 1
            
            # Build filter query
            filter_query = {
                "source_info.source_id": source_id,
                "user_id": user_id,
                "chunk_index": {"$gte": start_pos, "$lte": end_pos}
            }
            
            # Sử dụng MongoDB find để lấy nearby chunks
            nearby_chunks = await self.db_manager.find(
                collection_name="knowledge_chunks",
                filter_query=filter_query,
                sort=[("chunk_index", 1)]
            )
            
            return nearby_chunks
            
        except Exception as e:
            logger.error(f"❌ Error getting nearby chunks: {str(e)}")
            return []

    def _get_nearby_chunks_sync(
        self,
        collection,
        source_id: str,
        user_id: str,
        center_position: int,
        window: int,
        extra_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Lay chunks xung quanh vi tri center_position o che do sync"""
        try:
            start_pos = max(0, center_position - window)
            end_pos = center_position + window + 1

            filter_query: Dict[str, Any] = {
                "source_info.source_id": source_id,
                "user_id": user_id,
                "chunk_index": {"$gte": start_pos, "$lte": end_pos}
            }

            if extra_filters:
                filter_query.update(extra_filters)

            nearby_chunks = list(collection.find(filter_query).sort("chunk_index", 1))

            for chunk in nearby_chunks:
                if "_id" in chunk:
                    chunk["_id"] = str(chunk["_id"])

            return nearby_chunks

        except Exception as e:
            logger.error(f"[sync] Error getting nearby chunks for source {source_id}: {str(e)}")
            return []
    
    def clear_cache(self):
        """Xóa cache"""
        self.query_cache.clear()
        logger.info("🧹 Cleared embedding cache")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê của service"""
        try:
            return {
                'query_cache_size': len(self.query_cache),
                'search_method': 'MongoDB Vector Search',
                'status': 'active'
            }
        except Exception as e:
            logger.error(f"❌ Error getting stats: {str(e)}")
            return {'status': 'error', 'error': str(e)}
    
    # Sync wrapper methods để tránh async conflicts trong tools
    def search_relevant_chunks_sync(
        self,
        query: str,
        document_ids: Optional[List[str]],
        user_id: str,
        limit: int = 10,
        similarity_threshold: float = 0.35,  # Threshold cân bằng giữa chất lượng và coverage
        use_hybrid: bool = True,
        chunk_types: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        company_id: Optional[str] = None,
        metadata_tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Sync wrapper cho search_relevant_chunks sử dụng MongoDB vector search"""
        client = None
        try:
            # 1. Tạo kết nối MongoDB cục bộ
            client = MongoClient(MONGODB_URI)
            db = client[MONGODB_DATABASE]
            collection = db["knowledge_chunks"]
            
            # 2. Tạo embedding cho query (sync)
            query_embedding = get_query_embedding(query)
            
            # 3. Build filter query cho documents và user
            filter_query: Dict[str, Any] = {"user_id": user_id}

            if document_ids:
                filter_query["source_info.source_id"] = {"$in": document_ids}

            if chunk_types:
                filter_query["chunk_type"] = chunk_types[0] if len(chunk_types) == 1 else {"$in": chunk_types}

            if source_types:
                filter_query["source_info.type"] = source_types[0] if len(source_types) == 1 else {"$in": source_types}

            if company_id:
                filter_query["company_id"] = company_id
            
            # Build aggregation pipeline
            if use_hybrid:
                # Hybrid search pipeline
                query_words = query.lower().split()
                
                pipeline = [
                    {"$match": filter_query},
                    {"$match": {"content_embedding": {"$exists": True, "$ne": None}}},
                    {
                        "$addFields": {
                            # Semantic similarity score
                            "semantic_score": {
                                "$let": {
                                    "vars": {
                                        "dotProduct": {
                                            "$reduce": {
                                                "input": {"$range": [0, {"$size": "$content_embedding"}]},
                                                "initialValue": 0,
                                                "in": {
                                                    "$add": [
                                                        "$$value",
                                                        {"$multiply": [
                                                            {"$arrayElemAt": ["$content_embedding", "$$this"]},
                                                            {"$arrayElemAt": [query_embedding, "$$this"]}
                                                        ]}
                                                    ]
                                                }
                                            }
                                        },
                                        "normA": {
                                            "$sqrt": {
                                                "$reduce": {
                                                    "input": "$content_embedding",
                                                    "initialValue": 0,
                                                    "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                                }
                                            }
                                        },
                                        "normB": {
                                            "$literal": (sum(x * x for x in query_embedding) ** 0.5)
                                        }
                                    },
                                    "in": {
                                        "$cond": {
                                            "if": {"$and": [{"$gt": ["$$normA", 0]}, {"$gt": ["$$normB", 0]}]},
                                            "then": {"$divide": ["$$dotProduct", {"$multiply": ["$$normA", "$$normB"]}]},
                                            "else": 0
                                        }
                                    }
                                }
                            },
                            
                            # Keyword matching score
                            "keyword_score": {
                                "$let": {
                                    "vars": {
                                        "textContent": {"$toLower": {"$ifNull": ["$content", ""]}}
                                    },
                                    "in": {
                                        "$divide": [
                                            {
                                                "$size": {
                                                    "$filter": {
                                                        "input": query_words,
                                                        "cond": {
                                                            "$regexMatch": {
                                                                "input": "$$textContent",
                                                                "regex": {"$concat": [".*", "$$this", ".*"]},
                                                                "options": "i"
                                                            }
                                                        }
                                                    }
                                                }
                                            },
                                            len(query_words) if query_words else 1
                                        ]
                                    }
                                }
                            }
                        }
                    },
                    {
                        "$addFields": {
                            "final_score": {
                                "$add": [
                                    {"$multiply": ["$semantic_score", 0.5]},
                                    {"$multiply": ["$keyword_score", 0.3]}
                                ]
                            }
                        }
                    },
                    {"$match": {"semantic_score": {"$gte": similarity_threshold}}},
                    {"$sort": {"final_score": -1}},
                    {"$limit": limit}
                ]
            else:
                # Vector search only pipeline
                pipeline = [
                    {"$match": filter_query},
                    {"$match": {"content_embedding": {"$exists": True, "$ne": None}}},
                    {
                        "$addFields": {
                            "similarity_score": {
                                "$let": {
                                    "vars": {
                                        "dotProduct": {
                                            "$reduce": {
                                                "input": {"$range": [0, {"$size": "$content_embedding"}]},
                                                "initialValue": 0,
                                                "in": {
                                                    "$add": [
                                                        "$$value",
                                                        {"$multiply": [
                                                            {"$arrayElemAt": ["$content_embedding", "$$this"]},
                                                            {"$arrayElemAt": [query_embedding, "$$this"]}
                                                        ]}
                                                    ]
                                                }
                                            }
                                        },
                                        "normA": {
                                            "$sqrt": {
                                                "$reduce": {
                                                    "input": "$content_embedding",
                                                    "initialValue": 0,
                                                    "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                                }
                                            }
                                        },
                                        "normB": {
                                            "$literal": (sum(x * x for x in query_embedding) ** 0.5)
                                        }
                                    },
                                    "in": {
                                        "$cond": {
                                            "if": {"$and": [{"$gt": ["$$normA", 0]}, {"$gt": ["$$normB", 0]}]},
                                            "then": {"$divide": ["$$dotProduct", {"$multiply": ["$$normA", "$$normB"]}]},
                                            "else": 0
                                        }
                                    }
                                }
                            }
                        }
                    },
                    {"$match": {"similarity_score": {"$gte": similarity_threshold}}},
                    {"$sort": {"similarity_score": -1}},
                    {"$limit": limit}
                ]
            
            # 4. Execute aggregation
            results = list(collection.aggregate(pipeline))
            
            # 5. Convert ObjectIds to strings
            for result in results:
                if '_id' in result:
                    result['_id'] = str(result['_id'])
            
            logger.info(f"✅ Found {len(results)} relevant chunks for query: '{query}'")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in search_relevant_chunks_sync: {str(e)}")
            return []
        finally:
            # 6. Đảm bảo đóng kết nối
            if client:
                try:
                    client.close()
                except:
                    pass
    
    def search_with_context_sync(
        self,
        query: str,
        document_ids: Optional[List[str]],
        user_id: str,
        context_window: int = 2,
        limit: int = 10,
        chunk_types: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        company_id: Optional[str] = None,
        metadata_tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Sync wrapper cho search_with_context"""
        client = None
        try:
            # 1. Tìm kiếm chunks chính
            main_chunks = self.search_relevant_chunks_sync(
                query=query,
                document_ids=document_ids,
                user_id=user_id,
                limit=limit,
                chunk_types=chunk_types,
                source_types=source_types,
                company_id=company_id,
                metadata_tags=metadata_tags
            )
            
            if not main_chunks:
                return {
                    'chunks': [],
                    'context_chunks': [],
                    'total_found': 0
                }
            
            # 2. Chuẩn bị bộ lọc bổ sung cho context chunks
            extra_filters: Dict[str, Any] = {}
            if chunk_types:
                extra_filters["chunk_type"] = chunk_types[0] if len(chunk_types) == 1 else {"$in": chunk_types}
            if source_types:
                extra_filters["source_info.type"] = source_types[0] if len(source_types) == 1 else {"$in": source_types}
            if company_id:
                extra_filters["company_id"] = company_id
            if metadata_tags:
                extra_filters["metadata.tags"] = {"$all": metadata_tags}

            # 3. Mở kết nối MongoDB để lấy context chunks
            client = MongoClient(MONGODB_URI)
            collection = client[MONGODB_DATABASE]["knowledge_chunks"]

            context_chunks: List[Dict[str, Any]] = []
            for chunk in main_chunks:
                try:
                    chunk_position = chunk.get('chunk_index', 0)
                    source_info = chunk.get('source_info') or {}
                    source_id = source_info.get('source_id') or chunk.get('source_id')

                    if not source_id:
                        continue

                    nearby = self._get_nearby_chunks_sync(
                        collection=collection,
                        source_id=source_id,
                        user_id=user_id,
                        center_position=chunk_position,
                        window=context_window,
                        extra_filters=extra_filters
                    )
                    context_chunks.extend(nearby)
                except Exception as context_error:
                    logger.warning(f"[sync] Error getting context for chunk {chunk.get('_id')}: {str(context_error)}")
                    continue

            # 4. Loại bỏ trùng lặp và các chunk chính khỏi context
            seen_main_ids = {str(chunk['_id']) for chunk in main_chunks if '_id' in chunk}
            unique_context: List[Dict[str, Any]] = []
            seen_context_ids = set()

            for context_chunk in context_chunks:
                chunk_id = str(context_chunk.get('_id'))
                if chunk_id in seen_main_ids or chunk_id in seen_context_ids:
                    continue

                seen_context_ids.add(chunk_id)
                context_chunk['_id'] = chunk_id
                unique_context.append(context_chunk)

            result = {
                'chunks': main_chunks,
                'context_chunks': unique_context,
                'total_found': len(main_chunks),
                'context_found': len(unique_context)
            }
            
            logger.info(f"[sync] Search with context: {len(main_chunks)} main + {len(unique_context)} context chunks")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in search_with_context_sync: {str(e)}")
            return {'chunks': [], 'context_chunks': [], 'total_found': 0}
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass
