# 실행 셋업 가이드

각 프로젝트를 로컬에서 직접 실행해보고 싶을 때 필요한 공통 준비와 프로젝트별 실행 명령입니다. `README.md`의 "빠른 시작"에서 여기로 연결됩니다.

## 1. API 키 설정 — ⚠️ 필수

**실제 `.env` 파일은 복사하지 않았습니다.** 각 프로젝트에 `.env.example`만 들어 있습니다.

```powershell
# 실행할 프로젝트 폴더에서
copy .env.example .env
notepad .env        # 본인 API 키 입력
```

| 필요한 키 | 사용 프로젝트 |
|---|---|
| `OPENAI_API_KEY` | 01, 02, 06, 07, 10 |
| `ANTHROPIC_API_KEY` | 01 |
| `JIRA_*` (선택, 결함 자동등록) | 02, 06 |
| 키 불필요 | 04, 05, 08, 09 |

> 01·02·05·06·08은 키 없이도(또는 더미 키로도) 테스트가 통과합니다 — 근거는 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) 참조.

## 2. Python 가상환경

`venv`는 다른 PC에서 동작하지 않으므로 복사하지 않았습니다. 프로젝트마다 새로 만드세요.

```powershell
cd <프로젝트 폴더>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `Activate.ps1` 실행이 막히면: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## 3. Node 프로젝트

`node_modules`도 복사하지 않았습니다. `npm install`로 복원하세요.

## 4. 공개 호스팅 시 주의사항 (직접 배포해볼 경우)

- **키 없이 안전하게 공개 가능한 것**: 05 · 08 · 09(단 08·09는 아래 "웹 실행 점검" 조건 확인)
- **01·02·06·07·10은 OpenAI/Anthropic 키가 듭니다.** 공개 URL로 두면 방문자가 누르는 만큼 본인 카드로 결제됩니다. 크롤러 한 대만 붙어도 하룻밤에 요금이 나갈 수 있습니다.
- 꼭 공개해야 한다면 **사용량 한도 설정 + 비밀번호/토큰 보호 + 면접 기간 한정 공개**, 이 셋을 반드시 함께 적용하세요.

## 5. 보안 확인 사항

- **실제 키 유출 0건** — `.env` 실파일은 저장소에 없고, 소스 내 `sk-…` 하드코딩도 없습니다(발견된 노출 사례와 조치는 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) 참조).
- **루트 `.gitignore`** — `.env`·`.venv`·`node_modules` 커밋을 막습니다.
- **100MB 초과 파일 없음.** `06_AI_Chatbot_QA/tools/k6.exe`(61MB)는 50MB 경고 대상이라 `.gitignore`로 제외했습니다(필요 시 `winget install k6`로 로컬 설치).

## 6. 웹 실행 점검 (2026-08-06, 깃허브에 push된 그대로 호스팅했을 때)

| # | 프로젝트 | 웹 실행 | 필요 조건 |
|---|---|---|---|
| 01 | VOC 멀티에이전트 | 일부 기능 제한 | Docker 필요(gRPC 6개 + 웹서버 동시 기동) |
| 02 | AI품질·운영 모니터링 | 일부 기능 제한 | Prometheus·Grafana·k6가 로컬 Docker 스택 전제 |
| 04 | QA 문서 산출물 | 해당 없음 | 문서 13종, 실행 프로그램이 아님 |
| 05 | RAIT 평가 시스템 | 정상 | 키 불필요, 기동 확인 완료 |
| 06 | 팀 프로젝트 — AI 챗봇 QA | 일부 기능 제한 | compose 4서비스 구조 |
| 07 | RAG 챗봇 | 정상 | API 키 필요 |
| 08 | AI Agent 모니터링 | 일부 기능 제한 | `streamlit_app.py:17`의 `127.0.0.1:8001` 하드코딩을 환경변수로 바꾸는 수정 필요 |
| 09 | 풀스택 웹앱 | 일부 기능 제한 | 프론트는 정적 배포 가능, 백엔드 기능은 MongoDB 필요 |
| 10 | 배송조회 챗봇 | 일부 기능 제한 | API 키 필요, UI 없음(`/docs`로 대체 가능) |

## 프로젝트별 실행 방법

> 아래 각 프로젝트는 먼저 위 "공통 준비"(venv 생성 + `pip install` 또는 `npm install` + `.env` 복사)를 마쳤다는 전제이며, 여기서는 프로젝트 고유 실행 명령만 적습니다.

### 01. VOC_Improve — 멀티에이전트 QA 시스템
> 6-에이전트 VOC 분석 + LLM Judge + 품질게이트 + 레드팀 / gRPC·MCP·Docker·CI

```powershell
cd 01_VOC_Improve_MultiAgent
# .env에 ANTHROPIC_API_KEY 입력 후:
python run_all.py           # ① 6개 에이전트 전체 파이프라인 실행
python web_app.py           # ② 웹 UI (브라우저 테스트)
python grpc_server.py       # ③ gRPC A2A 서버
python main.py              # ④ MCP 서버
pytest tests -v             # ⑤ 테스트
python quality_diagnosis/run_quality_suite.py   # ⑥ 품질 진단 스위트
```
**볼거리**: `quality_diagnosis/`(LLM Judge·품질게이트·레드팀·재현성), `docs/`(발표 PPTX/PDF, PRD), `videos/`(시연 영상 2편)

### 02. AI 품질 + 운영 모니터링 플랫폼
> 레드팀·환각검출·PII스캔·회귀·RAG절제·비용추적·Jira연동 + k6 + Grafana/Prometheus

```powershell
cd 02_AI_Quality_Platform
.\run_full.ps1                              # 대시보드 + 모니터링 원클릭 실행
streamlit run dashboard\streamlit_app.py    # 대시보드만
python -m quality.quality_pipeline          # 품질 파이프라인
pytest tests -v                             # 테스트
docker-compose up -d                        # Prometheus + Grafana 스택
k6 run performance\k6_test.js               # 부하 테스트 (k6 미설치 시 winget install k6)
```
**볼거리**: `quality/`(모듈 12종), `monitoring/grafana/`(대시보드 2종 + 알림규칙), `docs/`(테스트계획서·결함리포트·성능리포트·사양서)

### 04. QA 문서 산출물 (실행 불필요 — 문서 전용)

요구사항정의서·업무분장·WBS·Jira 칸반·보안가이드·취약지표 분석기준·회의록·이슈트래킹시트·단위/통합 테스트계획서·프로그램분석보고서 등 13종.

### 05. RAIT 평가 시스템
```powershell
cd 05_RAIT_Evaluation_System
streamlit run app\app.py     # ① 평가 대시보드
python src\main.py           # ② 평가 엔진 (별도 실행, Mock LLM Judge)
```

### 06. 팀 프로젝트 — AI 챗봇 QA
```powershell
cd 06_AI_Chatbot_QA
python main.py                              # 평가 실행
python api_app.py                           # FastAPI + /metrics
streamlit run dashboard\streamlit_app.py    # 대시보드
pytest -v                                   # 테스트
docker-compose up -d                        # Prometheus 연동
```
> 자세한 실행법은 폴더 안 `RUN_GUIDE.md` 참조. 부하 테스트에 필요한 `k6`는 저장소에 포함되어 있지 않으니 `winget install k6`로 설치하세요.

### 07. RAG 챗봇
```powershell
cd 07_RAG_Chatbot
streamlit run app.py       # 챗봇 UI
python ingest.py           # 문서 재색인 (documents/ 기준)
python run_evaluation.py   # 답변 품질 평가
python run_tests.py        # 테스트
```
> ChromaDB 인덱스와 `uploads/`(국민취업지원제도 매뉴얼 PDF) 포함 — 바로 질의 가능합니다.

### 08. AI Agent 모니터링 대시보드
```powershell
cd 08_AI_Agent_Dashboard
uvicorn app:app --reload             # ① API 서버
streamlit run streamlit_app.py       # ② 대시보드 (별도 터미널)
python tests\run_tests.py            # ③ 기능/성능 테스트
```
> 02번의 축약 원형입니다.

### 09. 풀스택 웹앱 — Cypress E2E + Jest
```powershell
cd 09_FullStack_WebApp\backend
npm install
copy .env.example .env
npm start                # Express API (schema.sql로 DB 먼저 생성)
npm test                 # 단위(node:test 5건) + 통합(Jest 4건) — exit 0

cd ..\frontend
npm install
npm run dev              # React/Vite 개발 서버
npx cypress open         # E2E 테스트
```
> 이 프로젝트의 포트폴리오 가치는 앱 자체가 아니라 `cypress/` E2E 테스트와 `jest` 단위 테스트입니다.

### 10. 배송조회 LangGraph 챗봇
```powershell
cd 10_LangGraph_Chatbot
python main.py       # Python 버전 (FastAPI)
npm install; npm start   # Node 버전 (edubot.js)
```
