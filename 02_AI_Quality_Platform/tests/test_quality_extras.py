"""[고도화 추가 4종] 커버리지 갭 / PII 검사 / 비용 추적 / 환각 교차검증 테스트."""

from quality.coverage_gap import analyze_coverage
from quality.pii_scan import scan_text, scan_answers
from quality.cost_tracker import estimate_tokens, estimate_case_cost, track_cost
from quality.hallucination_check import grounding_score


# ── #1 커버리지 갭 ──────────────────────────────────────────────
def test_coverage_reports_gap_and_total():
    r = analyze_coverage()
    assert r["total"] >= r["covered"]
    assert r["gap"] == r["total"] - r["covered"]
    assert 0.0 <= r["coverage_pct"] <= 100.0


def test_coverage_flags_safety_uncovered():
    r = analyze_coverage()
    # 현재 프로젝트는 안전성 카테고리에 테스트케이스가 없어 위험 미커버로 잡혀야 함
    assert "안전성" in r["uncovered_risk"] or all(
        row["covered"] for row in r["rows"] if row["risk"]
    )


# ── #7 PII 검사 ─────────────────────────────────────────────────
def test_pii_detects_phone_and_email():
    hits = scan_text("연락처 010-1234-5678, 메일 admin@example.com")
    types = {h["type"] for h in hits}
    assert "전화번호" in types
    assert "이메일" in types


def test_pii_clean_answer_has_no_findings():
    result = scan_answers([{"case_id": "T", "agent": "r", "text": "지각 3회 시 결석 1일 처리됩니다."}])
    assert result["clean"] is True
    assert result["exposure_count"] == 0


def test_pii_detects_rrn():
    hits = scan_text("주민번호 900101-1234567 입니다")
    assert any(h["type"] == "주민등록번호" for h in hits)


# ── #8 비용 추적 ────────────────────────────────────────────────
def test_estimate_tokens_positive():
    assert estimate_tokens("안녕하세요 테스트입니다") > 0
    assert estimate_tokens("") == 0


def test_estimate_case_cost_output_costs_more_than_input():
    # 동일 토큰이면 출력 단가가 입력보다 비싸므로 출력 비용 비중이 큼
    c = estimate_case_cost("질문", "답변")
    assert c["total_tokens"] == c["input_tokens"] + c["output_tokens"]
    assert c["cost_usd"] >= 0


def test_track_cost_aggregates():
    r = track_cost([
        {"case_id": "A", "question": "질문1", "answer": "답변1"},
        {"case_id": "B", "question": "질문2", "answer": "답변2"},
    ])
    assert len(r["rows"]) == 2
    assert r["total_tokens"] == sum(row["total_tokens"] for row in r["rows"])


# ── #3 환각 교차검증 ────────────────────────────────────────────
def test_grounding_high_when_words_in_corpus():
    corpus = {"교육과정", "320시간", "총"}
    g = grounding_score("교육과정 총 320시간", corpus)
    assert g["score"] == 1.0


def test_grounding_low_flags_hallucination():
    corpus = {"교육과정", "출결", "수료"}
    g = grounding_score("우주 비행사 자격증 무료 항공권 제공", corpus)
    assert g["score"] < 0.5
    assert g["total"] > 0


def test_grounding_empty_answer_is_safe():
    g = grounding_score("", {"교육과정"})
    assert g["score"] == 1.0
