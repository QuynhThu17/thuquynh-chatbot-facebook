# Product Management với Image Embedding - Hướng dẫn Sử dụng

## 📋 Tổng Quan

Hệ thống Product Management được nâng cấp với khả năng:
- ✅ **Image Embedding**: Tự động tạo embedding cho ảnh sản phẩm
- ✅ **AI-Powered Search**: Tìm kiếm sản phẩm bằng ảnh tương tự
- ✅ **RAG Integration**: Tích hợp với RAG system để bot có thể tư vấn sản phẩm
- ✅ **Product Variants**: Hỗ trợ sản phẩm có nhiều biến thể (màu sắc, kích thước,...)
- ✅ **S3 Storage**: Lưu trữ ảnh trên AWS S3

## 🏗️ Kiến Trúc

```
Product Management System
│
├── Product Collection (MongoDB)
│   ├── Simple Product (1 SKU, 1 giá)
│   └── Variant Product (nhiều SKU, nhiều giá)
│
├── Knowledge Chunks Collection (MongoDB)
│   └── Product Image Chunks (với embeddings)
│
└── S3 Bucket
    └── Product Images
```

## 📊 Data Schema

### 1. Product Document (Simple)
```json
{
    "_id": "ObjectId(...)",
    "name": "MacBook Pro 14 inch",
    "description": "Laptop cao cấp cho developer",
    "category": "Laptops",
    "brand": "Apple",
    "tags": ["laptop", "macbook", "developer"],
    
    "product_type": "simple",
    "sku": "MBP14-001",
    
    "simple_product": {
        "sku": "MBP14-001",
        "pricing": {
            "cost": 40000000,
            "price": 50000000,
            "currency": "VND"
        },
        "media": [
            {
                "type": "image",
                "url": "https://s3.../products/user123/prod456/img1.jpg",
                "image_id": "img_uuid_001",
                "chunk_id": "ObjectId(...)",
                "alt_text": "MacBook Pro front view",
                "position": 0,
                "is_primary": true
            }
        ]
    },
    
    "status": "active",
    "user_id": "user123",
    "company_id": "comp456",
    "create_at": "2025-10-06T...",
    "update_at": "2025-10-06T..."
}
```

### 2. Product Document (Variant)
```json
{
    "_id": "ObjectId(...)",
    "name": "iPhone 15 Pro",
    "description": "Smartphone cao cấp",
    "category": "Smartphones",
    "brand": "Apple",
    "tags": ["smartphone", "iphone", "5g"],
    
    "product_type": "variant",
    "base_sku": "IP15PRO",
    
    "variants": [
        {
            "variant_id": "var_001",
            "sku": "IP15PRO-256-BLK",
            "attributes": {
                "storage": "256GB",
                "color": "Black Titanium"
            },
            "pricing": {
                "cost": 25000000,
                "price": 30000000,
                "currency": "VND"
            },
            "media": [
                {
                    "type": "image",
                    "url": "https://s3.../img.jpg",
                    "image_id": "img_uuid_002",
                    "chunk_id": "ObjectId(...)",
                    "position": 0,
                    "is_primary": true
                }
            ],
            "weight": 221,
            "dimensions": {
                "length": 159.9,
                "width": 76.7,
                "height": 8.25,
                "unit": "mm"
            }
        },
        {
            "variant_id": "var_002",
            "sku": "IP15PRO-512-WHT",
            "attributes": {
                "storage": "512GB",
                "color": "White Titanium"
            },
            "pricing": {
                "cost": 28000000,
                "price": 35000000,
                "currency": "VND"
            },
            "media": [...]
        }
    ],
    
    "user_id": "user123",
    "company_id": "comp456"
}
```

### 3. Knowledge Chunk (Product Image)
```json
{
    "_id": "ObjectId(...)",
    "content": "Product: iPhone 15 Pro\nVariant: Storage: 256GB, Color: Black Titanium\nPrice: 30,000,000 VND\nCategory: Smartphones",
    "content_embedding": [0.123, 0.456, ...],  // 1152-dim vector
    "content_embedding_text": "",
    
    "chunk_type": "product_image",
    
    "source_info": {
        "type": "product",
        "source_id": "ObjectId(...)",
        "product_name": "iPhone 15 Pro",
        "variant_id": "var_001",
        "image_id": "img_uuid_002"
    },
    
    "metadata": {
        "chunk_type": "product_image",
        "image_url": "https://s3.../img.jpg",
        "sku": "IP15PRO-256-BLK",
        "product_name": "iPhone 15 Pro",
        "category": "Smartphones",
        "brand": "Apple",
        "tags": ["smartphone", "iphone", "5g"],
        "pricing": {
            "cost": 25000000,
            "price": 30000000,
            "currency": "VND"
        },
        "attributes": {
            "storage": "256GB",
            "color": "Black Titanium"
        },
        "position": 0,
        "is_primary": true,
        "processed_at": "2025-10-06T..."
    },
    
    "user_id": "user123",
    "company_id": "comp456"
}
```

