"""[고도화 3] 회귀 테스트 모듈 테스트."""

from quality.regression import compare_runs


def _case(case_id, rule_decision, rule_acc, api_decision="PASS", api_acc=5):
    def agent(decision, acc):
        return {
            "evaluation_result": {
                "accuracy": {"score": acc},
                "groundedness": {"score": 5},
                "helpfulness": {"score": 5},
                "safety": {"score": 5},
                "overall_decision": decision,
            }
        }
    return {
        "case_id": case_id,
        "category": "출결",
        "rule_based": agent(rule_decision, rule_acc),
        "api_based": agent(api_decision, api_acc),
    }


def test_detects_decision_regression():
    baseline = [_case("TC-001", "PASS", 5)]
    current = [_case("TC-001", "FAIL", 2)]  # PASS→FAIL, accuracy 5→2

    result = compare_runs(baseline, current)

    assert result["has_regression"] is True
    kinds = [r["kind"] for r in result["regressions"]]
    assert "판정 하락" in kinds
    assert any("accuracy 하락" in k for k in kinds)


def test_detects_improvement_no_regression():
    baseline = [_case("TC-001", "REVIEW", 3)]
    current = [_case("TC-001", "PASS", 5)]

    result = compare_runs(baseline, current)

    assert result["has_regression"] is False
    assert len(result["improvements"]) > 0


def test_detects_missing_case_as_regression():
    baseline = [_case("TC-001", "PASS", 5), _case("TC-002", "PASS", 5)]
    current = [_case("TC-001", "PASS", 5)]  # TC-002 누락

    result = compare_runs(baseline, current)

    assert result["has_regression"] is True
    assert any(r["kind"] == "케이스 누락" for r in result["regressions"])


def test_identical_runs_no_change():
    baseline = [_case("TC-001", "PASS", 5)]
    current = [_case("TC-001", "PASS", 5)]

    result = compare_runs(baseline, current)

    assert result["has_regression"] is False
    assert len(result["regressions"]) == 0
    assert len(result["improvements"]) == 0
