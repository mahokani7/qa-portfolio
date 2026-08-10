from fastapi import FastAPI
from pydantic import BaseModel
from chatbot_agent import chat_with_bot # 앞서 작성한 파일 임포트

app = FastAPI(title="배송조회 챗봇 API")

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session" # 세션 관리를 위한 ID (맥락 유지 실습 시 활용)

class ChatResponse(BaseModel):
    reply: str

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # 실제 환경에서는 session_id를 기반으로 LangChain의 메모리(chat_history)를 로드하는 로직이 추가됩니다.
    bot_reply = chat_with_bot(request.message)
    return ChatResponse(reply=bot_reply)

# 서버 실행 명령어: uvicorn main:app --reload
# API 문서(테스트용 UI): http://localhost:8000/docs