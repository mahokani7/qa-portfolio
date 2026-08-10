import pandas as pd
import streamlit as st

from services.k6_service import (
    K6RunSettings,
    get_k6_version,
    is_k6_available,
    load_recent_runs,
    run_k6_test,
)


def render_k6_runner_page():
    st.markdown(
        """
        <div class="section-card">
            <div class="section-title">k6 성능 테스트 실행</div>
            <p class="section-desc">화면에서 부하 조건을 조정하고 k6를 실행한 뒤 결과를 보고서 부록에 연결합니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    available = is_k6_available()
    version = get_k6_version()
    if available:
        st.success(f"k6 실행 가능: {version or 'version 확인됨'}")
    else:
        st.warning("k6 실행 파일을 찾을 수 없습니다. k6 설치 후 터미널을 새로 열고 다시 실행해주세요.")

    settings = render_settings_form()

    run_col, hint_col = st.columns([0.28, 0.72])
    with run_col:
        run_clicked = st.button("k6 실행", type="primary", use_container_width=True, disabled=not available)
    with hint_col:
        st.caption("실행 결과는 reports/k6_runs에 저장되고 최신 결과는 reports/k6_summary.json으로 갱신됩니다.")

    if run_clicked:
        run_and_render_result(settings)

    render_recent_runs()


def render_settings_form():
    st.markdown("#### 실행 설정")
    target_url = st.text_input(
        "대상 URL",
        value=st.session_state.get("k6_target_url", "http://localhost:8000/health"),
        help="예: http://localhost:8000/health 또는 http://localhost:8000/ask?question=...",
    )
    st.session_state.k6_target_url = target_url

    load_col, time_col, threshold_col = st.columns(3)
    with load_col:
        vus = st.slider("동시 사용자 수", min_value=1, max_value=200, value=20, step=1)
        think_time = st.slider("요청 간 대기시간(초)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    with time_col:
        duration_seconds = st.slider("총 테스트 시간(초)", min_value=10, max_value=600, value=60, step=10)
        ramp_up_seconds = st.slider("Ramp-up 시간(초)", min_value=0, max_value=300, value=10, step=5)
    with threshold_col:
        p95_threshold_ms = st.slider("p95 응답시간 기준(ms)", min_value=100, max_value=30000, value=3000, step=100)
        failure_rate_threshold_pct = st.slider("실패율 기준(%)", min_value=0.0, max_value=50.0, value=1.0, step=0.1)
        checks_threshold_pct = st.slider("체크 성공률 기준(%)", min_value=50.0, max_value=100.0, value=95.0, step=0.5)

    return K6RunSettings(
        target_url=target_url.strip(),
        vus=vus,
        duration_seconds=duration_seconds,
        ramp_up_seconds=min(ramp_up_seconds, max(duration_seconds - 1, 0)),
        p95_threshold_ms=p95_threshold_ms,
        failure_rate_threshold_pct=failure_rate_threshold_pct,
        checks_threshold_pct=checks_threshold_pct,
        think_time_seconds=think_time,
    )


def run_and_render_result(settings):
    try:
        with st.spinner("k6 성능 테스트 실행 중입니다..."):
            result = run_k6_test(settings)
    except ValueError as exc:
        st.error(str(exc))
        return

    if result.get("ok"):
        st.success("k6 성능 테스트가 완료되었습니다.")
    else:
        st.error(result.get("error") or "k6 실행 중 오류가 발생했습니다.")

    render_result_summary(result)

    with st.expander("실행 로그", expanded=not result.get("ok")):
        stdout = result.get("stdout") or ""
        stderr = result.get("stderr") or ""
        if stdout:
            st.code(stdout, language="text")
        if stderr:
            st.code(stderr, language="text")
        if not stdout and not stderr:
            st.caption("표시할 로그가 없습니다.")


def render_result_summary(result):
    summary = result.get("summary") or {}
    if not summary:
        st.info("k6 요약 결과가 아직 생성되지 않았습니다.")
        return

    decision = decide_result(summary, result.get("settings", {}))
    cols = st.columns(7)
    cols[0].metric("총 요청", format_number(summary.get("total_requests")))
    cols[1].metric("실패율", f"{summary.get('failure_rate', 0):.2f}%")
    cols[2].metric("평균 응답", format_seconds(summary.get("avg_duration_seconds")))
    cols[3].metric("p95 응답", format_seconds(summary.get("p95_duration_seconds")))
    cols[4].metric("처리량", f"{summary.get('throughput', 0):.2f}/s")
    cols[5].metric("체크 성공률", f"{summary.get('checks_rate', 0):.2f}%")
    cols[6].metric("판정", decision)

    rows = pd.DataFrame(
        [
            {"항목": "실행 ID", "값": result.get("run_id", "-")},
            {"항목": "결과 파일", "값": result.get("summary_path", "-")},
            {"항목": "대상 URL", "값": result.get("settings", {}).get("target_url", "-")},
        ]
    )
    st.dataframe(rows, hide_index=True, use_container_width=True)


def render_recent_runs():
    st.markdown("#### 최근 k6 수행이력")
    records = load_recent_runs(limit=10)
    if not records:
        st.info("아직 k6 수행이력이 없습니다.")
        return

    rows = []
    for record in records:
        summary = record.get("summary") or {}
        settings = record.get("settings") or {}
        rows.append(
            {
                "실행시각": record.get("created_at", ""),
                "대상 URL": settings.get("target_url", ""),
                "VUs": settings.get("vus", ""),
                "시간(초)": settings.get("duration_seconds", ""),
                "요청 수": int(summary.get("total_requests", 0) or 0),
                "실패율": f"{summary.get('failure_rate', 0):.2f}%",
                "p95": format_seconds(summary.get("p95_duration_seconds")),
                "판정": decide_result(summary, settings),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def decide_result(summary, settings):
    failure_rate = float(summary.get("failure_rate", 0) or 0)
    p95_seconds = float(summary.get("p95_duration_seconds", 0) or 0)
    checks_rate = float(summary.get("checks_rate", 0) or 0)
    p95_limit = float(settings.get("p95_threshold_ms", 3000) or 3000) / 1000
    failure_limit = float(settings.get("failure_rate_threshold_pct", 1.0) or 1.0)
    checks_limit = float(settings.get("checks_threshold_pct", 95.0) or 95.0)

    if failure_rate <= failure_limit and p95_seconds <= p95_limit and checks_rate >= checks_limit:
        return "PASS"
    return "FAIL"


def format_seconds(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "-"
    if numeric <= 0:
        return "-"
    return f"{numeric:.2f}s"


def format_number(value):
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "0"
