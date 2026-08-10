"""
coverage_gap.py  [고도화 #1: 테스트 커버리지 갭 자동 탐지 — DeepEval/RAGAS 커버리지 관점]
------------------------------------------------------------------------------
평가 기준(evaluation_criteria.json)에 정의된 카테고리 중, 테스트케이스(test_cases.json)가
하나도 없는 카테고리를 자동으로 찾아낸다. 특히 안전성 관련 카테고리 누락은 최우선 리스크다.
외부 API 불필요 — 데이터 비교만 수행.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import TEST_CASE_FILE, EVALUATION_CRITERIA_FILE

# 안전/보안 성격의 카테고리(누락 시 위험도 높음)를 표시하기 위한 키워드
RISK_KEYWORDS = ["안전", "위험", "보안"]


def analyze_coverage(test_case_file: Path = None, criteria_file: Path = None) -> Dict:
    """
    카테고리별 테스트케이스 커버 여부를 분석한다.
    :return: {rows, total, covered, gap, coverage_pct}
    """
    test_case_file = test_case_file or TEST_CASE_FILE
    criteria_file = criteria_file or EVALUATION_CRITERIA_FILE

    criteria = json.loads(Path(criteria_file).read_text(encoding="utf-8"))
    cases = json.loads(Path(test_case_file).read_text(encoding="utf-8"))

    all_categories = list(criteria.keys())
    counts: Dict[str, int] = {}
    for c in cases:
        cat = c.get("category")
        counts[cat] = counts.get(cat, 0) + 1

    rows: List[Dict] = []
    for cat in all_categories:
        n = counts.get(cat, 0)
        is_risk = any(k in cat for k in RISK_KEYWORDS)
        rows.append({
            "category": cat,
            "test_count": n,
            "covered": n > 0,
            "risk": is_risk,
            "status": "커버됨" if n > 0 else ("⚠️ 미커버(위험)" if is_risk else "미커버"),
        })

    covered = sum(1 for r in rows if r["covered"])
    total = len(all_categories)
    return {
        "rows": rows,
        "total": total,
        "covered": covered,
        "gap": total - covered,
        "coverage_pct": round(covered / total * 100, 1) if total else 0.0,
        "uncovered_risk": [r["category"] for r in rows if not r["covered"] and r["risk"]],
    }


if __name__ == "__main__":
    r = analyze_coverage()
    print(f"=== 테스트 커버리지 갭 분석 ===")
    print(f"전체 {r['total']}개 카테고리 중 {r['covered']}개 커버 (커버리지 {r['coverage_pct']}%), 갭 {r['gap']}개")
    for row in r["rows"]:
        mark = "O" if row["covered"] else "X"
        print(f"  [{mark}] {row['category']:<18} 테스트 {row['test_count']}건  {row['status']}")
    if r["uncovered_risk"]:
        print(f"\n최우선 보강 필요(안전/위험 미커버): {r['uncovered_risk']}")
