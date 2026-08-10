"""
schemas.py
- FastAPI 요청/응답 데이터 형식(Pydantic 모델)을 정의합니다.
"""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="사용자 질문")
    use_rule_based: bool = Field(
        default=False, description="True면 규칙 기반 챗봇, False(기본)면 API(RAG) 기반 챗봇으로 답변 생성"
    )


class AskResponse(BaseModel):
    question: str
    answer: str
    agent_type: str = Field(description="'rule_based' 또는 'api_based'")


class HealthResponse(BaseModel):
    status: str = "ok"
