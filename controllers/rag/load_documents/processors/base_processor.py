"""
Base Document Processor
Lớp cơ sở cho tất cả các document processors
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)

@dataclass
class PageContent:
    """Cấu trúc dữ liệu cho nội dung từng page"""
    page_number: int
    text_content: str  # Text thuần không có image tags
    full_content: str  # Text + image tags đầy đủ
    images: List[Dict[str, Any]]  # [{"image_data": bytes, "position": int, "metadata": {...}}]
    page_metadata: Dict[str, Any]

@dataclass
class DocumentContent:
    """Cấu trúc dữ liệu cho nội dung document"""
    pages: List[PageContent]  # Danh sách các page
    total_text_content: str  # Toàn bộ text content
    total_images: List[Dict[str, Any]]  # Tất cả ảnh với page info
    metadata: Dict[str, Any]
    
@dataclass 
class ProcessedChunk:
    """Cấu trúc dữ liệu cho chunk đã xử lý"""
    content: str  # Full content including image tags
    content_embedding: str  # Content for embedding (no image tags)
    chunk_type: str  # "text", "page", "image"
    images: List[str]  # URLs của ảnh trong chunk này
    page_number: Optional[int]
    chunk_index: int
    metadata: Dict[str, Any]

class BaseDocumentProcessor(ABC):
    """
    Lớp cơ sở cho tất cả các document processors
    """
    
    def __init__(self):
        self.supported_extensions = []
        self.process_images = False  # Flag để control việc xử lý ảnh
        
    @abstractmethod
    async def extract_content(self, file_path: str, file_data: bytes) -> DocumentContent:
        """
        Trích xuất nội dung từ file
        
        Args:
            file_path: Đường dẫn file
            file_data: Dữ liệu file dạng bytes
            
        Returns:
            DocumentContent: Nội dung đã trích xuất
        """
        pass
    
    @abstractmethod
    def can_process(self, file_extension: str) -> bool:
        """
        Kiểm tra có thể xử lý file này không
        
        Args:
            file_extension: Phần mở rộng file (vd: .pdf, .docx)
            
        Returns:
            bool: True nếu có thể xử lý
        """
        pass
    
    def validate_file(self, file_data: bytes, file_extension: str) -> bool:
        """
        Validate file trước khi xử lý
        
        Args:
            file_data: Dữ liệu file
            file_extension: Phần mở rộng file
            
        Returns:
            bool: True nếu file hợp lệ
        """
        try:
            # Kiểm tra kích thước file
            if len(file_data) == 0:
                logger.error("File is empty")
                return False
                
            # Kiểm tra kích thước tối đa (20MB)
            if len(file_data) > 20 * 1024 * 1024:
                logger.error("File size exceeds 20MB limit")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating file: {str(e)}")
            return False
    
    def clean_text(self, text: str) -> str:
        """
        Làm sạch text content
        
        Args:
            text: Text cần làm sạch
            
        Returns:
            str: Text đã làm sạch
        """
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
        import re
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        lines = text.split("\n")
        processed = []
        for line in lines:
            line = re.sub(r' {2,}', ' ', line.strip())
            processed.append(line)
        text = "\n".join(processed).strip()
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
        
    def sanitize_filename_for_ascii(self, filename: str) -> str:
        """
        Chuyển đổi filename có ký tự đặc biệt thành ASCII-only cho S3 metadata
        
        Args:
            filename: Tên file gốc có thể chứa ký tự unicode
            
        Returns:
            str: Tên file chỉ chứa ký tự ASCII
        """
        # Chuyển đổi unicode thành ASCII gần nhất
        # VD: "ĐỐI TÁC" -> "DOI TAC" 
        ascii_filename = unicodedata.normalize('NFD', filename)
        ascii_filename = ''.join(c for c in ascii_filename if unicodedata.category(c) != 'Mn')
        
        # Loại bỏ các ký tự không phải ASCII
        ascii_filename = ascii_filename.encode('ascii', 'ignore').decode('ascii')
        
        # Thay thế các ký tự đặc biệt còn lại bằng underscore
        ascii_filename = re.sub(r'[^\w\s.-]', '_', ascii_filename)
        
        # Loại bỏ multiple spaces/underscores liên tiếp
        ascii_filename = re.sub(r'[\s_]+', '_', ascii_filename)
        
        return ascii_filename.strip('_')
    
    def extract_metadata(self, file_path: str, file_data: bytes) -> Dict[str, Any]:
        """
        Trích xuất metadata cơ bản từ file
        
        Args:
            file_path: Đường dẫn file
            file_data: Dữ liệu file
            
        Returns:
            Dict[str, Any]: Metadata
        """
        import os
        from datetime import datetime
        
        return {
            "file_name": os.path.basename(file_path),
            "file_size": len(file_data),
            "file_extension": os.path.splitext(file_path)[1].lower(),
            "processed_at": datetime.now().isoformat(),
            "processor": self.__class__.__name__
        }
    
    def _convert_legacy_to_page_structure(self, text_content: str, images: List[Dict[str, Any]], 
                                        metadata: Dict[str, Any]) -> DocumentContent:
        """
        Convert legacy DocumentContent structure to new page-aware structure
        For processors that haven't been updated yet
        
        Args:
            text_content: Legacy text content
            images: Legacy images list
            metadata: Document metadata
            
        Returns:
            DocumentContent: New page-aware structure
        """
        # Create a single page for legacy content
        page_content = PageContent(
            page_number=1,
            text_content=text_content,
            full_content=self._insert_image_placeholders(text_content, images),
            images=self._convert_legacy_images(images),
            page_metadata={
                "page_number": 1,
                "text_length": len(text_content),
                "image_count": len(images)
            }
        )
        
        return DocumentContent(
            pages=[page_content],
            total_text_content=text_content,
            total_images=self._convert_legacy_images(images),
            metadata=metadata
        )
    
    def _insert_image_placeholders(self, text: str, images: List[Dict[str, Any]]) -> str:
        """Insert image placeholders into text for legacy compatibility"""
        if not images:
            return text
        
        # For simplicity, add image tags at the end
        image_tags = []
        for i, img in enumerate(images):
            image_id = img.get("image_id", f"img_{i}")
            image_tags.append(f"<image:{image_id}>")
        
        return text + "\n\n" + "\n".join(image_tags)
    
    def _convert_legacy_images(self, images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert legacy image format to new format"""
        converted = []
        for i, img in enumerate(images):
            converted_img = img.copy()
            if "image_id" not in converted_img:
                converted_img["image_id"] = f"img_{i}"
            if "page" not in converted_img:
                converted_img["page"] = 1
            converted.append(converted_img)
        return converted
