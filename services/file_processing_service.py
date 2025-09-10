# services/file_processing_service.py

import os
import re
import io
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
from dotenv import load_dotenv
from llama_cloud_services import LlamaParse
from pdf2docx import Converter

# LlamaParse에 전달할 파싱 지시어 (상수로 정의)
PARSING_INSTRUCTION = (
    "본문과 표를 구분해 주세요.\n"
    "- 표의 첫 행이 여러 줄로 구성되어 있다면, 이를 헤더로 간주하고 병합해 하나의 헤더로 만들어주세요.\n"
    "- 표는 정확히 html 형식으로 변환해주세요.\n"
    "- 표의 헤더는 반드시 각 열에 맞춰 분리해주세요.\n"
    "- 줄 바꿈 태그(<br/>)는 절대 사용하지 말고, 여러 조건이 있는 셀은 슬래시(/) 또는 쉼표(,)로 구분해주세요.\n"
    "- 병합된 셀은 해당 열에 맞춰 반복 삽입해주세요.\n"
    "- 열 수가 불균형한 행은 무조건 헤더 열 수에 맞춰 정렬해주세요.\n"
    "- 요약이나 설명은 절대 포함하지 마세요.\n"
)

class FileProcessorService:
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        load_dotenv()
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("LLAMA_CLOUD_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        self.llama_parser = LlamaParse(
            api_key=api_key,
            parse_mode="parse_page_with_agent",
            model="openai-gpt-4-1",
            high_res_ocr=True,
            adaptive_long_table=True,
            outlined_table_extraction=True,
            output_tables_as_HTML=True,
            markdown_table_multiline_header_separator="<br />",
            system_prompt_append=PARSING_INSTRUCTION,
            page_separator="\n\n—\n\n",
        )
        print("✅ LlamaParse 클라이언트가 성공적으로 초기화되었습니다.")

    async def process_full_pipeline(self, pdf_path: str, start_page: int = 0, end_page: Optional[int] = None) -> Tuple[str, str, str, str]:
        """하나의 PDF 파일로 DOCX, Markdown, HTML, RAG-TXT 파일을 순차적으로 생성합니다."""
        print(f"🚀 전체 파이프라인 시작: {pdf_path}")
        docx_path = self.convert_pdf_to_docx(pdf_path, start_page, end_page)
        markdown_path = await self.parse_pdf_to_markdown(pdf_path)
        html_path = self.convert_docx_to_html(docx_path)
        rag_text_path = self.convert_html_to_rag_text(html_path)
        print(f"✅ 전체 파이프라인 완료. 최종 TXT: {rag_text_path}")
        return docx_path, markdown_path, html_path, rag_text_path

    def convert_pdf_to_docx(self, pdf_path: str, start_page: int = 0, end_page: Optional[int] = None) -> str:
        print(f"📄 DOCX 변환 시작: {pdf_path}")
        pdf_path_obj = Path(pdf_path)
        docx_path = pdf_path_obj.with_suffix(".docx")
        cv = Converter(str(pdf_path_obj))
        cv.convert(str(docx_path), start=start_page, end=end_page)
        cv.close()
        print(f"✅ DOCX 저장 완료: {docx_path}")
        return str(docx_path)

    async def parse_pdf_to_markdown(self, pdf_path: str) -> str:
        print(f"📄 LlamaParse 시작: {pdf_path}")
        pdf_path_obj = Path(pdf_path)
        output_md_path = pdf_path_obj.with_suffix(".md")
        result = await self.llama_parser.aparse(str(pdf_path_obj))
        markdown_documents = result.get_markdown_documents(split_by_page=True)
        processed_pages = [self._preprocess_text(doc.text) for doc in markdown_documents]
        final_markdown = "\n\n".join(processed_pages)
        with open(output_md_path, "w", encoding="utf-8") as f_md:
            f_md.write(final_markdown)
        print(f"✅ Markdown 저장 완료: {output_md_path}")
        return str(output_md_path)

    def convert_docx_to_html(self, docx_path: str) -> str:
        print(f"📄 HTML 변환 시작: {docx_path}")
        html_path = Path(docx_path).with_suffix(".html")
        doc = Document(docx_path)
        full_parts = []
        section_blocks_list = self._get_section_blocks(doc)
        for idx, (section, section_blocks) in enumerate(zip(doc.sections, section_blocks_list), 1):
            header_parts = self._process_header_footer(section.header, f"Header-구역{idx}")
            full_parts.extend(header_parts)
            body_parts = self._process_body(section_blocks)
            full_parts.extend(body_parts)
        full_html = self._prettify_html("\n".join(full_parts))
        soup = BeautifulSoup(full_html, "html.parser")
        table_parts = []
        for table in soup.find_all("table"):
            prev_p = table.find_previous("p")
            if prev_p and not self._is_footer_text(prev_p.get_text(strip=True)):
                table_parts.append(f"# {prev_p.get_text(strip=True)}")
            table_parts.append(str(table))
        tables_only_html = self._prettify_html("\n".join(table_parts))
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(tables_only_html)
        print(f"✅ tables_only HTML 생성 완료: {html_path}")
        return str(html_path)

    def convert_html_to_rag_text(self, html_path: str) -> str:
        print(f"📄 RAG-TXT 변환 시작: {html_path}")
        output_txt_path = Path(html_path).with_suffix(".txt")
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            print(f"❌ 오류: 입력 파일 '{html_path}'을 찾을 수 없습니다.")
            return str(output_txt_path)
        
        blocks = content.split('\n# ')
        blocks = [b.strip() for b in blocks if b.strip()]
        final_sentences = []
        total_blocks = len(blocks)
        print(f"✅ 총 {total_blocks}개의 테이블 블록을 발견했습니다. 변환을 시작합니다...")

        for i, block in enumerate(blocks):
            parts = block.split('\n', 1)
            if len(parts) < 2:
                continue
            
            title, table_html = parts[0].strip(), parts[1].strip()
            try:
                df_list = pd.read_html(io.StringIO(table_html), header=0, encoding='utf-8')
                if not df_list: continue
                df = df_list[0]

                if any('대 학' in str(val) for val in df.iloc[0].values):
                    new_header, df = df.iloc[0], df[1:]
                    df.columns = [f"{str(col).split('.')[0]} {val}" if 'Unnamed' not in str(col) else val for col, val in new_header.items()]
                
                for _, row in df.iterrows():
                    row_data = ", ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                    sentence = f"제목: {title}, {row_data}"
                    final_sentences.append(sentence)
            except Exception as e:
                print(f"⚠️ {i+1}번째 테이블 처리 중 오류 발생 (건너뜁니다): {e}")

        with open(output_txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final_sentences))
        print(f"🎉 RAG-TXT 변환 완료! 총 {len(final_sentences)}개 문장이 '{output_txt_path}'에 저장되었습니다.")
        return str(output_txt_path)

    def _preprocess_text(self, text: str) -> str:
        text_without_tables = re.sub(r"<table.*?</table>", "", text, flags=re.DOTALL)
        text = text_without_tables.replace('\r\n', '\n')
        text = re.sub(r'<br\s*/?>', ' / ', text)
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        text = re.sub(r'\n{2,}', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    def _prettify_html(self, html: str) -> str:
        html = re.sub(r'>\s+<', '><', html)
        html = re.sub(r'(</[^>]+>)', r'\1\n', html)
        return html.strip()

    def _iter_block_items(self, element, doc):
        for child in element.iterchildren():
            if isinstance(child, CT_P): yield Paragraph(child, doc)
            elif isinstance(child, CT_Tbl): yield Table(child, doc)

    def _extract_textbox_texts(self, paragraph):
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts = []
        for txbx in paragraph._element.findall('.//w:txbxContent', ns):
            for t in txbx.findall('.//w:t', ns):
                if t.text: texts.append(t.text)
        return texts

    def _get_section_blocks(self, doc):
        body = doc.element.body
        blocks = list(self._iter_block_items(body, doc))
        section_boundaries, current_blocks = [], []
        for blk in blocks:
            current_blocks.append(blk)
            if isinstance(blk, Paragraph) and blk._element.find('.//w:sectPr', {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}) is not None:
                section_boundaries.append(current_blocks)
                current_blocks = []
        if current_blocks: section_boundaries.append(current_blocks)
        return section_boundaries

    def _is_footer_text(self, text: str) -> bool:
        text = text.strip()
        if not text: return True
        if re.fullmatch(r"-?\s*\d{1,4}\s*-?", text): return True
        if re.fullmatch(r"(p\.?|page)\s*\d{1,4}", text, re.IGNORECASE): return True
        return False

    def _process_header_footer(self, section_part, label):
        parts = []
        for para in section_part.paragraphs:
            combined_text = para.text.strip()
            for tb_text in self._extract_textbox_texts(para):
                if tb_text not in combined_text: combined_text += tb_text
            if combined_text and not self._is_footer_text(combined_text):
                parts.append(f"<p class='header'>[{label}] {combined_text}</p>")
        for table in section_part.tables:
            html_table = "<table border='1' class='header'>\n"
            for row in table.rows:
                html_table += "<tr>" + "".join(f"<td>{'<br>'.join(p.text.strip() for p in cell.paragraphs if p.text.strip())}</td>" for cell in row.cells) + "</tr>\n"
            html_table += "</table>\n"
            parts.append(html_table)
        return parts

    def _process_body(self, blocks):
        parts = []
        for block in blocks:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if text and not self._is_footer_text(text): parts.append(f"<p>{text}</p>")
                tb_combined = "".join(self._extract_textbox_texts(block)).strip()
                if tb_combined and not self._is_footer_text(tb_combined): parts.append(f"<p>{tb_combined}</p>")
            elif isinstance(block, Table):
                html_table = "<table border='1'>\n"
                for row in block.rows:
                    html_table += "<tr>" + "".join(f"<td>{'<br>'.join(p.text.strip() for p in cell.paragraphs if p.text.strip())}</td>" for cell in row.cells) + "</tr>\n"
                html_table += "</table>\n"
                parts.append(html_table)
        return parts