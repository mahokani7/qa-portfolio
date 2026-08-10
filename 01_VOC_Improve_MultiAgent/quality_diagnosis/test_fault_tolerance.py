"""교수님 요구사항 7번: 멀티 Agent 장애·예외 처리 자동 진단.

표준 unittest로 바로 실행할 수 있고, pytest가 설치된 환경에서도 수집됩니다.
"""

from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import grpc

from agents.interpreter import NLInterpreterAgent
from grpc_server import VOCGRPCRuntime, inspect_agent_startup_state, is_endpoint_available
from quality_diagnosis.qa_test_utils import (
    EmptyRetrieverAgent,
    RejectedAPIClient,
    SlowRetrieverAgent,
    start_retriever_server,
    unused_endpoint,
)
from utils.settings import DEFAULT_CSV
from utils.validation import ValidationError, validate_csv_path


class SynchronousFaultTests(unittest.TestCase):
    def test_all_ready_existing_agents_are_reused(self):
        """6개 포트가 모두 정상 gRPC이면 충돌 오류가 아니라 재사용 상태여야 합니다."""
        agents = [
            (f"Agent{index}", f"agents.agent{index}", f"127.0.0.1:{6100 + index}")
            for index in range(6)
        ]
        with (
            patch("grpc_server.is_endpoint_available", return_value=False),
            patch("grpc_server.is_grpc_endpoint_ready", return_value=True),
        ):
            result = inspect_agent_startup_state(agents)
        self.assertEqual(result["state"], "already_running")
        self.assertEqual(len(result["grpc_ready"]), 6)

    def test_partial_port_occupation_remains_a_conflict(self):
        """일부 Agent만 남은 상태는 정상 재사용으로 오인하면 안 됩니다."""
        agents = [
            ("Interpreter", "agents.interpreter", "127.0.0.1:6001"),
            ("Retriever", "agents.retriever", "127.0.0.1:6002"),
        ]
        with (
            patch(
                "grpc_server.is_endpoint_available",
                side_effect=lambda endpoint: endpoint.endswith(":6002"),
            ),
            patch("grpc_server.is_grpc_endpoint_ready", return_value=True),
        ):
            result = inspect_agent_startup_state(agents)
        self.assertEqual(result["state"], "conflict")
        self.assertEqual(result["occupied"], [("Interpreter", "127.0.0.1:6001")])

    def test_port_collision_is_detected_before_process_start(self):
        """동일 포트를 이미 사용 중이면 실행 관리자 사전 점검에서 탐지해야 합니다."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            occupied.bind(("127.0.0.1", 0))
            occupied.listen(1)
            endpoint = f"127.0.0.1:{occupied.getsockname()[1]}"
            self.assertFalse(is_endpoint_available(endpoint))

    def test_missing_csv_returns_explicit_file_error(self):
        """CSV가 없으면 파일 오류가 경로와 함께 명확히 드러나야 합니다."""
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing_voc.csv"
            with patch.dict(os.environ, {"A2A_ALLOWED_CSV_DIRS": directory}):
                with self.assertRaisesRegex(ValidationError, "CSV 파일을 찾을 수 없습니다"):
                    validate_csv_path(str(missing))

    def test_missing_api_key_is_not_hidden(self):
        """API 키 미설정은 일반 성공이나 모호한 오류로 처리하면 안 됩니다."""
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
            NLInterpreterAgent(client=None)


class AsynchronousFaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_api_key_error_is_preserved(self):
        """외부 API가 인증을 거부하면 원인 문자열을 숨기지 않아야 합니다."""
        agent = NLInterpreterAgent(client=RejectedAPIClient())
        with self.assertRaisesRegex(RuntimeError, "invalid_api_key"):
            await agent.parse("결제 관련 VOC를 분석해 주세요.", DEFAULT_CSV)

    async def test_retriever_shutdown_reports_connection_failure(self):
        """Retriever가 꺼져 있으면 성공으로 위장하지 않고 gRPC 오류를 반환해야 합니다."""
        with patch("grpc_server.RETRIEVER_ENDPOINT", unused_endpoint()):
            with self.assertRaises(grpc.aio.AioRpcError) as caught:
                await VOCGRPCRuntime().run_with_params(
                    filters=["결제"], task="both", max_items=10,
                    csv_path=DEFAULT_CSV, timeout=0.3,
                )
        self.assertIn(
            caught.exception.code(),
            {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED},
        )

    async def test_slow_agent_returns_deadline_exceeded(self):
        """Agent 응답 지연은 무한 대기하지 않고 제한 시간 오류가 되어야 합니다."""
        server, endpoint = await start_retriever_server(SlowRetrieverAgent(delay_seconds=0.3))
        try:
            with patch("grpc_server.RETRIEVER_ENDPOINT", endpoint):
                with self.assertRaises((grpc.aio.AioRpcError, TimeoutError)) as caught:
                    await VOCGRPCRuntime().run_with_params(
                        filters=["결제"], task="both", max_items=10,
                        csv_path=DEFAULT_CSV, timeout=0.05,
                    )
            if isinstance(caught.exception, grpc.aio.AioRpcError):
                self.assertEqual(caught.exception.code(), grpc.StatusCode.DEADLINE_EXCEEDED)
        finally:
            await server.stop(grace=0)

    async def test_empty_search_stops_safely_without_hallucination(self):
        """검색 결과가 없으면 이후 LLM 단계를 실행하거나 원인을 지어내면 안 됩니다."""
        server, endpoint = await start_retriever_server(EmptyRetrieverAgent())
        try:
            with patch("grpc_server.RETRIEVER_ENDPOINT", endpoint):
                result = await VOCGRPCRuntime().run_with_params(
                    filters=["존재하지않는유형"], task="both", max_items=10,
                    csv_path=DEFAULT_CSV, timeout=2,
                )
        finally:
            await server.stop(grace=0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "NO_MATCHING_VOC")
        self.assertIn("검색된 VOC가 없어", result["message"])
        self.assertEqual(result["summary"], "")
        self.assertEqual(result["policy"], "")
        self.assertEqual(
            [stage["agent"] for stage in result["stages"]],
            ["Interpreter", "Retriever"],
        )


if __name__ == "__main__":
    unittest.main()
