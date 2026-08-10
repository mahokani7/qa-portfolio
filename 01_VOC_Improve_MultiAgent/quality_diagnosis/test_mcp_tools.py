"""MCP 도구의 입력 검증·성공 계약·장애 응답을 서버 없이 검증합니다."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from utils import tools
from utils.settings import DEFAULT_CSV


class FakeRuntime:
    def __init__(self, *, fail_question: bool = False):
        self.fail_question = fail_question
        self.question_calls = 0
        self.param_calls = 0

    async def run_with_question(self, **_kwargs):
        self.question_calls += 1
        if self.fail_question:
            raise RuntimeError("Interpreter unavailable")
        return {
            "ok": True,
            "error_code": None,
            "message": "success",
            "summary": "VOC 요약 결과",
            "policy": "정책 개선안",
            "trace": "Interpreter; Retriever; Summarizer; Evaluator; Critic; Improver",
        }

    async def run_with_params(self, **_kwargs):
        self.param_calls += 1
        return {
            "ok": True,
            "error_code": None,
            "message": "success",
            "summary": "키워드 기반 VOC 요약 결과",
            "policy": "키워드 기반 정책 개선안",
            "trace": "Retriever; Summarizer; Evaluator; Critic; Improver",
        }


class MCPToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_check_reports_csv_metadata(self):
        result = await tools.health_check(DEFAULT_CSV)
        self.assertTrue(result["ok"])
        self.assertGreater(result["size"], 0)

    async def test_health_check_reports_missing_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "missing.csv")
            with patch.dict(os.environ, {"A2A_ALLOWED_CSV_DIRS": directory}):
                result = await tools.health_check(missing)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "HEALTH_CHECK_FAILED")

    async def test_analyze_voc_returns_standard_success_shape(self):
        runtime = FakeRuntime()
        with patch("utils.tools.get_runtime", return_value=runtime):
            result = await tools.analyze_voc("결제,주문", "both", 10, DEFAULT_CSV)
        self.assertTrue(result["ok"])
        self.assertEqual(result["error_code"], None)
        self.assertEqual(runtime.param_calls, 1)

    async def test_natural_language_tool_uses_keyword_fallback(self):
        runtime = FakeRuntime(fail_question=True)
        with patch("utils.tools.get_runtime", return_value=runtime):
            result = await tools.analyze_voc_nl_v2("결제 주문 오류를 분석해 주세요.", DEFAULT_CSV)
        self.assertTrue(result["ok"])
        self.assertEqual(runtime.question_calls, 1)
        self.assertEqual(runtime.param_calls, 1)
        self.assertIn("fallback", result["note"])

    async def test_invalid_task_returns_error_instead_of_exception(self):
        result = await tools.analyze_voc("결제", "delete", 10, DEFAULT_CSV)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "ANALYZE_VOC_FAILED")


if __name__ == "__main__":
    unittest.main()
