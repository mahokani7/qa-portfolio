import time


def get_agent_answer(question: str) -> str:
    question = question.strip()

    if not question:
        raise ValueError("질문을 입력해야 합니다.")

    if "오류" in question:
        raise RuntimeError("의도적으로 발생시킨 Agent 오류입니다.")

    if "느리게" in question or "천천히" in question:
        time.sleep(5)
        return "응답을 지연시킨 테스트 답변입니다."

    if "대한민국의 수도" in question:
        return "대한민국의 수도는 서울입니다."

    if "현재 서비스 상태" in question:
        return "현재 AI Agent 서비스는 정상적으로 실행 중입니다."

    if "안녕하세요" in question:
        return "안녕하세요. AI Agent 모니터링 실습용 챗봇입니다."

    return f"입력하신 질문은 '{question}'입니다. 현재는 교육용 모의 응답을 제공합니다."