# main.py

from fastapi import FastAPI
from routers import chat_router, processing_router
from routers import ocr_router

app = FastAPI(
    title="RAG Chatbot API",
    description="PDF 문서를 기반으로 질문에 답변하는 RAG 챗봇 API입니다.",
    version="1.0.0"
)

# 라우터 등록
app.include_router(processing_router.router, prefix="/api/v1/processing", tags=["File Processing"])
app.include_router(chat_router.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(ocr_router.router, prefix="/api", tags=["OCR"])

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "RAG Chatbot API에 오신 것을 환영합니다. /docs 로 이동하여 API 문서를 확인하세요."}

# Uvicorn으로 앱 실행 (터미널에서 직접 실행 시)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)