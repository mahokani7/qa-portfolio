from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
K6_SUMMARY_PATH = BASE_DIR / "performance" / "k6_summary.json"

DEFAULT_API_URL = "http://127.0.0.1:8001"
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"


st.set_page_config(
    page_title="AI Agent 운영·모니터링",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 2.2rem;
                padding-bottom: 2rem;
                max-width: 1450px;
            }

            [data-testid="stMetric"] {
                background-color: #ffffff;
                border: 1px solid #e6eaf0;
                border-radius: 14px;
                padding: 16px 18px;
                box-shadow: 0 3px 10px rgba(20, 40, 70, 0.05);
            }

            [data-testid="stMetricLabel"] {
                font-size: 0.9rem;
                font-weight: 700;
            }

            .dashboard-title {
                font-size: 2.25rem;
                font-weight: 800;
                margin-bottom: 0.2rem;
            }

            .dashboard-subtitle {
                color: #6c757d;
                font-size: 0.95rem;
                margin-bottom: 1.2rem;
            }

            .status-box {
                border-radius: 14px;
                padding: 18px 20px;
                margin-bottom: 1rem;
                font-size: 1.05rem;
                font-weight: 700;
            }

            .status-normal {
                background-color: #eaf8ef;
                border: 1px solid #b9e2c5;
                color: #136c35;
            }

            .status-warning {
                background-color: #fff7df;
                border: 1px solid #f0d38a;
                color: #8a6200;
            }

            .status-danger {
                background-color: #fff0f0;
                border: 1px solid #f2b8b8;
                color: #a61b1b;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_k6_summary() -> dict:
    if not K6_SUMMARY_PATH.exists():
        return {}

    try:
        return json.loads(K6_SUMMARY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def get_metric_values(k6_data: dict) -> dict:
    metrics = k6_data.get("metrics", {})

    http_duration = metrics.get("http_req_duration", {}).get("values", {})
    http_failed = metrics.get("http_req_failed", {}).get("values", {})
    http_requests = metrics.get("http_reqs", {}).get("values", {})

    average_ms = safe_float(http_duration.get("avg"))
    p95_ms = safe_float(http_duration.get("p(95)"))
    error_rate = safe_float(http_failed.get("rate")) * 100
    request_count = int(safe_float(http_requests.get("count")))

    return {
        "average_ms": average_ms,
        "p95_ms": p95_ms,
        "error_rate": error_rate,
        "request_count": request_count,
    }


def check_api_health(api_url: str) -> tuple[bool, str]:
    try:
        response = requests.get(
            f"{api_url.rstrip('/')}/health",
            timeout=3,
        )

        if response.status_code == 200:
            return True, "정상"

        return False, f"응답 코드 {response.status_code}"

    except requests.RequestException:
        return False, "연결 실패"


def get_status_info(
    api_connected: bool,
    error_rate: float,
    p95_ms: float,
) -> tuple[str, str, str]:
    if not api_connected:
        return (
            "🔴 장애",
            "status-danger",
            "FastAPI 서버에 연결할 수 없습니다. 서버 실행 상태를 확인하세요.",
        )

    if error_rate >= 5 or p95_ms >= 3000:
        return (
            "🔴 장애",
            "status-danger",
            "오류율 또는 응답시간이 기준을 크게 초과했습니다.",
        )

    if error_rate >= 1 or p95_ms >= 1000:
        return (
            "🟡 주의",
            "status-warning",
            "서비스는 동작하지만 성능 점검이 필요합니다.",
        )

    return (
        "🟢 정상",
        "status-normal",
        "AI Agent 서비스가 정상적으로 운영 중입니다.",
    )


def create_demo_response_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "시간": ["10:00", "10:01", "10:02", "10:03", "10:04", "10:05"],
            "응답시간(ms)": [8.4, 7.9, 9.2, 7.4, 8.1, 7.8],
        }
    )


