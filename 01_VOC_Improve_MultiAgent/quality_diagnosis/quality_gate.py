"""CI-friendly deterministic quality gate with JUnit evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from quality_diagnosis.evidence_report import write_execution_evidence
from quality_diagnosis.red_team import run_red_team
from quality_diagnosis.run_quality_suite import main as run_quality_suite_main
from utils.deployment_policy import load_deployment_config


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "quality_diagnosis" / "reports"


def _load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _latest(directory: Path, pattern: str) -> Path | None:
    paths = [path for path in directory.glob(pattern) if path.is_file()]
    return max(paths, key=lambda path: path.stat().st_mtime) if paths else None


def run_quality_gate(
    *,
    output_dir: Path = REPORTS,
    domain: str = "ecommerce",
    minimum_score: float | None = None,
    execute_suite: bool = True,
    execute_red_team: bool = True,
) -> dict[str, Any]:
    if domain not in {"ecommerce", "insurance"}:
        raise ValueError("domain은 ecommerce 또는 insurance여야 합니다.")
    threshold = float(
        load_deployment_config()["minimum_score"] if minimum_score is None else minimum_score
    )
    if not 0 <= threshold <= 100:
        raise ValueError("품질 게이트 기준 점수는 0~100이어야 합니다.")
    output_dir.mkdir(parents=True, exist_ok=True)

    suite_exit = run_quality_suite_main() if execute_suite else 0
    suite = _load(output_dir / "test_result.json")
    red_team = (
        run_red_team(output_dir)
        if execute_red_team
        else {"summary": _load(_latest(output_dir, "red_team_*.json")).get("summary", {})}
    )
    red_summary = red_team.get("summary") or {}
    e2e_path = _latest(output_dir, f"{domain}_offline_e2e_*.json")
    e2e = _load(e2e_path)
    e2e_summary = e2e.get("summary") if isinstance(e2e.get("summary"), dict) else {}

    components = [
        {
            "case_id": "GATE-AUTOMATED-SUITE",
            "component": "자동 품질 테스트",
            "status": "PASS" if suite_exit == 0 and suite.get("successful") else "FAIL",
            "score": 100 if suite_exit == 0 and suite.get("successful") else 0,
            "detail": f"{suite.get('passed', 0)}/{suite.get('total', 0)} PASS",
        },
        {
            "case_id": "GATE-RED-TEAM",
            "component": "OWASP Red Team",
            "status": "PASS" if red_summary.get("successful") else "FAIL",
            "score": float(red_summary.get("average_score") or 0),
            "detail": f"{red_summary.get('passed', 0)}/{red_summary.get('total', 0)} PASS",
        },
        {
            "case_id": "GATE-OFFLINE-E2E",
            "component": f"{domain} 오프라인 E2E",
            "status": "PASS" if (
                e2e_summary
                and int(e2e_summary.get("failed") or 0) == 0
                and float(e2e_summary.get("average_score") or 0) >= threshold
            ) else "FAIL",
            "score": float(e2e_summary.get("average_score") or 0),
            "detail": (
                f"{e2e_summary.get('passed', 0)}/{e2e_summary.get('total', 0)} PASS · "
                f"평균 {e2e_summary.get('average_score', 0)}점 · 기준 {threshold}점"
                if e2e_summary else "오프라인 E2E 보고서 없음"
            ),
        },
    ]
    gate_descriptors = {
        "GATE-AUTOMATED-SUITE": (
            "자동 품질 테스트 통과", "기능·Agent·MCP·Judge 계약 검증",
            "자동 품질 테스트가 모두 PASS하고 실행 오류가 없어야 합니다.",
        ),
        "GATE-RED-TEAM": (
            "OWASP 보안 진단 통과", "프롬프트 공격·개인정보·권한·비용 공격 검증",
            "20개 보안 시나리오가 모두 PASS해야 합니다.",
        ),
        "GATE-OFFLINE-E2E": (
            "오프라인 E2E 배포 기준 충족", f"{domain} 전체 파이프라인 품질 검증",
            f"실패 케이스가 없고 평균 점수가 배포 기준 {threshold}점 이상이어야 합니다.",
        ),
    }
    for row in components:
        title, description, expected = gate_descriptors[row["case_id"]]
        row["test_descriptor"] = {
            "case_number": row["case_id"],
            "title": title,
            "category": "CI 품질 게이트",
            "description": description,
            "expected": expected,
            "actual": row["detail"],
            "scored": "true",
        }
    passed = sum(row["status"] == "PASS" for row in components)
    scores = [float(row["score"]) for row in components]
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "domain": domain,
        "mode": "ci",
        "total": len(components),
        "passed": passed,
        "failed": len(components) - passed,
        "errors": 0,
        "pass_rate": round(passed / len(components) * 100, 1),
        "average_score": round(sum(scores) / len(scores), 1),
        "minimum_score": threshold,
        "successful": passed == len(components),
        "verdict": "PASS" if passed == len(components) else "HOLD",
    }
    payload = {
        "summary": summary,
        "inputs": {
            "quality_suite": "test_result.json",
            "red_team": red_team.get("report") if isinstance(red_team, dict) else None,
            "e2e": e2e_path.name if e2e_path else None,
        },
        "results": components,
    }
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    report_path = output_dir / f"quality_gate_{domain}_{stamp}.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence = write_execution_evidence(f"quality_gate_{domain}", payload, output_dir)
    return {
        "summary": summary,
        "report": str(report_path),
        "evidence": evidence,
        "results": components,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=("ecommerce", "insurance"), default="ecommerce")
    parser.add_argument("--minimum-score", type=float)
    parser.add_argument("--skip-suite", action="store_true")
    parser.add_argument("--skip-red-team", action="store_true")
    args = parser.parse_args()
    result = run_quality_gate(
        domain=args.domain,
        minimum_score=args.minimum_score,
        execute_suite=not args.skip_suite,
        execute_red_team=not args.skip_red_team,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["summary"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
