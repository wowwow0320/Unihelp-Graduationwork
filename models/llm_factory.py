# models/llm_factory.py

from core.config import settings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

def get_llm():
    """설정에 맞는 LLM 클라이언트를 반환합니다."""
    if settings.DEFAULT_MODEL == "OPENAI":
        return ChatOpenAI(temperature=0.1, model="gpt-4.1")
    else:
        raise ValueError(f"Unsupported LLM model: {settings.DEFAULT_MODEL}")

def get_embedding_model():
    """설정에 맞는 임베딩 모델 클라이언트를 반환합니다."""
    if settings.DEFAULT_MODEL == "OPENAI":
        return OpenAIEmbeddings(model="text-embedding-3-small")
    else:
        raise ValueError(f"Unsupported Embedding model: {settings.DEFAULT_MODEL}")

# 전역적으로 사용할 모델 인스턴스 생성
llm = get_llm()
embedding_model = get_embedding_model()