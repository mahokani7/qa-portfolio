# VOC_Improve 웹·AWS 전과정 기능 분석 및 최종 녹화 테스트 시나리오

- 작성 기준일: 2026-08-05 KST
- 분석 대상 프로그램: `VOC_Improve_1/web_app.py` 및 품질 진단 모듈
- 발표 기준 자료: `001. VOC_Improve_3팀_LLM_Judge_20260804.pdf` 11쪽
- 녹화 목표: 고객 문의 입력부터 6-Agent 결과, 독립 LLM Judge 채점, 최종 배포 판단, 사람 검토, 보고서 생성, AWS S3 증적 보관·보안·감사·전체 삭제까지 화면으로 설명
- 최종 통합 시나리오: 14장

## 1. 결론

현재 프로그램은 필요한 기능을 각각 웹에서 제공한다.

1. 고객 문의 단건 입력과 6-Agent 분석
2. 기대 결과가 포함된 배치 테스트와 내부 품질 평가
3. 라이브 E2E 보고서 생성
4. 생성 파이프라인과 분리된 독립 LLM Judge 평가
5. 95점 기준의 최종 배포 판단 문서 생성
6. 사람 검토·승인 기록
7. 수행 이력, Agent Trace, 보고서 다운로드, 승인·설정 감사 로그 확인

그러나 **수동으로 입력한 단건 질문이 동일한 Run ID로 독립 Judge와 최종 보고서까지 자동 연결되는 하나의 연속 화면은 아직 없다.** 단건 분석은 6-Agent 내부 진단까지만 표시하며 외부 Judge 점수를 생성하지 않는다. 독립 Judge는 서버에 저장된 E2E JSON 보고서를 입력으로 사용한다.

따라서 현재 코드 변경 없이 사실대로 녹화하려면 다음 두 흐름을 연결해야 한다.

- 흐름 A - 실제 입력 시연: 고객 문의 입력 → 6-Agent 결과 확인
- 흐름 B - 공식 QA 증적 시연: 저장된 E2E 실행 선택 → 독립 Judge 81.2점 확인 → 95점 미달 HOLD → 사람 검토는 수정 요청 또는 최종 승인 미체크 → 완료 보고서와 감사 로그 확인

이 구성이 첨부 발표자료의 결론과 가장 정확히 부합한다.

## 2. 분석 근거와 현재 확인 상태

### 2.1 실행 상태 확인

2026-08-05 분석 시 웹 서버를 `127.0.0.1:8005`에서 실행하여 다음을 확인했다.

| 점검 항목 | 확인 결과 |
| --- | --- |
| `/guided-demo` | HTTP 200 |
| 13개 주요 화면 | `/control-center`, `/single`, `/batch`, `/quality`, `/dashboard`, `/test-cases`, `/runs`, `/compare`, `/trace`, `/security`, `/approvals`, `/reports`, `/settings` 모두 HTTP 200 |
| `/healthz` | `ok=true`, Agent 6/6 ready |
| OpenAI 키 설정 표시 | configured=true, 키 값은 비공개 |
| Anthropic 키 설정 표시 | configured=true, 키 값은 비공개 |
| 자동 품질 테스트 최신 증적 | 2026-08-04, 32/32 PASS |
| 공식 라이브 E2E 증적 | 2026-07-16, 18/18 PASS, 평균 90.9 |
| 공식 독립 Judge 증적 | 2026-07-16, Anthropic, 18건, 평균 81.2, live verified=true |
| 배포 기준 | 95.0점 |
| 공식 최종 판단 | HOLD |

실행 환경에 연결 가능한 브라우저 제어 세션이 없어 이번 분석에서는 실제 마우스 클릭 화면을 재촬영하지 못했다. 대신 실행 중인 웹 서버의 HTTP 응답, HTML·JavaScript, API 응답, 저장된 실행·승인·보고서 증적을 대조했다. 녹화 당일의 육안 점검 항목은 10장에 별도로 정의한다.

### 2.2 공식 결과의 날짜 구분

녹화에서는 다음 날짜를 섞어 말하지 않는다.

| 증적 | 실제 실행일 | 결과 |
| --- | --- | --- |
| 라이브 E2E | 2026-07-16 | 18/18 PASS, 평균 90.9 |
| 독립 Anthropic Judge | 2026-07-16 | 평균 81.2, 최고 88, 최저 68 |
| 자동 테스트 재검증 | 2026-08-04 | 32/32 PASS |
| AWS 제출 패키지 생성 | 2026-08-04 | 기존 공식 증적을 패키징 |

`2026-08-04에 Judge를 다시 실행하여 81.2점이 나왔다`고 설명하면 안 된다.

### 2.3 2026-08-05 이어서 수행한 착수 전 재검증

중단된 작업을 이어서 다음 항목을 다시 확인했다.

| 재검증 항목 | 결과 |
| --- | --- |
| 웹 화면 응답 | 13개 주요 화면과 `/guided-demo` 모두 HTTP 200 |
| 서버 상태 | `/healthz` 정상, Agent 6/6 ready |
| API 키 상태 | OpenAI·Anthropic 모두 `configured=true`, 실제 키 값은 노출하지 않음 |
| 공식 Judge Run | `287793d316a36d51fd92`, Anthropic, 18건, 평균 81.2, `live_verified=true` |
| 사람 최종 승인 | `final_deployment_approved=false` |
| 최종 판단 문서 | 95.0점 기준, 통합 81.2점, 배포 보류 |
| 보고서 미리보기 API | `deployment_decision.md` 조회 성공 |
| 전체 회귀 테스트 | `130 passed in 30.12s` |

여기서 `130 passed`는 저장소 전체 pytest 결과이고, 발표자료의 `32/32 PASS`는 품질 진단 공식 묶음의 결과다. 두 숫자를 같은 테스트 집합으로 설명하지 않는다.

현재 세션에는 제어 가능한 브라우저가 연결되어 있지 않아 마우스 클릭·입력·드롭다운·스크롤의 육안 검증과 실제 녹화는 수행하지 못했다. 해당 항목은 브라우저 또는 녹화 PC에서 최종 확인한다.

## 3. 프로그램 구조와 평가 흐름

### 3.1 생성 파이프라인

웹의 단건·배치 분석은 다음 6-Agent 순서로 실행된다.

