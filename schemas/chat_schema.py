# schemas/chat_schema.py

from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str

class ProcessingResponse(BaseModel):
    message: str
    markdown_file: str
    rag_text_file: str
    collection_name: str
    
class ConversionResponse(BaseModel):
    message: str
    source_file: str
    output_file: str

# 4단계 변환 결과를 모두 포함하는 최종 응답 모델
class FullProcessingResponse(BaseModel):
    message: str
    source_file: str
    docx_file: str
    markdown_file: str
    html_file: str
    rag_text_file: str