"""
service_agent.py
- 실제 챗봇 역할
- API 없이도 실행 가능한 규칙 기반 모의 챗봇
"""

import re

from knowledge_base import get_all_policies, search_chroma_knowledge, search_uploaded_knowledge

policies = get_all_policies()


def _best_knowledge_text(user_question):
    matches = search_chroma_knowledge(user_question, limit=1)
    if not matches:
        matches = search_uploaded_knowledge(user_question, limit=1)
    if not matches:
        return ""
    return matches[0].get("text", "")


def _first_match(pattern, text):
    match = re.search(pattern, text or "")
    return match.group(0) if match else ""


def get_response(user_question: str, use_knowledge_search: bool = True) -> str:
    """
    사용자 질문에 대해 규칙 기반으로 답변 생성.
    업로드 지식 파일에서 관련 내용을 먼저 찾고, 없으면 기본 정책 정보로 답변.
    """
    q = user_question.lower()
    knowledge_text = _best_knowledge_text(user_question) if use_knowledge_search else ""

    if "시간" in user_question and "교육" in user_question:
        total_hours = _first_match(r"\d+\s*시간", knowledge_text) or policies["총_교육시간"]
        return f"이 교육과정은 총 {total_hours} 과정입니다."

    if "지각" in user_question:
        if knowledge_text and "지각" in knowledge_text and ("결석" in knowledge_text or "처리" in knowledge_text):
            return f"{knowledge_text}"
        return f"{policies['지각_기준']}로 처리됩니다."

    if "수료" in user_question and "출석" in user_question:
        attendance_rate = _first_match(r"\d+\s*퍼센트|\d+\s*%", knowledge_text)
        if attendance_rate:
            attendance_rate = attendance_rate.replace("%", "퍼센트")
            return f"수료를 위해서는 전체 훈련시간의 {attendance_rate} 이상 출석해야 합니다."
        return f"수료를 위해서는 {policies['수료_출석_기준']}해야 합니다."

    if "취업" in user_question:
        if knowledge_text and "취업" in knowledge_text:
            return f"{knowledge_text} 주요 지원 항목에는 {policies['취업지원_내용']}이 포함됩니다."
        return f"수료 후 {policies['취업지원_내용']} 등을 받으실 수 있습니다."

    if "날씨" in user_question:
        return policies["안내_외_질문_응답"]

    if "혼내" in user_question or "괴롭" in user_question or "위협" in user_question:
        return policies["부적절_요청_응답"]

    if knowledge_text:
        return f"업로드된 지식 파일 기준으로 확인한 내용입니다. {knowledge_text}"

    return "죄송합니다, 해당 질문에 대한 답변을 준비하지 못했습니다."


if __name__ == "__main__":
    print(get_response("이 교육과정은 총 몇 시간인가요?"))
