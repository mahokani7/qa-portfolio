import unittest

from quality_diagnosis.repeatability import analyze_trials


def _row(score: float, passed: bool = True, summary: str = "같은 답변"):
    return {
        "case_id": "TC-01",
        "question": "질문",
        "quality": {"score": score, "passed": passed},
        "analysis": {
            "summary": summary,
            "policy": "같은 정책",
            "metrics": {"total_duration_ms": 10},
        },
    }


class RepeatabilityTests(unittest.TestCase):
    def test_stable_trials_pass(self):
        result = analyze_trials([[_row(95)], [_row(95.5)], [_row(94.8)]])[0]
        self.assertTrue(result["stable"])
        self.assertEqual(result["status"], "PASS")
        self.assertLessEqual(result["score_stddev"], 1.0)

    def test_status_flip_is_flaky(self):
        result = analyze_trials([[_row(95, True)], [_row(75, False)]])[0]
        self.assertFalse(result["stable"])
        self.assertTrue(result["status_flip"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["status_change_count"], 1)

    def test_independent_judge_disagreement_is_flaky(self):
        first = _row(95)
        second = _row(95)
        first["judge"] = {"decision": "배포 가능", "total_score": 96}
        second["judge"] = {"decision": "배포 보류", "total_score": 80}
        result = analyze_trials([[first], [second]])[0]
        self.assertTrue(result["judge_disagreement"])
        self.assertFalse(result["stable"])

    def test_requires_at_least_two_trials(self):
        with self.assertRaises(ValueError):
            analyze_trials([[_row(95)]])


if __name__ == "__main__":
    unittest.main()
