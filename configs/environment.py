from dotenv import load_dotenv
import pytz
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings 
from mem0 import Memory

from configs import constant

load_dotenv()

# ================================================
# EMBEDDINGS

# OpenAI Embeddings với cấu hình đúng
# embeddings_model = OpenAIEmbeddings(
#     model="text-embedding-3-small",
#     openai_api_key=os.getenv("OPENAI_API_KEY"),
#     openai_api_base="https://api.openai.com/v1"
# )

# Local Embeddings for Text
model_name = "Qwen/Qwen3-Embedding-0.6B"
model_kwargs = {"device": "cpu"}
encode_kwargs = {"normalize_embeddings": True}
embeddings_model = HuggingFaceEmbeddings(
    model_name=model_name, model_kwargs=model_kwargs, encode_kwargs=encode_kwargs
)

# Image Embeddings using SigLIP (better than CLIP)
# Dimension: 1152 for siglip-large
from transformers import AutoProcessor, AutoModel
import torch

image_model_name = "google/siglip-large-patch16-384"  # 1152 dimensions

# Lazy init to avoid heavy downloads/missing optional deps at import time
_image_model = None
_image_processor = None

def _ensure_image_model_loaded():
    global _image_model, _image_processor
    if _image_model is not None and _image_processor is not None:
        return
    try:
        _image_processor = AutoProcessor.from_pretrained(image_model_name)
        _image_model = AutoModel.from_pretrained(image_model_name)
        _image_model.eval()  # Set to evaluation mode
    except ImportError as e:
        # SigLIP tokenizer requires SentencePiece
        raise ImportError(
            "SigLIP requires the SentencePiece library. Install it with 'pip install sentencepiece' "
            "and restart the app."
        ) from e
    except Exception:
        # Re-raise unexpected issues (e.g., connectivity, missing model)
        raise


# ================================================
# MEMORY
def _create_memory_instance() -> Memory:
    """Create a Mem0 Memory instance with a safe Qdrant config.

    - If `QDRANT_HOST` and `QDRANT_PORT` are provided, connects to that server.
    - Otherwise, uses a local on-disk path under `resources/tmp` to avoid
      conflicting with the default `/tmp/qdrant` lock on Windows.
    """
    vs_config = {}

    host = constant.QDRANT_HOST
    port = constant.QDRANT_PORT

    if host and port:
        vs_config.update({
            "host": host,
            "port": int(port),
        })
    else:
        # Fallback to local persistent path to avoid /tmp lock conflicts
        base_tmp = constant.DATA_TMP if hasattr(constant, "DATA_TMP") else "./resources/tmp"
        local_path = os.path.join(base_tmp, "qdrant_mem0")
        os.makedirs(local_path, exist_ok=True)
        vs_config.update({
            "path": local_path,
            "on_disk": True,  # prevent Mem0 from deleting the dir if it exists
        })

    cfg = {
        "vector_store": {
            "provider": "qdrant",
            "config": vs_config,
        }
    }
    return Memory.from_config(cfg)


# Initialize memory with safe configuration
_enable_mem0 = os.getenv("ENABLE_MEM0", "false").lower() == "true"
try:
    memory = _create_memory_instance() if _enable_mem0 else None
except Exception:
    memory = None

# ================================================
vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

def get_vietnam_now():
    """
    Lấy thời gian hiện tại theo múi giờ Việt Nam
    
    Returns:
        datetime: Thời gian hiện tại ở Việt Nam (timezone-aware)
    """
    from datetime import datetime
    return datetime.now(vietnam_tz)

def get_vietnam_now_naive():
    """
    Lấy thời gian hiện tại theo múi giờ Việt Nam (naive datetime - không có timezone info)
    Sử dụng hàm này để thay thế datetime.utcnow() trong toàn bộ project
    
    Returns:
        datetime: Thời gian hiện tại ở Việt Nam (naive datetime)
    """
    from datetime import datetime
    return datetime.now(vietnam_tz).replace(tzinfo=None)

# ================================================
# LLM
llm = ChatOpenAI(
    model="o4-mini", 
    temperature=1,
    streaming=False,
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    openai_api_base="https://api.openai.com/v1"
)

# ================================================
# FUNCTIONS
def get_llm():
    return llm


def get_embedding():
    return embeddings_model


def get_query_embedding(query_text: str):
    """
    Tạo embedding cho query text để vector search
    
    Args:
        query_text (str): Text cần tạo embedding
        
    Returns:
        List[float]: Vector embedding của query
    """
    return embeddings_model.embed_query(query_text)


def get_image_embedding_model():
    """
    Lấy image embedding model và processor
    
    Returns:
        Tuple[AutoModel, AutoProcessor]: Model và processor cho image embedding
    """
    _ensure_image_model_loaded()
    return _image_model, _image_processor

