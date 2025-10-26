# /services/crawling_service.py

import os
import time
import pandas as pd
import logging
import re
import shutil
import tempfile
import asyncio
import json
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from typing import Tuple, List, Optional, Dict

from core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# [추가] 이미지 확장자 정의
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')

class CrawlingService:
    def __init__(self):
        self.USER_ID = settings.CROWLING_ID
        self.USER_PW = settings.CROWLING_PW
        self.max_posts_to_scrape = 10

    async def crawl_yongin_notices_with_files(self) -> Tuple[Optional[List[Dict]], str]:
        """
        크롤링 후, 각 공지사항 데이터와 해당 첨부파일 경로 리스트가 포함된
        딕셔셔너리 리스트와 임시 디렉토리 경로를 반환합니다.
        반환값: (notice_data_with_paths, temp_dir_path)
        """
        result = await asyncio.to_thread(self._run_crawl_logic_for_send)
        return result

    def _run_crawl_logic_for_send(self) -> Tuple[Optional[List[Dict]], str]:
        """크롤링을 수행하고, 각 공지 딕셔너리에 이미지/첨부파일 전체 경로를 포함시켜 반환합니다."""

        save_dir = tempfile.mkdtemp(prefix="yongin_crawl_")
        download_dir = os.path.join(save_dir, 'downloads')
        os.makedirs(download_dir)

        log_file_path = os.path.join(save_dir, 'crawler.log')
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

        logger.info(f'임시 데이터 저장 폴더: {save_dir}')
        logger.info(f'첨부파일 저장 폴더: {download_dir}')

        options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        options.add_experimental_option('prefs', prefs)
        options.add_argument('User-Agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 11_1_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument("--window-size=1920,1080")
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        driver = None
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            wait = WebDriverWait(driver, 10)
            logger.info('WebDriver 초기화 완료.')
        except Exception as e:
            logger.error(f"WebDriver 초기화 실패: {e}")
            shutil.rmtree(save_dir)
            raise Exception(f"WebDriver 초기화 실패: {e}")

        crawled_data_with_paths: List[Dict] = []

        try:
            # --- 로그인 ---
            login_url = 'https://total.yongin.ac.kr/login.do'
            driver.get(login_url)
            wait.until(EC.element_to_be_clickable((By.ID, 'userid'))).send_keys(self.USER_ID)
            driver.find_element(By.ID, 'pwd').send_keys(self.USER_PW)
            wait.until(EC.element_to_be_clickable((By.ID, 'btn_login'))).click()
            try:
                WebDriverWait(driver, 2).until(EC.alert_is_present())
                alert = driver.switch_to.alert; alert_text = alert.text; alert.accept()
                raise ValueError(f"로그인 실패: {alert_text}")
            except TimeoutException: logger.info("로그인 성공 확인 중...")

            # --- 게시판 이동 ---
            full_menu_xpath = "//a[contains(@class, 'btn_fullmenu')]"
            wait.until(EC.element_to_be_clickable((By.XPATH, full_menu_xpath))).click()
            notice_link_xpath = "//div[@id='full_menu']//h3[contains(@onclick, '/stdt/board/notice/list.do')]"
            wait.until(EC.element_to_be_clickable((By.XPATH, notice_link_xpath))).click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.hand')))

            # --- 게시물 순회 및 데이터 추출 ---
            posts_on_page = driver.find_elements(By.CSS_SELECTOR, 'tr.hand')
            num_to_scrape = min(len(posts_on_page), self.max_posts_to_scrape)

            for i in range(num_to_scrape):
                notice_info = {} # 현재 게시글 정보 저장용
                
                # [수정] 이미지/첨부파일 경로 리스트 분리
                image_full_paths = []
                attachment_full_paths = []

                all_posts = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'tr.hand')))
                post_to_click = all_posts[i]
                try:
                    driver.execute_script("arguments[0].click();", post_to_click)
                except Exception as e:
                    logger.error(f"게시물 {i+1} 클릭 실패: {e}. 건너뜁니다.")
                    continue

                wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'bbs_title')))
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')

                # --- [수정] 데이터 추출 및 견고한 파싱 ---
                
                # 1. 제목 (Title)
                title_element = soup.find('th', 'bbs_title')
                title_text = title_element.get_text(strip=True) if title_element else ""
                title = re.sub(r"^\s*\[.*?\]\s*", "", title_text) # [공지] 태그 제거

                meta_tag = soup.find('td', 'bbs_date')
                
                # 2. 작성자 (Writer -> Department)
                writer = "" # 기본값 초기화
                try:
                    # 2-1. '작성자: 장학과' 텍스트 노드 파싱 시도
                    if meta_tag and meta_tag.contents:
                        writer_text_node = meta_tag.contents[0].strip()
                        if ":" in writer_text_node:
                            writer = writer_text_node.split(':', 1)[1].strip()
                except Exception as e:
                    logger.warning(f"'{title}' 공지에서 작성자 파싱 중 오류: {e}")

                # 2-2. 파싱 실패 시, 제목에서 힌트 찾기 (예: [취창업지원센터])
                if not writer:
                    try:
                        match = re.search(r"\[(.*?)\]", title_text) # [공지] 태그 제거 전 원본 제목
                        if match:
                            potential_writer = match.group(1).strip()
                            if 3 < len(potential_writer) < 20 and not potential_writer.isdigit():
                                writer = potential_writer
                                logger.info(f"'{title}' 공지에서 작성자를 제목('[ ]')에서 추출: {writer}")
                    except Exception as e:
                         logger.warning(f"'{title}' 공지 제목에서 작성자 추출 중 오류: {e}")
                        
                # 2-3. [최후의 보루] 그래도 없으면 기본값 할당
                if not writer:
                    # (중요) "학교 본부"라는 User가 Spring DB에 반드시 존재해야 합니다.
                    writer = "학교 본부" 
                    logger.warning(f"'{title}' 공지에서 작성자를 찾을 수 없어 기본값 '학교 본부'를 할당합니다.")
                
                # 3. 작성일 (Date) 및 본문 (Content)
                date = meta_tag.find('span', class_='mr100').get_text(strip=True).split(':')[1].strip()
                content = soup.find('td', 'bbs_content').get_text(strip=True)

                # Spring DTO에 맞게 Key 이름 변경
                notice_info['title'] = title
                notice_info['department'] = writer # 'writer'는 이제 절대 비어있지 않음
                notice_info['text'] = content
                notice_info['original_date'] = date # 참고용 원본 작성일

                # --- [수정 완료] ---

                # 첨부파일 다운로드 및 경로 저장
                post_attachment_filenames = [] 
                try:
                    file_elements = driver.find_elements(By.CSS_SELECTOR, "td.bbs_file a")
                    if file_elements:
                        for file_element in file_elements:
                            file_name = file_element.text.strip()
                            post_attachment_filenames.append(file_name)
                            
                            driver.execute_script("arguments[0].click();", file_element)
                            logger.info(f" - 다운로드 실행: {file_name}")
                            time.sleep(3) # 다운로드 대기

                            full_file_path = os.path.join(download_dir, file_name)
                            if os.path.exists(full_file_path):
                                
                                # [수정] 파일 확장자로 이미지/첨부파일 분리
                                if file_name.lower().endswith(IMAGE_EXTENSIONS):
                                    image_full_paths.append(full_file_path)
                                else:
                                    attachment_full_paths.append(full_file_path)
                            else:
                                logger.warning(f" - 파일 다운로드 실패 또는 시간 부족: {file_name}")
                except Exception as e:
                    logger.error(f"첨부파일 처리 중 오류: {e}")

                notice_info['original_filenames'] = post_attachment_filenames # (참고용)
                
                # [수정] 분리된 리스트를 딕셔너리에 저장
                notice_info['image_full_paths'] = image_full_paths
                notice_info['attachment_full_paths'] = attachment_full_paths

                crawled_data_with_paths.append(notice_info) # 최종 리스트에 추가

                driver.back()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.hand')))

        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}")
            return None, save_dir
        finally:
            if driver:
                driver.quit()
            logger.removeHandler(file_handler)
            file_handler.close()

        if crawled_data_with_paths:
            # [수정] 불필요한 JSON 저장 로직 삭제
            logger.info("크롤링 데이터 수집 및 파일 다운로드 완료.")
            return crawled_data_with_paths, save_dir
        else:
            logger.info("수집된 데이터가 없습니다.")
            return None, save_dir

crawling_service = CrawlingService()