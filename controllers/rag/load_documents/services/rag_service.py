"""
Enhanced RAG Service
Service tích hợp tất cả components để tạo hệ thống RAG hoàn thiện
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
import time
import sys
from pathlib import Path

# Add project directories to path
current_dir = Path(__file__).parent
load_documents_dir = current_dir.parent
project_root = load_documents_dir.parents[2]  # Go up to project root
sys.path.append(str(load_documents_dir))
sys.path.append(str(project_root))

from chunkers import ChunkerFactory, ChunkResult
from embedders import EmbedderFactory, EmbeddingResult
from processors import BaseDocumentProcessor, PDFProcessor, DocProcessor, ExcelProcessor
from storage import S3Service
from services.document_loader_service import DocumentLoaderService

# Import existing managers
from controllers.data.managements.knowledge_management import KnowledgeChunkManager, DocumentManager
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)

class RAGService:
    """
    Enhanced RAG Service tích hợp tất cả advanced features:
    - Multi-strategy chunking (semantic, hierarchical, adaptive)
    - Context-aware embeddings 
    - Multi-level embeddings
    - Intelligent document processing
    - Optimized storage and retrieval
    """
    
    def __init__(self, db_manager: MongoDBManager,
                 chunker_strategy: str = "semantic",
                 embedder_strategy: str = "contextual",
                 **kwargs):
        """
        Initialize Enhanced RAG Service
        
        Args:
            db_manager: MongoDB manager
            chunker_strategy: Chunking strategy (adaptive, semantic, hierarchical, recursive)
            embedder_strategy: Embedding strategy (contextual, multi_level, hybrid)
            **kwargs: Additional configuration
        """
        self.db_manager = db_manager
        self.chunker_strategy = chunker_strategy
        self.embedder_strategy = embedder_strategy
        self.config = kwargs
        
        # Initialize managers
        self.knowledge_chunk_manager = KnowledgeChunkManager(db_manager)
        self.document_manager = DocumentManager(db_manager)
        
        # Initialize storage
        self.s3_service = S3Service()
        
        # Initialize processors
        self.processors = {
            '.pdf': PDFProcessor(),
            '.docx': DocProcessor(),
            '.doc': DocProcessor(), 
            '.xlsx': ExcelProcessor(),
            '.xls': ExcelProcessor()
        }
        
        # Initialize factories
        self.chunker_factory = ChunkerFactory()
        self.embedder_factory = EmbedderFactory()
        
        # Initialize components (lazy loading)
        self.chunker = None
        self.embedder = None
        
        logger.info(f"Enhanced RAG Service initialized with chunker={chunker_strategy}, embedder={embedder_strategy}")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            # Initialize chunker with fixed parameters
            self.chunker = self.chunker_factory.create_chunker(
                strategy="semantic",  # Always use semantic chunking
                chunk_size=256,  # Fixed chunk size
                overlap=0,  # No overlap
                **self.config
            )
            
            # Initialize embedder
            self.embedder = self.embedder_factory.create_embedder(
                strategy=self.embedder_strategy,
                model_name=self.config.get('model_name', 'Qwen/Qwen3-Embedding-0.6B'),
                **self.config
            )
            
            # Initialize embedder model
            await self.embedder.initialize()
            
            # Warm up embedder
            await self.embedder.warm_up()
            
            logger.info("Enhanced RAG Service initialization completed")
            
        except Exception as e:
            logger.error(f"Error initializing Enhanced RAG Service: {str(e)}")
            raise

    async def process_document(self, file_data: bytes,  file_name: str, user_id: str, company_id: str = None, processing_options: Optional[Dict[str, Any]] = None, document_name: str = "") -> Dict[str, Any]:
        """
        Process document với RAG capabilities - delegates to new page-aware system
        
        Args:
            file_data: Document data
            file_name: File name
            user_id: User ID
            company_id: Company ID
            processing_options: Processing options
            
        Returns:
            Dict: Processing results với detailed metrics
        """
        try:
            # Initialize document loader service if not available
            if not hasattr(self, 'document_loader_service'):
                self.document_loader_service = DocumentLoaderService(self.db_manager)
            
            # Delegate to the new page-aware document processing system
            result = await self.document_loader_service.process_document(
                file_data=file_data,
                file_name=file_name,
                user_id=user_id,
                company_id=company_id,
                processing_options=processing_options,
                document_name=document_name
            )
            
            logger.info(f"Document processed successfully via page-aware system: {file_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced document processing {file_name}: {str(e)}")
            raise
    
    async def _analyze_document(self, file_data: bytes, file_name: str, 
                               options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze document để optimize processing strategy
        
        Args:
            file_data: File data
            file_name: File name
            options: Processing options
            
        Returns:
            Dict: Analysis results
        """
        import os
        
        file_extension = os.path.splitext(file_name)[1].lower()
        file_size = len(file_data)
        
        analysis = {
            'file_name': file_name,
            'file_extension': file_extension,
            'file_size': file_size,
            'file_type': None,
            'complexity_score': 0.5,
            'estimated_pages': 1,
            'has_images': False,
            'has_tables': False,
            'language': 'auto',
            'recommended_chunker': None,
            'recommended_embedder': None
        }
        
        # Determine file type
        if file_extension in ['.pdf']:
            analysis['file_type'] = 'pdf'
            analysis['estimated_pages'] = max(1, file_size // 50000)  # Rough estimate
        elif file_extension in ['.docx', '.doc']:
            analysis['file_type'] = 'word'
            analysis['estimated_pages'] = max(1, file_size // 30000)
        elif file_extension in ['.xlsx', '.xls']:
            analysis['file_type'] = 'excel'
            analysis['has_tables'] = True
        
        # Quick content analysis if processor available
        try:
            processor = self.processors.get(file_extension)
            if processor:
                # Quick peek at content for analysis
                peek_content = await processor.extract_content(file_name, file_data)
                
                if peek_content:
                    analysis['has_images'] = len(peek_content.total_images) > 0
                    
                    # Analyze text complexity
                    text = peek_content.total_text_content[:5000]  # First 5000 chars
                    analysis['complexity_score'] = self._calculate_complexity_score(text)
                    analysis['language'] = self._detect_language(text)
                    
                    # Check for tables in text
                    if not analysis['has_tables']:
                        analysis['has_tables'] = self._has_table_content(text)
                        
        except Exception as e:
            logger.warning(f"Error in quick content analysis: {str(e)}")
        
        # Recommend strategies based on analysis
        analysis['recommended_chunker'] = self.chunker_factory.recommend_strategy(
            document_type=file_extension,
            content_length=file_size,
            has_structure=analysis['has_tables'],
            is_narrative=analysis['complexity_score'] > 0.6
        )
        
        analysis['recommended_embedder'] = self.embedder_factory.recommend_strategy(
            document_type=file_extension,
            content_complexity="high" if analysis['complexity_score'] > 0.7 else "medium",
            has_context=True
        )
        
        return analysis
    
    async def _extract_document_content(self, file_data: bytes, file_name: str):
        """Extract content using appropriate processor"""
        import os
        
        file_extension = os.path.splitext(file_name)[1].lower()
        processor = self.processors.get(file_extension)
        
        if not processor:
            raise ValueError(f"No processor available for {file_extension}")
        
        return await processor.extract_content(file_name, file_data)
    
    async def _process_images(self, images: List[Dict[str, Any]], 
                             user_id: str, document_id: str, 
                             file_name: str) -> Dict[str, Any]:
        """Process và upload images"""
        image_urls = []
        
        for i, img_data in enumerate(images):
            try:
                img_format = img_data.get("metadata", {}).get("format", "JPEG")
                content_type = f"image/{img_format.lower()}"
                
                url = await self.s3_service.upload_image(
                    img_data["image_data"],
                    file_name,
                    user_id,
                    document_id,
                    i,
                    content_type
                )
                
                if url:
                    image_urls.append(url)
                    
            except Exception as e:
                logger.error(f"Error processing image {i}: {str(e)}")
                continue
        
        return {
            'image_urls': image_urls,
            'images_processed': len(image_urls),
            'images_failed': len(images) - len(image_urls)
        }
    
    async def _create_enhanced_text_content(self, text_content: str,
                                          image_urls: List[str],
                                          images: List[Dict[str, Any]],
                                          analysis: Dict[str, Any]) -> str:
        """Create enhanced text content với image tags và optimization"""
        
        if not image_urls or not images:
            return text_content
        
        try:
            # Create image mapping
            url_mapping = {}
            for i, url in enumerate(image_urls):
                if i < len(images):
                    url_mapping[i] = url
            
            # Replace image placeholders
            import re
            placeholder_pattern = r'\[IMAGE_(\d+)\]'
            
            def replace_placeholder(match):
                img_index = int(match.group(1)) - 1
                if img_index in url_mapping:
                    return f"<image:{url_mapping[img_index]}>"
                return match.group(0)
            
            result_text = re.sub(placeholder_pattern, replace_placeholder, text_content)
            
            # If no placeholders, intelligently place images
            if not re.search(placeholder_pattern, text_content):
                result_text = self._intelligently_place_images(result_text, image_urls, analysis)
            
            return result_text
            
        except Exception as e:
            logger.error(f"Error creating enhanced text content: {str(e)}")
            # Fallback
            image_tags = [f"<image:{url}>" for url in image_urls]
            return text_content + "\n\n" + "\n".join(image_tags)
    
    async def _enhanced_chunking(self, text: str, analysis: Dict[str, Any],
                               options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform enhanced chunking"""
        try:
            # Use recommended strategy if not overridden
            chunker_strategy = options.get('chunker_strategy', analysis.get('recommended_chunker', self.chunker_strategy))
            
            # Create optimized chunker for this specific document
            chunker = self.chunker_factory.create_chunker(
                strategy=chunker_strategy,
                chunk_size=options.get('chunk_size', self.config.get('chunk_size', 1000)),
                overlap=options.get('overlap', self.config.get('overlap', 200)),
                document_type=analysis['file_extension']
            )
            
            # Perform chunking
            chunks = await chunker.chunk_text(text, analysis)
            
            # Calculate quality metrics
            quality_metrics = self._calculate_chunking_quality(chunks, text, analysis)
            
            return {
                'chunks': chunks,
                'strategy_used': chunker_strategy,
                'total_chunks': len(chunks),
                'avg_chunk_size': sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0,
                'quality_score': quality_metrics['overall_score'],
                'quality_metrics': quality_metrics
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced chunking: {str(e)}")
            # Fallback to default chunker
            chunks = await self.chunker.chunk_text(text, analysis)
            return {
                'chunks': chunks,
                'strategy_used': self.chunker_strategy,
                'total_chunks': len(chunks),
                'avg_chunk_size': sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0,
                'quality_score': 0.5
            }
    
    async def _enhanced_embedding(self, chunks: List[ChunkResult],
                                analysis: Dict[str, Any],
                                options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform enhanced embedding"""
        try:
            # Use recommended strategy if not overridden
            embedder_strategy = options.get('embedder_strategy', analysis.get('recommended_embedder', self.embedder_strategy))
            
            # Create optimized embedder for this document
            if embedder_strategy != self.embedder_strategy:
                embedder = self.embedder_factory.create_embedder(
                    strategy=embedder_strategy,
                    model_name=self.config.get('model_name', 'Qwen/Qwen3-Embedding-0.6B'),
                    document_type=analysis['file_extension'],
                    chunk_type=analysis.get('recommended_chunker')
                )
                await embedder.initialize()
            else:
                embedder = self.embedder
            
            # Prepare contexts for chunks
            contexts = []
            for chunk in chunks:
                context = {
                    'preceding_context': chunk.metadata.preceding_context,
                    'following_context': chunk.metadata.following_context,
                    'section_title': chunk.metadata.section_title,
                    'document_metadata': analysis
                }
                contexts.append(context)
            
            # Embed chunks
            chunk_texts = [chunk.content for chunk in chunks]
            embedding_results = await embedder.embed_batch(chunk_texts, contexts)
            
            # Calculate metrics
            total_tokens = sum(result.metadata.token_count or 0 for result in embedding_results)
            avg_confidence = sum(result.metadata.confidence_score or 0 for result in embedding_results) / len(embedding_results) if embedding_results else 0
            vector_dimension = embedding_results[0].metadata.vector_dimension if embedding_results else 0
            
            # Combine chunk and embedding data
            chunk_embeddings = []
            for chunk, embedding_result in zip(chunks, embedding_results):
                chunk_embeddings.append({
                    'chunk': chunk,
                    'embedding': embedding_result
                })
            
            return {
                'chunk_embeddings': chunk_embeddings,
                'strategy_used': embedder_strategy,
                'model_used': embedder.model_name,
                'vector_dimension': vector_dimension,
                'total_tokens': total_tokens,
                'avg_confidence': avg_confidence,
                'avg_processing_time': sum(result.metadata.processing_time or 0 for result in embedding_results) / len(embedding_results) if embedding_results else 0
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced embedding: {str(e)}")
            raise
    
    async def _store_enhanced_chunks(self, chunk_embeddings: List[Dict[str, Any]],
                                   document_id: str, user_id: str, company_id: str,
                                   analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Store chunks với enhanced metadata"""
        stored_chunks = []
        
        for item in chunk_embeddings:
            chunk = item['chunk']
            embedding = item['embedding']
            
            try:
                # Enhanced source info
                source_info = {
                    "type": "document",
                    "source_id": document_id,
                    "title": analysis.get('title', analysis['file_name']),
                    "file_type": analysis['file_extension'],
                    "analysis_metadata": analysis
                }
                
                # Enhanced chunk metadata
                enhanced_metadata = {
                    **chunk.metadata.to_dict(),
                    'embedding_metadata': embedding.metadata.to_dict(),
                    'processing_strategy': {
                        'chunker': analysis.get('recommended_chunker'),
                        'embedder': analysis.get('recommended_embedder')
                    },
                    'quality_metrics': {
                        'confidence_score': embedding.metadata.confidence_score,
                        'semantic_density': embedding.metadata.semantic_density,
                        'coherence_score': chunk.metadata.coherence_score,
                        'completeness_score': chunk.metadata.completeness_score
                    },
                    'context_info': {
                        'has_preceding': bool(chunk.metadata.preceding_context),
                        'has_following': bool(chunk.metadata.following_context),
                        'context_strategy': embedding.metadata.context_strategy
                    }
                }
                
                # Store chunk
                chunk_record = await self.knowledge_chunk_manager.create_knowledge_chunk(
                    content=chunk.content,
                    content_embedding=embedding.vector.tolist(),
                    source_info=source_info,
                    user_id=user_id,
                    company_id=company_id,
                    metadata=enhanced_metadata
                )
                
                stored_chunks.append(chunk_record)
                
            except Exception as e:
                logger.error(f"Error storing chunk {chunk.metadata.chunk_index}: {str(e)}")
                continue
        
        return {
            'chunks_stored': len(stored_chunks),
            'chunks_failed': len(chunk_embeddings) - len(stored_chunks),
            'chunk_ids': [str(chunk["_id"]) for chunk in stored_chunks]
        }
    
    async def _cleanup_failed_processing(self, document_id: str, image_urls: List[str]):
        """Cleanup sau khi processing thất bại"""
        try:
            await self.document_manager.delete_by_id(document_id)
            await self.knowledge_chunk_manager.delete_by_source_id(document_id)
            
            for url in image_urls:
                await self.s3_service.delete_file(url)
                
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    def _calculate_complexity_score(self, text: str) -> float:
        """Calculate text complexity score"""
        try:
            words = text.split()
            sentences = text.split('.')
            
            if not words or not sentences:
                return 0.5
            
            avg_word_length = sum(len(word) for word in words) / len(words)
            avg_sentence_length = len(words) / len(sentences)
            unique_word_ratio = len(set(words)) / len(words)
            
            # Normalize and combine
            complexity = (
                min(1.0, avg_word_length / 8) * 0.3 +
                min(1.0, avg_sentence_length / 20) * 0.4 +
                unique_word_ratio * 0.3
            )
            
            return complexity
            
        except:
            return 0.5
    
    def _detect_language(self, text: str) -> str:
        """Detect text language"""
        # Simple Vietnamese detection
        vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)
        vietnamese_ratio = vietnamese_count / len(text) if text else 0
        
        return 'vi' if vietnamese_ratio > 0.01 else 'en'
    
    def _has_table_content(self, text: str) -> bool:
        """Check if text có table content"""
        import re
        table_indicators = [
            r'\|.*\|',  # Pipe tables
            r'\t.*\t',  # Tab-separated
            r'┌.*┐',    # Box drawing
            r'├.*┤'     # Box drawing
        ]
        
        for pattern in table_indicators:
            if re.search(pattern, text):
                return True
        
        return False
    
    def _intelligently_place_images(self, text: str, image_urls: List[str], 
                                   analysis: Dict[str, Any]) -> str:
        """Intelligently place images trong text"""
        if not image_urls:
            return text
        
        # Split into paragraphs
        paragraphs = text.split('\n\n')
        
        if len(paragraphs) <= 1:
            # Just append images at end
            image_tags = [f"<image:{url}>" for url in image_urls]
            return text + "\n\n" + "\n".join(image_tags)
        
        # Distribute images evenly
        total_paragraphs = len(paragraphs)
        images_per_section = max(1, total_paragraphs // len(image_urls))
        
        result_paragraphs = []
        image_index = 0
        
        for i, paragraph in enumerate(paragraphs):
            result_paragraphs.append(paragraph)
            
            # Insert image after every images_per_section paragraphs
            if (i + 1) % images_per_section == 0 and image_index < len(image_urls):
                result_paragraphs.append(f"<image:{image_urls[image_index]}>")
                image_index += 1
        
        # Add remaining images at end
        while image_index < len(image_urls):
            result_paragraphs.append(f"<image:{image_urls[image_index]}>")
            image_index += 1
        
        return '\n\n'.join(result_paragraphs)
    
    def _calculate_chunking_quality(self, chunks: List[ChunkResult], 
                                   original_text: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate chunking quality metrics"""
        if not chunks:
            return {'overall_score': 0.0}
        
        try:
            # Size consistency
            sizes = [len(chunk.content) for chunk in chunks]
            avg_size = sum(sizes) / len(sizes)
            size_variance = sum((s - avg_size) ** 2 for s in sizes) / len(sizes)
            size_consistency = 1.0 / (1.0 + size_variance / (avg_size ** 2)) if avg_size > 0 else 0
            
            # Semantic coherence (from chunk metadata)
            coherence_scores = [chunk.metadata.coherence_score or 0.5 for chunk in chunks]
            avg_coherence = sum(coherence_scores) / len(coherence_scores)
            
            # Coverage (total chunk content vs original)
            total_chunk_length = sum(len(chunk.content) for chunk in chunks)
            coverage = min(1.0, total_chunk_length / len(original_text)) if original_text else 0
            
            # Overall score
            overall_score = (size_consistency * 0.3 + avg_coherence * 0.5 + coverage * 0.2)
            
            return {
                'overall_score': overall_score,
                'size_consistency': size_consistency,
                'avg_coherence': avg_coherence,
                'coverage': coverage,
                'avg_chunk_size': avg_size,
                'total_chunks': len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Error calculating chunking quality: {str(e)}")
            return {'overall_score': 0.5}
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        try:
            stats = {
                'chunker': {
                    'strategy': self.chunker_strategy,
                    'available_strategies': self.chunker_factory.get_available_strategies()
                },
                'embedder': {
                    'strategy': self.embedder_strategy,
                    'model': self.embedder.model_name if self.embedder else None,
                    'available_strategies': self.embedder_factory.get_available_strategies()
                },
                'processors': {
                    'supported_formats': list(self.processors.keys())
                }
            }
            
            if self.embedder:
                stats['embedder'].update(self.embedder.get_model_info())
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting processing stats: {str(e)}")
            return {}