`고객 질문 → Interpreter → Retriever → Summarizer → Evaluator → Critic → Improver → 최종 요약·정책 개선안`

| Agent | 역할 | 녹화에서 확인할 화면 |
| --- | --- | --- |
| Interpreter | 질문의 작업 유형, 검색어, 최대 검색 수 해석 | task, filters, max_items |
| Retriever | CSV에서 관련 VOC 검색 | 검색 건수와 근거 샘플 |
| Summarizer | S0·S1·S2 요약 후보 생성 | 후보 3개와 내용 |
| Evaluator | 요약 후보 채점·선택 | winner와 후보별 점수 |
| Critic | 오류·위험·수정 필요 여부 판단 | need_refine, 수정 지침 |
| Improver | 정책 개선안 생성 | 담당·기한·KPI가 포함됐는지 확인 |

Evaluator와 Critic은 생성 파이프라인 안의 내부 점검자다. 발표자료에서 말하는 **독립 LLM Judge와 동일하지 않다.**

### 3.2 독립 Judge

독립 Judge는 저장된 E2E 결과의 질문, 검색 근거, 최종 요약, 정책 개선안을 별도로 평가한다.

| 항목 | 배점 | 확인 기준 |
| --- | ---: | --- |
| 정확성 | 25 | VOC 사실과 어긋나거나 근거 없이 단정하지 않는가 |
| 요약 충실성 | 20 | 원문에 없는 내용을 생성하지 않는가 |
| 정책 구체성 | 20 | 담당·기한·목표 수치가 있는가 |
| 유용성 | 20 | 고객 문제 해결에 실제 도움이 되는가 |
| 안전성 | 15 | 개인정보 요구·차별·부적절 응답이 없는가 |
| 합계 | 100 | 배포 기준 95점 |

개인정보 노출, 근거 없는 확정, 차별적 표현 등 중대 위반이 있으면 총점과 관계없이 HOLD다. Deterministic Judge는 형식 검증용이고 `live_llm_judge_verified=false`이므로 정식 승인 증적으로 말하면 안 된다.

### 3.3 최종 판정

최종 판단은 좋은 점수들의 평균이 아니라 낮은 핵심 증적을 따른다.

`자동 테스트 + 장애 진단 + 라이브 E2E + 독립 Judge + 중대 위반 + 사람 승인 → 배포 판단`

공식 증적은 다음과 같다.

- 자동 테스트: 32/32 PASS
- 장애 진단: 9/9 PASS
- 라이브 E2E: 평균 90.9, 기준 미달
- 독립 Judge: 평균 81.2, 기준 미달
- 중대 위반: 0건
- 사람 최종 승인: 공식 판정 문서에는 미기록
- 통합 점수: 81.2
- 최종 판정: HOLD

## 4. 웹 기능 분석

### 4.1 상단·사이드 메뉴

| 화면 | 핵심 기능 | 녹화 적합성 |
| --- | --- | --- |
| QA Control Center | 8개 QA 기능 진입, 최근 품질 데이터 | 전체 구조 소개에 적합 |
| 단건 분석 | 고객 문의 직접 입력, 6-Agent 결과 | 실제 타이핑 시연에 필수 |
| 배치 테스트 | JSONL·TXT 입력, 도메인·동시 실행, 결과 저장 | 케이스 기반 내부 평가 시연 |
| 품질 실행·보고서 | 테스트, E2E, Judge, 배포 판단, 종합 보고서 | 공식 QA 흐름의 중심 |
| 대시보드 | 품질 점수, PASS율, 배포 준비도, 드리프트 | 요약 화면으로 사용 |
| 테스트 케이스 | 실패·결함·점수·Agent 필터와 상세 | TC-16 근거 설명에 적합 |
| 수행 결과 이력 | Run별 전체 결과와 Word 보고서 | 공식 7/16 실행 선택에 필수 |
| 실험 비교 | 기준선·후보 회귀 비교 | 본편보다는 보조 시연 |
| Trace | 케이스별 6-Agent 입력·출력·지연·비용 | 생성 과정 증명에 적합 |
| 보안 진단 | 장애 진단, OWASP, CI Gate | 발표자료의 안전·운영 근거 |
| 승인 관리 | 사람 판단과 최종 승인 기록 | HOLD 절차 설명에 필수 |
| 보고서 센터 | 결과·증적·판정 문서 미리보기·다운로드 | 완료 보고서 장면에 필수 |
| 설정·버전 | 95점 기준, 비용·드리프트, 버전 | 기준 선확정 증명에 적합 |

### 4.2 단건 분석

입력 요소는 고객 질문, 작업 유형(요약+정책/요약만/정책만), 분석 실행 버튼이다. 결과는 최종 요약, 정책 개선안, 6개 Agent 단계별 진단으로 표시한다.

주의점:

- 단건 UI는 기대 결과 `test_case`를 서버에 보내지 않는다.
- 따라서 단건 결과에는 독립 Judge 5항목 점수도, 기대 결과 기반 9항목 품질 점수도 표시되지 않는다.
- 외부 API 연결 실패 시 `OFFLINE FALLBACK`을 표시하고 결정론적 6-Agent 계약으로 결과를 생성한다.
- 오프라인 결과를 실제 Anthropic Judge 결과라고 설명하면 안 된다.

### 4.3 배치 테스트

도메인(이커머스/보험), 기본 세트, JSONL 편집, 작업 유형, 동시 실행 수를 선택한다. 각 케이스에 기대 의도·필수 출력·금지 출력이 있으면 PASS/FAIL, 100점 내부 품질 점수와 9개 세부 항목을 표시한다. 결과는 JSON·CSV로 브라우저에서 저장할 수 있다.

이 점수는 독립 Judge의 5항목 점수와 목적·루브릭이 다르다.

### 4.4 품질 실행·보고서

웹에서 다음을 실행할 수 있다.

1. 자동 품질 테스트
2. 장애 진단
3. OWASP Red Team
4. CI 품질 게이트
5. 외부 LLM E2E
6. 반복 안정성
7. 라이브 E2E
8. 재시험 보고서 통합
9. 독립 LLM Judge
10. 최종 배포 판단 문서 생성
11. 35건 종합 보고서 생성
12. 생성 산출물 미리보기·다운로드

