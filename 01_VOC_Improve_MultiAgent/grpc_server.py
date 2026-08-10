# ================================================
# File: grpc_server.py
# Role: A2A VOC Orchestrator (gRPC 기반 클라이언트)
# ================================================

# ============ 표준 라이브러리 및 타입 힌트 ============
# Python 3.7+ 호환성을 위한 annotations 가져오기 (타입 힌트 지연 평가)
from __future__ import annotations
# 운영체제 관련 기능 (환경변수 읽기 등)
import os
# JSON 데이터 직렬화/역직렬화
import json
import socket
import time
# 타입 힌트를 위한 타입 정의들
from typing import Dict, Any, Optional, List
# gRPC 라이브러리 (비동기 클라이언트/서버 통신)
import grpc
# Protocol Buffers로 생성된 메시지 및 서비스 정의
import voc_pb2
import voc_pb2_grpc

# ============ 프로젝트 내부 모듈 임포트 ============
# settings.py에서 기본 CSV 경로를 불러오는 방식으로 통일
# 이렇게 하면 CSV 경로 설정이 한 곳에서 관리됩니다
from utils.settings import DEFAULT_CSV, STAGE_TIMEOUT, TOTAL_TIMEOUT
from utils.validation import (
    enforce_summary_grounding,
    is_multi_issue_question,
    needs_clarification,
    select_grounded_winner,
    select_valid_winner,
    validate_candidates,
    validate_csv_path,
    validate_filters,
    validate_max_items,
    validate_question,
    validate_task,
)


def _remaining_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("VOC 분석의 전체 제한 시간을 초과했습니다.")
    return min(remaining, STAGE_TIMEOUT)


