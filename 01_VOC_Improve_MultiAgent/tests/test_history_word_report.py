"""수행 이력별 Word 종합 품질평가 결과 보고서 회귀 테스트."""

import tempfile
import unittest
import zipfile
from pathlib import Path

from quality_diagnosis.history_word_report import _rag_rows, build_history_word_report


class HistoryWordReportTests(unittest.TestCase):
    def test_builds_auditable_docx_with_complete_run_data(self):
        run = {
            "run_id": "e2e-history-TC-01",
            "generated_at": "2026-07-15T17:00:00+09:00",
            "kind": "e2e",
            "source_file": "e2e-history.json",
            "domain": "ecommerce",
            "mode": "both",
            "provider": "openai",
            "model": "test-model",
            "git_commit": "abc1234",
            "dataset_version": "dataset-v1",
            "prompt_version": "prompt-v2",
            "live_verified": True,
            "total": 1,
            "passed": 1,
            "failed": 0,
            "pass_rate": 100.0,
            "average_score": 97.0,
            "deployment_threshold": 95.0,
            "average_duration_ms": 1200.0,
            "p95_duration_ms": 1200.0,
            "total_tokens": 321,
            "estimated_cost": 0.0123,
            "rate_limit_count": 0,
            "defects_count": 0,
            "critical_violations": 0,
            "metadata": {"source_size": 2048},
            "release_approval": {"status": "APPROVED", "final_deployment_approved": True},
            "cases": [{
                "case_id": "TC-01",
                "question": "결제는 완료되었는데 주문 내역에 보이지 않습니다.",
                "status": "PASS",
                "score": 97.0,
                "output": "요약: 결제 후 주문 내역이 생성되지 않았습니다. 정책: 동기화 상태를 점검하고 고객에게 처리 상황을 안내합니다.",
                "metrics": {
                    "defects": [],
                    "hard_blockers": [],
                    "deployment": {"label": "배포 가능", "minimum_score": 95, "score_gap": 2},
                    "rag": {
                        "context_precision": 1.0,
                        "context_recall": 1.0,
                        "faithfulness": 0.98,
                        "response_relevancy": 1.0,
                        "noise_sensitivity": 1.0,
                        "citation_coverage": 0.8,
                        "passed": True,
                    },
                    "rubric": {
                        "interpreter": {
                            "label": "Interpreter 요구사항 해석",
                            "score": 15,
                            "max_score": 15,
                            "passed": True,
                            "evidence": {"missing": [], "matched": ["결제", "주문 내역"]},
                        },
                        "improver_actionability": {
                            "label": "Improver 실행 가능성",
                            "score": 15,
                            "max_score": 15,
                            "passed": True,
                            "evidence": {"missing": [], "matched": ["고객 안내", "개선안", "우선순위"]},
                        },
                    },
                },
                "trace": [
                    {
                        "agent": "Interpreter",
                        "role": "요구사항 해석",
                        "check": "의도와 검색 조건 구성",
                        "duration_ms": 110,
                        "total_tokens": 25,
                        "provider": "openai",
                        "model": "test-model",
                        "output": {"task": "결제 주문 불일치 분석", "filters": {"domain": "결제"}, "max_items": 5},
                    },
                    {
                        "agent": "Retriever",
                        "role": "VOC 근거 검색",
                        "check": "관련 고객 불만 확보",
                        "duration_ms": 80,
                        "total_tokens": 20,
                        "provider": "local",
                        "model": "tfidf",
                        "output": {"retrieved_count": 3, "samples": ["결제 완료 후 주문 생성 지연"]},
                    },
                    {
                        "agent": "Summarizer",
                        "role": "요약 생성",
                        "check": "고객 현상과 영향 요약",
                        "duration_ms": 150,
                        "total_tokens": 70,
                        "provider": "openai",
                        "model": "test-model",
                        "output": {"post_refine_summary": "결제 후 주문 내역이 생성되지 않았습니다."},
                    },
                    {
                        "agent": "Evaluator",
                        "role": "후보 평가",
                        "check": "관련성과 구조 평가",
                        "duration_ms": 120,
                        "total_tokens": 55,
                        "provider": "openai",
                        "model": "test-model",
                        "output": {"winner": "summary_a", "scores": {"summary_a": 9.5}},
                    },
                    {
                        "agent": "Critic",
                        "role": "위험 비판",
                        "check": "누락과 과장 확인",
                        "duration_ms": 100,
                        "total_tokens": 45,
                        "provider": "openai",
                        "model": "test-model",
                        "output": {"need_refine": False, "edits": []},
                    },
                    {
                        "agent": "Improver",
                        "role": "정책 개선안 생성",
                        "check": "담당자·기한·지표 포함",
                        "duration_ms": 200,
                        "total_tokens": 106,
                        "provider": "openai",
                        "model": "test-model",
                        "output": {"policy": "동기화 상태를 점검하고 고객에게 처리 상황을 안내합니다."},
                    },
                ],
                "raw": {
                    "analysis": {
                        "summary": "결제 후 주문 내역이 생성되지 않았습니다.",
                        "policy": "동기화 상태를 점검하고 고객에게 처리 상황을 안내합니다.",
                    },
                    "quality": {
                        "deployment": {"label": "배포 가능", "minimum_score": 95, "score_gap": 2},
                        "checks": {
                            "intent": {"expected": "결제 완료 후 주문 조회 실패", "passed": True, "ratio": 1.0, "missing": []},
                            "keywords": {"matched": ["결제", "주문 내역", "동기화"], "missing": [], "passed": True},
                            "required_output": {"matched": ["원인 추정", "고객 안내", "개선안", "우선순위"], "missing": [], "passed": True},
                            "prohibited_output": {"violations": [], "passed": True},
                        },
                    },
                },
            }],
            "source_payload": {"report": "full-source-payload", "private_marker": "RAW-EVIDENCE-001"},
        }

        with tempfile.TemporaryDirectory() as directory:
            path = build_history_word_report(run, Path(directory))

            self.assertTrue(path.is_file())
            self.assertEqual(path.suffix, ".docx")
            self.assertGreater(path.stat().st_size, 10_000)
            with zipfile.ZipFile(path) as archive:
                archive.testzip()
                document_xml = archive.read("word/document.xml").decode("utf-8")
            for expected in (
                "종합 품질평가 결과 보고서",
                "e2e-history-TC-01",
                "TC-01",
                "결제는 완료되었는데 주문 내역에 보이지 않습니다.",
                "1. 우리가 구축한 품질평가 구조",
                "2. 고객 불만 사항에 기반한 개선 정책 도출 메커니즘",
                "3. 왜 해당 개선안이 타당하다고 판단했는가",
                "4. 프로세스 단계별 전문 판단 프로세스",
                "5. 과정에서 점검한 기술적 사항",
                "6. 품질전문가가 성공적인 품질평가라고 판단하는 근거",
                "7. 이번 품질평가를 통해 실질적으로 얻은 성과",
                "8. 성공 판정의 합리적 범위와 한계 명시",
                "QA Lead 최종 종합 평가 의견",
                "결제 후 주문 내역이 생성되지 않았습니다.",
                "동기화 상태를 점검하고 고객에게 처리 상황을 안내합니다.",
                "결제 완료 후 주문 조회 실패",
                "VOC 근거 검색",
                "지표·종합 판정",
                "RAG 6지표 종합",
                "양호",
            ):
                self.assertIn(expected, document_xml)
            for prohibited in (
                "부록 A. 실행 이력 전체 원본 데이터",
                "RAW-EVIDENCE-001",
                "source_payload",
                "private_marker",
                '"run_id"',
                "참고",
            ):
                self.assertNotIn(prohibited, document_xml)

    def test_rag_rows_use_real_metric_and_overall_verdicts(self):
        measured = _rag_rows({"metrics": {"rag": {
            "context_precision": 0.9, "context_recall": 0.7,
            "faithfulness": 0.5, "response_relevancy": 1.0,
            "noise_sensitivity": 0.8, "citation_coverage": 0.3,
            "ratio": 0.7, "passed": True,
        }}})
        self.assertEqual([row[2] for row in measured[:6]], [
            "양호", "주의", "개선 필요", "양호", "양호", "개선 필요",
        ])
        self.assertEqual(measured[-1], ["RAG 6지표 종합", "70.0%", "PASS"])
        missing = _rag_rows({})
        self.assertTrue(all(row[2] == "미측정" for row in missing[:6]))
        self.assertEqual(missing[-1], ["RAG 6지표 종합", "-", "측정 데이터 없음"])


if __name__ == "__main__":
    unittest.main()
