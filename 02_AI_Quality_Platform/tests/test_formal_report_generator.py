"""quality/formal_report_generator.py의 순수 로직(심각도 판정 등)을 검증합니다."""

from quality.formal_report_generator import _derive_severity, _weakest_metric


def _case(category, rule_status="PASS", groundedness_score=5):
    return {
        "category": category,
        "rule_validation": {"rule_status": rule_status},
        "evaluation_result": {
            "accuracy": {"score": 5, "reason": "ok"},
            "groundedness": {"score": groundedness_score, "reason": "ok"},
            "helpfulness": {"score": 5, "reason": "ok"},
            "safety": {"score": 5, "reason": "ok"},
        },
    }


def test_derive_severity_is_critical_for_safety_category():
    assert _derive_severity(_case("안전성 위험 관리")) == "Critical"


def test_derive_severity_is_high_when_rule_fails():
    assert _derive_severity(_case("출결", rule_status="FAIL")) == "High"


def test_derive_severity_is_medium_for_low_groundedness():
    assert _derive_severity(_case("출결", groundedness_score=2)) == "Medium"


def test_derive_severity_is_low_otherwise():
    assert _derive_severity(_case("출결")) == "Low"


def test_weakest_metric_picks_lowest_score():
    case = _case("출결")
    case["evaluation_result"]["helpfulness"]["score"] = 1
    key, score, _reason = _weakest_metric(case)
    assert key == "helpfulness"
    assert score == 1
