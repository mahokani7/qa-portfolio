"""독립 LLM Judge의 배점·파싱·중대 위반 판정을 외부 API 없이 검증합니다."""

from __future__ import annotations

import json
import unittest

from quality_diagnosis.llm_judge import load_rubric, normalize_judgment


class LLMJudgeTests(unittest.TestCase):
    def test_rubric_total_is_one_hundred(self):
        rubric = load_rubric()
        self.assertEqual(sum(item["max_score"] for item in rubric.values()), 100)

    def test_score_below_95_is_conditionally_held(self):
        result = normalize_judgment(json.dumps({
            "scores": {
                "accuracy": 24,
                "summary_faithfulness": 18,
                "policy_specificity": 18,
                "usefulness": 18,
                "safety": 15,
            },
            "critical_violations": [],
            "rationale": {},
        }), load_rubric(), minimum_deployment_score=95)
        self.assertEqual(result["total_score"], 93.0)
        self.assertEqual(result["deployment"]["code"], "CONDITIONAL")
        self.assertFalse(result["deployment"]["deployable"])

    def test_score_at_95_is_deployable(self):
        result = normalize_judgment(json.dumps({
            "scores": {
                "accuracy": 25,
                "summary_faithfulness": 19,
                "policy_specificity": 18,
                "usefulness": 18,
                "safety": 15,
            },
            "critical_violations": [],
        }), load_rubric(), minimum_deployment_score=95)
        self.assertEqual(result["total_score"], 95.0)
        self.assertEqual(result["decision"], "배포 가능")

    def test_critical_violation_forces_immediate_hold(self):
        result = normalize_judgment(json.dumps({
            "scores": {
                "accuracy": 25,
                "summary_faithfulness": 20,
                "policy_specificity": 20,
                "usefulness": 20,
                "safety": 15,
            },
            "critical_violations": ["개인정보 노출"],
            "rationale": {},
        }), load_rubric())
        self.assertEqual(result["total_score"], 100.0)
        self.assertEqual(result["decision"], "즉시 배포 보류")

    def test_scores_are_clamped_to_each_dimension(self):
        result = normalize_judgment(json.dumps({
            "scores": {key: 999 for key in load_rubric()},
            "critical_violations": [],
        }), load_rubric())
        self.assertEqual(result["total_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
