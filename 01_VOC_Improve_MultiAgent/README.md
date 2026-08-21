# VOC Improve 프로젝트

VOC(Voice of Customer) 분석 시스템 - 고객 불만사항 분석 및 정책 개선안 생성

**왜 필요한가**: 멀티에이전트가 VOC를 분업 처리하면, 산출물 품질을 사람이 매번 검수해야 하는 병목이 생깁니다. 이 프로젝트는 내부 파이프라인 채점과는 별도로 독립 LLM Judge를 2차 검수 레이어로 붙여, "자동 처리 결과를 그대로 배포해도 되는가"를 확인 가능하게 만듭니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 팀 프로젝트(4인) |
| 내 역할 | 테스트 시나리오 설계, 평가 루브릭 설계, Judge 프롬프트 검증, 독립 Judge 결과 검증, 발표·시연 |
| 테스트 범위 | `tests/` unittest 98건, `quality_diagnosis/` pytest 32건, 레드팀 20개 시나리오, 오프라인/라이브 E2E |
| 자동화 도구 | unittest, pytest, `quality_gate.py`(CI 스타일 배포 게이트) |
| 주요 검증 | 6-Agent 파이프라인 동작, 독립 LLM Judge 채점, "자동테스트 PASS + 배포게이트 3중 검증" 조합 |
| 주요 결함 | 라이브 E2E 18건 중 내부 파이프라인이 100점(배포 가능) 판정한 케이스에서, 독립 Judge는 정책구체성 축을 0점으로 재평가(18건 중 7건에서 이 축이 최저점) |
| 개선 결과 | 이 간극을 근거로 최종 판정을 배포 보류로 확정하고, 다음 개선 과제(정책 구체성 축을 프롬프트 단계에서 보강)를 문서화 |
| 최종 판정 | **HOLD** — pytest 32건은 전부 PASS했지만 독립 Judge 평균 81.2점이 배포 기준(95점) 미달 |

## Project Type

팀 프로젝트(4인) — 멀티에이전트 파이프라인·AWS 인프라·리포팅 대시보드는 팀원이 담당했습니다.

## My Role

- 테스트 시나리오 설계, 평가 루브릭(LLM Judge 채점 기준) 설계
- Judge 프롬프트 검증, 독립 LLM Judge 채점 결과 검증
- 최종 발표 스크립트 작성 및 시연