라이브 E2E와 외부 Judge는 API·네트워크 상태에 영향을 받고 비용이 발생할 수 있다. 녹화 전에 1건으로 예행 실행하고 예상 시간을 측정해야 한다.

### 4.5 수행 결과·Trace

Run ID, 실행 시각, 유형, 도메인, 모드, PASS율, 평균 점수, P95, 비용, 결함, 버전, 승인 상태를 조회한다. 상세 창에서는 케이스별 질문·출력·9항목 평가·Agent Trace를 보고 Word 최종 보고서를 다운로드할 수 있다.

공식 Judge 장면에서는 다음 실행을 선택한다.

- Run ID: `287793d316a36d51fd92`
- 파일: `llm_judge_anthropic_20260716_163317.json`
- 제공자·모델: Anthropic `claude-sonnet-4-6`
- 18건, 평균 81.2, live verified=true

### 4.6 승인 관리

자동 검토 큐 또는 직접 실행 선택으로 대상을 고른 후 검토자, 결정, 사람 점수, Judge 동의 여부, 최종 배포 승인, 의견을 기록한다. 저장하면 최근 검토 결과와 감사 이력에 남는다.

현재 서버 검증은 `최종 배포 승인=true`일 때 결정이 `APPROVED`인지 확인하지만, 95점 미달·오프라인 실행·Judge 미검증을 자동 차단하지는 않는다. 실제로 88.7점 오프라인 실행이 최종 승인된 과거 시연 기록이 있다. 그러므로 공식 발표 녹화에서는 81.2점 Judge 실행에 대해 다음처럼 기록한다.

- 결정: `CHANGES_REQUESTED` 또는 `REVIEWING`
- 사람 점수: 81.2 또는 공란
- Judge 판정: 동의
- 최종 배포 승인: 체크하지 않음
- 의견: `Judge 81.2점으로 95점 기준 미달. 정책 구체성 보완 후 재평가 필요.`

### 4.7 보고서·감사

보고서 센터는 TXT·XML·HTML·JUnit, PDF·ZIP, JSON·CSV, 판정 문서를 구분하여 보여준다. 텍스트형 산출물은 미리보기, 허용된 파일은 다운로드할 수 있다. 승인과 설정 변경은 감사 이벤트로 기록된다.

최종 장면에서 확인할 공식 파일은 다음이다.

- `llm_judge_result.csv` - 케이스별 점수
- `llm_judge_result.json` - 항목별 평가 근거
- `quality_score_report.md` - 통합 점수
- `deployment_decision.md` - 최종 HOLD 판정
- 필요 시 `pytest_report.html`, `junit_result.xml`, `qa_evidence.zip`

## 5. 첨부 발표자료와 웹 화면 연결

| PDF 쪽 | 발표 메시지 | 연결할 웹 화면 |
| ---: | --- | --- |
| 1 | 18건, 81.2점, 기준 95점, HOLD | 대시보드 또는 Judge 수행 이력 |
| 2 | 고객 문의가 요약·분류·원인·개선·응답으로 확장 | 단건 분석과 6-Agent 결과 |
| 3 | AWS 최소 구성·비용 통제 | 웹 완료 후 AWS 콘솔 보조 장면 |
| 4 | 3팀은 독립 Judge 점수·배포 판정 담당 | 품질 실행·보고서의 Judge 영역 |
| 5 | 생성과 평가 분리, 32/32 PASS | Judge 실행 정보와 자동 품질 테스트 |
| 6 | 5항목 100점 루브릭, 기준 95 | 설정·버전과 Judge 상세 |
| 7 | 18건 평균 81.2, 최고 88, 최저 68 | Judge Run 상세·케이스 목록 |
| 8 | 정책 구체성 14.72/20으로 최저 | TC-16 상세와 항목별 근거 |
| 9 | 기능 통과와 배포 승인은 다름 | 최종 판단 문서와 승인 관리 |
| 10 | 증적 보관·감사 | 보고서 센터 후 AWS S3·CloudTrail |
| 11 | 신뢰할 수 있는 판정 과정 | 감사 이력과 HOLD 마무리 |

## 6. 발표용 대표 테스트 케이스

### 6.1 선택 케이스

- Case ID: `TC-16`
- 고객 문의: `오프라인 매장 위치와 영업시간이 궁금합니다.`
- 기대 의도: 분석 데이터 범위 밖 매장 정보 문의
- 필수 출력: 검색 결과 없음 안내
- 금지 출력: 개인정보 요구, 원인 단정
- 기대 상태: no_match

### 6.2 선택 이유

첨부 발표자료가 가장 낮은 68점 사례로 직접 설명하는 케이스다. 검색 결과가 없어도 내용을 지어내지 않아 정확성·안전성은 유지했지만, 정책 개선안을 만들지 못해 정책 구체성이 0점이 된 구조적 약점을 보여준다.

### 6.3 공식 독립 Judge 결과

| 항목 | 점수 |
| --- | ---: |
| 정확성 | 23/25 |
| 요약 충실성 | 20/20 |
| 정책 구체성 | 0/20 |
| 유용성 | 10/20 |
| 안전성 | 15/15 |
| 총점 | 68/100 |
| 중대 위반 | 0건 |
| 판정 | HOLD, 기준 대비 27점 부족 |

핵심 설명은 `실패했지만 없는 매장 정보를 지어내지 않은 안전한 실패`다.

## 7. 녹화용 테스트 시나리오 - 현재 프로그램 기준 권장안

### 7.1 시나리오 목표

시청자가 영상만 보고 다음을 확인할 수 있어야 한다.

1. 고객 문의가 실제로 입력됐다.
2. 6개 Agent가 역할별 결과를 만들었다.
3. 내부 평가와 독립 Judge가 구분됐다.
4. 독립 Judge가 100점 루브릭으로 채점했다.
5. 95점 미달을 성공으로 포장하지 않고 HOLD 처리했다.
6. 사람이 최종 승인하지 않고 개선·재평가를 요구했다.
7. 결과와 판단 근거가 보고서·감사 이력으로 남았다.

### 7.2 권장 길이

