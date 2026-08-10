"""
pytest 실행 결과(JUnit XML)와 coverage 결과(Cobertura XML)를 읽어
tests_output/test_results.md 에 자동 테스트 결과 리포트를 생성합니다.

실행 순서:
1) pytest 실행 (pytest.ini의 --junitxml, --cov-report=xml 옵션으로 tests_output/에 원본 결과 저장)
2) python scripts/generate_test_report_md.py 실행 (이 스크립트가 tests_output/test_results.md 생성)
"""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "tests_output"
JUNIT_XML = OUTPUT_DIR / "junit.xml"
COVERAGE_XML = OUTPUT_DIR / "coverage.xml"
REPORT_MD = OUTPUT_DIR / "test_results.md"


def parse_junit(junit_path: Path) -> dict:
    tree = ET.parse(junit_path)
    root = tree.getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root

    cases = []
    for case in suite.findall("testcase"):
        status = "PASS"
        detail = ""
        failure = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if failure is not None:
            status = "FAIL"
            detail = (failure.get("message") or "")[:120]
        elif error is not None:
            status = "ERROR"
            detail = (error.get("message") or "")[:120]
        elif skipped is not None:
            status = "SKIP"
            detail = (skipped.get("message") or "")[:120]

        cases.append({
            "name": f"{case.get('classname')}::{case.get('name')}",
            "status": status,
            "time": float(case.get("time", 0.0)),
            "detail": detail,
        })

    return {
        "total": int(suite.get("tests", 0)),
        "failures": int(suite.get("failures", 0)),
        "errors": int(suite.get("errors", 0)),
        "skipped": int(suite.get("skipped", 0)),
        "time": float(suite.get("time", 0.0)),
        "cases": cases,
    }


def parse_coverage(coverage_path: Path) -> float:
    tree = ET.parse(coverage_path)
    root = tree.getroot()
    return float(root.get("line-rate", 0.0)) * 100


def build_markdown(junit: dict, coverage_pct: float) -> str:
    passed = junit["total"] - junit["failures"] - junit["errors"] - junit["skipped"]
    lines = [
        "# 자동 테스트 결과 (pytest)",
        "",
        f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 요약",
        "",
        f"- 총 테스트: {junit['total']}건",
        f"- 통과(PASS): {passed}건",
        f"- 실패(FAIL): {junit['failures']}건",
        f"- 오류(ERROR): {junit['errors']}건",
        f"- 스킵(SKIP): {junit['skipped']}건",
        f"- 실행 시간: {junit['time']:.2f}초",
        f"- 코드 커버리지: {coverage_pct:.1f}%",
        "",
        f"> {junit['total']} passed, coverage: {coverage_pct:.0f}%" if junit["failures"] == 0 and junit["errors"] == 0
        else f"> {passed}/{junit['total']} passed, coverage: {coverage_pct:.0f}%",
        "",
        "## 개별 테스트 결과",
        "",
        "| 테스트 | 상태 | 소요시간(s) | 비고 |",
        "|---|---|---|---|",
    ]
    for case in junit["cases"]:
        lines.append(f"| {case['name']} | {case['status']} | {case['time']:.3f} | {case['detail']} |")

    lines += [
        "",
        "## 해석 — 자동 테스트의 역할",
        "",
        "자동 테스트는 \"오류 발견\"에서 끝나는 것이 아니라, 결함 원인을 찾고 수정 우선순위를 정하는 근거로 사용합니다.",
        "실패(FAIL)한 테스트가 있다면 어떤 모듈·함수가 깨졌는지 위 표에서 바로 확인해 우선순위를 정합니다.",
    ]
    return "\n".join(lines)


def main():
    if not JUNIT_XML.exists() or not COVERAGE_XML.exists():
        print(f"[Error] {JUNIT_XML} 또는 {COVERAGE_XML}이 없습니다. 먼저 `pytest`를 실행하세요.")
        sys.exit(1)

    junit = parse_junit(JUNIT_XML)
    coverage_pct = parse_coverage(COVERAGE_XML)
    markdown = build_markdown(junit, coverage_pct)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(markdown, encoding="utf-8")
    print(f"[Success] 저장 완료: {REPORT_MD}")
    print(f"  {junit['total']} tests, coverage: {coverage_pct:.1f}%")


if __name__ == "__main__":
    main()
