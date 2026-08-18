<!-- TODO: 히어로 스크린샷 -->

# AI QA 포트폴리오 — 요구사항을 아는 PM이 만드는 품질 시스템

**최성우 | IT 기획·PM → AI QA**

20년+ IT 기획·PM 경험을 AI/LLM 서비스 품질 검증으로 확장하고 있습니다. 툴을 실행하는 QA가 아니라 **"무엇을 좋은 응답이라고 볼 것인가"라는 평가 기준 자체를 설계하는 QA**를 지향합니다.

`Python · pytest · LLM-as-a-Judge · Streamlit · Docker · Cypress · k6 · Grafana/Prometheus · Jira` — 이 저장소 9개 프로젝트에서 실제로 사용한 스택입니다.

- 개인 브랜딩 사이트(경력·연락처): [mahokani7.github.io](https://mahokani7.github.io/)
- AI QA 포트폴리오(정리된 버전): [mahokani7.github.io/qa](https://mahokani7.github.io/qa/)

---

## 이 포트폴리오가 증명하는 QA 역량

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

## 대표 프로젝트 3선

### [`01`](01_VOC_Improve_MultiAgent/) VOC 멀티에이전트 QA — 자동 테스트 PASS ≠ 배포 승인

내부 파이프라인이 100점(배포 가능)으로 판정한 케이스를, 별도로 붙인 독립 LLM Judge가 정책구체성 축을 0점으로 재평가해 배포를 보류(HOLD)시킨 사례. pytest 32건은 전부 PASS했지만 독립 Judge 평균은 배포 기준(95점) 미달이었습니다 — "테스트 통과"와 "배포 판단"이 다른 층위라는 것을 실제 수치로 확인했습니다.

- **증명하는 QA 역량**: 품질 게이트 설계, 독립 LLM Judge 평가, 팀 프로젝트 내 QA 역할 수행
- **스택**: Python · gRPC · MCP · pytest · LLM-as-a-Judge(Anthropic/OpenAI)

### [`02`](02_AI_Quality_Platform/) AI 품질 평가 플랫폼 — Judge 하나에 기대지 않는 교차 검증

AI 응답 품질을 레드팀(공격 주입)·PII스캔(정규식)·환각검출(근거 코퍼스 대조)·회귀·RAG on/off 비교 등 12개 독립 모듈로 나눠 검증합니다. 채점 기준 하나가 틀렸을 때를 대비해 서로 다른 방식으로 교차 확인하도록 설계했습니다.

- **증명하는 QA 역량**: 다각도 품질 검증 설계, 성능·모니터링 연동, pytest 84건 자동화
- **스택**: Python · pytest · k6 · Docker · Prometheus/Grafana · Jira

### [`05`](05_RAIT_Evaluation_System/) RaiT 평가 시스템 — 8축 루브릭 + 도메인 정책 기반 판정

AI 응답 품질을 8개 축으로 분해해 채점하고, 도메인(고위험 금융/일반 등)마다 다른 기준점·가중치·과락 조건으로 PASS/FAIL을 판정하는 프레임워크입니다. 설정을 못 찾으면 기본값으로 조용히 넘어가지 않고 즉시 실패시키도록 설계해, 채점 결과가 소리 없이 달라지는 결함을 방지했습니다.

- **증명하는 QA 역량**: 평가 루브릭 설계, CI 스타일 배포 게이트(종료 코드), 조용한 실패 방지 설계
- **스택**: Python · Streamlit · Mock LLM Judge

---

## 전체 프로젝트 인덱스

| # | 프로젝트 | 초점 | 스택 | 증명 QA 역량 |
|---|---|---|---|---|
| [01](01_VOC_Improve_MultiAgent/) | VOC 멀티에이전트 QA | 6-Agent 파이프라인 + 독립 Judge 배포 판정 | Python·gRPC·MCP·pytest | 품질 게이트·Judge 평가 |
| [02](02_AI_Quality_Platform/) | AI 품질 평가 플랫폼 | 12개 검증 모듈 교차 평가 | Python·pytest·k6·Docker·Grafana | 레드팀·성능·모니터링 |
| [04](04_QA_WBS_TestPlan/) | QA 문서 산출물 | 요구사항→WBS→테스트계획→재검증 문서화 | Jira·WBS·문서 | QA 프로세스 문서화 |
| [05](05_RAIT_Evaluation_System/) | RaiT 평가 시스템 | 8축 루브릭 + 도메인 정책 PASS/FAIL | Python·Streamlit | 루브릭 설계·품질 게이트 |
| [06](06_AI_Chatbot_QA/) | AI 챗봇 QA 자동화 플랫폼(팀) | 규칙+LLM 이중 검증, 테스트 이력 관리 | Python·pytest·Docker·k6·Jira | 통합 테스트·QA 문서 |
| [07](07_RAG_Chatbot/) | RAG 챗봇 | 문서 기반 근거 답변 + Judge 채점 | Python·ChromaDB·Streamlit | Judge 설계·근거 검증 |
| [08](08_AI_Agent_Dashboard/) | AI Agent 모니터링 대시보드 | Mock 기반 장애·성능 시뮬레이션 | Python·FastAPI·Streamlit | 테스트 시나리오 설계 |
| [09](09_FullStack_WebApp/) | 풀스택 웹앱 QA | Unit→Integration→E2E 계층 분리 | Cypress·Jest·Express·React | E2E 자동화·API 스텁 |
| [10](10_LangGraph_Chatbot/) | LangGraph 챗봇 | 도구 호출 Agent 안전성 설계 | Python·LangGraph·Node.js | 시나리오 설계·안전성 검증 |

각 프로젝트 README에는 QA SUMMARY(역할·테스트범위·주요 결함·최종 판정)가 정리돼 있습니다.

---

## 자가 QA 검증 결과

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

검증 과정에서 발견한 결함 7건(의존성 오류, 자격 증명 노출, 채점 로직 결함 등)과 수정·재검증 내역은 [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)에 정리했습니다. 자동 테스트는 총 276건을 직접 실행해 통과를 확인했으며, 프로젝트별 구성과 팀/개인 역할 구분은 위 "전체 프로젝트 인덱스"와 각 프로젝트 README에 있습니다.

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
- 전화: 010-5033-1779
- 커리어 홈: [mahokani7.github.io](https://mahokani7.github.io/)
- 검증 방법·발견한 결함·수정 내역: [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)
