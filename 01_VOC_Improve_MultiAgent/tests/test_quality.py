from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from utils.deployment_policy import (
    evaluate_release_evidence,
    load_deployment_config,
    save_deployment_config,
    score_deployment_decision,
)
from quality_diagnosis.evidence_report import write_execution_evidence
from utils.quality_evaluator import evaluate_quality_case, validate_quality_case
from utils.validation import ValidationError


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _case(**overrides):
    case = {
        "case_id": "TC-QUALITY",
        "question": "결제는 완료되었는데 주문 내역에 보이지 않습니다.",
        "expected_intent": "결제 완료 후 주문 조회 실패",
        "expected_keywords": ["결제", "주문 내역", "주문 생성", "동기화"],
        "required_output": ["원인 추정", "고객 안내", "개선안", "우선순위"],
        "prohibited_output": [
            "근거 없는 환불 확정",
            "개인정보 요구",
            "무조건 시스템 오류라고 단정",
        ],
    }
    case.update(overrides)
    return case


def _successful_analysis(policy: str | None = None):
    summary = (
        "결제 완료 후 주문 내역에서 주문이 조회되지 않는 현상입니다. "
        "주문 생성 또는 동기화 지연이 원인일 가능성이 있습니다."
    )
    final_policy = policy or (
        "고객 안내: 주문 내역을 다시 확인하도록 안내합니다. "
        "개선안: 주문 생성과 동기화 상태를 점검합니다. "
        "우선순위: 담당 운영팀이 결제 완료 건을 최우선으로 확인하고 "
        "1주 이내 처리시간 20% 단축을 목표 지표로 관리합니다."
    )
    return {
        "ok": True,
        "error_code": None,
        "message": "success",
        "summary": summary,
        "policy": final_policy,
        "trace": "Interpreter; Retriever; Summarizer; Evaluator; Critic; Improver",
        "metrics": {
            "total_duration_ms": 1250,
            "stage_duration_ms": {"Interpreter": 100, "Retriever": 50, "Summarizer": 400},
        },
        "stages": [
            {
                "agent": "Interpreter",
                "output": {
                    "filters": ["결제", "주문 내역", "주문 생성", "동기화"]
                },
            },
            {
                "agent": "Retriever",
                "output": {
                    "samples": [
                        "결제 완료 후 주문 내역에 주문 생성이 반영되지 않아 동기화가 지연됩니다."
                    ]
                },
            },
            {
                "agent": "Summarizer",
                "output": {"candidates": {"S0": summary, "S1": summary + " 고객 안내 필요"}},
            },
            {
                "agent": "Evaluator",
                "output": {
                    "winner": "S0",
                    "scores": {"S0": 9.0, "S1": 8.0},
                    "selected_summary": summary,
                },
            },
            {
                "agent": "Critic",
                "output": {"need_refine": False, "edits": [], "ask_more_samples": False},
            },
            {
                "agent": "Improver",
                "output": {"policy": final_policy, "skipped": False},
            },
        ],
    }


class QualityCaseSchemaTests(unittest.TestCase):
    def test_all_jsonl_cases_have_required_expected_results(self):
        path = os.path.join(ROOT, "test_cases.txt")
        with open(path, encoding="utf-8") as stream:
            cases = [
                validate_quality_case(json.loads(line))
                for line in stream
                if line.strip() and not line.lstrip().startswith("#")
            ]

        self.assertEqual(len(cases), 18)
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        self.assertTrue(all(case["expected_keywords"] for case in cases))
        self.assertTrue(all(case["required_output"] for case in cases))

    def test_missing_expected_field_is_rejected(self):
        case = _case()
        del case["required_output"]
        with self.assertRaises(ValidationError):
            validate_quality_case(case)

    def test_empty_expected_result_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_quality_case(_case(expected_keywords=[]))


