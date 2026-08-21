# AI 챗봇 QA 자동화 플랫폼 (팀 프로젝트)

AI 기반 소프트웨어 테스터(QA) 및 모니터링 실무 과정의 팀 프로젝트입니다. 02번(AI Agent 품질관리·운영 모니터링 플랫폼)과 이름이 비슷하지만 **서로 다른 프로젝트**입니다 — 02는 개인 프로젝트, 이 프로젝트는 4인 팀 프로젝트입니다.

교육과정 안내 챗봇을 대상으로 테스트케이스 업로드, 자동 평가, 결과 리포트, 지식 DB 관리, Service Agent API, 운영 모니터링 기능을 구현합니다.

**왜 필요한가**: 교육과정 안내 챗봇의 응답을 규칙 기반 1차 검증과 LLM Judge 2차 평가로 이중 검증하고, 그 결과를 테스트 이력으로 남겨 팀이 반복 검증할 수 있게 하는 것이 목표입니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 팀 프로젝트(4인) |
| 내 역할 | pytest 테스트 스위트(53건) 설계·구현, 테스트케이스 설계, 통합 테스트, QA 문서, 최종 발표 |
| 테스트 범위 | `tests/` pytest 53건(현재) — 초기 단계에는 14건이었고 이후 범위가 넓어짐(아래 "현재 구현 단계" 참고) |
| 자동화 도구 | pytest, k6, Docker Compose(Prometheus/Grafana), Jira 연동 |
| 주요 검증 | 규칙 기반 검증 + LLM Judge 평가 이중 검증, RAG ON/OFF 비교, 테스트 수행 이력 조회·비교 |
| 주요 결함 | 이 README의 "현재 구현 단계"에 초기 단계 테스트 결과(14건)가 남아 있어 최신 My Role의 53건과 서로 다른 시점의 숫자가 함께 있었음 |
| 개선 결과 | 두 숫자가 서로 다른 시점(초기 단계 vs 현재)의 값임을 명시하는 안내문 추가 |
| 최종 판정 | **PASS** — pytest 53/53 |

## Project Type

팀 프로젝트(4인) — 팀이 초기 버전(같은 기반 코드: service_agent.py·judge_agent.py·rule_validator.py·config.py)에 Docker/Jira/모니터링을 추가로 확장한 버전입니다. 초기 버전은 이 버전으로 완전히 대체되어 저장소에서 별도로 두지 않았습니다.

## My Role

- pytest 테스트 스위트(`tests/`, 53건) 설계·구현
- 테스트케이스 설계 및 통합 테스트 수행
- QA 문서(단위/통합 테스트 계획서 등)와 최종 발표 자료 작성

Service Agent·Judge Agent·규칙 검증 로직, 환경 구성, 리포트/대시보드 구현은 팀원이 담당했습니다. 자세한 역할 분담 근거는 [`04_QA_WBS_TestPlan`](../04_QA_WBS_TestPlan/)의 업무분장 문서를 참고하세요.

## 📌 포트폴리오 핵심 문서

- [최종 품질 보고서](reports/final_quality_report.md) — 규칙 검증 23건 통과율 등 실측 결과
- 위 QA SUMMARY, 아래 QA 관점의 핵심 — 제가 수행한 역할과 발견한 문제

## QA 관점의 핵심

- **무엇을 검증했는가**: 교육과정 안내 챗봇의 응답을 규칙 기반 1차 검증과 LLM Judge 2차 평가로 이중 검증
- **왜 검증했는가**: 규칙 기반 검증만으로는 놓치는 응답 품질(자연스러움·근거성)을, LLM Judge만으로는 놓치는 명확한 정책 위반(규칙 기반이 더 확실)을 서로 보완하기 위해
- **PASS/FAIL 기준**: `tests/` pytest 전수 통과 + 규칙 검증 통과율
- **발견한 문제**: 이 README의 "현재 구현 단계"에 초기 단계 테스트 결과(14건)가 남아 있어 최신 My Role의 53건과 서로 다른 시점의 숫자가 함께 있었음(아래 각주 참고)
- **어떻게 분석했는가**: 초기 단계(Service Agent·FastAPI 핵심 엔드포인트만)와 현재(k6·Jira 연동·파이프라인 실행기·리포트 생성기까지 확장된 범위)가 서로 다른 시점의 값임을 확인
- **재검증**: 두 숫자가 서로 다른 시점의 값임을 명시하는 안내문 추가, `pytest -v`로 현재 53건 재확인

> **53건 수치에 대한 참고**: 이 숫자는 오늘 기준으로는 정확하지만, 파라미터화된 테스트 중 일부(`test_selected_registered_testcase_rule_validation`)는 `data/testcases/testcase_uploads.json`에 등록된 **최신 업로드 테스트케이스 집합**의 건수만큼 자동으로 늘어나거나 줄어듭니다. 즉 53은 코드에 고정된 상수가 아니라, 현재 등록된 데이터에 따라 달라질 수 있는 값입니다.

