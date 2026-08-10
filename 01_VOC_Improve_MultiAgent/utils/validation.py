"""공통 입력값, CSV 경로, 네트워크 바인딩 검증."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALID_TASKS = {"summary", "policy", "both"}
TRUE_VALUES = {"1", "true", "yes", "on"}
VOC_DOMAIN_TERMS = {
    "결제", "주문", "배송", "환불", "취소", "쿠폰", "로그인", "앱", "상담",
    "인증", "회원", "상품", "영수증", "포인트", "오류", "장애", "멈춤", "지연", "개인정보",
}


class ValidationError(ValueError):
    """외부 입력값이 허용 범위를 벗어났을 때 발생합니다."""


def validate_question(question: str, *, max_length: int = 2_000) -> str:
    value = (question or "").strip()
    if not value:
        raise ValidationError("질문을 입력해 주세요.")
    if len(value) > max_length:
        raise ValidationError(f"질문은 {max_length}자 이하여야 합니다.")
    return value


def needs_clarification(question: str) -> bool:
    """대상 기능과 증상이 모두 없는 짧은 문의는 임의 분석하지 않습니다."""
    value = str(question or "").strip()
    if "개인정보" in value:
        return False
    vague_expressions = ("이상해요", "왜 이래", "다 안 돼", "다 안돼")
    return len(value) <= 20 and (
        not any(term in value for term in VOC_DOMAIN_TERMS)
        or any(expression in value for expression in vague_expressions)
    )


def is_multi_issue_question(question: str) -> bool:
    """복수 문제를 잇는 대표적인 한국어 연결 표현을 보수적으로 탐지합니다."""
    value = str(question or "").strip()
    return len(value) >= 20 and (
        value.count("도 ") >= 1
        or " 및 " in value
        or "되는데" in value
        or "하면서" in value
    )


def validate_task(task: str | None) -> str:
    value = (task or "both").strip().lower()
    if value not in VALID_TASKS:
        raise ValidationError("task는 summary, policy, both 중 하나여야 합니다.")
    return value


def validate_max_items(value: object, *, default: int = 30) -> int:
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise ValidationError("max_items는 정수여야 합니다.") from exc
    if not 5 <= parsed <= 200:
        raise ValidationError("max_items는 5 이상 200 이하여야 합니다.")
    return parsed


def validate_filters(filters: Optional[Iterable[object]]) -> list[str]:
    if filters is None:
        return []
    if isinstance(filters, (str, bytes)):
        raise ValidationError("filters는 문자열 목록이어야 합니다.")
    cleaned: list[str] = []
    for item in filters:
        value = str(item).strip()
        if not value:
            continue
        if len(value) > 100:
            raise ValidationError("각 필터는 100자 이하여야 합니다.")
        if value not in cleaned:
            cleaned.append(value)
    if len(cleaned) > 20:
        raise ValidationError("필터는 최대 20개까지 사용할 수 있습니다.")
    return cleaned


def allowed_csv_roots() -> list[Path]:
    """기본적으로 프로젝트 내부만 허용하고 환경변수로 안전하게 확장합니다."""
    roots = [PROJECT_ROOT]
    configured = os.environ.get("A2A_ALLOWED_CSV_DIRS", "")
    for raw in configured.split(os.pathsep):
        if raw.strip():
            roots.append(Path(raw.strip()).expanduser().resolve())
    return list(dict.fromkeys(roots))


def validate_csv_path(path: str, *, must_exist: bool = True) -> str:
    if not path or not str(path).strip():
        raise ValidationError("CSV 경로가 비어 있습니다.")
    candidate = Path(str(path).strip()).expanduser().resolve()
    if candidate.suffix.lower() != ".csv":
        raise ValidationError(".csv 파일만 사용할 수 있습니다.")
    if not any(candidate == root or root in candidate.parents for root in allowed_csv_roots()):
        raise ValidationError(
            "허용되지 않은 CSV 경로입니다. A2A_ALLOWED_CSV_DIRS로 허용 폴더를 지정할 수 있습니다."
        )
    if must_exist and (not candidate.exists() or not candidate.is_file()):
        raise ValidationError(f"CSV 파일을 찾을 수 없습니다: {candidate}")
    return str(candidate)


def validate_bind_address(address: str) -> str:
    """원격 바인딩은 명시적으로 허용한 경우에만 사용합니다."""
    value = (address or "").strip()
    try:
        host, port_text = value.rsplit(":", 1)
        port = int(port_text)
    except (ValueError, AttributeError) as exc:
        raise ValidationError(f"올바르지 않은 바인딩 주소입니다: {value}") from exc
    if not 1 <= port <= 65_535:
        raise ValidationError("포트는 1~65535 범위여야 합니다.")
    loopback_hosts = {"127.0.0.1", "localhost", "::1", "[::1]"}
    allow_remote = os.environ.get("A2A_ALLOW_REMOTE_BIND", "").lower() in TRUE_VALUES
    if host not in loopback_hosts and not allow_remote:
        raise ValidationError(
            "원격 gRPC 바인딩은 기본적으로 차단됩니다. 필요하면 A2A_ALLOW_REMOTE_BIND=1을 설정하세요."
        )
    return value


def validate_candidates(candidates: object) -> dict[str, str]:
    if not isinstance(candidates, dict):
        raise ValidationError("요약 후보 응답이 객체 형식이 아닙니다.")
    cleaned = {
        str(key): str(value).strip()
        for key, value in candidates.items()
        if str(key).startswith("S") and str(value).strip()
    }
    if not cleaned:
        raise ValidationError("유효한 요약 후보가 생성되지 않았습니다.")
    return cleaned


def select_valid_winner(
    candidates: dict[str, str],
    winner: object,
    scores: object = None,
) -> str:
    requested = str(winner or "")
    if requested in candidates:
        return requested
    if isinstance(scores, dict):
        ranked: list[tuple[float, str]] = []
        for key in candidates:
            try:
                ranked.append((float(scores.get(key, float("-inf"))), key))
            except (TypeError, ValueError):
                continue
        if ranked:
            return max(ranked)[1]
    return next(iter(candidates))


def _character_ngrams(text: object, size: int = 2) -> set[str]:
    """한국어 조사 차이를 견디도록 공백·기호를 제거한 문자 n-gram을 만듭니다."""
    normalized = re.sub(r"[^0-9A-Za-z가-힣]", "", str(text or "").lower())
    if not normalized:
        return set()
    if len(normalized) < size:
        return {normalized}
    return {normalized[index:index + size] for index in range(len(normalized) - size + 1)}


def _anchor_coverage(candidate: str, anchor: str) -> float:
    """후보가 기준 문장의 핵심 문자 조합을 얼마나 포함하는지 계산합니다."""
    anchor_grams = _character_ngrams(anchor)
    if not anchor_grams:
        return 0.0
    return len(_character_ngrams(candidate) & anchor_grams) / len(anchor_grams)


def select_grounded_winner(
    candidates: dict[str, str],
    requested_winner: str,
    question: str,
    source_texts: Optional[Iterable[str]] = None,
    *,
    override_margin: float = 0.08,
) -> tuple[str, dict[str, float], bool]:
    """질문·검색 1순위와 명백히 어긋난 LLM 후보 선택만 보수적으로 교정합니다."""
    sources = [str(value) for value in (source_texts or []) if str(value).strip()]
    primary_source = sources[0] if sources else ""
    relevance = {
        key: round(
            0.7 * _anchor_coverage(text, question)
            + 0.3 * _anchor_coverage(text, primary_source),
            4,
        )
        for key, text in candidates.items()
    }
    selected = requested_winner if requested_winner in candidates else next(iter(candidates))
    best = max(relevance, key=lambda key: (relevance[key], key))
    should_override = relevance[best] >= relevance[selected] + override_margin
    return (best if should_override else selected), relevance, should_override


def enforce_summary_grounding(
    summary: str,
    question: str,
    source_texts: Optional[Iterable[str]] = None,
    *,
    exact_match_threshold: float = 0.5,
    minimum_precision: float = 0.4,
) -> tuple[str, bool, float]:
    """질문과 1순위 원문이 거의 같을 때 요약의 외부 사실 혼입을 차단합니다."""
    sources = [str(value).strip() for value in (source_texts or []) if str(value).strip()]
    if not sources or not str(summary or "").strip():
        return str(summary or "").strip(), False, 1.0

    primary_source = sources[0]
    if _anchor_coverage(primary_source, question) < exact_match_threshold:
        return str(summary).strip(), False, 1.0

    candidate_grams = _character_ngrams(summary)
    anchor_grams = _character_ngrams(f"{question} {primary_source}")
    precision = (
        len(candidate_grams & anchor_grams) / len(candidate_grams)
        if candidate_grams
        else 0.0
    )
    if precision < minimum_precision:
        return primary_source, True, round(precision, 4)
    return str(summary).strip(), False, round(precision, 4)


def validate_generated_text(text: object, *, label: str, min_length: int) -> str:
    value = str(text or "").strip()
    if len(value) < min_length:
        raise ValidationError(f"생성된 {label} 내용이 충분하지 않습니다.")
    return value