class QualityEvaluationTests(unittest.TestCase):
    def test_expected_elements_produce_pass_and_evidence(self):
        result = evaluate_quality_case(
            _case(), _successful_analysis(), minimum_deployment_score=95
        )

        self.assertTrue(result["passed"])
        self.assertGreaterEqual(result["score"], 90)
        self.assertEqual(sum(item["max_score"] for item in result["rubric"].values()), 100)
        self.assertEqual(result["deployment"]["code"], "CONDITIONAL")
        self.assertEqual(result["deployment"]["minimum_score"], 95)
        self.assertFalse(result["deployment"]["deployable"])
        self.assertTrue(result["checks"]["required_output"]["matched"])
        self.assertFalse(result["checks"]["prohibited_output"]["violations"])

    def test_prohibited_claim_produces_fail(self):
        analysis = _successful_analysis(
            "고객 안내 후 무조건 환불을 확정합니다. 개선안은 즉시 처리하며 우선순위는 최우선입니다."
        )
        result = evaluate_quality_case(_case(), analysis)

        self.assertFalse(result["passed"])
        self.assertEqual(result["deployment"]["code"], "IMMEDIATE_HOLD")
        self.assertIn("결제·환불 관련 잘못된 확정 안내", result["hard_blockers"])
        self.assertFalse(result["checks"]["prohibited_output"]["passed"])
        self.assertEqual(
            result["checks"]["prohibited_output"]["violations"][0]["item"],
            "근거 없는 환불 확정",
        )

    def test_expected_no_match_can_pass(self):
        case = _case(
            expected_status="no_match",
            expected_intent="검색 가능한 VOC 없음",
            expected_keywords=["검색 결과 없음"],
            required_output=["검색 결과 없음 안내"],
        )
        analysis = {
            "ok": False,
            "error_code": "NO_MATCHING_VOC",
            "note": "검색된 VOC가 없어 결과를 만들 수 없습니다.",
            "stages": [],
        }
        result = evaluate_quality_case(case, analysis)

        self.assertTrue(result["passed"])
        self.assertEqual(result["score"], 100.0)


class DeploymentPolicyTests(unittest.TestCase):
    def test_default_is_95_and_saved_value_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment_settings.json"
            self.assertEqual(load_deployment_config(path)["minimum_score"], 95)

            saved = save_deployment_config(97, path)
            self.assertEqual(saved["minimum_score"], 97)
            self.assertEqual(load_deployment_config(path)["source"], "saved")

    def test_95_is_deployable_and_94_9_is_not(self):
        self.assertTrue(score_deployment_decision(95, [], 95)["deployable"])
        self.assertFalse(score_deployment_decision(94.9, [], 95)["deployable"])

    def test_release_requires_both_live_scores_to_meet_threshold(self):
        assessment = evaluate_release_evidence(
            {"successful": True},
            {"successful": True},
            {"summary": {"failed": 0, "average_score": 96, "live_quality_verified": True}},
            {"average_score": 94, "live_llm_judge_verified": True, "results": []},
            95,
        )
        self.assertFalse(assessment["technical_pass"])
        self.assertEqual(assessment["overall_score"], 94)
        self.assertTrue(any("Judge 평균" in item for item in assessment["blockers"]))

    def test_formal_release_requires_final_human_approval(self):
        assessment = evaluate_release_evidence(
            {"successful": True},
            {"successful": True},
            {"summary": {"failed": 0, "average_score": 97, "live_quality_verified": True}},
            {"average_score": 96, "live_llm_judge_verified": True, "results": []},
            95,
            {"decision": "APPROVED", "final_deployment_approved": True},
        )
        self.assertTrue(assessment["technical_pass"])
        self.assertTrue(assessment["formal_deployable"])
        self.assertEqual(assessment["code"], "RELEASE_APPROVED")


class EvidenceReportTests(unittest.TestCase):
    def test_each_run_creates_txt_xml_html_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            files = write_execution_evidence(
                "unit_test",
                {
                    "total": 1,
                    "passed": 1,
                    "failed": 0,
                    "successful": True,
                    "results": [{"test": "TC-EVIDENCE", "status": "PASS", "detail": "ok"}],
                },
                output,
            )
            self.assertTrue(all(Path(path).is_file() for path in files.values()))
            self.assertIn("qualityEvidence", Path(files["xml"]).read_text(encoding="utf-8"))
            self.assertIn("testsuite", Path(files["junit"]).read_text(encoding="utf-8"))
            self.assertIn("VOC 품질 테스트 실행 증적", Path(files["html"]).read_text(encoding="utf-8"))
            self.assertTrue((output / "test_execution_history.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
