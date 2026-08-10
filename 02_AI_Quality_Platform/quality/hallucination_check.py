"""
hallucination_check.py  [고도화 #3: 환각(Hallucination) 자동 탐지 보강 — RAGAS Faithfulness 관점]
------------------------------------------------------------------------------
LLM Judge의 '근거성' 점수가 주관적이라는 한계를 보완하기 위해, 답변 내용이 실제 지식 베이스
(업로드된 기준정보 원문)에 얼마나 뒷받침되는지를 문자열 단어 겹침으로 교차검증한다.
지원율(grounding score)이 낮으면 근거 없는 내용(환각) 가능성이 높다. 외부 API 불필요.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.knowledge_base import list_uploaded_knowledge_files, read_document_text

# 근거 판정에서 제외할 흔한 기능어(불용어) — 겹침 점수 왜곡 방지
STOPWORDS = {
    "그리고", "그러나", "하지만", "또는", "합니다", "입니다", "있습니다", "없습니다",
    "대한", "위한", "통해", "따라", "관련", "경우", "해당", "이것", "저것", "여기",
}
_WORD_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")


def _tokens(text: str) -> List[str]:
    return [w for w in _WORD_RE.findall(text or "") if w not in STOPWORDS]


def build_corpus_words() -> Set[str]:
    """업로드된 지식 파일 전체를 읽어 단어 집합(근거 코퍼스)을 만든다."""
    corpus: Set[str] = set()
    for f in list_uploaded_knowledge_files():
        try:
            corpus.update(_tokens(read_document_text(f)))
        except Exception:
            continue
    return corpus


def grounding_score(answer: str, corpus_words: Set[str]) -> Dict:
    """
    답변의 내용어 중 지식 코퍼스에 존재하는 비율(지원율)을 계산한다.
    :return: {score(0~1), supported, total, unsupported_words}
    """
    words = _tokens(answer)
    if not words:
        return {"score": 1.0, "supported": 0, "total": 0, "unsupported_words": []}
    supported = [w for w in words if w in corpus_words]
    unsupported = sorted(set(w for w in words if w not in corpus_words))
    return {
        "score": round(len(supported) / len(words), 3),
        "supported": len(supported),
        "total": len(words),
        "unsupported_words": unsupported[:15],
    }


def check_answers(items: List[Dict], threshold: float = 0.5) -> Dict:
    """
    여러 답변의 근거 지원율을 계산하고, 임계값 미만은 '환각 의심'으로 표시한다.
    :param items: [{"case_id":..., "agent":..., "answer":...}, ...]
    """
    corpus = build_corpus_words()
    rows = []
    for it in items:
        g = grounding_score(it.get("answer", ""), corpus)
        rows.append({
            "case_id": it.get("case_id", "-"),
            "agent": it.get("agent", "-"),
            "grounding": g["score"],
            "supported": f"{g['supported']}/{g['total']}",
            "suspect": g["score"] < threshold and g["total"] > 0,
        })
    suspects = [r for r in rows if r["suspect"]]
    return {
        "rows": rows,
        "corpus_size": len(corpus),
        "suspect_count": len(suspects),
        "threshold": threshold,
    }


if __name__ == "__main__":
    corpus = build_corpus_words()
    print(f"=== 환각 교차검증 (근거 코퍼스 단어 {len(corpus)}개) ===")
    samples = [
        {"case_id": "TC-001", "agent": "api", "answer": "이 교육과정은 총 320시간입니다."},
        {"case_id": "TC-X", "agent": "api", "answer": "이 과정은 우주 비행사 자격증과 무료 항공권을 제공합니다."},
    ]
    r = check_answers(samples)
    for row in r["rows"]:
        flag = " <- 환각 의심" if row["suspect"] else ""
        print(f"  {row['case_id']}/{row['agent']}: 지원율 {row['grounding']:.2f} ({row['supported']}){flag}")
