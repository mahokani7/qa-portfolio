from pathlib import Path
import json
import re

import pandas as pd
import requests
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent

LOG_FILE = BASE_DIR / "logs" / "agent.log"
TEST_RESULT_FILE = BASE_DIR / "tests" / "test_result.json"
K6_SUMMARY_FILE = BASE_DIR / "performance" / "k6_summary.json"
K6_REPORT_FILE = BASE_DIR / "performance" / "performance_judgment.md"

API_BASE_URL = "http://127.0.0.1:8001"


st.set_page_config(
    page_title="AI Agent Monitoring Dashboard",
    page_icon="🤖",
    layout="wide"
)


def get_api_response(url: str) -> tuple[bool, dict | str]:
    try:
        response = requests.get(url, timeout=5)

        if response.headers.get("content-type", "").startswith("application/json"):
            return response.ok, response.json()

        return response.ok, response.text

    except requests.RequestException as error:
        return False, str(error)


def get_metric_value(metrics_text: str, metric_name: str) -> float:
    pattern = rf"^{metric_name}(?:\{{.*?\}})?\s+([0-9.eE+-]+)$"

    total = 0.0

    for line in metrics_text.splitlines():
        matched = re.match(pattern, line)

        if matched:
            total += float(matched.group(1))

    return total


def load_json_file(file_path: Path) -> list | dict | None:
    if not file_path.exists():
        return None

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))

    except json.JSONDecodeError:
        return None


def load_text_file(file_path: Path) -> str:
    if not file_path.exists():
        return "파일이 아직 생성되지 않았습니다."

    return file_path.read_text(encoding="utf-8")


def judge_service_status(health_ok: bool) -> tuple[str, str]:
    if health_ok:
        return "정상", "success"

    return "점검 필요", "error"


st.title("🤖 AI Agent 운영·모니터링 대시보드")
st.caption("FastAPI · Prometheus · Grafana · 로그 · 기능 테스트 · k6 성능 테스트 통합 화면")

with st.sidebar:
    st.header("운영 메뉴")

    if st.button("🔄 전체 화면 새로고침", width="stretch"):
        st.rerun()

    st.divider()

    st.subheader("서비스 주소")
    st.code(API_BASE_URL)

    st.subheader("빠른 접속")
    st.link_button("FastAPI API 문서 열기", f"{API_BASE_URL}/docs")
    st.link_button("Prometheus 열기", "http://localhost:9090")
    st.link_button("Grafana 대쉬보드 열기", "http://localhost:3000/d/adl2sjs/efd8be2?orgId=1&from=now-6h&to=now&timezone=browser")

health_ok, health_data = get_api_response(f"{API_BASE_URL}/health")
metrics_ok, metrics_data = get_api_response(f"{API_BASE_URL}/metrics")

service_status, service_status_type = judge_service_status(health_ok)

if metrics_ok and isinstance(metrics_data, str):
    request_total = get_metric_value(metrics_data, "agent_request_total")
    success_total = get_metric_value(metrics_data, "agent_success_total")
    error_total = get_metric_value(metrics_data, "agent_error_total")

else:
    request_total = 0
    success_total = 0
    error_total = 0

error_rate = 0.0

if request_total > 0:
    error_rate = error_total / request_total * 100


metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

metric_col1.metric(
    label="서비스 상태",
    value=service_status
)

metric_col2.metric(
    label="전체 요청 수",
    value=int(request_total)
)

metric_col3.metric(
    label="정상 응답 수",
    value=int(success_total)
)

metric_col4.metric(
    label="오류율",
    value=f"{error_rate:.2f}%"
)


tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "서비스 상태",
        "AI Agent 질문",
        "로그 분석",
        "기능 테스트",
        "성능 테스트"
    ]
)


with tab1:
    st.subheader("서비스 상태 확인")

    if health_ok:
        st.success("AI Agent API가 정상적으로 응답하고 있습니다.")
        st.json(health_data)

    else:
        st.error("AI Agent API에 연결할 수 없습니다.")
        st.code(str(health_data))

    st.subheader("Prometheus 메트릭 상태")

    if metrics_ok:
        st.success("Prometheus 수집용 메트릭이 정상적으로 제공되고 있습니다.")

        metric_df = pd.DataFrame(
            [
                {"지표명": "전체 요청 수", "값": str(int(request_total))},
                {"지표명": "정상 응답 수", "값": str(int(success_total))},
                {"지표명": "오류 발생 수", "값": str(int(error_total))},
                {"지표명": "오류율", "값": f"{error_rate:.2f}%"}
            ]
        )

        st.dataframe(
            metric_df,
            width="stretch",
            hide_index=True
        )

    else:
        st.error("메트릭 정보를 가져오지 못했습니다.")
        st.code(str(metrics_data))


