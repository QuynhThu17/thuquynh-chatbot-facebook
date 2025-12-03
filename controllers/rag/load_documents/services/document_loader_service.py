"""
Document Loader Service
Service chính để orchestrate việc load và xử lý documents
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import os
from io import BytesIO
import sys
from pathlib import Path

# Add project directories to path
current_dir = Path(__file__).parent
load_documents_dir = current_dir.parent
project_root = load_documents_dir.parents[2]  # Go up to project root
sys.path.append(str(load_documents_dir))
sys.path.append(str(project_root))

from chunkers import ChunkerFactory, ChunkResult
from embedders import EmbedderFactory, EmbeddingResult
from processors.base_processor import BaseDocumentProcessor, DocumentContent, ProcessedChunk, PageContent
from processors.docling_processor import DoclingProcessor
from processors.ragflow_parser import get_ragflow_parser
from storage.s3_service import S3Service
from controllers.rag.load_documents.utils import DocumentUtils

# Import các managers từ project
from controllers.data.managements.knowledge_management import (
    KnowledgeChunkManager, 
    DocumentManager
)
from controllers.databases.mongodb.mongodb import MongoDBManager
from configs.environment import get_embedding

logger = logging.getLogger(__name__)

class DocumentLoaderService:
    """
    Service chính để load và xử lý documents
    Tích hợp với knowledge management system hiện có
    """
    
    def __init__(self, db_manager: MongoDBManager):
        """
        Khởi tạo DocumentLoaderService
        
        Args:
            db_manager: MongoDB manager instance
        """
        self.db_manager = db_manager
        self.knowledge_chunk_manager = KnowledgeChunkManager(db_manager)
        self.document_manager = DocumentManager(db_manager)
        self.s3_service = S3Service()
        
        self.processors = {
            '.pdf': DoclingProcessor(),
            '.docx': DoclingProcessor(),
            '.pptx': DoclingProcessor(),
            '.xlsx': DoclingProcessor(),
            '.xls': DoclingProcessor(),
            '.html': DoclingProcessor(),
            '.htm': DoclingProcessor(),
            '.png': DoclingProcessor(),
            '.jpg': DoclingProcessor(),
            '.jpeg': DoclingProcessor(),
            '.gif': DoclingProcessor(),
            '.bmp': DoclingProcessor(),
            '.tiff': DoclingProcessor(),
        }
        
        # Initialize RAGFlow parser (mặc định)
        try:
            self.ragflow_parser = get_ragflow_parser()
            self.use_ragflow = True
            logger.info("RAGFlow parser enabled as default")
        except Exception as e:
            logger.warning(f"RAGFlow parser not available, using legacy processors: {str(e)}")
            self.ragflow_parser = None
            self.use_ragflow = False
        
        # Initialize Enhanced RAG factories
        self.chunker_factory = ChunkerFactory()
        self.embedder_factory = EmbedderFactory()
        
        logger.info("DocumentLoaderService initialized with Enhanced RAG capabilities")
    
    @staticmethod
    def _run_processor_extract(processor, file_name: str, file_data: bytes):
        """Execute processor.extract_content inside a dedicated event loop."""
        return asyncio.run(processor.extract_content(file_name, file_data))
    
    async def process_document(self, file_data: bytes, file_name: str, 
                              user_id: str, company_id: str = None,
                              processing_options: Optional[Dict[str, Any]] = None, document_name: str = "") -> Dict[str, Any]:
        """
        Xử lý document với Enhanced RAG System - tự động chọn chunking strategy tối ưu
        
        Args:
            file_data: Dữ liệu file
            file_name: Tên file
            user_id: ID người dùng
            company_id: ID công ty (optional)
            processing_options: Tùy chọn xử lý (optional) - có thể bao gồm "process_images": True/False
            document_name: Tên document tùy chỉnh
            
        Returns:
            Dict[str, Any]: Kết quả xử lý với enhanced metrics
        """
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting Enhanced RAG document processing: {file_name} for user {user_id}")
            
            # Get process_images flag from options (default: False)
            process_images = processing_options.get("process_images", False) if processing_options else False
            
            parser_engine = processing_options.get("parser_engine", "docling") if processing_options else "docling"
            
            # Override use_ragflow based on parser_engine
            use_ragflow_for_this_doc = (parser_engine == "ragflow") and self.use_ragflow
            
            logger.info(f"Processing {file_name} with parser_engine={parser_engine}, process_images={process_images}")
            
            # 1. Phân tích document để chọn strategy tối ưu
            analysis = await self._analyze_document_for_optimal_strategy(file_data, file_name)
            logger.info(f"Document analysis completed: type={analysis['file_type']}, "
                       f"complexity={analysis['complexity_score']:.2f}, "
                       f"recommended_strategy={analysis['recommended_chunker']}")
            
            # 2. Extract content
            file_extension = os.path.splitext(file_name)[1].lower()
            if not self._can_process_file(file_extension):
                raise ValueError(f"Unsupported file type: {file_extension}")
                
            document_content = await self._extract_document_content(
                file_data, file_name, file_extension, process_images, use_ragflow_for_this_doc
            )
            
            # 3. Upload document gốc lên S3
            original_url = await self.s3_service.upload_document(
                file_data, file_name, user_id
            )
            
            # 4. Tạo document record trong DB
            document_record = await self.document_manager.create_document(
                document_name=document_name or file_name,
                file_name=file_name,
                file_type=file_extension,
                storage_type="s3",
                storage_url=original_url or "",
                user_id=user_id,
                title=document_content.metadata.get("title", file_name),
                content="",  # Sẽ update sau
                status="processing",
                company_id=company_id
            )
            
            document_id = str(document_record["_id"])
            
            # 5. Upload images lên S3 với page tracking (nếu process_images=True)
            image_urls_mapping = {}
            if process_images and document_content.total_images:
                logger.info(f"Processing {len(document_content.total_images)} images with deduplication...")
                image_urls_mapping = await self._upload_images_to_s3_with_deduplication(
                    document_content.total_images, user_id, document_id, file_name
                )
                logger.info(f"Uploaded {len(image_urls_mapping)} unique images (deduplicated from {len(document_content.total_images)})")
            else:
                logger.info(f"Image processing skipped (process_images={process_images})")
            
            # 6. Tạo page-aware chunks với Enhanced RAG
            chunking_result = await self._create_page_aware_knowledge_chunks(
                document_content, 
                document_id, 
                user_id, 
                company_id,
                analysis,
                image_urls_mapping
            )
            
            # 7. Update document record với final content
            await self.document_manager.update_content(
                document_id, document_content.total_text_content, "processed"
            )
            
            # 9. Tính toán processing metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                "success": True,
                "document_id": document_id,
                "processing_time": processing_time,
                "analysis": analysis,
                "chunks_created": chunking_result["total_chunks"],
                "chunk_strategy_used": chunking_result["strategy_used"],
                "chunk_quality_score": chunking_result["quality_score"],
                "embedding_strategy_used": chunking_result["embedding_strategy"],
                "images_processed": len(image_urls_mapping),
                "original_url": original_url,
                "metadata": document_content.metadata,
                "chunk_ids": chunking_result["chunk_ids"],
                "processing_stats": {
                    "avg_chunk_size": chunking_result["avg_chunk_size"],
                    "chunks_per_strategy": chunking_result.get("chunks_per_strategy", {}),
                    "embedding_performance": chunking_result.get("embedding_performance", {}),
                    "quality_metrics": chunking_result.get("quality_metrics", {})
                }
            }
            
            logger.info(f"Enhanced RAG processing completed: {file_name} in {processing_time:.2f}s, "
                       f"strategy={chunking_result['strategy_used']}, "
                       f"chunks={chunking_result['total_chunks']}, "
                       f"quality={chunking_result['quality_score']:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced document processing {file_name}: {str(e)}")
            # Cleanup nếu có lỗi
            try:
                if 'document_id' in locals():
                    await self._cleanup_failed_processing(document_id, image_urls_mapping if 'image_urls_mapping' in locals() else {})
            except:
                pass
            raise
    
    async def _extract_document_content(self, file_data: bytes, file_name: str, 
                                       file_extension: str, process_images: bool = False, 
                                       use_ragflow: bool = True) -> DocumentContent:
        """
        Trích xuất nội dung từ document - ưu tiên dùng RAGFlow
        
        Args:
            file_data: Dữ liệu file
            file_name: Tên file
            file_extension: Extension file
            process_images: Có xử lý ảnh hay không
            use_ragflow: Có dùng RAGFlow parser hay không
            
        Returns:
            DocumentContent: Nội dung đã trích xuất
        """
        # Thử dùng RAGFlow trước nếu có và được yêu cầu
        if use_ragflow and self.ragflow_parser:
            try:
                logger.info(f"Using RAGFlow parser for {file_name}")
                sections, tables = await self.ragflow_parser.parse(file_data, file_name, file_extension)
                
                # Convert RAGFlow output sang DocumentContent format
                return self._convert_ragflow_to_document_content(sections, tables, file_name, file_extension)
                
            except Exception as e:
                logger.warning(f"RAGFlow parsing failed, falling back to legacy: {str(e)}")
                # Fall through to legacy processors
        
        # Fallback to legacy processors
        logger.info(f"Using legacy processor for {file_name}")
        processor = self.processors.get(file_extension)
        if not processor:
            raise ValueError(f"No processor found for {file_extension}")
        
        # Set process_images flag for processor
        if hasattr(processor, 'process_images'):
            processor.process_images = process_images
        
        return await asyncio.to_thread(
            self._run_processor_extract,
            processor,
            file_name,
            file_data
        )
    
    def _convert_ragflow_to_document_content(self, sections: List[Dict], tables: List[Dict], 
                                            file_name: str, file_extension: str) -> DocumentContent:
        """
        Convert RAGFlow parsed data sang DocumentContent format
        
        Args:
            sections: RAGFlow sections
            tables: RAGFlow tables
            file_name: File name
            file_extension: File extension
            
        Returns:
            DocumentContent: Converted content
        """
        pages = []
        all_images = []
        total_text_content = ""
        
        # Group sections by page (for PDF) or create single page for other formats
        if file_extension.lower() == '.pdf':
            # PDF: group by page
            page_sections = {}
            for section in sections:
                page_num = section.get('page', 1)
                if page_num not in page_sections:
                    page_sections[page_num] = []
                page_sections[page_num].append(section['text'])
            
            for page_num in sorted(page_sections.keys()):
                page_text = "\n\n".join(page_sections[page_num])
                total_text_content += page_text + "\n\n"
                
                page_content = PageContent(
                    page_number=page_num,
                    text_content=page_text,
                    full_content=page_text,
                    images=[],  # RAGFlow không extract images trong version này
                    page_metadata={
                        "page_number": page_num,
                        "text_length": len(page_text),
                        "image_count": 0,
                        "parser": "ragflow"
                    }
                )
                pages.append(page_content)
        else:
            # DOCX/Excel: single page
            all_text = "\n\n".join([s.get('text', '') for s in sections])
            total_text_content = all_text
            
            page_content = PageContent(
                page_number=1,
                text_content=all_text,
                full_content=all_text,
                images=[],
                page_metadata={
                    "page_number": 1,
                    "text_length": len(all_text),
                    "image_count": 0,
                    "parser": "ragflow"
                }
            )
            pages.append(page_content)
        
        # Add tables to content
        for table in tables:
            total_text_content += "\n\n" + table.get('html', '')
        
        metadata = {
            "title": file_name,
            "file_type": file_extension,
            "parser": "ragflow",
            "sections_count": len(sections),
            "tables_count": len(tables)
        }
        
        return DocumentContent(
            pages=pages,
            total_text_content=total_text_content.strip(),
            total_images=all_images,
            metadata=metadata
        )
    
    async def _upload_images_to_s3(self, images: List[Dict[str, Any]], 
                                  user_id: str, document_id: str, 
                                  file_name: str) -> List[str]:
        """
        Upload tất cả ảnh lên S3
        
        Args:
            images: Danh sách ảnh
            user_id: ID người dùng
            document_id: ID document
            file_name: Tên file gốc
            
        Returns:
            List[str]: Danh sách URLs
        """
        image_urls = []
        
        for i, img_data in enumerate(images):
            try:
                # Determine content type
                img_format = img_data.get("metadata", {}).get("format", "JPEG")
                content_type = f"image/{img_format.lower()}"
                
                # Upload ảnh
                url = await self.s3_service.upload_image(
                    img_data["image_data"],
                    file_name,
                    user_id,
                    document_id,
                    i,
                    content_type
                )
                
                if url:
                    image_urls.append(url)
                    logger.info(f"Uploaded image {i+1}/{len(images)} for document {document_id}")
                else:
                    logger.warning(f"Failed to upload image {i+1} for document {document_id}")
                    
            except Exception as e:
                logger.error(f"Error uploading image {i}: {str(e)}")
                continue
        
        return image_urls
    
    async def _upload_images_to_s3_with_pages(self, images: List[Dict[str, Any]], 
                                            user_id: str, document_id: str, 
                                            file_name: str) -> Dict[str, str]:
        """
        Upload tất cả ảnh lên S3 với tracking thông tin page
        
        Args:
            images: Danh sách ảnh với page info
            user_id: ID người dùng
            document_id: ID document
            file_name: Tên file gốc
            
        Returns:
            Dict[str, str]: Mapping từ image_id -> URL
        """
        image_urls_mapping = {}
        
        for img_data in images:
            try:
                image_id = img_data.get("image_id", f"page_{img_data['page']}_img_{img_data.get('image_index_in_page', 0)}")
                
                # Determine content type
                img_format = img_data.get("metadata", {}).get("format", "JPEG")
                content_type = f"image/{img_format.lower()}"
                
                # Upload ảnh với unique filename
                unique_filename = f"{file_name}_page_{img_data['page']}_{img_data.get('image_index_in_page', 0)}"
                url = await self.s3_service.upload_image(
                    img_data["image_data"],
                    unique_filename,
                    user_id,
                    document_id,
                    img_data.get('image_index_in_page', 0),
                    content_type
                )
                
                if url:
                    image_urls_mapping[image_id] = url
                    logger.info(f"Uploaded image {image_id} for document {document_id}")
                else:
                    logger.warning(f"Failed to upload image {image_id} for document {document_id}")
                    
            except Exception as e:
                logger.error(f"Error uploading image {img_data.get('image_id', 'unknown')}: {str(e)}")
                continue
        
        return image_urls_mapping
    
    async def _upload_images_to_s3_with_deduplication(self, images: List[Dict[str, Any]], 
                                                      user_id: str, document_id: str, 
                                                      file_name: str) -> Dict[str, str]:
        """
        Upload ảnh lên S3 với deduplication (tránh upload ảnh trùng lặp như logo)
        
        Args:
            images: Danh sách ảnh với page info
            user_id: ID người dùng
            document_id: ID document
            file_name: Tên file gốc
            
        Returns:
            Dict[str, str]: Mapping từ image_id -> URL
        """
        import hashlib
        
        image_urls_mapping = {}
        image_hash_to_url = {}  # Cache: hash -> URL để tái sử dụng
        duplicate_count = 0
        
        for img_data in images:
            try:
                image_id = img_data.get("image_id", f"page_{img_data['page']}_img_{img_data.get('image_index_in_page', 0)}")
                
                # Tính hash của ảnh để detect duplicates
                image_bytes = img_data["image_data"]
                image_hash = hashlib.md5(image_bytes).hexdigest()
                
                # Kiểm tra xem ảnh này đã upload chưa
                if image_hash in image_hash_to_url:
                    # Ảnh trùng lặp, dùng lại URL
                    url = image_hash_to_url[image_hash]
                    image_urls_mapping[image_id] = url
                    duplicate_count += 1
                    logger.info(f"Reusing URL for duplicate image {image_id} (hash: {image_hash[:8]}...)")
                    continue
                
                # Determine content type
                img_format = img_data.get("metadata", {}).get("format", "JPEG")
                content_type = f"image/{img_format.lower()}"
                
                # Upload ảnh với unique filename
                unique_filename = f"{file_name}_page_{img_data['page']}_{img_data.get('image_index_in_page', 0)}"
                url = await self.s3_service.upload_image(
                    image_bytes,
                    unique_filename,
                    user_id,
                    document_id,
                    img_data.get('image_index_in_page', 0),
                    content_type
                )
                
                if url:
                    image_urls_mapping[image_id] = url
                    image_hash_to_url[image_hash] = url  # Cache URL cho lần sau
                    logger.info(f"Uploaded new image {image_id} for document {document_id} (hash: {image_hash[:8]}...)")
                else:
                    logger.warning(f"Failed to upload image {image_id} for document {document_id}")
                    
            except Exception as e:
                logger.error(f"Error uploading image {img_data.get('image_id', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Image upload completed: {len(image_urls_mapping)} unique URLs, {duplicate_count} duplicates reused")
        return image_urls_mapping
    
    async def _create_text_with_image_tags(self, text_content: str, 
                                          image_urls: List[str],
                                          images: List[Dict[str, Any]]) -> str:
        """
        Tạo text content với image tags theo đúng vị trí
        
        Args:
            text_content: Text gốc
            image_urls: URLs của ảnh
            images: Metadata ảnh với vị trí
            
        Returns:
            str: Text với image tags
        """
        if not image_urls or not images:
            return text_content
        
        try:
            # Tạo mapping giữa ảnh và URL
            url_mapping = {}
            for i, url in enumerate(image_urls):
                if i < len(images):
                    url_mapping[i] = url
            
            # Replace image placeholders bằng URLs
            result_text = text_content
            
            # Tìm và replace các placeholder [IMAGE_X]
            import re
            placeholder_pattern = r'\[IMAGE_(\d+)\]'
            
            def replace_placeholder(match):
                img_index = int(match.group(1)) - 1  # Convert to 0-based
                if img_index in url_mapping:
                    return f"<image:{url_mapping[img_index]}>"
                return match.group(0)  # Keep original if no URL
            
            result_text = re.sub(placeholder_pattern, replace_placeholder, result_text)
            
            # Nếu không có placeholder, chèn ảnh vào cuối mỗi section
            if not re.search(placeholder_pattern, text_content):
                # Chia text thành sections và chèn ảnh
                sections = result_text.split('\n\n')
                if len(sections) > 1 and image_urls:
                    # Chèn ảnh đều đặn giữa các sections
                    section_per_image = max(1, len(sections) // len(image_urls))
                    
                    new_sections = []
                    img_index = 0
                    
                    for i, section in enumerate(sections):
                        new_sections.append(section)
                        
                        # Chèn ảnh sau mỗi section_per_image sections
                        if (i + 1) % section_per_image == 0 and img_index < len(image_urls):
                            new_sections.append(f"<image:{image_urls[img_index]}>")
                            img_index += 1
                    
                    # Thêm ảnh còn lại vào cuối
                    while img_index < len(image_urls):
                        new_sections.append(f"<image:{image_urls[img_index]}>")
                        img_index += 1
                    
                    result_text = '\n\n'.join(new_sections)
            
            return result_text
            
        except Exception as e:
            logger.error(f"Error creating text with image tags: {str(e)}")
            # Fallback: thêm tất cả ảnh vào cuối
            image_tags = [f"<image:{url}>" for url in image_urls]
            return text_content + "\n\n" + "\n".join(image_tags)
    
    async def _create_knowledge_chunks(self, text_content: str, document_id: str,
                                      user_id: str, company_id: str,
                                      chunk_size: int, overlap: int,
                                      metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tạo knowledge chunks từ text content với bulk insert để tối ưu hiệu suất
        
        Args:
            text_content: Text content đã có image tags
            document_id: ID document
            user_id: ID người dùng
            company_id: ID công ty
            chunk_size: Kích thước chunk
            overlap: Overlap
            metadata: Document metadata
            
        Returns:
            List[Dict]: Danh sách chunks đã tạo
        """
        try:
            # Chia text thành chunks
            text_chunks = DocumentUtils.chunk_text(text_content, chunk_size, overlap)
            logger.info(f"Split text into {len(text_chunks)} chunks for document {document_id}")
            
            # Chuẩn bị data cho bulk insert
            chunks_data = []
            
            # Tạo embeddings cho tất cả chunks
            for chunk_data in text_chunks:
                try:
                    # Tạo embedding cho chunk
                    embedding = await DocumentUtils.generate_embedding(str(chunk_data["content"]).lower())
                    
                    if not embedding:
                        logger.warning(f"Could not generate embedding for chunk {chunk_data['chunk_index']}")
                        continue
                    
                    # Tạo source info
                    source_info = {
                        "type": "document",
                        "source_id": document_id,
                        "title": metadata.get("title", metadata.get("file_name", "Unknown"))
                    }
                    
                    # Tạo chunk metadata
                    chunk_metadata = {
                        "chunk_index": chunk_data["chunk_index"],
                        "start_position": chunk_data["start_position"],
                        "end_position": chunk_data["end_position"],
                        "chunk_length": chunk_data["length"],
                        "page_number": metadata.get("page_count", 1),
                        "document_metadata": metadata,
                        "processed_at": DocumentUtils.format_timestamp()
                    }
                    
                    # Chuẩn bị chunk data cho bulk insert
                    chunk_doc = {
                        "content": chunk_data["content"],
                        "content_embedding": embedding,
                        "source_info": source_info,
                        "metadata": chunk_metadata,
                        "user_id": user_id,
                        "company_id": company_id
                    }
                    chunks_data.append(chunk_doc)
                    
                except Exception as e:
                    logger.error(f"Error preparing chunk {chunk_data['chunk_index']}: {str(e)}")
                    continue
            
            if not chunks_data:
                logger.warning(f"No valid chunks to insert for document {document_id}")
                return []
            
            # Bulk insert tất cả chunks cùng lúc
            logger.info(f"Bulk inserting {len(chunks_data)} chunks for document {document_id}")
            chunks = await self.knowledge_chunk_manager.bulk_create_chunks(chunks_data)
            logger.info(f"Successfully created {len(chunks)} chunks for document {document_id}")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error creating knowledge chunks: {str(e)}")
            raise
    
    async def _analyze_document_for_optimal_strategy(self, file_data: bytes, file_name: str) -> Dict[str, Any]:
        """
        Phân tích document để chọn chunking strategy tối ưu
        
        Args:
            file_data: File data
            file_name: File name
            
        Returns:
            Dict: Analysis results với recommended strategies
        """
        file_extension = os.path.splitext(file_name)[1].lower()
        file_size = len(file_data)
        
        analysis = {
            'file_name': file_name,
            'file_extension': file_extension,
            'file_size': file_size,
            'file_type': self._determine_file_type(file_extension),
            'complexity_score': 0.5,
            'estimated_content_length': file_size,
            'has_structure': False,
            'is_narrative': False,
            'language': 'auto',
            'recommended_chunker': 'semantic',  # Force semantic chunking
            'recommended_embedder': 'contextual',
            'optimal_chunk_size': 256,  # Fixed chunk size
            'optimal_overlap': 0  # No overlap
        }
        
        # Force semantic chunking with fixed parameters for all file types
        if file_extension in ['.pdf']:
            analysis['file_type'] = 'pdf'
            analysis['estimated_content_length'] = file_size * 2  # PDF có thể có text ít hơn file size
            analysis['has_structure'] = True
            analysis['recommended_chunker'] = 'semantic'  # Force semantic chunking
            analysis['optimal_chunk_size'] = 256  # Fixed chunk size
            analysis['optimal_overlap'] = 0  # No overlap
            
        elif file_extension in ['.docx', '.doc']:
            analysis['file_type'] = 'word'
            analysis['is_narrative'] = True
            analysis['recommended_chunker'] = 'semantic'  # Force semantic chunking
            analysis['optimal_chunk_size'] = 256  # Fixed chunk size
            analysis['optimal_overlap'] = 0  # No overlap
            
        elif file_extension in ['.xlsx', '.xls']:
            analysis['file_type'] = 'excel'
            analysis['has_structure'] = True
            analysis['recommended_chunker'] = 'semantic'  # Force semantic chunking
            analysis['optimal_chunk_size'] = 256  # Fixed chunk size
            analysis['optimal_overlap'] = 0  # No overlap
            
        elif file_extension in ['.txt']:
            analysis['file_type'] = 'text'
            analysis['is_narrative'] = True
            analysis['recommended_chunker'] = 'semantic'  # Force semantic chunking
            analysis['optimal_chunk_size'] = 256  # Fixed chunk size
            analysis['optimal_overlap'] = 0  # No overlap
        
        # Advanced analysis if we can peek at content
        try:
            processor = self.processors.get(file_extension)
            if processor and file_size < 1024 * 1024:  # Only for files < 1MB
                # Quick content peek
                content_peek = await self._quick_content_peek(file_data, file_name, processor)
                if content_peek:
                    analysis.update(content_peek)
        except Exception as e:
            logger.debug(f"Could not perform advanced analysis: {str(e)}")
        
        # Final strategy selection based on analysis
        analysis['recommended_chunker'] = self._select_optimal_chunker(analysis)
        analysis['recommended_embedder'] = self._select_optimal_embedder(analysis)
        
        return analysis
    
    async def _quick_content_peek(self, file_data: bytes, file_name: str, processor) -> Dict[str, Any]:
        """
        Quick peek at content for better analysis
        """
        try:
            # Extract small portion of content for analysis
            content = await asyncio.to_thread(
                self._run_processor_extract,
                processor,
                file_name,
                file_data
            )
            text = content.total_text_content[:2000]  # First 2000 chars
            
            if not text:
                return {}
            
            # Analyze text characteristics
            complexity = self._calculate_text_complexity(text)
            language = self._detect_text_language(text)
            has_structure = self._detect_text_structure(text)
            
            return {
                'complexity_score': complexity,
                'language': language,
                'has_structure': has_structure,
                'is_narrative': complexity > 0.6 and not has_structure,
                'sample_text_length': len(text)
            }
            
        except Exception as e:
            logger.debug(f"Error in content peek: {str(e)}")
            return {}
    
    def _determine_file_type(self, file_extension: str) -> str:
        """Determine file type category"""
        mapping = {
            '.pdf': 'pdf',
            '.docx': 'word', '.doc': 'word',
            '.xlsx': 'excel', '.xls': 'excel',
            '.txt': 'text'
        }
        return mapping.get(file_extension, 'unknown')
    
    def _select_optimal_chunker(self, analysis: Dict[str, Any]) -> str:
        """
        Select optimal chunker based on analysis
        """
        file_type = analysis['file_type']
        complexity = analysis['complexity_score']
        has_structure = analysis['has_structure']
        is_narrative = analysis['is_narrative']
        file_size = analysis['file_size']
        
        # Rule-based selection
        if file_type == 'pdf' and file_size > 1024 * 1024:  # Large PDF
            return 'hierarchical'
        elif file_type == 'excel' or (has_structure and not is_narrative):
            return 'recursive'
        elif is_narrative and complexity > 0.6:
            return 'semantic'
        elif file_size > 5 * 1024 * 1024:  # Very large files
            return 'hierarchical'
        else:
            return 'adaptive'  # Let adaptive decide
    
    def _select_optimal_embedder(self, analysis: Dict[str, Any]) -> str:
        """
        Select optimal embedder based on analysis
        """
        complexity = analysis['complexity_score']
        has_structure = analysis['has_structure']
        file_size = analysis['file_size']
        
        # For now, use contextual for most cases
        # Multi-level for complex structured documents
        if has_structure and complexity > 0.7 and file_size > 1024 * 1024:
            return 'multi_level'
        else:
            return 'contextual'
    
    def _calculate_text_complexity(self, text: str) -> float:
        """Calculate text complexity score"""
        try:
            import re
            
            if not text:
                return 0.5
            
            words = re.findall(r'\b\w+\b', text.lower())
            sentences = re.split(r'[.!?]+', text)
            
            if not words or not sentences:
                return 0.5
            
            # Metrics
            avg_word_length = sum(len(word) for word in words) / len(words)
            avg_sentence_length = len(words) / len(sentences)
            unique_word_ratio = len(set(words)) / len(words)
            
            # Normalize and combine
            complexity = (
                min(1.0, avg_word_length / 8) * 0.3 +
                min(1.0, avg_sentence_length / 20) * 0.4 +
                unique_word_ratio * 0.3
            )
            
            return max(0.1, min(0.9, complexity))
            
        except Exception:
            return 0.5
    
    def _detect_text_language(self, text: str) -> str:
        """Simple language detection"""
        if not text:
            return 'en'
        
        # Vietnamese characters
        vietnamese_chars = 'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ'
        vietnamese_count = sum(1 for char in text.lower() if char in vietnamese_chars)
        vietnamese_ratio = vietnamese_count / len(text)
        
        return 'vi' if vietnamese_ratio > 0.01 else 'en'
    
    def _detect_text_structure(self, text: str) -> bool:
        """Detect if text has clear structure"""
        import re
        
        # Look for structure indicators
        structure_indicators = [
            r'^\s*\d+\.',  # Numbered lists
            r'^\s*[•\-\*]',  # Bullet points
            r'^\s*#{1,6}\s',  # Markdown headers
            r'^\s*[A-Z][^.!?]*:',  # Section headers
            r'\|.*\|',  # Tables
            r'^\s*Chapter\s+\d+',  # Chapters
            r'^\s*Section\s+\d+'  # Sections
        ]
        
        lines = text.split('\n')
        structured_lines = 0
        
        for line in lines:
            for pattern in structure_indicators:
                if re.search(pattern, line, re.MULTILINE | re.IGNORECASE):
                    structured_lines += 1
                    break
        
        return structured_lines > len(lines) * 0.1  # 10% threshold
    
    async def _create_enhanced_text_with_context(self, text_content: str, 
                                               image_urls: List[str],
                                               images: List[Dict[str, Any]],
                                               analysis: Dict[str, Any]) -> str:
        """
        Create enhanced text content với context awareness
        """
        if not image_urls or not images:
            return text_content
        
        try:
            # Enhanced image placement based on document structure
            if analysis.get('has_structure', False):
                return self._place_images_structurally(text_content, image_urls, analysis)
            else:
                return self._place_images_semantically(text_content, image_urls, analysis)
                
        except Exception as e:
            logger.error(f"Error creating enhanced text: {str(e)}")
            # Fallback to simple placement
            return await self._create_text_with_image_tags(text_content, image_urls, images)
    
    def _place_images_structurally(self, text: str, image_urls: List[str], analysis: Dict[str, Any]) -> str:
        """Place images based on document structure"""
        import re
        
        # Find structural breaks
        sections = re.split(r'\n\s*\n', text)  # Split by double newlines
        
        if len(sections) <= 1:
            return self._place_images_evenly(text, image_urls)
        
        # Distribute images across sections
        section_per_image = max(1, len(sections) // len(image_urls))
        result_sections = []
        image_index = 0
        
        for i, section in enumerate(sections):
            result_sections.append(section)
            
            # Place image after every few sections
            if (i + 1) % section_per_image == 0 and image_index < len(image_urls):
                result_sections.append(f"<image:{image_urls[image_index]}>")
                image_index += 1
        
        # Add remaining images
        while image_index < len(image_urls):
            result_sections.append(f"<image:{image_urls[image_index]}>")
            image_index += 1
        
        return '\n\n'.join(result_sections)
    
    def _place_images_semantically(self, text: str, image_urls: List[str], analysis: Dict[str, Any]) -> str:
        """Place images based on semantic breaks"""
        # For narrative text, place at natural breaks
        sentences = text.split('. ')
        
        if len(sentences) <= len(image_urls):
            return self._place_images_evenly(text, image_urls)
        
        # Place at sentence boundaries
        sentences_per_image = len(sentences) // len(image_urls)
        result = []
        image_index = 0
        
        for i, sentence in enumerate(sentences):
            if i == len(sentences) - 1:
                result.append(sentence)  # Last sentence, no period
            else:
                result.append(sentence + '.')
            
            if (i + 1) % sentences_per_image == 0 and image_index < len(image_urls):
                result.append(f"\n\n<image:{image_urls[image_index]}>\n\n")
                image_index += 1
        
        # Add remaining images
        while image_index < len(image_urls):
            result.append(f"\n\n<image:{image_urls[image_index]}>\n\n")
            image_index += 1
        
        return ' '.join(result)
    
    def _place_images_evenly(self, text: str, image_urls: List[str]) -> str:
        """Fallback: place images evenly throughout text"""
        paragraphs = text.split('\n\n')
        
        if len(paragraphs) <= 1:
            # No clear paragraphs, append at end
            image_tags = [f"<image:{url}>" for url in image_urls]
            return text + "\n\n" + "\n".join(image_tags)
        
        # Distribute evenly
        paragraphs_per_image = max(1, len(paragraphs) // len(image_urls))
        result = []
        image_index = 0
        
        for i, paragraph in enumerate(paragraphs):
            result.append(paragraph)
            
            if (i + 1) % paragraphs_per_image == 0 and image_index < len(image_urls):
                result.append(f"<image:{image_urls[image_index]}>")
                image_index += 1
        
        # Add remaining images
        while image_index < len(image_urls):
            result.append(f"<image:{image_urls[image_index]}>")
            image_index += 1
        
        return '\n\n'.join(result)
    
    async def _create_enhanced_knowledge_chunks(self, text_content: str, document_id: str,
                                              user_id: str, company_id: str,
                                              analysis: Dict[str, Any],
                                              metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tạo knowledge chunks với Enhanced RAG - tự động chọn strategy tối ưu
        """
        start_time = datetime.now()
        
        try:
            # Force semantic chunking with fixed parameters
            chunker_strategy = "semantic"  # Always use semantic chunking
            chunk_size = 256  # Fixed chunk size
            overlap = 0  # No overlap
            
            logger.info(f"Using forced chunking strategy: {chunker_strategy} with size={chunk_size}, overlap={overlap}")
            
            chunker = self.chunker_factory.create_chunker(
                strategy=chunker_strategy,
                chunk_size=chunk_size,
                overlap=overlap,
                document_type=analysis['file_extension']
            )
            
            # Perform chunking
            chunk_results = await chunker.chunk_text(text_content, analysis)
            
            # Tạo embedder với strategy tối ưu
            embedder_strategy = analysis['recommended_embedder']
            embedder = self.embedder_factory.create_embedder(
                strategy=embedder_strategy,
                model_name='Qwen/Qwen3-Embedding-0.6B'
            )
            
            # Initialize embedder
            await embedder.initialize()
            
            logger.info(f"Using embedding strategy: {embedder_strategy}")
            
            # Create embeddings với context
            chunk_texts = [chunk.content for chunk in chunk_results]
            contexts = []
            
            for chunk in chunk_results:
                context = {
                    'document_metadata': analysis,
                    'chunk_metadata': chunk.metadata.to_dict(),
                    'preceding_context': chunk.metadata.preceding_context,
                    'following_context': chunk.metadata.following_context
                }
                contexts.append(context)
            
            # Generate embeddings
            embedding_results = await embedder.embed_batch(chunk_texts, contexts)
            
            # Prepare chunks data for bulk insert
            chunks_data = []
            total_tokens = 0
            quality_scores = []
            
            for i, (chunk, embedding_result) in enumerate(zip(chunk_results, embedding_results)):
                try:
                    # Enhanced source info
                    source_info = {
                        "type": "document",
                        "source_id": document_id,
                        "title": metadata.get("title", analysis.get("file_name", "Unknown")),
                        "file_type": analysis['file_extension'],
                        "chunking_strategy": chunker_strategy,
                        "embedding_strategy": embedder_strategy
                    }
                    
                    # Enhanced chunk metadata
                    chunk_metadata = {
                        "chunk_index": chunk.metadata.chunk_index,
                        "chunk_type": chunk.metadata.chunk_type.value,
                        "start_position": chunk.metadata.start_position,
                        "end_position": chunk.metadata.end_position,
                        "chunk_length": chunk.metadata.length,
                        "token_count": chunk.metadata.token_count,
                        "semantic_similarity": chunk.metadata.semantic_similarity,
                        "coherence_score": chunk.metadata.coherence_score,
                        "completeness_score": chunk.metadata.completeness_score,
                        "section_title": chunk.metadata.section_title,
                        "page_number": chunk.metadata.page_number,
                        "level": chunk.metadata.level,
                        "language": chunk.metadata.language or analysis.get('language', 'auto'),
                        "keywords": chunk.metadata.keywords,
                        "document_analysis": analysis,
                        "embedding_metadata": {
                            "model": embedder.model_name,
                            "strategy": embedder_strategy,
                            "confidence": embedding_result.metadata.confidence_score,
                            "processing_time": embedding_result.metadata.processing_time
                        },
                        "processed_at": datetime.now().isoformat()
                    }
                    
                    # Chuẩn bị chunk data cho bulk insert
                    chunk_doc = {
                        "content": chunk.content,
                        "content_embedding": embedding_result.embedding,
                        "source_info": source_info,
                        "metadata": chunk_metadata,
                        "user_id": user_id,
                        "company_id": company_id
                    }
                    chunks_data.append(chunk_doc)
                    
                    # Collect metrics
                    if embedding_result.metadata.token_count:
                        total_tokens += embedding_result.metadata.token_count
                    
                    if chunk.metadata.coherence_score:
                        quality_scores.append(chunk.metadata.coherence_score)
                    
                except Exception as e:
                    logger.error(f"Error preparing enhanced chunk {i}: {str(e)}")
                    continue
            
            # Bulk insert all chunks at once
            if chunks_data:
                logger.info(f"Bulk inserting {len(chunks_data)} enhanced chunks for document {document_id}")
                stored_chunks = await self.knowledge_chunk_manager.bulk_create_chunks(chunks_data)
                logger.info(f"Successfully bulk inserted {len(stored_chunks)} enhanced chunks")
            else:
                stored_chunks = []
            
            # Calculate final metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            avg_chunk_size = sum(len(chunk.content) for chunk in chunk_results) / len(chunk_results) if chunk_results else 0
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
            
            result = {
                "total_chunks": len(stored_chunks),
                "strategy_used": chunker_strategy,
                "embedding_strategy": embedder_strategy,
                "avg_chunk_size": avg_chunk_size,
                "quality_score": avg_quality,
                "processing_time": processing_time,
                "chunk_ids": [str(chunk["_id"]) for chunk in stored_chunks],
                "quality_metrics": {
                    "avg_coherence": avg_quality,
                    "total_tokens": total_tokens,
                    "chunks_created": len(stored_chunks),
                    "chunks_failed": len(chunk_results) - len(stored_chunks)
                },
                "embedding_performance": {
                    "model_used": embedder.model_name,
                    "avg_processing_time": processing_time / len(chunk_results) if chunk_results else 0,
                    "total_embeddings": len(embedding_results)
                }
            }
            
            logger.info(f"Enhanced chunking completed: {len(stored_chunks)} chunks created "
                       f"using {chunker_strategy} strategy in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced chunk creation: {str(e)}")
            raise
    
    async def _create_page_aware_knowledge_chunks(self, document_content: DocumentContent, 
                                                document_id: str, user_id: str, company_id: str,
                                                analysis: Dict[str, Any],
                                                image_urls_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Tạo page-aware knowledge chunks với bulk processing để tối ưu hiệu suất
        
        Args:
            document_content: Document content với page info
            document_id: ID document
            user_id: ID người dùng  
            company_id: ID công ty
            analysis: Document analysis
            image_urls_mapping: Mapping image_id -> URL
            
        Returns:
            Dict: Kết quả chunking
        """
        # Sử dụng bulk processing method thay vì tạo từng chunk
        return await self._bulk_process_enhanced_document(
            document_content, document_id, user_id, company_id, 
            analysis, image_urls_mapping
        )
    
    async def _generate_placeholder_image_embedding(self, image_data: bytes) -> List[float]:
        """
        Generate image embedding using SigLIP model
        SigLIP provides better performance than CLIP for image-text retrieval
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            List[float]: Image embedding vector (1152 dimensions for siglip-base)
        """
        try:
            from PIL import Image
            import io
            import torch
            from configs.environment import get_image_embedding_model
            
            # Load image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed (handle RGBA, grayscale, etc.)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get model and processor
            image_model, image_processor = get_image_embedding_model()
            
            # Process image
            inputs = image_processor(images=image, return_tensors="pt")
            
            # Generate embedding
            with torch.no_grad():
                outputs = image_model.get_image_features(**inputs)
                # Normalize embedding for better similarity search
                embedding = outputs / outputs.norm(dim=-1, keepdim=True)
                embedding_list = embedding.squeeze().cpu().numpy().tolist()
            
            logger.info(f"Generated image embedding with dimension: {len(embedding_list)}")
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating image embedding: {str(e)}")
            # Fallback to zero vector if error (same dimension as model output: 1152)
            return [0.0] * 1152

    async def _bulk_process_enhanced_document(self, document_content, document_id: str, 
                                            user_id: str, company_id: str, 
                                            analysis: Dict[str, Any], 
                                            image_urls_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Xử lý enhanced document với bulk insert để tối ưu hiệu suất
        
        Args:
            document_content: Parsed document content
            document_id: Document ID
            user_id: User ID
            company_id: Company ID  
            analysis: Document analysis data
            image_urls_mapping: Mapping image IDs to S3 URLs
            
        Returns:
            Dict: Processing results with metrics
        """
        start_time = datetime.now()
        all_chunks_data = []
        
        try:
            # Tạo embedder cho text
            text_embedder = self.embedder_factory.create_embedder(
                strategy="contextual",
                model_name='Qwen/Qwen3-Embedding-0.6B'
            )
            await text_embedder.initialize()
            
            logger.info(f"Processing {len(document_content.pages)} pages for document {document_id}")
            
            for page in document_content.pages:
                page_num = page.page_number
                
                # Replace image IDs with URLs in full content
                full_page_content = page.full_content or page.text_content
                for image in page.images:
                    image_id = image.get("image_id")
                    if image_id in image_urls_mapping:
                        image_tag = f"<image:{image_urls_mapping[image_id]}>"
                        full_page_content += f"\n{image_tag}"
                
                # Prepare source info for this page
                source_info = {
                    "type": "document",
                    "source_id": document_id,
                    "title": analysis.get("file_name", "Unknown")
                }
                is_pdf = (analysis.get("file_type") == "pdf") or (document_content.metadata.get("file_extension", "").lower() == ".pdf")
                
                # 1. Chunk theo page cho PDF: mỗi page → một chunk duy nhất
                if is_pdf:
                    try:
                        page_embedding = await DocumentUtils.generate_embedding((page.text_content or "").lower())
                        if page_embedding:
                            page_metadata = {
                                "chunk_type": "page",
                                "page_number": page_num,
                                "text_length": len(page.text_content or ""),
                                "image_count": len(page.images),
                                "document_metadata": analysis,
                                "processed_at": datetime.now().isoformat()
                            }
                            page_chunk_doc = {
                                "content": full_page_content,
                                "content_embedding_text": page.text_content or "",
                                "content_embedding": page_embedding,
                                "chunk_type": "page",
                                "source_info": source_info,
                                "metadata": page_metadata,
                                "user_id": user_id,
                                "company_id": company_id
                            }
                            all_chunks_data.append(page_chunk_doc)
                    except Exception as e:
                        logger.error(f"Error preparing page chunk for page {page_num}: {str(e)}")
                else:
                    # 1b. Với non-PDF: chia nhỏ theo semantic như trước
                    if (page.full_content or page.text_content).strip():
                        text_chunks = DocumentUtils.chunk_text(page.text_content, 
                                                             analysis.get('optimal_chunk_size', 1000), 
                                                             analysis.get('optimal_overlap', 200))
                        for chunk_data in text_chunks:
                            try:
                                embedding = await DocumentUtils.generate_embedding(str(chunk_data["content"]).lower())
                                if not embedding:
                                    continue
                                chunk_metadata = {
                                    "chunk_index": chunk_data["chunk_index"],
                                    "chunk_type": "text", 
                                    "page_number": page_num,
                                    "start_position": chunk_data["start_position"],
                                    "end_position": chunk_data["end_position"],
                                    "chunk_length": chunk_data["length"],
                                    "document_metadata": analysis,
                                    "processed_at": datetime.now().isoformat()
                                }
                                chunk_doc = {
                                    "content": full_page_content,
                                    "content_embedding_text": chunk_data["content"],
                                    "content_embedding": embedding,
                                    "chunk_type": "text",
                                    "source_info": source_info,
                                    "metadata": chunk_metadata,
                                    "user_id": user_id,
                                    "company_id": company_id
                                }
                                all_chunks_data.append(chunk_doc)
                            except Exception as e:
                                logger.error(f"Error preparing text chunk {chunk_data['chunk_index']} page {page_num}: {str(e)}")
                                continue
                
                # 2. Image chunks giữ nguyên hành vi (phụ thuộc process_images ở upstream)
                
                # 3. Tạo individual image chunks
                for image in page.images:
                    try:
                        image_id = image.get("image_id")
                        if image_id not in image_urls_mapping:
                            continue
                            
                        # Generate image embedding
                        image_embedding = await self._generate_placeholder_image_embedding(image["image_data"])
                        
                        if image_embedding:
                            image_metadata = {
                                "chunk_type": "image",
                                "page_number": page_num,
                                "image_id": image_id,
                                "image_url": image_urls_mapping[image_id],
                                "image_position": image.get("position", 0),
                                "image_metadata": image.get("metadata", {}),
                                "document_metadata": analysis,
                                "processed_at": datetime.now().isoformat()
                            }
                            
                            image_chunk_doc = {
                                "content": full_page_content,  # Full page content
                                "content_embedding_text": "",  # No text for image chunks
                                "content_embedding": image_embedding,  # Image embedding for similarity
                                "chunk_type": "image",
                                "source_info": source_info,
                                "metadata": image_metadata,
                                "user_id": user_id,
                                "company_id": company_id
                            }
                            all_chunks_data.append(image_chunk_doc)
                            
                    except Exception as e:
                        logger.error(f"Error preparing image chunk {image.get('image_id')} page {page_num}: {str(e)}")
                        continue
            
            # Bulk insert all chunks at once
            if all_chunks_data:
                logger.info(f"Bulk inserting {len(all_chunks_data)} chunks for document {document_id}")
                all_chunks = await self.knowledge_chunk_manager.bulk_create_chunks(all_chunks_data)
                logger.info(f"Successfully bulk inserted {len(all_chunks)} chunks")
            else:
                all_chunks = []
            
            # Calculate metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            text_chunks = [c for c in all_chunks if c.get("metadata", {}).get("chunk_type") == "text"]
            page_chunks = [c for c in all_chunks if c.get("metadata", {}).get("chunk_type") == "page"] 
            image_chunks = [c for c in all_chunks if c.get("metadata", {}).get("chunk_type") == "image"]
            
            result = {
                "total_chunks": len(all_chunks),
                "text_chunks": len(text_chunks),
                "page_chunks": len(page_chunks), 
                "image_chunks": len(image_chunks),
                "strategy_used": "page_aware_chunking_bulk",
                "embedding_strategy": "mixed",
                "processing_time": processing_time,
                "quality_score": 0.85,  # Default good score
                "chunk_ids": [str(chunk["_id"]) for chunk in all_chunks],
                "avg_chunk_size": sum(len(c.get("content", "")) for c in all_chunks) / len(all_chunks) if all_chunks else 0
            }
            
            logger.info(f"Bulk page-aware chunking completed: {len(all_chunks)} total chunks "
                       f"({len(text_chunks)} text, {len(page_chunks)} page, {len(image_chunks)} image) "
                       f"in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in bulk enhanced document processing: {str(e)}")
            raise
    
    async def _cleanup_failed_processing(self, document_id: str, image_urls_mapping: Dict[str, str]):
        """
        Cleanup khi xử lý thất bại
        
        Args:
            document_id: ID document
            image_urls_mapping: Mapping ảnh cần xóa
        """
        try:
            # Xóa document record
            await self.document_manager.delete_by_id(document_id)
            
            # Xóa chunks
            await self.knowledge_chunk_manager.delete_by_source_id(document_id)
            
            # Xóa ảnh từ S3
            for url in image_urls_mapping.values():
                await self.s3_service.delete_file(url)
                
            logger.info(f"Cleaned up failed processing for document {document_id}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    def _can_process_file(self, file_extension: str) -> bool:
        """
        Kiểm tra có thể xử lý file này không
        
        Args:
            file_extension: Extension file
            
        Returns:
            bool: True nếu có thể xử lý
        """
        return file_extension.lower() in self.processors
    
    async def get_supported_formats(self) -> List[str]:
        """
        Lấy danh sách format được hỗ trợ
        
        Returns:
            List[str]: Danh sách extensions
        """
        return list(self.processors.keys())
    
    async def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin document và chunks
        
        Args:
            document_id: ID document
            
        Returns:
            Dict: Thông tin document
        """
        try:
            # Lấy document record
            document = await self.document_manager.get_by_id(document_id)
            if not document:
                return None
            
            # Lấy chunks
            chunks = await self.knowledge_chunk_manager.get_by_source_id(document_id)
            
            return {
                "document": document,
                "chunks": chunks,
                "chunk_count": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"Error getting document info: {str(e)}")
            return None
