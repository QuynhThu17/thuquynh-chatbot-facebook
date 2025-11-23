"""
Base Chunker Interface
Interface cơ bản cho tất cả các chunker strategies
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ChunkType(Enum):
    """Loại chunk"""
    SEMANTIC = "semantic"
    FIXED_SIZE = "fixed_size" 
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SECTION = "section"
    PAGE = "page"
    HIERARCHICAL = "hierarchical"
    ADAPTIVE = "adaptive"

@dataclass
class ChunkMetadata:
    """Metadata cho mỗi chunk"""
    chunk_index: int
    chunk_type: ChunkType
    start_position: int
    end_position: int
    length: int
    token_count: Optional[int] = None
    
    # Semantic metadata
    semantic_similarity: Optional[float] = None
    topic: Optional[str] = None
    section_title: Optional[str] = None
    
    # Hierarchical metadata
    parent_chunk_id: Optional[str] = None
    child_chunk_ids: Optional[List[str]] = None
    level: Optional[int] = None
    
    # Document-specific metadata
    page_number: Optional[int] = None
    sheet_name: Optional[str] = None
    table_info: Optional[Dict[str, Any]] = None
    
    # Context metadata
    preceding_context: Optional[str] = None
    following_context: Optional[str] = None
    
    # Quality metrics
    coherence_score: Optional[float] = None
    completeness_score: Optional[float] = None
    
    # Additional metadata
    keywords: Optional[List[str]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    language: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'chunk_index': self.chunk_index,
            'chunk_type': self.chunk_type.value,
            'start_position': self.start_position,
            'end_position': self.end_position,
            'length': self.length,
            'token_count': self.token_count,
            'semantic_similarity': self.semantic_similarity,
            'topic': self.topic,
            'section_title': self.section_title,
            'parent_chunk_id': self.parent_chunk_id,
            'child_chunk_ids': self.child_chunk_ids,
            'level': self.level,
            'page_number': self.page_number,
            'sheet_name': self.sheet_name,
            'table_info': self.table_info,
            'preceding_context': self.preceding_context,
            'following_context': self.following_context,
            'coherence_score': self.coherence_score,
            'completeness_score': self.completeness_score,
            'keywords': self.keywords,
            'entities': self.entities,
            'language': self.language
        }

@dataclass 
class ChunkResult:
    """Kết quả chunking"""
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'content': self.content,
            'metadata': self.metadata.to_dict(),
            'embedding': self.embedding
        }

class BaseChunker(ABC):
    """
    Abstract base class cho tất cả chunker strategies
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200, **kwargs):
        """
        Initialize chunker
        
        Args:
            chunk_size: Kích thước chunk mong muốn
            overlap: Overlap giữa các chunk
            **kwargs: Additional parameters cho specific chunkers
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.config = kwargs
        logger.info(f"Initialized {self.__class__.__name__} with chunk_size={chunk_size}, overlap={overlap}")
    
    @abstractmethod
    async def chunk_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkResult]:
        """
        Chia text thành chunks
        
        Args:
            text: Text cần chia
            document_metadata: Metadata của document
            
        Returns:
            List[ChunkResult]: Danh sách chunks
        """
        pass
    
    @abstractmethod
    def get_chunk_type(self) -> ChunkType:
        """
        Lấy loại chunk của chunker này
        
        Returns:
            ChunkType: Loại chunk
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
            
        return True
    
    def clean_text(self, text: str) -> str:
        """
        Clean và normalize text
        
        Args:
            text: Text cần clean
            
        Returns:
            str: Text đã clean
        """
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove zero-width characters
        text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)
        
        return text.strip()
    
    def calculate_token_count(self, text: str) -> int:
        """
        Ước tính số token trong text
        
        Args:
            text: Text cần đếm
            
        Returns:
            int: Số token ước tính
        """
        # Rough estimation: 1 token ≈ 4 characters for English
        # Adjust for Vietnamese and other languages
        return len(text) // 3  # More conservative for Vietnamese
    
    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        Extract keywords từ text
        
        Args:
            text: Text cần extract keywords
            max_keywords: Số keywords tối đa
            
        Returns:
            List[str]: Danh sách keywords
        """
        try:
            import re
            from collections import Counter
            
            # Simple keyword extraction
            # Remove punctuation and convert to lowercase
            words = re.findall(r'\b\w+\b', text.lower())
            
            # Filter out common stop words (basic Vietnamese and English)
            stop_words = {
                'và', 'của', 'là', 'có', 'được', 'với', 'cho', 'trong', 'từ', 'về', 'này', 'đó',
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'
            }
            
            words = [w for w in words if w not in stop_words and len(w) > 2]
            
            # Get most common words
            word_counts = Counter(words)
            keywords = [word for word, count in word_counts.most_common(max_keywords)]
            
            return keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return []
    
    def detect_language(self, text: str) -> str:
        """
        Detect language của text
        
        Args:
            text: Text cần detect
            
        Returns:
            str: Language code (vi, en, etc.)
        """
        try:
            # Simple Vietnamese detection
            vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
            
            vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)
            vietnamese_ratio = vietnamese_count / len(text) if text else 0
            
            if vietnamese_ratio > 0.01:  # If more than 1% Vietnamese characters
                return 'vi'
            else:
                return 'en'
                
        except Exception as e:
            logger.error(f"Error detecting language: {str(e)}")
            return 'en'
    
    def add_context(self, chunks: List[ChunkResult], context_size: int = 100) -> List[ChunkResult]:
        """
        Thêm context cho các chunks
        
        Args:
            chunks: Danh sách chunks
            context_size: Kích thước context
            
        Returns:
            List[ChunkResult]: Chunks với context
        """
        if len(chunks) <= 1:
            return chunks
        
        for i, chunk in enumerate(chunks):
            # Add preceding context
            if i > 0:
                prev_chunk = chunks[i-1]
                chunk.metadata.preceding_context = prev_chunk.content[-context_size:]
            
            # Add following context  
            if i < len(chunks) - 1:
                next_chunk = chunks[i+1]
                chunk.metadata.following_context = next_chunk.content[:context_size]
        
        return chunks
    
    async def post_process_chunks(self, chunks: List[ChunkResult]) -> List[ChunkResult]:
        """
        Post-process chunks sau khi chunking
        
        Args:
            chunks: Raw chunks
            
        Returns:
            List[ChunkResult]: Processed chunks
        """
        # Add context
        chunks = self.add_context(chunks)
        
        # Calculate quality metrics
        for chunk in chunks:
            chunk.metadata.token_count = self.calculate_token_count(chunk.content)
            chunk.metadata.keywords = self.extract_keywords(chunk.content)
            chunk.metadata.language = self.detect_language(chunk.content)
            
            # Simple coherence score based on sentence count and length variation
            sentences = chunk.content.split('.')
            sentence_lengths = [len(s.strip()) for s in sentences if s.strip()]
            
            if sentence_lengths:
                # Coherence based on length consistency
                mean_length = sum(sentence_lengths) / len(sentence_lengths)
                variance = sum((l - mean_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)
                chunk.metadata.coherence_score = 1.0 / (1.0 + variance / (mean_length ** 2))
            else:
                chunk.metadata.coherence_score = 0.5
        
        return chunks
