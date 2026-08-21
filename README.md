# 최성우 | IT 기획·PM → AI/LLM QA

20년+ IT 기획·PM 경험을 기반으로 요구사항 분석부터 AI/LLM 품질기준 설계, 테스트 자동화, 결함 분석까지 연결합니다.

- 커리어 홈(전체 경력·연락처): [mahokani7.github.io](https://mahokani7.github.io/)
- AI QA 핵심 포트폴리오: [mahokani7.github.io/qa](https://mahokani7.github.io/qa/)
- 실무면접관용 상세 검증 포트폴리오: [mahokani7.github.io/qa-portfolio](https://mahokani7.github.io/qa-portfolio/)

---

## Target Role

**AI/LLM QA · AI 품질기획 · IT 서비스기획 · Technical PM**

## Why Me?

- 20년+ IT 기획·PM 경험 — 요구사항과 서비스 구조를 먼저 이해하는 QA
- LLM 응답 품질 평가 기준(Rubric) 설계 — "무엇을 좋은 응답이라고 볼 것인가"를 측정 가능한 축으로 정의
- 테스트 자동화 및 품질 리포트 작성 — pytest·Cypress·k6로 검증하고 결과를 문서로 남김
- AI 도구를 활용하되, 요구사항 정의·결과 검증·최종 품질 판단은 직접 수행

---

## Featured Projects

> 프로젝트 번호는 원본 작업 순서를 유지했으며, 03은 공개 포트폴리오 범위에서 제외했습니다.

### [`01`](01_VOC_Improve_MultiAgent/) VOC 멀티에이전트 QA

**Purpose**: VOC(고객의 소리) 멀티에이전트가 만든 정책 개선안을, 자동 처리 결과 그대로 배포해도 되는지 독립적으로 검증하는 QA 체계 구축

**My Role**: 테스트 시나리오 설계, 평가 루브릭(LLM Judge 채점 기준) 설계, Judge 프롬프트 검증, 독립 LLM Judge 결과 검증, 발표·시연 — 팀 프로젝트(4인)이며 멀티에이전트 파이프라인·AWS 인프라는 팀원 담당

**QA Challenge**: 자동 테스트가 통과했더라도 독립적인 LLM Judge의 평가를 통해 배포 여부를 다시 판단할 수 있는 QA 구조가 필요했음 — 내부 파이프라인이 100점(배포 가능)으로 판정한 케이스를 독립 Judge는 정책구체성 축에서 0점으로 재평가

**Key Result**: pytest 32/32 PASS, 독립 Judge 평균 81.2점(배포 기준 95점 미달) → **배포 보류(HOLD)** 판정

**View Project**: [01_VOC_Improve_MultiAgent](01_VOC_Improve_MultiAgent/)

### [`02`](02_AI_Quality_Platform/) AI 품질 평가 플랫폼

**Purpose**: AI 응답 품질을 Judge 채점 하나에 의존하지 않고, 레드팀·PII·환각·회귀 등 서로 다른 방식으로 교차 검증하는 품질 관리 체계 설계

**My Role**: 팀 프로젝트 기반 Judge/Rule-based 코드를 바탕으로 루브릭(8축 평가 기준), JSON Schema, 레드팀·PII스캔·환각검출 등 12개 독립 검증 모듈, Streamlit 대시보드, pytest·k6 테스트 체계를 단독 확장 — 개인 확장 프로젝트

**QA Challenge**: 채점 기준(Judge) 하나가 틀렸을 때 그 오류를 놓치지 않으려면 어떻게 교차 검증할 것인가

**Key Result**: pytest 84/84 PASS, k6 부하테스트 오류율 0%·p95 13~21ms

**View Project**: [02_AI_Quality_Platform](02_AI_Quality_Platform/)

### [`05`](05_RAIT_Evaluation_System/) RaiT 평가 시스템

**Purpose**: 사람마다 다른 "좋은 응답"의 판단 기준을, 8개의 측정 가능한 축과 도메인별 정책으로 표준화해 반복 가능한 품질 판정 체계로 구현

**My Role**: 8축 지표 체계 정의, Judge 프롬프트 설계, 계산 엔진(4가지 집계 방식) 구현, 도메인별 정책(기준점·가중치·과락 조건) 설계, Streamlit 대시보드 구현 — 개인 프로젝트(단독 설계·구현)

**QA Challenge**: 정책 설정을 못 찾았을 때 조용히 기본값(가중치 1.0)으로 채점을 이어가면, 도메인별 가중치가 소리 없이 사라지는 채점 결함이 생김 — 실패를 숨기지 않고 즉시 드러내는 설계로 방지

**Key Result**: Mock LLM Judge 기준 파이프라인 정상 동작 확인(실제 LLM 대량 채점·pytest 스위트는 이 프로젝트에서 수행하지 않았음을 그대로 밝혀둠)

**View Project**: [05_RAIT_Evaluation_System](05_RAIT_Evaluation_System/)

---

## Additional Projects

대표 3개 외에도 다양한 QA 환경(팀 프로젝트, RAG, 웹 E2E, Agent 안전성 등)을 직접 검증했습니다.

### AI/LLM QA & Evaluation

- [`06`](06_AI_Chatbot_QA/) AI 챗봇 QA 자동화 플랫폼(팀 프로젝트) — 규칙 기반 1차 검증 + LLM Judge 2차 평가 이중 검증, pytest 53건
- [`07`](07_RAG_Chatbot/) RAG 챗봇 — 문서 기반 근거 답변 + LLM Judge 채점(이해도·정확성), 최신 평가 10건 중 7건 PASS
- [`08`](08_AI_Agent_Dashboard/) AI Agent 모니터링 대시보드 — Mock 기반 장애·성능 시뮬레이션, 기능 테스트 4/4 PASS
- [`10`](10_LangGraph_Chatbot/) LangGraph 챗봇 — 도구 호출(Tool-calling) Agent의 안전성 원칙을 수동 시나리오로 검증

### QA Process / Planning

- [`04`](04_QA_WBS_TestPlan/) QA 문서 산출물(팀 프로젝트) — 요구사항→WBS→테스트계획→재검증으로 이어지는 QA 프로세스 문서화, My Work/Team Artifacts 구분
- [`09`](09_FullStack_WebApp/) 풀스택 웹앱 QA — Cypress E2E + Jest/node:test로 단위→통합→E2E 계층을 분리한 자동화 테스트

> 번호가 02→04로 건너뛰는 이유: 03(AI 챗봇 QA 파이프라인 초기 버전)은 같은 팀 프로젝트의 확장판인 06으로 완전히 대체되어 이 저장소에서 제외했습니다. 자세한 내용은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md) 참고.

각 프로젝트 README에는 QA SUMMARY(역할·테스트범위·주요 결함·최종 판정)와 My Role, 📌 포트폴리오 핵심 문서가 정리돼 있습니다.

---

## Tech Stack & 증명 QA 역량

`Python · pytest · LLM-as-a-Judge · Streamlit · Docker · Cypress · k6 · Grafana/Prometheus · Jira` — 이 저장소 9개 프로젝트에서 실제로 사용한 스택입니다.

| QA 역량 | 설명 | 근거 프로젝트 |
|---|---|---|
| 테스트 설계·계획 | 테스트 시나리오·케이스 설계, 단위/통합 테스트 계획서 작성 | 01, 04, 09 |
| 결함 관리·리포팅 | 결함 발견→원인 분석→수정→재검증, 이슈트래킹 | 01, 02, 04, 06 |
| LLM-as-a-Judge 평가 설계 | 채점 루브릭·프롬프트·JSON 출력 스키마 설계 | 01, 02, 05, 07 |
| 품질 게이트·회귀 | 자동테스트+레드팀+E2E를 조합한 배포 판정, 회귀 테스트 | 01, 02, 05 |
| 성능·부하 테스트(k6) | 부하 테스트 설계·실행, 오류율/응답시간 측정 | 02, 06 |
| 운영 모니터링(Grafana/Prometheus) | 대시보드·알림 규칙 연동 | 02, 06 |
| E2E 자동화(Cypress) | 네트워크 스텁 기반 E2E, 단위/통합 테스트 계층 분리 | 09 |
| QA 문서화(요구사항·WBS·칸반) | 요구사항정의서·WBS·테스트계획서·Jira 칸반 | 04 |
| 보안·레드팀 검증 | 프롬프트 인젝션·PII 유출·권한 공격 시나리오 검증 | 01, 02 |

---

## 🔍 Portfolio Self-QA

이 포트폴리오 자체도 "링크만 걸어두고 실행된다고 주장"하지 않았습니다. 한 대의 PC에서 전부 새로 설치하고 직접 실행해 상태를 판정했고, **정상 작동하지 않는 부분도 숨기지 않고 그대로 표시**했습니다 — 이 표 자체가 QA 태도의 증거입니다.

| # | 프로젝트 | 상태 | 필요 조건 |
|---|---|---|---|
| 01 | VOC 멀티에이전트 | ✅ 실행검증 | 🐳 Docker 스택(gRPC 6개+웹서버 동시 기동) |
| 02 | AI품질·운영 모니터링 | ✅ 실행검증 | 🔑 API 키 · 🐳 Docker(Prometheus/Grafana/k6) |
| 04 | QA 문서 산출물 | 📄 문서 전용 | — |
| 05 | RAIT 평가 시스템 | ✅ 실행검증 | 없음(키 불필요) |
| 06 | 팀 프로젝트 — AI 챗봇 QA | ✅ 실행검증 | 🔑 API 키 · 🐳 Docker(4서비스 구성) |
| 07 | RAG 챗봇 | 구조 확인 | 🔑 API 키 |
| 08 | AI Agent 모니터링 | ✅ 실행검증 | 없음(로컬 Mock) |
| 09 | 풀스택 웹앱 | ✅ 실행검증(테스트) | 💾 백엔드 기능은 MongoDB 필요 |
| 10 | LangGraph 챗봇 | 구조 확인 | 🔑 API 키 |

`✅ 실행검증` = 실제 명령을 돌려 종료 코드와 출력을 확인 · `구조 확인` = API 키가 필요해 모듈 구조·의존성까지만 확인 · `🔑`/`🐳`/`💾` = 실행에 필요한 조건(문제가 아니라 실행 환경 요구사항)

검증 과정에서 발견한 결함 7건(의존성 오류, 자격 증명 노출, 채점 로직 결함 등)과 수정·재검증 내역은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)에 정리했습니다. 자동 테스트는 총 276건을 직접 실행해 통과를 확인했습니다.

---

## 실행 방법 (빠른 시작)

```powershell
cd <프로젝트 폴더>
python -m venv .venv && .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # 필요한 경우 API 키 입력
pytest   # 또는 각 프로젝트 README의 실행 명령
```

API 키 안내, Node 프로젝트 설치, 프로젝트별 상세 실행 명령, 공개 호스팅 시 주의사항은 [`SETUP.md`](SETUP.md)에 정리했습니다.

---

## AI 활용 원칙

이 저장소의 코드와 문서 작성에 AI 도구(Claude 등)를 코드 작성과 문서 초안의 **보조 수단**으로 활용했습니다. 요구사항 정의·테스트 설계·결과 검증·오류 원인 분석·최종 품질 판단은 **직접 수행**했습니다.

---

## Contact

- 이메일: [mahokani7@gmail.com](mailto:mahokani7@gmail.com)
- 커리어 홈: [mahokani7.github.io](https://mahokani7.github.io/)
- 검증 방법·발견한 결함·수정 내역: [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)
