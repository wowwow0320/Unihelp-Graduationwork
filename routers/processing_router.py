# routers/processing_router.py

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
# 👇 [수정] 새로 추가한 CollectionListResponse를 가져옵니다.
from schemas.chat_schema import FullProcessingResponse, CollectionListResponse
from services.file_processing_service import FileProcessorService
from services.vector_store_service import vector_store_service

router = APIRouter()

file_processor = FileProcessorService()

# --- 파일 처리부터 벡터 DB 구축까지 한 번에 실행하는 최종 API ---
@router.post("/process-pdf-full-and-build-db", response_model=FullProcessingResponse)
async def process_pdf_full_and_build_db(
    file: UploadFile = File(...),
    collection_name: str = Form(...)
):
    """
    PDF 파일을 업로드하여 모든 형식(DOCX, MD, HTML, TXT)으로 변환하고,
    최종 결과물로 벡터 DB까지 구축합니다.
    """
    if not collection_name.strip():
        raise HTTPException(status_code=400, detail="collection_name을 반드시 입력해야 합니다.")

    # 🔽 [수정] 파일명을 고유화하는 로직을 제거하고 원본 파일명을 사용합니다.
    file_path = file_processor.upload_dir / file.filename
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # 1. 4단계 파일 처리 파이프라인 실행 (DOCX, MD, HTML, TXT 생성)
        docx_path, markdown_path, html_path, rag_text_path = await file_processor.process_full_pipeline(
            pdf_path=str(file_path)
        )
        
        # 2. 생성된 파일들로 벡터 DB 구축
        print(f"🔧 벡터 DB 구축 시작: 컬렉션='{collection_name}'")
        vector_store_service.build_from_files(
            md_path=markdown_path,
            txt_path=rag_text_path,
            collection_name=collection_name
        )
        
        # 3. 모든 작업 완료 후 최종 결과 반환
        return FullProcessingResponse(
            message=f"PDF 파일 처리 및 '{collection_name}' 벡터 DB 구축이 모두 완료되었습니다.",
            source_file=file.filename,
            docx_file=docx_path,
            markdown_file=markdown_path,
            html_file=html_path,
            rag_text_file=rag_text_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# 👇 [신규 추가] 저장된 컬렉션 목록을 조회하는 API
@router.get("/collections", response_model=CollectionListResponse)
async def list_all_collections():
    """
    현재 Chroma DB에 저장되어 있는 모든 컬렉션의 목록을 조회합니다.
    """
    try:
        collection_names = vector_store_service.list_collections()
        return CollectionListResponse(collections=collection_names)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컬렉션 조회 중 오류 발생: {e}")