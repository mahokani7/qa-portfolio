# 최성우 | IT 기획 · PM · AI QA

20년+ IT 기획·PM 경험을 바탕으로 AI/LLM 서비스의 품질과 테스트 영역으로 역량을 확장하고 있습니다.

이 저장소에는 AI QA 교육 과정에서 진행한 개인·팀 프로젝트 9개 중, 직접 설계·구현·테스트·검증한 산출물을 정리했습니다.

- 개인 브랜딩 사이트: [mahokani7.github.io](https://mahokani7.github.io/)
- AI QA 포트폴리오(정리된 버전): [mahokani7.github.io/qa](https://mahokani7.github.io/qa/)

## 핵심 역량

이 저장소의 프로젝트에서 실제로 사용한 역량만 적었습니다.

- 요구사항 분석 및 테스트 전략 수립
- 테스트 케이스 설계, 결함 분석·관리
- LLM-as-a-Judge 기반 AI 응답 품질 평가
- 품질 지표·루브릭 설계 (RaiT 8축 프레임워크)
- API 테스트(pytest), E2E 테스트(Cypress)
- Jira 기반 QA 관리, WBS·테스트 계획 수립
- QA 결과 분석 및 재검증(Re-test)

## Featured Projects

9개 프로젝트 중 먼저 보시면 좋은 4개입니다. 나머지 5개는 [Additional Projects](#additional-projects)에 있습니다.

### [`04`](04_QA_WBS_TestPlan/) QA 문서 산출물

- **프로젝트 성격**: QA 프로세스 문서 13종(팀 프로젝트 산출물)
- **핵심**: 요구사항정의서 → WBS → 테스트 계획서 → 결함/이슈 관리 → 재검증까지 QA 문서 체계
- **내 역할**: 단위·통합 테스트 계획서, 최종 발표 자료를 직접 작성했습니다. 나머지 문서는 팀 공동 산출물입니다 — 상세 구분은 [`04_QA_WBS_TestPlan/README.md`](04_QA_WBS_TestPlan/README.md) 참고.

### [`02`](02_AI_Quality_Platform/) AI 품질 평가 플랫폼

- **프로젝트 성격**: 개인 프로젝트
- **핵심**: 레드팀·환각검출·PII스캔·회귀·RAG절제·비용추적·Jira연동 + k6 성능 테스트 + Grafana/Prometheus 모니터링
- **내 역할**: 기획부터 구현까지 단독 수행 — 루브릭 설계, Judge/Rule-based Agent 구현, JSON Schema 설계, Streamlit 대시보드, pytest 84건 설계. 상세는 [`02_AI_Quality_Platform/README.md`](02_AI_Quality_Platform/README.md) 참고.

### [`01`](01_VOC_Improve_MultiAgent/) VOC 멀티에이전트 QA 파이프라인

- **프로젝트 성격**: 팀 프로젝트(4인)
- **핵심**: 6-에이전트 VOC 분석 파이프라인 + 독립 LLM Judge 2차 검수. pytest는 전부 PASS했지만 독립 Judge는 배포 기준(95점) 미달로 배포 보류(HOLD) 판정 — 테스트 통과와 배포 승인이 다른 층위라는 것을 확인한 사례.
- **내 역할**: 테스트 시나리오 설계, 평가 루브릭 설계, Judge 프롬프트 검증, 독립 Judge 결과 검증, 최종 발표·시연. 개발·인프라·리포팅은 팀원이 담당했습니다. 상세는 [`01_VOC_Improve_MultiAgent/README.md`](01_VOC_Improve_MultiAgent/README.md) 참고.

### [`09`](09_FullStack_WebApp/) 풀스택 웹앱 QA

- **프로젝트 성격**: 개인 프로젝트 — 전통적 웹 QA 자동화 역량을 보여주는 유일한 항목
- **핵심**: Cypress E2E 테스트, Jest 통합 테스트, node:test 단위 테스트
- **내 역할**: 테스트 대상 웹앱과 Cypress/Jest 테스트 스위트를 직접 작성. `npm test` 기준 단위 5건·통합 4건 전부 PASS. 상세는 [`09_FullStack_WebApp/README.md`](09_FullStack_WebApp/README.md) 참고.

## Additional Projects

`05`(RaiT 평가 시스템, 개인) · `06`(AI 챗봇 QA, 팀 프로젝트) · `07`(RAG 챗봇, 개인) · `08`(AI Agent 모니터링, 개인) · `10`(LangGraph 챗봇, 개인) — 실행 방법은 아래 [프로젝트별 실행 방법](#프로젝트별-실행-방법)에 전부 있습니다.

## AI 활용 원칙

이 저장소의 코드와 문서 작성에 AI 도구(Claude 등)를 코드 작성과 문서 초안의 **보조 수단**으로 활용했습니다. 요구사항 정의·테스트 설계·결과 검증·오류 원인 분석·최종 품질 판단은 **직접 수행**했습니다. 이 저장소를 공개용으로 정리하면서 발견한 결함(의존성 오류, 자격 증명 노출, 채점 로직 결함 등)과 수정 내역은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)에 정리했습니다.

## 검증 결과 · QA 증적

수집일: 2026-08-05
수록 프로젝트: **9개** — `01`~`10` 중 03 제외(교육과정 원래 번호 08·12·13·16을 재배치). 03(AI 챗봇 QA 파이프라인)은 06과 같은 팀 프로젝트의 초기 버전이라 06으로 통합하고 저장소에서 제외했습니다.
선정 기준: **웹으로 보여줄 수 있는 것** + QA 문서 산출물(04)

> ### 📄 실행 검증 요약(실무자 영역)은 [`index.html`](index.html)을 여세요 ([mahokani7.github.io/qa-portfolio](https://mahokani7.github.io/qa-portfolio/)에서도 볼 수 있습니다)
> 실행 증적(명령·종료코드·출력), 웹 가동 가능성 4축 판정이 들어 있습니다.
> **검증 요약** — 실행 검증 완료 6개(01·02·05·06·08·09) / API 키 필요 2개(07·10) / 문서 1개(04)
>
> 자동 테스트 **276건**을 직접 실행해 통과를 확인했습니다 — 내역:

| 항목 | 테스트 수 |
|---|---:|
| 01 · VOC 멀티에이전트 (`unittest`) | 98 |
| 01 · VOC 멀티에이전트 (품질 스위트, pytest) | 32 |
| 02 · AI 품질 평가 플랫폼 (pytest) | 84 |
| 06 · 팀 프로젝트 — AI 챗봇 QA (pytest) | 53 |
| 09 · 풀스택 웹앱 (`node:test`) | 5 |
| 09 · 풀스택 웹앱 (Jest) | 4 |
| **합계** | **276** |

> 276건 전부를 처음부터 직접 개발했다는 뜻은 아닙니다. 01·06은 팀 프로젝트이며, 그 안에서 제가 실제로 담당한 테스트 설계·검증 범위는 [Featured Projects](#featured-projects)의 프로젝트별 "내 역할"에 구분해 두었습니다.
> 검증 방법과 발견한 결함·수정 내역은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)에 정리했습니다.

### 깃허브 → 웹 실행 점검 (2026-08-06)

깃허브에 push한 그 상태로 호스팅에 연결했을 때 **방문자에게 실제로 무엇이 보이는가**를 판정했습니다.

| # | 프로젝트 | 판정 | 키 | 막는 것 |
|---|---|---|---|---|
| 01 | VOC 멀티에이전트 | ⚠️ 부분 | 2개 | Docker 필요 (gRPC 6개 + 웹서버 동시 기동) |
| 02 | AI품질·운영 모니터링 | ⚠️ 부분 | 필요 | Prometheus·Grafana·k6가 로컬 Docker 스택 전제 |
| **04** | **QA 문서 산출물** | ❌ **실행 불가** | — | **실행할 프로그램이 아님 — 문서 13종** |
| 05 | RAIT 평가 시스템 | ✅ 실행됨 | **불필요** | — (기동 확인 완료) |
| 06 | 팀 프로젝트 — AI 챗봇 QA | ⚠️ 부분 | 필요 | compose 4서비스 구조 |
| 07 | RAG 챗봇 | ✅ 실행됨 | 필요 | — (올리기 가장 쉬움) |
| 08 | AI Agent 모니터링 | ⚠️ 부분 | **불필요** | `streamlit_app.py:17`이 `127.0.0.1:8001` 하드코딩 |
| 09 | 풀스택 웹앱 | ⚠️ 부분 | 불필요 | **화면만 뜨고 기능 불가** — `/api` 404, MongoDB 필요 |
| 10 | 배송조회 챗봇 | ⚠️ 부분 | 필요 | UI 없음 (`/docs`로 대체 가능) |

**웹에서 실행 자체가 불가능한 것은 04번 하나뿐**이고, 그것도 결함이 아니라 문서라서 그렇습니다.
나머지 8개는 전부 뜨지만, ⚠️ 표시된 6개는 **일부 기능이 죽은 채로** 뜹니다.

> **키 없이 안전하게 공개 가능한 것: 05 · 08 · 09** (단 08·09는 위 조치 필요)
> 나머지 **01·02·06·07·10은 OpenAI 키가 듭니다.** 공개 URL로 두면 방문자가 누르는 만큼 본인 카드로 결제됩니다.
> 사용량 한도 설정 + 비밀번호·토큰 + 면접 기간 한정 공개, 이 셋은 반드시 함께 하세요.

### 깃허브 업로드 전 확인 사항

- **실제 키 유출 0건** — `.env` 실파일 없음, 소스 내 `sk-…` 하드코딩 없음(발견된 노출 사례와 조치는 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) 참조)
- **루트 `.gitignore` 추가함** — `.env`·`.venv`·`node_modules` 커밋 방지
- **100MB 초과 파일 없음.** `06_AI_Chatbot_QA/tools/k6.exe`(61MB)는 50MB 경고 대상이라 `.gitignore`로 저장소에서 제외함(필요 시 `winget install k6`로 로컬 설치)

---

## 실행 전 공통 준비 (한 번만)

### 1. API 키 설정 — ⚠️ 필수

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

> 01·02·06·08·05는 키 없이도(또는 더미 키로도) 테스트가 통과합니다 — 근거는 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) 참조.

### 2. Python 가상환경

`venv`는 다른 PC에서 동작하지 않으므로 복사하지 않았습니다. 프로젝트마다 새로 만드세요.

```powershell
cd <프로젝트 폴더>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> `Activate.ps1` 실행이 막히면: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

### 3. Node 프로젝트

`node_modules`도 복사하지 않았습니다. `npm install`로 복원하세요.

---

## 프로젝트별 실행 방법

> 아래 각 프로젝트는 먼저 위 "공통 준비"(venv 생성 + `pip install` 또는 `npm install` + `.env` 복사)를 마쳤다는 전제이며, 여기서는 프로젝트 고유 실행 명령만 적습니다.

### 🥇 01. VOC_Improve — 멀티에이전트 QA 시스템
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

### 🥈 02. AI 품질 + 운영 모니터링 플랫폼 ⭐ QA 도구 폭이 가장 넓음
> 레드팀·환각검출·PII스캔·회귀·RAG절제·비용추적·Jira연동 + k6 + Grafana/Prometheus

```powershell
cd 02_AI_Quality_Platform
.\run_full.ps1                              # ★ 대시보드 + 모니터링 원클릭 실행
streamlit run dashboard\streamlit_app.py    # 대시보드만
python -m quality.quality_pipeline          # 품질 파이프라인
pytest tests -v                             # 테스트
docker-compose up -d                        # Prometheus + Grafana 스택
k6 run performance\k6_test.js               # 부하 테스트 (k6 미설치 시 winget install k6)
```
**볼거리**: `quality/`(모듈 12종), `monitoring/grafana/`(대시보드 2종 + 알림규칙), `docs/`(테스트계획서·결함리포트·성능리포트·사양서)

### 04. QA 문서 산출물 (실행 불필요 — 문서 전용)
> **QA 직무 증빙 1순위.** 코드보다 이쪽이 채용에서 더 강합니다.

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
> 팀 프로젝트(4인)입니다. 이 코드는 팀이 함께 만든 초기 버전을 이어받아 확장한 것이며, 제 담당은 pytest 테스트 스위트 설계·구현과 QA 문서 작성입니다. 자세한 역할 분담은 [`04_QA_WBS_TestPlan/README.md`](04_QA_WBS_TestPlan/README.md) 참고.

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
> 02번의 축약 원형입니다. 02번을 보여줄 수 있으면 이건 부록으로 충분합니다.

### 09. 풀스택 웹앱 (테스트 대상) — **Cypress E2E + Jest 포함**
```powershell
cd 09_FullStack_WebApp\backend
npm install
copy .env.example .env
npm start                # Express API (schema.sql로 DB 먼저 생성)
npm test                 # 단위(node:test 5건) + 통합(Jest 4건) — exit 0

cd ..\frontend
npm install
npm run dev              # React/Vite 개발 서버
npx cypress open         # ★ E2E 테스트 (QA 포트폴리오 핵심)
```
> **이 프로젝트의 포트폴리오 가치는 앱 자체가 아니라 `cypress/` E2E 테스트와 `jest` 단위 테스트입니다.**

### 10. 배송조회 LangGraph 챗봇
```powershell
cd 10_LangGraph_Chatbot
python main.py       # Python 버전 (FastAPI)
npm install; npm start   # Node 버전 (edubot.js)
```

---

## 포트폴리오 발표 시 추천 순서

| 순서 | 프로젝트 | 이유 | 키 없이 시연 |
|---|---|---|---|
| 1 | **04** (QA 문서) | 코드 켜기 전에 QA 프로세스 이해도부터 보여줌 | 문서 |
| 2 | **02** (품질+모니터링) | 도구 폭이 가장 넓음 — 레드팀·PII·k6·Grafana·Jira | ✅ (더미 키) |
| 3 | **01** (VOC) | 규모·완성도 최대 + 시연 영상 2편 + 오프라인 모드 | ✅ |
| 4 | **09** (Cypress E2E) | **전통적 웹 QA 자동화 역량을 증명하는 유일한 항목** | ✅ |

---

검증 방법, 발견한 결함, 수정 내역, 재검증 결과는 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)를 참조하세요.

## GitHub

- 이 저장소: [github.com/mahokani7/qa-portfolio](https://github.com/mahokani7/qa-portfolio)
- 개인 브랜딩 사이트: [mahokani7.github.io](https://mahokani7.github.io/)
- AI QA 포트폴리오(정리된 버전): [mahokani7.github.io/qa](https://mahokani7.github.io/qa/)
