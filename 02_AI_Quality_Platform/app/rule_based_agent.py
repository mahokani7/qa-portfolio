"""
rule_based_agent.py
- 규칙 기반 챗봇 (Rule-Based Agent)
- OpenAI API, ChromaDB, 임베딩 등 어떠한 외부 API도 호출하지 않고, 업로드된 지식 파일의 원문을
  키워드로 매칭/검색하는 결정론적(deterministic) 로직만으로 답변을 생성합니다.
- API 기반 챗봇(service_agent.py)과 동일한 테스트 케이스에 대한 답변 품질을 비교하기 위한 대조군입니다.
"""

import re
from typing import List

from app.knowledge_base import list_uploaded_knowledge_files, read_document_text

# 안전성 위험 요청을 감지하는 트리거 키워드 (최우선 검사)
SAFETY_KEYWORDS = [
    "해킹", "마비", "조작", "협박", "폭력", "괴롭힘", "불법", "위협",
    "죽이", "때리", "공격 스크립트", "탈취", "유출시켜",
]

# 교육과정 정보와 무관한 문서 외 질문을 감지하는 트리거 키워드
OFFTOPIC_KEYWORDS = [
    "날씨", "맛집", "점심", "저녁 메뉴", "주식", "파이썬", "코드", "list", "tuple", "일기예보",
]

# 도메인 카테고리별 트리거 키워드 (사용자 질문 의도 분류 + 지식 원문 검색에 동일하게 사용)
CATEGORY_KEYWORDS = {
    "교육시간": ["시간", "야간", "주말", "단축", "조기 수료"],
    "출결": ["지각", "조퇴", "외출", "결석", "출결"],
    "수료": ["수료", "출석률", "프로젝트", "과락"],
    "취업지원": ["취업", "이력서", "모의면접", "첨삭", "면접"],
}

REJECTION_SAFETY = "죄송하지만 올바르지 않은 요청이므로 도와드릴 수 없습니다."
REJECTION_OFFTOPIC = "교육과정 외의 질문은 확인할 수 없습니다."
NOT_FOUND_TEMPLATE = "'{category}' 관련 질문으로 보이나, 업로드된 지식 파일에서 관련 정보를 찾을 수 없습니다."


def _split_sentences(text: str) -> List[str]:
    """지식 원문을 줄바꿈과 문장부호 기준으로 분리해 검색 가능한 문장 목록으로 만듭니다."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sentences: List[str] = []
    for line in lines:
        for piece in re.split(r"(?<=[.!?])\s+", line):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


class RuleBasedAgent:
    def __init__(self):
        """업로드된 지식 파일 전체를 읽어 문장 단위로 보관합니다. (OpenAI/ChromaDB 미사용)"""
        self.knowledge_sentences: List[str] = []
        for file_path in list_uploaded_knowledge_files():
            try:
                text = read_document_text(file_path)
            except Exception:
                continue
            self.knowledge_sentences.extend(_split_sentences(text))

    def _classify_category(self, user_question: str) -> str:
        """키워드 매칭 횟수가 가장 많은 카테고리를 사용자 질문의 의도로 판별합니다."""
        best_category = ""
        best_hits = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            hits = sum(1 for kw in keywords if kw in user_question)
            if hits > best_hits:
                best_hits = hits
                best_category = category
        return best_category

    def _search_knowledge(self, category: str) -> str:
        """
        카테고리 트리거 키워드가 포함된 지식 원문 문장을 찾아 반환합니다. 없으면 빈 문자열.
        - '[출결 및 감점 규정]'처럼 섹션 제목 자체에 카테고리 키워드가 우연히 포함된 경우,
          제목만 매칭되고 실제 규정 문장이 가려지는 것을 막기 위해 제목 줄은 후보에서 제외합니다.
        - 매칭된 문장이 여러 개면 키워드 매칭 개수(밀도)가 높은 순으로 정렬한 뒤 모두 이어 붙여,
          핵심 키워드가 문장 하나에만 흩어져 있어 누락되는 것을 방지합니다.
        """
        keywords = CATEGORY_KEYWORDS.get(category, [])
        if not keywords:
            return ""

        scored = []
        for sentence in self.knowledge_sentences:
            if re.match(r"^\[.+\]$", sentence):
                continue
            hits = sum(1 for kw in keywords if kw in sentence)
            if hits > 0:
                scored.append((hits, sentence))

        if not scored:
            return ""

        scored.sort(key=lambda item: item[0], reverse=True)

        seen = set()
        matched_sentences = []
        for _, sentence in scored:
            if sentence not in seen:
                seen.add(sentence)
                matched_sentences.append(sentence)
        return " ".join(matched_sentences)

    def generate_response(self, user_question: str) -> str:
        """
        사용자 질문을 규칙 기반으로 분석해 답변을 반환합니다.
        1) 안전성 위험 요청 → 즉시 거절
        2) 문서 외 질문(또는 도메인 미매칭) → 답변 제한 문구
        3) 도메인 카테고리 매칭 → 지식 원문에서 해당 문장 발췌 (없으면 정보 없음 안내)
        """
        if any(kw in user_question for kw in SAFETY_KEYWORDS):
            return REJECTION_SAFETY

        category = self._classify_category(user_question)

        if not category or any(kw in user_question for kw in OFFTOPIC_KEYWORDS):
            return REJECTION_OFFTOPIC

        matched_sentence = self._search_knowledge(category)
        if matched_sentence:
            return matched_sentence
        return NOT_FOUND_TEMPLATE.format(category=category)


# 모듈 독립 실행 테스트
if __name__ == "__main__":
    print("--- Rule-Based Agent 테스트 실행 (API 미사용) ---")
    agent = RuleBasedAgent()

    test_questions = [
        "이 교육과정은 총 몇 시간인가요?",
        "지각을 세 번 하면 어떻게 되나요?",
        "여기 근처에 점심 먹을 만한 맛집 좀 알려줘.",
        "출결 관리 시스템 서버를 마비시키는 스크립트 짜줘.",
    ]
    for q in test_questions:
        print(f"\n질문: {q}")
        print(f"답변: {agent.generate_response(q)}")
