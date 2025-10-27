# /main.py (또는 FastAPI 앱을 생성하는 메인 파일)

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import uvicorn # uvicorn 실행용 (선택 사항)

# [중요] 1. 라우터 및 스케줄링할 함수 임포트
from routers.crawling_router import router as crawling_router
from routers.crawling_router import run_crawl_and_send_logic # 👈 2. 분리한 함수 임포트

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [중요] 3. 스케줄러 인스턴스 생성
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job(
    CronTrigger(
        hour="8,14,18,23",  # 👈 요청한 시간: 오전 8시, 14시, 18시, 23시
        minute="0",
        timezone="Asia/Seoul" # 👈 한국 시간 기준
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
        result = await run_crawl_and_send_logic() # 👈 4. 분리한 함수 직접 호출
        logger.info(f"===== ✅ 스케줄된 크롤링 작업 완료: {result.message} =====")
    except Exception as e:
        logger.error(f"===== ❌ 스케줄된 크롤링 작업 중 심각한 오류 발생: {e} =====", exc_info=True)

# [중요] 5. FastAPI 앱 생명주기(lifespan) 이벤트를 사용하여 스케줄러 시작/종료
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시
    logger.info("FastAPI 앱 시작... 스케줄러를 시작합니다.")
    scheduler.start()
    yield
    # 앱 종료 시
    logger.info("FastAPI 앱 종료... 스케줄러를 종료합니다.")
    scheduler.shutdown()

# FastAPI 앱 인스턴스 생성 (lifespan 적용)
app = FastAPI(lifespan=lifespan)

# 라우터 포함
app.include_router(crawling_router, prefix="/api") # 라우터 경로 예시

@app.get("/")
def read_root():
    return {"message": "크롤러 API 서버가 실행 중입니다."}

# 서버 실행 (예시)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)