# PDF 기반 RAG 챗봇 API (FastAPI)

이 프로젝트는 FastAPI를 사용하여 PDF 문서의 내용을 기반으로 질문에 답변하는 RAG(Retrieval-Augmented Generation) 챗봇 API를 구축합니다. 사용자는 PDF 파일을 업로드하여 고유한 이름의 '컬렉션'을 생성할 수 있으며, 개발자는 설정 파일에서 특정 컬렉션을 지정하여 챗봇의 지식 베이스로 사용할 수 있습니다.

## ✨ 주요 기능

* **동적 지식 베이스**: PDF 파일을 업로드하여 여러 개의 독립된 지식 컬렉션을 생성하고 관리할 수 있습니다.
* **MVC 유사 아키텍처**: `routers`, `services`, `models` 등 서비스 지향적인 구조로 코드를 구성하여 유지보수와 확장이 용이합니다.
* **쉬운 지식 베이스 전환**: 개발자는 `.env` 파일의 `DEFAULT_DB_COLLECTION_NAME` 값 변경만으로 챗봇이 사용하는 지식 베이스를 손쉽게 전환할 수 있습니다.
* **자동화된 문서 처리**: PDF에서 텍스트와 테이블을 추출하여 RAG에 최적화된 형식으로 자동 변환하고 벡터 DB에 저장합니다.
* **API 문서 자동 생성**: FastAPI의 내장 기능을 통해 `http://127.0.0.1:8000/docs`에서 Swagger UI 문서를 제공합니다.

---

## 🚀 시작하기

이 섹션에서는 프로젝트를 로컬 환경에서 설정하고 실행하는 방법을 안내합니다.

### 1. 사전 요구사항

