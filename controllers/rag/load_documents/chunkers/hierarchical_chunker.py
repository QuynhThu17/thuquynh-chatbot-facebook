"""
Hierarchical Chunker
Tạo hierarchical chunks với parent-child relationships
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid

from .base_chunker import BaseChunker, ChunkResult, ChunkMetadata, ChunkType
from .recursive_chunker import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

class HierarchicalChunker(BaseChunker):
    """
    Hierarchical chunker tạo multi-level chunks
    Level 0: Document level
    Level 1: Section/Page level 
    Level 2: Paragraph level
    Level 3: Sentence level
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 200,
                 levels: List[Dict[str, Any]] = None,
                 **kwargs):
        """
        Initialize Hierarchical Chunker
        
        Args:
            chunk_size: Base chunk size
            overlap: Overlap between chunks
            levels: Configuration cho từng level
        """
        super().__init__(chunk_size, overlap, **kwargs)
        
        # Default level configuration
        if levels is None:
            self.levels = [
                {
                    'name': 'document',
                    'chunk_size': chunk_size * 8,  # Large chunks
                    'separators': ['\n\n\n', '\f'],  # Page breaks, form feeds
                    'min_chunk_size': chunk_size * 2
                },
                {
                    'name': 'section', 
                    'chunk_size': chunk_size * 4,  # Medium chunks
                    'separators': ['\n\n'],  # Paragraph breaks
                    'min_chunk_size': chunk_size
                },
                {
                    'name': 'paragraph',
                    'chunk_size': chunk_size,  # Base chunks
                    'separators': ['. ', '! ', '? '],  # Sentence breaks
                    'min_chunk_size': chunk_size // 2
                },
                {
                    'name': 'sentence',
                    'chunk_size': chunk_size // 2,  # Small chunks
                    'separators': [', ', '; ', ' '],  # Clause/word breaks
                    'min_chunk_size': chunk_size // 4
                }
            ]
        else:
            self.levels = levels
    
    def get_chunk_type(self) -> ChunkType:
        """Return chunk type"""
        return ChunkType.HIERARCHICAL
    
    async def chunk_text(self, text: str, document_metadata: Optional[Dict[str, Any]] = None) -> List[ChunkResult]:
        """
        Tạo hierarchical chunks
        
        Args:
            text: Text cần chia
            document_metadata: Metadata của document
            
        Returns:
            List[ChunkResult]: Danh sách tất cả chunks từ mọi levels
        """
        if not self.validate_text(text):
            return []
        
        # Clean text
        text = self.clean_text(text)
        
        try:
            # Tạo hierarchical structure
            hierarchy = await self._create_hierarchy(text, document_metadata)
            
            # Convert hierarchy thành flat list of chunks
            all_chunks = await self._flatten_hierarchy(hierarchy)
            
            # Post-process chunks
            all_chunks = await self.post_process_chunks(all_chunks)
            
            logger.info(f"Created {len(all_chunks)} hierarchical chunks across {len(self.levels)} levels")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Error in hierarchical chunking: {str(e)}")
            return []
    
    async def _create_hierarchy(self, text: str, document_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Tạo hierarchical structure
        
        Args:
            text: Text cần xử lý
            document_metadata: Document metadata
            
        Returns:
            Dict: Hierarchical structure
        """
        # Root node
        root_id = str(uuid.uuid4())
        hierarchy = {
            'id': root_id,
            'level': -1,
            'name': 'root',
            'content': text,
            'metadata': document_metadata or {},
            'children': []
        }
        
        # Tạo children cho từng level
        await self._create_level_children(hierarchy, text, 0)
        
        return hierarchy
    
    async def _create_level_children(self, parent_node: Dict[str, Any], 
                                   text: str, level_index: int):
        """
        Tạo children cho một level
        
        Args:
            parent_node: Parent node
            text: Text cần chia
            level_index: Index của level hiện tại
        """
        if level_index >= len(self.levels):
            return
        
        level_config = self.levels[level_index]
        
        # Sử dụng RecursiveCharacterTextSplitter cho level này
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=level_config['chunk_size'],
            overlap=self.overlap,
            separators=level_config['separators']
        )
        
        # Split text
        splits = await splitter._recursive_split(text, level_config['separators'])
        
        # Combine splits thành chunks cho level này
        current_chunk = ""
        chunk_index = 0
        
        for split in splits:
            potential_chunk = current_chunk + split if current_chunk else split
            
            # Kiểm tra kích thước
            if (len(potential_chunk) <= level_config['chunk_size'] or 
                len(current_chunk) < level_config['min_chunk_size']):
                current_chunk = potential_chunk
            else:
                # Tạo child node
                if current_chunk.strip():
                    child_node = await self._create_child_node(
                        current_chunk.strip(), parent_node['id'], 
                        level_index, chunk_index, level_config['name']
                    )
                    parent_node['children'].append(child_node)
                    
                    # Recursively tạo children cho node này
                    await self._create_level_children(child_node, current_chunk.strip(), level_index + 1)
                    chunk_index += 1
                
                # Bắt đầu chunk mới với overlap
                overlap_text = await self._get_overlap_text(current_chunk, self.overlap)
                current_chunk = overlap_text + split if overlap_text else split
        
        # Xử lý chunk cuối cùng
        if current_chunk.strip():
            child_node = await self._create_child_node(
                current_chunk.strip(), parent_node['id'],
                level_index, chunk_index, level_config['name']
            )
            parent_node['children'].append(child_node)
            await self._create_level_children(child_node, current_chunk.strip(), level_index + 1)
    
    async def _create_child_node(self, content: str, parent_id: str, 
                               level: int, index: int, level_name: str) -> Dict[str, Any]:
        """
        Tạo child node
        
        Args:
            content: Content của node
            parent_id: ID của parent
            level: Level index
            index: Index trong level
            level_name: Tên của level
            
        Returns:
            Dict: Child node
        """
        node_id = str(uuid.uuid4())
        
        return {
            'id': node_id,
            'level': level,
            'name': level_name,
            'content': content,
            'parent_id': parent_id,
            'index': index,
            'children': [],
            'metadata': {
                'level_name': level_name,
                'level_index': level,
                'chunk_index': index,
                'content_length': len(content)
            }
        }
    
    async def _flatten_hierarchy(self, hierarchy: Dict[str, Any]) -> List[ChunkResult]:
        """
        Chuyển hierarchy thành flat list of chunks
        
        Args:
            hierarchy: Hierarchical structure
            
        Returns:
            List[ChunkResult]: Flat list của tất cả chunks
        """
        chunks = []
        chunk_counter = 0
        
        await self._traverse_hierarchy(hierarchy, chunks, chunk_counter, set())
        
        return chunks
    
    async def _traverse_hierarchy(self, node: Dict[str, Any], 
                                chunks: List[ChunkResult], 
                                chunk_counter: int,
                                visited: set):
        """
        Traverse hierarchy để collect chunks
        
        Args:
            node: Current node
            chunks: List để add chunks vào
            chunk_counter: Counter cho chunk index
            visited: Set of visited node IDs
        """
        if node['id'] in visited:
            return chunk_counter
        
        visited.add(node['id'])
        
        # Skip root node
        if node['level'] >= 0:
            # Tạo chunk cho node này
            chunk_result = await self._create_chunk_from_node(node, chunk_counter)
            chunks.append(chunk_result)
            chunk_counter += 1
        
        # Traverse children
        for child in node['children']:
            chunk_counter = await self._traverse_hierarchy(child, chunks, chunk_counter, visited)
        
        return chunk_counter
    
    async def _create_chunk_from_node(self, node: Dict[str, Any], chunk_index: int) -> ChunkResult:
        """
        Tạo ChunkResult từ node
        
        Args:
            node: Node data
            chunk_index: Global chunk index
            
        Returns:
            ChunkResult: Chunk result
        """
        content = node['content']
        
        # Collect child IDs
        child_ids = [child['id'] for child in node['children']]
        
        # Create metadata
        metadata = ChunkMetadata(
            chunk_index=chunk_index,
            chunk_type=self.get_chunk_type(),
            start_position=0,  # Would need to calculate actual position
            end_position=len(content),
            length=len(content),
            level=node['level'],
            parent_chunk_id=node.get('parent_id'),
            child_chunk_ids=child_ids if child_ids else None,
            section_title=self._extract_section_title(content, node['name'])
        )
        
        # Add level-specific metadata
        metadata.topic = f"{node['name']}_level_{node['level']}"
        
        return ChunkResult(content=content, metadata=metadata)
    
    def _extract_section_title(self, content: str, level_name: str) -> Optional[str]:
        """
        Extract section title từ content
        
        Args:
            content: Content
            level_name: Level name
            
        Returns:
            str: Section title
        """
        try:
            # For document level, use first line
            if level_name == 'document':
                first_line = content.split('\n')[0].strip()
                if len(first_line) < 200:  # Reasonable title length
                    return first_line
            
            # For section level, look for headers
            elif level_name == 'section':
                lines = content.split('\n')
                for line in lines[:3]:  # Check first 3 lines
                    line = line.strip()
                    if (len(line) < 100 and 
                        (line.endswith(':') or line.isupper())):
                        return line
            
            # For paragraph level, use first sentence
            elif level_name == 'paragraph':
                sentences = content.split('.')
                if sentences:
                    first_sentence = sentences[0].strip()
                    if len(first_sentence) < 150:
                        return first_sentence
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting section title: {str(e)}")
            return None
    
    async def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        """
        Get overlap text từ cuối chunk
        
        Args:
            text: Text gốc
            overlap_size: Kích thước overlap
            
        Returns:
            str: Overlap text
        """
        if overlap_size <= 0 or len(text) <= overlap_size:
            return ""
        
        return text[-overlap_size:]
