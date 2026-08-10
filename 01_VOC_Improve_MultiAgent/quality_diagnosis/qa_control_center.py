"""QA Control Center data store and report index.

The application already produces immutable JSON evidence files.  This module
builds a lightweight SQLite index over those files so the browser can show run
history, baseline comparisons, agent traces, approval decisions and drift
alerts without changing the original evidence.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from utils.experiment_version import git_revision


DEFAULT_SETTINGS: dict[str, float] = {
    "input_cost_per_million": 0.0,
    "output_cost_per_million": 0.0,
    "cost_budget": 0.0,
    "drift_score_drop": 3.0,
    "drift_pass_rate_drop": 5.0,
    "drift_latency_increase_pct": 30.0,
    "drift_p95_increase_pct": 30.0,
    "drift_cost_increase_pct": 30.0,
    "rate_limit_alert_count": 1.0,
    "human_judge_gap_threshold": 10.0,
}
INDEX_SCHEMA_VERSION = 3
AGENT_RUBRIC_KEYS = {
    "Interpreter": "interpreter_accuracy",
    "Retriever": "retriever_relevance",
    "Summarizer": "summarizer_faithfulness",
    "Evaluator": "evaluator_validity",
    "Critic": "critic_risk_detection",
    "Improver": "improver_actionability",
}

ALLOWED_APPROVAL_DECISIONS = {
    "PENDING",
    "REVIEWING",
    "APPROVED",
    "REJECTED",
    "CHANGES_REQUESTED",
}

# unittest의 긴 Python 식별자를 운영자용 테스트 번호와 설명으로 변환합니다.
# 원본 식별자는 감사 추적을 위해 보존하되 화면의 기본 제목으로 사용하지 않습니다.
AUTOMATED_TEST_CATALOG: dict[str, tuple[str, str, str, str, str]] = {
    "test_anthropic_wrapper_uses_central_policy_model": (
        "AGENT-01", "Anthropic 정책 모델 중앙 설정 검증", "Agent 단위 테스트",
        "Anthropic 래퍼가 개별 하드코딩 대신 공통 정책 모델 설정을 사용하는지 확인합니다.",
        "AnthropicChat의 모델과 중앙 MODEL_POLICY 값이 같아야 합니다.",
    ),
    "test_critic_returns_structured_risk_decision": (
        "AGENT-02", "Critic 구조화 위험 판정 검증", "Agent 단위 테스트",
        "Critic이 요약 검토 결과를 수정 여부·수정 지침·추가 샘플 여부로 구조화하는지 확인합니다.",
        "need_refine은 Boolean, edits는 목록, ask_more_samples는 Boolean이어야 합니다.",
    ),
    "test_evaluator_selects_highest_scored_candidate": (
        "AGENT-03", "Evaluator 최고 점수 후보 선택 검증", "Agent 단위 테스트",
        "S0·S1·S2 요약 후보를 결정적 Evaluator에 전달해 최고점 후보 선택 규칙을 확인합니다.",
        "winner가 S0이고 S0 점수가 모든 후보 점수 중 최고점이어야 합니다.",
    ),
    "test_improver_returns_actionable_policy": (
        "AGENT-04", "Improver 실행 가능한 정책 생성 검증", "Agent 단위 테스트",
        "결제 후 주문 반영 지연 요약으로 담당·일정·목표 지표가 있는 정책을 생성하는지 확인합니다.",
        "정책에 담당, 1주 이내 일정, 목표 지표가 모두 포함되어야 합니다.",
    ),
    "test_interpreter_extracts_expected_search_terms": (
        "AGENT-05", "Interpreter 검색어 추출 검증", "Agent 단위 테스트",
        "첫 번째 VOC 테스트 질문을 분석해 작업 유형과 검색 키워드를 추출하는지 확인합니다.",
        "task=both, 기대 키워드 포함, max_items=10이어야 합니다.",
    ),
    "test_retriever_returns_relevant_voc": (
        "AGENT-06", "Retriever 관련 VOC 검색 검증", "Agent 단위 테스트",
        "결제·주문 키워드로 CSV를 검색해 관련 고객 불만을 반환하는지 확인합니다.",
        "검색 결과가 존재하고 최소 한 건에 결제 또는 주문 키워드가 포함되어야 합니다.",
    ),
    "test_summarizer_creates_three_candidates": (
        "AGENT-07", "Summarizer 요약 후보 3개 생성 검증", "Agent 단위 테스트",
        "주문 반영 지연 VOC로 S0·S1·S2 세 가지 요약 후보를 생성하는지 확인합니다.",
        "후보 키가 S0·S1·S2이고 모든 요약이 비어 있지 않아야 합니다.",
    ),
    "test_feature_cases_complete_expected_agent_path": (
        "PIPE-01", "18개 기능 케이스 Agent 경로 완주 검증", "파이프라인 E2E 테스트",
        "이커머스 18개 케이스를 오프라인 전체 파이프라인으로 실행해 단계 연결을 확인합니다.",
        "18건 모두 PASS하고 상황별 기대 Agent 순서를 정확히 따라야 합니다.",
    ),
    "test_quality_catalog_contains_exactly_twenty_cases": (
        "PIPE-02", "품질 카탈로그 20건 구성 검증", "파이프라인 E2E 테스트",
        "품질 테스트 카탈로그와 기대 결과 파일의 개수·고유성·장애 시나리오 구성을 확인합니다.",
        "각 파일 20건, case_id 중복 없음, 장애 시나리오 2건이어야 합니다.",
    ),
    "test_empty_search_stops_safely_without_hallucination": (
        "FAULT-01", "빈 검색 결과의 안전 중단 검증", "장애 허용성 테스트",
        "Retriever 결과가 0건일 때 후속 LLM이 사실을 만들어내지 않고 중단하는지 확인합니다.",
        "NO_MATCHING_VOC 오류로 종료하고 요약·정책을 생성하지 않아야 합니다.",
    ),
    "test_rejected_api_key_error_is_preserved": (
        "FAULT-02", "API 인증 거부 원인 보존 검증", "장애 허용성 테스트",
        "외부 모델 API가 인증을 거부했을 때 실제 실패 원인이 보존되는지 확인합니다.",
        "인증 오류를 성공이나 모호한 일반 오류로 변환하지 않아야 합니다.",
    ),
    "test_retriever_shutdown_reports_connection_failure": (
        "FAULT-03", "Retriever 중단 연결 실패 검증", "장애 허용성 테스트",
        "Retriever 서비스가 꺼진 상황에서 파이프라인 오류 처리를 확인합니다.",
        "성공으로 위장하지 않고 gRPC 연결 실패를 반환해야 합니다.",
    ),
    "test_slow_agent_returns_deadline_exceeded": (
        "FAULT-04", "Agent 지연 시간 제한 검증", "장애 허용성 테스트",
        "Agent 응답이 제한 시간을 넘을 때 무한 대기하지 않는지 확인합니다.",
        "DEADLINE_EXCEEDED 시간 초과 오류를 반환해야 합니다.",
    ),
    "test_all_ready_existing_agents_are_reused": (
        "FAULT-05", "기존 6개 Agent 재사용 검증", "장애 허용성 테스트",
        "6001~6006의 정상 Agent가 이미 실행 중일 때 중복 실행 판단을 확인합니다.",
        "충돌이 아니라 already_running 재사용 상태로 판정해야 합니다.",
    ),
    "test_missing_api_key_is_not_hidden": (
        "FAULT-06", "API 키 누락 오류 표시 검증", "장애 허용성 테스트",
        "필수 API 키가 없을 때 시작 실패 원인이 명확히 표시되는지 확인합니다.",
        "키 누락을 성공이나 모호한 오류로 숨기지 않아야 합니다.",
    ),
    "test_missing_csv_returns_explicit_file_error": (
        "FAULT-07", "CSV 누락 파일 오류 검증", "장애 허용성 테스트",
        "존재하지 않는 VOC CSV를 지정했을 때 파일 검증을 확인합니다.",
        "누락된 파일 경로와 명확한 파일 오류를 반환해야 합니다.",
    ),
    "test_partial_port_occupation_remains_a_conflict": (
        "FAULT-08", "일부 Agent 포트 충돌 검증", "장애 허용성 테스트",
        "6개 중 일부 포트만 점유된 비정상 상태의 시작 판단을 확인합니다.",
        "정상 재사용이 아니라 conflict 상태로 판정해야 합니다.",
    ),
    "test_port_collision_is_detected_before_process_start": (
        "FAULT-09", "프로세스 시작 전 포트 충돌 검증", "장애 허용성 테스트",
        "사용 중인 포트를 가진 상태에서 Agent 프로세스를 시작하려는 상황을 확인합니다.",
        "자식 프로세스 시작 전에 포트 충돌을 탐지해야 합니다.",
    ),
    "test_analyze_voc_returns_standard_success_shape": (
        "MCP-01", "MCP VOC 분석 성공 응답 형식 검증", "MCP 도구 테스트",
        "analyze_voc 도구가 정상 실행 결과를 공통 응답 구조로 반환하는지 확인합니다.",
        "ok=true, error_code=null이고 파라미터 실행 경로를 한 번 호출해야 합니다.",
    ),
    "test_health_check_reports_csv_metadata": (
        "MCP-02", "MCP CSV 상태 점검 메타데이터 검증", "MCP 도구 테스트",
        "health_check 도구가 기본 CSV의 접근 가능성과 크기를 반환하는지 확인합니다.",
        "ok=true이고 파일 크기가 0보다 커야 합니다.",
    ),
    "test_health_check_reports_missing_csv": (
        "MCP-03", "MCP 누락 CSV 오류 검증", "MCP 도구 테스트",
        "health_check에 없는 CSV를 전달했을 때 표준 오류 응답을 확인합니다.",
        "ok=false이고 error_code=HEALTH_CHECK_FAILED여야 합니다.",
    ),
    "test_invalid_task_returns_error_instead_of_exception": (
        "MCP-04", "MCP 잘못된 작업값 오류 응답 검증", "MCP 도구 테스트",
        "지원하지 않는 task 값을 전달했을 때 예외 대신 표준 오류를 반환하는지 확인합니다.",
        "ok=false이고 ANALYZE_VOC_FAILED 오류 코드를 반환해야 합니다.",
    ),
    "test_natural_language_tool_uses_keyword_fallback": (
        "MCP-05", "자연어 분석 실패 시 키워드 대체 검증", "MCP 도구 테스트",
        "Interpreter 실행 실패 시 자연어 질문에서 키워드를 추출해 대체 분석하는지 확인합니다.",
        "질문 경로와 파라미터 경로를 각각 한 번 호출하고 fallback을 표시해야 합니다.",
    ),
    "test_critical_violation_forces_immediate_hold": (
        "JUDGE-01", "중대 위반 즉시 배포 보류 검증", "LLM Judge 판정 테스트",
        "Judge 평가에 중대 위반이 있을 때 점수와 무관하게 배포를 차단하는지 확인합니다.",
        "판정이 IMMEDIATE_HOLD이며 배포 불가여야 합니다.",
    ),
    "test_rubric_total_is_one_hundred": (
        "JUDGE-02", "Judge 평가표 총점 100점 검증", "LLM Judge 판정 테스트",
        "독립 Judge의 평가 항목 배점 합계를 확인합니다.",
        "전체 평가 항목의 최대 점수 합계가 정확히 100이어야 합니다.",
    ),
    "test_score_at_95_is_deployable": (
        "JUDGE-03", "95점 배포 가능 경계값 검증", "LLM Judge 판정 테스트",
        "배포 기준과 같은 95점에서 경계 판정이 올바른지 확인합니다.",
        "중대 위반이 없으면 95점은 DEPLOYABLE이어야 합니다.",
    ),
    "test_score_below_95_is_conditionally_held": (
        "JUDGE-04", "95점 미만 조건부 보류 검증", "LLM Judge 판정 테스트",
        "배포 기준보다 낮은 점수의 판정 규칙을 확인합니다.",
        "95점 미만은 배포 불가이며 조건부 보류로 분류되어야 합니다.",
    ),
    "test_scores_are_clamped_to_each_dimension": (
        "JUDGE-05", "Judge 항목별 점수 범위 제한 검증", "LLM Judge 판정 테스트",
        "모델이 배점 범위를 벗어난 점수를 반환했을 때 정규화하는지 확인합니다.",
        "각 점수는 해당 항목의 0~최대 배점 범위로 제한되어야 합니다.",
    ),
    "test_api_429_is_classified_with_recovery_guidance": (
        "REG-01", "API 429 사용량 제한 안내 회귀 검증", "핵심 결함 회귀 테스트",
        "API 사용량 제한이 일반 서버 오류가 아닌 복구 가능한 429로 분류되는지 확인합니다.",
        "API_RATE_LIMITED 코드와 재시도 안내를 반환해야 합니다.",
    ),
    "test_provider_branch_uses_anthropic_messages_interface": (
        "REG-02", "Anthropic 전용 인터페이스 분기 회귀 검증", "핵심 결함 회귀 테스트",
        "Anthropic Judge 분기에서 OpenAI 인수가 섞이지 않는지 확인합니다.",
        "Anthropic messages 인터페이스에 허용된 인수만 전달해야 합니다.",
    ),
}


def describe_automated_test(test_id: str, status: str = "", detail: str = "") -> dict[str, str] | None:
    """Return a human-readable descriptor for a unittest result identifier."""
    value = str(test_id or "")
    if not value.startswith("quality_diagnosis.") or ".test_" not in value:
        return None
    method = value.rsplit(".", 1)[-1]
    entry = AUTOMATED_TEST_CATALOG.get(method)
    if entry:
        case_number, title, category, description, expected = entry
    else:
        case_number = "AUTO-ETC"
        title = method.removeprefix("test_").replace("_", " ")
        category = "자동 품질 테스트"
        description = "Python unittest로 시스템의 내부 동작 계약을 검증합니다."
        expected = "정의된 assertion을 모두 통과해야 합니다."
    normalized_status = str(status or "UNKNOWN").upper()
    actual = (
        "PASS — 정의된 검증 조건을 모두 충족했습니다."
        if normalized_status == "PASS"
        else f"{normalized_status} — {detail or '실패 상세는 실행 증적을 확인하세요.'}"
    )
    module_path = value.rsplit(".", 2)[0].replace(".", "/") + ".py"
    return {
        "case_number": case_number,
        "title": title,
        "category": category,
        "description": description,
        "expected": expected,
        "actual": actual,
        "internal_id": value,
        "source": module_path,
        "scored": "false",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_run_id(path: Path) -> str:
    return hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:20]


def _estimated_tokens(value: Any) -> int:
    """Return a labelled estimate when provider usage metadata is unavailable."""
    text = _json(value)
    return max(1, math.ceil(len(text) / 4)) if text else 0


def _pass_rate(passed: int, total: int) -> float:
    return round((passed / total) * 100, 1) if total else 0.0


def _percentile(values: Iterable[float], percentile: float = 0.95) -> float:
    ordered = sorted(float(value) for value in values if float(value) >= 0)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 2)
    fraction = position - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def _git_commit(root: Path) -> str:
    return git_revision(root)


def _source_kind(path: Path, payload: dict[str, Any]) -> str | None:
    name = path.name.lower()
    if "_e2e_" in name:
        return "e2e"
    if name.startswith("test_35_case_result_"):
        return "comprehensive_35"
    if name.startswith("llm_judge_"):
        return "llm_judge"
    if name.startswith("fault_diagnosis_"):
        return "fault_diagnosis"
    if name == "test_result.json":
        return "quality_suite"
    if name.startswith("repeatability_"):
        return "repeatability"
    if name.startswith("red_team_"):
        return "red_team"
    if name.startswith("quality_gate_"):
        return "quality_gate"
    if isinstance(payload.get("summary"), dict) and isinstance(payload.get("results"), list):
        return "quality_run"
    return None


RUN_KIND_LABELS = {
    "e2e": "6-Agent E2E 품질검증",
    "comprehensive_35": "35건 종합 품질평가",
    "llm_judge": "독립 LLM Judge 평가",
    "fault_diagnosis": "장애 허용성 진단",
    "quality_suite": "자동 품질 테스트",
    "repeatability": "반복 안정성 진단",
    "red_team": "OWASP 보안 진단",
    "quality_gate": "CI 품질 게이트",
    "quality_run": "품질 실행",
}
DOMAIN_LABELS = {"ecommerce": "이커머스", "insurance": "보험", "security": "보안"}


def _qa_run_label(kind: str, domain: str = "", mode: str = "") -> str:
    label = RUN_KIND_LABELS.get(str(kind or ""), "품질 실행")
    context = DOMAIN_LABELS.get(str(domain or ""), str(domain or ""))
    mode_label = {"live": "라이브", "offline": "오프라인", "ci": "CI"}.get(
        str(mode or ""), str(mode or "")
    )
    suffix = " · ".join(value for value in (context, mode_label) if value)
    return f"{label} · {suffix}" if suffix else label


def _summary_from_payload(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    total = _integer(source.get("total"), len(results))
    passed = _integer(source.get("passed"))
    failed = _integer(source.get("failed"), max(total - passed, 0))
    if kind == "llm_judge":
        passed = sum(
            1 for row in results
            if str(row.get("decision") or "").upper() in {"PASS", "DEPLOYABLE", "APPROVED"}
        )
        total = len(results)
        failed = max(total - passed, 0)
    scores = [
        _number(row.get("score", row.get("total_score")), -1)
        for row in results if isinstance(row, dict)
    ]
    scores = [score for score in scores if score >= 0]
    average_score = source.get("average_score", payload.get("average_score"))
    if average_score is None and scores:
        average_score = sum(scores) / len(scores)
    mode = str(source.get("mode") or payload.get("mode") or "")
    domain = str(source.get("domain") or payload.get("domain") or "")
    if not mode and kind == "llm_judge":
        mode = str(payload.get("provider") or "judge")
    generated_at = str(
        source.get("generated_at") or payload.get("generated_at") or ""
    )
    duration_values = []
    rate_limit_count = 0
    critical_violations = 0
    for row in results:
        if not isinstance(row, dict):
            continue
        analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
        metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
        duration = _number(metrics.get("total_duration_ms"), -1)
        if duration >= 0:
            duration_values.append(duration)
        error_text = " ".join((
            str(row.get("error_code") or ""),
            str(analysis.get("error_code") or ""),
            str(analysis.get("message") or ""),
        )).lower()
        if "429" in error_text or "rate_limit" in error_text or "rate limit" in error_text:
            rate_limit_count += 1
        quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
        critical_violations += len(quality.get("hard_blockers") or [])
        critical_violations += len(row.get("critical_violations") or [])
    average_duration = (
        round(sum(duration_values) / len(duration_values), 2) if duration_values else 0.0
    )
    models = source.get("models") if isinstance(source.get("models"), dict) else {}
    provider = str(payload.get("provider") or source.get("provider") or "")
    model = str(payload.get("model") or source.get("model") or "")
    if not model and models:
        model = " / ".join(dict.fromkeys(str(value) for value in models.values() if value))
    threshold = source.get("minimum_deployment_score", payload.get("minimum_deployment_score"))
    return {
        "generated_at": generated_at,
        "mode": mode,
        "domain": domain,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": _number(source.get("pass_rate"), _pass_rate(passed, total)),
        "average_score": round(_number(average_score), 2),
        "average_duration_ms": average_duration,
        "live_verified": bool(
            source.get("live_quality_verified")
            or payload.get("live_llm_judge_verified")
            or mode.startswith("live")
        ),
        "provider": provider,
        "model": model,
        "deployment_threshold": round(_number(threshold, 95.0), 2),
        "p95_duration_ms": _percentile(duration_values),
        "rate_limit_count": rate_limit_count,
        "critical_violations": critical_violations,
    }


def _case_status(row: dict[str, Any]) -> str:
    quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
    if "passed" in quality:
        return "PASS" if quality.get("passed") else "FAIL"
    raw = str(row.get("status") or row.get("decision") or "").upper()
    if raw in {"PASSED", "SUCCESS", "DEPLOYABLE", "APPROVED"}:
        return "PASS"
    if raw in {"FAILED", "ERROR", "REJECTED", "HOLD"}:
        return "FAIL"
    return raw or "UNKNOWN"


def _case_score(row: dict[str, Any]) -> float:
    quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
    return round(_number(quality.get("score", row.get("score", row.get("total_score")))), 2)


def _case_output(row: dict[str, Any]) -> str:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    parts = []
    if analysis.get("summary"):
        parts.append(f"요약: {analysis['summary']}")
    if analysis.get("policy"):
        parts.append(f"정책: {analysis['policy']}")
    if row.get("rationale"):
        parts.append(f"Judge 근거: {row['rationale']}")
    if not parts and row.get("detail"):
        parts.append(str(row.get("detail")))
    return "\n".join(parts)


def _case_metrics(row: dict[str, Any]) -> dict[str, Any]:
    quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
    checks = quality.get("checks") if isinstance(quality.get("checks"), dict) else {}
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    metrics = analysis.get("metrics") if isinstance(analysis.get("metrics"), dict) else {}
    rubric = quality.get("rubric") or {}
    agent_scores = {
        str(key): _number(value.get("score"))
        for key, value in rubric.items()
        if isinstance(value, dict)
    }
    hard_blockers = quality.get("hard_blockers") or []
    return {
        "deployment": quality.get("deployment") or {},
        "hard_blockers": hard_blockers,
        "defects": list(hard_blockers) + list(row.get("critical_violations") or []),
        "rubric": rubric,
        "agent_scores": agent_scores,
        "rag": checks.get("rag_metrics") or {},
        "duration_ms": _number(metrics.get("total_duration_ms")),
        "stage_duration_ms": metrics.get("stage_duration_ms") or {},
        "usage": row.get("usage") if isinstance(row.get("usage"), dict) else {},
    }


def _trace_input(
    agent: str,
    row: dict[str, Any],
    output: dict[str, Any],
    prior_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    question = str(row.get("question") or "")
    if agent == "Interpreter":
        return {"question": question}
    if agent == "Retriever":
        intent = prior_outputs.get("Interpreter", {})
        return {key: intent.get(key) for key in ("filters", "max_items", "csv_path")}
    if agent == "Summarizer":
        return {
            "question": question,
            "samples": prior_outputs.get("Retriever", {}).get("samples") or [],
        }
    if agent == "Evaluator":
        return {
            "question": question,
            "candidates": prior_outputs.get("Summarizer", {}).get("candidates") or {},
        }
    if agent == "Critic":
        return {
            "question": question,
            "selected_summary": prior_outputs.get("Evaluator", {}).get("selected_summary") or "",
        }
    if agent == "Improver":
        return {
            "question": question,
            "summary": str((row.get("analysis") or {}).get("summary") or ""),
            "critic_edits": prior_outputs.get("Critic", {}).get("edits") or [],
        }
    return {"question": question}


def _agent_model(agent: str, models: dict[str, Any]) -> str:
    if agent in {"Interpreter", "Summarizer", "Evaluator", "Critic"}:
        return str(models.get("summary") or models.get("openai") or "")
    if agent == "Improver":
        return str(models.get("policy") or models.get("anthropic") or "")
    return "deterministic-retrieval" if agent == "Retriever" else ""


def _case_trace(
    row: dict[str, Any],
    input_rate: float = 0.0,
    output_rate: float = 0.0,
    models: dict[str, Any] | None = None,
    prompt_version: str = "unknown",
) -> list[dict[str, Any]]:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    stages = analysis.get("stages") if isinstance(analysis.get("stages"), list) else []
    trace = []
    offset = 0.0
    prior_outputs: dict[str, dict[str, Any]] = {}
    model_map = models or {}
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            continue
        duration = round(_number(stage.get("duration_ms")), 2)
        output = stage.get("output") if isinstance(stage.get("output"), dict) else {}
        agent = str(stage.get("agent") or f"Stage {index + 1}")
        stage_input = stage.get("input") if isinstance(stage.get("input"), dict) else None
        stage_input = stage_input or _trace_input(agent, row, output, prior_outputs)
        usage = stage.get("usage") if isinstance(stage.get("usage"), dict) else {}
        input_tokens = _integer(usage.get("input_tokens"), _estimated_tokens(stage_input))
        output_tokens = _integer(usage.get("output_tokens"), _estimated_tokens(output))
        exact_usage = bool(usage) and "input_tokens" in usage and "output_tokens" in usage
        cost = (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
        error = stage.get("error") if isinstance(stage.get("error"), dict) else {}
        trace.append({
            "sequence": index + 1,
            "agent": agent,
            "role": str(stage.get("role") or ""),
            "check": str(stage.get("check") or ""),
            "start_ms": round(offset, 2),
            "duration_ms": duration,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_output_tokens": output_tokens,
            "cost": round(cost, 6),
            "estimated_cost": round(cost, 6),
            "usage_is_estimated": not exact_usage,
            "provider": "anthropic" if agent == "Improver" else "local" if agent == "Retriever" else "openai",
            "model": _agent_model(agent, model_map),
            "prompt_version": prompt_version,
            "retry_count": _integer(stage.get("retry_count")),
            "error": error,
            "input": stage_input,
            "output": output,
            "before_refine": output.get("pre_refine_summary") or output.get("before_refine") or "",
            "after_refine": output.get("post_refine_summary") or output.get("after_refine") or "",
        })
        prior_outputs[agent] = output
        offset += duration
    return trace


@dataclass(frozen=True)
class ControlCenterPaths:
    reports: Path
    database: Path
    settings: Path


class QAControlCenter:
    """Persistent QA run index used by the local Starlette web application."""

    def __init__(
        self,
        reports_dir: Path,
        database_path: Path | None = None,
        settings_path: Path | None = None,
    ) -> None:
        reports = Path(reports_dir).resolve()
        reports.mkdir(parents=True, exist_ok=True)
        self.paths = ControlCenterPaths(
            reports=reports,
            database=Path(database_path or reports / "qa_control_center.db").resolve(),
            settings=Path(settings_path or reports / "observability_settings.json").resolve(),
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.paths.database, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    source_file TEXT NOT NULL UNIQUE,
                    source_digest TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    domain TEXT NOT NULL DEFAULT '',
                    mode TEXT NOT NULL DEFAULT '',
                    total INTEGER NOT NULL DEFAULT 0,
                    passed INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    pass_rate REAL NOT NULL DEFAULT 0,
                    average_score REAL NOT NULL DEFAULT 0,
                    average_duration_ms REAL NOT NULL DEFAULT 0,
                    live_verified INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    dataset_version TEXT NOT NULL DEFAULT '',
                    prompt_version TEXT NOT NULL DEFAULT '',
                    git_commit TEXT NOT NULL DEFAULT 'unknown',
                    deployment_threshold REAL NOT NULL DEFAULT 95,
                    p95_duration_ms REAL NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0,
                    rate_limit_count INTEGER NOT NULL DEFAULT 0,
                    defects_count INTEGER NOT NULL DEFAULT 0,
                    critical_violations INTEGER NOT NULL DEFAULT 0,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS case_results (
                    run_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'UNKNOWN',
                    score REAL NOT NULL DEFAULT 0,
                    output_text TEXT NOT NULL DEFAULT '',
                    metrics_json TEXT NOT NULL DEFAULT '{}',
                    trace_json TEXT NOT NULL DEFAULT '[]',
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY (run_id, case_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    case_id TEXT NOT NULL DEFAULT '',
                    review_score REAL,
                    judge_agreement INTEGER,
                    final_deployment_approved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT '',
                    target TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_generated ON runs(generated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runs_kind_domain ON runs(kind, domain, generated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_approvals_run ON approvals(run_id, created_at DESC);
                """
            )
            # 기존 사용자 DB를 지우지 않고 새 Experiment/승인 필드를 추가합니다.
            run_columns = {
                "git_commit": "TEXT NOT NULL DEFAULT 'unknown'",
                "deployment_threshold": "REAL NOT NULL DEFAULT 95",
                "p95_duration_ms": "REAL NOT NULL DEFAULT 0",
                "total_tokens": "INTEGER NOT NULL DEFAULT 0",
                "estimated_cost": "REAL NOT NULL DEFAULT 0",
                "rate_limit_count": "INTEGER NOT NULL DEFAULT 0",
                "defects_count": "INTEGER NOT NULL DEFAULT 0",
                "critical_violations": "INTEGER NOT NULL DEFAULT 0",
            }
            approval_columns = {
                "case_id": "TEXT NOT NULL DEFAULT ''",
                "review_score": "REAL",
                "judge_agreement": "INTEGER",
                "final_deployment_approved": "INTEGER NOT NULL DEFAULT 0",
            }
            for table, definitions in (("runs", run_columns), ("approvals", approval_columns)):
                existing = {
                    str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")
                }
                for name, definition in definitions.items():
                    if name not in existing:
                        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def load_settings(self) -> dict[str, float]:
        settings = dict(DEFAULT_SETTINGS)
        if self.paths.settings.is_file():
            try:
                raw = json.loads(self.paths.settings.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    for key in settings:
                        if key in raw:
                            settings[key] = max(0.0, _number(raw[key], settings[key]))
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        return settings

    def save_settings(self, values: dict[str, Any], actor: str = "web") -> dict[str, float]:
        settings = self.load_settings()
        for key in settings:
            if key in values:
                number = _number(values[key], -1)
                if number < 0:
                    raise ValueError(f"{key} 값은 0 이상이어야 합니다.")
                settings[key] = round(number, 6)
        temporary = self.paths.settings.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.paths.settings)
        if any(key in values for key in ("input_cost_per_million", "output_cost_per_million")):
            with closing(self._connect()) as connection, connection:
                rows = connection.execute(
                    "SELECT run_id, case_id, metrics_json, trace_json FROM case_results"
                ).fetchall()
                run_costs: dict[str, float] = {}
                for row in rows:
                    trace = _loads(row["trace_json"], [])
                    for stage in trace:
                        cost = (
                            _integer(stage.get("input_tokens")) / 1_000_000
                            * settings["input_cost_per_million"]
                            + _integer(stage.get("output_tokens")) / 1_000_000
                            * settings["output_cost_per_million"]
                        )
                        stage["cost"] = stage["estimated_cost"] = round(cost, 6)
                    metrics = _loads(row["metrics_json"], {})
                    usage = metrics.get("usage") if isinstance(metrics.get("usage"), dict) else {}
                    direct_cost = (
                        _integer(usage.get("input_tokens")) / 1_000_000
                        * settings["input_cost_per_million"]
                        + _integer(usage.get("output_tokens")) / 1_000_000
                        * settings["output_cost_per_million"]
                    )
                    run_costs[row["run_id"]] = run_costs.get(row["run_id"], 0.0) + direct_cost + sum(
                        _number(stage.get("cost")) for stage in trace
                    )
                    connection.execute(
                        "UPDATE case_results SET trace_json = ? WHERE run_id = ? AND case_id = ?",
                        (_json(trace), row["run_id"], row["case_id"]),
                    )
                for run_id, cost in run_costs.items():
                    connection.execute(
                        "UPDATE runs SET estimated_cost = ? WHERE run_id = ?",
                        (round(cost, 6), run_id),
                    )
        self.audit("SETTINGS_UPDATED", actor, self.paths.settings.name, settings)
        return settings

    def _version_digest(self, candidates: Iterable[Path]) -> str:
        digest = hashlib.sha256()
        found = False
        for path in candidates:
            if not path.is_file():
                continue
            found = True
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()[:12] if found else "unknown"

    def _dataset_version(self) -> str:
        root = self.paths.reports.parent.parent
        return self._version_digest((
            root / "test_cases.txt",
            root / "test_cases_insurance.jsonl",
            root / "voc.csv",
            root / "data" / "voc_insurance.csv",
        ))

    def _prompt_version(self) -> str:
        root = self.paths.reports.parent.parent
        files = sorted((root / "agents").glob("*.py")) if (root / "agents").is_dir() else []
        files.extend((root / "utils" / "quality_evaluator.py", root / "e2e_runner.py"))
        return self._version_digest(files)

    def sync_reports(self) -> dict[str, int]:
        indexed = 0
        skipped = 0
        errors = 0
        patterns = (
            "*e2e_*.json",
            "test_35_case_result_*.json",
            "llm_judge_*.json",
            "fault_diagnosis_*.json",
            "repeatability_*.json",
            "red_team_*.json",
            "quality_gate_*.json",
            "test_result.json",
        )
        paths: dict[str, Path] = {}
        for pattern in patterns:
            for path in self.paths.reports.glob(pattern):
                if path.is_file():
                    paths[path.name] = path
        for path in sorted(paths.values(), key=lambda value: value.stat().st_mtime):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    skipped += 1
                    continue
                kind = _source_kind(path, payload)
                if kind is None:
                    skipped += 1
                    continue
                digest = _file_digest(path)
                with closing(self._connect()) as connection, connection:
                    current = connection.execute(
                        "SELECT source_digest, metadata_json FROM runs WHERE source_file = ?", (path.name,)
                    ).fetchone()
                current_metadata = _loads(current["metadata_json"], {}) if current else {}
                if (
                    current and current["source_digest"] == digest
                    and _integer(current_metadata.get("index_schema_version")) >= INDEX_SCHEMA_VERSION
                ):
                    skipped += 1
                    continue
                self._index_report(path, payload, kind, digest)
                indexed += 1
            except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error):
                errors += 1
        return {"indexed": indexed, "skipped": skipped, "errors": errors, "total": len(paths)}

    def _index_report(
        self, path: Path, payload: dict[str, Any], kind: str, digest: str
    ) -> None:
        run_id = _stable_run_id(path)
        summary = _summary_from_payload(kind, payload)
        generated_at = summary["generated_at"] or datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        ).astimezone().isoformat(timespec="seconds")
        root = self.paths.reports.parent.parent
        source_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        experiment = source_summary.get("experiment") if isinstance(source_summary.get("experiment"), dict) else (
            payload.get("experiment") if isinstance(payload.get("experiment"), dict) else {}
        )
        dataset_version = str(experiment.get("dataset_version") or self._dataset_version())
        prompt_version = str(experiment.get("prompt_version") or self._prompt_version())
        models = experiment.get("models") if isinstance(experiment.get("models"), dict) else {}
        if not models:
            models = source_summary.get("models") if isinstance(source_summary.get("models"), dict) else {}
        if not models and summary.get("model"):
            models = {"judge": summary["model"]}
        metadata = {
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "scope": payload.get("scope"),
            "initial": payload.get("initial"),
            "models": models,
            "configuration": {
                "deployment_threshold": experiment.get("deployment_threshold", summary["deployment_threshold"]),
                "concurrency": experiment.get("concurrency"),
                "input_cost_per_million": self.load_settings()["input_cost_per_million"],
                "output_cost_per_million": self.load_settings()["output_cost_per_million"],
            },
            "source_size": path.stat().st_size,
        }
        results = payload.get("results") if isinstance(payload.get("results"), list) else []
        settings = self.load_settings()
        traces: list[list[dict[str, Any]]] = []
        metrics: list[dict[str, Any]] = []
        for raw_row in results:
            if not isinstance(raw_row, dict):
                traces.append([])
                metrics.append({})
                continue
            traces.append(_case_trace(
                raw_row,
                settings["input_cost_per_million"],
                settings["output_cost_per_million"],
                models,
                prompt_version,
            ))
            metrics.append(_case_metrics(raw_row))
        total_tokens = sum(
            _integer(stage.get("total_tokens")) for trace in traces for stage in trace
        )
        direct_input_tokens = sum(
            _integer(metric.get("usage", {}).get("input_tokens")) for metric in metrics
        )
        direct_output_tokens = sum(
            _integer(metric.get("usage", {}).get("output_tokens")) for metric in metrics
        )
        total_tokens += direct_input_tokens + direct_output_tokens
        estimated_cost = round(sum(
            _number(stage.get("cost")) for trace in traces for stage in trace
        ) + (direct_input_tokens / 1_000_000) * settings["input_cost_per_million"]
        + (direct_output_tokens / 1_000_000) * settings["output_cost_per_million"], 6)
        defects_count = sum(
            max(1, len(metric.get("defects") or []))
            for row, metric in zip(results, metrics)
            if isinstance(row, dict) and (_case_status(row) != "PASS" or metric.get("defects"))
        )
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, kind, source_file, source_digest, generated_at, indexed_at,
                    domain, mode, total, passed, failed, pass_rate, average_score,
                    average_duration_ms, live_verified, provider, model,
                    dataset_version, prompt_version, git_commit, deployment_threshold,
                    p95_duration_ms, total_tokens, estimated_cost, rate_limit_count,
                    defects_count, critical_violations, metadata_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET
                    kind=excluded.kind, source_file=excluded.source_file,
                    source_digest=excluded.source_digest, generated_at=excluded.generated_at,
                    indexed_at=excluded.indexed_at, domain=excluded.domain, mode=excluded.mode,
                    total=excluded.total, passed=excluded.passed, failed=excluded.failed,
                    pass_rate=excluded.pass_rate, average_score=excluded.average_score,
                    average_duration_ms=excluded.average_duration_ms,
                    live_verified=excluded.live_verified, provider=excluded.provider,
                    model=excluded.model, dataset_version=excluded.dataset_version,
                    prompt_version=excluded.prompt_version, git_commit=excluded.git_commit,
                    deployment_threshold=excluded.deployment_threshold,
                    p95_duration_ms=excluded.p95_duration_ms,
                    total_tokens=excluded.total_tokens, estimated_cost=excluded.estimated_cost,
                    rate_limit_count=excluded.rate_limit_count,
                    defects_count=excluded.defects_count,
                    critical_violations=excluded.critical_violations,
                    metadata_json=excluded.metadata_json
                """,
                (
                    run_id, kind, path.name, digest, generated_at, _now_iso(),
                    summary["domain"], summary["mode"], summary["total"],
                    summary["passed"], summary["failed"], summary["pass_rate"],
                    summary["average_score"], summary["average_duration_ms"],
                    int(summary["live_verified"]), summary["provider"], summary["model"],
                    dataset_version, prompt_version, str(experiment.get("git_commit") or _git_commit(root)),
                    _number(experiment.get("deployment_threshold"), summary["deployment_threshold"]), summary["p95_duration_ms"],
                    total_tokens, estimated_cost, summary["rate_limit_count"],
                    defects_count, summary["critical_violations"], _json(metadata),
                ),
            )
            connection.execute("DELETE FROM case_results WHERE run_id = ?", (run_id,))
            seen: dict[str, int] = {}
            for position, raw_row in enumerate(results, 1):
                if not isinstance(raw_row, dict):
                    continue
                base_id = str(
                    raw_row.get("case_id") or raw_row.get("test") or f"ROW-{position:03d}"
                )
                seen[base_id] = seen.get(base_id, 0) + 1
                case_id = base_id if seen[base_id] == 1 else f"{base_id}#{seen[base_id]}"
                connection.execute(
                    """
                    INSERT INTO case_results (
                        run_id, case_id, question, status, score, output_text,
                        metrics_json, trace_json, raw_json
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        run_id,
                        case_id,
                        str(raw_row.get("question") or ""),
                        _case_status(raw_row),
                        _case_score(raw_row),
                        _case_output(raw_row),
                        _json(metrics[position - 1]),
                        _json(traces[position - 1]),
                        _json(raw_row),
                    ),
                )

    @staticmethod
    def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["live_verified"] = bool(value.get("live_verified"))
        value["metadata"] = _loads(value.pop("metadata_json", "{}"), {})
        return value

    def list_runs(
        self,
        *,
        limit: int = 100,
        kind: str = "",
        domain: str = "",
        status: str = "",
        query: str = "",
        minimum_score: float | None = None,
        maximum_score: float | None = None,
        defects_only: bool = False,
        agent: str = "",
        sort_by: str = "generated_at",
        sort_direction: str = "desc",
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if kind:
            clauses.append("kind = ?")
            values.append(kind)
        if domain:
            clauses.append("domain = ?")
            values.append(domain)
        if status.upper() == "PASS":
            clauses.append("failed = 0 AND total > 0")
        elif status.upper() == "FAIL":
            clauses.append("failed > 0")
        if query:
            clauses.append("(source_file LIKE ? OR run_id LIKE ? OR model LIKE ? OR git_commit LIKE ?)")
            term = f"%{query}%"
            values.extend((term, term, term, term))
        if minimum_score is not None:
            clauses.append("average_score >= ?")
            values.append(float(minimum_score))
        if maximum_score is not None:
            clauses.append("average_score <= ?")
            values.append(float(maximum_score))
        if defects_only:
            clauses.append("defects_count > 0")
        if agent:
            rubric_key = AGENT_RUBRIC_KEYS.get(agent)
            if rubric_key:
                clauses.append(
                    "EXISTS (SELECT 1 FROM case_results c WHERE c.run_id = runs.run_id "
                    "AND json_extract(c.metrics_json, ?) = 0)"
                )
                values.append(f"$.rubric.{rubric_key}.passed")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        allowed_sorts = {
            "generated_at", "average_score", "pass_rate", "average_duration_ms",
            "p95_duration_ms", "estimated_cost", "defects_count",
        }
        order_column = sort_by if sort_by in allowed_sorts else "generated_at"
        order_direction = "ASC" if str(sort_direction).lower() == "asc" else "DESC"
        values.append(max(1, min(int(limit), 500)))
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"SELECT * FROM runs {where} ORDER BY {order_column} {order_direction}, indexed_at DESC LIMIT ?",
                values,
            ).fetchall()
            latest_approvals = {
                row["run_id"]: dict(row)
                for row in connection.execute(
                    "SELECT a.* FROM approvals a JOIN (SELECT run_id, MAX(approval_id) approval_id "
                    "FROM approvals GROUP BY run_id) x ON x.approval_id = a.approval_id"
                ).fetchall()
            }
        result = []
        for row in rows:
            value = self._run_dict(row)
            approval = latest_approvals.get(value["run_id"], {})
            value["approval_status"] = approval.get("decision", "PENDING")
            value["final_deployment_approved"] = bool(
                approval.get("final_deployment_approved", 0)
            )
            result.append(value)
        return result

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection, connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            cases = connection.execute(
                "SELECT case_id, question, status, score, output_text, metrics_json, trace_json, raw_json "
                "FROM case_results WHERE run_id = ? ORDER BY case_id",
                (run_id,),
            ).fetchall()
        result = self._run_dict(run)
        result["cases"] = [
            {
                "case_id": row["case_id"],
                "question": row["question"],
                "status": row["status"],
                "score": row["score"],
                "output": row["output_text"],
                "metrics": _loads(row["metrics_json"], {}),
                "trace": _loads(row["trace_json"], []),
                "raw": _loads(row["raw_json"], {}),
            }
            for row in cases
        ]
        for case in result["cases"]:
            descriptor = describe_automated_test(
                case["case_id"], case["status"], str((case["raw"] or {}).get("detail") or "")
            )
            if descriptor:
                case["test_descriptor"] = descriptor
        source_path = (self.paths.reports / result["source_file"]).resolve()
        if (
            source_path.parent == self.paths.reports.resolve()
            and source_path.is_file()
            and source_path.suffix.lower() == ".json"
        ):
            try:
                source_payload = json.loads(source_path.read_text(encoding="utf-8"))
                result["source_payload"] = source_payload if isinstance(source_payload, dict) else {
                    "value": source_payload
                }
            except (OSError, ValueError, json.JSONDecodeError):
                result["source_payload"] = {}
        else:
            result["source_payload"] = {}
        result["approvals"] = self.list_approvals(run_id=run_id)
        latest_approval = result["approvals"][0] if result["approvals"] else None
        result["release_approval"] = {
            "status": latest_approval["decision"] if latest_approval else "PENDING",
            "final_deployment_approved": bool(
                latest_approval and latest_approval.get("final_deployment_approved")
            ),
        }
        return result

    def list_case_results(
        self,
        *,
        limit: int = 200,
        run_id: str = "",
        domain: str = "",
        status: str = "",
        query: str = "",
        defects_only: bool = False,
        agent: str = "",
        minimum_score: float | None = None,
        sort_by: str = "score",
        sort_direction: str = "asc",
    ) -> list[dict[str, Any]]:
        # 케이스 Explorer에는 실제 테스트 케이스 판정만 노출합니다. 배포 보고서의
        # "배포 보류", "조건부 배포" 같은 실행 수준 판정은 수행 이력/대시보드에서
        # 다루며, 케이스 FAIL 수에 섞이지 않도록 제외합니다.
        clauses: list[str] = ["UPPER(c.status) IN ('PASS','FAIL','ERROR','UNKNOWN')"]
        values: list[Any] = []
        if run_id:
            clauses.append("c.run_id = ?")
            values.append(run_id)
        if domain:
            clauses.append("r.domain = ?")
            values.append(domain)
        if status.upper() in {"PASS", "FAIL", "ERROR", "UNKNOWN"}:
            clauses.append("c.status = ?")
            values.append(status.upper())
        if query:
            clauses.append("(c.case_id LIKE ? OR c.question LIKE ? OR c.output_text LIKE ?)")
            term = f"%{query}%"
            values.extend((term, term, term))
        if defects_only:
            clauses.append(
                "(c.status <> 'PASS' OR c.metrics_json LIKE '%\"defects\":[\"%')"
            )
        if agent:
            rubric_key = AGENT_RUBRIC_KEYS.get(agent)
            if rubric_key:
                clauses.append("json_extract(c.metrics_json, ?) = 0")
                values.append(f"$.rubric.{rubric_key}.passed")
        if minimum_score is not None:
            clauses.append("c.score >= ?")
            values.append(float(minimum_score))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sort_columns = {
            "score": "c.score", "generated_at": "r.generated_at",
            "duration": "json_extract(c.metrics_json, '$.duration_ms')",
            "case_id": "c.case_id",
        }
        order = sort_columns.get(sort_by, "c.score")
        direction = "DESC" if str(sort_direction).lower() == "desc" else "ASC"
        values.append(max(1, min(int(limit), 1000)))
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT c.run_id, c.case_id, c.question, c.status, c.score,
                       c.output_text, c.metrics_json, c.trace_json,
                       r.generated_at, r.kind, r.domain, r.mode, r.source_file
                FROM case_results c JOIN runs r ON r.run_id = c.run_id
                {where} ORDER BY {order} {direction}, r.generated_at DESC LIMIT ?
                """,
                values,
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["metrics"] = _loads(value.pop("metrics_json", "{}"), {})
            value["trace"] = _loads(value.pop("trace_json", "[]"), [])
            value["output"] = value.pop("output_text", "")
            descriptor = describe_automated_test(
                value["case_id"], value["status"], value["output"]
            )
            if descriptor:
                value["test_descriptor"] = descriptor
            result.append(value)
        return result

    def compare_runs(self, baseline_id: str, candidate_id: str) -> dict[str, Any]:
        baseline = self.get_run(baseline_id)
        candidate = self.get_run(candidate_id)
        if baseline is None or candidate is None:
            raise ValueError("기준선 또는 후보 실행 이력을 찾을 수 없습니다.")
        baseline_cases = {row["case_id"]: row for row in baseline["cases"]}
        candidate_cases = {row["case_id"]: row for row in candidate["cases"]}
        rows = []
        counts = {"improved": 0, "regressed": 0, "unchanged": 0, "added": 0, "removed": 0}
        for case_id in sorted(set(baseline_cases) | set(candidate_cases)):
            before = baseline_cases.get(case_id)
            after = candidate_cases.get(case_id)
            if before is None:
                classification = "added"
            elif after is None:
                classification = "removed"
            elif before["status"] != "PASS" and after["status"] == "PASS":
                classification = "improved"
            elif before["status"] == "PASS" and after["status"] != "PASS":
                classification = "regressed"
            else:
                delta = _number(after["score"]) - _number(before["score"])
                classification = "improved" if delta >= 1 else "regressed" if delta <= -1 else "unchanged"
            counts[classification] += 1
            before_output = before["output"] if before else ""
            after_output = after["output"] if after else ""
            diff_lines = list(difflib.unified_diff(
                before_output.splitlines(), after_output.splitlines(),
                fromfile="baseline", tofile="candidate", lineterm="",
            ))
            rows.append({
                "case_id": case_id,
                "classification": classification,
                "baseline_status": before["status"] if before else "MISSING",
                "candidate_status": after["status"] if after else "MISSING",
                "baseline_score": before["score"] if before else None,
                "candidate_score": after["score"] if after else None,
                "score_delta": round(
                    _number(after["score"] if after else 0) - _number(before["score"] if before else 0), 2
                ),
                "duration_delta_ms": round(
                    _number((after or {}).get("metrics", {}).get("duration_ms"))
                    - _number((before or {}).get("metrics", {}).get("duration_ms")), 2
                ),
                "token_delta": sum(_integer(stage.get("total_tokens")) for stage in (after or {}).get("trace", []))
                - sum(_integer(stage.get("total_tokens")) for stage in (before or {}).get("trace", [])),
                "cost_delta": round(
                    sum(_number(stage.get("cost")) for stage in (after or {}).get("trace", []))
                    - sum(_number(stage.get("cost")) for stage in (before or {}).get("trace", [])), 6
                ),
                "agent_score_delta": {
                    key: round(
                        _number((after or {}).get("metrics", {}).get("agent_scores", {}).get(key))
                        - _number((before or {}).get("metrics", {}).get("agent_scores", {}).get(key)), 2
                    )
                    for key in sorted(set(
                        (before or {}).get("metrics", {}).get("agent_scores", {})
                    ) | set((after or {}).get("metrics", {}).get("agent_scores", {})))
                },
                "new_defects": sorted(set((after or {}).get("metrics", {}).get("defects", []))
                                      - set((before or {}).get("metrics", {}).get("defects", []))),
                "output_diff": "\n".join(diff_lines[:120]),
            })

        def aggregate(run: dict[str, Any]) -> tuple[dict[str, float], dict[str, float]]:
            score_values: dict[str, list[float]] = {}
            duration_values: dict[str, list[float]] = {}
            rubric_agents = {value: key for key, value in AGENT_RUBRIC_KEYS.items()}
            for case in run["cases"]:
                for key, value in case.get("metrics", {}).get("agent_scores", {}).items():
                    score_values.setdefault(rubric_agents.get(key, key), []).append(_number(value))
                for stage in case.get("trace", []):
                    duration_values.setdefault(str(stage.get("agent") or ""), []).append(
                        _number(stage.get("duration_ms"))
                    )
            return (
                {key: round(sum(values) / len(values), 2) for key, values in score_values.items() if values},
                {key: round(sum(values) / len(values), 2) for key, values in duration_values.items() if key and values},
            )

        baseline_scores, baseline_timings = aggregate(baseline)
        candidate_scores, candidate_timings = aggregate(candidate)
        return {
            "baseline": {key: baseline[key] for key in baseline if key != "cases"},
            "candidate": {key: candidate[key] for key in candidate if key != "cases"},
            "summary": {
                **counts,
                "score_delta": round(candidate["average_score"] - baseline["average_score"], 2),
                "pass_rate_delta": round(candidate["pass_rate"] - baseline["pass_rate"], 2),
                "duration_delta_ms": round(
                    candidate["average_duration_ms"] - baseline["average_duration_ms"], 2
                ),
                "p95_duration_delta_ms": round(
                    candidate.get("p95_duration_ms", 0) - baseline.get("p95_duration_ms", 0), 2
                ),
                "token_delta": candidate.get("total_tokens", 0) - baseline.get("total_tokens", 0),
                "cost_delta": round(
                    candidate.get("estimated_cost", 0) - baseline.get("estimated_cost", 0), 6
                ),
                "defect_delta": candidate.get("defects_count", 0) - baseline.get("defects_count", 0),
                "critical_violation_delta": candidate.get("critical_violations", 0)
                - baseline.get("critical_violations", 0),
                "agent_score_delta": {
                    key: round(candidate_scores.get(key, 0) - baseline_scores.get(key, 0), 2)
                    for key in sorted(set(baseline_scores) | set(candidate_scores))
                },
                "agent_duration_delta_ms": {
                    key: round(candidate_timings.get(key, 0) - baseline_timings.get(key, 0), 2)
                    for key in sorted(set(baseline_timings) | set(candidate_timings))
                },
                "release_gate": "HOLD" if counts["regressed"] else "PASS",
            },
            "cases": rows,
        }

    def create_approval(
        self,
        run_id: str,
        reviewer: str,
        decision: str,
        comment: str = "",
        *,
        case_id: str = "",
        review_score: float | None = None,
        judge_agreement: bool | None = None,
        final_deployment_approved: bool = False,
    ) -> dict[str, Any]:
        reviewer = str(reviewer or "").strip()
        decision = str(decision or "").strip().upper()
        comment = str(comment or "").strip()
        if not reviewer or len(reviewer) > 80:
            raise ValueError("검토자 이름을 1~80자로 입력하세요.")
        if decision not in ALLOWED_APPROVAL_DECISIONS:
            raise ValueError("지원하지 않는 승인 결정입니다.")
        case_id = str(case_id or "").strip()[:120]
        if review_score is not None:
            review_score = _number(review_score, -1)
            if not 0 <= review_score <= 100:
                raise ValueError("사람 검토 점수는 0~100이어야 합니다.")
        if final_deployment_approved and decision != "APPROVED":
            raise ValueError("최종 배포 승인은 승인(APPROVED) 상태에서만 기록할 수 있습니다.")
        with closing(self._connect()) as connection, connection:
            exists = connection.execute(
                "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if exists is None:
                raise ValueError("승인할 실행 이력을 찾을 수 없습니다.")
            if case_id:
                case_exists = connection.execute(
                    "SELECT 1 FROM case_results WHERE run_id = ? AND case_id = ?",
                    (run_id, case_id),
                ).fetchone()
                if case_exists is None:
                    raise ValueError("검토할 테스트 케이스를 찾을 수 없습니다.")
            cursor = connection.execute(
                """
                INSERT INTO approvals(
                    run_id, reviewer, decision, comment, case_id, review_score,
                    judge_agreement, final_deployment_approved, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id, reviewer, decision, comment[:2000], case_id, review_score,
                    None if judge_agreement is None else int(bool(judge_agreement)),
                    int(bool(final_deployment_approved)), _now_iso(),
                ),
            )
            approval_id = cursor.lastrowid
        self.audit("APPROVAL_RECORDED", reviewer, run_id, {
            "decision": decision,
            "case_id": case_id,
            "review_score": review_score,
            "judge_agreement": judge_agreement,
            "final_deployment_approved": bool(final_deployment_approved),
            "comment": comment[:2000],
        })
        return self.list_approvals(approval_id=approval_id)[0]

    def list_approvals(
        self, *, run_id: str = "", approval_id: int | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if run_id:
            clauses.append("a.run_id = ?")
            values.append(run_id)
        if approval_id is not None:
            clauses.append("a.approval_id = ?")
            values.append(approval_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(max(1, min(limit, 500)))
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                f"""
                SELECT a.*, r.kind, r.domain, r.mode, r.generated_at AS run_generated_at,
                       r.total AS run_total, r.passed AS run_passed, r.failed AS run_failed,
                       r.average_score AS run_average_score,
                       c.question AS case_question, c.status AS case_status,
                       c.score AS case_score, c.output_text AS case_output,
                       c.raw_json AS case_raw_json
                FROM approvals a JOIN runs r ON r.run_id = a.run_id
                LEFT JOIN case_results c ON c.run_id = a.run_id AND c.case_id = a.case_id
                {where} ORDER BY a.created_at DESC, a.approval_id DESC LIMIT ?
                """,
                values,
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["judge_agreement"] = (
                None if value.get("judge_agreement") is None else bool(value["judge_agreement"])
            )
            value["final_deployment_approved"] = bool(value.get("final_deployment_approved"))
            raw_case = _loads(value.pop("case_raw_json", "{}"), {})
            descriptor = raw_case.get("test_descriptor") if isinstance(raw_case.get("test_descriptor"), dict) else {}
            value["case_title"] = str(
                descriptor.get("title") or raw_case.get("title") or raw_case.get("category") or ""
            )
            if value.get("case_id") and not value.get("case_question"):
                with closing(self._connect()) as lookup:
                    fallback = lookup.execute(
                        """
                        SELECT c.question FROM case_results c JOIN runs r ON r.run_id = c.run_id
                        WHERE c.case_id = ? AND c.question <> ''
                        ORDER BY r.generated_at DESC LIMIT 1
                        """,
                        (value["case_id"].split("#", 1)[0],),
                    ).fetchone()
                if fallback:
                    value["case_question"] = str(fallback[0] or "")
            value["run_label"] = _qa_run_label(value["kind"], value["domain"], value["mode"])
            value["scope_label"] = (
                f"{value['case_id']} · {value['case_title']}".rstrip(" ·")
                if value.get("case_id") else "실행 전체 검토"
            )
            value["qa_summary"] = (
                f"{value['case_status']} · {value['case_score']:.1f}점"
                if value.get("case_id") and value.get("case_status")
                else f"{value['run_passed']}/{value['run_total']} PASS · 평균 {value['run_average_score']:.1f}점"
            )
            value["case_output"] = str(value.get("case_output") or "")[:800]
            value["sample_cases"] = []
            if not value.get("case_id"):
                with closing(self._connect()) as sample_connection:
                    sample_rows = sample_connection.execute(
                        """
                        SELECT case_id, question, status, score, output_text, raw_json
                        FROM case_results WHERE run_id = ? ORDER BY case_id LIMIT 50
                        """,
                        (value["run_id"],),
                    ).fetchall()
                for sample_row in sample_rows:
                    sample_raw = _loads(sample_row["raw_json"], {})
                    sample_descriptor = (
                        sample_raw.get("test_descriptor")
                        if isinstance(sample_raw.get("test_descriptor"), dict) else {}
                    )
                    sample_title = str(
                        sample_descriptor.get("title") or sample_raw.get("title")
                        or sample_raw.get("category") or sample_row["question"] or "검증 항목"
                    )
                    value["sample_cases"].append({
                        "case_id": sample_row["case_id"], "title": sample_title,
                        "status": sample_row["status"], "score": sample_row["score"],
                        "output": str(sample_row["output_text"] or "")[:240],
                    })
            comment = str(value.get("comment") or "")
            value["comment_corrupted"] = comment.count("?") >= 3 or "???" in comment
            result.append(value)
        return result

    def review_queue(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return automatically prioritised case/run reviews.

        FAIL, hard blockers, Judge/E2E score disagreement and missing final human
        approval all feed the same queue.  This keeps the queue deterministic and
        usable even when no live Judge report exists.
        """
        settings = self.load_settings()
        runs = self.list_runs(limit=300)
        latest_by_kind: dict[tuple[str, str], dict[str, Any]] = {}
        for run in runs:
            latest_by_kind.setdefault((run["kind"], run["domain"]), run)
        judge_runs = [run for run in runs if run["kind"] == "llm_judge"]
        with closing(self._connect()) as connection:
            question_rows = connection.execute(
                """
                SELECT c.case_id, c.question FROM case_results c JOIN runs r ON r.run_id = c.run_id
                WHERE c.question <> '' ORDER BY r.generated_at DESC
                """
            ).fetchall()
        question_catalog: dict[str, str] = {}
        for question_row in question_rows:
            question_catalog.setdefault(str(question_row["case_id"]).split("#", 1)[0], str(question_row["question"]))
        judge_scores: dict[str, float] = {}
        if judge_runs:
            judge_detail = self.get_run(judge_runs[0]["run_id"])
            if judge_detail:
                judge_scores = {
                    case["case_id"].split("#", 1)[0]: _number(case["score"])
                    for case in judge_detail["cases"]
                }
        queue: list[dict[str, Any]] = []
        for run in runs:
            if run["kind"] not in {"e2e", "comprehensive_35", "llm_judge"}:
                continue
            detail = self.get_run(run["run_id"])
            if detail is None:
                continue
            approved_cases = {
                approval.get("case_id") or "*"
                for approval in detail["approvals"]
                if approval["decision"] == "APPROVED"
            }
            latest_reviews: dict[str, dict[str, Any]] = {}
            for approval in detail["approvals"]:
                latest_reviews.setdefault(str(approval.get("case_id") or "*"), approval)
            for case in detail["cases"]:
                base_id = case["case_id"].split("#", 1)[0]
                raw_case = case.get("raw") if isinstance(case.get("raw"), dict) else {}
                descriptor = raw_case.get("test_descriptor") if isinstance(raw_case.get("test_descriptor"), dict) else {}
                case_title = str(descriptor.get("title") or raw_case.get("title") or "")
                question = str(case.get("question") or question_catalog.get(base_id) or case_title)
                review = latest_reviews.get(case["case_id"]) or latest_reviews.get("*") or {}
                comparison_score = (
                    _number(review.get("review_score"))
                    if review.get("review_score") is not None else _number(case["score"])
                )
                gap = abs(comparison_score - judge_scores.get(base_id, comparison_score))
                defects = case.get("metrics", {}).get("defects", [])
                reasons = []
                if case["status"] != "PASS":
                    reasons.append("FAIL 또는 오류")
                if defects:
                    reasons.append("결함·중대 위반")
                if base_id in judge_scores and gap >= settings["human_judge_gap_threshold"]:
                    label = "사람/Judge" if review.get("review_score") is not None else "내부/Judge"
                    reasons.append(f"{label} 점수 차이 {gap:.1f}점")
                if "*" not in approved_cases and case["case_id"] not in approved_cases:
                    reasons.append("사람 승인 미기록")
                if not reasons:
                    continue
                priority = 3 if defects else 2 if case["status"] != "PASS" or gap else 1
                queue.append({
                    "run_id": run["run_id"], "case_id": case["case_id"],
                    "question": question, "case_title": case_title, "status": case["status"],
                    "score": case["score"], "judge_score": judge_scores.get(base_id),
                    "human_score": review.get("review_score"),
                    "score_gap": round(gap, 2), "reasons": reasons,
                    "priority": priority, "generated_at": run["generated_at"],
                    "domain": run["domain"], "kind": run["kind"],
                    "run_label": _qa_run_label(run["kind"], run["domain"], run["mode"]),
                    "output": str(case.get("output") or "")[:500],
                })
        queue.sort(key=lambda item: (-item["priority"], -item["score_gap"], item["score"]))
        return queue[: max(1, min(limit, 500))]

    def audit(
        self, event_type: str, actor: str = "", target: str = "", detail: Any = None
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO audit_events(event_type, actor, target, detail_json, created_at) VALUES (?,?,?,?,?)",
                (event_type, actor, target, _json(detail or {}), _now_iso()),
            )

    def list_audit_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection, connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY event_id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["detail"] = _loads(value.pop("detail_json", "{}"), {})
            result.append(value)
        return result

    def version_history(self, limit: int = 100) -> list[dict[str, Any]]:
        runs = self.list_runs(limit=limit)
        return [
            {
                "run_id": run["run_id"], "generated_at": run["generated_at"],
                "git_commit": run.get("git_commit") or "unknown",
                "dataset_version": run.get("dataset_version") or "unknown",
                "prompt_version": run.get("prompt_version") or "unknown",
                "provider": run.get("provider") or "",
                "model": run.get("model") or "",
                "deployment_threshold": run.get("deployment_threshold", 95),
                "configuration": run.get("metadata", {}).get("configuration") or {},
            }
            for run in runs
        ]

    def drift_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        settings = self.load_settings()
        runs = self.list_runs(limit=500)
        grouped: dict[tuple[str, str, str, int], list[dict[str, Any]]] = {}
        for run in runs:
            # 전체 회귀와 비용 확인용 1건 실행을 비교하면 거짓 경보가 발생하므로
            # 유형·도메인·모드뿐 아니라 동일 케이스 규모끼리 비교합니다.
            grouped.setdefault(
                (run["kind"], run["domain"], run["mode"], int(run["total"])), []
            ).append(run)
        alerts = []
        for key, values in grouped.items():
            latest = values[0]
            if latest.get("rate_limit_count", 0) >= settings["rate_limit_alert_count"]:
                alerts.append({
                    "kind": key[0], "domain": key[1], "mode": key[2], "total": key[3],
                    "latest_run_id": latest["run_id"], "previous_run_id": "",
                    "severity": "critical", "reasons": [
                        f"HTTP 429 {latest['rate_limit_count']}건 감지"
                    ],
                    "score_drop": 0, "pass_rate_drop": 0,
                    "latency_increase_pct": 0, "p95_increase_pct": 0,
                    "cost_increase_pct": 0, "rate_limit_count": latest["rate_limit_count"],
                })
            if settings["cost_budget"] > 0 and latest.get("estimated_cost", 0) > settings["cost_budget"]:
                alerts.append({
                    "kind": key[0], "domain": key[1], "mode": key[2], "total": key[3],
                    "latest_run_id": latest["run_id"], "previous_run_id": "",
                    "severity": "critical", "reasons": [
                        f"실행 비용 {latest['estimated_cost']:.4f}가 예산 {settings['cost_budget']:.4f} 초과"
                    ],
                    "score_drop": 0, "pass_rate_drop": 0,
                    "latency_increase_pct": 0, "p95_increase_pct": 0,
                    "cost_increase_pct": 0, "rate_limit_count": latest.get("rate_limit_count", 0),
                })
            if len(values) < 2:
                continue
            previous = values[1]
            score_drop = previous["average_score"] - latest["average_score"]
            pass_drop = previous["pass_rate"] - latest["pass_rate"]
            latency_increase_pct = 0.0
            if previous["average_duration_ms"] > 0:
                latency_increase_pct = (
                    (latest["average_duration_ms"] - previous["average_duration_ms"])
                    / previous["average_duration_ms"] * 100
                )
            p95_increase_pct = 0.0
            if previous.get("p95_duration_ms", 0) > 0:
                p95_increase_pct = (
                    (latest.get("p95_duration_ms", 0) - previous["p95_duration_ms"])
                    / previous["p95_duration_ms"] * 100
                )
            cost_increase_pct = 0.0
            if previous.get("estimated_cost", 0) > 0:
                cost_increase_pct = (
                    (latest.get("estimated_cost", 0) - previous["estimated_cost"])
                    / previous["estimated_cost"] * 100
                )
            reasons = []
            if score_drop >= settings["drift_score_drop"]:
                reasons.append(f"평균 점수 {score_drop:.1f}점 하락")
            if pass_drop >= settings["drift_pass_rate_drop"]:
                reasons.append(f"PASS율 {pass_drop:.1f}%p 하락")
            if latency_increase_pct >= settings["drift_latency_increase_pct"]:
                reasons.append(f"평균 지연 {latency_increase_pct:.1f}% 증가")
            if p95_increase_pct >= settings["drift_p95_increase_pct"]:
                reasons.append(f"P95 지연 {p95_increase_pct:.1f}% 증가")
            if cost_increase_pct >= settings["drift_cost_increase_pct"]:
                reasons.append(f"추정 비용 {cost_increase_pct:.1f}% 증가")
            if reasons:
                alerts.append({
                    "kind": key[0], "domain": key[1], "mode": key[2],
                    "total": key[3],
                    "latest_run_id": latest["run_id"],
                    "previous_run_id": previous["run_id"],
                    "severity": "critical" if pass_drop >= 10 or score_drop >= 8 else "warning",
                    "reasons": reasons,
                    "score_drop": round(score_drop, 2),
                    "pass_rate_drop": round(pass_drop, 2),
                    "latency_increase_pct": round(latency_increase_pct, 2),
                    "p95_increase_pct": round(p95_increase_pct, 2),
                    "cost_increase_pct": round(cost_increase_pct, 2),
                    "rate_limit_count": latest.get("rate_limit_count", 0),
                })
        return alerts[: max(1, min(limit, 100))]

    def dashboard(self) -> dict[str, Any]:
        sync = self.sync_reports()
        runs = self.list_runs(limit=100)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_runs: list[dict[str, Any]] = []
        for run in runs:
            try:
                generated_at = datetime.fromisoformat(str(run.get("generated_at") or "").replace("Z", "+00:00"))
                if generated_at.tzinfo is None:
                    generated_at = generated_at.replace(tzinfo=timezone.utc)
                if generated_at.astimezone(timezone.utc) >= seven_days_ago:
                    recent_runs.append(run)
            except ValueError:
                continue
        recent_total = sum(max(int(run.get("total") or 0), 0) for run in recent_runs)
        recent_passed = sum(max(int(run.get("passed") or 0), 0) for run in recent_runs)
        recent_durations = [
            float(run.get("average_duration_ms") or 0)
            for run in recent_runs if float(run.get("average_duration_ms") or 0) > 0
        ]
        recent_summary = {
            "window_days": 7,
            "run_count": len(recent_runs),
            "gate_pass_rate": round(recent_passed / recent_total * 100, 1) if recent_total else 0.0,
            "average_duration_ms": round(sum(recent_durations) / len(recent_durations), 1) if recent_durations else 0.0,
        }
        latest_by_kind: dict[str, dict[str, Any]] = {}
        for run in runs:
            latest_by_kind.setdefault(run["kind"], run)
        e2e_runs = [run for run in runs if run["kind"] == "e2e"][:20]
        latest = runs[0] if runs else None
        approvals = self.list_approvals(limit=20)
        latest_decisions: dict[str, str] = {}
        for approval in approvals:
            latest_decisions.setdefault(approval["run_id"], approval["decision"])
        pending_runs = [
            run for run in runs[:50]
            if latest_decisions.get(run["run_id"], "PENDING") == "PENDING"
        ]
        review_queue = self.review_queue(limit=50)
        drift_alerts = self.drift_alerts()
        rate_events = [
            event for event in self.list_audit_events(limit=100)
            if event["event_type"] == "API_RATE_LIMITED"
        ]
        if rate_events:
            drift_alerts.insert(0, {
                "kind": "runtime", "domain": "external-api", "mode": "live", "total": 0,
                "latest_run_id": "", "previous_run_id": "", "severity": "critical",
                "reasons": [f"웹 실행 중 HTTP 429 누적 {len(rate_events)}건"],
                "rate_limit_count": len(rate_events),
                "latest_event_at": rate_events[0]["created_at"],
            })
        return {
            "sync": sync,
            "run_count": len(runs),
            "recent_summary": recent_summary,
            "latest": latest,
            "latest_by_kind": latest_by_kind,
            "trends": [
                {
                    "run_id": run["run_id"],
                    "generated_at": run["generated_at"],
                    "domain": run["domain"],
                    "mode": run["mode"],
                    "score": run["average_score"],
                    "pass_rate": run["pass_rate"],
                    "duration_ms": run["average_duration_ms"],
                    "p95_duration_ms": run.get("p95_duration_ms", 0),
                    "cost": run.get("estimated_cost", 0),
                    "tokens": run.get("total_tokens", 0),
                    "rate_limit_count": run.get("rate_limit_count", 0),
                }
                for run in reversed(e2e_runs)
            ],
            "drift_alerts": drift_alerts,
            "pending_approval_count": len(review_queue),
            "pending_approvals": pending_runs[:10],
            "review_queue": review_queue,
            "approvals": approvals,
            "versions": self.version_history(limit=30),
            "settings": self.load_settings(),
        }


__all__ = [
    "ALLOWED_APPROVAL_DECISIONS",
    "DEFAULT_SETTINGS",
    "QAControlCenter",
]
