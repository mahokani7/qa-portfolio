# 감사 기록 — 수집·검증 상세 내역

`README.md`에서 분리한 상세 기록입니다. 실행 방법이 아니라 **"왜 이렇게 됐는지"**를 다룹니다.

---

## 제외한 항목 (2026-08-05)

> ### ⚠️ 이 아래 번호는 **교육과정 원래 번호**입니다
> 제출본의 `01`~`10`은 빈 번호 없이 새로 매긴 번호이고,
> 제거 목록은 **원본 폴더를 찾아 복원할 때 기준이 되는 원래 번호**를 그대로 뒀습니다.
> **따라서 두 체계의 같은 숫자는 서로 다른 프로젝트를 가리킵니다** —
> 예컨대 제출본 `07`은 RAG 챗봇이지만, 아래 표의 `07`은 제거된 Judge 테스트 자동화 Lab입니다.

### 웹 가동 불가로 제거한 프로그램 8개

CLI 전용이거나 대화형 콘솔이라 **링크를 눌러 볼 화면이 없는** 항목입니다.
코드 품질과 무관한 제거이며, 원본에서 언제든 복원됩니다.

| 원래 번호 | 프로젝트 | 제거 사유 |
|---|---|---|
| 07 | Judge 테스트 자동화 Lab | CLI 전용 — 표준출력과 파일 리포트만 생성 |
| 09 | Agent 라우팅 분류 모델 | CLI 전용 — PNG·CSV·MD 산출 |
| 10 | 오프라인 A/B 배포 판정 | CLI 전용 — 배포판정 보고서 생성 |
| 11 | BERTScore 기준선 회귀 | CLI 전용 — 평가 리포트 생성 |
| 14 | 뉴스 수집 멀티에이전트 | CLI 전용 배치 파이프라인 |
| 15 | LangChain 멀티툴 에이전트 | CLI 전용 + 키 2개 필요 |
| 17 | 수강신청 챗봇 | 대화형 콘솔 — 웹 인터페이스 없음 |
| 18 | LMS QA 챗봇 | 대화형 콘솔 — 웹 인터페이스 없음 |

> 04번(QA 문서 13종)도 웹 가동 대상은 아니지만 **프로그램이 아니라 문서**이고
> QA 채용에서 가장 먼저 읽히는 항목이라 남겼습니다.

### 그 밖에 제외한 항목

| 항목 (원래 번호) | 사유 | 원본 |
|---|---|---|
| 19 · 모바일 초대장 | 애초에 복사되지 않아 폴더가 존재하지 않았음 | `C:\qaeduc2\Mobile_Invitation` |
| 20 · 정적웹 포트폴리오페이지 | **QA 실습물이 아님** — "21년차 IT 기획·PM" 명의의 프리랜서 수주용 소개 페이지라 QA 포지션 지원 서류에서 초점을 흐림 | `C:\qaeduc2\PR1` |

> 두 항목 모두 **원본은 그대로 남아 있습니다.** 웹 퍼블리싱 실습으로 다시 넣고 싶으면 위 경로에서 복사하세요.

---

## 복사 시 제외한 것과 그 이유

