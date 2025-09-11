# /routers/ocr_router.py

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from schemas.chat_schema import CreditAnalysisResponse
from services.ocr_processing_service import ocr_service

router = APIRouter()

@router.post("/ocr/extract-credits", response_model=CreditAnalysisResponse)
async def extract_credit_info_from_pdf(file: UploadFile = File(...)):
    """
    PDF 성적표 파일을 OCR로 분석하고 JSON을 반환합니다.
    작업 완료 후 업로드된 원본 PDF 파일은 자동으로 삭제됩니다.
    """
    # 업로드된 파일을 임시 저장
    file_path = ocr_service.upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # try...finally 구문을 사용하여 파일 처리를 보장합니다.
    try:
        # OCR 서비스 실행
        credit_data = ocr_service.process_pdf_for_credits(str(file_path))
        
        # 성공 시 결과 반환
        return credit_data
    except ValueError as e:
        # 키워드나 테이블을 못 찾은 경우 404 에러를 반환
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # 그 외 서버 내부 오류 발생 시 500 에러를 반환
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {e}")
    finally:
        # try 블록의 성공/실패 여부와 관계없이 항상 이 부분이 실행됩니다.
        # 파일이 존재하는지 확인하고 안전하게 삭제합니다.
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 임시 OCR 파일 삭제 완료: {file_path}")