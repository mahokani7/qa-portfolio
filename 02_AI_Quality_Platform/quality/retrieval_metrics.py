"""
retrieval_metrics.py  [고도화 제안 1: 검색 품질 분리 측정 — RAGAS 벤치마킹]
------------------------------------------------------------------------------
RAG를 '검색 단계'와 '생성 단계'로 분리해 채점한다. 최종 답변만 채점하던 한계를 보완하여,
정확성이 낮을 때 그 원인이 검색(관련 문서를 못 찾음)인지 생성(찾았는데 잘못 씀)인지 진단한다.

- Context Recall    : 정답에 필요한 관련 문서 중 실제 검색된 비율 (검색이 빠뜨렸나?)
- Context Precision : 검색 결과 상위 순위에 관련 문서가 잘 배치됐는지 (관련 없는 문서로 오염됐나?)

라벨링된 평가셋(retrieval_eval_set.json)을 기준으로 계산한다.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EVAL_SET_FILE = Path(__file__).resolve().parent / "retrieval_eval_set.json"


def context_recall(retrieved_relevance: List[int], total_relevant: int) -> float:
    """검색된 청크의 관련여부(1/0) 리스트와 전체 관련 문서 수로 재현율을 계산한다."""
    if total_relevant <= 0:
        return 0.0
    return sum(retrieved_relevance) / total_relevant


def context_precision(retrieved_relevance: List[int]) -> float:
    """
    RAGAS 방식 Context Precision@k.
    각 순위 k에서 관련 문서일 때만 precision@k를 계산해 평균낸다.(관련 문서가 상위일수록 높음)
    """
    if not retrieved_relevance or sum(retrieved_relevance) == 0:
        return 0.0
    hit = 0
    weighted = 0.0
    for k, rel in enumerate(retrieved_relevance, start=1):
        if rel == 1:
            hit += 1
            weighted += hit / k
    return weighted / sum(retrieved_relevance)


def load_eval_set(path: Path = EVAL_SET_FILE) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"검색 평가셋을 찾을 수 없습니다: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_retrieval(eval_set: List[Dict] = None) -> Dict:
    """
    평가셋 전체에 대해 케이스별 Recall/Precision과 평균을 계산해 반환한다.
    :return: {"cases": [...], "avg_recall": float, "avg_precision": float}
    """
    eval_set = eval_set if eval_set is not None else load_eval_set()
    cases = []
    for item in eval_set:
        rel = item["retrieved_relevance"]
        rec = context_recall(rel, item["total_relevant"])
        prec = context_precision(rel)
        cases.append({
            "question": item["question"],
            "recall": round(rec, 3),
            "precision": round(prec, 3),
            "retrieved_relevance": rel,
            "total_relevant": item["total_relevant"],
        })
    n = len(cases) or 1
    return {
        "cases": cases,
        "avg_recall": round(sum(c["recall"] for c in cases) / n, 3),
        "avg_precision": round(sum(c["precision"] for c in cases) / n, 3),
    }


if __name__ == "__main__":
    result = evaluate_retrieval()
    print("=== 검색 품질 분리 측정 (Context Precision/Recall) ===")
    for c in result["cases"]:
        print(f"  {c['question'][:34]:<34} Recall={c['recall']:.2f}  Precision={c['precision']:.2f}")
    print(f"  평균: Recall={result['avg_recall']:.2f}  Precision={result['avg_precision']:.2f}")
