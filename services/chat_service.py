# services/chat_service.py
import re
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_teddynote import logging
from services.vector_store_service import vector_store_service
from models.llm_factory import llm
from core.config import settings # ✨ 변경된 부분: 설정을 직접 가져오기 위해 import 추가

class ChatService:
    def __init__(self):
        logging.langsmith("RAG", set_enable=True)
        self.llm = llm
        self.template = """당신은 사용자의 질문에 답하는 AI 어시스턴트인 '용용이'입니다.

        다음 규칙을 엄격하게 준수하세요:
        1. 오직 제공된 "#Context:"에서 찾은 정보만을 사용하여 질문에 답변하세요.
        2. 만약 제공된 문맥에서 답변을 찾을 수 없다면, "제공된 정보 내에서는 답변을 찾을 수 없습니다."라고만 답변하세요.
        3. 당신이 자체적으로 학습한 지식은 절대로 사용하지 마세요.
        4. 답변은 한국어로 작성해 주세요.
        5. 제공된 문맥에는 여러 검색 결과가 포함될 수 있습니다. 사용자의 질문에 담긴 모든 조건(예: 학과, 학년, 요일 등)을 완벽하게 만족하는 결과만을 찾아내어 답변을 구성하세요
        
        #Question: 
        {question} 
        #Context: 
        {context} 

        #Answer:"""
        self.prompt = ChatPromptTemplate.from_template(self.template)

    # ⬇️ [신규 추가]
    # ⬇️ [수정] key_mapping과 if 조건을 사용자님 요구에 맞게 변경
    # ⬇️ [수정] where 필터와 where_document 필터를 분리하여 생성
    # ⬇️ [수정] '학년'을 metadata_keys -> document_keys로 이동
    def _parse_question_to_filter(self, question: str) -> (dict, dict, str):
        """
        질문을 (메타데이터 필터, 문서내용 필터, 순수 검색어) 튜플로 분리합니다.
        - '이수구분'만 $eq (메타데이터) 필터로 생성
        - 나머지는 $contains (문서 본문) 필터로 생성
        """
        
        # 1. 유연한 정규식 (이전과 동일)
        pattern = re.compile(r"('|\"|`)([^'\"]+)\1\s*:\s*('|\"|`)([^'\"]+)\3")
        matches = pattern.findall(question)
        
        if not matches:
            return None, None, question 

        # 2. DB의 메타데이터 키 매핑 (이전과 동일)
        key_mapping = {
            "이수구분": "이수구분",
            "학점": "학점 (인원)",
            "강의시간": "강의시간",
            "제목": "제목",
            "학년": "학년",
        }
        
        # 3. ⭐️ [변경] 필터링 전략 수정 (사용자님 최종 요청)
        #    $eq (정확히 일치)로 검색할 키 (메타데이터 필터)
        metadata_keys = ["이수구분"] # 👈 '학년' 제거
        #    $contains (포함)로 검색할 키 (문서 본문 필터)
        document_keys = ["학점", "강의시간", "제목", "학년"] # 👈 '학년' 추가

        metadata_conditions = []
        document_conditions = []

        for match in matches:
            key = match[1].strip()
            value = match[3].strip()
            
            mapped_key = key_mapping.get(key)
            if not mapped_key:
                print(f"⚠️ 매핑되지 않은 키 (무시): {key}")
                continue
                
            if key in metadata_keys:
                # 1. 메타데이터 필터($eq) 조건 추가
                metadata_conditions.append({mapped_key: {"$eq": value}})
            
            elif key in document_keys:
                # 2. 문서 본문 필터($contains) 로직
                #    'value' 자체를 포함하는지 검색 (예: "컴퓨터과학과", "1", "화")
                document_conditions.append({"$contains": value})
        
        # 4. 메타데이터 필터($eq) 생성 (이전과 동일)
        final_metadata_filter = None
        if len(metadata_conditions) == 1:
            final_metadata_filter = metadata_conditions[0]
        elif len(metadata_conditions) >= 2:
            # (이수구분 하나만 쓰므로 이 코드는 실행되지 않지만, 만약을 위해 둡니다)
            final_metadata_filter = {"$and": metadata_conditions}

        # 5. 문서 본문 필터($contains) 생성 (이전과 동일)
        final_document_filter = None
        if len(document_conditions) == 1:
            final_document_filter = document_conditions[0]
        elif len(document_conditions) >= 2:
            final_document_filter = {"$and": document_conditions} 

        # 6. 순수 검색어 추출 (이전과 동일)
        search_query = pattern.sub('', question).strip()
        if len(search_query) < 5:
            search_query = "과목 추천" 
            
        print(f"✅ 생성된 DB 'where' 필터: {final_metadata_filter}")
        print(f"✅ 생성된 DB 'where_document' 필터: {final_document_filter}")
        print(f"✅ 순수 검색어: {search_query}")
        
        if not final_metadata_filter and not final_document_filter:
            return None, None, question

        return final_metadata_filter, final_document_filter, search_query
    
    # ✨ 변경된 부분: get_answer 메서드에서 collection_name 인자를 제거합니다.
    # ⬇️ [수정]
    # ⬇️ [수정] 두 개의 필터를 받아서 retriever에 전달
    def get_answer(self, question: str) -> str:
        """질문에 대해 필터링된 컬렉션을 기반으로 답변을 생성합니다."""
        
        collection_name = settings.DEFAULT_DB_COLLECTION_NAME
        if not collection_name:
            raise ValueError("core/config.py에 DEFAULT_DB_COLLECTION_NAME이 설정되지 않았습니다.")

        # 1. 👈 [변경] 3개의 값을 반환받음
        metadata_filter, document_filter, search_query = self._parse_question_to_filter(question)

        # 2. 👈 [변경] 두 개의 필터를 모두 전달
        retriever = vector_store_service.get_retriever(
            collection_name, 
            metadata_filter=metadata_filter,
            document_filter=document_filter 
        )
        
        # 3. 순수 검색어로 문서 조회
        docs = retriever.invoke(search_query) 
        if not docs:
            return "요청하신 조건에 맞는 과목을 찾을 수 없습니다. 조건을 다시 확인해주세요."
        
        # 4. Chain 정의 (이전과 동일)
        chain = (
            {
                "context": (lambda x: search_query) | retriever, 
                "question": RunnablePassthrough() 
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        # 5. 원본 질문으로 Chain 실행
        response = chain.invoke(question)
        return response

chat_service = ChatService()