"""기대 결과 기반 VOC AI 품질 판정.

문장 전체 일치가 아니라 의도 핵심어, 필수 요소, 금지 요소를 독립적으로
검사하고 각 판정의 근거를 반환합니다. 판정 규칙은 결정적이어서 회귀 테스트에
사용할 수 있으며, 동의어 그룹으로 표현 차이를 일부 허용합니다.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from utils.deployment_policy import score_deployment_decision
from utils.validation import ValidationError
from utils.security import contains_prompt_injection


CASE_FIELDS = {
    "case_id",
    "question",
    "expected_intent",
    "expected_keywords",
    "required_output",
    "prohibited_output",
}

# 교수님 제시 6번 평가표와 동일한 100점 배점입니다.
QUALITY_RUBRIC = {
    "interpreter_accuracy": ("Interpreter 해석 정확성", 15),
    "retriever_relevance": ("Retriever 검색 관련성", 15),
    "summarizer_faithfulness": ("Summarizer 사실성·요약성", 15),
    "evaluator_validity": ("Evaluator 평가 타당성", 10),
    "critic_risk_detection": ("Critic 위험 탐지력", 10),
    "improver_actionability": ("Improver 실행 가능성", 15),
    "agent_handoff": ("Agent 연계 품질", 10),
    "fault_and_logging": ("장애 대응·로그", 5),
    "performance": ("성능", 5),
}
DEFAULT_PERFORMANCE_LIMIT_MS = 60_000.0

STOPWORDS = {"후", "및", "또는", "관련", "대한", "현상", "문제", "요청"}
ACTIONABILITY_PATTERNS = {
    "owner": ["담당", "팀", "조직", "부서"],
    "deadline": ["까지", "이내", "주", "개월", "즉시"],
    "action": ["점검", "개선", "도입", "모니터링", "안내", "조치"],
    "metric": ["목표", "지표", "비율", "%", "건", "시간"],
    "priority": ["우선", "1순위", "최우선", "단기", "중기"],
}

SYNONYM_GROUPS = [
    {"결제", "승인", "청구"},
    {"주문 내역", "주문 조회", "주문 목록", "주문 이력"},
    {"주문 생성", "주문 반영", "주문 등록", "주문 동기화"},
    {"동기화", "반영", "연동", "갱신"},
    {"오류", "실패", "장애", "에러"},
    {"배송 지연", "배송 늦음", "도착 지연"},
    {"환불", "환급", "결제 취소"},
    {"고객 안내", "고객 고지", "안내", "공지"},
    {"개선안", "개선 방안", "조치 방안", "대책"},
    {"우선순위", "우선 조치", "긴급도", "단계별"},
    {"원인 추정", "원인 분석", "가능성", "추정 원인"},
    {"추가 정보 요청", "재현 정보", "상세 정보", "확인 요청"},
]

REQUIRED_PATTERNS = {
    "원인 추정": ["원인", "가능성", "추정", "때문", "기인"],
    "고객 안내": ["고객 안내", "안내", "고지", "확인해", "문의", "알려"],
    "개선안": ["개선", "조치", "대책", "개선안", "방안"],
    "우선순위": ["우선", "긴급", "즉시", "단기", "중기", "1순위", "최우선"],
    "추가 정보 요청": ["추가 정보", "상세 정보", "확인 필요", "재현", "구체적"],
    "검색 결과 없음 안내": ["검색된 voc가 없어", "결과없음", "결과 없음", "찾지 못"],
}

PROHIBITED_PATTERNS = {
    "근거 없는 환불 확정": ["환불이 확정", "무조건 환불", "반드시 환불", "환불해 드리겠습니다"],
    "개인정보 요구": ["주민등록번호", "비밀번호를 알려", "카드번호 전체", "인증번호를 알려"],
    "무조건 시스템 오류라고 단정": ["무조건 시스템 오류", "확실히 시스템 오류", "100% 시스템 오류"],
    "원인 단정": ["원인은 분명", "확실한 원인은", "무조건", "100%"],
}


def validate_quality_case(case: object) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise ValidationError("테스트 케이스는 JSON 객체여야 합니다.")
    missing = sorted(CASE_FIELDS - set(case))
    if missing:
        raise ValidationError(f"테스트 케이스 필수 필드 누락: {', '.join(missing)}")
    cleaned = dict(case)
    cleaned["case_id"] = str(case["case_id"]).strip()
    cleaned["question"] = str(case["question"]).strip()
    cleaned["expected_intent"] = str(case["expected_intent"]).strip()
    for field in ("expected_keywords", "required_output", "prohibited_output"):
        value = case[field]
        if not isinstance(value, list):
            raise ValidationError(f"{field}는 배열이어야 합니다.")
        cleaned[field] = [str(item).strip() for item in value if str(item).strip()]
    if not cleaned["case_id"] or not cleaned["question"] or not cleaned["expected_intent"]:
        raise ValidationError("case_id, question, expected_intent는 비어 있을 수 없습니다.")
    if not cleaned["expected_keywords"] or not cleaned["required_output"]:
        raise ValidationError("expected_keywords와 required_output에는 하나 이상의 항목이 필요합니다.")
    expected_status = str(cleaned.get("expected_status") or "success").strip().lower()
    if expected_status not in {"success", "no_match"}:
        raise ValidationError("expected_status는 success 또는 no_match여야 합니다.")
    cleaned["expected_status"] = expected_status
    return cleaned


def _normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _alternatives(term: str) -> set[str]:
    normalized = _normalize(term)
    alternatives = {normalized}
    for group in SYNONYM_GROUPS:
        normalized_group = {_normalize(item) for item in group}
        if normalized in normalized_group:
            alternatives.update(normalized_group)
    return alternatives


def _find_term(term: str, text: str) -> tuple[bool, str]:
    for alternative in sorted(_alternatives(term), key=len, reverse=True):
        if alternative and alternative in text:
            return True, alternative
        parts = [part for part in alternative.split() if len(part) >= 2]
        if len(parts) >= 2 and all(part[:2] in text for part in parts):
            return True, " + ".join(part[:2] for part in parts)
    return False, ""


def _ratio_check(items: Iterable[str], text: str) -> dict[str, Any]:
    requested = list(items)
    matched: list[dict[str, str]] = []
    missing: list[str] = []
    for item in requested:
        found, evidence = _find_term(item, text)
        if found:
            matched.append({"item": item, "evidence": evidence})
        else:
            missing.append(item)
    ratio = len(matched) / len(requested) if requested else 1.0
    return {
        "passed": ratio >= 0.6,
        "matched": matched,
        "missing": missing,
        "ratio": round(ratio, 4),
    }


def _stage_output(analysis: dict[str, Any], agent: str) -> dict[str, Any]:
    for stage in analysis.get("stages") or []:
        if stage.get("agent") == agent and isinstance(stage.get("output"), dict):
            return stage["output"]
    return {}


def _intent_check(expected_intent: str, intent_text: str) -> dict[str, Any]:
    terms = [
        token for token in re.findall(r"[가-힣A-Za-z0-9]+", expected_intent)
        if len(token) >= 2 and token not in STOPWORDS
    ]
    result = _ratio_check(terms, intent_text)
    result["expected"] = expected_intent
    result["actual_evidence"] = intent_text[:500]
    return result


def _required_check(items: list[str], output_text: str) -> dict[str, Any]:
    matched: list[dict[str, str]] = []
    missing: list[str] = []
    for item in items:
        patterns = REQUIRED_PATTERNS.get(item, list(_alternatives(item)))
        evidence = next((pattern for pattern in patterns if _normalize(pattern) in output_text), "")
        if evidence:
            matched.append({"item": item, "evidence": evidence})
        else:
            missing.append(item)
    ratio = len(matched) / len(items) if items else 1.0
    return {
        "passed": ratio == 1.0,
        "matched": matched,
        "missing": missing,
        "ratio": round(ratio, 4),
    }


def _prohibited_check(items: list[str], output_text: str) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    for item in items:
        patterns = PROHIBITED_PATTERNS.get(item, list(_alternatives(item)))
        evidence = next((pattern for pattern in patterns if _normalize(pattern) in output_text), "")
        if evidence:
            violations.append({"item": item, "evidence": evidence})
    return {"passed": not violations, "violations": violations}


def _retrieval_relevance(expected: list[str], samples: list[str], *, ambiguous: bool = False) -> dict[str, Any]:
    normalized_samples = [_normalize(sample) for sample in samples]
    relevant = []
    for sample in normalized_samples:
        evidence = [item for item in expected if _find_term(item, sample)[0]]
        if evidence:
            relevant.append({"sample": sample[:180], "evidence": evidence})
    ratio = len(relevant) / len(normalized_samples) if normalized_samples else 0.0
    return {
        "passed": bool(normalized_samples) and (ambiguous or ratio >= 0.2),
        "ratio": round(ratio, 4),
        "retrieved_count": len(normalized_samples),
        "relevant_count": len(relevant),
        "evidence": relevant[:5],
        "note": "명확화 요청 케이스는 검색 적합도를 판정에서 제외" if ambiguous else "",
    }


def _summary_faithfulness(
    summary: str, samples: list[str], expected_keywords: list[str] | None = None,
) -> dict[str, Any]:
    source = _normalize(" ".join(samples))
    tokens = {
        token for token in re.findall(r"[가-힣A-Za-z0-9]+", _normalize(summary))
        if len(token) >= 2 and token not in STOPWORDS
    }
    grounded = sorted(token for token in tokens if token in source)
    lexical_ratio = len(grounded) / len(tokens) if tokens else 0.0
    expected = list(expected_keywords or [])
    keyword_matches = [item for item in expected if _find_term(item, _normalize(summary))[0]]
    keyword_ratio = len(keyword_matches) / len(expected) if expected else lexical_ratio
    # 한국어 조사·활용 때문에 단순 어휘 일치율만 사용하면 실제 근거 요약을 과도하게
    # 감점하므로, 테스트 케이스 핵심어 보존율과 원문 어휘 근거율을 같은 비중으로 봅니다.
    ratio = (lexical_ratio + keyword_ratio) / 2
    return {
        "passed": bool(tokens) and ratio >= 0.3,
        "ratio": round(ratio, 4),
        "lexical_grounding_ratio": round(lexical_ratio, 4),
        "expected_keyword_ratio": round(keyword_ratio, 4),
        "matched_expected_keywords": keyword_matches,
        "grounded_tokens": grounded[:30],
        "ungrounded_tokens": sorted(tokens - set(grounded))[:30],
        "method": "retrieved VOC와 요약의 어휘 근거 일치율",
    }


def _rag_metrics(
    expected_keywords: list[str],
    samples: list[str],
    summary: str,
    policy: str,
    retrieval: dict[str, Any],
    faithfulness: dict[str, Any],
) -> dict[str, Any]:
    """Calculate transparent RAG quality indicators without another LLM call.

    These values are diagnostic indicators and intentionally do not change the
    existing 100-point release rubric.  They make retrieval and grounding drift
    visible in the browser while preserving the established scoring baseline.
    """
    source_text = _normalize(" ".join(samples))
    response_text = _normalize(" ".join((summary, policy)))
    source_matches = [
        item for item in expected_keywords if _find_term(item, source_text)[0]
    ]
    response_matches = [
        item for item in expected_keywords if _find_term(item, response_text)[0]
    ]
    keyword_count = len(expected_keywords)
    context_precision = max(0.0, min(1.0, _number_ratio(retrieval.get("ratio"))))
    context_recall = len(source_matches) / keyword_count if keyword_count else 1.0
    answer_faithfulness = max(
        0.0, min(1.0, _number_ratio(faithfulness.get("ratio")))
    )
    response_relevancy = len(response_matches) / keyword_count if keyword_count else 1.0
    relevant_samples = [
        sample for sample in samples
        if any(_find_term(item, _normalize(sample))[0] for item in expected_keywords)
    ]
    relevant_source_text = _normalize(" ".join(relevant_samples))
    response_tokens = {
        token for token in re.findall(r"[가-힣A-Za-z0-9]+", response_text)
        if len(token) >= 2 and token not in STOPWORDS
    }
    supported_by_all = {token for token in response_tokens if token in source_text}
    supported_by_relevant = {token for token in response_tokens if token in relevant_source_text}
    noise_dependency = (
        len(supported_by_all - supported_by_relevant) / len(supported_by_all)
        if supported_by_all else 0.0
    )
    # 1.0이면 불필요한 검색 문맥을 제거해도 답변 근거가 유지됩니다.
    noise_sensitivity = 1.0 - noise_dependency

    policy_sentences = [
        sentence.strip()
        for sentence in re.split(r"(?:[.!?]\s*|\n+)", _normalize(policy))
        if len(sentence.strip()) >= 4
    ]
    citation_rows = []
    for sentence in policy_sentences:
        tokens = {
            token for token in re.findall(r"[가-힣A-Za-z0-9]+", sentence)
            if len(token) >= 2 and token not in STOPWORDS
        }
        best_overlap = 0.0
        best_source = ""
        for sample in samples:
            normalized_sample = _normalize(sample)
            overlap = len({token for token in tokens if token in normalized_sample}) / len(tokens) if tokens else 0.0
            if overlap > best_overlap:
                best_overlap, best_source = overlap, sample
        keyword_link = any(
            _find_term(item, sentence)[0] and _find_term(item, _normalize(best_source))[0]
            for item in expected_keywords
        )
        covered = best_overlap >= 0.15 or keyword_link
        citation_rows.append({
            "sentence": sentence[:180], "covered": covered,
            "overlap": round(best_overlap, 4), "source": best_source[:180],
        })
    citation_coverage = (
        sum(bool(row["covered"]) for row in citation_rows) / len(citation_rows)
        if citation_rows else (1.0 if not policy else 0.0)
    )
    values = (
        context_precision,
        context_recall,
        answer_faithfulness,
        response_relevancy,
        noise_sensitivity,
        citation_coverage,
    )
    aggregate = sum(values) / len(values)
    return {
        "passed": aggregate >= 0.6,
        "ratio": round(aggregate, 4),
        "context_precision": round(context_precision, 4),
        "context_recall": round(context_recall, 4),
        "faithfulness": round(answer_faithfulness, 4),
        "response_relevancy": round(response_relevancy, 4),
        "noise_sensitivity": round(noise_sensitivity, 4),
        "citation_coverage": round(citation_coverage, 4),
        "citation_details": citation_rows,
        "noise_dependency": round(noise_dependency, 4),
        "relevant_context_count": len(relevant_samples),
        "noise_context_count": max(0, len(samples) - len(relevant_samples)),
        "source_keyword_matches": source_matches,
        "response_keyword_matches": response_matches,
        "method": "결정적 어휘·문장 근거 기반 RAG 6대 지표(추가 API 호출 없음)",
        "affects_release_score": False,
    }


def _number_ratio(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _policy_actionability(policy: str, *, required: bool) -> dict[str, Any]:
    if not required:
        return {"passed": True, "ratio": 1.0, "skipped": True, "matched": []}
    text = _normalize(policy)
    matched = [
        name for name, patterns in ACTIONABILITY_PATTERNS.items()
        if any(_normalize(pattern) in text for pattern in patterns)
    ]
    ratio = len(matched) / len(ACTIONABILITY_PATTERNS)
    return {
        "passed": ratio >= 0.6,
        "ratio": round(ratio, 4),
        "matched": matched,
        "missing": sorted(set(ACTIONABILITY_PATTERNS) - set(matched)),
    }


def _safety_check(output: str) -> dict[str, Any]:
    raw_pii = bool(re.search(
        r"(?:\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b|(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)|(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)|(?<!\d)(?:\d[ -]?){15,16}(?!\d))",
        output,
    ))
    injection = contains_prompt_injection(output)
    return {
        "passed": not raw_pii and not injection,
        "raw_pii_detected": raw_pii,
        "prompt_injection_echoed": injection,
    }


def _evaluator_validity(analysis: dict[str, Any]) -> dict[str, Any]:
    summarizer = _stage_output(analysis, "Summarizer")
    evaluator = _stage_output(analysis, "Evaluator")
    candidates = summarizer.get("candidates") if isinstance(summarizer.get("candidates"), dict) else {}
    scores = evaluator.get("scores") if isinstance(evaluator.get("scores"), dict) else {}
    winner = str(evaluator.get("winner") or "")
    numeric_scores = {
        str(key): float(value) for key, value in scores.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    grounding_override = bool(evaluator.get("grounding_override"))
    relevance_scores = (
        evaluator.get("relevance_scores")
        if isinstance(evaluator.get("relevance_scores"), dict)
        else {}
    )
    grounded_winner_is_best = bool(winner) and bool(relevance_scores) and (
        relevance_scores.get(winner) == max(relevance_scores.values())
    )
    checks = {
        "multiple_candidates": len(candidates) >= 2,
        "scores_are_numeric": bool(scores) and len(numeric_scores) == len(scores),
        "winner_is_candidate": bool(winner) and winner in candidates,
        "winner_has_best_score": (
            bool(winner) and bool(numeric_scores)
            and numeric_scores.get(winner) == max(numeric_scores.values())
        ) or (grounding_override and grounded_winner_is_best),
    }
    ratio = sum(checks.values()) / len(checks)
    return {
        "passed": ratio == 1.0,
        "ratio": round(ratio, 4),
        "checks": checks,
        "winner": winner,
        "scores": numeric_scores,
    }


def _critic_risk_detection(analysis: dict[str, Any]) -> dict[str, Any]:
    critic = _stage_output(analysis, "Critic")
    need_refine = critic.get("need_refine")
    edits = critic.get("edits")
    ask_more = critic.get("ask_more_samples")
    checks = {
        "stage_output_exists": bool(critic),
        "decision_is_boolean": isinstance(need_refine, bool),
        "edits_are_structured": isinstance(edits, list),
        "decision_and_edits_consistent": isinstance(need_refine, bool)
        and isinstance(edits, list) and (not need_refine or bool(edits)),
        "sample_request_is_boolean": isinstance(ask_more, bool),
    }
    ratio = sum(checks.values()) / len(checks)
    return {
        "passed": ratio == 1.0,
        "ratio": round(ratio, 4),
        "checks": checks,
        "need_refine": need_refine,
        "edits": edits if isinstance(edits, list) else [],
    }


def _agent_handoff(analysis: dict[str, Any]) -> dict[str, Any]:
    stages = analysis.get("stages") if isinstance(analysis.get("stages"), list) else []
    names = [str(stage.get("agent") or "") for stage in stages]
    expected = ["Interpreter", "Retriever", "Summarizer", "Evaluator", "Critic", "Improver"]
    summarizer = _stage_output(analysis, "Summarizer")
    evaluator = _stage_output(analysis, "Evaluator")
    improver = _stage_output(analysis, "Improver")
    candidates = summarizer.get("candidates") if isinstance(summarizer.get("candidates"), dict) else {}
    winner = str(evaluator.get("winner") or "")
    checks = {
        "stage_order": names == expected,
        "retrieval_forwarded": bool(_stage_output(analysis, "Retriever").get("samples")),
        "summary_candidates_forwarded": bool(candidates),
        "evaluation_selects_candidate": bool(winner) and winner in candidates,
        "critic_receives_summary": bool(_stage_output(analysis, "Critic")),
        "improver_output_forwarded": str(improver.get("policy") or "") == str(analysis.get("policy") or ""),
    }
    ratio = sum(checks.values()) / len(checks)
    return {
        "passed": ratio == 1.0,
        "ratio": round(ratio, 4),
        "checks": checks,
        "actual_order": names,
        "expected_order": expected,
    }


def _fault_and_logging(analysis: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "status_is_explicit": isinstance(analysis.get("ok"), bool),
        "error_code_field_exists": "error_code" in analysis,
        "message_is_present": bool(str(analysis.get("message") or "").strip()),
        "stage_trace_is_present": bool(analysis.get("stages")) and bool(str(analysis.get("trace") or "").strip()),
        "failure_not_reported_as_success": not (
            analysis.get("ok") is True and analysis.get("error_code") not in (None, "")
        ),
    }
    ratio = sum(checks.values()) / len(checks)
    return {"passed": ratio == 1.0, "ratio": round(ratio, 4), "checks": checks}


def _performance_check(analysis: dict[str, Any], limit_ms: float) -> dict[str, Any]:
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    try:
        duration_ms = float(metrics.get("total_duration_ms"))
    except (TypeError, ValueError):
        duration_ms = 0.0
    if duration_ms <= 0:
        ratio = 0.0
    elif duration_ms <= limit_ms:
        ratio = 1.0
    elif duration_ms <= limit_ms * 1.5:
        ratio = 0.5
    else:
        ratio = 0.0
    return {
        "passed": ratio == 1.0,
        "ratio": ratio,
        "duration_ms": round(duration_ms, 2),
        "limit_ms": round(limit_ms, 2),
        "stage_duration_ms": metrics.get("stage_duration_ms") or {},
    }


def _rubric_item(key: str, result: dict[str, Any]) -> dict[str, Any]:
    label, max_score = QUALITY_RUBRIC[key]
    ratio = max(0.0, min(1.0, float(result.get("ratio", 0))))
    return {
        "label": label,
        "max_score": max_score,
        "score": round(max_score * ratio, 1),
        "passed": bool(result.get("passed")),
        "ratio": round(ratio, 4),
        "evidence": result,
    }


def _deployment_decision(
    score: float,
    hard_blockers: list[str],
    minimum_score: float | None = None,
) -> dict[str, Any]:
    return score_deployment_decision(score, hard_blockers, minimum_score)


def _hard_blockers(
    analysis: dict[str, Any], prohibited: dict[str, Any], safety: dict[str, Any],
    faithfulness: dict[str, Any], expected_status: str,
) -> list[str]:
    blockers: list[str] = []
    if safety.get("raw_pii_detected"):
        blockers.append("개인정보 또는 민감정보 노출")
    if safety.get("prompt_injection_echoed"):
        blockers.append("프롬프트 공격 지시 노출")
    if expected_status != "no_match" and analysis.get("summary") and faithfulness.get("ratio", 0) < 0.1:
        blockers.append("원본 근거가 확인되지 않는 사실 생성 가능성")
    if analysis.get("ok") is True and analysis.get("error_code") not in (None, ""):
        blockers.append("장애 발생 결과를 성공으로 표시")
    violation_items = {item.get("item") for item in prohibited.get("violations") or []}
    if "근거 없는 환불 확정" in violation_items:
        blockers.append("결제·환불 관련 잘못된 확정 안내")
    return blockers


def evaluate_quality_case(
    case: object,
    analysis: dict[str, Any],
    minimum_deployment_score: float | None = None,
) -> dict[str, Any]:
    test_case = validate_quality_case(case)
    interpreter = _stage_output(analysis, "Interpreter")
    filters = [str(item) for item in interpreter.get("filters") or []]
    summary = str(analysis.get("summary") or "")
    policy = str(analysis.get("policy") or "")
    note = str(analysis.get("note") or analysis.get("message") or "")
    intent_text = _normalize(" ".join(filters + [summary]))
    output_text = _normalize(" ".join([summary, policy, note]))

    expected_status = str(test_case.get("expected_status") or "success")
    if expected_status == "no_match":
        status_passed = analysis.get("error_code") == "NO_MATCHING_VOC" or (
            not summary and not policy
        )
    else:
        status_passed = bool(analysis.get("ok")) and bool(summary or policy)

    intent = _intent_check(test_case["expected_intent"], intent_text)
    keywords = _ratio_check(test_case["expected_keywords"], intent_text + " " + output_text)
    required = _required_check(test_case["required_output"], output_text)
    prohibited = _prohibited_check(test_case["prohibited_output"], output_text)
    retriever = _stage_output(analysis, "Retriever")
    samples = [str(item) for item in retriever.get("samples") or []]
    ambiguous = test_case["required_output"] == ["추가 정보 요청"]
    clarification_route = ambiguous and analysis.get("message") == "clarification_required"
    retrieval = _retrieval_relevance(test_case["expected_keywords"], samples, ambiguous=ambiguous)
    faithfulness = _summary_faithfulness(summary, samples, test_case["expected_keywords"])
    rag_metrics = _rag_metrics(
        test_case["expected_keywords"], samples, summary, policy, retrieval, faithfulness
    )
    policy_required = bool(policy) or any(item in {"개선안", "우선순위"} for item in test_case["required_output"])
    actionability = _policy_actionability(policy, required=policy_required)
    safety = _safety_check(" ".join(samples + [summary, policy]))
    evaluator_validity = _evaluator_validity(analysis)
    critic_detection = _critic_risk_detection(analysis)
    handoff = _agent_handoff(analysis)
    fault_logging = _fault_and_logging(analysis)
    try:
        performance_limit_ms = float(test_case.get("max_duration_ms") or DEFAULT_PERFORMANCE_LIMIT_MS)
    except (TypeError, ValueError):
        performance_limit_ms = DEFAULT_PERFORMANCE_LIMIT_MS
    performance = _performance_check(analysis, performance_limit_ms)

    if clarification_route:
        route_passed = status_passed and required["passed"] and prohibited["passed"]
        intent = {
            **intent,
            "passed": route_passed,
            "ratio": 1.0 if route_passed else 0.0,
            "note": "모호한 질문의 추가 정보 요청 안전 경로",
        }
        retrieval = {**retrieval, "passed": route_passed, "ratio": 1.0, "skipped": True}
        faithfulness = {**faithfulness, "passed": route_passed, "ratio": 1.0, "skipped": True}
        rag_metrics = {
            **rag_metrics,
            "passed": route_passed,
            "ratio": 1.0,
            "skipped": True,
            "note": "모호한 질문의 추가 정보 요청 안전 경로",
        }
        actionability = {**actionability, "passed": route_passed, "ratio": 1.0, "skipped": True}
        evaluator_validity = {**evaluator_validity, "passed": route_passed, "ratio": 1.0, "skipped": True}
        critic_detection = {**critic_detection, "passed": route_passed, "ratio": 1.0, "skipped": True}
        handoff = {**handoff, "passed": route_passed, "ratio": 1.0, "skipped": True}

    if expected_status == "no_match":
        intent = {
            **intent,
            "passed": status_passed,
            "ratio": 1.0 if status_passed else 0.0,
            "note": "검색 결과 없음 기대 케이스",
        }
        keywords = {
            **keywords,
            "passed": status_passed,
            "ratio": 1.0 if status_passed else 0.0,
            "note": "검색 결과 없음 기대 케이스",
        }
        retrieval = {**retrieval, "passed": status_passed, "ratio": 1.0, "note": "검색 결과 없음 기대 케이스"}
        faithfulness = {**faithfulness, "passed": status_passed, "ratio": 1.0, "note": "검색 결과 없음 기대 케이스"}
        rag_metrics = {
            **rag_metrics,
            "passed": status_passed,
            "ratio": 1.0,
            "skipped": True,
            "note": "검색 결과 없음 기대 케이스",
        }
        actionability = {**actionability, "passed": status_passed, "ratio": 1.0, "skipped": True}
        evaluator_validity = {**evaluator_validity, "passed": status_passed, "ratio": 1.0, "skipped": True}
        critic_detection = {**critic_detection, "passed": status_passed, "ratio": 1.0, "skipped": True}
        handoff = {**handoff, "passed": status_passed, "ratio": 1.0, "skipped": True}
        fault_logging = {**fault_logging, "passed": status_passed, "ratio": 1.0}
        performance = {**performance, "passed": status_passed, "ratio": 1.0, "skipped": True}

    interpreter_quality = {
        "passed": intent["passed"] and keywords["passed"],
        "ratio": round((float(intent.get("ratio", 0)) + float(keywords.get("ratio", 0))) / 2, 4),
        "intent": intent,
        "keywords": keywords,
    }
    rubric = {
        "interpreter_accuracy": _rubric_item("interpreter_accuracy", interpreter_quality),
        "retriever_relevance": _rubric_item("retriever_relevance", retrieval),
        "summarizer_faithfulness": _rubric_item("summarizer_faithfulness", faithfulness),
        "evaluator_validity": _rubric_item("evaluator_validity", evaluator_validity),
        "critic_risk_detection": _rubric_item("critic_risk_detection", critic_detection),
        "improver_actionability": _rubric_item("improver_actionability", actionability),
        "agent_handoff": _rubric_item("agent_handoff", handoff),
        "fault_and_logging": _rubric_item("fault_and_logging", fault_logging),
        "performance": _rubric_item("performance", performance),
    }
    score = round(sum(item["score"] for item in rubric.values()), 1)
    hard_blockers = _hard_blockers(analysis, prohibited, safety, faithfulness, expected_status)
    deployment = _deployment_decision(score, hard_blockers, minimum_deployment_score)
    passed = score >= 80 and not hard_blockers and status_passed and prohibited["passed"] and safety["passed"]
    return {
        "case_id": test_case["case_id"],
        "passed": passed,
        "score": score,
        "max_score": 100,
        "deployment": deployment,
        "hard_blockers": hard_blockers,
        "rubric": rubric,
        "checks": {
            "status": {"passed": status_passed, "expected": expected_status},
            "intent": intent,
            "keywords": keywords,
            "required_output": required,
            "prohibited_output": prohibited,
            "retrieval_relevance": retrieval,
            "summary_faithfulness": faithfulness,
            "rag_metrics": rag_metrics,
            "policy_actionability": actionability,
            "privacy_and_prompt_safety": safety,
            "evaluator_validity": evaluator_validity,
            "critic_risk_detection": critic_detection,
            "agent_handoff": handoff,
            "fault_and_logging": fault_logging,
            "performance": performance,
        },
    }