def render_k6_report(
    average_ms: float,
    p95_ms: float,
    error_rate: float,
    request_count: int,
) -> None:
    avg_result = "PASS" if average_ms <= 1000 else "FAIL"
    p95_result = "PASS" if p95_ms <= 2000 else "FAIL"
    error_result = "PASS" if error_rate <= 1 else "FAIL"
    total_result = (
        "PASS"
        if avg_result == "PASS"
        and p95_result == "PASS"
        and error_result == "PASS"
        else "FAIL"
    )

    report_df = pd.DataFrame(
        [
            {
                "평가 항목": "평균 응답시간",
                "측정값": f"{average_ms:.2f} ms",
                "기준": "1,000 ms 이하",
                "판정": avg_result,
            },
            {
                "평가 항목": "P95 응답시간",
                "측정값": f"{p95_ms:.2f} ms",
                "기준": "2,000 ms 이하",
                "판정": p95_result,
            },
            {
                "평가 항목": "오류율",
                "측정값": f"{error_rate:.2f}%",
                "기준": "1% 이하",
                "판정": error_result,
            },
            {
                "평가 항목": "전체 요청 수",
                "측정값": f"{request_count}건",
                "기준": "테스트 완료",
                "판정": "PASS",
            },
        ]
    )

    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True,
    )

    if total_result == "PASS":
        st.success(
            "최종 판정: PASS — 현재 AI Agent는 설정된 성능 기준을 충족합니다."
        )
    else:
        st.error(
            "최종 판정: FAIL — 오류율 또는 응답시간이 성능 기준을 초과했습니다."
        )


