# services/vector_store_service.py

from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from core.config import settings
from models.llm_factory import embedding_model
from typing import List, Optional, Dict, Any  # 👈 [수정]

class VectorStoreService:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self.embedding_model = embedding_model

    def _load_db(self, collection_name: str) -> Chroma:
        if not collection_name:
            raise ValueError("Collection name must be provided.")
        return Chroma(
            persist_directory=self.db_path,
            embedding_function=self.embedding_model,
            collection_name=collection_name
        )

    def _process_markdown_file(self, file_path: str) -> list[Document]:
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()
        headers_to_split_on = [("#", "Header 1")]
        markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
        md_header_splits = markdown_splitter.split_text(docs[0].page_content)
        char_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        return char_splitter.split_documents(md_header_splits)


    def _process_table_text_file(self, file_path: str) -> list[Document]:
        """
        'Key: Value' 형태의 텍스트 파일을 한 줄씩 읽어,
        - 원본 텍스트 전체는 page_content에 저장하고,
        - 파싱된 Key:Value 쌍은 metadata에 동적으로 저장합니다.
        """
        documents = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # 1. 원본 한 줄을 그대로 page_content로 사용합니다.
                #    이렇게 하면 의미 기반 검색 시 모든 정보를 활용할 수 있습니다.
                page_content = line.strip()
                if not page_content:
                    continue

                try:
                    # 2. 메타데이터 딕셔너리를 동적으로 생성합니다.
                    metadata = {}
                    parts = page_content.split(', ')
                    for part in parts:
                        if ': ' in part:
                            key, value = part.split(': ', 1)
                            metadata[key.strip()] = value.strip()
                    
                    # 3. page_content와 동적으로 생성된 metadata로 Document 객체를 만듭니다.
                    documents.append(Document(page_content=page_content, metadata=metadata))
                
                except Exception as e:
                    print(f"⚠️ 한 줄을 메타데이터로 파싱하는 중 오류가 발생했습니다 (건너뜁니다): {page_content}")
                    print(f"   오류 내용: {e}")

        return documents

    def build_from_files(self, md_path: str, txt_path: str, collection_name: str):
        db = self._load_db(collection_name)
        md_chunks = self._process_markdown_file(md_path)
        txt_chunks = self._process_table_text_file(txt_path)
        all_chunks = md_chunks + txt_chunks

        if not all_chunks:
            print("처리할 데이터가 없습니다.")
            return

        batch_size = 64
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            db.add_documents(batch)
            print(f"-> {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}개 문서 처리 완료...")
        
        print(f"\n🎉 컬렉션 '{collection_name}'의 Chroma DB 업데이트가 성공적으로 완료되었습니다!")
    
    # DB에 저장된 모든 컬렉션 목록을 반환하는 메서드
    def list_collections(self) -> List[str]:
        """
        Chroma DB에 저장된 모든 컬렉션의 이름 목록을 반환합니다.
        """
        # 특정 컬렉션 이름 없이 Chroma 클라이언트에 연결
        client = Chroma(
            persist_directory=self.db_path,
            embedding_function=self.embedding_model
        )
        
        collections = client._client.list_collections()
        
        # 컬렉션 객체 리스트에서 이름만 추출하여 반환
        return [col.name for col in collections] if collections else []

    # def get_retriever(self, collection_name: str):
    #     db = self._load_db(collection_name)
    #     return db.as_retriever(
    #         search_type="mmr",
    #         search_kwargs={"k": 10, "lambda_mult": 0.9, "fetch_k": 20}
    #     )
    # ⬇️ [수정]
    # ⬇️ [수정] metadata_filter와 document_filter를 모두 받도록 변경
    def get_retriever(
        self, 
        collection_name: str, 
        metadata_filter: Optional[Dict[str, Any]] = None,
        document_filter: Optional[Dict[str, Any]] = None  # 👈 [추가]
    ):
        db = self._load_db(collection_name)
        
        search_kwargs = {
            "k": 20
        }
        search_type = "similarity" 
            
        # 1. [추가] 메타데이터 필터 (where)
        if metadata_filter:
            search_kwargs["filter"] = metadata_filter
        
        # 2. [추가] 문서 본문 필터 (where_document)
        if document_filter:
            search_kwargs["where_document"] = document_filter # 👈 [추가]

        return db.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )
vector_store_service = VectorStoreService()