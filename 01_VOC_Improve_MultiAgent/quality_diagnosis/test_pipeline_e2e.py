"""자연어 질문부터 6개 Agent와 품질 판정까지 전체 경로를 검증합니다."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from e2e_runner import ROOT, run


class PipelineE2ETests(unittest.IsolatedAsyncioTestCase):
    def test_quality_catalog_contains_exactly_twenty_cases(self):
        catalog = json.loads(
            (ROOT / "quality_diagnosis" / "test_cases.json").read_text(encoding="utf-8")
        )
        expected = json.loads(
            (ROOT / "quality_diagnosis" / "expected_results.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(catalog), 20)
        self.assertEqual(len(expected), 20)
        self.assertEqual(sum(case["scenario_type"] == "fault" for case in catalog), 2)
        self.assertEqual(len({case["case_id"] for case in catalog}), 20)

    async def test_feature_cases_complete_expected_agent_path(self):
        with tempfile.TemporaryDirectory() as directory:
            result = await run("offline", ROOT / "test_cases.txt", Path(directory))
            report = json.loads(Path(result["json"]).read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["passed"], 18)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(sum(report["summary"]["rubric_averages"][key]["max_score"] for key in report["summary"]["rubric_averages"]), 100)
        for row in report["results"]:
            agents = [stage["agent"] for stage in row["analysis"].get("stages", [])]
            if row["analysis"].get("message") == "clarification_required":
                self.assertEqual(agents, ["Interpreter"])
            elif row["analysis"].get("error_code") == "NO_MATCHING_VOC":
                self.assertEqual(agents, ["Interpreter", "Retriever"])
            else:
                self.assertEqual(
                    agents,
                    ["Interpreter", "Retriever", "Summarizer", "Evaluator", "Critic", "Improver"],
                )


if __name__ == "__main__":
    unittest.main()
