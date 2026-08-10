"""실제 운영 서버를 중단하지 않고 장애 상황을 만드는 테스트 보조 도구."""

from __future__ import annotations

import asyncio
import socket
from contextlib import closing
from types import SimpleNamespace

import grpc

import voc_pb2_grpc
from agents.retriever import RetrieverServicer


def unused_endpoint() -> str:
    """현재 비어 있는 loopback 포트를 확보한 뒤 주소만 반환합니다."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        return f"127.0.0.1:{probe.getsockname()[1]}"


async def start_retriever_server(agent) -> tuple[grpc.aio.Server, str]:
    server = grpc.aio.server()
    voc_pb2_grpc.add_RetrieverServicer_to_server(RetrieverServicer(agent), server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    return server, f"127.0.0.1:{port}"


class EmptyRetrieverAgent:
    async def run(self, _csv_path, _filters, _max_items):
        return []


class SlowRetrieverAgent:
    def __init__(self, delay_seconds: float = 0.3):
        self.delay_seconds = delay_seconds

    async def run(self, _csv_path, _filters, _max_items):
        await asyncio.sleep(self.delay_seconds)
        return ["지연 후 반환되는 VOC"]


class RejectedAPIClient:
    """실제 외부 호출 없이 API 인증 거부를 재현합니다."""

    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    async def create(self, **_kwargs):
        raise RuntimeError("401 invalid_api_key")
