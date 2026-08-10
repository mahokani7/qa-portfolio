"""6개 Agent의 역할과 기본 출력 계약을 독립적으로 검증합니다."""

from __future__ import annotations

import unittest

from agents.critic import CriticAgent
from agents.evaluator import EvaluatorAgent
from agents.improver import PolicyImproverAgent
from agents.interpreter import NLInterpreterAgent
from agents.retriever import RetrieverAgent
from agents.summarizer import SummarizerAgent
from e2e_runner import ROOT, load_cases
from utils.fake_llm import (
    DeterministicEvaluatorLLM,
    DeterministicOpenAIClient,
    DeterministicPolicyLLM,
    DeterministicSummaryLLM,
)
from utils.settings import DEFAULT_CSV
from utils.settings import MODEL_POLICY
from llm_wrappers.anthropic_chat import AnthropicChat


class AgentUnitTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(ROOT / "test_cases.txt")

    async def test_interpreter_extracts_expected_search_terms(self):
        case = self.cases[0]
        agent = NLInterpreterAgent(client=DeterministicOpenAIClient(self.cases))
        result = await agent.parse(case["question"], DEFAULT_CSV)
        self.assertEqual(result.task, "both")
        self.assertTrue(set(case["expected_keywords"][:2]).issubset(set(result.filters or [])))
        self.assertEqual(result.max_items, 10)

    async def test_retriever_returns_relevant_voc(self):
        results = await RetrieverAgent().run(DEFAULT_CSV, ["결제", "주문"], 10)
        self.assertTrue(results)
        self.assertTrue(any("결제" in result or "주문" in result for result in results))

    async def test_summarizer_creates_three_candidates(self):
        agent = SummarizerAgent(llm=DeterministicSummaryLLM(self.cases))
        candidates = await agent.make_candidates(
            ["결제 완료 후 주문 생성이 반영되지 않았습니다."], 10, 3,
            self.cases[0]["question"],
        )
        self.assertEqual(set(candidates), {"S0", "S1", "S2"})
        self.assertTrue(all(value.strip() for value in candidates.values()))

    async def test_evaluator_selects_highest_scored_candidate(self):
        result = await EvaluatorAgent(llm=DeterministicEvaluatorLLM()).evaluate(
            "both", {"S0": "요약 0", "S1": "요약 1", "S2": "요약 2"}
        )
        self.assertEqual(result["winner"], "S0")
        self.assertEqual(result["scores"]["S0"], max(result["scores"].values()))

    async def test_critic_returns_structured_risk_decision(self):
        result = await CriticAgent(client=DeterministicOpenAIClient([])).review(
            "검색된 VOC에 근거한 요약입니다.", "summary"
        )
        self.assertIsInstance(result.need_refine, bool)
        self.assertIsInstance(result.edits, list)
        self.assertIsInstance(result.ask_more_samples, bool)

    async def test_improver_returns_actionable_policy(self):
        result = await PolicyImproverAgent(llm=DeterministicPolicyLLM()).improve(
            "결제 완료 후 주문 반영이 지연되는 VOC가 반복됩니다.",
            "결제 관련 개선안을 제안해 주세요.",
        )
        self.assertIn("담당", result.policy)
        self.assertIn("1주 이내", result.policy)
        self.assertIn("목표 지표", result.policy)

    async def test_anthropic_wrapper_uses_central_policy_model(self):
        self.assertEqual(AnthropicChat().model, MODEL_POLICY)


if __name__ == "__main__":
    unittest.main()
