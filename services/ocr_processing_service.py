# /services/ocr_processing_service.py

import json
import re
from pathlib import Path

import easyocr
import fitz  # PyMuPDF
import numpy as np
import pdfplumber
from PIL import Image


class OcrProcessingService:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        # easyocr 리더는 초기화 시 시간이 걸리므로 서버 시작 시 한 번만 실행합니다.
        print("EasyOCR 리더를 초기화합니다... (ko, en)")
        self.reader = easyocr.Reader(['ko', 'en'])

    def _extract_table_image_from_pdf(self, pdf_path: str, keyword="이수학점 비교") -> Image.Image | None:
        """PDF 파일에서 키워드를 찾아 근처 테이블 영역을 이미지로 추출합니다."""
        print(f"'{pdf_path}'에서 '{keyword}' 테이블 검색 중...")
        try:
            pdf_document = fitz.open(pdf_path)
        except Exception as e:
            print(f"❌ PDF 파일을 열 수 없습니다: {e}")
            return None

        for page_number in range(len(pdf_document)):
            page = pdf_document[page_number]
            text_instances = page.search_for(keyword)

            if text_instances:
                print(f"✅ 페이지 {page_number + 1}에서 키워드 발견.")
                keyword_rect = text_instances[0]
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                with pdfplumber.open(pdf_path) as plumber_pdf:
                    plumber_page = plumber_pdf.pages[page_number]
                    if plumber_page.extract_tables():
                        print("✅ 페이지 내 테이블 확인 완료.")
                        x0, y0, x1, y1 = keyword_rect
                        crop_rect = (page.rect.width - 230, y1 - 20, page.rect.width, y1 + 330)
                        scale = pix.width / page.rect.width
                        crop_pixel_rect = tuple(int(val * scale) for val in crop_rect)
                        cropped_img = img.crop(crop_pixel_rect)
                        print("✅ 테이블 이미지 추출 완료.")
                        return cropped_img

        print(f"❌ '{keyword}' 키워드 또는 테이블을 찾을 수 없습니다.")
        return None

    def _parse_ocr_to_json(self, text: str) -> dict:
        """OCR로 추출된 텍스트를 분석하여 지정된 JSON 형식으로 변환합니다."""
        print("OCR 텍스트 파싱 중...")
        data_template = {
            "교양 필수": {"이수기준": None, "취득학점": None},
            "기초전공": {"이수기준": None, "취득학점": None},
            "단일전공자 최소전공이수학점": {"이수기준": None, "취득학점": None},
            "복수,부,연계전공 기초전공": {"이수기준": None, "취득학점": None},
            "복수,부,연계전공 최소전공이수학점": {"이수기준": None, "취득학점": None},
            "졸업학점": None,
            "취득학점": None,
            "편입인정학점": None
        }
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]

        for i, line in enumerate(lines):
            if "교양필수" in line:
                if i + 2 < len(lines) and lines[i+1].isdigit() and lines[i+2].isdigit():
                    data_template["교양 필수"]["이수기준"] = int(lines[i+1])
                    data_template["교양 필수"]["취득학점"] = int(lines[i+2])
                    break
        for i, line in enumerate(lines):
            if "단일전공자" in line:
                if i + 3 < len(lines) and lines[i+1].isdigit() and lines[i+2].isdigit() and "최소전공이수학점" in lines[i+3]:
                    data_template["단일전공자 최소전공이수학점"]["이수기준"] = int(lines[i+1])
                    data_template["단일전공자 최소전공이수학점"]["취득학점"] = int(lines[i+2])
                    break
        b_indices = [i for i, line in enumerate(lines) if "복수" in line or "연계" in line]
        if len(b_indices) >= 1:
            idx1 = b_indices[0]
            if idx1 + 3 < len(lines) and lines[idx1+1].isdigit() and lines[idx1+2].isdigit() and "기초전공" in lines[idx1+3]:
                data_template["복수,부,연계전공 기초전공"]["이수기준"] = int(lines[idx1+1])
                data_template["복수,부,연계전공 기초전공"]["취득학점"] = int(lines[idx1+2])
        if len(b_indices) >= 2:
            idx2 = b_indices[1]
            if idx2 + 3 < len(lines) and lines[idx2+1].isdigit() and lines[idx2+2].isdigit() and "최소전공이수학점" in lines[idx2+3]:
                data_template["복수,부,연계전공 최소전공이수학점"]["이수기준"] = int(lines[idx2+1])
                data_template["복수,부,연계전공 최소전공이수학점"]["취득학점"] = int(lines[idx2+2])
        for i, line in enumerate(lines):
            if "기초전공" in line and (i == 0 or "복수" not in lines[i-1]):
                if i + 2 < len(lines) and lines[i+1].isdigit() and lines[i+2].isdigit():
                    data_template["기초전공"]["이수기준"] = int(lines[i+1])
                    data_template["기초전공"]["취득학점"] = int(lines[i+2])
                    break
        for i, line in enumerate(lines):
            if "졸업학점" in line:
                if i + 1 < len(lines) and lines[i+1].isdigit():
                    data_template["졸업학점"] = int(lines[i+1])
            elif "취득학 점" in line:
                if i + 1 < len(lines) and lines[i+1].isdigit():
                    data_template["취득학점"] = int(lines[i+1])
            elif "편입인정학점" in line:
                if i + 1 < len(lines) and lines[i+1].isdigit():
                    data_template["편입인정학점"] = int(lines[i+1])
                else:
                    data_template["편입인정학점"] = 0
        print("✅ 파싱 완료.")
        return data_template
    
    def process_pdf_for_credits(self, pdf_path: str) -> dict:
        """PDF 학점표를 받아 OCR 처리 후 JSON 데이터를 반환하는 메인 파이프라인입니다."""
        table_image = self._extract_table_image_from_pdf(pdf_path)
        if table_image is None:
            raise ValueError("PDF에서 '이수학점 비교' 키워드나 관련 테이블을 찾을 수 없습니다.")

        print("EasyOCR로 텍스트 추출 실행 중...")
        try:
            img_np = np.array(table_image)
            ocr_result = self.reader.readtext(img_np, detail=0)
            ocr_text = "\n".join(ocr_result)
            print("✅ OCR 텍스트 추출 완료.")
        except Exception as e:
            print(f"❌ EasyOCR 실행 중 오류 발생: {e}")
            raise e

        final_data = self._parse_ocr_to_json(ocr_text)
        return final_data

# 👇 [중요] 이 부분이 파일에 누락되어 오류가 발생했습니다.
# 클래스 정의 후, 실제로 사용할 객체(인스턴스)를 생성해줘야 합니다.
ocr_service = OcrProcessingService()