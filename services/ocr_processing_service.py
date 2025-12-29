# /services/ocr_processing_service.py

import fitz  # PyMuPDF
import pdfplumber
from pathlib import Path

class OcrProcessingService:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # EasyOCR 제거로 인해 초기화 과정이 매우 가벼워졌습니다.
        print("✅ OcrProcessingService 초기화 완료 (PDF 좌표 기반 모드)")

    def process_pdf_for_credits(self, pdf_path: str) -> dict:
        """
        PDF 학점표를 받아 좌표 기반으로 데이터를 정밀 추출하여 dict를 반환합니다.
        Router에서 호출하는 메인 진입점입니다.
        """
        # 1. '이수학점 비교' 표의 좌표(Bounding Box) 찾기
        bbox, page_index = self._find_table_coordinates(pdf_path, keyword="이수학점 비교")
        
        if not bbox:
            # Router의 404 처리를 위해 ValueError 발생
            raise ValueError("PDF에서 '이수학점 비교' 키워드나 관련 테이블을 찾을 수 없습니다.")

        # 2. 해당 좌표의 데이터를 텍스트/테이블로 추출
        extracted_rows = self._extract_data_from_bbox(pdf_path, bbox, page_index)
        
        # 3. 요청된 JSON 포맷으로 파싱
        final_data = self._parse_rows_to_json(extracted_rows)
        
        return final_data

    def _find_table_coordinates(self, pdf_path: str, keyword: str):
        """PyMuPDF를 사용하여 키워드 좌표를 기반으로 테이블 영역을 계산합니다."""
        doc = fitz.open(pdf_path)
        for page_idx, page in enumerate(doc):
            text_instances = page.search_for(keyword)
            if text_instances:
                inst = text_instances[0]  # 첫 번째 발견된 키워드
                
                # 좌표 계산 로직
                # (페이지 우측 영역 - 230, 키워드 위쪽 - 20, 페이지 끝, 키워드 아래 + 330)
                x0 = page.rect.width - 230
                top = inst.y1 - 20
                x1 = page.rect.width
                bottom = inst.y1 + 330
                
                doc.close()
                return (x0, top, x1, bottom), page_idx
        
        doc.close()
        return None, -1

    def _extract_data_from_bbox(self, pdf_path: str, bbox, page_index):
        """pdfplumber로 특정 영역(bbox)의 텍스트를 줄 단위로 추출합니다."""
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_index]
            cropped_page = page.crop(bbox)
            
            # 테이블 구조로 추출 시도 (가장 정확함)
            table = cropped_page.extract_table()
            
            if table:
                cleaned_rows = []
                for row in table:
                    # None 값 제거 및 공백/줄바꿈 정리
                    cleaned_row = [str(cell).replace('\n', '').replace(' ', '') for cell in row if cell is not None]
                    if cleaned_row:
                        cleaned_rows.append(cleaned_row)
                return cleaned_rows
            
            # 테이블 인식이 안 될 경우 텍스트 라인으로 추출 (Fallback)
            text = cropped_page.extract_text()
            return [line.split() for line in text.split('\n') if line.strip()]

    def _parse_rows_to_json(self, rows) -> dict:
        """
        비정형 표(셀 병합 등)에 대응하기 위해 행별로 숫자만 추출하여 매핑하는 로직입니다.
        """
        print("📊 데이터 정밀 파싱 중...")
        
        data_template = {
            "교양 필수": {"이수기준": 0, "취득학점": 0},
            "기초전공": {"이수기준": 0, "취득학점": 0},
            "단일전공자 최소전공이수학점": {"이수기준": 0, "취득학점": 0},
            "복수,부,연계전공 기초전공": {"이수기준": 0, "취득학점": 0},
            "복수,부,연계전공 최소전공이수학점": {"이수기준": 0, "취득학점": 0},
            "졸업학점": 0,
            "취득학점": 0, 
            "편입인정학점": 0
        }

        # 텍스트 정리 헬퍼
        def clean_text(text):
            return str(text).replace(" ", "").replace("\n", "").strip()

        for row in rows:
            # 1. 행 전체 텍스트 합치기 (키워드 검색용)
            full_row_text = clean_text("".join([str(cell) for cell in row if cell]))
            
            # 2. 행에서 '숫자'만 추출 (순서 유지)
            nums = []
            for cell in row:
                if cell:
                    s = str(cell).strip()
                    if s.isdigit():
                        nums.append(int(s))

            if not nums:
                continue

            # --- 조건별 매핑 ---

            # 1. 교양필수
            if "교양필수" in full_row_text and len(nums) >= 2:
                data_template["교양 필수"]["이수기준"] = nums[0]
                data_template["교양 필수"]["취득학점"] = nums[1]

            # 2. 기초전공 (복수전공 제외)
            elif "기초전공" in full_row_text and "복수" not in full_row_text and len(nums) >= 2:
                data_template["기초전공"]["이수기준"] = nums[0]
                data_template["기초전공"]["취득학점"] = nums[1]

            # 3. 단일전공자
            elif "단일전공자" in full_row_text and len(nums) >= 2:
                data_template["단일전공자 최소전공이수학점"]["이수기준"] = nums[0]
                data_template["단일전공자 최소전공이수학점"]["취득학점"] = nums[1]

            # 4. 복수/부/연계전공 기초전공
            elif ("복수" in full_row_text or "연계" in full_row_text) and "기초전공" in full_row_text and len(nums) >= 2:
                data_template["복수,부,연계전공 기초전공"]["이수기준"] = nums[0]
                data_template["복수,부,연계전공 기초전공"]["취득학점"] = nums[1]

            # 5. 복수/부/연계전공 최소전공
            elif ("복수" in full_row_text or "연계" in full_row_text) and "최소전공" in full_row_text and len(nums) >= 2:
                data_template["복수,부,연계전공 최소전공이수학점"]["이수기준"] = nums[0]
                data_template["복수,부,연계전공 최소전공이수학점"]["취득학점"] = nums[1]

            # 6. 졸업학점
            elif "졸업학점" in full_row_text and len(nums) >= 1:
                data_template["졸업학점"] = nums[0]

            # 7. 총 취득학점
            elif ("취득학점" in full_row_text or "계" in full_row_text) and "교양" not in full_row_text and "전공" not in full_row_text:
                if len(nums) >= 1:
                    data_template["취득학점"] = nums[0]

            # 8. 편입인정학점
            elif "편입" in full_row_text and len(nums) >= 1:
                data_template["편입인정학점"] = nums[0]

        return data_template

# 싱글톤 인스턴스 생성 (Router에서 import하여 사용)
ocr_service = OcrProcessingService()