import json
import sys
import time
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

from core.paths import PROJECT_DIR, REPORTS_DIR


if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from config import GRAFANA_DASHBOARD_URL, GRAFANA_URL, K6_SUMMARY_FILE, PROMETHEUS_URL  # noqa: E402


PROMETHEUS_TIMEOUT_SECONDS = 1.0


def render_ops_monitoring_page():
    snapshot = collect_ops_snapshot()

    st.markdown(
        """
        <div class="section-card">
            <div class="section-title">운영 모니터링</div>
            <p class="section-desc">Prometheus API를 직접 조회해 Golden Signals, 요청 수, 오류율, 응답시간을 현재 프로젝트 화면 스타일로 확인합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_connection_status(snapshot)
    render_monitoring_actions(snapshot)
    render_golden_signals(snapshot)
    render_request_dashboard(snapshot)
    render_traffic_and_errors(snapshot)
    render_duration_distribution(snapshot)
    render_k6_summary(snapshot)


def collect_ops_snapshot():
    prometheus = PrometheusClient(PROMETHEUS_URL)
    prometheus_alive = prometheus.is_available()
    evaluation = load_evaluation_summary()
    k6_summary = load_k6_summary()

    metrics = {}
    if prometheus_alive:
        metrics = {
            "total_requests": prometheus.query_number("sum(increase(http_requests_total[5m]))"),
            "error_requests": prometheus.query_number('sum(increase(http_requests_total{status=~"5..|4.."}[5m]))'),
            "avg_latency": prometheus.query_number("rate(agent_response_seconds_sum[5m]) / rate(agent_response_seconds_count[5m])"),
            "p95_latency": prometheus.query_number(
                "histogram_quantile(0.95, sum(rate(agent_response_seconds_bucket[5m])) by (le))"
            ),
            "service_up": prometheus.query_number("up"),
        }

    fallback_requests = evaluation.get("case_count", 0)
    total_requests = metrics.get("total_requests") if metrics.get("total_requests") is not None else fallback_requests
    error_requests = metrics.get("error_requests") if metrics.get("error_requests") is not None else evaluation.get("failed_count", 0)
    avg_latency = first_number(metrics.get("avg_latency"), k6_summary.get("avg_duration_seconds"))
    p95_latency = first_number(metrics.get("p95_latency"), k6_summary.get("p95_duration_seconds"))
    error_rate = safe_rate(error_requests, total_requests)

    return {
        "prometheus_alive": prometheus_alive,
        "prometheus_url": PROMETHEUS_URL,
        "grafana_url": GRAFANA_URL,
        "grafana_dashboard_url": GRAFANA_DASHBOARD_URL,
        "total_requests": total_requests,
        "success_requests": max(total_requests - error_requests, 0),
        "error_requests": error_requests,
        "error_rate": error_rate,
        "avg_latency": avg_latency,
        "p95_latency": p95_latency,
        "service_up": metrics.get("service_up"),
        "request_series": prometheus.query_range_series("sum(increase(http_requests_total[1m]))") if prometheus_alive else pd.DataFrame(),
        "error_series": prometheus.query_range_series('sum(increase(http_requests_total{status=~"5..|4.."}[1m]))') if prometheus_alive else pd.DataFrame(),
        "duration_series": prometheus.query_range_series(
            "rate(agent_response_seconds_sum[1m]) / rate(agent_response_seconds_count[1m])"
        )
        if prometheus_alive
        else pd.DataFrame(),
        "evaluation": evaluation,
        "k6_summary": k6_summary,
        "duration_distribution": build_duration_distribution(avg_latency, p95_latency, k6_summary),
    }


def render_connection_status(snapshot):
    st.markdown("#### 연결 상태")
    cols = st.columns(3)
    prometheus_status = "연결됨" if snapshot["prometheus_alive"] else "연결 안 됨"
    cols[0].metric("Prometheus", prometheus_status, snapshot["prometheus_url"])
    cols[1].metric("Grafana", "URL 설정됨" if snapshot["grafana_url"] else "설정 없음", snapshot["grafana_url"] or "-")
    cols[2].metric("k6 결과", "로드됨" if snapshot["k6_summary"] else "파일 없음")

    if not snapshot["prometheus_alive"]:
        st.warning("Prometheus 연결 안 됨. 로컬 결과 파일 또는 테스트 실행 결과 기반 대체 값을 표시합니다.")


def render_monitoring_actions(snapshot):
    dashboard_url = snapshot["grafana_dashboard_url"] or snapshot["grafana_url"]
    st.caption("이 화면의 지표는 Streamlit이 Prometheus API를 직접 조회해 표시합니다. 최신 값은 화면을 새로고침하면 다시 조회됩니다.")
    action_cols = st.columns([1, 1, 4])
    with action_cols[0]:
        if st.button("현재 지표 새로고침", use_container_width=True):
            st.rerun()
    with action_cols[1]:
        if dashboard_url:
            st.link_button("Grafana 열기", dashboard_url, use_container_width=True)
        else:
            st.button("Grafana 미설정", disabled=True, use_container_width=True)
    if not dashboard_url:
        st.info("Grafana URL이 설정되지 않았습니다. .env에 GRAFANA_URL 또는 GRAFANA_DASHBOARD_URL을 설정하세요.")


def render_golden_signals(snapshot):
    st.markdown("#### Golden Signals")
    latency_status = classify_latency(snapshot["p95_latency"])
    traffic_status = "정상" if snapshot["total_requests"] else "데이터 없음"
    error_status = classify_error_rate(snapshot["error_rate"])
    saturation_status = "데이터 없음"

    rows = pd.DataFrame(
        [
            {"Signal": "Latency", "현재값": format_seconds(snapshot["p95_latency"]), "상태": latency_status},
            {"Signal": "Traffic", "현재값": f"{snapshot['total_requests']:.0f} req", "상태": traffic_status},
            {"Signal": "Errors", "현재값": f"{snapshot['error_rate']:.2f}%", "상태": error_status},
            {"Signal": "Saturation", "현재값": "추가 메트릭 필요", "상태": saturation_status},
        ]
    )
    st.dataframe(rows, hide_index=True, use_container_width=True)


def render_request_dashboard(snapshot):
    st.markdown("#### 요청 / 오류율 / 응답시간")
    cols = st.columns(6)
    cols[0].metric("총 요청 수", f"{snapshot['total_requests']:.0f}")
    cols[1].metric("성공 요청 수", f"{snapshot['success_requests']:.0f}")
    cols[2].metric("오류 요청 수", f"{snapshot['error_requests']:.0f}")
    cols[3].metric("오류율", f"{snapshot['error_rate']:.2f}%")
    cols[4].metric("평균 응답시간", format_seconds(snapshot["avg_latency"]))
    cols[5].metric("p95 응답시간", format_seconds(snapshot["p95_latency"]))

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("**시간대별 요청 수**")
        render_series_or_info(snapshot["request_series"], "request_rate")
    with chart_col2:
        st.markdown("**응답시간 추이**")
        render_series_or_info(snapshot["duration_series"], "duration_seconds")


def render_traffic_and_errors(snapshot):
    st.markdown("#### 트래픽 & 오류")
    requests_per_minute = snapshot["total_requests"] / 5 if snapshot["total_requests"] else 0
    metric_col, chart_col = st.columns([0.9, 1.6])
    with metric_col:
        row1, row2, row3 = st.container(), st.container(), st.container()
        row1.metric("분당 요청 수", f"{requests_per_minute:.1f}")
        row2.metric("오류 수", f"{snapshot['error_requests']:.0f}")
        row3.metric("서비스 Alive", "정상" if snapshot["service_up"] else "데이터 없음")

    error_series = snapshot["error_series"]
    with chart_col:
        if not error_series.empty:
            st.line_chart(error_series, x="time", y="error_rate", height=210)
        elif not snapshot["request_series"].empty and "time" in snapshot["request_series"].columns:
            zero_error_series = pd.DataFrame(
                {
                    "time": snapshot["request_series"]["time"],
                    "error_rate": 0,
                }
            )
            st.line_chart(zero_error_series, x="time", y="error_rate", height=210)
            st.caption("최근 수집 구간의 4xx/5xx 오류 시계열이 없어 0으로 표시합니다.")
        else:
            st.info("Prometheus 오류 시계열 데이터가 없습니다. HTTP 상태코드별 오류 분포와 Top N 메시지는 추가 로그가 필요합니다.")


def render_duration_distribution(snapshot):
    st.markdown("#### 응답시간 분포")
    distribution = snapshot["duration_distribution"]
    if distribution.empty:
        st.info("응답시간 분포 데이터가 없습니다.")
        return

    section_height = max(170, min(260, 42 + len(distribution) * 35))
    table_col, chart_col = st.columns([0.9, 1.6])
    with table_col:
        st.dataframe(distribution, hide_index=True, use_container_width=True, height=section_height)
    with chart_col:
        st.bar_chart(distribution, x="percentile", y="seconds", height=section_height)


def render_k6_summary(snapshot):
    st.markdown("#### k6 성능 테스트 결과")
    k6_summary = snapshot["k6_summary"]
    if not k6_summary:
        st.info(f"k6 결과 파일이 없습니다: {resolve_k6_summary_path()}")
        return

    failure_rate = k6_summary.get("failure_rate", 0)
    p95 = k6_summary.get("p95_duration_seconds", 0)
    decision = "PASS" if failure_rate <= 1 and p95 <= 2 else "REVIEW" if failure_rate <= 5 and p95 <= 5 else "FAIL"

    cols = st.columns(7)
    cols[0].metric("총 요청 수", f"{k6_summary.get('total_requests', 0):.0f}")
    cols[1].metric("실패율", f"{failure_rate:.2f}%")
    cols[2].metric("평균 응답시간", format_seconds(k6_summary.get("avg_duration_seconds")))
    cols[3].metric("p95 응답시간", format_seconds(p95))
    cols[4].metric("처리량", f"{k6_summary.get('throughput', 0):.2f}/s")
    cols[5].metric("VUs", f"{k6_summary.get('vus', '-')}")
    cols[6].metric("판정", decision)


class PrometheusClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def is_available(self):
        try:
            response = httpx.get(f"{self.base_url}/api/v1/query", params={"query": "up"}, timeout=PROMETHEUS_TIMEOUT_SECONDS)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def query_number(self, query):
        try:
            response = httpx.get(
                f"{self.base_url}/api/v1/query",
                params={"query": query},
                timeout=PROMETHEUS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            result = response.json().get("data", {}).get("result", [])
            if not result:
                return None
            return float(result[0]["value"][1])
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return None

    def query_range_series(self, query):
        try:
            end_time = time.time()
            start_time = end_time - 15 * 60
            response = httpx.get(
                f"{self.base_url}/api/v1/query_range",
                params={"query": query, "start": start_time, "end": end_time, "step": "30s"},
                timeout=PROMETHEUS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            result = response.json().get("data", {}).get("result", [])
            if not result:
                return pd.DataFrame()
            values = result[0].get("values", [])
            rows = [{"time": pd.to_datetime(item[0], unit="s"), query_label(query): float(item[1])} for item in values]
            return pd.DataFrame(rows)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return pd.DataFrame()


def load_evaluation_summary():
    csv_path = REPORTS_DIR / "evaluation_result.csv"
    if not csv_path.exists():
        return {"case_count": 0, "failed_count": 0}

    try:
        dataframe = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError):
        return {"case_count": 0, "failed_count": 0}

    failed_count = 0
    if "rule_passed" in dataframe.columns:
        failed_count = int((dataframe["rule_passed"].astype(str).str.lower() != "true").sum())
    return {"case_count": len(dataframe), "failed_count": failed_count}


def load_k6_summary():
    summary_path = resolve_k6_summary_path()
    if summary_path.exists():
        try:
            with summary_path.open("r", encoding="utf-8") as file:
                return normalize_k6_summary(json.load(file))
        except (OSError, json.JSONDecodeError):
            return {}

    csv_path = REPORTS_DIR / "k6_result.csv"
    if csv_path.exists():
        try:
            dataframe = pd.read_csv(csv_path)
            return normalize_k6_csv(dataframe)
        except (OSError, pd.errors.ParserError):
            return {}
    return {}


def normalize_k6_summary(summary):
    metrics = summary.get("metrics", summary)
    return {
        "total_requests": metric_value(metrics, "http_reqs", "count"),
        "failure_rate": metric_value(metrics, "http_req_failed", "rate") * 100,
        "avg_duration_seconds": metric_value(metrics, "http_req_duration", "avg") / 1000,
        "p95_duration_seconds": metric_value(metrics, "http_req_duration", "p(95)") / 1000,
        "throughput": metric_value(metrics, "http_reqs", "rate"),
        "vus": metric_value(metrics, "vus_max", "value") or metric_value(metrics, "vus", "value"),
        "duration_seconds": metric_value(metrics, "iteration_duration", "avg") / 1000,
        "p50_duration_seconds": metric_value(metrics, "http_req_duration", "med") / 1000,
        "p90_duration_seconds": metric_value(metrics, "http_req_duration", "p(90)") / 1000,
        "p99_duration_seconds": metric_value(metrics, "http_req_duration", "p(99)") / 1000,
        "max_duration_seconds": metric_value(metrics, "http_req_duration", "max") / 1000,
    }


def normalize_k6_csv(dataframe):
    if dataframe.empty:
        return {}
    duration_column = "http_req_duration" if "http_req_duration" in dataframe.columns else None
    durations = pd.to_numeric(dataframe[duration_column], errors="coerce").dropna() / 1000 if duration_column else pd.Series(dtype=float)
    failed = pd.to_numeric(dataframe.get("http_req_failed", pd.Series(dtype=float)), errors="coerce").fillna(0)
    return {
        "total_requests": len(dataframe),
        "failure_rate": float(failed.mean() * 100) if len(failed) else 0,
        "avg_duration_seconds": float(durations.mean()) if len(durations) else 0,
        "p95_duration_seconds": float(durations.quantile(0.95)) if len(durations) else 0,
        "throughput": 0,
        "vus": dataframe["vus"].max() if "vus" in dataframe.columns else "-",
    }


def resolve_k6_summary_path():
    path = Path(K6_SUMMARY_FILE)
    return path if path.is_absolute() else PROJECT_DIR / path


def metric_value(metrics, metric_name, key):
    value = metrics.get(metric_name, {})
    if isinstance(value, dict):
        return float(value.get(key, 0) or 0)
    return 0


def build_duration_distribution(avg_latency, p95_latency, k6_summary):
    rows = []
    percentile_values = {
        "avg": first_number(avg_latency, k6_summary.get("avg_duration_seconds")),
        "p50": k6_summary.get("p50_duration_seconds"),
        "p90": k6_summary.get("p90_duration_seconds"),
        "p95": first_number(p95_latency, k6_summary.get("p95_duration_seconds")),
        "p99": k6_summary.get("p99_duration_seconds"),
        "max": k6_summary.get("max_duration_seconds"),
    }
    for percentile, seconds in percentile_values.items():
        if seconds is not None and seconds > 0:
            rows.append({"percentile": percentile, "seconds": round(float(seconds), 3)})
    return pd.DataFrame(rows)


def classify_error_rate(error_rate):
    if error_rate is None:
        return "데이터 없음"
    if error_rate < 1:
        return "정상"
    if error_rate < 5:
        return "주의"
    return "위험"


def classify_latency(seconds):
    if seconds is None or seconds <= 0:
        return "데이터 없음"
    if seconds >= 5:
        return "위험"
    if seconds >= 2:
        return "주의"
    return "정상"


def safe_rate(part, total):
    return float(part) / float(total) * 100 if total else 0


def first_number(*values):
    for value in values:
        if value is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if numeric >= 0:
                return numeric
    return 0


def format_seconds(value):
    if value is None or value <= 0:
        return "-"
    return f"{float(value):.2f}s"


def render_series_or_info(dataframe, y_column):
    if dataframe.empty or y_column not in dataframe.columns:
        st.info("Prometheus 시계열 데이터가 없습니다.")
        return
    st.line_chart(dataframe, x="time", y=y_column)


def query_label(query):
    if "error" in query or "5.." in query:
        return "error_rate"
    if "response" in query or "duration" in query:
        return "duration_seconds"
    return "request_rate"
