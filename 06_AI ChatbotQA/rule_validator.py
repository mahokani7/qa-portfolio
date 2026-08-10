"""
rule_validator.py
- AI 평가 전, 기본적인 규칙 기반 검증 수행
- AI 평가 결과가 이상하더라도 최소한의 오류를 먼저 찾아내기 위함
"""


def validate(response: str, expected_keyword: str) -> dict:
    """
    챗봇 응답에 기대 키워드가 포함되어 있는지 검사.
    반환: {"passed": bool, "reason": str}
    """
    if not response:
        return {"passed": False, "reason": "응답이 비어 있습니다."}

    passed = expected_keyword in response
    reason = (
        f"'{expected_keyword}' 키워드 포함 확인됨"
        if passed
        else f"'{expected_keyword}' 키워드 누락"
    )
    return {"passed": passed, "reason": reason}