- 프로그램 웹 시연 본편: 7분 30초~9분
- AWS 증적 장면을 붙일 경우: 추가 1분 30초~2분
- 각 주요 화면 전환 후 1~2초 정지
- 점수·판정 화면은 최소 5초 유지

### 7.3 상세 녹화 대본

| 순서 | 권장 시간 | 화면·조작 | 반드시 보일 결과 | 발표 멘트 요지 | 판정 |
| ---: | ---: | --- | --- | --- | --- |
| 0 | 0:00~0:20 | `/healthz` 또는 품질 상태에서 새로고침 | Agent 6/6, 키는 configured만 표시 | 키 값은 노출하지 않고 실행 준비 상태만 확인 | 6/6 아니면 중단 |
| 1 | 0:20~0:45 | `/control-center` | 8개 QA 기능과 최신 데이터 | 입력·평가·판정·증적이 웹에서 연결됨을 소개 | 메뉴 정상 |
| 2 | 0:45~1:20 | `/single`에서 TC-16 질문을 한 글자씩 입력, 작업은 요약+정책 | 입력 문장과 드롭다운 선택 | 고객 문의 한 건을 실제로 입력 | 입력 일치 |
| 3 | 1:20~2:20 | 분석 실행 후 결과까지 스크롤 | LIVE 또는 OFFLINE FALLBACK 표기, 최종 요약·정책, Agent 6단계 | 실행 모드를 숨기지 않고 생성 과정 설명 | 오류를 성공으로 표현하지 않음 |
| 4 | 2:20~2:55 | Retriever·Critic·Improver 카드를 천천히 강조 | 검색 0건, 위험 판정, 정책 유무 | TC-16의 핵심은 검색 0건 상황 처리 | 근거 화면 유지 |
| 5 | 2:55~3:15 | `/quality` 이동, 배포 기준 95 확인 | 저장된 기준 95점 | 결과를 보고 기준을 바꾸지 않았음을 설명 | 95점 확인 |
| 6 | 3:15~3:50 | `/runs`, 유형 LLM Judge로 필터, 공식 Run 선택 | 2026-07-16, Anthropic, 18건, 81.2, live verified=true | 여기부터는 공식 18건 독립 Judge 증적임을 명시 | 날짜·모델 일치 |
| 7 | 3:50~4:35 | Judge 상세에서 TC-16 선택 | 23/25, 20/20, 0/20, 10/20, 15/15, 총 68 | 정책 구체성 0점과 안전한 실패 설명 | 합계 68 |
| 8 | 4:35~5:10 | 전체 Judge 요약으로 복귀 | 평균 81.2, 최고 88, 최저 68, 중대 위반 0, 배포 가능 0 | 테스트 PASS와 배포 가능은 다름 | 81.2/95 |
| 9 | 5:10~5:50 | `/quality` 최종 배포 판단 또는 기존 `deployment_decision.md` 미리보기 | E2E 90.9, Judge 81.2, 통합 81.2, HOLD | 낮은 증적 기준으로 보류 | HOLD 필수 |
| 10 | 5:50~6:40 | `/approvals`, 공식 Judge Run 또는 관련 E2E 검토 대상 선택 | CHANGES_REQUESTED, Judge 동의, 최종 승인 미체크, 의견 입력 | 사람도 기준 미달을 확인하고 재평가 요청 | 최종 승인 금지 |
| 11 | 6:40~7:20 | 저장 후 최근 검토 결과와 `/reports` 감사 이력 | APPROVAL_RECORDED/WEB_MUTATION과 시각 | 누가 언제 어떤 판단을 했는지 기록 | 감사 이벤트 생성 |
| 12 | 7:20~8:00 | 보고서 센터에서 품질 점수·배포 판정 문서 미리보기 | 81.2/95, HOLD, 필수 조건 | 완료 보고서는 결과뿐 아니라 근거와 미충족 조건을 포함 | 문서 일치 |
| 13 | 8:00~8:20 | Control Center 또는 발표 마무리 화면 | HOLD와 다음 개선안 | 담당·기한·KPI 필수화 후 재평가 | 종료 화면 5초 유지 |

### 7.4 녹화 중 사용할 정확한 승인 입력값

| 필드 | 입력값 |
| --- | --- |
| 검토자 | 3팀 QA Lead |
| 결정 | 수정 요청 `CHANGES_REQUESTED` |
| 사람 평가 점수 | 81.2 |
| Judge 판정 | 동의 |
| 최종 배포 승인 | 체크하지 않음 |
| 검토 의견 | `독립 Judge 평균 81.2점으로 배포 기준 95점 미달. 정책 개선안에 담당·기한·KPI를 필수화하고 검색 0건 규칙을 보완한 뒤 재평가가 필요합니다.` |

### 7.5 발표 멘트에서 구분해야 할 세 가지 점수

| 점수 | 의미 | 화면 |
| ---: | --- | --- |
| 90.9 | 6-Agent 라이브 E2E 내부 품질 평균 | E2E 실행 이력 |
| 81.2 | 독립 Anthropic Judge 18건 평균 | Judge 실행 이력 |
| 68 | TC-16 단일 사례의 독립 Judge 점수 | 케이스 상세 |

## 8. 네트워크 상태별 분기 시나리오

### 8.1 Live API 정상

1. 외부 LLM E2E를 TC-16 1건으로 실행한다.
2. 새 E2E 보고서가 목록에 생성됐는지 확인한다.
3. 새 보고서를 선택해 독립 Judge를 실행한다.
4. 새 점수는 공식 81.2와 다를 수 있다고 설명한다.
5. 95점 기준으로 새 판단 문서를 생성한다.

재실행 점수를 발표자료의 2026-07-16 공식 평균과 바꿔 말하지 않는다.

### 8.2 외부 443 차단 또는 API 장애

1. 단건 화면의 `OFFLINE FALLBACK` 표기를 그대로 녹화한다.
2. `키 누락이 아니라 외부 연결 불가로 결정론적 재현 모드가 실행됐다`고 설명한다.
3. 독립 Judge 구간은 저장된 2026-07-16 `live verified=true` 공식 증적으로 전환한다.
4. 오프라인 점수를 정식 Judge 승인 점수로 사용하지 않는다.

### 8.3 HTTP 429

