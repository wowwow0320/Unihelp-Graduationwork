# services/chat_service.py

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
        1. 오직 제공된 "#문맥:"에서 찾은 정보만을 사용하여 질문에 답변하세요.
        2. 만약 제공된 문맥에서 답변을 찾을 수 없다면, "제공된 정보 내에서는 답변을 찾을 수 없습니다."라고만 답변하세요.
        3. 당신이 자체적으로 학습한 지식은 절대로 사용하지 마세요.
        4. 답변은 한국어로 작성해 주세요.
        #Question: 
        {question} 
        #Context: 
        {context} 

        #Answer:"""
        self.prompt = ChatPromptTemplate.from_template(self.template)

    # ✨ 변경된 부분: get_answer 메서드에서 collection_name 인자를 제거합니다.
    def get_answer(self, question: str) -> str:
        """질문에 대해 기본 설정된 컬렉션을 기반으로 답변을 생성합니다."""
        
        # 1. 설정 파일(config.py)에서 기본 컬렉션 이름을 가져옵니다.
        collection_name = settings.DEFAULT_DB_COLLECTION_NAME
        if not collection_name:
            raise ValueError("core/config.py에 DEFAULT_DB_COLLECTION_NAME이 설정되지 않았습니다.")

        # 2. 해당 컬렉션 이름으로 retriever를 가져옵니다.
        retriever = vector_store_service.get_retriever(collection_name)
        
        docs = retriever.invoke(question)
        if not docs:
            return "모르겠습니다. 제가 제대로 이해하지 못했거나 챗봇에서 제공하지 않는 내용은 검색되지 않습니다."
        
        chain = (
            {"context": retriever, "question": RunnablePassthrough()}
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
        response = chain.invoke(question)
        return response

chat_service = ChatService()