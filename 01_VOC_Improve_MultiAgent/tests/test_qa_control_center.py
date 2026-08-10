import json
import tempfile
import unittest
from pathlib import Path

from quality_diagnosis.qa_control_center import QAControlCenter, describe_automated_test


def _report(generated_at: str, score: float, passed: bool, duration: float) -> dict:
    return {
        "summary": {
            "generated_at": generated_at,
            "domain": "ecommerce",
            "mode": "offline",
            "total": 1,
            "passed": int(passed),
            "failed": int(not passed),
            "average_score": score,
        },
        "results": [
            {
                "case_id": "TC-01",
                "question": "결제 후 주문 조회가 안 됩니다.",
                "quality": {
                    "passed": passed,
                    "score": score,
                    "checks": {
                        "rag_metrics": {
                            "context_precision": 0.8,
                            "context_recall": 1.0,
                            "faithfulness": 0.9,
                            "response_relevancy": 1.0,
                        }
                    },
                },
                "analysis": {
                    "summary": "주문 조회 동기화 문제입니다.",
                    "policy": "모니터링을 개선합니다.",
                    "metrics": {"total_duration_ms": duration},
                    "stages": [
                        {
                            "agent": "Interpreter",
                            "role": "질문 해석",
                            "check": "의도 정확성",
                            "duration_ms": duration,
                            "output": {"filters": ["결제", "주문"]},
                        }
                    ],
                },
            }
        ],
    }


class QAControlCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.reports = Path(self.temp.name)
        (self.reports / "ecommerce_offline_e2e_20260715_100000.json").write_text(
            json.dumps(_report("2026-07-15T10:00:00+09:00", 91, False, 100)),
            encoding="utf-8",
        )
        (self.reports / "ecommerce_offline_e2e_20260715_110000.json").write_text(
            json.dumps(_report("2026-07-15T11:00:00+09:00", 97, True, 80)),
            encoding="utf-8",
        )
        self.center = QAControlCenter(self.reports)

    def tearDown(self):
        self.temp.cleanup()

    def test_sync_history_trace_and_versions(self):
        result = self.center.sync_reports()
        self.assertEqual(result["indexed"], 2)
        runs = self.center.list_runs()
        self.assertEqual(len(runs), 2)
        self.assertTrue(runs[0]["dataset_version"])
        detail = self.center.get_run(runs[0]["run_id"])
        self.assertEqual(detail["cases"][0]["trace"][0]["agent"], "Interpreter")
        self.assertTrue(detail["cases"][0]["trace"][0]["usage_is_estimated"])
        self.assertGreater(detail["total_tokens"], 0)
        self.assertGreater(detail["p95_duration_ms"], 0)
        self.assertIn("git_commit", detail)
        self.assertEqual(detail["cases"][0]["metrics"]["rag"]["context_recall"], 1.0)

    def test_baseline_comparison_marks_improvement(self):
        self.center.sync_reports()
        runs = self.center.list_runs()
        comparison = self.center.compare_runs(runs[1]["run_id"], runs[0]["run_id"])
        self.assertEqual(comparison["summary"]["improved"], 1)
        self.assertEqual(comparison["summary"]["regressed"], 0)
        self.assertEqual(comparison["summary"]["release_gate"], "PASS")
        self.assertIn("agent_score_delta", comparison["summary"])
        self.assertIn("p95_duration_delta_ms", comparison["summary"])

    def test_approval_is_audited(self):
        self.center.sync_reports()
        run_id = self.center.list_runs()[0]["run_id"]
        approval = self.center.create_approval(run_id, "QA 담당자", "APPROVED", "확인 완료")
        self.assertEqual(approval["decision"], "APPROVED")
        self.assertEqual(approval["run_label"], "6-Agent E2E 품질검증 · 이커머스 · 오프라인")
        self.assertEqual(approval["qa_summary"], "1/1 PASS · 평균 97.0점")
        self.assertEqual(approval["sample_cases"][0]["case_id"], "TC-01")
        self.assertNotIn("source_file", approval)
        self.assertEqual(self.center.list_audit_events()[0]["event_type"], "APPROVAL_RECORDED")

    def test_settings_validation_and_drift(self):
        self.center.sync_reports()
        settings = self.center.save_settings({"drift_score_drop": 2})
        self.assertEqual(settings["drift_score_drop"], 2)
        with self.assertRaises(ValueError):
            self.center.save_settings({"input_cost_per_million": -1})
        # The latest run improved, therefore no negative drift is reported.
        self.assertEqual(self.center.drift_alerts(), [])

    def test_extended_review_workflow_case_filter_and_versions(self):
        self.center.sync_reports()
        run_id = self.center.list_runs()[0]["run_id"]
        approval = self.center.create_approval(
            run_id,
            "QA 리드",
            "REVIEWING",
            "Judge와 점수 비교 중",
            case_id="TC-01",
            review_score=96.5,
            judge_agreement=False,
        )
        self.assertEqual(approval["case_id"], "TC-01")
        self.assertFalse(approval["judge_agreement"])
        self.assertEqual(approval["case_question"], "결제 후 주문 조회가 안 됩니다.")
        self.assertIn("주문 조회 동기화 문제", approval["case_output"])
        self.assertEqual(approval["qa_summary"], "PASS · 97.0점")
        cases = self.center.list_case_results(status="PASS", minimum_score=90)
        self.assertEqual(cases[0]["case_id"], "TC-01")
        self.assertTrue(self.center.version_history())
        with self.assertRaises(ValueError):
            self.center.create_approval(
                run_id, "QA 리드", "REJECTED", final_deployment_approved=True
            )

    def test_corrupted_approval_comment_is_flagged_without_losing_case_data(self):
        self.center.sync_reports()
        run_id = self.center.list_runs()[0]["run_id"]
        approval = self.center.create_approval(
            run_id, "QA 담당자", "REVIEWING", "? ?? ?????", case_id="TC-01"
        )

        self.assertTrue(approval["comment_corrupted"])
        self.assertEqual(approval["case_question"], "결제 후 주문 조회가 안 됩니다.")
        self.assertTrue(approval["case_output"])

    def test_unittest_identifier_has_human_readable_descriptor(self):
        descriptor = describe_automated_test(
            "quality_diagnosis.test_agent_unit.AgentUnitTests."
            "test_evaluator_selects_highest_scored_candidate",
            "PASS",
        )

        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor["case_number"], "AGENT-03")
        self.assertEqual(descriptor["title"], "Evaluator 최고 점수 후보 선택 검증")
        self.assertIn("winner가 S0", descriptor["expected"])
        self.assertIn("PASS", descriptor["actual"])


if __name__ == "__main__":
    unittest.main()