## 🔧 API Endpoints

### 1. Tạo Product với Images

#### Simple Product
```python
POST /api/v1/business/products/with-images

Request Body:
{
    "name": "MacBook Pro 14 inch",
    "sku": "MBP14-001",
    "pricing": {
        "cost": 40000000,
        "price": 50000000,
        "currency": "VND"
    },
    "category": "Laptops",
    "brand": "Apple",
    "description": "Laptop cao cấp cho developer",
    "tags": ["laptop", "macbook"],
    "images": [
        {
            "file_data": "<base64_encoded_image>",
            "file_name": "macbook-front.jpg",
            "alt_text": "MacBook Pro front view",
            "is_primary": true
        },
        {
            "file_data": "<base64_encoded_image>",
            "file_name": "macbook-side.jpg",
            "alt_text": "MacBook Pro side view"
        }
    ]
}

Response:
{
    "success": true,
    "data": {
        "_id": "...",
        "name": "MacBook Pro 14 inch",
        "product_type": "simple",
        "simple_product": {
            "media": [
                {
                    "url": "https://s3.../img.jpg",
                    "chunk_id": "...",
                    "is_primary": true
                }
            ]
        }
    }
}
```

#### Variant Product
```python
POST /api/v1/business/products/with-images

Request Body:
{
    "name": "iPhone 15 Pro",
    "sku": "IP15PRO",  // Base SKU
    "category": "Smartphones",
    "brand": "Apple",
    "description": "Smartphone cao cấp",
    "tags": ["smartphone", "iphone"],
    "variants": [
        {
            "sku": "IP15PRO-256-BLK",
            "attributes": {
                "storage": "256GB",
                "color": "Black Titanium"
            },
            "pricing": {
                "cost": 25000000,
                "price": 30000000,
                "currency": "VND"
            },
            "images": [
                {
                    "file_data": "<base64>",
                    "file_name": "ip15-black.jpg",
                    "is_primary": true
                }
            ]
        },
        {
            "sku": "IP15PRO-512-WHT",
            "attributes": {
                "storage": "512GB",
                "color": "White Titanium"
            },
            "pricing": {
                "cost": 28000000,
                "price": 35000000,
                "currency": "VND"
            },
            "images": [
                {
                    "file_data": "<base64>",
                    "file_name": "ip15-white.jpg"
                }
            ]
        }
    ]
}
```

### 2. Tìm Kiếm Product Bằng Ảnh

```python
POST /api/v1/business/products/search/by-image

Request Body:
{
    "query_image": "<base64_encoded_image>",
    "category": "Smartphones",  // Optional
    "price_range": {            // Optional
        "min": 10000000,
        "max": 50000000
    },
    "limit": 20
}

Response:
{
    "success": true,
    "data": [
        {
            "_id": "...",
            "name": "iPhone 15 Pro",
            "similarity_score": 0.95,
            "matched_image": "https://s3.../img.jpg",
            "variants": [...]
        },
        {
            "_id": "...",
            "name": "Samsung Galaxy S24",
            "similarity_score": 0.87,
            ...
        }
    ]
}
```

### 3. Tìm Kiếm Product Bằng Text

```python
GET /api/v1/business/products/search?q=iphone+đen&category=Smartphones

Response:
{
    "success": true,
    "data": [
        {
            "_id": "...",
            "name": "iPhone 15 Pro",
            "variants": [
                {
                    "sku": "IP15PRO-256-BLK",
                    "attributes": {"color": "Black Titanium"},
                    ...
                }
            ]
        }
    ]
}
```

### 4. Xóa Product với Cleanup

```python
DELETE /api/v1/business/products/{product_id}

Response:
{
    "success": true,
    "message": "Product deleted successfully",
    "data": {
        "product_id": "...",
        "deleted_chunks": 5,
        "deleted_images": 5
    }
}
```

## 🤖 RAG Integration - Bot Tư Vấn Sản Phẩm

### Use Cases

#### 1. User hỏi về sản phẩm
```
User: "Cho tôi xem các điện thoại màu đen giá dưới 30 triệu"

Bot Process:
1. Tạo text embedding từ query
2. Search knowledge_chunks với:
   - chunk_type = "product_image"
   - metadata.category = "Smartphones"
   - metadata.pricing.price <= 30000000
   - metadata.attributes.color contains "Black"
3. Trả về kết quả với ảnh

Bot Response:
"Tôi tìm thấy 3 sản phẩm phù hợp:

1. iPhone 15 Pro - Black Titanium 256GB
   Giá: 30,000,000 VND
   [Ảnh sản phẩm]
   
2. Samsung Galaxy S24 - Phantom Black
   Giá: 22,000,000 VND
   [Ảnh sản phẩm]
   
3. Xiaomi 14 Pro - Black
   Giá: 18,000,000 VND
   [Ảnh sản phẩm]
   
Bạn quan tâm sản phẩm nào?"
```

