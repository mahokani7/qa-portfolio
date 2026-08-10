"""
ServiceAgent(RAG+LLM) 테스트 — 실제 OpenAI/ChromaDB 네트워크 호출 없이 mock으로 검증합니다.
"""

from unittest.mock import patch, MagicMock

from app.service_agent import ServiceAgent


def _make_fake_completion(content: str):
    fake = MagicMock()
    fake.choices = [MagicMock(message=MagicMock(content=content))]
    return fake


def test_generate_response_returns_stripped_llm_answer():
    with patch("app.service_agent.retrieve_context", return_value=["교육과정은 총 320시간입니다."]):
        agent = ServiceAgent()
        with patch.object(agent.client.chat.completions, "create",
                           return_value=_make_fake_completion("  총 320시간입니다.  ")):
            answer = agent.generate_response("이 교육과정은 총 몇 시간인가요?")
    assert answer == "총 320시간입니다."


def test_generate_response_handles_api_error_gracefully():
    with patch("app.service_agent.retrieve_context", return_value=[]):
        agent = ServiceAgent()
        with patch.object(agent.client.chat.completions, "create", side_effect=Exception("network down")):
            answer = agent.generate_response("질문")
    assert "오류" in answer


def test_build_system_prompt_includes_retrieved_context():
    agent = ServiceAgent()
    prompt = agent._build_system_prompt(["규정 문장 A", "규정 문장 B"])
    assert "규정 문장 A" in prompt
    assert "규정 문장 B" in prompt


def test_build_system_prompt_handles_empty_context():
    agent = ServiceAgent()
    prompt = agent._build_system_prompt([])
    assert "찾지 못했습니다" in prompt