def _remaining_total_timeout(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("VOC 분석의 전체 제한 시간을 초과했습니다.")
    return remaining


def _elapsed_ms(started_at: float) -> float:
    """성능 QA 보고서에 사용할 경과 시간을 밀리초 단위로 반환합니다."""
    return round((time.perf_counter() - started_at) * 1000, 2)


def is_endpoint_available(endpoint: str) -> bool:
    """gRPC 프로세스를 시작하기 전에 로컬 포트 충돌 여부를 확인합니다."""
    try:
        host, port_text = endpoint.rsplit(":", 1)
        port = int(port_text)
        host = host.strip("[]")
        if host == "localhost":
            host = "127.0.0.1"
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind((host, port))
        return True
    except (OSError, TypeError, ValueError):
        return False


def is_grpc_endpoint_ready(endpoint: str, timeout: float = 1.0) -> bool:
    """점유 중인 endpoint가 단순 TCP가 아니라 응답 가능한 gRPC 서버인지 확인합니다."""
    channel = grpc.insecure_channel(endpoint)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        return True
    except (grpc.FutureTimeoutError, OSError, ValueError):
        return False
    finally:
        channel.close()


def inspect_agent_startup_state(
    agents: list[tuple[str, str, str]],
) -> dict[str, Any]:
    """신규 기동 가능, 기존 전체 재사용, 일부 충돌 상태를 구분합니다."""
    occupied = [
        (name, endpoint) for name, _module, endpoint in agents
        if not is_endpoint_available(endpoint)
    ]
    if not occupied:
        return {"state": "available", "occupied": [], "grpc_ready": []}

    grpc_ready = [
        (name, endpoint) for name, endpoint in occupied
        if is_grpc_endpoint_ready(endpoint)
    ]
    state = (
        "already_running"
        if len(occupied) == len(agents) and len(grpc_ready) == len(agents)
        else "conflict"
    )
    return {"state": state, "occupied": occupied, "grpc_ready": grpc_ready}

# ============ gRPC 에이전트 엔드포인트 설정 ============
# 각 에이전트 서비스의 네트워크 주소를 환경변수에서 읽어옵니다
# 환경변수가 없으면 기본값(localhost)을 사용합니다
# 각 에이전트는 독립적인 포트에서 실행됩니다
INTERPRETER_ENDPOINT = os.environ.get("INTERPRETER_ENDPOINT", "localhost:6001")  # 자연어 질의 해석 서비스
RETRIEVER_ENDPOINT   = os.environ.get("RETRIEVER_ENDPOINT",   "localhost:6002")  # VOC 데이터 검색 서비스
SUMMARIZER_ENDPOINT  = os.environ.get("SUMMARIZER_ENDPOINT",  "localhost:6003")  # 요약 생성 서비스
EVALUATOR_ENDPOINT   = os.environ.get("EVALUATOR_ENDPOINT",   "localhost:6004")  # 요약 평가 서비스
CRITIC_ENDPOINT      = os.environ.get("CRITIC_ENDPOINT",      "localhost:6005")  # 요약/정책 비평 서비스
IMPROVER_ENDPOINT    = os.environ.get("IMPROVER_ENDPOINT",    "localhost:6006")  # 정책 개선안 생성 서비스


class VOCGRPCRuntime:
    """
    A2A VOC 전체 파이프라인 실행기
    MCP 서버에서 호출되는 인터페이스
    """

    # ============ 초기화 메서드 ============
    def __init__(self):
        # 각 에이전트는 모듈 상단의 INTERPRETER_ENDPOINT, SUMMARIZER_ENDPOINT 등 환경 변수 기반 상수를 사용합니다
        pass

    # ============ 자연어 기반 실행 메서드 ============
    # 사용자의 자연어 질의를 받아서 전체 VOC 분석 파이프라인을 실행합니다
    # 이 메서드는 Interpreter 에이전트를 먼저 호출하여 질의를 구조화된 파라미터로 변환합니다
    async def run_with_question(
        self,
        question: str,
        csv_path: Optional[str],
        timeout: float = TOTAL_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        자연어 질의를 받아 VOC 분석 파이프라인을 실행합니다.
        
        Args:
            question: 사용자의 자연어 질의 (예: "상담 대기 시간 관련 불만 분석")
            csv_path: VOC 데이터 CSV 파일 경로 (None이면 기본값 사용)
            timeout: 각 gRPC 호출의 타임아웃 시간(초)
            
        Returns:
            Dict: 분석 결과 (summary, policy, trace 등 포함)
        """

        return await self._execute_pipeline(
            question=question,
            csv_path=csv_path,
            timeout=timeout,
        )

    # ============ 파라미터 기반 실행 메서드 ============
    # 자연어 질의 없이 직접 파라미터를 지정하여 VOC 분석을 수행합니다
    # 이 메서드는 Interpreter를 거치지 않고 바로 파이프라인을 실행합니다
    async def run_with_params(
        self,
        filters: Optional[List[str]],
        task: str,
        max_items: int,
        csv_path: str,
        timeout: float = TOTAL_TIMEOUT
    ) -> Dict[str, Any]:
        """
        직접 파라미터를 지정하여 VOC 분석 파이프라인을 실행합니다.
        
        Args:
            filters: 필터링할 키워드 리스트 (None이면 필터링 없음)
            task: 수행할 작업 ("summary", "policy", "both")
            max_items: 분석할 최대 VOC 개수
            csv_path: VOC 데이터 CSV 파일 경로
            timeout: 각 gRPC 호출의 타임아웃 시간(초)
            
        Returns:
            Dict: 분석 결과 (summary, policy, trace 등 포함)
        """

        final_csv = validate_csv_path(csv_path or DEFAULT_CSV)
        intent = {
            "task": validate_task(task),
            "filters": validate_filters(filters),
            "max_items": validate_max_items(max_items),
            "csv_path": final_csv,
        }
        return await self._execute_pipeline(
            question="",
            csv_path=final_csv,
            timeout=timeout,
            intent_override=intent,
        )

    # ============ 단계별 진단(QA) 실행 메서드 ============
    # 최종 답변만이 아니라 6개 에이전트의 각 단계 산출물을 수집합니다.
    # 리팩터링으로 각 servicer가 "순수 함수"가 되었기에, 여기서 단계를 하나씩
    # 직접 호출하여 중간 결과(intent, 검색결과, 후보, 평가, 비평, 정책)를 모두
    # 관찰할 수 있습니다. (내부 품질 진단용)
    async def _execute_pipeline(
        self,
        question: str,
        csv_path: Optional[str],
        timeout: float = TOTAL_TIMEOUT,
        task_override: Optional[str] = None,
        intent_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        VOC 파이프라인을 단계별로 실행하며 각 에이전트의 출력을 수집해 반환합니다.

        Returns:
            Dict: {
              "ok": bool,
              "question": str,
              "stages": [ {agent, role, check, output}, ... ],  # 6개 에이전트 단계
              "summary": str,   # 최종 요약
              "policy": str,    # 최종 정책 개선안
            }
        """
        question = validate_question(question) if intent_override is None else (question or "")
        final_csv = validate_csv_path(csv_path or DEFAULT_CSV)
        pipeline_started = time.perf_counter()
        deadline = time.monotonic() + min(float(timeout), TOTAL_TIMEOUT)
        stages: List[Dict[str, Any]] = []

        if intent_override is None and needs_clarification(question):
            summary = (
                "장애 대상과 증상이 불명확하여 원인을 판단할 수 없습니다. "
                "안전한 재현과 분석을 위해 추가 정보가 필요합니다."
            )
            policy = (
                "추가 정보 요청: 개인정보를 제외하고 문제가 발생한 대상 기능, 관찰된 증상, "
                "발생 시점과 재현 절차를 알려주세요. 확인 전에는 원인을 단정하지 않습니다."
            )
            stages.append({
                "agent": "Interpreter",
                "role": "질문 명확성 판정",
                "check": "대상과 증상이 분석 가능한 수준인지",
                "duration_ms": _elapsed_ms(pipeline_started),
                "output": {"clarification_required": True, "source": "deterministic_guard"},
            })
            return {
                "ok": True,
                "error_code": None,
                "message": "clarification_required",
                "question": question,
                "stages": stages,
                "summary": summary,
                "policy": policy,
                "trace": "Interpreter",
                "metrics": {
                    "total_duration_ms": _elapsed_ms(pipeline_started),
                    "stage_duration_ms": {"Interpreter": stages[0]["duration_ms"]},
                },
            }

        # ---------- 1) Interpreter: 질문 의도·검색 조건 해석 ----------
        stage_started = time.perf_counter()
        if intent_override is None:
            async with grpc.aio.insecure_channel(INTERPRETER_ENDPOINT) as ch:
                stub = voc_pb2_grpc.InterpreterStub(ch)
                ires = await stub.ParseQuestion(
                    voc_pb2.ParseQuestionReq(question=question, default_csv=final_csv),
                    timeout=_remaining_timeout(deadline),
                )
            task = validate_task(task_override or ires.task or "both")
            filters = validate_filters(list(ires.filters))
            max_items = validate_max_items(ires.max_items or 30)
            csv_path2 = validate_csv_path(ires.csv_path or final_csv)
        else:
            task = validate_task(task_override or intent_override.get("task"))
            filters = validate_filters(intent_override.get("filters"))
            max_items = validate_max_items(intent_override.get("max_items"))
            csv_path2 = validate_csv_path(str(intent_override.get("csv_path") or final_csv))
        stages.append({
            "agent": "Interpreter",
            "role": "질문 의도·검색 조건 해석",
            "check": "의도, 키워드, 카테고리 해석 정확성",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {
                "task": task,
                "filters": filters,
                "max_items": max_items,
                "csv_path": csv_path2,
                "source": "provided" if intent_override is not None else "llm",
            },
        })

        # ---------- 2) Retriever: VOC 데이터 검색 ----------
        stage_started = time.perf_counter()
        async with grpc.aio.insecure_channel(RETRIEVER_ENDPOINT) as ch:
            stub = voc_pb2_grpc.RetrieverStub(ch)
            rres = await stub.Retrieve(
                voc_pb2.RetrieveReq(csv_path=csv_path2, filters=filters, max_items=max_items),
                timeout=_remaining_timeout(deadline),
            )
        texts = list(rres.texts)
        stages.append({
            "agent": "Retriever",
            "role": "VOC 데이터 검색",
            "check": "관련 불만을 빠뜨리지 않고 찾는지",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {"retrieved_count": len(texts), "samples": texts[:10]},
        })

        # 검색 결과가 없으면 이후 단계는 진행 불가 → 현재까지의 단계만 반환
        if not texts:
            no_match_message = (
                "검색된 VOC가 없어 요약과 정책을 생성하지 않았습니다. "
                "검색어와 데이터 범위를 확인한 뒤 다시 시도하고, 개인정보 삭제처럼 VOC 분석 범위 밖의 요청은 "
                "개인정보를 이 화면에 입력하지 말고 실제 공식 개인정보 처리 요청 채널을 이용하세요."
            )
            return {
                "ok": False,
                "error_code": "NO_MATCHING_VOC",
                "message": no_match_message,
                "question": question,
                "stages": stages,
                "summary": "",
                "policy": "",
                "note": no_match_message,
                "trace": "; ".join(stage["agent"] for stage in stages),
                "metrics": {
                    "total_duration_ms": _elapsed_ms(pipeline_started),
                    "stage_duration_ms": {
                        stage["agent"]: stage["duration_ms"] for stage in stages
                    },
                },
            }

        # ---------- 3) Summarizer: 검색 결과 요약(후보 생성) ----------
        stage_started = time.perf_counter()
        async with grpc.aio.insecure_channel(SUMMARIZER_ENDPOINT) as ch:
            stub = voc_pb2_grpc.SummarizerStub(ch)
            sres = await stub.MakeCandidates(
                voc_pb2.SummarizeReq(texts=texts, max_items=max_items, n=3, question=question),
                timeout=_remaining_timeout(deadline),
            )
        candidates = validate_candidates(dict(sres.candidates))
        stages.append({
            "agent": "Summarizer",
            "role": "검색 결과 요약",
            "check": "원문 왜곡, 핵심 누락, 중복 여부",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {"candidates": candidates},
        })

        # ---------- 4) Evaluator: 요약 후보 평가 ----------
        stage_started = time.perf_counter()
        async with grpc.aio.insecure_channel(EVALUATOR_ENDPOINT) as ch:
            stub = voc_pb2_grpc.EvaluatorStub(ch)
            eres = await stub.Evaluate(
                voc_pb2.EvaluateReq(
                    task=task,
                    candidates=candidates,
                    question=question,
                    source_texts=texts[:10],
                ),
                timeout=_remaining_timeout(deadline),
            )
        try:
            scores = json.loads(eres.scores_json or "{}")
        except Exception:
            scores = {}
        llm_winner = select_valid_winner(candidates, eres.winner, scores)
        winner, relevance_scores, grounding_override = select_grounded_winner(
            candidates, llm_winner, question, texts
        )
        summary = candidates[winner]
        summary, summary_grounding_fallback, summary_grounding_precision = enforce_summary_grounding(
            summary, question, texts
        )
        stages.append({
            "agent": "Evaluator",
            "role": "요약·결과 평가",
            "check": "평가 기준이 일관적인지",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {
                "winner": winner,
                "llm_winner": llm_winner,
                "scores": scores,
                "relevance_scores": relevance_scores,
                "grounding_override": grounding_override,
                "summary_grounding_fallback": summary_grounding_fallback,
                "summary_grounding_precision": summary_grounding_precision,
                "selected_summary": summary,
            },
        })

        # ---------- 5) Critic: 위험·한계 지적 (요약 검토) ----------
        stage_started = time.perf_counter()
        async with grpc.aio.insecure_channel(CRITIC_ENDPOINT) as ch:
            stub = voc_pb2_grpc.CriticStub(ch)
            cres = await stub.Review(
                voc_pb2.ReviewReq(
                    doc=(
                        f"[사용자 질문]\n{question}\n\n"
                        f"[검색된 원본 VOC]\n" + "\n".join(f"- {text}" for text in texts[:5])
                        + f"\n\n[검토할 요약]\n{summary}"
                    ),
                    role="summary",
                ),
                timeout=_remaining_timeout(deadline),
            )
        need_refine = bool(cres.need_refine)
        edits = list(cres.edits)
        stages.append({
            "agent": "Critic",
            "role": "위험·한계 지적",
            "check": "실제 문제와 리스크를 찾는지",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {"need_refine": need_refine, "edits": edits, "ask_more_samples": bool(cres.ask_more_samples)},
        })

        # 필요 시 요약 개선 (Critic 지적 반영)
        pre_refine_summary = summary
        if need_refine and edits:
            refine_started = time.perf_counter()
            async with grpc.aio.insecure_channel(SUMMARIZER_ENDPOINT) as ch:
                stub = voc_pb2_grpc.SummarizerStub(ch)
                fres = await stub.Refine(
                    voc_pb2.RefineReq(
                        draft=summary,
                        edits_json=json.dumps(
                            {"edits": edits, "question": question, "source_voc": texts[:5]},
                            ensure_ascii=False,
                        ),
                    ),
                    timeout=_remaining_timeout(deadline),
                )
            summary = fres.text or summary
            stages[2]["output"]["refine_duration_ms"] = _elapsed_ms(refine_started)

        summary, post_refine_fallback, post_refine_precision = enforce_summary_grounding(
            summary, question, texts
        )
        if is_multi_issue_question(question):
            grounded_cases = "\n".join(f"- {text}" for text in texts[:10])
            summary = (
                f"복합 장애 문의로 다음 문제가 함께 제기되었습니다: {question}\n"
                f"검색 원문에서 확인된 관련 사례:\n{grounded_cases}"
            )
        stages[2]["output"]["post_refine_grounding_fallback"] = post_refine_fallback
        stages[2]["output"]["post_refine_grounding_precision"] = post_refine_precision
        stages[2]["output"]["pre_refine_summary"] = pre_refine_summary
        stages[2]["output"]["post_refine_summary"] = summary
        stages[2]["output"]["refined"] = bool(need_refine and edits)

        # ---------- 6) Improver: 정책 개선안 제안 ----------
        policy = ""
        stage_started = time.perf_counter()
        if task in ("policy", "both"):
            async with grpc.aio.insecure_channel(IMPROVER_ENDPOINT) as ch:
                stub = voc_pb2_grpc.ImproverStub(ch)
                pres = await stub.Improve(
                    voc_pb2.PolicyReq(summary=summary, question=question),
                    timeout=_remaining_timeout(deadline),
                )
            policy = pres.policy or ""
        stages.append({
            "agent": "Improver",
            "role": "정책 개선안 제안",
            "check": "개선안이 구체적이고 실행 가능한지",
            "duration_ms": _elapsed_ms(stage_started),
            "output": {"policy": policy, "skipped": task not in ("policy", "both")},
        })

        return {
            "ok": True,
            "error_code": None,
            "message": "success",
            "question": question,
            "stages": stages,
            "summary": summary,
            "policy": policy,
            "intent_json": json.dumps(
                {"task": task, "filters": filters, "max_items": max_items, "csv_path": csv_path2},
                ensure_ascii=False,
            ),
            "eval_json": json.dumps(scores, ensure_ascii=False),
            "summary_critic_json": json.dumps(
                {"need_refine": need_refine, "edits": edits}, ensure_ascii=False
            ),
            "trace": "; ".join(stage["agent"] for stage in stages),
            "metrics": {
                "total_duration_ms": _elapsed_ms(pipeline_started),
                "stage_duration_ms": {
                    stage["agent"]: stage["duration_ms"] for stage in stages
                },
            },
        }

    async def run_with_diagnostics(
        self,
        question: str,
        csv_path: Optional[str],
        timeout: float = TOTAL_TIMEOUT,
        task_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """일반 실행과 동일한 공통 파이프라인을 사용하며 단계 산출물도 반환합니다."""
        return await self._execute_pipeline(
            question=question,
            csv_path=csv_path,
            timeout=timeout,
            task_override=task_override,
        )


# ================================================================
# 통합 실행 관리자 (Process Supervisor)
# ================================================================
# `python grpc_server.py` 로 실행하면, 이 블록이 6개 에이전트를 각각 별도의
# 프로세스(python -m agents.XXX)로 기동하고, 각 포트의 준비 상태를 확인한 뒤,
# Ctrl+C 를 누를 때까지 유지하는 "통합 실행 관리자" 로 동작합니다.
#
# 위의 VOCGRPCRuntime 클래스는 MCP 도구가 사용하는 "오케스트레이터"이며,
# 이 __main__ 블록은 직접 실행할 때만 동작하므로 서로 간섭하지 않습니다.
#
# 사용법:
#   1) API 키 설정 (환경변수 또는 프로젝트 루트의 .env)
#   2) python grpc_server.py     → 6개 에이전트 동시 기동
#   3) (별도 터미널) python main.py  → MCP 서버 실행
if __name__ == "__main__":
    import sys
    import time
    import logging
    import subprocess

    # ============ .env 로드 (선택) ============
    # python-dotenv가 있으면 .env를 읽어 환경변수로 주입합니다.
    # subprocess는 부모의 환경변수를 상속하므로, 자식 에이전트도 API 키를 받습니다.
    ROOT = os.path.dirname(os.path.abspath(__file__))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, ".env"))
        load_dotenv(os.path.join(os.path.dirname(ROOT), ".env"))
    except Exception:
        pass

    # ============ 로깅 설정 ============
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    log = logging.getLogger("__main__")

    # ============ 에이전트 정의 ============
    # (표시 이름, 실행 모듈, 준비 확인용 host:port)
    AGENTS = [
        ("Interpreter", "agents.interpreter", os.environ.get("INTERPRETER_BIND", "127.0.0.1:6001")),
        ("Retriever",   "agents.retriever",   os.environ.get("RETRIEVER_BIND", "127.0.0.1:6002")),
        ("Summarizer",  "agents.summarizer",  os.environ.get("SUMMARIZER_BIND", "127.0.0.1:6003")),
        ("Evaluator",   "agents.evaluator",   os.environ.get("EVALUATOR_BIND", "127.0.0.1:6004")),
        ("Critic",      "agents.critic",      os.environ.get("CRITIC_BIND", "127.0.0.1:6005")),
        ("Improver",    "agents.improver",    os.environ.get("IMPROVER_BIND", "127.0.0.1:6006")),
    ]

    def wait_ready(endpoint: str, timeout: float = 30.0) -> bool:
        """해당 host:port에 TCP 연결이 될 때까지(=서버가 뜰 때까지) 대기합니다."""
        host, port_s = endpoint.split(":")
        port = int(port_s)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection((host, port), timeout=1.0):
                    return True
            except OSError:
                time.sleep(0.3)
        return False

    procs = []  # (name, Popen) 목록

    def cleanup():
        """모든 자식 에이전트 프로세스를 정상 종료합니다."""
        for name, p in procs:
            if p.poll() is None:
                p.terminate()
        for name, p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()
            log.info(f"{name} 종료")

    # ============ 1) 6개 에이전트 프로세스 기동 ============
    startup_state = inspect_agent_startup_state(AGENTS)
    if startup_state["state"] == "already_running":
        running_agents = [
            f"{name}({endpoint})" for name, endpoint in startup_state["grpc_ready"]
        ]
        log.info("6개 VOC gRPC 에이전트가 이미 정상 실행 중입니다: %s", ", ".join(running_agents))
        log.info("중복 기동을 건너뜁니다. 현재 에이전트를 그대로 재사용하세요.")
        log.info("웹 화면은 별도 터미널에서 python web_app.py 실행 후 http://127.0.0.1:8000 에 접속합니다.")
        sys.exit(0)
    if startup_state["state"] == "conflict":
        busy_agents = [
            f"{name}({endpoint})" for name, endpoint in startup_state["occupied"]
        ]
        ready_names = {name for name, _endpoint in startup_state["grpc_ready"]}
        unhealthy = [name for name, _endpoint in startup_state["occupied"] if name not in ready_names]
        log.error("일부 포트가 사용 중이어서 안전하게 시작할 수 없습니다: %s", ", ".join(busy_agents))
        if unhealthy:
            log.error("gRPC 준비 확인 실패: %s", ", ".join(unhealthy))
        log.error("부분 실행 프로세스를 종료하거나 포트 설정을 변경한 뒤 다시 실행하세요.")
        sys.exit(1)

    log.info("6개 VOC gRPC 에이전트 시작을 요청합니다.")
    for name, module, endpoint in AGENTS:
        cmd = [sys.executable, "-m", module]
        log.info(f"{name} 시작 | command={sys.executable} -m {module} | endpoint={endpoint}")
        procs.append((name, subprocess.Popen(cmd, cwd=ROOT)))

    # ============ 2) 준비 상태 확인 ============
    all_ready = True
    for name, module, endpoint in AGENTS:
        if wait_ready(endpoint):
            log.info(f"{name} 준비 완료 | endpoint={endpoint}")
        else:
            all_ready = False
            log.error(f"{name} 준비 실패(시간 초과) | endpoint={endpoint}")

    if not all_ready:
        log.error("일부 에이전트가 준비되지 않아 전체를 종료합니다. (API 키/포트 충돌을 확인하세요)")
        cleanup()
        sys.exit(1)

    log.info("6개 VOC gRPC 에이전트가 모두 준비되었습니다.")
    log.info("통합 gRPC 실행 관리자가 동작 중입니다. 종료하려면 Ctrl+C를 누르세요.")

    # ============ 3) 감시 루프 (Ctrl+C 까지 유지) ============
    try:
        while True:
            time.sleep(1.0)
            # 자식 프로세스가 예기치 않게 죽으면 전체를 정리하고 종료
            dead = [(n, p) for n, p in procs if p.poll() is not None]
            if dead:
                for n, p in dead:
                    log.error(f"{n} 프로세스가 예기치 않게 종료됨 (exit={p.returncode}).")
                log.error("남은 에이전트를 정리하고 종료합니다.")
                break
    except KeyboardInterrupt:
        log.info("Ctrl+C 감지 — 종료합니다.")
    finally:
        cleanup()

