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

    # ⬇️ [수정] 
    # ⬇️ 'key':'value' 유무에 따라 '키워드 $or 필터'와 'Key:Value 필터'로 분기하도록 
    # ⬇️ 함수 로직 전체를 재구성했습니다.
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
        
        # 3. ⭐️ [로직 수정] 'key':'value' 패턴(matches) 유무로 분기
        if not matches:
            # Case 1: 'key':'value' 패턴이 없는 일반 질문 (예: "체육학과 졸업요건")
            
            # 1-1. 질문을 공백 기준으로 단어로 분리
            keywords = question.split()
            if not keywords:
                return None, None, question # 빈 질문

            # 1-2. 각 단어를 $contains 조건으로 리스트 생성
            document_conditions = []
            for keyword in keywords:
                if len(keyword) > 1: # 1글자 단어 무시 (간단한 조사 필터링)
                    document_conditions.append({"$contains": keyword})
            
            # 1-3. ⭐️ [핵심] 이 조건들을 $or 로 묶음
            #      "체육학과" OR "졸업" OR "학점"
            #      하나의 키워드만 일치해도 필터링 후보에 포함됨.
            final_document_filter = None
            if len(document_conditions) == 1:
                final_document_filter = document_conditions[0]
            elif len(document_conditions) >= 2:
                final_document_filter = {"$or": document_conditions}
            
            if final_document_filter:
                print(f"✅ (키워드 $or 검색) 생성된 'where_document' 필터: {final_document_filter}")
            
            # 1-4. 메타데이터 필터는 없고, '문서 본문 필터'와 '원본 검색어' 반환
            #      (원본 검색어는 필터링된 결과 내에서 의미상 순위를 매길 때 사용됩니다)
            return None, final_document_filter, question
            
        else:
            # Case 2: 'key':'value' 패턴이 있는 필터 질문 (기존 로직)
            
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
            
            # 7. (기존 로직) 필터가 생성되었지만 비어있을 경우에 대한 예외 처리
            if not final_metadata_filter and not final_document_filter:
                 # 'key':'value'가 있었지만 매핑되는 키가 없어서 필터가 안 만들어진 경우
                 # 이 경우 순수 검색어(search_query)로만 검색
                 return None, None, search_query
                 
            return final_metadata_filter, final_document_filter, search_query
    
    # [수정 없음] get_answer 함수는 이미 하이브리드 검색을 지원하므로 수정할 필요가 없습니다.
    def get_answer(self, question: str) -> str:
        """질문에 대해 필터링된 컬렉션을 기반으로 답변을 생성합니다."""
        
        collection_name = settings.DEFAULT_DB_COLLECTION_NAME
        if not collection_name:
            raise ValueError("core/config.py에 DEFAULT_DB_COLLECTION_NAME이 설정되지 않았습니다.")

        # 1. 3개의 값을 반환받음 (새로운 로직이 적용됨)
        metadata_filter, document_filter, search_query = self._parse_question_to_filter(question)

        # 2. 두 개의 필터를 모두 전달
        retriever = vector_store_service.get_retriever(
            collection_name, 
            metadata_filter=metadata_filter,
            document_filter=document_filter 
        )
        
        # 3. 순수 검색어로 문서 조회
        #    (필터가 있다면 필터링된 결과 내에서, 없다면 전체에서 조회)
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