def main() -> None:
    apply_custom_style()

    with st.sidebar:
        st.header("⚙️ 운영 메뉴")

        if st.button("🔄 전체 화면 새로고침", use_container_width=True):
            st.rerun()

        st.divider()

        st.subheader("서비스 연결")
        api_url = st.text_input(
            "FastAPI 주소",
            value=DEFAULT_API_URL,
        )

        st.divider()

        st.subheader("빠른 접속")

        st.link_button(
            "📘 FastAPI API 문서",
            f"{api_url.rstrip('/')}/docs",
            use_container_width=True,
        )

        st.link_button(
            "📊 Prometheus 열기",
            PROMETHEUS_URL,
            use_container_width=True,
        )

        st.link_button(
            "📈 Grafana 열기",
            GRAFANA_URL,
            use_container_width=True,
        )

        st.divider()

        st.caption("k6 결과 파일 위치")
        st.code("performance/results/k6_summary.json")

    api_connected, api_message = check_api_health(api_url)

    k6_data = load_k6_summary()
    metric_values = get_metric_values(k6_data)

    average_ms = metric_values["average_ms"]
    p95_ms = metric_values["p95_ms"]
    error_rate = metric_values["error_rate"]
    request_count = metric_values["request_count"]

    status_label, status_class, status_message = get_status_info(
        api_connected=api_connected,
        error_rate=error_rate,
        p95_ms=p95_ms,
    )

    success_count = max(
        request_count - round(request_count * (error_rate / 100)),
        0,
    )
    success_rate = 100 - error_rate

    title_col, time_col = st.columns([5, 1])

    with title_col:
        st.markdown(
            '<div class="dashboard-title">🤖 AI Agent 운영·모니터링 대시보드</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="dashboard-subtitle">'
            "FastAPI · Prometheus · Grafana · 로그 · 기능 테스트 · k6 성능 테스트 통합 화면"
            "</div>",
            unsafe_allow_html=True,
        )

    with time_col:
        st.caption("마지막 화면 갱신")
        st.write(datetime.now().strftime("%H:%M:%S"))

    st.markdown(
        f'<div class="status-box {status_class}">{status_label} · {status_message}</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "서비스 상태",
            "정상" if api_connected else "연결 실패",
            api_message,
        )

    with col2:
        st.metric(
            "전체 요청 수",
            f"{request_count:,}건",
        )

    with col3:
        st.metric(
            "정상 응답 수",
            f"{success_count:,}건",
            f"성공률 {success_rate:.2f}%",
        )

    with col4:
        st.metric(
            "오류율",
            f"{error_rate:.2f}%",
            delta_color="inverse",
        )

    with col5:
        st.metric(
            "P95 응답시간",
            f"{p95_ms:.2f} ms",
            delta_color="inverse",
        )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📡 실시간 상태",
            "🤖 AI Agent 질문",
            "📋 로그 분석",
            "✅ 기능 테스트",
            "⚡ 성능 테스트",
        ]
    )

    with tab1:
        st.subheader("서비스 연결 상태")

        service_df = pd.DataFrame(
            [
                {
                    "구성 요소": "FastAPI",
                    "상태": "정상" if api_connected else "연결 실패",
                    "주소": api_url,
                },
                {
                    "구성 요소": "Prometheus",
                    "상태": "접속 링크 제공",
                    "주소": PROMETHEUS_URL,
                },
                {
                    "구성 요소": "Grafana",
                    "상태": "접속 링크 제공",
                    "주소": GRAFANA_URL,
                },
                {
                    "구성 요소": "k6 성능 결과",
                    "상태": "불러옴" if k6_data else "결과 파일 없음",
                    "주소": str(K6_SUMMARY_PATH),
                },
            ]
        )

        st.dataframe(
            service_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        st.subheader("AI Agent 질문 테스트")

        question = st.text_input(
            "AI Agent에게 질문",
            placeholder="예: AI Agent 운영 모니터링이 무엇인가요?",
        )

        if st.button("질문 전송", type="primary"):
            if not question.strip():
                st.warning("질문 내용을 입력하세요.")
            else:
                try:
                    response = requests.get(
                        f"{api_url.rstrip('/')}/ask",
                        params={"question": question.strip()},
                        timeout=10,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        st.success("정상 응답을 받았습니다.")
                        st.write(result.get("answer", "답변 내용이 없습니다."))
                        st.caption(
                            f"응답시간: {result.get('response_seconds', 0)}초"
                        )
                    else:
                        st.error(
                            f"요청 실패: HTTP {response.status_code}"
                        )
                        st.code(response.text)

                except requests.RequestException as error:
                    st.error(f"FastAPI 요청 중 오류가 발생했습니다: {error}")

    with tab3:
        st.subheader("로그 분석")

        st.info(
            "현재 단계에서는 FastAPI 콘솔 로그와 Prometheus 지표를 중심으로 확인합니다."
        )

        st.markdown(
            """
            **확인할 주요 항목**

            - 정상 응답 로그
            - 입력값 검증 오류
            - AI Agent 처리 오류
            - 응답시간 증가 여부
            - 오류 발생 시각과 반복 패턴
            """
        )

    with tab4:
        st.subheader("기능 테스트 결과")

        test_df = pd.DataFrame(
            [
                {
                    "테스트 항목": "헬스체크 API",
                    "기대 결과": "healthy 응답",
                    "현재 상태": "PASS" if api_connected else "CHECK",
                },
                {
                    "테스트 항목": "AI Agent 질문",
                    "기대 결과": "정상 답변 반환",
                    "현재 상태": "수동 실행 필요",
                },
                {
                    "테스트 항목": "Prometheus Metrics",
                    "기대 결과": "/metrics 지표 노출",
                    "현재 상태": "확인 필요",
                },
            ]
        )

        st.dataframe(
            test_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab5:
        st.subheader("⚡ k6 성능 테스트 결과")

        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)

        with perf_col1:
            st.metric("평균 응답시간", f"{average_ms:.2f} ms")

        with perf_col2:
            st.metric("P95 응답시간", f"{p95_ms:.2f} ms")

        with perf_col3:
            st.metric("오류율", f"{error_rate:.2f}%")

        with perf_col4:
            result_label = (
                "PASS"
                if error_rate <= 1 and p95_ms <= 2000
                else "CHECK"
            )
            st.metric("최종 판정", result_label)

        if not k6_data:
            st.warning(
                "k6 결과 파일을 아직 찾을 수 없습니다. "
                "성능 테스트 실행 후 JSON 결과를 생성하세요."
            )

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.caption("응답시간 추세 예시")
            st.line_chart(
                create_demo_response_data(),
                x="시간",
                y="응답시간(ms)",
            )

        with chart_col2:
            st.caption("요청 처리 현황")
            request_df = pd.DataFrame(
                {
                    "구분": ["정상 응답", "오류 응답"],
                    "건수": [
                        success_count,
                        max(request_count - success_count, 0),
                    ],
                }
            )
            st.bar_chart(
                request_df,
                x="구분",
                y="건수",
            )

        with st.expander("📄 성능 테스트 판정 보고서 보기", expanded=False):
            render_k6_report(
                average_ms=average_ms,
                p95_ms=p95_ms,
                error_rate=error_rate,
                request_count=request_count,
            )


if __name__ == "__main__":
    main()

