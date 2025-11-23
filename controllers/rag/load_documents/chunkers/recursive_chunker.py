"""
Recursive Character Text Splitter
Chunker sử dụng recursive character splitting với nhiều separators
"""

import logging
from typing import List, Dict, Any, Optional
import re

from .base_chunker import BaseChunker, ChunkResult, ChunkMetadata, ChunkType

logger = logging.getLogger(__name__)

class RecursiveCharacterTextSplitter(BaseChunker):
    """
    Recursive character text splitter
    Chia text theo hierarchy của separators để giữ nguyên structure
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200,
                 separators: Optional[List[str]] = None,
                 keep_separator: bool = True,
                 **kwargs):
        """
        Initialize Recursive Character Text Splitter
        
        Args:
            chunk_size: Kích thước chunk mong muốn
            overlap: Overlap giữa các chunk
            separators: Danh sách separators theo thứ tự ưu tiên
            keep_separator: Có giữ separator trong chunk không
        """
        super().__init__(chunk_size, overlap, **kwargs)
        self.keep_separator = keep_separator
        
        # Default separators for Vietnamese and English
        if separators is None:
            self.separators = [
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentence endings
                "! ",    # Exclamation endings
                "? ",    # Question endings
                "; ",    # Semicolon
                ", ",    # Comma
                " ",     # Space
                ""       # Character level (last resort)
            ]
        else:
            self.separators = separators
    
    def get_chunk_type(self) -> ChunkType:
        """Return chunk type"""
        return ChunkType.FIXED_SIZE
    
    async def chunk_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkResult]:
        """
        Chia text thành chunks sử dụng recursive splitting
        
        Args:
            text: Text cần chia
            document_metadata: Metadata của document
            
        Returns:
            List[ChunkResult]: Danh sách chunks
        """
        if not self.validate_text(text):
            return []
        
        # Clean text
        text = self.clean_text(text)
        
        try:
            # Split text recursively
            splits = await self._recursive_split(text, self.separators)
            
            # Combine splits into chunks
            chunks = await self._combine_splits_into_chunks(splits, document_metadata)
            
            # Post-process chunks
            chunks = await self.post_process_chunks(chunks)
            
            logger.info(f"Created {len(chunks)} recursive chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in recursive chunking: {str(e)}")
            return []
    
    async def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        """
        Recursively split text với multiple separators
        
        Args:
            text: Text cần split
            separators: Danh sách separators
            
        Returns:
            List[str]: Text splits
        """
        final_chunks = []
        
        # Separator to split on
        separator = separators[0] if separators else ""
        new_separators = separators[1:] if len(separators) > 1 else []
        
        # Split by separator
        if separator == "":
            # Character level split (last resort)
            splits = list(text)
        else:
            splits = text.split(separator)
        
        # Process each split
        good_splits = []
        for split in splits:
            if not split.strip():
                continue
                
            if len(split) > self.chunk_size:
                # If split is still too large, recursively split further
                if new_separators:
                    subsplits = await self._recursive_split(split, new_separators)
                    good_splits.extend(subsplits)
                else:
                    # Force split at character level
                    for i in range(0, len(split), self.chunk_size):
                        good_splits.append(split[i:i + self.chunk_size])
            else:
                good_splits.append(split)
        
        # Add back separators if keeping them
        if self.keep_separator and separator and separator != "":
            final_splits = []
            for i, split in enumerate(good_splits):
                if i > 0:
                    # Add separator back (except for first split)
                    final_splits.append(separator + split)
                else:
                    final_splits.append(split)
            return final_splits
        
        return good_splits
    
    async def _combine_splits_into_chunks(self, splits: List[str], 
                                        document_metadata: Optional[Dict[str, Any]]) -> List[ChunkResult]:
        """
        Combine splits thành chunks với overlap
        
        Args:
            splits: Text splits
            document_metadata: Document metadata
            
        Returns:
            List[ChunkResult]: Chunks
        """
        if not splits:
            return []
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        for i, split in enumerate(splits):
            # Kiểm tra nếu thêm split này vào chunk có vượt quá chunk_size không
            potential_chunk = current_chunk + split if current_chunk else split
            
            if len(potential_chunk) <= self.chunk_size or not current_chunk:
                # Thêm split vào chunk hiện tại
                current_chunk = potential_chunk
            else:
                # Tạo chunk từ nội dung hiện tại
                if current_chunk.strip():
                    chunk_result = await self._create_chunk_result(
                        current_chunk.strip(), chunk_index, current_start, document_metadata
                    )
                    chunks.append(chunk_result)
                    chunk_index += 1
                
                # Bắt đầu chunk mới với overlap
                overlap_text = await self._get_overlap_text(current_chunk, self.overlap)
                current_chunk = overlap_text + split if overlap_text else split
                current_start = self._find_text_position(current_chunk, splits, i)
        
        # Thêm chunk cuối cùng
        if current_chunk.strip():
            chunk_result = await self._create_chunk_result(
                current_chunk.strip(), chunk_index, current_start, document_metadata
            )
            chunks.append(chunk_result)
        
        return chunks
    
    async def _create_chunk_result(self, content: str, chunk_index: int, 
                                 start_position: int, 
                                 document_metadata: Optional[Dict[str, Any]]) -> ChunkResult:
        """
        Tạo ChunkResult từ content
        
        Args:
            content: Chunk content
            chunk_index: Index của chunk
            start_position: Start position
            document_metadata: Document metadata
            
        Returns:
            ChunkResult: Chunk result
        """
        end_position = start_position + len(content)
        
        # Detect structure elements
        structure_info = await self._analyze_structure(content)
        
        metadata = ChunkMetadata(
            chunk_index=chunk_index,
            chunk_type=self.get_chunk_type(),
            start_position=start_position,
            end_position=end_position,
            length=len(content),
            section_title=structure_info.get('section_title'),
            completeness_score=structure_info.get('completeness_score', 0.5)
        )
        
        # Add document-specific metadata
        if document_metadata:
            metadata.page_number = document_metadata.get('page_number')
            metadata.sheet_name = document_metadata.get('sheet_name')
        
        return ChunkResult(content=content, metadata=metadata)
    
    async def _analyze_structure(self, text: str) -> Dict[str, Any]:
        """
        Analyze text structure để extract metadata
        
        Args:
            text: Text cần analyze
            
        Returns:
            Dict: Structure information
        """
        structure_info = {}
        
        try:
            # Detect potential section titles (lines with less than 100 chars, ends with colon or all caps)
            lines = text.split('\n')
            for line in lines[:3]:  # Check first 3 lines
                line = line.strip()
                if (len(line) < 100 and 
                    (line.endswith(':') or line.isupper() or 
                     re.match(r'^[A-Z][A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ\s]+$', line))):
                    structure_info['section_title'] = line
                    break
            
            # Calculate completeness score based on sentence completeness
            sentences = re.split(r'[.!?]', text)
            complete_sentences = [s for s in sentences if s.strip() and len(s.strip()) > 10]
            
            if sentences:
                # Check if last sentence is complete (ends with punctuation)
                last_sentence_complete = text.rstrip().endswith(('.', '!', '?'))
                completeness = len(complete_sentences) / len(sentences)
                
                if last_sentence_complete:
                    completeness = min(1.0, completeness + 0.2)
                
                structure_info['completeness_score'] = completeness
            
        except Exception as e:
            logger.error(f"Error analyzing structure: {str(e)}")
        
        return structure_info
    
    async def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        """
        Lấy overlap text từ cuối chunk
        
        Args:
            text: Text gốc
            overlap_size: Kích thước overlap
            
        Returns:
            str: Overlap text
        """
        if overlap_size <= 0 or len(text) <= overlap_size:
            return ""
        
        # Lấy overlap_size ký tự cuối
        overlap_text = text[-overlap_size:]
        
        # Tìm boundary tốt để cắt (sentence, word boundary)
        # Tìm sentence boundary trước
        for sep in ['. ', '! ', '? ', '\n']:
            if sep in overlap_text:
                parts = overlap_text.split(sep)
                if len(parts) > 1:
                    # Lấy từ separator cuối cùng
                    last_sep_index = overlap_text.rfind(sep)
                    return overlap_text[last_sep_index + len(sep):]
        
        # Fallback: tìm word boundary
        space_index = overlap_text.find(' ')
        if space_index > 0:
            return overlap_text[space_index + 1:]
        
        return overlap_text
    
    def _find_text_position(self, text: str, splits: List[str], current_index: int) -> int:
        """
        Tìm position của text trong document gốc (simplified)
        
        Args:
            text: Text cần tìm position
            splits: All splits
            current_index: Current split index
            
        Returns:
            int: Estimated position
        """
        # Simplified position calculation
        # In real implementation, this should track actual positions
        position = 0
        for i, split in enumerate(splits[:current_index]):
            position += len(split)
        
        return position
