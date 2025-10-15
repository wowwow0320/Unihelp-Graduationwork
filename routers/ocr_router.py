# /routers/ocr_router.py

import shutil
import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from schemas.chat_schema import CreditAnalysisResponse
from services.ocr_processing_service import ocr_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/extract-credits", response_model=CreditAnalysisResponse)
async def extract_credit_info_from_pdf(file: UploadFile = File(...)):
    """
    PDF 성적표 파일을 OCR로 분석하고 JSON을 반환합니다.
    작업 완료 후 업로드된 원본 PDF 파일은 자동으로 삭제됩니다.
    """
    # ✨ 추가된 부분: 업로드된 파일의 크기를 가져옵니다.
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    logger.info(f"OCR 요청 수신: {file.filename} (크기: {file_size / 1024:.2f}k)")

    # 업로드된 파일을 임시 저장
    file_path = ocr_service.upload_dir / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # OCR 서비스 실행
        credit_data = ocr_service.process_pdf_for_credits(str(file_path))
        
        # 성공 시 결과 반환
        return credit_data
    except ValueError as e:
        # 키워드나 테이블을 못 찾은 경우 404 에러를 반환
        logger.warning(f"OCR 처리 중 값 오류: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 그 외 서버 내부 오류 발생 시 500 에러를 반환
        logger.error(f"파일 처리 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {e}")
    finally:
        # try 블록의 성공/실패 여부와 관계없이 항상 이 부분이 실행됩니다.
        # 파일이 존재하는지 확인하고 안전하게 삭제합니다.
        if file_path.exists():
            file_path.unlink()
            logger.info(f"✅ 임시 OCR 파일 삭제 완료: {file_path}")
