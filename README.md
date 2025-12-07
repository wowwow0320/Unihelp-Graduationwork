# 프로젝트 소개

이 프로젝트는 **FastAPI**를 기반으로 구축된 AI 백엔드 서버로, 크게 세 가지 핵심 기능을 수행합니다.

1.  **RAG (Retrieval-Augmented Generation) 챗봇**: PDF 문서를 분석하여 벡터 DB를 구축하고, 질문의 의도(필터링/검색)를 파악하여 정확한 답변을 제공합니다.
2.  **학점표 OCR 분석**: 성적표 PDF를 이미지로 변환 후 **EasyOCR**을 통해 분석하여 이수 학점 정보를 구조화된 JSON으로 반환합니다.
3.  **공지사항 크롤링 및 동기화**: **Selenium**을 이용해 학교 공지사항을 크롤링하고, 텍스트와 첨부파일을 **Spring 서버**로 자동 전송합니다.

## 1. 주요 기능 (Key Features)

###  RAG & Chatbot (문서 기반 질의응답)

* **하이브리드 검색 로직**: 사용자의 질문을 분석하여 **Metadata Filter**(`key:value` 매칭)와 **Semantic Search**, 그리고 **Keyword($or)** 검색을 자동으로 조합해 최적의 답변을 찾습니다.
* **지능형 PDF 처리**: `LlamaParse` 및 자체 파이프라인을 통해 PDF를 텍스트, 표로 분리하여 처리합니다.
* **동적 메타데이터 파싱**: 텍스트 파일의 `Key: Value` 구조를 자동으로 인식하여 벡터 DB의 메타데이터로 저장합니다.

###  OCR (광학 문자 인식)

* **성적표 자동 분석**: PDF 내에서 '이수학점 비교' 테이블을 찾아 이미지를 캡처하고, **EasyOCR**을 수행하여 과목 영역별 이수/취득 학점을 추출합니다.
* **자동 정리**: 분석이 완료된 원본 파일은 서버에서 즉시 삭제되어 보안을 유지합니다.

###  Crawling & Scheduling (크롤링 및 자동화)

* **공지사항 자동 수집**: **Selenium**을 활용하여 로그인 후 학교 게시판의 공지사항(제목, 부서, 내용, 날짜)을 수집합니다.
* **첨부파일/이미지 처리**: 게시글 내의 이미지와 첨부파일을 다운로드하여 분류합니다.
* **스케줄러 내장**: **APScheduler**가 탑재되어 지정된 시간(10:50, 14:50, 17:50, 23:50)에 자동으로 크롤링 작업을 수행합니다.
* **Spring 서버 연동**: 수집된 데이터를 `multipart/form-data` 형식으로 Spring 메인 서버 API로 전송합니다.

---

## 2. 디렉토리 구조

```plaintext
/rag_fastapi_project
|
├── main.py                     # FastAPI 앱 실행 및 스케줄러(Scheduler) 설정
├── .env                        # 환경 변수 (API Key, DB 설정, 크롤링 계정 등)
├── requirements.txt            # 의존성 패키지 목록
|
├── core/
│   └── config.py               # 프로젝트 설정 관리
|
├── models/
│   └── llm_factory.py          # LLM 및 Embedding 모델 인스턴스 생성
|
├── routers/
│   ├── chat_router.py          # RAG 챗봇 API
│   ├── processing_router.py    # PDF 처리 및 벡터 DB 관리 API
│   ├── ocr_router.py           # 성적표 OCR 분석 API
│   └── crawling_router.py      # [NEW] 크롤링 수동 실행 API
|
├── services/
│   ├── chat_service.py         # 질문 파싱 및 답변 생성 로직 (하이브리드 검색)
│   ├── file_processing_service.py # PDF -> MD/TXT/HTML 변환 파이프라인
│   ├── vector_store_service.py # ChromaDB 저장 및 검색 로직 (메타데이터 필터링)
│   ├── ocr_processing_service.py  # [Updated] EasyOCR 기반 성적표 파싱
│   └── crawling_service.py     # [NEW] Selenium 공지사항 크롤링 및 파일 다운로드
|
├── schemas/
│   └── chat_schema.py          # Pydantic 데이터 모델
|
├── uploads/                    # (자동 생성) 파일 처리용 임시 저장소
└── chroma_db_combined/         # (자동 생성) 벡터 DB 저장소
```

