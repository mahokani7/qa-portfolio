"""quality_diagnosis의 모든 자동 테스트를 실행하고 통합 결과를 저장합니다."""

from __future__ import annotations

import csv
import io
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path


QUALITY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QUALITY_ROOT.parent
REPORTS = QUALITY_ROOT / "reports"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quality_diagnosis.evidence_report import write_execution_evidence
from quality_diagnosis.qa_control_center import describe_automated_test


MODULES = [
    "quality_diagnosis.test_agent_unit",
    "quality_diagnosis.test_pipeline_e2e",
    "quality_diagnosis.test_fault_tolerance",
    "quality_diagnosis.test_mcp_tools",
    "quality_diagnosis.test_llm_judge",
    "quality_diagnosis.test_release_defects",
]


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[dict[str, object]] = []

    @staticmethod
    def _record(test, status: str, detail: str) -> dict[str, object]:
        test_id = test.id()
        descriptor = describe_automated_test(test_id, status, detail)
        return {
            "test": test_id,
            "status": status,
            "detail": detail,
            "test_descriptor": descriptor or {},
        }

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append(self._record(test, "PASS", ""))

    def addFailure(self, test, err):
        super().addFailure(test, err)
        detail = self._exc_info_to_string(err, test)
        self.records.append(self._record(test, "FAIL", detail))

    def addError(self, test, err):
        super().addError(test, err)
        detail = self._exc_info_to_string(err, test)
        self.records.append(self._record(test, "ERROR", detail))


def main() -> int:
    suite = unittest.TestSuite(
        unittest.defaultTestLoader.loadTestsFromName(module) for module in MODULES
    )
    output = io.StringIO()
    result: RecordingResult = unittest.TextTestRunner(
        stream=output, verbosity=2, resultclass=RecordingResult
    ).run(suite)
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": result.testsRun,
        "passed": sum(row["status"] == "PASS" for row in result.records),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "results": result.records,
    }
    (REPORTS / "test_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (REPORTS / "test_result.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=(
            "case_number", "title", "category", "description", "expected", "actual",
            "status", "detail", "test", "source",
        ))
        writer.writeheader()
        for row in result.records:
            descriptor = row.get("test_descriptor") if isinstance(row.get("test_descriptor"), dict) else {}
            writer.writerow({
                "case_number": descriptor.get("case_number", ""),
                "title": descriptor.get("title", ""),
                "category": descriptor.get("category", ""),
                "description": descriptor.get("description", ""),
                "expected": descriptor.get("expected", ""),
                "actual": descriptor.get("actual", ""),
                "status": row["status"],
                "detail": row["detail"],
                "test": row["test"],
                "source": descriptor.get("source", ""),
            })
    (REPORTS / "pytest_result.txt").write_text(output.getvalue(), encoding="utf-8")
    evidence = write_execution_evidence("quality_suite", payload, REPORTS)
    print(output.getvalue())
    print(json.dumps({
        **{key: payload[key] for key in ("total", "passed", "failed", "errors", "successful")},
        "evidence": evidence,
    }, ensure_ascii=False, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
