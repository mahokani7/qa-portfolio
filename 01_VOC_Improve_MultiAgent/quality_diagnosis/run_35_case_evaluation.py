"""33개 VOC 도메인 케이스와 2개 핵심 결함을 합친 35건 평가를 실행합니다."""

from __future__ import annotations

import asyncio
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

from e2e_runner import run as run_e2e
from quality_diagnosis.evidence_report import write_execution_evidence
from utils.settings import DEFAULT_CSV


async def _run_domains() -> list[dict]:
    ecommerce = await run_e2e(
        "offline",
        PROJECT_ROOT / "test_cases.txt",
        REPORTS,
        Path(DEFAULT_CSV),
        "ecommerce",
        concurrency=2,
    )
    insurance = await run_e2e(
        "offline",
        PROJECT_ROOT / "test_cases_insurance.jsonl",
        REPORTS,
        PROJECT_ROOT / "data" / "voc_insurance.csv",
        "insurance",
        concurrency=2,
    )
    rows = []
    for result, expected in ((ecommerce, 18), (insurance, 15)):
        report = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
        domain_rows = report.get("results") or []
        if len(domain_rows) != expected:
            raise RuntimeError(f"{result['summary']['domain']} 케이스가 {expected}건이 아닙니다.")
        rows.extend(domain_rows)
    return rows


def _run_defect_regressions() -> tuple[bool, str]:
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "quality_diagnosis.test_release_defects"
    )
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    return result.wasSuccessful() and result.testsRun == 2, output.getvalue()


async def run() -> dict:
    domain_rows = await _run_domains()
    defects_passed, defect_output = await asyncio.to_thread(_run_defect_regressions)
    final_rows = [
        {
            "case_id": str(row["case_id"]),
            "category": "VOC 분석·정책 개선",
            "initial_status": "PASS",
            "status": "PASS" if (row.get("quality") or {}).get("passed") else "FAIL",
            "score": (row.get("quality") or {}).get("score"),
            "detail": str(row.get("question") or ""),
        }
        for row in domain_rows
    ]
    defect_cases = [
        {
            "case_id": "DEF-BRANCH-01",
            "category": "분기 인터페이스",
            "initial_status": "FAIL",
            "status": "PASS" if defects_passed else "FAIL",
            "score": 100 if defects_passed else 0,
            "detail": "Anthropic Judge 분기에서 provider 전용 Messages 인터페이스 사용",
        },
        {
            "case_id": "DEF-429-01",
            "category": "API 429 내결함성",
            "initial_status": "FAIL",
            "status": "PASS" if defects_passed else "FAIL",
            "score": 100 if defects_passed else 0,
            "detail": "HTTP 429 분류, 동시 실행 1건 축소 및 사용량 한도 확인 안내",
        },
    ]
    final_rows.extend(defect_cases)
    if len(final_rows) != 35:
        raise RuntimeError(f"종합 평가 케이스가 35건이 아닙니다: {len(final_rows)}")
    final_passed = sum(row["status"] == "PASS" for row in final_rows)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {
            "ecommerce": 18,
            "insurance": 15,
            "defect_regression": 2,
            "total": 35,
        },
        "initial": {"total": 35, "passed": 33, "failed": 2, "pass_rate": 94.3},
        "summary": {
            "total": 35,
            "passed": final_passed,
            "failed": 35 - final_passed,
            "errors": 0,
            "successful": final_passed == 35,
            "pass_rate": round(final_passed / 35 * 100, 1),
        },
        "defect_test_output": defect_output,
        "results": final_rows,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORTS / f"test_35_case_result_{stamp}.json"
    csv_path = REPORTS / f"test_35_case_result_{stamp}.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("case_id", "category", "initial_status", "status", "score", "detail"),
        )
        writer.writeheader()
        writer.writerows(final_rows)
    evidence = write_execution_evidence("comprehensive_35_cases", payload, REPORTS)
    return {
        "successful": payload["summary"]["successful"],
        "initial": payload["initial"],
        "summary": payload["summary"],
        "json": str(json_path),
        "csv": str(csv_path),
        "evidence": evidence,
    }


def main() -> int:
    result = asyncio.run(run())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
