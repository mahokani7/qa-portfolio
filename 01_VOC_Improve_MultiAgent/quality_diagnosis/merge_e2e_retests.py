"""전체 E2E 보고서에 선택 재시험 결과를 덮어써 최종 감사 보고서를 생성합니다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from e2e_runner import _summary, save_results


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge(base: Path, retests: list[Path], output_dir: Path) -> dict[str, Any]:
    base_report = _read(base)
    rows_by_id = {
        str(row["case_id"]): row
        for row in base_report.get("results") or []
    }
    if not rows_by_id:
        raise ValueError("기준 보고서에 results가 없습니다.")

    replaced: list[str] = []
    for path in retests:
        for row in _read(path).get("results") or []:
            case_id = str(row["case_id"])
            if case_id not in rows_by_id:
                raise ValueError(f"기준 보고서에 없는 재시험 case_id: {case_id}")
            rows_by_id[case_id] = row
            replaced.append(case_id)

    rows = list(rows_by_id.values())
    domain = str((base_report.get("summary") or {}).get("domain") or "ecommerce")
    json_path, csv_path, score_path, decision_path = save_results(
        "live_retest_merged", rows, output_dir, domain
    )
    return {
        "summary": _summary("live", rows, domain),
        "retested_case_ids": sorted(set(replaced)),
        "json": str(json_path),
        "csv": str(csv_path),
        "quality_score_report": str(score_path),
        "deployment_decision": str(decision_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--retest", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "reports",
    )
    args = parser.parse_args()
    print(json.dumps(merge(args.base, args.retest, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
