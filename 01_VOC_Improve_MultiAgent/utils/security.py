"""VOC 원문의 개인정보와 프롬프트 인젝션 표현을 최소화합니다."""

from __future__ import annotations

import re
from html import escape


PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("[이메일]", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("[전화번호]", re.compile(r"(?<!\d)(?:01[016789]|0\d{1,2})[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)")),
    ("[주민번호]", re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)")),
    ("[카드번호]", re.compile(r"(?<!\d)(?:\d[ -]?){15,16}(?!\d)")),
)

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:이전|위|앞선)\s*(?:지시|명령|프롬프트).{0,15}(?:무시|잊어|폐기)", re.I),
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.I),
    re.compile(r"(?:system|assistant)\s*(?:prompt|message)", re.I),
    re.compile(r"(?:비밀|api\s*key|시스템\s*프롬프트).{0,12}(?:출력|공개|알려)", re.I),
)

DANGEROUS_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:os\.system|subprocess\.(?:run|popen)|powershell(?:\.exe)?|cmd(?:\.exe)?\s+/c)", re.I),
    re.compile(r"(?:rm\s+-rf|del\s+/[sq]|remove-item|invoke-expression)", re.I),
    re.compile(r"(?:실행|호출)\s*(?:해|하라|하세요)?.{0,12}(?:셸|쉘|명령|스크립트|powershell|cmd)", re.I),
)


def mask_pii(text: object) -> str:
    """대표적인 직접 식별자를 자리표시자로 치환합니다."""
    value = str(text or "")
    for replacement, pattern in PII_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def contains_prompt_injection(text: object) -> bool:
    value = str(text or "")
    return any(pattern.search(value) for pattern in INJECTION_PATTERNS)


def neutralize_prompt_injection(text: object) -> str:
    """명령형 공격 문자열을 데이터 표식으로 바꿔 LLM 지시로 해석될 가능성을 낮춥니다."""
    value = str(text or "")
    for pattern in INJECTION_PATTERNS:
        value = pattern.sub("[차단된 프롬프트 지시]", value)
    return value


def contains_dangerous_instruction(text: object) -> bool:
    value = str(text or "")
    return any(pattern.search(value) for pattern in DANGEROUS_COMMAND_PATTERNS)


def neutralize_dangerous_instruction(text: object) -> str:
    value = str(text or "")
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        value = pattern.sub("[차단된 명령 실행 지시]", value)
    return value


def escape_untrusted_html(text: object) -> str:
    """Escape model/VOC text before it is placed into an HTML context."""
    return escape(str(text or ""), quote=True)


def sanitize_voc_text(text: object) -> str:
    return neutralize_dangerous_instruction(
        neutralize_prompt_injection(mask_pii(text))
    ).strip()
