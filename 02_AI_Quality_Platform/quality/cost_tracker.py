"""
cost_tracker.py  [고도화 #8: 토큰/비용 추적 리포트 — Langfuse / Datadog LLM Observability 벤치마킹]
------------------------------------------------------------------------------
질문·답변의 토큰 수를 추정하고 모델 단가를 곱해 케이스별/전체 예상 비용을 산출한다.
'품질 대비 비용'을 리포트에 함께 제공해 운영 의사결정을 돕는다.
tiktoken 미설치 환경에서도 동작하도록 경량 추정기를 사용한다(추정치임을 명시).
"""

import math
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# gpt-4o-mini 단가 (USD per 1M tokens) — 프로젝트에서 실제 사용하는 모델 기준
PRICE_PER_1M = {"input": 0.15, "output": 0.60}
USD_TO_KRW = 1400  # 환율(대략) — 원화 환산용


def estimate_tokens(text: str) -> int:
    """
    tiktoken 없이 토큰 수를 추정한다.
    - 영문/숫자/기호는 약 4자당 1토큰, 한글은 약 1.5자당 1토큰(평균)에 가깝게 가중.
    """
    if not text:
        return 0
    korean = sum(1 for ch in text if "가" <= ch <= "힣")
    others = len(text) - korean
    return max(1, math.ceil(korean / 1.5 + others / 4))


def estimate_case_cost(question: str, answer: str) -> Dict:
    """한 케이스(질문=입력, 답변=출력)의 토큰/비용을 추정한다."""
    in_tok = estimate_tokens(question)
    out_tok = estimate_tokens(answer)
    cost_usd = in_tok / 1_000_000 * PRICE_PER_1M["input"] + out_tok / 1_000_000 * PRICE_PER_1M["output"]
    return {
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
        "cost_usd": cost_usd,
        "cost_krw": cost_usd * USD_TO_KRW,
    }


def track_cost(items: List[Dict]) -> Dict:
    """
    여러 케이스의 비용을 추적한다.
    :param items: [{"case_id":..., "question":..., "answer":...}, ...]
    :return: {rows, total_tokens, total_cost_usd, total_cost_krw, avg_tokens}
    """
    rows = []
    total_tokens = 0
    total_usd = 0.0
    for it in items:
        c = estimate_case_cost(it.get("question", ""), it.get("answer", ""))
        rows.append({"case_id": it.get("case_id", "-"), **c})
        total_tokens += c["total_tokens"]
        total_usd += c["cost_usd"]
    n = len(rows) or 1
    return {
        "rows": rows,
        "total_tokens": total_tokens,
        "total_cost_usd": total_usd,
        "total_cost_krw": total_usd * USD_TO_KRW,
        "avg_tokens": round(total_tokens / n, 1),
        "model": "gpt-4o-mini",
    }


if __name__ == "__main__":
    samples = [
        {"case_id": "TC-001", "question": "이 교육과정은 총 몇 시간인가요?", "answer": "총 320시간입니다."},
        {"case_id": "TC-002", "question": "지각을 세 번 하면 어떻게 되나요?", "answer": "지각 3회 누적 시 결석 1일로 처리됩니다."},
    ]
    r = track_cost(samples)
    print(f"=== 토큰/비용 추적 (추정, 모델 {r['model']}) ===")
    for row in r["rows"]:
        print(f"  {row['case_id']}: 입력 {row['input_tokens']} + 출력 {row['output_tokens']} = "
              f"{row['total_tokens']}토큰,  약 {row['cost_krw']:.3f}원")
    print(f"  합계: {r['total_tokens']}토큰,  약 ${r['total_cost_usd']:.5f} ({r['total_cost_krw']:.2f}원)")
    print("  ※ tiktoken 미사용 추정치이며 시스템 프롬프트/RAG 컨텍스트는 제외됨.")
