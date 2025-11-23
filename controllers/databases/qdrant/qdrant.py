import json
import os
import psutil
import concurrent.futures
from typing import List, Optional
from qdrant_client import QdrantClient, models
from langchain_qdrant import Qdrant
from langchain.schema import Document

from configs import constant, environment


def create_optimized_collection(client: QdrantClient, collection_name: str, vector_size: int = 1536):
    """Tạo collection với cấu hình tối ưu"""
    if client.collection_exists(collection_name):
        return

    num_segments = max(1, psutil.cpu_count(logical=False) // 2)  # Giảm số segment để tối ưu
    
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
            on_disk=False,  # Giữ trong RAM để tăng tốc
        ),
        # Bỏ quantization để tăng tốc độ insert
        hnsw_config=models.HnswConfigDiff(
            m=16,           # Giảm m để tăng tốc insert
            ef_construct=100,  # Giảm ef_construct để tăng tốc
            full_scan_threshold=10000,  # Tăng threshold
            max_indexing_threads=0,  # Sử dụng tất cả threads có sẵn
        ),
        optimizers_config=models.OptimizersConfigDiff(
            default_segment_number=num_segments,
            max_segment_size=None,  # Không giới hạn
            memmap_threshold=None,  # Không sử dụng memmap
            indexing_threshold=20000,  # Tăng threshold trước khi index
            flush_interval_sec=5,  # Giảm thời gian flush
            max_optimization_threads=None,  # Sử dụng tất cả threads
        )
    )


def batch_embed_documents(docs: List[Document], batch_size: int = 100) -> List[List[float]]:
    """Embed documents theo batch để tối ưu tốc độ"""
    embeddings = []
    texts = [doc.page_content for doc in docs]
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        try:
            batch_embeddings = environment.embeddings_model.embed_documents(batch_texts)
            embeddings.extend(batch_embeddings)
        except Exception as e:
            print(f"Error embedding batch {i//batch_size + 1}: {e}")
            # Thử embed từng document một nếu batch fail
            for text in batch_texts:
                try:
                    single_embedding = environment.embeddings_model.embed_documents([text])
                    embeddings.extend(single_embedding)
                except Exception:
                    embeddings.append([0.0] * 1536)  # Vector zero nếu fail
    
    return embeddings


def save_vector_db_as_ids_optimized(docs: List[Document], collection_name: str, point_ids: List[str]) -> Optional[Qdrant]:
    """
    Lưu documents vào Qdrant với tốc độ tối ưu
    """
    if len(docs) != len(point_ids):
        raise ValueError("Số lượng docs và point_ids không khớp!")

    if not docs or not point_ids:
        return None

    try:
        # Khởi tạo client
        client = QdrantClient(
            url=constant.QDRANT_SERVER, 
            api_key=constant.QDRANT_API_KEY,
            timeout=60,  # Tăng timeout
            prefer_grpc=True,  # Sử dụng gRPC để tăng tốc
        )
        
        # Tạo collection tối ưu
        create_optimized_collection(client, collection_name)
        
        # Xác định batch size dựa trên số lượng docs
        total_docs = len(docs)
        if total_docs <= 100:
            batch_size = total_docs
        elif total_docs <= 1000:
            batch_size = 100
        else:
            batch_size = 200
        
        # Embed tất cả documents một lần
        print(f"Embedding {total_docs} documents...")
        embeddings = batch_embed_documents(docs, batch_size=50)
        
        # Tạo points
        points = [
            models.PointStruct(
                id=point_id,
                vector=embedding,
                payload={"content": doc.page_content, "metadata": doc.metadata}
            )
            for point_id, embedding, doc in zip(point_ids, embeddings, docs)
        ]
        
        # Lưu theo batch
        print(f"Saving {len(points)} points to Qdrant...")
        success_count = 0
        
        for i in range(0, len(points), batch_size):
            batch_points = points[i:i + batch_size]
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    client.upsert(
                        collection_name=collection_name,
                        points=batch_points,
                        wait=True  # Chờ xác nhận
                    )
                    success_count += len(batch_points)
                    print(f"Saved batch {i//batch_size + 1}/{(len(points)-1)//batch_size + 1} ({success_count}/{len(points)} points)")
                    break
                    
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"Retry {retry_count} for batch {i//batch_size + 1}: {e}")
                        # Giảm batch size nếu fail
                        if len(batch_points) > 1:
                            smaller_batch_size = len(batch_points) // 2
                            for j in range(0, len(batch_points), smaller_batch_size):
                                small_batch = batch_points[j:j + smaller_batch_size]
                                try:
                                    client.upsert(
                                        collection_name=collection_name,
                                        points=small_batch,
                                        wait=True
                                    )
                                    success_count += len(small_batch)
                                except Exception:
                                    print(f"Failed to save small batch at index {j}")
                            break
                    else:
                        print(f"Failed to save batch {i//batch_size + 1} after {max_retries} retries")
        
        print(f"Successfully saved {success_count}/{len(points)} points")
        
        # Trả về Qdrant client
        return Qdrant.from_existing_collection(
            embedding=environment.embeddings_model,
            collection_name=collection_name,
            url=constant.QDRANT_SERVER,
            api_key=constant.QDRANT_API_KEY,
            prefer_grpc=True,
        )
        
    except Exception as e:
        print(f"Error in save_vector_db_as_ids_optimized: {e}")
        return None


