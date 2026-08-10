import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from agent_service import get_agent_answer
from logger_config import logger
from metrics import (
    agent_error_total,
    agent_request_total,
    agent_response_seconds,
    agent_service_status,
    agent_success_total,
)


app = FastAPI(
    title="AI Agent Monitoring API",
    description="AI Agent 운영·모니터링·품질관리 실습용 API",
    version="1.0.0"
)

agent_service_status.set(1)


@app.get("/")
def root():
    return {
        "message": "AI Agent Monitoring API가 정상 실행 중입니다."
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ai_agent_monitoring"
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.api_route("/ask", methods=["GET", "POST"])
def ask_agent(
    question: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="AI Agent에게 전달할 질문"
    )
):
    endpoint = "/ask"
    start_time = time.perf_counter()

    agent_request_total.labels(endpoint=endpoint).inc()

    logger.info("요청 시작 | question=%s", question)

    try:
        answer = get_agent_answer(question)

        elapsed = time.perf_counter() - start_time

        agent_success_total.labels(endpoint=endpoint).inc()
        agent_response_seconds.labels(endpoint=endpoint).observe(elapsed)

        logger.info(
            "정상 응답 | question=%s | elapsed=%.3f",
            question,
            elapsed
        )

        return {
            "status": "success",
            "question": question,
            "answer": answer,
            "response_seconds": round(elapsed, 3)
        }

    except ValueError as error:
        elapsed = time.perf_counter() - start_time

        agent_error_total.labels(
            endpoint=endpoint,
            error_type="validation_error"
        ).inc()

        agent_response_seconds.labels(endpoint=endpoint).observe(elapsed)

        logger.error(
            "입력 오류 | question=%s | error=%s",
            question,
            str(error)
        )

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        elapsed = time.perf_counter() - start_time

        agent_error_total.labels(
            endpoint=endpoint,
            error_type="agent_error"
        ).inc()

        agent_response_seconds.labels(endpoint=endpoint).observe(elapsed)

        logger.exception(
            "Agent 오류 | question=%s | error=%s",
            question,
            str(error)
        )

        raise HTTPException(
            status_code=500,
            detail="AI Agent 처리 중 오류가 발생했습니다."
        )


@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )