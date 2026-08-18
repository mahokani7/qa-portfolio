# AI Agent 품질관리·운영 모니터링 플랫폼

AI Agent의 답변 품질을 평가하고 운영 상태를 모니터링하는 통합 프로젝트입니다. FastAPI 기반 질의 API, RAG 지식 검색, 품질 평가 파이프라인, Streamlit 대시보드, Prometheus/Grafana 모니터링을 제공합니다.

## Project Type

개인 프로젝트 — 기획부터 구현까지 단독 수행

## My Role

- 루브릭(8축 평가 기준·가중치) 설계
- Judge Agent(`app/judge_agent.py`) 구현 — LLM 기반 채점 로직
- Rule-based Agent(`app/rule_based_agent.py`) 구현 — 규칙 기반 1차 검증
- JSON Schema(`app/schemas.py`) 설계 — Judge 출력 구조화
- Streamlit 대시보드(`dashboard/streamlit_app.py`) 구현
- pytest 테스트 18개 파일(정상 케이스·레드팀·회귀 시나리오) 설계·구현
- k6 성능 테스트 설계·실행

## 주요 기능

- FastAPI 기반 AI Agent API (`/health`, `/ask`, `/metrics`)
- OpenAI API와 ChromaDB를 이용한 RAG 지식 검색
- 규칙 검증, 환각 검사, 회귀/레드팀/검색 품질 평가
- pytest 및 커버리지 기반 자동 테스트
- Streamlit 품질 대시보드
- Prometheus/Grafana 운영 모니터링
- Jira 결함 자동 등록(선택 사항)
- Docker Compose 기반 통합 실행

## 프로젝트 구조

```text
.
├─ app/                 # FastAPI 애플리케이션과 AI Agent
├─ dashboard/           # Streamlit 대시보드
├─ data/knowledge/      # 평가 기준과 RAG 원본 문서
├─ monitoring/          # Prometheus/Grafana 설정
├─ performance/         # k6 성능 테스트
├─ quality/             # 품질 평가 파이프라인과 보고서 생성
├─ scripts/             # 보조 스크립트
├─ tests/               # pytest 테스트
├─ docker-compose.yml
├─ Dockerfile
├─ requirements.txt
├─ run_all.ps1          # 로컬 구성요소 실행
└─ run_full.ps1         # Docker 기반 통합 실행
```

## 준비 사항

- Python 3.12
- OpenAI API 키
- 선택: Docker Desktop, k6, Jira 계정

## 로컬 설치 및 실행

PowerShell에서 다음 명령을 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

생성된 `.env` 파일의 `OPENAI_API_KEY` 값을 설정합니다. `.env`는 Git에 포함되지 않습니다.

FastAPI만 실행하려면:

```powershell
uvicorn app.main:app --reload
```

Streamlit 대시보드를 별도로 실행하려면:

```powershell
streamlit run dashboard\streamlit_app.py
```

Windows 통합 실행 스크립트를 사용하려면:

```powershell
.\run_all.ps1
```

Docker 기반 전체 구성을 실행하려면:

```powershell
.\run_full.ps1
```

주요 접속 주소:

| 서비스 | 주소 |
|---|---|
| FastAPI 문서 | http://localhost:8000/docs |
| Streamlit | http://localhost:8501 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## 테스트

```powershell
pytest
```

테스트 결과와 커버리지 파일은 `tests_output/`에 생성되며 Git에는 포함되지 않습니다.

## 품질 평가 모듈 (`quality/`)

LLM Judge 채점 하나에 의존하지 않고, 서로 다른 방식으로 답변 품질을 교차 검증하는 12개 모듈로 구성됩니다.

| 모듈 | 검증 방식 |
|---|---|
| `redteam.py` | 프롬프트 인젝션·탈옥·PII 유도 등 공격 케이스를 주입해 방어율(%) 산출. 정상 질문 대조군으로 과잉 차단도 함께 검사 |
| `pii_scan.py` | 답변에서 전화번호·이메일·주민등록번호·카드번호 정규식 매칭으로 개인정보 노출 검사 |
| `hallucination_check.py` | 답변의 단어가 업로드된 지식 파일(근거 코퍼스)에 실제로 존재하는 비율(지원율)을 계산해 근거 없는 내용(환각) 의심 케이스를 표시 |
| `rag_ablation.py` | 같은 질문을 규칙기반 / RAG OFF / RAG ON 세 방식으로 답변시켜 정답 키워드 포함률을 비교 — "RAG가 정확성을 몇 %p 올렸는가"를 대조군 실험으로 계산(`lift`) |
| `cost_tracker.py` | 토큰 수를 추정해 케이스별 예상 비용(원화 환산 포함) 산출. tiktoken 미사용 추정치라는 한계를 코드·출력 양쪽에 명시 |
| `jira_reporter.py` | 결함 케이스를 Jira 이슈로 자동 등록(선택 기능) |
| `regression.py`, `retrieval_metrics.py`, `coverage_gap.py` 등 | 회귀 검증, 검색 품질 지표, 테스트 커버리지 공백 분석 |

각 모듈은 `python -m quality.<모듈명>`으로 단독 실행할 수 있고, `quality_pipeline.py`가 이를 하나의 파이프라인으로 묶습니다.

## 환경변수

| 변수 | 필수 여부 | 설명 |
|---|---:|---|
| `OPENAI_API_KEY` | 필수 | OpenAI API 인증 키 |
| `JIRA_BASE_URL` | 선택 | Jira 사이트 주소 |
| `JIRA_EMAIL` | 선택 | Jira 계정 이메일 |
| `JIRA_API_TOKEN` | 선택 | Jira API 토큰 |
| `JIRA_PROJECT_KEY` | 선택 | Jira 프로젝트 키 |
| `JIRA_ISSUE_TYPE` | 선택 | 생성할 Jira 이슈 유형(기본값 `Bug`) |
| `PROMETHEUS_URL` | 선택 | Prometheus 주소 |
| `GRAFANA_BASE_URL` | 선택 | Grafana 주소 |

값의 형식은 `.env.example`을 참고하세요. API 키와 토큰이 들어 있는 `.env`는 절대로 커밋하지 마세요.

## GitHub 업로드

처음 업로드하는 방법과 이후 업데이트 절차는 [GITHUB_UPLOAD_GUIDE.md](GITHUB_UPLOAD_GUIDE.md)를 참고하세요.