def save_vector_db_as_ids_parallel(docs: List[Document], collection_name: str, point_ids: List[str], max_workers: int = 4) -> Optional[Qdrant]:
    """
    Lưu documents vào Qdrant với xử lý song song
    """
    if len(docs) != len(point_ids):
        raise ValueError("Số lượng docs và point_ids không khớp!")

    if not docs or not point_ids:
        return None

    try:
        # Khởi tạo client
        client = QdrantClient(
            url=constant.QDRANT_SERVER, 
            api_key=constant.QDRANT_API_KEY,
            timeout=60,
            prefer_grpc=True,
        )
        
        # Tạo collection
        create_optimized_collection(client, collection_name)
        
        # Embed documents
        print(f"Embedding {len(docs)} documents...")
        embeddings = batch_embed_documents(docs, batch_size=50)
        
        # Chia thành chunks cho xử lý song song
        chunk_size = max(10, len(docs) // max_workers)
        chunks = []
        
        for i in range(0, len(docs), chunk_size):
            chunk_docs = docs[i:i + chunk_size]
            chunk_ids = point_ids[i:i + chunk_size]
            chunk_embeddings = embeddings[i:i + chunk_size]
            chunks.append((chunk_docs, chunk_ids, chunk_embeddings))
        
        def save_chunk(chunk_data):
            chunk_docs, chunk_ids, chunk_embeddings = chunk_data
            points = [
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={"content": doc.page_content, "metadata": doc.metadata}
                )
                for point_id, embedding, doc in zip(chunk_ids, chunk_embeddings, chunk_docs)
            ]
            
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                return len(points)
            except Exception as e:
                print(f"Error saving chunk: {e}")
                return 0
        
        # Xử lý song song
        total_saved = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(save_chunk, chunk) for chunk in chunks]
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                saved_count = future.result()
                total_saved += saved_count
                print(f"Completed chunk {i+1}/{len(chunks)}: saved {saved_count} points")
        
        print(f"Total saved: {total_saved}/{len(docs)} points")
        
        return Qdrant.from_existing_collection(
            embedding=environment.embeddings_model,
            collection_name=collection_name,
            url=constant.QDRANT_SERVER,
            api_key=constant.QDRANT_API_KEY,
            prefer_grpc=True,
        )
        
    except Exception as e:
        print(f"Error in save_vector_db_as_ids_parallel: {e}")
        return None


# Thay thế function cũ bằng function tối ưu
def save_vector_db_as_ids(docs: List[Document], collection_name: str, point_ids: List[str]) -> Optional[Qdrant]:
    """
    Wrapper function tự động chọn phương pháp tối ưu nhất
    """
    if len(docs) <= 100:
        # Với ít documents, dùng phương pháp đơn giản
        return save_vector_db_as_ids_optimized(docs, collection_name, point_ids)
    else:
        # Với nhiều documents, dùng phương pháp song song
        return save_vector_db_as_ids_parallel(docs, collection_name, point_ids)


