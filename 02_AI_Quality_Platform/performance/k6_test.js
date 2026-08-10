// k6 부하테스트 스크립트
// 실행: k6 run performance/k6_test.js
// 전제: app/main.py(FastAPI)가 http://localhost:8000 에 uvicorn으로 떠 있어야 함
//   uvicorn app.main:app --host 0.0.0.0 --port 8000

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 10,          // 가상 사용자 수 (동시 접속자)
  duration: "30s",   // 테스트 지속 시간
  thresholds: {
    http_req_failed: ["rate<0.05"],       // 오류율 5% 미만
    http_req_duration: ["p(95)<1000"],    // p95 응답시간 1000ms 미만
  },
};

const BASE_URL = "http://localhost:8000";

export default function () {
  const healthRes = http.get(`${BASE_URL}/health`);
  check(healthRes, { "health status is 200": (r) => r.status === 200 });

  const payload = JSON.stringify({
    question: "지각을 세 번 하면 어떻게 되나요?",
    use_rule_based: true, // 부하테스트 단계에서는 OpenAI 비용 없이 규칙 기반 경로로 측정
  });
  const params = { headers: { "Content-Type": "application/json" } };

  const askRes = http.post(`${BASE_URL}/ask`, payload, params);
  check(askRes, { "ask status is 200": (r) => r.status === 200 });

  sleep(1);
}