* **Python 3.9 이상**: [Python 공식 웹사이트](https://www.python.org/downloads/)에서 설치할 수 있습니다.
* **API 키**:
    * **OpenAI API Key**: [OpenAI 웹사이트](https://platform.openai.com/api-keys)에서 발급받으세요.
    * **LlamaParse API Key**: [LlamaCloud](https://cloud.llamaindex.ai/)에 가입하여 발급받으세요. (PDF 파싱에 사용됩니다.)

### 2. 프로젝트 설정

#### (1) 가상 환경 생성 및 활성화

프로젝트 의존성을 시스템의 다른 프로젝트와 격리하기 위해 가상 환경을 생성하고 활성화합니다.

```bash
# 1. 'venv'라는 이름의 가상 환경 생성
python -m venv venv

# 2. 가상 환경 활성화
# Windows의 경우
.\venv\Scripts\activate
# macOS / Linux의 경우
source venv/bin/activate
```

가상 환경이 활성화되면 터미널 프롬프트 앞에 `(venv)`가 표시됩니다.

#### (2) 의존성 라이브러리 설치

프로젝트에 필요한 모든 라이브러리를 `requirements.txt` 파일을 이용해 한 번에 설치합니다.

```bash
pip install -r requirements.txt
```

#### (3) 환경 변수 설정 (`.env` 파일)

프로젝트 최상위 경로에 `.env` 파일을 생성하고 아래 내용을 복사하여 붙여넣으세요. 그리고 **실제 API 키를 입력**해야 합니다.

```text
# .env

# --- AI Model Selection ---
DEFAULT_MODEL="OPENAI"

# --- API Keys ---
OPENAI_API_KEY="sk-..."
LLAMA_CLOUD_API_KEY="ll-..."

# --- DB Collection ---
# 채팅 API에서 사용할 기본 컬렉션 이름입니다.
# 개발자가 이 값을 직접 수정하여 챗봇의 지식 베이스를 변경할 수 있습니다.
DEFAULT_DB_COLLECTION_NAME="lecture-2025-2"
```

### 3. 서버 실행

모든 설정이 완료되었습니다. 이제 아래 명령어로 FastAPI 개발 서버를 실행합니다.

```bash
uvicorn main:app --reload
```

서버가 성공적으로 실행되면 웹 브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하여 API 문서를 확인하고 테스트할 수 있습니다.

---

## ⚙️ Git Ignore 설정 (`.gitignore`)

프로젝트를 Git으로 관리할 때, 민감한 정보(API 키), 불필요한 파일, 자동으로 생성되는 데이터가 저장소에 포함되지 않도록 `.gitignore` 파일을 설정하는 것이 매우 중요합니다. 프로젝트 최상위 경로에 **`.gitignore`** 라는 이름의 파일을 생성하고 아래 내용을 복사하여 붙여넣으세요.

```gitignore
# ---------------------------------
# .gitignore
# ---------------------------------

# 환경 변수 파일
# API 키와 같은 민감한 정보가 포함되어 있으므로 절대 Git에 올리면 안 됩니다.
.env

# Python 가상 환경 폴더
# 각자의 컴퓨터 환경에 따라 내용이 다르며, requirements.txt를 통해 재생성해야 합니다.
venv/
/venv/

# Python 캐시 및 컴파일 파일
# 자동으로 생성되는 불필요한 파일입니다.
__pycache__/
*.pyc

# 자동 생성 데이터 폴더
# 사용자가 업로드한 파일과 생성된 벡터 DB는 소스 코드가 아닙니다.
uploads/
chroma_db_combined/

# IDE / 편집기 설정 파일
# 개인의 개발 환경 설정을 공유할 필요는 없습니다.
.vscode/
.idea/

# macOS 시스템 파일
.DS_Store
```

---

## 📖 API 사용 가이드

API는 크게 두 가지 기능을 제공합니다: **PDF 처리 및 DB 구축**과 **채팅**.

### 1단계: PDF 처리 및 지식 컬렉션 구축

먼저 질문의 기반이 될 PDF 파일을 업로드하여 벡터 DB에 지식 컬렉션을 만들어야 합니다. 이 엔드포인트는 파일과 텍스트 데이터를 함께 전송하기 위해 **`multipart/form-data`** 형식을 사용합니다.

* **Endpoint**: `POST /api/v1/processing/process-pdf`
* **요청 형식**: `multipart/form-data`
* **폼 필드 (Form Fields)**:
    * `collection_name` (string, 필수): 생성할 지식 컬렉션의 고유한 이름.
    * `file` (file, 필수): 업로드할 PDF 파일.
* **`curl` 예시**:

    ```bash
    curl -X 'POST' \
      '[http://127.0.0.1:8000/api/v1/processing/process-pdf](http://127.0.0.1:8000/api/v1/processing/process-pdf)' \
      -H 'accept: application/json' \
      -F 'collection_name=lecture-2025-2' \
      -F 'file=@/경로/내/파일.pdf'
    ```

> #### 💡 상세 사용법: UI로 쉽게 파일 업로드하기
>
> `curl` 명령어가 익숙하지 않다면, 서버 실행 후 `http://127.0.0.1:8000/docs`에 접속하세요. `POST /api/v1/processing/process-pdf` 항목을 열고 "Try it out" 버튼을 누르면 웹 화면에서 직접 컬렉션 이름을 입력하고 파일을 선택하여 테스트할 수 있습니다.
> 

### 2단계: 채팅 (질의응답)

지식 컬렉션 구축이 완료되면, `.env` 파일에 설정된 컬렉션을 대상으로 질문할 수 있습니다. 이 엔드포인트는 텍스트 데이터만 주고받으므로 **`application/json`** 형식을 사용합니다.

* **Endpoint**: `POST /api/v1/chat/chat`
* **요청 형식**: `application/json`
* **요청 본문 (JSON)**:

    ```json
    {
      "question": "컴퓨터과학과 졸업 요건에 대해서 알려줘."
    }
    ```
* **`curl` 예시**:

    ```bash
    curl -X 'POST' \
      '[http://127.0.0.1:8000/api/v1/chat/chat](http://127.0.0.1:8000/api/v1/chat/chat)' \
      -H 'accept: application/json' \
      -H 'Content-Type: application/json' \
      -d '{
      "question": "컴퓨터과학과 졸업 요건에 대해서 알려줘."
    }'
    ```

---

## 🤔 문제 해결 (Troubleshooting)

#### `422 Unprocessable Entity` 오류가 발생하나요?

이 오류는 API로 보낸 요청 데이터의 형식이 잘못되었을 때 발생합니다. 주로 JSON 문법 오류가 원인입니다.

* **❌ 잘못된 예시 (마지막에 쉼표가 있음):** `{ "question": "질문 내용.", }`
* **❌ 잘못된 예시 (값의 시작 따옴표가 없음):** `{ "question": 질문 내용" }`
* **✅ 올바른 예시:** `{ "question": "질문 내용" }`

#### `ModuleNotFoundError` 오류가 발생하나요?

필수 라이브러리가 설치되지 않았다는 의미입니다. 아래 사항을 확인하세요.

1.  **가상 환경(`venv`)이 활성화**되어 있는지 확인하세요.
2.  `pip install -r requirements.txt` 명령어로 모든 라이브러리가 잘 설치되었는지 확인하세요.

---

## 📂 프로젝트 구성

### 최종 `requirements.txt`

```text
# requirements.txt
fastapi
uvicorn[standard]
python-dotenv
pdf2docx
llama-parse
python-docx
beautifulsoup4
pandas
lxml
html5lib
langchain
langchain-openai
langchain-chroma
langchain-teddynote
scikit-learn
tiktoken
langchain-community
python-multipart
```

### 디렉토리 구조

```
/rag_fastapi_project
|
├── main.py
├── .env
├── requirements.txt
├── README.md
├── .gitignore
|
├── core/
│   └── config.py
|
├── models/
│   └── llm_factory.py
|
├── routers/
│   ├── chat_router.py
│   └── processing_router.py
|
├── schemas/
│   └── chat_schema.py
|
├── services/
│   ├── chat_service.py
│   ├── file_processing_service.py
│   └── vector_store_service.py
|
├── uploads/  (자동 생성)
└── chroma_db_combined/ (자동 생성)
```