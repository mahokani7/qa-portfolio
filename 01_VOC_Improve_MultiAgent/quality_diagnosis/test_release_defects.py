"""초기 35건 평가에서 실패했던 2개 결함의 전용 재시험입니다."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from quality_diagnosis.llm_judge import AnthropicJudgeClient
from utils.api_resilience import (
    classify_provider_error,
    is_rate_limit_error,
    rate_limit_guidance,
    redact_api_secrets,
)


class _FakeMessages:
    def __init__(self):
        self.arguments = None

    async def create(self, **kwargs):
        self.arguments = kwargs
        return SimpleNamespace(content=[SimpleNamespace(text="정상")])


class _FakeAnthropicClient:
    def __init__(self):
        self.messages = _FakeMessages()


class _RateLimitError(RuntimeError):
    status_code = 429


class ReleaseDefectRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_branch_uses_anthropic_messages_interface(self):
        """분기 인터페이스 오류: Anthropic 전용 인수만 전달해야 합니다."""
        fake = _FakeAnthropicClient()
        with patch("quality_diagnosis.llm_judge.claude_client", fake):
            response = await AnthropicJudgeClient()("평가")

        self.assertEqual(response, "정상")
        self.assertIn("model", fake.messages.arguments)
        self.assertIn("max_tokens", fake.messages.arguments)
        self.assertIn("messages", fake.messages.arguments)
        self.assertNotIn("temperature", fake.messages.arguments)

    async def test_api_429_is_classified_with_recovery_guidance(self):
        """API 429 장애: 일반 500이 아니라 재시도 가능한 사용량 제한으로 분류합니다."""
        error = _RateLimitError("Too Many Requests")
        self.assertTrue(is_rate_limit_error(error))
        self.assertIn("동시 실행을 1건", rate_limit_guidance())
        self.assertIn("사용량 한도", rate_limit_guidance())

    async def test_provider_auth_error_is_redacted_and_classified(self):
        """API 인증 오류는 키를 숨기고 재시작 안내가 있는 401로 변환합니다."""
        secret = "sk-proj-" + "x" * 32
        classified = classify_provider_error(
            f"Error code: 401 - invalid_api_key - Incorrect API key provided: {secret}"
        )

        self.assertEqual(classified["error_code"], "API_AUTHENTICATION_FAILED")
        self.assertEqual(classified["status_code"], 401)
        self.assertIn("grpc_server.py", classified["message"])
        self.assertNotIn(secret, redact_api_secrets(secret))

    async def test_provider_credit_error_has_billing_guidance(self):
        """크레딧 부족은 일반 502가 아닌 결제 복구가 가능한 오류로 분류합니다."""
        classified = classify_provider_error(
            "Anthropic API: Your credit balance is too low. Go to Plans & Billing to purchase credits."
        )

        self.assertEqual(classified["error_code"], "API_CREDIT_EXHAUSTED")
        self.assertEqual(classified["status_code"], 402)
        self.assertIn("결제", classified["message"])


if __name__ == "__main__":
    unittest.main()
