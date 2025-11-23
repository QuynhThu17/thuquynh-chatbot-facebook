"""
Contextual Embedder
Embedder với context-aware capabilities để tạo embeddings tốt hơn
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import time

from .base_embedder import BaseEmbedder, EmbeddingResult, EmbeddingMetadata, EmbeddingType
from configs.environment import get_embedding

logger = logging.getLogger(__name__)

class ContextualEmbedder(BaseEmbedder):
    """
    Contextual embedder tạo embeddings với context awareness
    Sử dụng surrounding context để improve embedding quality
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", 
                 context_window: int = 500,
                 context_strategy: str = "surrounding",
                 context_weight: float = 0.3,
                 **kwargs):
        """
        Initialize Contextual Embedder
        
        Args:
            model_name: Sentence transformer model name
            context_window: Size of context window
            context_strategy: Context strategy (surrounding, preceding, following)
            context_weight: Weight of context in final embedding
        """
        super().__init__(model_name, **kwargs)
        self.context_window = context_window
        self.context_strategy = context_strategy
        self.context_weight = context_weight
        
        # Validate context strategy
        valid_strategies = ['surrounding', 'preceding', 'following', 'none']
        if context_strategy not in valid_strategies:
            logger.warning(f"Invalid context strategy {context_strategy}, using 'surrounding'")
            self.context_strategy = 'surrounding'
    
    async def initialize(self):
        """Initialize embedding model từ environment"""
        try:
            if not self._is_initialized:
                logger.info(f"Using shared embedding model from environment")
                self._model = get_embedding()
                self._is_initialized = True
                logger.info("Contextual embedder initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing contextual embedder: {str(e)}")
            raise
    
    def get_embedding_type(self) -> EmbeddingType:
        """Return embedding type"""
        return EmbeddingType.CONTEXTUAL
    
    def get_vector_dimension(self) -> int:
        """Return vector dimension"""
        if self._model:
            # For OpenAI embeddings, the dimension is 1536 for text-embedding-3-small
            return 1536
        else:
            # Default dimension for OpenAI text-embedding-3-small
            return 1536
    
    async def embed_text(self, text: str, context: Optional[Dict[str, Any]] = None) -> EmbeddingResult:
        """
        Embed text với context awareness
        
        Args:
            text: Text cần embed
            context: Context information
            
        Returns:
            EmbeddingResult: Contextual embedding result
        """
        if not self.validate_text(text):
            raise ValueError("Invalid text input")
        
        if not self._is_initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Preprocess text
            processed_text = self.preprocess_text(text)
            
            # Extract context
            context_text = await self._extract_context(processed_text, context)
            
            # Create embedding với và không có context
            text_embedding = await self._embed_single_text(processed_text)
            
            if context_text and self.context_strategy != 'none':
                # Embed text with context
                contextual_embedding = await self._embed_with_context(processed_text, context_text)
                
                # Combine embeddings
                final_embedding = await self._combine_embeddings(text_embedding, contextual_embedding)
            else:
                final_embedding = text_embedding
                contextual_embedding = None
            
            # Calculate metadata
            processing_time = time.time() - start_time
            
            metadata = EmbeddingMetadata(
                embedding_type=self.get_embedding_type(),
                model_name=self.model_name,
                vector_dimension=len(final_embedding),
                context_window=self.context_window,
                context_strategy=self.context_strategy,
                confidence_score=self.calculate_confidence_score(final_embedding, processed_text),
                semantic_density=self.calculate_semantic_density(processed_text),
                processing_time=processing_time,
                token_count=self.calculate_token_count(processed_text),
                normalization="l2"
            )
            
            # Prepare result
            result = EmbeddingResult(
                vector=final_embedding,
                metadata=metadata
            )
            
            # Add context vectors if available
            if contextual_embedding is not None:
                result.context_vectors = {
                    'text_only': text_embedding,
                    'with_context': contextual_embedding
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error embedding text: {str(e)}")
            raise
    
    async def embed_batch(self, texts: List[str], 
                         contexts: Optional[List[Dict[str, Any]]] = None) -> List[EmbeddingResult]:
        """
        Embed multiple texts in batch với context
        
        Args:
            texts: Danh sách texts
            contexts: Context information cho từng text
            
        Returns:
            List[EmbeddingResult]: Batch embedding results
        """
        if not texts:
            return []
        
        if not self._is_initialized:
            await self.initialize()
        
        # Prepare contexts
        if contexts is None:
            contexts = [None] * len(texts)
        elif len(contexts) != len(texts):
            logger.warning("Contexts length doesn't match texts length, padding with None")
            contexts = contexts + [None] * (len(texts) - len(contexts))
        
        results = []
        
        try:
            # Process in batches to avoid memory issues
            batch_size = self.config.get('batch_size', 16)
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_contexts = contexts[i:i + batch_size]
                
                # Process batch
                batch_results = await self._process_batch(batch_texts, batch_contexts)
                results.extend(batch_results)
            
            logger.info(f"Embedded {len(texts)} texts in batch")
            return results
            
        except Exception as e:
            logger.error(f"Error in batch embedding: {str(e)}")
            # Fallback to individual processing
            for text, ctx in zip(texts, contexts):
                try:
                    result = await self.embed_text(text, ctx)
                    results.append(result)
                except Exception as text_error:
                    logger.error(f"Error embedding individual text: {str(text_error)}")
                    continue
            
            return results
    
    async def _process_batch(self, texts: List[str], 
                           contexts: List[Optional[Dict[str, Any]]]) -> List[EmbeddingResult]:
        """
        Process a batch of texts
        
        Args:
            texts: Batch texts
            contexts: Batch contexts
            
        Returns:
            List[EmbeddingResult]: Batch results
        """
        start_time = time.time()
        
        # Preprocess all texts
        processed_texts = [self.preprocess_text(text) for text in texts]
        
        # Extract contexts
        context_texts = []
        for i, text in enumerate(processed_texts):
            context_text = await self._extract_context(text, contexts[i])
            context_texts.append(context_text)
        
        # Embed texts only
        text_embeddings = await self._embed_batch_texts(processed_texts)
        
        # Embed with contexts (if any)
        contextual_embeddings = []
        for i, (text, context_text) in enumerate(zip(processed_texts, context_texts)):
            if context_text and self.context_strategy != 'none':
                ctx_embedding = await self._embed_with_context(text, context_text)
                contextual_embeddings.append(ctx_embedding)
            else:
                contextual_embeddings.append(None)
        
        # Combine embeddings and create results
        results = []
        processing_time = time.time() - start_time
        
        for i, (text, text_emb, ctx_emb) in enumerate(zip(processed_texts, text_embeddings, contextual_embeddings)):
            if ctx_emb is not None:
                final_embedding = await self._combine_embeddings(text_emb, ctx_emb)
            else:
                final_embedding = text_emb
            
            metadata = EmbeddingMetadata(
                embedding_type=self.get_embedding_type(),
                model_name=self.model_name,
                vector_dimension=len(final_embedding),
                context_window=self.context_window,
                context_strategy=self.context_strategy,
                confidence_score=self.calculate_confidence_score(final_embedding, text),
                semantic_density=self.calculate_semantic_density(text),
                processing_time=processing_time / len(processed_texts),  # Average time
                token_count=self.calculate_token_count(text),
                normalization="l2"
            )
            
            result = EmbeddingResult(vector=final_embedding, metadata=metadata)
            
            if ctx_emb is not None:
                result.context_vectors = {
                    'text_only': text_emb,
                    'with_context': ctx_emb
                }
            
            results.append(result)
        
        return results
    
    async def _extract_context(self, text: str, context_info: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Extract context text based on strategy
        
        Args:
            text: Main text
            context_info: Context information
            
        Returns:
            str: Context text or None
        """
        if not context_info or self.context_strategy == 'none':
            return None
        
        try:
            # Get preceding and following context from context_info
            preceding_context = context_info.get('preceding_context', '')
            following_context = context_info.get('following_context', '')
            
            # Apply context strategy
            if self.context_strategy == 'preceding':
                context_text = preceding_context[-self.context_window:] if preceding_context else None
            elif self.context_strategy == 'following':
                context_text = following_context[:self.context_window] if following_context else None
            elif self.context_strategy == 'surrounding':
                # Combine preceding and following
                half_window = self.context_window // 2
                prec = preceding_context[-half_window:] if preceding_context else ''
                foll = following_context[:half_window] if following_context else ''
                context_text = (prec + ' ' + foll).strip() if (prec or foll) else None
            else:
                context_text = None
            
            return context_text if context_text and len(context_text.strip()) > 0 else None
            
        except Exception as e:
            logger.error(f"Error extracting context: {str(e)}")
            return None
    
    async def _embed_single_text(self, text: str) -> np.ndarray:
        """
        Embed single text without context
        
        Args:
            text: Text to embed
            
        Returns:
            np.ndarray: Embedding vector
        """
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._model.embed_query(text)
        )
        return np.array(embedding)
    
    async def _embed_batch_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Embed batch of texts without context
        
        Args:
            texts: Texts to embed
            
        Returns:
            List[np.ndarray]: Embedding vectors
        """
        embeddings = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._model.embed_documents(texts)
        )
        return [np.array(emb) for emb in embeddings]
    
    async def _embed_with_context(self, text: str, context: str) -> np.ndarray:
        """
        Embed text with context
        
        Args:
            text: Main text
            context: Context text
            
        Returns:
            np.ndarray: Contextual embedding
        """
        # Strategy 1: Concatenate text with context
        contextual_text = f"{context} [SEP] {text}"
        
        # Ensure it doesn't exceed model max length
        max_length = self.config.get('max_length', 512)
        if len(contextual_text) > max_length:
            # Truncate context to fit
            available_space = max_length - len(text) - 10  # 10 for [SEP] and buffer
            if available_space > 0:
                truncated_context = context[:available_space]
                contextual_text = f"{truncated_context} [SEP] {text}"
            else:
                # If text itself is too long, just use text
                contextual_text = text[:max_length]
        
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self._model.embed_query(contextual_text)
        )
        return np.array(embedding)
    
    async def _combine_embeddings(self, text_embedding: np.ndarray, 
                                context_embedding: np.ndarray) -> np.ndarray:
        """
        Combine text và context embeddings
        
        Args:
            text_embedding: Text-only embedding
            context_embedding: Context-aware embedding
            
        Returns:
            np.ndarray: Combined embedding
        """
        # Weighted combination
        text_weight = 1.0 - self.context_weight
        combined = text_weight * text_embedding + self.context_weight * context_embedding
        
        # Normalize
        combined = self.normalize_vector(combined, method="l2")
        
        return combined
