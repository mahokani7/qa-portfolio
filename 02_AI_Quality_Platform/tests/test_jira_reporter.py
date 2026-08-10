"""
quality/jira_reporter.py 테스트.
- Jira 미설정 시 네트워크 호출 없이 안전하게 건너뛰는지, 설정 시 mock으로 이슈 생성 요청이 올바른지 검증합니다.
"""

from unittest.mock import patch, MagicMock

import quality.jira_reporter as jira_reporter


def _fail_case(case_id="TC-001", category="안전성"):
    eval_result = {
        "accuracy": {"score": 1, "reason": "부정확"},
        "groundedness": {"score": 1, "reason": "근거 없음"},
        "helpfulness": {"score": 1, "reason": "도움 안 됨"},
        "safety": {"score": 1, "reason": "위험"},
        "overall_decision": "FAIL",
        "summary": "위험 질문에 잘못 답변함.",
    }
    agent_result = {
        "ai_answer": "위험한 답변입니다.",
        "rule_validation": {"keyword_found": False, "rule_status": "FAIL", "rule_reason": "거절 실패"},
        "evaluation_result": eval_result,
    }
    return {
        "case_id": case_id,
        "category": category,
        "test_type": "위험질문",
        "user_question": "위험한 질문입니다.",
        "rule_based": agent_result,
        "api_based": agent_result,
    }


def _pass_case(case_id="TC-002"):
    eval_result = {
        "accuracy": {"score": 5, "reason": "정확"},
        "groundedness": {"score": 5, "reason": "근거 명확"},
        "helpfulness": {"score": 5, "reason": "유용"},
        "safety": {"score": 5, "reason": "안전"},
        "overall_decision": "PASS",
        "summary": "정상 응답.",
    }
    agent_result = {
        "ai_answer": "정상 답변입니다.",
        "rule_validation": {"keyword_found": True, "rule_status": "PASS", "rule_reason": "통과"},
        "evaluation_result": eval_result,
    }
    return {
        "case_id": case_id,
        "category": "출결",
        "test_type": "정상",
        "user_question": "지각을 세 번 하면 어떻게 되나요?",
        "rule_based": agent_result,
        "api_based": agent_result,
    }


def test_extract_fail_cases_only_returns_fail_decisions():
    outputs = [_fail_case(), _pass_case()]
    fails = jira_reporter._extract_fail_cases(outputs)
    # FAIL 케이스 1건 x (rule_based + api_based) = 2개 항목
    assert len(fails) == 2
    assert all(f["case_id"] == "TC-001" for f in fails)
    assert fails[0]["severity"] == "Critical"  # 카테고리가 '안전성'


def test_create_issues_returns_empty_list_when_no_failures():
    outputs = [_pass_case()]
    result = jira_reporter.create_issues_for_failures(outputs)
    assert result == []


def test_create_issues_skips_gracefully_when_not_configured(monkeypatch):
    monkeypatch.setattr(jira_reporter, "JIRA_BASE_URL", None)
    monkeypatch.setattr(jira_reporter, "JIRA_EMAIL", None)
    monkeypatch.setattr(jira_reporter, "JIRA_API_TOKEN", None)
    monkeypatch.setattr(jira_reporter, "JIRA_PROJECT_KEY", None)

    with patch("quality.jira_reporter.requests.post") as mock_post:
        result = jira_reporter.create_issues_for_failures([_fail_case()])

    assert result == []
    mock_post.assert_not_called()


def test_create_issues_posts_to_jira_when_configured(monkeypatch):
    monkeypatch.setattr(jira_reporter, "JIRA_BASE_URL", "https://example.atlassian.net")
    monkeypatch.setattr(jira_reporter, "JIRA_EMAIL", "user@example.com")
    monkeypatch.setattr(jira_reporter, "JIRA_API_TOKEN", "fake-token")
    monkeypatch.setattr(jira_reporter, "JIRA_PROJECT_KEY", "AIQ")

    fake_response = MagicMock(status_code=201)
    fake_response.json.return_value = {"key": "AIQ-1"}

    with patch("quality.jira_reporter.requests.post", return_value=fake_response) as mock_post:
        result = jira_reporter.create_issues_for_failures([_fail_case()])

    assert result == ["AIQ-1", "AIQ-1"]  # rule_based + api_based 각각 1건씩
    assert mock_post.call_count == 2
    called_url = mock_post.call_args_list[0].args[0]
    assert called_url == "https://example.atlassian.net/rest/api/3/issue"
