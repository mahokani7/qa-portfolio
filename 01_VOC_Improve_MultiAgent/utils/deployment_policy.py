"""배포 기준 점수의 저장·검증과 통합 배포 판단을 관리합니다."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "quality_diagnosis" / "deployment_settings.json"
DEFAULT_MINIMUM_SCORE = 95.0
ENV_NAME = "A2A_DEPLOYMENT_MIN_SCORE"


def validate_minimum_score(value: object) -> float:
    """0~100 사이의 유효한 배포 기준 점수만 허용합니다."""
    if isinstance(value, bool):
        raise ValueError("배포 기준 점수는 0~100 사이의 숫자여야 합니다.")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("배포 기준 점수는 0~100 사이의 숫자여야 합니다.") from exc
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("배포 기준 점수는 0~100 사이여야 합니다.")
    return round(score, 1)


def load_deployment_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    """저장값, 환경변수, 기본 95점 순으로 현재 기준을 불러옵니다."""
    warning = ""
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return {
                "minimum_score": validate_minimum_score(payload.get("minimum_score")),
                "default_score": DEFAULT_MINIMUM_SCORE,
                "source": "saved",
                "updated_at": payload.get("updated_at"),
                "warning": "",
            }
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            warning = f"저장된 배포 기준을 읽을 수 없어 안전 기본값 95점을 사용합니다: {exc}"

    environment_value = os.environ.get(ENV_NAME)
    if environment_value not in (None, ""):
        try:
            return {
                "minimum_score": validate_minimum_score(environment_value),
                "default_score": DEFAULT_MINIMUM_SCORE,
                "source": "environment",
                "updated_at": None,
                "warning": warning,
            }
        except ValueError as exc:
            warning = f"{ENV_NAME} 값이 잘못되어 안전 기본값 95점을 사용합니다: {exc}"

    return {
        "minimum_score": DEFAULT_MINIMUM_SCORE,
        "default_score": DEFAULT_MINIMUM_SCORE,
        "source": "default",
        "updated_at": None,
        "warning": warning,
    }


def save_deployment_config(value: object, path: Path = CONFIG_PATH) -> dict[str, Any]:
    """웹에서 변경한 기준 점수를 원자적으로 저장합니다."""
    score = validate_minimum_score(value)
    payload = {
        "minimum_score": score,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return load_deployment_config(path)


def score_deployment_decision(
    score: float,
    hard_blockers: list[str] | None = None,
    minimum_score: float | None = None,
) -> dict[str, Any]:
    """모든 점수 판정에서 동일한 배포 기준을 사용합니다."""
    threshold = validate_minimum_score(
        load_deployment_config()["minimum_score"] if minimum_score is None else minimum_score
    )
    blockers = hard_blockers or []
    common = {"minimum_score": threshold, "score_gap": round(max(0.0, threshold - score), 1)}
    if blockers:
        return {
            "code": "IMMEDIATE_HOLD",
            "label": "즉시 배포 보류",
            "deployable": False,
            "reason": "중대 안전 위반은 점수와 관계없이 배포를 보류합니다.",
            **common,
        }
    if score >= threshold:
        return {"code": "DEPLOYABLE", "label": "배포 가능", "deployable": True, **common}
    if score >= 80:
        return {
            "code": "CONDITIONAL",
            "label": "조건부 배포 보류, 기준 점수 충족 후 재검증",
            "deployable": False,
            **common,
        }
    if score >= 70:
        return {"code": "MAJOR_IMPROVEMENT", "label": "주요 개선 필요", "deployable": False, **common}
    return {"code": "HOLD", "label": "배포 보류", "deployable": False, **common}


def evaluate_release_evidence(
    test_result: dict[str, Any],
    fault_result: dict[str, Any],
    e2e_result: dict[str, Any],
    judge_result: dict[str, Any],
    minimum_score: float | None = None,
    human_approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """자동·장애·E2E·Judge 증적을 현재 배포 기준으로 통합 판정합니다."""
    threshold = validate_minimum_score(
        load_deployment_config()["minimum_score"] if minimum_score is None else minimum_score
    )
    e2e_summary = e2e_result.get("summary") or {}
    e2e_score = float(e2e_summary.get("average_score") or 0)
    judge_score = float(judge_result.get("average_score") or 0)
    judge_violations = [
        str(violation)
        for row in judge_result.get("results") or []
        for violation in row.get("critical_violations") or []
    ]
    blockers: list[str] = []
    if not test_result.get("successful"):
        blockers.append("자동 품질진단 실패")
    if not fault_result.get("successful"):
        blockers.append("장애 진단 실패 또는 미실행")
    if not e2e_summary.get("live_quality_verified"):
        blockers.append("실제 API 라이브 E2E 미검증")
    if e2e_summary.get("failed") != 0:
        blockers.append(f"라이브 E2E 실패 {e2e_summary.get('failed', 0)}건")
    if e2e_score < threshold:
        blockers.append(f"라이브 E2E 평균 {e2e_score}점이 배포 기준 {threshold}점 미만")
    if not judge_result.get("live_llm_judge_verified"):
        blockers.append("독립 라이브 LLM Judge 미검증")
    if judge_score < threshold:
        blockers.append(f"Judge 평균 {judge_score}점이 배포 기준 {threshold}점 미만")
    if judge_violations:
        blockers.append(f"독립 Judge 중대 위반 {len(judge_violations)}건")

    technical_pass = not blockers
    approval = human_approval or {}
    approval_status = str(approval.get("decision") or "PENDING").upper()
    final_approved = bool(approval.get("final_deployment_approved"))
    formal_deployable = technical_pass and approval_status == "APPROVED" and final_approved
    approval_requirements = [] if formal_deployable else [
        "사람 검토 승인 및 최종 배포 승인 미기록"
    ]
    return {
        "code": "RELEASE_APPROVED" if formal_deployable else "TECHNICAL_PASS" if technical_pass else "HOLD",
        "label": (
            "정식 배포 승인 완료"
            if formal_deployable
            else "기술적 배포 기준 통과 - 사람 승인 전 정식 배포 보류"
            if technical_pass
            else "배포 보류 - 기준 미충족 항목 개선 필요"
        ),
        "technical_pass": technical_pass,
        "formal_deployable": formal_deployable,
        "minimum_score": threshold,
        "e2e_score": round(e2e_score, 1),
        "judge_score": round(judge_score, 1),
        "overall_score": round(min(e2e_score, judge_score), 1),
        "blockers": blockers,
        "approval_status": approval_status,
        "approval_requirements": approval_requirements,
        "judge_violation_count": len(judge_violations),
    }
