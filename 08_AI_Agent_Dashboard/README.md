# AI Agent 운영·모니터링 대시보드

AI Agent(챗봇) API를 FastAPI로 서비스하고, Streamlit 대시보드에서 서비스 상태·질문 테스트·로그 분석·기능 테스트·성능 테스트 결과를 한눈에 확인하는 실습 프로젝트입니다. 02번(AI 품질·운영 모니터링 플랫폼)의 축약 원형으로, 외부 API 키 없이 **완전히 로컬 mock으로 동작**합니다.

## 주요 기능

Streamlit 대시보드에서 아래 5가지를 확인할 수 있습니다.

| 탭 | 확인 내용 |
|---|---|
| 서비스 상태 | API 정상 여부, 전체 요청 수, 오류율 |
| AI Agent 질문 | 정상·오류·느린 응답 재현 |
| 로그 분석 | INFO·ERROR 로그와 오류 내용 |
| 기능 테스트 | 테스트 케이스별 PASS·FAIL |
| 성능 테스트 | 평균 응답시간, P95, 오류율, 최종 적합 여부 |

```text
사용자 → Streamlit 화면 → API 호출 → FastAPI 서버 → AI Agent(모의 응답 로직) → 결과 반환
```

- k6로 FastAPI 서버에 부하를 보내 성능 테스트
- Docker Compose로 Prometheus·Grafana를 묶어 실행(운영 모니터링)

## 프로젝트 구조

```text
.
├─ app.py                # FastAPI 엔트리포인트 (/health, /ask, /metrics)
├─ agent_service.py       # AI Agent 모의 응답 로직 (외부 API 불필요)
├─ logger_config.py       # 로깅 설정
├─ metrics.py             # Prometheus 지표 정의
├─ streamlit_app.py       # Streamlit 대시보드(5탭 구성)
├─ dashboard.py           # 대시보드 확장판(k6/Prometheus/Grafana 링크 포함)
├─ tests/
│  ├─ run_tests.py         # 실행 중인 API에 대한 기능 테스트(HTTP 호출)
│  └─ test_cases.json
├─ performance/
│  ├─ k6_test.js           # k6 부하 테스트
│  └─ lifecycle_test.js
├─ docker-compose.yml      # Prometheus + Grafana
└─ requirements.txt
```

## 준비 사항

- Python 3.10+
- (선택) Docker Desktop, k6 — Prometheus/Grafana/부하테스트 시에만 필요

## 설치 및 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

### 1) FastAPI 서버 실행

```powershell
py -m uvicorn app:app --host 127.0.0.1 --port 8001
```

접속 주소: **http://127.0.0.1:8001** (`/health`, `/ask?question=...`, `/metrics`)

### 2) Streamlit 대시보드 실행 (별도 터미널)

```powershell
streamlit run streamlit_app.py
```

브라우저에서 **http://localhost:8501** 접속. `streamlit_app.py`는 API 주소로 `http://127.0.0.1:8001`을 사용하므로 반드시 1)의 서버가 먼저 떠 있어야 합니다.

### 3) 기능 테스트 실행 (서버가 떠 있는 상태에서)

```powershell
py tests\run_tests.py
```

결과는 `tests/test_result.json`에 저장됩니다. (검증 완료: 4/4 PASS)

### 4) 성능 테스트 (선택, k6 필요)

```powershell
k6 run performance\k6_test.js
```

### 5) Docker Compose로 Prometheus + Grafana 실행 (선택)

```powershell
docker compose up -d
```

| 서비스 | 주소 |
|---|---|
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## 참고

- `agent_service.py`는 키워드 기반 모의 응답만 반환하므로 `OPENAI_API_KEY` 없이도 전체 흐름(요청 → 응답 → 지표 수집 → 테스트)이 동작합니다.
- 의도적 오류·지연 재현: 질문에 "오류"가 들어가면 500 에러, "느리게"/"천천히"가 들어가면 5초 지연 응답을 반환합니다(장애 시뮬레이션용).
