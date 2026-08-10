"""[고도화 2] 자동 레드티밍 테스트."""

from unittest.mock import MagicMock

from quality.redteam import is_defended, run_redteam, load_cases


def test_is_defended_detects_safety_rejection():
    assert is_defended("죄송하지만 올바르지 않은 요청이므로 도와드릴 수 없습니다.") is True


def test_is_defended_ignores_knowledge_gap():
    # '정보를 찾을 수 없습니다'(지식 부재)는 안전 거절이 아님 → False
    assert is_defended("'출결' 관련 정보를 찾을 수 없습니다.") is False


def test_is_defended_false_for_normal_answer():
    assert is_defended("지각 3회 누적 시 결석 1일로 처리됩니다.") is False


def test_load_cases_has_attack_and_control():
    cases = load_cases()
    assert any(c["expected"] == "reject" for c in cases)
    assert any(c["expected"] == "answer" for c in cases)


def test_run_redteam_all_defended_with_mock_agent():
    """공격은 모두 거절하고 정상 질문엔 답하는 이상적 챗봇 → 방어율 100%, 전체 통과."""
    agent = MagicMock()

    def fake(prompt):
        # 공격 프롬프트(위험 키워드 포함)면 거절, 아니면 정상 응답
        if any(k in prompt for k in ["무시", "마비", "전화번호", "조작", "해킹", "협박"]):
            return "죄송하지만 도와드릴 수 없습니다."
        return "지각 3회 누적 시 결석 1일로 처리됩니다."

    agent.generate_response.side_effect = fake
    report = run_redteam(agent=agent)

    assert report["defense_rate"] == 100.0
    assert report["all_pass"] is True


def test_run_redteam_detects_vulnerability():
    """모든 요청에 순순히 답하는 취약한 챗봇 → 방어 실패 검출."""
    agent = MagicMock()
    agent.generate_response.return_value = "네, 알려드리겠습니다. 방법은..."
    report = run_redteam(agent=agent)

    assert report["defense_rate"] < 100.0
    assert report["all_pass"] is False
