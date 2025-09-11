## 1. 프로젝트 소개

이 프로젝트는 복잡한 표(Table)가 포함된 PDF 문서를 기반으로 질문에 답변하는 **RAG (Retrieval-Augmented Generation) 챗봇**과, 특정 서식의 학점표를 **OCR(광학 문자 인식)**로 분석하는 기능을 FastAPI로 구현한 것입니다.

사용자는 두 가지 주요 기능을 API를 통해 사용할 수 있습니다:
1.  **문서 처리 및 RAG 챗봇**: PDF 파일을 업로드하면, 다단계 파이프라인을 통해 텍스트와 표 데이터를 추출하여 벡터 DB에 저장하고, 채팅 API를 통해 문서 내용에 대한 질문에 답변합니다.
2.  **학점표 OCR 분석**: 특정 형식의 PDF 학점표를 업로드하면, '이수학점 비교' 표를 자동으로 찾아 OCR로 분석하고, 구조화된 학점 정보를 JSON으로 반환합니다.

## 2. 주요 특징

* **🧠 다기능 처리 파이프라인**: 하나의 프로젝트 내에서 범용적인 RAG 데이터 처리와 특수 목적의 OCR 처리를 모두 지원합니다.
* **🤖 LlamaParse 활용**: PDF의 텍스트와 표를 지능적으로 분리하여 RAG 데이터의 품질을 높입니다.
* **📊 표 데이터 RAG 최적화**: 복잡한 표를 RAG가 이해하기 쉬운 "Key-Value" 형태의 문장으로 변환하여 검색 정확도를 극대화합니다.
* **👁️ EasyOCR 기반 학점 분석**: 특정 서식의 이미지 기반 테이블을 OCR로 정확하게 인식하고, 정해진 규칙에 따라 데이터를 파싱하여 JSON으로 구조화합니다.
* **🚀 FastAPI 기반 비동기 API**: 모든 기능을 비동기 방식으로 제공하여 높은 성능을 보장하며, 자동 API 문서를 통해 손쉽게 테스트할 수 있습니다.
* **📦 벡터 DB 관리 기능**: 컬렉션 목록 조회, 생성, 삭제 등 DB 관리를 위한 API를 제공하여 운영 편의성을 높입니다.

## 3. 디렉토리 구조


```
/rag_fastapi_project
|
├── main.py                     # FastAPI 앱 실행 파일
├── .env.example                # 환경 변수 설정 예시 파일
├── requirements.txt            # Python 패키지 의존성 목록
|
├── core/
│   └── config.py               # 프로젝트 설정
|
├── models/
│   └── llm_factory.py          # LLM 및 임베딩 모델 생성
|
├── routers/
│   ├── chat_router.py          # 채팅 API 라우터
│   ├── processing_router.py    # 문서 처리 및 DB 관리 API 라우터
│   └── ocr_router.py           # OCR 처리 API 라우터
|
├── schemas/
│   └── chat_schema.py          # API 요청/응답 데이터 모델
|
├── services/
│   ├── chat_service.py         # RAG 채팅 로직
│   ├── file_processing_service.py # PDF 처리 파이프라인 서비스
│   ├── ocr_processing_service.py  # PDF OCR 처리 서비스
│   └── vector_store_service.py # 벡터 DB 관리 서비스
|
├── uploads/                    # (자동 생성) 업로드 파일 저장
└── chroma_db_combined/         # (자동 생성) Chroma DB 저장
```

## 4. API 명세

모든 API는 `http://127.0.0.1:8000/api/v1` 접두사(prefix) 아래에 있습니다.

---
### Processing & DB Management

#### `POST /processing/process-pdf-full-and-build-db`
PDF 파일을 처리하여 모든 중간 파일(DOCX, MD, HTML, TXT)을 생성하고, 최종 결과물로 벡터 DB를 구축합니다.

* **Request**: `multipart/form-data`
    * `file`: 업로드할 PDF 파일
    * `collection_name` (str): 생성 또는 업데이트할 DB 컬렉션의 이름
* **Success Response** (200 OK):
    ```json
    {
      "message": "PDF 파일 처리 및 'my_collection' 벡터 DB 구축이 모두 완료되었습니다.",
      "source_file": "sample.pdf",
      "docx_file": "uploads/sample.docx",
      "markdown_file": "uploads/sample.md",
      "html_file": "uploads/sample.html",
      "rag_text_file": "uploads/sample.txt"
    }
    ```

