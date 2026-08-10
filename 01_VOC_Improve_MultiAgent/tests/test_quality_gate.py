import json
import tempfile
import unittest
from pathlib import Path

from quality_diagnosis.quality_gate import run_quality_gate


class QualityGateTests(unittest.TestCase):
    def test_gate_combines_suite_red_team_and_e2e_with_junit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "test_result.json").write_text(
                json.dumps({"successful": True, "total": 10, "passed": 10}), encoding="utf-8"
            )
            (output / "red_team_1.json").write_text(
                json.dumps({"summary": {"successful": True, "total": 12, "passed": 12, "average_score": 100}}),
                encoding="utf-8",
            )
            (output / "ecommerce_offline_e2e_1.json").write_text(
                json.dumps({"summary": {"total": 2, "passed": 2, "failed": 0, "average_score": 96}}),
                encoding="utf-8",
            )
            result = run_quality_gate(
                output_dir=output,
                domain="ecommerce",
                minimum_score=95,
                execute_suite=False,
                execute_red_team=False,
            )
            self.assertTrue(result["summary"]["successful"])
            self.assertEqual(result["summary"]["verdict"], "PASS")
            self.assertEqual(len(result["results"]), 3)
            self.assertTrue(all(row.get("test_descriptor") for row in result["results"]))
            self.assertTrue(all("source" not in row["test_descriptor"] for row in result["results"]))
            self.assertTrue(Path(result["evidence"]["junit"]).is_file())

            held = run_quality_gate(
                output_dir=output,
                domain="ecommerce",
                minimum_score=99,
                execute_suite=False,
                execute_red_team=False,
            )
            self.assertFalse(held["summary"]["successful"])
            self.assertEqual(held["summary"]["verdict"], "HOLD")


if __name__ == "__main__":
    unittest.main()
