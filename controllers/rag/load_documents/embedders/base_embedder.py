"""
Base Embedder Interface
Interface cơ bản cho tất cả embedding strategies
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingType(Enum):
    """Loại embedding"""
    DENSE = "dense"           # Dense vectors (BERT, sentence transformers)
    SPARSE = "sparse"         # Sparse vectors (TF-IDF, BM25)
    HYBRID = "hybrid"         # Combination of dense and sparse
    CONTEXTUAL = "contextual" # Context-aware embeddings
    MULTI_LEVEL = "multi_level" # Multiple granularity levels

@dataclass
class EmbeddingMetadata:
    """Metadata cho embedding"""
    embedding_type: EmbeddingType
    model_name: str
    vector_dimension: int
    
    # Context information
    context_window: Optional[int] = None
    context_strategy: Optional[str] = None
    
    # Multi-level information
    levels: Optional[List[str]] = None
    level_weights: Optional[Dict[str, float]] = None
    
    # Quality metrics
    confidence_score: Optional[float] = None
    semantic_density: Optional[float] = None
    
    # Processing info
    processing_time: Optional[float] = None
    token_count: Optional[int] = None
    
    # Model-specific info
    model_version: Optional[str] = None
    normalization: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'embedding_type': self.embedding_type.value,
            'model_name': self.model_name,
            'vector_dimension': self.vector_dimension,
            'context_window': self.context_window,
            'context_strategy': self.context_strategy,
            'levels': self.levels,
            'level_weights': self.level_weights,
            'confidence_score': self.confidence_score,
            'semantic_density': self.semantic_density,
            'processing_time': self.processing_time,
            'token_count': self.token_count,
            'model_version': self.model_version,
            'normalization': self.normalization
        }

@dataclass
class EmbeddingResult:
    """Kết quả embedding"""
    vector: np.ndarray
    metadata: EmbeddingMetadata
    
    # Multi-vector results
    additional_vectors: Optional[Dict[str, np.ndarray]] = None
    
    # Context embeddings
    context_vectors: Optional[Dict[str, np.ndarray]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        result = {
            'vector': self.vector.tolist(),
            'metadata': self.metadata.to_dict()
        }
        
        if self.additional_vectors:
            result['additional_vectors'] = {
                key: vec.tolist() for key, vec in self.additional_vectors.items()
            }
        
        if self.context_vectors:
            result['context_vectors'] = {
                key: vec.tolist() for key, vec in self.context_vectors.items()
            }
        
        return result

class BaseEmbedder(ABC):
    """
    Abstract base class cho tất cả embedding strategies
    """
    
    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", **kwargs):
        """
        Initialize embedder
        
        Args:
            model_name: Tên model embedding
            **kwargs: Additional parameters
        """
        self.model_name = model_name
        self.config = kwargs
        self._model = None
        self._is_initialized = False
        
        logger.info(f"Initialized {self.__class__.__name__} with model {model_name}")
    
    @abstractmethod
    async def initialize(self):
        """Initialize model và resources"""
        pass
    
    @abstractmethod
    async def embed_text(self, text: str, context: Optional[Dict[str, Any]] = None) -> EmbeddingResult:
        """
        Embed một text
        
        Args:
            text: Text cần embed
            context: Context information
            
        Returns:
            EmbeddingResult: Embedding result
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str], 
                         contexts: Optional[List[Dict[str, Any]]] = None) -> List[EmbeddingResult]:
        """
        Embed multiple texts in batch
        
        Args:
            texts: Danh sách texts
            contexts: Context information cho từng text
            
        Returns:
            List[EmbeddingResult]: Embedding results
        """
        pass
    
    @abstractmethod
    def get_embedding_type(self) -> EmbeddingType:
        """
        Lấy loại embedding của embedder này
        
        Returns:
            EmbeddingType: Embedding type
        """
        pass
    
    @abstractmethod
    def get_vector_dimension(self) -> int:
        """
        Lấy dimension của embedding vector
        
        Returns:
            int: Vector dimension
        """
        pass
    
    def validate_text(self, text: str) -> bool:
        """
        Validate input text
        
        Args:
            text: Text cần validate
            
        Returns:
            bool: True nếu text hợp lệ
        """
        if not text or not isinstance(text, str):
            return False
        
        if len(text.strip()) == 0:
            return False
        
        # Check maximum length (model dependent)
        max_length = self.config.get('max_length', 8192)
        if len(text) > max_length:
            logger.warning(f"Text length {len(text)} exceeds max_length {max_length}")
            return False
        
        return True
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text trước khi embedding
        
        Args:
            text: Text cần preprocess
            
        Returns:
            str: Preprocessed text
        """
        # Basic preprocessing
        text = text.strip()
        
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text
    
    def calculate_token_count(self, text: str) -> int:
        """
        Ước tính số token
        
        Args:
            text: Text cần đếm
            
        Returns:
            int: Số token ước tính
        """
        # Simple estimation: ~4 characters per token for English, ~3 for Vietnamese
        return len(text) // 3
    
    def calculate_semantic_density(self, text: str) -> float:
        """
        Tính semantic density của text
        
        Args:
            text: Text cần tính
            
        Returns:
            float: Semantic density score (0-1)
        """
        try:
            words = text.split()
            if not words:
                return 0.0
            
            # Simple metrics
            unique_words = len(set(word.lower() for word in words))
            total_words = len(words)
            
            # Vocabulary richness
            vocab_richness = unique_words / total_words if total_words > 0 else 0
            
            # Average word length (indicator of complexity)
            avg_word_length = sum(len(word) for word in words) / total_words if total_words > 0 else 0
            normalized_word_length = min(1.0, avg_word_length / 8)  # Normalize to ~8 chars
            
            # Punctuation ratio (indicator of structure)
            import re
            punctuation_count = len(re.findall(r'[^\w\s]', text))
            punct_ratio = min(1.0, punctuation_count / len(text) * 10) if text else 0
            
            # Combined score
            density = (vocab_richness * 0.5 + normalized_word_length * 0.3 + punct_ratio * 0.2)
            
            return min(1.0, density)
            
        except Exception as e:
            logger.error(f"Error calculating semantic density: {str(e)}")
            return 0.5  # Default value
    
    def normalize_vector(self, vector: np.ndarray, method: str = "l2") -> np.ndarray:
        """
        Normalize embedding vector
        
        Args:
            vector: Vector cần normalize
            method: Normalization method (l2, l1, max)
            
        Returns:
            np.ndarray: Normalized vector
        """
        try:
            if method == "l2":
                norm = np.linalg.norm(vector)
                return vector / norm if norm > 0 else vector
            elif method == "l1":
                norm = np.sum(np.abs(vector))
                return vector / norm if norm > 0 else vector
            elif method == "max":
                max_val = np.max(np.abs(vector))
                return vector / max_val if max_val > 0 else vector
            else:
                return vector
                
        except Exception as e:
            logger.error(f"Error normalizing vector: {str(e)}")
            return vector
    
    def calculate_confidence_score(self, vector: np.ndarray, text: str) -> float:
        """
        Tính confidence score cho embedding
        
        Args:
            vector: Embedding vector
            text: Original text
            
        Returns:
            float: Confidence score (0-1)
        """
        try:
            # Vector magnitude (higher = more confident)
            magnitude = np.linalg.norm(vector)
            magnitude_score = min(1.0, magnitude / 10)  # Normalize
            
            # Vector sparsity (lower sparsity = more confident)
            non_zero_ratio = np.count_nonzero(vector) / len(vector)
            sparsity_score = non_zero_ratio
            
            # Text length factor
            text_length_score = min(1.0, len(text) / 1000)  # Normalize to ~1000 chars
            
            # Combined confidence
            confidence = (magnitude_score * 0.4 + sparsity_score * 0.4 + text_length_score * 0.2)
            
            return min(1.0, confidence)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {str(e)}")
            return 0.5
    
    async def warm_up(self, sample_texts: Optional[List[str]] = None):
        """
        Warm up model với sample texts
        
        Args:
            sample_texts: Sample texts for warm up
        """
        if not self._is_initialized:
            await self.initialize()
        
        if not sample_texts:
            sample_texts = [
                "This is a sample text for warming up the embedding model.",
                "Đây là văn bản mẫu để khởi động mô hình embedding."
            ]
        
        try:
            logger.info("Warming up embedding model...")
            await self.embed_batch(sample_texts)
            logger.info("Model warm-up completed")
            
        except Exception as e:
            logger.error(f"Error during model warm-up: {str(e)}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Lấy thông tin về model
        
        Returns:
            Dict: Model information
        """
        return {
            'model_name': self.model_name,
            'embedding_type': self.get_embedding_type().value,
            'vector_dimension': self.get_vector_dimension(),
            'is_initialized': self._is_initialized,
            'config': self.config
        }
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            if hasattr(self, '_model') and self._model:
                # Cleanup model if needed
                del self._model
                self._model = None
            
            self._is_initialized = False
            logger.info(f"{self.__class__.__name__} cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    def __del__(self):
        """Destructor"""
        try:
            if self._is_initialized:
                # Note: async cleanup in destructor is tricky
                # Better to call cleanup() explicitly
                pass
        except:
            pass
