"""
Base Manager Class cho MongoDB Collections
Cung cấp các chức năng CRUD cơ bản cho tất cả collections
"""

import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from configs.environment import get_vietnam_now_naive
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError
from controllers.databases.mongodb.mongodb import MongoDBManager

logger = logging.getLogger(__name__)


class BaseManager:
    """Base class cho tất cả MongoDB collection managers"""

    def __init__(self, db_manager: MongoDBManager, collection_name: str):
        """
        Khởi tạo Base Manager

        Args:
            db_manager (MongoDBManager): MongoDB manager instance
            collection_name (str): Tên collection
        """
        self.db_manager = db_manager
        self.collection_name = collection_name
        self._collection = None

    @property
    def collection(self):
        """Lazy load collection"""
        if self._collection is None:
            self._collection = self.db_manager.database[self.collection_name]
        return self._collection

    def _add_timestamps(
        self, data: Dict[str, Any], is_update: bool = False
    ) -> Dict[str, Any]:
        """
        Thêm timestamp vào data

        Args:
            data: Dictionary data
            is_update: True nếu là update operation
        """
        now = get_vietnam_now_naive()
        if not is_update:
            data["create_at"] = now
        data["update_at"] = now
        return data

    def _serialize_object_id(self, obj: Any) -> Any:
        """Convert ObjectId thành string để serialize JSON"""
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {key: self._serialize_object_id(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_object_id(item) for item in obj]
        return obj

    async def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tạo document mới

        Args:
            data: Dictionary chứa data để tạo

        Returns:
            Dictionary chứa document đã tạo với _id
        """
        try:
            # Thêm timestamps
            data = self._add_timestamps(data)

            # Insert vào database
            result = await self.collection.insert_one(data)

            # Lấy document vừa tạo
            created_doc = await self.collection.find_one({"_id": result.inserted_id})

            logger.info(
                f"Created document in {self.collection_name} with ID: {result.inserted_id}"
            )
            return self._serialize_object_id(created_doc)

        except DuplicateKeyError as e:
            logger.error(f"Duplicate key error in {self.collection_name}: {str(e)}")
            raise ValueError(f"Duplicate key error: {str(e)}")
        except PyMongoError as e:
            logger.error(f"MongoDB error in {self.collection_name}: {str(e)}")
            raise Exception(f"Database error: {str(e)}")

    async def get_by_id(self, doc_id: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
        """
        Lấy document theo ID

        Args:
            doc_id: ID của document (có thể là ObjectId hoặc custom string ID)

        Returns:
            Dictionary chứa document hoặc None
        """
        try:
            # Nếu là string, kiểm tra xem có phải ObjectId hợp lệ không
            if isinstance(doc_id, str):
                # Kiểm tra xem string có phải là ObjectId hợp lệ (24 ký tự hex)
                if len(doc_id) == 24:
                    try:
                        doc_id = ObjectId(doc_id)
                    except:
                        # Nếu không convert được thành ObjectId, sử dụng string gốc
                        pass
                # Nếu không phải ObjectId format, sử dụng string gốc làm custom ID

            doc = await self.collection.find_one({"_id": doc_id})
            return self._serialize_object_id(doc) if doc else None

        except Exception as e:
            logger.error(
                f"Error getting document by ID in {self.collection_name}: {str(e)}"
            )
            return None

    async def get_all(
        self,
        filter_query: Dict[str, Any] = None,
        skip: int = 0,
        limit: int = 100,
        sort_by: str = "create_at",
        sort_order: int = -1,
    ) -> List[Dict[str, Any]]:
        """
        Lấy tất cả documents với filter

        Args:
            filter_query: MongoDB filter query
            skip: Số documents bỏ qua
            limit: Số documents tối đa trả về (None = không giới hạn)
            sort_by: Field để sort
            sort_order: 1 cho ascending, -1 cho descending

        Returns:
            List các documents
        """
        try:
            if filter_query is None:
                filter_query = {}

            cursor = (
                self.collection.find(filter_query)
                .skip(skip)
                .sort(sort_by, sort_order)
            )
            
            # ✅ FIX: Chỉ apply limit nếu limit > 0
            # Nếu limit <= 0 hoặc None → lấy HẾT (unlimited)
            if limit and limit > 0:
                cursor = cursor.limit(limit)
                docs = await cursor.to_list(length=limit)
            else:
                # Lấy tất cả documents (không giới hạn)
                docs = await cursor.to_list(length=None)

            return [self._serialize_object_id(doc) for doc in docs]

        except Exception as e:
            logger.error(f"Error getting documents in {self.collection_name}: {str(e)}")
            return []

    async def update_by_id(
        self, doc_id: Union[str, ObjectId], update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Cập nhật document theo ID

        Args:
            doc_id: ID của document
            update_data: Data để cập nhật

        Returns:
            Dictionary chứa document đã cập nhật
        """
        try:
            if isinstance(doc_id, str):
                doc_id = ObjectId(doc_id)

            # Thêm update timestamp
            update_data = self._add_timestamps(update_data, is_update=True)

            result = await self.collection.update_one(
                {"_id": doc_id}, {"$set": update_data}
            )

            if result.matched_count == 0:
                return None

            # Lấy document đã cập nhật
            updated_doc = await self.collection.find_one({"_id": doc_id})
            logger.info(f"Updated document in {self.collection_name} with ID: {doc_id}")

            return self._serialize_object_id(updated_doc)

        except Exception as e:
            logger.error(f"Error updating document in {self.collection_name}: {str(e)}")
            raise Exception(f"Update error: {str(e)}")

    async def delete_by_id(self, doc_id: Union[str, ObjectId]) -> bool:
        """
        Xóa document theo ID

        Args:
            doc_id: ID của document

        Returns:
            True nếu xóa thành công
        """
        try:
            if isinstance(doc_id, str):
                doc_id = ObjectId(doc_id)

            result = await self.collection.delete_one({"_id": doc_id})

            if result.deleted_count > 0:
                logger.info(
                    f"Deleted document in {self.collection_name} with ID: {doc_id}"
                )
                return True
            return False

        except Exception as e:
            logger.error(f"Error deleting document in {self.collection_name}: {str(e)}")
            return False

    async def copy_by_id(
        self, doc_id: Union[str, ObjectId], copy_data: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Copy document theo ID

        Args:
            doc_id: ID của document cần copy
            copy_data: Data để override khi copy

        Returns:
            Dictionary chứa document đã copy
        """
        try:
            # Lấy document gốc
            original_doc = await self.get_by_id(doc_id)
            if not original_doc:
                return None

            # Remove _id và timestamps
            new_doc = original_doc.copy()
            new_doc.pop("_id", None)
            new_doc.pop("create_at", None)
            new_doc.pop("update_at", None)

            # Apply copy_data nếu có
            if copy_data:
                new_doc.update(copy_data)

            # Tạo document mới
            return await self.create(new_doc)

        except Exception as e:
            logger.error(f"Error copying document in {self.collection_name}: {str(e)}")
            raise Exception(f"Copy error: {str(e)}")

    async def bulk_create(
        self, data_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Tạo nhiều documents cùng lúc

        Args:
            data_list: List các documents để tạo

        Returns:
            List các documents đã tạo
        """
        try:
            # Thêm timestamps cho tất cả
            processed_data = [self._add_timestamps(data.copy()) for data in data_list]

            result = await self.collection.insert_many(processed_data)

            # Lấy tất cả documents vừa tạo
            created_docs = await self.collection.find(
                {"_id": {"$in": result.inserted_ids}}
            ).to_list(length=len(result.inserted_ids))

            logger.info(
                f"Bulk created {len(created_docs)} documents in {self.collection_name}"
            )
            return [self._serialize_object_id(doc) for doc in created_docs]

        except Exception as e:
            logger.error(
                f"Error bulk creating documents in {self.collection_name}: {str(e)}"
            )
            raise Exception(f"Bulk create error: {str(e)}")

    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """
        Cập nhật nhiều documents cùng lúc

        Args:
            updates: List các update operations
            Format: [{"filter": {}, "update": {}}, ...]

        Returns:
            Số documents đã cập nhật
        """
        try:
            operations = []
            for update_op in updates:
                filter_query = update_op.get("filter", {})
                update_data = self._add_timestamps(
                    update_op.get("update", {}), is_update=True
                )

                operations.append(
                    {
                        "updateMany": {
                            "filter": filter_query,
                            "update": {"$set": update_data},
                        }
                    }
                )

            if not operations:
                return 0

            result = await self.collection.bulk_write(operations)
            modified_count = result.modified_count

            logger.info(
                f"Bulk updated {modified_count} documents in {self.collection_name}"
            )
            return modified_count

        except Exception as e:
            logger.error(
                f"Error bulk updating documents in {self.collection_name}: {str(e)}"
            )
            raise Exception(f"Bulk update error: {str(e)}")

    async def bulk_delete(self, filter_queries: List[Dict[str, Any]]) -> int:
        """
        Xóa nhiều documents cùng lúc

        Args:
            filter_queries: List các filter queries để xóa

        Returns:
            Số documents đã xóa
        """
        try:
            operations = []
            for filter_query in filter_queries:
                operations.append({"deleteMany": {"filter": filter_query}})

            if not operations:
                return 0

            result = await self.collection.bulk_write(operations)
            deleted_count = result.deleted_count

            logger.info(
                f"Bulk deleted {deleted_count} documents in {self.collection_name}"
            )
            return deleted_count

        except Exception as e:
            logger.error(
                f"Error bulk deleting documents in {self.collection_name}: {str(e)}"
            )
            raise Exception(f"Bulk delete error: {str(e)}")

    async def count(self, filter_query: Dict[str, Any] = None) -> int:
        """
        Đếm số documents

        Args:
            filter_query: MongoDB filter query

        Returns:
            Số documents
        """
        try:
            if filter_query is None:
                filter_query = {}

            count = await self.collection.count_documents(filter_query)
            return count

        except Exception as e:
            logger.error(
                f"Error counting documents in {self.collection_name}: {str(e)}"
            )
            return 0

    async def search(
        self, search_query: str, fields: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm text trong documents

        Args:
            search_query: Query string để tìm kiếm
            fields: List các fields để tìm kiếm

        Returns:
            List documents tìm được
        """
        try:
            if not fields:
                # Tìm kiếm text index nếu có
                pipeline = [
                    {"$match": {"$text": {"$search": search_query}}},
                    {"$sort": {"score": {"$meta": "textScore"}}},
                ]
            else:
                # Tìm kiếm regex trong các fields cụ thể
                or_conditions = []
                for field in fields:
                    or_conditions.append(
                        {field: {"$regex": search_query, "$options": "i"}}
                    )

                pipeline = [{"$match": {"$or": or_conditions}}]

            cursor = self.collection.aggregate(pipeline)
            docs = await cursor.to_list(length=100)

            return [self._serialize_object_id(doc) for doc in docs]

        except Exception as e:
            logger.error(
                f"Error searching documents in {self.collection_name}: {str(e)}"
            )
            return []
