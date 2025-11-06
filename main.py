# /main.py

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import uvicorn

# [중요] 1. 기존 라우터들 임포트
from routers import chat_router, processing_router, ocr_router, crawling_router

# [중요] 2. 스케줄링할 함수 임포트
from routers.crawling_router import run_crawl_and_send_logic

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [중요] 3. 스케줄러 인스턴스 생성
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job(
    CronTrigger(
        hour="10,14,17,23",
        minute="50",
        timezone="Asia/Seoul" # 한국 시간 기준
    ),
    id="crawl_yongin_notices_job",
    name="용인대 공지사항 크롤링 및 전송"
)
async def scheduled_crawl_job():
    """
    스케줄러에 의해 주기적으로 실행될 작업.
    """
    logger.info("===== ⏰ 스케줄된 크롤링 작업 시작 =====")
    try:
        result = await run_crawl_and_send_logic() # 분리한 크롤링 함수 호출
        logger.info(f"===== ✅ 스케줄된 크롤링 작업 완료: {result.message} =====")
    except Exception as e:
        logger.error(f"===== ❌ 스케줄된 크롤링 작업 중 심각한 오류 발생: {e} =====", exc_info=True)


# [중요] 4. FastAPI 앱 생명주기(lifespan) 이벤트 정의
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시
    logger.info("FastAPI 앱 시작... 스케줄러를 시작합니다.")
    scheduler.start()
    yield
    # 앱 종료 시
    logger.info("FastAPI 앱 종료... 스케줄러를 종료합니다.")
    scheduler.shutdown()

# [중요] 5. FastAPI 앱 생성 시 'lifespan' 적용
app = FastAPI(
    title="RAG Chatbot API",
    description="PDF 문서를 기반으로 질문에 답변하는 RAG 챗봇 API 및 크롤링 기능을 제공합니다.",
    version="1.0.0",
    lifespan=lifespan  # 👈 스케줄러 생명주기 적용
)

# [중요] 6. 기존 라우터들 모두 등록
app.include_router(processing_router.router, prefix="/api/v1/processing", tags=["File Processing & DB Management"])
app.include_router(chat_router.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(ocr_router.router, prefix="/api/v1/ocr", tags=["OCR Processing"])
app.include_router(crawling_router.router, prefix="/api/v1/crawl", tags=["Crawling"]) # 👈 크롤링 라우터 prefix 확인하세요

@app.get("/", tags=["Root"])
async def read_root():
    """
    루트 엔드포인트. API 서버가 실행 중인지 확인합니다.
    """
    return {"message": "RAG Chatbot API (with Crawling Scheduler) is running."}

# Uvicorn으로 앱 실행 (터미널에서 직접 실행 시)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)