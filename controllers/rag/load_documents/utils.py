"""
Document Processing Utilities
Các hàm tiện ích cho việc xử lý document
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime
import hashlib
import uuid
from PIL import Image
from io import BytesIO
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parents[3]  # Go up 3 levels to reach project root
sys.path.append(str(project_root))

from configs.environment import get_embedding

logger = logging.getLogger(__name__)

class DocumentUtils:
    """
    Các hàm tiện ích cho document processing
    """
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
        """
        Chia text thành các chunks với overlap
        
        Args:
            text: Text cần chia
            chunk_size: Kích thước mỗi chunk
            overlap: Số ký tự overlap giữa các chunk
            
        Returns:
            List[Dict]: Danh sách chunks với metadata
        """
        if not text or len(text.strip()) == 0:
            return []
            
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Tính end position
            end = start + chunk_size
            
            # Nếu không phải chunk cuối, tìm điểm cắt tốt (space, newline, sentence ending)
            if end < len(text):
                # Tìm điểm cắt tốt nhất trong 50 ký tự cuối
                search_start = max(end - 50, start)
                
                # Ưu tiên cắt tại câu (. ! ?)
                sentence_end = DocumentUtils._find_last_sentence_end(text, search_start, end)
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    # Nếu không tìm thấy kết thúc câu, cắt tại word boundary
                    word_end = DocumentUtils._find_last_word_boundary(text, search_start, end)
                    if word_end > start:
                        end = word_end
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    "content": chunk_text,
                    "chunk_index": chunk_index,
                    "start_position": start,
                    "end_position": end,
                    "length": len(chunk_text)
                })
                chunk_index += 1
            
            # Di chuyển start position với overlap
            start = max(end - overlap, start + 1)
            
            # Tránh infinite loop
            if start >= len(text):
                break
                
        return chunks
    
    @staticmethod
    def _find_last_sentence_end(text: str, start: int, end: int) -> int:
        """Tìm vị trí kết thúc câu cuối cùng trong đoạn text"""
        sentence_endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
        last_pos = -1
        
        for ending in sentence_endings:
            pos = text.rfind(ending, start, end)
            if pos > last_pos:
                last_pos = pos + len(ending) - 1
                
        return last_pos
    
    @staticmethod
    def _find_last_word_boundary(text: str, start: int, end: int) -> int:
        """Tìm word boundary cuối cùng"""
        pos = text.rfind(' ', start, end)
        if pos > start:
            return pos
        return end
    
    @staticmethod
    def detect_image_placeholders(text: str) -> List[Dict[str, Any]]:
        """
        Tìm các placeholder cho ảnh trong text (như [IMAGE], <image>, etc.)
        
        Args:
            text: Text cần tìm
            
        Returns:
            List[Dict]: Danh sách vị trí và loại placeholder
        """
        patterns = [
            r'\[IMAGE\]',
            r'\[image\]',
            r'<image>',
            r'<IMAGE>',
            r'\[FIGURE\]',
            r'\[figure\]',
            r'<figure>',
            r'<FIGURE>'
        ]
        
        placeholders = []
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                placeholders.append({
                    "pattern": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "position": match.start()
                })
        
        # Sắp xếp theo vị trí
        placeholders.sort(key=lambda x: x['position'])
        return placeholders
    
    @staticmethod
    def insert_image_tags(text: str, image_urls: List[str], positions: List[int] = None) -> str:
        """
        Chèn image tags vào text tại các vị trí cụ thể
        
        Args:
            text: Text gốc
            image_urls: Danh sách URLs của ảnh
            positions: Vị trí chèn (nếu None, sẽ chèn đều đặn)
            
        Returns:
            str: Text đã chèn image tags
        """
        if not image_urls:
            return text
            
        if not positions:
            # Chia đều các ảnh trong text
            text_length = len(text)
            positions = [int(i * text_length / (len(image_urls) + 1)) for i in range(1, len(image_urls) + 1)]
        
        # Sắp xếp theo thứ tự giảm dần để chèn từ cuối lên đầu
        url_pos_pairs = list(zip(image_urls, positions))
        url_pos_pairs.sort(key=lambda x: x[1], reverse=True)
        
        result_text = text
        for url, pos in url_pos_pairs:
            pos = min(pos, len(result_text))
            image_tag = f" <image:{url}> "
            result_text = result_text[:pos] + image_tag + result_text[pos:]
            
        return result_text
    
    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """
        Tạo embedding cho text
        
        Args:
            text: Text cần tạo embedding
            
        Returns:
            List[float]: Vector embedding
        """
        try:
            embeddings_model = get_embedding()
            embedding = await embeddings_model.aembed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return []
    
    @staticmethod
    def calculate_text_hash(text: str) -> str:
        """
        Tính hash cho text để detect duplicate
        
        Args:
            text: Text cần hash
            
        Returns:
            str: MD5 hash
        """
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    @staticmethod
    def validate_image_data(image_data: bytes) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate và lấy thông tin ảnh
        
        Args:
            image_data: Dữ liệu ảnh
            
        Returns:
            Tuple[bool, Dict]: (is_valid, metadata)
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                metadata = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height
                }
                
                # Kiểm tra kích thước hợp lệ
                if img.width < 10 or img.height < 10:
                    return False, {"error": "Image too small"}
                
                # Kiểm tra kích thước file
                if len(image_data) > 10 * 1024 * 1024:  # 10MB
                    return False, {"error": "Image too large"}
                
                return True, metadata
                
        except Exception as e:
            logger.error(f"Error validating image: {str(e)}")
            return False, {"error": str(e)}
    
    @staticmethod
    def optimize_image(image_data: bytes, max_width: int = 1200, quality: int = 85) -> bytes:
        """
        Tối ưu hóa ảnh (resize và compress)
        
        Args:
            image_data: Dữ liệu ảnh gốc
            max_width: Chiều rộng tối đa
            quality: Chất lượng JPEG (1-100)
            
        Returns:
            bytes: Dữ liệu ảnh đã tối ưu
        """
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Chuyển sang RGB nếu cần
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize nếu cần
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                
                # Lưu với quality được chỉ định
                output = BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            logger.error(f"Error optimizing image: {str(e)}")
            return image_data  # Trả về ảnh gốc nếu có lỗi
    
    @staticmethod
    def generate_unique_id() -> str:
        """Tạo unique ID"""
        return str(uuid.uuid4())
    
    @staticmethod
    def format_timestamp() -> str:
        """Tạo timestamp string"""
        return datetime.now().isoformat()
    
    @staticmethod
    def clean_filename(filename: str) -> str:
        """
        Làm sạch tên file
        
        Args:
            filename: Tên file gốc
            
        Returns:
            str: Tên file đã làm sạch
        """
        # Loại bỏ các ký tự không an toàn
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Loại bỏ spaces đầu cuối
        filename = filename.strip()
        
        # Giới hạn độ dài
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            max_name_length = 255 - len(ext) - 1
            filename = name[:max_name_length] + '.' + ext if ext else name[:255]
        
        return filename
