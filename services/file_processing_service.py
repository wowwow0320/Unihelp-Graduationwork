# services/file_processing_service.py

import os
import re
from pathlib import Path
from pdf2docx import Converter
from llama_parse import LlamaParse
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table
from bs4 import BeautifulSoup
import pandas as pd
import io
from core.config import settings

class FileProcessingService:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

    def _pdf_to_docx(self, pdf_path: str, docx_path: str):
        try:
            cv = Converter(str(pdf_path))
            cv.convert(str(docx_path))
            cv.close()
            print(f"📄 PDF → DOCX 변환 완료: {docx_path}")
        except Exception as e:
            raise Exception(f"pdf_to_docx 오류: {e}")

    def _pdf_to_markdown(self, pdf_path: str, md_path: str):
        parsing_instruction = (
            "본문과 표를 구분해 주세요.\n"
            "- 표의 첫 행이 여러 줄로 구성되어 있다면, 이를 헤더로 간주하고 병합해 하나의 헤더로 만들어주세요.\n"
            "- 표는 정확히 html 형식으로 변환해주세요.\n"
            "- 표의 헤더는 반드시 각 열에 맞춰 분리해주세요.\n"
            "- 줄 바꿈 태그(<br/>)는 절대 사용하지 말고, 여러 조건이 있는 셀은 슬래시(/) 또는 쉼표(,)로 구분해주세요.\n"
            "- 병합된 셀은 해당 열에 맞춰 반복 삽입해주세요.\n"
            "- 열 수가 불균형한 행은 무조건 헤더 열 수에 맞춰 정렬해주세요.\n"
            "- 요약이나 설명은 절대 포함하지 마세요.\n"
        )
        parser = LlamaParse(api_key=settings.LLAMA_CLOUD_API_KEY, result_type="markdown", parsing_instruction=parsing_instruction, verbose=True)
        try:
            documents = parser.load_data(str(pdf_path))
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(documents[0].text)
            print(f"📄 PDF → Markdown 변환 완료: {md_path}")
        except Exception as e:
            raise Exception(f"pdf_to_markdown 오류: {e}")

    def _docx_tables_to_html(self, docx_path: str, html_path: str):
        doc = Document(docx_path)
        full_parts = []
        for table in doc.tables:
            html_table = "<table border='1'>\n"
            for row in table.rows:
                html_table += "  <tr>\n"
                for cell in row.cells:
                    cell_text = "<br>".join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                    html_table += f"    <td>{cell_text}</td>\n"
                html_table += "  </tr>\n"
            html_table += "</table>\n"
            full_parts.append(html_table)
        
        soup = BeautifulSoup("\n".join(full_parts), "html.parser")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print(f"📄 DOCX → HTML(Tables) 변환 완료: {html_path}")

    def _html_tables_to_text(self, html_path: str, txt_path: str):
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            raise Exception(f"입력 파일 '{html_path}'을 찾을 수 없습니다.")

        blocks = content.split('\n# ')[1:] if '\n# ' in content else [content]
        final_sentences = []
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block: continue
            parts = block.split('\n', 1)
            title = parts[0].strip() if len(parts) > 1 else f"테이블 {i+1}"
            table_html = parts[1].strip() if len(parts) > 1 else block
            try:
                df_list = pd.read_html(io.StringIO(table_html), header=0, encoding='utf-8')
                if not df_list: continue
                df = df_list[0]
                if df.iloc[0].astype(str).str.contains('대 학').any():
                    new_header = df.iloc[0]
                    df = df[1:]
                    df.columns = [f"{col.split('.')[0]} {val}" if 'Unnamed' not in str(col) else val for col, val in new_header.items()]
                for _, row in df.iterrows():
                    row_data = ", ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                    final_sentences.append(f"제목: {title}, {row_data}")
            except Exception as e:
                print(f"⚠️ {i+1}번째 테이블 처리 중 오류 발생 (건너뜁니다): {e}")
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final_sentences))
        print(f"📄 HTML → TXT(RAG) 변환 완료: {txt_path}")

    def process_pipeline(self, pdf_path: str) -> tuple[str, str]:
        base_name = Path(pdf_path).stem
        
        docx_path = self.upload_dir / f"{base_name}.docx"
        self._pdf_to_docx(pdf_path, docx_path)
        
        md_path = self.upload_dir / f"{base_name}.md"
        self._pdf_to_markdown(pdf_path, md_path)
        
        html_path = self.upload_dir / f"{base_name}.html"
        self._docx_tables_to_html(docx_path, html_path)
        
        txt_path = self.upload_dir / f"{base_name}_rag.txt"
        self._html_tables_to_text(html_path, txt_path)
            
        return str(md_path), str(txt_path)

file_processor = FileProcessingService()