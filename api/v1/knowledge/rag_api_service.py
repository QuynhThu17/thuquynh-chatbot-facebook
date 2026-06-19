"""
Enhanced RAG API Service
Service wrapper để tích hợp Enhanced RAG System vào API endpoints
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import os
from io import BytesIO

# Import Enhanced RAG Components
from controllers.rag.load_documents import (
    RAGService
)
from controllers.rag.load_documents.services.document_loader_service import DocumentLoaderService

# Import existing managers
from controllers.data.managements.knowledge_management import KnowledgeChunkManager, DocumentManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

class RAGAPIService:
    """
    Service để tích hợp Enhanced RAG System vào API
    """
    
    def __init__(self, db_manager: MongoDBManager):
        """
        Initialize service
        
        Args:
            db_manager: MongoDB manager instance
        """
        self.db_manager = db_manager
        self.knowledge_manager = KnowledgeChunkManager(db_manager)
        self.document_manager = DocumentManager(db_manager)
        
        # Initialize Enhanced RAG Service
        self.rag_service = RAGService(
            knowledge_manager=self.knowledge_manager,
            document_manager=self.document_manager,
            db_manager=db_manager
        )
        
        logger.info("Enhanced RAG API Service initialized")
    
    async def process_document_upload(self, 
                                    file_data: bytes,
                                    file_name: str,
                                    user_id: str,
                                    company_id: Optional[str] = None,
                                    chunk_strategy: str = "adaptive",
                                    embedding_strategy: str = "contextual",
                                    chunk_size: int = 1000,
                                    overlap: int = 0,
                                    tags: Optional[List[str]] = None,
                                    metadata: Optional[Dict[str, Any]] = None,
                                    document_name: str = "",
                                    process_images: bool = False,
                                    parser_engine: str = "ragflow") -> Dict[str, Any]:
        """
        Process document upload using RAG System with RAGFlow parser

        Args:
            file_data: File data bytes
            file_name: Original file name
            user_id: User ID
            company_id: Company ID (optional)
            chunk_strategy: Chunking strategy (semantic, recursive, hierarchical, adaptive)
            embedding_strategy: Embedding strategy (contextual, multi_level)
            chunk_size: Chunk size
            overlap: Chunk overlap
            tags: Document tags
            metadata: Additional metadata
            document_name: Document name
            process_images: Whether to process images in document (default: False)
            parser_engine: Parser engine to use (ragflow=default, legacy=old)
            
        Returns:
            Dict with processing results
        """
        try:
            # Prepare metadata
            doc_metadata = {
                "user_id": user_id,
                "company_id": company_id,
                "file_name": file_name,
                "upload_time": datetime.now().isoformat(),
                "tags": tags or [],
                "processing_strategy": {
                    "chunker": chunk_strategy,
                    "embedder": embedding_strategy,
                    "chunk_size": chunk_size,
                    "overlap": overlap
                },
                **(metadata or {})
            }
            
            # Get file extension
            file_extension = os.path.splitext(file_name)[1].lower()
            
            # Prepare processing options for Enhanced RAG
            # Force specific chunking parameters
            processing_options = {
                "metadata": doc_metadata,
                "chunker_strategy": "semantic",  # Always use semantic chunking
                "embedder_strategy": embedding_strategy,
                "chunk_size": 256,  # Fixed chunk size
                "overlap": 0,  # No overlap
                "file_type": file_extension,
                "user_id": user_id,
                "company_id": company_id,
                "process_images": process_images,  # Control image processing
                "parser_engine": parser_engine  # RAGFlow or legacy
            }
            
            if not document_name:
                document_name = file_name
            
            # Process document using Enhanced RAG Service
            result = await self.rag_service.process_document(
                file_data=file_data,
                file_name=file_name,
                user_id=user_id,
                company_id=company_id,
                processing_options=processing_options,
                document_name=document_name
            )
            
            # Prepare response
            response = {
                "success": True,
                "document_name": document_name,
                "document_id": result.get("document_id"),
                "file_name": file_name,
                "file_type": file_extension,
                "processing_stats": {
                    "total_chunks": result.get("total_chunks", 0),
                    "total_embeddings": result.get("total_embeddings", 0),
                    "processing_time": result.get("processing_time", 0),
                    "chunk_strategy": chunk_strategy,
                    "embedding_strategy": embedding_strategy
                },
                "chunk_details": result.get("chunk_details", []),
                "quality_metrics": result.get("quality_metrics", {}),
                "metadata": doc_metadata
            }
            
            logger.info(f"Successfully processed document {file_name} for user {user_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error processing document {file_name}: {str(e)}")
            raise
    
    async def search_knowledge(self,
                             query: str,
                             user_id: str,
                             company_id: Optional[str] = None,
                             top_k: int = 3,
                             similarity_threshold: float = 0.7,
                             filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Search knowledge base using Enhanced RAG
        
        Args:
            query: Search query
            user_id: User ID
            company_id: Company ID (optional)
            top_k: Number of results to return
            similarity_threshold: Minimum similarity threshold
            filters: Additional filters
            
        Returns:
            Search results
        """
        try:
            # Prepare search context
            search_context = {
                "user_id": user_id,
                "company_id": company_id,
                "filters": filters or {},
                "search_time": datetime.now().isoformat()
            }
            
            # Perform enhanced search
            results = await self.rag_service.search_knowledge(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                context=search_context
            )
            
            return {
                "success": True,
                "query": query,
                "results": results.get("chunks", []),
                "search_stats": {
                    "total_found": len(results.get("chunks", [])),
                    "search_time": results.get("search_time", 0),
                    "similarity_scores": results.get("similarity_scores", [])
                },
                "context": search_context
            }
            
        except Exception as e:
            logger.error(f"Error searching knowledge for query '{query}': {str(e)}")
            raise
    
    async def generate_answer(self,
                            question: str,
                            user_id: str,
                            company_id: Optional[str] = None,
                            max_context_chunks: int = 5,
                            include_sources: bool = True) -> Dict[str, Any]:
        """
        Generate answer using Enhanced RAG
        
        Args:
            question: User question
            user_id: User ID  
            company_id: Company ID (optional)
            max_context_chunks: Maximum context chunks
            include_sources: Include source information
            
        Returns:
            Generated answer with sources
        """
        try:
            # Generate answer using Enhanced RAG
            result = await self.rag_service.generate_answer(
                question=question,
                user_id=user_id,
                company_id=company_id,
                max_context_chunks=max_context_chunks,
                include_sources=include_sources
            )
            
            return {
                "success": True,
                "question": question,
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "confidence_score": result.get("confidence_score", 0.0),
                "generation_stats": {
                    "context_chunks_used": len(result.get("sources", [])),
                    "generation_time": result.get("generation_time", 0),
                    "tokens_used": result.get("tokens_used", 0)
                },
                "metadata": {
                    "user_id": user_id,
                    "company_id": company_id,
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating answer for question '{question}': {str(e)}")
            raise
    
    def get_supported_strategies(self) -> Dict[str, Any]:
        """
        Get supported chunking and embedding strategies
        
        Returns:
            Dict with supported strategies and their descriptions
        """
        # Xác định động loại tệp hỗ trợ dựa trên tình trạng RAGFlow
        try:
            loader = DocumentLoaderService(self.db_manager)
            ragflow_available = bool(getattr(loader, "use_ragflow", False))
        except Exception:
            ragflow_available = False

        simple_types = [".txt", ".md"]
        if ragflow_available:
            # Chỉ thêm .csv khi RAGFlow khả dụng để tránh lỗi 500 từ legacy processors
            simple_types.append(".csv")

        return {
            "chunking_strategies": {
                "semantic": {
                    "name": "Semantic Chunking",
                    "description": "Chia chunks dựa trên semantic similarity",
                    "best_for": ["Text documents", "Articles", "Books"],
                    "parameters": ["chunk_size", "overlap", "similarity_threshold"]
                },
                "recursive": {
                    "name": "Recursive Character Text Splitter", 
                    "description": "Chia chunks theo cấu trúc văn bản",
                    "best_for": ["Structured documents", "Code", "Technical docs"],
                    "parameters": ["chunk_size", "overlap", "separators"]
                },
                "hierarchical": {
                    "name": "Hierarchical Chunking",
                    "description": "Chia chunks theo hierarchy (document → section → paragraph)",
                    "best_for": ["Long documents", "Academic papers", "Reports"],
                    "parameters": ["chunk_size", "overlap", "levels"]
                },
                "adaptive": {
                    "name": "Adaptive Chunking", 
                    "description": "Tự động chọn strategy tối ưu dựa trên document type",
                    "best_for": ["Mixed document types", "General purpose"],
                    "parameters": ["chunk_size", "overlap"]
                }
            },
            "embedding_strategies": {
                "contextual": {
                    "name": "Contextual Embeddings",
                    "description": "Embeddings có context awareness",
                    "best_for": ["General purpose", "Mixed content"],
                    "models": ["Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-0.6B"]
                },
                "multi_level": {
                    "name": "Multi-Level Embeddings",
                    "description": "Embeddings ở nhiều levels (sentence, paragraph, document)",
                    "best_for": ["Complex documents", "Hierarchical search"],
                    "models": ["Qwen/Qwen3-Embedding-0.6B", "Qwen/Qwen3-Embedding-0.6B"]
                }
            },
            "supported_file_types": {
                "advanced": [
                    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
                    ".pptx", ".html", ".htm",
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"
                ],
                "simple": simple_types
            }
        }
