"""
품질평가 파이프라인 테스트.
- 파일 I/O 검증 + Judge Agent를 mock으로 대체해 "답변 → Judge → 규칙 검증 → 보고서" 전체 흐름
  (Quality Pipeline Test)을 실제 OpenAI 호출 없이 검증합니다.
"""

from unittest.mock import MagicMock

from quality.quality_pipeline import load_test_cases, evaluate_agent_answer
from quality.rule_validator import RuleValidator


def test_load_test_cases_returns_nonempty_list():
    cases = load_test_cases()
    assert isinstance(cases, list)
    assert len(cases) > 0


def test_each_case_has_required_fields():
    cases = load_test_cases()
    for case in cases:
        assert "case_id" in case
        assert "category" in case
        assert "user_question" in case


def test_evaluate_agent_answer_full_flow_pass():
    """답변 → 규칙 검증 → (mock)Judge 채점 → 표준 결과 스키마 조립까지의 전체 흐름을 검증합니다."""
    case = {
        "case_id": "TC-TEST-01",
        "category": "출결",
        "user_question": "지각을 세 번 하면 어떻게 되나요?",
        "expected_keyword": "결석 1일",
    }
    ai_answer = "지각 3회 누적 시 결석 1일로 처리됩니다."

    rule_validator = RuleValidator()
    judge_agent = MagicMock()
    judge_agent.evaluate_response.return_value = {
        "accuracy_score": 5, "groundedness_score": 5, "usefulness_score": 5,
        "safety_score": 5, "judgment": "PASS", "reason": "기준에 부합합니다.",
    }

    result = evaluate_agent_answer(case, ai_answer, rule_validator, judge_agent)

    assert result["rule_validation"]["rule_status"] == "PASS"
    assert result["evaluation_result"]["overall_decision"] == "PASS"
    assert result["evaluation_result"]["accuracy"]["score"] == 5
    judge_agent.evaluate_response.assert_called_once_with(
        category="출결", user_question=case["user_question"], chatbot_reply=ai_answer
    )


def test_evaluate_agent_answer_fails_on_missing_keyword_even_if_judge_passes():
    """규칙 검증(키워드 누락)이 실패하면, Judge가 PASS를 줘도 rule_status는 FAIL이어야 함."""
    case = {
        "case_id": "TC-TEST-02",
        "category": "출결",
        "user_question": "지각을 세 번 하면 어떻게 되나요?",
        "expected_keyword": "결석 1일",
    }
    ai_answer = "지각을 하면 안 좋습니다."  # 핵심 키워드 누락

    rule_validator = RuleValidator()
    judge_agent = MagicMock()
    judge_agent.evaluate_response.return_value = {
        "accuracy_score": 5, "groundedness_score": 5, "usefulness_score": 5,
        "safety_score": 5, "judgment": "PASS", "reason": "그럴듯해 보입니다.",
    }

    result = evaluate_agent_answer(case, ai_answer, rule_validator, judge_agent)

    assert result["rule_validation"]["keyword_found"] is False
    assert result["rule_validation"]["rule_status"] == "FAIL"
