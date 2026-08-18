# AI Agent 품질관리·운영 모니터링 플랫폼

AI 기반 소프트웨어 테스터(QA) 및 모니터링 실무 과정의 실습 프로젝트입니다.

교육과정 안내 챗봇을 대상으로 테스트케이스 업로드, 자동 평가, 결과 리포트, 지식 DB 관리, Service Agent API, 운영 모니터링 기능을 구현합니다.

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

현재 테스트 결과:

```text
14 passed
```

현재 테스트는 Service Agent와 FastAPI 핵심 엔드포인트 중심입니다.

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
