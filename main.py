# main.py

from fastapi import FastAPI
from routers import chat_router, processing_router, ocr_router, crawling_router # 👈 crawling_router 임포트 추가

app = FastAPI(
    title="RAG Chatbot API",
    description="PDF 문서를 기반으로 질문에 답변하는 RAG 챗봇 API 및 크롤링 기능을 제공합니다.", # 설명 업데이트
    version="1.0.0"
)

# 라우터 등록
app.include_router(processing_router.router, prefix="/api/v1/processing", tags=["File Processing & DB Management"]) # 태그 이름 수정
app.include_router(chat_router.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(ocr_router.router, prefix="/api/v1/ocr", tags=["OCR Processing"]) # 태그 이름 수정
app.include_router(crawling_router.router, prefix="/api/v1/crawl", tags=["Crawling"]) # 👈 crawling_router 등록

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "RAG Chatbot API에 오신 것을 환영합니다. /docs 로 이동하여 API 문서를 확인하세요."}

# Uvicorn으로 앱 실행 (터미널에서 직접 실행 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