---

## 🔧 Technical Reference

아래는 실행 방법·API·코드 구조 등 기술적 상세입니다(RUN_GUIDE.md 포함). 프로젝트 핵심 내용은 위 요약과 문서에서 먼저 확인할 수 있습니다.

## 주요 기능

- Streamlit 기반 품질관리 대시보드
- 테스트케이스 JSON/CSV 업로드 및 관리
- 선택한 테스트케이스 실행
- 규칙 기반 검증 및 OpenAI Judge 기반 응답 품질 평가
- 테스트 수행 이력 조회, 상세 비교, 삭제
- 실행별 JSON/CSV/Markdown 리포트와 실행 로그 생성
- RAG ON/OFF 비교 결과 생성
- ChromaDB 기반 지식 DB 검색 및 fallback 문서 검색
- 지식 DB 파일 업로드, 미리보기, 검색 테스트
- FastAPI 기반 Service Agent API 제공
- Prometheus/Grafana 운영 모니터링
- k6 성능 테스트 결과 조회
- Docker Compose 통합 실행

## 현재 구현 단계

### 1단계: Service Agent + FastAPI

Service Agent를 API로 호출할 수 있도록 FastAPI 앱을 추가했습니다.

제공 API:

- `GET /`
- `GET /health`
- `POST /ask`
- `GET /ask?question=...`

### 2단계: pytest 기능 테스트

자동 테스트로 Service Agent, 규칙 검증, FastAPI 엔드포인트, 테스트 실행 결과 변환 로직을 검증합니다.

이 단계 당시의 테스트 결과(스코프: Service Agent·FastAPI 핵심 엔드포인트만):

```text
14 passed
```

> **참고**: 위 `14 passed`는 이 초기 단계 스냅샷입니다. 이후 k6 성능 테스트·Jira 연동·파이프라인 실행기·리포트 생성기까지 테스트 범위가 넓어져, 현재 `tests/` 전체 실행 결과는 **53 passed**입니다(`pytest -v`로 재확인 가능, 위 "My Role" 참고).

## 프로젝트 구조

```text
.
  api_app.py                  # FastAPI 엔트리포인트
  config.py                   # 경로 및 환경 설정
  service_agent.py            # 챗봇 응답 생성 로직
  rule_validator.py           # 규칙 기반 검증
  judge_agent.py              # OpenAI 기반 품질 평가
  report_generator.py         # 평가 결과 리포트 생성
  main.py                     # CLI 기반 전체 파이프라인 실행
  requirements.txt            # Python 의존성
  Dockerfile                  # API/대시보드 컨테이너 이미지
  docker-compose.yml          # FastAPI, Streamlit, Prometheus, Grafana 통합 실행
  .env                        # 환경 변수 파일

  dashboard/
    streamlit_app.py          # Streamlit 대시보드 엔트리포인트
    navigation.py             # 상단 메뉴/사이드바 렌더링

    core/                     # 공통 설정, 상태, 저장 기능
    services/                 # 지식베이스, 테스트 실행 서비스
    components/               # 리포트/차트 UI 컴포넌트
    testcase/                 # 테스트케이스 변환/헬퍼
    pages_top/                # 상단 메뉴별 화면

  data/
    chroma/                   # ChromaDB 영속 저장소
    knowledge/uploads/        # 지식 파일 업로드 위치
    testcases/                # 테스트케이스 업로드/실행 이력

  reports/
    evaluation_result.*       # 최신 RAG ON 평가 결과
    rag_off_evaluation_result.* # 최신 RAG OFF 평가 결과
    k6_runs/                  # k6 실행 결과
    test_runs/                # 테스트 실행별 리포트
```

## 설치 방법

이 폴더가 프로젝트 루트입니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 자동 테스트 실행

기본 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

커버리지 포함 테스트:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --cov=. --cov-report=term-missing
```

## 환경 변수

`.env` 파일은 프로젝트 루트(`.env.example` 참고)에 둡니다.

```env
OPENAI_API_KEY=your_api_key_here
JIRA_BASE_URL=https://example.atlassian.net
JIRA_EMAIL=your_email@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=QA
JIRA_ISSUE_TYPE=Bug
```

OpenAI API 키가 없으면 Judge 평가가 실패 결과로 처리될 수 있습니다. Jira 값은 결함 등록 기능을 사용할 때 필요합니다.

## Streamlit 대시보드 실행

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard\streamlit_app.py
```

기본 접속 주소:

```text
http://localhost:8501
```

## FastAPI 실행