def save_vector_db(docs, collection_names):
    qdrant_docs = Qdrant.from_documents(
        documents=docs,
        embedding=environment.embeddings_model,
        url=constant.QDRANT_SERVER,
        prefer_grpc=False,
        collection_name=collection_names,
        api_key=constant.QDRANT_API_KEY,
    )
    return qdrant_docs


def load_vector_db(collection_names):
    try:
        client = Qdrant.from_existing_collection(
            embedding=environment.embeddings_model,
            collection_name=collection_names,
            url=constant.QDRANT_SERVER,
            api_key=constant.QDRANT_API_KEY,
        )
        return client
    except Exception:
        a = "None"
        return a


def similarity_search_qdrant_data(db, query, k=3):
    # Cấu hình tham số tìm kiếm
    search_params = models.SearchParams(
        hnsw_ef=512,  # Tăng số lượng neighbor để cải thiện độ chính xác
        quantization=models.QuantizationSearchParams(
            rescore=True  # Bật rescoring để tinh chỉnh kết quả
        )
    )

    docs = db.similarity_search(query=query, k=k, search_params=search_params)
    return docs


def similarity_search_qdrant_data_with_score(db, query, k=3):
    # Cấu hình tham số tìm kiếm
    search_params = models.SearchParams(
        hnsw_ef=512,  # Tăng số lượng neighbor để cải thiện độ chính xác
        quantization=models.QuantizationSearchParams(
            rescore=True  # Bật rescoring để tinh chỉnh kết quả
        )
    )

    docs = db.similarity_search_with_score(query=query, k=k, search_params=search_params)
    return docs


def max_marginal_relevance_search_qdrant_data(db, query, k=3, fetch_k=3):
    docs = db.max_marginal_relevance_search(query=query, k=k, fetch_k=fetch_k)
    return docs


def get_point_from_ids(db, collection_name, point_ids):
    id = db.client.retrieve(collection_name=collection_name, ids=point_ids)
    return id


def as_retriever(db):
    db.as_retriever(
        search_kwargs={"k": 20, "score_threshold": 0.5},
        search_type="similarity_score_threshold",
    )


def save_list_nodes_qdrant(node_name, file_name):
    chatbot_name = constant.CHATBOT_NAME
    _path = constant.DATA_USER

    path = _path + "/" + chatbot_name
    json_file_path = f"{path}/list_nodes_qdrant.json"

    # Tạo thư mục nếu chưa tồn tại
    os.makedirs(os.path.dirname(json_file_path), exist_ok=True)

    # Đọc dữ liệu hiện có từ file JSON
    if os.path.exists(json_file_path):
        with open(json_file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    else:
        data = []

    # Kiểm tra nếu đã có node_name trong danh sách, thì tăng count lên 1, nếu không thì thêm mới
    for item in data:
        if item["node_name"] == node_name:
            item["count"] = item.get("count", 0) + 1  # Nếu có, tăng count lên 1
            break
    else:
        # Nếu không có node_name, thêm mới thông tin vào danh sách
        data.append({"node_name": node_name, "file_name": file_name, "count": 1})

    # Ghi lại dữ liệu vào file JSON
    with open(json_file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    return


def filter_node_names(keyword):
    chatbot_name = constant.CHATBOT_NAME
    _path = constant.DATA_USER

    path = _path + "/" + chatbot_name
    json_file_path = f"{path}/list_nodes_qdrant.json"

    # Mở file JSON và đọc dữ liệu
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Tạo một danh sách để chứa node_name có keyword
    filtered_node_names = []

    # Nếu keyword là "ALL", trả về tất cả các node_name
    if keyword == "ALL":
        return [item.get("node_name", "") for item in data]

    # Lọc tất cả các node_name khớp chính xác với keyword
    for item in data:
        node_name = item.get("node_name", "")
        # Kiểm tra nếu keyword khớp chính xác một phần trong node_name
        if keyword in node_name.split("_"):
            filtered_node_names.append(node_name)

    return filtered_node_names

