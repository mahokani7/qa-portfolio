# 성능 테스트 보고서

## 실행 방법

### (1) 기본 실행 — 결과를 터미널에 출력
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
k6 run performance/k6_test.js
```

### (2) Grafana 연동 실행 — k6 결과를 Prometheus로 보내 Grafana에서 시각화
Docker 스택(app+prometheus+grafana)이 떠 있는 상태에서 (Prometheus는 remote-write 수신 활성화됨):
```bash
# PowerShell
$env:K6_PROMETHEUS_RW_SERVER_URL="http://localhost:9090/api/v1/write"
$env:K6_PROMETHEUS_RW_TREND_STATS="p(95),p(99),avg,max"
k6 run -o experimental-prometheus-rw performance/k6_test.js
```
실행 후 Grafana에서 확인:
- **k6 성능 대시보드**: http://localhost:3000/d/k6-performance  (admin/admin)
- 총 요청수 / 오류율 / p95 응답시간 / VUs / 응답시간 추이 / 초당 요청률 패널 제공

## 결과 (실측 예시 — 2026-07-07)

| 도구 | 총 요청 | 오류율 | 평균(ms) | p95(ms) | 판정 |
|---|---|---|---|---|---|
| k6 (10 VUs, 30s) | 600 | 0.00% | 약 10~40 | 13~21 | **Pass** |

## 판정 기준
오류율 5% 이하, p95 응답시간 1000ms 이하이면 Pass. LLM API 호출(judge_agent, service_agent)이 포함된 구간은
지연이 클 수 있어 실측 후 기준 재조정 여부를 검토합니다. 부하테스트 자체는 비용 절감을 위해 규칙 기반 경로
(`use_rule_based: true`)로 우선 측정합니다.

## 성능 개선 의견 (실측 후 기재)
- 예상 병목: LLM API 호출, ChromaDB 검색
- 개선 후보: 응답 캐싱, 비동기 처리, 배치 평가화
