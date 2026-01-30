# RAG FastAPI Project

FastAPI 기반의 RAG(Retrieval-Augmented Generation) 챗봇 및 문서 처리 시스템입니다. PDF 문서를 벡터 데이터베이스로 변환하고, 지능형 검색을 통해 정확한 답변을 제공합니다. 또한 OCR 기능과 자동화된 웹 크롤링 기능을 포함합니다.

## 📋 목차

- [주요 기능](#주요-기능)
- [프로젝트 구조](#프로젝트-구조)
- [API 명세](#api-명세)
- [설치 및 실행](#설치-및-실행)
- [환경 변수 설정](#환경-변수-설정)
- [사용 예시](#사용-예시)
- [기술 스택](#기술-스택)
- [자동화 시스템](#자동화-시스템)

---

## 🚀 주요 기능

### 1. RAG 챗봇 (Retrieval-Augmented Generation)

- **하이브리드 검색 시스템**
  - 메타데이터 필터링: `key:value` 형식의 질문을 자동으로 파싱하여 정확한 필터링 수행
  - 의미 기반 검색: 벡터 유사도 검색을 통한 컨텍스트 기반 답변
  - 키워드 검색: 일반 질문의 경우 키워드 기반 `$or` 검색 수행
- **지능형 질문 파싱**: 사용자 질문을 분석하여 최적의 검색 전략 자동 선택
- **동적 메타데이터 추출**: 텍스트 파일의 `Key: Value` 구조를 자동 인식하여 메타데이터로 저장

### 2. PDF 문서 처리

- **다중 형식 변환**: PDF를 DOCX, Markdown, HTML, TXT 형식으로 자동 변환
- **LlamaParse 통합**: 고급 PDF 파싱을 위한 LlamaParse API 활용
- **벡터 DB 자동 구축**: 처리된 문서를 ChromaDB에 자동 저장하여 검색 가능하게 만듦
- **배치 처리**: 대용량 문서도 효율적으로 처리

### 3. OCR (광학 문자 인식)

- **성적표 자동 분석**: PDF 성적표에서 '이수학점 비교' 테이블을 자동으로 찾아 OCR 수행
- **구조화된 데이터 추출**: 이수기준, 취득학점 등 정보를 JSON 형식으로 반환
- **자동 파일 정리**: 분석 완료 후 원본 파일 자동 삭제로 보안 유지

### 4. 웹 크롤링 및 자동화

- **공지사항 자동 수집**: Selenium을 활용한 학교 공지사항 크롤링
- **첨부파일 처리**: 게시글의 이미지 및 첨부파일 자동 다운로드 및 분류
- **스케줄링**: APScheduler를 통한 자동 크롤링 (매일 10:50, 14:50, 17:50, 23:50)
- **Spring 서버 연동**: 수집된 데이터를 multipart/form-data 형식으로 자동 전송

---

## 📁 프로젝트 구조

```
rag_fastapi_project/
├── main.py                          # FastAPI 앱 진입점 및 스케줄러 설정
├── requirements.txt                 # Python 패키지 의존성
├── README.md                        # 프로젝트 문서
│
├── core/
│   └── config.py                    # 환경 변수 및 설정 관리
│
├── models/
│   └── llm_factory.py               # LLM 및 Embedding 모델 팩토리
│
├── routers/
│   ├── chat_router.py               # RAG 챗봇 API 엔드포인트
│   ├── processing_router.py         # PDF 처리 및 벡터 DB 관리 API
│   ├── ocr_router.py                # OCR 분석 API
│   └── crawling_router.py           # 크롤링 수동 실행 API
│
├── services/
│   ├── chat_service.py              # 질문 파싱 및 답변 생성 로직
│   ├── file_processing_service.py  # PDF 변환 파이프라인
│   ├── vector_store_service.py      # ChromaDB 저장 및 검색 로직
│   ├── ocr_processing_service.py   # EasyOCR 기반 성적표 파싱
│   └── crawling_service.py          # Selenium 크롤링 서비스
│
├── schemas/
│   └── chat_schema.py               # Pydantic 데이터 모델 정의
│
├── uploads/                         # 업로드된 파일 임시 저장소
├── processed_files/                 # 처리된 파일 저장소
└── chroma_db/                       # ChromaDB 벡터 데이터베이스 저장소
```

---

## 🔌 API 명세

모든 API는 `http://127.0.0.1:8000/api/v1` 접두사를 사용합니다.

### 📄 File Processing & DB Management

#### `POST /api/v1/processing/process-pdf-full-and-build-db`

PDF 파일을 업로드하여 모든 형식으로 변환하고 벡터 DB를 구축합니다.

**Request:**
- `file`: PDF 파일 (multipart/form-data)
- `collection_name`: 벡터 DB 컬렉션 이름 (Form Data)

**Response:**
```json
{
  "message": "PDF 파일 처리 및 '2025-2' 벡터 DB 구축이 모두 완료되었습니다.",
  "source_file": "example.pdf",
  "docx_file": "uploads/example.docx",
  "markdown_file": "uploads/example.md",
  "html_file": "uploads/example.html",
  "rag_text_file": "uploads/example.txt"
}
```

#### `POST /api/v1/processing/process-pdf-only`

PDF 파일을 변환만 수행합니다. (벡터 DB 구축 제외)

**Request:**
- `file`: PDF 파일 (multipart/form-data)

#### `GET /api/v1/processing/collections`

현재 생성된 모든 벡터 DB 컬렉션 목록을 조회합니다.

**Response:**
```json
{
  "collections": ["2025-2", "2024-1"]
}
```

### 💬 Chat

#### `POST /api/v1/chat/chat`

구축된 문서를 기반으로 질문에 답변합니다.

**Request:**
```json
{
  "question": "1학년 교양 필수 과목 추천해줘"
}
```

또는 필터링 검색:
```json
{
  "question": "'학년':'1' '이수구분':'교양' 과목 추천"
}
```

**Response:**
```json
{
  "answer": "1학년 교양 필수 과목으로는 다음과 같은 과목들이 있습니다..."
}
```

**특징:**
- 일반 질문: 키워드 및 의미 기반 검색
- `'key':'value'` 패턴 포함 시: 메타데이터 필터링 + 의미 검색 조합

### 📄 OCR Processing

#### `POST /api/v1/ocr/extract-credits`

성적표 PDF를 업로드하여 이수학점 정보를 추출합니다.

**Request:**
- `file`: 성적표 PDF 파일 (multipart/form-data)

**Response:**
```json
{
  "교양 필수": {
    "이수기준": 10,
    "취득학점": 10
  },
  "기초전공": {
    "이수기준": 9,
    "취득학점": 9
  },
  "단일전공자 최소전공이수학점": {
    "이수기준": 60,
    "취득학점": 45
  },
  "졸업학점": 130,
  "취득학점": 140,
  "편입인정학점": 0
}
```

### 🕷️ Crawling

#### `POST /api/v1/crawl/crawl-and-send-all-to-spring`

공지사항을 크롤링하여 Spring 서버로 전송합니다. (수동 실행용)

**Response:**
```json
{
  "message": "크롤링 및 Spring 서버 전송 시도가 완료되었습니다.",
  "total_crawled": 5,
  "successful_sends": 4,
  "failed_sends": 1,
  "send_results": [
    {
      "notice_title": "2025학년도 1학기 수강신청 안내",
      "status": "성공",
      "spring_status_code": 200
    }
  ]
}
```

**Note:** 평소에는 스케줄러가 자동으로 실행하므로, 테스트나 긴급 동기화 시에만 사용합니다.

---

## 🛠️ 설치 및 실행

### 1. 사전 요구사항

- Python 3.11 이상
- Chrome 브라우저 (Selenium 크롤링용)
- OpenAI API Key
- Llama Cloud API Key

### 2. 가상환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 입력하세요:

```bash
# AI & API Keys
OPENAI_API_KEY=sk-your-openai-api-key
LLAMA_CLOUD_API_KEY=llx-your-llama-cloud-api-key

# 크롤링 계정 (학교 포털 정보)
CROWLING_ID=your_portal_id
CROWLING_PW=your_portal_password

# Spring 서버 연동
SPRING_SERVER_UPLOAD_URL=http://your-spring-server:port/api/upload
CRAWLER_SECRET_KEY=your-secret-token

# DB 설정
DEFAULT_MODEL=OPENAI
DB_PATH=./chroma_db
DEFAULT_DB_COLLECTION_NAME=2025-2
```

### 5. 서버 실행

```bash
# 개발 모드 (자동 리로드)
uvicorn main:app --reload

# 프로덕션 모드
uvicorn main:app --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 📝 사용 예시

### 1. PDF 업로드 및 벡터 DB 구축

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/processing/process-pdf-full-and-build-db" \
  -F "file=@example.pdf" \
  -F "collection_name=2025-2"
```

### 2. 챗봇 질문

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "1학년 교양 필수 과목 추천해줘"
  }'
```

### 3. 필터링 검색

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/chat/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "\"학년\":\"1\" \"이수구분\":\"교양\" 과목 추천"
  }'
```

### 4. OCR 성적표 분석

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/ocr/extract-credits" \
  -F "file=@transcript.pdf"
```

---

## 🛠️ 기술 스택

### Backend Framework
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **Uvicorn**: ASGI 서버

### AI & ML
- **LangChain**: LLM 애플리케이션 프레임워크
- **OpenAI GPT-4**: 대화형 LLM
- **OpenAI Embeddings**: 텍스트 임베딩 모델
- **ChromaDB**: 벡터 데이터베이스

### 문서 처리
- **LlamaParse**: 고급 PDF 파싱
- **PyMuPDF**: PDF 처리
- **pdf2docx**: PDF to DOCX 변환
- **python-docx**: DOCX 파일 처리

### OCR
- **EasyOCR**: 광학 문자 인식
- **pdfplumber**: PDF 텍스트 추출
- **Pillow**: 이미지 처리

### 크롤링
- **Selenium**: 웹 자동화 및 크롤링
- **BeautifulSoup4**: HTML 파싱
- **httpx**: 비동기 HTTP 클라이언트

### 스케줄링
- **APScheduler**: 비동기 작업 스케줄링

### 기타
- **Pydantic**: 데이터 검증
- **python-dotenv**: 환경 변수 관리

---

## ⏰ 자동화 시스템

### 스케줄러 동작

서버가 시작되면 **APScheduler**가 백그라운드에서 자동으로 실행됩니다.

**크롤링 스케줄:**
- 매일 **10:50, 14:50, 17:50, 23:50** (KST 기준)

**자동화 프로세스:**
1. 학교 포털 자동 로그인
2. 공지사항 게시판 접근 및 최신글 파싱
3. 본문 텍스트, 이미지, 첨부파일 다운로드
4. Spring 서버로 데이터 전송 (`multipart/form-data`)
5. 임시 파일 자동 삭제 및 로그 기록

**스케줄 변경 방법:**
`main.py`의 `CronTrigger` 설정을 수정하여 스케줄을 변경할 수 있습니다:

```python
@scheduler.scheduled_job(
    CronTrigger(
        hour="10,14,17,23",
        minute="50",
        timezone="Asia/Seoul"
    ),
    id="crawl_yongin_notices_job",
    name="용인대 공지사항 크롤링 및 전송"
)
```

---

## 🔍 주요 특징

### 하이브리드 검색 시스템

1. **메타데이터 필터링**: `'key':'value'` 패턴을 인식하여 정확한 필터링 수행
2. **의미 기반 검색**: 벡터 유사도 검색으로 컨텍스트 기반 답변
3. **키워드 검색**: 일반 질문의 경우 키워드 기반 `$or` 검색

### 비동기 처리

- 모든 I/O 작업(벡터 DB 검색, LLM 호출)을 비동기로 처리하여 높은 성능 유지
- 여러 요청을 동시에 처리 가능

### 자동 파일 관리

- OCR 처리 후 원본 파일 자동 삭제
- 크롤링 후 임시 파일 자동 정리
- 업로드된 파일의 자동 관리

---

## 📄 라이선스

이 프로젝트는 내부 사용을 위한 프로젝트입니다.

---

## 🤝 기여

프로젝트 개선을 위한 제안이나 버그 리포트는 이슈로 등록해주세요.

---

## 📞 문의

프로젝트 관련 문의사항이 있으시면 이슈를 생성해주세요.
