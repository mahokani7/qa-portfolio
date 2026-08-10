"""
main.py (app/)
- AI Agent 품질관리·운영 모니터링 플랫폼의 FastAPI 진입점입니다.
- /health, /ask, /metrics 를 제공합니다.
- 실행: 프로젝트 루트에서 `uvicorn app.main:app --reload`
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Response

from app.schemas import AskRequest, AskResponse, HealthResponse
from app.logger_config import get_logger
from app.metrics import record_ask_request, record_health_request, render_metrics, Timer

logger = get_logger(__name__)

app = FastAPI(title="AI Agent 품질관리·운영 모니터링 플랫폼", version="0.1.0")

_service_agent = None
_rule_based_agent = None


def _get_service_agent():
    global _service_agent
    if _service_agent is None:
        from app.service_agent import ServiceAgent
        _service_agent = ServiceAgent()
    return _service_agent


def _get_rule_based_agent():
    global _rule_based_agent
    if _rule_based_agent is None:
        from app.rule_based_agent import RuleBasedAgent
        _rule_based_agent = RuleBasedAgent()
    return _rule_based_agent


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    record_health_request()
    return HealthResponse(status="ok")


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    is_error = False
    agent_type = "rule_based" if payload.use_rule_based else "api_based"
    with Timer() as t:
        try:
            if payload.use_rule_based:
                agent = _get_rule_based_agent()
            else:
                agent = _get_service_agent()
            answer = agent.generate_response(payload.question)
        except Exception:
            is_error = True
            logger.exception("답변 생성 중 오류 발생 (question=%s)", payload.question)
            raise
        finally:
            # 성공/실패 모두 계측한다. 예외 시 raise가 with 블록을 빠져나가 블록 밖 코드가
            # 실행되지 않으므로, 반드시 이 finally 안에서 기록해야 오류 요청도 집계된다.
            # (finally는 __exit__보다 먼저 실행되어 t.elapsed가 갱신되기 전이므로 current_elapsed 사용)
            record_ask_request(agent_type, t.current_elapsed(), is_error=is_error)
    return AskResponse(question=payload.question, answer=answer, agent_type=agent_type)


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)
