"""
Knowledge Management API Endpoints
Cung cấp API cho documents, knowledge_chunks, histories, feedback
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from configs.environment import get_vietnam_now_naive, get_embedding
import logging
import os
import json
import uuid
import re
import time
import asyncio

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.data.limit_service import get_limit_service
from controllers.auth.auth_middleware import get_current_user

from controllers.rag.load_documents.services.document_loader_service import DocumentLoaderService
from .rag_api_service import RAGAPIService
from configs.constant import MAX_FILE_SIZE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Knowledge Management"])

# Pydantic Models
class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

# Q&A Pair Models
class QAPairCreate(BaseModel):
    question: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    company_id: Optional[str] = None

class QAPairUpdate(BaseModel):
    question: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None

# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()

# Dependency to get Enhanced RAG service
def get_enhanced_rag_service():
    factory = get_mongodb_factory()
    return RAGAPIService(factory.db_manager)


@router.post("/documents/upload", response_model=Dict[str, Any])
async def upload_document(
    file: UploadFile = File(...),
    name: str = Form(""),
    company_id: Optional[str] = Form(""),
    process_images: bool = Form(False),
    parser_engine: str = Form("ragflow"),
    rag_service: RAGAPIService = Depends(get_enhanced_rag_service),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Upload và xử lý document cho Enhanced RAG system với RAGFlow parser
    
    - **file**: File PDF, DOC, DOCX, XLS, XLSX, TXT
    - **name**: Tên tài liệu
    - **company_id**: ID công ty (optional)
    - **process_images**: Xử lý ảnh trong tài liệu (mặc định: False)
    - **parser_engine**: Engine parsing (ragflow=mặc định, legacy=cũ)
    """
    try:
        import time
        start_time = time.time()
        
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi upload document
        limit_service = get_limit_service(factory)
        limit_check = await limit_service.check_limit_before_create(user_id, "knowledge")
        
        if not limit_check.get("can_create", False):
            raise HTTPException(
                status_code=403, 
                detail=limit_check.get("message", "Cannot upload more documents due to package limits")
            )
        
        # Xử lý company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        else:
            # Lấy company mặc định của user
            default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
            if default_company:
                company_id = str(default_company["_id"])
        
        # Read file data trước để có file size
        file_data = await file.read()
        file_size = len(file_data)
        
        # Validate file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File size exceeds maximum limit of {MAX_FILE_SIZE / (1024*1024):.1f}MB"
            )
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Get supported strategies for validation
        supported = rag_service.get_supported_strategies()
        
        # Force semantic chunking with specific parameters
        chunk_strategy = "semantic"  # semantic, recursive, hierarchical, adaptive
        embedding_strategy = "contextual"  # contextual, multi_level
        chunk_size = 256  # Fixed chunk size for all documents
        overlap = 0  # No overlap between chunks

        # Validate chunking strategy
        if chunk_strategy not in supported["chunking_strategies"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported chunk strategy. Supported: {list(supported['chunking_strategies'].keys())}"
            )
        
        # Validate embedding strategy
        if embedding_strategy not in supported["embedding_strategies"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported embedding strategy. Supported: {list(supported['embedding_strategies'].keys())}"
            )
        
        # Validate file type
        all_supported = supported["supported_file_types"]["advanced"] + supported["supported_file_types"]["simple"]
        file_extension = None
        if file.filename:
            file_extension = os.path.splitext(file.filename)[1].lower()
            
        if not file_extension or file_extension not in all_supported:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported: {', '.join(all_supported)}"
            )
        
        # Parse tags
        tag_list = []
        
        # Validate parser_engine
        if parser_engine not in ["ragflow", "legacy"]:
            logger.warning(f"Invalid parser_engine '{parser_engine}', using default 'ragflow'")
            parser_engine = "ragflow"
        
        # Process document using Enhanced RAG Service with RAGFlow
        result = await rag_service.process_document_upload(
            file_data=file_data,
            file_name=file.filename,
            user_id=user_id,
            company_id=company_id,
            chunk_strategy=chunk_strategy,
            embedding_strategy=embedding_strategy,
            chunk_size=chunk_size,
            overlap=overlap,
            tags=tag_list,
            document_name=name,
            process_images=process_images,
            parser_engine=parser_engine
        )
        
        try:
            # Tính processing time
            processing_time = time.time() - start_time
            
            # Lấy thống kê chunks và images sau khi process
            document_id = result.get("document_id")
            total_chunks = 0
            total_images = 0
            
            if document_id:
                # Get chunks để đếm
                chunks = await factory.knowledge_chunk_manager.get_by_source_id(document_id)
                total_chunks = len(chunks)
                
                # Extract và đếm images từ chunks  
                import re
                all_images = []
                for chunk in chunks:
                    image_urls = re.findall(r'<image:([^>]+)>', chunk.get('content', ''))
                    all_images.extend(image_urls)
                total_images = len(set(all_images))  # Unique images
                
                # Cập nhật document với metadata bổ sung
                metadata_update = {
                    "file_size": file_size,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "total_chunks": total_chunks,
                    "total_images": total_images,
                    "processing_time": round(processing_time, 2),
                    "processing_time_formatted": f"{processing_time:.2f}s",
                    "technical_info": {
                        "chunk_strategy": chunk_strategy,
                        "embedding_strategy": embedding_strategy,
                        "chunk_size": chunk_size,
                        "overlap": overlap
                    }
                }
                
                # Update document với metadata
                await factory.document_manager.update_by_id(document_id, {
                    "metadata": metadata_update,
                    "update_at": get_vietnam_now_naive()
                })
                
                # Thêm metadata vào result trả về
                result["metadata"] = metadata_update
        except Exception as meta_error:
            logger.warning(f"Failed to update document metadata: {str(meta_error)}")
            # Không raise error vì document đã được xử lý thành công
        
        return {
            "success": True,
            "message": "Document processed successfully with Enhanced RAG",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents", response_model=Dict[str, Any])
async def get_documents(
    company_id: Optional[str] = Query(None, description="Filter by company ID (Rỗng sẽ lấy trong tất cả công ty của user)"),
    status: Optional[str] = Query(None, description="Document status filter (uploaded, processing, processed, failed)"),
    file_type: Optional[str] = Query(None, description="File type filter (.pdf, .docx, .txt, etc.)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Lấy documents của user với thông tin processing"""
    try:
        user_id = current_user.get("user_id")
        
        # Xử lý company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        # Nếu company_id rỗng thì lấy documents từ tất cả công ty của user (company_id=None)
        
        documents = await factory.document_manager.get_by_user_id(
            user_id=user_id, 
            company_id=company_id,
            status=status
        )
        
        # Filter by file_type if provided
        if file_type:
            documents = [doc for doc in documents if doc.get("file_type", "").lower() == file_type.lower()]
        
        # Simple pagination
        total = len(documents)
        paginated_documents = documents[skip:skip+limit]
        
        # Enhance với thông tin chunks và images
        enhanced_documents = []
        for doc in paginated_documents:
            doc_id = str(doc["_id"])
            
            # Get chunk count
            chunks = await factory.knowledge_chunk_manager.get_by_source_id(doc_id)
            
            # Extract images
            all_images = []
            for chunk in chunks:
                import re
                image_urls = re.findall(r'<image:([^>]+)>', chunk.get('content', ''))
                all_images.extend(image_urls)
            
            unique_images = list(set(all_images))
            
            enhanced_doc = {
                "document_id": doc_id,
                "document_name": doc.get("document_name", ""),
                "file_name": doc.get("file_name", ""),
                "file_type": doc.get("file_type", ""),
                "title": doc.get("title", ""),
                "status": doc.get("status", ""),
                "storage_type": doc.get("storage_type", ""),
                "storage_url": doc.get("storage_url", ""),
                "chunk_count": len(chunks),
                "image_count": len(unique_images),
                "has_images": len(unique_images) > 0,
                "processing_type": "advanced" if len(unique_images) > 0 or len(chunks) > 1 else "simple",
                "created_at": doc.get("create_at", ""),
                "updated_at": doc.get("update_at", "")
            }
            
            enhanced_documents.append(enhanced_doc)
        
        return {
            "success": True,
            "data": enhanced_documents,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            },
            "summary": {
                "total_documents": total,
                "advanced_processed": len([d for d in enhanced_documents if d["processing_type"] == "advanced"]),
                "simple_processed": len([d for d in enhanced_documents if d["processing_type"] == "simple"])
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/options", response_model=Dict[str, Any])
async def get_document_options(
    rag_service: RAGAPIService = Depends(get_enhanced_rag_service),
):
    """
    Trả về các chiến lược hỗ trợ và loại tệp được hỗ trợ hiện tại.
    Dùng để UI hiển thị lựa chọn hợp lệ và kiểm tra trước khi upload.
    """
    try:
        supported = rag_service.get_supported_strategies()
        return {"success": True, "data": supported}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", response_model=Dict[str, Any])
async def delete_document(
    document_id: str, 
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Xóa document và tất cả chunks liên quan, bao gồm cleanup S3"""
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra document tồn tại và thuộc về user
        document = await factory.document_manager.get_by_id(document_id)
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        # Get chunks để lấy danh sách images cần xóa
        chunks = await factory.knowledge_chunk_manager.get_by_source_id(document_id)
        
        # Extract image URLs from chunks
        image_urls = []
        for chunk in chunks:
            import re
            urls = re.findall(r'<image:([^>]+)>', chunk.get('content', ''))
            image_urls.extend(urls)
        
        # Xóa chunks
        deleted_chunks = await factory.knowledge_chunk_manager.delete_by_source_id(document_id)
        
        # Xóa document
        await factory.document_manager.delete_by_id(document_id)
        
        # Cleanup S3 files nếu có
        cleanup_results = {"images_deleted": 0, "document_deleted": False}
        
        try:
            import asyncio
            document_service = DocumentLoaderService(factory.db_manager)
            
            # Tạo danh sách các tasks để xóa song song
            delete_tasks = []
            
            # Xóa document gốc từ S3
            storage_url = document.get("storage_url")
            if storage_url and "s3.amazonaws.com" in storage_url:
                delete_tasks.append(document_service.s3_service.delete_file(storage_url))
            
            # Xóa images từ S3 - thêm vào list tasks
            s3_image_urls = [img_url for img_url in image_urls if "s3.amazonaws.com" in img_url]
            for img_url in s3_image_urls:
                delete_tasks.append(document_service.s3_service.delete_file(img_url))
            
            # Chạy tất cả các tasks xóa song song
            if delete_tasks:
                delete_results = await asyncio.gather(*delete_tasks, return_exceptions=True)
                
                # Xử lý kết quả xóa document gốc
                if storage_url and "s3.amazonaws.com" in storage_url:
                    cleanup_results["document_deleted"] = delete_results[0] if not isinstance(delete_results[0], Exception) else False
                    # Kết quả xóa images bắt đầu từ index 1
                    image_results = delete_results[1:] if len(delete_results) > 1 else []
                else:
                    # Không có document gốc, tất cả kết quả là images
                    image_results = delete_results
                
                # Đếm số images đã xóa thành công
                cleanup_results["images_deleted"] = sum(1 for result in image_results if result is True)
                        
        except Exception as cleanup_error:
            logger.warning(f"S3 cleanup failed: {str(cleanup_error)}")
            # Không raise error vì document đã xóa khỏi DB thành công
        
        return {
            "success": True,
            "message": "Document deleted successfully",
            "data": {
                "document_id": document_id,
                "deleted_chunks": deleted_chunks,
                "cleanup_results": cleanup_results,
                "total_images_found": len(image_urls)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ================== Q&A PAIRS ENDPOINTS ==================

@router.post("/knowledge/qa-pairs", response_model=Dict[str, Any])
async def create_qa_pair(
    qa_data: QAPairCreate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo cặp Question-Answer mới
    
    - **question**: Câu hỏi
    - **content**: Nội dung trả lời
    - **category**: Danh mục (optional) - gọi api GET /api/v1/knowledge/qa-pairs/options để lấy dữ liệu
    - **tags**: Tags (optional) - gọi api GET /api/v1/knowledge/qa-pairs/options để lấy dữ liệu
    - **company_id**: ID công ty (optional)
    """
    try:
        user_id = current_user.get("user_id")
        
        # Kiểm tra limit trước khi tạo Q&A
        # limit_service = get_limit_service(factory)
        # limit_check = await limit_service.check_limit_before_create(user_id, "knowledge")
        
        # if not limit_check.get("can_create", False):
        #     raise HTTPException(
        #         status_code=403, 
        #         detail=limit_check.get("message", "Cannot create more Q&A pairs due to package limits")
        #     )
        
        # Xử lý company_id
        company_id = qa_data.company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        else:
            # Lấy company mặc định của user
            default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
            if default_company:
                company_id = str(default_company["_id"])
        
        # Sanitize và validate input - giữ nguyên các ký tự đặc biệt nhưng loại bỏ whitespace thừa
        def sanitize_text(text):
            """
            Sanitize text để đảm bảo an toàn khi lưu vào database
            Chỉ loại bỏ leading/trailing whitespace, giữ nguyên các ký tự đặc biệt
            """
            if not text:
                return ""
            # Chỉ strip whitespace, giữ nguyên tất cả ký tự đặc biệt
            sanitized = text.strip()
            # Loại bỏ null bytes nếu có (có thể gây lỗi database)
            sanitized = sanitized.replace('\x00', '')
            return sanitized
        
        # Sanitize question và content
        clean_question = sanitize_text(qa_data.question)
        clean_content = sanitize_text(qa_data.content)
        
        # Validate input sau khi sanitize
        if not clean_question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        if not clean_content:
            raise HTTPException(status_code=400, detail="Content cannot be empty")
        
        # Validate độ dài để tránh quá tải
        if len(clean_question) > 1000:
            raise HTTPException(status_code=400, detail="Question is too long (max 1000 characters)")
        if len(clean_content) > 10000:
            raise HTTPException(status_code=400, detail="Content is too long (max 10000 characters)")
        
        # Tạo embedding cho question (không phải content) - vì khi user hỏi, ta tìm question tương tự
        embedding_service = get_embedding()
        question_embedding = await embedding_service.aembed_query(clean_question)
        
        # Tạo unique ID cho QA pair
        import uuid
        qa_id = str(uuid.uuid4())
        
        # Chuẩn bị source_info cho qa_pair - sử dụng clean_question
        source_info = {
            "type": "qa_pair",
            "source_id": qa_id,
            "title": clean_question
        }
        
        # Chuẩn bị metadata - lưu answer vào metadata, không phải question
        metadata = {
            "type": "qa_pair",
            "category": qa_data.category or "general",
            "tags": qa_data.tags or [],
            "answer": clean_content,  # Lưu answer vào metadata
            "created_via": "api"
        }
        
        # Tạo knowledge chunk với logic đúng:
        # - content: question (để hiển thị và search)
        # - content_embedding_text: question (để embed)
        # - metadata.answer: answer/content (câu trả lời)
        chunk = await factory.knowledge_chunk_manager.create_knowledge_chunk_with_type(
            content=clean_question,  # Lưu question vào content
            content_embedding_text=clean_question,  # Embed question
            content_embedding=question_embedding,  # Vector của question
            chunk_type="qa_pair",
            source_info=source_info,
            user_id=user_id,
            company_id=company_id,
            metadata=metadata
        )
        
        # Backup vào file JSON
        try:
            backup_dir = "resources/backup"
            os.makedirs(backup_dir, exist_ok=True)
            backup_file = os.path.join(backup_dir, "kat_qa.json")
            
            # Chuẩn bị data để backup
            qa_backup = {
                "qa_id": qa_id,
                "chunk_id": str(chunk["_id"]),
                "question": clean_question,
                "answer": clean_content,  # Đổi từ content -> answer
                "category": metadata["category"],
                "tags": metadata["tags"],
                "company_id": company_id,
                "user_id": user_id,
                "created_at": chunk.get("create_at").isoformat() if chunk.get("create_at") else datetime.now().isoformat()
            }
            
            # Đọc file hiện tại hoặc tạo mới
            backup_data = []
            if os.path.exists(backup_file):
                try:
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:  # Chỉ parse nếu file có nội dung
                            backup_data = json.loads(content)
                            if not isinstance(backup_data, list):
                                backup_data = []
                except json.JSONDecodeError:
                    # File JSON bị lỗi, tạo mới
                    logger.warning(f"Invalid JSON in {backup_file}, creating new file")
                    backup_data = []
            
            # Thêm Q&A mới vào đầu list
            backup_data.insert(0, qa_backup)
            
            # Ghi lại file
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Q&A pair backed up successfully: {qa_id}")
        except Exception as backup_error:
            logger.warning(f"Failed to backup Q&A pair: {str(backup_error)}")
            # Không raise error vì Q&A đã được tạo thành công
        
        return {
            "success": True,
            "message": "Q&A pair created successfully",
            "data": {
                "qa_id": qa_id,
                "chunk_id": str(chunk["_id"]),
                "question": clean_question,
                "answer": clean_content,  # Đổi từ content -> answer
                "category": metadata["category"],
                "tags": metadata["tags"],
                "company_id": company_id,
                "created_at": chunk.get("create_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Q&A pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/knowledge/qa-pairs/batch", response_model=Dict[str, Any])
async def create_qa_pairs_batch(
    qa_list: List[QAPairCreate],
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Tạo nhiều Q&A pairs cùng lúc (batch import)
    
    - **qa_list**: Danh sách các Q&A pairs cần tạo
    
    Mỗi item trong danh sách phải có:
    - **question**: Câu hỏi
    - **content**: Nội dung trả lời
    - **category**: Danh mục (optional)
    - **tags**: Tags (optional)
    - **company_id**: ID công ty (optional, nếu không có sẽ dùng company mặc định)
    """
    try:
        user_id = current_user.get("user_id")
        
        if not qa_list or len(qa_list) == 0:
            raise HTTPException(status_code=400, detail="QA list cannot be empty")
        
        # if len(qa_list) > 100:
        #     raise HTTPException(status_code=400, detail="Cannot import more than 100 Q&A pairs at once")
        
        # Get default company if needed
        default_company = await factory.company_manager.get_default_company_by_user_id(user_id)
        default_company_id = str(default_company["_id"]) if default_company else None
        
        embedding_service = get_embedding()
        
        def sanitize_text(text):
            """Sanitize text để đảm bảo an toàn khi lưu vào database"""
            if not text:
                return ""
            sanitized = text.strip()
            sanitized = sanitized.replace('\x00', '')
            return sanitized
        
        success_count = 0
        failed_count = 0
        results = []
        
        for idx, qa_data in enumerate(qa_list):
            try:
                # Xử lý company_id cho từng item
                company_id = qa_data.company_id or default_company_id
                
                if qa_data.company_id:
                    # Kiểm tra company có tồn tại và thuộc về user không
                    company = await factory.company_manager.get_by_id(qa_data.company_id)
                    if not company or company.get("user_id") != user_id:
                        failed_count += 1
                        results.append({
                            "index": idx,
                            "status": "failed",
                            "error": "Company not found or access denied"
                        })
                        continue
                
                # Sanitize và validate
                clean_question = sanitize_text(qa_data.question)
                clean_content = sanitize_text(qa_data.content)
                
                if not clean_question or not clean_content:
                    failed_count += 1
                    results.append({
                        "index": idx,
                        "status": "failed",
                        "error": "Question or answer cannot be empty"
                    })
                    continue
                
                if len(clean_question) > 1000 or len(clean_content) > 10000:
                    failed_count += 1
                    results.append({
                        "index": idx,
                        "status": "failed",
                        "error": "Question or answer is too long"
                    })
                    continue
                
                # Tạo embedding
                question_embedding = await embedding_service.aembed_query(clean_question)
                
                # Tạo unique ID
                qa_id = str(uuid.uuid4())
                
                # Chuẩn bị source_info và metadata
                source_info = {
                    "type": "qa_pair",
                    "source_id": qa_id,
                    "title": clean_question
                }
                
                metadata = {
                    "type": "qa_pair",
                    "category": qa_data.category or "general",
                    "tags": qa_data.tags or [],
                    "answer": clean_content,
                    "created_via": "batch_import"
                }
                
                # Tạo knowledge chunk
                chunk = await factory.knowledge_chunk_manager.create_knowledge_chunk_with_type(
                    content=clean_question,
                    content_embedding_text=clean_question,
                    content_embedding=question_embedding,
                    chunk_type="qa_pair",
                    source_info=source_info,
                    user_id=user_id,
                    company_id=company_id,
                    metadata=metadata
                )
                
                success_count += 1
                results.append({
                    "index": idx,
                    "status": "success",
                    "qa_id": qa_id,
                    "chunk_id": str(chunk["_id"])
                })
                
            except Exception as item_error:
                failed_count += 1
                results.append({
                    "index": idx,
                    "status": "failed",
                    "error": str(item_error)
                })
                logger.error(f"Error creating Q&A pair at index {idx}: {str(item_error)}")
        
        return {
            "success": True,
            "message": f"Batch import completed: {success_count} succeeded, {failed_count} failed",
            "data": {
                "total": len(qa_list),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch Q&A pair creation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/knowledge/qa-pairs", response_model=Dict[str, Any])
async def get_qa_pairs(
    company_id: Optional[str] = Query(None, description="Filter by company ID (Rỗng sẽ lấy trong tất cả công ty của user)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search in questions and content"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory), 
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách Q&A pairs của user
    """
    try:
        user_id = current_user.get("user_id")
        
        # Xử lý company_id
        if company_id:
            # Kiểm tra company có tồn tại và thuộc về user không
            company = await factory.company_manager.get_by_id(company_id)
            if not company:
                raise HTTPException(status_code=404, detail="Company not found")
            if company.get("user_id") != user_id:
                raise HTTPException(status_code=403, detail="Company access denied")
        
        # Get Q&A chunks
        qa_chunks = await factory.knowledge_chunk_manager.get_by_user_id(
            user_id=user_id,
            company_id=company_id,
            source_type="qa_pair"
        )
        
        # Filter by category
        if category:
            qa_chunks = [chunk for chunk in qa_chunks 
                        if chunk.get("metadata", {}).get("category") == category]
        
        # Filter by tag
        if tag:
            qa_chunks = [chunk for chunk in qa_chunks 
                        if tag in chunk.get("metadata", {}).get("tags", [])]
        
        # Search filter - tìm trong cả question (content) và answer (metadata.answer)
        if search:
            search_lower = search.lower()
            qa_chunks = [chunk for chunk in qa_chunks 
                        if search_lower in chunk.get("content", "").lower() or  # Search trong question
                           search_lower in chunk.get("metadata", {}).get("answer", "").lower()]  # Search trong answer
        
        # Sort by created date (newest first)
        qa_chunks.sort(key=lambda x: x.get("create_at", datetime.min), reverse=True)
        
        # Pagination
        total = len(qa_chunks)
        paginated_chunks = qa_chunks[skip:skip+limit]
        
        # Format response
        qa_pairs = []
        for chunk in paginated_chunks:
            qa_pair = {
                "qa_id": chunk.get("source_info", {}).get("source_id"),
                "chunk_id": str(chunk["_id"]),
                "question": chunk.get("content", ""),  # Question lưu trong content
                "answer": chunk.get("metadata", {}).get("answer", ""),  # Answer lưu trong metadata
                "category": chunk.get("metadata", {}).get("category", "general"),
                "tags": chunk.get("metadata", {}).get("tags", []),
                "company_id": chunk.get("company_id"),
                "created_at": chunk.get("create_at"),
                "updated_at": chunk.get("update_at")
            }
            qa_pairs.append(qa_pair)
        
        # Get categories and tags statistics
        all_categories = set()
        all_tags = set()
        for chunk in qa_chunks:
            metadata = chunk.get("metadata", {})
            if metadata.get("category"):
                all_categories.add(metadata["category"])
            if metadata.get("tags"):
                all_tags.update(metadata["tags"])
        
        return {
            "success": True,
            "data": qa_pairs,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            },
            "summary": {
                "total_qa_pairs": total,
                "categories": sorted(list(all_categories)),
                "tags": sorted(list(all_tags))
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Q&A pairs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/knowledge/qa-pairs/{qa_id}", response_model=Dict[str, Any])
async def update_qa_pair(
    qa_id: str,
    qa_data: QAPairUpdate,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Cập nhật Q&A pair
    """
    try:
        user_id = current_user.get("user_id")
        
        # Tìm chunk theo qa_id
        chunks = await factory.knowledge_chunk_manager.get_by_user_id(
            user_id=user_id,
            source_type="qa_pair"
        )
        
        target_chunk = None
        for chunk in chunks:
            if chunk.get("source_info", {}).get("source_id") == qa_id:
                target_chunk = chunk
                break
        
        if not target_chunk:
            raise HTTPException(status_code=404, detail="Q&A pair not found")
        
        # Helper function để sanitize text (tái sử dụng logic từ create)
        def sanitize_text(text):
            """
            Sanitize text để đảm bảo an toàn khi lưu vào database
            Chỉ loại bỏ leading/trailing whitespace, giữ nguyên các ký tự đặc biệt
            """
            if not text:
                return ""
            # Chỉ strip whitespace, giữ nguyên tất cả ký tự đặc biệt
            sanitized = text.strip()
            # Loại bỏ null bytes nếu có (có thể gây lỗi database)
            sanitized = sanitized.replace('\x00', '')
            return sanitized
        
        # Chuẩn bị data để update
        update_data = {"update_at": get_vietnam_now_naive()}
        
        # Update question nếu có
        if qa_data.question is not None:
            clean_question = sanitize_text(qa_data.question)
            if not clean_question:
                raise HTTPException(status_code=400, detail="Question cannot be empty")
            if len(clean_question) > 1000:
                raise HTTPException(status_code=400, detail="Question is too long (max 1000 characters)")
            
            # Tạo embedding mới cho question
            embedding_service = get_embedding()
            question_embedding = await embedding_service.aembed_query(clean_question)
            
            # Update question vào content và source_info
            update_data["content"] = clean_question
            update_data["content_embedding_text"] = clean_question
            update_data["content_embedding"] = question_embedding
            update_data["source_info.title"] = clean_question
        
        # Update content (answer) nếu có
        if qa_data.content is not None:
            clean_content = sanitize_text(qa_data.content)
            if not clean_content:
                raise HTTPException(status_code=400, detail="Content cannot be empty")
            if len(clean_content) > 10000:
                raise HTTPException(status_code=400, detail="Content is too long (max 10000 characters)")
            
            # Lưu answer vào metadata
            update_data["metadata.answer"] = clean_content
        
        # Update category nếu có
        if qa_data.category is not None:
            update_data["metadata.category"] = qa_data.category
        
        # Update tags nếu có
        if qa_data.tags is not None:
            update_data["metadata.tags"] = qa_data.tags
        
        # Thực hiện update
        await factory.knowledge_chunk_manager.update_by_id(
            str(target_chunk["_id"]), 
            update_data
        )
        
        # Get updated chunk để trả về
        updated_chunk = await factory.knowledge_chunk_manager.get_by_id(str(target_chunk["_id"]))
        
        return {
            "success": True,
            "message": "Q&A pair updated successfully",
            "data": {
                "qa_id": qa_id,
                "chunk_id": str(updated_chunk["_id"]),
                "question": updated_chunk.get("content", ""),  # Question từ content
                "answer": updated_chunk.get("metadata", {}).get("answer", ""),  # Answer từ metadata
                "category": updated_chunk.get("metadata", {}).get("category", "general"),
                "tags": updated_chunk.get("metadata", {}).get("tags", []),
                "updated_at": updated_chunk.get("update_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating Q&A pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge/qa-pairs/{qa_id}", response_model=Dict[str, Any])
async def delete_qa_pair(
    qa_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Xóa Q&A pair
    """
    try:
        user_id = current_user.get("user_id")
        
        # Tìm chunk theo qa_id
        chunks = await factory.knowledge_chunk_manager.get_by_user_id(
            user_id=user_id,
            source_type="qa_pair"
        )
        
        target_chunk = None
        for chunk in chunks:
            if chunk.get("source_info", {}).get("source_id") == qa_id:
                target_chunk = chunk
                break
        
        if not target_chunk:
            raise HTTPException(status_code=404, detail="Q&A pair not found")
        
        # Xóa chunk
        await factory.knowledge_chunk_manager.delete_by_id(str(target_chunk["_id"]))
        
        return {
            "success": True,
            "message": "Q&A pair deleted successfully",
            "data": {
                "qa_id": qa_id,
                "deleted_chunk_id": str(target_chunk["_id"])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting Q&A pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/qa-pairs/{qa_id}", response_model=Dict[str, Any])
async def get_qa_pair(
    qa_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    Lấy thông tin chi tiết một Q&A pair
    """
    try:
        user_id = current_user.get("user_id")
        
        # Tìm chunk theo qa_id
        chunks = await factory.knowledge_chunk_manager.get_by_user_id(
            user_id=user_id,
            source_type="qa_pair"
        )
        
        target_chunk = None
        for chunk in chunks:
            if chunk.get("source_info", {}).get("source_id") == qa_id:
                target_chunk = chunk
                break
        
        if not target_chunk:
            raise HTTPException(status_code=404, detail="Q&A pair not found")
        
        return {
            "success": True,
            "data": {
                "qa_id": qa_id,
                "chunk_id": str(target_chunk["_id"]),
                "question": target_chunk.get("content", ""),  # Question từ content
                "answer": target_chunk.get("metadata", {}).get("answer", ""),  # Answer từ metadata
                "category": target_chunk.get("metadata", {}).get("category", "general"),
                "tags": target_chunk.get("metadata", {}).get("tags", []),
                "company_id": target_chunk.get("company_id"),
                "created_at": target_chunk.get("create_at"),
                "updated_at": target_chunk.get("update_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Q&A pair: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/qa-pairs/options", response_model=Dict[str, Any])
async def get_qa_pair_options():
    """
    Lấy danh sách categories và tags được đề xuất cho Q&A pairs
    """
    try:
        # Predefined categories dựa trên các ngành nghề trong hệ thống
        categories = [
            {
                "value": "general",
                "label": "Tổng quát",
                "description": "Câu hỏi chung không thuộc ngành cụ thể",
                "is_default": True
            },
            {
                "value": "real_estate",
                "label": "Bất động sản",
                "description": "Tư vấn mua bán, cho thuê nhà đất",
                "is_default": False
            },
            {
                "value": "fashion_retail",
                "label": "Thời trang & Bán lẻ",
                "description": "Tư vấn về quần áo, phụ kiện, size",
                "is_default": False
            },
            {
                "value": "beauty_skincare",
                "label": "Làm đẹp & Chăm sóc da",
                "description": "Tư vấn mỹ phẩm, skincare, làm đẹp",
                "is_default": False
            },
            {
                "value": "education",
                "label": "Giáo dục",
                "description": "Tư vấn học tập, khóa học, kỹ năng",
                "is_default": False
            },
            {
                "value": "technology",
                "label": "Công nghệ & IT",
                "description": "Hỗ trợ kỹ thuật, sản phẩm công nghệ",
                "is_default": False
            },
            {
                "value": "healthcare",
                "label": "Y tế & Sức khỏe",
                "description": "Tư vấn sức khỏe, dịch vụ y tế",
                "is_default": False
            },
            {
                "value": "finance",
                "label": "Tài chính & Ngân hàng",
                "description": "Tư vấn tài chính, đầu tư, vay vốn",
                "is_default": False
            },
            {
                "value": "food_beverage",
                "label": "Ẩm thực & Đồ uống",
                "description": "Thực đơn, đặt bàn, giao hàng",
                "is_default": False
            },
            {
                "value": "travel_tourism",
                "label": "Du lịch",
                "description": "Tư vấn tour, khách sạn, vé máy bay",
                "is_default": False
            },
            {
                "value": "automotive",
                "label": "Ô tô",
                "description": "Tư vấn mua bán xe, bảo dưỡng",
                "is_default": False
            },
            {
                "value": "business_consulting",
                "label": "Tư vấn kinh doanh",
                "description": "Tư vấn chiến lược, quản lý doanh nghiệp",
                "is_default": False
            }
        ]
        
        # Predefined tags được nhóm theo loại
        tags = {
            "common": {
                "label": "Thẻ chung",
                "tags": [
                    {"value": "faq", "label": "Câu hỏi thường gặp"},
                    {"value": "product_info", "label": "Thông tin sản phẩm"},
                    {"value": "pricing", "label": "Giá cả"},
                    {"value": "support", "label": "Hỗ trợ"},
                    {"value": "troubleshooting", "label": "Khắc phục sự cố"},
                    {"value": "how_to", "label": "Hướng dẫn"},
                    {"value": "policy", "label": "Chính sách"},
                    {"value": "contact", "label": "Liên hệ"},
                    {"value": "warranty", "label": "Bảo hành"},
                    {"value": "shipping", "label": "Vận chuyển"}
                ]
            },
            "business": {
                "label": "Kinh doanh",
                "tags": [
                    {"value": "consultation", "label": "Tư vấn"},
                    {"value": "quotation", "label": "Báo giá"},
                    {"value": "booking", "label": "Đặt lịch"},
                    {"value": "appointment", "label": "Hẹn gặp"},
                    {"value": "service_info", "label": "Thông tin dịch vụ"},
                    {"value": "promotion", "label": "Khuyến mãi"},
                    {"value": "membership", "label": "Thành viên"},
                    {"value": "payment", "label": "Thanh toán"}
                ]
            },
            "technical": {
                "label": "Kỹ thuật",
                "tags": [
                    {"value": "installation", "label": "Cài đặt"},
                    {"value": "configuration", "label": "Cấu hình"},
                    {"value": "specifications", "label": "Thông số kỹ thuật"},
                    {"value": "compatibility", "label": "Tương thích"},
                    {"value": "updates", "label": "Cập nhật"},
                    {"value": "security", "label": "Bảo mật"},
                    {"value": "performance", "label": "Hiệu suất"}
                ]
            },
            "customer_service": {
                "label": "Chăm sóc khách hàng",
                "tags": [
                    {"value": "complaint", "label": "Khiếu nại"},
                    {"value": "feedback", "label": "Phản hồi"},
                    {"value": "return_refund", "label": "Đổi trả hoàn tiền"},
                    {"value": "account_issues", "label": "Vấn đề tài khoản"},
                    {"value": "order_status", "label": "Trạng thái đơn hàng"},
                    {"value": "delivery", "label": "Giao hàng"}
                ]
            }
        }
        
        return {
            "success": True,
            "data": {
                "categories": categories,
                "tags": tags
            },
            "message": "Q&A pair options retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting Q&A pair options: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
