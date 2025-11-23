"""
Multi-Level Embedder
Tạo embeddings ở multiple levels (sentence, paragraph, document)
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import time

from .base_embedder import BaseEmbedder, EmbeddingResult, EmbeddingMetadata, EmbeddingType
from configs.environment import get_embedding

logger = logging.getLogger(__name__)

class MultiLevelEmbedder(BaseEmbedder):
    """
    Multi-level embedder tạo embeddings ở nhiều levels khác nhau
    - Sentence level: Embedding cho từng sentence
    - Paragraph level: Embedding cho từng paragraph
    - Document level: Embedding cho toàn document
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B",
                 levels: List[str] = None,
                 level_weights: Dict[str, float] = None,
                 aggregation_method: str = "weighted_average",
                 **kwargs):
        """
        Initialize Multi-Level Embedder
        
        Args:
            model_name: Model name
            levels: List of levels to embed (sentence, paragraph, document)
            level_weights: Weights for each level
            aggregation_method: Method to aggregate multi-level embeddings
        """
        super().__init__(model_name, **kwargs)
        
        # Default levels
        if levels is None:
            self.levels = ['sentence', 'paragraph', 'document']
        else:
            self.levels = levels
        
        # Default weights
        if level_weights is None:
            self.level_weights = {
                'sentence': 0.4,
                'paragraph': 0.4,
                'document': 0.2
            }
        else:
            self.level_weights = level_weights
        
        # Normalize weights
        total_weight = sum(self.level_weights.values())
        if total_weight > 0:
            self.level_weights = {k: v/total_weight for k, v in self.level_weights.items()}
        
        self.aggregation_method = aggregation_method
        
        # Direct initialization without contextual embedder dependency
        self._embedding_model = None
    
    async def initialize(self):
        """Initialize embedder"""
        if not self._is_initialized:
            logger.info(f"Using shared embedding model from environment")
            self._model = get_embedding()
            self._embedding_model = self._model
            self._is_initialized = True
            logger.info("Multi-level embedder initialized successfully")
    
    def get_embedding_type(self) -> EmbeddingType:
        """Return embedding type"""
        return EmbeddingType.MULTI_LEVEL
    
    def get_vector_dimension(self) -> int:
        """Return vector dimension"""
        # For OpenAI embeddings, the dimension is 1536 for text-embedding-3-small
        return 1536
    
    async def embed_text(self, text: str, context: Optional[Dict[str, Any]] = None) -> EmbeddingResult:
        """
        Embed text với multi-level approach
        
        Args:
            text: Text cần embed
            context: Context information
            
        Returns:
            EmbeddingResult: Multi-level embedding result
        """
        if not self.validate_text(text):
            raise ValueError("Invalid text input")
        
        if not self._is_initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # Preprocess text
            processed_text = self.preprocess_text(text)
            
            # Extract text levels
            text_levels = await self._extract_text_levels(processed_text)
            
            # Embed each level
            level_embeddings = {}
            for level in self.levels:
                if level in text_levels and text_levels[level]:
                    level_embedding = await self._embed_level(text_levels[level], level, context)
                    level_embeddings[level] = level_embedding
            
            # Aggregate embeddings
            final_embedding = await self._aggregate_embeddings(level_embeddings)
            
            # Calculate metadata
            processing_time = time.time() - start_time
            
            metadata = EmbeddingMetadata(
                embedding_type=self.get_embedding_type(),
                model_name=self.model_name,
                vector_dimension=len(final_embedding),
                levels=list(level_embeddings.keys()),
                level_weights=self.level_weights,
                confidence_score=self.calculate_confidence_score(final_embedding, processed_text),
                semantic_density=self.calculate_semantic_density(processed_text),
                processing_time=processing_time,
                token_count=self.calculate_token_count(processed_text),
                normalization="l2"
            )
            
            # Create result
            result = EmbeddingResult(
                vector=final_embedding,
                metadata=metadata,
                additional_vectors=level_embeddings
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in multi-level embedding: {str(e)}")
            raise
    
    async def embed_batch(self, texts: List[str], 
                         contexts: Optional[List[Dict[str, Any]]] = None) -> List[EmbeddingResult]:
        """
        Embed multiple texts with multi-level approach
        
        Args:
            texts: Danh sách texts
            contexts: Context information
            
        Returns:
            List[EmbeddingResult]: Multi-level embedding results
        """
        if not texts:
            return []
        
        if not self._is_initialized:
            await self.initialize()
        
        if contexts is None:
            contexts = [None] * len(texts)
        
        results = []
        
        try:
            # Process in batches for efficiency
            batch_size = self.config.get('batch_size', 8)  # Smaller batch for multi-level
            
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                batch_contexts = contexts[i:i + batch_size]
                
                # Process each text in batch (multi-level is complex to batch)
                batch_results = []
                for text, ctx in zip(batch_texts, batch_contexts):
                    try:
                        result = await self.embed_text(text, ctx)
                        batch_results.append(result)
                    except Exception as e:
                        logger.error(f"Error embedding text in batch: {str(e)}")
                        continue
                
                results.extend(batch_results)
            
            logger.info(f"Embedded {len(results)} texts with multi-level approach")
            return results
            
        except Exception as e:
            logger.error(f"Error in multi-level batch embedding: {str(e)}")
            return results
    
    async def _extract_text_levels(self, text: str) -> Dict[str, List[str]]:
        """
        Extract text ở các levels khác nhau
        
        Args:
            text: Text để extract
            
        Returns:
            Dict[str, List[str]]: Text chia theo levels
        """
        levels = {}
        
        try:
            # Document level
            if 'document' in self.levels:
                levels['document'] = [text]
            
            # Paragraph level
            if 'paragraph' in self.levels:
                paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
                if not paragraphs:
                    # Fallback: split by double newlines or long sentences
                    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
                levels['paragraph'] = paragraphs
            
            # Sentence level
            if 'sentence' in self.levels:
                # Simple sentence splitting
                import re
                sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ])'
                sentences = re.split(sentence_pattern, text)
                sentences = [s.strip() for s in sentences if s.strip()]
                levels['sentence'] = sentences
            
            # Clause level (if needed)
            if 'clause' in self.levels:
                clauses = []
                for sentence in levels.get('sentence', [text]):
                    # Split by commas, semicolons
                    clause_parts = re.split(r'[,;]', sentence)
                    clauses.extend([c.strip() for c in clause_parts if c.strip()])
                levels['clause'] = clauses
            
        except Exception as e:
            logger.error(f"Error extracting text levels: {str(e)}")
            # Fallback
            levels = {'document': [text]}
        
        return levels
    
    async def _embed_level(self, texts: List[str], level: str, 
                          context: Optional[Dict[str, Any]]) -> np.ndarray:
        """
        Embed texts ở một level cụ thể
        
        Args:
            texts: Texts to embed
            level: Level name
            context: Context information
            
        Returns:
            np.ndarray: Aggregated embedding for this level
        """
        if not texts:
            # Return zero vector if no text
            return np.zeros(self.get_vector_dimension())
        
        try:
            # Embed all texts in this level
            embeddings = []
            
            for text in texts:
                if len(text.strip()) > 0:
                    # Use embedding model directly
                    embedding = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: self._embedding_model.embed_query(text)
                    )
                    embeddings.append(np.array(embedding))
            
            if not embeddings:
                return np.zeros(self.get_vector_dimension())
            
            # Aggregate embeddings for this level
            level_embedding = await self._aggregate_level_embeddings(embeddings, level)
            
            return level_embedding
            
        except Exception as e:
            logger.error(f"Error embedding level {level}: {str(e)}")
            return np.zeros(self.get_vector_dimension())
    
    async def _aggregate_level_embeddings(self, embeddings: List[np.ndarray], level: str) -> np.ndarray:
        """
        Aggregate embeddings trong một level
        
        Args:
            embeddings: List of embeddings
            level: Level name
            
        Returns:
            np.ndarray: Aggregated embedding
        """
        if not embeddings:
            return np.zeros(self.get_vector_dimension())
        
        embeddings_array = np.array(embeddings)
        
        # Different aggregation strategies for different levels
        if level == 'sentence':
            # For sentences, use weighted average based on length
            lengths = [len(emb) for emb in embeddings]
            total_length = sum(lengths) if lengths else 1
            weights = [l / total_length for l in lengths]
            
            aggregated = np.average(embeddings_array, axis=0, weights=weights)
            
        elif level == 'paragraph':
            # For paragraphs, use simple average
            aggregated = np.mean(embeddings_array, axis=0)
            
        elif level == 'document':
            # For document, use first embedding (already whole document)
            aggregated = embeddings_array[0] if len(embeddings_array) > 0 else np.zeros(self.get_vector_dimension())
            
        else:
            # Default: simple average
            aggregated = np.mean(embeddings_array, axis=0)
        
        # Normalize
        aggregated = self.normalize_vector(aggregated, method="l2")
        
        return aggregated
    
    async def _aggregate_embeddings(self, level_embeddings: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Aggregate embeddings từ multiple levels
        
        Args:
            level_embeddings: Embeddings từ each level
            
        Returns:
            np.ndarray: Final aggregated embedding
        """
        if not level_embeddings:
            return np.zeros(self.get_vector_dimension())
        
        try:
            if self.aggregation_method == "weighted_average":
                # Weighted average based on level weights
                total_weight = 0
                weighted_sum = np.zeros(self.get_vector_dimension())
                
                for level, embedding in level_embeddings.items():
                    weight = self.level_weights.get(level, 0)
                    if weight > 0:
                        weighted_sum += weight * embedding
                        total_weight += weight
                
                if total_weight > 0:
                    final_embedding = weighted_sum / total_weight
                else:
                    final_embedding = np.mean(list(level_embeddings.values()), axis=0)
            
            elif self.aggregation_method == "concatenation":
                # Concatenate embeddings (increases dimension)
                embeddings_list = [level_embeddings[level] for level in self.levels if level in level_embeddings]
                final_embedding = np.concatenate(embeddings_list) if embeddings_list else np.zeros(self.get_vector_dimension())
            
            elif self.aggregation_method == "max_pooling":
                # Max pooling across levels
                embeddings_array = np.array([level_embeddings[level] for level in self.levels if level in level_embeddings])
                final_embedding = np.max(embeddings_array, axis=0) if len(embeddings_array) > 0 else np.zeros(self.get_vector_dimension())
            
            elif self.aggregation_method == "attention":
                # Attention-based aggregation (simplified)
                final_embedding = await self._attention_aggregation(level_embeddings)
            
            else:
                # Default: simple average
                embeddings_list = list(level_embeddings.values())
                final_embedding = np.mean(embeddings_list, axis=0) if embeddings_list else np.zeros(self.get_vector_dimension())
            
            # Normalize final embedding
            final_embedding = self.normalize_vector(final_embedding, method="l2")
            
            return final_embedding
            
        except Exception as e:
            logger.error(f"Error aggregating embeddings: {str(e)}")
            # Fallback to simple average
            embeddings_list = list(level_embeddings.values())
            return np.mean(embeddings_list, axis=0) if embeddings_list else np.zeros(self.get_vector_dimension())
    
    async def _attention_aggregation(self, level_embeddings: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Attention-based aggregation of level embeddings
        
        Args:
            level_embeddings: Level embeddings
            
        Returns:
            np.ndarray: Attention-aggregated embedding
        """
        try:
            embeddings_list = []
            level_names = []
            
            for level in self.levels:
                if level in level_embeddings:
                    embeddings_list.append(level_embeddings[level])
                    level_names.append(level)
            
            if not embeddings_list:
                return np.zeros(self.get_vector_dimension())
            
            embeddings_array = np.array(embeddings_list)
            
            # Simple attention: compute attention weights based on embedding magnitudes
            magnitudes = np.linalg.norm(embeddings_array, axis=1)
            attention_weights = magnitudes / np.sum(magnitudes) if np.sum(magnitudes) > 0 else np.ones(len(magnitudes)) / len(magnitudes)
            
            # Weighted combination
            final_embedding = np.sum(embeddings_array * attention_weights.reshape(-1, 1), axis=0)
            
            return final_embedding
            
        except Exception as e:
            logger.error(f"Error in attention aggregation: {str(e)}")
            # Fallback to weighted average
            return await self._aggregate_embeddings(level_embeddings)