| 제외 대상 | 이유 | 복구 방법 |
|---|---|---|
| **`.env` (실제 API 키)** | 유출 방지 — 포트폴리오는 남에게 전달됨 | `copy .env.example .env` 후 본인 키 입력 |
| `venv`, `.venv` | **다른 PC에서 절대 동작 안 함** (절대경로 박힘), 폴더당 최대 700MB | `python -m venv .venv` |
| `node_modules` | 재설치가 정석, 용량 과다 | `npm install` |
| `__pycache__`, `*.pyc`, `.pytest_cache` | 빌드 캐시 | 자동 재생성 |
| `.git`, `.idea`, `.gradle` | 저장소·IDE 메타데이터 | — |
| `obs/`(원본 녹화 48MB), `.tmp/` | 편집 전 원본 — `videos/`의 완성본으로 대체 | 원본 `C:\qaeduc2\VOC_Improve_1\obs\` |
| `data\chunks_head`(128MB), `pdf_text_probe.txt`(12MB) | 디버그 덤프, 실행에 불필요 | 원본 `C:\0710pt\...\` |
| `logs/`, `tests_output/` **내용** | 이전 실행 로그 | **빈 폴더는 복원해 뒀습니다** (없으면 실행 실패) |

**포함한 것**: ChromaDB 인덱스, 평가 리포트/이력, 발표자료, 시연 영상, 테스트 데이터, `k6.exe`
→ 재색인·재실행 없이 결과를 바로 보여줄 수 있도록 남겼습니다.

---

## 검증 결과 (2026-08-05 실행 검증 후 갱신)

| 항목 | 결과 |
|---|---|
| 실제 `.env` 파일 유출 | **0건** |
| `.env.example` 내 실제 API 키 | 🔴 **2건 발견 → 제거 완료** (원래 번호 15·18번, 이후 폴더 제거) |
| 소스 내 API 키 하드코딩 (`sk-…`) | **0건** (01·02번 매칭은 테스트 픽스처와 마스킹된 오류 로그 — 정상) |
| 전체 Python 파일 문법 검사 | 271개 **전부 통과** |
| `requirements.txt` 오류 | 🔴 **5건 발견 → 수정 완료** (제출본 01·06·08 / 원래 번호 09·11은 이후 폴더 제거) |

### 🔴 반드시 조치하세요 — API 키 폐기

`15_LangChain_멀티툴_에이전트\.env.example`과 `18_LMS_QA_챗봇\.env.example`에
**동일한 실제 OpenAI 키가 평문으로 들어 있었습니다.** 두 파일 모두 빈 값으로 교체했지만,
**해당 키는 이미 노출된 것이므로 OpenAI 콘솔에서 폐기·재발급하세요.**
(`C:\qaeduc2\SAMPLE0608\main.py`의 하드코딩 키와 같은 키입니다.)

**미해결 상태** — 아직 폐기·재발급이 확인되지 않았습니다.

### `requirements.txt` 수정 내역

| # | 증상 | 수정 |
|---|---|---|
| 01 | `mcp>=1.2`가 2.0.0을 설치 → `mcp.server.fastmcp` 제거되어 import 실패 | `mcp>=1.2,<2.0` |
| 06 | `chromadb==0.5.23`이 `chroma-hnswlib` C++ 빌드 요구 → Windows/Py3.12 설치 실패 | `chromadb>=1.0,<2.0` |
| 08 | `prometheus-client`·`requests`·`streamlit`·`pandas` 누락 | 4종 추가 |

> 수정 후 전부 재실행해 통과를 확인했습니다. 상세 증적은 [`PORTFOLIO.html`](PORTFOLIO.html) 참조.

### 2026-08-06 추가 수정 (코드에 반영 완료)

| # | 파일 | 수정 | 검증 |
|---|---|---|---|
| 05 | `src/utils/config_loader.py` | 상대경로 → `__file__` 기준 절대경로. 설정 파일이 없을 때 기본값을 새로 쓰는 대신 예외 발생 | 프로젝트 밖에서 실행해 `high_risk_finance` 가중치(`S·A=2.0`) 정상 로드 확인 |
| 06 | `Dockerfile` · `.dockerignore` | `CMD`(uvicorn) 추가, Windows 전용 `tools/k6.exe` 제외 | `docker compose config` exit 0 (이미지 빌드는 미검증) |
| 09 | `backend/package.json` | `test:unit`(node --test) / `test:integration`(jest) 분리 | **`npm test` → 9건 통과, exit 0** |
| 10 | `main.py` | 실행 안내 주석 오타 수정, `/docs` 주소 추가 | — |
| 06·08 | `requirements.txt` | **한글 주석이 있는데 BOM이 없어 한국어 윈도우에서 `pip install`이 `UnicodeDecodeError`로 실패.** BOM 추가로 로케일과 무관하게 UTF-8로 읽히게 함 | 재설치 exit 0 |
| 전체 | `.gitignore` (루트) | 10개 중 5개에 `.gitignore`가 없어 `.env`가 커밋될 위험 → 루트에 공통 파일 추가 | — |

> **05번은 단순 버그가 아니라 채점 결함이었습니다.** 설정 파일을 못 찾으면 오류 없이
> 기본 가중치(전부 1.0)로 덮어써서, `high_risk_finance`의 `S·A=2.0`이 사라진 채 평가가 진행됐습니다.

### API 키 관련 검증 정정 (2026-08-05/06)

- **01** — `.env` 없이도 `unittest`(98건)·품질 스위트(32건)·오프라인 E2E·장애진단·deterministic Judge가 전부 통과합니다.
- **02** — 테스트가 LLM 호출을 전부 모킹하므로 **더미 키**(`sk-dummy` 같은 아무 값)만 넣으면 84건 전부 통과합니다. 실제 과금은 없습니다.
- **06** — `pytest` 53건이 키 없이 통과합니다.
- **08** — 에이전트가 모의 구현이라 애초에 키가 필요 없습니다. `.env.example`의 `OPENAI_API_KEY`는 실제로 쓰이지 않습니다.
- **05** — `.env.example`에 `OPENAI_API_KEY`가 있지만 **대시보드(`app/app.py`)는 LLM을 전혀 호출하지 않습니다.**
  슬라이더로 점수를 넣어 가중치·과락을 계산하는 순수 계산기라 **키 없이 그대로 실행됩니다**(기동 확인 완료).
  `LLMJudge`는 `use_mock=True`로 난수를 돌려주며 대시보드에서 쓰이지 않습니다.

---

## 원본 위치 (대조 · 복원용)

제거한 프로젝트는 아래 원본 경로에서 폴더째 복사하면 그대로 되살아납니다.
**원래 번호 기준으로 정렬**했습니다 — 복원할 때 찾는 기준이 원래 번호이기 때문입니다.

| 원래 번호 | 제출본 번호 | 포트폴리오 폴더 | 원본 |
|---:|---:|---|---|
| 01 | **01** | `01_VOC_Improve_MultiAgent` | `C:\qaeduc2\VOC_Improve_1` |
| 02 | **02** | `02_AI_Quality_Platform` | `C:\ai_quality_final_project_rule_2` |
| 03 | **03** | `03_AI_Chatbot_QA_Pipeline` | `C:\ai_quality_final_project2607011616` |
| 04 | **04** | `04_QA_WBS_TestPlan` | `C:\qaeduc2\ai_quality_final_project00\Doc` |
| 05 | **05** | `05_RAIT_Evaluation_System` | `C:\qaeduc2\rait-pilot-system` |
| 06 | **06** | `06_AI ChatbotQA` | `C:\0710pt\ai_quality_final_project_Team3` |
| 07 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\fake_judge_lab` |
| 08 | **07** | `07_RAG_Chatbot` | `C:\qaeduc2\rag_chatbot_(2)` |
| 09 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\routing_classifier_project` |
| 10 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\ab_test_practice` |
| 11 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\baseline_model_evaluation` |
| 12 | **08** | `08_AI_Agent_Dashboard` | `C:\qaeduc2\0706_ai_agent_monitoring` |
| 13 | **09** | `09_FullStack_WebApp` | `C:\qaeduc2\web_applcation_dev_2` |
| 14 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\test555` |
| 15 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\langchain_multi_tool_agent` |
| 16 | **10** | `10_LangGraph_Chatbot` | `C:\qaeduc2\project_2026` |
| 17 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\lms-enrollment-chatbot` |
| 18 | — | *(웹 가동 불가로 제거)* | `C:\qaeduc2\lms-chatbot (1)\lms-chatbot` |
| 19 | — | *(폴더가 애초에 없었음)* | `C:\qaeduc2\Mobile_Invitation` |
| 20 | — | *(QA 실습물이 아님)* | `C:\qaeduc2\PR1` |

