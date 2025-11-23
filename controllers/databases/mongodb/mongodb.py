import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo.errors import (
    ConnectionFailure, 
    ServerSelectionTimeoutError,
    DuplicateKeyError,
    BulkWriteError,
    PyMongoError
)
from bson import ObjectId
import json
from configs.environment import get_vietnam_now_naive

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBManager:
    """
    MongoDB Manager - Quản lý kết nối và thao tác với MongoDB
    Hỗ trợ async/await, logging, error handling
    """
    
    def __init__(self, connection_string: str = None):
        """
        Khởi tạo MongoDB Manager
        
        Args:
            connection_string (str): Connection string MongoDB
        """
        self.connection_string = connection_string or "mongodb://admin:strongpassword@144.91.113.233:27017/admin?authSource=admin"
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self.is_connected = False
        
    async def connect(self, database_name: str = "mekongai_social") -> bool:
        """
        Kết nối tới MongoDB
        
        Args:
            database_name (str): Tên database
            
        Returns:
            bool: True nếu kết nối thành công
        """
        try:
            self.client = AsyncIOMotorClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000,
                maxPoolSize=50,
                minPoolSize=5
            )
            
            # Test connection
            await self.client.admin.command('ping')
            
            self.database = self.client[database_name]
            self.is_connected = True
            
            logger.info(f"✅ Kết nối thành công tới MongoDB database: {database_name}")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"❌ Lỗi kết nối MongoDB: {e}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"❌ Lỗi không xác định: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Ngắt kết nối MongoDB"""
        if self.client:
            self.client.close()
            self.is_connected = False
            logger.info("🔌 Đã ngắt kết nối MongoDB")
    
    def _ensure_connected(self):
        """Kiểm tra kết nối trước khi thực hiện thao tác"""
        if not self.is_connected or self.database is None:
            raise ConnectionError("Chưa kết nối tới MongoDB. Vui lòng gọi connect() trước.")
    
    # ================== DATABASE OPERATIONS ==================
    
    async def create_database(self, database_name: str) -> bool:
        """
        Tạo database mới
        
        Args:
            database_name (str): Tên database
            
        Returns:
            bool: True nếu tạo thành công
        """
        try:
            self._ensure_connected()
            # MongoDB tự động tạo database khi insert document đầu tiên
            temp_db = self.client[database_name]
            await temp_db.create_collection("_temp")
            await temp_db.drop_collection("_temp")
            
            logger.info(f"✅ Tạo database '{database_name}' thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi tạo database '{database_name}': {e}")
            return False
    
    async def list_databases(self) -> List[str]:
        """
        Liệt kê tất cả databases
        
        Returns:
            List[str]: Danh sách tên databases
        """
        try:
            self._ensure_connected()
            db_list = await self.client.list_database_names()
            logger.info(f"📋 Danh sách databases: {db_list}")
            return db_list
            
        except Exception as e:
            logger.error(f"❌ Lỗi liệt kê databases: {e}")
            return []
    
    async def drop_database(self, database_name: str) -> bool:
        """
        Xóa database
        
        Args:
            database_name (str): Tên database cần xóa
            
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            self._ensure_connected()
            await self.client.drop_database(database_name)
            logger.info(f"🗑️ Xóa database '{database_name}' thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi xóa database '{database_name}': {e}")
            return False
    
    # ================== COLLECTION OPERATIONS ==================
    
    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """
        Lấy collection
        
        Args:
            collection_name (str): Tên collection
            
        Returns:
            AsyncIOMotorCollection: Collection object
        """
        self._ensure_connected()
        return self.database[collection_name]
    
    async def create_collection(self, collection_name: str, **options) -> bool:
        """
        Tạo collection mới
        
        Args:
            collection_name (str): Tên collection
            **options: Các tùy chọn khác
            
        Returns:
            bool: True nếu tạo thành công
        """
        try:
            self._ensure_connected()
            await self.database.create_collection(collection_name, **options)
            logger.info(f"✅ Tạo collection '{collection_name}' thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi tạo collection '{collection_name}': {e}")
            return False
    
    async def list_collections(self) -> List[str]:
        """
        Liệt kê tất cả collections
        
        Returns:
            List[str]: Danh sách tên collections
        """
        try:
            self._ensure_connected()
            collections = await self.database.list_collection_names()
            logger.info(f"📋 Danh sách collections: {collections}")
            return collections
            
        except Exception as e:
            logger.error(f"❌ Lỗi liệt kê collections: {e}")
            return []
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        Xóa collection
        
        Args:
            collection_name (str): Tên collection cần xóa
            
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            self._ensure_connected()
            await self.database.drop_collection(collection_name)
            logger.info(f"🗑️ Xóa collection '{collection_name}' thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi xóa collection '{collection_name}': {e}")
            return False
    
    # ================== DOCUMENT OPERATIONS ==================
    
    async def insert_one(self, collection_name: str, document: Dict[str, Any]) -> Optional[str]:
        """
        Thêm một document
        
        Args:
            collection_name (str): Tên collection
            document (Dict): Document cần thêm (có thể chứa _id để chỉ định ObjectID cố định)
            
        Returns:
            Optional[str]: ID của document vừa thêm
        """
        try:
            self._ensure_connected()
            
            # Xử lý _id nếu được cung cấp
            custom_id = None
            if '_id' in document:
                custom_id = document['_id']
                # Nếu _id là string, chuyển thành ObjectId
                if isinstance(custom_id, str):
                    try:
                        document['_id'] = ObjectId(custom_id)
                        custom_id = document['_id']
                    except Exception:
                        # Nếu không thể convert thành ObjectId, giữ nguyên giá trị
                        pass
            
            # Thêm timestamp
            document['created_at'] = get_vietnam_now_naive()
            document['updated_at'] = get_vietnam_now_naive()
            
            collection = self.get_collection(collection_name)
            result = await collection.insert_one(document)
            
            # Sử dụng custom_id nếu có, ngược lại dùng inserted_id
            document_id = str(custom_id) if custom_id else str(result.inserted_id)
            logger.info(f"✅ Thêm document vào '{collection_name}' thành công. ID: {document_id}")
            return document_id
            
        except DuplicateKeyError as e:
            logger.error(f"❌ Lỗi trùng lặp key trong '{collection_name}': {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Lỗi thêm document vào '{collection_name}': {e}")
            return None
    
    async def insert_many(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[str]:
        """
        Thêm nhiều documents
        
        Args:
            collection_name (str): Tên collection
            documents (List[Dict]): Danh sách documents (có thể chứa _id để chỉ định ObjectID cố định)
            
        Returns:
            List[str]: Danh sách IDs của documents vừa thêm
        """
        try:
            self._ensure_connected()
            
            # Xử lý _id và timestamp cho tất cả documents
            current_time = get_vietnam_now_naive()
            custom_ids = []
            
            for i, doc in enumerate(documents):
                # Xử lý _id nếu được cung cấp
                if '_id' in doc:
                    custom_id = doc['_id']
                    # Nếu _id là string, chuyển thành ObjectId
                    if isinstance(custom_id, str):
                        try:
                            doc['_id'] = ObjectId(custom_id)
                            custom_ids.append(str(doc['_id']))
                        except Exception:
                            # Nếu không thể convert thành ObjectId, giữ nguyên giá trị
                            custom_ids.append(str(custom_id))
                    else:
                        custom_ids.append(str(custom_id))
                else:
                    custom_ids.append(None)
                
                # Thêm timestamp
                doc['created_at'] = current_time
                doc['updated_at'] = current_time
            
            collection = self.get_collection(collection_name)
            result = await collection.insert_many(documents)
            
            # Tạo danh sách IDs kết hợp custom_ids và inserted_ids
            document_ids = []
            for i, inserted_id in enumerate(result.inserted_ids):
                if custom_ids[i] is not None:
                    document_ids.append(custom_ids[i])
                else:
                    document_ids.append(str(inserted_id))
            
            logger.info(f"✅ Thêm {len(document_ids)} documents vào '{collection_name}' thành công")
            return document_ids
            
        except BulkWriteError as e:
            logger.error(f"❌ Lỗi bulk write trong '{collection_name}': {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Lỗi thêm documents vào '{collection_name}': {e}")
            return []
    
    async def find_one(self, collection_name: str, filter_dict: Dict[str, Any] = None, projection: Dict[str, int] = None) -> Optional[Dict[str, Any]]:
        """
        Tìm một document
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            projection (Dict): Các field cần lấy
            
        Returns:
            Optional[Dict]: Document tìm được
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            filter_dict = filter_dict or {}
            
            # Xử lý ObjectId nếu có
            if '_id' in filter_dict and isinstance(filter_dict['_id'], str):
                filter_dict['_id'] = ObjectId(filter_dict['_id'])
            
            result = await collection.find_one(filter_dict, projection)
            
            if result:
                # Convert ObjectId thành string
                if '_id' in result:
                    result['_id'] = str(result['_id'])
                logger.info(f"✅ Tìm thấy document trong '{collection_name}'")
            else:
                logger.info(f"🔍 Không tìm thấy document trong '{collection_name}' với filter: {filter_dict}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Lỗi tìm document trong '{collection_name}': {e}")
            return None
    
    async def find_many(self, collection_name: str, filter_dict: Dict[str, Any] = None, 
                       projection: Dict[str, int] = None, sort: List[tuple] = None, 
                       limit: int = None, skip: int = 0) -> List[Dict[str, Any]]:
        """
        Tìm nhiều documents
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            projection (Dict): Các field cần lấy
            sort (List[tuple]): Sắp xếp [('field', 1/-1)]
            limit (int): Giới hạn số lượng
            skip (int): Bỏ qua số lượng
            
        Returns:
            List[Dict]: Danh sách documents
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            filter_dict = filter_dict or {}
            
            cursor = collection.find(filter_dict, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            if skip > 0:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)
            
            results = await cursor.to_list(length=None)
            
            # Convert ObjectIds thành strings
            for result in results:
                if '_id' in result:
                    result['_id'] = str(result['_id'])
            
            logger.info(f"✅ Tìm thấy {len(results)} documents trong '{collection_name}'")
            return results
            
        except Exception as e:
            logger.error(f"❌ Lỗi tìm documents trong '{collection_name}': {e}")
            return []
    
    async def update_one(self, collection_name: str, filter_dict: Dict[str, Any], 
                        update_dict: Dict[str, Any], upsert: bool = False) -> bool:
        """
        Cập nhật một document
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            update_dict (Dict): Dữ liệu cập nhật
            upsert (bool): Tạo mới nếu không tìm thấy
            
        Returns:
            bool: True nếu cập nhật thành công
        """
        try:
            self._ensure_connected()
            
            # Xử lý ObjectId nếu có
            if '_id' in filter_dict and isinstance(filter_dict['_id'], str):
                filter_dict['_id'] = ObjectId(filter_dict['_id'])
            
            # Thêm timestamp
            if '$set' not in update_dict:
                update_dict = {'$set': update_dict}
            
            update_dict['$set']['updated_at'] = get_vietnam_now_naive()
            
            collection = self.get_collection(collection_name)
            result = await collection.update_one(filter_dict, update_dict, upsert=upsert)
            
            if result.modified_count > 0:
                logger.info(f"✅ Cập nhật document trong '{collection_name}' thành công")
                return True
            elif result.upserted_id and upsert:
                logger.info(f"✅ Tạo mới document trong '{collection_name}' thành công")
                return True
            else:
                logger.info(f"🔍 Không tìm thấy document để cập nhật trong '{collection_name}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ Lỗi cập nhật document trong '{collection_name}': {e}")
            return False
    
    async def update_many(self, collection_name: str, filter_dict: Dict[str, Any], 
                         update_dict: Dict[str, Any], upsert: bool = False) -> int:
        """
        Cập nhật nhiều documents
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            update_dict (Dict): Dữ liệu cập nhật
            upsert (bool): Tạo mới nếu không tìm thấy
            
        Returns:
            int: Số lượng documents đã cập nhật
        """
        try:
            self._ensure_connected()
            
            # Thêm timestamp
            if '$set' not in update_dict:
                update_dict = {'$set': update_dict}
            
            update_dict['$set']['updated_at'] = get_vietnam_now_naive()
            
            collection = self.get_collection(collection_name)
            result = await collection.update_many(filter_dict, update_dict, upsert=upsert)
            
            logger.info(f"✅ Cập nhật {result.modified_count} documents trong '{collection_name}' thành công")
            return result.modified_count
            
        except Exception as e:
            logger.error(f"❌ Lỗi cập nhật documents trong '{collection_name}': {e}")
            return 0
    
    async def delete_one(self, collection_name: str, filter_dict: Dict[str, Any]) -> bool:
        """
        Xóa một document
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            
        Returns:
            bool: True nếu xóa thành công
        """
        try:
            self._ensure_connected()
            
            # Xử lý ObjectId nếu có
            if '_id' in filter_dict and isinstance(filter_dict['_id'], str):
                filter_dict['_id'] = ObjectId(filter_dict['_id'])
            
            collection = self.get_collection(collection_name)
            result = await collection.delete_one(filter_dict)
            
            if result.deleted_count > 0:
                logger.info(f"✅ Xóa document trong '{collection_name}' thành công")
                return True
            else:
                logger.info(f"🔍 Không tìm thấy document để xóa trong '{collection_name}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ Lỗi xóa document trong '{collection_name}': {e}")
            return False
    
    async def delete_many(self, collection_name: str, filter_dict: Dict[str, Any]) -> int:
        """
        Xóa nhiều documents
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện tìm kiếm
            
        Returns:
            int: Số lượng documents đã xóa
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            result = await collection.delete_many(filter_dict)
            
            logger.info(f"✅ Xóa {result.deleted_count} documents trong '{collection_name}' thành công")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"❌ Lỗi xóa documents trong '{collection_name}': {e}")
            return 0
    
    # ================== ADVANCED OPERATIONS ==================
    
    async def count_documents(self, collection_name: str, filter_dict: Dict[str, Any] = None) -> int:
        """
        Đếm số lượng documents
        
        Args:
            collection_name (str): Tên collection
            filter_dict (Dict): Điều kiện đếm
            
        Returns:
            int: Số lượng documents
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            filter_dict = filter_dict or {}
            
            count = await collection.count_documents(filter_dict)
            logger.info(f"📊 Collection '{collection_name}' có {count} documents")
            return count
            
        except Exception as e:
            logger.error(f"❌ Lỗi đếm documents trong '{collection_name}': {e}")
            return 0
    
    async def aggregate(self, collection_name: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Thực hiện aggregation
        
        Args:
            collection_name (str): Tên collection
            pipeline (List[Dict]): Pipeline aggregation
            
        Returns:
            List[Dict]: Kết quả aggregation
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)
            
            # Convert ObjectIds thành strings
            for result in results:
                if '_id' in result and isinstance(result['_id'], ObjectId):
                    result['_id'] = str(result['_id'])
            
            # logger.info(f"✅ Aggregation trong '{collection_name}' trả về {len(results)} kết quả")
            return results
            
        except Exception as e:
            logger.error(f"❌ Lỗi aggregation trong '{collection_name}': {e}")
            return []
    
    async def create_index(self, collection_name: str, keys: Union[str, List[tuple]], **options) -> bool:
        """
        Tạo index cho collection
        
        Args:
            collection_name (str): Tên collection
            keys: Key hoặc list các keys cho index
            **options: Các tùy chọn khác
            
        Returns:
            bool: True nếu tạo thành công
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            await collection.create_index(keys, **options)
            
            logger.info(f"✅ Tạo index cho '{collection_name}' thành công")
            return True
            
        except Exception as e:
            logger.error(f"❌ Lỗi tạo index cho '{collection_name}': {e}")
            return False
    
    async def list_indexes(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        Liệt kê các indexes của collection
        
        Args:
            collection_name (str): Tên collection
            
        Returns:
            List[Dict]: Danh sách indexes
        """
        try:
            self._ensure_connected()
            
            collection = self.get_collection(collection_name)
            indexes = await collection.list_indexes().to_list(length=None)
            
            logger.info(f"📋 Collection '{collection_name}' có {len(indexes)} indexes")
            return indexes
            
        except Exception as e:
            logger.error(f"❌ Lỗi liệt kê indexes cho '{collection_name}': {e}")
            return []
    
    # ================== VECTOR SEARCH METHODS ==================
    
    async def vector_search(
        self, 
        collection_name: str, 
        query_vector: List[float],
        vector_field: str = "content_embedding",
        filter_query: Dict[str, Any] = None,
        limit: int = 10,
        similarity_threshold: float = 0.5  # Giảm threshold default
    ) -> List[Dict[str, Any]]:
        """
        Thực hiện vector similarity search sử dụng MongoDB aggregation
        
        Args:
            collection_name (str): Tên collection
            query_vector (List[float]): Vector embedding của query
            vector_field (str): Tên field chứa vector embedding
            filter_query (Dict): Filter query để lọc documents
            limit (int): Số lượng kết quả tối đa
            similarity_threshold (float): Ngưỡng similarity tối thiểu
            
        Returns:
            List[Dict]: Documents với similarity scores
        """
        try:
            self._ensure_connected()
            
            # Build aggregation pipeline cho vector similarity search
            pipeline = []
            
            # Stage 1: Match filter nếu có
            if filter_query:
                pipeline.append({"$match": filter_query})
            
            # Stage 2: Match documents có vector embedding
            pipeline.append({
                "$match": {
                    vector_field: {"$exists": True, "$ne": None}
                }
            })
            
            # Stage 3: Add computed similarity score
            # Sử dụng dot product approximation cho cosine similarity 
            # (MongoDB không có built-in cosine similarity)
            pipeline.append({
                "$addFields": {
                    "similarity_score": {
                        "$let": {
                            "vars": {
                                "dotProduct": {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": f"${vector_field}"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {"$multiply": [
                                                    {"$arrayElemAt": [f"${vector_field}", "$$this"]},
                                                    {"$arrayElemAt": [query_vector, "$$this"]}
                                                ]}
                                            ]
                                        }
                                    }
                                },
                                "normA": {
                                    "$sqrt": {
                                        "$reduce": {
                                            "input": f"${vector_field}",
                                            "initialValue": 0,
                                            "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                        }
                                    }
                                },
                                "normB": {
                                    "$literal": (sum(x * x for x in query_vector) ** 0.5)
                                }
                            },
                            "in": {
                                "$cond": {
                                    "if": {"$and": [{"$gt": ["$$normA", 0]}, {"$gt": ["$$normB", 0]}]},
                                    "then": {"$divide": ["$$dotProduct", {"$multiply": ["$$normA", "$$normB"]}]},
                                    "else": 0
                                }
                            }
                        }
                    }
                }
            })
            
            # Stage 4: Filter by similarity threshold
            pipeline.append({
                "$match": {
                    "similarity_score": {"$gte": similarity_threshold}
                }
            })
            
            # Stage 5: Sort by similarity score descending
            pipeline.append({
                "$sort": {"similarity_score": -1}
            })
            
            # Stage 6: Limit results
            pipeline.append({
                "$limit": limit
            })
            
            # Execute aggregation
            results = await self.aggregate(collection_name, pipeline)
            
            logger.info(f"🔍 Vector search trong '{collection_name}' trả về {len(results)} kết quả")
            return results
            
        except Exception as e:
            logger.error(f"❌ Lỗi vector search trong '{collection_name}': {e}")
            return []
    
    async def hybrid_search(
        self, 
        collection_name: str, 
        query_text: str,
        query_vector: List[float],
        text_fields: List[str] = ["content"],
        vector_field: str = "content_embedding",
        filter_query: Dict[str, Any] = None,
        limit: int = 10,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.5  # Giảm threshold default
    ) -> List[Dict[str, Any]]:
        """
        Thực hiện hybrid search (semantic + keyword) 
        
        Args:
            collection_name (str): Tên collection
            query_text (str): Query text cho keyword search
            query_vector (List[float]): Vector embedding cho semantic search
            text_fields (List[str]): Các fields để search text
            vector_field (str): Field chứa vector embedding
            filter_query (Dict): Filter query
            limit (int): Số lượng kết quả
            semantic_weight (float): Trọng số cho semantic score
            keyword_weight (float): Trọng số cho keyword score
            similarity_threshold (float): Ngưỡng similarity tối thiểu
            
        Returns:
            List[Dict]: Documents với combined scores
        """
        try:
            self._ensure_connected()
            
            # Prepare query words for keyword matching
            query_words = query_text.lower().split()
            
            pipeline = []
            
            # Stage 1: Match filter nếu có
            if filter_query:
                pipeline.append({"$match": filter_query})
            
            # Stage 2: Match documents có vector embedding
            pipeline.append({
                "$match": {
                    vector_field: {"$exists": True, "$ne": None}
                }
            })
            
            # Stage 3: Add computed scores
            pipeline.append({
                "$addFields": {
                    # Semantic similarity score (same as vector_search)
                    "semantic_score": {
                        "$let": {
                            "vars": {
                                "dotProduct": {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": f"${vector_field}"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {"$multiply": [
                                                    {"$arrayElemAt": [f"${vector_field}", "$$this"]},
                                                    {"$arrayElemAt": [query_vector, "$$this"]}
                                                ]}
                                            ]
                                        }
                                    }
                                },
                                "normA": {
                                    "$sqrt": {
                                        "$reduce": {
                                            "input": f"${vector_field}",
                                            "initialValue": 0,
                                            "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                        }
                                    }
                                },
                                "normB": {
                                    "$literal": (sum(x * x for x in query_vector) ** 0.5)
                                }
                            },
                            "in": {
                                "$cond": {
                                    "if": {"$and": [{"$gt": ["$$normA", 0]}, {"$gt": ["$$normB", 0]}]},
                                    "then": {"$divide": ["$$dotProduct", {"$multiply": ["$$normA", "$$normB"]}]},
                                    "else": 0
                                }
                            }
                        }
                    },
                    
                    # Keyword matching score
                    "keyword_score": {
                        "$let": {
                            "vars": {
                                "textContent": {
                                    "$toLower": {
                                        "$ifNull": [
                                            {"$getField": {"field": text_fields[0], "input": "$$ROOT"}},
                                            ""
                                        ]
                                    }
                                }
                            },
                            "in": {
                                "$divide": [
                                    {
                                        "$size": {
                                            "$filter": {
                                                "input": query_words,
                                                "cond": {
                                                    "$regexMatch": {
                                                        "input": "$$textContent",
                                                        "regex": {"$concat": [".*", "$$this", ".*"]},
                                                        "options": "i"
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    len(query_words) if query_words else 1
                                ]
                            }
                        }
                    }
                }
            })
            
            # Stage 4: Calculate final hybrid score
            pipeline.append({
                "$addFields": {
                    "final_score": {
                        "$add": [
                            {"$multiply": ["$semantic_score", semantic_weight]},
                            {"$multiply": ["$keyword_score", keyword_weight]}
                        ]
                    }
                }
            })
            
            # Stage 5: Filter by semantic similarity threshold  
            pipeline.append({
                "$match": {
                    "semantic_score": {"$gte": similarity_threshold}
                }
            })
            
            # Stage 6: Sort by final score descending
            pipeline.append({
                "$sort": {"final_score": -1}
            })
            
            # Stage 7: Limit results
            pipeline.append({
                "$limit": limit
            })
            
            # Execute aggregation
            results = await self.aggregate(collection_name, pipeline)
            
            # logger.info(f"🔍 Hybrid search trong '{collection_name}' trả về {len(results)} kết quả")
            return results
            
        except Exception as e:
            logger.error(f"❌ Lỗi hybrid search trong '{collection_name}': {e}")
            return []
    
    # ================== UTILITY METHODS ==================
    
    async def get_database_stats(self) -> Optional[Dict[str, Any]]:
        """
        Lấy thống kê database
        
        Returns:
            Optional[Dict]: Thống kê database
        """
        try:
            self._ensure_connected()
            
            stats = await self.database.command("dbStats")
            logger.info("📊 Lấy thống kê database thành công")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Lỗi lấy thống kê database: {e}")
            return None
    
    async def get_collection_stats(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thống kê collection
        
        Args:
            collection_name (str): Tên collection
            
        Returns:
            Optional[Dict]: Thống kê collection
        """
        try:
            self._ensure_connected()
            
            stats = await self.database.command("collStats", collection_name)
            logger.info(f"📊 Lấy thống kê collection '{collection_name}' thành công")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Lỗi lấy thống kê collection '{collection_name}': {e}")
            return None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()


# ================== SINGLETON INSTANCE ==================

# Tạo instance singleton để sử dụng trong toàn bộ ứng dụng
mongodb_manager = MongoDBManager()

# ================== CONVENIENCE FUNCTIONS ==================

async def init_mongodb(database_name: str = "mekongai_social") -> bool:
    """
    Khởi tạo kết nối MongoDB
    
    Args:
        database_name (str): Tên database
        
    Returns:
        bool: True nếu kết nối thành công
    """
    return await mongodb_manager.connect(database_name)

async def close_mongodb():
    """Đóng kết nối MongoDB"""
    await mongodb_manager.disconnect()

# Export các hàm chính để sử dụng dễ dang
__all__ = [
    'MongoDBManager',
    'mongodb_manager', 
    'init_mongodb',
    'close_mongodb'
]