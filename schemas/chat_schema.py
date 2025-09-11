# /schemas/chat_schema.py

from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str

class FullProcessingResponse(BaseModel):
    message: str
    source_file: str
    docx_file: str
    markdown_file: str
    html_file: str
    rag_text_file: str

class CollectionListResponse(BaseModel):
    collections: List[str]

# 👇 [신규 추가] OCR 분석 결과를 위한 데이터 모델
# 이 부분이 파일에 누락되어 오류가 발생했습니다.
class CreditInfo(BaseModel):
    이수기준: Optional[int] = None
    취득학점: Optional[int] = None

class CreditAnalysisResponse(BaseModel):
    교양_필수: CreditInfo = Field(..., alias="교양 필수")
    기초전공: CreditInfo
    단일전공자_최소전공이수학점: CreditInfo = Field(..., alias="단일전공자 최소전공이수학점")
    복수_부_연계전공_기초전공: CreditInfo = Field(..., alias="복수,부,연계전공 기초전공")
    복수_부_연계전공_최소전공이수학점: CreditInfo = Field(..., alias="복수,부,연계전공 최소전공이수학점")
    졸업학점: Optional[int] = None
    취득학점: Optional[int] = None
    편입인정학점: Optional[int] = None