> 원본은 **삭제하지 않았습니다.** 이 폴더가 잘못되면 언제든 다시 만들 수 있습니다.
> 번호를 다시 매겨도 **원본은 원래 번호 그대로**이므로 이 표가 두 체계를 잇는 유일한 기준표입니다.

---

## 2026-08-10 추가 작업 (STEP 2/3~6, 실행환경 검증 및 공개 준비)

- **실행환경 복구 및 검증**: 01·02·03·05·06·07·08·10 8개 프로젝트에 `.venv` 생성 + `pip install -r requirements.txt` 후 실행 검증.
  - 01: pytest 32/32 PASS · 02: pytest 84/84 PASS(더미 키) · 06: pytest 53/53 PASS · 08: 실제 서버 기동 후 기능테스트 4/4 PASS · 05: mock 모드로 파이프라인 실행 확인 · 03·07·10: 핵심 모듈 import 검증(실 API 필요해 전체 실행은 미검증).
- **06 README 경로 오류 수정**: 존재하지 않는 옛 경로(`C:\260710_project\ai_quality_final_project_Team3\`)가 남아있어 실제 폴더 루트 기준으로 설치/테스트/streamlit/uvicorn/docker 명령을 전부 수정함.
- **07 중복 폴더 삭제**: `07_RAG_Chatbot\rag_chatbot\` 하위에 26MB짜리 통째 중복(더 오래된 버전, chroma_db·업로드 PDF 포함)이 있어 사용자 승인 받아 삭제. (`0625_new.py`, `prompts/`는 미사용 스크래치 파일이나 사소해 보류)
- **05·07·08 README 재작성**: 비정형(제목/설치 안내 부재) README를 제목·주요기능·구조·설치·실행·접속주소 포맷으로 재작성.
- **10 README 신규 작성**: README 자체가 없어 신규 작성. Python(FastAPI, 배송조회봇)과 Node.js(에듀봇) 두 구현이 공존함을 명시.
- **루트 README 자기소개 추가**: 최성우(IT PM 27년 경력 → AI QA 전환) 소개 섹션 추가.
- **k6.exe 저장소 제외**: `06/tools/k6.exe`(61MB, GitHub 50MB 경고 대상)를 `.gitignore`에 추가해 커밋에서 제외. 필요 시 `winget install k6`로 로컬 설치 안내로 대체.
