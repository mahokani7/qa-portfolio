"""Repeated E2E execution and flakiness analysis."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from e2e_runner import run as run_e2e
from quality_diagnosis.evidence_report import write_execution_evidence
from quality_diagnosis.llm_judge import run as run_llm_judge


def _load_results(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"반복 실행 결과 형식이 올바르지 않습니다: {path.name}")
    return [row for row in rows if isinstance(row, dict)]


def _normalize_output(row: dict[str, Any]) -> str:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    text = " ".join((str(analysis.get("summary") or ""), str(analysis.get("policy") or "")))
    return " ".join(text.lower().split())


def analyze_trials(trials: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if len(trials) < 2:
        raise ValueError("반복 안정성 분석에는 최소 2회 실행이 필요합니다.")
    by_case: dict[str, list[dict[str, Any]]] = {}
    for trial_number, rows in enumerate(trials, 1):
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            by_case.setdefault(case_id, []).append({"trial": trial_number, **row})
    results = []
    for case_id, rows in sorted(by_case.items()):
        statuses = [
            bool((row.get("quality") or {}).get("passed"))
            for row in rows
        ]
        scores = [float((row.get("quality") or {}).get("score") or 0) for row in rows]
        outputs = [_normalize_output(row) for row in rows]
        unique_outputs = len(set(outputs))
        score_stddev = statistics.pstdev(scores) if len(scores) > 1 else 0.0
        score_spread = max(scores) - min(scores) if scores else 0.0
        status_flip = len(set(statuses)) > 1
        status_change_count = sum(
            previous != current for previous, current in zip(statuses, statuses[1:])
        )
        judge_verdicts = [
            str((row.get("judge") or {}).get("decision") or "")
            for row in rows if (row.get("judge") or {}).get("decision")
        ]
        judge_scores = [
            _score for _score in (
                float((row.get("judge") or {}).get("total_score") or 0)
                for row in rows if row.get("judge")
            ) if _score >= 0
        ]
        judge_disagreement = len(set(judge_verdicts)) > 1
        missing_trials = len(trials) - len(rows)
        stable = (
            not status_flip and not judge_disagreement
            and score_stddev <= 1.0 and missing_trials == 0
        )
        stability_score = max(
            0.0,
            100.0 - score_stddev * 10 - score_spread * 2
            - (35 if status_flip else 0) - (20 if judge_disagreement else 0)
            - missing_trials * 20,
        )
        results.append({
            "case_id": case_id,
            "question": str(rows[0].get("question") or ""),
            "status": "PASS" if stable else "FAIL",
            "score": round(stability_score, 1),
            "stable": stable,
            "status_flip": status_flip,
            "status_change_count": status_change_count,
            "score_mean": round(statistics.mean(scores), 2) if scores else 0.0,
            "score_min": round(min(scores), 2) if scores else 0.0,
            "score_max": round(max(scores), 2) if scores else 0.0,
            "score_stddev": round(score_stddev, 3),
            "score_spread": round(score_spread, 2),
            "output_variants": unique_outputs,
            "judge_verdicts": judge_verdicts,
            "judge_disagreement": judge_disagreement,
            "judge_score_mean": round(statistics.mean(judge_scores), 2) if judge_scores else None,
            "judge_score_stddev": round(statistics.pstdev(judge_scores), 3)
            if len(judge_scores) > 1 else 0.0 if judge_scores else None,
            "missing_trials": missing_trials,
            "detail": (
                f"상태변경={status_change_count}회, 표준편차={score_stddev:.3f}, "
                f"점수범위={score_spread:.1f}, 출력변형={unique_outputs}, "
                f"Judge불일치={judge_disagreement}"
            ),
            "trials": [
                {
                    "trial": row["trial"],
                    "passed": bool((row.get("quality") or {}).get("passed")),
                    "score": float((row.get("quality") or {}).get("score") or 0),
                    "duration_ms": float(
                        (((row.get("analysis") or {}).get("metrics") or {}).get("total_duration_ms")) or 0
                    ),
                    "judge_decision": str((row.get("judge") or {}).get("decision") or ""),
                    "judge_score": (row.get("judge") or {}).get("total_score"),
                }
                for row in rows
            ],
        })
    return results


async def run_repeatability(
    *,
    mode: str,
    domain: str,
    cases_path: Path,
    csv_path: Path,
    output_dir: Path,
    trials: int = 3,
    limit: int | None = 5,
    case_ids: list[str] | None = None,
    concurrency: int = 1,
    judge_provider: str = "deterministic",
    progress_callback=None,
) -> dict[str, Any]:
    if mode not in {"offline", "live"}:
        raise ValueError("mode는 offline 또는 live여야 합니다.")
    if not 2 <= trials <= 5:
        raise ValueError("반복 횟수는 2~5회여야 합니다.")
    if limit is not None and not 1 <= limit <= 20:
        raise ValueError("실행 범위는 1~20건이어야 합니다.")
    if judge_provider not in {"deterministic", "openai", "anthropic", "none"}:
        raise ValueError("Judge는 deterministic, openai, anthropic, none 중 하나여야 합니다.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    trial_root = output_dir / "repeatability_trials" / stamp
    trial_payloads: list[list[dict[str, Any]]] = []
    trial_reports: list[str] = []
    judge_reports: list[str] = []
    for trial in range(1, trials + 1):
        if progress_callback:
            progress_callback(trial - 1, trials, f"반복 {trial}/{trials} E2E 실행")
        trial_dir = trial_root / f"trial_{trial}"
        result = await run_e2e(
            mode,
            cases_path,
            trial_dir,
            csv_path,
            domain,
            limit,
            case_ids,
            concurrency,
        )
        report_path = Path(result["json"])
        trial_rows = _load_results(report_path)
        if judge_provider != "none":
            judge_result = await run_llm_judge(
                judge_provider, report_path, trial_dir, include_all=True
            )
            judge_path = Path(judge_result["json"])
            judge_payload = json.loads(judge_path.read_text(encoding="utf-8"))
            judge_by_case = {
                str(item.get("case_id") or ""): item
                for item in judge_payload.get("results") or [] if isinstance(item, dict)
            }
            for row in trial_rows:
                row["judge"] = judge_by_case.get(str(row.get("case_id") or ""), {})
            judge_reports.append(str(judge_path.relative_to(output_dir)))
        trial_payloads.append(trial_rows)
        trial_reports.append(str(report_path.relative_to(output_dir)))
        if progress_callback:
            progress_callback(trial, trials, f"반복 {trial}/{trials} 및 Judge 완료")
    rows = analyze_trials(trial_payloads)
    passed = sum(row["stable"] for row in rows)
    average_stability = round(
        sum(float(row["score"]) for row in rows) / len(rows), 1
    ) if rows else 0.0
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "domain": domain,
        "mode": mode,
        "trials": trials,
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "pass_rate": round(passed / len(rows) * 100, 1) if rows else 0.0,
        "average_score": average_stability,
        "successful": passed == len(rows) and bool(rows),
        "live_quality_verified": mode == "live",
        "criteria": {
            "status_flip_allowed": False,
            "maximum_score_stddev": 1.0,
            "judge_disagreement_allowed": False,
        },
        "judge_provider": judge_provider,
    }
    payload = {
        "summary": summary,
        "trial_reports": trial_reports,
        "judge_reports": judge_reports,
        "results": rows,
    }
    json_path = output_dir / f"repeatability_{domain}_{mode}_{stamp}.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    evidence = write_execution_evidence(
        f"repeatability_{domain}_{mode}", payload, output_dir
    )
    return {
        "summary": summary,
        "report": str(json_path),
        "trial_reports": trial_reports,
        "judge_reports": judge_reports,
        "evidence": evidence,
        "results": rows,
    }


__all__ = ["analyze_trials", "run_repeatability"]
