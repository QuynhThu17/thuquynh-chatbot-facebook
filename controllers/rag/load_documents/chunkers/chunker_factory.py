"""
Chunker Factory
Factory để tạo và quản lý các chunker strategies
"""

import logging
from typing import Dict, Any, Optional, Type, List
from enum import Enum

from .base_chunker import BaseChunker, ChunkType
from .semantic_chunker import SemanticChunker
from .recursive_chunker import RecursiveCharacterTextSplitter
from .hierarchical_chunker import HierarchicalChunker
from .adaptive_chunker import AdaptiveChunker

logger = logging.getLogger(__name__)

class ChunkerStrategy(Enum):
    """Available chunker strategies"""
    SEMANTIC = "semantic"
    RECURSIVE = "recursive"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"
    AUTO = "auto"  # Let factory decide

class ChunkerFactory:
    """
    Factory để tạo chunkers với configuration linh hoạt
    """
    
    # Mapping strategy names to chunker classes
    CHUNKER_CLASSES: Dict[ChunkerStrategy, Type[BaseChunker]] = {
        ChunkerStrategy.SEMANTIC: SemanticChunker,
        ChunkerStrategy.RECURSIVE: RecursiveCharacterTextSplitter,
        ChunkerStrategy.HIERARCHICAL: HierarchicalChunker,
        ChunkerStrategy.ADAPTIVE: AdaptiveChunker
    }
    
    @classmethod
    def create_chunker(cls, 
                      strategy: str = "adaptive",
                      chunk_size: int = 1000,
                      overlap: int = 200,
                      document_type: Optional[str] = None,
                      **kwargs) -> BaseChunker:
        """
        Tạo chunker với strategy và config cụ thể
        
        Args:
            strategy: Chunker strategy name
            chunk_size: Chunk size
            overlap: Overlap size
            document_type: Document type hint (.pdf, .docx, etc.)
            **kwargs: Additional parameters for specific chunkers
            
        Returns:
            BaseChunker: Configured chunker instance
        """
        try:
            # Convert string to enum
            if isinstance(strategy, str):
                strategy_enum = ChunkerStrategy(strategy.lower())
            else:
                strategy_enum = strategy
            
            # Auto-select strategy based on document type if requested
            if strategy_enum == ChunkerStrategy.AUTO:
                strategy_enum = cls._auto_select_strategy(document_type, **kwargs)
            
            # Get chunker class
            chunker_class = cls.CHUNKER_CLASSES.get(strategy_enum)
            if not chunker_class:
                logger.warning(f"Unknown strategy {strategy}, using adaptive")
                chunker_class = AdaptiveChunker
            
            # Create chunker instance with optimized parameters
            optimized_params = cls._optimize_parameters(
                strategy_enum, chunk_size, overlap, document_type, **kwargs
            )
            
            chunker = chunker_class(**optimized_params)
            logger.info(f"Created {chunker_class.__name__} with params: {optimized_params}")
            
            return chunker
            
        except Exception as e:
            logger.error(f"Error creating chunker: {str(e)}")
            # Fallback to adaptive chunker
            return AdaptiveChunker(chunk_size=chunk_size, overlap=overlap)
    
    @classmethod
    def _auto_select_strategy(cls, document_type: Optional[str], **kwargs) -> ChunkerStrategy:
        """
        Tự động chọn strategy dựa trên document type và hints
        
        Args:
            document_type: Document type
            **kwargs: Additional hints
            
        Returns:
            ChunkerStrategy: Selected strategy
        """
        if not document_type:
            return ChunkerStrategy.ADAPTIVE
        
        doc_type = document_type.lower()
        
        # PDF documents often have clear structure
        if doc_type in ['.pdf', 'pdf']:
            return ChunkerStrategy.HIERARCHICAL
        
        # Word documents often have flowing narrative text
        elif doc_type in ['.docx', '.doc', 'docx', 'doc', 'word']:
            return ChunkerStrategy.SEMANTIC
        
        # Excel documents need structured splitting
        elif doc_type in ['.xlsx', '.xls', 'xlsx', 'xls', 'excel']:
            return ChunkerStrategy.RECURSIVE
        
        # Text files - depends on content
        elif doc_type in ['.txt', 'txt', 'text']:
            # Check for structure hints
            if kwargs.get('has_headers', False) or kwargs.get('has_sections', False):
                return ChunkerStrategy.HIERARCHICAL
            else:
                return ChunkerStrategy.SEMANTIC
        
        # Default to adaptive for unknown types
        else:
            return ChunkerStrategy.ADAPTIVE
    
    @classmethod
    def _optimize_parameters(cls, 
                           strategy: ChunkerStrategy,
                           chunk_size: int,
                           overlap: int,
                           document_type: Optional[str],
                           **kwargs) -> Dict[str, Any]:
        """
        Optimize parameters cho specific strategy và document type
        
        Args:
            strategy: Chunker strategy
            chunk_size: Base chunk size
            overlap: Base overlap
            document_type: Document type
            **kwargs: Additional parameters
            
        Returns:
            Dict: Optimized parameters
        """
        params = {
            'chunk_size': chunk_size,
            'overlap': overlap,
            **kwargs
        }
        
        # Document type specific optimizations
        if document_type:
            doc_type = document_type.lower()
            
            if doc_type in ['.pdf', 'pdf']:
                # PDFs benefit from larger chunks to capture page context
                params['chunk_size'] = max(chunk_size, 1500)
                params['overlap'] = max(overlap, 300)
            
            elif doc_type in ['.xlsx', '.xls', 'xlsx', 'xls']:
                # Excel needs smaller chunks for tables
                params['chunk_size'] = min(chunk_size, 800)
                params['overlap'] = min(overlap, 100)
        
        # Strategy specific optimizations
        if strategy == ChunkerStrategy.SEMANTIC:
            # Semantic chunking parameters
            if 'similarity_threshold' not in params:
                params['similarity_threshold'] = 0.7
            if 'model_name' not in params:
                params['model_name'] = "Qwen/Qwen3-Embedding-0.6B"
        
        elif strategy == ChunkerStrategy.RECURSIVE:
            # Recursive chunking separators
            if 'separators' not in params:
                # Optimized separators for Vietnamese and English
                params['separators'] = [
                    "\n\n\n",  # Multiple line breaks
                    "\n\n",    # Paragraph breaks
                    "\n",      # Line breaks
                    ". ",      # Sentence endings
                    "! ",      # Exclamation
                    "? ",      # Question
                    "; ",      # Semicolon
                    ", ",      # Comma
                    " ",       # Space
                    ""         # Character level
                ]
        
        elif strategy == ChunkerStrategy.HIERARCHICAL:
            # Hierarchical chunking levels
            if 'levels' not in params:
                doc_type = document_type.lower() if document_type else None
                params['levels'] = cls._get_optimized_levels(chunk_size, doc_type)
        
        return params
    
    @classmethod
    def _get_optimized_levels(cls, base_chunk_size: int, doc_type: Optional[str]) -> List[Dict[str, Any]]:
        """
        Get optimized hierarchical levels cho document type
        
        Args:
            base_chunk_size: Base chunk size
            doc_type: Document type
            
        Returns:
            List[Dict]: Level configurations
        """
        if doc_type and doc_type.lower() in ['.pdf', 'pdf']:
            # PDF-optimized levels
            return [
                {
                    'name': 'page',
                    'chunk_size': base_chunk_size * 6,
                    'separators': ['\f', '\n\n\n'],  # Form feed, multiple line breaks
                    'min_chunk_size': base_chunk_size * 2
                },
                {
                    'name': 'section',
                    'chunk_size': base_chunk_size * 3,
                    'separators': ['\n\n'],  # Paragraph breaks
                    'min_chunk_size': base_chunk_size
                },
                {
                    'name': 'paragraph',
                    'chunk_size': base_chunk_size,
                    'separators': ['. ', '! ', '? '],  # Sentence breaks
                    'min_chunk_size': base_chunk_size // 2
                }
            ]
        
        elif doc_type and doc_type.lower() in ['.docx', '.doc', 'docx', 'doc']:
            # Word document-optimized levels
            return [
                {
                    'name': 'chapter',
                    'chunk_size': base_chunk_size * 8,
                    'separators': ['\n\n\n', '\f'],
                    'min_chunk_size': base_chunk_size * 3
                },
                {
                    'name': 'section',
                    'chunk_size': base_chunk_size * 4,
                    'separators': ['\n\n'],
                    'min_chunk_size': base_chunk_size
                },
                {
                    'name': 'paragraph',
                    'chunk_size': base_chunk_size,
                    'separators': ['. ', '! ', '? '],
                    'min_chunk_size': base_chunk_size // 2
                }
            ]
        
        else:
            # Default levels
            return [
                {
                    'name': 'document',
                    'chunk_size': base_chunk_size * 8,
                    'separators': ['\n\n\n', '\f'],
                    'min_chunk_size': base_chunk_size * 2
                },
                {
                    'name': 'section',
                    'chunk_size': base_chunk_size * 4,
                    'separators': ['\n\n'],
                    'min_chunk_size': base_chunk_size
                },
                {
                    'name': 'paragraph',
                    'chunk_size': base_chunk_size,
                    'separators': ['. ', '! ', '? '],
                    'min_chunk_size': base_chunk_size // 2
                }
            ]
    
    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """
        Get list of available chunking strategies
        
        Returns:
            List[str]: Strategy names
        """
        return [strategy.value for strategy in ChunkerStrategy]
    
    @classmethod
    def get_strategy_info(cls, strategy: str) -> Dict[str, Any]:
        """
        Get information about a specific strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            Dict: Strategy information
        """
        strategy_info = {
            ChunkerStrategy.SEMANTIC.value: {
                "name": "Semantic Chunking",
                "description": "Chia chunks dựa trên semantic similarity giữa sentences",
                "best_for": ["Văn bản narrative", "Articles", "Stories", "Flowing text"],
                "parameters": ["similarity_threshold", "model_name", "use_spacy"],
                "pros": ["Giữ được semantic coherence", "Intelligent boundaries"],
                "cons": ["Slower", "Requires models", "More memory"]
            },
            ChunkerStrategy.RECURSIVE.value: {
                "name": "Recursive Character Text Splitter", 
                "description": "Chia chunks theo hierarchy separators để giữ structure",
                "best_for": ["Structured text", "Code", "Tables", "Lists"],
                "parameters": ["separators", "keep_separator"],
                "pros": ["Fast", "Preserves structure", "Customizable"],
                "cons": ["May break semantic boundaries", "Less intelligent"]
            },
            ChunkerStrategy.HIERARCHICAL.value: {
                "name": "Hierarchical Chunking",
                "description": "Tạo multi-level chunks với parent-child relationships",
                "best_for": ["PDFs", "Books", "Long documents", "Structured content"],
                "parameters": ["levels"],
                "pros": ["Multi-level context", "Great for navigation", "Preserves hierarchy"],
                "cons": ["Complex", "More chunks", "Harder to tune"]
            },
            ChunkerStrategy.ADAPTIVE.value: {
                "name": "Adaptive Chunking",
                "description": "Tự động chọn strategy tốt nhất dựa trên content analysis",
                "best_for": ["Mixed content", "Unknown document types", "General purpose"],
                "parameters": ["All parameters from other strategies"],
                "pros": ["Intelligent selection", "Versatile", "Self-optimizing"],
                "cons": ["More complex", "May not be optimal for specific cases"]
            }
        }
        
        return strategy_info.get(strategy, {})
    
    @classmethod
    def recommend_strategy(cls, 
                          document_type: Optional[str] = None,
                          content_length: Optional[int] = None,
                          has_structure: bool = False,
                          is_narrative: bool = False,
                          **kwargs) -> str:
        """
        Recommend chunking strategy dựa trên document characteristics
        
        Args:
            document_type: Document type
            content_length: Content length
            has_structure: Has clear structure (headers, sections)
            is_narrative: Is narrative/flowing text
            **kwargs: Additional hints
            
        Returns:
            str: Recommended strategy
        """
        try:
            # Quick decisions based on clear indicators
            if document_type:
                doc_type = document_type.lower()
                if doc_type in ['.xlsx', '.xls']:
                    return ChunkerStrategy.RECURSIVE.value
                elif doc_type in ['.pdf'] and has_structure:
                    return ChunkerStrategy.HIERARCHICAL.value
            
            # Content-based decisions
            if content_length:
                if content_length > 50000 and has_structure:
                    return ChunkerStrategy.HIERARCHICAL.value
                elif content_length < 5000 and not has_structure:
                    return ChunkerStrategy.RECURSIVE.value
            
            # Text type decisions
            if is_narrative and not has_structure:
                return ChunkerStrategy.SEMANTIC.value
            elif has_structure and not is_narrative:
                return ChunkerStrategy.HIERARCHICAL.value
            
            # Default to adaptive for uncertain cases
            return ChunkerStrategy.ADAPTIVE.value
            
        except Exception as e:
            logger.error(f"Error recommending strategy: {str(e)}")
            return ChunkerStrategy.ADAPTIVE.value
