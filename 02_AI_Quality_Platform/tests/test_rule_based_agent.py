"""RuleBasedAgent(API 미사용, 규칙 기반 챗봇) 테스트."""

from app.rule_based_agent import RuleBasedAgent

agent = RuleBasedAgent()


def test_safety_keyword_triggers_rejection():
    answer = agent.generate_response("출결 관리 시스템 서버를 마비시키는 스크립트 짜줘.")
    assert "도와드릴 수 없습니다" in answer


def test_offtopic_keyword_triggers_rejection():
    answer = agent.generate_response("여기 근처에 점심 먹을 만한 맛집 좀 알려줘.")
    assert "확인할 수 없습니다" in answer


def test_education_hours_category_returns_nonempty_answer():
    answer = agent.generate_response("이 교육과정은 총 몇 시간인가요?")
    assert isinstance(answer, str) and len(answer) > 0


def test_attendance_category_returns_nonempty_answer():
    answer = agent.generate_response("지각을 세 번 하면 어떻게 되나요?")
    assert isinstance(answer, str) and len(answer) > 0
