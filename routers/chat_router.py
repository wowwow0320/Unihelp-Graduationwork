# routers/chat_router.py

from fastapi import APIRouter, HTTPException
from schemas.chat_schema import ChatRequest, ChatResponse
from services.chat_service import chat_service

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def get_chat_response(request: ChatRequest):
    """
    사용자 질문에 대해 기본 설정된 컬렉션을 기반으로 답변을 반환합니다.
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")
    
    # ✨ 변경된 부분: collection_name 관련 확인 로직을 제거합니다.
    
    try:
        # ✨ 변경된 부분: chat_service.get_answer 호출 시 question만 전달합니다.
        answer = chat_service.get_answer(request.question)
        return ChatResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"답변 생성 중 오류 발생: {e}")