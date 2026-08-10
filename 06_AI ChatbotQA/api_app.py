"""
api_app.py
- 1단계 산출물: Service Agent를 FastAPI API로 제공
- /: API 안내
- /health: 서버 상태 확인
- /ask: 사용자 질문에 대한 챗봇 응답 반환
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from service_agent import get_response


app = FastAPI(
    title="AI Education Chatbot Service Agent API",
    description="AI 교육과정 안내 챗봇 Service Agent API",
    version="1.0.0",
)


REQUEST_BUCKETS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
_metrics_lock = Lock()
_request_counts = defaultdict(int)
_duration_bucket_counts = defaultdict(int)
_duration_count = 0
_duration_sum = 0.0


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="사용자 질문")


class AskResponse(BaseModel):
    question: str
    answer: str


@app.middleware("http")
async def collect_http_metrics(request, call_next):
    global _duration_count, _duration_sum

    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    path = request.url.path
    if path != "/metrics":
        labels = (request.method, path, str(response.status_code))
        with _metrics_lock:
            _request_counts[labels] += 1
            _duration_count += 1
            _duration_sum += duration
            for bucket in REQUEST_BUCKETS:
                if duration <= bucket:
                    _duration_bucket_counts[bucket] += 1
            _duration_bucket_counts[float("inf")] += 1

    return response


@app.get("/")
def root():
    return {
        "service": "AI Education Chatbot Service Agent API",
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "ask": "POST /ask",
            "docs": "GET /docs",
        },
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "service-agent"}


@app.get("/metrics")
def metrics():
    lines = [
        "# HELP http_requests_total Total HTTP requests.",
        "# TYPE http_requests_total counter",
    ]

    with _metrics_lock:
        request_counts = dict(_request_counts)
        bucket_counts = dict(_duration_bucket_counts)
        duration_count = _duration_count
        duration_sum = _duration_sum

    for (method, path, status), count in sorted(request_counts.items()):
        lines.append(
            f'http_requests_total{{method="{escape_label(method)}",path="{escape_label(path)}",status="{escape_label(status)}"}} {count}'
        )

    lines.extend(
        [
            "# HELP agent_response_seconds HTTP response duration in seconds.",
            "# TYPE agent_response_seconds histogram",
        ]
    )
    for bucket in REQUEST_BUCKETS:
        lines.append(f'agent_response_seconds_bucket{{le="{bucket:g}"}} {bucket_counts.get(bucket, 0)}')
    lines.append(f'agent_response_seconds_bucket{{le="+Inf"}} {bucket_counts.get(float("inf"), 0)}')
    lines.append(f"agent_response_seconds_count {duration_count}")
    lines.append(f"agent_response_seconds_sum {duration_sum}")

    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    answer = get_response(request.question)
    return {"question": request.question, "answer": answer}


@app.get("/ask", response_model=AskResponse)
def ask_get(question: str):
    answer = get_response(question)
    return {"question": question, "answer": answer}


def escape_label(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
