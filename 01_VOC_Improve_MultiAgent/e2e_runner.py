"""18개 JSONL 케이스를 공통 gRPC 파이프라인으로 실행하고 JSON/CSV 결과를 저장합니다."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import grpc

import grpc_server
import voc_pb2_grpc
from agents.critic import CriticAgent, CriticServicer
from agents.evaluator import EvaluatorAgent, EvaluatorServicer
from agents.improver import ImproverServicer, PolicyImproverAgent
from agents.interpreter import InterpreterServicer, NLInterpreterAgent
from agents.retriever import RetrieverAgent, RetrieverServicer
from agents.summarizer import SummarizerAgent, SummarizerServicer
from utils.fake_llm import (
    DeterministicEvaluatorLLM,
    DeterministicOpenAIClient,
    DeterministicPolicyLLM,
    DeterministicSummaryLLM,
)
from utils.deployment_policy import load_deployment_config, score_deployment_decision
from quality_diagnosis.evidence_report import write_execution_evidence
from utils.quality_evaluator import QUALITY_RUBRIC, evaluate_quality_case, validate_quality_case
from utils.settings import DEFAULT_CSV, MODEL_POLICY, MODEL_SUMMARY, TOTAL_TIMEOUT
from utils.experiment_version import capture_experiment


ROOT = Path(__file__).resolve().parent


def load_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [
            validate_quality_case(json.loads(line))
            for line in stream
            if line.strip() and not line.lstrip().startswith("#")
        ]


async def _start_server(register) -> tuple[grpc.aio.Server, str]:
    server = grpc.aio.server()
    register(server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return server, f"127.0.0.1:{port}"


async def start_offline_servers(cases: list[dict[str, Any]]) -> list[grpc.aio.Server]:
    client = DeterministicOpenAIClient(cases)
    definitions = [
        ("INTERPRETER_ENDPOINT", lambda s: voc_pb2_grpc.add_InterpreterServicer_to_server(
            InterpreterServicer(NLInterpreterAgent(client=client)), s)),
        ("RETRIEVER_ENDPOINT", lambda s: voc_pb2_grpc.add_RetrieverServicer_to_server(
            RetrieverServicer(RetrieverAgent()), s)),
        ("SUMMARIZER_ENDPOINT", lambda s: voc_pb2_grpc.add_SummarizerServicer_to_server(
            SummarizerServicer(SummarizerAgent(llm=DeterministicSummaryLLM(cases))), s)),
        ("EVALUATOR_ENDPOINT", lambda s: voc_pb2_grpc.add_EvaluatorServicer_to_server(
            EvaluatorServicer(EvaluatorAgent(llm=DeterministicEvaluatorLLM())), s)),
        ("CRITIC_ENDPOINT", lambda s: voc_pb2_grpc.add_CriticServicer_to_server(
            CriticServicer(CriticAgent(client=client)), s)),
    ]
    servers: list[grpc.aio.Server] = []
    for constant, register in definitions:
        server, endpoint = await _start_server(register)
        servers.append(server)
        setattr(grpc_server, constant, endpoint)

    policy_agent = PolicyImproverAgent(llm=DeterministicPolicyLLM())
    policy_agent.critic_endpoint = grpc_server.CRITIC_ENDPOINT
    server, endpoint = await _start_server(
        lambda s: voc_pb2_grpc.add_ImproverServicer_to_server(ImproverServicer(policy_agent), s)
    )
    servers.append(server)
    grpc_server.IMPROVER_ENDPOINT = endpoint
    return servers


def _summary(
    mode: str,
    rows: list[dict[str, Any]],
    domain: str,
    experiment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    passed = sum(bool(row["quality"]["passed"]) for row in rows)
    scores = [float(row["quality"]["score"]) for row in rows]
    dimensions = (
        "retrieval_relevance", "summary_faithfulness", "policy_actionability",
        "privacy_and_prompt_safety",
    )
    averages = {}
    for dimension in dimensions:
        values = [float(row["quality"]["checks"][dimension].get("ratio", 1.0)) * 100 for row in rows]
        averages[dimension] = round(sum(values) / len(values), 1) if values else 0.0
    rubric_averages = {}
    for key, (label, max_score) in QUALITY_RUBRIC.items():
        values = [float(row["quality"]["rubric"][key]["score"]) for row in rows]
        rubric_averages[key] = {
            "label": label,
            "average_score": round(sum(values) / len(values), 1) if values else 0.0,
            "max_score": max_score,
        }
    deployment_counts: dict[str, int] = {}
    for row in rows:
        code = str(row["quality"]["deployment"]["code"])
        deployment_counts[code] = deployment_counts.get(code, 0) + 1
    value = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "domain": domain,
        "mode": mode,
        "total": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "minimum_deployment_score": load_deployment_config()["minimum_score"],
        "dimension_averages": averages,
        "rubric_averages": rubric_averages,
        "deployment_counts": deployment_counts,
        "hard_blocked": sum(bool(row["quality"]["hard_blockers"]) for row in rows),
        "live_quality_verified": mode.startswith("live"),
        "models": {"summary": MODEL_SUMMARY, "policy": MODEL_POLICY} if mode == "live" else {"summary": "deterministic-fake", "policy": "deterministic-fake"},
    }
    if experiment:
        value["experiment"] = experiment
    return value


def save_results(
    mode: str, rows: list[dict[str, Any]], output_dir: Path, domain: str,
    experiment: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"{domain}_{mode}_e2e_{stamp}"
    summary = _summary(mode, rows, domain, experiment)
    minimum_score = load_deployment_config()["minimum_score"]
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    score_report_path = output_dir / f"{domain}_{mode}_quality_score_report_{stamp}.md"
    deployment_path = output_dir / f"{domain}_{mode}_deployment_decision_{stamp}.md"
    json_path.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "case_id", "passed", "score", "retrieval_relevance",
            "summary_faithfulness", "policy_actionability", "safety", "deployment",
            "hard_blockers", *QUALITY_RUBRIC.keys(), "total_duration_ms", "error_code",
        ])
        writer.writeheader()
        for row in rows:
            checks = row["quality"]["checks"]
            writer.writerow({
                "case_id": row["case_id"], "passed": row["quality"]["passed"],
                "score": row["quality"]["score"],
                "retrieval_relevance": checks["retrieval_relevance"].get("ratio"),
                "summary_faithfulness": checks["summary_faithfulness"].get("ratio"),
                "policy_actionability": checks["policy_actionability"].get("ratio"),
                "safety": checks["privacy_and_prompt_safety"].get("passed"),
                "deployment": row["quality"]["deployment"]["label"],
                "hard_blockers": "; ".join(row["quality"]["hard_blockers"]),
                **{
                    key: row["quality"]["rubric"][key]["score"]
                    for key in QUALITY_RUBRIC
                },
                "total_duration_ms": checks["performance"].get("duration_ms"),
                "error_code": row["analysis"].get("error_code"),
            })
    rubric_lines = [
        f"| {item['label']} | {item['average_score']} | {item['max_score']} |"
        for item in summary["rubric_averages"].values()
    ]
    score_report_path.write_text(
        "\n".join([
            f"# {domain} {mode} 품질 점수 보고서",
            "",
            f"- 생성 시각: {summary['generated_at']}",
            f"- 테스트: {summary['total']}건 (PASS {summary['passed']} / FAIL {summary['failed']})",
            f"- 평균 점수: **{summary['average_score']} / 100**",
            f"- 배포 기준 점수: **{minimum_score} / 100**",
            f"- 즉시 배포 보류: {summary['hard_blocked']}건",
            f"- 실제 LLM 품질 검증: {summary['live_quality_verified']}",
            "",
            "| 평가 항목 | 평균 획득점수 | 배점 |",
            "| --- | ---: | ---: |",
            *rubric_lines,
            "",
            "오프라인 결과는 결정적 테스트 대역을 사용한 회귀 기준이며 실제 LLM 품질 승인이 아닙니다.",
        ]),
        encoding="utf-8",
    )
    if mode != "live":
        decision = "기술적 파일럿 검증 통과 — 실제 LLM Judge 및 사람 검토 후 정식 승인 필요"
    else:
        blockers = ["E2E 실패 케이스"] if summary["failed"] else []
        if summary["hard_blocked"]:
            blockers.append("중대 안전 위반")
        decision = score_deployment_decision(
            summary["average_score"], blockers, minimum_score
        )["label"]
    deployment_path.write_text(
        "\n".join([
            f"# {domain} {mode} 배포 판단",
            "",
            f"## {decision}",
            "",
            f"- 평균 점수: {summary['average_score']} / 100",
            f"- 배포 기준 점수: {minimum_score} / 100",
            f"- 실패: {summary['failed']}건",
            f"- 즉시 보류: {summary['hard_blocked']}건",
            f"- 실제 LLM 품질 검증: {summary['live_quality_verified']}",
        ]),
        encoding="utf-8",
    )
    return json_path, csv_path, score_report_path, deployment_path


async def run(
    mode: str,
    cases_path: Path,
    output_dir: Path,
    csv_path: Path | str = DEFAULT_CSV,
    domain: str = "ecommerce",
    limit: int | None = None,
    case_ids: list[str] | None = None,
    concurrency: int = 1,
    progress_callback=None,
) -> dict[str, Any]:
    cases = load_cases(cases_path)
    if case_ids:
        requested = {value.strip() for value in case_ids if value.strip()}
        cases = [case for case in cases if case["case_id"] in requested]
        missing = requested - {case["case_id"] for case in cases}
        if missing:
            raise ValueError(f"존재하지 않는 case_id: {', '.join(sorted(missing))}")
    if limit is not None:
        if limit < 1:
            raise ValueError("limit은 1 이상이어야 합니다.")
        cases = cases[:limit]
    if not isinstance(concurrency, int) or not 1 <= concurrency <= 4:
        raise ValueError("concurrency는 1~4 사이여야 합니다.")
    models = (
        {"summary": MODEL_SUMMARY, "policy": MODEL_POLICY}
        if mode == "live" else {"summary": "deterministic-fake", "policy": "deterministic-fake"}
    )
    experiment = capture_experiment(
        root=ROOT,
        dataset_files=(Path(cases_path), Path(csv_path)),
        prompt_files=tuple(sorted((ROOT / "agents").glob("*.py"))) + (
            ROOT / "utils" / "quality_evaluator.py", ROOT / "e2e_runner.py",
        ),
        models=models,
        deployment_threshold=load_deployment_config()["minimum_score"],
        concurrency=concurrency,
    )
    endpoint_names = (
        "INTERPRETER_ENDPOINT", "RETRIEVER_ENDPOINT", "SUMMARIZER_ENDPOINT",
        "EVALUATOR_ENDPOINT", "CRITIC_ENDPOINT", "IMPROVER_ENDPOINT",
    )
    previous_endpoints = {
        name: getattr(grpc_server, name) for name in endpoint_names
    }
    servers: list[grpc.aio.Server] = []
    if mode == "offline":
        servers = await start_offline_servers(cases)
    runtime = grpc_server.VOCGRPCRuntime()
    semaphore = asyncio.Semaphore(concurrency)
    completed = 0
    progress_lock = asyncio.Lock()

    def notify(done: int, case_id: str, phase: str) -> None:
        if progress_callback:
            progress_callback(done, len(cases), case_id, phase)

    async def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
        nonlocal completed
        async with semaphore:
            notify(completed, str(case["case_id"]), "6-Agent 분석 중")
            analysis = await runtime.run_with_diagnostics(
                question=case["question"], csv_path=str(csv_path), timeout=TOTAL_TIMEOUT,
                task_override="both",
            )
            quality = evaluate_quality_case(case, analysis)
            result = {
                "case_id": case["case_id"],
                "question": case["question"],
                "quality": quality,
                "analysis": analysis,
            }
            async with progress_lock:
                completed += 1
                notify(completed, str(case["case_id"]), "품질 판정 완료")
            return result

    try:
        rows = await asyncio.gather(*(evaluate_case(case) for case in cases))
    finally:
        for server in reversed(servers):
            await server.stop(grace=0)
        if mode == "offline":
            for name, endpoint in previous_endpoints.items():
                setattr(grpc_server, name, endpoint)
    json_path, result_csv_path, score_report_path, deployment_path = save_results(
        mode, rows, output_dir, domain, experiment
    )
    summary = _summary(mode, rows, domain, experiment)
    evidence = write_execution_evidence(
        f"{domain}_{mode}_e2e",
        {"summary": summary, "results": rows},
        output_dir,
    )
    return {
        "summary": summary,
        "json": str(json_path),
        "csv": str(result_csv_path),
        "quality_score_report": str(score_report_path),
        "deployment_decision": str(deployment_path),
        "evidence": evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--cases", type=Path, default=ROOT / "test_cases.txt")
    parser.add_argument("--csv", type=Path, default=Path(DEFAULT_CSV))
    parser.add_argument("--domain", choices=("ecommerce", "insurance"), default="ecommerce")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "quality_diagnosis" / "reports")
    parser.add_argument("--limit", type=int, help="비용 확인용으로 앞에서 N개 케이스만 실행")
    parser.add_argument("--case-ids", nargs="+", help="재시험할 case_id 목록")
    parser.add_argument(
        "--concurrency", type=int, default=1, choices=range(1, 5),
        help="동시에 실행할 케이스 수(1~4, 라이브 권장값 2)",
    )
    args = parser.parse_args()
    if args.mode == "live" and not (os.environ.get("OPENAI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY")):
        parser.error("live 모드는 OPENAI_API_KEY와 ANTHROPIC_API_KEY가 필요합니다.")
    result = asyncio.run(
        run(
            args.mode, args.cases, args.output_dir, args.csv, args.domain,
            args.limit, args.case_ids, args.concurrency,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
