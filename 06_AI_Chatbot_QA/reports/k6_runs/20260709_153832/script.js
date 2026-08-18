import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '10s', target: 20 },
    { duration: '20s', target: 20 },
    { duration: '5s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'],
    http_req_failed: ['rate<0.0100'],
    checks: ['rate>0.9500'],
  },
};

const TARGET_URL = "http://localhost:8000/health";

export default function () {
  const res = http.get(TARGET_URL);
  check(res, {
    'status is 2xx or 3xx': (r) => r.status >= 200 && r.status < 400,
    'body returned': (r) => r.body !== null && r.body.length >= 0,
  });
  sleep(1.0);
}
