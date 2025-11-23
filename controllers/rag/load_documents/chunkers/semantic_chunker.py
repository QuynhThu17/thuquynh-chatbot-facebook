"""
Semantic Chunker
Chia chunks dựa trên semantic similarity và sentence transformers
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import spacy
from sklearn.metrics.pairwise import cosine_similarity
import re

from .base_chunker import BaseChunker, ChunkResult, ChunkMetadata, ChunkType
from configs.environment import get_embedding

logger = logging.getLogger(__name__)

class SemanticChunker(BaseChunker):
    """
    Chunker dựa trên semantic similarity
    Sử dụng sentence transformers để tính similarity giữa sentences
    """
    
    def __init__(self, chunk_size: int = 256, overlap: int = 0, 
                 similarity_threshold: float = 0.8,  # Higher threshold for small chunks
                 model_name: str = "Qwen/Qwen3-Embedding-0.6B",
                 use_spacy: bool = True,
                 **kwargs):
        """
        Initialize Semantic Chunker
        
        Args:
            chunk_size: Kích thước chunk mong muốn
            overlap: Overlap giữa các chunk
            similarity_threshold: Ngưỡng similarity để nhóm sentences
            model_name: Tên model sentence transformer
            use_spacy: Có sử dụng spaCy để segment sentences không
        """
        super().__init__(chunk_size, overlap, **kwargs)
        self.similarity_threshold = similarity_threshold
        self.model_name = model_name
        self.use_spacy = use_spacy
        
        # Initialize models
        self._model = None
        self._nlp = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize embedding model và spaCy models"""
        try:
            # Use shared embedding model
            self._model = get_embedding()
            logger.info(f"Using shared embedding model from environment")
            
            # Load spaCy model for better sentence segmentation
            if self.use_spacy:
                try:
                    # Try Vietnamese model first
                    self._nlp = spacy.load("vi_core_news_sm")
                    logger.info("Loaded Vietnamese spaCy model")
                except OSError:
                    try:
                        # Fallback to English model
                        self._nlp = spacy.load("en_core_web_sm")
                        logger.info("Loaded English spaCy model")
                    except OSError:
                        logger.warning("No spaCy model found, using regex for sentence segmentation")
                        self._nlp = None
                        self.use_spacy = False
                        
        except Exception as e:
            logger.error(f"Error initializing models: {str(e)}")
            self._model = None
            self._nlp = None
    
    def get_chunk_type(self) -> ChunkType:
        """Return chunk type"""
        return ChunkType.SEMANTIC
    
    async def chunk_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkResult]:
        """
        Chia text thành semantic chunks
        
        Args:
            text: Text cần chia
            document_metadata: Metadata của document
            
        Returns:
            List[ChunkResult]: Danh sách semantic chunks
        """
        if not self.validate_text(text):
            return []
        
        # Clean text
        text = self.clean_text(text)
        
        try:
            # 1. Segment text thành sentences
            sentences = await self._segment_sentences(text)
            
            if len(sentences) <= 1:
                # Nếu chỉ có 1 sentence, return as single chunk
                metadata = ChunkMetadata(
                    chunk_index=0,
                    chunk_type=self.get_chunk_type(),
                    start_position=0,
                    end_position=len(text),
                    length=len(text),
                    semantic_similarity=1.0
                )
                return [ChunkResult(content=text, metadata=metadata)]
            
            # 2. Tính embeddings cho sentences
            sentence_embeddings = await self._get_sentence_embeddings(sentences)
            
            # 3. Group sentences dựa trên semantic similarity
            sentence_groups = await self._group_sentences_by_similarity(
                sentences, sentence_embeddings
            )
            
            # 4. Tạo chunks từ sentence groups
            chunks = await self._create_chunks_from_groups(
                sentence_groups, text, document_metadata
            )
            
            # 5. Post-process chunks
            chunks = await self.post_process_chunks(chunks)
            
            logger.info(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in semantic chunking: {str(e)}")
            # Fallback to simple chunking
            return await self._fallback_chunking(text, document_metadata)
    
    async def _segment_sentences(self, text: str) -> List[Dict[str, Any]]:
        """
        Segment text thành sentences với position info
        
        Args:
            text: Text cần segment
            
        Returns:
            List[Dict]: Sentences với start/end positions
        """
        sentences = []
        
        if self.use_spacy and self._nlp:
            # Use spaCy for better sentence segmentation
            doc = self._nlp(text)
            for sent in doc.sents:
                sentence_text = sent.text.strip()
                if sentence_text:
                    sentences.append({
                        'text': sentence_text,
                        'start': sent.start_char,
                        'end': sent.end_char
                    })
        else:
            # Fallback to regex-based segmentation
            # Improved regex for Vietnamese and English
            sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ])'
            
            parts = re.split(sentence_pattern, text)
            start_pos = 0
            
            for part in parts:
                part = part.strip()
                if part:
                    end_pos = start_pos + len(part)
                    sentences.append({
                        'text': part,
                        'start': start_pos,
                        'end': end_pos
                    })
                    start_pos = text.find(part, start_pos) + len(part)
        
        return sentences
    
    async def _get_sentence_embeddings(self, sentences: List[Dict[str, Any]]) -> np.ndarray:
        """
        Tính embeddings cho sentences
        
        Args:
            sentences: Danh sách sentences
            
        Returns:
            np.ndarray: Sentence embeddings
        """
        if not self._model:
            raise ValueError("Sentence transformer model not initialized")
        
        sentence_texts = [s['text'] for s in sentences]
        
        # Encode sentences in batches to avoid memory issues
        batch_size = 32
        embeddings = []
        
        for i in range(0, len(sentence_texts), batch_size):
            batch = sentence_texts[i:i + batch_size]
            # Use OpenAI embeddings
            batch_embeddings = self._model.embed_documents(batch)
            embeddings.append(np.array(batch_embeddings))
        
        return np.vstack(embeddings)
    
    async def _group_sentences_by_similarity(self, 
                                           sentences: List[Dict[str, Any]], 
                                           embeddings: np.ndarray) -> List[List[int]]:
        """
        Nhóm sentences dựa trên semantic similarity
        
        Args:
            sentences: Danh sách sentences
            embeddings: Sentence embeddings
            
        Returns:
            List[List[int]]: Groups of sentence indices
        """
        if len(sentences) <= 1:
            return [[0]] if sentences else []
        
        # Tính cosine similarity matrix
        similarity_matrix = cosine_similarity(embeddings)
        
        # Group sentences using sliding window approach
        groups = []
        current_group = [0]
        
        for i in range(1, len(sentences)):
            # Tính similarity với sentences trong group hiện tại
            group_similarities = [similarity_matrix[i][j] for j in current_group]
            avg_similarity = np.mean(group_similarities)
            
            # Kiểm tra kích thước group hiện tại
            current_group_size = sum(len(sentences[j]['text']) for j in current_group)
            
            # Quyết định có thêm vào group hiện tại hay tạo group mới
            # For small chunk sizes, be more strict about size limits
            max_group_size = self.chunk_size * 1.1 if self.chunk_size <= 300 else self.chunk_size * 1.2
            if (avg_similarity >= self.similarity_threshold and 
                current_group_size + len(sentences[i]['text']) <= max_group_size):
                current_group.append(i)
            else:
                # Kết thúc group hiện tại và bắt đầu group mới
                groups.append(current_group)
                current_group = [i]
        
        # Thêm group cuối cùng
        if current_group:
            groups.append(current_group)
        
        # Merge các group quá nhỏ với group kế bên
        groups = self._merge_small_groups(groups, sentences)
        
        return groups
    
    def _merge_small_groups(self, groups: List[List[int]], 
                           sentences: List[Dict[str, Any]]) -> List[List[int]]:
        """
        Merge các group quá nhỏ với group kế bên
        
        Args:
            groups: Original groups
            sentences: Sentences data
            
        Returns:
            List[List[int]]: Merged groups
        """
        if len(groups) <= 1:
            return groups
        
        # For small chunk sizes, use higher minimum ratio
        min_ratio = 0.4 if self.chunk_size <= 300 else 0.25
        min_chunk_size = int(self.chunk_size * min_ratio)  # Higher minimum for small chunks
        merged_groups = []
        i = 0
        
        while i < len(groups):
            current_group = groups[i]
            current_size = sum(len(sentences[j]['text']) for j in current_group)
            
            # Nếu group quá nhỏ và có group tiếp theo
            if current_size < min_chunk_size and i + 1 < len(groups):
                next_group = groups[i + 1]
                next_size = sum(len(sentences[j]['text']) for j in next_group)
                
                # Merge nếu tổng size không vượt quá ngưỡng
                if current_size + next_size <= self.chunk_size * 1.5:
                    merged_groups.append(current_group + next_group)
                    i += 2  # Skip next group vì đã merge
                    continue
            
            merged_groups.append(current_group)
            i += 1
        
        return merged_groups
    
    async def _create_chunks_from_groups(self, 
                                       groups: List[List[int]], 
                                       original_text: str,
                                       document_metadata: Optional[Dict[str, Any]]) -> List[ChunkResult]:
        """
        Tạo chunks từ sentence groups
        
        Args:
            groups: Sentence groups
            original_text: Text gốc
            document_metadata: Document metadata
            
        Returns:
            List[ChunkResult]: Chunks
        """
        sentences = await self._segment_sentences(original_text)
        chunks = []
        
        for chunk_index, group in enumerate(groups):
            # Combine sentences trong group
            group_sentences = [sentences[i] for i in group]
            
            # Tính start và end position
            start_pos = group_sentences[0]['start']
            end_pos = group_sentences[-1]['end']
            
            # Extract chunk content
            chunk_content = original_text[start_pos:end_pos].strip()
            
            # Tính average semantic similarity cho group
            if len(group) > 1 and self._model:
                group_texts = [sentences[i]['text'] for i in group]
                group_embeddings = self._model.embed_documents(group_texts)
                group_embeddings = np.array(group_embeddings)
                similarity_matrix = cosine_similarity(group_embeddings)
                
                # Tính average similarity (exclude diagonal)
                similarities = []
                for i in range(len(similarity_matrix)):
                    for j in range(i + 1, len(similarity_matrix)):
                        similarities.append(similarity_matrix[i][j])
                
                avg_similarity = np.mean(similarities) if similarities else 1.0
            else:
                avg_similarity = 1.0
            
            # Extract topic từ first sentence (simplified)
            topic = await self._extract_topic(chunk_content)
            
            # Tạo metadata
            metadata = ChunkMetadata(
                chunk_index=chunk_index,
                chunk_type=self.get_chunk_type(),
                start_position=start_pos,
                end_position=end_pos,
                length=len(chunk_content),
                semantic_similarity=avg_similarity,
                topic=topic
            )
            
            # Add document-specific metadata
            if document_metadata:
                metadata.page_number = document_metadata.get('page_number')
                metadata.section_title = document_metadata.get('section_title')
            
            chunks.append(ChunkResult(content=chunk_content, metadata=metadata))
        
        return chunks
    
    async def _extract_topic(self, text: str) -> Optional[str]:
        """
        Extract topic từ text (simplified approach)
        
        Args:
            text: Text cần extract topic
            
        Returns:
            str: Topic string
        """
        try:
            # Simple topic extraction based on first sentence keywords
            sentences = text.split('.')
            if sentences:
                first_sentence = sentences[0].strip()
                keywords = self.extract_keywords(first_sentence, max_keywords=3)
                if keywords:
                    return ' '.join(keywords[:2])  # Top 2 keywords as topic
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting topic: {str(e)}")
            return None
    
    async def _fallback_chunking(self, text: str, 
                               document_metadata: Optional[Dict[str, Any]]) -> List[ChunkResult]:
        """
        Fallback chunking method khi semantic chunking fails
        
        Args:
            text: Text cần chunk
            document_metadata: Document metadata
            
        Returns:
            List[ChunkResult]: Basic chunks
        """
        logger.warning("Using fallback chunking method")
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            
            # Find good break point
            if end < len(text):
                # Look for sentence boundary within last 100 chars
                search_start = max(end - 100, start)
                for i in range(end, search_start, -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk_content = text[start:end].strip()
            
            if chunk_content:
                metadata = ChunkMetadata(
                    chunk_index=chunk_index,
                    chunk_type=ChunkType.FIXED_SIZE,
                    start_position=start,
                    end_position=end,
                    length=len(chunk_content),
                    semantic_similarity=0.5  # Default value
                )
                
                chunks.append(ChunkResult(content=chunk_content, metadata=metadata))
                chunk_index += 1
            
            start = end - self.overlap if end > self.overlap else end
        
        return chunks
