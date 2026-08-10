# 테스트 계획서

## 1. 테스트 대상
- FastAPI 서비스(`app/main.py`): `/health`, `/ask`, `/metrics`
- 품질평가 파이프라인(`quality/quality_pipeline.py`): 규칙 기반 vs API 기반 챗봇 비교

## 2. 테스트 레벨

| 레벨 | 대상 | 파일 |
|---|---|---|
| Health Test | 서버 정상 기동 여부 | `tests/test_health.py` |
| API Test | 요청/응답 형식 검증 | `tests/test_agent_api.py` |
| Quality Pipeline Test | 테스트케이스 로드·필드 검증 (TODO: Judge mock 추가) | `tests/test_quality_pipeline.py` |
| Negative Test | 빈 질문/짧은 답변/안전성 위반 등 | `tests/test_negative_cases.py` |
| Performance Test | 동시 사용자 부하 시 응답시간·오류율 | `performance/k6_test.js` |
| Monitoring Test | `/metrics` 노출 여부 (TODO: 실제 Prometheus 연동 후 검증) | 수동 확인 |

## 3. 커버리지 갭 (1차 프로젝트에서 이관된 이슈)
`quality/test_cases.json` 기준, `evaluation_criteria.json`의 12개 카테고리 중 다음 카테고리는 테스트케이스가 없어 추가가 필요합니다:
안전성, 안전성 위험 관리, 문서 외 질문, 문서 외 질문 제한, 수료, 수료 기준, 취업지원, 복합 질문.
(특히 안전성 관련 카테고리 누락이 최우선 보강 대상)

## 4. 합격 기준
`ITEM_PASS_THRESHOLD = 85%` (PASS 케이스 수 / 전체 케이스 수 × 100) — 1차 프로젝트 기준과 동일하게 적용.
성능 테스트는 오류율 5% 이하, p95 응답시간 1000ms 이하를 Pass 기준으로 함(LLM 호출 구간은 실측 후 재조정 검토).
