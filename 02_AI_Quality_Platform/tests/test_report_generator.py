"""
quality/report_generator.py 테스트 — JSON/CSV/Markdown 리포트 생성 (4단계 산출물: 품질 보고서).
"""

import json

import quality.report_generator as report_generator_module
from quality.report_generator import ReportGenerator, list_archived_runs


def _fake_case(case_id="TC-001", decision="PASS"):
    eval_result = {
        "accuracy": {"score": 5, "reason": "정확합니다."},
        "groundedness": {"score": 5, "reason": "근거가 명확합니다."},
        "helpfulness": {"score": 5, "reason": "유용합니다."},
        "safety": {"score": 5, "reason": "안전합니다."},
        "overall_decision": decision,
        "summary": "평가 요약입니다.",
    }
    agent_result = {
        "ai_answer": "테스트 답변입니다.",
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


def test_generate_json_report_writes_valid_json(tmp_path):
    rg = ReportGenerator()
    path = rg.generate_json_report([_fake_case()], output_dir=tmp_path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["case_id"] == "TC-001"


def test_generate_csv_report_contains_decision_columns(tmp_path):
    rg = ReportGenerator()
    path = rg.generate_csv_report([_fake_case()], output_dir=tmp_path)
    assert path.exists()
    content = path.read_text(encoding="utf-8-sig")
    assert "rule_overall_decision" in content
    assert "api_overall_decision" in content


def test_generate_markdown_report_reports_pass_rate(tmp_path):
    rg = ReportGenerator()
    rg.output_dir = tmp_path
    path = rg.generate_markdown_report([_fake_case()])
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "100.0%" in content  # 1건 중 1건 PASS


def test_archive_run_creates_meta_and_report_files(tmp_path, monkeypatch):
    monkeypatch.setattr(report_generator_module, "HISTORY_DIR", tmp_path)
    rg = ReportGenerator()

    meta = rg.archive_run([_fake_case()])

    assert meta["total"] == 1
    assert meta["rule_pass"] == 1
    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "meta.json").exists()
    assert (run_dirs[0] / "evaluation_result.json").exists()
    assert (run_dirs[0] / "evaluation_result.csv").exists()


def test_list_archived_runs_returns_saved_run(tmp_path, monkeypatch):
    monkeypatch.setattr(report_generator_module, "HISTORY_DIR", tmp_path)
    rg = ReportGenerator()
    rg.archive_run([_fake_case()])

    runs = list_archived_runs()

    assert len(runs) == 1
    assert runs[0]["total"] == 1
