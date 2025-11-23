"""
Enhanced Document Loading and Processing System for RAG
Hệ thống đọc và xử lý đa dạng các loại file với RAG capabilities tiên tiến:

- Advanced Chunking: Semantic, Hierarchical, Adaptive chunking strategies
- Context-Aware Embeddings: Multi-level và contextual embeddings  
- Intelligent Processing: Auto-optimization based on document analysis
- Flexible Architecture: Modular design với factory patterns

Components:
- chunkers/: Advanced chunking strategies (semantic, hierarchical, adaptive)
- embedders/: Context-aware và multi-level embedding systems
- processors/: Document processors for different file types
- services/: Main services (DocumentLoaderService, EnhancedRAGService)
- storage/: Storage services (S3, local)
"""

# Main services
from .services import DocumentLoaderService, RAGService

# Chunking system
from .chunkers import (
    ChunkerFactory, BaseChunker, ChunkResult, ChunkMetadata,
    SemanticChunker, RecursiveCharacterTextSplitter, 
    HierarchicalChunker, AdaptiveChunker
)

# Embedding system  
from .embedders import (
    EmbedderFactory, BaseEmbedder, EmbeddingResult, EmbeddingMetadata,
    ContextualEmbedder, MultiLevelEmbedder
)

# Document processors
from .processors import (
    BaseDocumentProcessor, DocumentContent, ProcessedChunk,
    PDFProcessor, DocProcessor, ExcelProcessor
)

# Storage services
from .storage import S3Service

# Utilities
from .utils import DocumentUtils

__all__ = [
    # Main services
    'DocumentLoaderService',
    'RAGService',
    
    # Chunking system
    'ChunkerFactory',
    'BaseChunker', 
    'ChunkResult',
    'ChunkMetadata',
    'SemanticChunker',
    'RecursiveCharacterTextSplitter',
    'HierarchicalChunker', 
    'AdaptiveChunker',
    
    # Embedding system
    'EmbedderFactory',
    'BaseEmbedder',
    'EmbeddingResult',
    'EmbeddingMetadata', 
    'ContextualEmbedder',
    'MultiLevelEmbedder',
    
    # Document processors
    'BaseDocumentProcessor',
    'DocumentContent',
    'ProcessedChunk',
    'PDFProcessor',
    'DocProcessor', 
    'ExcelProcessor',
    
    # Storage
    'S3Service',
    
    # Utilities
    'DocumentUtils'
]
