from rule_validator import validate


def test_rule_validator_passes_when_keyword_exists():
    result = validate("이 교육과정은 총 320시간 과정입니다.", "320시간")

    assert result["passed"] is True
    assert "포함" in result["reason"]


def test_rule_validator_fails_when_keyword_is_missing():
    result = validate("이 교육과정은 총 150시간 과정입니다.", "320시간")

    assert result["passed"] is False
    assert "누락" in result["reason"]


def test_rule_validator_fails_when_response_is_empty():
    result = validate("", "320시간")

    assert result == {"passed": False, "reason": "응답이 비어 있습니다."}
