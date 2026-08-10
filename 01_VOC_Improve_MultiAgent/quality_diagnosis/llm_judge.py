"""내부 Evaluator/Critic과 분리된 최종 결과 Judge 실행기."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


QUALITY_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = QUALITY_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quality_diagnosis.judge_prompt import build_judge_prompt
from quality_diagnosis.evidence_report import write_execution_evidence
from utils.deployment_policy import load_deployment_config, score_deployment_decision
from utils.json_utils import extract_json
from utils.settings import MODEL_POLICY, MODEL_SUMMARY, claude_client, openai_client


class JudgeClient(Protocol):
    async def __call__(self, prompt: str) -> str: ...


class OpenAIJudgeClient:
    def __init__(self) -> None:
        self.last_usage: dict[str, Any] = {}

    async def __call__(self, prompt: str) -> str:
        if openai_client is None:
            raise RuntimeError("OPENAI_API_KEY가 없어 OpenAI Judge를 실행할 수 없습니다.")
        response = await openai_client.chat.completions.create(
            model=os.environ.get("A2A_JUDGE_MODEL", MODEL_SUMMARY),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        usage = getattr(response, "usage", None)
        self.last_usage = {
            "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "exact": usage is not None,
        }
        return response.choices[0].message.content or ""


class AnthropicJudgeClient:
    def __init__(self) -> None:
        self.last_usage: dict[str, Any] = {}

    async def __call__(self, prompt: str) -> str:
        if claude_client is None:
            raise RuntimeError("ANTHROPIC_API_KEY가 없어 Anthropic Judge를 실행할 수 없습니다.")
        response = await claude_client.messages.create(
            model=os.environ.get("A2A_JUDGE_MODEL", MODEL_POLICY),
            max_tokens=1600,
            messages=[{"role": "user", "content": prompt}],
        )
        usage = getattr(response, "usage", None)
        self.last_usage = {
            "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
            "exact": usage is not None,
        }
        return "".join(getattr(block, "text", "") for block in response.content)


class DeterministicJudgeClient:
    """형식과 보고서 경로 검증 전용이며 실제 LLM Judge로 간주하지 않습니다."""

    async def __call__(self, _prompt: str) -> str:
        self.last_usage = {
            "input_tokens": max(1, len(_prompt) // 4),
            "output_tokens": 90,
            "exact": False,
        }
        return json.dumps({
            "scores": {
                "accuracy": 23,
                "summary_faithfulness": 18,
                "policy_specificity": 18,
                "usefulness": 18,
                "safety": 15,
            },
            "critical_violations": [],
            "rationale": {
                "accuracy": "오프라인 형식 검증",
                "summary_faithfulness": "오프라인 형식 검증",
                "policy_specificity": "오프라인 형식 검증",
                "usefulness": "오프라인 형식 검증",
                "safety": "오프라인 형식 검증",
            },
        }, ensure_ascii=False)


def load_rubric(path: Path = QUALITY_ROOT / "judge_rubric.json") -> dict[str, Any]:
    rubric = json.loads(path.read_text(encoding="utf-8"))
    if sum(int(item["max_score"]) for item in rubric.values()) != 100:
        raise ValueError("Judge 배점 합계는 100점이어야 합니다.")
    return rubric


def normalize_judgment(
    raw: str,
    rubric: dict[str, Any],
    minimum_deployment_score: float | None = None,
) -> dict[str, Any]:
    payload = extract_json(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("scores"), dict):
        raise ValueError("Judge 응답에서 scores JSON 객체를 찾을 수 없습니다.")
    scores = {}
    for key, config in rubric.items():
        maximum = int(config["max_score"])
        try:
            value = float(payload["scores"].get(key, 0))
        except (TypeError, ValueError):
            value = 0
        scores[key] = round(max(0.0, min(float(maximum), value)), 1)
    violations = [str(item).strip() for item in payload.get("critical_violations") or [] if str(item).strip()]
    total = round(sum(scores.values()), 1)
    deployment = score_deployment_decision(total, violations, minimum_deployment_score)
    return {
        "scores": scores,
        "total_score": total,
        "critical_violations": violations,
        "decision": deployment["label"],
        "deployment": deployment,
        "rationale": payload.get("rationale") if isinstance(payload.get("rationale"), dict) else {},
    }


async def judge_one(
    row: dict[str, Any], client: JudgeClient, rubric: dict[str, Any], focus: str = "",
) -> dict[str, Any]:
    analysis = row.get("analysis") or {}
    retriever = next(
        (stage.get("output") or {} for stage in analysis.get("stages") or [] if stage.get("agent") == "Retriever"),
        {},
    )
    prompt = build_judge_prompt(
        question=str(row.get("question") or analysis.get("question") or ""),
        sources=[str(item) for item in retriever.get("samples") or []],
        summary=str(
            analysis.get("summary")
            or analysis.get("message")
            or analysis.get("note")
            or ""
        ),
        policy=str(analysis.get("policy") or ""),
        rubric=rubric,
        focus=focus,
    )
    judgment = normalize_judgment(await client(prompt), rubric)
    return {
        "case_id": row.get("case_id"), **judgment,
        "usage": getattr(client, "last_usage", {
            "input_tokens": max(1, len(prompt) // 4), "output_tokens": 0, "exact": False,
        }),
    }


def _latest_e2e_report() -> Path:
    reports = sorted((QUALITY_ROOT / "reports").glob("*offline_e2e_*.json"))
    if not reports:
        raise FileNotFoundError("먼저 e2e_runner.py --mode offline을 실행하세요.")
    return reports[-1]


async def run(
    provider: str,
    input_path: Path,
    output_dir: Path,
    *,
    include_all: bool = False,
) -> dict[str, Any]:
    report = json.loads(input_path.read_text(encoding="utf-8"))
    rubric = load_rubric()
    focus_cases = {
        item["case_id"]: item.get("focus", "")
        for item in json.loads((QUALITY_ROOT / "judge_cases.json").read_text(encoding="utf-8"))
    }
    selected = [
        row for row in report.get("results") or []
        if include_all or row.get("case_id") in focus_cases
    ]
    clients: dict[str, JudgeClient] = {
        "deterministic": DeterministicJudgeClient(),
        "openai": OpenAIJudgeClient(),
        "anthropic": AnthropicJudgeClient(),
    }
    results = [
        await judge_one(row, clients[provider], rubric, focus_cases.get(str(row["case_id"]), ""))
        for row in selected
    ]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"llm_judge_{provider}_{stamp}.json"
    csv_path = output_dir / f"llm_judge_{provider}_{stamp}.csv"
    average = round(sum(row["total_score"] for row in results) / len(results), 1) if results else 0.0
    source_experiment = (
        (report.get("summary") or {}).get("experiment")
        if isinstance(report.get("summary"), dict) else {}
    ) or {}
    if not isinstance(source_experiment, dict):
        source_experiment = {}
    judge_model = (
        "deterministic-judge"
        if provider == "deterministic"
        else os.environ.get("A2A_JUDGE_MODEL", MODEL_SUMMARY if provider == "openai" else MODEL_POLICY)
    )
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": provider,
        "minimum_deployment_score": load_deployment_config()["minimum_score"],
        "live_llm_judge_verified": provider != "deterministic",
        "source_report": str(input_path),
        "model": judge_model,
        "experiment": {
            **source_experiment,
            "models": {**(source_experiment.get("models") or {}), "judge": judge_model},
            "deployment_threshold": load_deployment_config()["minimum_score"],
        },
        "average_score": average,
        "results": results,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "case_id", *rubric.keys(), "total_score", "decision", "critical_violations",
        ])
        writer.writeheader()
        for row in results:
            writer.writerow({
                "case_id": row["case_id"],
                **row["scores"],
                "total_score": row["total_score"],
                "decision": row["decision"],
                "critical_violations": "; ".join(row["critical_violations"]),
            })
    evidence = write_execution_evidence(f"llm_judge_{provider}", payload, output_dir)
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "evidence": evidence,
        **{key: payload[key] for key in ("provider", "live_llm_judge_verified", "average_score")},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("deterministic", "openai", "anthropic"), default="deterministic")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=QUALITY_ROOT / "reports")
    args = parser.parse_args()
    result = asyncio.run(run(args.provider, args.input or _latest_e2e_report(), args.output_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
