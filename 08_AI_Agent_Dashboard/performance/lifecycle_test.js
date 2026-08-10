import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 3,
  duration: "10s",
};

export function setup() {
  console.log("1. setup() 실행: 테스트 시작 전 서버 상태 확인");

  const response = http.get("http://127.0.0.1:8001/health");

  check(response, {
    "health API 상태코드가 200인가": (res) => res.status === 200,
  });

  return {
    baseUrl: "http://127.0.0.1:8001",
    testName: "k6 라이프사이클 실습",
  };
}

export default function (data) {
  const response = http.get(`${data.baseUrl}/health`);

  check(response, {
    "VU 요청 성공": (res) => res.status === 200,
  });

  sleep(1);
}

export function teardown(data) {
  console.log(`4. teardown() 실행: ${data.testName} 종료`);
}

export function handleSummary(data) {
  return {
    "performance/lifecycle_summary.json": JSON.stringify(data, null, 2),
  };
}