"""
/ask API 형식 테스트.
- OpenAI API 키 없이도 돌아가도록 규칙 기반(use_rule_based=True) 경로만 검증합니다.
- API(RAG) 기반 경로는 실제 OpenAI 키가 필요해 통합 환경에서만 별도로 검증합니다.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_ask_rule_based_returns_expected_schema():
    response = client.post("/ask", json={"question": "지각을 세 번 하면 어떻게 되나요?", "use_rule_based": True})
    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "rule_based"
    assert body["question"] == "지각을 세 번 하면 어떻게 되나요?"
    assert isinstance(body["answer"], str) and len(body["answer"]) > 0


def test_ask_rejects_empty_question():
    response = client.post("/ask", json={"question": "", "use_rule_based": True})
    assert response.status_code == 422  # Pydantic min_length 검증에 의해 거부됨