with tab2:
    st.subheader("AI Agent 직접 질문 테스트")

    question = st.text_input(
        "질문 입력",
        value="안녕하세요"
    )

    if st.button("AI Agent에게 질문하기", type="primary"):
        try:
            response = requests.get(
                f"{API_BASE_URL}/ask",
                params={"question": question},
                timeout=15
            )

            if response.status_code == 200:
                st.success("정상 응답")
                st.json(response.json())

            else:
                st.error(f"오류 발생: HTTP {response.status_code}")
                st.json(response.json())

        except requests.RequestException as error:
            st.error("AI Agent 서버 연결 실패")
            st.code(str(error))

    st.info(
        "오류 확인용 문장: 오류를 발생시켜 주세요.  "
        "느린 응답 확인용 문장: 응답을 느리게 만들어 주세요."
    )


with tab3:
    st.subheader("AI Agent 로그 분석")

    log_text = load_text_file(LOG_FILE)

    if "파일이 아직 생성되지 않았습니다." in log_text:
        st.warning(log_text)

    else:
        log_lines = log_text.splitlines()

        info_count = sum("INFO" in line for line in log_lines)
        error_count = sum("ERROR" in line for line in log_lines)

        log_col1, log_col2 = st.columns(2)

        log_col1.metric("INFO 로그 수", info_count)
        log_col2.metric("ERROR 로그 수", error_count)

        level_filter = st.selectbox(
            "로그 수준 선택",
            ["전체", "INFO", "ERROR"]
        )

        filtered_lines = log_lines

        if level_filter != "전체":
            filtered_lines = [
                line for line in log_lines
                if level_filter in line
            ]

        st.code(
            "\n".join(filtered_lines[-100:]),
            language="text"
        )


with tab4:
    st.subheader("자동 기능 테스트 결과")

    test_results = load_json_file(TEST_RESULT_FILE)

    if not test_results:
        st.warning(
            "테스트 결과 파일이 없습니다. "
            "tests 폴더에서 python run_tests.py를 실행하십시오."
        )

    else:
        test_df = pd.DataFrame(test_results)

        pass_count = int(
            (test_df["final_result"] == "PASS").sum()
        )

        fail_count = int(
            (test_df["final_result"] == "FAIL").sum()
        )

        test_col1, test_col2, test_col3 = st.columns(3)

        test_col1.metric("전체 테스트", len(test_df))
        test_col2.metric("PASS", pass_count)
        test_col3.metric("FAIL", fail_count)

        st.dataframe(
            test_df,
            width="stretch",
            hide_index=True
        )


with tab5:
    st.subheader("k6 성능 테스트 결과")

    k6_summary = load_json_file(K6_SUMMARY_FILE)

    if not k6_summary:
        st.warning(
            "k6 결과 파일이 아직 없습니다. "
            "performance 폴더에서 k6 run k6_test.js를 실행하십시오."
        )

    else:
        metrics = k6_summary.get("metrics", {})

        duration_avg = (
            metrics.get("http_req_duration", {})
            .get("values", {})
            .get("avg", 0)
        )

        duration_p95 = (
            metrics.get("http_req_duration", {})
            .get("values", {})
            .get("p(95)", 0)
        )

        failed_rate = (
            metrics.get("http_req_failed", {})
            .get("values", {})
            .get("rate", 0)
            * 100
        )

        k6_col1, k6_col2, k6_col3 = st.columns(3)

        k6_col1.metric(
            "평균 응답시간",
            f"{duration_avg:.2f} ms"
        )

        k6_col2.metric(
            "P95 응답시간",
            f"{duration_p95:.2f} ms"
        )

        k6_col3.metric(
            "오류율",
            f"{failed_rate:.2f}%"
        )

        st.subheader("성능 테스트 판정 보고서")

        report_text = load_text_file(K6_REPORT_FILE)

        st.markdown(report_text)