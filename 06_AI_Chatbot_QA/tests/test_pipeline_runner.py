from services.pipeline_runner import _build_api_based_result, _build_rule_based_result, _decision_from_scores, _flatten_for_report


def test_decision_from_scores_returns_pass_for_high_scores():
    assert _decision_from_scores([4, 5, 4, 5]) == "PASS"


def test_decision_from_scores_returns_review_for_middle_scores():
    assert _decision_from_scores([2, 3, 4, 5]) == "REVIEW"


def test_decision_from_scores_returns_fail_for_low_scores():
    assert _decision_from_scores([1, 5, 5, 5]) == "FAIL"


def test_rule_based_result_uses_rule_validation_status():
    result = _build_rule_based_result(
        "이 교육과정은 총 320시간 과정입니다.",
        {"passed": True, "reason": "'320시간' 키워드 포함 확인됨"},
    )

    assert result["evaluation_result"]["overall_decision"] == "PASS"
    assert result["evaluation_result"]["accuracy"]["score"] == 5


def test_api_based_result_uses_judge_scores():
    result = _build_api_based_result(
        "이 교육과정은 총 320시간 과정입니다.",
        {"passed": True, "reason": "'320시간' 키워드 포함 확인됨"},
        {"accuracy": 4, "groundedness": 4, "helpfulness": 5, "safety": 5, "comment": "정확합니다."},
    )

    assert result["evaluation_result"]["overall_decision"] == "PASS"
    assert result["evaluation_result"]["helpfulness"]["score"] == 5


def test_flatten_for_report_preserves_core_fields():
    pipeline_outputs = [
        {
            "case_id": "TC-001",
            "category": "정확성",
            "test_type": "Happy",
            "user_question": "이 교육과정은 총 몇 시간인가요?",
            "api_based": _build_api_based_result(
                "이 교육과정은 총 320시간 과정입니다.",
                {"passed": True, "reason": "'320시간' 키워드 포함 확인됨"},
                {"accuracy": 4, "groundedness": 4, "helpfulness": 5, "safety": 5, "comment": "정확합니다."},
            ),
        }
    ]

    rows = _flatten_for_report(pipeline_outputs)

    assert rows[0]["case_id"] == "TC-001"
    assert rows[0]["rule_passed"] is True
    assert rows[0]["accuracy"] == 4
