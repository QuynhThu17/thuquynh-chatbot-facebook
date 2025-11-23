"""
Enhanced Product Manager với Image Embedding Support
Quản lý products với AI-powered image search và RAG integration
"""

import logging
import io
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from bson import ObjectId

# Image processing
from PIL import Image
import torch
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from controllers.databases.mongodb.mongodb import MongoDBManager
from .base_manager import BaseManager
from configs.environment import get_image_embedding_model, embeddings_model

logger = logging.getLogger(__name__)


class ProductEnhancedManager(BaseManager):
    """
    Enhanced Product Manager với image embedding capabilities
    
    Features:
    - Tự động generate image embeddings cho product images
    - Lưu embeddings vào knowledge_chunks để tích hợp RAG
    - Hỗ trợ tìm kiếm product bằng ảnh
    - Hỗ trợ product variants (size, color, etc.)
    - Category & taxonomy support
    """
    
    def __init__(self, db_manager: MongoDBManager):
        super().__init__(db_manager, "products")
        self.knowledge_chunk_manager = None  # Will be injected
        self.s3_manager = None  # Will be injected
    
    def set_dependencies(self, knowledge_chunk_manager, s3_manager):
        """Inject dependencies"""
        self.knowledge_chunk_manager = knowledge_chunk_manager
        self.s3_manager = s3_manager
    
    async def _generate_image_embedding(self, image_data: bytes) -> List[float]:
        """
        Generate image embedding using SigLIP model
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            List[float]: Image embedding vector (1152 dimensions)
        """
        try:
            # Load image from bytes
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get model and processor
            image_model, image_processor = get_image_embedding_model()
            
            # Process image
            inputs = image_processor(images=image, return_tensors="pt")
            
            # Generate embedding
            with torch.no_grad():
                outputs = image_model.get_image_features(**inputs)
                # Normalize embedding
                embedding = outputs / outputs.norm(dim=-1, keepdim=True)
                embedding_list = embedding.squeeze().cpu().numpy().tolist()
            
            logger.info(f"Generated image embedding with dimension: {len(embedding_list)}")
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating image embedding: {str(e)}")
            # Fallback to zero vector (1152 dimensions for siglip-base)
            return [0.0] * 1152
    
    async def _upload_image_to_s3(self, image_data: bytes, file_name: str, 
                                 user_id: str, product_id: str) -> Optional[str]:
        """
        Upload image to S3
        
        Args:
            image_data: Raw image bytes
            file_name: Original file name
            user_id: User ID for path
            product_id: Product ID for path
            
        Returns:
            str: S3 URL or None if failed
        """
        try:
            if not self.s3_manager:
                logger.warning("S3 manager not configured, skipping upload")
                return None
            
            # Generate unique image ID
            image_id = str(uuid.uuid4())
            file_extension = file_name.split('.')[-1] if '.' in file_name else 'jpg'
            s3_key = f"products/{user_id}/{product_id}/{image_id}.{file_extension}"
            
            # Upload to S3
            s3_url = await self.s3_manager.upload_file(
                file_data=image_data,
                file_name=s3_key,
                content_type=f"image/{file_extension}"
            )
            
            return s3_url
            
        except Exception as e:
            logger.error(f"Error uploading image to S3: {str(e)}")
            return None
    
    async def _create_product_image_chunk(self, product_info: Dict[str, Any],
                                         variant_info: Optional[Dict[str, Any]],
                                         image_url: str,
                                         image_embedding: List[float],
                                         user_id: str,
                                         company_id: Optional[str],
                                         image_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tạo knowledge chunk cho product image với embedding
        Cấu trúc giống document image chunks:
        - content: Full thông tin product (như full page content)
        - content_embedding: Image embedding
        - chunk_type: "image"
        - metadata: Chứa product info để filter
        
        Args:
            product_info: Thông tin product
            variant_info: Thông tin variant (nếu có)
            image_url: URL ảnh trên S3
            image_embedding: Image embedding vector
            user_id: User ID
            company_id: Company ID
            image_metadata: Additional image metadata
            
        Returns:
            Dict: Created chunk document
        """
        try:
            # Build FULL content text (như full page content của document)
            product_name = product_info.get("name", "Unknown Product")
            sku = variant_info.get("sku") if variant_info else product_info.get("sku")
            category = product_info.get("category") or product_info.get("data", {}).get("category") or "uncategorized"
            brand = product_info.get("brand") or product_info.get("data", {}).get("brand") or ""
            
            # Build detailed content
            content_parts = [
                f"Product: {product_name}",
                f"SKU: {sku}",
            ]
            
            if brand:
                content_parts.append(f"Brand: {brand}")
            
            content_parts.append(f"Category: {category}")
            
            # Add variant info if exists
            if variant_info:
                variant_desc = ", ".join([f"{k}: {v}" for k, v in variant_info.get("attributes", {}).items()])
                if variant_desc:
                    content_parts.append(f"Variant: {variant_desc}")
                
                pricing = variant_info.get("pricing", {})
                if pricing.get("cost"):
                    content_parts.append(f"Cost: {pricing['cost']:,.0f} {pricing.get('currency', 'VND')}")
                if pricing.get("price"):
                    content_parts.append(f"Price: {pricing['price']:,.0f} {pricing.get('currency', 'VND')}")
                if pricing.get("sale_price"):
                    content_parts.append(f"Sale Price: {pricing['sale_price']:,.0f} {pricing.get('currency', 'VND')}")
                    
                # Add dimensions if exist
                dimensions = variant_info.get("dimensions")
                if dimensions:
                    dim_str = f"{dimensions.get('length')}x{dimensions.get('width')}x{dimensions.get('height')} {dimensions.get('unit', 'mm')}"
                    content_parts.append(f"Dimensions: {dim_str}")
                    
                # Add weight
                weight = variant_info.get("weight")
                if weight:
                    content_parts.append(f"Weight: {weight}g")
            else:
                # Simple product pricing
                pricing = product_info.get("pricing", {})
                if pricing.get("cost"):
                    content_parts.append(f"Cost: {pricing['cost']:,.0f} {pricing.get('currency', 'VND')}")
                if pricing.get("price"):
                    content_parts.append(f"Price: {pricing['price']:,.0f} {pricing.get('currency', 'VND')}")
                if pricing.get("sale_price"):
                    content_parts.append(f"Sale Price: {pricing['sale_price']:,.0f} {pricing.get('currency', 'VND')}")
            
            # Add description
            description = product_info.get("description") or product_info.get("data", {}).get("description")
            if description:
                content_parts.append(f"Description: {description}")
            
            # Add tags
            tags = product_info.get("tags", [])
            if tags:
                content_parts.append(f"Tags: {', '.join(tags)}")
            
            # Add image tag (giống document)
            content_parts.append(f"\n<image:{image_url}>")
            
            content = "\n".join(content_parts)
            
            # Prepare source info
            source_info = {
                "type": "product",
                "source_id": str(product_info.get("_id")),
                "title": product_name
            }
            
            # Prepare metadata (giống document image chunks)
            chunk_metadata = {
                "chunk_type": "image",
                "image_url": image_url,
                "image_id": image_metadata.get("image_id"),
                "image_position": image_metadata.get("position", 0),
                "is_primary": image_metadata.get("is_primary", False),
                # Product-specific metadata
                "sku": sku,
                "product_name": product_name,
                "category": category,
                "brand": brand,
                "tags": tags,
                "variant_id": variant_info.get("variant_id") if variant_info else None,
                "processed_at": get_vietnam_now_naive().isoformat()
            }
            
            # Add pricing to metadata for filtering
            if variant_info:
                chunk_metadata["pricing"] = variant_info.get("pricing", {})
                chunk_metadata["attributes"] = variant_info.get("attributes", {})
            else:
                chunk_metadata["pricing"] = product_info.get("pricing", {})
            
            # Tạo chunk giống document image chunk structure
            chunk_data = {
                "content": content,  # Full product info
                "content_embedding_text": "",  # Empty for image chunks
                "content_embedding": image_embedding,  # Image embedding
                "chunk_type": "image",  # Giống document image
                "source_info": source_info,
                "metadata": chunk_metadata,
                "user_id": user_id,
                "company_id": company_id
            }
            
            # Create chunk using base create method
            chunk = await self.knowledge_chunk_manager.create(chunk_data)
            
            logger.info(f"Created product image chunk: {chunk['_id']} for product {product_name}")
            return chunk
            
        except Exception as e:
            logger.error(f"Error creating product image chunk: {str(e)}")
            raise
    
    async def create_product_with_images(self, 
                                        name: str,
                                        user_id: str,
                                        sku: str,
                                        pricing: Dict[str, Any],
                                        images: List[Dict[str, Any]],  # [{file_data, file_name, alt_text, is_primary}]
                                        company_id: Optional[str] = None,
                                        category: Optional[str] = None,
                                        brand: Optional[str] = None,
                                        description: Optional[str] = None,
                                        tags: Optional[List[str]] = None,
                                        data: Optional[Dict[str, Any]] = None,
                                        variants: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Tạo product mới với image embedding
        
        Args:
            name: Tên sản phẩm
            user_id: ID user
            sku: Mã SKU (cho simple product hoặc base SKU cho variant product)
            pricing: Thông tin giá (cho simple product)
            images: List ảnh [{file_data, file_name, alt_text, is_primary}]
            company_id: ID company
            category: Danh mục sản phẩm
            brand: Thương hiệu
            description: Mô tả sản phẩm
            tags: Tags cho search
            data: Dữ liệu bổ sung
            variants: List variants (nếu là variant product)
            
        Returns:
            Dict: Created product document
        """
        try:
            # Tạo product document trước để có product_id
            product_data = {
                "name": name,
                "description": description,
                "category": category,
                "brand": brand,
                "tags": tags or [],
                "user_id": user_id,
                "company_id": company_id,
                "data": data or {}
            }
            
            if variants:
                # Variant product
                product_data["product_type"] = "variant"
                product_data["base_sku"] = sku
                product_data["variants"] = []
            else:
                # Simple product
                product_data["product_type"] = "simple"
                product_data["sku"] = sku
                product_data["pricing"] = pricing
                product_data["simple_product"] = {
                    "sku": sku,
                    "pricing": pricing,
                    "media": []
                }
            
            product_data["status"] = "active"
            
            # Create product document
            product = await self.create(product_data)
            product_id = str(product["_id"])
            
            # Process images for simple product
            if not variants:
                media_items = await self._process_images(
                    images=images,
                    product_info=product,
                    variant_info=None,
                    user_id=user_id,
                    company_id=company_id,
                    product_id=product_id
                )
                
                # Update product with media
                await self.update_by_id(product_id, {
                    "simple_product.media": media_items
                })
                
            else:
                # Process variants
                processed_variants = []
                for variant_data in variants:
                    variant_images = variant_data.pop("images", [])
                    
                    # Process variant images
                    media_items = await self._process_images(
                        images=variant_images,
                        product_info=product,
                        variant_info=variant_data,
                        user_id=user_id,
                        company_id=company_id,
                        product_id=product_id
                    )
                    
                    variant_data["media"] = media_items
                    variant_data["variant_id"] = str(uuid.uuid4())
                    processed_variants.append(variant_data)
                
                # Update product with variants
                await self.update_by_id(product_id, {
                    "variants": processed_variants
                })
            
            # Get updated product
            updated_product = await self.get_by_id(product_id)
            return updated_product
            
        except Exception as e:
            logger.error(f"Error creating product with images: {str(e)}")
            # Cleanup on error
            if 'product_id' in locals():
                await self.delete_by_id(product_id)
            raise
    
    async def _process_images(self, images: List[Dict[str, Any]],
                             product_info: Dict[str, Any],
                             variant_info: Optional[Dict[str, Any]],
                             user_id: str,
                             company_id: Optional[str],
                             product_id: str) -> List[Dict[str, Any]]:
        """
        Process và upload images, generate embeddings
        
        Args:
            images: List ảnh với file_data
            product_info: Product info
            variant_info: Variant info (nếu có)
            user_id: User ID
            company_id: Company ID
            product_id: Product ID
            
        Returns:
            List[Dict]: Processed media items
        """
        media_items = []
        
        for idx, image_data in enumerate(images):
            try:
                file_data = image_data.get("file_data")
                file_name = image_data.get("file_name", f"image_{idx}.jpg")
                alt_text = image_data.get("alt_text", "")
                is_primary = image_data.get("is_primary", idx == 0)
                
                if not file_data:
                    logger.warning(f"Skipping image {idx}: no file_data")
                    continue
                
                # Upload to S3
                image_url = await self._upload_image_to_s3(
                    image_data=file_data,
                    file_name=file_name,
                    user_id=user_id,
                    product_id=product_id
                )
                
                if not image_url:
                    logger.warning(f"Failed to upload image {idx}")
                    continue
                
                # Generate embedding
                image_embedding = await self._generate_image_embedding(file_data)
                
                # Create knowledge chunk
                image_id = str(uuid.uuid4())
                chunk = await self._create_product_image_chunk(
                    product_info=product_info,
                    variant_info=variant_info,
                    image_url=image_url,
                    image_embedding=image_embedding,
                    user_id=user_id,
                    company_id=company_id,
                    image_metadata={
                        "image_id": image_id,
                        "position": idx,
                        "alt_text": alt_text,
                        "is_primary": is_primary
                    }
                )
                
                # Build media item
                media_item = {
                    "type": "image",
                    "url": image_url,
                    "image_id": image_id,
                    "chunk_id": str(chunk["_id"]),
                    "alt_text": alt_text,
                    "position": idx,
                    "is_primary": is_primary
                }
                
                media_items.append(media_item)
                
            except Exception as e:
                logger.error(f"Error processing image {idx}: {str(e)}")
                continue
        
        return media_items
    
    async def search_products_by_image(self, query_image_data: bytes,
                                      user_id: Optional[str] = None,
                                      company_id: Optional[str] = None,
                                      category: Optional[str] = None,
                                      price_range: Optional[Dict[str, float]] = None,
                                      limit: int = 20) -> List[Dict[str, Any]]:
        """
        Tìm kiếm products bằng ảnh tương tự
        
        Args:
            query_image_data: Query image bytes
            user_id: Filter by user (optional)
            company_id: Filter by company (optional)
            category: Filter by category (optional)
            price_range: {"min": 0, "max": 1000000}
            limit: Max results
            
        Returns:
            List[Dict]: Similar products with scores
        """
        try:
            logger.info(f"🖼️ === SEARCH_PRODUCTS_BY_IMAGE START ===")
            logger.info(f"   Image data size: {len(query_image_data)} bytes")
            logger.info(f"   company_id: {company_id}")
            logger.info(f"   category: {category}")
            logger.info(f"   price_range: {price_range}")
            logger.info(f"   limit: {limit}")
            
            # Generate embedding for query image
            query_embedding = await self._generate_image_embedding(query_image_data)
            logger.info(f"✅ Generated query embedding: dimension={len(query_embedding)}")
            
            # Build filter for knowledge_chunks (chunk_type = "image" + source_info.type = "product")
            filter_dict = {
                "chunk_type": "image",
                "source_info.type": "product"
            }
            
            if user_id:
                filter_dict["user_id"] = user_id
            if company_id:
                filter_dict["company_id"] = company_id
            if category:
                filter_dict["metadata.category"] = category
            if price_range:
                if price_range.get("min"):
                    filter_dict["metadata.pricing.price"] = {"$gte": price_range["min"]}
                if price_range.get("max"):
                    filter_dict["metadata.pricing.price"] = {"$lte": price_range["max"]}
            
            logger.info(f"🔍 Searching image chunks with filter: {filter_dict}")
            
            # ✅ FIX: Get ALL image chunks (KHÔNG giới hạn) để tránh miss products
            # Trước đây: limit=limit * 10 (chỉ 50 chunks) → chỉ lấy products đầu tiên
            # Bây giờ: limit=0 để lấy HẾT tất cả image chunks trong DB
            # Lý do: Nếu chỉ lấy N chunks đầu tiên, có thể miss các products khác
            # vì chunks được sort theo _id (thứ tự upload), không phải similarity
            similar_chunks = await self.knowledge_chunk_manager.get_all(
                filter_query=filter_dict,
                limit=0  # ✅ 0 = unlimited, lấy HẾT tất cả chunks
            )
            
            logger.info(f"📄 Found {len(similar_chunks)} image chunks from database (ALL chunks, no limit)")
            
            if not similar_chunks:
                logger.warning(f"❌ No image chunks found matching filter: {filter_dict}")
                return []
            
            # ✅ Calculate cosine similarity for each chunk (same as search_image_in_knowledge)
            query_vec = np.array(query_embedding).reshape(1, -1)
            similarities = []
            
            logger.info(f"🔢 Calculating similarities for {len(similar_chunks)} chunks...")
            
            # ✅ Track unique products để debug
            unique_product_ids = set()
            
            for chunk in similar_chunks:
                chunk_embedding = chunk.get('content_embedding')
                if chunk_embedding and len(chunk_embedding) == len(query_embedding):
                    chunk_vec = np.array(chunk_embedding).reshape(1, -1)
                    # ✅ IMPORTANT: Normalize cả 2 vectors
                    chunk_vec_normalized = chunk_vec / np.linalg.norm(chunk_vec)
                    query_vec_normalized = query_vec / np.linalg.norm(query_vec)
                    
                    similarity = cosine_similarity(query_vec_normalized, chunk_vec_normalized)[0][0]
                    
                    product_id = chunk.get('source_info', {}).get('source_id')
                    unique_product_ids.add(product_id)
                    
                    similarities.append({
                        'chunk': chunk,
                        'similarity': float(similarity),
                        'product_id': product_id,
                        'chunk_name': chunk.get('chunk_name', 'Unknown')
                    })
            
            logger.info(f"✅ Calculated {len(similarities)} similarity scores")
            logger.info(f"📦 Found {len(unique_product_ids)} unique products in chunks")
            
            if not similarities:
                logger.warning(f"❌ No valid embeddings found to compare")
                return []
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            # ✅ Log top 10 matches (tăng từ 5 lên 10 để thấy diversity)
            logger.info(f"🎯 Top 10 similarity scores:")
            for i, match in enumerate(similarities[:10], 1):
                chunk_content = match['chunk'].get('content', '')[:100]  # First 100 chars
                logger.info(f"  {i}. Product: {match.get('product_id')} | "
                          f"Similarity: {match['similarity']:.4f} ({match['similarity']:.2%}) | "
                          f"Content: {chunk_content}...")
            
            logger.info(f"✅ Found {len(similarities)} products with similarity scores")
            if similarities:
                logger.info(f"   Top match: {similarities[0]['similarity']:.4f}")
            
            # Group by product_id and get best match per product
            products_map = {}
            for item in similarities:
                chunk = item['chunk']
                similarity_score = item['similarity']
                
                source_info = chunk.get("source_info", {})
                product_id = source_info.get("source_id")
                
                if product_id not in products_map:
                    products_map[product_id] = {
                        "product_id": product_id,
                        "score": similarity_score,  # ✅ Real similarity score from vector search!
                        "chunk": chunk
                    }
            
            logger.info(f"📦 Grouped into {len(products_map)} unique products")
            
            # Get full product info
            results = []
            for product_match in products_map.values():
                product = await self.get_by_id(product_match["product_id"])
                if product:
                    product["similarity_score"] = product_match["score"]
                    product["matched_image"] = product_match["chunk"].get("metadata", {}).get("image_url")
                    results.append(product)
                    logger.info(f"  ✅ Product {product.get('name', 'N/A')}: score={product_match['score']:.4f}")
            
            # ✅ Sort by real similarity score (highest first)
            results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
            
            logger.info(f"🎯 Returning top {min(limit, len(results))} products")
            logger.info(f"🖼️ === SEARCH_PRODUCTS_BY_IMAGE END ===\n")
            
            return results[:limit]  # Return top N most similar products
            
        except Exception as e:
            logger.error(f"Error searching products by image: {str(e)}")
            return []
    
    async def search_products_by_text(self, query: str,
                                     user_id: Optional[str] = None,
                                     company_id: Optional[str] = None,
                                     category: Optional[str] = None,
                                     limit: int = 100) -> List[Dict[str, Any]]:
        """
        Tìm kiếm products bằng text
        
        Args:
            query: Search query
            user_id: Filter by user
            company_id: Filter by company
            category: Filter by category
            limit: Max results (default 100, tăng từ 50)
            
        Returns:
            List[Dict]: Matching products
        """
        try:
            logger.info(f"🔍 TEXT SEARCH: query='{query}', company_id={company_id}, limit={limit}")
            
            # Build filter
            filter_query = {}
            if user_id:
                filter_query["user_id"] = user_id
            if company_id:
                filter_query["company_id"] = company_id
            if category:
                filter_query["category"] = category
            
            # Text search
            filter_query["$or"] = [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"tags": {"$regex": query, "$options": "i"}},
                {"sku": {"$regex": query, "$options": "i"}},
                {"base_sku": {"$regex": query, "$options": "i"}},
                {"variants.sku": {"$regex": query, "$options": "i"}}
            ]
            
            logger.info(f"🔍 Text search filter: {filter_query}")
            
            products = await self.get_all(filter_query=filter_query, limit=limit)
            
            logger.info(f"✅ Found {len(products)} products matching text query")
            
            return products
            
        except Exception as e:
            logger.error(f"Error searching products by text: {str(e)}")
            return []
    
    async def delete_product_with_cleanup(self, product_id: Union[str, ObjectId],
                                         user_id: str) -> bool:
        """
        Xóa product và cleanup tất cả related data
        
        Args:
            product_id: Product ID
            user_id: User ID for verification
            
        Returns:
            bool: Success status
        """
        try:
            # Get product
            product = await self.get_by_id(product_id)
            if not product:
                return False
            
            if product.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete product {product_id} owned by {product.get('user_id')}")
                return False
            
            # Collect all image URLs and chunk IDs
            image_urls = []
            chunk_ids = []
            
            if product.get("product_type") == "simple":
                media = product.get("simple_product", {}).get("media", [])
                for item in media:
                    if item.get("url"):
                        image_urls.append(item["url"])
                    if item.get("chunk_id"):
                        chunk_ids.append(item["chunk_id"])
            else:
                # Variant product
                for variant in product.get("variants", []):
                    for item in variant.get("media", []):
                        if item.get("url"):
                            image_urls.append(item["url"])
                        if item.get("chunk_id"):
                            chunk_ids.append(item["chunk_id"])
            
            # Delete chunks
            for chunk_id in chunk_ids:
                try:
                    await self.knowledge_chunk_manager.delete_by_id(chunk_id)
                except Exception as e:
                    logger.error(f"Error deleting chunk {chunk_id}: {str(e)}")
            
            # Delete images from S3
            if self.s3_manager:
                for image_url in image_urls:
                    try:
                        await self.s3_manager.delete_file(image_url)
                    except Exception as e:
                        logger.error(f"Error deleting S3 file {image_url}: {str(e)}")
            
            # Delete product
            await self.delete_by_id(product_id)
            
            logger.info(f"Deleted product {product_id} with {len(chunk_ids)} chunks and {len(image_urls)} images")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting product with cleanup: {str(e)}")
            return False
    
    async def process_product_images_from_urls(self,
                                              product_id: str,
                                              user_id: str,
                                              product_info: Dict[str, Any],
                                              image_urls: List[tuple]) -> List[str]:
        """
        Xử lý images từ URLs có sẵn (không upload S3)
        Chỉ download, generate embedding và tạo chunks
        
        Args:
            product_id: ID của product
            user_id: User ID
            product_info: Product info dict
            image_urls: List of (url, alt_text) tuples
            
        Returns:
            List[str]: List chunk IDs created
        """
        import requests
        
        chunk_ids = []
        
        for idx, (image_url, alt_text) in enumerate(image_urls):
            try:
                # Download image từ URL
                response = requests.get(image_url, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"Failed to download image from {image_url}")
                    continue
                
                image_data = response.content
                
                # Generate embedding
                image_embedding = await self._generate_image_embedding(image_data)
                
                # Create chunk
                image_id = str(uuid.uuid4())
                chunk = await self._create_product_image_chunk(
                    product_info=product_info,
                    variant_info=None,
                    image_url=image_url,
                    image_embedding=image_embedding,
                    user_id=user_id,
                    company_id=product_info.get("company_id"),
                    image_metadata={
                        "image_id": image_id,
                        "position": idx,
                        "alt_text": alt_text,
                        "is_primary": idx == 0
                    }
                )
                
                if chunk:
                    chunk_ids.append(str(chunk["_id"]))
                    logger.info(f"Created chunk for image {idx}: {image_url}")
                    
            except Exception as e:
                logger.error(f"Error processing image {image_url}: {str(e)}")
                continue
        
        logger.info(f"Processed {len(chunk_ids)} images for product {product_id}")
        return chunk_ids
    
    # ============ Existing methods from ProductManager ============
    
    async def get_by_user_id(self, user_id: str, company_id: str = None) -> List[Dict[str, Any]]:
        """Lấy products theo user_id"""
        filter_query = {"user_id": user_id}
        if company_id:
            filter_query["company_id"] = company_id
        
        return await self.get_all(filter_query=filter_query)
    
    async def get_by_sku(self, sku: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Lấy product theo SKU"""
        filter_query = {
            "$or": [
                {"sku": sku},
                {"base_sku": sku},
                {"variants.sku": sku}
            ]
        }
        if user_id:
            filter_query["user_id"] = user_id
        
        products = await self.get_all(filter_query=filter_query, limit=1)
        return products[0] if products else None
