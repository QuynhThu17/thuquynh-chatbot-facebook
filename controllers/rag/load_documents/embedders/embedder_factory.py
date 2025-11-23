"""
Embedder Factory
Factory để tạo và quản lý các embedding strategies
"""

import logging
from typing import Dict, Any, Optional, Type, List
from enum import Enum

from .base_embedder import BaseEmbedder, EmbeddingType
from .contextual_embedder import ContextualEmbedder
from .multi_level_embedder import MultiLevelEmbedder

logger = logging.getLogger(__name__)

class EmbedderStrategy(Enum):
    """Available embedder strategies"""
    CONTEXTUAL = "contextual"
    MULTI_LEVEL = "multi_level"
    HYBRID = "hybrid"
    AUTO = "auto"

class EmbedderFactory:
    """
    Factory để tạo embedders với configuration linh hoạt
    """
    
    # Mapping strategy names to embedder classes
    EMBEDDER_CLASSES: Dict[EmbedderStrategy, Type[BaseEmbedder]] = {
        EmbedderStrategy.CONTEXTUAL: ContextualEmbedder,
        EmbedderStrategy.MULTI_LEVEL: MultiLevelEmbedder,
    }
    
    @classmethod
    def create_embedder(cls, 
                       strategy: str = "contextual",
                       model_name: str = "shared_embedding_model",
                       document_type: Optional[str] = None,
                       chunk_type: Optional[str] = None,
                       **kwargs) -> BaseEmbedder:
        """
        Tạo embedder với strategy và config cụ thể
        
        Args:
            strategy: Embedder strategy name
            model_name: Model name
            document_type: Document type hint
            chunk_type: Chunk type hint
            **kwargs: Additional parameters
            
        Returns:
            BaseEmbedder: Configured embedder instance
        """
        try:
            # Convert string to enum
            if isinstance(strategy, str):
                strategy_enum = EmbedderStrategy(strategy.lower())
            else:
                strategy_enum = strategy
            
            # Auto-select strategy if requested
            if strategy_enum == EmbedderStrategy.AUTO:
                strategy_enum = cls._auto_select_strategy(document_type, chunk_type, **kwargs)
            
            # Handle hybrid strategy
            if strategy_enum == EmbedderStrategy.HYBRID:
                return cls._create_hybrid_embedder(model_name, document_type, chunk_type, **kwargs)
            
            # Get embedder class
            embedder_class = cls.EMBEDDER_CLASSES.get(strategy_enum)
            if not embedder_class:
                logger.warning(f"Unknown strategy {strategy}, using contextual")
                embedder_class = ContextualEmbedder
            
            # Optimize parameters
            optimized_params = cls._optimize_parameters(
                strategy_enum, model_name, document_type, chunk_type, **kwargs
            )
            
            embedder = embedder_class(**optimized_params)
            logger.info(f"Created {embedder_class.__name__} with model {model_name}")
            
            return embedder
            
        except Exception as e:
            logger.error(f"Error creating embedder: {str(e)}")
            # Fallback to contextual embedder
            return ContextualEmbedder(model_name=model_name)
    
    @classmethod
    def _auto_select_strategy(cls, document_type: Optional[str], 
                             chunk_type: Optional[str], **kwargs) -> EmbedderStrategy:
        """
        Tự động chọn strategy dựa trên hints
        
        Args:
            document_type: Document type
            chunk_type: Chunk type
            **kwargs: Additional hints
            
        Returns:
            EmbedderStrategy: Selected strategy
        """
        # Document type preferences
        if document_type:
            doc_type = document_type.lower()
            if doc_type in ['.pdf', 'pdf']:
                return EmbedderStrategy.MULTI_LEVEL  # PDFs benefit from multi-level
            elif doc_type in ['.docx', '.doc']:
                return EmbedderStrategy.CONTEXTUAL   # Word docs benefit from context
        
        # Chunk type preferences
        if chunk_type:
            chunk_type = chunk_type.lower()
            if chunk_type in ['hierarchical', 'multi_level']:
                return EmbedderStrategy.MULTI_LEVEL
            elif chunk_type in ['semantic', 'contextual']:
                return EmbedderStrategy.CONTEXTUAL
        
        # Content hints
        if kwargs.get('has_structure', False):
            return EmbedderStrategy.MULTI_LEVEL
        
        if kwargs.get('is_narrative', False):
            return EmbedderStrategy.CONTEXTUAL
        
        # Default to contextual for general use
        return EmbedderStrategy.CONTEXTUAL
    
    @classmethod
    def _create_hybrid_embedder(cls, model_name: str, document_type: Optional[str],
                               chunk_type: Optional[str], **kwargs):
        """
        Tạo hybrid embedder (combination of strategies)
        
        Args:
            model_name: Model name
            document_type: Document type
            chunk_type: Chunk type
            **kwargs: Additional parameters
            
        Returns:
            BaseEmbedder: Hybrid embedder
        """
        # For now, return multi-level embedder as it includes contextual features
        # In future, can implement true hybrid that combines multiple embedders
        return MultiLevelEmbedder(model_name=model_name, **kwargs)
    
    @classmethod
    def _optimize_parameters(cls, strategy: EmbedderStrategy, model_name: str,
                           document_type: Optional[str], chunk_type: Optional[str],
                           **kwargs) -> Dict[str, Any]:
        """
        Optimize parameters cho specific strategy
        
        Args:
            strategy: Embedder strategy
            model_name: Model name
            document_type: Document type
            chunk_type: Chunk type
            **kwargs: Additional parameters
            
        Returns:
            Dict: Optimized parameters
        """
        params = {
            'model_name': model_name,
            **kwargs
        }
        
        # Strategy-specific optimizations
        if strategy == EmbedderStrategy.CONTEXTUAL:
            # Contextual embedder parameters
            if 'context_window' not in params:
                if document_type and document_type.lower() in ['.pdf', 'pdf']:
                    params['context_window'] = 1000  # Larger context for PDFs
                else:
                    params['context_window'] = 500
            
            if 'context_strategy' not in params:
                if chunk_type == 'semantic':
                    params['context_strategy'] = 'surrounding'
                else:
                    params['context_strategy'] = 'preceding'
        
        elif strategy == EmbedderStrategy.MULTI_LEVEL:
            # Multi-level embedder parameters
            if 'levels' not in params:
                if document_type and document_type.lower() in ['.pdf', 'pdf']:
                    params['levels'] = ['sentence', 'paragraph', 'page']
                elif chunk_type == 'hierarchical':
                    params['levels'] = ['sentence', 'paragraph', 'section']
                else:
                    params['levels'] = ['sentence', 'paragraph', 'document']
            
            if 'level_weights' not in params:
                if chunk_type == 'semantic':
                    params['level_weights'] = {
                        'sentence': 0.5,
                        'paragraph': 0.4,
                        'document': 0.1
                    }
                else:
                    params['level_weights'] = {
                        'sentence': 0.3,
                        'paragraph': 0.5,
                        'document': 0.2
                    }
        
        # Model-specific optimizations
        if 'multilingual' in model_name.lower():
            params['batch_size'] = 8  # Smaller batch for multilingual models
        else:
            params['batch_size'] = 16
        
        # Document type optimizations
        if document_type:
            doc_type = document_type.lower()
            if doc_type in ['.xlsx', '.xls']:
                params['context_window'] = params.get('context_window', 200)  # Smaller context for tables
            elif doc_type in ['.pdf', 'pdf']:
                params['max_length'] = 1024  # Longer sequences for PDFs
        
        return params
    
    @classmethod
    def get_recommended_model(cls, language: str = "multilingual", 
                             performance_priority: str = "balanced") -> str:
        """
        Recommend model dựa trên requirements
        
        Args:
            language: Target language (en, vi, multilingual)
            performance_priority: Priority (speed, quality, balanced)
            
        Returns:
            str: Recommended model name
        """
        if language == "vi" or language == "vietnamese":
            # Vietnamese-optimized models
            if performance_priority == "speed":
                return "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            elif performance_priority == "quality":
                return "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
            else:
                return "Qwen/Qwen3-Embedding-0.6B"
        
        elif language == "en" or language == "english":
            # English-optimized models
            if performance_priority == "speed":
                return "Qwen/Qwen3-Embedding-0.6B"
            elif performance_priority == "quality":
                return "Qwen/Qwen3-Embedding-0.6B"
            else:
                return "Qwen/Qwen3-Embedding-0.6B"
        
        else:
            # Multilingual models
            if performance_priority == "speed":
                return "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            elif performance_priority == "quality":
                return "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
            else:
                return "Qwen/Qwen3-Embedding-0.6B"
    
    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """
        Get list of available embedding strategies
        
        Returns:
            List[str]: Strategy names
        """
        return [strategy.value for strategy in EmbedderStrategy]
    
    @classmethod
    def get_strategy_info(cls, strategy: str) -> Dict[str, Any]:
        """
        Get information about specific strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            Dict: Strategy information
        """
        strategy_info = {
            EmbedderStrategy.CONTEXTUAL.value: {
                "name": "Contextual Embedder",
                "description": "Tạo embeddings với context awareness",
                "best_for": ["Flowing text", "Narrative content", "Context-dependent meaning"],
                "parameters": ["context_window", "context_strategy", "context_weight"],
                "pros": ["Better semantic understanding", "Context-aware", "Good for ambiguous text"],
                "cons": ["Slower than basic", "More complex", "Requires more memory"]
            },
            EmbedderStrategy.MULTI_LEVEL.value: {
                "name": "Multi-Level Embedder",
                "description": "Tạo embeddings ở multiple granularity levels",
                "best_for": ["Structured documents", "Hierarchical content", "Complex documents"],
                "parameters": ["levels", "level_weights", "aggregation_method"],
                "pros": ["Rich representation", "Multi-granularity", "Good for complex docs"],
                "cons": ["Most complex", "Slowest", "Highest memory usage"]
            },
            EmbedderStrategy.HYBRID.value: {
                "name": "Hybrid Embedder",
                "description": "Combination of multiple embedding strategies",
                "best_for": ["Mixed content", "Complex requirements", "Best quality"],
                "parameters": ["Various from combined strategies"],
                "pros": ["Best of both worlds", "Flexible", "High quality"],
                "cons": ["Most complex", "Slowest", "Hardest to tune"]
            }
        }
        
        return strategy_info.get(strategy, {})
    
    @classmethod
    def recommend_strategy(cls, 
                          document_type: Optional[str] = None,
                          content_complexity: str = "medium",
                          performance_priority: str = "balanced",
                          has_context: bool = True,
                          **kwargs) -> str:
        """
        Recommend embedding strategy dựa trên requirements
        
        Args:
            document_type: Document type
            content_complexity: Complexity (low, medium, high)
            performance_priority: Priority (speed, quality, balanced)
            has_context: Whether context is available
            **kwargs: Additional hints
            
        Returns:
            str: Recommended strategy
        """
        try:
            # Performance priority decisions
            if performance_priority == "speed":
                return EmbedderStrategy.CONTEXTUAL.value
            
            # Complexity-based decisions
            if content_complexity == "high":
                if has_context:
                    return EmbedderStrategy.MULTI_LEVEL.value
                else:
                    return EmbedderStrategy.CONTEXTUAL.value
            
            elif content_complexity == "low":
                return EmbedderStrategy.CONTEXTUAL.value
            
            # Document type decisions
            if document_type:
                doc_type = document_type.lower()
                if doc_type in ['.pdf', 'pdf']:
                    return EmbedderStrategy.MULTI_LEVEL.value
                elif doc_type in ['.xlsx', '.xls']:
                    return EmbedderStrategy.CONTEXTUAL.value
            
            # Balanced choice
            if performance_priority == "quality":
                return EmbedderStrategy.MULTI_LEVEL.value
            else:
                return EmbedderStrategy.CONTEXTUAL.value
                
        except Exception as e:
            logger.error(f"Error recommending strategy: {str(e)}")
            return EmbedderStrategy.CONTEXTUAL.value
