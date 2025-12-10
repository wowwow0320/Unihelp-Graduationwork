# routers/chat_router.py

import logging
from fastapi import APIRouter, HTTPException
from schemas.chat_schema import ChatRequest, ChatResponse
from services.chat_service import chat_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def get_chat_response(request: ChatRequest):
    """
    사용자 질문에 대해 기본 설정된 컬렉션을 기반으로 답변을 반환합니다.
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
    
    # 질문의 크기를 로그로 출력합니다.
    question_size = len(request.question.encode('utf-8'))
    logger.info(f"수신된 질문 크기: {question_size / 1024:.2f}k")
    
    try:
        # ✨ [수정됨] 비동기 서비스 호출
        # chat_service.get_answer() -> await chat_service.get_answer()
        # 서비스가 작업을 완료할 때까지 기다리되, 서버(Event Loop)는 차단하지 않음
        answer = await chat_service.get_answer(request.question)
        return ChatResponse(answer=answer)
    except Exception as e:
        logger.error(f"답변 생성 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"답변 생성 중 오류 발생: {e}")