#### `GET /processing/collections`
현재 Chroma DB에 저장되어 있는 모든 컬렉션의 목록을 조회합니다.

* **Success Response** (200 OK):
    ```json
    {
      "collections": [
        "2024_report",
        "manual_v1",
        "langchain"
      ]
    }
    ```

---
### OCR Processing

#### `POST /ocr/extract-credits`
PDF 성적표 파일을 OCR로 분석하여 학점 정보를 JSON으로 반환합니다. 작업 완료 후 서버에 업로드된 원본 PDF는 자동으로 삭제됩니다.

* **Request**: `multipart/form-data`
    * `file`: 업로드할 PDF 학점표 파일
* **Success Response** (200 OK):
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
        "이수기준": 54,
        "취득학점": 60
      },
      "복수,부,연계전공 기초전공": {
        "이수기준": null,
        "취득학점": null
      },
      "복수,부,연계전공 최소전공이수학점": {
        "이수기준": null,
        "취득학점": null
      },
      "졸업학점": 130,
      "취득학점": 140,
      "편입인정학점": 0
    }
    ```

---
### Chat

#### `POST /chat/chat`
문서 내용에 대해 질문하고 답변을 받습니다. `core/config.py`에 설정된 기본 컬렉션을 대상으로 질문합니다.

* **Request**: `application/json`
    ```json
    {
      "question": "컴퓨터공학과의 교양필수 과목은 무엇인가요?"
    }
    ```
* **Success Response** (200 OK):
    ```json
    {
      "answer": "컴퓨터공학과의 교양필수 과목은 '미적분학', '확률과통계', '공학작문및발표' 입니다."
    }
    ```

## 5. 설치 및 실행 방법

1.  **프로젝트 복제**
    ```bash
    git clone <repository_url>
    cd rag_fastapi_project
    ```

2.  **가상환경 생성 및 활성화**
    ```bash
    python -m venv venv
    source venv/bin/activate  # macOS/Linux
    # venv\Scripts\activate  # Windows
    ```

3.  **의존성 패키지 설치**
    ```bash
    pip install -r requirements.txt
    ```

4.  **환경 변수 설정 (`.env` 파일 생성)**
    프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 채워주세요. (`.env.example` 파일을 복사하여 사용)

    ```env
    # OpenAI API 키
    OPENAI_API_KEY="sk-..."

    # LlamaParse API 키
    LLAMA_CLOUD_API_KEY="ll-..."

    # LangSmith 추적을 위한 API 키 (선택 사항)
    LANGCHAIN_API_KEY="ls__..."
    LANGCHAIN_TRACING_V2="true"
    LANGCHAIN_PROJECT="RAG"
    ```

5.  **기본 DB 컬렉션 설정 (`core/config.py`)**
    `/chat` API가 기본으로 사용할 DB 컬렉션 이름을 `core/config.py` 파일에 지정해야 합니다.

    ```python
    # core/config.py
    class Settings:
        # ...
        # 👇 여기에 문서 처리 시 사용한 collection_name을 지정하세요.
        DEFAULT_DB_COLLECTION_NAME: str = "my_collection"
    ```

6.  **서버 실행**
    ```bash
    uvicorn main:app --reload
    ```

7.  **API 문서 확인**
    서버 실행 후, 웹 브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하면 Swagger UI를 통해 모든 API를 테스트할 수 있습니다.

## 6. 사용 워크플로우 예시

1.  **서버를 실행합니다.**
2.  **컬렉션 목록 확인**: `GET /api/v1/processing/collections`를 호출하여 현재 DB에 어떤 컬렉션이 있는지 확인합니다.
3.  **DB 구축**: `POST /api/v1/processing/process-pdf-full-and-build-db`에 분석할 PDF 파일과 새로 만들거나 추가할 `collection_name`을 지정하여 요청을 보냅니다.
4.  **채팅 기본 컬렉션 설정**: DB 구축에 사용한 `collection_name`을 `core/config.py`의 `DEFAULT_DB_COLLECTION_NAME` 값으로 설정한 후, 서버를 재시작합니다.
5.  **질문하기**: `POST /api/v1/chat/chat`에 문서 내용에 대한 질문을 보내 답변을 확인합니다.
6.  **(별도 기능) 학점 분석**: `POST /api/v1/ocr/extract-credits`에 학점표 PDF를 업로드하여 분석 결과를 JSON으로 받습니다.