팀원별 역할 상세는 [mahokani7.github.io/qa/project-01.html](https://mahokani7.github.io/qa/project-01.html) 참고.

## 📌 포트폴리오 핵심 문서

이 프로젝트에서 제가 수행한 역할과 QA 결과를 빠르게 확인할 수 있는 문서입니다.

- [PRD](docs/PRD_VOC_Improve_QA_Control_Center_20260716.md) — 요구사항 정의
- [최종 발표자료](docs/FINAL_PRESENTATION.pdf) ([PPTX](docs/FINAL_PRESENTATION.pptx)) — 11장, 자동테스트 PASS와 독립 Judge 판정이 갈린 지점을 중심으로 구성
- [녹화 시나리오](docs/VOC_WEB_ANALYSIS_RECORDING_SCENARIO_20260805.md) — 고객 문의 입력→6-Agent 처리→독립 Judge 채점→배포 판단까지 데모 스크립트
- [품질 점수 리포트](aws_upload/qa_evidence/quality_score_report.md) · [배포 판단 문서](aws_upload/qa_evidence/deployment_decision.md) · [pytest 실행 결과](aws_upload/qa_evidence/pytest_result.txt) — QA 관점의 핵심(아래) 판단에 쓰인 실측 증적

## QA 관점의 핵심

- **무엇을 검증했는가**: 6-Agent 파이프라인이 만든 정책 개선안을, 내부 파이프라인 채점과는 독립된 LLM Judge로 2차 검수해도 같은 결론이 나오는가
- **왜 검증했는가**: 자동 테스트 PASS만으로 배포를 승인하면, 파이프라인 자체 편향(자기 채점)을 놓칠 수 있기 때문
- **PASS/FAIL 기준**: `quality_gate.py`가 (1) 자동 품질 테스트 전수 통과 (2) OWASP 레드팀 20개 시나리오 통과 (3) 오프라인 E2E 평균이 배포 기준(95점) 이상 — 셋 다 충족해야 PASS, 하나라도 미달이면 HOLD
- **발견한 문제**: pytest 32/32 PASS했지만, 라이브 E2E 18건 중 내부 파이프라인이 100점(배포 가능) 판정한 케이스를 독립 Judge는 정책구체성 축에서 0점으로 재평가(18건 중 7건에서 이 축이 최저점) — [`quality_score_report.md`](aws_upload/qa_evidence/quality_score_report.md)
- **어떻게 분석했는가**: 항목별 Judge 점수(정확성 85%·요약충실성 82%·정책구체성 74%·유용성 76%·안전성 91%)를 배점별로 분해해 정책구체성이 유일한 저점 축임을 특정 — [`deployment_decision.md`](aws_upload/qa_evidence/deployment_decision.md)
- **재검증**: Judge 평균 81.2점이 배포 기준 95점에 미달함을 근거로 최종 판정을 배포 보류(HOLD)로 확정, 정책 구체성 축을 프롬프트 단계에서 보강하는 것을 다음 개선 과제로 문서화

---

## 🔧 Technical Reference

아래는 실행 방법·아키텍처·코드 구조 등 기술적 상세입니다. 프로젝트 핵심 내용은 위 요약과 문서에서 먼저 확인할 수 있습니다.

## 프로젝트 구조

```
VOC_Improve/
│
├── main.py                    # MCP 서버 메인 진입점
├── run_all.py                # (대안) 6개 서버를 단일 프로세스로 동시 기동하는 런처
├── web_app.py                # (선택) 브라우저에서 테스트하는 로컬 웹 UI
├── grpc_server.py            # A2A 오케스트레이터 + 6개 에이전트 실행 관리자(python grpc_server.py)
├── voc.proto                 # Protocol Buffers 정의 파일
├── voc_pb2.py                # Protocol Buffers 생성 파일 (Python)
├── voc_pb2_grpc.py           # gRPC 서비스 생성 파일 (Python)
├── voc.csv                   # VOC 데이터 파일
├── pyproject.toml            # 프로젝트 설정 파일
├── README.md                 # 프로젝트 문서
│
├── agents/                   # AI 에이전트 모듈
│   ├── __init__.py
│   ├── interpreter.py       # 자연어 질의 해석 에이전트
│   ├── retriever.py         # VOC 데이터 검색 에이전트
│   ├── summarizer.py        # VOC 요약 생성 에이전트
│   ├── improver.py          # 정책 개선안 생성 에이전트
│   ├── evaluator.py         # 결과 평가 에이전트
│   └── critic.py            # 결과 비판/개선 에이전트
│
├── llm_wrappers/            # LLM API 래퍼
│   ├── __init__.py
│   ├── openai_chat.py       # OpenAI API 래퍼
│   └── anthropic_chat.py    # Anthropic API 래퍼
│
└── utils/                   # 유틸리티 모듈
    ├── __init__.py
    ├── settings.py          # 설정 관리
    ├── tools.py             # MCP 도구 정의
    ├── json_utils.py        # JSON 처리 유틸리티
    └── utils.py             # 기타 유틸리티 함수
```

## 주요 기능

- **자연어 질의 분석**: 자연어 질의를 통한 VOC 분석 요청 처리
- **VOC 요약 생성**: 고객 불만사항을 분석하여 요약 생성
- **정책 개선안 생성**: VOC 분석 결과를 바탕으로 정책 개선안 제시
- **gRPC 통신**: A2A 시스템과의 gRPC 기반 통신
- **MCP 서버**: Claude Desktop/Cursor와의 통신을 위한 MCP 프로토콜 지원

## 기술 스택

- Python 3.10+
- gRPC
- Protocol Buffers
- OpenAI API / Anthropic API
- MCP (Model Context Protocol)

## 안전 설정과 테스트

- gRPC 서버는 기본적으로 `127.0.0.1:6001~6006`에만 바인딩됩니다.
- CSV는 프로젝트 폴더 내부만 허용됩니다. 추가 폴더는 `A2A_ALLOWED_CSV_DIRS`로 지정합니다.
- 전체 요청 제한은 `A2A_TOTAL_TIMEOUT`, 단계별 제한은 `A2A_STAGE_TIMEOUT`으로 조정합니다.
- 환경변수 예시는 `.env.example`을 참고합니다.
- 자동 테스트: `python -m unittest discover -s tests -v`

원격 바인딩은 기본 차단됩니다. 인증과 TLS가 적용된 별도 프록시가 준비된 경우에만
`A2A_ALLOW_REMOTE_BIND=1`을 사용하세요.

### 입력 방어 (`utils/security.py`, `utils/validation.py`)

VOC 원문은 사용자가 통제할 수 없는 외부 입력이라는 전제로 파이프라인에 들어가기 전에 처리합니다.

- **PII 마스킹**: 이메일·전화번호·주민번호·카드번호 패턴을 자리표시자로 치환
- **프롬프트 인젝션 방어**: "이전 지시 무시해" 류 명령형 문자열을 탐지해 `[차단된 프롬프트 지시]`로 무력화
- **위험 명령어 탐지**: `os.system`·`subprocess`·`rm -rf` 등 실행형 문자열을 데이터로만 취급하도록 치환
- **API 키 redaction** (`utils/api_resilience.py`): 공급자 오류 메시지에 키가 섞여 나오는 경우 로그·화면에 출력되기 전에 정규식으로 제거
- **경로 접근 제한**: CSV 입력은 프로젝트 루트 하위로 제한(환경변수로만 명시적 확장 가능) — 경로 탈출 방지

### 품질 게이트 — 테스트 통과와 배포 승인은 다른 기준 (`quality_diagnosis/quality_gate.py`)

`run_quality_gate()`는 서로 독립적인 3개 검증을 각각 실행하고, **셋 다 PASS해야만** 최종 판정이 `PASS`이고 하나라도 실패하면 `HOLD`를 반환합니다.

1. 자동 품질 테스트(unittest/pytest) 전수 통과 여부
2. OWASP 레드팀 20개 시나리오(프롬프트 공격·개인정보·권한·비용 공격) 통과 여부
3. 도메인별 오프라인 E2E 평균 점수가 배포 기준(`load_deployment_config()`, 기본 배포 임계값) 이상인지

이 저장소 전체에서 강조하는 "자동 테스트 PASS가 곧 배포 승인은 아니다"는 이 스크립트가 실제로 구현하는 로직입니다.

## 아키텍처 (실행 흐름)

MCP 도구 호출은 **오케스트레이터(`grpc_server.VOCGRPCRuntime`)** 를 거쳐
**`Summarizer.RunPipeline`** 이라는 단일 경로로 처리됩니다.

```
MCP 클라이언트 (Claude Desktop/Cursor)
        │  main.py → utils/tools.py (FastMCP)
        ▼
grpc_server.VOCGRPCRuntime (오케스트레이터)
        │  ① Interpreter.ParseQuestion  → 질의를 intent로 해석
        ▼  ② Summarizer.RunPipeline     → 아래 순서로 각 에이전트를 직접 호출
   Retriever(6002) → Summarizer 요약후보 → Evaluator(6004)
   → Critic(6005, 요약검토) → [필요시 요약 refine]
   → Improver(6006, 정책생성 → Critic 정책검토 → 필요시 refine)
```

각 에이전트는 자기 역할만 수행하는 순수 서비스이며(하위 에이전트를 임의로
연쇄 호출하지 않음), 파이프라인 순서는 오케스트레이터가 단일하게 제어합니다.

## 실행 방법

### 1) 의존성 설치

의존성은 `pyproject.toml`에 선언돼 있으므로, 프로젝트 루트에서 한 번에 설치합니다.

```bash
# 가상환경 활성화 후 (Python 3.10+)
pip install -e .

# voc.proto를 다시 컴파일해야 한다면(개발용) grpcio-tools도 함께 설치
pip install -e ".[dev]"
```

### 2) API 키 설정

환경변수로 설정하거나, 프로젝트 루트에 `.env` 파일을 만듭니다.

```bash
# 예: .env 파일
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# (선택) 모델/데이터 경로 오버라이드
# A2A_MODEL_SUMMARY=gpt-4o-mini
# A2A_MODEL_POLICY=claude-sonnet-4-20250514
# A2A_VOC_CSV=/path/to/voc.csv
```

- `OPENAI_API_KEY` — 질의 해석·요약·평가·비평에 필요 (없으면 서버 구동 실패)
- `ANTHROPIC_API_KEY` — 정책 개선안 생성에 필요

API 키나 결제 상태에 문제가 있으면 웹은 공급자 오류 원문이나 키 일부를 노출하지 않고
다음 오류 코드와 복구 안내를 표시합니다.

- `API_AUTHENTICATION_FAILED`(401): `.env`의 키를 새 키로 교체하고 `grpc_server.py` 재시작
- `API_CREDIT_EXHAUSTED`(402): 해당 공급자의 크레딧·결제 한도 확인
- `API_RATE_LIMITED`(429): 잠시 후 재시도하고 배치 동시 실행을 1건으로 축소

`.env`를 변경해도 실행 중인 Agent 프로세스에는 자동 반영되지 않으므로, 키를 바꾼 뒤에는
반드시 `grpc_server.py`를 종료하고 다시 실행합니다.

### 3) 6개 에이전트 서버 기동 (한 번에)

```bash
python grpc_server.py
```

- `grpc_server.py`의 통합 실행 관리자가 6개 에이전트를 **각각 별도 프로세스**
  (`python -m agents.XXX`)로 기동하고, 각 포트의 준비 상태를 확인한 뒤,
  `Ctrl+C` 를 누를 때까지 유지합니다.
- Interpreter(6001), Retriever(6002), Summarizer(6003), Evaluator(6004),
  Critic(6005), Improver(6006).
- 6개 포트가 모두 정상 gRPC 응답 중이면 중복 기동 오류로 처리하지 않고
  `이미 정상 실행 중` 안내 후 종료 코드 0으로 끝납니다. 이 경우 기존 에이전트를
  그대로 사용하고 별도 터미널에서 `python web_app.py`만 실행하면 됩니다.
- 일부 포트만 남아 있거나 gRPC 준비 확인에 실패한 경우에만 충돌 오류로 차단합니다.
- 종료: `Ctrl+C` (모든 자식 프로세스 정상 종료)
- 실행 로그 예시:
  ```
  | INFO | __main__ | 6개 VOC gRPC 에이전트 시작을 요청합니다.
  | INFO | __main__ | Interpreter 시작 | command=... -m agents.interpreter | endpoint=localhost:6001
  ...
  | INFO | __main__ | 6개 VOC gRPC 에이전트가 모두 준비되었습니다.
  | INFO | __main__ | 통합 gRPC 실행 관리자가 동작 중입니다. 종료하려면 Ctrl+C를 누르세요.
  ```

> 💡 **대안 — 단일 프로세스 런처(`run_all.py`)**
> `python run_all.py` 는 6개 서버를 하나의 asyncio 프로세스에서 동시에 띄웁니다.
> 더 가볍지만 프로세스 격리는 없습니다. 개별 포트 바인딩은 `INTERPRETER_BIND`,
> `RETRIEVER_BIND`, `SUMMARIZER_BIND`, `EVALUATOR_BIND`, `CRITIC_BIND`,
> `IMPROVER_BIND` 환경변수로 조정할 수 있습니다.

> ⚠️ 이 서버들이 모두 떠 있어야 파이프라인이 동작합니다. 하나라도 없으면
> 오케스트레이터의 gRPC 호출이 타임아웃/실패합니다.

### 4) MCP 서버 실행 (별도 터미널)

`run_all.py`가 실행 중인 상태에서, 다른 터미널에서 MCP 서버를 띄웁니다.

```bash
python main.py
```

Claude Desktop/Cursor의 MCP 설정(`.vscode/mcp.json` 등)에서 이 서버를 등록하면
`analyze_voc_nl_v2`, `analyze_voc`, `summarize_voc`, `policy_from_summary`,
`health_check` 도구를 사용할 수 있습니다.

### (선택) 브라우저에서 테스트하기

MCP 클라이언트(Claude Desktop/Cursor) 없이 브라우저에서 바로 테스트하고 싶다면
`web_app.py`(로컬 웹 UI)를 사용합니다.

```bash
# 1) 웹 UI 의존성 설치 (최초 1회)
pip install -e ".[web]"

# 2) 6개 에이전트 기동 (터미널 1)
python grpc_server.py

# 3) 웹 서버 실행 (터미널 2)
python web_app.py
```

그런 다음 브라우저에서 **http://127.0.0.1:8000** 에 접속해 질문을 입력하고
[분석 실행]을 누르면 요약과 정책 개선안이 표시됩니다.
(포트 변경: `WEB_PORT` 환경변수)

배치 테스트 탭에서는 **이커머스/보험** 도메인을 선택할 수 있습니다. 도메인을 바꾸면
해당 CSV와 JSONL 기대 결과가 자동으로 로드되며 결과 파일명에도 도메인이 표시됩니다.

- 이커머스: `voc.csv` 30건 + `test_cases.txt` 18건
- 보험: `data/voc_insurance.csv` 50건 + `test_cases_insurance.jsonl` 15건

### 웹 품질 운영·보고서 탭

기존 CLI 품질 기능도 브라우저의 **품질 운영·보고서** 탭에서 실행할 수 있습니다.

- 6개 gRPC 에이전트와 API 키 설정 여부 확인(키 값 자체는 표시하지 않음)
- 자동 품질 테스트, 장애 진단, 결정적 모델 오프라인 E2E 실행
- 이커머스/보험 라이브 E2E 전체·일부·case_id 선택 실행
- 기준 E2E와 선택 재시험 보고서 통합
- Deterministic/OpenAI/Anthropic 독립 Judge 실행
- 배포 기준 점수를 화면에서 조회·변경·저장(저장값이 없으면 기본 95점)
- 라이브 E2E와 Judge가 모두 기준 점수 이상인지 현재 배포 결과로 즉시 표시
- E2E·Judge 증적을 선택해 최종 배포 판단 문서 생성
- JSON·CSV·Markdown·TXT 산출물 목록 확인 및 다운로드

라이브 E2E와 실제 LLM Judge는 API 비용이 발생하므로 화면의 비용 동의 체크박스를
선택한 경우에만 실행됩니다. 동의하지 않은 요청은 서버에서도 거부합니다. 자동 품질
테스트, 장애 진단, Deterministic Judge와 기존 보고서 조회는 외부 LLM 비용이 없습니다.

### QA Control Center 고도화 기능

첫 화면의 사이드바형 QA Control Center에서 다음 기능을 사용할 수 있습니다.

- 실행을 Experiment로 색인: 실행 ID·Git 상태·데이터셋/프롬프트/모델 버전·배포 기준·점수·P95·토큰·비용·결함
- 기준선과 후보 실행 비교: PASS율·점수·Agent별 점수/지연·비용·결함·출력 Diff
- 테스트 케이스 Explorer: 도메인·상태·점수·결함·Agent 필터와 실패 원인 상세
- 6-Agent Trace: 입력/출력·모델·프롬프트 버전·처리시간·토큰/비용·오류/재시도·Refine 전후
- 중요 5개 케이스 3회 반복과 독립 Judge 변동성 분석
- RAG 6대 지표: Context Precision/Recall, Faithfulness, Relevancy, Noise Sensitivity, Citation Coverage
- 사람 검토 상태(대기/검토 중/수정 요청/승인/반려), 사람 점수, Judge 동의, 최종 배포 승인
- OWASP 정렬 Red Team 20종, CI 95점 품질 게이트, P95·비용·HTTP 429 드리프트 알림
- 실행 ID별 증적 묶음, 안전한 텍스트 미리보기, 밝은/어두운 테마와 모바일 접이식 메뉴

웹 권한을 분리하려면 `.env`에 `WEB_VIEWER_TOKEN`, `WEB_REVIEWER_TOKEN`,
`WEB_ADMIN_TOKEN`을 설정합니다. 값을 비워 두면 기존처럼 로컬 개발 모드이며, 실제 토큰
값은 소스·로그·화면에 저장하지 않습니다. 기존 `WEB_OPERATOR_TOKEN`도 admin 권한으로
호환됩니다.

### 웹 발표자료

브라우저에서 **http://127.0.0.1:8000/presentation**을 열면 2026-07-14부터 현재까지의
개발 과정, 아키텍처, 교수님 요구사항 적용, 정량 검증, 성능 개선, 데모 순서와 향후 계획을
슬라이드로 발표할 수 있습니다. 방향키로 이동하고, `N`은 발표자 노트, `F`는 전체화면이며
PDF 인쇄도 지원합니다.

앞으로 모든 기능은 [상시 개발 원칙](docs/개발원칙_발표및웹적용.md)에 따라 웹 UI·웹 API·
검증 결과와 발표 기록을 함께 갱신합니다. 발표의 기준 이력은
[개발 진행 발표 원장](docs/개발진행_발표원장.md)에 누적합니다.

### 테스트 실행 시간

`요약 + 정책` 1건은 Interpreter·Summarizer·Evaluator·Critic·Improver 처리 중 외부
LLM을 최소 6회 호출하고, Critic이 수정을 요구하면 최대 8회 호출합니다. 기존 라이브
18건 보고서의 합산 처리시간은 약 573초였고 건당 평균은 31.8초였습니다.

웹 배치와 오프라인·라이브 E2E는 기본적으로 **동시 2건**을 실행합니다. 기존 측정값을
기준으로 18건 예상시간은 직렬 약 9.5분에서 약 4.9분으로 줄어듭니다. 동시 3건은 더
빠를 수 있지만 계정의 API 사용량 제한에 걸릴 수 있으므로 2건을 권장합니다. 동시 실행은
총 API 호출 수나 비용을 줄이지 않고 대기시간만 줄입니다.

CLI에서도 다음처럼 지정할 수 있습니다.

```bash
python e2e_runner.py --mode live --domain ecommerce --concurrency 2
```

API 오류 때 SDK 재시도가 과도하게 누적되지 않도록 기본 재시도는 1회입니다.
`A2A_API_TIMEOUT`, `A2A_API_MAX_RETRIES`로 조정할 수 있으며 변경 후 gRPC 에이전트를
재시작해야 적용됩니다.

## 18개 품질 케이스 E2E 테스트

일반 실행, 웹 진단 실행, E2E 테스트는 모두 `VOCGRPCRuntime._execute_pipeline`이라는
동일한 파이프라인 함수를 사용합니다. 따라서 진단 화면만 별도로 동작해 실제 실행과
달라지는 문제를 방지합니다.

### 오프라인 E2E — 외부 API·비용 없음

```bash
python e2e_runner.py --mode offline --domain ecommerce

# 보험 도메인
python e2e_runner.py --mode offline --domain insurance `
  --cases test_cases_insurance.jsonl `
  --csv data\voc_insurance.csv
```

- 실제 Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver gRPC 경로 실행
- LLM 응답만 결정적 테스트 대역으로 교체하여 항상 같은 결과로 연결·분기·판정 회귀 검사
- `quality_diagnosis/reports/{domain}_offline_e2e_YYYYMMDD_HHMMSS.json`과 `.csv` 생성
- 결과의 `live_quality_verified`는 `false`: 실제 모델 답변 품질을 검증했다는 의미가 아님

### 라이브 E2E — 실제 OpenAI·Anthropic 품질 확인

먼저 `python grpc_server.py`로 6개 서버를 실행한 뒤 별도 터미널에서 실행합니다.

```bash
python e2e_runner.py --mode live --domain ecommerce

# 보험 도메인
python e2e_runner.py --mode live --domain insurance `
  --cases test_cases_insurance.jsonl `
  --csv data\voc_insurance.csv
```

- `.env`의 `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 필요
- 실제 모델 응답으로 18개 JSONL 케이스 실행
- API 비용, 네트워크 및 모델 응답 변동이 발생할 수 있음
- `quality_diagnosis/reports/{domain}_live_e2e_YYYYMMDD_HHMMSS.json`과 `.csv` 생성
- 실행에 성공한 라이브 보고서만 `live_quality_verified: true`

각 결과에는 PASS/FAIL, 총점, 검색 적합도, 요약의 검색 원문 근거율,
정책 실행 가능성, 개인정보·프롬프트 안전성, 에이전트별 중간 산출물이 포함됩니다.

## QA 교육 예제로서의 검증 범위

이 프로젝트는 **멀티에이전트·gRPC·MCP·LLM 품질평가를 한 번에 경험할 수 있는
중급 QA 실습 예제**입니다. 18개 오프라인 E2E 테스트는 실제 6단계 gRPC 파이프라인의
연결, 검색, 요약 후보 선택, 비평·개선 분기, 보안 처리 및 품질 판정이 재현 가능하게
동작함을 검증합니다.

다만 오프라인 PASS는 실제 상용 LLM의 답변 품질 보증이 아닙니다. 실제 AI 품질은
`--mode live` 결과의 `live_quality_verified`, 케이스별 실패 근거와 품질 지표를 함께
확인해야 합니다. 검색 원문 근거율 또한 어휘 기반 자동 지표이므로, 중요한 정책 결정에는
사람의 사실성·타당성 검토가 추가로 필요합니다.

## 35건 종합 품질평가와 첨부 증적

웹의 **품질 운영·보고서 → 6. 종합 품질평가 첨부 보고서**에서
**35건 종합 보고서 생성**을 누르면 이커머스 18건, 보험 15건, 핵심 결함 회귀 2건을
평가하고 다음 파일을 생성합니다.

- 최종 제출·발표용 PDF
- 브라우저용 HTML, 구조화 XML, 텍스트 TXT, 원본 JSON
- 테스트 추이·점검 범위·결함 상태·잔여 위험 PNG 그래프
- 위 파일과 핵심 원본 증적을 묶은 ZIP

현재 정량 기준선은 초기 33 PASS / 2 FAIL에서 결함 수정 후 최종 35 PASS / 0 FAIL입니다.
이는 정의된 품질평가 범위의 완료 판정입니다. 운영 배포에는 최신 보관 라이브 평가인
**2026-07-16 E2E 90.9점과 독립 Judge 81.2점**을 적용하며, 낮은 81.2점이 배포 기준
95점에 미달하므로 **HOLD**입니다. `90.6 / 89.0`은 2026-07-15 종합보고서의 과거
기준선이며 현재 판정값으로 사용하지 않습니다. 2026-08-03에는 Judge를 재실행하지 않고
7월 16일 결과로 AWS 제출 패키지를 생성했습니다.

공식 품질 실행은 매번 타임스탬프가 붙은 TXT·XML·HTML 증적을 별도로 만들고
`quality_diagnosis/reports/test_execution_history.jsonl`에 실행 이력을 누적합니다.

