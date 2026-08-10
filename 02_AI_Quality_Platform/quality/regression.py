"""
regression.py  [고도화 제안 3: 회귀 테스트(Regression) — Promptfoo/DeepEval 벤치마킹]
------------------------------------------------------------------------------
두 번의 파이프라인 실행 결과(baseline vs current)를 케이스 단위로 비교해,
판정이 뒤집혔거나(PASS->FAIL) 지표 점수가 하락한 지점을 자동 검출한다.
reports/history/ 에 이미 쌓이는 실행 이력을 그대로 활용한다.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import HISTORY_DIR

DECISION_RANK = {"FAIL": 0, "REVIEW": 1, "PASS": 2}
METRICS = ["accuracy", "groundedness", "helpfulness", "safety"]
AGENTS = [("rule_based", "규칙 기반"), ("api_based", "API 기반")]


def _index_by_case(run: List[Dict]) -> Dict[str, Dict]:
    return {c["case_id"]: c for c in run}


def compare_runs(baseline: List[Dict], current: List[Dict]) -> Dict:
    """
    두 실행 결과를 비교해 회귀/개선 항목을 반환한다.
    :return: {"regressions": [...], "improvements": [...], "has_regression": bool}
    """
    base_idx = _index_by_case(baseline)
    cur_idx = _index_by_case(current)

    regressions: List[Dict] = []
    improvements: List[Dict] = []

    for case_id, base_case in base_idx.items():
        cur_case = cur_idx.get(case_id)
        if not cur_case:
            regressions.append({"case_id": case_id, "agent": "-", "kind": "케이스 누락",
                                "detail": "이전엔 있었으나 현재 실행에 없음"})
            continue

        for agent_key, agent_label in AGENTS:
            base_eval = base_case.get(agent_key, {}).get("evaluation_result", {})
            cur_eval = cur_case.get(agent_key, {}).get("evaluation_result", {})
            if not base_eval or not cur_eval:
                continue

            # 판정 변화
            b_dec = base_eval.get("overall_decision", "FAIL")
            c_dec = cur_eval.get("overall_decision", "FAIL")
            if DECISION_RANK.get(c_dec, 0) < DECISION_RANK.get(b_dec, 0):
                regressions.append({"case_id": case_id, "agent": agent_label,
                                    "kind": "판정 하락", "detail": f"{b_dec} → {c_dec}"})
            elif DECISION_RANK.get(c_dec, 0) > DECISION_RANK.get(b_dec, 0):
                improvements.append({"case_id": case_id, "agent": agent_label,
                                    "kind": "판정 상승", "detail": f"{b_dec} → {c_dec}"})

            # 지표 점수 변화
            for m in METRICS:
                b_score = base_eval.get(m, {}).get("score", 0)
                c_score = cur_eval.get(m, {}).get("score", 0)
                if c_score < b_score:
                    regressions.append({"case_id": case_id, "agent": agent_label,
                                        "kind": f"{m} 하락", "detail": f"{b_score} → {c_score}"})
                elif c_score > b_score:
                    improvements.append({"case_id": case_id, "agent": agent_label,
                                        "kind": f"{m} 상승", "detail": f"{b_score} → {c_score}"})

    return {
        "regressions": regressions,
        "improvements": improvements,
        "has_regression": len(regressions) > 0,
    }


def list_history_runs() -> List[Path]:
    """reports/history/ 의 실행 이력 폴더를 최신순으로 반환한다."""
    if not HISTORY_DIR.exists():
        return []
    runs = [d for d in HISTORY_DIR.iterdir() if (d / "evaluation_result.json").exists()]
    return sorted(runs, reverse=True)


def load_run(run_dir: Path) -> List[Dict]:
    return json.loads((run_dir / "evaluation_result.json").read_text(encoding="utf-8"))


def compare_latest_two() -> Tuple[Dict, str, str]:
    """
    가장 최근 두 실행 이력을 자동으로 비교한다. (baseline=직전, current=최신)
    :return: (비교결과, baseline 타임스탬프, current 타임스탬프)
    """
    runs = list_history_runs()
    if len(runs) < 2:
        raise ValueError("비교하려면 최소 2개의 실행 이력이 필요합니다.")
    current_dir, baseline_dir = runs[0], runs[1]
    result = compare_runs(load_run(baseline_dir), load_run(current_dir))
    return result, baseline_dir.name, current_dir.name


if __name__ == "__main__":
    try:
        result, base_ts, cur_ts = compare_latest_two()
    except ValueError as e:
        print(f"[안내] {e}")
        sys.exit(0)

    print(f"=== 회귀 테스트: {base_ts}(baseline) vs {cur_ts}(current) ===")
    print(f"\n[회귀(품질 하락) {len(result['regressions'])}건]")
    for r in result["regressions"]:
        print(f"  [X]  {r['case_id']:<8} {r['agent']:<8} {r['kind']:<14} {r['detail']}")
    print(f"\n[개선 {len(result['improvements'])}건]")
    for r in result["improvements"]:
        print(f"  [OK] {r['case_id']:<8} {r['agent']:<8} {r['kind']:<14} {r['detail']}")
    print("\n판정:", "회귀 발견 → 배포 보류 권고" if result["has_regression"] else "회귀 없음 → 배포 안전")
