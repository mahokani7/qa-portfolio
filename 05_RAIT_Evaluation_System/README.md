# RaiT 품질 평가 시스템

AI 응답 품질을 R·E·U·S·T·A·C·P(관련성·적합성·이해도·안전성·표현성·정확성·일관성·지속성) 8개 지표로 평가하고, 도메인별 정책(기준점·과락 조건)에 따라 서비스 배포 가능 여부(PASS/FAIL)를 판정하는 교육용 품질관리 도구입니다.

**왜 필요한가**: "좋은 응답"이라는 판단은 사람마다 기준이 달라 재현이 안 됩니다. 모호한 판단을 8개의 측정 가능한 축으로 나누고, 도메인(고위험 금융/일반 등)마다 다른 기준점·가중치·과락 조건을 정책으로 분리해 반복 가능한 품질 판정을 만드는 것이 목표입니다.

## QA SUMMARY

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | 개인 프로젝트 |
| 내 역할 | 지표 체계부터 계산 로직까지 단독 설계·구현 |
| 테스트 범위 | 별도 pytest 스위트 없음 — Mock LLM Judge로 파이프라인 전체 실행 검증, 4가지 집계 방식×3개 도메인 정책 조합 확인 |
| 자동화 도구 | Mock LLM Judge(`use_mock=True`), `src/main.py`(실패 시 종료 코드 1) |
| 주요 검증 | 도메인별 정책이 서로 다른 PASS/FAIL 판정을 내는지 확인 |
| 주요 결함 | 설정 로더가 정책 파일을 상대경로로 찾다 못 찾으면, 오류 없이 기본 가중치(전부 1.0)로 조용히 넘어가 도메인별 가중치(예: 고위험 금융 안전성 2.0)가 소리 없이 사라지는 채점 결함 |
| 개선 결과 | 설정 경로를 절대경로로 고정하고, 설정을 못 찾으면 즉시 `FileNotFoundError`를 발생시키도록 수정 — 조용한 실패 대신 실패를 드러내는 설계로 변경 |
| 최종 판정 | **PASS**(Mock 기준) — 실제 LLM 대량 채점은 이 프로젝트에서 수행하지 않았습니다 |

## Project Type

개인 프로젝트 — 지표 체계부터 계산 로직까지 단독 설계·구현

## My Role

- 8축 지표 체계 정의 및 축별 판정 기준(루브릭) 수립
- Judge 프롬프트(`src/runner/llm_judge.py`) 설계 — 축별 점수+근거를 JSON으로 반환
- 계산 엔진(`src/engine/calculator.py`, `src/engine/filter.py`) 구현 — simple/weight/cutoff/hybrid 4가지 집계 방식
- 도메인별 정책(`config/policy_config.json`) 설계 — 기준점·가중치·과락 조건
- Streamlit 대시보드(`app/app.py`) 구현
- Mock LLM Judge로 파이프라인 전체 실행 검증(별도 pytest 스위트는 없음)

## 📌 채용담당자용 핵심 문서

- [EXPLAIN.md](EXPLAIN.md) — 8축 지표 정의와 코드 흐름 설명
- [config/policy_config.json](config/policy_config.json) — 도메인별 실제 정책(기준점·가중치·과락 조건)
- 별도의 테스트 결과·품질 보고서 문서는 없습니다(아래 QA 관점의 핵심 참고)

## QA 관점의 핵심

- **무엇을 검증했는가**: 사람이 "좋은 응답"을 그때그때 임의로 판단하지 않고, R·E·U·S·T·A·C·P 8개 축을 정의해 같은 기준으로 반복 평가할 수 있는지
- **왜 검증했는가**: 채점 기준이 사람마다 다르면 재현이 안 되고, 도메인마다(고위험 금융 vs 일반) 요구되는 기준점·가중치도 다르기 때문
- **PASS/FAIL 기준**: 도메인별 정책(`config/policy_config.json`)의 기준점·과락 조건에 따라 simple/weight/cutoff/hybrid 4가지 집계 방식으로 판정
- **발견한 문제**: 정책 설정 파일을 상대경로로 찾을 때 실행 위치(CWD)에 따라 못 찾으면, 오류 없이 기본 가중치(전부 1.0)로 조용히 넘어가 도메인별 가중치가 소리 없이 사라지는 채점 결함
- **어떻게 분석했는가**: `high_risk_finance` 도메인의 안전성·정확성 가중치 2.0이 조용히 1.0으로 대체되는 것을 코드 추적으로 확인(아래 설계 노트 참고)
- **재검증**: 설정 경로를 절대경로로 고정하고, 설정을 못 찾으면 즉시 `FileNotFoundError`를 발생시키도록 수정 — Mock LLM Judge로 파이프라인 재실행해 확인. 실제 LLM 대량 채점(pytest 스위트)은 이 프로젝트에서 수행하지 않았다는 점은 그대로 밝혀둡니다

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

정책 설정 파일(`config/policy_config.json`)을 상대경로로 찾으면 실행 위치(CWD)에 따라 못 찾을 수 있습니다. 이때 흔한 실수는 "설정을 못 찾으면 기본값으로 채점 진행"인데, 이렇게 하면 `high_risk_finance` 도메인의 `안전성(S)·정확성(A)` 가중치 2.0이 조용히 전부 1.0으로 대체되어 **오류 없이 점수만 달라집니다**. 이 프로젝트는 그 대신:

- 설정 경로를 `__file__` 기준 절대경로로 고정해 CWD에 영향받지 않게 하고
- 설정 파일이 없으면 기본값을 만들어 넘어가지 않고 즉시 `FileNotFoundError`를 발생시킵니다

정답을 못 구했을 때 "그럴듯한 기본값"으로 조용히 넘어가는 대신 실패를 드러내는 편이, 채점 시스템에서는 더 안전하다는 판단입니다.

## 참고

- 코드 흐름을 초심자 눈높이로 설명한 문서: [EXPLAIN.md](EXPLAIN.md)
