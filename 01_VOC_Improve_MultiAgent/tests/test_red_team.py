import io
import tempfile
import unittest
from pathlib import Path

from quality_diagnosis.red_team import run_red_team
from quality_diagnosis.run_fault_diagnosis import RecordingResult


class RedTeamTests(unittest.TestCase):
    def test_all_deterministic_security_checks_pass_and_create_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_red_team(Path(directory))
            self.assertEqual(result["summary"]["total"], 20)
            self.assertEqual(result["summary"]["failed"], 0)
            self.assertTrue(result["summary"]["successful"])
            self.assertEqual({row["status"] for row in result["results"]}, {"PASS"})
            self.assertEqual(len({row["test_descriptor"]["case_number"] for row in result["results"]}), 20)
            for row in result["results"]:
                descriptor = row["test_descriptor"]
                self.assertTrue(descriptor["title"])
                self.assertTrue(descriptor["description"])
                self.assertTrue(descriptor["expected"])
                self.assertNotIn("source", descriptor)
                self.assertNotIn("internal_id", descriptor)
            for path in result["evidence"].values():
                self.assertTrue(Path(path).is_file())

    def test_fault_diagnosis_records_only_qa_facing_descriptor(self):
        suite = unittest.defaultTestLoader.loadTestsFromName(
            "quality_diagnosis.test_fault_tolerance.SynchronousFaultTests.test_missing_api_key_is_not_hidden"
        )
        result = unittest.TextTestRunner(
            stream=io.StringIO(), resultclass=RecordingResult
        ).run(suite)

        self.assertTrue(result.wasSuccessful())
        row = result.records[0]
        self.assertEqual(row["test"], "FAULT-06")
        self.assertNotIn("quality_diagnosis.", str(row))
        self.assertNotIn("source", row["test_descriptor"])
        self.assertNotIn("internal_id", row["test_descriptor"])


if __name__ == "__main__":
    unittest.main()