## 3. API 명세

모든 API는 `http://127.0.0.1:8000/api/v1` 접두사를 가집니다.

### 🛠️ File Processing & DB
* **POST** `/processing/process-pdf-full-and-build-db`
    * PDF를 업로드하여 변환(MD, TXT 등)하고, 지정된 컬렉션 이름으로 벡터 DB를 구축합니다.
    * **Params**: `collection_name` (필수)
* **POST** `/processing/process-pdf-only`
    * PDF를 업로드하여 변환만 수행합니다. (DB 구축 X, 중간 파일 확인용)
* **GET** `/processing/collections`
    * 현재 생성된 모든 벡터 DB 컬렉션 목록을 조회합니다.

### 💬 Chat
* **POST** `/chat/chat`
    * 구축된 문서를 바탕으로 질문에 답변합니다.
    * **특징**: 질문에 "학년:1", "이수구분:교양" 같은 패턴이 있으면 자동으로 **필터링 검색**을 수행하며, 일반 질문은 키워드 및 의미 검색을 병행합니다.

### 📄 OCR Processing
* **POST** `/ocr/extract-credits`
    * 성적표 PDF를 업로드하면 이수학점표를 OCR로 인식하여 JSON 결과를 반환합니다.
    * **Return Example**:
        ```json
        {
          "교양 필수": { "이수기준": 10, "취득학점": 10 },
          "기초전공": { "이수기준": 9, "취득학점": 9 },
          "졸업학점": 130,
          "취득학점": 140
          ...
        }
        ```

### 🕷️ Crawling (System)
* **POST** `/crawl/crawl-and-send-all-to-spring`
    * **(수동 트리거)** 즉시 공지사항을 크롤링하여 Spring 서버로 전송합니다.
    * **Note**: 평소에는 서버 내부의 스케줄러가 자동으로 이 작업을 수행하므로, 테스트나 긴급 동기화 시에만 사용합니다.

---

## 4. 설치 및 실행 방법

### 1. 환경 설정
프로젝트 루트에 `.env` 파일을 생성하고 다음 정보를 입력하세요.

```bash
# --- AI & API Keys ---
OPENAI_API_KEY=sk-...
LLAMA_CLOUD_API_KEY=llx-...
GOOGLE_API_KEY=...

# --- Crawling Account (학교 포털 정보) ---
CROWLING_ID=your_id
CROWLING_PW=your_password

# --- Spring Server Interaction ---
SPRING_SERVER_UPLOAD_URL=http://spring-server-ip:port/api/upload
CRAWLER_SECRET_KEY=secret_token_for_auth

# --- DB Path ---
DB_PATH=chroma_db_combined
```

### 2. 패키지 설치
Chrome 브라우저가 설치되어 있어야 합니다. (Selenium 구동용)

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 3. 서버 실행
FastAPI 서버를 실행하면 스케줄러도 함께 시작됩니다.

```bash
uvicorn main:app --reload
```

## 5. 자동화 시스템 동작 방식 (Scheduler)

이 서버는 `main.py` 실행 시 **APScheduler**가 백그라운드에서 동작합니다.

* **동작 시간**: 매일 **10:50, 14:50, 17:50, 23:50** (KST 기준)
* **프로세스**:
    1. 학교 포털 로그인
    2. 공지사항 게시판 접근 및 최신글 파싱
    3. 본문 텍스트, 이미지, 첨부파일 다운로드
    4. Spring 서버로 데이터 전송 (`multipart/form-data`)
    5. 임시 파일 삭제 및 로그 기록