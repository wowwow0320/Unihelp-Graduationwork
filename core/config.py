# core/config.py

from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    # AI 모델 설정
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "OPENAI").upper()

    # API 키
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

    # ChromaDB 경로
    DB_PATH = "./chroma_db"
    DEFAULT_DB_COLLECTION_NAME = "2025-2"

    # 토크나이저 병렬 처리 비활성화
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    def __init__(self):
        if self.DEFAULT_MODEL == "OPENAI" and not self.OPENAI_API_KEY:
            raise ValueError("❌ OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")
        if not self.LLAMA_CLOUD_API_KEY:
            raise ValueError("❌ LLAMA_CLOUD_API_KEY가 .env 파일에 설정되지 않았습니다.")

settings = Settings()