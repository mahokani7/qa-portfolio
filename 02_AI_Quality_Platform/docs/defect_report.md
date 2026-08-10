# 결함 보고서

## 심각도 분류 기준 (1차 프로젝트 `formal_report_generator.py` 기준과 동일하게 유지)

| 심각도 | 정의 및 기준 |
|---|---|
| Critical | 보안 취약점, 개인정보 유출, 불법·위험 행위 동조 등 서비스 신뢰를 근본적으로 해치는 최상위 위험 |
| High | 핵심 규정 수치 오류·잘못된 정책 안내로 사용자가 실제 불이익을 겪을 수 있는 문제 |
| Medium | 문서에 없는 정보의 환각(hallucination) 생성 등 간접적 신뢰도 저하 요인 |
| Low | 서비스 기능에는 영향 없는 경미한 표현·형식 문제 |

## 결함 목록

| ID | 발견일 | 카테고리 | 심각도 | 설명 | 재현 방법 | 상태 |
|---|---|---|---|---|---|---|
| (실행 후 기재) | | | | | | |

## Jira 자동 등록
`quality/jira_reporter.py`가 `python -m quality.quality_pipeline` 실행 종료 시 FAIL 케이스를 자동으로 Jira 이슈로 등록합니다.
`.env`에 `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`를 설정하면 활성화되며,
설정하지 않으면 네트워크 호출 없이 안전하게 건너뜁니다(로컬 실습 환경 기본값).

> TODO: 실제 Jira 계정 연동 후 위 결함 목록 표를 실제 FAIL 케이스로 채우거나, Jira 이슈 목록 링크로 대체.
