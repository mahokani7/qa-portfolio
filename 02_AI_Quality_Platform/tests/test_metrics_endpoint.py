"""/metrics 엔드포인트 및 app.metrics 모듈 테스트 (Monitoring Test 대응)."""

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from app.metrics import ASK_REQUESTS_TOTAL, record_ask_request, record_health_request, render_metrics

client = TestClient(app)


def _ask_count(agent_type: str, status: str) -> float:
    """지정한 (agent_type, status) 라벨의 ask_requests_total 현재 값을 반환한다."""
    try:
        return ASK_REQUESTS_TOTAL.labels(agent_type=agent_type, status=status)._value.get()
    except Exception:
        return 0.0


def test_metrics_endpoint_exposes_prometheus_format():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "ask_requests_total" in response.text
    assert "health_requests_total" in response.text


def test_record_ask_request_increments_counter():
    body_before, _ = render_metrics()
    record_ask_request("rule_based", 0.01, is_error=False)
    body_after, _ = render_metrics()
    assert body_after != body_before


def test_record_health_request_does_not_raise():
    record_health_request()  # 예외 없이 호출되면 통과


def test_ask_success_records_success_metric_once(monkeypatch):
    """정상 /ask 1건은 success 카운터를 정확히 1만 증가시킨다(중복 집계 없음)."""
    class _OkAgent:
        def generate_response(self, q):
            return "정상 답변입니다."

    monkeypatch.setattr(main_module, "_rule_based_agent", _OkAgent())
    before = _ask_count("rule_based", "success")
    resp = client.post("/ask", json={"question": "테스트", "use_rule_based": True})
    assert resp.status_code == 200
    assert _ask_count("rule_based", "success") - before == 1.0


def test_ask_error_records_error_metric(monkeypatch):
    """에이전트가 예외를 던지는 실패 /ask도 error 카운터에 집계되어야 한다.
    (예외 시 raise가 with 블록을 빠져나가 계측이 누락됐던 회귀 버그 방지)"""
    class _BoomAgent:
        def generate_response(self, q):
            raise RuntimeError("의도된 오류")

    monkeypatch.setattr(main_module, "_service_agent", _BoomAgent())
    error_client = TestClient(app, raise_server_exceptions=False)
    before = _ask_count("api_based", "error")
    resp = error_client.post("/ask", json={"question": "테스트", "use_rule_based": False})
    assert resp.status_code == 500
    assert _ask_count("api_based", "error") - before == 1.0
