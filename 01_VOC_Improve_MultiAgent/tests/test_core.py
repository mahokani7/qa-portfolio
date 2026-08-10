from __future__ import annotations

import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import voc_pb2
from agents.critic import CriticAgent
from agents.evaluator import EvaluatorAgent
from agents.retriever import RetrieverAgent
from agents.summarizer import SummarizerAgent
from grpc_server import VOCGRPCRuntime
from utils.errors import error_result, success_result
from utils.settings import DEFAULT_CSV
from utils.validation import (
    ValidationError,
    enforce_summary_grounding,
    is_multi_issue_question,
    needs_clarification,
    select_grounded_winner,
    select_valid_winner,
    validate_bind_address,
    validate_candidates,
    validate_csv_path,
    validate_max_items,
    validate_task,
)


class _FakeLLM:
    def __init__(self, response: str):
        self.response = response

    async def __call__(self, _prompt: str) -> str:
        return self.response


class _FakeCompletions:
    async def create(self, **_kwargs):
        content = """```json
{"need_refine": true, "edits": ["수치를 추가해라"], "ask_more_samples": false}
```"""
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class CoreValidationTests(unittest.TestCase):
    def test_task_and_max_items_validation(self):
        self.assertEqual(validate_task("SUMMARY"), "summary")
        self.assertEqual(validate_max_items("30"), 30)
        with self.assertRaises(ValidationError):
            validate_task("delete")
        with self.assertRaises(ValidationError):
            validate_max_items(500)

    def test_csv_is_limited_to_allowed_roots(self):
        self.assertEqual(validate_csv_path(DEFAULT_CSV), os.path.abspath(DEFAULT_CSV))
        with self.assertRaises(ValidationError):
            validate_csv_path(r"C:\Windows\secret.csv", must_exist=False)

    def test_remote_bind_is_blocked_by_default(self):
        with patch.dict(os.environ, {"A2A_ALLOW_REMOTE_BIND": ""}, clear=False):
            self.assertEqual(validate_bind_address("127.0.0.1:6001"), "127.0.0.1:6001")
            with self.assertRaises(ValidationError):
                validate_bind_address("0.0.0.0:6001")

    def test_candidate_and_winner_fallback(self):
        candidates = validate_candidates({"S0": "첫 요약", "S1": "둘째 요약", "X": "제외"})
        self.assertEqual(select_valid_winner(candidates, "1", {"S0": 7, "S1": 9}), "S1")

    def test_grounding_guard_overrides_clearly_unrelated_winner(self):
        candidates = {
            "S0": "결제는 완료됐지만 주문 내역에 주문이 표시되지 않는 문제가 발생했다.",
            "S1": "주문 취소 후 상태 반영이 지연됐다.",
            "S2": "결제 후 주문 확인 이메일과 영수증이 발송되지 않았다.",
        }
        winner, scores, overridden = select_grounded_winner(
            candidates,
            "S2",
            "결제는 완료되었는데 주문 내역에 보이지 않습니다.",
            ["결제 완료 후 주문 내역에 주문이 표시되지 않아 확인이 어렵습니다."],
        )
        self.assertEqual(winner, "S0")
        self.assertTrue(overridden)
        self.assertGreater(scores["S0"], scores["S2"])

    def test_grounding_guard_keeps_close_llm_choice(self):
        candidates = {
            "S0": "결제 완료 후 주문 내역 반영이 지연됐다.",
            "S1": "결제 완료 후 주문 내역 반영이 늦게 표시됐다.",
        }
        winner, _scores, overridden = select_grounded_winner(
            candidates,
            "S1",
            "결제 완료 후 주문 내역 반영이 늦습니다.",
            ["결제된 주문의 주문 내역 반영 지연"],
        )
        self.assertEqual(winner, "S1")
        self.assertFalse(overridden)

    def test_exact_question_summary_drops_unrelated_case(self):
        grounded, replaced, precision = enforce_summary_grounding(
            "결제 완료 주문이 보이지 않으며 별도로 영수증 이메일도 발송되지 않았다.",
            "결제는 완료되었는데 주문 내역에 보이지 않습니다.",
            ["결제는 정상적으로 완료됐는데 주문 내역에 해당 주문이 표시되지 않아 불안합니다."],
        )
        self.assertTrue(replaced)
        self.assertLess(precision, 0.4)
        self.assertNotIn("이메일", grounded)

    def test_vague_question_requires_clarification(self):
        self.assertTrue(needs_clarification("그냥 다 안 돼요."))
        self.assertTrue(needs_clarification("이거 왜 이래요?"))
        self.assertTrue(needs_clarification("앱이 이상해요."))
        self.assertFalse(needs_clarification("결제 후 주문 내역이 안 보여요."))
        self.assertFalse(needs_clarification("제 개인정보 삭제해주세요."))

    def test_multi_issue_question_is_detected(self):
        self.assertTrue(is_multi_issue_question("배송은 지연되는데 환불 요청도 처리가 안 됩니다."))
        self.assertTrue(is_multi_issue_question("로그인도 안 되고 앱도 멈추고 상담 연결도 안 됩니다."))

    def test_standard_result_shape(self):
        self.assertEqual(success_result(value=1)["error_code"], None)
        failed = error_result("TEST_ERROR", "실패")
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["error_code"], "TEST_ERROR")

    def test_proto_carries_original_question(self):
        request = voc_pb2.RunPipelineReq(question="배송 지연 중심으로 분석")
        self.assertEqual(request.question, "배송 지연 중심으로 분석")