```powershell
.\.venv\Scripts\python.exe -m uvicorn api_app:app --reload --port 8000
```

기본 접속 주소:

```text
http://localhost:8000
```

루트 주소에서는 API 상태와 주요 엔드포인트 안내를 확인할 수 있습니다.

Swagger 문서:

```text
http://localhost:8000/docs
```

## Docker Compose 실행

Docker Desktop 실행 후 프로젝트 폴더에서 아래 명령을 실행합니다.

```powershell
docker compose up --build
```

접속 주소:

```text
Streamlit:   http://localhost:8501
FastAPI:     http://localhost:8000
Prometheus:  http://localhost:9090
Grafana:     http://localhost:3000
```

종료:

```powershell
docker compose down
```

## API 사용 예시

### Health Check

```powershell
Invoke-RestMethod http://localhost:8000
```

```powershell
Invoke-RestMethod http://localhost:8000/health
```

응답 예시:

```json
{
  "status": "ok",
  "service": "service-agent"
}
```

### 질문 요청

브라우저 또는 GET 방식으로 간단히 확인:

```text
http://localhost:8000/ask?question=이%20교육과정은%20총%20몇%20시간인가요?
```

PowerShell GET 예시:

```powershell
Invoke-RestMethod "http://localhost:8000/ask?question=이 교육과정은 총 몇 시간인가요?"
```

POST 예시:

```powershell
Invoke-RestMethod http://localhost:8000/ask `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"question":"이 교육과정은 총 몇 시간인가요?"}'
```

응답 예시:

```json
{
  "question": "이 교육과정은 총 몇 시간인가요?",
  "answer": "이 교육과정은 총 320시간 과정입니다."
}
```

## 테스트케이스 파일 형식

테스트케이스는 JSON 또는 CSV로 업로드할 수 있습니다.

필수/권장 필드:

```json
{
  "case_id": "TC-001",
  "category": "정확성",
  "test_type": "Happy",
  "user_question": "이 교육과정은 총 몇 시간인가요?",
  "expected_keyword": "320시간",
  "expected_policy": "정확한 시간 안내"
}
```

## 지식 DB 관리

지원 파일:

- `.txt`
- `.md`
- `.docx`
- `.pdf`

지식 DB 관리 화면에서 업로드된 문서를 선택하면 파일 내용을 미리볼 수 있고, 검색 질문을 입력해 ChromaDB 검색 결과를 확인할 수 있습니다.

동작 방식:

```text
1. 업로드 파일 저장
2. 인덱스 재구축
3. ChromaDB 검색 결과를 챗봇 답변에 우선 사용
4. ChromaDB 사용 불가 시 업로드 문서 직접 검색으로 대체
5. 검색 결과가 없으면 기본 정책 정보로 답변
```

ChromaDB 저장 위치:

```text
data/chroma/
```

## 테스트 실행 산출물

테스트 실행 시 실행별 폴더가 생성됩니다.

```text
reports/test_runs/RUN-YYYYMMDDHHMMSS/
  execution.log
  run_manifest.json
  dashboard_snapshot.json
  inputs/
  reports/
    evaluation_result.json
    evaluation_result.csv
    final_quality_report.md
    rag_off_evaluation_result.json
    rag_off_evaluation_result.csv
```

`evaluation_result.*`는 RAG ON 평가 결과이고, `rag_off_evaluation_result.*`는 지식 검색을 끈 RAG OFF 평가 결과입니다. 실행결과 상세의 고도화 지표에서 RAG ON/OFF 비교를 확인할 수 있습니다.

## 자주 발생하는 문제

### `Client.__init__() got an unexpected keyword argument 'proxies'`

`openai`와 `httpx` 버전 호환 문제입니다.

현재 프로젝트에서는 아래 조합을 사용합니다.

```text
openai==1.40.0
httpx==0.27.2
```

### DOCX/PDF 미리보기가 안 보이는 경우

아래 패키지가 설치되어 있어야 합니다.

```text
python-docx==1.1.2
pypdf==4.3.1
```

### ChromaDB 설치 또는 빌드가 오래 걸리는 경우

`chromadb` 의존성이 추가되어 Docker 빌드 시간이 늘어날 수 있습니다. 빌드 후 지식 DB 관리 화면에서 `인덱스 재구축`을 실행하면 `data/chroma/`에 검색 인덱스가 생성됩니다.

### Streamlit 프로세스 종료

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.CommandLine -match 'streamlit' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## 현재 보강 가능 항목

- ChromaDB 검색 품질 점수 산정 고도화
- RAG ON/OFF 비교 리포트 시각화 강화
- k6 실행 환경의 Docker 내장화
- Jira 결함 등록 템플릿 세분화
- 대시보드 UI 테스트 자동화
