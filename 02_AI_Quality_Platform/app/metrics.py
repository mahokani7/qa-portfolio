"""
metrics.py
- Prometheus 운영 지표 수집 모듈 (prometheus_client 기반).
- app/main.py의 /ask, /health 요청을 계측하고 /metrics 엔드포인트로 표준 Prometheus exposition 포맷을 노출합니다.
- monitoring/prometheus.yml이 이 /metrics를 스크레이핑합니다.
"""

import time

from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest

# 요청 수 (성공/실패, agent_type 라벨별)
ASK_REQUESTS_TOTAL = Counter(
    "ask_requests_total", "Total /ask requests", ["agent_type", "status"]
)

# 응답시간 분포 (초 단위) - Grafana에서 p95 등 계산 가능
ASK_REQUEST_LATENCY_SECONDS = Histogram(
    "ask_request_latency_seconds", "Latency of /ask requests in seconds", ["agent_type"]
)

# 헬스체크 호출 수
HEALTH_REQUESTS_TOTAL = Counter("health_requests_total", "Total /health requests")


def record_ask_request(agent_type: str, latency_seconds: float, is_error: bool) -> None:
    """/ask 요청 1건의 처리 결과를 Prometheus 지표에 반영합니다."""
    status = "error" if is_error else "success"
    ASK_REQUESTS_TOTAL.labels(agent_type=agent_type, status=status).inc()
    ASK_REQUEST_LATENCY_SECONDS.labels(agent_type=agent_type).observe(latency_seconds)


def record_health_request() -> None:
    HEALTH_REQUESTS_TOTAL.inc()


def render_metrics() -> tuple[bytes, str]:
    """Prometheus 표준 exposition 포맷(bytes)과 Content-Type을 반환합니다."""
    return generate_latest(), CONTENT_TYPE_LATEST


class Timer:
    """with Timer() as t: ... 형태로 처리 시간을 측정하는 간단한 컨텍스트 매니저."""

    def __enter__(self):
        self._start = time.perf_counter()
        self.elapsed = 0.0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self._start

    def current_elapsed(self) -> float:
        """__exit__ 이전(예: with 블록 내부 finally)에서도 현재까지의 경과시간을 계산해 반환한다.
        (with 블록의 finally는 __exit__보다 먼저 실행되어 self.elapsed가 아직 갱신되지 않기 때문)"""
        return time.perf_counter() - self._start
