# 📚 PDF 문서 기반 RAG 챗봇 API 서버

## 1. 프로젝트 소개

이 프로젝트는 복잡한 표(Table)가 포함된 PDF 문서를 기반으로 질문에 답변하는 **RAG (Retrieval-Augmented Generation) 챗봇**을 FastAPI로 구현한 것입니다.

사용자가 PDF 파일을 업로드하면, 서버는 다단계 문서 처리 파이프라인을 통해 문서의 텍스트와 표 데이터를 추출하고, 이를 검색에 용이한 형태로 가공하여 벡터 데이터베이스(Chroma DB)에 저장합니다. 이후 사용자는 채팅 API를 통해 문서 내용에 관한 질문을 하고, RAG 기술을 통해 정확도 높은 답변을 얻을 수 있습니다.

## 2. 주요 특징

* **🧠 다단계 문서 처리 파이프라인**: `PDF` → `DOCX` → `HTML` → `RAG 최적화 TXT`로 이어지는 체계적인 변환 과정을 통해 정보 손실을 최소화하고 데이터 품질을 극대화합니다.
* **🤖 LlamaParse 활용**: LlamaIndex의 LlamaParse를 사용하여 PDF의 텍스트와 표를 지능적으로 분리하고 추출합니다.
* **📊 표 데이터 RAG 최적화**: 복잡한 표 구조를 RAG가 이해하기 쉬운 "Key-Value" 형태의 문장으로 변환하여, 표 내용에 대한 질문에 정확하게 답변할 수 있습니다.
* **🚀 FastAPI 기반 비동기 API**: FastAPI를 사용하여 문서 처리 및 채팅 기능을 비동기 방식으로 제공하여 높은 성능을 보장합니다.
* **📦 벡터 DB 자동 구축**: 처리된 텍스트와 표 데이터를 자동으로 임베딩하여 Chroma DB에 저장하고, 검색을 위한 Retriever를 구성합니다.

## 3. 디렉토리 구조

```
/rag_fastapi_project
|
├── main.py             # FastAPI 앱 실행 파일
├── .env                # 환경 변수 설정 파일
├── requirements.txt    # Python 패키지 의존성 목록
├── README.md           # 프로젝트 설명서
├── .gitignore
|
├── core/
│   └── config.py       # 프로젝트 설정 (DB 경로, 기본 컬렉션 이름 등)
|
├── models/
│   └── llm_factory.py  # LLM 및 임베딩 모델 생성
|
├── routers/
│   ├── chat_router.py  # 채팅 관련 API 라우터
│   └── processing_router.py  # 문서 처리 및 DB 구축 API 라우터
|
├── schemas/
│   └── chat_schema.py  # API 요청/응답 데이터 모델 (Pydantic)
|
├── services/
│   ├── chat_service.py  # RAG 체인 및 채팅 로직
│   ├── file_processing_service.py  # PDF 처리 파이프라인 서비스
│   └── vector_store_service.py     # 벡터 DB 관리 서비스
|
├── uploads/  (자동 생성)  # 업로드된 파일이 저장되는 디렉토리 (자동 생성)
└── chroma_db_combined/ (자동 생성) # Chroma DB 파일이 저장되는 디렉토리 (자동 생성)
```

## 4. 핵심 동작 원리 (파일 처리 파이프라인)

본 프로젝트의 핵심은 업로드된 PDF를 RAG에 가장 적합한 형태로 가공하는 4단계 파이프라인입니다.

1.  **1단계: `PDF` → `DOCX`**
    * `pdf2docx` 라이브러리를 사용해 원본 PDF를 DOCX 형식으로 변환합니다. 이는 후속 단계에서 표와 텍스트의 구조적 무결성을 유지하는 데 도움이 됩니다.

2.  **2단계: `PDF` → `Markdown` (텍스트 추출)**
    * `LlamaParse`를 사용하여 PDF에서 표를 제외한 순수 텍스트만 추출하여 Markdown 파일로 저장합니다. 이 텍스트는 문서의 일반적인 문맥 정보를 제공하는 데 사용됩니다.

3.  **3단계: `DOCX` → `HTML` (표 구조화)**
    * 1단계에서 생성된 DOCX를 HTML로 변환합니다. 이 과정은 복잡한 표의 행(row), 열(column), 병합된 셀(cell) 구조를 명확하게 보존하는 데 매우 효과적입니다.

4.  **4단계: `HTML` → `RAG 최적화 TXT` (표 데이터 문장 변환)**
    * 3단계의 HTML에서 테이블 데이터를 `pandas`로 읽어옵니다.
    * 각 **테이블의 한 행(row)**을 정보 단위로 보고, `제목: [표 제목], 열1: [값1], 열2: [값2], ...` 와 같은 **하나의 완전한 문장으로 변환**합니다.
    * 이 방식은 벡터 검색 시 표의 특정 행에 대한 정보가 하나의 단위로 묶여 검색되도록 하여 RAG의 성능을 극대화합니다.

5.  **5단계: 벡터 DB 구축**
    * 2단계에서 생성된 `Markdown` (일반 텍스트)과 4단계에서 생성된 `TXT` (표 데이터 문장)를 함께 임베딩하여 지정된 `collection_name`으로 Chroma DB에 저장합니다.

## 5. API 명세

### 문서 처리 및 DB 구축

PDF 파일을 처리하고 벡터 DB를 생성합니다.

* **Endpoint**: `/process-pdf-full-and-build-db`
* **Method**: `POST`
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

### 챗봇 답변 받기

문서 내용에 대해 질문하고 답변을 받습니다.

* **Endpoint**: `/chat`
* **Method**: `POST`
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

## 6. 설치 및 실행 방법

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
    프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 채워주세요.

    ```env
    # LlamaParse API 키
    LLAMA_CLOUD_API_KEY="ll-..."

    # 사용하는 LLM의 API 키 (예: OpenAI)
    OPENAI_API_KEY="sk-..."

    # LangSmith 추적을 위한 API 키 (선택 사항)
    LANGCHAIN_API_KEY="ls__..."
    LANGCHAIN_TRACING_V2="true"
    LANGCHAIN_PROJECT="RAG"
    ```

5.  **기본 DB 컬렉션 설정 (`core/config.py`)**
    `chat` API가 기본으로 사용할 DB 컬렉션 이름을 `core/config.py` 파일에 지정해야 합니다.

    ```python
    # core/config.py
    
    from pydantic_settings import BaseSettings

    class Settings(BaseSettings):
        DB_PATH: str = "chroma_db_combined"
        # 👇 여기에 문서 처리 시 사용한 collection_name을 지정하세요.
        DEFAULT_DB_COLLECTION_NAME: str = "my_collection"

    settings = Settings()
    ```

6.  **서버 실행**
    ```bash
    uvicorn main:app --reload
    ```

7.  **API 문서 확인**
    서버 실행 후, 웹 브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하면 Swagger UI를 통해 API를 테스트할 수 있습니다.

## 7. 사용 방법

1.  Uvicorn 서버를 실행합니다.
2.  API 클라이언트(Postman, Swagger UI 등)를 사용하여 `POST /process-pdf-full-and-build-db` 엔드포인트에 PDF 파일과 `collection_name`을 전송하여 문서를 처리하고 DB를 구축합니다.
3.  **`core/config.py`** 파일의 `DEFAULT_DB_COLLECTION_NAME` 값을 방금 사용한 `collection_name`으로 설정하고 서버를 재시작합니다.
4.  `POST /chat` 엔드포인트에 문서 내용과 관련된 질문을 JSON 형식으로 전송합니다.
5.  AI가 생성한 답변을 확인합니다.