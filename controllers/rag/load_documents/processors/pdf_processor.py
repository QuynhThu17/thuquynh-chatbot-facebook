"""
PDF Document Processor
Xử lý file PDF, trích xuất text  theo đúng thứ tự
"""

import logging
from typing import Dict, List, Any, Optional
import fitz  # PyMuPDF
from io import BytesIO
import re
import sys
from pathlib import Path

# Add project directories to path
current_dir = Path(__file__).parent
load_documents_dir = current_dir.parent
sys.path.append(str(load_documents_dir))

from .base_processor import BaseDocumentProcessor, DocumentContent, PageContent
from controllers.rag.load_documents.utils import DocumentUtils

logger = logging.getLogger(__name__)

class PDFProcessor(BaseDocumentProcessor):
    """
    Processor cho file PDF
    Sử dụng PyMuPDF để trích xuất text và ảnh
    """
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.pdf']
    
    def can_process(self, file_extension: str) -> bool:
        """Kiểm tra có thể xử lý file PDF không"""
        return file_extension.lower() in self.supported_extensions
    
    async def extract_content(self, file_path: str, file_data: bytes) -> DocumentContent:
        """
        Trích xuất nội dung từ file PDF theo page
        
        Args:
            file_path: Đường dẫn file
            file_data: Dữ liệu file PDF
            
        Returns:
            DocumentContent: Nội dung đã trích xuất với thông tin page
        """
        try:
            # Validate file
            if not self.validate_file(file_data, '.pdf'):
                raise ValueError("Invalid PDF file")
            
            # Mở PDF từ bytes
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            
            pages = []
            all_images = []
            total_text_content = ""
            
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                
                # Trích xuất text từ page
                page_text = page.get_text()
                page_text = self.clean_text(page_text)
                
                # Trích xuất ảnh từ page (nếu process_images=True)
                page_images = []
                if self.process_images:
                    page_images = await self._extract_images_from_page(page, page_num)
                
                # Tạo full content với image tags
                full_page_content = await self._create_page_content_with_images(
                    page_text, page_images, page_num
                )
                
                # Tạo PageContent
                page_content = PageContent(
                    page_number=page_num + 1,
                    text_content=page_text,
                    full_content=full_page_content,
                    images=page_images,
                    page_metadata={
                        "page_number": page_num + 1,
                        "text_length": len(page_text),
                        "image_count": len(page_images)
                    }
                )
                
                pages.append(page_content)
                all_images.extend(page_images)
                total_text_content += page_text + "\n\n"
            
            pdf_document.close()
            
            # Tạo metadata
            metadata = self.extract_metadata(file_path, file_data)
            metadata.update(await self._extract_pdf_metadata(file_data))
            
            return DocumentContent(
                pages=pages,
                total_text_content=total_text_content.strip(),
                total_images=all_images,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error extracting content from PDF: {str(e)}")
            raise
    
    async def _extract_images_from_page(self, page, page_num: int) -> List[Dict[str, Any]]:
        """
        Trích xuất tất cả ảnh từ một page
        
        Args:
            page: PyMuPDF page object
            page_num: Số page (0-based)
            
        Returns:
            List[Dict]: Danh sách ảnh với thông tin page
        """
        images = []
        
        try:
            # Lấy danh sách ảnh trong page
            image_list = page.get_images(full=True)
            
            for img_index, img in enumerate(image_list):
                try:
                    # Lấy thông tin ảnh
                    xref = img[0]
                    pix = fitz.Pixmap(page.parent, xref)
                    
                    # Bỏ qua ảnh CMYK
                    if pix.n - pix.alpha < 4:
                        # Chuyển sang RGB nếu cần
                        if pix.n != 4:  # Not RGB
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        # Lấy image data
                        img_data = pix.tobytes("png")
                        
                        # Validate ảnh
                        is_valid, img_metadata = DocumentUtils.validate_image_data(img_data)
                        
                        if is_valid:
                            # Tối ưu hóa ảnh
                            optimized_img_data = DocumentUtils.optimize_image(img_data)
                            
                            # Lấy vị trí ảnh trên page (estimate)
                            img_rects = page.get_image_rects(xref)
                            position = 0
                            if img_rects:
                                # Ước tính vị trí dựa trên coordinate y
                                rect = img_rects[0]
                                page_height = page.rect.height
                                position = int((1 - rect.y0 / page_height) * 1000)  # Normalize to 0-1000
                            
                            images.append({
                                "image_data": optimized_img_data,
                                "position": position,
                                "page": page_num + 1,  # 1-based page numbering
                                "image_index_in_page": img_index,
                                "image_id": f"page_{page_num + 1}_img_{img_index}",
                                "metadata": {
                                    "width": pix.width,
                                    "height": pix.height,
                                    "format": "PNG",
                                    "original_xref": xref,
                                    **img_metadata
                                }
                            })
                    
                    pix = None  # Clean up
                    
                except Exception as e:
                    logger.warning(f"Error extracting image {img_index} from page {page_num}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting images from page {page_num}: {str(e)}")
        
        # Sắp xếp ảnh theo vị trí trên page
        images.sort(key=lambda x: x['position'])
        
        return images
    
    async def _create_page_content_with_images(self, page_text: str, page_images: List[Dict[str, Any]], 
                                             page_num: int) -> str:
        """
        Tạo nội dung page với image tags theo thứ tự xuất hiện
        
        Args:
            page_text: Text của page
            page_images: Danh sách ảnh trong page
            page_num: Số page
            
        Returns:
            str: Nội dung page với image tags
        """
        if not page_images:
            return page_text
        
        # Chia text thành paragraphs
        paragraphs = re.split(r'\n\s*\n', page_text)
        text_length = len(page_text)
        
        # Estimate vị trí của các đoạn text
        paragraph_positions = []
        current_pos = 0
        
        for para in paragraphs:
            if para.strip():
                paragraph_positions.append({
                    "content": para.strip(),
                    "position": current_pos,
                    "type": "text"
                })
            current_pos += len(para) + 2  # +2 for newlines
        
        # Thêm ảnh vào danh sách với vị trí
        all_items = paragraph_positions.copy()
        for img in page_images:
            # Tạo image tag với unique ID
            image_tag = f"<image:{img['image_id']}>"
            all_items.append({
                "content": image_tag,
                "position": img["position"],
                "type": "image",
                "image_data": img
            })
        
        # Sắp xếp theo vị trí
        all_items.sort(key=lambda x: x["position"])
        
        # Tạo content merged
        merged_content = ""
        
        for item in all_items:
            if item["type"] == "text":
                merged_content += item["content"] + "\n\n"
            else:
                # Chèn image tag
                merged_content += item["content"] + "\n\n"
        
        return merged_content.strip()
    
    async def _create_page_content_with_images(self, page_text: str, page_images: List[Dict[str, Any]], 
                                             page_num: int) -> str:
        """
        Tạo nội dung page với image tags
        
        Args:
            page_text: Text của page
            page_images: Danh sách ảnh trong page
            page_num: Số page
            
        Returns:
            str: Content với image tags
        """
        if not page_images:
            return page_text
        
        # Chia text thành paragraphs
        paragraphs = re.split(r'\n\s*\n', page_text)
        text_length = len(page_text)
        
        # Estimate vị trí của các đoạn text
        paragraph_positions = []
        current_pos = 0
        
        for para in paragraphs:
            if para.strip():
                paragraph_positions.append({
                    "content": para.strip(),
                    "position": current_pos,
                    "type": "text"
                })
            current_pos += len(para) + 2  # +2 for newlines
        
        # Thêm ảnh vào danh sách với vị trí
        all_items = paragraph_positions.copy()
        for img in page_images:
            all_items.append({
                "content": f"<image:{img['image_id']}>",
                "position": img["position"],
                "type": "image"
            })
        
        # Sắp xếp theo vị trí
        all_items.sort(key=lambda x: x["position"])
        
        # Tạo content merged
        merged_content = ""
        
        for item in all_items:
            if item["type"] == "text":
                merged_content += item["content"] + "\n\n"
            else:
                # Chèn image tag
                merged_content += item["content"] + "\n\n"
        
        return merged_content.strip()
    
    async def _extract_pdf_metadata(self, file_data: bytes) -> Dict[str, Any]:
        """
        Trích xuất metadata từ PDF
        
        Args:
            file_data: Dữ liệu PDF
            
        Returns:
            Dict[str, Any]: Metadata
        """
        try:
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            
            metadata = {
                "page_count": len(pdf_document),
                "pdf_version": pdf_document.pdf_version() if hasattr(pdf_document, 'pdf_version') else None,
                "is_encrypted": pdf_document.needs_pass,
                "permissions": pdf_document.permissions if hasattr(pdf_document, 'permissions') else None
            }
            
            # Lấy document metadata
            doc_metadata = pdf_document.metadata
            if doc_metadata:
                metadata.update({
                    "title": doc_metadata.get("title", ""),
                    "author": doc_metadata.get("author", ""),
                    "subject": doc_metadata.get("subject", ""),
                    "creator": doc_metadata.get("creator", ""),
                    "producer": doc_metadata.get("producer", ""),
                    "creation_date": doc_metadata.get("creationDate", ""),
                    "modification_date": doc_metadata.get("modDate", "")
                })
            
            pdf_document.close()
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {str(e)}")
            return {}
    
    def _estimate_text_position(self, text: str, total_text: str) -> int:
        """
        Ước tính vị trí của text trong document
        
        Args:
            text: Đoạn text cần tìm vị trí
            total_text: Toàn bộ text
            
        Returns:
            int: Vị trí ước tính (0-1000)
        """
        try:
            pos = total_text.find(text)
            if pos >= 0:
                return int((pos / len(total_text)) * 1000)
            return 0
        except:
            return 0
