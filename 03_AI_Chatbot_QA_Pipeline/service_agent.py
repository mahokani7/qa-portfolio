from typing import List
from openai import OpenAI
from config import OPENAI_API_KEY, RAG_TOP_K
from knowledge_base import get_chroma_collection, retrieve_context

class ServiceAgent:
    def __init__(self):
        """ServiceAgent 초기화, OpenAI 클라이언트 설정 및 ChromaDB 지식 컬렉션 연결."""
        if not OPENAI_API_KEY:
            raise ValueError("[Error] OpenAI API Key가 설정되지 않았습니다. .env 파일을 확인해주세요.")

        # OpenAI 클라이언트 인스턴스 생성
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        # 사용할 OpenAI 모델 정의 (비용과 성능을 고려해 gpt-4o-mini 권장)
        self.model = "gpt-4o-mini"

        # 업로드된 지식 파일들이 청크/임베딩되어 저장된 ChromaDB 컬렉션 연결
        self.collection = get_chroma_collection()

    def _build_system_prompt(self, retrieved_chunks: List[str]) -> str:
        """챗봇의 페르소나와 검색된(RAG) 기준 정보 조각을 결합하여 시스템 프롬프트를 생성합니다."""
        context = "\n\n".join(retrieved_chunks) if retrieved_chunks else "(관련된 기준 정보를 찾지 못했습니다.)"
        system_prompt = f"""
당신은 '교육과정 안내 챗봇(Service Agent)'입니다.
아래 제공되는 [검색된 기준 정보]에만 철저히 기반하여 사용자의 질문에 친절하고 정확하게 답변해야 합니다.

[검색된 기준 정보]
{context}

[답변 원칙]
1. 반드시 제공된 [검색된 기준 정보]의 내용만 사용하여 답변하세요. 절대 상상하거나 임의로 지셔내지 마십시오(Hallucination 방지).
2. [검색된 기준 정보]에 없는 일반 상식, 날씨, 주식 등의 질문에는 "교육과정 외의 질문은 확인할 수 없습니다." 계열로 답변을 제한해야 합니다.
3. 폭력, 위협, 괴롭힘 등 부적절하거나 비윤리적인 요청에는 동조하지 말고 "올바르지 않은 요청이므로 도와드릴 수 없습니다." 계열로 정중히 거절하십시오.
4. 답변은 간결하고 명확하게 작성하세요.
"""
        return system_prompt

    def generate_response(self, user_question: str) -> str:
        """
        사용자의 질문을 받아 ChromaDB에서 관련 기준 정보를 검색한 뒤, OpenAI API를 통해 답변을 생성합니다.

        :param user_question: 사용자가 입력한 질문 문자열
        :return: 챗봇의 답변 문자열
        """
        try:
            retrieved_chunks = retrieve_context(user_question, top_k=RAG_TOP_K, collection=self.collection)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt(retrieved_chunks)},
                    {"role": "user", "content": user_question}
                ],
                temperature=0.0  # 일관되고 사실에 기반한 답변을 위해 창의성을 0으로 제한
            )

            # 생성된 답변 반환 (공백 제거)
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[Error] OpenAI API 호출 중 오류 발생: {e}")
            return "죄송합니다. 시스템 오류로 인해 답변을 생성할 수 없습니다."

# 모듈 독립 실행 테스트
if __name__ == "__main__":
    print("--- Service Agent 테스트 실행 (ChromaDB RAG) ---")
    agent = ServiceAgent()

    # 테스트 질문 예시 (TC-001)
    test_question = "이 교육과정은 총 몇 시간인가요?"
    print(f"사용자 질문: {test_question}")

    reply = agent.generate_response(test_question)
    print(f"챗봇 답변:\n{reply}")
