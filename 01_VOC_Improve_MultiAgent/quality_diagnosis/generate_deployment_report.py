"""기능·장애·Judge 증적을 합쳐 현재 배포 판단 문서를 생성합니다."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

QUALITY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QUALITY_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.deployment_policy import evaluate_release_evidence, load_deployment_config


REPORTS = QUALITY_ROOT / "reports"


def _latest(pattern: str) -> Path | None:
    matches = [path for path in REPORTS.glob(pattern) if path.is_file()]
    return max(matches, key=lambda path: path.stat().st_mtime) if matches else None


def _latest_judge() -> Path | None:
    matches = [path for path in REPORTS.glob("llm_judge_*.json") if path.is_file()]
    return max(
        matches,
        key=lambda path: (
            0 if "deterministic" in path.name else 1,
            path.stat().st_mtime,
        ),
    ) if matches else None


def _read(path: Path | None) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path and path.is_file() else {}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2e", type=Path)
    parser.add_argument("--judge", type=Path)
    args = parser.parse_args()
    test_result = _read(REPORTS / "test_result.json")
    e2e_path = (
        args.e2e
        or _latest("*live_retest_merged_e2e_*.json")
        or _latest("*live_e2e_*.json")
        or _latest("*offline_e2e_*.json")
    )
    e2e = _read(e2e_path)
    fault = _read(_latest("fault_diagnosis_*.json"))
    judge = _read(args.judge or _latest_judge())
    e2e_summary = e2e.get("summary") or {}
    config = load_deployment_config()
    assessment = evaluate_release_evidence(
        test_result, fault, e2e, judge, config["minimum_score"]
    )
    blockers = assessment["blockers"] + assessment["approval_requirements"]
    decision = assessment["label"]
    report = "\n".join([
        "# 최종 배포 판단",
        "",
        f"- 생성 시각: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 현재 판단: **{decision}**",
        f"- 배포 기준 점수: **{assessment['minimum_score']}/100**",
        f"- 현재 통합 점수(낮은 증적 기준): **{assessment['overall_score']}/100**",
        "",
        "## 증적 요약",
        "",
        f"- 품질진단 자동 테스트: {test_result.get('passed', 0)}/{test_result.get('total', 0)} PASS",
        f"- 장애 진단: {fault.get('passed', 0)}/{fault.get('total', 0)} PASS",
        f"- 라이브 E2E: {e2e_summary.get('passed', 0)}/{e2e_summary.get('total', 0)} PASS",
        f"- 라이브 평균 점수: {e2e_summary.get('average_score', 0)}/100",
        f"- Judge 평균 점수: {judge.get('average_score', 0)}/100",
        f"- 실제 LLM Judge 확인: {judge.get('live_llm_judge_verified', False)}",
        f"- Judge 중대 위반: {assessment['judge_violation_count']}건",
        "",
        "## 정식 승인 전 필수 조건",
        "",
        *[f"- {item}" for item in blockers],
        "",
        "자동·LLM 평가가 통과해도 정식 배포에는 사람 검토 승인이 필요합니다.",
    ])
    (REPORTS / "deployment_decision.md").write_text(report, encoding="utf-8")
    (REPORTS / "quality_score_report.md").write_text("\n".join([
        "# 통합 품질 점수 보고서",
        "",
        f"- 라이브 E2E 평균: {e2e_summary.get('average_score', 0)}/100",
        f"- Judge 평균: {judge.get('average_score', 0)}/100",
        f"- 배포 기준: {assessment['minimum_score']}/100",
        f"- 통합 점수(낮은 증적 기준): {assessment['overall_score']}/100",
        f"- 중대 위반: {e2e_summary.get('hard_blocked', 0)}건",
        f"- 자동 테스트 성공: {test_result.get('successful', False)}",
        f"- 라이브 품질 검증: {e2e_summary.get('live_quality_verified', False)}",
    ]), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
