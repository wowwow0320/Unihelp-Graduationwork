# services/chat_service.py
import re
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_teddynote import logging
from services.vector_store_service import vector_store_service
from models.llm_factory import llm
from core.config import settings

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

    # ⬇️ [CPU 연산 로직] 
    # 이 함수는 I/O(네트워크/디스크) 작업이 없는 순수 문자열 연산이므로 
    # async를 붙이지 않아도 됩니다. (async 함수 내부에서 일반 함수 호출 가능)
    def _parse_question_to_filter(self, question: str) -> (dict, dict, str):
        """
        질문을 (메타데이터 필터, 문서내용 필터, 순수 검색어) 튜플로 분리합니다.
        - 1. 'key':'value' 패턴이 없으면: 질문을 단어 단위로 쪼개 $or 필터 생성
        - 2. 'key':'value' 패턴이 있으면: 해당 $eq, $contains 필터 생성
        """
        
        # 1. 'key':'value' 정규식
        pattern = re.compile(r"('|\"|`)([^'\"]+)\1\s*:\s*('|\"|`)([^'\"]+)\3")
        matches = pattern.findall(question)
        
        # 2. DB 키 매핑 및 필터 전략 (공통)
        key_mapping = {
            "이수구분": "이수구분",
            "학점": "학점 (인원)",
            "강의시간": "강의시간",
            "제목": "제목",
            "학년": "학년",
        }
        metadata_keys = ["이수구분"] # $eq (메타데이터) 필터
        document_keys = ["학점", "강의시간", "제목", "학년"] # $contains (문서 본문) 필터
        
        # 3. 'key':'value' 패턴(matches) 유무로 분기
        if not matches:
            # Case 1: 'key':'value' 패턴이 없는 일반 질문
            
            # 1-1. 질문을 공백 기준으로 단어로 분리
            keywords = question.split()
            if not keywords:
                return None, None, question # 빈 질문

            # 1-2. 각 단어를 $contains 조건으로 리스트 생성
            document_conditions = []
            for keyword in keywords:
                if len(keyword) > 1: # 1글자 단어 무시
                    document_conditions.append({"$contains": keyword})
            
            # 1-3. 이 조건들을 $or 로 묶음
            final_document_filter = None
            if len(document_conditions) == 1:
                final_document_filter = document_conditions[0]
            elif len(document_conditions) >= 2:
                final_document_filter = {"$or": document_conditions}
            
            if final_document_filter:
                print(f"✅ (키워드 $or 검색) 생성된 'where_document' 필터: {final_document_filter}")
            
            return None, final_document_filter, question
            
        else:
            # Case 2: 'key':'value' 패턴이 있는 필터 질문
            
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
                    metadata_conditions.append({mapped_key: {"$eq": value}})
                elif key in document_keys:
                    document_conditions.append({"$contains": value})
            
            # 4. 메타데이터 필터($eq) 생성
            final_metadata_filter = None
            if len(metadata_conditions) == 1:
                final_metadata_filter = metadata_conditions[0]
            elif len(metadata_conditions) >= 2:
                final_metadata_filter = {"$and": metadata_conditions}
                
            # 5. 문서 본문 필터($contains) 생성
            final_document_filter = None
            if len(document_conditions) == 1:
                final_document_filter = document_conditions[0]
            elif len(document_conditions) >= 2:
                final_document_filter = {"$and": document_conditions}
                
            # 6. 순수 검색어 추출
            search_query = pattern.sub('', question).strip()
            if len(search_query) < 5:
                search_query = "과목 추천"
            
            print(f"✅ (Key:Value 필터 검색) 생성된 'where' 필터: {final_metadata_filter}")
            print(f"✅ (Key:Value 필터 검색) 생성된 'where_document' 필터: {final_document_filter}")
            print(f"✅ (Key:Value 필터 검색) 순수 검색어: {search_query}")
            
            if not final_metadata_filter and not final_document_filter:
                 return None, None, search_query
                 
            return final_metadata_filter, final_document_filter, search_query
    
    # ⬇️ [비동기 적용 핵심 부분]
    # async def로 변경하고 내부의 모든 I/O 호출을 await ... ainvoke로 변경
    async def get_answer(self, question: str) -> str:
        """질문에 대해 필터링된 컬렉션을 기반으로 답변을 생성합니다."""
        
        collection_name = settings.DEFAULT_DB_COLLECTION_NAME
        if not collection_name:
            raise ValueError("core/config.py에 DEFAULT_DB_COLLECTION_NAME이 설정되지 않았습니다.")

        # 1. 3개의 값을 반환받음
        metadata_filter, document_filter, search_query = self._parse_question_to_filter(question)

        # 2. 두 개의 필터를 모두 전달 (Retriever 생성 자체는 빠르므로 동기 실행)
        retriever = vector_store_service.get_retriever(
            collection_name, 
            metadata_filter=metadata_filter,
            document_filter=document_filter 
        )
        
        # 3. ✨ [수정됨] 순수 검색어로 문서 조회 (비동기 처리)
        #    retriever.invoke() -> await retriever.ainvoke()
        #    벡터 DB 검색 시간 동안 서버가 멈추지 않게 함
        docs = await retriever.ainvoke(search_query) 
        
        if not docs:
            return "요청하신 조건에 맞는 과목을 찾을 수 없습니다. 조건을 다시 확인해주세요."
        
        # 4. Chain 정의
        #    (여기서 retriever는 나중에 chain.ainvoke() 될 때 내부적으로 비동기 실행됨)
        chain = (
            {
                "context": (lambda x: search_query) | retriever, 
                "question": RunnablePassthrough() 
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        
        # 5. ✨ [수정됨] Chain 실행 (비동기 처리)
        #    chain.invoke() -> await chain.ainvoke()
        #    LLM 답변 생성 시간(수 초) 동안 다른 요청 처리가 가능해짐
        response = await chain.ainvoke(question)
        return response

chat_service = ChatService()