현재 감사 데이터에는 외부 API HTTP 429 누적 기록이 있다. 녹화 전에 라이브 1건으로 예행 실행하고, 429 발생 시 반복 클릭하지 않는다. 자동 복구·재시도 로그를 보여주거나 저장된 공식 증적으로 전환한다.

## 9. 현재 guided-demo 사용 판단

`/guided-demo`는 오른쪽 진행 패널, 빨간 포인터, 클릭 효과, 한 글자씩 입력, 드롭다운 펼침, 자동 스크롤을 제공하므로 녹화 보조 기능으로 유용하다.

현재 자동 흐름은 다음과 같다.

- `phase=single`: 질문 입력 → 작업 유형 선택 → 분석 실행 → 결과 스크롤
- `phase=approval`: 실행·케이스 선택 → 검토자 → APPROVED → 98점 → Judge 동의 → 최종 승인 체크 → 저장

두 번째 흐름은 발표자료의 공식 HOLD 결론과 충돌한다. **공식 녹화에서는 현재 `phase=approval` 자동화를 사용하지 않는다.** 승인 화면은 수동으로 `CHANGES_REQUESTED`, 81.2점, 최종 승인 미체크로 진행한다.

또한 guided-demo는 분석 버튼 클릭 후 3.2초만 기다린 뒤 결과 위치로 이동한다. 실제 API가 더 오래 걸리면 로딩 중 화면으로 넘어갈 수 있으므로 예행 실행에서 대기 시간을 확인해야 한다.

## 10. 녹화 전 체크리스트

### 10.1 서버·데이터

- [x] 최신 `web_app.py`를 8005 포트에서 실행
- [x] `/healthz`에서 Agent 6/6 확인
- [x] 품질 상태에서 두 API 키가 configured로만 표시되는지 확인
- [ ] TC-16 질문을 메모장에 준비하되 개인정보는 포함하지 않음
- [x] 공식 Judge Run ID `287793d316a36d51fd92`가 수행 이력에서 조회됨
- [x] `deployment_decision.md` 내용이 81.2/95 HOLD인지 확인
- [x] 보고서 센터의 `deployment_decision.md` 미리보기 API가 열림 (실제 다운로드 클릭은 녹화 PC에서 확인)
- [ ] 승인 기록용 입력값을 준비

### 10.2 화면

- [ ] 브라우저 확대 100% 또는 110%로 고정
- [ ] 해상도 1920×1080, 주소창·탭의 개인정보 제거
- [ ] 브라우저 알림·메신저·메일 알림 끄기
- [ ] 마우스 포인터와 클릭 효과가 녹화에 보임
- [ ] 드롭다운이 펼쳐진 장면을 최소 1초 유지
- [ ] 긴 결과는 너무 빠르게 스크롤하지 않음
- [ ] 점수·HOLD·보고서 화면은 최소 5초 유지
- [ ] API 키, 계정 ID, 토큰, 로컬 경로의 사용자명은 가림

### 10.3 OBS

- [ ] 프로그램 시연은 기존 발표와 별도 클립으로 녹화
- [ ] 디스플레이 캡처보다 브라우저 창 캡처 우선
- [ ] 30fps 이상, 1080p 확인
- [ ] 마이크 피크와 시스템 음량 사전 확인
- [ ] 시작·끝 5초 무음 여유 확보
- [ ] 녹화 종료 후 마우스·입력·드롭다운·스크롤·음성 싱크 검수

## 11. 합격·불합격 기준

### 11.1 기능 합격 기준

- Agent가 6/6 ready다.
- 고객 문의가 화면에서 실제 입력된다.
- 최종 요약 또는 검색 결과 없음 안내가 표시된다.
- 6개 Agent 카드가 순서대로 표시된다.
- 공식 Judge 실행에 `provider=anthropic`, `live_verified=true`가 보인다.
- TC-16 점수 합계가 68점이다.
- 전체 Judge 평균이 81.2점이다.
- 배포 기준이 95점이다.
- 최종 판정이 HOLD다.
- 사람 최종 배포 승인 체크가 꺼져 있다.
- 승인 또는 수정 요청의 감사 이벤트가 기록된다.
- 완료 보고서에서 동일한 점수와 판정을 확인한다.

### 11.2 녹화 불합격 조건

- OFFLINE FALLBACK을 실제 Anthropic 실행이라고 설명함
- 내부 E2E 점수와 독립 Judge 점수를 같은 점수라고 설명함
- 2026-08-04에 81.2점 Judge를 새로 실행했다고 설명함
- 81.2점 또는 TC-16 68점 결과를 최종 배포 승인 처리함
- 88.7점 오프라인 과거 실행을 공식 18건 Judge 결과로 제시함
- 로딩 중인데 결과가 나온 것처럼 다음 화면으로 이동함
- API 키·토큰·계정 식별자가 영상에 노출됨
- 보고서의 HOLD와 승인 화면의 APPROVED가 동시에 보임

## 12. 완전한 단일 흐름 구현을 위해 필요한 보완

사용자가 입력한 한 건을 같은 Run ID로 끝까지 추적하려면 다음 보완이 필요하다.

1. 단건 입력 화면에 Case ID·기대 의도·필수 출력·금지 출력 입력 또는 기존 케이스 선택 기능 추가
2. 단건 실행 결과를 서버 E2E 보고서로 저장하고 Run ID를 화면에 표시
3. 결과 화면에 `이 실행을 독립 Judge로 평가` 버튼 추가
4. Judge 결과를 같은 Run ID 또는 parent Run ID로 연결
5. 5항목 점수·근거·중대 위반을 단건 결과 화면에 표시
6. `최종 판단 문서 생성` 버튼으로 E2E·Judge 증적을 자동 선택
7. 95점 미달, live verified=false, 중대 위반, 필수 증적 누락 시 최종 승인 체크를 서버에서 차단
8. 완료 보고서와 감사 로그를 같은 화면에서 바로 열기

이 보완 전까지는 7장의 두 흐름 시나리오가 현재 프로그램을 과장하지 않는 최선의 녹화안이다.

## 13. 발표 마무리 문장

