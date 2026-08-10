"""장애 진단 전용 테스트를 실행하고 JSON/Markdown 보고서를 생성합니다."""

from __future__ import annotations

import io
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quality_diagnosis.evidence_report import write_execution_evidence
from quality_diagnosis.qa_control_center import describe_automated_test


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[dict[str, str]] = []

    def _record(self, test, status: str, detail: str = "") -> None:
        descriptor = describe_automated_test(test.id(), status, detail) or {}
        # 보안 진단 화면과 증적에는 QA가 판단할 정보만 저장합니다.
        descriptor.pop("source", None)
        descriptor.pop("internal_id", None)
        self.records.append({
            "test": descriptor.get("case_number") or test.id(),
            "status": status,
            "detail": descriptor.get("actual") or detail,
            "test_descriptor": descriptor,
        })

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR", self._exc_info_to_string(err, test))


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "quality_diagnosis.test_fault_tolerance"
    )
    output = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=output,
        verbosity=2,
        resultclass=RecordingResult,
    )
    result: RecordingResult = runner.run(suite)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    json_path = REPORTS / f"fault_diagnosis_{stamp}.json"
    markdown_path = REPORTS / f"fault_diagnosis_{stamp}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = [
        f"| {row['test_descriptor'].get('case_number', row['test'])} · {row['test_descriptor'].get('title', '')} | {row['status']} |"
        for row in result.records
    ]
    markdown_path.write_text(
        "\n".join([
            "# 장애 진단 자동화 결과",
            "",
            f"- 실행 시각: {payload['generated_at']}",
            f"- 결과: {payload['passed']}/{payload['total']} PASS",
            f"- 실패: {payload['failed']}, 오류: {payload['errors']}",
            "",
            "| 시나리오 | 결과 |",
            "| --- | --- |",
            *rows,
        ]),
        encoding="utf-8",
    )
    evidence = write_execution_evidence("fault_diagnosis", payload, REPORTS)
    print(output.getvalue())
    print(json.dumps({
        "successful": result.wasSuccessful(),
        "json": str(json_path),
        "markdown": str(markdown_path),
        "evidence": evidence,
    }, ensure_ascii=False, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
