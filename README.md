# 최성우 | IT 기획·PM 20년+ → AI/LLM QA

요구사항을 검증 가능한 품질 기준으로 구조화하고, 테스트 설계·실행·결함 분석·재검증을 거쳐 Release 판단까지 연결합니다.
AI/LLM 품질평가에서는 실제 실행, Mock, 외부 API 필요 범위를 구분해 결과와 한계를 함께 기록합니다.

- 커리어 홈(전체 경력·연락처): [mahokani7.github.io](https://mahokani7.github.io/)
- AI QA 핵심 포트폴리오: [mahokani7.github.io/qa](https://mahokani7.github.io/qa/)
- 상세 QA 검증 및 증적: [mahokani7.github.io/qa-portfolio](https://mahokani7.github.io/qa-portfolio/)

---

## Target Role

**Primary** · AI/LLM QA · AI 품질기획<br>
**Adjacent** · IT 서비스기획 · Technical PM

## Evidence Snapshot

| Evidence | Result |
|---|---:|
| Public QA Projects | **9** |
| Verified Automated Tests | **276 PASS** |
| Validation Findings | **7** |
| PRJ_01 Live E2E | **18** |
| Release Decision Case | **HOLD** |

> **TEST PASS ≠ RELEASE GO**<br>
> pytest 32/32 PASS → Live E2E 18건 → 독립 Judge 평균 81.2점 → Release 기준 95점 미달 → **HOLD**<br>
> 테스트 성공과 Release 승인을 분리한 대표 QA 판단 사례입니다.

`276`은 전체 포트폴리오에서 실제 실행 결과를 확인한 자동 테스트 수이며, 팀 프로젝트에 포함된 테스트를 함께 집계한 값입니다. `7`은 코드 결함뿐 아니라 보안·의존성·설정 로딩·테스트 러너·테스트 용이성에서 확인한 검증 이슈를 포함합니다.

## Core Competencies

- 요구사항을 검증 가능한 품질 기준으로 구조화
- 테스트 전략·테스트 케이스·회귀 시나리오 설계
- pytest·Cypress·Jest·node:test·k6 기반 자동화 검증
- LLM Judge·Rubric·Rule 기반 AI 응답 품질평가
- 결함 분석·수정 확인·재검증·Release 판단

---

## Featured Projects

> 프로젝트 번호는 원본 작업 순서를 유지했으며, 03은 공개 포트폴리오 범위에서 제외했습니다.

### [`01`](01_VOC_Improve_MultiAgent/) · VOC Multi-Agent QA

- **검증 목표**: 멀티에이전트 결과물을 독립 Judge로 재검증
- **My Role**: 테스트 시나리오·루브릭 설계, Judge 프롬프트·결과 검증, 발표·시연
- **Team Scope**: 멀티에이전트 파이프라인·AWS 인프라·대시보드는 팀원 담당
- **Evidence / Result**: pytest 32건·Live E2E 18건, Judge 81.2점 / 기준 95점 → **HOLD**

### [`02`](02_AI_Quality_Platform/) · AI 품질 평가 플랫폼

- **검증 목표**: Judge·Rule·레드팀·PII·환각·회귀 검증을 조합해 단일 채점 의존 완화
- **My Role**: 팀 프로젝트 기반 코드에서 12개 품질 모듈·대시보드·테스트 체계를 독립 확장
- **Evidence**: pytest 84건, k6 600요청
- **Result**: 84/84 PASS, 오류율 0%·p95 13~21ms — **개인 확장 프로젝트**

### [`05`](05_RAIT_Evaluation_System/) · RaiT 평가 시스템

- **검증 목표**: 본 프로젝트에서 직접 정의한 RaiT 8축으로 반복 가능한 1차 품질평가 기준 구성
- **My Role**: 지표·루브릭·Judge 프롬프트·계산 엔진·도메인 정책·대시보드 단독 설계·구현
- **Evidence**: RE·EX·UP·ST·TR·AT·CO·PR, 4가지 집계 방식과 도메인별 정책 실행
- **Result**: Mock LLM Judge로 파이프라인 검증 — 실서비스 대량 LLM 채점과 pytest는 미수행

---

## Additional Projects

| Project | Focus | Evidence |
|---|---|---|
| [`04`](04_QA_WBS_TestPlan/) | 테스트 계획·WBS | 본인 작성 테스트 계획서·발표자료, 팀 산출물 구분 |
| [`06`](06_AI_Chatbot_QA/) | AI Chatbot QA | pytest 53건, 팀 프로젝트 역할 구분 |
| [`07`](07_RAG_Chatbot/) | RAG QA | 최신 평가 7/10 PASS, 실패 결과 유지 |
| [`08`](08_AI_Agent_Dashboard/) | Monitoring | Mock 기반 기능 테스트 4/4 PASS |
| [`09`](09_FullStack_WebApp/) | Full-stack QA | node:test 5건 + Jest 4건 = 9/9 PASS, Cypress E2E 코드 |
| [`10`](10_LangGraph_Chatbot/) | Agent 안전성 | Python import 검증, Node 구현 정적 검토, API 키 필요 |

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
| 05 | RaiT 평가 시스템 | ✅ 실행검증 | 없음(키 불필요) |
| 06 | 팀 프로젝트 — AI 챗봇 QA | ✅ 실행검증 | 🔑 API 키 · 🐳 Docker(4서비스 구성) |
| 07 | RAG 챗봇 | 구조 확인 | 🔑 API 키 |
| 08 | AI Agent 모니터링 | ✅ 실행검증 | 없음(로컬 Mock) |
| 09 | 풀스택 웹앱 | ✅ 실행검증(테스트) | 💾 백엔드 기능은 MongoDB 필요 |
| 10 | LangGraph 챗봇 | 구조 확인 | 🔑 API 키 |

`✅ 실행검증` = 실제 명령을 돌려 종료 코드와 출력을 확인 · `구조 확인` = API 키가 필요해 모듈 구조·의존성까지만 확인 · `🔑`/`🐳`/`💾` = 실행에 필요한 조건(문제가 아니라 실행 환경 요구사항)

검증 과정에서 확인한 이슈 7건(자격 증명 노출, 의존성, 설정 로딩, 테스트 러너·용이성)과 수정·재검증 내역은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)에 정리했습니다. 자동 테스트 276건은 팀 프로젝트를 포함해 전체 포트폴리오에서 실제 실행 결과를 확인한 합계입니다.

---

## Run & Validation

- 실행 환경·설치·프로젝트별 명령: [`SETUP.md`](SETUP.md)
- 실제 실행 여부·테스트 수·Mock/API 조건·결함·재검증: [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)

---

## AI 활용 범위

- **AI 활용**: 코드·문서 초안, 반복 작업, 코드 검토 보조
- **직접 수행**: 요구사항 분석, 테스트 전략·TC 설계, 테스트 실행, 결과 검증, 결함 분석, 재검증, 품질·Release 판단

---

## Contact

- 이메일: [mahokani7@gmail.com](mailto:mahokani7@gmail.com)
- 커리어 홈: [mahokani7.github.io](https://mahokani7.github.io/)
- 검증 방법·발견한 결함·수정 내역: [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)