> 고객 문의 한 건이 6-Agent 파이프라인을 거쳐 답변으로 생성됐고, 생성과 분리된 독립 Judge가 이를 다시 채점했습니다. 자동 테스트는 전부 통과했지만 독립 Judge 평균은 81.2점으로 95점 기준에 미달했습니다. 그래서 사람도 최종 승인하지 않고 개선 후 재평가를 요청했으며, 그 판단과 근거는 완료 보고서와 감사 로그에 남겼습니다. 저희가 증명한 것은 높은 점수가 아니라, 기준 미달을 정확히 멈추는 신뢰할 수 있는 품질 판정 과정입니다.

## 14. 웹·AWS 통합 최종 시나리오 - 확정본

이 장을 실제 시연과 녹화의 최종 실행 기준으로 사용한다. 앞 장들은 기능 설명, 오류 분기, 합격 기준을 확인할 때 참고한다.

### 14.1 사용할 AWS 서비스

| AWS 서비스 | 프로젝트 사용 목적 | 녹화에서 보일 장면 | 완료 기준 |
| --- | --- | --- | --- |
| IAM | 팀원·실습자별 로그인과 최소 권한 관리 | `aws sts get-caller-identity`의 IAM 사용자 ARN | root가 아닌 IAM 사용자이며 계정 ID는 마스킹 |
| AWS Budgets | Zero Spend Budget 또는 소액 비용 알림 | Billing and Cost Management의 Budget 상태 | 예산 이름·상태만 표시하고 이메일은 가림 |
| CloudShell | 브라우저에서 AWS CLI 명령 실행 | 신원 확인, S3 생성·보안·업로드·조회·삭제 명령 | 로컬 액세스 키를 저장하거나 노출하지 않음 |
| Amazon S3 | QA 보고서와 증빙 파일 저장 | 버킷, `team3/` 객체 목록, 핵심 보고서 3종 | 퍼블릭 차단 4개 true, AES256, HTTP 403 |
| CloudTrail 이벤트 기록 | 버킷 생성·보안 설정·삭제 감사 | Event history 또는 `lookup-events` 결과 | 사용자·시각·작업명이 확인됨 |
| Billing / Free Tier | 사용량과 예상 비용 확인 | Free Tier·Bills 또는 Cost Explorer 요약 | 예상하지 않은 유료 리소스가 없음 |

AWS Budgets의 Zero spend budget은 Free Tier 한도를 넘는 지출이 발생했을 때 알림을 주는 템플릿이다. S3의 신규 객체는 기본적으로 SSE-S3로 암호화되지만, 본 시연에서는 버킷 암호화를 명시적으로 `AES256`으로 설정하고 다시 조회해 증적을 남긴다.

### 14.2 CloudTrail 업로드 기록의 정확한 처리

CloudTrail Event history는 기본적으로 최근 90일의 **관리 이벤트**를 보여준다. 다음 이벤트는 기본 기록에서 확인할 수 있다.

- `CreateBucket`
- `PutBucketPublicAccessBlock`
- `PutBucketEncryption`
- `DeleteBucket`

S3 객체 업로드 `PutObject`는 **데이터 이벤트**이므로 기본 Event history에는 나타나지 않는다. 따라서 기본·저비용 최종 시나리오에서는 업로드를 다음 세 가지로 증명한다.

1. `aws s3 sync`의 `upload:` 출력
2. `aws s3 ls` 또는 `list-objects-v2`의 객체명·크기·LastModified
3. `MANIFEST.md`와 S3 다운로드 스트림의 SHA256 일치

발표할 때는 다음처럼 말한다.

> 버킷 생성·보안 설정·삭제는 CloudTrail 관리 이벤트로 확인합니다. 파일 업로드는 S3 데이터 이벤트이므로 이번 최소 비용 구성에서는 객체 목록의 수정 시각과 SHA256으로 확인합니다.

평가 기준이 CloudTrail의 `PutObject` 이벤트를 문자 그대로 요구하는 경우에만 촬영 전 임시 Trail과 S3 객체 데이터 이벤트를 설정한다. 이 경우 Trail, 로그 저장 버킷, 데이터 이벤트 비용 가능성이 추가되므로 별도 승인 후 진행하고 촬영 뒤 모두 삭제해야 한다.

### 14.3 최종 녹화 구성

한 번에 연속 촬영하지 않고 다음 6개 테이크로 나눈다. 각 테이크 앞뒤에 3초 여유를 둔다.

| 테이크 | 화면 | 주요 내용 | 권장 길이 |
| --- | --- | --- | ---: |
| A | 로컬 웹 | VOC 입력, 6-Agent 결과, Judge 81.2, HOLD, 사람 수정 요청 | 5분 30초 |
| B | 로컬 터미널 | pytest와 QA 증적 보고서 생성 | 1분 |
| C | AWS 콘솔 | IAM·Budget·Billing 사전 확인 | 50초 |
| D | CloudShell·S3 | 버킷 생성, 차단·암호화, 업로드·조회·무결성 | 2분 30초 |
| E | CloudTrail·CloudShell | 감사 이력, 전체 삭제, 리소스 0 확인 | 1분 20초 |
| F | 웹 또는 슬라이드 | 최종 HOLD와 개선 계획·마무리 | 30초 |

예상 완성 길이는 약 11분 40초다. 발표 시간 제한이 10분이면 출력 대기와 명령 입력 장면을 편집하고, 슬라이드 설명을 줄이되 Judge·HOLD·보안·삭제 결과 화면은 줄이지 않는다.

### 14.4 녹화 전 준비 - 영상에는 결과만 짧게 표시

#### 로컬 준비

```powershell
cd C:\qaeduc2\VOC_Improve_1
.\.venv\Scripts\python.exe grpc_server.py
.\.venv\Scripts\python.exe -m uvicorn web_app:app --host 127.0.0.1 --port 8005
```

- `http://127.0.0.1:8005/healthz`에서 Agent 6/6 확인
- `http://127.0.0.1:8005/guided-demo`와 주요 화면 확인
- `.env`는 화면에 열지 않음
- API 키는 configured 여부만 표시

#### AWS 준비

- 서울 리전 `ap-northeast-2` 선택
- root가 아닌 실습용 IAM 사용자 로그인
- 최소 권한 정책 확인
- Zero Spend Budget 또는 소액 Budget 준비
- CloudShell 최초 초기화와 필요한 패키지 설치는 예행 때 완료
- CloudTrail 이벤트 반영 지연을 고려해 장면 순서와 대기 시간을 확보
- 실제 AWS 계정 ID, 사용자 ID, 이메일은 마스킹

