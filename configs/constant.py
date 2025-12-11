import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ================================================
# SERVER
SERVER_ADDRESS = os.getenv("SERVER_ADDRESS", "http://localhost:1975")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ================================================
# CONFIGS
MAX_FILE_SIZE = 20 * 1024 * 1024
MAX_NUM_TOKEN = 70000

NODE_CHUNK_SIZE_TYPE_1 = 128
NODE_CHUNK_SIZE_TYPE_2 = 256
NODE_CHUNK_SIZE_TYPE_3 = 512
NODE_CHUNK_SIZE_TYPE_4 = 1024
NODE_CHUNK_SIZE_TYPE_5 = 1536
NODE_CHUNK_SIZE_TYPE_6 = 2048

# ================================================
# CHATBOT
CHATBOT_NAME = "BOT"

#
MODEL_CHATBOT_BASIC = "gpt-4.1"
MODEL_CHATBOT_REFERENCE = "gpt-4.1"
MODEL_CHATBOT_CHART = "gpt-4.1"
MODEL_CHATBOT_SUGGESTION = "gpt-4.1-mini"
MODEL_CHATBOT_CUSTOM_PROMPT = "gpt-4.1"
MODEL_PROVINCE_MERGER = "gpt-4.1"
MODEL_KAT = "gpt-4.1"
MODEL_SCHOOL = "gpt-4.1"
MODEL_SUMMARY = "gpt-4.1-mini"

K_CHATBOT_BASIC = 10
K_CHATBOT_REFERENCE = 10
K_CHATBOT_CHART = 10
K_CHATBOT_CUSTOM_PROMPT = 10
K_PROVINCE_MERGER = 5
K_KAT = 5
K_SCHOOL = 5

# ================================================
# PATH
DATA = "./resources/data"
DATA_USER = "./resources/data/user"
DATA_PUBLIC = "./resources/data/public"

DATA_HISTORY = "./resources/data/history"

DATA_TOKEN = "./resources/data/token"

DATA_CHART = "./resources/tmp/chart"
DATA_TMP = "./resources/tmp"

LOG = "./resources/logs"

ALL_DATA_UPLOAD = "./resources/data/all_qdrant_collections.json"

# ================================================
# QDRANT
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = os.getenv("QDRANT_PORT")
QDRANT_SERVER = os.getenv("QDRANT_SERVER")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# MYSQL
MYSQL_DB_HOST = os.getenv("MYSQL_DB_HOST")
MYSQL_DB_NAME = os.getenv("MYSQL_DB_NAME")
MYSQL_DB_USER = os.getenv("MYSQL_DB_USER")
MYSQL_DB_PASSWORD = os.getenv("MYSQL_DB_PASSWORD")

# MONGODB
MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
MONGODB_PORT = os.getenv("MONGODB_PORT", "27017")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "mekongai_social")
MONGODB_USERNAME = os.getenv("MONGODB_USERNAME", "")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD", "")
MONGODB_URI = os.getenv("MONGODB_CONNECTION", f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/{MONGODB_DATABASE}")

# ================================================
# VLLM
VLLM_URL = os.getenv("VLLM_URL")
VLLM_TOKEN = os.getenv("VLLM_TOKEN")

# ================================================
# AWS
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION")

# ================================================
# SUPERADMIN & WHITE LABEL CONFIGURATION
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "admin@mekongai.com")
SUPERADMIN_PASSWORD = os.getenv("SUPERADMIN_PASSWORD", "MekongAI@2025!Secure")
IS_WHITE_LABEL_SYSTEM = os.getenv("IS_WHITE_LABEL_SYSTEM", "false").lower() == "true"
WHITE_LABEL_API_KEY = os.getenv("WHITE_LABEL_API_KEY", "")  # API Key của White Label này để gửi về MekongAI
MEKONGAI_SUPERADMIN_API_URL = os.getenv("MEKONGAI_SUPERADMIN_API_URL", "https://api.mekongai.com/super-admin")
WHITE_LABEL_PARTNER_ID = os.getenv("WHITE_LABEL_PARTNER_ID", "")  # ID của đối tác White Label trong hệ thống MekongAI
WHITE_LABEL_COMPANY_NAME = os.getenv("WHITE_LABEL_COMPANY_NAME", "MekongAI")
WHITE_LABEL_DOMAIN = os.getenv("WHITE_LABEL_DOMAIN", "mekongai.com")

# ================================================
# EMAIL
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
JWT_REFRESH_KEY = os.getenv("JWT_REFRESH_KEY") or os.getenv("JWT_REFRESH_SECRET") or secrets.token_urlsafe(32)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "hueaitest@gmail.com"
SMTP_PASSWORD = "udsd nwgx cwjg drbw"
VERIFICATION_TIMEOUT = 5 * 60

# JWT login:
JWT = os.getenv("JWT", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
ACCESS_REFRESH_TOKEN_EXPIRE_DAY = int(os.getenv("ACCESS_REFRESH_TOKEN_EXPIRE_DAY", os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "365")))

# PARENT ID
PARENT_ORG_ID = os.getenv("PARENT_ORG_ID", "")

# ================================================
# PAYMENT GATEWAY - PayOS
PAYOS_CLIENT_ID = os.getenv("PAYOS_CLIENT_ID")
PAYOS_API_KEY = os.getenv("PAYOS_API_KEY") 
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY")

# ================================================
# FACEBOOK
CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN")
REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")

# ================================================
# COST CALCULATION
COST_TOKEN = 1000  # 1000 tokens = 1 VND

