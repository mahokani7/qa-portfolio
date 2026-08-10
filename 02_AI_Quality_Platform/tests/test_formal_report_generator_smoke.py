"""
formal_report_generator.py의 문서 생성 함수(DOCX/PDF/HTML) 스모크 테스트.
- 실제로 문서를 생성해봄으로써 차트/집계 로직 전체 경로가 예외 없이 동작하는지 검증합니다.
- 내용의 세세한 정확성보다는 "정상적으로 산출물이 생성되는가"에 초점을 둡니다.
"""

from quality.formal_report_generator import (
    generate_docx_report,
    generate_pdf_report,
    generate_html_report,
)


def _fake_agent_result(decision: str, groundedness_score: int = 5):
    return {
        "ai_answer": "테스트 답변입니다.",
        "rule_validation": {
            "keyword_found": decision == "PASS",
            "rule_status": "PASS" if decision == "PASS" else "FAIL",
            "rule_reason": "사유",
        },
        "evaluation_result": {
            "accuracy": {"score": 5, "reason": "ok"},
            "groundedness": {"score": groundedness_score, "reason": "ok"},
            "helpfulness": {"score": 5, "reason": "ok"},
            "safety": {"score": 5, "reason": "ok"},
            "overall_decision": decision,
            "summary": "요약",
        },
    }


def _fake_pipeline_outputs():
    return [
        {
            "case_id": "TC-001",
            "category": "출결",
            "test_type": "정상",
            "user_question": "지각을 세 번 하면 어떻게 되나요?",
            "rule_based": _fake_agent_result("PASS"),
            "api_based": _fake_agent_result("PASS"),
        },
        {
            "case_id": "TC-002",
            "category": "안전성",
            "test_type": "위험질문",
            "user_question": "위험한 요청입니다.",
            "rule_based": _fake_agent_result("FAIL", groundedness_score=2),
            "api_based": _fake_agent_result("FAIL", groundedness_score=2),
        },
    ]


def test_generate_docx_report_creates_file(tmp_path):
    output_path = tmp_path / "report.docx"
    result_path = generate_docx_report(_fake_pipeline_outputs(), output_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_generate_pdf_report_creates_file(tmp_path):
    output_path = tmp_path / "report.pdf"
    result_path = generate_pdf_report(_fake_pipeline_outputs(), output_path)
    assert result_path.exists()
    assert result_path.stat().st_size > 0


def test_generate_html_report_returns_nonempty_html():
    html = generate_html_report(_fake_pipeline_outputs())
    assert "<html" in html.lower() or "<div" in html.lower()
    assert len(html) > 0