class ParserTests(unittest.IsolatedAsyncioTestCase):
    def test_multiline_summary_candidates_are_preserved(self):
        agent = SummarizerAgent.__new__(SummarizerAgent)
        parsed = agent._parse_candidates(
            "S0: 첫 줄\n- 둘째 줄\n- 셋째 줄\nS1: 다른 요약\n상세 내용"
        )
        self.assertEqual(parsed["S0"], "첫 줄\n- 둘째 줄\n- 셋째 줄")
        self.assertEqual(parsed["S1"], "다른 요약\n상세 내용")

    async def test_evaluator_rejects_unknown_winner(self):
        agent = EvaluatorAgent.__new__(EvaluatorAgent)
        agent.llm = _FakeLLM(
            json.dumps({"winner": "1", "scores": {"S0": 6, "S1": 9}})
        )
        result = await agent.evaluate("summary", {"S0": "요약 0", "S1": "요약 1"})
        self.assertEqual(result["winner"], "S1")

    async def test_critic_accepts_json_code_block(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=_FakeCompletions())
        )
        with patch("agents.critic.openai_client", fake_client):
            result = await CriticAgent(model="test-model").review("충분한 요약문", "summary")
        self.assertTrue(result.need_refine)
        self.assertEqual(result.edits, ["수치를 추가해라"])

    async def test_missing_openai_key_is_reported(self):
        with patch("agents.critic.openai_client", None):
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                await CriticAgent(model="test-model").review("충분한 요약문", "summary")

    async def test_unavailable_grpc_server_fails_fast(self):
        with patch("grpc_server.SUMMARIZER_ENDPOINT", "127.0.0.1:65534"):
            with self.assertRaises(Exception):
                await VOCGRPCRuntime().run_with_params(
                    filters=["결제"],
                    task="summary",
                    max_items=10,
                    csv_path=DEFAULT_CSV,
                    timeout=0.2,
                )

    async def test_retriever_results_and_empty_case(self):
        agent = RetrieverAgent()
        payment = await agent.run(DEFAULT_CSV, ["결제"], 30)
        empty = await agent.run(DEFAULT_CSV, ["개인정보 삭제"], 30)
        self.assertGreater(len(payment), 0)
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
