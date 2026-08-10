"""AWS S3 업로드용 QA 증적 패키지를 만듭니다.

3팀(LLM Judge 품질평가) 발표·시연 기준 산출물:
  pytest_result.txt / pytest_report.html / junit_result.xml
  llm_judge_result.csv / llm_judge_result.json
  quality_score_report.md / deployment_decision.md
  MANIFEST.md (SHA256 무결성 목록)

사용:
  .venv/Scripts/python.exe scripts/build_aws_evidence.py
  .venv/Scripts/python.exe scripts/build_aws_evidence.py --skip-pytest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS = PROJECT_ROOT / "quality_diagnosis" / "reports"
OUTPUT = PROJECT_ROOT / "aws_upload" / "qa_evidence"

PYTEST_TARGETS = [
    "quality_diagnosis/test_agent_unit.py",
    "quality_diagnosis/test_pipeline_e2e.py",
    "quality_diagnosis/test_fault_tolerance.py",
    "quality_diagnosis/test_mcp_tools.py",
    "quality_diagnosis/test_llm_judge.py",
    "quality_diagnosis/test_release_defects.py",
]

RUBRIC_LABELS = {
    "accuracy": ("정확성", 25),
    "summary_faithfulness": ("요약 충실성", 20),
    "policy_specificity": ("정책 구체성", 20),
    "usefulness": ("유용성", 20),
    "safety": ("안전성", 15),
}


def run_pytest() -> None:
    """pytest를 실행해 TXT·HTML·JUnit 3종 증적을 만듭니다."""
    common = [
        sys.executable, "-m", "pytest", *PYTEST_TARGETS, "-v", "-p", "no:cacheprovider",
    ]
    reports = [
        f"--html={OUTPUT / 'pytest_report.html'}",
        "--self-contained-html",
        f"--junitxml={OUTPUT / 'junit_result.xml'}",
    ]
    subprocess.run(common + reports, cwd=PROJECT_ROOT, check=False)
    with (OUTPUT / "pytest_result.txt").open("w", encoding="utf-8") as handle:
        subprocess.run(common, cwd=PROJECT_ROOT, check=False, stdout=handle, stderr=handle)


def latest_live_judge() -> Path:
    """파일 수정시각이 아니라 실제 실행시각 기준 최신 LLM Judge를 고릅니다."""
    candidates = []
    for path in REPORTS.glob("llm_judge_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("live_llm_judge_verified") and data.get("results"):
            generated_at = str(data.get("generated_at") or "")
            candidates.append((generated_at, len(data["results"]), path))
    if not candidates:
        raise SystemExit("실제 LLM Judge 결과가 없습니다. llm_judge.py를 먼저 실행하세요.")
    return max(candidates)[2]


def judge_dimension_table(csv_path: Path) -> list[str]:
    """Judge CSV에서 5개 평가 차원의 평균을 표로 만듭니다."""
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8-sig").splitlines()))
    lines = ["| Judge 평가 항목 | 평균 획득점수 | 배점 |", "| --- | ---: | ---: |"]
    for key, (label, maximum) in RUBRIC_LABELS.items():
        values = [float(row[key]) for row in rows]
        lines.append(f"| {label} | {sum(values) / len(values):.2f} | {maximum} |")
    decisions: dict[str, int] = {}
    for row in rows:
        decisions[row["decision"]] = decisions.get(row["decision"], 0) + 1
    lines.append("")
    lines.append(f"- 평가 케이스: {len(rows)}건")
    for decision, count in sorted(decisions.items(), key=lambda item: -item[1]):
        lines.append(f"- 판정 `{decision}`: {count}건")
    violations = sum(1 for row in rows if row.get("critical_violations"))
    lines.append(f"- 중대 위반: {violations}건")
    return lines


def build_quality_report(judge_json: Path, judge_csv: Path) -> None:
    """통합 점수 보고서에 Judge 5개 차원 상세를 덧붙입니다."""
    base = (REPORTS / "quality_score_report.md").read_text(encoding="utf-8")
    judge = json.loads(judge_json.read_text(encoding="utf-8"))
    source_path = Path(str(judge.get("source_report") or ""))
    source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    package_at = datetime.now().astimezone().isoformat(timespec="seconds")
    body = "\n".join([
        base.rstrip(),
        "",
        "## 증적 날짜 구분",
        "",
        f"- 라이브 E2E 실행 시각: {source.get('summary', {}).get('generated_at') or source.get('generated_at')}",
        f"- 독립 LLM Judge 실행 시각: {judge.get('generated_at')}",
        f"- AWS 제출 패키지 생성 시각: {package_at}",
        "- 패키지 생성일에 라이브 E2E·Judge를 재실행한 것은 아닙니다.",
        "",
        "## 독립 LLM Judge 상세",
        "",
        f"- Judge 제공자: {judge.get('provider')} / 모델 {judge.get('model')}",
        f"- 생성 시각: {judge.get('generated_at')}",
        f"- 실제 LLM Judge 검증: {judge.get('live_llm_judge_verified')}",
        "",
        *judge_dimension_table(judge_csv),
        "",
        "> 생성 모델(OpenAI)이 만든 결과를 평가 모델(Anthropic)이 채점하는 독립 평가 구조입니다.",
    ])
    (OUTPUT / "quality_score_report.md").write_text(body + "\n", encoding="utf-8")


def build_deployment_report(judge_json: Path) -> None:
    """배포판정에 평가 실행일과 패키지 생성일을 명시합니다."""
    base = (REPORTS / "deployment_decision.md").read_text(encoding="utf-8")
    base = base.replace("- 생성 시각:", "- 배포판정 보고서 원본 생성 시각:", 1)
    judge = json.loads(judge_json.read_text(encoding="utf-8"))
    source_path = Path(str(judge.get("source_report") or ""))
    source = json.loads(source_path.read_text(encoding="utf-8")) if source_path.is_file() else {}
    e2e_at = source.get("summary", {}).get("generated_at") or source.get("generated_at")
    package_at = datetime.now().astimezone().isoformat(timespec="seconds")
    notice = "\n".join([
        "",
        "> **날짜 구분**",
        f"> - 라이브 E2E 실행: {e2e_at}",
        f"> - 독립 LLM Judge 실행: {judge.get('generated_at')}",
        f"> - AWS 제출 패키지 생성: {package_at}",
        "> - 패키지 생성일에 라이브 E2E·Judge를 재실행한 것은 아닙니다.",
        "",
    ])
    title, remainder = base.split("\n", 1)
    (OUTPUT / "deployment_decision.md").write_text(title + notice + remainder, encoding="utf-8")


def write_manifest() -> None:
    """업로드 전 무결성 확인용 SHA256 목록을 남깁니다."""
    lines = [
        "# QA 증적 매니페스트",
        "",
        f"- 생성 시각: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        "- 용도: S3 업로드 전후 파일 무결성 대조",
        "",
        "| 파일 | 크기(byte) | SHA256 |",
        "| --- | ---: | --- |",
    ]
    for path in sorted(OUTPUT.iterdir()):
        if path.name == "MANIFEST.md" or not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"| {path.name} | {path.stat().st_size} | `{digest}` |")
    (OUTPUT / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pytest", action="store_true", help="기존 pytest 증적을 재사용")
    args = parser.parse_args()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    if not args.skip_pytest:
        run_pytest()

    judge_json = latest_live_judge()
    judge_csv = judge_json.with_suffix(".csv")
    shutil.copy2(judge_json, OUTPUT / "llm_judge_result.json")
    shutil.copy2(judge_csv, OUTPUT / "llm_judge_result.csv")
    build_deployment_report(judge_json)
    build_quality_report(judge_json, judge_csv)
    write_manifest()

    print(f"증적 패키지: {OUTPUT}")
    for path in sorted(OUTPUT.iterdir()):
        print(f"  {path.name:28} {path.stat().st_size:>9,} byte")


if __name__ == "__main__":
    main()
