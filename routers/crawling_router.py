# /routers/crawling_router.py

import shutil
import os
import httpx
import logging
import json
from typing import List, Tuple, Optional, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from core.config import settings # 👈 settings 임포트 확인
from services.crawling_service import crawling_service
from schemas.chat_schema import CrawlSendSummaryResponse, SpringSendResult
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/crawl-and-send-all-to-spring", response_model=CrawlSendSummaryResponse)
async def crawl_and_send_all_to_spring(background_tasks: BackgroundTasks):
    """
    용인대 공지사항을 크롤링하여, 각 게시글과 해당 첨부파일을
    Spring 서버로 개별 `multipart/form-data` 전송합니다. (API 키 인증 포함)
    """
    crawled_data: Optional[List[Dict]] = None
    temp_dir: str = ""
    send_results: List[SpringSendResult] = []
    successful_sends = 0
    failed_sends = 0

    try:
        # 1. 크롤링 실행
        crawled_data, temp_dir = await crawling_service.crawl_yongin_notices_with_files()

        if temp_dir and os.path.exists(temp_dir):
            background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
            logger.info(f"임시 디렉터리 [{temp_dir}] 삭제 예약됨.")

        if not crawled_data:
            logger.warning("크롤링된 데이터가 없어 Spring 서버로 전송할 수 없습니다.")
            raise HTTPException(status_code=404, detail="수집된 데이터가 없습니다.")

        total_crawled = len(crawled_data)
        logger.info(f"총 {total_crawled}개의 게시글 크롤링 완료. Spring 서버로 전송 시작...")

        # ▼▼▼ [수정] 1: Spring에 보낼 API 키 헤더 생성 ▼▼▼
        # Spring ApiKeyAuthFilter가 검사할 헤더
        headers = {
            "X-Auth-Token": settings.CRAWLER_SECRET_KEY
        }
        # ▲▲▲ [수정] 1 ▲▲▲

        # 2. 각 게시글별로 Spring 서버에 전송
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i, notice in enumerate(crawled_data):
                notice_title = notice.get('title', f'게시글 {i+1}')
                logger.info(f"-> {i+1}/{total_crawled}번째 게시글 전송 시도: {notice_title}")

                files_to_send = []
                file_objs_to_close = []
                
                # 'dto' 파트 (JSON) 생성
                dto_part = {
                    "title": notice.get("title"),
                    "text": notice.get("text"),
                    "department": notice.get("department"),
                    "originalCreatedAt": datetime.now().isoformat()
                }
                dto_json_str = json.dumps(dto_part, ensure_ascii=False)
                files_to_send.append(('dto', (None, dto_json_str, 'application/json')))

                # 'images' 파트 (이미지 파일)
                image_paths = notice.get('image_full_paths', [])
                for file_path in image_paths:
                    if os.path.exists(file_path):
                        try:
                            f_obj = open(file_path, 'rb')
                            file_objs_to_close.append(f_obj)
                            files_to_send.append(('images', (os.path.basename(file_path), f_obj, 'application/octet-stream')))
                        except Exception as file_open_err:
                            logger.error(f"   - 이미지 파일 열기 실패: {file_path}, 오류: {file_open_err}")
                    else:
                        logger.warning(f"   - 이미지 파일 경로 없음: {file_path}")
                
                # 'attachments' 파트 (기타 첨부파일)
                attachment_paths = notice.get('attachment_full_paths', [])
                for file_path in attachment_paths:
                    if os.path.exists(file_path):
                        try:
                            f_obj = open(file_path, 'rb')
                            file_objs_to_close.append(f_obj)
                            files_to_send.append(('attachments', (os.path.basename(file_path), f_obj, 'application/octet-stream')))
                        except Exception as file_open_err:
                            logger.error(f"   - 첨부파일 열기 실패: {file_path}, 오류: {file_open_err}")
                    else:
                        logger.warning(f"   - 첨부파일 경로 없음: {file_path}")

                # Spring 서버에 POST 요청
                try:
                    # ▼▼▼ [수정] 2: 'headers=headers' 추가 ▼▼▼
                    response = await client.post(
                        settings.SPRING_SERVER_UPLOAD_URL, # "http://localhost:8080/route/notices/school"
                        files=files_to_send,
                        headers=headers # 👈 API 키 헤더 적용
                    )
                    # ▲▲▲ [수정] 2 ▲▲▲
                    
                    response.raise_for_status()
                    
                    send_results.append(SpringSendResult(
                        notice_title=notice_title,
                        status="성공",
                        spring_status_code=response.status_code
                    ))
                    successful_sends += 1
                    logger.info(f"   - 전송 성공 (HTTP {response.status_code})")

                except httpx.HTTPStatusError as e:
                    error_body = e.response.text
                    logger.error(f"   - Spring 서버 오류: {e.response.status_code} - {error_body}")
                    send_results.append(SpringSendResult(
                        notice_title=notice_title,
                        status="실패",
                        spring_status_code=e.response.status_code,
                        error_message=f"Spring 서버 오류: {error_body}"
                    ))
                    failed_sends += 1
                except httpx.RequestError as e:
                    logger.error(f"   - Spring 서버 연결 실패: {e}")
                    send_results.append(SpringSendResult(
                        notice_title=notice_title,
                        status="실패",
                        error_message=f"Spring 서버 연결 실패: {str(e)}"
                    ))
                    failed_sends += 1
                except Exception as e:
                    logger.error(f"   - 전송 중 예기치 않은 오류: {e}")
                    send_results.append(SpringSendResult(
                        notice_title=notice_title,
                        status="실패",
                        error_message=f"전송 준비/실행 중 오류: {str(e)}"
                    ))
                    failed_sends += 1
                finally:
                    # 각 요청마다 열었던 파일 객체들 닫기
                    for f_obj in file_objs_to_close:
                        f_obj.close()

        # 3. 모든 전송 완료 후 최종 결과 반환
        logger.info(f"Spring 서버 전송 완료. 성공: {successful_sends}, 실패: {failed_sends}")
        return CrawlSendSummaryResponse(
            message="크롤링 및 Spring 서버 전송 시도가 완료되었습니다.",
            total_crawled=total_crawled,
            successful_sends=successful_sends,
            failed_sends=failed_sends,
            send_results=send_results
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"크롤링 또는 전송 프로세스 중 예기치 않은 오류 발생: {e}", exc_info=True)
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except Exception as rm_err: logger.error(f"오류 발생 후 임시 디렉터리 정리 실패: {rm_err}")
            
        raise HTTPException(status_code=500, detail=f"크롤링/전송 실패: {str(e)}")