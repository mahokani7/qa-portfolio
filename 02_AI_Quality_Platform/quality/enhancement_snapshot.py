"""
enhancement_snapshot.py
------------------------------------------------------------------------------
파이프라인을 실행한 '그 시점'의 고도화 지표를 스냅샷으로 저장/로드한다.
- OpenAI 호출이 전혀 없는(=비용 0원) 지표만 담는다: 커버리지 갭, 레드티밍(규칙기반).
  (검색품질/RAG on/off는 OpenAI 임베딩·완성 호출이 있어 비용이 발생하므로 스냅샷에서 제외 → 실시간으로만 표시)
- 이렇게 저장해두면 히스토리에서 과거 실행을 선택했을 때 '그 실행 시점'의 지표를 그대로 재현할 수 있다.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SNAPSHOT_FILENAME = "enhancement_snapshot.json"


def build_free_snapshot() -> dict:
    """비용 0원 고도화 지표(커버리지 갭 + 레드티밍)를 계산해 스냅샷 딕셔너리로 반환한다."""
    from quality.coverage_gap import analyze_coverage
    from quality.redteam import run_redteam

    snapshot = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coverage": None,
        "redteam": None,
    }
    try:
        snapshot["coverage"] = analyze_coverage()
    except Exception as e:
        snapshot["coverage_error"] = str(e)
    try:
        snapshot["redteam"] = run_redteam()
    except Exception as e:
        snapshot["redteam_error"] = str(e)
    return snapshot


def save_snapshot(snapshot: dict, *dirs: Path) -> None:
    """스냅샷을 여러 폴더(예: reports/, reports/history/<ts>/)에 동일하게 저장한다."""
    for d in dirs:
        d = Path(d)
        d.mkdir(parents=True, exist_ok=True)
        (d / SNAPSHOT_FILENAME).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_snapshot(directory: Path) -> Optional[dict]:
    """지정한 폴더에서 스냅샷을 로드한다. 없으면 None."""
    p = Path(directory) / SNAPSHOT_FILENAME
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


if __name__ == "__main__":
    from config import REPORTS_DIR

    snap = build_free_snapshot()
    save_snapshot(snap, REPORTS_DIR)
    cov = snap.get("coverage") or {}
    rt = snap.get("redteam") or {}
    print("=== 무료 고도화 지표 스냅샷 ===")
    print(f"  생성 시각: {snap['generated_at']}")
    print(f"  커버리지: {cov.get('coverage_pct')}%  (안전/위험 미커버: {cov.get('uncovered_risk')})")
    print(f"  레드티밍 방어율: {rt.get('defense_rate')}%  ({rt.get('attack_defended')}/{rt.get('attack_total')})")
