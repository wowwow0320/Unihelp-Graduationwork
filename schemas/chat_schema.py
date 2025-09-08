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