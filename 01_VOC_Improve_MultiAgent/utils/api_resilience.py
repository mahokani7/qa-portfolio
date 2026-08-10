"""외부 LLM API 오류를 안전한 사용자 안내로 분류합니다."""

from __future__ import annotations

import re


_API_KEY_PATTERN = re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{8,}\b", re.I)


def redact_api_secrets(value: object) -> str:
    """공급자 오류에 포함될 수 있는 API 키를 웹·로그용 문자열에서 제거합니다."""
    return _API_KEY_PATTERN.sub("[API_KEY_REDACTED]", str(value or ""))


def classify_provider_error(value: object) -> dict[str, object] | None:
    """공급자 오류 원문을 HTTP 상태·오류 코드·복구 안내로 변환합니다."""
    safe = redact_api_secrets(value)
    text = safe.lower()
    provider = "Anthropic" if "anthropic" in text else "OpenAI" if "openai" in text else "외부 LLM"

    if any(token in text for token in ("invalid_api_key", "incorrect api key", "authentication_error")) or re.search(
        r"(?:error code|status)[^\n]{0,12}\b401\b", text
    ):
        return {
            "error_code": "API_AUTHENTICATION_FAILED",
            "status_code": 401,
            "message": (
                f"{provider} API 키 인증에 실패했습니다. 프로젝트 .env의 키를 새 키로 교체한 뒤 "
                "grpc_server.py를 다시 시작하세요."
            ),
        }

    if any(
        token in text
        for token in (
            "credit balance is too low",
            "insufficient_quota",
            "insufficient credits",
            "purchase credits",
            "plans & billing",
        )
    ):
        return {
            "error_code": "API_CREDIT_EXHAUSTED",
            "status_code": 402,
            "message": (
                f"{provider} API 크레딧 또는 결제 한도가 부족합니다. 공급자 결제 화면에서 "
                "잔액과 사용 한도를 확인한 뒤 다시 실행하세요."
            ),
        }

    if any(token in text for token in ("429", "rate limit", "too many requests")):
        return {
            "error_code": "API_RATE_LIMITED",
            "status_code": 429,
            "message": rate_limit_guidance(),
        }

    return None


def is_rate_limit_error(exc: BaseException) -> bool:
    """SDK 종류와 관계없이 HTTP 429·rate limit 오류를 식별합니다."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    if status == 429:
        return True
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def rate_limit_guidance() -> str:
    return (
        "외부 LLM API 사용량 제한(HTTP 429)이 발생했습니다. "
        "잠시 후 다시 실행하고 동시 실행을 1건으로 낮추세요. "
        "반복되면 공급자 사용량 한도와 결제 상태를 확인하세요."
    )
