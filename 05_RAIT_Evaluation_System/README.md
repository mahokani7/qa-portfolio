# RaiT 품질 평가 시스템

AI 응답 품질을 R·E·U·S·T·A·C·P(관련성·적합성·이해도·안전성·표현성·정확성·일관성·지속성) 8개 지표로 평가하고, 도메인별 정책(기준점·과락 조건)에 따라 서비스 배포 가능 여부(PASS/FAIL)를 판정하는 교육용 품질관리 도구입니다.

## Project Type

개인 프로젝트 — 지표 체계부터 계산 로직까지 단독 설계·구현

## My Role

- 8축 지표 체계 정의 및 축별 판정 기준(루브릭) 수립
- Judge 프롬프트(`src/runner/llm_judge.py`) 설계 — 축별 점수+근거를 JSON으로 반환
- 계산 엔진(`src/engine/calculator.py`, `src/engine/filter.py`) 구현 — simple/weight/cutoff/hybrid 4가지 집계 방식
- 도메인별 정책(`config/policy_config.json`) 설계 — 기준점·가중치·과락 조건
- Streamlit 대시보드(`app/app.py`) 구현
- Mock LLM Judge로 파이프라인 전체 실행 검증(별도 pytest 스위트는 없음)

## 주요 기능

- Streamlit 대시보드에서 8개 지표 점수를 슬라이더로 직접 조정하며 실시간 판정 확인
- `simple`(단순 평균) / `weight`(가중 평균) / `cutoff`(과락 기준) / `hybrid`(가중치+과락) 4가지 계산 방식
- `default_pilot` / `high_risk_finance` / `low_risk_entertainment` 등 도메인별 정책 프로필
- CLI 자동 평가 파이프라인(`src/main.py`) — 배포 가능 여부에 따라 종료 코드 반환(CI/CD 연동 가능)
- LLM Judge는 `use_mock=True`로 기본 동작하여 API 키 없이도 파이프라인 검증 가능

## 프로젝트 구조

```text
.
├─ app/
│  └─ app.py              # Streamlit 웹 대시보드(계기판)
├─ src/
│  ├─ main.py              # 자동 평가 파이프라인(엔진) — CI/CD용
│  ├─ runner/
│  │  ├─ llm_judge.py       # LLM Judge(점수 채점, mock 지원)
│  │  └─ agent_caller.py
│  ├─ engine/
│  │  ├─ calculator.py      # 점수 계산기
│  │  └─ filter.py          # 합격/불합격 심사관
│  └─ utils/
│     ├─ config_loader.py   # 정책 로더
│     └─ logger.py
├─ config/
│  └─ policy_config.json    # 평가 규정집(기준점·가중치·과락 조건)
├─ data/
│  └─ test_cases.json       # 테스트 데이터
├─ EXPLAIN.md               # 코드 흐름 상세 설명
└─ requirements.txt
```

`app.py`는 교육용·시각화용(사람이 점수를 직접 조정), `main.py`는 자동화·CI/CD용(테스트 케이스를 읽어 자동 평가, 실패 시 `sys.exit(1)`)입니다.

## 준비 사항

- Python 3.10+
- (선택) OpenAI API 키 — 기본은 mock 모드로 동작하므로 필수는 아님

## 설치 및 실행

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 1) 웹 대시보드 실행

```powershell
streamlit run app\app.py
```

브라우저에서 **http://localhost:8501** 접속 후 사이드바에서 정책·계산 방식을 고른 뒤 8개 지표 슬라이더를 조정하면 PASS/FAIL 판정을 바로 확인할 수 있습니다.

### 2) 자동 평가 파이프라인 실행 (별도 터미널)

```powershell
py src\main.py
```

`data/test_cases.json`의 케이스를 순회하며 채점 → 계산 → 판정을 수행하고, 하나라도 Fail이면 종료 코드 1을 반환합니다(배포 게이트로 활용 가능).

## 환경변수

| 변수 | 필수 여부 | 설명 |
|---|---:|---|
| `OPENAI_API_KEY` | 선택 | `LLMJudge(use_mock=False)`로 실제 LLM 채점을 쓸 때만 필요. 기본 mock 모드에서는 불필요 |

## 설계 노트 — 조용한 실패 방지 (`src/utils/config_loader.py`)

정책 설정 파일(`config/policy_config.json`)을 상대경로로 찾으면 실행 위치(CWD)에 따라 못 찾을 수 있습니다. 이때 흔한 실수는 "설정을 못 찾으면 기본값으로 채점 진행"인데, 이렇게 하면 `high_risk_finance` 도메인의 `안전성(S)·달성도(A)` 가중치 2.0이 조용히 전부 1.0으로 대체되어 **오류 없이 점수만 달라집니다**. 이 프로젝트는 그 대신:

- 설정 경로를 `__file__` 기준 절대경로로 고정해 CWD에 영향받지 않게 하고
- 설정 파일이 없으면 기본값을 만들어 넘어가지 않고 즉시 `FileNotFoundError`를 발생시킵니다

정답을 못 구했을 때 "그럴듯한 기본값"으로 조용히 넘어가는 대신 실패를 드러내는 편이, 채점 시스템에서는 더 안전하다는 판단입니다.

## 참고

- 코드 흐름을 초심자 눈높이로 설명한 문서: [EXPLAIN.md](EXPLAIN.md)
