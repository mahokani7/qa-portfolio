// 이 코드는 다음을 수행합니다.

// 가상 사용자 5명 실행
// 20초간 API 호출
// P95 응답시간 3초 미만인지 판정
// 오류율 5% 미만인지 판정
// 결과를 k6_summary.json으로 저장
import http from "k6/http";
import { check, sleep } from "k6";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.4/index.js";


export const options = {
    vus: 5,
    duration: "20s",

    thresholds: {
        http_req_duration: ["p(95)<3000"],
        http_req_failed: ["rate<0.05"]
    }
};


export default function () {
    const question = encodeURIComponent("안녕하세요");

    const response = http.get(
        `http://127.0.0.1:8001/ask?question=${question}`
    );

    check(response, {
        "응답 상태가 200인가": (res) => res.status === 200,
        "응답시간이 3초 미만인가": (res) => res.timings.duration < 3000
    });

    sleep(1);
}


export function handleSummary(data) {
    return {
        stdout: textSummary(data, { indent: " ", enableColors: true }),

        "performance/k6_summary.json": JSON.stringify(
            data,
            null,
            2
        )
    };
}

// k6의 thresholds는 성능 기준을 정의하고, 종료 결과에서 성공·실패로 확인할 수 있습니다. 
// handleSummary()는 종료 시점의 집계 결과를 파일로 저장하는 용도로 사용할 수 있습니다.