"""
JudgeAgent(AI 심층 평가) 테스트 — 실제 OpenAI 네트워크 호출 없이 mock으로 검증합니다.
Quality Pipeline Test 요구사항(3단계: AI Judge 품질평가)에 대응합니다.
"""

from unittest.mock import patch, MagicMock

from app.judge_agent import JudgeAgent


def _make_fake_parsed_completion(**scores):
    fake_parsed = MagicMock()
    fake_parsed.model_dump.return_value = scores
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(parsed=fake_parsed))]
    return fake


def test_evaluate_response_returns_parsed_scores():
    agent = JudgeAgent()
    fake_completion = _make_fake_parsed_completion(
        accuracy_score=5, groundedness_score=5, usefulness_score=5,
        safety_score=5, judgment="PASS", reason="모든 기준을 충족합니다.",
    )
    with patch.object(agent.client.beta.chat.completions, "parse", return_value=fake_completion):
        result = agent.evaluate_response(category="출결", user_question="Q", chatbot_reply="A")

    assert result["judgment"] == "PASS"
    assert result["accuracy_score"] == 5


def test_evaluate_response_handles_api_error_as_fail():
    agent = JudgeAgent()
    with patch.object(agent.client.beta.chat.completions, "parse", side_effect=Exception("timeout")):
        result = agent.evaluate_response(category="출결", user_question="Q", chatbot_reply="A")

    assert result["judgment"] == "FAIL"
    assert result["accuracy_score"] == 0


def test_evaluate_response_uses_category_criteria_in_prompt():
    """criteria.json에 없는 카테고리도 기본 policy로 폴백되어 오류 없이 동작해야 함."""
    agent = JudgeAgent()
    fake_completion = _make_fake_parsed_completion(
        accuracy_score=3, groundedness_score=3, usefulness_score=3,
        safety_score=3, judgment="REVIEW", reason="애매합니다.",
    )
    with patch.object(agent.client.beta.chat.completions, "parse", return_value=fake_completion) as mock_parse:
        result = agent.evaluate_response(category="존재하지않는카테고리", user_question="Q", chatbot_reply="A")

    assert result["judgment"] == "REVIEW"
    mock_parse.assert_called_once()
