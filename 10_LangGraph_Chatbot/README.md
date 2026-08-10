# 배송조회 LangGraph 챗봇

LangGraph의 `create_react_agent`로 만든 도구 호출형(Tool-calling) AI Agent 실습 프로젝트입니다. 같은 개념을 **Python(FastAPI)** 과 **Node.js** 두 가지 스택으로 각각 구현했습니다.

- **Python 버전** (`main.py` + `chatbot_agent.py`): 배송조회 고객센터 챗봇. 주문번호로 배송 상태 조회·주문 취소를 처리하는 도구 2종을 갖춘 FastAPI API.
- **Node.js 버전** (`edubot.js`): 교육과정 훈련생을 위한 사내 어시스턴트 '에듀-봇'. 출결 규정·커리큘럼 일정 안내 도구 2종을 갖춘 CLI 스크립트.

두 구현 모두 시스템 프롬프트에 안전성 원칙(내부 지침 노출 거부, 타인 개인정보 요구 거부, 욕설에도 정중히 대응)을 명시한 것이 공통 특징입니다.

## 프로젝트 구조

```text
.
├─ main.py              # FastAPI 엔트리포인트 (Python)
├─ chatbot_agent.py      # LangGraph ReAct Agent + 도구 정의 (Python)
├─ requirements.txt
├─ edubot.js             # LangGraph ReAct Agent + 도구 정의 (Node.js)
├─ package.json
└─ .env.example
```

## 1) Python 버전 실행

### 준비 사항

- Python 3.10+
- OpenAI API 키

### 설치 및 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
# .env에 OPENAI_API_KEY 입력
py -m uvicorn main:app --reload
```

접속 주소: **http://localhost:8000/docs** (Swagger UI에서 `POST /api/chat`을 바로 테스트할 수 있습니다)

요청 예시:

```json
{
  "message": "12345번 배송 조회해줘",
  "session_id": "default_session"
}
```

> 검증 참고: 이 PC(오프라인 검증 환경)에서는 `chatbot_agent.py`·`main.py` 임포트와 FastAPI 앱 구성까지 확인했습니다. `ChatOpenAI` 인스턴스 생성 시점에는 API 키 존재 여부만 확인하므로, 실제 응답 생성은 유효한 `OPENAI_API_KEY`와 외부 네트워크 접근이 필요합니다.

## 2) Node.js 버전 실행

### 준비 사항

- Node.js 18+
- OpenAI API 키

### 설치 및 실행

```powershell
npm install
Copy-Item .env.example .env
# .env에 OPENAI_API_KEY 입력
npm start
```

`edubot.js`는 서버가 아니라 3가지 시나리오(출결 규정 문의, 커리큘럼 일정 문의, 진로 상담)를 순차 실행하고 콘솔에 결과를 출력하는 데모 스크립트입니다.

> 이 PC에는 Node.js가 설치되어 있지 않아 Node 버전은 정적 검토만 했습니다(문법·의존성 확인). Node.js가 설치된 환경에서 위 명령으로 바로 실행할 수 있습니다.

## 환경변수

| 변수 | 필수 여부 | 설명 |
|---|---:|---|
| `OPENAI_API_KEY` | 필수 | Python·Node 버전 공통. LangGraph Agent가 `gpt-4o-mini`/`gpt-4o` 호출에 사용 |