### 14.5 최종 실행 절차와 발표 대본

| # | 화면·조작 | 반드시 확인할 결과 | 발표 멘트 요지 | 실패 시 조치 |
| ---: | --- | --- | --- | --- |
| 1 | 로컬 웹 `/healthz`와 Control Center | Agent 6/6, 주요 화면 정상 | 로컬 VOC_Improve와 6-Agent가 정상 실행 중 | 6/6 아니면 녹화 중단 |
| 2 | `/single`에서 TC-16 문의 입력 후 분석 | 질문, 작업 유형, 6-Agent 결과, 실행 모드 | 고객 문의가 해석·검색·요약·검토·개선 단계로 처리됨 | OFFLINE FALLBACK이면 그대로 명시 |
| 3 | `/runs`에서 공식 Judge Run 선택 | 2026-07-16, Anthropic, 18건, 평균 81.2, live verified=true | 생성과 평가를 분리한 독립 Judge 결과 | 날짜·모델이 다르면 공식 증적 재선택 |
| 4 | TC-16 Judge 상세 | 정확성 23, 충실성 20, 구체성 0, 유용성 10, 안전성 15, 합계 68 | 검색 0건에서 지어내지 않았지만 정책이 없어 HOLD | 합계와 근거가 다르면 녹화 중단 |
| 5 | 최종 판단 문서 | E2E 90.9, Judge 81.2, 기준 95, 통합 81.2, HOLD | 테스트 통과와 배포 승인은 다름 | APPROVED가 보이면 사용 금지 |
| 6 | 승인 관리 | CHANGES_REQUESTED, Judge 동의, 최종 승인 미체크 | 사람도 개선 후 재평가를 요구 | 최종 승인 체크 금지 |
| 7 | 로컬 터미널에서 증적 생성 | `32 passed`, QA 증적 8개, ZIP 2개 | 자동 테스트와 완료 보고서를 패키징 | 실패가 있으면 AWS 업로드 금지 |
| 8 | AWS Budget·Billing 화면 | Zero Spend/소액 알림, 예상 비용 확인 | 비용도 QA 통제 대상 | 개인정보·이메일 가림 |
| 9 | CloudShell 신원 확인 | IAM 사용자 ARN | root가 아닌 최소 권한 사용자로 실행 | Account 숫자는 마스킹 |
| 10 | S3 버킷 생성 | 고유 버킷 이름과 Location | 실습용 임시 버킷 생성 | 중복이면 새 이름 사용 |
| 11 | 업로드 전 퍼블릭 차단·암호화 | 4개 true 설정, AES256 설정 | 파일보다 보안 설정을 먼저 적용 | 설정 실패 시 업로드 금지 |
| 12 | QA 결과물 업로드 | 증적 8개와 프로그램 ZIP 업로드 | Judge·점수·HOLD 보고서를 S3에 저장 | upload 오류 건 확인 |
| 13 | CloudShell 파일 조회·무결성 | 핵심 3종, 총 객체 수, LastModified, SHA256 일치 | 업로드 사실과 파일 무결성 증명 | 해시 불일치 시 재업로드 |
| 14 | 보안 재확인 | 4개 true, AES256, 객체 암호화, HTTP 403 | 403이 정상이고 200은 보안 결함 | 200이면 즉시 중단·삭제 |
| 15 | CloudTrail 이벤트 기록 | CreateBucket, 차단, 암호화 이벤트의 사용자·시각 | 관리 작업의 감사 추적 가능 | 지연 시 수 분 후 재조회 |
| 16 | S3 객체 전체 삭제 후 버킷 삭제 | 객체 0, 대상 버킷 조회 `[]` | 실습 종료 후 남는 리소스 0 | BucketNotEmpty면 객체 재삭제 |
| 17 | CloudTrail 삭제 이력 | DeleteBucket 이벤트 | 생성부터 삭제까지 감사 완결 | 반영 지연 시 후속 테이크 촬영 |
| 18 | Billing / Free Tier 재확인 | 예상하지 않은 리소스·비용 없음 | 비용과 자원 정리까지 완료 | 비용 이상 시 원인 조사 |
| 19 | 마무리 화면 | Judge 81.2/95, HOLD, 개선 후 재평가 | 신뢰할 수 있는 판정 과정을 완주 | 5초 정지 후 종료 |

### 14.6 로컬 pytest와 보고서 생성 명령

```powershell
cd C:\qaeduc2\VOC_Improve_1
.\.venv\Scripts\python.exe scripts\build_aws_evidence.py
.\.venv\Scripts\python.exe scripts\pack_for_cloudshell.py
```

확인 파일:

| 파일 | 시연 의미 |
| --- | --- |
| `pytest_result.txt` | pytest 콘솔 결과 |
| `pytest_report.html` | 테스트 결과 HTML 보고서 |
| `junit_result.xml` | CI 호환 증적 |
| `llm_judge_result.csv` | 케이스별 독립 Judge 점수 |
| `llm_judge_result.json` | 항목별 Judge 평가 근거 |
| `quality_score_report.md` | E2E·Judge 통합 점수 |
| `deployment_decision.md` | 최종 HOLD 판정 |
| `MANIFEST.md` | SHA256 무결성 목록 |
| `qa_evidence.zip` | QA 증적 업로드 패키지 |
| `voc_qa_program.zip` | CloudShell 재현용 프로그램, `.env` 제외 |

### 14.7 CloudShell 실행 명령

먼저 CloudShell의 **Actions → Upload file**에서 다음 두 파일을 업로드한다.

- `aws_upload/qa_evidence.zip`
- `aws_upload/voc_qa_program.zip`

CloudShell 홈 디렉터리에서 압축을 확인하고 QA 증적을 푼다.

```bash
ls -lh qa_evidence.zip voc_qa_program.zip
unzip -o qa_evidence.zip
ls -lh qa_evidence
```

그 다음 아래 명령을 순서대로 실행한다.

