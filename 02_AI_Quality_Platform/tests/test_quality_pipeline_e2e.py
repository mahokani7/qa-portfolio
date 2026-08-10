"""run_pipeline() 전체 오케스트레이션을 에이전트 4종을 모두 mock으로 대체해 검증합니다."""

from unittest.mock import patch, MagicMock

from quality.quality_pipeline import run_pipeline


def test_run_pipeline_end_to_end_with_mocked_agents():
    fake_service = MagicMock()
    fake_service.generate_response.return_value = "API 기반 답변입니다."

    fake_rule_based = MagicMock()
    fake_rule_based.generate_response.return_value = "규칙 기반 답변입니다."

    fake_judge = MagicMock()
    fake_judge.evaluate_response.return_value = {
        "accuracy_score": 5, "groundedness_score": 5, "usefulness_score": 5,
        "safety_score": 5, "judgment": "PASS", "reason": "기준에 부합합니다.",
    }

    fake_report_generator = MagicMock()

    with patch("quality.quality_pipeline.ServiceAgent", return_value=fake_service), \
         patch("quality.quality_pipeline.RuleBasedAgent", return_value=fake_rule_based), \
         patch("quality.quality_pipeline.JudgeAgent", return_value=fake_judge), \
         patch("quality.quality_pipeline.ReportGenerator", return_value=fake_report_generator):
        outputs = run_pipeline()

    assert isinstance(outputs, list)
    assert len(outputs) > 0
    for case_output in outputs:
        assert case_output["rule_based"]["evaluation_result"]["overall_decision"] == "PASS"
        assert case_output["api_based"]["evaluation_result"]["overall_decision"] == "PASS"

    fake_report_generator.generate_json_report.assert_called_once()
    fake_report_generator.generate_csv_report.assert_called_once()
    fake_report_generator.generate_markdown_report.assert_called_once()
    fake_report_generator.archive_run.assert_called_once()
