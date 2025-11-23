"""
Adaptive Chunker
Chunker thích ứng dựa trên document type và content characteristics
"""

import logging
from typing import List, Dict, Any, Optional, Union
import re

from .base_chunker import BaseChunker, ChunkResult, ChunkMetadata, ChunkType
from .semantic_chunker import SemanticChunker
from .recursive_chunker import RecursiveCharacterTextSplitter
from .hierarchical_chunker import HierarchicalChunker

logger = logging.getLogger(__name__)

class AdaptiveChunker(BaseChunker):
    """
    Adaptive chunker tự động chọn strategy tốt nhất dựa trên:
    - Document type (.pdf, .docx, .xlsx)
    - Content characteristics (structured vs unstructured)
    - Text properties (length, language, complexity)
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200, **kwargs):
        """
        Initialize Adaptive Chunker
        
        Args:
            chunk_size: Base chunk size
            overlap: Base overlap
        """
        super().__init__(chunk_size, overlap, **kwargs)
        
        # Initialize chunkers
        self.semantic_chunker = SemanticChunker(chunk_size, overlap, **kwargs)
        self.recursive_chunker = RecursiveCharacterTextSplitter(chunk_size, overlap, **kwargs)
        self.hierarchical_chunker = HierarchicalChunker(chunk_size, overlap, **kwargs)
        
        # Strategy weights
        self.strategy_weights = {
            'semantic': 0.0,
            'recursive': 0.0,
            'hierarchical': 0.0,
            'hybrid': 0.0
        }
    
    def get_chunk_type(self) -> ChunkType:
        """Return chunk type"""
        return ChunkType.ADAPTIVE
    
    async def chunk_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkResult]:
        """
        Adaptive chunking - chọn strategy tốt nhất
        
        Args:
            text: Text cần chia
            document_metadata: Metadata của document
            
        Returns:
            List[ChunkResult]: Danh sách chunks
        """
        if not self.validate_text(text):
            return []
        
        try:
            # Analyze content để chọn strategy
            content_analysis = await self._analyze_content(text, document_metadata)
            
            # Chọn chunking strategy
            strategy = await self._select_strategy(content_analysis)
            
            # Apply chunking strategy
            chunks = await self._apply_strategy(text, strategy, document_metadata, content_analysis)
            
            # Post-process và optimize
            chunks = await self._optimize_chunks(chunks, content_analysis)
            
            # Update metadata với strategy info
            for chunk in chunks:
                chunk.metadata.topic = f"adaptive_{strategy}"
            
            logger.info(f"Adaptive chunking used '{strategy}' strategy, created {len(chunks)} chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in adaptive chunking: {str(e)}")
            # Fallback to recursive chunking
            return await self.recursive_chunker.chunk_text(text, document_metadata)
    
    async def _analyze_content(self, text: str, document_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze content characteristics
        
        Args:
            text: Text để analyze
            document_metadata: Document metadata
            
        Returns:
            Dict: Content analysis results
        """
        analysis = {
            'length': len(text),
            'word_count': len(text.split()),
            'line_count': len(text.split('\n')),
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
            'sentence_count': len(re.findall(r'[.!?]+', text)),
            'language': self.detect_language(text),
            'document_type': None,
            'structure_score': 0.0,
            'complexity_score': 0.0,
            'semantic_coherence': 0.0,
            'table_count': 0,
            'list_count': 0,
            'header_count': 0
        }
        
        # Document type từ metadata
        if document_metadata:
            file_name = document_metadata.get('file_name', '')
            if file_name:
                if file_name.endswith(('.pdf', '.PDF')):
                    analysis['document_type'] = 'pdf'
                elif file_name.endswith(('.docx', '.doc', '.DOCX', '.DOC')):
                    analysis['document_type'] = 'word'
                elif file_name.endswith(('.xlsx', '.xls', '.XLSX', '.XLS')):
                    analysis['document_type'] = 'excel'
                else:
                    analysis['document_type'] = 'text'
        
        # Structure analysis
        analysis.update(await self._analyze_structure(text))
        
        # Complexity analysis
        analysis.update(await self._analyze_complexity(text))
        
        # Semantic analysis (if possible)
        analysis.update(await self._analyze_semantics(text))
        
        return analysis
    
    async def _analyze_structure(self, text: str) -> Dict[str, Any]:
        """
        Analyze text structure
        
        Args:
            text: Text để analyze
            
        Returns:
            Dict: Structure metrics
        """
        structure_metrics = {
            'structure_score': 0.0,
            'table_count': 0,
            'list_count': 0,
            'header_count': 0,
            'has_toc': False,
            'section_consistency': 0.0
        }
        
        try:
            lines = text.split('\n')
            
            # Count tables (simple detection)
            table_patterns = [r'\|.*\|', r'\t.*\t', r'┌.*┐', r'├.*┤']
            table_lines = 0
            for line in lines:
                for pattern in table_patterns:
                    if re.search(pattern, line):
                        table_lines += 1
                        break
            structure_metrics['table_count'] = table_lines
            
            # Count lists
            list_patterns = [r'^\s*[-*+]\s', r'^\s*\d+\.\s', r'^\s*[a-zA-Z]\.\s']
            list_lines = 0
            for line in lines:
                for pattern in list_patterns:
                    if re.search(pattern, line):
                        list_lines += 1
                        break
            structure_metrics['list_count'] = list_lines
            
            # Count headers (lines that are short, title-case, or all caps)
            header_lines = 0
            for line in lines:
                line = line.strip()
                if (line and len(line) < 100 and 
                    (line.isupper() or line.istitle() or line.endswith(':'))):
                    header_lines += 1
            structure_metrics['header_count'] = header_lines
            
            # Check for table of contents
            toc_keywords = ['mục lục', 'table of contents', 'contents', 'index']
            structure_metrics['has_toc'] = any(
                keyword in text.lower() for keyword in toc_keywords
            )
            
            # Calculate overall structure score
            total_lines = len(lines)
            if total_lines > 0:
                structured_lines = table_lines + list_lines + header_lines
                structure_metrics['structure_score'] = min(1.0, structured_lines / total_lines * 2)
            
        except Exception as e:
            logger.error(f"Error analyzing structure: {str(e)}")
        
        return structure_metrics
    
    async def _analyze_complexity(self, text: str) -> Dict[str, Any]:
        """
        Analyze text complexity
        
        Args:
            text: Text để analyze
            
        Returns:
            Dict: Complexity metrics
        """
        complexity_metrics = {
            'complexity_score': 0.0,
            'avg_sentence_length': 0.0,
            'avg_word_length': 0.0,
            'punctuation_density': 0.0,
            'vocabulary_richness': 0.0
        }
        
        try:
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            
            if words:
                # Average word length
                complexity_metrics['avg_word_length'] = sum(len(word) for word in words) / len(words)
                
                # Vocabulary richness (unique words / total words)
                unique_words = set(word.lower() for word in words)
                complexity_metrics['vocabulary_richness'] = len(unique_words) / len(words)
            
            if sentences:
                # Average sentence length
                sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
                if sentence_lengths:
                    complexity_metrics['avg_sentence_length'] = sum(sentence_lengths) / len(sentence_lengths)
            
            # Punctuation density
            punctuation_count = len(re.findall(r'[^\w\s]', text))
            if text:
                complexity_metrics['punctuation_density'] = punctuation_count / len(text)
            
            # Overall complexity score
            complexity_factors = [
                min(1.0, complexity_metrics['avg_sentence_length'] / 20),  # Normalize to ~20 words
                min(1.0, complexity_metrics['avg_word_length'] / 8),       # Normalize to ~8 chars
                complexity_metrics['punctuation_density'] * 10,           # Scale up
                complexity_metrics['vocabulary_richness']
            ]
            
            complexity_metrics['complexity_score'] = sum(complexity_factors) / len(complexity_factors)
            
        except Exception as e:
            logger.error(f"Error analyzing complexity: {str(e)}")
        
        return complexity_metrics
    
    async def _analyze_semantics(self, text: str) -> Dict[str, Any]:
        """
        Analyze semantic characteristics
        
        Args:
            text: Text để analyze
            
        Returns:
            Dict: Semantic metrics
        """
        semantic_metrics = {
            'semantic_coherence': 0.5,  # Default value
            'topic_diversity': 0.5,
            'narrative_flow': 0.5
        }
        
        try:
            # Simple semantic analysis without heavy models
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            
            if len(paragraphs) > 1:
                # Check topic consistency by keyword overlap
                keyword_sets = []
                for paragraph in paragraphs[:10]:  # Limit to first 10 paragraphs
                    keywords = set(self.extract_keywords(paragraph, max_keywords=5))
                    keyword_sets.append(keywords)
                
                # Calculate average keyword overlap between adjacent paragraphs
                overlaps = []
                for i in range(len(keyword_sets) - 1):
                    if keyword_sets[i] and keyword_sets[i + 1]:
                        overlap = len(keyword_sets[i] & keyword_sets[i + 1])
                        total = len(keyword_sets[i] | keyword_sets[i + 1])
                        if total > 0:
                            overlaps.append(overlap / total)
                
                if overlaps:
                    semantic_metrics['semantic_coherence'] = sum(overlaps) / len(overlaps)
                
                # Topic diversity (inverse of coherence)
                semantic_metrics['topic_diversity'] = 1.0 - semantic_metrics['semantic_coherence']
            
            # Narrative flow (based on temporal/logical connectors)
            flow_indicators = [
                'first', 'second', 'third', 'then', 'next', 'finally',
                'before', 'after', 'meanwhile', 'subsequently',
                'đầu tiên', 'thứ hai', 'thứ ba', 'sau đó', 'tiếp theo', 'cuối cùng',
                'trước khi', 'sau khi', 'trong khi', 'kế tiếp'
            ]
            
            flow_count = sum(1 for indicator in flow_indicators if indicator in text.lower())
            total_sentences = len(re.split(r'[.!?]+', text))
            
            if total_sentences > 0:
                semantic_metrics['narrative_flow'] = min(1.0, flow_count / total_sentences * 10)
            
        except Exception as e:
            logger.error(f"Error analyzing semantics: {str(e)}")
        
        return semantic_metrics
    
    async def _select_strategy(self, analysis: Dict[str, Any]) -> str:
        """
        Chọn chunking strategy dựa trên analysis
        
        Args:
            analysis: Content analysis
            
        Returns:
            str: Strategy name
        """
        weights = {
            'semantic': 0.0,
            'recursive': 0.0,
            'hierarchical': 0.0,
            'hybrid': 0.0
        }
        
        # Document type weights
        doc_type = analysis.get('document_type', 'text')
        if doc_type == 'pdf':
            weights['hierarchical'] += 0.3  # PDFs often have clear structure
            weights['recursive'] += 0.2
        elif doc_type == 'word':
            weights['semantic'] += 0.2     # Word docs often have flowing text
            weights['hierarchical'] += 0.2
        elif doc_type == 'excel':
            weights['recursive'] += 0.4    # Excel needs structured splitting
        
        # Structure score weights
        structure_score = analysis.get('structure_score', 0.0)
        if structure_score > 0.3:
            weights['hierarchical'] += structure_score * 0.4
            weights['recursive'] += structure_score * 0.3
        else:
            weights['semantic'] += (1.0 - structure_score) * 0.3
        
        # Complexity weights
        complexity = analysis.get('complexity_score', 0.5)
        if complexity > 0.6:
            weights['semantic'] += 0.3     # Complex text benefits from semantic chunking
        else:
            weights['recursive'] += 0.2    # Simple text can use recursive
        
        # Semantic coherence weights
        coherence = analysis.get('semantic_coherence', 0.5)
        if coherence > 0.6:
            weights['semantic'] += coherence * 0.4
        
        # Length-based weights
        length = analysis.get('length', 0)
        if length > 50000:  # Very long documents
            weights['hierarchical'] += 0.3
        elif length < 5000:  # Short documents
            weights['recursive'] += 0.2
        
        # Special cases
        if analysis.get('table_count', 0) > 10:
            weights['recursive'] += 0.3    # Many tables need structured splitting
        
        if analysis.get('header_count', 0) > 5:
            weights['hierarchical'] += 0.3  # Many headers suggest hierarchy
        
        # Hybrid strategy for balanced content
        balance_score = abs(weights['semantic'] - weights['recursive'])
        if balance_score < 0.2:
            weights['hybrid'] += 0.3
        
        # Select strategy with highest weight
        selected_strategy = max(weights.keys(), key=lambda k: weights[k])
        
        # Store weights for debugging
        self.strategy_weights = weights
        
        logger.info(f"Strategy selection weights: {weights}, selected: {selected_strategy}")
        return selected_strategy
    
    async def _apply_strategy(self, text: str, strategy: str, 
                            document_metadata: Optional[Dict[str, Any]],
                            analysis: Dict[str, Any]) -> List[ChunkResult]:
        """
        Apply selected chunking strategy
        
        Args:
            text: Text để chunk
            strategy: Selected strategy
            document_metadata: Document metadata
            analysis: Content analysis
            
        Returns:
            List[ChunkResult]: Chunks
        """
        if strategy == 'semantic':
            return await self.semantic_chunker.chunk_text(text, document_metadata)
        
        elif strategy == 'recursive':
            return await self.recursive_chunker.chunk_text(text, document_metadata)
        
        elif strategy == 'hierarchical':
            return await self.hierarchical_chunker.chunk_text(text, document_metadata)
        
        elif strategy == 'hybrid':
            return await self._hybrid_chunking(text, document_metadata, analysis)
        
        else:
            # Fallback
            return await self.recursive_chunker.chunk_text(text, document_metadata)
    
    async def _hybrid_chunking(self, text: str, 
                             document_metadata: Optional[Dict[str, Any]],
                             analysis: Dict[str, Any]) -> List[ChunkResult]:
        """
        Hybrid chunking combines multiple strategies
        
        Args:
            text: Text để chunk
            document_metadata: Document metadata
            analysis: Content analysis
            
        Returns:
            List[ChunkResult]: Combined chunks
        """
        try:
            # Sử dụng hierarchical cho high-level structure
            hierarchical_chunks = await self.hierarchical_chunker.chunk_text(text, document_metadata)
            
            # Lọc chunks cấp cao (level 0-1)
            high_level_chunks = [
                chunk for chunk in hierarchical_chunks 
                if chunk.metadata.level is not None and chunk.metadata.level <= 1
            ]
            
            # Sử dụng semantic chunking cho từng high-level chunk
            final_chunks = []
            chunk_index = 0
            
            for high_chunk in high_level_chunks:
                # Apply semantic chunking to this chunk's content
                semantic_chunks = await self.semantic_chunker.chunk_text(
                    high_chunk.content, document_metadata
                )
                
                # Update metadata để maintain hierarchy
                for sem_chunk in semantic_chunks:
                    sem_chunk.metadata.chunk_index = chunk_index
                    sem_chunk.metadata.parent_chunk_id = high_chunk.metadata.parent_chunk_id
                    sem_chunk.metadata.level = (high_chunk.metadata.level or 0) + 1
                    sem_chunk.metadata.section_title = high_chunk.metadata.section_title
                    
                    final_chunks.append(sem_chunk)
                    chunk_index += 1
            
            # Nếu không có high-level chunks, fallback to semantic
            if not final_chunks:
                final_chunks = await self.semantic_chunker.chunk_text(text, document_metadata)
            
            logger.info(f"Hybrid chunking: {len(high_level_chunks)} high-level -> {len(final_chunks)} final chunks")
            return final_chunks
            
        except Exception as e:
            logger.error(f"Error in hybrid chunking: {str(e)}")
            # Fallback to semantic
            return await self.semantic_chunker.chunk_text(text, document_metadata)
    
    async def _optimize_chunks(self, chunks: List[ChunkResult], 
                             analysis: Dict[str, Any]) -> List[ChunkResult]:
        """
        Optimize chunks based on analysis
        
        Args:
            chunks: Input chunks
            analysis: Content analysis
            
        Returns:
            List[ChunkResult]: Optimized chunks
        """
        if not chunks:
            return chunks
        
        try:
            # Merge very small chunks
            min_size = self.chunk_size // 4
            optimized_chunks = []
            
            i = 0
            while i < len(chunks):
                current_chunk = chunks[i]
                
                # If chunk is too small, try to merge with next
                if (len(current_chunk.content) < min_size and 
                    i + 1 < len(chunks) and 
                    len(current_chunk.content + chunks[i + 1].content) <= self.chunk_size * 1.2):
                    
                    # Merge chunks
                    merged_content = current_chunk.content + "\n\n" + chunks[i + 1].content
                    merged_metadata = current_chunk.metadata
                    merged_metadata.length = len(merged_content)
                    merged_metadata.end_position = chunks[i + 1].metadata.end_position
                    
                    merged_chunk = ChunkResult(content=merged_content, metadata=merged_metadata)
                    optimized_chunks.append(merged_chunk)
                    i += 2  # Skip next chunk
                else:
                    optimized_chunks.append(current_chunk)
                    i += 1
            
            # Re-index chunks
            for idx, chunk in enumerate(optimized_chunks):
                chunk.metadata.chunk_index = idx
            
            logger.info(f"Chunk optimization: {len(chunks)} -> {len(optimized_chunks)} chunks")
            return optimized_chunks
            
        except Exception as e:
            logger.error(f"Error optimizing chunks: {str(e)}")
            return chunks
