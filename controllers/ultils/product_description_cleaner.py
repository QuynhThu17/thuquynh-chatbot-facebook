import re
from bs4 import BeautifulSoup
from typing import List, Tuple, Optional

class ProductDescriptionCleaner:
    """
    Class để làm sạch mô tả sản phẩm HTML thành text dễ đọc
    Sử dụng cho nhiều trường hợp khác nhau
    """
    
    def __init__(self):
        # Các thẻ HTML sẽ bị loại bỏ hoàn toàn
        self.unwanted_tags = [
            'style', 'script', 'meta', 'link', 'title', 'head',
            'caption', 'iframe', 'img', 'video', 'audio', 'figure',
            'figcaption', 'embed', 'object', 'param', 'source'
        ]
        
        # Các pattern HTML cần làm sạch
        self.html_patterns = [
            r'caption\s+id[^>]*>',
            r'caption$',
            r'\[/?caption[^\]]*\]',
            r'align["\'][^"\']*["\']',
            r'width["\'][^"\']*["\']', 
            r'id["\'][^"\']*["\']',
            r'class["\'][^"\']*["\']',
        ]
    
    def clean_description(self, html_content: str) -> str:
        """
        Làm sạch một mô tả HTML
        
        Args:
            html_content (str): Nội dung HTML cần làm sạch
            
        Returns:
            str: Text đã được làm sạch và format
        """
        if not html_content or not html_content.strip():
            return ""
        
        # Làm sạch HTML patterns trước
        html_content = self._clean_html_patterns(html_content)
        
        # Parse HTML với BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Xóa các thẻ không cần thiết
        for tag in self.unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # Xử lý các thẻ cần giữ cấu trúc
        self._preserve_structure(soup)
        
        # Lấy text và làm sạch cuối cùng
        clean_text = soup.get_text(separator='\n')
        
        return self._final_text_cleanup(clean_text)
    
    def _clean_html_patterns(self, html_content: str) -> str:
        """Làm sạch các HTML pattern không cần thiết"""
        # Loại bỏ caption shortcode
        html_content = re.sub(r'\[/?caption[^\]]*\]', '', html_content)
        
        # Loại bỏ các attribute không cần thiết
        for pattern in self.html_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.IGNORECASE)
        
        return html_content
    
    def _preserve_structure(self, soup):
        """Xử lý các thẻ HTML nhưng giữ nguyên cấu trúc"""
        
        # Xử lý danh sách trước để format đúng
        self._format_lists(soup)
        
        # Xử lý blockquote - giữ nguyên xuống dòng
        for blockquote in soup.find_all('blockquote'):
            blockquote.insert_before('\n\n')
            blockquote.insert_after('\n\n')
        
        # Xử lý tiêu đề - thêm xuống dòng
        for i in range(1, 7):
            for heading in soup.find_all(f'h{i}'):
                heading.insert_before('\n\n')
                heading.insert_after('\n\n')
        
        # Xử lý paragraph - thêm xuống dòng
        for p in soup.find_all('p'):
            p.insert_after('\n\n')
    
    def _format_lists(self, soup):
        """Format danh sách ul và ol với bullet points"""
        # Xử lý danh sách ul
        for ul in soup.find_all('ul'):
            ul.insert_before('\n\n')
            
            # Xử lý từng li
            for li in ul.find_all('li'):
                # Lấy nội dung của li và thêm bullet
                li_text = li.get_text(separator=' ', strip=True)
                if li_text:
                    # Tạo text với bullet point
                    li.clear()
                    li.string = f"• {li_text}"
                    li.insert_after('\n')
            
            ul.insert_after('\n\n')
        
        # Xử lý danh sách ol
        for ol in soup.find_all('ol'):
            ol.insert_before('\n\n')
            
            # Xử lý từng li với số thứ tự
            for idx, li in enumerate(ol.find_all('li'), 1):
                li_text = li.get_text(separator=' ', strip=True)
                if li_text:
                    # Tạo text với số thứ tự
                    li.clear()
                    li.string = f"{idx}. {li_text}"
                    li.insert_after('\n')
            
            ol.insert_after('\n\n')
    
    def _final_text_cleanup(self, text: str) -> str:
        """Làm sạch text cuối cùng nhưng giữ nguyên cấu trúc"""
        
        # Loại bỏ URL, phone, email trước
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'\b\d{4}[\.\-]?\d{3}[\.\-]?\d{3}\b', '[Hotline]', text)
        text = re.sub(r'\S+@\S+\.\S+', '[Email]', text)
        
        # Tách thành các dòng và xử lý
        lines = text.split('\n')
        cleaned_lines = []
        prev_line = ""
        
        for line in lines:
            line = line.strip()
            
            # Bỏ qua dòng trống liên tiếp quá nhiều
            if not line:
                if cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')
                continue
            
            # Chuẩn hóa khoảng trắng trong dòng
            line = re.sub(r'[ \t]+', ' ', line)
            
            # Tránh trùng lặp nội dung
            if line != prev_line and len(line) > 3:
                cleaned_lines.append(line)
                prev_line = line
        
        # Gộp lại và làm sạch cuối
        result = '\n'.join(cleaned_lines)
        
        # Giảm nhiều dòng trống thành tối đa 2 dòng
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # Loại bỏ khoảng trắng đầu cuối
        result = result.strip()
        
        return result
    
    def _final_cleanup(self, text: str) -> str:
        """Làm sạch cuối cùng - loại bỏ URL, phone, email"""
        # Loại bỏ URL
        text = re.sub(r'https?://[^\s]+', '', text)
        
        # Loại bỏ số điện thoại
        text = re.sub(r'\b\d{4}[\.\-]?\d{3}[\.\-]?\d{3}\b', '[Hotline]', text)
        
        # Loại bỏ email  
        text = re.sub(r'\S+@\S+\.\S+', '[Email]', text)
        
        # Loại bỏ ký tự đặc biệt không cần thiết
        text = re.sub(r'[^\w\s\.,;:!?\-"•#\(\)]', ' ', text, flags=re.UNICODE)
        
        # Chuẩn hóa khoảng trắng
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        return text
    
    def create_summary(self, text: str, max_length: int = 500) -> str:
        """
        Tạo tóm tắt từ text dài
        
        Args:
            text (str): Text gốc
            max_length (int): Độ dài tối đa của tóm tắt
            
        Returns:
            str: Text tóm tắt
        """
        if len(text) <= max_length:
            return text
            
        sentences = re.split(r'[.!?]+', text)
        summary_sentences = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence and not sentence.startswith(('##', '###', '•')):
                if current_length + len(sentence) <= max_length:
                    summary_sentences.append(sentence)
                    current_length += len(sentence)
                else:
                    break
        
        result = '. '.join(summary_sentences)
        if result and not result.endswith('.'):
            result += '.'
            
        return result if result else text[:max_length]
    
    def process_multiple(self, *descriptions) -> Tuple[List[str], List[str]]:
        """
        Xử lý nhiều mô tả cùng lúc
        
        Args:
            *descriptions: Các mô tả HTML cần xử lý
            
        Returns:
            Tuple[List[str], List[str]]: (cleaned_descriptions, summaries)
        """
        cleaned_results = []
        summaries = []
        
        for desc in descriptions:
            cleaned = self.clean_description(desc)
            summary = self.create_summary(cleaned)
            
            cleaned_results.append(cleaned)
            summaries.append(summary)
        
        return cleaned_results, summaries
    
    def save_results(self, 
                    cleaned_results: List[str], 
                    summaries: List[str],
                    cleaned_filename: str = 'cleaned_descriptions.txt',
                    summary_filename: str = 'summaries.txt'):
        """
        Lưu kết quả vào file
        
        Args:
            cleaned_results (List[str]): Danh sách mô tả đã làm sạch
            summaries (List[str]): Danh sách tóm tắt
            cleaned_filename (str): Tên file cho mô tả đầy đủ
            summary_filename (str): Tên file cho tóm tắt
        """
        # Lưu mô tả đầy đủ
        with open(cleaned_filename, 'w', encoding='utf-8') as f:
            for i, result in enumerate(cleaned_results, 1):
                f.write(f"=== MÔ TẢ ĐẦY ĐỦ {i} ===\n\n")
                f.write(result)
                f.write(f"\n\n{'='*50}\n\n")
        
        # Lưu tóm tắt
        with open(summary_filename, 'w', encoding='utf-8') as f:
            for i, summary in enumerate(summaries, 1):
                f.write(f"=== TÓM TẮT MÔ TẢ {i} ===\n\n")
                f.write(summary)
                f.write(f"\n\n{'='*30}\n\n")


cleaner = ProductDescriptionCleaner()

