# /services/crawling_service.py

import os
import time
import pandas as pd
import logging
import re
import shutil
import tempfile
import asyncio
import json # 👈 json 모듈 추가
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

class CrawlingService:
    def __init__(self):
        self.USER_ID = settings.CROWLING_ID
        self.USER_PW = settings.CROWLING_PW
        self.max_posts_to_scrape = 10

    # 👇 [수정] 반환 타입 힌트 변경: List[Dict]가 공지 데이터 + 파일 경로 포함
    async def crawl_yongin_notices_with_files(self) -> Tuple[Optional[List[Dict]], str]:
        """
        크롤링 후, 각 공지사항 데이터와 해당 첨부파일 경로 리스트가 포함된
        딕셔너리 리스트와 임시 디렉토리 경로를 반환합니다.
        반환값: (notice_data_with_paths, temp_dir_path)
        """
        result = await asyncio.to_thread(self._run_crawl_logic_for_send)
        return result

    # 👇 [수정] 함수 이름 및 로직 변경
    def _run_crawl_logic_for_send(self) -> Tuple[Optional[List[Dict]], str]:
        """크롤링을 수행하고, 각 공지 딕셔너리에 첨부파일 전체 경로를 포함시켜 반환합니다."""

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

        # 👇 [수정] 데이터를 바로 딕셔너리 리스트로 저장
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
                attachment_full_paths = [] # 현재 게시글 첨부파일 경로 저장용

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

                # 데이터 추출
                title = re.sub(r"^\s*\[.*?\]\s*", "", soup.find('th', 'bbs_title').get_text(strip=True))
                meta_tag = soup.find('td', 'bbs_date')
                writer = meta_tag.contents[0].strip().split(':')[1].strip()
                date = meta_tag.find('span', class_='mr100').get_text(strip=True).split(':')[1].strip()
                content = soup.find('td', 'bbs_content').get_text(strip=True)

                notice_info['제목'] = title
                notice_info['작성자'] = writer
                notice_info['작성일'] = date
                notice_info['내용'] = content

                # 첨부파일 다운로드 및 경로 저장
                post_attachment_filenames = [] # 현재 게시글의 파일명만 (JSON 저장용)
                try:
                    file_elements = driver.find_elements(By.CSS_SELECTOR, "td.bbs_file a")
                    if file_elements:
                        for file_element in file_elements:
                            file_name = file_element.text.strip()
                            post_attachment_filenames.append(file_name) # 파일명 리스트 추가
                            
                            # 다운로드 실행
                            driver.execute_script("arguments[0].click();", file_element)
                            logger.info(f" - 다운로드 실행: {file_name}")
                            time.sleep(3) # 다운로드 대기

                            # 👇 다운로드된 파일의 전체 경로 생성 및 저장
                            full_file_path = os.path.join(download_dir, file_name)
                            if os.path.exists(full_file_path): # 다운로드가 실제로 완료되었는지 확인
                                attachment_full_paths.append(full_file_path)
                            else:
                                logger.warning(f" - 파일 다운로드 실패 또는 시간 부족: {file_name}")
                except Exception as e:
                    logger.error(f"첨부파일 처리 중 오류: {e}")

                notice_info['첨부파일'] = post_attachment_filenames # JSON에는 파일명 리스트 저장
                notice_info['attachment_full_paths'] = attachment_full_paths # 내부 처리용 전체 경로

                crawled_data_with_paths.append(notice_info) # 최종 리스트에 추가

                driver.back()
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'tr.hand')))

        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}")
            # 오류 발생 시에도 임시 디렉토리 경로는 반환해야 함 (정리 목적)
            return None, save_dir
        finally:
            if driver:
                driver.quit()
            logger.removeHandler(file_handler)
            file_handler.close()

        if crawled_data_with_paths:
            # 👇 [수정] JSON 파일 생성 로직 추가 (Spring 전송 시 필요)
            json_data_for_spring = []
            for item in crawled_data_with_paths:
                 # Spring으로 보낼 데이터에서는 attachment_full_paths 제외
                item_copy = item.copy()
                del item_copy['attachment_full_paths']
                json_data_for_spring.append(item_copy)
            
            # 임시 디렉토리에 전체 데이터를 담은 data.json 저장 (옵션)
            try:
                json_path = os.path.join(save_dir, 'crawled_data.json')
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data_for_spring, f, ensure_ascii=False, indent=4)
                logger.info("크롤링 데이터 요약 JSON 저장 완료.")
            except Exception as json_err:
                logger.error(f"크롤링 데이터 요약 JSON 저장 실패: {json_err}")
                
            return crawled_data_with_paths, save_dir
        else:
            logger.info("수집된 데이터가 없습니다.")
            return None, save_dir

crawling_service = CrawlingService()