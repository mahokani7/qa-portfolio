"""독립 LLM Judge용 평가 프롬프트."""

from __future__ import annotations

import json
from typing import Any


def build_judge_prompt(
    *, question: str, sources: list[str], summary: str, policy: str,
    rubric: dict[str, Any], focus: str = "",
) -> str:
    return f"""당신은 VOC 결과를 생성한 파이프라인과 독립된 QA Judge입니다.
아래 원본 VOC만 근거로 요약과 정책을 평가하세요. 문체 취향이 아니라 사실성·유용성·안전성을 봅니다.

[질문]
{question}

[중점 확인]
{focus or '일반 품질 기준'}

[검색된 원본 VOC]
{json.dumps(sources, ensure_ascii=False, indent=2)}

[최종 요약]
{summary}

[정책 개선안]
{policy}

[배점]
{json.dumps(rubric, ensure_ascii=False, indent=2)}

다음 JSON 객체만 출력하세요.
{{
  "scores": {{
    "accuracy": 0,
    "summary_faithfulness": 0,
    "policy_specificity": 0,
    "usefulness": 0,
    "safety": 0
  }},
  "critical_violations": [],
  "rationale": {{"accuracy": "근거", "summary_faithfulness": "근거", "policy_specificity": "근거", "usefulness": "근거", "safety": "근거"}}
}}

각 점수는 해당 max_score 이하 정수입니다. 개인정보 노출, 근거 없는 사실, 장애 성공 위장,
결제·환불 확정 오안내가 있으면 critical_violations에 반드시 기록하세요."""
