"""외부 API 없이 멀티에이전트 연결을 검증하는 결정적 LLM 테스트 대역."""

from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any


class DeterministicOpenAIClient:
    """Interpreter와 Critic이 사용하는 Chat Completions 모양을 구현합니다."""

    def __init__(self, cases: list[dict[str, Any]]):
        self._by_question = {str(case["question"]): case for case in cases}
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **kwargs):
        messages = kwargs.get("messages") or []
        prompt = "\n".join(str(message.get("content") or "") for message in messages)
        if "VOC 분석을 위한 질의 해석기" in prompt:
            question = next((q for q in self._by_question if q in prompt), "")
            case = self._by_question.get(question, {})
            filters = list(case.get("expected_keywords") or [])
            if case.get("required_output") == ["추가 정보 요청"] and "앱" not in question:
                filters = []
            payload = {
                "task": "both",
                "filters": filters[:20],
                "max_items": 10,
                "csv_path": "default_csv",
            }
        else:
            payload = {"need_refine": False, "edits": [], "ask_more_samples": False}
        content = json.dumps(payload, ensure_ascii=False)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class DeterministicSummaryLLM:
    def __init__(self, cases: list[dict[str, Any]] | None = None):
        self._by_question = {str(case["question"]): case for case in (cases or [])}

    async def __call__(self, prompt: str) -> str:
        if "draft:" in prompt and "edits:" in prompt:
            match = re.search(r"draft:\s*(.*?)\s*edits:", prompt, re.S)
            return (match.group(1).strip() if match else "요약 개선 결과")
        matches = re.findall(r"(?:^|\n)<voc_data>\s*(.*?)\s*</voc_data>", prompt, re.S)
        source = (matches[-1].strip() if matches else "검색된 VOC")
        question = next((q for q in self._by_question if q in prompt), "")
        case = self._by_question.get(question, {})
        expectation = " ".join(
            [str(case.get("expected_intent") or "")] + list(case.get("expected_keywords") or [])
        ).strip()
        base = (
            f"{source} {expectation} 원인 추정 가능성을 확인해야 합니다. "
            "고객 안내와 추가 정보 요청이 필요하며 개선안과 우선순위를 마련해야 합니다."
        )
        return f"S0: {base}\nS1: {base}\nS2: {base}"


class DeterministicEvaluatorLLM:
    async def __call__(self, _prompt: str) -> str:
        return json.dumps(
            {"winner": "S0", "scores": {"S0": 9.0, "S1": 8.0, "S2": 7.0}},
            ensure_ascii=False,
        )


class DeterministicPolicyLLM:
    async def __call__(self, _prompt: str, max_tokens: int = 1024) -> str:
        del max_tokens
        return (
            "최우선 개선안: 담당 운영팀은 즉시 원인을 점검하고 고객 안내를 시행합니다. "
            "1주 이내 동기화와 오류 모니터링을 개선하며 처리시간 20% 단축을 목표 지표로 관리합니다."
        )
