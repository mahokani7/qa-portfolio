"""
rag_ablation.py  [고도화 제안: RAG on/off 3-way 비교 — RAGAS/ablation 벤치마킹]
------------------------------------------------------------------------------
동일한 질문에 대해 세 가지 방식의 정확성(정답 키워드 포함률)을 나란히 비교한다.
  1) 규칙 기반 챗봇        : LLM/RAG 없이 지식 파일 원문을 키워드로 검색
  2) API 기반 (RAG OFF)   : LLM 자체 지식만으로 답변 (지식 베이스 미참조)  ← 대조군
  3) API 기반 (RAG ON)    : LLM + ChromaDB 검색(RAG)으로 답변            ← 실험군

'RAG ON' 정확성에서 'RAG OFF' 정확성을 뺀 값(lift)이 곧 "RAG가 정확성을 몇 %p 올렸는가"의
정량 근거가 된다. (프로젝트 지식은 320시간·결석 1일 등 도메인 특화 정보라, RAG가 없으면
LLM이 정확히 알 수 없으므로 RAG의 기여가 수치로 드러난다.)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import TEST_CASE_FILE


def _load_accuracy_cases() -> List[Dict]:
    """정답 키워드(expected_keyword)가 있는 '정확성 측정 가능' 케이스만 골라 반환한다.
    (안전성/문서외 거절 케이스는 정답 키워드가 없어 정확성 측정 대상이 아니므로 제외)"""
    if not TEST_CASE_FILE.exists():
        raise FileNotFoundError(f"테스트 케이스 파일을 찾을 수 없습니다: {TEST_CASE_FILE}")
    cases = json.loads(TEST_CASE_FILE.read_text(encoding="utf-8"))
    return [c for c in cases if (c.get("expected_keyword") or "").strip()]


def run_rag_ablation(cases: Optional[List[Dict]] = None) -> Dict:
    """
    규칙기반 / RAG OFF / RAG ON 세 방식의 정답 키워드 포함률(정확성)을 비교한다.
    :return: {
        "rows": [케이스별 결과...],
        "total": int,
        "acc_rule": float, "acc_rag_off": float, "acc_rag_on": float,   # 각 방식 정확성(%)
        "lift": float,           # RAG ON - RAG OFF (RAG의 정확성 기여, %p)
        "lift_vs_rule": float,   # RAG ON - 규칙기반 (%p)
    }
    """
    from app.rule_based_agent import RuleBasedAgent
    from app.service_agent import ServiceAgent

    cases = cases if cases is not None else _load_accuracy_cases()
    rule_agent = RuleBasedAgent()
    api_agent = ServiceAgent()

    rows = []
    rule_hits = rag_off_hits = rag_on_hits = 0

    for c in cases:
        q = c.get("user_question", "")
        kw = (c.get("expected_keyword") or "").strip()

        rule_ans = rule_agent.generate_response(q)
        rag_off_ans = api_agent.generate_response(q, use_rag=False)
        rag_on_ans = api_agent.generate_response(q, use_rag=True)

        rule_hit = kw in rule_ans
        rag_off_hit = kw in rag_off_ans
        rag_on_hit = kw in rag_on_ans

        rule_hits += rule_hit
        rag_off_hits += rag_off_hit
        rag_on_hits += rag_on_hit

        rows.append({
            "case_id": c.get("case_id"),
            "question": q,
            "expected_keyword": kw,
            "rule_hit": rule_hit,
            "rag_off_hit": rag_off_hit,
            "rag_on_hit": rag_on_hit,
            "rule_answer": rule_ans,
            "rag_off_answer": rag_off_ans,
            "rag_on_answer": rag_on_ans,
        })

    total = len(cases)
    pct = lambda n: round(n / total * 100, 1) if total else 0.0
    acc_rule = pct(rule_hits)
    acc_rag_off = pct(rag_off_hits)
    acc_rag_on = pct(rag_on_hits)

    return {
        "rows": rows,
        "total": total,
        "acc_rule": acc_rule,
        "acc_rag_off": acc_rag_off,
        "acc_rag_on": acc_rag_on,
        "lift": round(acc_rag_on - acc_rag_off, 1),
        "lift_vs_rule": round(acc_rag_on - acc_rule, 1),
    }


if __name__ == "__main__":
    report = run_rag_ablation()
    print("=== RAG on/off 3-way 정확성 비교 ===")
    print(f"  규칙기반      : {report['acc_rule']}%")
    print(f"  API RAG OFF   : {report['acc_rag_off']}%")
    print(f"  API RAG ON    : {report['acc_rag_on']}%")
    print(f"  RAG lift (ON-OFF): +{report['lift']}%p")
    for r in report["rows"]:
        print(f"  [{r['case_id']}] kw='{r['expected_keyword']}' "
              f"rule={'O' if r['rule_hit'] else 'X'} off={'O' if r['rag_off_hit'] else 'X'} on={'O' if r['rag_on_hit'] else 'X'}")