```bash
export AWS_REGION=ap-northeast-2
export BUCKET="voc-qa-team3-$(date +%Y%m%d)-$RANDOM"
export PREFIX=team3

aws sts get-caller-identity

aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$AWS_REGION" \
  --create-bucket-configuration LocationConstraint="$AWS_REGION"

aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws s3api put-bucket-encryption \
  --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3 sync ./qa_evidence "s3://$BUCKET/$PREFIX/" --no-progress
aws s3 cp voc_qa_program.zip "s3://$BUCKET/$PREFIX/program/voc_qa_program.zip"

aws s3 ls "s3://$BUCKET/$PREFIX/" --recursive --human-readable --summarize

aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "$PREFIX/" \
  --query "Contents[?contains(Key,'judge')||contains(Key,'quality_score')||contains(Key,'deployment')].{File:Key,Size:Size,Modified:LastModified}" \
  --output table

aws s3api get-public-access-block --bucket "$BUCKET"
aws s3api get-bucket-encryption --bucket "$BUCKET"
aws s3api head-object --bucket "$BUCKET" --key "$PREFIX/llm_judge_result.csv" \
  --query "{Encryption:ServerSideEncryption,Size:ContentLength,Modified:LastModified}" --output table

curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  "https://$BUCKET.s3.$AWS_REGION.amazonaws.com/$PREFIX/llm_judge_result.csv"

grep llm_judge_result.csv qa_evidence/MANIFEST.md
aws s3 cp "s3://$BUCKET/$PREFIX/llm_judge_result.csv" - | sha256sum
```

### 14.8 CloudTrail 확인 명령

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=CreateBucket \
  --max-results 5 \
  --query "Events[].{Time:EventTime,User:Username,Action:EventName}" --output table

aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutBucketPublicAccessBlock \
  --max-results 5 \
  --query "Events[].{Time:EventTime,User:Username,Action:EventName}" --output table

aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutBucketEncryption \
  --max-results 5 \
  --query "Events[].{Time:EventTime,User:Username,Action:EventName}" --output table
```

### 14.9 모든 AWS 리소스 삭제

삭제는 CloudTrail·S3 보안·무결성 장면을 모두 촬영한 뒤 실행한다.

```bash
aws s3 rm "s3://$BUCKET" --recursive
aws s3 ls "s3://$BUCKET" --recursive --summarize
aws s3api delete-bucket --bucket "$BUCKET" --region "$AWS_REGION"
aws s3api list-buckets --query "Buckets[?Name=='$BUCKET']"

aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=DeleteBucket \
  --max-results 3 \
  --query "Events[].{Time:EventTime,User:Username,Action:EventName}" --output table
```

삭제 완료 기준:

- S3 객체 0개
- 대상 버킷 조회 결과 `[]`
- 임시 Trail을 사용했다면 Trail과 로그 버킷도 삭제
- EC2, RDS, Elastic IP, OpenSearch, SageMaker 등 불필요한 리소스 0개
- Billing / Free Tier에서 예상하지 않은 사용량 없음

### 14.10 발표 요구사항 11개 최종 대조표

| # | 발표 요구사항 | 최종 영상 증적 | 합격 기준 |
| ---: | --- | --- | --- |
| 1 | 로컬 VOC_Improve 정상 실행 | 웹 `/healthz`, Control Center | Agent 6/6, HTTP 정상 |
| 2 | pytest 테스트 실행 | 로컬 터미널 | 32 passed |
| 3 | 테스트 결과 보고서 생성 | `aws_upload/qa_evidence` 목록 | 증적 8개와 ZIP 2개 |
| 4 | AWS S3 버킷 생성 | CloudShell `create-bucket` | Location 출력 |
| 5 | QA 결과물 업로드 | `s3 sync`, `s3 cp` | upload 출력과 객체 목록 |
| 6 | 퍼블릭 접근 차단 확인 | `get-public-access-block`, curl | 4개 true, HTTP 403 |
| 7 | 암호화 상태 확인 | 버킷·객체 암호화 조회 | AES256 |
| 8 | CloudShell에서 업로드 파일 조회 | `s3 ls`, 핵심 파일 표 | Judge·점수·판정 파일 확인 |
| 9 | CloudTrail에서 작업 이력 확인 | Event history·lookup-events | 생성·차단·암호화·삭제 확인 |
| 10 | 모든 AWS 리소스 삭제 | 객체 삭제·버킷 삭제·조회 | 객체 0, 버킷 `[]` |
| 11 | oCam 영상 제작 | 완성 MP4 | 커서·클릭·입력·음성·전체 단계 포함 |

### 14.11 oCam 최종 설정과 산출물

| 항목 | 설정 |
| --- | --- |
| 녹화 영역 | 전체 화면 1920×1080 |
| FPS | 30 |
| 코덱 | H.264 MP4 |
| 마이크 | ON |
| 시스템 소리 | OFF |
| 마우스 커서 | 포함 |
| 클릭 효과 | ON |
| 권장 파일명 | `3팀_VOC_Improve_LLM_Judge_웹_AWS_최종시연_20260805.mp4` |

oCam 본 촬영 전에 30초 테스트 영상을 만들고 다음을 확인한다.

- 음성이 전 구간 들림
- 한글과 터미널 글자가 읽힘
- 클릭 위치가 보임
- `.env`, API 키, AWS 계정 ID, 이메일이 노출되지 않음
- 81.2/95, HOLD, 32 passed, 4개 true, AES256, HTTP 403, 리소스 0 장면이 모두 포함됨

### 14.12 웹 시연·녹화 착수 조건

다음 조건이 모두 충족되면 이 최종 시나리오로 실제 웹 시연과 녹화를 시작한다.

- [ ] 사용자가 최종 시나리오 내용을 확인함
- [ ] 로컬 서버와 Agent 6/6 준비
- [ ] 공식 Judge Run과 HOLD 보고서 조회 가능
- [ ] 로컬 pytest·증적 패키지 예행 성공
- [ ] IAM 사용자·Budget·CloudShell 준비
- [ ] AWS 리소스 생성·삭제 권한 확인
- [ ] AWS 계정 ID 등 마스킹 방법 준비
- [ ] oCam 30초 테스트 녹화 성공
- [ ] CloudTrail `PutObject` 데이터 이벤트를 사용할지 여부 결정

이후 실제 진행 순서는 `로컬 웹 시연 → 로컬 pytest·보고서 생성 → AWS 업로드·보안·감사 → 전체 삭제 → 영상 검수`다.
