from prometheus_client import Counter, Histogram, Gauge


agent_request_total = Counter(
    "agent_request_total",
    "AI Agent 전체 요청 수",
    ["endpoint"]
)

agent_success_total = Counter(
    "agent_success_total",
    "AI Agent 정상 응답 수",
    ["endpoint"]
)

agent_error_total = Counter(
    "agent_error_total",
    "AI Agent 오류 응답 수",
    ["endpoint", "error_type"]
)

agent_response_seconds = Histogram(
    "agent_response_seconds",
    "AI Agent 응답시간(초)",
    ["endpoint"]
)

agent_service_status = Gauge(
    "agent_service_status",
    "AI Agent 서비스 상태, 정상=1, 비정상=0"
)