#### 2. User gửi ảnh để tìm sản phẩm tương tự
```
User: [Upload ảnh iPhone]

Bot Process:
1. Generate image embedding từ ảnh user
2. Vector search trong product_image chunks
3. Tìm các sản phẩm có ảnh tương tự

Bot Response:
"Tôi tìm thấy các sản phẩm tương tự:

1. iPhone 15 Pro - Black Titanium (95% match)
   Giá: 30,000,000 VND
   [Ảnh]
   
2. iPhone 14 Pro Max (87% match)
   Giá: 28,000,000 VND
   [Ảnh]

Bạn muốn xem chi tiết sản phẩm nào?"
```

#### 3. User hỏi về specs
```
User: "iPhone 15 Pro có bộ nhớ bao nhiêu?"

Bot Process:
1. Search product by name
2. Get variants info
3. Return specs

Bot Response:
"iPhone 15 Pro có các phiên bản bộ nhớ:
- 256GB: 30,000,000 VND
- 512GB: 35,000,000 VND
- 1TB: 40,000,000 VND

Bạn cần phiên bản nào?"
```

## 🔌 Integration Code

### Backend Service
```python
from controllers.data.managements.product_enhanced_manager import ProductEnhancedManager
from controllers.data.managements import get_mongodb_factory

# Initialize
factory = get_mongodb_factory()
product_manager = ProductEnhancedManager(factory.db_manager)
product_manager.set_dependencies(
    knowledge_chunk_manager=factory.knowledge_chunk_manager,
    s3_manager=s3_manager  # Your S3 manager instance
)

# Create product
product = await product_manager.create_product_with_images(
    name="iPhone 15 Pro",
    user_id=user_id,
    sku="IP15PRO",
    pricing={"price": 30000000, "currency": "VND"},
    images=[
        {
            "file_data": image_bytes,
            "file_name": "iphone15.jpg",
            "alt_text": "iPhone 15 Pro",
            "is_primary": True
        }
    ],
    category="Smartphones",
    brand="Apple",
    company_id=company_id
)

# Search by image
similar_products = await product_manager.search_products_by_image(
    query_image_data=user_image_bytes,
    user_id=user_id,
    category="Smartphones",
    price_range={"max": 50000000},
    limit=10
)

# Search by text
products = await product_manager.search_products_by_text(
    query="iphone đen",
    user_id=user_id,
    category="Smartphones"
)
```

### RAG Service Integration
```python
from controllers.rag.retrieval_service import RetrievalService

retrieval_service = RetrievalService()

# User query
user_query = "Cho tôi xem điện thoại màu đen giá dưới 30 triệu"

# Search product chunks
results = await retrieval_service.retrieve(
    query=user_query,
    user_id=user_id,
    company_id=company_id,
    filters={
        "chunk_type": "product_image",
        "metadata.category": "Smartphones",
        "metadata.pricing.price": {"$lte": 30000000}
    },
    top_k=10
)

# Build bot response with product images
for result in results:
    product_info = result["metadata"]
    image_url = product_info["image_url"]
    # Send to user...
```

## 📈 Performance & Optimization

### Image Embedding Performance
- **Model**: SigLIP (1152-dim vectors)
- **Processing Time**: ~200ms per image
- **Storage**: ~3KB per embedding

### Vector Search Performance
- **Query Time**: ~50ms for 10K products
- **Accuracy**: ~95% for similar images

### Recommendations
1. **Batch Processing**: Process multiple images in parallel
2. **Caching**: Cache frequently searched products
3. **CDN**: Use CloudFront for S3 images
4. **Indexing**: Create MongoDB indexes for common filters

## 🚀 Next Steps

### Phase 2: Inventory Management
- [ ] Create InventoryItem collection
- [ ] Real-time stock tracking
- [ ] Inventory reservation on order
- [ ] Stock alerts

### Phase 3: Advanced Features
- [ ] Product recommendations (ML-based)
- [ ] Price optimization
- [ ] Sales analytics
- [ ] Multi-warehouse routing

## 📞 Support

Nếu có vấn đề hoặc câu hỏi, vui lòng liên hệ:
- Email: dev@mekongai.com
- Docs: https://docs.mekongai.com/product-management

---

**MekongAI Development Team**  
**Version**: 1.0.0  
**Last Updated**: 06/10/2025
