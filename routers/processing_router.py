# routers/processing_router.py

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import shutil
from services.file_processing_service import file_processor
from services.vector_store_service import vector_store_service
from schemas.chat_schema import ProcessingResponse

router = APIRouter()

@router.post("/process-pdf", response_model=ProcessingResponse)
async def process_pdf_and_build_db(
    collection_name: str = Form(...), 
    file: UploadFile = File(...)
):
    """
    PDF 파일을 업로드하여 처리하고, 지정된 이름의 컬렉션에 벡터 DB를 구축합니다.
    """
    if not collection_name.strip():
        raise HTTPException(status_code=400, detail="collection_name을 반드시 입력해야 합니다.")
        
    file_path = file_processor.upload_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        md_path, txt_path = file_processor.process_pipeline(str(file_path))
        vector_store_service.build_from_files(md_path, txt_path, collection_name)

        return ProcessingResponse(
            message=f"PDF 처리 및 '{collection_name}' 컬렉션 구축이 완료되었습니다.",
            markdown_file=md_path,
            rag_text_file=txt_path,
            collection_name=collection_name
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))