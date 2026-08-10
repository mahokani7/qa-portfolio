# 이 파일은 k6_summary.json을 읽고, 
# 교육생이 제출할 수 있는 성능 테스트 판정 보고서인 
# performance_judgment.md를 자동 생성합니다.
import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

SUMMARY_FILE = BASE_DIR / "k6_summary.json"
REPORT_FILE = BASE_DIR / "performance_judgment.md"


P95_STANDARD_MS = 3000
ERROR_RATE_STANDARD_PERCENT = 5.0


def load_summary() -> dict:
    if not SUMMARY_FILE.exists():
        raise FileNotFoundError(
            "k6_summary.json 파일이 없습니다. "
            "먼저 k6 성능 테스트를 실행하십시오."
        )

    return json.loads(
        SUMMARY_FILE.read_text(encoding="utf-8")
    )


def get_metric_value(
    metrics: dict,
    metric_name: str,
    value_name: str,
    default: float = 0.0
) -> float:
    return (
        metrics.get(metric_name, {})
        .get("values", {})
        .get(value_name, default)
    )


def judge_p95(p95_ms: float) -> tuple[str, str]:
    if p95_ms < P95_STANDARD_MS:
        return "PASS", "P95 응답시간이 기준 이내입니다."

    return "FAIL", "P95 응답시간이 기준을 초과했습니다."


def judge_error_rate(error_rate_percent: float) -> tuple[str, str]:
    if error_rate_percent < ERROR_RATE_STANDARD_PERCENT:
        return "PASS", "오류율이 기준 이내입니다."

    return "FAIL", "오류율이 기준을 초과했습니다."


def create_final_judgment(
    p95_result: str,
    error_result: str
) -> tuple[str, str]:
    if p95_result == "PASS" and error_result == "PASS":
        return (
            "적합",
            "현재 설정된 성능 기준을 모두 만족했습니다."
        )

    return (
        "개선 필요",
        "일부 성능 기준을 만족하지 못했으므로 원인 분석과 개선이 필요합니다."
    )


def create_markdown_report(summary: dict) -> str:
    metrics = summary.get("metrics", {})

    avg_response_ms = get_metric_value(
        metrics,
        "http_req_duration",
        "avg"
    )

    p95_response_ms = get_metric_value(
        metrics,
        "http_req_duration",
        "p(95)"
    )

    max_response_ms = get_metric_value(
        metrics,
        "http_req_duration",
        "max"
    )

    error_rate = (
        get_metric_value(
            metrics,
            "http_req_failed",
            "rate"
        )
        * 100
    )

    request_count = get_metric_value(
        metrics,
        "http_reqs",
        "count"
    )

    iteration_count = get_metric_value(
        metrics,
        "iterations",
        "count"
    )

    p95_result, p95_comment = judge_p95(p95_response_ms)

    error_result, error_comment = judge_error_rate(error_rate)

    final_result, final_comment = create_final_judgment(
        p95_result,
        error_result
    )

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return f"""# AI Agent 성능 테스트 판정 보고서

## 1. 테스트 개요

| 항목 | 내용 |
|---|---|
| 테스트 도구 | k6 |
| 테스트 일시 | {created_at} |
| 대상 서비스 | AI Agent FastAPI API |
| 테스트 URL | http://127.0.0.1:8001/ask |
| 가상 사용자 | 5명 |
| 테스트 시간 | 20초 |

---

## 2. 성능 측정 결과

| 측정 항목 | 측정값 |
|---|---:|
| 전체 요청 수 | {request_count:.0f}건 |
| 전체 반복 수 | {iteration_count:.0f}회 |
| 평균 응답시간 | {avg_response_ms:.2f} ms |
| P95 응답시간 | {p95_response_ms:.2f} ms |
| 최대 응답시간 | {max_response_ms:.2f} ms |
| 오류율 | {error_rate:.2f}% |

---

## 3. 성능 기준 및 판정

| 품질 기준 | 기준값 | 측정값 | 판정 |
|---|---:|---:|---|
| P95 응답시간 | {P95_STANDARD_MS:,} ms 미만 | {p95_response_ms:.2f} ms | {p95_result} |
| 오류율 | {ERROR_RATE_STANDARD_PERCENT:.2f}% 미만 | {error_rate:.2f}% | {error_result} |

---

## 4. 세부 판정 의견

### P95 응답시간

- 판정: **{p95_result}**
- 의견: {p95_comment}

### 오류율

- 판정: **{error_result}**
- 의견: {error_comment}

---

## 5. 종합 판정

### 최종 결과: **{final_result}**

{final_comment}

---

## 6. 개선 권고사항

| 상황 | 권고 조치 |
|---|---|
| 응답시간이 길어지는 경우 | Agent 처리 로직, 외부 API 호출 시간, 네트워크 상태를 확인한다. |
| 오류율이 증가하는 경우 | 오류 로그를 확인하고 예외 처리, 입력값 검증, 재시도 로직을 점검한다. |
| 동시 사용자 증가 시 성능 저하 | 서버 자원, API 호출 제한, 캐시 적용, 비동기 처리 방식을 검토한다. |
| 반복 장애 발생 | 테스트 케이스를 추가하고 자동 성능 테스트를 정기 실행한다. |
"""


def save_report(report_text: str) -> None:
    REPORT_FILE.write_text(
        report_text,
        encoding="utf-8"
    )


def main() -> None:
    summary = load_summary()

    report_text = create_markdown_report(summary)

    save_report(report_text)


if __name__ == "__main__":
    main()