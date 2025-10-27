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


# ▼▼▼ [수정 1] 핵심 로직을 별도 async 함수로 분리 ▼▼▼
async def run_crawl_and_send_logic() -> CrawlSendSummaryResponse:
    """
    용인대 공지사항을 크롤링하고 Spring 서버로 전송하는 핵심 로직.
    (스케줄러 및 엔드포인트에서 공통으로 호출)
    """
    crawled_data: Optional[List[Dict]] = None
    temp_dir: str = ""
    send_results: List[SpringSendResult] = []
    successful_sends = 0
    failed_sends = 0
    total_crawled = 0

    try:
        # 1. 크롤링 실행
        crawled_data, temp_dir = await crawling_service.crawl_yongin_notices_with_files()

        if not crawled_data:
            logger.warning("크롤링된 데이터가 없어 Spring 서버로 전송할 수 없습니다.")
            # 스케줄러에서 실행될 때 HTTPException 대신 요약 응답 반환
            return CrawlSendSummaryResponse(
                message="수집된 데이터가 없습니다.",
                total_crawled=0,
                successful_sends=0,
                failed_sends=0,
                send_results=[]
            )

        total_crawled = len(crawled_data)
        logger.info(f"총 {total_crawled}개의 게시글 크롤링 완료. Spring 서버로 전송 시작...")

        headers = {
            "X-Auth-Token": settings.CRAWLER_SECRET_KEY
        }

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
                    response = await client.post(
                        settings.SPRING_SERVER_UPLOAD_URL,
                        files=files_to_send,
                        headers=headers
                    )
                    
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
                # ( ... 기존 오류 처리 로직 ... )
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

    except Exception as e:
        logger.error(f"크롤링 또는 전송 프로세스 중 예기치 않은 오류 발생: {e}", exc_info=True)
        # 스케줄러에서 실행될 때를 대비해 오류가 포함된 응답 반환
        return CrawlSendSummaryResponse(
            message=f"크롤링/전송 실패: {str(e)}",
            total_crawled=total_crawled,
            successful_sends=successful_sends,
            failed_sends=failed_sends,
            send_results=send_results
        )
    finally:
        # ▼▼▼ [수정 2] background_tasks 대신 finally에서 직접 디렉터리 삭제 ▼▼▼
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"임시 디렉터리 [{temp_dir}] 정리 완료.")
            except Exception as rm_err:
                logger.error(f"임시 디렉터리 [{temp_dir}] 정리 실패: {rm_err}")
# ▲▲▲ [수정 1, 2] ▲▲▲


@router.post("/crawl-and-send-all-to-spring", response_model=CrawlSendSummaryResponse)
async def crawl_and_send_all_to_spring(background_tasks: BackgroundTasks): # 👈 background_tasks는 이제 사용되지 않지만, 호환성을 위해 남겨둘 수 있습니다.
    """
    용인대 공지사항을 크롤링하여, 각 게시글과 해당 첨부파일을
    Spring 서버로 개별 `multipart/form-data` 전송합니다. (API 키 인증 포함)
    
    (이 엔드포인트는 수동 실행용이며, 자동 스케줄링은 별도로 동작합니다.)
    """
    # ▼▼▼ [수정 3] 분리된 함수를 직접 호출하고 결과를 기다림 ▼▼▼
    try:
        # 원래 코드처럼 작업이 끝날 때까지 기다렸다가 결과를 반환합니다.
        return await run_crawl_and_send_logic()
    except Exception as e:
        logger.error(f"엔드포인트 실행 중 예기치 않은 오류: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"작업 실행 실패: {str(e)}")
    # ▲▲▲ [수정 3] ▲▲▲