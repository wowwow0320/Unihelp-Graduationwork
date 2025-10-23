# /routers/crawling_router.py

import shutil
import os
import httpx
import logging
import json # 👈 json 모듈 추가
from typing import List, Tuple, Optional, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from core.config import settings
from services.crawling_service import crawling_service
# 👇 [수정] 응답 스키마 변경
from schemas.chat_schema import CrawlSendSummaryResponse, SpringSendResult

router = APIRouter()
logger = logging.getLogger(__name__)

# 👇 [수정] 엔드포인트 이름 변경 (하는 일이 바뀌었으므로)
@router.post("/crawl-and-send-all-to-spring", response_model=CrawlSendSummaryResponse)
async def crawl_and_send_all_to_spring(background_tasks: BackgroundTasks):
    """
    용인대 공지사항을 크롤링하여, 각 게시글과 해당 첨부파일을
    Spring 서버로 개별 `multipart/form-data` 전송합니다.
    """
    crawled_data: Optional[List[Dict]] = None
    temp_dir: str = ""
    send_results: List[SpringSendResult] = []
    successful_sends = 0
    failed_sends = 0

    try:
        # 1. 크롤링 실행 (공지 데이터 + 첨부파일 경로 리스트 포함)
        crawled_data, temp_dir = await crawling_service.crawl_yongin_notices_with_files()

        # 백그라운드 작업으로 임시 디렉터리 삭제 예약
        if temp_dir and os.path.exists(temp_dir):
            background_tasks.add_task(shutil.rmtree, temp_dir, ignore_errors=True)
            logger.info(f"임시 디렉터리 [{temp_dir}] 삭제 예약됨.")

        if not crawled_data:
            logger.warning("크롤링된 데이터가 없어 Spring 서버로 전송할 수 없습니다.")
            raise HTTPException(status_code=404, detail="수집된 데이터가 없습니다.")

        total_crawled = len(crawled_data)
        logger.info(f"총 {total_crawled}개의 게시글 크롤링 완료. Spring 서버로 전송 시작...")

        # 2. 각 게시글별로 Spring 서버에 전송
        async with httpx.AsyncClient(timeout=60.0) as client: # 타임아웃 1분
            for i, notice in enumerate(crawled_data):
                notice_title = notice.get('제목', f'게시글 {i+1}')
                logger.info(f"-> {i+1}/{total_crawled}번째 게시글 전송 시도: {notice_title}")

                files_to_send = []
                file_objs_to_close = []
                
                # 'data' 파트 (JSON): attachment_full_paths 제외하고 전송
                notice_data_for_spring = notice.copy()
                attachment_full_paths = notice_data_for_spring.pop('attachment_full_paths', []) # 경로 추출 및 제거
                
                # 딕셔너리를 JSON 문자열로 변환
                notice_json_str = json.dumps(notice_data_for_spring, ensure_ascii=False)
                files_to_send.append(('data', (None, notice_json_str, 'application/json')))

                # 'files' 파트 (첨부파일)
                for file_path in attachment_full_paths:
                    if os.path.exists(file_path):
                        try:
                            f_obj = open(file_path, 'rb')
                            file_objs_to_close.append(f_obj)
                            files_to_send.append(('files', (os.path.basename(file_path), f_obj, 'application/octet-stream')))
                        except Exception as file_open_err:
                            logger.error(f"   - 첨부파일 열기 실패: {file_path}, 오류: {file_open_err}")
                    else:
                         logger.warning(f"   - 첨부파일 경로 없음: {file_path}")

                # Spring 서버에 POST 요청
                try:
                    response = await client.post(
                        settings.SPRING_SERVER_UPLOAD_URL,
                        files=files_to_send # files 인자로 전달
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
        # 이미 처리된 HTTP 예외는 그대로 다시 발생시킴
        raise
    except Exception as e:
        # 크롤링 자체에서 발생한 오류 (로그인 실패 등)
        logger.error(f"크롤링 또는 전송 프로세스 중 예기치 않은 오류 발생: {e}", exc_info=True)
        # 임시 디렉터리 정리 (백그라운드 작업과 별개로 예외 발생 시 즉시 시도)
        if temp_dir and os.path.exists(temp_dir):
            try: shutil.rmtree(temp_dir)
            except Exception as rm_err: logger.error(f"오류 발생 후 임시 디렉터리 정리 실패: {rm_err}")
                
        raise HTTPException(status_code=500, detail=f"크롤링/전송 실패: {str(e)}")